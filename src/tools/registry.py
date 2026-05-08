"""Tool registry — a small, deterministic dispatch table.

The registry is an explicit map from tool name to tool instance. Names
and aliases are normalised to lowercase; lookup is O(1). It does *not*
do intent parsing — that's the router's job. Tools are registered
explicitly by the orchestrator at startup.
"""
from __future__ import annotations

from typing import Dict, Iterable, Iterator, List, Optional

from .base import BaseTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}
        self._aliases: Dict[str, str] = {}

    def register(self, tool: BaseTool) -> None:
        if not tool.name:
            raise ValueError("Tool must declare a name")
        key = tool.name.lower()
        self._tools[key] = tool
        for alias in tool.aliases or []:
            self._aliases[alias.lower()] = key

    def register_many(self, tools: Iterable[BaseTool]) -> None:
        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> Optional[BaseTool]:
        if not name:
            return None
        key = name.lower()
        if key in self._tools:
            return self._tools[key]
        aliased = self._aliases.get(key)
        if aliased:
            return self._tools.get(aliased)
        return None

    def __contains__(self, name: str) -> bool:
        return self.get(name) is not None

    def __iter__(self) -> Iterator[BaseTool]:
        return iter(self._tools.values())

    def names(self) -> List[str]:
        return list(self._tools.keys())
