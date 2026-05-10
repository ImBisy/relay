"""LLM-powered intent extraction for Relay.

The router and orchestrator stay deterministic. This module is the one
place where natural language is turned into typed ``Intent`` objects.
Tool dispatch, confirmations, and persistence happen on the structured
output — not on the model.
"""
from .extractor import IntentExtractor, build_default_extractor
from .schemas import (
    ChatIntent,
    Intent,
    NoteIntent,
    ParsedRequest,
    PolishIntent,
    QueryIntent,
    ReminderIntent,
    SendEmailIntent,
)

__all__ = [
    "IntentExtractor",
    "build_default_extractor",
    "ChatIntent",
    "Intent",
    "NoteIntent",
    "ParsedRequest",
    "PolishIntent",
    "QueryIntent",
    "ReminderIntent",
    "SendEmailIntent",
]
