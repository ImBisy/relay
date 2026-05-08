"""Base tool interface for the Relay assistant.

Every tool inherits from ``BaseTool`` and must declare a name and a
safety level. The contract is intentionally small but explicit:

- ``execute(args, ctx)`` does the work and returns a ``ToolResult``.
- ``validate(args)`` runs cheap structural checks before execution.
- ``preview(args)`` produces a short, human-readable description used
  in confirmation prompts and the activity log.
- ``cancel(action_id)`` cleans up a pending action when the user
  cancels (override only if the tool stages pending actions).
- ``can_handle(text)`` and ``parse_args(text)`` are optional hooks for
  tool-driven routing if the rule-based router ever needs to ask a
  tool whether it can take a piece of input.

``ctx`` is optional so legacy callers that just want to execute a tool
in a smoke test (see ``test_relay.py``) keep working.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:  # pragma: no cover - import only for type hints
    from ..core.context import ToolContext


class ToolResultStatus(Enum):
    """Status of tool execution."""
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"
    CANCELLED = "cancelled"
    NEEDS_CONFIRMATION = "needs_confirmation"


@dataclass
class ToolResult:
    """Result of tool execution.

    ``data`` is a structured payload (used by the dashboard, logs, and
    the personality renderer); ``message`` is the short user-facing
    summary; ``preview`` is the human-readable description shown when
    confirming a sensitive action.
    """

    status: ToolResultStatus
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    requires_confirmation: bool = False
    confirmation_prompt: Optional[str] = None
    action_id: Optional[str] = None
    preview: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def success(cls, message: str, data: Optional[Dict[str, Any]] = None,
                preview: Optional[str] = None) -> "ToolResult":
        return cls(status=ToolResultStatus.SUCCESS, message=message,
                   data=data, preview=preview)

    @classmethod
    def failure(cls, message: str, error: Optional[str] = None,
                data: Optional[Dict[str, Any]] = None) -> "ToolResult":
        return cls(status=ToolResultStatus.FAILURE, message=message,
                   error=error, data=data)

    @classmethod
    def pending(cls, message: str, data: Optional[Dict[str, Any]] = None) -> "ToolResult":
        return cls(status=ToolResultStatus.PENDING, message=message, data=data)

    @classmethod
    def cancelled(cls, message: str = "Action cancelled.",
                  data: Optional[Dict[str, Any]] = None) -> "ToolResult":
        return cls(status=ToolResultStatus.CANCELLED, message=message, data=data)

    @classmethod
    def needs_confirmation(cls, message: str, prompt: str,
                           data: Optional[Dict[str, Any]] = None,
                           action_id: Optional[str] = None,
                           preview: Optional[str] = None) -> "ToolResult":
        return cls(
            status=ToolResultStatus.NEEDS_CONFIRMATION,
            message=message,
            data=data,
            requires_confirmation=True,
            confirmation_prompt=prompt,
            action_id=action_id,
            preview=preview,
        )


class BaseTool(ABC):
    """Base class for all tools.

    Subclasses set ``name``, ``aliases``, ``description``,
    ``safety_level``, and ``supported_actions`` as class attributes.
    """

    name: str = ""
    aliases: List[str] = []
    description: str = ""
    requires_confirmation: bool = False
    supported_actions: List[str] = []
    # Set by ``__init_subclass__`` to ``SafetyLevel.SAFE`` if not
    # explicitly declared by the subclass; using ``Any`` keeps the
    # forward import simple.
    safety_level: Any = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if cls.safety_level is None:
            from ..core.safety import SafetyLevel
            cls.safety_level = SafetyLevel.SAFE

    @abstractmethod
    def execute(self, args: Dict[str, Any],
                ctx: Optional["ToolContext"] = None) -> ToolResult:
        """Execute the tool with the given arguments."""

    @abstractmethod
    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate arguments without performing any side effects."""

    # ----- optional contract extensions -----

    def can_handle(self, text: str) -> bool:  # noqa: ARG002 - hook
        """Return True if this tool can plausibly handle ``text``.

        Default implementation always returns False; the rule-based
        router does the routing.
        """
        return False

    def parse_args(self, text: str) -> Dict[str, Any]:  # noqa: ARG002 - hook
        """Parse free-form text into arguments. Default: empty dict."""
        return {}

    def preview(self, args: Dict[str, Any]) -> str:  # noqa: ARG002 - hook
        """One-line preview used in confirmation prompts and the audit log."""
        return ""

    def cancel(self, action_id: str) -> ToolResult:  # noqa: ARG002 - hook
        """Cancel a pending action (only meaningful for tools that stage them)."""
        return ToolResult.failure(
            "This tool does not support cancellation.",
            error="cancel_not_supported",
        )

    def get_confirmation_prompt(self, args: Dict[str, Any]) -> Optional[str]:
        """Backwards-compatible hook for legacy tools."""
        if not self.requires_confirmation:
            return None
        return self.preview(args) or None
