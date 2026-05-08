"""Core orchestration primitives for Relay.

This package owns the routing, planning, and dispatching pipeline. It
deliberately contains no tool-specific or LLM logic — those live in
``src/tools`` and ``src/content``/``src/chat`` respectively.
"""
from .result import ToolResult, ToolResultStatus
from .safety import SafetyLevel
from .context import ToolContext
from .action_plan import ActionPlan, ActionStep, RouteKind
from .router import Router

__all__ = [
    "ToolResult",
    "ToolResultStatus",
    "SafetyLevel",
    "ToolContext",
    "ActionPlan",
    "ActionStep",
    "RouteKind",
    "Router",
]
