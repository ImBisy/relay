"""Chat service — LLM-only path for general conversation.

This service is invoked only when the deterministic router decides the
input is *not* a command. It cannot dispatch tools, change state, or
trigger side effects on its own. The orchestrator routes here as a
fallback after rule-based command parsing has clearly declined.
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


_DEFAULT_SYSTEM_PROMPT = (
    "You are Relay, a calm and capable AI assistant. Keep replies short "
    "(1-2 sentences when possible), grounded, and helpful. If the user "
    "asks for an action you can perform — sending email, taking notes, "
    "setting reminders, scheduling events — describe what they should "
    "say so Relay can route it as a command. Never claim to have "
    "performed an action; you cannot run tools from this conversation."
)


class ChatService:
    """Free-form chat with optional history."""

    def __init__(self, openrouter_client: Optional[Any] = None,
                 system_prompt: Optional[str] = None,
                 history_limit: int = 8) -> None:
        self.openrouter = openrouter_client
        self.system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        self.history_limit = history_limit
        self._history: List[Any] = []

    def is_available(self) -> bool:
        return self.openrouter is not None

    def reply(self, text: str) -> Optional[str]:
        if not text or not text.strip():
            return None
        if not self.openrouter:
            return ("I'm not configured for chat yet — set OPENROUTER_API_KEY "
                    "and try again.")
        try:
            from ..agents.openrouter import OpenRouterMessage
            messages: List[OpenRouterMessage] = [
                OpenRouterMessage(role="system", content=self.system_prompt)
            ]
            messages.extend(self._history[-self.history_limit:])
            messages.append(OpenRouterMessage(role="user", content=text))
            response = self.openrouter.chat(messages, temperature=0.6, max_tokens=300)
            if not response:
                return None
            self._history.append(OpenRouterMessage(role="user", content=text))
            self._history.append(OpenRouterMessage(role="assistant", content=response))
            return response
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Chat service failed: %s", exc)
            return None

    def reset(self) -> None:
        self._history = []
