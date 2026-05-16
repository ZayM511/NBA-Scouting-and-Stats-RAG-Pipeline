"""Unit tests for the pure-function helpers in player_game_stats.py."""

from __future__ import annotations

import math

from src.ingest_stats.player_game_stats import _safe_float, _safe_int, _ts_pct


def test_safe_int_handles_none_and_empty() -> None:
    assert _safe_int(None) is None
    assert _safe_int("") is None
    assert _safe_int("not a number") is None


def test_safe_int_converts_numerics() -> None:
    assert _safe_int(42) == 42
    assert _safe_int("42") == 42
    assert _safe_int(42.7) == 42


def test_safe_float_handles_none_and_empty() -> None:
    assert _safe_float(None) is None
    assert _safe_float("") is None
    assert _safe_float("xyz") is None


def test_safe_float_converts_numerics() -> None:
    assert _safe_float(0.523) == 0.523
    assert _safe_float("0.523") == 0.523


def test_ts_pct_handles_zero_attempts() -> None:
    # No shots taken at all: TS% should be None, not raise.
    assert _ts_pct(0, 0, 0) is None


def test_ts_pct_propagates_none() -> None:
    assert _ts_pct(None, 10, 4) is None
    assert _ts_pct(20, None, 4) is None
    assert _ts_pct(20, 10, None) is None


def test_ts_pct_known_value() -> None:
    # Curry-ish line: 30 pts on 20 FGA and 5 FTA.
    # TS = 30 / (2 * (20 + 0.44 * 5)) = 30 / (2 * 22.2) = 30 / 44.4 = 0.6757
    result = _ts_pct(30, 20, 5)
    assert result is not None
    assert math.isclose(result, 0.6757, abs_tol=0.001)
