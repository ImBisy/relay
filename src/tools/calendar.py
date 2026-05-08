"""
Calendar tool for managing events and schedules.
"""
import json
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path
from .base import BaseTool, ToolResult
from ..config.settings import config


class CalendarTool(BaseTool):
    """
    Calendar management tool.
    
    Supports:
    - Adding events
    - Viewing schedule
    - Natural language time parsing
    """
    
    name = "calendar"
    description = "Manage calendar events and view schedule"
    requires_confirmation = False
    
    # Relative time patterns
    TIME_PATTERNS = {
        'today': 0,
        'tomorrow': 1,
        'next week': 7,
        'in a week': 7,
        'in two weeks': 14,
        'next month': 30,
    }
    
    DAY_PATTERNS = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6,
        'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6,
    }
    
    TIME_OF_DAY = {
        'morning': (9, 0),
        'afternoon': (14, 0),
        'evening': (18, 0),
        'night': (20, 0),
        'noon': (12, 0),
        'midnight': (0, 0),
    }
    
    def __init__(self):
        self.data_dir = config.get_data_dir()
        self.events_file = self.data_dir / "events.json"
        self._ensure_data_file()
    
    def _ensure_data_file(self):
        """Ensure events data file exists."""
        if not self.events_file.exists():
            with open(self.events_file, 'w') as f:
                json.dump({}, f)
    
    def execute(self, entities: Dict[str, Any]) -> ToolResult:
        """Execute calendar action."""
        action = entities.get('calendar_action', 'add')
        
        if action == 'view' or 'view' in entities.get('intent', ''):
            return self._view_schedule(entities)
        
        return self._add_event(entities)
    
    def _add_event(self, entities: Dict[str, Any]) -> ToolResult:
        """Add a new calendar event."""
        is_valid, error = self.validate(entities)
        if not is_valid:
            return ToolResult.failure(f"Invalid event: {error}")
        
        # Extract event details
        title = entities.get('event_title', entities.get('content', 'Untitled Event'))
        
        # Parse datetime
        dt_result = self._parse_datetime(entities)
        if not dt_result:
            return ToolResult.needs_confirmation(
                "When would you like to schedule this?",
                prompt=f"Schedule '{title}' for when?",
                data={'title': title}
            )
        
        start_time, end_time = dt_result
        
        # Check for conflicts
        conflicts = self._check_conflicts(start_time, end_time)
        
        event_data = {
            'id': self._generate_event_id(),
            'title': title,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat() if end_time else None,
            'description': entities.get('description', ''),
            'location': entities.get('location', ''),
            'created_at': datetime.now().isoformat(),
        }
        
        # Save event
        events = self._load_events()
        events[event_data['id']] = event_data
        self._save_events(events)
        
        # Format response
        time_str = start_time.strftime("%I:%M %p" if config.user.time_format == "%I:%M %p" else "%H:%M")
        date_str = start_time.strftime("%A, %B %d")
        
        message = f"Scheduled '{title}' for {date_str} at {time_str}"
        
        if conflicts:
            message += f". Note: {len(conflicts)} conflicting event(s)."
        
        return ToolResult.success(
            message,
            data={
                'event_id': event_data['id'],
                'title': title,
                'datetime': start_time.isoformat(),
                'conflicts': conflicts,
            }
        )
    
    def _view_schedule(self, entities: Dict[str, Any]) -> ToolResult:
        """View calendar schedule."""
        # Parse date range
        date_range = self._parse_date_range(entities)
        
        events = self._load_events()
        
        # Filter events in range
        filtered_events = []
        for event in events.values():
            event_time = datetime.fromisoformat(event['start_time'])
            if date_range[0] <= event_time <= date_range[1]:
                filtered_events.append(event)
        
        # Sort by time
        filtered_events.sort(key=lambda e: e['start_time'])
        
        if not filtered_events:
            return ToolResult.success("Your calendar is clear for that period.")
        
        # Format events
        event_list = []
        for event in filtered_events:
            dt = datetime.fromisoformat(event['start_time'])
            time_str = dt.strftime("%I:%M %p")
            event_list.append(f"{time_str}: {event['title']}")
        
        return ToolResult.success(
            f"You have {len(filtered_events)} event(s):",
            data={'events': event_list}
        )
    
    def validate(self, entities: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate calendar entities."""
        action = entities.get('calendar_action', 'add')
        
        if action == 'view':
            return True, None
        
        # For adding events
        if not entities.get('event_title') and not entities.get('content'):
            return False, "Event title required"
        
        return True, None
    
    def get_confirmation_prompt(self, entities: Dict[str, Any]) -> Optional[str]:
        """Generate confirmation prompt for ambiguous events."""
        if entities.get('ambiguous_time'):
            title = entities.get('event_title', 'this event')
            return f"Add '{title}' to calendar? (Time unclear - will need clarification)"
        return None
    
    def _parse_datetime(self, entities: Dict[str, Any]) -> Optional[tuple[datetime, Optional[datetime]]]:
        """
        Parse datetime from entities.
        
        Returns:
            (start_time, end_time) or None if parsing fails
        """
        text = entities.get('content', '') + ' ' + entities.get('raw_input', '')
        text_lower = text.lower()
        
        now = datetime.now()
        target_date = now.date()
        target_time = None
        duration_minutes = 60  # Default 1 hour
        
        # Check for relative days
        for pattern, days in self.TIME_PATTERNS.items():
            if pattern in text_lower:
                target_date = now.date() + timedelta(days=days)
                break
        
        # Check for day of week
        for day_name, day_num in self.DAY_PATTERNS.items():
            if day_name in text_lower:
                days_ahead = day_num - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                target_date = now.date() + timedelta(days=days_ahead)
                break
        
        # Check for time of day
        for tod, (hour, minute) in self.TIME_OF_DAY.items():
            if tod in text_lower:
                target_time = (hour, minute)
                break
        
        # Check for specific time (e.g., "3:30", "15:00")
        time_match = re.search(r'(\d{1,2}):(\d{2})\s*(am|pm)?', text_lower)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            ampm = time_match.group(3)
            
            if ampm == 'pm' and hour != 12:
                hour += 12
            elif ampm == 'am' and hour == 12:
                hour = 0
            
            target_time = (hour, minute)
        
        # Extract duration
        duration_match = re.search(r'for\s+(\d+)\s*(min|minute|minutes|hour|hours|hr)?', text_lower)
        if duration_match:
            amount = int(duration_match.group(1))
            unit = duration_match.group(2) or 'min'
            if unit.startswith('hour') or unit.startswith('hr'):
                duration_minutes = amount * 60
            else:
                duration_minutes = amount
        
        if target_time is None:
            return None  # Could not determine time
        
        from datetime import time as dt_time
        start_time = datetime.combine(
            target_date,
            dt_time(target_time[0], target_time[1])
        )
        
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        return (start_time, end_time)
    
    def _parse_date_range(self, entities: Dict[str, Any]) -> tuple[datetime, datetime]:
        """Parse date range for viewing schedule."""
        text = entities.get('raw_input', '').lower()
        
        now = datetime.now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        
        # Check for relative terms
        if 'tomorrow' in text:
            start = start + timedelta(days=1)
            end = start + timedelta(days=1)
        elif 'this week' in text:
            end = start + timedelta(days=7)
        elif 'next week' in text:
            start = start + timedelta(days=7)
            end = start + timedelta(days=7)
        elif 'today' in text or 'schedule' in text:
            pass  # Default is today
        
        return (start, end)
    
    def _check_conflicts(self, start_time: datetime, end_time: Optional[datetime]) -> List[Dict]:
        """Check for conflicting events."""
        if not end_time:
            end_time = start_time + timedelta(hours=1)
        
        events = self._load_events()
        conflicts = []
        
        for event in events.values():
            event_start = datetime.fromisoformat(event['start_time'])
            event_end = datetime.fromisoformat(event['end_time']) if event['end_time'] else event_start + timedelta(hours=1)
            
            # Check overlap
            if start_time < event_end and end_time > event_start:
                conflicts.append(event)
        
        return conflicts
    
    def _load_events(self) -> Dict[str, Dict]:
        """Load events from storage."""
        try:
            with open(self.events_file) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_events(self, events: Dict[str, Dict]):
        """Save events to storage."""
        with open(self.events_file, 'w') as f:
            json.dump(events, f, indent=2, default=str)
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        import uuid
        return f"evt_{uuid.uuid4().hex[:12]}"
