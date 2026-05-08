"""
General query tool for questions and information retrieval.
Uses OpenRouter for answering general knowledge questions.
"""
from typing import Dict, Any, Optional
from .base import BaseTool, ToolResult
from ..agents.openrouter import OpenRouterClient, OpenRouterMessage


class QueryTool(BaseTool):
    """
    General query tool for answering questions.
    
    Routes to OpenRouter for:
    - General knowledge questions
    - Explanations
    - Advice
    """
    
    name = "query"
    description = "Answer general questions and provide information"
    requires_confirmation = False
    
    def __init__(self, openrouter_client: Optional[OpenRouterClient] = None):
        self.openrouter = openrouter_client
    
    def execute(self, entities: Dict[str, Any]) -> ToolResult:
        """Execute query."""
        if not self.openrouter:
            return ToolResult.failure(
                "I'm not configured to answer questions yet. Please set up OpenRouter."
            )
        
        query = entities.get('query') or entities.get('content') or entities.get('question')
        
        if not query:
            return ToolResult.failure("I didn't catch your question")
        
        try:
            response = self._ask_openrouter(query)
            
            if response:
                return ToolResult.success(
                    response,
                    data={'query': query, 'answer': response}
                )
            else:
                return ToolResult.failure("I couldn't generate a response")
                
        except Exception as e:
            return ToolResult.failure("Something went wrong", error=str(e))
    
    def _ask_openrouter(self, query: str) -> Optional[str]:
        """Send query to OpenRouter."""
        messages = [
            OpenRouterMessage(
                role="system",
                content="""You are Relay, a helpful and concise AI assistant.
Provide brief, accurate answers. Be efficient and direct.
Keep responses to 2-3 sentences when possible.
If you don't know something, say so clearly."""
            ),
            OpenRouterMessage(role="user", content=query)
        ]
        
        return self.openrouter.chat(messages, temperature=0.5, max_tokens=300)
    
    def validate(self, entities: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate query entities."""
        query = entities.get('query') or entities.get('content') or entities.get('question')
        
        if not query:
            return False, "Query required"
        
        return True, None
