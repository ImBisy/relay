"""
Relay personality and response generation system.
"""
import random
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class ResponseTone(Enum):
    """Response tone variants."""
    NEUTRAL = "neutral"
    EFFICIENT = "efficient"
    WITTY = "witty"
    APOLOGETIC = "apologetic"
    CONFIRMING = "confirming"


@dataclass
class ResponseContext:
    """Context for generating appropriate responses."""
    action_type: str
    success: bool
    requires_confirmation: bool
    urgent: bool = False
    error: Optional[str] = None
    user_name: Optional[str] = None


class PersonalityEngine:
    """
    Relay personality engine.
    
    Characteristics:
    - Calm and composed
    - Efficient and concise
    - Occasionally witty (rare, subtle)
    - Never verbose
    - Always in control
    """
    
    # Response templates by category
    ACKNOWLEDGMENTS = [
        "Got it.",
        "Understood.",
        "Acknowledged.",
        "Copy that.",
        "On it.",
    ]
    
    SUCCESS_RESPONSES = {
        "email": [
            "Email drafted. Waiting for your confirmation before sending.",
            "Message ready. Ready to send when you are.",
            "Draft prepared. Review and confirm when ready.",
        ],
        "email_sent": [
            "Email sent successfully.",
            "Message delivered.",
            "Sent and confirmed.",
        ],
        "calendar": [
            "Scheduled. You're all set.",
            "Added to your calendar.",
            "Event created. Marked on your schedule.",
        ],
        "reminder": [
            "Reminder set.",
            "Noted. I'll remind you.",
            "Captured. You won't forget.",
        ],
        "note": [
            "Saved to your notes.",
            "Captured.",
            "Noted.",
        ],
        "timer": [
            "Timer started.",
            "Counting down now.",
            "Timer running.",
        ],
        "timer_stop": [
            "Timer stopped.",
            "Countdown halted.",
        ],
        "system": [
            "Done.",
            "Complete.",
            "Handled.",
        ],
        "web": [
            "Here you are.",
            "Found it.",
            "Results ready.",
        ],
        "query": [
            "Here's what I found.",
            "The answer, sir.",
            "Information retrieved.",
        ],
    }
    
    CONFIRMATION_REQUESTS = [
        "Shall I proceed?",
        "Ready to execute. Confirm?",
        "Proceed with this action?",
    ]
    
    CLARIFICATION_REQUESTS = [
        "Could you clarify that for me?",
        "I need a bit more detail to proceed.",
        "Could you rephrase that?",
        "I'm not entirely certain. Could you specify?",
    ]
    
    WITTY_REMARKS = [
        "That's... an interesting way to phrase it. I'll handle it anyway.",
        "Creative phrasing. Processing now.",
        "Noted, despite the unusual phrasing.",
        "I'll add that to my 'creative user inputs' collection. Done.",
    ]
    
    ERROR_RESPONSES = [
        "I encountered an issue. Let me try again.",
        "Something went wrong. Retrying.",
        "A minor hiccup. Attempting to resolve.",
    ]
    
    ERROR_FINAL = [
        "I'm unable to complete this action. Perhaps we could try a different approach?",
        "This appears to be beyond my current capabilities. Shall we try something else?",
    ]
    
    GREETINGS = [
        "At your service.",
        "How may I assist?",
        "What can I do for you?",
    ]
    
    def __init__(self, witty_frequency: float = 0.05):
        """
        Initialize personality engine.
        
        Args:
            witty_frequency: Probability of adding a witty remark (0-1)
        """
        self.witty_frequency = witty_frequency
    
    def generate_response(self, context: ResponseContext, 
                          details: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate a response based on context.
        
        Structure: [Acknowledgment] + [Action Summary] + [Status/Confirmation]
        """
        parts = []
        
        # Don't be witty during errors or urgent situations
        allow_witty = not context.error and not context.urgent
        
        # 1. Acknowledgment (brief)
        if context.success:
            # Only add acknowledgment for certain actions
            if context.action_type in ['email', 'calendar']:
                parts.append(random.choice(self.ACKNOWLEDGMENTS))
        
        # 2. Action summary and status
        if context.error:
            parts.append(self._handle_error(context))
        elif context.requires_confirmation:
            parts.append(self._handle_confirmation(context, details))
        else:
            parts.append(self._handle_success(context, details))
        
        # 3. Occasional wit (rare, subtle)
        if allow_witty and random.random() < self.witty_frequency:
            witty = self._maybe_add_wit(context)
            if witty:
                parts.insert(-1, witty)  # Insert before final part
        
        response = " ".join(parts)
        return response
    
    def _handle_success(self, context: ResponseContext, 
                        details: Optional[Dict[str, Any]]) -> str:
        """Generate success response."""
        action = context.action_type
        
        # Get appropriate response templates
        if action in self.SUCCESS_RESPONSES:
            templates = self.SUCCESS_RESPONSES[action]
        else:
            templates = ["Done.", "Complete.", "Finished."]
        
        # Add context-specific details
        response = random.choice(templates)
        
        if details:
            if 'recipient' in details and action == 'email':
                response += f" Send to {details['recipient']}?"
            elif 'event_time' in details and action == 'calendar':
                response += f" ({details['event_time']})"
            elif 'timer_duration' in details and action == 'timer':
                response += f" {details['timer_duration']} remaining."
        
        return response
    
    def _handle_confirmation(self, context: ResponseContext,
                             details: Optional[Dict[str, Any]]) -> str:
        """Generate confirmation request."""
        action = context.action_type
        
        if action == 'email':
            if details and 'recipient' in details:
                return f"Send this to {details['recipient']}?"
            return "Ready to send. Confirm?"
        
        if action == 'calendar':
            if details and 'event_title' in details:
                return f"Add '{details['event_title']}' to your calendar?"
            return "Shall I add this to your calendar?"
        
        return random.choice(self.CONFIRMATION_REQUESTS)
    
    def _handle_error(self, context: ResponseContext) -> str:
        """Generate error response."""
        # Check if this is a retry
        if context.error and 'retry' in context.error.lower():
            return random.choice(self.ERROR_RESPONSES)
        
        return random.choice(self.ERROR_FINAL)
    
    def _maybe_add_wit(self, context: ResponseContext) -> Optional[str]:
        """Occasionally add a subtle witty remark."""
        # Only witty for note/reminder actions, never for critical stuff
        if context.action_type in ['note', 'reminder', 'query']:
            if random.random() < 0.3:  # 30% of already rare witty moments
                return random.choice(self.WITTY_REMARKS)
        return None
    
    def greeting(self) -> str:
        """Generate greeting."""
        return random.choice(self.GREETINGS)
    
    def clarification(self, reason: Optional[str] = None) -> str:
        """Generate clarification request."""
        base = random.choice(self.CLARIFICATION_REQUESTS)
        if reason:
            return f"{base} ({reason})"
        return base
    
    def format_list(self, items: List[str], item_type: str = "items") -> str:
        """Format a list of items in Relay style."""
        if not items:
            return f"No {item_type} found."
        
        if len(items) == 1:
            return f"One {item_type[:-1]}: {items[0]}"
        
        if len(items) <= 3:
            return f"{len(items)} {item_type}: " + ", ".join(items)
        
        return f"{len(items)} {item_type}. First few: " + ", ".join(items[:3])


# Singleton instance
personality = PersonalityEngine()
