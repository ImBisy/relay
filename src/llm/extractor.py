"""Schema-based intent extraction.

This is the only place in Relay where natural language is interpreted.
Inputs are turned into validated ``Intent`` objects (see ``schemas``)
and handed back to the deterministic router. Tool dispatch,
confirmations, and persistence happen on the structured output.

Two operating modes:

1. **LLM-backed** — when an Instructor-wrapped client is available,
   extraction goes through a fast model (default
   ``qwen/qwen-2.5-7b-instruct:free`` via OpenRouter). Instructor
   handles JSON mode + retries + Pydantic validation.

2. **Fallback** — when no client is configured (offline / tests / no
   API key), a small keyword classifier produces a best-guess
   ``Intent`` so the rest of the system still works. Never returns an
   empty result; never asks the user to rephrase.

The slow model (used by ``ContentEngine`` for polishing) is *not*
touched here — extraction is a fast-path concern.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from .schemas import (
    ChatIntent,
    NoteIntent,
    ParsedRequest,
    PolishIntent,
    QueryIntent,
    ReminderIntent,
    SendEmailIntent,
)

logger = logging.getLogger(__name__)


DEFAULT_FAST_MODEL = "qwen/qwen-2.5-7b-instruct:free"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


_SYSTEM_PROMPT = """You convert raw user input into structured action intents \
for the Relay assistant. Your only job is to identify what the user wants; \
deterministic code in Relay decides which tool to run.

ALWAYS produce at least one intent. If the request contains multiple actions \
("remind me X and email Y"), produce one intent per action, in the order the \
user said them. If the request is ambiguous, return your best-guess single \
intent rather than nothing — never refuse, never ask the user to rephrase.

Available intents:
- send_email: user wants to compose, draft, or send an email
- reminder:   user wants a time-bound reminder ("remind me ...")
- note:       user wants to capture a fact or thought ("note that ...", "jot down ...")
- polish:     user wants you to rewrite/improve a piece of text
- query:      user is asking a general-knowledge question
- chat:       smalltalk or free-form conversation with no tool action

