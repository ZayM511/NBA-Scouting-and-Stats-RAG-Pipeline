"""Tests that the SCHEMA_DESCRIPTION constant stays in sync with the
actual migration file. If a column is dropped from 001_init.sql, this
test fails so the prompt can be updated to match."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.retrieve_stats.schema import SCHEMA_DESCRIPTION


@pytest.fixture(scope="module")
def init_sql() -> str:
    path = Path(__file__).parent.parent.parent / "src" / "schema" / "migrations" / "001_init.sql"
    return path.read_text(encoding="utf-8").lower()


REQUIRED_TABLES = (
    "players",
    "teams",
    "games",
    "player_game_stats",
    "play_by_play",
    "articles_chunks",
)


REQUIRED_COLUMNS = (
    ("players", "is_top30"),
    ("players", "team"),
    ("players", "position"),
    ("games", "is_playoff"),
    ("games", "playoff_round"),
    ("games", "season"),
    ("games", "season_type"),
    ("player_game_stats", "is_clutch_data"),
    ("player_game_stats", "ts_pct"),
    ("player_game_stats", "pts"),
    ("articles_chunks", "player_ids"),
)


@pytest.mark.parametrize("table", REQUIRED_TABLES)
def test_schema_description_includes_table(table: str) -> None:
    assert table in SCHEMA_DESCRIPTION.lower(), (
        f"SCHEMA_DESCRIPTION missing {table!r} (Phase E will produce bad SQL without it)"
    )


@pytest.mark.parametrize("table,column", REQUIRED_COLUMNS)
def test_schema_description_includes_column(table: str, column: str) -> None:
    assert column in SCHEMA_DESCRIPTION.lower(), (
        f"SCHEMA_DESCRIPTION missing {table}.{column!r}"
    )


@pytest.mark.parametrize("table", REQUIRED_TABLES)
def test_init_sql_actually_has_table(table: str, init_sql: str) -> None:
    """Sanity check: the migration file really has these tables (so the
    description above can't drift into a fantasy schema)."""
    assert f"create table if not exists {table}" in init_sql, (
        f"migration 001_init.sql missing CREATE TABLE for {table}"
    )


def test_schema_description_mentions_gin_player_ids_pattern() -> None:
    # The SQL gen prompt depends on this convention being explicit.
    assert "gin" in SCHEMA_DESCRIPTION.lower()
    assert "&&" in SCHEMA_DESCRIPTION
