"""Standard result shape returned by every tool.

Re-exports ``ToolResult`` from ``src.tools.base`` so callers can depend
on a single import path. The shape is intentionally identical to the
existing legacy interface to avoid breaking working tools.
"""
from __future__ import annotations

from ..tools.base import ToolResult, ToolResultStatus

__all__ = ["ToolResult", "ToolResultStatus"]
