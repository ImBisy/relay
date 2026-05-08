"""Persistence for reminders."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from .db import Database, get_default_db
from .models import Reminder, _now_iso


class RemindersStore:
    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db or get_default_db()

    @staticmethod
    def new_id() -> str:
        return f"rem_{uuid.uuid4().hex[:12]}"

    def create(self, reminder: Reminder) -> Reminder:
        row = reminder.to_row()
        self.db.execute(
            """INSERT INTO reminders
               (id, text, remind_at, created_at, updated_at, completed, completed_at, source, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["id"], row["text"], row["remind_at"],
                row["created_at"], row["updated_at"], row["completed"],
                row["completed_at"], row["source"], row["metadata"],
            ),
        )
        return reminder

    def get(self, reminder_id: str) -> Optional[Reminder]:
        row = self.db.query_one(
            "SELECT * FROM reminders WHERE id = ?", (reminder_id,)
        )
        return Reminder.from_row(dict(row)) if row else None

    def list_active(self, limit: int = 100) -> List[Reminder]:
        rows = self.db.query(
            """SELECT * FROM reminders
               WHERE completed = 0
               ORDER BY COALESCE(remind_at, '9999-12-31'), created_at
               LIMIT ?""",
            (limit,),
        )
        return [Reminder.from_row(dict(r)) for r in rows]

    def list_all(self, limit: int = 200) -> List[Reminder]:
        rows = self.db.query(
            "SELECT * FROM reminders ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [Reminder.from_row(dict(r)) for r in rows]

    def search(self, query: str, limit: int = 50) -> List[Reminder]:
        like = f"%{query.lower()}%"
        rows = self.db.query(
            """SELECT * FROM reminders
               WHERE LOWER(text) LIKE ?
               ORDER BY created_at DESC LIMIT ?""",
            (like, limit),
        )
        return [Reminder.from_row(dict(r)) for r in rows]

    def mark_completed(self, reminder_id: str) -> bool:
        cur = self.db.execute(
            """UPDATE reminders
               SET completed = 1, completed_at = ?, updated_at = ?
               WHERE id = ? AND completed = 0""",
            (_now_iso(), _now_iso(), reminder_id),
        )
        return cur.rowcount > 0

    def update_text(self, reminder_id: str, text: str) -> bool:
        cur = self.db.execute(
            "UPDATE reminders SET text = ?, updated_at = ? WHERE id = ?",
            (text, _now_iso(), reminder_id),
        )
        return cur.rowcount > 0

    def delete(self, reminder_id: str) -> bool:
        cur = self.db.execute(
            "DELETE FROM reminders WHERE id = ?", (reminder_id,)
        )
        return cur.rowcount > 0

    def due_now(self, now: Optional[datetime] = None) -> List[Reminder]:
        cutoff = (now or datetime.utcnow()).isoformat(timespec="seconds")
        rows = self.db.query(
            """SELECT * FROM reminders
               WHERE completed = 0 AND remind_at IS NOT NULL AND remind_at <= ?
               ORDER BY remind_at""",
            (cutoff,),
        )
        return [Reminder.from_row(dict(r)) for r in rows]
