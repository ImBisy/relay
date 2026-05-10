"""Tests for the schema-based intent extractor.

These exercise the offline / fallback path (``client=None``). The
LLM-backed path is identical at the API surface — the only difference
is that Instructor fills in the ``ParsedRequest`` from a real model
response. The fallback path must already cover every acceptance test
the user specified, so the system stays usable with no API key.
"""
from __future__ import annotations

import pytest

from src.core.action_plan import RouteKind
from src.core.router import Router
from src.llm.extractor import IntentExtractor
from src.llm.schemas import (
    ChatIntent,
    NoteIntent,
    PolishIntent,
    ReminderIntent,
    SendEmailIntent,
)


@pytest.fixture
def extractor():
    return IntentExtractor(client=None)


# ----- acceptance tests from the spec -----


def test_acceptance_reminder_with_time(extractor):
    request = extractor.extract("remind me 8pm meeting")
    assert len(request.intents) == 1
    intent = request.intents[0]
    assert isinstance(intent, ReminderIntent)
    assert "meeting" in intent.text.lower()
    assert intent.when_text and "8pm" in intent.when_text.lower()


def test_acceptance_email_with_alias(extractor):
    request = extractor.extract(
        "send an email to personal saying meeting moved"
    )
    assert len(request.intents) == 1
    intent = request.intents[0]
    assert isinstance(intent, SendEmailIntent)
    assert intent.recipient_alias == "personal"
    assert intent.body and "meeting moved" in intent.body.lower()


def test_acceptance_note_with_day(extractor):
    request = extractor.extract("note that chemistry test is friday")
    assert len(request.intents) == 1
    intent = request.intents[0]
    assert isinstance(intent, NoteIntent)
    assert "chemistry" in intent.content.lower()


def test_acceptance_polish_request(extractor):
    request = extractor.extract("rewrite this to sound professional")
    assert len(request.intents) == 1
    intent = request.intents[0]
    assert isinstance(intent, PolishIntent)
    assert intent.tone in {"professional", "polished"}


# ----- general behavior -----


def test_never_returns_empty_intents(extractor):
    """The system must never refuse to interpret input."""
    for raw in [
        "asdf qwer",
        "hello there",
        "the sky is blue",
        "lol",
        "?!",
    ]:
        request = extractor.extract(raw)
        assert request.intents, f"empty for {raw!r}"


def test_compound_remind_and_note(extractor):
    request = extractor.extract(
        "remind me to call mom and take a note about lunch"
    )
    kinds = [type(i).__name__ for i in request.intents]
    assert "ReminderIntent" in kinds
    assert "NoteIntent" in kinds


def test_chat_falls_through(extractor):
    """Conversational input lands on a non-tool intent so the router
    sends it to the chat service."""
    from src.llm.schemas import QueryIntent

    request = extractor.extract("hello there how are you doing today")
    assert request.intents
    assert isinstance(request.intents[0], (ChatIntent, QueryIntent))


def test_question_routes_through_chat():
    router = Router(IntentExtractor(client=None))
    decision = router.route("what is the capital of france?")
    assert decision.kind == RouteKind.CHAT


def test_polish_routes_through_chat():
    router = Router(IntentExtractor(client=None))
    decision = router.route("rewrite this to sound professional")
    assert decision.kind == RouteKind.CHAT


def test_reminder_with_time_phrase_preserved_for_router():
    """The router must hand the reminder tool a time-bearing string so
    its existing time parser can populate ``remind_at``."""
    router = Router(IntentExtractor(client=None))
    decision = router.route("remind me about the meeting at 8pm")
    assert decision.kind == RouteKind.COMMAND
    step = decision.plan.steps[0]
    assert step.tool_name == "reminder"
    text = step.args["reminder_text"].lower()
    assert "8pm" in text
