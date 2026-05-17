"""Season-aggregate clutch stats per player + season + season_type.

Sourced from nba_api LeagueDashPlayerClutch with the league-standard clutch
definition (last 5 minutes, score within 5). One API call per (season,
season_type) returns every player; we only persist rows for players that
already exist in the `players` table.

Why aggregates and not per-game: the question class this enables is
"player X clutch shooting splits for reg season vs. playoffs," which is a
season-level query, not a per-game one. Per-game clutch can be added later
by parsing PlayByPlayV2 if needed.
"""

from __future__ import annotations

import logging
from typing import Any

from psycopg.types.json import Json

from src.ingest_stats.api_client import NBAClient
from src.ingest_stats.db import connect, write_audit

logger = logging.getLogger(__name__)


_INSERT_SQL = """
INSERT INTO player_clutch_stats (
    player_id, season, season_type,
    gp, min_total, pts,
    fgm, fga, fg3m, fg3a, ftm, fta,
    oreb, dreb, reb, ast, tov, stl, blk, pf, pfd, plus_minus,
    ts_pct, efg_pct,
    updated_at
)
VALUES (
    %(player_id)s, %(season)s, %(season_type)s,
    %(gp)s, %(min_total)s, %(pts)s,
    %(fgm)s, %(fga)s, %(fg3m)s, %(fg3a)s, %(ftm)s, %(fta)s,
    %(oreb)s, %(dreb)s, %(reb)s, %(ast)s, %(tov)s, %(stl)s, %(blk)s, %(pf)s, %(pfd)s, %(plus_minus)s,
    %(ts_pct)s, %(efg_pct)s,
    NOW()
)
ON CONFLICT (player_id, season, season_type) DO UPDATE SET
    gp         = EXCLUDED.gp,
    min_total  = EXCLUDED.min_total,
    pts        = EXCLUDED.pts,
    fgm        = EXCLUDED.fgm,
    fga        = EXCLUDED.fga,
    fg3m       = EXCLUDED.fg3m,
    fg3a       = EXCLUDED.fg3a,
    ftm        = EXCLUDED.ftm,
    fta        = EXCLUDED.fta,
    oreb       = EXCLUDED.oreb,
    dreb       = EXCLUDED.dreb,
    reb        = EXCLUDED.reb,
    ast        = EXCLUDED.ast,
    tov        = EXCLUDED.tov,
    stl        = EXCLUDED.stl,
    blk        = EXCLUDED.blk,
    pf         = EXCLUDED.pf,
    pfd        = EXCLUDED.pfd,
    plus_minus = EXCLUDED.plus_minus,
    ts_pct     = EXCLUDED.ts_pct,
    efg_pct    = EXCLUDED.efg_pct,
    updated_at = NOW();
"""


def _ts_pct(pts: int, fga: int, fta: int) -> float | None:
    """True shooting percentage. None when undefined (fga+fta = 0)."""
    denom = 2.0 * (fga + 0.44 * fta)
    if denom <= 0:
        return None
    return float(pts) / denom


def _efg_pct(fgm: int, fg3m: int, fga: int) -> float | None:
    """Effective field goal percentage. None when undefined (fga = 0)."""
    if fga <= 0:
        return None
    return (fgm + 0.5 * fg3m) / float(fga)


def _row_from_endpoint(row: dict[str, Any], season: str, season_type: str) -> dict[str, Any]:
    """Map a single LeagueDashPlayerClutch row into the player_clutch_stats schema."""
    pts = int(row.get("PTS") or 0)
    fgm = int(row.get("FGM") or 0)
    fga = int(row.get("FGA") or 0)
    fg3m = int(row.get("FG3M") or 0)
    fta = int(row.get("FTA") or 0)

    return {
        "player_id": int(row["PLAYER_ID"]),
        "season": season,
        "season_type": season_type,
        "gp": int(row.get("GP") or 0),
        "min_total": float(row.get("MIN") or 0.0),
        "pts": pts,
        "fgm": fgm,
        "fga": fga,
        "fg3m": fg3m,
        "fg3a": int(row.get("FG3A") or 0),
        "ftm": int(row.get("FTM") or 0),
        "fta": fta,
        "oreb": int(row.get("OREB") or 0),
        "dreb": int(row.get("DREB") or 0),
        "reb": int(row.get("REB") or 0),
        "ast": int(row.get("AST") or 0),
        "tov": int(row.get("TOV") or 0),
        "stl": int(row.get("STL") or 0),
        "blk": int(row.get("BLK") or 0),
        "pf": int(row.get("PF") or 0),
        "pfd": int(row.get("PFD") or 0),
        "plus_minus": int(row.get("PLUS_MINUS") or 0),
        "ts_pct": _ts_pct(pts, fga, fta),
        "efg_pct": _efg_pct(fgm, fg3m, fga),
    }


def sync_player_clutch(season: str = "2025-26", season_type: str = "Regular Season") -> int:
    """Pull season-aggregate clutch stats for the given (season, season_type)
    and UPSERT into `player_clutch_stats`. Returns the row count actually written.

    Only writes rows for players already in the `players` table to honor the
    foreign-key constraint. The endpoint covers the full league so most rows
    will land; bench warmers with zero clutch minutes are filtered by GP=0.
    """
    from nba_api.stats.endpoints import leaguedashplayerclutch

    client = NBAClient()
    endpoint = client.call(
        leaguedashplayerclutch.LeagueDashPlayerClutch,
        season=season,
        season_type_all_star=season_type,
        per_mode_detailed="Totals",
        clutch_time="Last 5 Minutes",
        point_diff="5",
    )

    df = endpoint.get_data_frames()[0]

    # Materialize the candidate set in Python so we can also filter against
    # the players table in a single round trip.
    candidates: list[dict[str, Any]] = []
    for _, raw in df.iterrows():
        row = _row_from_endpoint(raw.to_dict(), season, season_type)
        if row["gp"] <= 0:
            continue
        candidates.append(row)

    written = 0
    with connect() as conn:
        # Players we know about (rows missing from `players` would FK-fail).
        with conn.cursor() as cur:
            cur.execute("SELECT player_id FROM players")
            known = {r["player_id"] for r in cur.fetchall()}

        keep = [r for r in candidates if r["player_id"] in known]

        if keep:
            with conn.cursor() as cur:
                cur.executemany(_INSERT_SQL, keep)
                written = len(keep)
            conn.commit()

        write_audit(
            conn,
            source=f"nba_api/LeagueDashPlayerClutch/{season_type}",
            url=None,
            content_sha256=None,
            chunk_count=written,
            status="success",
        )

    logger.info(
        "sync_player_clutch(%s, %s): wrote %d rows (candidates=%d, known_players=%d)",
        season, season_type, written, len(candidates), len(keep) if candidates else 0,
    )
    return written
