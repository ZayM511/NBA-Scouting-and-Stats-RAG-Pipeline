"""Tests for the programmatic SQL safety layer."""

from __future__ import annotations

import pytest

from src.retrieve_stats.sql_safety import FORBIDDEN_KEYWORDS, review_sql


# ----------------------------------------------------------------------------
# Approved queries
# ----------------------------------------------------------------------------


def test_simple_select_is_approved() -> None:
    r = review_sql("SELECT 1")
    assert r.approved, r.reasons


def test_parameterized_select_is_approved() -> None:
    sql = """
        SELECT name, pts FROM player_game_stats pgs
        JOIN players p ON p.player_id = pgs.player_id
        WHERE p.name = %(name)s
    """
    r = review_sql(sql, params={"name": "Stephen Curry"})
    assert r.approved, r.reasons


def test_cte_starting_with_with_is_approved() -> None:
    sql = "WITH top AS (SELECT player_id FROM players LIMIT 5) SELECT * FROM top"
    r = review_sql(sql)
    assert r.approved, r.reasons


def test_trailing_semicolon_is_allowed() -> None:
    r = review_sql("SELECT 1;")
    assert r.approved, r.reasons


def test_keyword_inside_string_literal_is_tolerated() -> None:
    # 'DELETE' inside a string literal is not a DELETE statement.
    sql = "SELECT 'I will not DELETE anything' AS note"
    r = review_sql(sql)
    assert r.approved, r.reasons


# ----------------------------------------------------------------------------
# Rejected queries
# ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE players",
        "INSERT INTO players VALUES (1, 'x')",
        "UPDATE players SET name = 'x'",
        "DELETE FROM players",
        "ALTER TABLE players ADD COLUMN x INT",
        "TRUNCATE players",
        "GRANT ALL ON players TO nbarag",
        "REVOKE ALL ON players FROM nbarag",
        "COPY players FROM '/etc/passwd'",
        "VACUUM players",
    ],
)
def test_forbidden_keywords_rejected(sql: str) -> None:
    r = review_sql(sql)
    assert not r.approved
    assert any("forbidden keyword" in reason for reason in r.reasons)


def test_multi_statement_rejected() -> None:
    r = review_sql("SELECT 1; SELECT 2")
    assert not r.approved
    assert any("multi-statement" in reason for reason in r.reasons)


def test_empty_sql_rejected() -> None:
    r = review_sql("")
    assert not r.approved
    r2 = review_sql("   ")
    assert not r2.approved


def test_query_not_starting_with_select_or_with_rejected() -> None:
    # Even if it's harmless-looking, EXPLAIN/SET/etc. shouldn't pass the gate.
    r = review_sql("EXPLAIN SELECT 1")
    assert not r.approved


def test_declared_params_without_placeholders_rejected() -> None:
    # Model claimed it parameterized but the SQL has no %(...)s.
    r = review_sql("SELECT name FROM players WHERE name = 'Curry'", params={"name": "Curry"})
    assert not r.approved
    assert any("no %(name)s placeholders" in reason for reason in r.reasons)


def test_no_params_with_no_placeholders_is_fine() -> None:
    # A query with no user input doesn't need params.
    r = review_sql("SELECT COUNT(*) FROM players", params={})
    assert r.approved, r.reasons


# ----------------------------------------------------------------------------
# Edge cases
# ----------------------------------------------------------------------------


def test_forbidden_word_as_substring_of_identifier_is_tolerated() -> None:
    # 'updates' is not the UPDATE keyword (different token).
    sql = "SELECT * FROM (SELECT 1 AS updates) t"
    r = review_sql(sql)
    assert r.approved, r.reasons


def test_block_comment_with_forbidden_keyword_is_stripped() -> None:
    sql = "/* DROP TABLE pets; */ SELECT 1"
    r = review_sql(sql)
    assert r.approved, r.reasons


def test_line_comment_with_forbidden_keyword_is_stripped() -> None:
    sql = "SELECT 1 -- DROP TABLE pets"
    r = review_sql(sql)
    assert r.approved, r.reasons


def test_forbidden_keywords_constant_is_uppercase() -> None:
    for kw in FORBIDDEN_KEYWORDS:
        assert kw == kw.upper(), f"{kw} should be uppercase in the constant"
