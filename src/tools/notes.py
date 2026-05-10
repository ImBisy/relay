"""Notes tool — fast capture, backed by SQLite via NotesStore."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ..core.context import ToolContext
from ..core.safety import SafetyLevel
from ..storage import NotesStore
from ..storage.models import Note
from .base import BaseTool, ToolResult


_PREFIXES = (
    "note that", "note:", "take a note", "make a note",
    "jot down", "write down", "capture this", "remember this",
)


class NotesTool(BaseTool):
    """Append-only notes capture."""

    name = "note"
    aliases = ["notes"]
    description = "Capture quick notes and ideas"
    requires_confirmation = False
    safety_level = SafetyLevel.REVERSIBLE
    supported_actions = ["add", "list", "search", "delete"]

    def __init__(self, store: Optional[NotesStore] = None) -> None:
        self.store = store

    def execute(self, args: Dict[str, Any], ctx: Optional[ToolContext] = None) -> ToolResult:
        store = self._resolve_store(ctx)
        action = args.get("note_action", "add")
        if action == "list":
            return self._list(args, store)
        if action == "search":
            return self._search(args, store)
        if action == "delete":
            return self._delete(args, store)
        return self._add(args, store, ctx)

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        action = args.get("note_action", "add")
        if action == "list":
            return True, None
        if action == "search":
            if not (args.get("query") or args.get("content")):
                return False, "Search query required"
            return True, None
        if action == "delete":
            if not args.get("note_id"):
                return False, "Note id required"
            return True, None
        # add
        content = args.get("note_text") or args.get("content") or args.get("text") or ""
        if len(content.strip()) < 2:
            return False, "Note too short"
        return True, None

    def preview(self, args: Dict[str, Any]) -> str:
        content = (args.get("note_text") or args.get("content") or "").strip()
        if len(content) > 60:
            content = content[:60] + "..."
        return f"Note: {content}"

    def _resolve_store(self, ctx: Optional[ToolContext]) -> NotesStore:
        if ctx and ctx.notes is not None:
            return ctx.notes
        if self.store is not None:
            return self.store
        return NotesStore()

    def _add(self, args: Dict[str, Any], store: NotesStore,
             ctx: Optional[ToolContext]) -> ToolResult:
        ok, error = self.validate(args)
        if not ok:
            return ToolResult.failure(f"Cannot capture note: {error}")

        content = (args.get("note_text") or args.get("content") or args.get("text") or "").strip()
        lower = content.lower()
        for prefix in _PREFIXES:
            if lower.startswith(prefix):
                content = content[len(prefix):].lstrip(":, ").strip()
                break

        # Optional cleanup pass — formatting only, never new info.
        if ctx and ctx.content is not None:
            content = ctx.content.polish_note(content) or content

        note = Note(
            id=NotesStore.new_id(),
            content=content,
            tags=list(args.get("tags") or []),
            source=ctx.source if ctx else None,
        )
        store.create(note)

        display = content if len(content) <= 60 else content[:60] + "..."
        return ToolResult.success(
            f"Captured: {display}",
            data={"note_id": note.id, "content": content},
            preview=self.preview({"note_text": content}),
        )

    def _list(self, args: Dict[str, Any], store: NotesStore) -> ToolResult:
        limit = int(args.get("limit", 10))
        notes = store.list_recent(limit=limit)
        if not notes:
            return ToolResult.success("No notes yet.", data={"notes": []})
        formatted = []
        for n in notes:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(n.created_at)
                ts = dt.strftime("%I:%M %p")
            except ValueError:
                ts = "—"
            content = n.content if len(n.content) <= 60 else n.content[:60] + "..."
            formatted.append(f"[{ts}] {content}")
        return ToolResult.success(
            f"Your {len(notes)} most recent note(s):",
            data={"notes": formatted, "items": [n.to_public() for n in notes]},
        )

    def _search(self, args: Dict[str, Any], store: NotesStore) -> ToolResult:
        query = (args.get("query") or args.get("content") or "").strip()
        if not query:
            return ToolResult.failure("Search query required")
        results = store.search(query, limit=20)
        if not results:
            return ToolResult.success(f"No notes found for '{query}'.", data={"notes": []})
        formatted = [n.content if len(n.content) <= 60 else n.content[:60] + "..." for n in results]
        return ToolResult.success(
            f"Found {len(results)} note(s):",
            data={"notes": formatted, "items": [n.to_public() for n in results]},
        )

    def _delete(self, args: Dict[str, Any], store: NotesStore) -> ToolResult:
        note_id = args.get("note_id")
        if not note_id or not store.delete(note_id):
            return ToolResult.failure("Note not found.")
        return ToolResult.success("Note deleted.", data={"note_id": note_id})
