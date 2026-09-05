"""Web search tool using DuckDuckGo (ddgs)."""

from __future__ import annotations

import json
from ddgs import DDGS

from config import SEARCH_MAX_RESULTS
from tools.base import register_tool

_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web for current information on a topic. "
            "Returns a list of results with title, snippet, and URL."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
            },
            "required": ["query"],
        },
    },
}


@register_tool(_SCHEMA)
def web_search(query: str) -> str:
    """Run a DuckDuckGo search and return formatted results."""
    try:
        results = DDGS().text(query, max_results=SEARCH_MAX_RESULTS)
        if not results:
            return "No results found."

        formatted = []
        for r in results:
            formatted.append(
                f"**{r.get('title', 'No title')}**\n"
                f"{r.get('body', 'No snippet')}\n"
                f"URL: {r.get('href', 'N/A')}"
            )
        return "\n\n---\n\n".join(formatted)
    except Exception as e:
        return f"Search error: {e}"
