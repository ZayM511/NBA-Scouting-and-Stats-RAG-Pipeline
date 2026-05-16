"""Unit tests for matchup parsing in games.py."""

from __future__ import annotations

from src.ingest_stats.games import _parse_matchup


def test_parse_matchup_home_game() -> None:
    # "GSW vs. LAL" means GSW is home, LAL is away.
    home, away = _parse_matchup("GSW vs. LAL", team_abbr="GSW")
    assert home == "GSW"
    assert away == "LAL"


def test_parse_matchup_away_game() -> None:
    # "GSW @ LAL" means GSW is away, LAL is home.
    home, away = _parse_matchup("GSW @ LAL", team_abbr="GSW")
    assert home == "LAL"
    assert away == "GSW"


def test_parse_matchup_handles_three_letter_abbrs() -> None:
    home, away = _parse_matchup("OKC vs. SAS", team_abbr="OKC")
    assert home == "OKC"
    assert away == "SAS"
