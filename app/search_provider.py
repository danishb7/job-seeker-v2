"""Tavily-backed web search provider."""
from __future__ import annotations

from tavily import TavilyClient

from .config import TAVILY_API_KEY, TAVILY_MAX_RESULTS, TAVILY_SEARCH_DEPTH

_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None

# Tavily API rejects queries longer than this (BadRequestError).
TAVILY_MAX_QUERY_CHARS = 400


def tavily_search(query: str, include_domains: list[str] | None = None) -> list[dict[str, str]]:
    if not _client:
        return []
    q = str(query or "").strip()
    if len(q) > TAVILY_MAX_QUERY_CHARS:
        q = q[:TAVILY_MAX_QUERY_CHARS].rstrip()
    domains = [d.strip().lower() for d in (include_domains or []) if d and str(d).strip()]
    raw = _client.search(
        query=q,
        search_depth=TAVILY_SEARCH_DEPTH,
        max_results=TAVILY_MAX_RESULTS,
        include_domains=domains or None,
        topic="general",
    )
    return [
        {
            "title": str(r.get("title", "")),
            "url": str(r.get("url", "")),
            "snippet": str(r.get("content", ""))[:400],
        }
        for r in raw.get("results", [])
    ]
