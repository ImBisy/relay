"""
Intent parsing - converts natural language to structured commands.
Uses rule-based matching with OpenRouter fallback for complex cases.
"""
import re
from typing import Optional, Dict, Any, List
from .models import ParsedIntent, ActionType, EntityExtractor


class IntentParser:
    """Parse natural language into structured intents."""
    
    # Intent patterns for rule-based matching
    EMAIL_PATTERNS = [
        r'(?:send|compose|write)\s+(?:an?\s+)?email\s+(?:to\s+)?(.+)',
        r'email\s+(.+)',
        r'draft\s+(?:an?\s+)?email\s+(?:to\s+)?(.+)',
        r'send\s+(?:an?\s+)?message\s+(?:to\s+)?(.+)',
    ]
    
    CALENDAR_PATTERNS = [
        r'(?:add|create|schedule)\s+(?:an?\s+)?(?:meeting|event|appointment)\s+(.+)',
        r'(?:schedule|book)\s+(.+)',
        r'what\'s\s+(?:on\s+)?(?:my\s+)?(?:calendar|schedule)\s*(.+)?',
        r'(?:show|tell\s+me)\s+(?:my\s+)?schedule\s*(.+)?',
    ]
    
    REMINDER_PATTERNS = [
        r'remind\s+me\s+(?:to\s+)?(.+)',
        r'don\'t\s+let\s+me\s+forget\s+(.+)',
        r'remember\s+(?:to\s+)?(.+)',
        r'(?:set|create)\s+(?:a\s+)?reminder\s+(?:to\s+)?(.+)',
    ]
    
    NOTE_PATTERNS = [
        r'(?:take|make|jot\s+down)\s+(?:a\s+)?note\s*(?::\s*|\s+that\s+)?(.+)',
        r'note\s+(?:that\s+)?(.+)',
        r'write\s+down\s+(.+)',
        r'remember\s+this\s*:\s*(.+)',
        r'capture\s+(.+)',
    ]
    
    TIMER_PATTERNS = [
        r'(?:set|start|create)\s+(?:a\s+)?timer\s+(?:for\s+)?(.+)',
        r'timer\s+(?:for\s+)?(.+)',
        r'(?:stop|cancel|pause)\s+(?:the\s+)?timer',
        r'how\s+much\s+time\s+(?:is\s+)?left',
    ]
    
    SYSTEM_PATTERNS = [
        r'(?:open|launch|start)\s+(?:the\s+)?(?:app|application)?\s*(.+)',
        r'(?:close|quit)\s+(?:the\s+)?(?:app|application)?\s*(.+)',
        r'(?:volume|brightness)\s+(?:up|down|set\s+to)',
        r'(?:mute|unmute)',
        r'(?:sleep|shutdown|restart|lock)',
    ]
    
    WEB_PATTERNS = [
        r'(?:search|look\s+up|google)\s+(.+)',
        r'(?:open|go\s+to)\s+(?:the\s+)?(?:website|url|site)?\s*(.+)',
    ]
    
    QUERY_PATTERNS = [
        r'(?:what|who|when|where|why|how)\s+.+',
        r'tell\s+me\s+about\s+(.+)',
        r'what\s+(?:is|are)\s+(.+)',
    ]
    
    def __init__(self, openrouter_client: Optional[Any] = None):
        self.openrouter = openrouter_client
        self.extractor = EntityExtractor()
    
    def parse(self, text: str) -> ParsedIntent:
        """
        Parse input text into structured intent.
        
        Strategy:
        1. Try rule-based matching first (fast, deterministic)
        2. If low confidence or complex, use OpenRouter
        """
        text_lower = text.lower().strip()
        
        # Try rule-based matching
        intent = self._rule_based_parse(text_lower)
        
        # If low confidence and OpenRouter available, use it
        if not intent.is_confident(0.7) and self.openrouter:
            llm_intent = self._llm_parse(text)
            if llm_intent.confidence > intent.confidence:
                intent = llm_intent
        
        intent.raw_input = text
        return intent
    
    def _rule_based_parse(self, text: str) -> ParsedIntent:
        """Parse using rule-based pattern matching."""
        
        # Check each action type
        for action_type, patterns in [
            (ActionType.EMAIL, self.EMAIL_PATTERNS),
            (ActionType.CALENDAR, self.CALENDAR_PATTERNS),
            (ActionType.REMINDER, self.REMINDER_PATTERNS),
            (ActionType.NOTE, self.NOTE_PATTERNS),
            (ActionType.TIMER, self.TIMER_PATTERNS),
            (ActionType.SYSTEM, self.SYSTEM_PATTERNS),
            (ActionType.WEB, self.WEB_PATTERNS),
            (ActionType.QUERY, self.QUERY_PATTERNS),
        ]:
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return self._create_intent_from_match(
                        action_type, match, text, confidence=0.85
                    )
        
        # No match found
        return ParsedIntent(
            intent="unknown",
            action_type=ActionType.UNKNOWN,
            confidence=0.3,
            requires_confirmation=True,
            ambiguity_reason="Could not determine intent from input"
        )
    
    def _create_intent_from_match(self, action_type: ActionType, 
                                   match: re.Match, text: str,
                                   confidence: float) -> ParsedIntent:
        """Create ParsedIntent from regex match."""
        
        entities = {}
        requires_confirmation = False
        
        # Extract content from match groups
        if match.groups() and match.group(1):
            content = match.group(1).strip()
            entities['content'] = content
        
        # Action-specific entity extraction
        if action_type == ActionType.EMAIL:
            entities.update(self._extract_email_entities(text))
            requires_confirmation = True  # Always confirm email
            
        elif action_type == ActionType.CALENDAR:
            entities.update(self._extract_calendar_entities(text))
            requires_confirmation = entities.get('ambiguous_time', False)
            
        elif action_type == ActionType.REMINDER:
            entities.update(self._extract_reminder_entities(text))
            
        elif action_type == ActionType.TIMER:
            duration = self.extractor.extract_duration(text)
            if duration:
                entities['duration_minutes'] = duration
            else:
                confidence = 0.5
                requires_confirmation = True
                
        elif action_type == ActionType.SYSTEM:
            entities.update(self._extract_system_entities(text))
            
        return ParsedIntent(
            intent=action_type.value,
            action_type=action_type,
            entities=entities,
            confidence=confidence,
            requires_confirmation=requires_confirmation
        )
    
    def _extract_email_entities(self, text: str) -> Dict[str, Any]:
        """Extract email-specific entities."""
        entities = {}
        
        # Check for draft vs send
        if any(word in text for word in ['draft', 'write', 'compose']):
            if 'send' not in text:
                entities['draft_only'] = True
        
        # Look for recipient patterns
        recipient_patterns = [
            r'(?:to|for)\s+([\w\s]+?)(?:\s+(?:saying|about|regarding|that|$))',
            r'(?:to|for)\s+([\w\s]+?)(?:\s+(?:at|with)\s+)?',
        ]
        
        for pattern in recipient_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                recipient = match.group(1).strip()
                entities['recipient_alias'] = recipient
                break
        
        # Extract email body
        body_patterns = [
            r'(?:saying|about|regarding|that)\s+(.+)',
            r'(?:with|containing)\s+(?:the\s+)?(?:subject|message|body)?\s*(?:that\s+)?(.+)',
        ]
        
        for pattern in body_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                entities['body'] = match.group(1).strip()
                break
        
        # Extract actual email addresses
        emails = self.extractor.extract_emails(text)
        if emails:
            entities['recipient_email'] = emails[0]
        
        return entities
    
    def _extract_calendar_entities(self, text: str) -> Dict[str, Any]:
        """Extract calendar-specific entities."""
        entities = {}
        
        # Extract event title
        title_patterns = [
            r'(?:called|named|titled)\s+["\']?(.+?)["\']?(?:\s+(?:at|on|for|$))',
            r'(?:to\s+)?(?:discuss|talk\s+about|meet\s+about)\s+(.+?)(?:\s+(?:at|on|for|$))',
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                entities['event_title'] = match.group(1).strip()
                break
        
        # Mark ambiguous if no clear title
        if 'event_title' not in entities:
            entities['ambiguous_time'] = True
            # Try to use content as title
            if 'content' in entities:
                entities['event_title'] = entities['content']
        
        return entities
    
    def _extract_reminder_entities(self, text: str) -> Dict[str, Any]:
        """Extract reminder-specific entities."""
        entities = {}
        
        # Extract reminder text
        reminder_text = text
        prefixes = ['remind me to', "don't let me forget", 'remember to', 
                    'create a reminder to', 'set a reminder to']
        
        for prefix in prefixes:
            if reminder_text.startswith(prefix):
                reminder_text = reminder_text[len(prefix):].strip()
                break
        
        # Check for time specification
        duration = self.extractor.extract_duration(text)
        if duration:
            entities['remind_in_minutes'] = duration
        
        entities['reminder_text'] = reminder_text
        
        return entities
    
    def _extract_system_entities(self, text: str) -> Dict[str, Any]:
        """Extract system command entities."""
        entities = {}
        
        # Volume control
        if 'volume' in text:
            if 'up' in text or 'increase' in text:
                entities['command'] = 'volume_up'
            elif 'down' in text or 'decrease' in text:
                entities['command'] = 'volume_down'
            elif 'set' in text:
                entities['command'] = 'volume_set'
                # Try to extract level
                match = re.search(r'(\d+)%?', text)
                if match:
                    entities['level'] = int(match.group(1))
        
        # App control
        elif any(word in text for word in ['open', 'launch', 'start']):
            match = re.search(r'(?:open|launch|start)\s+(?:the\s+)?(?:app|application)?\s*(.+)', text)
            if match:
                entities['command'] = 'open_app'
                entities['app_name'] = match.group(1).strip()
        
        elif any(word in text for word in ['close', 'quit']):
            match = re.search(r'(?:close|quit)\s+(?:the\s+)?(?:app|application)?\s*(.+)', text)
            if match:
                entities['command'] = 'close_app'
                entities['app_name'] = match.group(1).strip()
        
        # System commands
        elif 'mute' in text:
            entities['command'] = 'mute' if 'unmute' not in text else 'unmute'
        elif 'sleep' in text:
            entities['command'] = 'sleep'
        elif 'shutdown' in text or 'turn off' in text:
            entities['command'] = 'shutdown'
        elif 'restart' in text:
            entities['command'] = 'restart'
        elif 'lock' in text:
            entities['command'] = 'lock'
        
        return entities
    
    def _llm_parse(self, text: str) -> ParsedIntent:
        """
        Use OpenRouter for complex parsing when rule-based fails.
        This is a fallback for ambiguous or complex commands.
        """
        if not self.openrouter:
            return ParsedIntent(
                intent="unknown",
                action_type=ActionType.UNKNOWN,
                confidence=0.3,
                requires_confirmation=True,
                ambiguity_reason="OpenRouter not configured"
            )
        
        # This will be implemented when OpenRouter client is ready
        # For now, return low confidence
        return ParsedIntent(
            intent="unknown",
            action_type=ActionType.UNKNOWN,
            confidence=0.3,
            requires_confirmation=True,
            ambiguity_reason="LLM parsing not yet implemented"
        )
