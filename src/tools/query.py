"""Generic query tool — thin wrapper around the chat service.

In the new architecture, free-form questions are routed to chat at the
router level. This tool exists for backwards compatibility with the
older intent type and for callers that want to route through the tool
layer specifically.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ..agents.openrouter import OpenRouterClient, OpenRouterMessage
from ..core.context import ToolContext
from ..core.safety import SafetyLevel
from .base import BaseTool, ToolResult


class QueryTool(BaseTool):
    name = "query"
    aliases = ["ask"]
    description = "Answer general questions and provide information"
    requires_confirmation = False
    safety_level = SafetyLevel.SAFE
    supported_actions = ["ask"]

    def __init__(self, openrouter_client: Optional[OpenRouterClient] = None) -> None:
        self.openrouter = openrouter_client

    def execute(self, args: Dict[str, Any], ctx: Optional[ToolContext] = None) -> ToolResult:
        if not self.openrouter:
            return ToolResult.failure(
                "I'm not configured to answer questions yet. Please set up OpenRouter.",
                error="llm_not_configured",
            )
        query = args.get("query") or args.get("content") or args.get("question")
        if not query:
            return ToolResult.failure("I didn't catch your question.")
        try:
            messages = [
                OpenRouterMessage(
                    role="system",
                    content=("You are Relay, a helpful and concise AI assistant. "
                             "Provide brief, accurate answers. Keep responses to 2-3 "
                             "sentences when possible."),
                ),
                OpenRouterMessage(role="user", content=query),
            ]
            response = self.openrouter.chat(messages, temperature=0.5, max_tokens=300)
            if not response:
                return ToolResult.failure("I couldn't generate a response.")
            return ToolResult.success(response,
                                      data={"query": query, "answer": response})
        except Exception as exc:
            return ToolResult.failure("Something went wrong", error=str(exc))

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not (args.get("query") or args.get("content") or args.get("question")):
            return False, "Query required"
        return True, None

    def preview(self, args: Dict[str, Any]) -> str:
        return f"Query: {args.get('query') or args.get('content') or ''}"
