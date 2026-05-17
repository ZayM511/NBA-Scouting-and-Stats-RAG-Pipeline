"""Unit tests for the pure-function helpers in live.py."""

from __future__ import annotations

import pandas as pd

from src.ingest_stats.live import (
    STATUS_BY_ID,
    _clean_clock,
    _infer_season,
    _infer_season_type,
    _map_header_row,
    _parse_tipoff_utc,
    _safe_int,
    _season_string,
)


def test_status_map_covers_known_codes() -> None:
    assert STATUS_BY_ID[1] == "scheduled"
    assert STATUS_BY_ID[2] == "live"
    assert STATUS_BY_ID[3] == "final"
    assert STATUS_BY_ID[4] == "postponed"


def test_safe_int_handles_junk() -> None:
    assert _safe_int(None) is None
    assert _safe_int("") is None
    assert _safe_int("nope") is None
    assert _safe_int("42") == 42
    assert _safe_int(7) == 7


def test_season_string_formats_year() -> None:
    assert _season_string(2025) == "2025-26"
    assert _season_string(1999) == "1999-00"


def test_infer_season_uses_october_boundary() -> None:
    assert _infer_season("2026-05-17") == "2025-26"  # May → previous-year start
    assert _infer_season("2026-11-03") == "2026-27"  # November → current year
    assert _infer_season("") == "2025-26"            # default fallback


def test_infer_season_type_from_game_id_prefix() -> None:
    assert _infer_season_type("0022500123") == "Regular Season"
    assert _infer_season_type("0042500301") == "Playoffs"
    assert _infer_season_type("0052500001") == "Play-In"
    assert _infer_season_type("0012500001") == "Preseason"


def test_clean_clock_blank_when_not_live() -> None:
    assert _clean_clock("PT06M42.00S", "scheduled") is None
    assert _clean_clock("PT06M42.00S", "final") is None
    assert _clean_clock("PT06M42.00S", "live") == "PT06M42.00S"
    assert _clean_clock("   ", "live") is None


def test_parse_tipoff_utc_strips_zulu_and_assumes_utc() -> None:
    assert _parse_tipoff_utc("2026-05-17T20:30:00Z") == "2026-05-17T20:30:00+00:00"
    # ScoreboardV2 returns plain ISO without TZ; treat as UTC midnight.
    assert _parse_tipoff_utc("2026-05-17T00:00:00") == "2026-05-17T00:00:00+00:00"
    assert _parse_tipoff_utc(None) is None
    assert _parse_tipoff_utc("not-a-date") is None


def test_map_header_row_extracts_core_fields() -> None:
    header_row = pd.Series(
        {
            "GAME_ID": "0042500301",
            "HOME_TEAM_ID": 1610612747,
            "VISITOR_TEAM_ID": 1610612760,
            "GAME_STATUS_ID": 2,
            "GAME_STATUS_TEXT": "Q3 6:42",
            "LIVE_PERIOD": 3,
            "LIVE_PC_TIME": "6:42",
            "GAME_DATE_EST": "2026-05-17T00:00:00",
            "SEASON": "2025",
            "ARENA_NAME": "Crypto.com Arena",
            "NATL_TV_BROADCASTER_ABBREVIATION": "ESPN",
        }
    )
    line_lookup = {
        ("0042500301", 1610612747): {"abbr": "LAL", "score": 72},
        ("0042500301", 1610612760): {"abbr": "OKC", "score": 69},
    }

    snap = _map_header_row(header_row, line_lookup)
    assert snap is not None
    assert snap.game_id == "0042500301"
    assert snap.status == "live"
    assert snap.period == 3
    assert snap.game_clock == "6:42"
    assert snap.home_abbr == "LAL"
    assert snap.away_abbr == "OKC"
    assert snap.home_score == 72
    assert snap.away_score == 69
    assert snap.arena_name == "Crypto.com Arena"
    assert snap.broadcast == "ESPN"
    assert snap.is_playoff is True
    assert snap.tipoff_utc and snap.tipoff_utc.startswith("2026-05-17")


def test_map_header_row_drops_period_when_scheduled() -> None:
    header_row = pd.Series(
        {
            "GAME_ID": "0022500999",
            "HOME_TEAM_ID": 1610612752,
            "VISITOR_TEAM_ID": 1610612755,
            "GAME_STATUS_ID": 1,
            "LIVE_PERIOD": 0,
            "LIVE_PC_TIME": "     ",
            "GAME_DATE_EST": "2026-05-20T00:00:00",
            "SEASON": "2025",
            "ARENA_NAME": "Madison Square Garden",
        }
    )
    line_lookup = {
        ("0022500999", 1610612752): {"abbr": "NYK", "score": None},
        ("0022500999", 1610612755): {"abbr": "PHI", "score": None},
    }
    snap = _map_header_row(header_row, line_lookup)
    assert snap is not None
    assert snap.status == "scheduled"
    assert snap.period is None
    assert snap.game_clock is None
    assert snap.home_score is None
    assert snap.is_playoff is False
