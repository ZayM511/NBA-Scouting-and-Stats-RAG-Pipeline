"""Dense (vector) retrieval via pgvector cosine distance.

Embeds the query with `voyage-3-large` (input_type='query' — Voyage's
asymmetric models need this) and orders chunks by `embedding <=> $vec`.
The HNSW index on the embedding column accelerates this once the corpus
is large enough that the planner prefers it over seq scan.

Returns up to `top_k` `ScoredChunk` results, sorted by descending cosine
similarity (which is 1 - cosine distance).
"""

from __future__ import annotations

import logging

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from src.config import get_settings
from src.ingest_prose.embedder import Embedder
from src.retrieve_prose.filters import ChunkFilters, ScoredChunk

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 50


def search_dense(
    query: str,
    *,
    filters: ChunkFilters | None = None,
    top_k: int = DEFAULT_TOP_K,
    embedder: Embedder | None = None,
    conn: psycopg.Connection | None = None,
) -> list[ScoredChunk]:
    """Dense vector retrieval. Returns up to `top_k` chunks.

    Reuse an `Embedder` across calls so the HTTP session and headers
    stay warm. Reuse a `conn` across multiple retrievers (BM25 + dense
    + filters) for a single query.
    """
    if not query or not query.strip():
        return []
    filters = filters or ChunkFilters()

    own_embedder = embedder is None
    embedder = embedder or Embedder()
    try:
        query_vec = embedder.embed_query(query.strip())
    finally:
        if own_embedder:
            embedder.close()

    where_clauses, params = filters.to_sql_clauses(table_alias="ac")
    params["query_vec"] = query_vec
    params["top_k"] = top_k

    where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    sql = f"""
        SELECT
            ac.id              AS chunk_id,
            ac.article_id      AS article_id,
            ac.text            AS text,
            ac.source          AS source,
            ac.article_type    AS article_type,
            ac.date            AS date,
            ac.player_ids      AS player_ids,
            1 - (ac.embedding <=> %(query_vec)s::vector) AS score
        FROM articles_chunks ac
        {where}
        ORDER BY ac.embedding <=> %(query_vec)s::vector
        LIMIT %(top_k)s
    """

    rows = _execute(sql, params, conn)
    return [_row_to_chunk(r) for r in rows]


def _execute(sql: str, params: dict, conn: psycopg.Connection | None):
    if conn is None:
        settings = get_settings()
        with psycopg.connect(str(settings.postgres_url), row_factory=dict_row) as own:
            register_vector(own)
            with own.cursor() as cur:
                cur.execute(sql, params)
                return list(cur.fetchall())
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def _row_to_chunk(row: dict) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=int(row["chunk_id"]),
        article_id=str(row["article_id"]),
        text=row["text"],
        source=row["source"],
        article_type=row["article_type"],
        score=float(row["score"] or 0.0),
        date=row.get("date"),
        player_ids=list(row.get("player_ids") or []),
    )
