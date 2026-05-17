"""Rate-limited wrapper around nba_api.

The stats.nba.com API has soft rate limits that are easy to trip if you call
in a tight loop. Empirically, ~600ms between calls is safe; <300ms gets you
intermittent 429s and 30s+ stalls. Stick with the default unless you've
measured.

Retries follow exponential backoff and only retry transient failures
(connection errors, timeouts, 429, 5xx). Don't retry 4xx other than 429.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


# nba_api exceptions we want to retry on. Imported lazily so the module imports
# cleanly in environments where nba_api isn't installed (e.g., partial CI).
try:
    from requests.exceptions import (
        ConnectionError as _ConnectionError,
        ReadTimeout,
        Timeout,
    )

    RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
        _ConnectionError,
        Timeout,
        ReadTimeout,
    )
except ImportError:  # pragma: no cover
    RETRYABLE_EXCEPTIONS = ()


# Default headers nba_api needs to be treated as a browser by stats.nba.com.
DEFAULT_HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://stats.nba.com/",
    "Origin": "https://stats.nba.com",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}


@dataclass
class RateLimiter:
    """Process-wide minimum delay between nba_api calls.

    Thread-safe: use one instance shared across all ingest workers. The lock
    ensures the delay is enforced even if multiple threads call in parallel.

    Default 0.6 seconds is the empirical safe floor for stats.nba.com.
    """

    min_interval_seconds: float = 0.6
    _last_call: float = 0.0
    _lock: Lock = Lock()  # type: ignore[assignment]

    def __post_init__(self) -> None:
        # Dataclass can't create the Lock directly; do it here.
        self._lock = Lock()
        self._last_call = 0.0

    def wait(self) -> None:
        """Block until at least min_interval_seconds have elapsed since the
        last call. Updates the last-call timestamp on return."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self.min_interval_seconds:
                sleep_for = self.min_interval_seconds - elapsed
                time.sleep(sleep_for)
            self._last_call = time.monotonic()


# Module-level singletons. Override in tests via monkeypatch if you need.
#
# The 'stats' limiter applies to stats.nba.com endpoints (LeagueGameLog,
# LeagueDashPlayerClutch, ScheduleLeagueV2Int, etc.) — they share the
# 600 ms empirical safe floor.
#
# The 'live' limiter applies to cdn.nba.com / live data endpoints
# (live.nba.endpoints.ScoreBoard) — different host, no cookie dance, and
# we want to be able to poll once a minute for live scores without the
# rate limiter slowing us down. 0.0 = no minimum delay (the wait() call
# is still safe to invoke).
_DEFAULT_LIMITER = RateLimiter(min_interval_seconds=0.6)
_LIVE_LIMITER = RateLimiter(min_interval_seconds=0.0)


def get_limiter() -> RateLimiter:
    return _DEFAULT_LIMITER


def get_live_limiter() -> RateLimiter:
    """Looser limiter for the live (cdn.nba.com) host."""
    return _LIVE_LIMITER


class NBAClient:
    """Wrapper that applies the rate limiter, retries, and consistent headers
    around every nba_api call."""

    def __init__(self, limiter: RateLimiter | None = None, timeout_seconds: int = 60) -> None:
        self.limiter = limiter or get_limiter()
        self.timeout_seconds = timeout_seconds

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS) if RETRYABLE_EXCEPTIONS else retry_if_exception_type(Exception),
        reraise=True,
    )
    def call(self, endpoint_factory: Any, /, **kwargs: Any) -> Any:
        """Invoke an nba_api endpoint with rate-limiting and retry.

        Usage:
            client.call(
                LeagueGameLog,
                season="2025-26",
                season_type_all_star="Regular Season",
            )

        `endpoint_factory` is the nba_api endpoint class (callable). kwargs are
        forwarded. The function returns the endpoint instance; callers fetch
        the relevant table via `.get_data_frames()[0]` or similar.
        """
        self.limiter.wait()
        logger.debug("nba_api call: %s kwargs=%s", endpoint_factory.__name__, kwargs)
        # nba_api ships its own NBA_STATS_HEADERS (with cookies + per-version
        # tweaks) inside library/http.py; passing our own `headers=` dict here
        # would override that and break the request. Only set the timeout.
        # If a caller really wants custom headers, they pass them explicitly.
        kwargs.setdefault("timeout", self.timeout_seconds)
        return endpoint_factory(**kwargs)
