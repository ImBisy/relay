"""
Main orchestrator - coordinates input, processing, and output.
"""
from typing import Optional, Dict, Any, Callable
import logging

from ..config.settings import config
from ..intent.parser import IntentParser
from ..intent.models import ParsedIntent, ActionType
from ..personality.responder import PersonalityEngine, ResponseContext
from ..tools.base import ToolResult, ToolResultStatus
from ..tools.email import EmailTool
from ..tools.calendar import CalendarTool
from ..tools.reminder import ReminderTool
from ..tools.notes import NotesTool
from ..tools.timer import TimerTool
from ..tools.system import SystemTool
from ..agents.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


class RelayOrchestrator:
    """
    Main orchestrator for the Relay assistant.
    
    Coordinates:
    - Intent parsing (rule-based + OpenRouter fallback)
    - Tool routing and execution
    - Response generation with personality
    - Confirmation handling
    """
    
    def __init__(self):
        """Initialize the orchestrator."""
        # Initialize OpenRouter if configured
        self.openrouter: Optional[OpenRouterClient] = None
        if config.api.openrouter_api_key:
            self.openrouter = OpenRouterClient(
                api_key=config.api.openrouter_api_key,
                base_url=config.api.openrouter_base_url,
                model=config.api.openrouter_model
            )
        
        # Initialize components
        self.intent_parser = IntentParser(self.openrouter)
        self.personality = PersonalityEngine()
        
        # Initialize tools
        self.tools = self._init_tools()
        
        # Confirmation callbacks
        self.confirmation_callbacks: Dict[str, Callable] = {}
        
        # Output callbacks
        self.response_callback: Optional[Callable[[str], None]] = None
        self.notification_callback: Optional[Callable[[str], None]] = None
    
    def _init_tools(self) -> Dict[str, Any]:
        """Initialize all tools."""
        return {
            ActionType.EMAIL.value: EmailTool(),
            ActionType.CALENDAR.value: CalendarTool(),
            ActionType.REMINDER.value: ReminderTool(self._on_notification),
            ActionType.NOTE.value: NotesTool(),
            ActionType.TIMER.value: TimerTool(self._on_notification),
            ActionType.SYSTEM.value: SystemTool(),
        }
    
    def _on_notification(self, message: str):
        """Handle notifications from tools."""
        if self.notification_callback:
            self.notification_callback(message)
    
    def set_response_callback(self, callback: Callable[[str], None]):
        """Set callback for responses."""
        self.response_callback = callback
    
    def set_notification_callback(self, callback: Callable[[str], None]):
        """Set callback for notifications."""
        self.notification_callback = callback
    
    def process_input(self, text: str) -> str:
        """
        Process user input and generate response.
        
        Args:
            text: User input text
            
        Returns:
            Response text
        """
        logger.info(f"Processing input: {text}")
        
        # 1. Parse intent
        intent = self.intent_parser.parse(text)
        
        # 2. Handle low confidence
        if not intent.is_confident(0.7):
            response = self._handle_low_confidence(intent)
            self._output(response)
            return response
        
        # 3. Route to appropriate tool
        result = self._execute_intent(intent)
        
        # 4. Generate response
        response = self._generate_response(intent, result)
        
        # 5. Output
        self._output(response)
        
        return response
    
    def _execute_intent(self, intent: ParsedIntent) -> ToolResult:
        """Execute the parsed intent."""
        action_type = intent.action_type.value
        
        # Get tool
        tool = self.tools.get(action_type)
        
        if not tool:
            return ToolResult.failure(
                f"Tool for {action_type} not available",
                error="Tool not implemented"
            )
        
        # Execute
        try:
            result = tool.execute(intent.entities)
            return result
        except Exception as e:
            logger.exception(f"Error executing {action_type}")
            return ToolResult.failure(
                "Something went wrong",
                error=str(e)
            )
    
    def _generate_response(self, intent: ParsedIntent, result: ToolResult) -> str:
        """Generate response based on intent and result."""
        context = ResponseContext(
            action_type=intent.action_type.value,
            success=result.status == ToolResultStatus.SUCCESS,
            requires_confirmation=result.requires_confirmation,
            urgent=False,
            error=result.error,
            user_name=config.user.name
        )
        
        details = result.data or {}
        
        # Handle confirmation needed
        if result.status == ToolResultStatus.NEEDS_CONFIRMATION:
            # Store for later confirmation
            if result.data and 'email_id' in result.data:
                self.confirmation_callbacks[result.data['email_id']] = \
                    lambda: self.tools[ActionType.EMAIL.value].confirm_send(result.data['email_id'])
            
            return result.message + " " + (result.confirmation_prompt or "Confirm?")
        
        # Handle failure with retry
        if result.status == ToolResultStatus.FAILURE:
            # Check if we should retry with OpenRouter
            if self.openrouter and intent.confidence < 0.9:
                # Try once more with LLM guidance
                return self._retry_with_llm(intent, result)
            
            return self.personality.generate_response(context, details)
        
        # Success
        return self.personality.generate_response(context, details)
    
    def _retry_with_llm(self, intent: ParsedIntent, failed_result: ToolResult) -> str:
        """Retry failed action with LLM guidance."""
        logger.info("Retrying with OpenRouter assistance")
        
        if not self.openrouter:
            context = ResponseContext(
                action_type=intent.action_type.value,
                success=False,
                requires_confirmation=False,
                error="retry"
            )
            return self.personality.generate_response(context)
        
        # Ask LLM to help fix the entities
        from ..agents.openrouter import OpenRouterMessage
        
        messages = [
            OpenRouterMessage(role="system", content="""You are helping a voice assistant correct an action.
The previous attempt failed. Suggest corrected entities to make the action succeed.
Output only a JSON object with the corrected entities."""),
            OpenRouterMessage(role="user", content=f"""Original intent: {intent.intent}
Entities: {intent.entities}
Error: {failed_result.error}

Suggest corrected entities.""")
        ]
        
        response = self.openrouter.chat(messages, temperature=0.2)
        
        if response:
            try:
                import json
                corrected = json.loads(response)
                intent.entities.update(corrected)
                
                # Retry
                new_result = self._execute_intent(intent)
                
                if new_result.status == ToolResultStatus.SUCCESS:
                    context = ResponseContext(
                        action_type=intent.action_type.value,
                        success=True,
                        requires_confirmation=False
                    )
                    return self.personality.generate_response(context, new_result.data)
            except Exception as e:
                logger.error(f"Retry failed: {e}")
        
        # Retry failed, return original error handling
        context = ResponseContext(
            action_type=intent.action_type.value,
            success=False,
            requires_confirmation=False,
            error="retry"
        )
        return self.personality.generate_response(context)
    
    def _handle_low_confidence(self, intent: ParsedIntent) -> str:
        """Handle low confidence parsing - use conversation mode."""
        # If OpenRouter is available, have a conversation
        if self.openrouter:
            try:
                from ..agents.openrouter import OpenRouterMessage
                
                messages = [
                    OpenRouterMessage(role="system", content="""You are Relay, a calm and efficient AI assistant for macOS.
You help with emails, calendar, reminders, notes, timers, and general questions.
Be concise, professional, and occasionally witty. Keep responses brief - one or two sentences max.
If the user wants to do something specific you can't help with, suggest what you can do instead."""),
                    OpenRouterMessage(role="user", content=intent.raw_input)
                ]
                
                response = self.openrouter.chat(messages, temperature=0.7)
                if response:
                    return response
            except Exception as e:
                logger.warning(f"OpenRouter conversation failed: {e}")
        
        # Fallback to personality-based clarification
        if intent.ambiguity_reason:
            return self.personality.clarification(intent.ambiguity_reason)
        return self.personality.clarification()
    
    def _output(self, text: str):
        """Output response."""
        if self.response_callback:
            self.response_callback(text)
        
        # Also log
        logger.info(f"Response: {text}")
    
    def confirm_action(self, action_id: str) -> str:
        """Confirm a pending action."""
        if action_id not in self.confirmation_callbacks:
            return "No pending action found."
        
        callback = self.confirmation_callbacks[action_id]
        
        try:
            result = callback()
            if isinstance(result, ToolResult):
                context = ResponseContext(
                    action_type="email",
                    success=result.status == ToolResultStatus.SUCCESS,
                    requires_confirmation=False
                )
                response = self.personality.generate_response(context, result.data)
            else:
                response = "Confirmed and executed."
        except Exception as e:
            logger.exception("Error confirming action")
            response = f"Could not complete action: {e}"
        
        # Clean up
        del self.confirmation_callbacks[action_id]
        
        self._output(response)
        return response
    
    def cancel_action(self, action_id: str) -> str:
        """Cancel a pending action."""
        if action_id not in self.confirmation_callbacks:
            return "No pending action found."
        
        # Try to cancel via tool
        if action_id.startswith('email_'):
            tool = self.tools.get(ActionType.EMAIL.value)
            if tool and hasattr(tool, 'cancel_send'):
                tool.cancel_send(action_id)
        
        del self.confirmation_callbacks[action_id]
        
        response = "Action cancelled."
        self._output(response)
        return response
    
    def greeting(self) -> str:
        """Generate greeting."""
        return self.personality.greeting()
