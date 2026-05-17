"""Unit tests for the balldontlie adapter parsers.

The HTTP layer is not exercised — those tests would need a key + network.
Here we only verify the parser maps balldontlie rows into the shared
GameSnapshot shape correctly so the fallback path is interchangeable with
the nba_api primary path.
"""

from __future__ import annotations

from src.ingest_stats.balldontlie import (
    GameSnapshot,
    _map_status,
    _parse_one,
    _parse_tipoff,
    _safe_int,
    _season_string,
)


def test_safe_int_handles_blanks() -> None:
    assert _safe_int(None) is None
    assert _safe_int("") is None
    assert _safe_int("xx") is None
    assert _safe_int("7") == 7
    assert _safe_int(7.9) == 7


def test_season_string_uses_starting_year() -> None:
    assert _season_string(2025) == "2025-26"
    assert _season_string(0) == ""


def test_map_status_handles_known_strings() -> None:
    assert _map_status("Final", 4) == "final"
    assert _map_status("Final/OT", 5) == "final"
    assert _map_status("Postponed", 0) == "postponed"
    assert _map_status("Q3 6:42", 3) == "live"
    assert _map_status("", 0) == "scheduled"
    # ISO datetime as status string → scheduled
    assert _map_status("2026-05-22T20:30:00Z", 0) == "scheduled"


def test_parse_tipoff_uses_status_when_iso_like() -> None:
    out = _parse_tipoff("2026-05-22", "2026-05-22T20:30:00Z")
    assert out == "2026-05-22T20:30:00+00:00"


def test_parse_tipoff_falls_back_to_date_field() -> None:
    # Status is "Final" (not an ISO); use date field (midnight UTC).
    out = _parse_tipoff("2026-05-22", "Final")
    assert out == "2026-05-22T00:00:00+00:00"


def test_parse_one_full_scheduled_game() -> None:
    raw = {
        "id": 1234,
        "date": "2026-05-22T20:30:00Z",
        "season": 2025,
        "status": "2026-05-22T20:30:00Z",  # ISO until tipoff
        "period": 0,
        "time": "",
        "home_team_score": 0,
        "visitor_team_score": 0,
        "postseason": True,
        "home_team": {"abbreviation": "OKC"},
        "visitor_team": {"abbreviation": "MIN"},
    }
    snap = _parse_one(raw)
    assert snap is not None
    assert isinstance(snap, GameSnapshot)
    assert snap.game_id == "bdl_2026-05-22_OKC_MIN"
    assert snap.status == "scheduled"
    assert snap.home_abbr == "OKC"
    assert snap.away_abbr == "MIN"
    assert snap.season == "2025-26"
    assert snap.season_type == "Playoffs"
    assert snap.tipoff_utc == "2026-05-22T20:30:00+00:00"
    assert snap.is_playoff is True


def test_parse_one_live_game_extracts_period_and_clock() -> None:
    raw = {
        "id": 1235,
        "date": "2026-05-22T20:30:00Z",
        "season": 2025,
        "status": "Q3 6:42",
        "period": 3,
        "time": "6:42",
        "home_team_score": 72,
        "visitor_team_score": 69,
        "postseason": True,
        "home_team": {"abbreviation": "OKC"},
        "visitor_team": {"abbreviation": "MIN"},
    }
    snap = _parse_one(raw)
    assert snap is not None
    assert snap.status == "live"
    assert snap.period == 3
    assert snap.game_clock == "6:42"
    assert snap.home_score == 72
    assert snap.away_score == 69


def test_parse_one_drops_rows_missing_team_abbr() -> None:
    raw = {
        "date": "2026-05-22T20:30:00Z",
        "home_team": {"abbreviation": ""},
        "visitor_team": {"abbreviation": "MIN"},
    }
    assert _parse_one(raw) is None
