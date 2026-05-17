"""Tests for the entity resolver. Uses an in-memory AliasResolver so the
tests don't depend on a live Postgres."""

from __future__ import annotations

import pytest

from src.normalize_entities.resolve import AliasResolver, _normalize_text, _tokenize


# ----------------------------------------------------------------------------
# _normalize_text / _tokenize
# ----------------------------------------------------------------------------


def test_normalize_text_strips_diacritics() -> None:
    assert _normalize_text("Dončić") == "doncic"
    assert _normalize_text("Luka Dončić") == "luka doncic"


def test_normalize_text_keeps_apostrophes_and_hyphens() -> None:
    assert _normalize_text("D'Angelo Russell") == "d'angelo russell"
    assert _normalize_text("Karl-Anthony Towns") == "karl-anthony towns"


def test_normalize_text_lowercases() -> None:
    assert _normalize_text("LEBRON JAMES") == "lebron james"


def test_normalize_text_collapses_whitespace() -> None:
    assert _normalize_text("Steph   Curry  hit  a  three") == "steph curry hit a three"


def test_tokenize_strips_possessive_s() -> None:
    # "Curry's three" → ["curry", "three"] (possessive stripped)
    assert _tokenize("curry's three") == ["curry", "three"]


def test_tokenize_keeps_apostrophes_inside_names() -> None:
    # "D'Angelo's" → ["d'angelo"] (the possessive 's, not the apostrophe in the name)
    assert _tokenize("d'angelo's three") == ["d'angelo", "three"]


def test_tokenize_keeps_hyphens() -> None:
    assert _tokenize("karl-anthony towns") == ["karl-anthony", "towns"]


def test_tokenize_drops_punctuation() -> None:
    assert _tokenize("steph, curry. hit") == ["steph", "curry", "hit"]


def test_tokenize_handles_empty() -> None:
    assert _tokenize("") == []
    assert _tokenize("   ") == []


# ----------------------------------------------------------------------------
# AliasResolver — using a synthetic map (no DB required)
# ----------------------------------------------------------------------------


@pytest.fixture
def resolver() -> AliasResolver:
    """A small synthetic alias map covering the test cases below."""
    alias_map = {
        # Stephen Curry (id 201939)
        "stephen curry": 201939,
        "steph": 201939,
        "steph curry": 201939,
        "curry": 201939,
        "the chef": 201939,
        "chef curry": 201939,
        # LeBron James (id 2544)
        "lebron james": 2544,
        "lebron": 2544,
        "king james": 2544,
        "the king": 2544,
        # Kevin Durant (id 201142)
        "kevin durant": 201142,
        "kd": 201142,
        "durant": 201142,
        # Karl-Anthony Towns (id 1626157)
        "karl-anthony towns": 1626157,
        "kat": 1626157,
        # Luka Dončić (id 1629029)
        "luka doncic": 1629029,
        "luka": 1629029,
        "doncic": 1629029,
        # D'Angelo Russell (id 1626156)
        "d'angelo russell": 1626156,
    }
    return AliasResolver(alias_to_player_id=alias_map)


def test_resolver_returns_empty_for_empty_text(resolver: AliasResolver) -> None:
    assert resolver.resolve("") == set()
    assert resolver.resolve("   ") == set()


def test_resolver_returns_empty_for_text_with_no_players(resolver: AliasResolver) -> None:
    assert resolver.resolve("The game was a blowout last night.") == set()


def test_resolver_matches_single_player(resolver: AliasResolver) -> None:
    assert resolver.resolve("Stephen Curry hit a three from the logo") == {201939}


def test_resolver_matches_multiple_players(resolver: AliasResolver) -> None:
    result = resolver.resolve("Steph and KD lit up the Lakers tonight")
    assert result == {201939, 201142}


def test_resolver_handles_possessive(resolver: AliasResolver) -> None:
    # "Curry's three" → Stephen Curry
    assert resolver.resolve("Curry's three pointer was clutch") == {201939}


def test_resolver_handles_nicknames(resolver: AliasResolver) -> None:
    assert resolver.resolve("The Chef cooked tonight") == {201939}
    assert resolver.resolve("King James was scoring at will") == {2544}


def test_resolver_handles_diacritics(resolver: AliasResolver) -> None:
    assert resolver.resolve("Luka Dončić scored 40 points") == {1629029}


def test_resolver_handles_hyphenated_names(resolver: AliasResolver) -> None:
    assert resolver.resolve("Karl-Anthony Towns dominated the boards") == {1626157}
    assert resolver.resolve("KAT had 30 and 15") == {1626157}


def test_resolver_handles_apostrophe_in_name(resolver: AliasResolver) -> None:
    assert resolver.resolve("D'Angelo Russell hit the buzzer beater") == {1626156}


def test_resolver_prefers_longest_match_within_position(resolver: AliasResolver) -> None:
    # "Stephen Curry" at position 0: scan tries the 2-token window first
    # ("stephen curry"), finds it, consumes both tokens. The 1-token
    # fallback ("stephen") never runs.
    pairs = resolver.resolve_with_aliases("Stephen Curry hit a deep three")
    assert pairs == [("stephen curry", 201939)]


def test_resolver_avoids_double_counting_in_set(resolver: AliasResolver) -> None:
    # "The Chef Curry" — the resolver may match this as "the chef" + "curry"
    # (greedy left-to-right) or as a different split. Either way, the SET
    # of player_ids should contain Curry once, not twice (sets dedupe).
    assert resolver.resolve("The Chef Curry dropped 50") == {201939}


def test_resolver_greedy_left_to_right(resolver: AliasResolver) -> None:
    # "Stephen Curry" — scanning starts at position 0 ("stephen") and tries
    # the longest match first. Since "stephen curry" is in the map, that
    # 2-token match wins and consumes both tokens.
    pairs = resolver.resolve_with_aliases("Stephen Curry hit a deep three")
    assert pairs == [("stephen curry", 201939)]


def test_resolver_handles_case_insensitive(resolver: AliasResolver) -> None:
    assert resolver.resolve("STEPH curry SCORED") == {201939}


def test_resolver_handles_punctuation_around_names(resolver: AliasResolver) -> None:
    # Commas, periods, etc. shouldn't break matching.
    assert resolver.resolve("Curry, LeBron, and KD all scored 30+") == {201939, 2544, 201142}


def test_resolver_with_empty_alias_map_is_safe() -> None:
    empty = AliasResolver(alias_to_player_id={})
    assert empty.resolve("Stephen Curry") == set()


def test_resolver_len_matches_map_size(resolver: AliasResolver) -> None:
    # Fixture has: Curry(6) + LeBron(4) + KD(3) + KAT(2) + Luka(3) + D'Angelo(1) = 19
    assert len(resolver) == 19
