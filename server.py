"""GroundRoute MCP server (stdio).

A thin local MCP server that exposes a single ``search`` tool and forwards each call to the hosted
GroundRoute API (https://api.groundroute.ai). Most users should use the hosted streamable-HTTP
endpoint directly (see README); this stdio server exists for stdio-only clients and for automated
registry/quality introspection.

Introspection (initialize / tools/list) works with no credentials. Executing a search requires a
GroundRoute API key in the GROUNDROUTE_API_KEY environment variable (get one at
https://groundroute.ai/keys).

The ``search`` tool advertises a rich definition — full description, per-parameter semantics, tool
annotations, and a structured output schema — so MCP clients (and quality scanners like Glama) get
the complete contract from introspection alone.
"""

from __future__ import annotations

import os
from typing import Annotated, Any, Literal

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

API_BASE = os.environ.get("GROUNDROUTE_API_BASE", "https://api.groundroute.ai")
TIMEOUT = float(os.environ.get("GROUNDROUTE_TIMEOUT", "30"))

mcp = FastMCP("groundroute")


# ── Structured output — gives `search` a real outputSchema (MCP best practice) ──
class SearchHit(BaseModel):
    """A single ranked search result."""

    url: str = Field(description="Result URL.")
    title: str | None = Field(default=None, description="Result title.")
    snippet: str | None = Field(
        default=None, description="Short highlighted extract from the page."
    )
    content: str | None = Field(
        default=None,
        description=(
            "Full page body / extract when the engine provides it (page mode → Firecrawl markdown, "
            "academic → Exa text); null for link-only engines. Use this for full-text reading."
        ),
    )
    source_engine: str | None = Field(
        default=None, description="The search engine GroundRoute routed this result to."
    )
    published_at: str | None = Field(
        default=None, description="ISO-8601 publish timestamp, when the engine reports one."
    )


class SearchCitation(BaseModel):
    """A source backing the synthesized answer."""

    url: str = Field(description="Cited source URL.")
    title: str | None = Field(default=None, description="Cited source title.")
    index: int | None = Field(default=None, description="Citation index referenced in the answer.")


class SearchToolMeta(BaseModel):
    """Routing, cache, and billing metadata for the call."""

    request_id: str = Field(description="GroundRoute request id — quote it when reporting issues.")
    cache_tier: str = Field(
        description="Tier that served the query: miss, exact_private, exact_pooled, or semantic."
    )
    degraded: bool = Field(description="True if a fallback/degraded path was used.")
    cost_usd: float = Field(description="Amount billed for this call, in USD.")


class SearchToolResult(BaseModel):
    """The `search` tool's structured result."""

    results: list[SearchHit] = Field(description="Ranked search results.")
    answer: str | None = Field(
        default=None, description="Synthesized answer when the query warrants one; else null."
    )
    citations: list[SearchCitation] = Field(
        default_factory=list, description="Sources backing the answer."
    )
    meta: SearchToolMeta = Field(description="Routing/cache/billing metadata for the call.")


# `from __future__ import annotations` defers the nested refs to strings — resolve them now so the
# JSON schema builds whether this module is run directly or imported by path.
SearchToolResult.model_rebuild()


def _meta(request_id: str, cache_tier: str, degraded: bool, cost_usd: float) -> SearchToolMeta:
    return SearchToolMeta(
        request_id=request_id, cache_tier=cache_tier, degraded=degraded, cost_usd=cost_usd
    )


def _notice(answer: str) -> SearchToolResult:
    """A result that carries an explanatory message instead of search hits (no fabricated data)."""
    return SearchToolResult(
        results=[], answer=answer, citations=[], meta=_meta("n/a", "miss", True, 0.0)
    )


