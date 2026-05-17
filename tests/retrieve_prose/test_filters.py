"""Tests for ChunkFilters SQL generation."""

from __future__ import annotations

from datetime import date

from src.retrieve_prose.filters import ChunkFilters


def test_empty_filters_produce_no_clauses() -> None:
    clauses, params = ChunkFilters().to_sql_clauses()
    assert clauses == []
    assert params == {}


def test_player_ids_uses_array_overlap_operator() -> None:
    clauses, params = ChunkFilters(player_ids=[201939, 2544]).to_sql_clauses()
    assert len(clauses) == 1
    assert "ac.player_ids && %(player_ids)s::INT[]" == clauses[0]
    assert params["player_ids"] == [201939, 2544]


def test_team_filter() -> None:
    clauses, params = ChunkFilters(team="GSW").to_sql_clauses()
    assert clauses == ["ac.team = %(team)s"]
    assert params == {"team": "GSW"}


def test_source_filter() -> None:
    clauses, params = ChunkFilters(source="r/nba").to_sql_clauses()
    assert clauses == ["ac.source = %(source)s"]
    assert params == {"source": "r/nba"}


def test_article_type_filter() -> None:
    clauses, params = ChunkFilters(article_type="reddit_thread").to_sql_clauses()
    assert clauses == ["ac.article_type = %(article_type)s"]
    assert params == {"article_type": "reddit_thread"}


def test_date_range_filter() -> None:
    clauses, params = ChunkFilters(
        date_from=date(2026, 4, 1),
        date_to=date(2026, 5, 31),
    ).to_sql_clauses()
    assert "ac.date >= %(date_from)s" in clauses
    assert "ac.date <= %(date_to)s" in clauses
    assert params["date_from"] == date(2026, 4, 1)
    assert params["date_to"] == date(2026, 5, 31)


def test_combined_filters() -> None:
    f = ChunkFilters(
        player_ids=[201939],
        source="r/nba",
        article_type="reddit_thread",
        date_from=date(2026, 5, 1),
    )
    clauses, params = f.to_sql_clauses()
    assert len(clauses) == 4
    # Each filter shows up as a named parameter (no string concatenation).
    assert all("%(" in c for c in clauses)
    assert set(params.keys()) == {"player_ids", "source", "article_type", "date_from"}


def test_table_alias_is_configurable() -> None:
    clauses, _ = ChunkFilters(team="LAL").to_sql_clauses(table_alias="chunks")
    assert clauses == ["chunks.team = %(team)s"]
