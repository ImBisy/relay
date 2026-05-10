"""Router tests — deterministic, code-first routing."""
from __future__ import annotations

from src.core.action_plan import RouteKind
from src.core.router import Router


def test_router_command_simple():
    router = Router()
    decision = router.route("Remind me to call mom at 5pm")
    assert decision.kind == RouteKind.COMMAND
    assert decision.plan is not None
    assert len(decision.plan.steps) == 1
    assert decision.plan.steps[0].tool_name == "reminder"


def test_router_strips_wakeword():
    router = Router()
    decision = router.route("Relay, remind me to submit the form at 6")
    assert decision.kind == RouteKind.COMMAND
    assert decision.plan.steps[0].tool_name == "reminder"


def test_router_email_does_not_split_on_and_inside_body():
    router = Router()
    decision = router.route(
        "send an email to John saying hi and thanks for the help"
    )
    assert decision.kind == RouteKind.COMMAND
    assert len(decision.plan.steps) == 1
    assert decision.plan.steps[0].tool_name == "email"


def test_router_compound_two_commands():
    router = Router()
    decision = router.route("remind me to call mom and take a note about lunch")
    assert decision.kind == RouteKind.COMMAND
    assert len(decision.plan.steps) == 2
    tools = [s.tool_name for s in decision.plan.steps]
    assert "reminder" in tools
    assert "note" in tools


def test_router_confirmation():
    router = Router()
    assert router.route("yes").kind == RouteKind.CONFIRMATION
    assert router.route("send it").kind == RouteKind.CONFIRMATION
    assert router.route("confirm").kind == RouteKind.CONFIRMATION


def test_router_cancellation():
    router = Router()
    assert router.route("cancel").kind == RouteKind.CANCELLATION
    assert router.route("nevermind").kind == RouteKind.CANCELLATION


def test_router_chat():
    router = Router()
    decision = router.route("what is the capital of france?")
    assert decision.kind == RouteKind.CHAT


def test_router_clarification_for_empty():
    router = Router()
    decision = router.route("")
    assert decision.kind == RouteKind.CLARIFICATION
