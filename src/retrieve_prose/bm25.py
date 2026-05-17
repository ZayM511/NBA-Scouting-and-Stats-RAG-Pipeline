"""BM25-style keyword retrieval via Postgres `ts_rank_cd`.

`articles_chunks.text_tsv` is a GENERATED tsvector column with a GIN
index (see `src/schema/migrations/001_init.sql`). The retriever ranks
matches via `ts_rank_cd`, which is the cover-density rank (favours
chunks where the query terms cluster close together — usually the
right BM25-like behavior for short, focused chunks).

Returns up to `top_k` `ScoredChunk` results, sorted by descending rank.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from src.config import get_settings
from src.retrieve_prose.filters import ChunkFilters, ScoredChunk

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 50


def search_bm25(
    query: str,
    *,
    filters: ChunkFilters | None = None,
    top_k: int = DEFAULT_TOP_K,
    conn: psycopg.Connection | None = None,
) -> list[ScoredChunk]:
    """BM25-style keyword retrieval. Returns up to `top_k` chunks.

    Caller can pass a live `conn` to reuse a transaction; otherwise this
    opens its own connection via the central config.
    """
    if not query or not query.strip():
        return []
    filters = filters or ChunkFilters()

    where_clauses, params = filters.to_sql_clauses(table_alias="ac")
    where_clauses.append("ac.text_tsv @@ plainto_tsquery('english', %(query)s)")
    params["query"] = query.strip()
    params["top_k"] = top_k

    where = " AND ".join(where_clauses)
    sql = f"""
        SELECT
            ac.id              AS chunk_id,
            ac.article_id      AS article_id,
            ac.text            AS text,
            ac.source          AS source,
            ac.article_type    AS article_type,
            ac.date            AS date,
            ac.player_ids      AS player_ids,
            ts_rank_cd(ac.text_tsv, plainto_tsquery('english', %(query)s)) AS score
        FROM articles_chunks ac
        WHERE {where}
        ORDER BY score DESC
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
