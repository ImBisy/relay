"""Persistence for the activity log / audit trail."""
from __future__ import annotations

from typing import List, Optional

from .db import Database, get_default_db
from .models import ActionLogEntry


class LogsStore:
    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db or get_default_db()

    def append(self, entry: ActionLogEntry) -> ActionLogEntry:
        row = entry.to_row()
        cur = self.db.execute(
            """INSERT INTO action_logs
               (created_at, source, raw_input, normalized, route, tool_name,
                args, status, message, error, plan_id, step_index, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["created_at"], row["source"], row["raw_input"],
                row["normalized"], row["route"], row["tool_name"],
                row["args"], row["status"], row["message"], row["error"],
                row["plan_id"], row["step_index"], row["metadata"],
            ),
        )
        entry.id = cur.lastrowid
        return entry

    def list_recent(self, limit: int = 100) -> List[ActionLogEntry]:
        rows = self.db.query(
            "SELECT * FROM action_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [ActionLogEntry.from_row(dict(r)) for r in rows]

    def list_by_plan(self, plan_id: str) -> List[ActionLogEntry]:
        rows = self.db.query(
            """SELECT * FROM action_logs
               WHERE plan_id = ? ORDER BY id""",
            (plan_id,),
        )
        return [ActionLogEntry.from_row(dict(r)) for r in rows]

    def clear(self) -> None:
        self.db.execute("DELETE FROM action_logs", ())
