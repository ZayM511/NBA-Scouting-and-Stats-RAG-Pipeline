"""Tests for the contextual-retrieval prefix builder."""

from __future__ import annotations

from datetime import date

from src.ingest_prose.contextual_prefix import (
    MAX_PLAYERS_IN_PREFIX,
    build_prefix,
)


def test_full_prefix_with_source_date_and_one_player() -> None:
    out = build_prefix(
        source="The Athletic",
        article_date=date(2026, 4, 12),
        player_names=["Victor Wembanyama"],
        chunk_text="Wemby altered an estimated twelve shots at the rim.",
    )
    assert out == (
        "Article from The Athletic, 2026-04-12, about Victor Wembanyama: "
        "Wemby altered an estimated twelve shots at the rim."
    )


def test_prefix_with_two_players_uses_and() -> None:
    out = build_prefix(
        source="ESPN",
        article_date=date(2026, 5, 1),
        player_names=["Nikola Jokić", "Jamal Murray"],
        chunk_text="The pick-and-roll between them produced 28 points.",
    )
    assert "about Nikola Jokić and Jamal Murray" in out


def test_prefix_with_three_players_uses_oxford_comma() -> None:
    out = build_prefix(
        source="The Ringer",
        article_date=date(2026, 4, 20),
        player_names=["LeBron James", "Luka Dončić", "Austin Reaves"],
        chunk_text="The Lakers trio combined for 78 points.",
    )
    assert "LeBron James, Luka Dončić, and Austin Reaves" in out


def test_prefix_truncates_player_list_when_too_long() -> None:
    names = [f"Player {i}" for i in range(MAX_PLAYERS_IN_PREFIX + 5)]
    out = build_prefix(
        source="The Athletic",
        article_date=date(2026, 1, 1),
        player_names=names,
        chunk_text="A power rankings article.",
    )
    # Only the first MAX_PLAYERS_IN_PREFIX names appear; rest collapse.
    assert "Player 0" in out
    assert f"Player {MAX_PLAYERS_IN_PREFIX - 1}" in out
    assert "and 5 others" in out


def test_prefix_dedupes_player_names_preserving_order() -> None:
    out = build_prefix(
        source="r/nba",
        article_date=date(2026, 5, 10),
        player_names=["Curry", "LeBron", "Curry"],
        chunk_text="Both stars dominated their matchups.",
    )
    assert "Curry and LeBron" in out
    # Make sure "Curry" doesn't appear twice in the names section.
    name_section = out.split("about ")[1].split(":")[0]
    assert name_section.count("Curry") == 1


def test_prefix_handles_missing_date() -> None:
    out = build_prefix(
        source="ESPN",
        article_date=None,
        player_names=["Cooper Flagg"],
        chunk_text="Cooper Flagg had 30 in his rookie year.",
    )
    assert "Article from ESPN, about Cooper Flagg:" in out
    # No date string.
    assert "2026" not in out and "None" not in out


def test_prefix_handles_missing_source() -> None:
    out = build_prefix(
        source=None,
        article_date=date(2026, 5, 1),
        player_names=["Anthony Edwards"],
        chunk_text="Ant scored 40 again.",
    )
    assert out.startswith("Article from an unknown source")


def test_prefix_handles_no_players() -> None:
    out = build_prefix(
        source="ESPN",
        article_date=date(2026, 5, 1),
        player_names=[],
        chunk_text="The league shifted toward small ball this season.",
    )
    assert "about no specific player" in out


def test_prefix_accepts_iso_date_string() -> None:
    out = build_prefix(
        source="r/nba",
        article_date="2026-04-22",
        player_names=["Sengun"],
        chunk_text="Sengun had a triple-double.",
    )
    assert "2026-04-22" in out


def test_prefix_includes_chunk_text_unchanged() -> None:
    chunk = "The pick-and-roll produced 28 points. They ran it 12 times."
    out = build_prefix(
        source="ESPN",
        article_date=None,
        player_names=None,
        chunk_text=chunk,
    )
    assert out.endswith(chunk)
