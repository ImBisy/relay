"""End-to-end orchestrator behaviour against in-memory stores."""
from __future__ import annotations


def test_reminder_creates_storage_record(orchestrator, stores):
    response = orchestrator.process_input("remind me to call mom at 5pm")
    assert "Reminder set" in response or "Captured" in response
    items = stores["reminders"].list_active()
    assert len(items) == 1
    assert "call mom" in items[0].text.lower()


def test_note_creates_storage_record(orchestrator, stores):
    orchestrator.process_input("take a note: biology mock is on Tuesday")
    notes = stores["notes"].list_recent()
    assert len(notes) == 1
    assert "biology" in notes[0].content.lower()


def test_email_stages_pending_action(orchestrator, stores):
    orchestrator.process_input(
        "send an email to test@example.com saying hello there"
    )
    pending = stores["pending"].list_pending()
    assert len(pending) == 1
    assert pending[0].tool_name == "email"
    args = pending[0].args
    assert args["recipient_email"] == "test@example.com"
    # No mail was sent yet — no SMTP attempt because we never hit confirm.


def test_cancellation_clears_pending(orchestrator, stores):
    orchestrator.process_input(
        "send an email to test@example.com saying hello"
    )
    assert len(stores["pending"].list_pending()) == 1
    orchestrator.process_input("cancel")
    assert stores["pending"].list_pending() == []


def test_compound_plan_creates_two_records(orchestrator, stores):
    orchestrator.process_input(
        "remind me to call mom and take a note about lunch"
    )
    assert len(stores["reminders"].list_active()) == 1
    assert len(stores["notes"].list_recent()) == 1


def test_chat_fallback_when_no_llm(orchestrator):
    response = orchestrator.process_input("what's the capital of france?")
    assert "OPENROUTER_API_KEY" in response or "Could you" in response or "rephrase" in response


def test_logs_capture_every_step(orchestrator, stores):
    orchestrator.process_input("take a note: review design mockups")
    statuses = {le.status for le in stores["logs"].list_recent(limit=50)}
    assert "routing" in statuses
    assert any(s.startswith("plan_") or s.startswith("step_") for s in statuses)
