"""Tests for the pure-function parts of generate_aliases.py.

The LLM-touching parts get a smoke test once we have a real Anthropic key
in the env; the parsing and normalization functions are unit-tested here."""

from __future__ import annotations

import pytest

from src.normalize_entities.generate_aliases import (
    canonical_rows_for,
    normalize_alias,
    parse_alias_array,
)


# ----------------------------------------------------------------------------
# normalize_alias
# ----------------------------------------------------------------------------


def test_normalize_alias_lowercases() -> None:
    assert normalize_alias("STEPH") == "steph"
    assert normalize_alias("Steph") == "steph"


def test_normalize_alias_strips_diacritics() -> None:
    # Luka Dončić
    assert normalize_alias("Dončić") == "doncic"
    assert normalize_alias("Luka Dončić") == "luka doncic"


def test_normalize_alias_keeps_apostrophes_and_hyphens() -> None:
    assert normalize_alias("D'Angelo Russell") == "d'angelo russell"
    assert normalize_alias("Karl-Anthony Towns") == "karl-anthony towns"
    assert normalize_alias("Shai Gilgeous-Alexander") == "shai gilgeous-alexander"


def test_normalize_alias_strips_other_punctuation() -> None:
    assert normalize_alias("Tim Hardaway Jr.") == "tim hardaway jr"
    assert normalize_alias('"the Chef"') == "the chef"
    assert normalize_alias("(LBJ)") == "lbj"


def test_normalize_alias_collapses_whitespace() -> None:
    assert normalize_alias("  Steph   Curry  ") == "steph curry"
    assert normalize_alias("Steph\tCurry") == "steph curry"


def test_normalize_alias_handles_empty() -> None:
    assert normalize_alias("") == ""
    assert normalize_alias("   ") == ""
    assert normalize_alias("...") == ""


# ----------------------------------------------------------------------------
# parse_alias_array
# ----------------------------------------------------------------------------


def test_parse_alias_array_strict_json() -> None:
    assert parse_alias_array('["Steph", "Curry", "the Chef"]') == ["Steph", "Curry", "the Chef"]


def test_parse_alias_array_with_code_fence() -> None:
    text = '```json\n["Steph", "Curry"]\n```'
    assert parse_alias_array(text) == ["Steph", "Curry"]


def test_parse_alias_array_with_fence_no_lang() -> None:
    text = '```\n["KAT", "Towns"]\n```'
    assert parse_alias_array(text) == ["KAT", "Towns"]


def test_parse_alias_array_with_leading_prose() -> None:
    text = 'Here are the aliases:\n\n["the Joker", "Jokic", "Big Honey"]\n\nDone.'
    assert parse_alias_array(text) == ["the Joker", "Jokic", "Big Honey"]


def test_parse_alias_array_rejects_non_string_entries() -> None:
    # If the model returns a mixed array, drop it (don't try to coerce).
    assert parse_alias_array('["Steph", 123, "Curry"]') == []


def test_parse_alias_array_rejects_object() -> None:
    assert parse_alias_array('{"alias": "Steph"}') == []


def test_parse_alias_array_handles_empty_input() -> None:
    assert parse_alias_array("") == []
    assert parse_alias_array("   ") == []


def test_parse_alias_array_handles_malformed_json() -> None:
    # Missing closing bracket
    assert parse_alias_array('["Steph", "Curry"') == []


# ----------------------------------------------------------------------------
# canonical_rows_for
# ----------------------------------------------------------------------------


def test_canonical_rows_includes_full_name_only() -> None:
    rows = canonical_rows_for({"player_id": 201939, "name": "Stephen Curry"})
    assert len(rows) == 1
    assert rows[0]["alias"] == "stephen curry"
    assert rows[0]["player_id"] == 201939
    assert rows[0]["confidence"] == 1.0
    assert rows[0]["source"] == "canonical"


def test_canonical_rows_handles_diacritics() -> None:
    rows = canonical_rows_for({"player_id": 1629029, "name": "Luka Dončić"})
    assert len(rows) == 1
    assert rows[0]["alias"] == "luka doncic"


def test_canonical_rows_returns_empty_for_no_name() -> None:
    assert canonical_rows_for({"player_id": 1, "name": ""}) == []
