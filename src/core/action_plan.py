"""Action plans — the structure produced by the router.

Every user input becomes a ``RouterDecision`` which carries one of:
- a ``RouteKind.COMMAND`` plan (one or more ``ActionStep``s),
- ``RouteKind.CHAT`` (free-form LLM chat),
- ``RouteKind.CONFIRMATION`` / ``RouteKind.CANCELLATION`` (operates on
  the most recent pending action),
- ``RouteKind.UNKNOWN`` (fall back to clarification).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .result import ToolResult


class RouteKind(str, Enum):
    COMMAND = "command"
    CHAT = "chat"
    CONFIRMATION = "confirmation"
    CANCELLATION = "cancellation"
    CLARIFICATION = "clarification"
    UNKNOWN = "unknown"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    NEEDS_CONFIRMATION = "needs_confirmation"


@dataclass
class ActionStep:
    tool_name: str
    args: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[int] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: Optional[ToolResult] = None
    error: Optional[str] = None
    raw_clause: Optional[str] = None

    def is_terminal(self) -> bool:
        return self.status in (
            StepStatus.SUCCESS,
            StepStatus.FAILURE,
            StepStatus.SKIPPED,
            StepStatus.NEEDS_CONFIRMATION,
        )


@dataclass
class ActionPlan:
    steps: List[ActionStep] = field(default_factory=list)
    plan_id: str = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:10]}")

    def __len__(self) -> int:
        return len(self.steps)

    @property
    def succeeded(self) -> bool:
        return bool(self.steps) and all(
            s.status == StepStatus.SUCCESS for s in self.steps
        )

    @property
    def has_pending_confirmation(self) -> bool:
        return any(s.status == StepStatus.NEEDS_CONFIRMATION for s in self.steps)

    def successful_steps(self) -> List[ActionStep]:
        return [s for s in self.steps if s.status == StepStatus.SUCCESS]

    def failed_steps(self) -> List[ActionStep]:
        return [s for s in self.steps if s.status == StepStatus.FAILURE]


@dataclass
class RouterDecision:
    kind: RouteKind
    plan: Optional[ActionPlan] = None
    chat_text: Optional[str] = None
    confirmation_target: Optional[str] = None
    clarification_reason: Optional[str] = None
    confidence: float = 1.0

    @classmethod
    def command(cls, plan: ActionPlan, confidence: float = 1.0) -> "RouterDecision":
        return cls(kind=RouteKind.COMMAND, plan=plan, confidence=confidence)

    @classmethod
    def chat(cls, text: str) -> "RouterDecision":
        return cls(kind=RouteKind.CHAT, chat_text=text)

    @classmethod
    def confirmation(cls, target: Optional[str] = None) -> "RouterDecision":
        return cls(kind=RouteKind.CONFIRMATION, confirmation_target=target)

    @classmethod
    def cancellation(cls, target: Optional[str] = None) -> "RouterDecision":
        return cls(kind=RouteKind.CANCELLATION, confirmation_target=target)

    @classmethod
    def clarification(cls, reason: str) -> "RouterDecision":
        return cls(kind=RouteKind.CLARIFICATION, clarification_reason=reason)