def _to_result(data: dict[str, Any]) -> SearchToolResult:
    """Map the hosted /v1/search JSON onto the structured tool result (tolerant of extra fields)."""
    cache_meta = data.get("cache_meta") or {}
    usage_meta = data.get("usage_meta") or {}
    return SearchToolResult(
        results=[
            SearchHit(
                url=str(r.get("url", "")),
                title=r.get("title"),
                snippet=r.get("snippet"),
                content=r.get("content"),
                source_engine=r.get("source_engine"),
                published_at=r.get("published_at"),
            )
            for r in (data.get("results") or [])
        ],
        answer=data.get("answer"),
        citations=[
            SearchCitation(url=str(c.get("url", "")), title=c.get("title"), index=c.get("index"))
            for c in (data.get("citations") or [])
        ],
        meta=_meta(
            request_id=str(data.get("request_id", "n/a")),
            cache_tier=str(cache_meta.get("cache_tier", "miss")),
            degraded=bool(data.get("degraded", False)),
            cost_usd=float(usage_meta.get("cost_usd", 0.0)),
        ),
    )


@mcp.tool(
    title="Web Search",
    annotations=ToolAnnotations(
        title="Web Search",
        readOnlyHint=True,  # never mutates server/user state
        destructiveHint=False,
        idempotentHint=False,  # repeat calls may return fresh results + bill again
        openWorldHint=True,  # queries the open web
    ),
)
async def search(
    query: Annotated[str, Field(description="The search query.")],
    mode: Annotated[
        Literal["auto", "web", "news", "academic", "answer", "page"],
        Field(
            description=(
                "Search mode: 'auto' (GroundRoute classifies and picks the engine), or force one of "
                "'web', 'news', 'academic', 'answer' (synthesized answer + citations), or 'page' "
                "(fetch full page content)."
            )
        ),
    ] = "auto",
    max_results: Annotated[
        int, Field(description="Maximum number of results to return.", ge=1, le=50)
    ] = 10,
    freshness: Annotated[
        Literal["fresh", "semi", "static"] | None,
        Field(
            description=(
                "Recency filter: 'fresh' (last day/week), 'semi' (last month), or 'static' "
                "(timeless). Omit to let GroundRoute auto-detect from the query."
            )
        ),
    ] = None,
    domains: Annotated[
        list[str] | None,
        Field(description="Restrict results to these domains (include-only), e.g. ['arxiv.org']."),
    ] = None,
    lang: Annotated[
        str | None, Field(description="ISO 639-1 language code to bias results, e.g. 'en'.")
    ] = None,
    country: Annotated[
        str | None, Field(description="ISO 3166-1 alpha-2 country code to bias results, e.g. 'us'.")
    ] = None,
) -> SearchToolResult:
    """Search the live web via GroundRoute.

    Routes the query to the best-value engine across Serper, Brave, Exa, Tavily, Firecrawl, and
    Perplexity (price-led — the cheapest engine that clears a quality bar), serving cache hits when
    available and failing over automatically. Returns ranked results, an optional synthesized answer
    with citations (answer mode), and routing/cache/billing metadata. Use it for any
    current-information, documentation, news, API, or research lookup.
    """
    api_key = os.environ.get("GROUNDROUTE_API_KEY", "").strip()
    if not api_key:
        return _notice(
            "GroundRoute API key not configured. Set the GROUNDROUTE_API_KEY environment variable "
            "(get a key at https://groundroute.ai/keys)."
        )

    payload: dict[str, Any] = {
        "query": query,
        "max_results": max(1, min(max_results, 50)),
        "mode": mode,
    }
    if freshness is not None:
        payload["freshness"] = freshness
    if domains:
        payload["domains"] = domains
    if lang is not None:
        payload["lang"] = lang
    if country is not None:
        payload["country"] = country
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(f"{API_BASE}/v1/search", json=payload, headers=headers)
    except httpx.HTTPError as exc:
        return _notice(f"GroundRoute request failed: {exc}")

    if resp.status_code >= 400:
        return _notice(f"GroundRoute returned HTTP {resp.status_code}: {resp.text[:500]}")

    try:
        return _to_result(resp.json())
    except (ValueError, KeyError, TypeError) as exc:
        return _notice(f"GroundRoute returned an unexpected response: {exc}")


if __name__ == "__main__":
    # FastMCP defaults to the stdio transport.
    mcp.run()
