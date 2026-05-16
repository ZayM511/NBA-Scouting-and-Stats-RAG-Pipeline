# brave-search (MCP)

Brave Search's MCP server. Useful during prose ingestion to find recent articles about specific players or playoff games, especially during dev when the corpus is still being built. Also handy during the live playoff updates phase when fresh content needs to be discovered between scheduled scrapes.

## Config (in .mcp.json)

```json
"brave-search": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-brave-search"],
  "env": {
    "BRAVE_API_KEY": "${env:BRAVE_API_KEY}"
  }
}
```

Get a free API key at brave.com/search/api. The free tier covers 2000 queries per month, plenty for dev work.

## Tools it exposes

- `brave_web_search` — general web search with query + count + offset.
- `brave_local_search` — locality-aware search (not relevant for this project).

The server returns: title, URL, description, age, and a snippet. Claude Code can take any of those URLs and pass them to a separate scraper.

## Use cases for this project

### 1. Finding recent player articles during ingestion

> "Find recent articles about Wemby's defensive performance this season."

Brave returns the top ten URLs with descriptions. Claude Code filters to articles from the allowlist (The Ringer, ESPN, The Athletic, etc.), passes them to the scraper.

### 2. Filling gaps after a stats anomaly

> "Curry just scored 50 last night. What did the major outlets write about it?"

Useful right after a notable game when the daily scrape hasn't run yet.

### 3. Playoff coverage discovery

The playoff window is when fresh content matters most. Between scheduled scrapes, brave-search finds the new articles since the last run.

### 4. Finding scouting reports on draft prospects

If we ever extend the project to incoming rookies, Brave is the right tool for finding No Ceilings-style scouting newsletters that don't show up on the regular news sites.

## When to prefer this over hardcoded source URLs

Hardcoded source URLs (a list of "scrape The Ringer's NBA feed every day") are the right default for routine ingestion. Brave is the right tool for:

- **Discovery.** Finding new outlets or new pieces that the hardcoded list missed.
- **Long tail.** Lesser-known scouting writers whose feeds aren't worth a permanent crawler.
- **Recent events.** When something just happened and the routine scrape is hours away.

Hardcoded scrapers are predictable and rate-limit-friendly. Brave search is on-demand and pays per query. Use the right tool for each job.

## Cost / safety notes

- 2000 free queries per month. Don't burn them on dev experiments; cache results aggressively.
- The free tier doesn't include date filters reliably; you may need to filter Brave's `age` field yourself.
- Articles linked from Brave are still untrusted content. Pass them through the same chunk-normalization pipeline as any other source (strip instruction-like phrases, log the URL and content hash).
- Respect each outlet's robots.txt. Brave finding a URL doesn't mean the outlet wants you scraping it.

## When not to use this

- During production query-time. The latency is unacceptable. Pre-ingest everything.
- For numeric stats. Brave returns prose; the stats live in nba_api.
- For finding nicknames. The Reddit corpus already covers that.
