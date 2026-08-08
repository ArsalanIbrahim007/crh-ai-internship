"""Live web search, via DuckDuckGo.

No API key and no rate limit to manage, which is why this over a commercial search API.
The tradeoff is that it scrapes, so it fails occasionally and the failure must not take
the agent down with it - a search that returns nothing is a normal outcome, not a crash.

Results are deliberately trimmed. Search snippets are verbose and the model pays for every
token of them, so each result is capped rather than passed through whole.
"""

from dataclasses import dataclass, field

MAX_RESULTS = 5
SNIPPET_CHARS = 300


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str


@dataclass
class SearchResult:
    ok: bool
    query: str
    hits: list[SearchHit] = field(default_factory=list)
    error: str = ""

    def to_text(self) -> str:
        if not self.ok:
            return f"SEARCH ERROR: {self.error}"
        if not self.hits:
            return f"No results found for: {self.query}"

        lines = []
        for i, h in enumerate(self.hits, 1):
            lines.append(f"[{i}] {h.title}")
            lines.append(f"    {h.url}")
            lines.append(f"    {h.snippet}")
        return "\n".join(lines)


def search_web(query: str, max_results: int = MAX_RESULTS) -> SearchResult:
    """Search the web and return the top results."""
    query = (query or "").strip()
    if not query:
        return SearchResult(ok=False, query=query, error="Empty search query.")

    max_results = max(1, min(int(max_results), 10))

    try:
        from ddgs import DDGS
    except ImportError:
        return SearchResult(ok=False, query=query,
                            error="ddgs is not installed. Run: pip install ddgs")

    try:
        raw = DDGS().text(query, max_results=max_results, safesearch="moderate")
    except Exception as e:
        # Scraped search fails for all sorts of reasons - rate limiting, layout changes,
        # no network. The agent should hear about it and move on, not crash.
        return SearchResult(ok=False, query=query, error=f"{type(e).__name__}: {e}")

    hits = []
    for r in raw or []:
        body = (r.get("body") or "").strip().replace("\n", " ")
        if len(body) > SNIPPET_CHARS:
            body = body[:SNIPPET_CHARS].rsplit(" ", 1)[0] + "..."
        hits.append(SearchHit(
            title=(r.get("title") or "Untitled").strip(),
            url=(r.get("href") or "").strip(),
            snippet=body,
        ))

    return SearchResult(ok=True, query=query, hits=hits)


if __name__ == "__main__":
    res = search_web("what is retrieval augmented generation", max_results=3)
    print("ok:", res.ok)
    print(res.to_text())
