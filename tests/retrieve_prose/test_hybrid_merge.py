"""Tests for hybrid_search.merge_results."""

from __future__ import annotations

from src.retrieve_prose.filters import ScoredChunk
from src.retrieve_prose.hybrid_search import merge_results


def _chunk(chunk_id: int, score: float = 0.5) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=chunk_id,
        article_id=f"art-{chunk_id}",
        text=f"chunk {chunk_id} text",
        source="r/nba",
        article_type="reddit_thread",
        score=score,
    )


def test_merge_empty_inputs() -> None:
    assert merge_results([], []) == []


def test_merge_keeps_unique_chunks() -> None:
    bm25 = [_chunk(1), _chunk(2)]
    dense = [_chunk(3), _chunk(4)]
    out = merge_results(bm25, dense)
    ids = [c.chunk_id for c in out]
    assert ids == [1, 2, 3, 4]


def test_merge_deduplicates_on_chunk_id() -> None:
    bm25 = [_chunk(1, score=0.9), _chunk(2)]
    dense = [_chunk(2, score=0.7), _chunk(3)]
    out = merge_results(bm25, dense)
    ids = [c.chunk_id for c in out]
    # 2 appears once; 1, 2, 3 in BM25-then-dense order.
    assert ids == [1, 2, 3]


def test_merge_preserves_bm25_score_when_chunk_in_both() -> None:
    # Bm25 has chunk 2 at score 0.9; dense has chunk 2 at 0.7.
    # The merge picks BM25's instance (the reranker will rescore anyway).
    bm25 = [_chunk(2, score=0.9)]
    dense = [_chunk(2, score=0.7)]
    out = merge_results(bm25, dense)
    assert len(out) == 1
    assert out[0].score == 0.9


def test_merge_preserves_bm25_order_first() -> None:
    bm25 = [_chunk(5), _chunk(3), _chunk(1)]
    dense = [_chunk(2), _chunk(4)]
    out = merge_results(bm25, dense)
    assert [c.chunk_id for c in out] == [5, 3, 1, 2, 4]
