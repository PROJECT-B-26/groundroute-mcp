"""GroundRoute MCP server (stdio).

A thin local MCP server that exposes a single ``search`` tool and forwards each
call to the hosted GroundRoute API (https://api.groundroute.ai). Most users
should use the hosted streamable-HTTP endpoint directly (see README); this stdio
server exists for stdio-only clients and for automated registry introspection.

Introspection (initialize / tools/list) works with no credentials. Executing a
search requires a GroundRoute API key in the GROUNDROUTE_API_KEY environment
variable (get one at https://groundroute.ai/keys).
"""

from __future__ import annotations

import os
from typing import Literal

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = os.environ.get("GROUNDROUTE_API_BASE", "https://api.groundroute.ai")
TIMEOUT = float(os.environ.get("GROUNDROUTE_TIMEOUT", "30"))

mcp = FastMCP("groundroute")


@mcp.tool()
async def search(
    query: str,
    max_results: int = 5,
    mode: Literal["auto", "web", "news", "academic", "answer", "page"] = "auto",
) -> str:
    """Search the live web across 6 engines (Serper, Brave, Exa, Tavily, Firecrawl, Perplexity) through one tool. Routes each query to the cheapest engine that clears a quality bar, caches repeats, and fails over automatically. Use for any current-information, documentation, news, API, or research lookup."""
    api_key = os.environ.get("GROUNDROUTE_API_KEY", "").strip()
    if not api_key:
        return (
            "GroundRoute API key not configured. Set the GROUNDROUTE_API_KEY "
            "environment variable (get a key at https://groundroute.ai/keys)."
        )

    payload = {"query": query, "max_results": max(1, min(max_results, 50)), "mode": mode}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(f"{API_BASE}/v1/search", json=payload, headers=headers)
    except httpx.HTTPError as exc:
        return f"GroundRoute request failed: {exc}"

    if resp.status_code >= 400:
        return f"GroundRoute returned HTTP {resp.status_code}: {resp.text[:500]}"

    return resp.text


if __name__ == "__main__":
    # FastMCP defaults to the stdio transport.
    mcp.run()
