"""Deterministic router — turns input into a ``RouterDecision``.

The router is intentionally code-first:
- detects confirmation / cancellation responses with simple word lists,
- splits compound requests on connectors like "and" / "then" / "also",
  but only when both halves parse to known commands,
- delegates per-clause parsing to ``IntentParser`` (rule-based regex),
- falls back to ``RouteKind.CHAT`` when the input has no command verbs
  but still looks conversational.

No LLMs, no probabilistic guessing in this layer.
"""
from __future__ import annotations

import re
from typing import List, Optional

from ..intent.models import ActionType, ParsedIntent
from ..intent.parser import IntentParser
from .action_plan import ActionPlan, ActionStep, RouterDecision, StepStatus


# Canonical action tokens used to attach a clause to a tool name. Keeps
# the router and the tool registry decoupled from the legacy ActionType
# enum at the call site.
_ACTION_TO_TOOL = {
    ActionType.EMAIL: "email",
    ActionType.CALENDAR: "calendar",
    ActionType.REMINDER: "reminder",
    ActionType.NOTE: "note",
    ActionType.TIMER: "timer",
    ActionType.SYSTEM: "system",
    ActionType.WEB: "web",
    ActionType.QUERY: "query",
}


_CONFIRMATION_WORDS = {
    "yes", "yep", "yeah", "sure", "ok", "okay", "confirm", "confirmed",
    "do it", "send it", "go ahead", "proceed", "send", "approve",
}

_CANCELLATION_WORDS = {
    "no", "nope", "cancel", "stop", "abort", "nevermind", "never mind",
    "discard", "scratch that", "forget it",
}

_CHAT_TRIGGERS = {
    "what is", "what's", "who is", "who's", "explain", "tell me about",
    "how do i", "how do you", "why", "how much", "how many",
    "define", "what does",
}

_CONNECTORS = re.compile(
    r"\s+(?:and(?:\s+also)?|then|after that|also)\s+",
    re.IGNORECASE,
)


class Router:
    """Decide what to do with a piece of user input."""

    def __init__(self, parser: Optional[IntentParser] = None) -> None:
        self.parser = parser or IntentParser()

    # ----- public API -----

    def route(self, text: str) -> RouterDecision:
        normalized = self._normalize(text)
        if not normalized:
            return RouterDecision.clarification("empty input")

        # 1. Simple confirmation / cancellation responses.
        if self._is_pure_confirmation(normalized):
            return RouterDecision.confirmation()
        if self._is_pure_cancellation(normalized):
            return RouterDecision.cancellation()

        # 2. Try to parse as a (possibly compound) command first.
        plan = self._try_plan(text, normalized)
        if plan is not None:
            # Free-form questions parse as QUERY but the answer always comes
            # from the chat service — there is no deterministic tool for
            # general knowledge. Route them through chat to keep the LLM
            # boundary clean.
            if (len(plan.steps) == 1
                    and plan.steps[0].tool_name == "query"):
                return RouterDecision.chat(text)
            return RouterDecision.command(plan)

        # 3. Fall through to chat for question-style input.
        if self._looks_like_chat(normalized):
            return RouterDecision.chat(text)

        return RouterDecision.clarification("could not determine intent")

    # ----- helpers -----

    @staticmethod
    def _normalize(text: str) -> str:
        if not text:
            return ""
        cleaned = text.strip()
        # Drop a leading "Relay," wake-word style address.
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

    @staticmethod
    def _looks_like_chat(text: str) -> bool:
        t = text.lower().strip()
        if t.endswith("?"):
            return True
        for trigger in _CHAT_TRIGGERS:
            if t.startswith(trigger):
                return True
        return False

    def _try_plan(self, original: str, normalized: str) -> Optional[ActionPlan]:
        """Attempt to build a plan with one or more steps.

        Compound splits are only accepted when *every* clause yields a
        known command at confidence >= 0.7. Otherwise we fall back to a
        single-clause parse to preserve email bodies that contain
        connectors like "and".
        """
        clauses = self._split_compound(normalized)
        if len(clauses) > 1:
            steps = self._parse_clauses(clauses)
            if steps and all(s.tool_name != "unknown" for s in steps):
                return ActionPlan(steps=steps)

        # Single-clause path.
        intent = self.parser.parse(normalized)
        intent.raw_input = original
        if intent.action_type == ActionType.UNKNOWN or not intent.is_confident(0.7):
            return None
        return ActionPlan(steps=[self._step_from_intent(intent, normalized)])

    def _split_compound(self, text: str) -> List[str]:
        # Avoid splitting inside quoted strings.
        if '"' in text or "'" in text:
            return [text]
        parts = [p.strip() for p in _CONNECTORS.split(text) if p.strip()]
        # Heuristic: only treat as compound if every part starts with a
        # plausible command verb.
        if len(parts) <= 1:
            return [text]
        if not all(self._looks_like_command(p) for p in parts):
            return [text]
        return parts

    @staticmethod
    def _looks_like_command(text: str) -> bool:
        first = text.lower().split()[:1]
        if not first:
            return False
        verb = first[0]
        return verb in {
            "send", "draft", "compose", "email", "schedule", "add",
            "create", "set", "remind", "remember", "note", "jot",
            "write", "capture", "take", "make", "open", "close",
            "launch", "start", "stop", "cancel", "search", "look",
            "find", "show", "tell", "what", "play", "lock", "sleep",
            "shutdown", "restart", "mute", "unmute", "volume",
        }

    def _parse_clauses(self, clauses: List[str]) -> List[ActionStep]:
        steps: List[ActionStep] = []
        for clause in clauses:
            intent = self.parser.parse(clause)
            intent.raw_input = clause
            if intent.action_type == ActionType.UNKNOWN or not intent.is_confident(0.7):
                steps.append(ActionStep(
                    tool_name="unknown",
                    args={"content": clause},
                    raw_clause=clause,
                ))
            else:
                steps.append(self._step_from_intent(intent, clause))
        return steps

    @staticmethod
    def _step_from_intent(intent: ParsedIntent, clause: str) -> ActionStep:
        tool_name = _ACTION_TO_TOOL.get(intent.action_type, intent.action_type.value)
        args = dict(intent.entities)
        args.setdefault("raw_input", clause)
        return ActionStep(
            tool_name=tool_name,
            args=args,
            raw_clause=clause,
            status=StepStatus.PENDING,
        )
