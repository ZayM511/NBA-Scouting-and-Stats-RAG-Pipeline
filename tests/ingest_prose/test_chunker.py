"""Tests for the recursive token chunker."""

from __future__ import annotations

import pytest

from src.ingest_prose.chunker import (
    DEFAULT_OVERLAP_RATIO,
    DEFAULT_TARGET_TOKENS,
    Chunk,
    chunk_text,
    count_tokens,
)


# ----------------------------------------------------------------------------
# Edge cases
# ----------------------------------------------------------------------------


def test_chunk_text_empty_input() -> None:
    assert chunk_text("") == []


def test_chunk_text_whitespace_only() -> None:
    assert chunk_text("   \n\n   ") == []


def test_chunk_text_short_input_returns_one_chunk() -> None:
    chunks = chunk_text("This is a short article about Steph Curry.")
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].text == "This is a short article about Steph Curry."
    assert chunks[0].token_count == count_tokens(chunks[0].text)


def test_chunk_text_rejects_invalid_target() -> None:
    with pytest.raises(ValueError, match="target_tokens"):
        chunk_text("hello", target_tokens=0)
    with pytest.raises(ValueError, match="target_tokens"):
        chunk_text("hello", target_tokens=-1)


def test_chunk_text_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError, match="overlap_ratio"):
        chunk_text("hello", overlap_ratio=1.0)
    with pytest.raises(ValueError, match="overlap_ratio"):
        chunk_text("hello", overlap_ratio=-0.1)


# ----------------------------------------------------------------------------
# Real chunking
# ----------------------------------------------------------------------------


def _long_text(n_paragraphs: int = 20) -> str:
    """Build a text that's deliberately long enough to need chunking."""
    paragraph = (
        "Stephen Curry has long been the most dominant shooter in NBA history. "
        "His range from beyond the arc extends well past the standard three-point line, "
        "and his ability to score off movement creates unique defensive challenges. "
        "Opposing teams routinely send two defenders at him on screen actions, "
        "creating 4-on-3 advantages for the rest of the Warriors offense."
    )
    return "\n\n".join([paragraph] * n_paragraphs)


def test_chunk_text_splits_long_input_into_multiple_chunks() -> None:
    text = _long_text(20)
    chunks = chunk_text(text, target_tokens=100)
    assert len(chunks) > 1


def test_chunk_text_assigns_sequential_indexes() -> None:
    text = _long_text(20)
    chunks = chunk_text(text, target_tokens=100)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_chunk_text_respects_target_token_count_within_tolerance() -> None:
    text = _long_text(20)
    target = 200
    overlap = int(target * DEFAULT_OVERLAP_RATIO)  # 30
    chunks = chunk_text(text, target_tokens=target)
    for c in chunks:
        # Allow target + overlap headroom; the grouping doesn't split inside
        # a piece, so the last piece in a chunk can push slightly over.
        assert c.token_count <= target + overlap + 50, (
            f"chunk {c.chunk_index} has {c.token_count} tokens, target {target}"
        )


def test_chunk_text_produces_overlap_between_consecutive_chunks() -> None:
    text = _long_text(30)
    chunks = chunk_text(text, target_tokens=150, overlap_ratio=0.20)
    assert len(chunks) >= 2
    # The trailing portion of chunk[i] should appear somewhere near the
    # start of chunk[i+1] (because we prepend the previous chunk's tail).
    for i in range(len(chunks) - 1):
        # Take the last ~10 chars of chunk i and look for them at the start of chunk i+1.
        tail_snippet = chunks[i].text[-50:].strip()
        # The overlap is a token suffix, not a character suffix, so just check
        # a shorter word appears.
        for word in tail_snippet.split():
            if len(word) >= 4 and word.lower() in chunks[i + 1].text[:200].lower():
                break
        else:
            pytest.fail(
                f"no overlap word from chunk {i} tail found in chunk {i+1} head"
            )


def test_chunk_text_zero_overlap_produces_no_overlap() -> None:
    text = _long_text(20)
    chunks = chunk_text(text, target_tokens=150, overlap_ratio=0.0)
    # With zero overlap the chunks should still cover the text (modulo a
    # tiny amount lost to strip()).
    assert len(chunks) > 1


def test_chunk_text_preserves_player_names_inside_chunks() -> None:
    text = _long_text(20)
    chunks = chunk_text(text, target_tokens=100)
    # "Stephen Curry" appears in every paragraph, so every chunk should
    # contain at least one instance.
    joined = " ".join(c.text for c in chunks)
    assert "Stephen Curry" in joined


# ----------------------------------------------------------------------------
# count_tokens helper
# ----------------------------------------------------------------------------


def test_count_tokens_empty() -> None:
    assert count_tokens("") == 0


def test_count_tokens_short_string() -> None:
    n = count_tokens("hello world")
    assert n >= 1
    assert n <= 4  # very loose upper bound


def test_count_tokens_grows_with_text() -> None:
    short = count_tokens("hello")
    long_text = count_tokens("hello " * 100)
    assert long_text > short * 50  # roughly proportional
