"""Deterministic router — turns input into a ``RouterDecision``.

The router is intentionally code-first. It runs three small, fast
checks against the raw input:

1. Is it a yes/no answer to a pending action? → confirmation /
   cancellation.
2. Otherwise, ask the ``IntentExtractor`` for one or more typed intent
   objects. The extractor uses a fast LLM with Pydantic schemas (or a
   keyword fallback when no API key is configured), and is the only
   place in Relay where natural language is *interpreted*.
3. Map each ``Intent`` to an ``ActionStep`` for the orchestrator. Pure
   chat / questions / polish requests bypass tools and route through
   the chat service.

The router does not call tools, does not write to storage, and does
not invent arguments. It produces a structured ``RouterDecision`` and
hands it back to the orchestrator.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from ..llm.extractor import IntentExtractor
from ..llm.schemas import (
    ChatIntent,
    NoteIntent,
    ParsedRequest,
    PolishIntent,
    QueryIntent,
    ReminderIntent,
    SendEmailIntent,
)
from .action_plan import ActionPlan, ActionStep, RouterDecision, StepStatus

logger = logging.getLogger(__name__)


_CONFIRMATION_WORDS = {
    "yes", "yep", "yeah", "sure", "ok", "okay", "confirm", "confirmed",
    "do it", "send it", "go ahead", "proceed", "send", "approve",
}
_CANCELLATION_WORDS = {
    "no", "nope", "cancel", "stop", "abort", "nevermind", "never mind",
    "discard", "scratch that", "forget it",
}


class Router:
    """Decide what to do with a piece of user input."""

    def __init__(self, extractor: Optional[IntentExtractor] = None) -> None:
        self.extractor = extractor or IntentExtractor()

    # ----- public API -----

    def route(self, text: str) -> RouterDecision:
        normalized = self._normalize(text)
        if not normalized:
            return RouterDecision.clarification(
                "I didn't catch anything — could you say that again?"
            )

        if self._is_pure_confirmation(normalized):
            return RouterDecision.confirmation()
        if self._is_pure_cancellation(normalized):
            return RouterDecision.cancellation()

        try:
            request = self.extractor.extract(normalized)
        except Exception as exc:  # pragma: no cover - extractor has its own fallback
            logger.warning("Extractor raised; routing as chat. (%s)", exc)
            return RouterDecision.chat(text)

        return self._decision_from_request(request, original=text,
                                            normalized=normalized)

    # ----- helpers -----

    @staticmethod
    def _normalize(text: str) -> str:
        if not text:
            return ""
        cleaned = text.strip()
        cleaned = re.sub(r"^\s*relay[\s,:.-]+", "", cleaned, flags=re.IGNORECASE)
        return cleaned

    @staticmethod
    def _is_pure_confirmation(text: str) -> bool:
        t = text.lower().rstrip(".!?")
        if t in _CONFIRMATION_WORDS:
            return True
        if t.startswith("yes ") and len(t) <= 12:
            return True
        return False

    @staticmethod
    def _is_pure_cancellation(text: str) -> bool:
        t = text.lower().rstrip(".!?")
        if t in _CANCELLATION_WORDS:
            return True
        if t.startswith("no ") and len(t) <= 12:
            return True
        return False

    def _decision_from_request(
        self, request: ParsedRequest, *, original: str, normalized: str,
    ) -> RouterDecision:
        if request.is_empty():
            return RouterDecision.chat(original)

        # Pure-chat / pure-question / standalone polish requests don't
        # have a deterministic tool — they go through the chat service.
        if len(request.intents) == 1:
            only = request.intents[0]
            if isinstance(only, ChatIntent):
                return RouterDecision.chat(only.message or original)
            if isinstance(only, QueryIntent):
                return RouterDecision.chat(only.question or original)
            if isinstance(only, PolishIntent):
                return RouterDecision.chat(_polish_chat_prompt(only, original))

        steps: List[ActionStep] = []
        for intent in request.intents:
            step = _intent_to_step(intent, normalized, original)
            if step is not None:
                steps.append(step)
        if not steps:
            return RouterDecision.chat(original)
        return RouterDecision.command(ActionPlan(steps=steps))


# ---------------------------------------------------------------------------
# Intent → ActionStep mapping
# ---------------------------------------------------------------------------


def _intent_to_step(intent: Any, clause: str, original: str) -> Optional[ActionStep]:
    """Map a single ``Intent`` instance to a deterministic action step.

    Returns ``None`` for intent kinds that aren't tool-backed (chat /
    query / polish). Those are handled by the router's single-intent
    fast path; if they appear inside a multi-intent request they are
    silently dropped so any sibling tool intents still execute.
    """
    if isinstance(intent, SendEmailIntent):
        return ActionStep(
            tool_name="email",
            args=_email_args(intent),
            raw_clause=clause,
            status=StepStatus.PENDING,
        )
    if isinstance(intent, ReminderIntent):
        return ActionStep(
            tool_name="reminder",
            args=_reminder_args(intent, clause),
            raw_clause=clause,
            status=StepStatus.PENDING,
        )
    if isinstance(intent, NoteIntent):
        return ActionStep(
            tool_name="note",
            args=_note_args(intent),
            raw_clause=clause,
            status=StepStatus.PENDING,
        )
    if isinstance(intent, (ChatIntent, QueryIntent, PolishIntent)):
        return None
    logger.warning("Unmapped intent type: %s", type(intent).__name__)
    return None


def _email_args(intent: SendEmailIntent) -> Dict[str, Any]:
    args: Dict[str, Any] = {"raw_input": ""}
    if intent.recipient_email:
        args["recipient_email"] = intent.recipient_email
    if intent.recipient_alias:
        args["recipient_alias"] = intent.recipient_alias
    if intent.subject:
        args["subject"] = intent.subject
    if intent.body:
        args["body"] = intent.body
    if intent.tone:
        args["tone"] = intent.tone
    if intent.draft_only:
        args["draft_only"] = True
    return args


def _reminder_args(intent: ReminderIntent, clause: str) -> Dict[str, Any]:
    text = (intent.text or "").strip()
    when = (intent.when_text or "").strip()
    # ``ReminderTool._resolve_remind_at`` parses time phrases out of the
    # reminder text. If the LLM stripped the time into ``when_text``, we
    # re-attach it so the existing time parser still finds it.
    if when and not _contains_time_phrase(text):
        text_with_time = f"{text} {when}".strip()
    else:
        text_with_time = text or clause
    return {
        "reminder_action": "create",
        "reminder_text": text_with_time,
        "raw_input": clause,
    }


def _note_args(intent: NoteIntent) -> Dict[str, Any]:
    return {
        "note_action": "add",
        "note_text": (intent.content or "").strip(),
        "tags": list(intent.tags or []),
        "raw_input": intent.content or "",
    }


_TIME_PHRASE_RE = re.compile(
    r"\b(in\s+\d+\s*(?:minute|minutes|min|mins?|hour|hours|hr|hrs?)|"
    r"at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?|"
    r"\d{1,2}(?::\d{2})?\s*(?:am|pm)|"
    r"tomorrow|today|tonight|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)


def _contains_time_phrase(text: str) -> bool:
    if not text:
        return False
    return _TIME_PHRASE_RE.search(text) is not None


def _polish_chat_prompt(intent: PolishIntent, original: str) -> str:
    """Frame a polish request as a chat message the LLM can answer.

    Standalone polish requests (no other action) flow through the chat
    service. We hand the chat layer a prompt that includes the user's
    target text and tone so the response is the rewritten text itself.
    """
    text = (intent.text or "").strip()
    tone = intent.tone or "polished"
    if text:
        return (
            f"Rewrite the following so it sounds {tone}. "
            f"Return only the rewritten text.\n\n{text}"
        )
    return original
