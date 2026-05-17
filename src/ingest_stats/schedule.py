"""Upcoming-schedule ingester.

Pulls the full 2025-26 schedule from stats.nba.com `ScheduleLeagueV2Int`
and UPSERTs future-game rows into the games table with accurate
tipoff_utc, arena_name, and broadcast info.

The endpoint returns the entire season (~1300 games). We only persist
games that are scheduled (status=1) or live (status=2) — final games are
loaded by the existing `sync_games()` daily refresh via LeagueGameLog and
shouldn't be touched here.

Fallback to balldontlie.io requires BALLDONTLIE_API_KEY in env.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from src.ingest_stats.api_client import NBAClient
from src.ingest_stats.balldontlie import GameSnapshot, get_upcoming_games as bdl_upcoming
from src.ingest_stats.db import connect, write_audit
from src.ingest_stats.live import STATUS_BY_ID, _UPSERT_SQL

logger = logging.getLogger(__name__)


def sync_upcoming_schedule(
    season: str = "2025-26",
    days_ahead: int = 14,
) -> int:
    """Pull the season schedule, keep games within `days_ahead`, UPSERT them.

    Returns count of rows written. Idempotent — re-running updates
    tipoff_utc / arena_name if the league moved a game.
    """
    today = datetime.now(timezone.utc).date()
    horizon = today + timedelta(days=days_ahead)

    snapshots: list[GameSnapshot] = []
    try:
        snapshots = _from_stats_nba(season, today, horizon)
        logger.info(
            "schedule: stats.nba.com returned %d upcoming games (next %d days)",
            len(snapshots), days_ahead,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("schedule: stats.nba.com failed (%s); trying fallback", type(exc).__name__)
        snapshots = _try_fallback(today, horizon)

    if not snapshots:
        with connect() as conn:
            write_audit(
                conn,
                source="upcoming_schedule",
                url=None,
                content_sha256=None,
                chunk_count=0,
                status="empty",
            )
        return 0

    return _upsert_games(snapshots)


# --------------------------------------------------------------------------- #
# Primary path: stats.nba.com ScheduleLeagueV2Int
# --------------------------------------------------------------------------- #


def _from_stats_nba(season: str, start: date, end: date) -> list[GameSnapshot]:
    from nba_api.stats.endpoints import scheduleleaguev2int

    client = NBAClient()
    ep = client.call(scheduleleaguev2int.ScheduleLeagueV2Int, season=season)
    dfs = ep.get_data_frames()
    if not dfs:
        return []

    df = dfs[0]
    snapshots: list[GameSnapshot] = []
    for _, row in df.iterrows():
        snap = _map_schedule_row(row, season)
        if snap is None:
            continue
        # Filter to active games within the horizon.
        if snap.status == "final":
            continue
        try:
            game_date = date.fromisoformat(snap.date) if snap.date else None
        except ValueError:
            game_date = None
        if game_date and (game_date < start or game_date > end):
            continue
        snapshots.append(snap)
    return snapshots


def _map_schedule_row(row: Any, season: str) -> GameSnapshot | None:
    game_id = str(row.get("gameId") or "")
    if not game_id:
        return None

    status_id = _safe_int(row.get("gameStatus")) or 1
    status = STATUS_BY_ID.get(status_id, "scheduled")

    home_abbr = str(row.get("homeTeam_teamTricode") or "")
    away_abbr = str(row.get("awayTeam_teamTricode") or "")
    if not (home_abbr and away_abbr):
        return None

    # Prefer gameDateTimeUTC (full ISO with tz); fall back to gameDateUTC.
    tipoff_utc = _parse_iso(row.get("gameDateTimeUTC")) or _parse_iso(row.get("gameDateUTC"))
    date_str = (tipoff_utc[:10] if tipoff_utc else str(row.get("gameDateEst") or "")[:10])

    series_text = str(row.get("seriesText") or "").strip() or None
    is_playoff = _infer_playoff(game_id, series_text)
    playoff_round = _infer_playoff_round(series_text) if is_playoff else None
    season_type = (
        "Playoffs" if is_playoff
        else "Play-In" if game_id.startswith("005")
        else "Preseason" if game_id.startswith("001")
        else "Regular Season"
    )

    arena_name = str(row.get("arenaName") or "").strip() or None
    broadcast = _first_broadcaster(row)

    return GameSnapshot(
        game_id=game_id,
        date=date_str,
        season=season,
        season_type=season_type,
        home_abbr=home_abbr,
        away_abbr=away_abbr,
        home_score=_safe_int(row.get("homeTeam_score")) or None,
        away_score=_safe_int(row.get("awayTeam_score")) or None,
        status=status,
        period=None,  # scheduled games have no clock state
        game_clock=None,
        tipoff_utc=tipoff_utc,
        arena_name=arena_name,
        broadcast=broadcast,
        is_playoff=is_playoff,
        playoff_round=playoff_round,
        playoff_series=series_text,
    )


def _first_broadcaster(row: Any) -> str | None:
    """Find a national TV broadcaster from the row's broadcaster columns."""
    for i in range(0, 5):
        key = f"nationalBroadcasters_{i}_broadcasterDisplay"
        v = row.get(key)
        if v and str(v) not in ("nan", "None"):
            return str(v)
    return None


