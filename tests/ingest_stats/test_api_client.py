"""Tests for the nba_api rate limiter and client wrapper."""

from __future__ import annotations

import time

from src.ingest_stats.api_client import DEFAULT_HEADERS, RateLimiter


def test_rate_limiter_respects_min_interval() -> None:
    limiter = RateLimiter(min_interval_seconds=0.2)
    start = time.monotonic()
    limiter.wait()  # first call returns immediately
    limiter.wait()  # second must wait at least 0.2s after the first
    limiter.wait()  # third must wait at least 0.2s after the second
    elapsed = time.monotonic() - start
    assert elapsed >= 0.4, f"expected >=0.4s for two delays, got {elapsed:.3f}s"


def test_rate_limiter_no_delay_when_interval_elapsed() -> None:
    limiter = RateLimiter(min_interval_seconds=0.05)
    limiter.wait()
    time.sleep(0.1)
    start = time.monotonic()
    limiter.wait()
    elapsed = time.monotonic() - start
    assert elapsed < 0.02, "should not delay when interval already elapsed"


def test_default_headers_include_stats_nba_origin() -> None:
    assert DEFAULT_HEADERS["x-nba-stats-origin"] == "stats"
    assert DEFAULT_HEADERS["x-nba-stats-token"] == "true"
    assert "User-Agent" in DEFAULT_HEADERS
    assert "Referer" in DEFAULT_HEADERS
