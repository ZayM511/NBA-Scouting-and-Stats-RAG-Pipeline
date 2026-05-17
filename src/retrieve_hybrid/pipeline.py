"""Hybrid retrieval orchestrator.

Pipeline:

  1. SQL filter → returns DISTINCT player_id matching the numeric criteria
  2. Hybrid prose search → BM25 + dense + Cohere Rerank, FILTERED to those
     player_ids via the GIN index on articles_chunks.player_ids
  3. Synthesis → combines the player set narrative with the prose findings

The output `HybridRetrievalResult` carries the full trace so the UI's
visible tool-use sidebar can show: the SQL that ran, the player set it
narrowed to, the chunks that came back, and the final synthesized answer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.ingest_prose.embedder import Embedder
from src.retrieve_hybrid.sql_filter import FilterResult, generate_hybrid_filter
from src.retrieve_prose.filters import ChunkFilters
from src.retrieve_prose.hybrid_search import HybridSearchResult, hybrid_search
from src.retrieve_prose.rerank import Reranker

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HybridRetrievalResult:
    """Full hybrid retrieval trace for the UI sidebar."""

    question: str
    filter: FilterResult
    retrieval: HybridSearchResult | None
    status: str  # 'ok' | 'no_players' | 'no_chunks' | 'filter_failed'
    notes: str = ""


def retrieve_hybrid(
    question: str,
    *,
    top_k: int = 8,
    bm25_k: int = 50,
    dense_k: int = 50,
    embedder: Embedder | None = None,
    reranker: Reranker | None = None,
    session_id: str = "hybrid",
) -> HybridRetrievalResult:
    """Run the full hybrid pipeline for one question."""
    if not question or not question.strip():
        raise ValueError("question must be non-empty")

    # 1. SQL filter narrows the player set.
    filter_result = generate_hybrid_filter(question, session_id=session_id)
    if filter_result.status not in ("ok", "empty"):
        return HybridRetrievalResult(
            question=question,
            filter=filter_result,
            retrieval=None,
            status="filter_failed",
            notes=f"sql filter status={filter_result.status}: {filter_result.error}",
        )
    if filter_result.status == "empty":
        return HybridRetrievalResult(
            question=question,
            filter=filter_result,
            retrieval=None,
            status="no_players",
            notes="The numeric filter matched zero players.",
        )

    logger.info(
        "hybrid: narrowed to %d player_ids: %s",
        len(filter_result.player_ids),
        filter_result.player_ids[:10],
    )

    # 2. Hybrid prose search inside the filtered player set.
    chunk_filters = ChunkFilters(player_ids=filter_result.player_ids)
    own_embedder = embedder is None
    own_reranker = reranker is None
    embedder = embedder or Embedder()
    reranker = reranker or Reranker()
    try:
        retrieval = hybrid_search(
            question,
            filters=chunk_filters,
            top_k=top_k,
            bm25_k=bm25_k,
            dense_k=dense_k,
            embedder=embedder,
            reranker=reranker,
        )
    finally:
        if own_embedder:
            embedder.close()
        if own_reranker:
            reranker.close()

    if not retrieval.chunks:
        return HybridRetrievalResult(
            question=question,
            filter=filter_result,
            retrieval=retrieval,
            status="no_chunks",
            notes=(
                f"Narrowed to {len(filter_result.player_ids)} players but no "
                "chunks mention them in the corpus."
            ),
        )

    return HybridRetrievalResult(
        question=question,
        filter=filter_result,
        retrieval=retrieval,
        status="ok",
    )
