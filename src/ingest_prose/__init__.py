"""Prose ingestion: scraped articles (The Ringer, ESPN, The Athletic) and
Reddit threads (PRAW).

Chunks at 400 tokens with 15% overlap, prepends contextual-retrieval prefix,
embeds with voyage-3-large, stores in `articles_chunks` with `player_ids`
populated by `normalize_entities`.

Built out after the initial stats ingestion lands.
"""
