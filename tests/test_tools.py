"""Tool-level smoke tests."""
from __future__ import annotations

from src.tools import EmailTool, NotesTool, ReminderTool


def test_reminder_tool_validate_requires_text():
    tool = ReminderTool()
    ok, error = tool.validate({})
    assert not ok and error


def test_reminder_tool_creates_record(stores):
    tool = ReminderTool(stores["reminders"])
    result = tool.execute({"reminder_text": "submit form"})
    assert result.status.value == "success"
    assert stores["reminders"].list_active()


def test_notes_tool_strips_prefix(stores):
    tool = NotesTool(stores["notes"])
    tool.execute({"content": "note: meeting moved to Tuesday"})
    notes = stores["notes"].list_recent()
    assert notes
    assert "meeting moved" in notes[0].content


def test_email_tool_stages_pending(stores):
    tool = EmailTool(pending_store=stores["pending"])
    result = tool.execute({
        "recipient_email": "t@example.com",
        "body": "hello",
    })
    assert result.status.value == "needs_confirmation"
    assert result.action_id is not None
    pending = stores["pending"].list_pending()
    assert len(pending) == 1
    assert pending[0].tool_name == "email"


def test_email_tool_validate_requires_recipient_and_body():
    tool = EmailTool()
    ok, _ = tool.validate({})
    assert not ok
    ok, _ = tool.validate({"recipient_email": "t@e.com"})
    assert not ok
    ok, _ = tool.validate({"recipient_email": "t@e.com", "body": "hi"})
    assert ok
