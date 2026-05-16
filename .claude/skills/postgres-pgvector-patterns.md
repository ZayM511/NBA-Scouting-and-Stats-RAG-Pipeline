# Postgres + pgvector — Patterns

Reference for vector search in Postgres on this project. We run Postgres 16 with pgvector via docker compose locally.

## Why Postgres + pgvector and not a separate vector DB

One database means one transaction, one backup story, one connection pool, one auth model. The hybrid query — "filter on `player_ids`, then vector-search the filtered set" — is one SQL statement, not a two-system orchestration. At this project's scale (a few hundred thousand chunks), pgvector is faster than the round-trip to a dedicated vector service. The interview answer is the same answer.

## Index choice: HNSW vs IVFFlat

| Index | When to use | Build time | Query time | Memory |
|---|---|---|---|---|
| **HNSW** | Default. Always use this for production. | Slow (minutes for 1M vectors) | Fast (sub-ms for top-K) | High |
| **IVFFlat** | Only if memory is constrained and HNSW won't fit. | Fast | Slower than HNSW, needs `lists` tuning | Lower |

Use HNSW. The build cost is paid once at ingest. Query latency wins.

```sql
CREATE INDEX articles_chunks_embedding_hnsw
ON articles_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

Tuning:

- `m` (default 16): graph connectivity. Higher = better recall, more memory. Stick with 16 for 1024-dim vectors.
- `ef_construction` (default 64): index build effort. Higher = better recall, slower build. 64 is fine for this project; bump to 200 if recall@5 is below 0.85.
- `hnsw.ef_search` (session-level, default 40): query-time effort. Set in your session for the rerank-first stage:

```sql
SET hnsw.ef_search = 100;
```

## Distance operators

pgvector exposes three operators:

| Operator | Distance | Use when |
|---|---|---|
| `<=>` | Cosine | **Default for embeddings.** Voyage and most modern embedding models are normalized; cosine and inner product converge. |
| `<#>` | Negative inner product | Faster than cosine. Use only if vectors are normalized (Voyage's are). |
| `<->` | Euclidean (L2) | Rarely the right choice for embeddings; use for spatial data. |

The index op-class must match: `vector_cosine_ops` for `<=>`, `vector_ip_ops` for `<#>`, `vector_l2_ops` for `<->`. Mismatched op-class = the index isn't used.

## Hybrid query patterns

### Pattern 1 — Filter then vector search (the project's main pattern)

The `player_ids` GIN index is the most important access path. Always filter on it first when a query mentions a specific player.

```sql
-- 1) Filter to chunks mentioning these players, 2) vector-search within them.
SELECT
  id,
  text,
  source,
  date,
  1 - (embedding <=> $1::vector) AS similarity
FROM articles_chunks
WHERE player_ids && $2::INT[]      -- GIN-indexed array overlap
  AND date >= $3                    -- optional date filter
ORDER BY embedding <=> $1::vector
LIMIT 50;
```

`&&` (array overlap) uses the GIN index. `=` and `IN` on array columns do not — they trigger a sequential scan.

Verify with `EXPLAIN`:

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT ... FROM articles_chunks WHERE player_ids && ARRAY[201939]::INT[] ...;
```

Look for `Bitmap Index Scan on articles_chunks_player_ids_gin` in the plan. If you see `Seq Scan`, the query is not using the index.

### Pattern 2 — Hybrid BM25 + vector with reranking

For prose queries where the user might use exact phrases ("triple-double", specific game dates) along with semantic intent, run BM25 and dense in parallel, merge, then rerank.

```sql
WITH bm25 AS (
  SELECT id, text, ts_rank(text_tsv, plainto_tsquery('english', $1)) AS score
  FROM articles_chunks
  WHERE text_tsv @@ plainto_tsquery('english', $1)
    AND player_ids && $2::INT[]
  ORDER BY score DESC
  LIMIT 50
),
dense AS (
  SELECT id, text, 1 - (embedding <=> $3::vector) AS score
  FROM articles_chunks
  WHERE player_ids && $2::INT[]
  ORDER BY embedding <=> $3::vector
  LIMIT 50
)
SELECT id, text FROM bm25
UNION
SELECT id, text FROM dense;
```

Pass the union to Cohere Rerank 3.5 with the user question. Keep the top 5–10.

### Pattern 3 — Time-aware boost for playoffs

During the playoffs we want recent chunks to win ties. Multiply similarity by an exponential recency factor:

```sql
SELECT
  id,
  text,
  date,
  (1 - (embedding <=> $1::vector)) * EXP(-EXTRACT(DAY FROM (CURRENT_DATE - date)) / 14.0) AS score
FROM articles_chunks
WHERE player_ids && $2::INT[]
ORDER BY score DESC
LIMIT 20;
```

The half-life (14 days) is a tuning knob. Lower during the Finals; raise during the regular season.

## Indexing checklist for this project

```sql
-- The main vector index
CREATE INDEX articles_chunks_embedding_hnsw
ON articles_chunks USING hnsw (embedding vector_cosine_ops);

-- Player ID filter (the most important access path)
CREATE INDEX articles_chunks_player_ids_gin
ON articles_chunks USING gin (player_ids);

-- Full-text search
ALTER TABLE articles_chunks
  ADD COLUMN text_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('english', text)) STORED;

CREATE INDEX articles_chunks_text_tsv_gin
ON articles_chunks USING gin (text_tsv);

-- Date filter for playoff freshness
CREATE INDEX articles_chunks_date_idx
ON articles_chunks (date DESC);

-- For stats queries
CREATE INDEX player_game_stats_player_id_idx ON player_game_stats (player_id);
CREATE INDEX player_game_stats_game_id_idx ON player_game_stats (game_id);
CREATE INDEX games_date_idx ON games (date DESC);
CREATE INDEX games_is_playoff_idx ON games (is_playoff, playoff_round);
```

## Anti-patterns

- **Calling `embedding = $1` instead of `embedding <=> $1::vector`.** Equality on vectors checks every component; you want distance.
- **Forgetting `::vector` cast.** pgvector won't auto-cast a Python list. Without the cast, you'll see "no operator matches" errors.
- **Filtering after `ORDER BY <=>`.** Postgres applies the order before the WHERE if the WHERE isn't index-friendly. Put the filter first; verify with EXPLAIN.
- **Using IVFFlat without recreating the index when the corpus grows.** IVFFlat's `lists` parameter is fixed at build time; a corpus 10x larger needs a rebuild. HNSW grows gracefully.
- **Skipping ANALYZE after bulk insert.** The query planner needs accurate statistics. Run `ANALYZE articles_chunks` after the initial ingest.

## Cost asymmetry to remember (and quote in interviews)

Vector search over 200K chunks = scan-style operation, hundreds of milliseconds.
Vector search over 50 chunks (player-filtered first) = a few milliseconds.

That's roughly **4000x** at the access-path level, and a meaningful accuracy lift because irrelevant chunks can't sneak into the top-K. Metadata pre-filtering is the cheapest accuracy gain in RAG.
