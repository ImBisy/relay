"""Calendar tool — backed by SQLite via CalendarStore."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from datetime import time as dt_time
from typing import Any, Dict, List, Optional, Tuple

from ..core.context import ToolContext
from ..core.safety import SafetyLevel
from ..storage import CalendarStore
from ..storage.models import CalendarEvent
from .base import BaseTool, ToolResult


_TIME_PATTERNS = {
    "today": 0,
    "tomorrow": 1,
    "next week": 7,
    "in a week": 7,
    "in two weeks": 14,
}

_DAY_PATTERNS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

_TIME_OF_DAY = {
    "morning": (9, 0),
    "afternoon": (14, 0),
    "evening": (18, 0),
    "night": (20, 0),
    "noon": (12, 0),
    "midnight": (0, 0),
}


class CalendarTool(BaseTool):
    name = "calendar"
    aliases = ["events", "schedule"]
    description = "Manage calendar events and view schedule"
    requires_confirmation = False
    safety_level = SafetyLevel.REVERSIBLE
    supported_actions = ["add", "view", "delete"]

    def __init__(self, store: Optional[CalendarStore] = None) -> None:
        self.store = store

    def execute(self, args: Dict[str, Any], ctx: Optional[ToolContext] = None) -> ToolResult:
        store = self._resolve_store(ctx)
        action = args.get("calendar_action", "add")
        if action == "view" or "view" in args.get("intent", ""):
            return self._view(args, store)
        return self._add(args, store, ctx)

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        action = args.get("calendar_action", "add")
        if action == "view":
            return True, None
        if not (args.get("event_title") or args.get("content")):
            return False, "Event title required"
        return True, None

    def preview(self, args: Dict[str, Any]) -> str:
        title = args.get("event_title") or args.get("content") or "event"
        return f"Calendar: {title}"

    def _resolve_store(self, ctx: Optional[ToolContext]) -> CalendarStore:
        if ctx and ctx.calendar is not None:
            return ctx.calendar
        if self.store is not None:
            return self.store
        return CalendarStore()

    def _add(self, args: Dict[str, Any], store: CalendarStore,
             ctx: Optional[ToolContext]) -> ToolResult:
        ok, error = self.validate(args)
        if not ok:
            return ToolResult.failure(f"Invalid event: {error}")

        title = args.get("event_title") or args.get("content") or "Untitled Event"
        start, end = self._parse_datetime(args)
        if start is None:
            return ToolResult.needs_confirmation(
                "When would you like to schedule this?",
                prompt=f"Schedule '{title}' for when?",
                data={"title": title},
            )

        event = CalendarEvent(
            id=CalendarStore.new_id(),
            title=title,
            description=args.get("description"),
            location=args.get("location"),
            start_time=start.isoformat(timespec="seconds"),
            end_time=end.isoformat(timespec="seconds") if end else None,
            source=ctx.source if ctx else None,
        )
        store.create(event)

        time_str = start.strftime("%I:%M %p")
        date_str = start.strftime("%A, %B %d")
        return ToolResult.success(
            f"Scheduled '{title}' for {date_str} at {time_str}",
            data={"event_id": event.id, "title": title, "datetime": event.start_time},
            preview=self.preview({"event_title": title}),
        )

    def _view(self, args: Dict[str, Any], store: CalendarStore) -> ToolResult:
        text = (args.get("raw_input") or args.get("content") or "").lower()
        now = datetime.now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        if "tomorrow" in text:
            start = start + timedelta(days=1)
            end = start + timedelta(days=1)
        elif "this week" in text:
            end = start + timedelta(days=7)
        elif "next week" in text:
            start = start + timedelta(days=7)
            end = start + timedelta(days=7)

        events = store.list_in_range(
            start.isoformat(timespec="seconds"),
            end.isoformat(timespec="seconds"),
        )
        if not events:
            return ToolResult.success("Your calendar is clear for that period.",
                                       data={"events": []})
        formatted: List[str] = []
        for e in events:
            try:
                dt = datetime.fromisoformat(e.start_time)
                formatted.append(f"{dt.strftime('%I:%M %p')}: {e.title}")
            except ValueError:
                formatted.append(e.title)
        return ToolResult.success(
            f"You have {len(events)} event(s):",
            data={"events": formatted, "items": [e.to_public() for e in events]},
        )

    def _parse_datetime(self, args: Dict[str, Any]) -> Tuple[Optional[datetime], Optional[datetime]]:
        text_parts = [str(args.get("content", "")), str(args.get("raw_input", ""))]
        text = " ".join(text_parts).lower()
        now = datetime.now()
        target_date = now.date()
        target_time: Optional[Tuple[int, int]] = None
        duration_minutes = 60

        for pattern, days in _TIME_PATTERNS.items():
            if pattern in text:
                target_date = now.date() + timedelta(days=days)
                break
        for day_name, day_num in _DAY_PATTERNS.items():
            if day_name in text:
                days_ahead = day_num - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                target_date = now.date() + timedelta(days=days_ahead)
                break
        for tod, (hour, minute) in _TIME_OF_DAY.items():
            if tod in text:
                target_time = (hour, minute)
                break

        time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", text)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            ampm = time_match.group(3)
            if ampm == "pm" and hour != 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            target_time = (hour, minute)
        else:
            time_match = re.search(r"(\d{1,2}):(\d{2})", text)
            if time_match:
                target_time = (int(time_match.group(1)), int(time_match.group(2)))

        duration_match = re.search(r"for\s+(\d+)\s*(min|minute|minutes|hour|hours|hr)?", text)
        if duration_match:
            amount = int(duration_match.group(1))
            unit = duration_match.group(2) or "min"
            duration_minutes = amount * 60 if unit.startswith(("hour", "hr")) else amount

        if target_time is None:
            return None, None
        start = datetime.combine(target_date, dt_time(target_time[0], target_time[1]))
        end = start + timedelta(minutes=duration_minutes)
        return start, end
