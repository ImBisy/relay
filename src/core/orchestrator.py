"""Relay orchestrator — a thin coordinator.

The orchestrator owns no tool logic, no LLM brain, and no business
rules. It:

1. normalizes input and stamps audit metadata,
2. asks the ``Router`` for a deterministic decision,
3. dispatches the matching tool(s) for command plans,
4. routes chat / clarification through dedicated services,
5. records every meaningful step in the activity log.

Confirmation lookups are pure storage operations against the
``PendingActionsStore`` — no callbacks live in process memory.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from ..chat.chat_service import ChatService
from ..config.settings import config
from ..content.engine import ContentEngine
from ..llm.extractor import IntentExtractor, build_default_extractor
from ..personality.responder import PersonalityEngine, ResponseContext
from ..storage import (
    CalendarStore,
    LogsStore,
    NotesStore,
    PendingActionsStore,
    RemindersStore,
)
from ..storage.models import ActionLogEntry
from ..tools import (
    BaseTool,
    CalendarTool,
    EmailTool,
    NotesTool,
    QueryTool,
    ReminderTool,
    SystemTool,
    TimerTool,
    ToolRegistry,
    ToolResult,
    ToolResultStatus,
    WebTool,
)
from .action_plan import ActionPlan, ActionStep, RouteKind, StepStatus
from .context import ToolContext
from .router import Router

logger = logging.getLogger(__name__)


_ROUTE_TO_TOOL_NAME = {
    "email": "email",
    "calendar": "calendar",
    "reminder": "reminder",
    "note": "note",
    "timer": "timer",
    "system": "system",
    "web": "web",
    "query": "query",
}


class RelayOrchestrator:
    """Coordinator. Decides nothing on its own; dispatches everything."""

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        router: Optional[Router] = None,
        reminders: Optional[RemindersStore] = None,
        notes: Optional[NotesStore] = None,
        calendar: Optional[CalendarStore] = None,
        logs: Optional[LogsStore] = None,
        pending_actions: Optional[PendingActionsStore] = None,
        content_engine: Optional[ContentEngine] = None,
        chat_service: Optional[ChatService] = None,
        personality: Optional[PersonalityEngine] = None,
        openrouter_client: Optional[Any] = None,
        extractor: Optional[IntentExtractor] = None,
    ) -> None:
        self.openrouter = openrouter_client or self._build_openrouter()

        self.reminders = reminders or RemindersStore()
        self.notes = notes or NotesStore()
        self.calendar = calendar or CalendarStore()
        self.logs = logs or LogsStore()
        self.pending_actions = pending_actions or PendingActionsStore()

        self.content = content_engine or ContentEngine(self.openrouter)
        self.chat = chat_service or ChatService(self.openrouter)
        self.personality = personality or PersonalityEngine()

        self.response_callback: Optional[Callable[[str], None]] = None
        self.notification_callback: Optional[Callable[[str], None]] = None

        self.extractor = extractor or build_default_extractor(
            api_key=config.api.openrouter_api_key,
            model=config.api.fast_model,
            base_url=config.api.openrouter_base_url,
        )
        self.router = router or Router(self.extractor)
        self.registry = registry or self._default_registry()

    # ----- public API -----

    def set_response_callback(self, callback: Callable[[str], None]) -> None:
        self.response_callback = callback

    def set_notification_callback(self, callback: Callable[[str], None]) -> None:
        self.notification_callback = callback

    def greeting(self) -> str:
        return self.personality.greeting()

    def process_input(self, text: str, source: str = "cli") -> str:
        if not text or not text.strip():
            return self._emit("I need a bit of input to work with.")

        decision = self.router.route(text)
        self._log("routing", route=decision.kind.value, source=source,
                  raw_input=text, normalized=text)

        if decision.kind == RouteKind.CONFIRMATION:
            return self._handle_confirmation(text, source)
        if decision.kind == RouteKind.CANCELLATION:
            return self._handle_cancellation(text, source)
        if decision.kind == RouteKind.CHAT:
            return self._handle_chat(text, source)
        if decision.kind == RouteKind.CLARIFICATION:
            return self._emit(self.personality.clarification(decision.clarification_reason))
        if decision.kind == RouteKind.COMMAND and decision.plan is not None:
            return self._run_plan(decision.plan, text, source)

        # Fallback — should not reach here.
        return self._emit(self.personality.clarification("unrouted input"))

    def confirm_pending(self, action_id: Optional[str] = None,
                         source: str = "cli") -> str:
        return self._handle_confirmation(action_id or "", source,
                                          explicit_id=bool(action_id))

    def cancel_pending(self, action_id: Optional[str] = None,
                        source: str = "cli") -> str:
        return self._handle_cancellation(action_id or "", source,
                                          explicit_id=bool(action_id))

    # ----- planning / dispatch -----

    def _run_plan(self, plan: ActionPlan, raw: str, source: str) -> str:
        self._log("plan_started", plan_id=plan.plan_id, source=source,
                  raw_input=raw,
                  metadata={"steps": len(plan.steps)})
        for index, step in enumerate(plan.steps):
            step.status = StepStatus.RUNNING
            self._log("step_started", plan_id=plan.plan_id,
                      step_index=index, tool_name=step.tool_name,
                      args=step.args, source=source)
            tool = self.registry.get(step.tool_name)
            if tool is None:
                step.status = StepStatus.FAILURE
                step.error = f"unknown tool: {step.tool_name}"
                step.result = ToolResult.failure(step.error)
                self._log("step_failed", plan_id=plan.plan_id,
                          step_index=index, tool_name=step.tool_name,
                          error=step.error, source=source)
                continue

            ok, error = tool.validate(step.args)
            if not ok:
                step.status = StepStatus.FAILURE
                step.error = error or "validation failed"
                step.result = ToolResult.failure(step.error)
                self._log("step_failed", plan_id=plan.plan_id,
                          step_index=index, tool_name=step.tool_name,
                          error=step.error, source=source)
                continue

            ctx = self._build_context(source, raw, plan.plan_id, index)
            try:
                result = tool.execute(step.args, ctx)
            except Exception as exc:  # broad: tool author bugs
                logger.exception("Tool execution error: %s", step.tool_name)
                result = ToolResult.failure("Something went wrong", error=str(exc))

            step.result = result
            step.status = self._step_status_for(result)
            self._log_result(plan.plan_id, index, step.tool_name, result)

            if step.status == StepStatus.FAILURE and len(plan.steps) > 1:
                # Skip remaining dependent steps (MVP: simple all-or-nothing).
                for remaining in plan.steps[index + 1:]:
                    remaining.status = StepStatus.SKIPPED
                break

        message = self._render_plan(plan)
        self._log("plan_completed", plan_id=plan.plan_id, source=source,
                  metadata={"succeeded": plan.succeeded})
        return self._emit(message)

    def _step_status_for(self, result: ToolResult) -> StepStatus:
        if result.status == ToolResultStatus.SUCCESS:
            return StepStatus.SUCCESS
        if result.status == ToolResultStatus.NEEDS_CONFIRMATION:
            return StepStatus.NEEDS_CONFIRMATION
        if result.status == ToolResultStatus.PENDING:
            return StepStatus.NEEDS_CONFIRMATION
        if result.status == ToolResultStatus.CANCELLED:
            return StepStatus.SKIPPED
        return StepStatus.FAILURE

    def _render_plan(self, plan: ActionPlan) -> str:
        # Simple, deterministic rendering for MVP. Single-step plans
        # render through the personality engine; multi-step plans
        # collect step-level messages.
        if len(plan.steps) == 1:
            step = plan.steps[0]
            return self._render_single(step)

        lines: List[str] = []
        for step in plan.steps:
            if step.result is None:
                continue
            prefix = {
                StepStatus.SUCCESS: "ok",
                StepStatus.FAILURE: "x",
                StepStatus.NEEDS_CONFIRMATION: "?",
                StepStatus.SKIPPED: "-",
            }.get(step.status, "·")
            lines.append(f"[{prefix}] {step.result.message}")
        if not lines:
            return "Nothing to do."
        return "\n".join(lines)

    def _render_single(self, step: ActionStep) -> str:
        result = step.result
        if result is None:
            return "Nothing to report."
        if result.status == ToolResultStatus.NEEDS_CONFIRMATION:
            return f"{result.message} {result.confirmation_prompt or 'Confirm?'}".strip()
        ctx = ResponseContext(
            action_type=step.tool_name,
            success=result.status == ToolResultStatus.SUCCESS,
            requires_confirmation=False,
            error=result.error,
        )
        # Prefer the tool's own message — it has the structured detail
        # already (recipients, times, etc.). Fall back to personality
        # only when the tool returned an empty message.
        if result.message:
            return result.message
        return self.personality.generate_response(ctx, result.data)

    # ----- chat / confirmation paths -----

    def _handle_chat(self, text: str, source: str) -> str:
        self._log("chat", route="chat", source=source, raw_input=text)
        reply = self.chat.reply(text)
        if reply:
            return self._emit(reply)
        return self._emit(self.personality.clarification(
            "I don't have a tool for that — could you rephrase as an action?"))

    def _handle_confirmation(self, raw: str, source: str,
                              explicit_id: bool = False) -> str:
        action: Optional[Any] = None
        if explicit_id:
            action = self.pending_actions.get(raw)
        else:
            action = self.pending_actions.latest_pending()

        if action is None:
            self._log("confirmation_missing", source=source, raw_input=raw)
            return self._emit("I don't have a pending action to confirm.")

        tool = self.registry.get(action.tool_name)
        if tool is None:
            self._log("confirmation_failed", tool_name=action.tool_name,
                      error="unknown_tool", source=source,
                      metadata={"action_id": action.id})
            return self._emit("That action's tool is no longer available.")

        ok, error = tool.validate(action.args)
        if not ok:
            self._pending_done(action.id, "failed")
            self._log("confirmation_failed", tool_name=action.tool_name,
                      error=error or "invalid", source=source,
                      metadata={"action_id": action.id})
            return self._emit(f"Cannot confirm: {error}")

        ctx = self._build_context(source, raw, plan_id=None, step_index=None,
                                   confirmed=True)
        try:
            result = tool.execute(action.args, ctx)
        except Exception as exc:
            logger.exception("Confirmation execution failed")
            self._pending_done(action.id, "failed")
            return self._emit(f"Could not complete action: {exc}")

        if result.status == ToolResultStatus.SUCCESS:
            self._pending_done(action.id, "confirmed")
        elif result.status == ToolResultStatus.FAILURE:
            self._pending_done(action.id, "failed")
        self._log("confirmed", tool_name=action.tool_name,
                  message=result.message, source=source,
                  metadata={"action_id": action.id,
                            "tool_status": result.status.value})
        return self._emit(result.message)

    def _handle_cancellation(self, raw: str, source: str,
                              explicit_id: bool = False) -> str:
        action: Optional[Any] = None
        if explicit_id:
            action = self.pending_actions.get(raw)
        else:
            action = self.pending_actions.latest_pending()

        if action is None:
            return self._emit("Nothing to cancel.")
        tool = self.registry.get(action.tool_name)
        if tool is not None:
            try:
                tool.cancel(action.id)
            except Exception:  # pragma: no cover - best effort
                logger.exception("Tool-side cancel failed")
        self.pending_actions.cancel(action.id)
        self._log("cancelled", tool_name=action.tool_name, source=source,
                  metadata={"action_id": action.id})
        return self._emit("Cancelled.")

    # ----- helpers -----

    def _build_context(self, source: str, raw: str,
                        plan_id: Optional[str], step_index: Optional[int],
                        confirmed: bool = False) -> ToolContext:
        return ToolContext(
            source=source,
            raw_input=raw,
            normalized=raw,
            plan_id=plan_id,
            step_index=step_index,
            confirmed=confirmed,
            reminders=self.reminders,
            notes=self.notes,
            calendar=self.calendar,
            logs=self.logs,
            pending_actions=self.pending_actions,
            content=self.content,
            notification_callback=self.notification_callback,
        )

    def _default_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        tools: List[BaseTool] = [
            ReminderTool(self.reminders, self.notification_callback),
            NotesTool(self.notes),
            CalendarTool(self.calendar),
            EmailTool(self.pending_actions),
            TimerTool(self.notification_callback),
            SystemTool(),
            WebTool(),
        ]
        if self.openrouter is not None:
            tools.append(QueryTool(self.openrouter))
        registry.register_many(tools)
        return registry

    def _build_openrouter(self) -> Optional[Any]:
        if not config.api.openrouter_api_key:
            return None
        try:
            from ..agents.openrouter import OpenRouterClient
            # Chat + content polish use the slow model. The intent
            # extractor builds its own client around the fast model.
            return OpenRouterClient(
                api_key=config.api.openrouter_api_key,
                base_url=config.api.openrouter_base_url,
                model=config.api.slow_model,
            )
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("OpenRouter client init failed: %s", exc)
            return None

    def _pending_done(self, action_id: str, status: str) -> None:
        if status == "confirmed":
            self.pending_actions.confirm(action_id)
        elif status == "cancelled":
            self.pending_actions.cancel(action_id)
        else:
            self.pending_actions.mark_status(action_id, "failed")

    def _emit(self, text: str) -> str:
        if self.response_callback:
            try:
                self.response_callback(text)
            except Exception:  # pragma: no cover - best effort
                logger.exception("response_callback raised")
        return text

    def _log_result(self, plan_id: str, step_index: int,
                     tool_name: str, result: ToolResult) -> None:
        status = {
            ToolResultStatus.SUCCESS: "step_succeeded",
            ToolResultStatus.FAILURE: "step_failed",
            ToolResultStatus.NEEDS_CONFIRMATION: "step_pending",
            ToolResultStatus.CANCELLED: "step_cancelled",
            ToolResultStatus.PENDING: "step_pending",
        }.get(result.status, "step_completed")
        self._log(
            status,
            tool_name=tool_name,
            message=result.message,
            error=result.error,
            metadata={"data": result.data} if result.data else None,
            plan_id=plan_id,
            step_index=step_index,
        )

    def _log(self, status: str, *,
             route: Optional[str] = None,
             tool_name: Optional[str] = None,
             message: Optional[str] = None,
             error: Optional[str] = None,
             plan_id: Optional[str] = None,
             step_index: Optional[int] = None,
             source: Optional[str] = None,
             raw_input: Optional[str] = None,
             normalized: Optional[str] = None,
             args: Optional[Dict[str, Any]] = None,
             metadata: Optional[Dict[str, Any]] = None) -> None:
        try:
            self.logs.append(
                ActionLogEntry(
                    status=status,
                    route=route,
                    tool_name=tool_name,
                    message=message,
                    error=error,
                    plan_id=plan_id,
                    step_index=step_index,
                    source=source,
                    raw_input=raw_input,
                    normalized=normalized,
                    args=args or {},
                    metadata=metadata or {},
                )
            )
        except Exception:  # pragma: no cover - logging must not fail user flow
            logger.exception("Failed to write activity log")
