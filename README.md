# GroundRoute — web search MCP server

[![smithery badge](https://smithery.ai/badge/groundroute-ai/web-search)](https://smithery.ai/servers/groundroute-ai/web-search)

Give your AI agent **web search across 6 engines** (Serper, Brave, Exa, Tavily, Firecrawl, Perplexity) through **one** MCP `search` tool. GroundRoute routes each query to the cheapest engine that meets the quality bar, caches the repeats, and fails over automatically — so you get good results without overpaying or wiring up six APIs.

- **Hosted** (no local process to run): `https://api.groundroute.ai/mcp` (streamable-HTTP)
- **Pricing:** gain-share — you keep ~half the cache savings, so it **never costs more than going direct.** Bring your own engine keys (BYOK) supported.
- **Get an API key:** https://groundroute.ai/keys · **Docs:** https://groundroute.ai/docs/mcp-server · **Live engine benchmark:** https://groundroute.ai/state-of-ai-search

## Install

**Claude Desktop / Claude Code** — add to your MCP config:
```json
{
  "mcpServers": {
    "groundroute": {
      "type": "http",
      "url": "https://api.groundroute.ai/mcp",
      "headers": { "Authorization": "Bearer gr_YOUR_KEY" }
    }
  }
}
```

**Cursor** — `~/.cursor/mcp.json`:
```json
{ "mcpServers": { "groundroute": { "url": "https://api.groundroute.ai/mcp",
  "headers": { "Authorization": "Bearer gr_YOUR_KEY" } } } }
```

**VS Code** (native MCP / Continue) — `.vscode/mcp.json`:
```json
{ "servers": { "groundroute": { "type": "http", "url": "https://api.groundroute.ai/mcp",
  "headers": { "Authorization": "Bearer gr_YOUR_KEY" } } } }
```

**Local / stdio-only clients** — bridge stdio ↔ HTTP with `mcp-remote`:
```json
{ "mcpServers": { "groundroute": {
  "command": "npx",
  "args": ["-y", "mcp-remote", "https://api.groundroute.ai/mcp", "--header", "Authorization:Bearer gr_YOUR_KEY"]
} } }
```

## Run this repo's stdio server (optional)

This repo also ships a small native **stdio** MCP server (`server.py`) that forwards to the hosted API — useful for stdio-only clients or containerized runs.

```bash
pip install -r requirements.txt
GROUNDROUTE_API_KEY=gr_YOUR_KEY python server.py
```

Or with Docker:

```bash
docker build -t groundroute-mcp .
docker run -i -e GROUNDROUTE_API_KEY=gr_YOUR_KEY groundroute-mcp
```

Introspection (tool discovery) works with no key; running a search requires `GROUNDROUTE_API_KEY` (get one at https://groundroute.ai/keys).

## The `search` tool
| Param | Type | Notes |
|---|---|---|
| `query` | string | required |
| `max_results` | integer | default 5, max 50 |
| `mode` | enum | `auto` (default), `web`, `news`, `academic`, `answer`, `page` |

Returns ranked results (and a synthesized answer for answer-class queries). Routed, cached, and reliable.

## How it works
One endpoint in front of many search engines, with price-led routing, caching, failover, and usage governance. See the [docs](https://groundroute.ai/docs/mcp-server) and the [State of AI Search benchmark](https://groundroute.ai/state-of-ai-search) (170 real agent queries across all 6 engines).

## Links
- Homepage: https://groundroute.ai
- Get a key: https://groundroute.ai/keys
- Playground (try without installing): https://groundroute.ai/playground
- Docs: https://groundroute.ai/docs/mcp-server

`registry-manifest.json` in this repo is the listing manifest for MCP registries.
