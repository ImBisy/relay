"""Content enrichment — optional LLM polish layer.

This package only runs *after* a tool has been chosen by code. It can
shape language (subject lines, polite phrasing, formatting) but it
cannot change recipients, dates, or the action itself.
"""
from .engine import ContentEngine
from .schemas import EmailContent, NoteContent, ReminderText

__all__ = ["ContentEngine", "EmailContent", "NoteContent", "ReminderText"]
