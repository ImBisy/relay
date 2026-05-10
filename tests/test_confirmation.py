"""Confirmation / cancellation flow against the structured pending store."""
from __future__ import annotations

from typing import Any, Dict, List

from src.chat.chat_service import ChatService
from src.content.engine import ContentEngine
from src.core.orchestrator import RelayOrchestrator
from src.tools import EmailTool, ToolRegistry, ReminderTool, NotesTool, CalendarTool, TimerTool, SystemTool, WebTool


def _build_orchestrator_with_capture(stores) -> tuple[RelayOrchestrator, List[Dict[str, Any]]]:
    sent: List[Dict[str, Any]] = []
    email_tool = EmailTool(
        pending_store=stores["pending"],
        smtp_send_fn=lambda payload: sent.append(payload),
    )
    registry = ToolRegistry()
    registry.register_many([
        ReminderTool(stores["reminders"]),
        NotesTool(stores["notes"]),
        CalendarTool(stores["calendar"]),
        email_tool,
        TimerTool(),
        SystemTool(),
        WebTool(),
    ])
    orchestrator = RelayOrchestrator(
        registry=registry,
        reminders=stores["reminders"],
        notes=stores["notes"],
        calendar=stores["calendar"],
        logs=stores["logs"],
        pending_actions=stores["pending"],
        content_engine=ContentEngine(enabled=False),
        chat_service=ChatService(openrouter_client=None),
        openrouter_client=None,
    )
    return orchestrator, sent


def test_email_confirmation_sends(monkeypatch, stores):
    orchestrator, sent = _build_orchestrator_with_capture(stores)
    # Provide a fake SMTP-capable account so EmailTool's _get_account passes.
    from src.config.settings import config
    config.email.accounts = {
        "Work": {
            "smtp_server": "smtp.example.com",
            "smtp_port": "587",
            "username": "user",
            "password": "pw",
            "from_address": "user@example.com",
        }
    }
    orchestrator.process_input(
        "send an email to test@example.com saying hello there"
    )
    pending = stores["pending"].list_pending()
    assert len(pending) == 1
    orchestrator.process_input("yes")
    assert len(sent) == 1
    assert sent[0]["to"] == "test@example.com"
    assert stores["pending"].list_pending() == []


def test_email_cancellation_does_not_send(stores):
    orchestrator, sent = _build_orchestrator_with_capture(stores)
    orchestrator.process_input(
        "send an email to test@example.com saying hello"
    )
    orchestrator.process_input("no")
    assert sent == []
    assert stores["pending"].list_pending() == []


def test_confirmation_without_pending(stores):
    orchestrator, _ = _build_orchestrator_with_capture(stores)
    response = orchestrator.process_input("yes")
    assert "no pending" in response.lower() or "don't have" in response.lower()
