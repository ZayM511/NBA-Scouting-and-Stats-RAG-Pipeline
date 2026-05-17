"""Live game scoreboard ingester.

Pulls today's games from stats.nba.com `ScoreboardV2` (status, period,
clock, scores) and UPSERTs them into the games table. Designed to be
called every 60 seconds by the APScheduler job in the FastAPI lifespan.

Falls back to balldontlie.io when stats.nba.com is unreachable, but only
if BALLDONTLIE_API_KEY is set in the environment (free signup at
balldontlie.io). Without the key the fallback is a no-op and the call
just logs a warning.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from typing import Any

from src.ingest_stats.api_client import NBAClient
from src.ingest_stats.balldontlie import GameSnapshot, get_live_games as bdl_live
from src.ingest_stats.db import connect, write_audit

logger = logging.getLogger(__name__)


# Map stats.nba.com GAME_STATUS_ID values to our status enum.
# 1 = scheduled, 2 = live (in progress), 3 = final, 4 = postponed (rare)
STATUS_BY_ID: dict[int, str] = {
    1: "scheduled",
    2: "live",
    3: "final",
    4: "postponed",
}


_UPSERT_SQL = """
INSERT INTO games (
    game_id, date, season, season_type, home_team, away_team,
    home_score, away_score, status, period, game_clock,
    tipoff_utc, arena_name, broadcast,
    is_playoff, playoff_round, playoff_series,
    refreshed_at
) VALUES (
    %(game_id)s, %(date)s, %(season)s, %(season_type)s,
    %(home_team)s, %(away_team)s,
    %(home_score)s, %(away_score)s, %(status)s, %(period)s, %(game_clock)s,
    %(tipoff_utc)s, %(arena_name)s, %(broadcast)s,
    %(is_playoff)s, %(playoff_round)s, %(playoff_series)s,
    NOW()
)
ON CONFLICT (game_id) DO UPDATE SET
    home_score     = COALESCE(EXCLUDED.home_score,  games.home_score),
    away_score     = COALESCE(EXCLUDED.away_score,  games.away_score),
    status         = EXCLUDED.status,
    period         = EXCLUDED.period,
    game_clock     = EXCLUDED.game_clock,
    tipoff_utc     = COALESCE(EXCLUDED.tipoff_utc,    games.tipoff_utc),
    arena_name     = COALESCE(EXCLUDED.arena_name,    games.arena_name),
    broadcast      = COALESCE(EXCLUDED.broadcast,     games.broadcast),
    is_playoff     = games.is_playoff OR EXCLUDED.is_playoff,
    playoff_round  = COALESCE(EXCLUDED.playoff_round, games.playoff_round),
    playoff_series = COALESCE(EXCLUDED.playoff_series, games.playoff_series),
    updated_at     = NOW(),
    refreshed_at   = NOW();
