"""Data models for Relay's system of record.

Plain dataclasses with explicit fields. They match the SQLite schema
defined in ``db.py`` and convert to/from row dicts for storage.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _dumps(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, default=str)


def _loads(value: Optional[str], default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


@dataclass
class Reminder:
    id: str
    text: str
    remind_at: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    completed: bool = False
    completed_at: Optional[str] = None
    source: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "remind_at": self.remind_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed": int(self.completed),
            "completed_at": self.completed_at,
            "source": self.source,
            "metadata": _dumps(self.metadata),
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "Reminder":
        return cls(
            id=row["id"],
            text=row["text"],
            remind_at=row["remind_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed=bool(row["completed"]),
            completed_at=row["completed_at"],
            source=row["source"],
            metadata=_loads(row["metadata"], {}),
        )

    def to_public(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


@dataclass
class Note:
    id: str
    content: str
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    source: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "tags": _dumps(self.tags),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": self.source,
            "metadata": _dumps(self.metadata),
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "Note":
        return cls(
            id=row["id"],
            content=row["content"],
            tags=_loads(row["tags"], []),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            source=row["source"],
            metadata=_loads(row["metadata"], {}),
        )

    def to_public(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CalendarEvent:
    id: str
    title: str
    start_time: str
    end_time: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    source: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "location": self.location,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": self.source,
            "metadata": _dumps(self.metadata),
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "CalendarEvent":
        return cls(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            location=row["location"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            source=row["source"],
            metadata=_loads(row["metadata"], {}),
        )

    def to_public(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ActionLogEntry:
    id: Optional[int] = None
    created_at: str = field(default_factory=_now_iso)
    source: Optional[str] = None
    raw_input: Optional[str] = None
    normalized: Optional[str] = None
    route: Optional[str] = None
    tool_name: Optional[str] = None
    args: Dict[str, Any] = field(default_factory=dict)
    status: str = "info"
    message: Optional[str] = None
    error: Optional[str] = None
    plan_id: Optional[str] = None
    step_index: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> Dict[str, Any]:
        return {
            "created_at": self.created_at,
            "source": self.source,
            "raw_input": self.raw_input,
            "normalized": self.normalized,
            "route": self.route,
            "tool_name": self.tool_name,
            "args": _dumps(self.args),
            "status": self.status,
            "message": self.message,
            "error": self.error,
            "plan_id": self.plan_id,
            "step_index": self.step_index,
            "metadata": _dumps(self.metadata),
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "ActionLogEntry":
        return cls(
            id=row["id"],
            created_at=row["created_at"],
            source=row["source"],
            raw_input=row["raw_input"],
            normalized=row["normalized"],
            route=row["route"],
            tool_name=row["tool_name"],
            args=_loads(row["args"], {}),
            status=row["status"],
            message=row["message"],
            error=row["error"],
            plan_id=row["plan_id"],
            step_index=row["step_index"],
            metadata=_loads(row["metadata"], {}),
        )

    def to_public(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PendingAction:
    id: str
    tool_name: str
    args: Dict[str, Any]
    preview: Optional[str] = None
    safety_level: str = "sensitive"
    created_at: str = field(default_factory=_now_iso)
    expires_at: Optional[str] = None
    status: str = "pending"
    source: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "args": _dumps(self.args) or "{}",
            "preview": self.preview,
            "safety_level": self.safety_level,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "status": self.status,
            "source": self.source,
            "metadata": _dumps(self.metadata),
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "PendingAction":
        return cls(
            id=row["id"],
            tool_name=row["tool_name"],
            args=_loads(row["args"], {}),
            preview=row["preview"],
            safety_level=row["safety_level"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            status=row["status"],
            source=row["source"],
            metadata=_loads(row["metadata"], {}),
        )

    def to_public(self) -> Dict[str, Any]:
        return asdict(self)
