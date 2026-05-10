"""Reminder tool — backed by SQLite via RemindersStore.

Creates structured ``Reminder`` records, schedules an in-process timer
for due reminders when a ``remind_at`` is known, and supports listing,
completing, and deleting reminders.
"""
from __future__ import annotations

import re
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from ..core.context import ToolContext
from ..core.safety import SafetyLevel
from ..storage import RemindersStore
from ..storage.models import Reminder
from .base import BaseTool, ToolResult


class ReminderTool(BaseTool):
    """Quick capture for time-bound tasks."""

    name = "reminder"
    aliases = ["reminders", "remind"]
    description = "Create and manage reminders"
    requires_confirmation = False
    safety_level = SafetyLevel.REVERSIBLE
    supported_actions = ["create", "list", "complete", "delete"]

    def __init__(self,
                 store: Optional[RemindersStore] = None,
                 notification_callback: Optional[Any] = None) -> None:
        self.store = store
        self.notification_callback = notification_callback
        self._timers: Dict[str, threading.Timer] = {}
        self._timers_lock = threading.Lock()

    # ----- BaseTool API -----

    def execute(self, args: Dict[str, Any], ctx: Optional[ToolContext] = None) -> ToolResult:
        store = self._resolve_store(ctx)
        action = args.get("reminder_action", "create")

        if action == "list":
            return self._list(store)
        if action == "complete":
            return self._complete(args, store)
        if action == "delete":
            return self._delete(args, store)
        return self._create(args, store, ctx)

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        action = args.get("reminder_action", "create")
        if action in ("list",):
            return True, None
        if action in ("complete", "delete"):
            if not (args.get("reminder_id") or args.get("content")):
                return False, "Reminder identifier required"
            return True, None
        # create
        text = args.get("reminder_text") or args.get("content") or args.get("text")
        if not text or not text.strip():
            return False, "Reminder text required"
        return True, None

    def preview(self, args: Dict[str, Any]) -> str:
        text = args.get("reminder_text") or args.get("content") or ""
        when = args.get("remind_in_minutes")
        if when:
            return f"Reminder: {text} (in {when} min)"
        return f"Reminder: {text}"

    # ----- internals -----

    def _resolve_store(self, ctx: Optional[ToolContext]) -> RemindersStore:
        if ctx and ctx.reminders is not None:
            return ctx.reminders
        if self.store is not None:
            return self.store
        return RemindersStore()

    def _create(self, args: Dict[str, Any], store: RemindersStore,
                ctx: Optional[ToolContext]) -> ToolResult:
        ok, error = self.validate(args)
        if not ok:
            return ToolResult.failure(f"Invalid reminder: {error}")

        text = (args.get("reminder_text") or args.get("content") or args.get("text") or "").strip()

        # Optional content polishing — never changes meaning, only wording.
        if ctx and ctx.content is not None:
            text = ctx.content.polish_reminder(text) or text

        when = self._resolve_remind_at(args)
        reminder = Reminder(
            id=RemindersStore.new_id(),
            text=text,
            remind_at=when.isoformat(timespec="seconds") if when else None,
            source=ctx.source if ctx else None,
        )
        store.create(reminder)

        if when is not None:
            self._schedule_notification(reminder.id, when, text,
                                         ctx.notification_callback if ctx else None)
            time_str = when.strftime("%I:%M %p")
            return ToolResult.success(
                f"Reminder set for {time_str}: {text}",
                data={"reminder_id": reminder.id, "remind_at": reminder.remind_at, "text": text},
                preview=self.preview({"reminder_text": text, "remind_in_minutes": args.get("remind_in_minutes")}),
            )
        return ToolResult.success(
            f"Captured: {text}",
            data={"reminder_id": reminder.id, "text": text},
            preview=self.preview({"reminder_text": text}),
        )

    def _list(self, store: RemindersStore) -> ToolResult:
        items = store.list_active(limit=20)
        if not items:
            return ToolResult.success("No active reminders.", data={"reminders": []})
        formatted = []
        for r in items:
            if r.remind_at:
                try:
                    dt = datetime.fromisoformat(r.remind_at)
                    formatted.append(f"[{dt.strftime('%I:%M %p')}] {r.text}")
                except ValueError:
                    formatted.append(r.text)
            else:
                formatted.append(r.text)
        return ToolResult.success(
            f"You have {len(items)} reminder(s):",
            data={"reminders": formatted, "items": [r.to_public() for r in items]},
        )

    def _complete(self, args: Dict[str, Any], store: RemindersStore) -> ToolResult:
        reminder_id = args.get("reminder_id")
        if not reminder_id:
            text = (args.get("content") or "").strip().lower()
            if not text:
                return ToolResult.failure("Could not identify reminder.")
            for r in store.list_active(limit=50):
                if text in r.text.lower():
                    reminder_id = r.id
                    break
        if not reminder_id:
            return ToolResult.failure("Reminder not found.")
        if not store.mark_completed(reminder_id):
            return ToolResult.failure("Reminder not found or already complete.")
        self._cancel_timer(reminder_id)
        return ToolResult.success("Reminder completed.", data={"reminder_id": reminder_id})

    def _delete(self, args: Dict[str, Any], store: RemindersStore) -> ToolResult:
        reminder_id = args.get("reminder_id")
        if not reminder_id:
            return ToolResult.failure("Reminder ID required.")
        if not store.delete(reminder_id):
            return ToolResult.failure("Reminder not found.")
        self._cancel_timer(reminder_id)
        return ToolResult.success("Reminder deleted.", data={"reminder_id": reminder_id})

    def _resolve_remind_at(self, args: Dict[str, Any]) -> Optional[datetime]:
        if "remind_in_minutes" in args and args["remind_in_minutes"]:
            return datetime.utcnow() + timedelta(minutes=int(args["remind_in_minutes"]))
        text = (args.get("reminder_text") or args.get("content") or "").lower()
        match = re.search(r"in\s+(\d+)\s*(min|minute|minutes|hour|hours|hr)", text)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            if unit.startswith("hour") or unit.startswith("hr"):
                return datetime.utcnow() + timedelta(hours=amount)
            return datetime.utcnow() + timedelta(minutes=amount)
        match = re.search(r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            ampm = match.group(3)
            if ampm == "pm" and hour != 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            now = datetime.now()
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target < now:
                target += timedelta(days=1)
            return target
        if "tomorrow" in text:
            tomorrow = datetime.now() + timedelta(days=1)
            return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
        return None

    def _schedule_notification(self, reminder_id: str, when: datetime,
                               text: str,
                               ctx_callback: Optional[Any]) -> None:
        delay = max(0.0, (when - datetime.utcnow()).total_seconds())
        callback = ctx_callback or self.notification_callback

        def _fire() -> None:
            if callback:
                try:
                    callback(f"Reminder: {text}")
                except Exception:  # pragma: no cover - best effort
                    pass
            self._cancel_timer(reminder_id)

        timer = threading.Timer(delay, _fire)
        timer.daemon = True
        with self._timers_lock:
            self._timers[reminder_id] = timer
        timer.start()

    def _cancel_timer(self, reminder_id: str) -> None:
        with self._timers_lock:
            timer = self._timers.pop(reminder_id, None)
        if timer is not None:
            timer.cancel()

    def cleanup(self) -> None:
        with self._timers_lock:
            timers = list(self._timers.values())
            self._timers.clear()
        for t in timers:
            t.cancel()
