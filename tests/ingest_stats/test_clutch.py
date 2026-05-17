"""Unit tests for the pure-function helpers in clutch.py."""

from __future__ import annotations

import math

from src.ingest_stats.clutch import _efg_pct, _row_from_endpoint, _ts_pct


def test_ts_pct_zero_attempts_returns_none() -> None:
    assert _ts_pct(0, 0, 0) is None


def test_ts_pct_known_value() -> None:
    # 30 pts on 20 FGA, 5 FTA → 30 / (2 * 22.2) = 0.6757
    result = _ts_pct(30, 20, 5)
    assert result is not None
    assert math.isclose(result, 0.6757, abs_tol=0.001)


def test_efg_pct_zero_fga_returns_none() -> None:
    assert _efg_pct(0, 0, 0) is None


def test_efg_pct_weights_threes() -> None:
    # 5 makes, 2 threes, 10 attempts → (5 + 1.0) / 10 = 0.6
    result = _efg_pct(5, 2, 10)
    assert result is not None
    assert math.isclose(result, 0.6, abs_tol=0.001)


def test_row_from_endpoint_maps_uppercase_keys() -> None:
    sample = {
        "PLAYER_ID": 1628983,
        "GP": 27,
        "MIN": 125.14,
        "PTS": 175,
        "FGM": 50,
        "FGA": 101,
        "FG3M": 10,
        "FG3A": 30,
        "FTM": 65,
        "FTA": 68,
        "OREB": 1,
        "DREB": 25,
        "REB": 26,
        "AST": 31,
        "TOV": 17,
        "STL": 12,
        "BLK": 5,
        "PF": 22,
        "PFD": 30,
        "PLUS_MINUS": 100,
    }
    row = _row_from_endpoint(sample, season="2025-26", season_type="Regular Season")
    assert row["player_id"] == 1628983
    assert row["season"] == "2025-26"
    assert row["season_type"] == "Regular Season"
    assert row["gp"] == 27
    assert row["pts"] == 175
    assert row["fga"] == 101
    assert row["fta"] == 68
    # 175 / (2 * (101 + 0.44 * 68)) = 175 / 261.84 = 0.6684
    assert row["ts_pct"] is not None
    assert math.isclose(row["ts_pct"], 0.6684, abs_tol=0.001)
    # (50 + 0.5 * 10) / 101 = 55 / 101 = 0.5446
    assert row["efg_pct"] is not None
    assert math.isclose(row["efg_pct"], 0.5446, abs_tol=0.001)


def test_row_from_endpoint_handles_missing_optional_fields() -> None:
    """Endpoint sometimes returns None for stats; we coerce to 0."""
    sample = {
        "PLAYER_ID": 999,
        "GP": 0,
        "MIN": None,
        "PTS": None,
        "FGM": None,
        "FGA": None,
        "FG3M": None,
        "FG3A": None,
        "FTM": None,
        "FTA": None,
    }
    row = _row_from_endpoint(sample, season="2025-26", season_type="Playoffs")
    assert row["pts"] == 0
    assert row["fga"] == 0
    # All zeros → TS% and eFG% should be None (undefined), not raise.
    assert row["ts_pct"] is None
    assert row["efg_pct"] is None
