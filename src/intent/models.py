"""
Intent parsing models and data structures.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class ActionType(Enum):
    """Supported action types."""
    EMAIL = "email"
    CALENDAR = "calendar"
    REMINDER = "reminder"
    NOTE = "note"
    TIMER = "timer"
    SYSTEM = "system"
    WEB = "web"
    QUERY = "query"
    UNKNOWN = "unknown"


class ConfidenceLevel(Enum):
    """Confidence thresholds."""
    HIGH = 0.9
    MEDIUM = 0.7
    LOW = 0.5


@dataclass
class ParsedIntent:
    """Structured representation of user intent."""
    intent: str
    action_type: ActionType
    entities: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    requires_confirmation: bool = False
    raw_input: str = ""
    ambiguity_reason: Optional[str] = None
    
    def is_confident(self, threshold: float = 0.7) -> bool:
        """Check if confidence meets threshold."""
        return self.confidence >= threshold
    
    def has_entity(self, key: str) -> bool:
        """Check if entity exists and is not empty."""
        return key in self.entities and self.entities[key]
    
    def get_entity(self, key: str, default: Any = None) -> Any:
        """Get entity value with default."""
        return self.entities.get(key, default)


@dataclass
class EntityExtractor:
    """Helper for extracting common entities from text."""
    
    @staticmethod
    def extract_emails(text: str) -> List[str]:
        """Extract email addresses from text."""
        import re
        pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        return re.findall(pattern, text)
    
    @staticmethod
    def extract_datetime(text: str) -> Optional[Dict[str, Any]]:
        """Extract datetime references from text."""
        # This is a placeholder - would integrate with dateparser or similar
        return None
    
    @staticmethod
    def extract_duration(text: str) -> Optional[int]:
        """Extract duration in minutes from text."""
        import re
        
        # Match patterns like "5 minutes", "2 hours", "30 min"
        patterns = [
            r'(\d+)\s*(?:minute|minutes|min|mins?)(?:\s|$)',
            r'(\d+)\s*(?:hour|hours|hr|hrs?)\s*(?:and\s*)?(\d*)\s*(?:minute|minutes|min)?',
            r'(\d+)\s*(?:second|seconds|sec|secs)',
        ]
        
        total_minutes = 0
        
        # Minutes
        match = re.search(patterns[0], text.lower())
        if match:
            total_minutes += int(match.group(1))
        
        # Hours (with optional minutes)
        match = re.search(patterns[1], text.lower())
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2)) if match.group(2) else 0
            total_minutes += hours * 60 + minutes
        
        # Seconds (convert to minutes, round up)
        match = re.search(patterns[2], text.lower())
        if match:
            seconds = int(match.group(1))
            total_minutes += (seconds + 59) // 60
        
        return total_minutes if total_minutes > 0 else None
