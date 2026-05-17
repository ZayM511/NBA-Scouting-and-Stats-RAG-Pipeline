"""Unit tests for the pure-function helpers in schedule.py."""

from __future__ import annotations

import pandas as pd

from src.ingest_stats.schedule import (
    _first_broadcaster,
    _infer_playoff,
    _infer_playoff_round,
    _map_schedule_row,
    _parse_iso,
)


def test_parse_iso_handles_zulu_and_offset() -> None:
    assert _parse_iso("2026-05-18T20:30:00Z") == "2026-05-18T20:30:00+00:00"
    assert _parse_iso("2026-05-18T20:30:00-04:00") == "2026-05-19T00:30:00+00:00"
    assert _parse_iso("") is None
    assert _parse_iso("nan") is None
    assert _parse_iso(None) is None


def test_infer_playoff_from_game_id_prefix() -> None:
    assert _infer_playoff("0042500301", None) is True
    assert _infer_playoff("0022500123", None) is False


def test_infer_playoff_from_series_text() -> None:
    assert _infer_playoff("0022500123", "Eastern Conference Finals") is True
    assert _infer_playoff("0022500123", "First Round - Game 3") is True
    assert _infer_playoff("0022500123", "Regular Season Game") is False


def test_infer_playoff_round_maps_known_phrases() -> None:
    assert _infer_playoff_round("First Round") == 1
    assert _infer_playoff_round("Round 1 - Game 5") == 1
    assert _infer_playoff_round("Conference Semifinals") == 2
    assert _infer_playoff_round("Eastern Conference Finals") == 3
    assert _infer_playoff_round("NBA Finals") == 4
    assert _infer_playoff_round("Finals") == 4
    assert _infer_playoff_round(None) is None
    assert _infer_playoff_round("Neutral Site") is None


def test_first_broadcaster_finds_first_non_nan() -> None:
    row = pd.Series(
        {
            "nationalBroadcasters_0_broadcasterDisplay": float("nan"),
            "nationalBroadcasters_1_broadcasterDisplay": "TNT",
            "nationalBroadcasters_2_broadcasterDisplay": "ESPN",
        }
    )
    assert _first_broadcaster(row) == "TNT"


def test_first_broadcaster_none_when_all_missing() -> None:
    row = pd.Series({"nationalBroadcasters_0_broadcasterDisplay": None})
    assert _first_broadcaster(row) is None


def test_map_schedule_row_extracts_full_game() -> None:
    row = pd.Series(
        {
            "gameId": "0042500401",
            "gameStatus": 1,
            "gameDateTimeUTC": "2026-05-22T01:30:00Z",
            "gameDateEst": "2026-05-21T00:00:00",
            "homeTeam_teamTricode": "OKC",
            "awayTeam_teamTricode": "MIN",
            "homeTeam_score": 0,
            "awayTeam_score": 0,
            "arenaName": "Paycom Center",
            "seriesText": "Conference Finals - Game 1",
            "nationalBroadcasters_0_broadcasterDisplay": "TNT",
        }
    )
    snap = _map_schedule_row(row, season="2025-26")
    assert snap is not None
    assert snap.game_id == "0042500401"
    assert snap.status == "scheduled"
    assert snap.home_abbr == "OKC"
    assert snap.away_abbr == "MIN"
    assert snap.tipoff_utc == "2026-05-22T01:30:00+00:00"
    assert snap.date == "2026-05-22"  # derived from UTC tipoff
    assert snap.arena_name == "Paycom Center"
    assert snap.is_playoff is True
    assert snap.playoff_round == 3
    assert snap.playoff_series == "Conference Finals - Game 1"
    assert snap.broadcast == "TNT"


def test_map_schedule_row_returns_none_when_teams_missing() -> None:
    row = pd.Series(
        {
            "gameId": "0042500401",
            "gameStatus": 1,
            "homeTeam_teamTricode": "",
            "awayTeam_teamTricode": "",
        }
    )
    assert _map_schedule_row(row, season="2025-26") is None
