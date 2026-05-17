"""Hybrid retrieval: BM25 union Dense, then Cohere Rerank.

Two-stage retrieval is the production pattern: cheap recall via BM25
and dense vector search (each returning ~50 candidates), then a smart
rerank step that re-scores the merged set with a cross-encoder. This
gives speed (we don't run the slow reranker over the whole corpus)
and accuracy (the merge of keyword + semantic catches both kinds of
match).

Pipeline:

  1. BM25 search → up to `bm25_k` chunks ordered by ts_rank_cd
  2. Dense search → up to `dense_k` chunks ordered by cosine similarity
  3. Merge on chunk_id (preserve the best score from each side)
  4. Rerank the merged candidate set with Cohere Rerank 3.5
  5. Return the top `top_k` chunks ordered by rerank relevance
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from src.config import get_settings
from src.ingest_prose.embedder import Embedder
from src.retrieve_prose.bm25 import search_bm25
from src.retrieve_prose.dense import search_dense
from src.retrieve_prose.filters import ChunkFilters, ScoredChunk
from src.retrieve_prose.rerank import Reranker

logger = logging.getLogger(__name__)


DEFAULT_BM25_K = 50
DEFAULT_DENSE_K = 50
DEFAULT_TOP_K = 10


@dataclass(frozen=True)
class HybridSearchResult:
    """Result of one hybrid search call. Includes the trace info the UI
    will eventually surface in the visible tool-use sidebar."""

    chunks: list[ScoredChunk]
    bm25_count: int
    dense_count: int
    merged_count: int
    reranked_count: int


def merge_results(
    bm25: list[ScoredChunk], dense: list[ScoredChunk]
) -> list[ScoredChunk]:
    """Union by chunk_id. Keep the BM25 instance when both are present
    (the score will be replaced by the reranker anyway; BM25 first is a
    stable, deterministic choice).
    """
    seen: set[int] = set()
    out: list[ScoredChunk] = []
    for c in bm25:
        if c.chunk_id not in seen:
            out.append(c)
            seen.add(c.chunk_id)
    for c in dense:
        if c.chunk_id not in seen:
            out.append(c)
            seen.add(c.chunk_id)
    return out


def hybrid_search(
    query: str,
    *,
    filters: ChunkFilters | None = None,
    bm25_k: int = DEFAULT_BM25_K,
    dense_k: int = DEFAULT_DENSE_K,
    top_k: int = DEFAULT_TOP_K,
    embedder: Embedder | None = None,
    reranker: Reranker | None = None,
    conn: psycopg.Connection | None = None,
) -> HybridSearchResult:
    """Run BM25 + dense + merge + Cohere Rerank.

    Reuse `embedder` and `reranker` across calls so the HTTP sessions stay
    warm. Pass a `conn` to keep BM25 and dense in the same transaction.
    """
    if not query or not query.strip():
        return HybridSearchResult(chunks=[], bm25_count=0, dense_count=0, merged_count=0, reranked_count=0)

    own_conn = conn is None
    if own_conn:
        settings = get_settings()
        conn = psycopg.connect(str(settings.postgres_url), row_factory=dict_row)
        register_vector(conn)
    own_embedder = embedder is None
    if own_embedder:
        embedder = Embedder()
    own_reranker = reranker is None
    if own_reranker:
        reranker = Reranker()

    try:
        bm25_hits = search_bm25(query, filters=filters, top_k=bm25_k, conn=conn)
        dense_hits = search_dense(
            query, filters=filters, top_k=dense_k, embedder=embedder, conn=conn
        )
        merged = merge_results(bm25_hits, dense_hits)

        if not merged:
            return HybridSearchResult(
                chunks=[], bm25_count=len(bm25_hits), dense_count=len(dense_hits),
                merged_count=0, reranked_count=0,
            )

        reranked = reranker.rerank_chunks(query, merged, top_k=top_k)
        return HybridSearchResult(
            chunks=reranked,
            bm25_count=len(bm25_hits),
            dense_count=len(dense_hits),
            merged_count=len(merged),
            reranked_count=len(reranked),
        )
    finally:
        if own_conn and conn is not None:
            conn.close()
        if own_embedder and embedder is not None:
            embedder.close()
        if own_reranker and reranker is not None:
            reranker.close()
