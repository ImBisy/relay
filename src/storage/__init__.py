"""Local-first persistence layer for Relay.

Provides SQLite-backed stores for reminders, notes, calendar events,
activity logs, and pending actions. Tools and services use these stores
directly; the orchestrator does not own persistence.
"""
from .db import Database, get_default_db, set_default_db
from .models import (
    Reminder,
    Note,
    CalendarEvent,
    ActionLogEntry,
    PendingAction,
)
from .reminders_store import RemindersStore
from .notes_store import NotesStore
from .calendar_store import CalendarStore
from .logs_store import LogsStore
from .pending_actions_store import PendingActionsStore

__all__ = [
    "Database",
    "get_default_db",
    "set_default_db",
    "Reminder",
    "Note",
    "CalendarEvent",
    "ActionLogEntry",
    "PendingAction",
    "RemindersStore",
    "NotesStore",
    "CalendarStore",
    "LogsStore",
    "PendingActionsStore",
]
