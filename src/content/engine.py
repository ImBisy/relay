"""Content enrichment engine.

Runs *after* a tool has been chosen by code. The engine accepts
structured fields and returns polished versions of the same fields.
It cannot change the action, the recipient, the date, or any other
field that defines what will actually happen.

If no LLM is configured, the engine falls back to deterministic
templates so the calling tool can always rely on getting *something*
sensible back.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from . import templates

logger = logging.getLogger(__name__)


class ContentEngine:
    """Optional LLM polish — never the primary brain."""

    def __init__(self, openrouter_client: Optional[Any] = None,
                 enabled: bool = True) -> None:
        self.openrouter = openrouter_client
        self.enabled = enabled

    # ----- emails -----

    def enrich_email(
        self,
        body: str,
        subject: Optional[str] = None,
        recipient: Optional[str] = None,
        tone: Optional[str] = None,
    ) -> Dict[str, str]:
        body = (body or "").strip()
        subject = (subject or "").strip()
        if not self.enabled or not self.openrouter:
            return {
                "subject": subject or templates.fallback_email_subject(body, tone),
                "body": body,
            }
        try:
            from ..agents.openrouter import OpenRouterMessage
            tone_hint = f" Tone: {tone}." if tone else ""
            system = (
                "You are an email-polish assistant for Relay. The user has "
                "already decided to send the email and to whom. Improve "
                "wording only. Do NOT add or remove recipients, dates, or "
                "facts. Return STRICT JSON: {\"subject\": ..., \"body\": ...}."
                + tone_hint
            )
            user = (
                f"Recipient: {recipient or 'unknown'}\n"
                f"Current subject: {subject or '(none — generate one)'}\n"
                f"Current body: {body}"
            )
            messages = [
                OpenRouterMessage(role="system", content=system),
                OpenRouterMessage(role="user", content=user),
            ]
            response = self.openrouter.chat(messages, temperature=0.3, max_tokens=400)
            if not response:
                raise ValueError("empty response")
            payload = self._parse_json(response)
            if not payload:
                raise ValueError("non-JSON response")
            polished_body = (payload.get("body") or body).strip()
            polished_subject = (payload.get("subject") or subject
                                or templates.fallback_email_subject(body, tone)).strip()
            return {"subject": polished_subject, "body": polished_body}
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Content enrichment failed (email): %s", exc)
            return {
                "subject": subject or templates.fallback_email_subject(body, tone),
                "body": body,
            }

    # ----- reminders / notes / notifications -----

    def polish_reminder(self, text: str) -> str:
        if not self.enabled or not self.openrouter:
            return templates.polish_reminder_text(text)
        try:
            from ..agents.openrouter import OpenRouterMessage
            messages = [
                OpenRouterMessage(
                    role="system",
                    content=(
                        "Rewrite the reminder text to be a concise, clear, "
                        "actionable sentence. Do NOT add new information. "
                        "Return only the rewritten text."
                    ),
                ),
                OpenRouterMessage(role="user", content=text),
            ]
            response = self.openrouter.chat(messages, temperature=0.2, max_tokens=80)
            if response:
                return response.strip().strip('"\'')
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Content enrichment failed (reminder): %s", exc)
        return templates.polish_reminder_text(text)

    def polish_note(self, content: str) -> str:
        if not self.enabled or not self.openrouter:
            return templates.polish_note(content)
        try:
            from ..agents.openrouter import OpenRouterMessage
            messages = [
                OpenRouterMessage(
                    role="system",
                    content=(
                        "Lightly clean up the note's grammar and formatting. "
                        "Do NOT add new information. Preserve the user's "
                        "wording where possible. Return only the cleaned note."
                    ),
                ),
                OpenRouterMessage(role="user", content=content),
            ]
            response = self.openrouter.chat(messages, temperature=0.2, max_tokens=400)
            if response:
                return response.strip()
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Content enrichment failed (note): %s", exc)
        return templates.polish_note(content)

    # ----- helpers -----

    @staticmethod
    def _parse_json(response: str) -> Optional[Dict[str, Any]]:
        import json
        text = response.strip()
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0]
        text = text.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None
