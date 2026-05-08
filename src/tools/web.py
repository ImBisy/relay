"""
Web query tool for searches and website access.
"""
import webbrowser
import urllib.parse
from typing import Dict, Any, Optional
from .base import BaseTool, ToolResult


class WebTool(BaseTool):
    """
    Web tool for browser control and searches.
    
    Supports:
    - Opening websites
    - Performing web searches
    """
    
    name = "web"
    description = "Open websites and perform web searches"
    requires_confirmation = False
    
    # Search engine URLs
    SEARCH_ENGINES = {
        'google': 'https://www.google.com/search?q={}',
        'duckduckgo': 'https://duckduckgo.com/?q={}',
        'bing': 'https://www.bing.com/search?q={}',
    }
    
    def __init__(self, default_search: str = 'google'):
        """
        Initialize web tool.
        
        Args:
            default_search: Default search engine ('google', 'duckduckgo', 'bing')
        """
        self.default_search = default_search
    
    def execute(self, entities: Dict[str, Any]) -> ToolResult:
        """Execute web action."""
        action = entities.get('web_action', 'search')
        
        # Detect action from text
        text = entities.get('content', '').lower()
        if any(word in text for word in ['open', 'go to', 'navigate to']):
            action = 'open'
        elif any(word in text for word in ['search', 'look up', 'find', 'google']):
            action = 'search'
        
        if action == 'open':
            return self._open_website(entities)
        else:
            return self._search(entities)
    
    def _search(self, entities: Dict[str, Any]) -> ToolResult:
        """Perform web search."""
        query = entities.get('query') or entities.get('content') or entities.get('search_term')
        
        if not query:
            return ToolResult.failure("Search query required")
        
        # Clean query (remove search keywords)
        search_keywords = ['search', 'look up', 'find', 'google', 'for']
        query_clean = query.lower()
        for keyword in search_keywords:
            query_clean = query_clean.replace(keyword, '')
        query_clean = query_clean.strip()
        
        # Encode query
        encoded_query = urllib.parse.quote(query_clean)
        
        # Build search URL
        search_template = self.SEARCH_ENGINES.get(self.default_search)
        search_url = search_template.format(encoded_query)
        
        # Open browser
        try:
            webbrowser.open(search_url)
            return ToolResult.success(
                f"Searching for '{query_clean}'",
                data={'search_url': search_url, 'query': query_clean}
            )
        except Exception as e:
            return ToolResult.failure("Could not open browser", error=str(e))
    
    def _open_website(self, entities: Dict[str, Any]) -> ToolResult:
        """Open a specific website."""
        url_or_name = entities.get('url') or entities.get('website') or entities.get('content')
        
        if not url_or_name:
            return ToolResult.failure("Website URL or name required")
        
        # Check if it's a URL or needs to be resolved
        url = self._resolve_url(url_or_name)
        
        try:
            webbrowser.open(url)
            return ToolResult.success(
                f"Opening {url}",
                data={'url': url}
            )
        except Exception as e:
            return ToolResult.failure("Could not open website", error=str(e))
    
    def _resolve_url(self, input_str: str) -> str:
        """Resolve input to a valid URL."""
        input_lower = input_str.lower().strip()
        
        # Check if already a URL
        if input_lower.startswith(('http://', 'https://')):
            return input_str
        
        # Common website shortcuts
        shortcuts = {
            'google': 'https://www.google.com',
            'gmail': 'https://mail.google.com',
            'youtube': 'https://www.youtube.com',
            'github': 'https://github.com',
            'maps': 'https://maps.google.com',
            'drive': 'https://drive.google.com',
            'calendar': 'https://calendar.google.com',
            'twitter': 'https://twitter.com',
            'x': 'https://x.com',
            'reddit': 'https://www.reddit.com',
            'news': 'https://news.google.com',
            'weather': 'https://www.weather.com',
        }
        
        if input_lower in shortcuts:
            return shortcuts[input_lower]
        
        # Try adding https
        if '.' in input_str:
            return f"https://{input_str}"
        
        # Fallback to search
        return self.SEARCH_ENGINES[self.default_search].format(
            urllib.parse.quote(input_str)
        )
    
    def validate(self, entities: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate web entities."""
        has_content = (
            entities.get('query') or 
            entities.get('content') or 
            entities.get('url') or
            entities.get('website')
        )
        
        if not has_content:
            return False, "Query or URL required"
        
        return True, None
