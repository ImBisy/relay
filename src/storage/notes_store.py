"""Persistence for notes."""
from __future__ import annotations

import uuid
from typing import List, Optional

from .db import Database, get_default_db
from .models import Note, _now_iso


class NotesStore:
    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db or get_default_db()

    @staticmethod
    def new_id() -> str:
        return f"note_{uuid.uuid4().hex[:12]}"

    def create(self, note: Note) -> Note:
        row = note.to_row()
        self.db.execute(
            """INSERT INTO notes
               (id, content, tags, created_at, updated_at, source, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                row["id"], row["content"], row["tags"],
                row["created_at"], row["updated_at"], row["source"], row["metadata"],
            ),
        )
        return note

    def get(self, note_id: str) -> Optional[Note]:
        row = self.db.query_one("SELECT * FROM notes WHERE id = ?", (note_id,))
        return Note.from_row(dict(row)) if row else None

    def list_recent(self, limit: int = 50) -> List[Note]:
        rows = self.db.query(
            "SELECT * FROM notes ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [Note.from_row(dict(r)) for r in rows]

    def search(self, query: str, limit: int = 50) -> List[Note]:
        like = f"%{query.lower()}%"
        rows = self.db.query(
            """SELECT * FROM notes
               WHERE LOWER(content) LIKE ? OR LOWER(tags) LIKE ?
               ORDER BY created_at DESC LIMIT ?""",
            (like, like, limit),
        )
        return [Note.from_row(dict(r)) for r in rows]

    def update_content(self, note_id: str, content: str) -> bool:
        cur = self.db.execute(
            "UPDATE notes SET content = ?, updated_at = ? WHERE id = ?",
            (content, _now_iso(), note_id),
        )
        return cur.rowcount > 0

    def delete(self, note_id: str) -> bool:
        cur = self.db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        return cur.rowcount > 0
