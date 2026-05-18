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
    # 'ok' — filter narrowed players AND chunks came back
    # 'no_chunks' — filter narrowed players but no chunks mentioned them
    # 'fallback_prose' — filter failed (gen_failed / empty / etc.); we
    #     fell back to unfiltered prose retrieval so the synthesis layer
    #     still has something to work with
    # 'filter_failed' — filter failed AND fallback retrieval also empty
    status: str
    notes: str = ""


def retrieve_hybrid(
    question: str,
    *,
    top_k: int = 8,
    bm25_k: int = 50,
    dense_k: int = 50,
    embedder: Embedder | None = None,
    reranker: Reranker | None = None,
    history: list[dict[str, str]] | None = None,
    session_id: str = "hybrid",
) -> HybridRetrievalResult:
    """Run the full hybrid pipeline for one question.

    `history` is an optional list of prior turns (Anthropic-style
    {role, content} dicts) used to give the SQL-filter model conversation
    context so pronouns in follow-up questions can be resolved.
    """
    if not question or not question.strip():
        raise ValueError("question must be non-empty")

    # 1. SQL filter narrows the player set.
    filter_result = generate_hybrid_filter(
        question, history=history, session_id=session_id
    )
    filter_ok = filter_result.status == "ok" and filter_result.player_ids
    if not filter_ok:
        # Fallback: the numeric narrow-down failed or matched nobody. Run
        # unfiltered prose retrieval so the synthesis layer still has
        # something to ground its answer in. We keep the failing
        # FilterResult on the trace so the UI shows exactly what went
        # wrong with the SQL step.
        own_embedder = embedder is None
        own_reranker = reranker is None
        embedder = embedder or Embedder()
        reranker = reranker or Reranker()
        try:
            retrieval = hybrid_search(
                question,
                filters=None,
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
                status="filter_failed",
                notes=(
                    f"sql filter status={filter_result.status}: "
                    f"{filter_result.error}; fallback prose retrieval also "
                    "returned zero chunks."
                ),
            )
        logger.info(
            "hybrid: filter status=%s, falling back to unfiltered prose "
            "(%d chunks)",
            filter_result.status,
            len(retrieval.chunks),
        )
        return HybridRetrievalResult(
            question=question,
            filter=filter_result,
            retrieval=retrieval,
            status="fallback_prose",
            notes=(
                f"SQL filter unavailable ({filter_result.status}: "
                f"{filter_result.error or 'no players matched'}); answered "
                "from unfiltered prose retrieval instead."
            ),
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
