"""Database schema and migrations.

Tables: `players`, `teams`, `games`, `player_game_stats`, `play_by_play`,
`articles_chunks`, `player_aliases`. Indexes: HNSW on chunk embeddings,
GIN on `articles_chunks.player_ids`, GIN tsvector on chunk text, btree on
the hot lookup paths.

The migration runner lands in Step 2.
"""
