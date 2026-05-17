"""Prose ingestion: scraped articles (The Ringer, ESPN, The Athletic) and
Reddit threads.

Reddit is read via the public `.json` endpoints (no OAuth). Reddit tightened
developer registration in 2024 and the registration queue is slow; the public
JSON path is rate-limited to 60 req/min/IP and is sufficient for our read-only
ingestion needs. The User-Agent header (REDDIT_USER_AGENT in .env) is the only
required credential — Reddit blocks requests with generic or missing UAs.

Chunks at 400 tokens with 15% overlap, prepends contextual-retrieval prefix,
embeds with voyage-3-large, stores in `articles_chunks` with `player_ids`
populated by `normalize_entities`.

Built out after the initial stats ingestion lands.
"""