Conventions:
- recipient_alias is a short label like "personal", "school", "work", \
"mom" — keep it lowercase and singular.
- Only fill recipient_email when a literal email address appears in the input.
- For reminders, copy the time string into when_text exactly as the user said \
it (e.g. "8pm", "in 30 minutes", "tomorrow", "friday").
- For notes, content should be the substance only — drop "note that" / \
"jot down" framing.
- For polish, text is what they want rewritten; tone is the requested tone.
- Don't invent recipients, dates, or content the user didn't say.
"""


class IntentExtractor:
    """Turn raw text into a validated ``ParsedRequest``.

    ``client`` is an Instructor-patched OpenAI-compatible client (see
    ``build_default_extractor``) or ``None`` for offline mode.
    """

    def __init__(
        self,
        client: Optional[Any] = None,
        model: str = DEFAULT_FAST_MODEL,
        system_prompt: Optional[str] = None,
        max_retries: int = 2,
    ) -> None:
        self.client = client
        self.model = model
        self.system_prompt = system_prompt or _SYSTEM_PROMPT
        self.max_retries = max_retries

    # ----- public API -----

    @property
    def is_llm_backed(self) -> bool:
        return self.client is not None

    def extract(self, text: str) -> ParsedRequest:
        cleaned = (text or "").strip()
        if not cleaned:
            return ParsedRequest(intents=[ChatIntent(message="")])

        if self.client is None:
            return _fallback_extract(cleaned)

        try:
            request = self.client.chat.completions.create(
                model=self.model,
                response_model=ParsedRequest,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": cleaned},
                ],
                temperature=0,
                max_retries=self.max_retries,
            )
        except Exception as exc:
            logger.warning("LLM extraction failed (%s); using fallback.", exc)
            return _fallback_extract(cleaned)

        if request.is_empty():
            return _fallback_extract(cleaned)
        return request


# ---------------------------------------------------------------------------
# Default-extractor wiring
# ---------------------------------------------------------------------------


def build_default_extractor(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
) -> IntentExtractor:
    """Build an ``IntentExtractor`` from configuration.

    If ``instructor`` / ``openai`` aren't installed, or no key is
    available, returns an extractor with ``client=None`` (fallback
    mode). The router still works — it just won't generalize as well
    on edge cases.
    """
    if not api_key:
        return IntentExtractor(model=model or DEFAULT_FAST_MODEL)
    try:
        import instructor
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - exercised only when missing
        logger.warning("instructor/openai not available (%s); using fallback.", exc)
        return IntentExtractor(model=model or DEFAULT_FAST_MODEL)

    try:
        raw = OpenAI(base_url=base_url, api_key=api_key)
        client = instructor.from_openai(raw, mode=instructor.Mode.JSON)
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("Instructor client init failed (%s); using fallback.", exc)
        return IntentExtractor(model=model or DEFAULT_FAST_MODEL)

    return IntentExtractor(client=client, model=model or DEFAULT_FAST_MODEL)


# ---------------------------------------------------------------------------
# Offline fallback
# ---------------------------------------------------------------------------


_EMAIL_STARTERS = (
    "send an email", "send a email", "send email", "send a message",
    "send mail ", "send mail to",
    "draft an email", "compose an email", "write an email",
    "email ",
)
_REMINDER_STARTERS = (
    "remind me", "set a reminder", "create a reminder",
    "remember to", "don't let me forget", "do not let me forget",
)
_NOTE_STARTERS = (
    "note that", "note:", "take a note", "make a note", "jot down",
    "write down", "capture this", "remember this",
)
_POLISH_STARTERS = (
    "rewrite this", "rewrite that", "polish this", "polish that",
    "improve this", "improve that",
    "make this sound", "make that sound",
    "make this more", "make that more",
    "clean this up", "clean that up",
)
_QUESTION_STARTERS = (
    "what is", "what's", "what are", "who is", "who's", "who are",
    "where is", "where's", "when is", "when's", "why ", "how ",
    "tell me about", "explain", "define",
)
_CONNECTORS_RE = re.compile(
    r"\s+(?:and(?:\s+also)?|then|after that|also)\s+", re.IGNORECASE,
)
_EMAIL_ADDR_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_TONE_RE = re.compile(
    r"\b(?:to\s+sound\s+|sound\s+more\s+|in\s+a\s+|more\s+)"
    r"(polite|formal|professional|casual|concise|friendly)\b",
    re.IGNORECASE,
)


def _fallback_extract(text: str) -> ParsedRequest:
    """Best-effort intent extraction without an LLM.

    Splits compound clauses on simple connectors, classifies each
    clause by leading verb, and returns one ``ParsedRequest`` covering
    the whole input. Always non-empty.
    """
    clauses = _split_compound(text)
    intents = []
    for clause in clauses:
        intents.append(_classify_clause(clause))
    return ParsedRequest(intents=intents)


def _split_compound(text: str) -> list[str]:
    if '"' in text or "'" in text:
        return [text]
    parts = [p.strip() for p in _CONNECTORS_RE.split(text) if p.strip()]
    if len(parts) <= 1:
        return [text]
    if not all(_looks_like_command(p) for p in parts):
        return [text]
    return parts


def _looks_like_command(text: str) -> bool:
    lower = text.lower().strip()
    starters = (
        _EMAIL_STARTERS + _REMINDER_STARTERS + _NOTE_STARTERS
        + _POLISH_STARTERS + _QUESTION_STARTERS
    )
    if any(lower.startswith(s) for s in starters):
        return True
    first = lower.split()[:1]
    if not first:
        return False
    return first[0] in {
        "send", "draft", "compose", "email", "remind", "remember",
        "note", "jot", "capture", "rewrite", "polish", "improve",
        "set", "schedule", "what", "tell", "show", "find", "search",
    }


def _classify_clause(text: str) -> Any:
    cleaned = text.strip()
    lower = cleaned.lower()

    # Polish (must come before email — "rewrite this email" should not be
    # classified as a send_email).
    if any(lower.startswith(p) for p in _POLISH_STARTERS):
        tone_match = _TONE_RE.search(lower)
        tone = tone_match.group(1).lower() if tone_match else None
        body = _strip_prefix(cleaned, _POLISH_STARTERS).strip()
        # "rewrite this to sound professional" → no actual text to polish
        if body.lower().startswith(("to sound", "more")) or not body:
            return PolishIntent(text="", tone=tone or "polished")
        return PolishIntent(text=body, tone=tone or "polished")

    # Email
    if any(lower.startswith(p) for p in _EMAIL_STARTERS) or lower.startswith("email "):
        return _build_email_intent(cleaned)

    # Reminder
    if any(lower.startswith(p) for p in _REMINDER_STARTERS):
        return _build_reminder_intent(cleaned)

    # Note
    if any(lower.startswith(p) for p in _NOTE_STARTERS):
        return _build_note_intent(cleaned)

    # Query (questions)
    if cleaned.endswith("?") or any(lower.startswith(p) for p in _QUESTION_STARTERS):
        return QueryIntent(question=cleaned)

    # Default: chat
    return ChatIntent(message=cleaned)


def _strip_prefix(text: str, prefixes: tuple[str, ...]) -> str:
    lower = text.lower()
    for prefix in prefixes:
        if lower.startswith(prefix):
            return text[len(prefix):].lstrip(" :,.")
    return text


def _build_reminder_intent(text: str) -> ReminderIntent:
    body = _strip_prefix(text, _REMINDER_STARTERS).strip()
    if body.lower().startswith("to "):
        body = body[3:].strip()
    when = _extract_when_phrase(body)
    if when:
        # Drop the time phrase from the reminder text itself.
        body_wo = _remove_when_phrase(body, when).strip()
        if body_wo:
            body = body_wo
    return ReminderIntent(text=body or text, when_text=when)


def _build_note_intent(text: str) -> NoteIntent:
    body = _strip_prefix(text, _NOTE_STARTERS).strip()
    if body.lower().startswith("that "):
        body = body[5:].strip()
    return NoteIntent(content=body or text)


def _build_email_intent(text: str) -> SendEmailIntent:
    lower = text.lower()
    body_text = _strip_prefix(text, _EMAIL_STARTERS).strip()

    recipient_email = None
    addr_match = _EMAIL_ADDR_RE.search(text)
    if addr_match:
        recipient_email = addr_match.group(0)

    recipient_alias = None
    # "send an email to <alias> saying ..."
    alias_match = re.search(
        r"(?:to|for)\s+(?:my\s+)?([a-zA-Z][a-zA-Z\s]*?)"
        r"(?:\s+(?:account|email|mail|address))?"
        r"(?:\s+(?:saying|telling|that|about|regarding|with)|$)",
        body_text, re.IGNORECASE,
    )
    if alias_match and not recipient_email:
        candidate = alias_match.group(1).strip().lower()
        candidate = re.sub(r"\s+", " ", candidate)
        if candidate and len(candidate) <= 40:
            recipient_alias = candidate

    body = None
    body_match = re.search(
        r"(?:saying|telling\s+(?:them|me|him|her))\s+(?:that\s+)?(.+)",
        text, re.IGNORECASE,
    )
    if body_match:
        body = body_match.group(1).strip().rstrip(".")

    draft_only = any(w in lower for w in ("draft ", "compose ")) and "send" not in lower

    return SendEmailIntent(
        recipient_alias=recipient_alias,
        recipient_email=recipient_email,
        body=body,
        draft_only=draft_only,
    )


_WHEN_PATTERNS = [
    re.compile(r"\b(in\s+\d+\s*(?:minute|minutes|min|mins?|hour|hours|hr|hrs))\b", re.IGNORECASE),
    re.compile(r"\b(at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", re.IGNORECASE),
    re.compile(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b", re.IGNORECASE),
    re.compile(r"\b(tomorrow(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?)\b", re.IGNORECASE),
    re.compile(r"\b(today(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?)\b", re.IGNORECASE),
    re.compile(r"\b(tonight)\b", re.IGNORECASE),
    re.compile(
        r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        re.IGNORECASE,
    ),
]


def _extract_when_phrase(text: str) -> Optional[str]:
    for pattern in _WHEN_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def _remove_when_phrase(text: str, when: str) -> str:
    return re.sub(re.escape(when), "", text, count=1, flags=re.IGNORECASE).strip(" ,.")


__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_FAST_MODEL",
    "IntentExtractor",
    "build_default_extractor",
]
