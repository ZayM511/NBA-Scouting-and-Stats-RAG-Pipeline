"""Tests for the Reddit source.

The HTTP-touching code is covered by the smoke run; here we cover the
pure helpers (date conversion, body builder) and the fetcher's input
validation.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.ingest_prose.reddit_source import (
    RedditFetcher,
    _build_body,
    _to_date,
)


# ----------------------------------------------------------------------------
# _to_date
# ----------------------------------------------------------------------------


def test_to_date_handles_unix_timestamp() -> None:
    # Known fixed timestamp: 2026-04-15 00:00:00 UTC.
    ts = 1776211200.0
    out = _to_date(ts)
    assert out == date(2026, 4, 15)


def test_to_date_handles_known_epoch() -> None:
    # 0 returns None (our convention treats 0/None/falsy as "no date").
    # Use a non-zero recognizable timestamp for the positive case.
    # 1735689600 = 2025-01-01 00:00:00 UTC
    assert _to_date(1735689600) == date(2025, 1, 1)


def test_to_date_handles_none_and_zero() -> None:
    assert _to_date(None) is None
    assert _to_date(0) is None


def test_to_date_handles_bad_input() -> None:
    assert _to_date("not a number") is None  # type: ignore[arg-type]


# ----------------------------------------------------------------------------
# _build_body
# ----------------------------------------------------------------------------


def test_build_body_title_only() -> None:
    post = {"title": "Wemby drops 35/12/8 vs the Knicks", "selftext": ""}
    out = _build_body(post, [])
    assert out == "Wemby drops 35/12/8 vs the Knicks"


def test_build_body_includes_selftext() -> None:
    post = {
        "title": "Game thread: SAS vs NYK",
        "selftext": "Wemby was unreal tonight; here's the box.",
    }
    out = _build_body(post, [])
    assert "Game thread: SAS vs NYK" in out
    assert "Wemby was unreal tonight" in out
    # Title and selftext separated by blank line.
    assert out.index("Wemby") > out.index("Game thread")


def test_build_body_appends_top_comments() -> None:
    post = {"title": "Post-game thread", "selftext": ""}
    comments = [
        {"body": "He's already a top-5 defender."},
        {"body": "That block on Brunson was insane."},
    ]
    out = _build_body(post, comments)
    assert "[top comments]" in out
    assert "He's already a top-5 defender." in out
    assert "That block on Brunson was insane." in out


def test_build_body_skips_empty_comments() -> None:
    post = {"title": "Hot take", "selftext": "Curry > MJ."}
    comments = [
        {"body": ""},
        {"body": "   "},
        {"body": "Disagree but respect."},
    ]
    out = _build_body(post, comments)
    # Only the non-empty comment shows.
    assert out.count("- ") == 1
    assert "Disagree but respect" in out


def test_build_body_handles_no_comments_section_when_empty() -> None:
    post = {"title": "Quick question", "selftext": "Anyone watching the game?"}
    out = _build_body(post, [])
    assert "[top comments]" not in out


# ----------------------------------------------------------------------------
# RedditFetcher input validation
# ----------------------------------------------------------------------------


def test_reddit_fetcher_rejects_placeholder_user_agent() -> None:
    with pytest.raises(ValueError, match="REDDIT_USER_AGENT"):
        RedditFetcher(user_agent="nba-rag/0.1 by <your_reddit_username>")


def test_reddit_fetcher_rejects_empty_user_agent() -> None:
    with pytest.raises(ValueError, match="REDDIT_USER_AGENT"):
        RedditFetcher(user_agent="")
