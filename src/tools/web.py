"""Web tool — opens URLs and runs searches via the system browser."""
from __future__ import annotations

import urllib.parse
import webbrowser
from typing import Any, Dict, Optional, Tuple

from ..core.context import ToolContext
from ..core.safety import SafetyLevel
from .base import BaseTool, ToolResult


_SEARCH_ENGINES = {
    "google": "https://www.google.com/search?q={}",
    "duckduckgo": "https://duckduckgo.com/?q={}",
    "bing": "https://www.bing.com/search?q={}",
}

_SHORTCUTS = {
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "maps": "https://maps.google.com",
    "drive": "https://drive.google.com",
    "calendar": "https://calendar.google.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "reddit": "https://www.reddit.com",
}


class WebTool(BaseTool):
    name = "web"
    aliases = ["browser", "search"]
    description = "Open websites and perform web searches"
    requires_confirmation = False
    safety_level = SafetyLevel.SAFE
    supported_actions = ["search", "open"]

    def __init__(self, default_search: str = "google",
                 opener: Optional[Any] = None) -> None:
        self.default_search = default_search
        self._opener = opener or webbrowser.open

    def execute(self, args: Dict[str, Any], ctx: Optional[ToolContext] = None) -> ToolResult:
        action = args.get("web_action", "search")
        text = (args.get("content") or "").lower()
        if any(word in text for word in ("open", "go to", "navigate to")):
            action = "open"
        elif any(word in text for word in ("search", "look up", "find", "google")):
            action = "search"

        if action == "open":
            return self._open(args)
        return self._search(args)

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not (args.get("query") or args.get("content") or args.get("url")
                or args.get("website")):
            return False, "Query or URL required"
        return True, None

    def preview(self, args: Dict[str, Any]) -> str:
        return f"Web: {args.get('query') or args.get('content') or args.get('url') or ''}"

    def _search(self, args: Dict[str, Any]) -> ToolResult:
        query = args.get("query") or args.get("content") or args.get("search_term") or ""
        for keyword in ("search", "look up", "find", "google", "for"):
            query = query.replace(keyword, "")
        query = query.strip()
        if not query:
            return ToolResult.failure("Search query required")
        encoded = urllib.parse.quote(query)
        url = _SEARCH_ENGINES.get(self.default_search, _SEARCH_ENGINES["google"]).format(encoded)
        try:
            self._opener(url)
        except Exception as exc:
            return ToolResult.failure("Could not open browser", error=str(exc))
        return ToolResult.success(f"Searching for '{query}'",
                                  data={"search_url": url, "query": query})

    def _open(self, args: Dict[str, Any]) -> ToolResult:
        target = args.get("url") or args.get("website") or args.get("content") or ""
        target = target.strip()
        if not target:
            return ToolResult.failure("Website URL or name required")
        url = self._resolve_url(target)
        try:
            self._opener(url)
        except Exception as exc:
            return ToolResult.failure("Could not open website", error=str(exc))
        return ToolResult.success(f"Opening {url}", data={"url": url})

    def _resolve_url(self, value: str) -> str:
        lower = value.lower().strip()
        if lower.startswith(("http://", "https://")):
            return value
        if lower in _SHORTCUTS:
            return _SHORTCUTS[lower]
        if "." in value:
            return f"https://{value}"
        encoded = urllib.parse.quote(value)
        return _SEARCH_ENGINES[self.default_search].format(encoded)
