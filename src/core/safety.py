"""Safety classification for tool actions.

Every tool declares the safety level of an action so the orchestrator
can decide whether to run immediately or stage a pending action for
explicit confirmation.
"""
from __future__ import annotations

from enum import Enum


class SafetyLevel(str, Enum):
    """Safety classification, ordered by severity."""

    SAFE = "safe"                # idempotent, no side effects (e.g. list reminders)
    REVERSIBLE = "reversible"    # easily undone (e.g. create a note)
    SENSITIVE = "sensitive"      # external side effects, ask first (e.g. send email)
    DESTRUCTIVE = "destructive"  # irreversible (e.g. delete data)
    EXTERNAL = "external"        # affects systems outside Relay (e.g. shutdown)

    @property
    def requires_confirmation(self) -> bool:
        return self in (SafetyLevel.SENSITIVE, SafetyLevel.DESTRUCTIVE, SafetyLevel.EXTERNAL)
