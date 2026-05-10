"""Shared fixtures for the Relay test suite."""
from __future__ import annotations

import pytest

from src.chat.chat_service import ChatService
from src.content.engine import ContentEngine
from src.core.orchestrator import RelayOrchestrator
from src.core.router import Router
from src.llm.extractor import IntentExtractor
from src.personality.responder import PersonalityEngine
from src.storage import (
    CalendarStore,
    Database,
    LogsStore,
    NotesStore,
    PendingActionsStore,
    RemindersStore,
)


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "relay.sqlite")


@pytest.fixture
def stores(db):
    return {
        "reminders": RemindersStore(db),
        "notes": NotesStore(db),
        "calendar": CalendarStore(db),
        "logs": LogsStore(db),
        "pending": PendingActionsStore(db),
    }


@pytest.fixture
def extractor():
    """Offline extractor — exercises the deterministic fallback path."""
    return IntentExtractor(client=None)


@pytest.fixture
def orchestrator(stores, extractor):
    return RelayOrchestrator(
        reminders=stores["reminders"],
        notes=stores["notes"],
        calendar=stores["calendar"],
        logs=stores["logs"],
        pending_actions=stores["pending"],
        content_engine=ContentEngine(enabled=False),
        chat_service=ChatService(openrouter_client=None),
        personality=PersonalityEngine(),
        router=Router(extractor),
        extractor=extractor,
        openrouter_client=None,
    )
