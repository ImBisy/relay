"""Chat service — separate boundary, never dispatches tools."""
from __future__ import annotations

from src.chat.chat_service import ChatService


class _FakeOpenRouter:
    def __init__(self, response):
        self.response = response

    def chat(self, messages, **kwargs):
        return self.response


def test_chat_without_llm_returns_friendly_message():
    chat = ChatService(openrouter_client=None)
    reply = chat.reply("hello")
    assert reply
    assert "OPENROUTER_API_KEY" in reply


def test_chat_with_llm_returns_response_and_keeps_history():
    chat = ChatService(openrouter_client=_FakeOpenRouter("howdy"))
    reply = chat.reply("hi")
    assert reply == "howdy"
    chat.reply("how are you?")
    assert len(chat._history) == 4  # user/assistant pairs * 2


def test_chat_empty_input_returns_none():
    chat = ChatService(openrouter_client=_FakeOpenRouter("ignored"))
    assert chat.reply("") is None
    assert chat.reply("   ") is None