"""


def sync_live_scoreboard(today: date | None = None) -> int:
    """Pull today's scoreboard and UPSERT each game. Returns the count.

    Tries stats.nba.com ScoreboardV2 first. If that raises, falls back to
    balldontlie.io (when BALLDONTLIE_API_KEY is set). On total failure
    logs an error and returns 0 — the API stays up either way.
    """
    if today is None:
        today = datetime.now(timezone.utc).date()

    snapshots: list[GameSnapshot] = []
    try:
        snapshots = _from_stats_nba(today)
        logger.info("live: stats.nba.com returned %d games for %s", len(snapshots), today)
    except Exception as exc:  # noqa: BLE001
        logger.warning("live: stats.nba.com failed (%s); trying fallback", type(exc).__name__)
        snapshots = _try_fallback(today)

    if not snapshots:
        with connect() as conn:
            write_audit(
                conn,
                source="live_scoreboard",
                url=None,
                content_sha256=None,
                chunk_count=0,
                status="empty",
            )
        return 0

    return _upsert_games(snapshots)


# --------------------------------------------------------------------------- #
# Primary path: stats.nba.com ScoreboardV2
# --------------------------------------------------------------------------- #


def _from_stats_nba(today: date) -> list[GameSnapshot]:
    """Call ScoreboardV2 for the given date and map results to GameSnapshot."""
    from nba_api.stats.endpoints import scoreboardv2

    client = NBAClient()
    ep = client.call(
        scoreboardv2.ScoreboardV2,
        game_date=today.isoformat(),
        league_id="00",
        day_offset=0,
    )
    dfs = ep.get_data_frames()
    if not dfs:
        return []

    # df[0] = game header (one row per game); df[1] = line score (two rows per game)
    header_df = dfs[0]
    line_df = dfs[1] if len(dfs) > 1 else None

    # Build a quick lookup from (game_id, team_id) -> score, abbr.
    line_by_team: dict[tuple[str, int], dict[str, Any]] = {}
    if line_df is not None:
        for _, row in line_df.iterrows():
            key = (str(row.get("GAME_ID")), int(row.get("TEAM_ID")))
            line_by_team[key] = {
                "abbr": str(row.get("TEAM_ABBREVIATION") or ""),
                "score": _safe_int(row.get("PTS")),
            }

    snapshots: list[GameSnapshot] = []
    for _, row in header_df.iterrows():
        snap = _map_header_row(row, line_by_team)
        if snap is not None:
            snapshots.append(snap)
    return snapshots


def _map_header_row(row: Any, line_by_team: dict[tuple[str, int], dict[str, Any]]) -> GameSnapshot | None:
    game_id = str(row.get("GAME_ID") or "")
    home_id = _safe_int(row.get("HOME_TEAM_ID"))
    away_id = _safe_int(row.get("VISITOR_TEAM_ID"))
    if not (game_id and home_id and away_id):
        return None

    home_line = line_by_team.get((game_id, home_id), {})
    away_line = line_by_team.get((game_id, away_id), {})

    status_id = _safe_int(row.get("GAME_STATUS_ID")) or 1
    status = STATUS_BY_ID.get(status_id, "scheduled")
    period = _safe_int(row.get("LIVE_PERIOD"))
    if period is not None and period <= 0:
        period = None

    # GAME_DATE_EST is like "2026-05-17T00:00:00" with no TZ; treat as UTC midnight.
    date_str = str(row.get("GAME_DATE_EST") or "")[:10]
    tipoff_utc = _parse_tipoff_utc(row.get("GAME_DATE_EST"))

    # Season string. Header returns SEASON='2025' for 2025-26.
    season_year = _safe_int(row.get("SEASON"))
    season = _season_string(season_year) if season_year else _infer_season(date_str)

    return GameSnapshot(
        game_id=game_id,
        date=date_str,
        season=season,
        season_type=_infer_season_type(game_id),
        home_abbr=str(home_line.get("abbr") or ""),
        away_abbr=str(away_line.get("abbr") or ""),
        home_score=home_line.get("score"),
        away_score=away_line.get("score"),
        status=status,
        period=period,
        game_clock=_clean_clock(row.get("LIVE_PC_TIME"), status),
        tipoff_utc=tipoff_utc,
        arena_name=str(row.get("ARENA_NAME") or "") or None,
        broadcast=str(row.get("NATL_TV_BROADCASTER_ABBREVIATION") or "") or None,
        is_playoff=_infer_season_type(game_id) == "Playoffs",
    )


def _clean_clock(raw: Any, status: str) -> str | None:
    if status != "live":
        return None
    s = str(raw or "").strip()
    return s or None


def _parse_tipoff_utc(v: Any) -> str | None:
    """ScoreboardV2 returns GAME_DATE_EST without TZ; assume UTC midnight."""
    if v is None:
        return None
    s = str(v).strip()
    if not s:
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


def _season_string(year: int) -> str:
    return f"{year}-{(year + 1) % 100:02d}"


def _infer_season(date_str: str) -> str:
    """Fallback for when SEASON is missing. NBA seasons start in Oct."""
    if not date_str:
        return "2025-26"
    try:
        d = date.fromisoformat(date_str)
        year = d.year if d.month >= 10 else d.year - 1
        return _season_string(year)
    except ValueError:
        return "2025-26"


def _infer_season_type(game_id: str) -> str:
    """nba_api game_ids: '002' prefix = regular season, '004' = playoffs,
    '005' = play-in (newer), '001' = preseason."""
    if game_id.startswith("004"):
        return "Playoffs"
    if game_id.startswith("005"):
        return "Play-In"
    if game_id.startswith("001"):
        return "Preseason"
    return "Regular Season"


# --------------------------------------------------------------------------- #
# Fallback: balldontlie
# --------------------------------------------------------------------------- #


def _try_fallback(today: date) -> list[GameSnapshot]:
    """Hit balldontlie if a key is configured, else return []."""
    if not os.environ.get("BALLDONTLIE_API_KEY"):
        logger.warning(
            "live: BALLDONTLIE_API_KEY not set; skipping fallback (sign up at balldontlie.io)"
        )
        return []
    try:
        snapshots = bdl_live(today.isoformat())
        logger.info("live: balldontlie returned %d games for %s", len(snapshots), today)
        return snapshots
    except Exception as exc:  # noqa: BLE001
        logger.exception("live: balldontlie fallback also failed: %s", exc)
        return []


# --------------------------------------------------------------------------- #
# DB writer
# --------------------------------------------------------------------------- #


def _upsert_games(snaps: list[GameSnapshot]) -> int:
    """UPSERT each snapshot into the games table. Returns rows written."""
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
            source="live_scoreboard",
            url=None,
            content_sha256=None,
            chunk_count=len(rows),
            status="success",
        )
    return len(rows)
