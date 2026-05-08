"""Content engine behaviour — deterministic fallback when no LLM."""
from __future__ import annotations

from src.content.engine import ContentEngine


def test_email_enrichment_without_llm_keeps_body():
    engine = ContentEngine(enabled=False)
    out = engine.enrich_email(body="please review", subject=None,
                                recipient="t@e.com")
    assert out["body"] == "please review"
    assert out["subject"]  # generated from body


def test_reminder_polish_without_llm():
    engine = ContentEngine(enabled=False)
    text = engine.polish_reminder("submit the form")
    assert text.endswith(".")
    assert text[0].isupper()


def test_note_polish_without_llm_preserves_content():
    engine = ContentEngine(enabled=False)
    assert engine.polish_note("  some note  ") == "some note"


class _FakeOpenRouter:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append(messages)
        return self.response


def test_email_enrichment_with_llm_uses_response():
    fake = _FakeOpenRouter('{"subject": "Quick note", "body": "Hi there."}')
    engine = ContentEngine(openrouter_client=fake, enabled=True)
    out = engine.enrich_email(body="hi", subject=None,
                                recipient="t@e.com", tone="friendly")
    assert out["subject"] == "Quick note"
    assert out["body"] == "Hi there."
    assert fake.calls  # the engine made the call


def test_email_enrichment_with_llm_falls_back_on_garbage():
    fake = _FakeOpenRouter("not json at all")
    engine = ContentEngine(openrouter_client=fake, enabled=True)
    out = engine.enrich_email(body="hi", subject="Original",
                                recipient="t@e.com")
    assert out["body"] == "hi"
    assert out["subject"] == "Original"
