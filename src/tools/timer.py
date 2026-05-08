"""Timer tool — in-process countdowns; logs completions to the audit trail."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from ..core.context import ToolContext
from ..core.safety import SafetyLevel
from ..intent.models import EntityExtractor
from .base import BaseTool, ToolResult


class TimerTool(BaseTool):
    name = "timer"
    aliases = ["timers"]
    description = "Create and manage countdown timers"
    requires_confirmation = False
    safety_level = SafetyLevel.SAFE
    supported_actions = ["create", "stop", "status"]

    def __init__(self, notification_callback: Optional[Any] = None) -> None:
        self.timers: Dict[str, Dict[str, Any]] = {}
        self.notification_callback = notification_callback
        self._lock = threading.Lock()

    def execute(self, args: Dict[str, Any], ctx: Optional[ToolContext] = None) -> ToolResult:
        action = args.get("timer_action", "create")
        text = (args.get("content") or "").lower()
        if any(word in text for word in ("stop", "cancel", "pause")):
            action = "stop"
        elif any(p in text for p in ("how much", "time left", "remaining")):
            action = "status"
        elif any(word in text for word in ("start", "set", "create")):
            action = "create"

        callback = (ctx.notification_callback if ctx and ctx.notification_callback
                    else self.notification_callback)

        if action in ("create", "start"):
            return self._create(args, callback)
        if action in ("stop", "cancel"):
            return self._stop(args)
        if action == "status":
            return self._status()
        return ToolResult.failure(f"Unknown timer action: {action}")

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        # Allow create without explicit duration; we'll ask in execute.
        return True, None

    def preview(self, args: Dict[str, Any]) -> str:
        duration = args.get("duration_minutes")
        if duration:
            return f"Timer for {duration} min"
        return "Timer"

    def _create(self, args: Dict[str, Any], callback: Optional[Any]) -> ToolResult:
        duration = args.get("duration_minutes") or EntityExtractor.extract_duration(
            args.get("content", "")
        )
        if not duration:
            return ToolResult.needs_confirmation(
                "For how long?",
                prompt="How many minutes should I set the timer for?",
            )

        import uuid
        timer_id = f"timer_{uuid.uuid4().hex[:8]}"
        end_time = datetime.utcnow() + timedelta(minutes=int(duration))
        label = args.get("label", "Timer")
        with self._lock:
            self.timers[timer_id] = {
                "id": timer_id,
                "duration_minutes": int(duration),
                "created_at": datetime.utcnow().isoformat(timespec="seconds"),
                "end_time": end_time.isoformat(timespec="seconds"),
                "label": label,
            }

        def _countdown() -> None:
            time.sleep(int(duration) * 60)
            with self._lock:
                still_active = timer_id in self.timers
                if still_active:
                    del self.timers[timer_id]
            if still_active and callback:
                try:
                    callback(f"Timer complete: {label}")
                except Exception:  # pragma: no cover - best effort
                    pass

        threading.Thread(target=_countdown, daemon=True).start()

        if int(duration) >= 60:
            hours = int(duration) // 60
            mins = int(duration) % 60
            time_str = f"{hours} hour{'s' if hours > 1 else ''}"
            if mins:
                time_str += f" {mins} minute{'s' if mins > 1 else ''}"
        else:
            time_str = f"{int(duration)} minute{'s' if int(duration) > 1 else ''}"

        return ToolResult.success(
            f"Timer started: {time_str}",
            data={"timer_id": timer_id, "duration": int(duration),
                  "end_time": end_time.isoformat(timespec="seconds")},
            preview=self.preview({"duration_minutes": int(duration)}),
        )

    def _stop(self, args: Dict[str, Any]) -> ToolResult:
        with self._lock:
            if not self.timers:
                return ToolResult.failure("No active timers.")
            label = args.get("label")
            if label:
                for tid, info in list(self.timers.items()):
                    if info.get("label", "").lower() == label.lower():
                        del self.timers[tid]
                        return ToolResult.success(f"Timer '{label}' stopped.")
                return ToolResult.failure(f"No timer named '{label}' found.")
            most_recent_id, most_recent = max(
                self.timers.items(), key=lambda kv: kv[1]["created_at"]
            )
            del self.timers[most_recent_id]
            return ToolResult.success(
                f"Timer stopped ({most_recent['duration_minutes']} min).",
                data={"stopped_timer": most_recent},
            )

    def _status(self) -> ToolResult:
        with self._lock:
            if not self.timers:
                return ToolResult.success("No active timers.", data={"timers": []})
            statuses = []
            for info in self.timers.values():
                end = datetime.fromisoformat(info["end_time"])
                remaining = end - datetime.utcnow()
                seconds = max(0, int(remaining.total_seconds()))
                minutes, secs = divmod(seconds, 60)
                label = info.get("label", "Timer")
                statuses.append(
                    f"{label}: {minutes}m {secs}s remaining" if minutes
                    else f"{label}: {secs}s remaining"
                )
            return ToolResult.success(
                f"{len(statuses)} active timer(s):",
                data={"timers": statuses},
            )

    def list_timers(self) -> Dict[str, Any]:
        with self._lock:
            return {tid: dict(info) for tid, info in self.timers.items()}
