"""Per-request context handed to tools and services.

Tools should not reach for global singletons. The ``ToolContext`` carries
everything they need: stores, the content enrichment engine, the source
of the request, and a reference to the active action plan.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:  # pragma: no cover - import only for type hints
    from ..content.engine import ContentEngine
    from ..storage import (
        CalendarStore,
        LogsStore,
        NotesStore,
        PendingActionsStore,
        RemindersStore,
    )


@dataclass
class ToolContext:
    """Bundle of services and metadata available to a tool execution."""

    source: str = "cli"
    raw_input: Optional[str] = None
    normalized: Optional[str] = None
    plan_id: Optional[str] = None
    step_index: Optional[int] = None
    confirmed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    reminders: Optional["RemindersStore"] = None
    notes: Optional["NotesStore"] = None
    calendar: Optional["CalendarStore"] = None
    logs: Optional["LogsStore"] = None
    pending_actions: Optional["PendingActionsStore"] = None
    content: Optional["ContentEngine"] = None

    notification_callback: Optional[Any] = None