def _parse_iso(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def _safe_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _infer_playoff(game_id: str, series_text: str | None) -> bool:
    if game_id.startswith("004"):
        return True
    if series_text and any(s in series_text.lower() for s in ("round", "finals", "conference")):
        return True
    return False


_PLAYOFF_ROUND_HINTS = (
    ("first round", 1), ("round 1", 1), ("r1", 1),
    ("conference semi", 2), ("round 2", 2),
    ("conference finals", 3), ("conf finals", 3),
    ("nba finals", 4), ("finals", 4),
)


def _infer_playoff_round(series_text: str | None) -> int | None:
    if not series_text:
        return None
    s = series_text.lower()
    for hint, rnd in _PLAYOFF_ROUND_HINTS:
        if hint in s:
            return rnd
    return None


# --------------------------------------------------------------------------- #
# Fallback
# --------------------------------------------------------------------------- #


def _try_fallback(start: date, end: date) -> list[GameSnapshot]:
    if not os.environ.get("BALLDONTLIE_API_KEY"):
        logger.warning(
            "schedule: BALLDONTLIE_API_KEY not set; skipping fallback "
            "(free signup at balldontlie.io)"
        )
        return []
    try:
        snaps = bdl_upcoming(start.isoformat(), end.isoformat())
        logger.info("schedule: balldontlie returned %d games", len(snaps))
        # balldontlie also returns finals in date range; drop them
        return [s for s in snaps if s.status != "final"]
    except Exception as exc:  # noqa: BLE001
        logger.exception("schedule: balldontlie fallback failed: %s", exc)
        return []


# --------------------------------------------------------------------------- #
# DB writer (reuses live.py's UPSERT SQL)
# --------------------------------------------------------------------------- #


def _upsert_games(snaps: list[GameSnapshot]) -> int:
    if not snaps:
        return 0
    rows = [
        {
            "game_id": s.game_id,
            "date": s.date or None,
            "season": s.season or "2025-26",
            "season_type": s.season_type,
            "home_team": s.home_abbr,
            "away_team": s.away_abbr,
            "home_score": s.home_score,
            "away_score": s.away_score,
            "status": s.status,
            "period": s.period,
            "game_clock": s.game_clock,
            "tipoff_utc": s.tipoff_utc,
            "arena_name": s.arena_name,
            "broadcast": s.broadcast,
            "is_playoff": s.is_playoff,
            "playoff_round": s.playoff_round,
            "playoff_series": s.playoff_series,
        }
        for s in snaps
    ]
    with connect() as conn:
        with conn.cursor() as cur:
            cur.executemany(_UPSERT_SQL, rows)
        conn.commit()
        write_audit(
            conn,
            source="upcoming_schedule",
            url=None,
            content_sha256=None,
            chunk_count=len(rows),
            status="success",
        )
    return len(rows)
