"""Tiny offline templates used when no LLM is configured.

These are deterministic, dependency-free, and always produce something
sensible. They never fail and never make up new facts.
"""
from __future__ import annotations

from typing import Optional


def fallback_email_subject(body: str, tone: Optional[str] = None) -> str:
    body = (body or "").strip()
    if not body:
        return "Quick note"
    first_line = body.splitlines()[0]
    snippet = first_line.strip(".!? ")
    if len(snippet) > 60:
        snippet = snippet[:60].rsplit(" ", 1)[0] + "..."
    return snippet or "Quick note"


def polish_reminder_text(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return text
    text = text[0].upper() + text[1:]
    if not text.endswith((".", "!", "?")):
        text += "."
    return text


def polish_note(content: str) -> str:
    return (content or "").strip()
