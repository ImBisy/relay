"""Persistence for calendar events."""
from __future__ import annotations

import uuid
from typing import List, Optional

from .db import Database, get_default_db
from .models import CalendarEvent, _now_iso


class CalendarStore:
    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db or get_default_db()

    @staticmethod
    def new_id() -> str:
        return f"evt_{uuid.uuid4().hex[:12]}"

    def create(self, event: CalendarEvent) -> CalendarEvent:
        row = event.to_row()
        self.db.execute(
            """INSERT INTO calendar_events
               (id, title, description, location, start_time, end_time,
                created_at, updated_at, source, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["id"], row["title"], row["description"], row["location"],
                row["start_time"], row["end_time"],
                row["created_at"], row["updated_at"], row["source"], row["metadata"],
            ),
        )
        return event

    def get(self, event_id: str) -> Optional[CalendarEvent]:
        row = self.db.query_one(
            "SELECT * FROM calendar_events WHERE id = ?", (event_id,)
        )
        return CalendarEvent.from_row(dict(row)) if row else None

    def list_in_range(self, start_iso: str, end_iso: str) -> List[CalendarEvent]:
        rows = self.db.query(
            """SELECT * FROM calendar_events
               WHERE start_time >= ? AND start_time <= ?
               ORDER BY start_time""",
            (start_iso, end_iso),
        )
        return [CalendarEvent.from_row(dict(r)) for r in rows]

    def list_upcoming(self, after_iso: Optional[str] = None,
                      limit: int = 50) -> List[CalendarEvent]:
        if after_iso is None:
            after_iso = _now_iso()
        rows = self.db.query(
            """SELECT * FROM calendar_events
               WHERE start_time >= ?
               ORDER BY start_time LIMIT ?""",
            (after_iso, limit),
        )
        return [CalendarEvent.from_row(dict(r)) for r in rows]

    def list_all(self, limit: int = 200) -> List[CalendarEvent]:
        rows = self.db.query(
            "SELECT * FROM calendar_events ORDER BY start_time DESC LIMIT ?",
            (limit,),
        )
        return [CalendarEvent.from_row(dict(r)) for r in rows]

    def update_title(self, event_id: str, title: str) -> bool:
        cur = self.db.execute(
            "UPDATE calendar_events SET title = ?, updated_at = ? WHERE id = ?",
            (title, _now_iso(), event_id),
        )
        return cur.rowcount > 0

    def delete(self, event_id: str) -> bool:
        cur = self.db.execute(
            "DELETE FROM calendar_events WHERE id = ?", (event_id,)
        )
        return cur.rowcount > 0
