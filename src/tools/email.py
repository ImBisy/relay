"""Email tool — sensitive action staged as a structured pending action.

The tool never sends an email on the first call. It validates inputs,
optionally polishes the body and subject through the content engine,
creates a row in ``pending_actions`` with all the data needed to
revalidate later, and returns ``NEEDS_CONFIRMATION``.

When the orchestrator confirms an action, it calls ``execute`` again
with ``ctx.confirmed=True`` and the same args; only then do we open an
SMTP connection.
"""
from __future__ import annotations

import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional, Tuple

from ..config.settings import config
from ..core.context import ToolContext
from ..core.safety import SafetyLevel
from ..storage import PendingActionsStore
from ..storage.models import PendingAction
from .base import BaseTool, ToolResult


class EmailTool(BaseTool):
    name = "email"
    aliases = ["mail"]
    description = "Send or draft emails"
    requires_confirmation = True
    safety_level = SafetyLevel.SENSITIVE
    supported_actions = ["send", "draft"]

    def __init__(self,
                 pending_store: Optional[PendingActionsStore] = None,
                 smtp_send_fn: Optional[Any] = None) -> None:
        self._pending_store = pending_store
        self._smtp_send_fn = smtp_send_fn or self._send_email_smtp

    # ----- BaseTool API -----

    def execute(self, args: Dict[str, Any], ctx: Optional[ToolContext] = None) -> ToolResult:
        ok, error = self.validate(args)
        if not ok:
            return ToolResult.failure(f"Invalid email request: {error}")

        recipient = self._resolve_recipient(args)
        if not recipient:
            alias = (args.get("recipient_alias") or args.get("to") or "").strip()
            if alias:
                return ToolResult.failure(
                    f"I couldn't find an email for \"{alias}\". Add it under "
                    "`email.accounts.aliases` in ~/.relay/config.json or give "
                    "me the full address."
                )
            return ToolResult.failure(
                "Tell me who to send it to — a saved alias or a full email address."
            )

        body = (args.get("body") or args.get("content") or "").strip()
        subject = (args.get("subject") or "").strip()

        # Optional content enrichment — fills in subject, polishes body.
        if ctx and ctx.content is not None:
            enriched = ctx.content.enrich_email(
                body=body, subject=subject, recipient=recipient,
                tone=args.get("tone"),
            )
            if enriched:
                body = enriched.get("body", body) or body
                subject = enriched.get("subject", subject) or subject

        if args.get("draft_only"):
            return ToolResult.success(
                f"Email drafted to {recipient}.",
                data={"recipient": recipient, "subject": subject, "body": body, "draft": True},
                preview=self._preview(recipient, subject, body),
            )

        # Confirmation path — either confirm a previously staged action
        # or stage a new one.
        if ctx and ctx.confirmed:
            return self._send_now(recipient, subject, body)

        store = self._resolve_store(ctx)
        pending = PendingAction(
            id=PendingActionsStore.new_id(),
            tool_name=self.name,
            args={
                "recipient_email": recipient,
                "subject": subject,
                "body": body,
            },
            preview=self._preview(recipient, subject, body),
            safety_level=SafetyLevel.SENSITIVE.value,
            source=ctx.source if ctx else None,
        )
        store.create(pending)
        return ToolResult.needs_confirmation(
            "Email prepared.",
            prompt=f"Send to {recipient}? Subject: {subject or '(none)'}",
            data={
                "recipient": recipient,
                "subject": subject or "No subject",
                "body": body,
                "preview": pending.preview,
            },
            action_id=pending.id,
            preview=pending.preview,
        )

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not (args.get("recipient_alias") or args.get("recipient_email") or args.get("to")):
            return False, "Recipient required (email address or alias)"
        if not (args.get("body") or args.get("content") or args.get("message")):
            return False, "Email body required"
        return True, None

    def preview(self, args: Dict[str, Any]) -> str:
        recipient = self._resolve_recipient(args) or "unknown"
        subject = args.get("subject") or "No subject"
        body = (args.get("body") or args.get("content") or "")
        return self._preview(recipient, subject, body)

    def cancel(self, action_id: str) -> ToolResult:
        store = self._resolve_store(None)
        if store.cancel(action_id):
            return ToolResult.cancelled("Email cancelled.")
        return ToolResult.failure("No pending email with that id.")

    # ----- internals -----

    def _resolve_store(self, ctx: Optional[ToolContext]) -> PendingActionsStore:
        if ctx and ctx.pending_actions is not None:
            return ctx.pending_actions
        if self._pending_store is not None:
            return self._pending_store
        return PendingActionsStore()

    def _send_now(self, recipient: str, subject: str, body: str) -> ToolResult:
        account = self._get_account()
        if not account:
            return ToolResult.failure(
                "No email account configured.",
                error="email_not_configured",
            )
        try:
            self._smtp_send_fn({
                "from": account.get("from_address", account.get("username")),
                "to": recipient,
                "subject": subject,
                "body": body,
                "account": account,
            })
        except Exception as exc:
            return ToolResult.failure("Failed to send email", error=str(exc))
        return ToolResult.success(
            f"Email sent to {recipient}.",
            data={"recipient": recipient, "subject": subject, "body": body},
            preview=self._preview(recipient, subject, body),
        )

    def _resolve_recipient(self, args: Dict[str, Any]) -> Optional[str]:
        if args.get("recipient_email"):
            return args["recipient_email"]
        if args.get("to"):
            value = args["to"]
            if re.match(r"\S+@\S+\.\S+", value):
                return value
        alias = (args.get("recipient_alias") or "").lower().strip()
        if not alias:
            return None
        aliases = config.email.accounts.get("aliases", {})
        if alias in aliases:
            return aliases[alias]
        normalized = alias.replace(" email", "").replace(" mail", "").strip()
        if normalized in aliases:
            return aliases[normalized]
        for key, value in aliases.items():
            key_l = key.lower()
            if normalized and (normalized in key_l or key_l in normalized):
                return value
        return None

    def _get_account(self) -> Optional[Dict[str, Any]]:
        accounts = config.email.accounts
        # Skip the alias section and other non-account entries.
        for name, value in accounts.items():
            if name == "aliases":
                continue
            if isinstance(value, dict) and value.get("smtp_server"):
                return value
        return None

    def _send_email_smtp(self, payload: Dict[str, Any]) -> None:
        account = payload["account"]
        msg = MIMEMultipart()
        msg["From"] = payload["from"]
        msg["To"] = payload["to"]
        msg["Subject"] = payload["subject"] or ""
        msg.attach(MIMEText(payload["body"], "plain"))
        with smtplib.SMTP(account["smtp_server"], int(account["smtp_port"])) as server:
            server.starttls()
            server.login(account["username"], account["password"])
            server.send_message(msg)

    @staticmethod
    def _preview(recipient: str, subject: str, body: str) -> str:
        body_preview = body if len(body) <= 80 else body[:80] + "..."
        subject = subject or "(no subject)"
        return f"Email to {recipient} — {subject}: {body_preview}"
