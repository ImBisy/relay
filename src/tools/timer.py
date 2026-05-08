"""
Timer tool for countdown timers.
"""
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable
from .base import BaseTool, ToolResult


class TimerTool(BaseTool):
    """
    Timer management tool.
    
    Supports:
    - Creating timers
    - Stopping/cancelling timers
    - Checking time remaining
    """
    
    name = "timer"
    description = "Create and manage countdown timers"
    requires_confirmation = False
    
    def __init__(self, notification_callback: Optional[Callable] = None):
        self.timers: Dict[str, Dict[str, Any]] = {}
        self.notification_callback = notification_callback
        self._lock = threading.Lock()
    
    def execute(self, entities: Dict[str, Any]) -> ToolResult:
        """Execute timer action."""
        action = entities.get('timer_action', 'create')
        text = entities.get('content', '').lower()
        
        # Detect action from text
        if any(word in text for word in ['stop', 'cancel', 'pause']):
            action = 'stop'
        elif any(phrase in text for phrase in ['how much', 'time left', 'remaining']):
            action = 'status'
        elif any(word in text for word in ['start', 'set', 'create']):
            action = 'create'
        
        if action == 'create' or action == 'start':
            return self._create_timer(entities)
        elif action == 'stop' or action == 'cancel':
            return self._stop_timer(entities)
        elif action == 'status':
            return self._timer_status(entities)
        else:
            return ToolResult.failure(f"Unknown timer action: {action}")
    
    def _create_timer(self, entities: Dict[str, Any]) -> ToolResult:
        """Create a new timer."""
        is_valid, error = self.validate(entities)
        if not is_valid:
            return ToolResult.failure(f"Cannot create timer: {error}")
        
        # Get duration
        duration_minutes = entities.get('duration_minutes')
        
        if not duration_minutes:
            # Try to extract from content
            from ..intent.models import EntityExtractor
            duration_minutes = EntityExtractor.extract_duration(entities.get('content', ''))
        
        if not duration_minutes:
            return ToolResult.needs_confirmation(
                "For how long?",
                prompt="How many minutes should I set the timer for?",
            )
        
        # Create timer
        timer_id = self._generate_timer_id()
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        
        timer_data = {
            'id': timer_id,
            'duration_minutes': duration_minutes,
            'created_at': datetime.now().isoformat(),
            'end_time': end_time.isoformat(),
            'label': entities.get('label', 'Timer'),
        }
        
        # Store timer
        with self._lock:
            self.timers[timer_id] = timer_data
        
        # Start countdown thread
        self._start_countdown(timer_id, duration_minutes, timer_data['label'])
        
        # Format time string
        if duration_minutes >= 60:
            hours = duration_minutes // 60
            mins = duration_minutes % 60
            time_str = f"{hours} hour{'s' if hours > 1 else ''}"
            if mins > 0:
                time_str += f" {mins} minute{'s' if mins > 1 else ''}"
        else:
            time_str = f"{duration_minutes} minute{'s' if duration_minutes > 1 else ''}"
        
        return ToolResult.success(
            f"Timer started: {time_str}",
            data={
                'timer_id': timer_id,
                'duration': duration_minutes,
                'end_time': end_time.isoformat(),
            }
        )
    
    def _stop_timer(self, entities: Dict[str, Any]) -> ToolResult:
        """Stop a running timer."""
        with self._lock:
            if not self.timers:
                return ToolResult.failure("No active timers.")
            
            # If multiple timers, stop the most recent one
            # Or look for specific label
            label = entities.get('label')
            
            if label:
                # Find timer with matching label
                for tid, timer in self.timers.items():
                    if timer.get('label', '').lower() == label.lower():
                        self._cancel_timer(tid)
                        return ToolResult.success(f"Timer '{label}' stopped.")
                return ToolResult.failure(f"No timer named '{label}' found.")
            
            # Stop most recent timer
            most_recent = max(self.timers.items(), key=lambda x: x[1]['created_at'])
            timer_id = most_recent[0]
            timer = most_recent[1]
            
            self._cancel_timer(timer_id)
            
            return ToolResult.success(
                f"Timer stopped ({timer['duration_minutes']} min).",
                data={'stopped_timer': timer}
            )
    
    def _timer_status(self, entities: Dict[str, Any]) -> ToolResult:
        """Check timer status."""
        with self._lock:
            if not self.timers:
                return ToolResult.success("No active timers.")
            
            status_list = []
            for timer_id, timer in self.timers.items():
                end_time = datetime.fromisoformat(timer['end_time'])
                remaining = end_time - datetime.now()
                
                if remaining.total_seconds() > 0:
                    minutes = int(remaining.total_seconds() // 60)
                    seconds = int(remaining.total_seconds() % 60)
                    
                    label = timer.get('label', 'Timer')
                    if minutes > 0:
                        status_list.append(f"{label}: {minutes}m {seconds}s remaining")
                    else:
                        status_list.append(f"{label}: {seconds}s remaining")
            
            if not status_list:
                return ToolResult.success("No active timers.")
            
            return ToolResult.success(
                f"{len(status_list)} active timer(s):",
                data={'timers': status_list}
            )
    
    def _start_countdown(self, timer_id: str, duration_minutes: int, label: str):
        """Start countdown thread for timer."""
        def countdown():
            time.sleep(duration_minutes * 60)
            
            # Check if timer still exists (wasn't cancelled)
            with self._lock:
                if timer_id in self.timers:
                    # Timer complete
                    if self.notification_callback:
                        self.notification_callback(f"Timer complete: {label}")
                    
                    # Remove timer
                    del self.timers[timer_id]
        
        thread = threading.Thread(target=countdown, daemon=True)
        thread.start()
    
    def _cancel_timer(self, timer_id: str):
        """Cancel a specific timer."""
        with self._lock:
            if timer_id in self.timers:
                del self.timers[timer_id]
    
    def validate(self, entities: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate timer entities."""
        action = entities.get('timer_action', 'create')
        
        if action == 'create':
            # Must have duration or be extractable
            if not entities.get('duration_minutes'):
                from ..intent.models import EntityExtractor
                duration = EntityExtractor.extract_duration(entities.get('content', ''))
                if not duration:
                    return True, None  # Will request confirmation for duration
        
        return True, None
    
    def _generate_timer_id(self) -> str:
        """Generate unique timer ID."""
        import uuid
        return f"timer_{uuid.uuid4().hex[:8]}"
    
    def list_timers(self) -> Dict[str, Any]:
        """Get all active timers."""
        with self._lock:
            return self.timers.copy()
