"""System control tool for macOS commands.

Volume changes are reversible; sleep / shutdown / restart trigger
``EXTERNAL`` side effects and require confirmation through the
orchestrator's pending-action flow.
"""
from __future__ import annotations

import subprocess
from typing import Any, Dict, Optional, Tuple

from ..core.context import ToolContext
from ..core.safety import SafetyLevel
from .base import BaseTool, ToolResult


_APP_ALIASES = {
    "safari": "Safari",
    "chrome": "Google Chrome",
    "firefox": "Firefox",
    "mail": "Mail",
    "messages": "Messages",
    "slack": "Slack",
    "spotify": "Spotify",
    "music": "Music",
    "notes": "Notes",
    "reminders": "Reminders",
    "calendar": "Calendar",
    "finder": "Finder",
    "terminal": "Terminal",
    "code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
}

_DESTRUCTIVE_COMMANDS = {"shutdown", "restart"}
_EXTERNAL_COMMANDS = {"sleep", "lock"}


class SystemTool(BaseTool):
    name = "system"
    aliases = ["mac", "macos"]
    description = "Control macOS system functions"
    requires_confirmation = False
    safety_level = SafetyLevel.REVERSIBLE
    supported_actions = [
        "volume_up", "volume_down", "volume_set", "mute", "unmute",
        "open_app", "close_app", "sleep", "lock", "restart", "shutdown",
    ]

    def __init__(self, runner: Optional[Any] = None) -> None:
        # Allow tests to inject a fake subprocess runner.
        self._runner = runner or subprocess.run

    def execute(self, args: Dict[str, Any], ctx: Optional[ToolContext] = None) -> ToolResult:
        command = args.get("command")
        ok, error = self.validate(args)
        if not ok:
            return ToolResult.failure(f"Invalid system request: {error}")
        handler = getattr(self, f"_cmd_{command}", None)
        if handler is None:
            return ToolResult.failure(f"Unknown command: {command}")
        return handler(args)

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        command = args.get("command")
        if not command:
            return False, "System command required"
        if command not in self.supported_actions:
            return False, f"Unknown command: {command}"
        if command in ("open_app", "close_app") and not args.get("app_name"):
            return False, "Application name required"
        return True, None

    def preview(self, args: Dict[str, Any]) -> str:
        command = args.get("command", "?")
        if args.get("app_name"):
            return f"System: {command} {args['app_name']}"
        return f"System: {command}"

    @property
    def safety_for(self) -> Any:  # pragma: no cover - convenience
        return self.safety_level

    def get_safety(self, command: str) -> SafetyLevel:
        if command in _DESTRUCTIVE_COMMANDS:
            return SafetyLevel.DESTRUCTIVE
        if command in _EXTERNAL_COMMANDS:
            return SafetyLevel.EXTERNAL
        return SafetyLevel.REVERSIBLE

    # ----- handlers -----

    def _osascript(self, script: str) -> Tuple[bool, str]:
        try:
            self._runner(["osascript", "-e", script], capture_output=True, check=True)
            return True, ""
        except Exception as exc:  # broad: subprocess.CalledProcessError or FileNotFoundError
            return False, str(exc)

    def _cmd_volume_up(self, args: Dict[str, Any]) -> ToolResult:
        ok, err = self._osascript(
            "set volume output volume (output volume of (get volume settings) + 10)"
        )
        return ToolResult.success("Volume increased.") if ok else ToolResult.failure(
            "Could not adjust volume", error=err)

    def _cmd_volume_down(self, args: Dict[str, Any]) -> ToolResult:
        ok, err = self._osascript(
            "set volume output volume (output volume of (get volume settings) - 10)"
        )
        return ToolResult.success("Volume decreased.") if ok else ToolResult.failure(
            "Could not adjust volume", error=err)

    def _cmd_volume_set(self, args: Dict[str, Any]) -> ToolResult:
        level = max(0, min(100, int(args.get("level", 50))))
        ok, err = self._osascript(f"set volume output volume {level}")
        return (ToolResult.success(f"Volume set to {level}%.")
                if ok else ToolResult.failure("Could not set volume", error=err))

    def _cmd_mute(self, args: Dict[str, Any]) -> ToolResult:
        ok, err = self._osascript("set volume with output muted")
        return ToolResult.success("Muted.") if ok else ToolResult.failure(
            "Could not mute", error=err)

    def _cmd_unmute(self, args: Dict[str, Any]) -> ToolResult:
        ok, err = self._osascript("set volume without output muted")
        return ToolResult.success("Unmuted.") if ok else ToolResult.failure(
            "Could not unmute", error=err)

    def _cmd_open_app(self, args: Dict[str, Any]) -> ToolResult:
        app = args["app_name"]
        resolved = _APP_ALIASES.get(app.lower(), app)
        try:
            self._runner(["open", "-a", resolved], capture_output=True, check=True)
            return ToolResult.success(f"Opened {resolved}.", data={"app": resolved})
        except Exception as exc:
            return ToolResult.failure(f"Could not open {resolved}", error=str(exc))

    def _cmd_close_app(self, args: Dict[str, Any]) -> ToolResult:
        app = args["app_name"]
        resolved = _APP_ALIASES.get(app.lower(), app)
        ok, err = self._osascript(f'tell application "{resolved}" to quit')
        return (ToolResult.success(f"Closed {resolved}.", data={"app": resolved})
                if ok else ToolResult.failure(f"Could not close {resolved}", error=err))

    def _cmd_sleep(self, args: Dict[str, Any]) -> ToolResult:
        ok, err = self._osascript('tell application "System Events" to sleep')
        return ToolResult.success("Going to sleep.") if ok else ToolResult.failure(
            "Could not sleep system", error=err)

    def _cmd_lock(self, args: Dict[str, Any]) -> ToolResult:
        try:
            self._runner(["/usr/bin/pmset", "displaysleepnow"], capture_output=True, check=False)
            return ToolResult.success("Screen locked.")
        except Exception as exc:
            return ToolResult.failure("Could not lock screen", error=str(exc))

    def _cmd_restart(self, args: Dict[str, Any]) -> ToolResult:
        ok, err = self._osascript('tell application "System Events" to restart')
        return ToolResult.success("Restarting.") if ok else ToolResult.failure(
            "Could not restart", error=err)

    def _cmd_shutdown(self, args: Dict[str, Any]) -> ToolResult:
        ok, err = self._osascript('tell application "System Events" to shut down')
        return ToolResult.success("Shutting down.") if ok else ToolResult.failure(
            "Could not shut down", error=err)
