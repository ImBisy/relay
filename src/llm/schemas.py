"""Pydantic intent schemas for the Relay extractor.

These are the only datatypes the router speaks. Everything downstream
(tool dispatch, persistence, confirmations) operates on validated
instances of these models. The LLM is responsible for filling them in;
the rest of the system is responsible for what to do with them.
"""
from __future__ import annotations

from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


# --- per-intent schemas -----------------------------------------------------


class _IntentBase(BaseModel):
    """Common config for every intent."""

    model_config = ConfigDict(extra="ignore")


class SendEmailIntent(_IntentBase):
    """User wants to send (or draft) an email."""

    intent: Literal["send_email"] = "send_email"
    recipient_alias: Optional[str] = Field(
        default=None,
        description=(
            "Short label the user uses for the recipient — e.g. 'personal', "
            "'school', 'work', 'mom'. Lowercase. Use this when the user "
            "names a relationship rather than an email address."
        ),
    )
    recipient_email: Optional[str] = Field(
        default=None,
        description=(
            "Literal email address. Only fill this when an explicit address "
            "appears in the user's text."
        ),
    )
    subject: Optional[str] = Field(
        default=None,
        description="Subject line, if the user gave one. Otherwise leave null.",
    )
    body: Optional[str] = Field(
        default=None,
        description=(
            "What the user wants the email to say. Strip framing words like "
            "'saying' or 'telling them' — keep just the message."
        ),
    )
    tone: Optional[Literal[
        "polite", "formal", "casual", "concise", "friendly", "professional",
    ]] = Field(
        default=None,
        description="Tone the user requested, if any.",
    )
    draft_only: bool = Field(
        default=False,
        description="True if the user said 'draft' / 'compose' but not 'send'.",
    )


class ReminderIntent(_IntentBase):
    """User wants Relay to remind them about something."""

    intent: Literal["reminder"] = "reminder"
    text: str = Field(description="What the reminder is about, in plain language.")
    when_text: Optional[str] = Field(
        default=None,
        description=(
            "Natural-language time the user said — e.g. '8pm', "
            "'in 30 minutes', 'tomorrow at noon', 'friday'. Leave null if "
            "no time was mentioned."
        ),
    )


class NoteIntent(_IntentBase):
    """User wants to capture a note for later."""

    intent: Literal["note"] = "note"
    content: str = Field(
        description=(
            "The substance of the note as it should be stored. Drop "
            "framing prefixes like 'note that' or 'jot down'."
        ),
    )
    tags: List[str] = Field(default_factory=list)


class PolishIntent(_IntentBase):
    """User wants to rewrite or improve a piece of text."""

    intent: Literal["polish"] = "polish"
    text: str = Field(
        description=(
            "Text the user wants rewritten. If the user only gave the "
            "instruction (e.g. 'rewrite this to sound professional') "
            "without supplying the text, return an empty string and Relay "
            "will ask for the source text."
        ),
    )
    tone: Optional[Literal[
        "polite", "formal", "professional", "casual", "concise",
        "friendly", "polished",
    ]] = Field(
        default="polished",
        description="Target tone for the rewrite.",
    )


class QueryIntent(_IntentBase):
    """User asked a general-knowledge / informational question."""

    intent: Literal["query"] = "query"
    question: str


class ChatIntent(_IntentBase):
    """Free-form conversation with no tool action."""

    intent: Literal["chat"] = "chat"
    message: str


# A discriminated union — Pydantic picks the right concrete type based
# on the ``intent`` field. Instructor uses this to drive the JSON schema
# it sends to the model.
Intent = Annotated[
    Union[
        SendEmailIntent,
        ReminderIntent,
        NoteIntent,
        PolishIntent,
        QueryIntent,
        ChatIntent,
    ],
    Field(discriminator="intent"),
]


class ParsedRequest(BaseModel):
    """Top-level extraction wrapper.

    The extractor always returns *at least one* intent. Multi-step
    requests like "remind me X and email Y" produce one intent per
    discrete action, in order.
    """

    model_config = ConfigDict(extra="ignore")

    intents: List[Intent] = Field(
        default_factory=list,
        description=(
            "One intent per discrete user action. For multi-step requests, "
            "produce multiple intents in the order the user said them."
        ),
    )

    def is_empty(self) -> bool:
        return not self.intents


__all__ = [
    "ChatIntent",
    "Intent",
    "NoteIntent",
    "ParsedRequest",
    "PolishIntent",
    "QueryIntent",
    "ReminderIntent",
    "SendEmailIntent",
]
