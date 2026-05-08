"""Persistence for pending (unconfirmed) actions.

We store pending actions as structured records, not as in-memory
callbacks. To execute one, the orchestrator looks up the record by id,
revalidates, and dispatches to the relevant tool. This survives
restarts and makes confirmations deterministic and auditable.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from .db import Database, get_default_db
from .models import PendingAction


class PendingActionsStore:
    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db or get_default_db()

    @staticmethod
    def new_id() -> str:
        return f"act_{uuid.uuid4().hex[:12]}"

    def create(self, action: PendingAction) -> PendingAction:
        row = action.to_row()
        self.db.execute(
            """INSERT INTO pending_actions
               (id, tool_name, args, preview, safety_level,
                created_at, expires_at, status, source, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["id"], row["tool_name"], row["args"], row["preview"],
                row["safety_level"], row["created_at"], row["expires_at"],
                row["status"], row["source"], row["metadata"],
            ),
        )
        return action

    def get(self, action_id: str) -> Optional[PendingAction]:
        row = self.db.query_one(
            "SELECT * FROM pending_actions WHERE id = ?", (action_id,)
        )
        return PendingAction.from_row(dict(row)) if row else None

    def latest_pending(self) -> Optional[PendingAction]:
        row = self.db.query_one(
            """SELECT * FROM pending_actions
               WHERE status = 'pending'
               ORDER BY created_at DESC LIMIT 1""",
        )
        return PendingAction.from_row(dict(row)) if row else None

    def list_pending(self) -> List[PendingAction]:
        rows = self.db.query(
            """SELECT * FROM pending_actions
               WHERE status = 'pending'
               ORDER BY created_at DESC""",
        )
        return [PendingAction.from_row(dict(r)) for r in rows]

    def list_all(self, limit: int = 100) -> List[PendingAction]:
        rows = self.db.query(
            "SELECT * FROM pending_actions ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [PendingAction.from_row(dict(r)) for r in rows]

    def mark_status(self, action_id: str, status: str) -> bool:
        cur = self.db.execute(
            "UPDATE pending_actions SET status = ? WHERE id = ?",
            (status, action_id),
        )
        return cur.rowcount > 0

    def confirm(self, action_id: str) -> bool:
        return self.mark_status(action_id, "confirmed")

    def cancel(self, action_id: str) -> bool:
        return self.mark_status(action_id, "cancelled")

    def expire_old(self, now: Optional[datetime] = None) -> int:
        cutoff = (now or datetime.utcnow()).isoformat(timespec="seconds")
        cur = self.db.execute(
            """UPDATE pending_actions
               SET status = 'expired'
               WHERE status = 'pending'
                 AND expires_at IS NOT NULL
                 AND expires_at < ?""",
            (cutoff,),
        )
        return cur.rowcount

    def purge_old(self, keep_last: int = 200) -> None:
        # Optional housekeeping; keep last N records
        rows = self.db.query(
            """SELECT id FROM pending_actions
               ORDER BY created_at DESC LIMIT -1 OFFSET ?""",
            (keep_last,),
        )
        for r in rows:
            self.db.execute(
                "DELETE FROM pending_actions WHERE id = ?", (r["id"],)
            )
