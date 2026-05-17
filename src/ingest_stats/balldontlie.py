"""balldontlie.io fallback adapter.

Used when nba_api fails (network, rate limit, schema drift). Returns the
same GameSnapshot shape the nba_api path produces, so live.py and
schedule.py can call the fallback transparently.

balldontlie's free tier allows 60 req/min, no API key required for these
public endpoints. The adapter is intentionally thin: GET, map, return.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)


BASE_URL = "https://api.balldontlie.io/v1"
TIMEOUT_SECONDS = 10


# Status codes used across both sources.
STATUS_SCHEDULED = "scheduled"
STATUS_LIVE = "live"
STATUS_FINAL = "final"
STATUS_POSTPONED = "postponed"


@dataclass(frozen=True)
class GameSnapshot:
    """Shared shape produced by both the nba_api and balldontlie ingest
    paths. Maps cleanly into the games table.

    `game_id` is the canonical nba_api id when sourced from nba_api
    (e.g. "0042500301"), or a synthetic "bdl_YYYY-MM-DD_HOME_AWAY" when
    sourced from balldontlie. The live ingester is expected to prefer
    matching to an existing game_id by (date, home_abbr, away_abbr)
    before inserting a synthetic row, so the bdl_ prefix is only used
    when no canonical row exists yet.
    """

    game_id: str
    date: str  # ISO date, e.g. "2026-05-18"
    season: str  # e.g. "2025-26"
    season_type: str  # "Regular Season" or "Playoffs"
    home_abbr: str
    away_abbr: str
    home_score: int | None
    away_score: int | None
    status: str  # scheduled | live | final | postponed
    period: int | None
    game_clock: str | None
    tipoff_utc: str | None  # ISO datetime
    arena_name: str | None = None
    broadcast: str | None = None
    is_playoff: bool = False
    playoff_round: int | None = None
    playoff_series: str | None = None


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def get_live_games(today: str | None = None) -> list[GameSnapshot]:
    """Fetch today's games (any status). `today` defaults to UTC today."""
    if today is None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    raw = _get("/games", params={"dates[]": today, "per_page": 100})
    return _parse_games(raw.get("data") or [])


def get_upcoming_games(
    start_date: str,
    end_date: str,
) -> list[GameSnapshot]:
    """Fetch games between two ISO dates (inclusive). Useful for schedule
    backfill when ScheduleLeagueV2Int is unreachable."""
    raw = _get(
        "/games",
        params={"start_date": start_date, "end_date": end_date, "per_page": 100},
    )
    return _parse_games(raw.get("data") or [])


# --------------------------------------------------------------------------- #
# HTTP + parsing
# --------------------------------------------------------------------------- #


def _get(path: str, *, params: dict[str, Any]) -> dict[str, Any]:
    url = f"{BASE_URL}{path}"
    logger.debug("balldontlie GET %s params=%s", url, params)
    resp = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json()


def _parse_games(rows: list[dict[str, Any]]) -> list[GameSnapshot]:
    return [s for r in rows if (s := _parse_one(r)) is not None]


def _parse_one(row: dict[str, Any]) -> GameSnapshot | None:
    """Map one balldontlie game dict to GameSnapshot. Returns None on
    malformed rows so a single bad record doesn't kill the whole batch."""
    try:
        home = row.get("home_team") or {}
        away = row.get("visitor_team") or {}
        home_abbr = str(home.get("abbreviation") or "").upper()
        away_abbr = str(away.get("abbreviation") or "").upper()
        date_str = str(row.get("date") or "")[:10]
        if not (home_abbr and away_abbr and date_str):
            return None

        status_raw = str(row.get("status") or "").strip()
        period = row.get("period")
        status = _map_status(status_raw, period)
        season_year = int(row.get("season") or 0)
        season = _season_string(season_year)
        is_playoff = bool(row.get("postseason"))
        season_type = "Playoffs" if is_playoff else "Regular Season"

        return GameSnapshot(
            game_id=f"bdl_{date_str}_{home_abbr}_{away_abbr}",
            date=date_str,
            season=season,
            season_type=season_type,
            home_abbr=home_abbr,
            away_abbr=away_abbr,
            home_score=_safe_int(row.get("home_team_score")),
            away_score=_safe_int(row.get("visitor_team_score")),
            status=status,
            period=_safe_int(period),
            game_clock=str(row.get("time") or "") or None,
            tipoff_utc=_parse_tipoff(row.get("date"), row.get("status")),
            is_playoff=is_playoff,
        )
    except Exception:  # noqa: BLE001
        logger.exception("balldontlie: failed to parse row %r", row)
        return None


def _map_status(status_raw: str, period: Any) -> str:
    """Map balldontlie's free-form status string to our enum.

    Observed values: ISO datetime (scheduled), "Final", "Q1 10:23",
    "Halftime", "Final/OT", "Postponed".
    """
    s = status_raw.lower()
    if not s:
        return STATUS_SCHEDULED
    if "final" in s:
        return STATUS_FINAL
    if "postponed" in s or "cancelled" in s:
        return STATUS_POSTPONED
    # Anything with a period > 0 or a quarter prefix is live.
    if isinstance(period, int) and period > 0:
        return STATUS_LIVE
    if any(s.startswith(p) for p in ("q1", "q2", "q3", "q4", "ot", "halftime", "half")):
        return STATUS_LIVE
    # Default: an ISO datetime-looking string means the game hasn't started.
    return STATUS_SCHEDULED


def _parse_tipoff(date_val: Any, status_val: Any) -> str | None:
    """balldontlie's `date` field is a UTC midnight string for completed games
    and a full ISO datetime for scheduled ones. Use the latter when present."""
    if isinstance(status_val, str):
        try:
            dt = datetime.fromisoformat(status_val.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).isoformat()
        except (ValueError, AttributeError):
            pass
    if isinstance(date_val, str):
        try:
            dt = datetime.fromisoformat(date_val.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            pass
    return None


def _safe_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _season_string(year: int) -> str:
    """balldontlie reports the starting year (2025 → 2025-26 season)."""
    if year <= 0:
        return ""
    return f"{year}-{(year + 1) % 100:02d}"
