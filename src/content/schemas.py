"""Constrained content schemas used by ``ContentEngine``.

The engine takes one of these dataclasses and returns a polished copy
with the same fields. Recipients, dates, and other action-defining
fields are kept verbatim by the engine — it only reshapes language.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class EmailContent:
    recipient: str
    subject: Optional[str]
    body: str
    tone: Optional[str] = None  # e.g. "polite", "concise", "formal"


@dataclass
class ReminderText:
    text: str
    when: Optional[str] = None


@dataclass
class NoteContent:
    content: str
    tags: List[str] | None = None


@dataclass
class NotificationText:
    text: str
    severity: str = "info"
