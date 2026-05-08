"""
Notes tool for fast idea capture.
"""
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from .base import BaseTool, ToolResult
from ..config.settings import config


class NotesTool(BaseTool):
    """
    Fast append-only note capture system.
    
    No friction - just capture and store.
    Supports voice-to-text input directly.
    """
    
    name = "note"
    description = "Capture quick notes and ideas"
    requires_confirmation = False
    
    def __init__(self):
        self.data_dir = config.get_data_dir()
        self.notes_file = self.data_dir / "notes.json"
        self._ensure_data_file()
    
    def _ensure_data_file(self):
        """Ensure notes data file exists."""
        if not self.notes_file.exists():
            with open(self.notes_file, 'w') as f:
                json.dump([], f)
    
    def execute(self, entities: Dict[str, Any]) -> ToolResult:
        """Execute note action."""
        action = entities.get('note_action', 'add')
        
        if action == 'list':
            return self._list_notes(entities)
        elif action == 'search':
            return self._search_notes(entities)
        else:
            return self._add_note(entities)
    
    def _add_note(self, entities: Dict[str, Any]) -> ToolResult:
        """Add a new note."""
        is_valid, error = self.validate(entities)
        if not is_valid:
            return ToolResult.failure(f"Cannot capture note: {error}")
        
        # Get note content
        content = (
            entities.get('note_text') or 
            entities.get('content') or 
            entities.get('text')
        )
        
        # Clean up common prefixes that might remain
        prefixes_to_remove = [
            'note that', 'note:', 'take a note', 'make a note',
            'jot down', 'write down', 'capture this', 'remember this'
        ]
        
        content_lower = content.lower()
        for prefix in prefixes_to_remove:
            if content_lower.startswith(prefix):
                content = content[len(prefix):].strip()
                content = content.lstrip(':').strip()
                break
        
        note_data = {
            'id': self._generate_note_id(),
            'content': content,
            'created_at': datetime.now().isoformat(),
            'tags': entities.get('tags', []),
            'source': entities.get('source', 'voice'),
        }
        
        # Load and append
        notes = self._load_notes()
        notes.append(note_data)
        self._save_notes(notes)
        
        # Truncate for response if very long
        display_content = content
        if len(display_content) > 50:
            display_content = display_content[:50] + "..."
        
        return ToolResult.success(
            f"Captured: {display_content}",
            data={'note_id': note_data['id']}
        )
    
    def _list_notes(self, entities: Dict[str, Any]) -> ToolResult:
        """List recent notes."""
        notes = self._load_notes()
        
        # Sort by date (newest first)
        notes.sort(key=lambda n: n['created_at'], reverse=True)
        
        # Limit
        limit = entities.get('limit', 5)
        recent_notes = notes[:limit]
        
        if not recent_notes:
            return ToolResult.success("No notes yet.")
        
        note_list = []
        for note in recent_notes:
            dt = datetime.fromisoformat(note['created_at'])
            time_str = dt.strftime("%I:%M %p")
            content = note['content']
            if len(content) > 40:
                content = content[:40] + "..."
            note_list.append(f"[{time_str}] {content}")
        
        return ToolResult.success(
            f"Your {len(recent_notes)} most recent note(s):",
            data={'notes': note_list}
        )
    
    def _search_notes(self, entities: Dict[str, Any]) -> ToolResult:
        """Search notes."""
        query = entities.get('query', entities.get('content', ''))
        
        if not query:
            return ToolResult.failure("Search query required")
        
        notes = self._load_notes()
        query_lower = query.lower()
        
        matching = [
            n for n in notes 
            if query_lower in n['content'].lower() or
            any(query_lower in tag.lower() for tag in n.get('tags', []))
        ]
        
        if not matching:
            return ToolResult.success(f"No notes found for '{query}'.")
        
        # Sort by relevance (exact match first)
        matching.sort(
            key=lambda n: (
                0 if query_lower in n['content'].lower().split() else 1,
                n['created_at']
            ),
            reverse=True
        )
        
        note_list = []
        for note in matching[:10]:  # Limit results
            content = note['content']
            if len(content) > 50:
                content = content[:50] + "..."
            note_list.append(content)
        
        return ToolResult.success(
            f"Found {len(matching)} note(s):",
            data={'notes': note_list}
        )
    
    def validate(self, entities: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate note entities."""
        content = (
            entities.get('note_text') or 
            entities.get('content') or 
            entities.get('text')
        )
        
        if not content:
            return False, "Note content required"
        
        if len(content.strip()) < 2:
            return False, "Note too short"
        
        return True, None
    
    def _load_notes(self) -> List[Dict]:
        """Load notes from storage."""
        try:
            with open(self.notes_file) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def _save_notes(self, notes: List[Dict]):
        """Save notes to storage."""
        with open(self.notes_file, 'w') as f:
            json.dump(notes, f, indent=2, default=str)
    
    def _generate_note_id(self) -> str:
        """Generate unique note ID."""
        import uuid
        return f"note_{uuid.uuid4().hex[:12]}"
