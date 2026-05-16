"""Per-player per-game stats. Pulls from LeagueGameLog at player level so we
get every player's box for every game in one call per season-type.

The play_by_play module pulls richer data for the top-30 separately.
"""

from __future__ import annotations

import logging
from typing import Any

from src.ingest_stats.api_client import NBAClient
from src.ingest_stats.db import connect, upsert_player_game_stats, write_audit

logger = logging.getLogger(__name__)


def _safe_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _safe_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ts_pct(pts: int | None, fga: int | None, fta: int | None) -> float | None:
    """Compute true shooting percentage from box score.

    TS% = PTS / (2 * (FGA + 0.44 * FTA))
    """
    if pts is None or fga is None or fta is None:
        return None
    denom = 2 * (fga + 0.44 * fta)
    if denom == 0:
        return None
    return round(pts / denom, 4)


def sync_player_game_stats(
    season: str = "2025-26", season_type: str = "Regular Season"
) -> int:
    """Pull every player-game box score for the given season + season_type
    and UPSERT into `player_game_stats`. Returns the row count.
    """
    from nba_api.stats.endpoints import LeagueGameLog

    client = NBAClient()
    endpoint = client.call(
        LeagueGameLog,
        season=season,
        season_type_all_star=season_type,
        player_or_team_abbreviation="P",  # player-level
    )
    df = endpoint.get_data_frames()[0]

    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        pts = _safe_int(row.get("PTS"))
        fga = _safe_int(row.get("FGA"))
        fta = _safe_int(row.get("FTA"))
        rows.append(
            {
                "player_id": int(row["PLAYER_ID"]),
                "game_id": str(row["GAME_ID"]),
                "is_clutch_data": False,
                "team": str(row.get("TEAM_ABBREVIATION")) if row.get("TEAM_ABBREVIATION") else None,
                "minutes": _safe_float(row.get("MIN")),
                "pts": pts,
                "ast": _safe_int(row.get("AST")),
                "reb": _safe_int(row.get("REB")),
                "oreb": _safe_int(row.get("OREB")),
                "dreb": _safe_int(row.get("DREB")),
                "stl": _safe_int(row.get("STL")),
                "blk": _safe_int(row.get("BLK")),
                "tov": _safe_int(row.get("TOV")),
                "pf": _safe_int(row.get("PF")),
                "fgm": _safe_int(row.get("FGM")),
                "fga": fga,
                "fg_pct": _safe_float(row.get("FG_PCT")),
                "fg3m": _safe_int(row.get("FG3M")),
                "fg3a": _safe_int(row.get("FG3A")),
                "fg3_pct": _safe_float(row.get("FG3_PCT")),
                "ftm": _safe_int(row.get("FTM")),
                "fta": fta,
                "ft_pct": _safe_float(row.get("FT_PCT")),
                "ts_pct": _ts_pct(pts, fga, fta),
                "usg_pct": None,  # filled in by the advanced-splits pass for top-30
                "plus_minus": _safe_int(row.get("PLUS_MINUS")),
            }
        )

    with connect() as conn:
        n = upsert_player_game_stats(conn, rows)
        write_audit(
            conn,
            source=f"nba_api/LeagueGameLog/{season_type}/player",
            url=None,
            content_sha256=None,
            chunk_count=n,
            status="success",
        )
    logger.info(
        "sync_player_game_stats(%s, %s): upserted %d rows", season, season_type, n
    )
    return n
