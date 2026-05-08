"""
Reminder tool for quick task capture.
"""
import json
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from .base import BaseTool, ToolResult
from ..config.settings import config


class ReminderTool(BaseTool):
    """
    Reminder management tool.
    
    Quick capture from speech, supports natural phrasing.
    No confirmation required.
    """
    
    name = "reminder"
    description = "Create and manage reminders"
    requires_confirmation = False
    
    def __init__(self, notification_callback: Optional[Callable] = None):
        self.data_dir = config.get_data_dir()
        self.reminders_file = self.data_dir / "reminders.json"
        self.notification_callback = notification_callback
        self._ensure_data_file()
        self._active_timers: Dict[str, threading.Timer] = {}
    
    def _ensure_data_file(self):
        """Ensure reminders data file exists."""
        if not self.reminders_file.exists():
            with open(self.reminders_file, 'w') as f:
                json.dump({}, f)
    
    def execute(self, entities: Dict[str, Any]) -> ToolResult:
        """Execute reminder action."""
        action = entities.get('reminder_action', 'create')
        
        if action == 'list':
            return self._list_reminders()
        elif action == 'complete':
            return self._complete_reminder(entities)
        elif action == 'delete':
            return self._delete_reminder(entities)
        else:
            return self._create_reminder(entities)
    
    def _create_reminder(self, entities: Dict[str, Any]) -> ToolResult:
        """Create a new reminder."""
        is_valid, error = self.validate(entities)
        if not is_valid:
            return ToolResult.failure(f"Invalid reminder: {error}")
        
        reminder_text = entities.get('reminder_text', entities.get('content', ''))
        
        # Parse when to remind
        remind_when = self._parse_reminder_time(entities)
        
        reminder_data = {
            'id': self._generate_reminder_id(),
            'text': reminder_text,
            'created_at': datetime.now().isoformat(),
            'remind_at': remind_when.isoformat() if remind_when else None,
            'completed': False,
        }
        
        # Save reminder
        reminders = self._load_reminders()
        reminders[reminder_data['id']] = reminder_data
        self._save_reminders(reminders)
        
        # Set timer if time specified
        if remind_when:
            self._schedule_notification(reminder_data['id'], remind_when, reminder_text)
            time_str = remind_when.strftime("%I:%M %p")
            return ToolResult.success(
                f"Reminder set for {time_str}: {reminder_text}",
                data={'reminder_id': reminder_data['id'], 'remind_at': remind_when.isoformat()}
            )
        
        return ToolResult.success(
            f"Captured: {reminder_text}",
            data={'reminder_id': reminder_data['id']}
        )
    
    def _list_reminders(self) -> ToolResult:
        """List active reminders."""
        reminders = self._load_reminders()
        active = [r for r in reminders.values() if not r['completed']]
        
        if not active:
            return ToolResult.success("No active reminders.")
        
        # Sort by remind_at time
        active.sort(key=lambda r: r.get('remind_at') or '9999')
        
        reminder_list = []
        for r in active:
            text = r['text']
            if r.get('remind_at'):
                dt = datetime.fromisoformat(r['remind_at'])
                time_str = dt.strftime("%I:%M %p")
                reminder_list.append(f"[{time_str}] {text}")
            else:
                reminder_list.append(text)
        
        return ToolResult.success(
            f"You have {len(active)} reminder(s):",
            data={'reminders': reminder_list}
        )
    
    def _complete_reminder(self, entities: Dict[str, Any]) -> ToolResult:
        """Mark reminder as complete."""
        reminder_id = entities.get('reminder_id')
        
        if not reminder_id:
            # Try to match by text
            text = entities.get('content', '')
            reminders = self._load_reminders()
            
            for rid, r in reminders.items():
                if text.lower() in r['text'].lower():
                    reminder_id = rid
                    break
        
        if not reminder_id:
            return ToolResult.failure("Could not identify reminder to complete")
        
        reminders = self._load_reminders()
        
        if reminder_id not in reminders:
            return ToolResult.failure("Reminder not found")
        
        reminders[reminder_id]['completed'] = True
        reminders[reminder_id]['completed_at'] = datetime.now().isoformat()
        
        self._save_reminders(reminders)
        
        # Cancel any pending timer
        if reminder_id in self._active_timers:
            self._active_timers[reminder_id].cancel()
            del self._active_timers[reminder_id]
        
        return ToolResult.success("Reminder completed.")
    
    def _delete_reminder(self, entities: Dict[str, Any]) -> ToolResult:
        """Delete a reminder."""
        reminder_id = entities.get('reminder_id')
        
        if not reminder_id:
            return ToolResult.failure("Reminder ID required")
        
        reminders = self._load_reminders()
        
        if reminder_id not in reminders:
            return ToolResult.failure("Reminder not found")
        
        del reminders[reminder_id]
        self._save_reminders(reminders)
        
        # Cancel any pending timer
        if reminder_id in self._active_timers:
            self._active_timers[reminder_id].cancel()
            del self._active_timers[reminder_id]
        
        return ToolResult.success("Reminder deleted.")
    
    def validate(self, entities: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate reminder entities."""
        reminder_text = (
            entities.get('reminder_text') or 
            entities.get('content') or
            entities.get('text')
        )
        
        if not reminder_text:
            return False, "Reminder text required"
        
        return True, None
    
    def _parse_reminder_time(self, entities: Dict[str, Any]) -> Optional[datetime]:
        """Parse when to remind from entities."""
        # Check for explicit time
        if 'remind_in_minutes' in entities:
            minutes = entities['remind_in_minutes']
            return datetime.now() + timedelta(minutes=minutes)
        
        # Check for time patterns in content
        text = entities.get('reminder_text', entities.get('content', ''))
        text_lower = text.lower()
        
        # Pattern: "in X minutes/hours"
        import re
        match = re.search(r'in\s+(\d+)\s*(min|minute|minutes|hour|hours|hr)', text_lower)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            if unit.startswith('hour'):
                return datetime.now() + timedelta(hours=amount)
            else:
                return datetime.now() + timedelta(minutes=amount)
        
        # Pattern: "at 3pm", "at 15:00"
        match = re.search(r'at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?', text_lower)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            ampm = match.group(3)
            
            if ampm == 'pm' and hour != 12:
                hour += 12
            elif ampm == 'am' and hour == 12:
                hour = 0
            
            target = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # If time has passed today, schedule for tomorrow
            if target < datetime.now():
                target += timedelta(days=1)
            
            return target
        
        # Pattern: "tomorrow", "next week"
        if 'tomorrow' in text_lower:
            tomorrow = datetime.now() + timedelta(days=1)
            return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
        
        if 'next week' in text_lower:
            next_week = datetime.now() + timedelta(days=7)
            return next_week.replace(hour=9, minute=0, second=0, microsecond=0)
        
        return None  # No time specified, will be task-only
    
    def _schedule_notification(self, reminder_id: str, when: datetime, text: str):
        """Schedule a notification timer."""
        now = datetime.now()
        delay_seconds = max(0, (when - now).total_seconds())
        
        def notify():
            if self.notification_callback:
                self.notification_callback(f"Reminder: {text}")
            
            # Mark as triggered
            reminders = self._load_reminders()
            if reminder_id in reminders:
                reminders[reminder_id]['triggered'] = True
                self._save_reminders(reminders)
        
        timer = threading.Timer(delay_seconds, notify)
        timer.daemon = True
        timer.start()
        
        self._active_timers[reminder_id] = timer
    
    def _load_reminders(self) -> Dict[str, Dict]:
        """Load reminders from storage."""
        try:
            with open(self.reminders_file) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_reminders(self, reminders: Dict[str, Dict]):
        """Save reminders to storage."""
        with open(self.reminders_file, 'w') as f:
            json.dump(reminders, f, indent=2, default=str)
    
    def _generate_reminder_id(self) -> str:
        """Generate unique reminder ID."""
        import uuid
        return f"rem_{uuid.uuid4().hex[:12]}"
    
    def cleanup(self):
        """Clean up all active timers."""
        for timer in self._active_timers.values():
            timer.cancel()
        self._active_timers.clear()
