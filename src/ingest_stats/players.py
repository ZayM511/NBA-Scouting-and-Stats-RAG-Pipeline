"""Player ingestion. Active players for the 2025-26 season.

Run at season start, refresh weekly during the regular season and daily
during the playoffs (rosters shift with two-way call-ups and 10-day signings).
"""

from __future__ import annotations

import logging
from typing import Any

from src.ingest_stats.api_client import NBAClient
from src.ingest_stats.db import connect, upsert_players, write_audit

logger = logging.getLogger(__name__)


# CommonAllPlayers and LeagueDashPlayerBioStats give us roster shape but no
# position. CommonTeamRoster is the canonical source for position, queried
# per team_id. The strings nba_api returns are single-letter ("G", "F", "C")
# or hyphenated ("G-F", "F-C") which already matches the schema convention.
def _normalize_position(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().upper()
    if not s:
        return None
    # Some endpoints return "Guard", "Forward-Center" — collapse those.
    if "-" in s:
        parts = [p[0] for p in s.split("-") if p]
        return "-".join(parts)
    if len(s) > 1:
        return s[0]
    return s


def _fetch_positions_for_team(client: NBAClient, team_id: int, season: str) -> dict[int, str]:
    """Return {player_id: position} for one team via CommonTeamRoster."""
    from nba_api.stats.endpoints import CommonTeamRoster

    endpoint = client.call(
        CommonTeamRoster,
        team_id=team_id,
        season=season,
    )
    df = endpoint.get_data_frames()[0]
    out: dict[int, str] = {}
    for _, row in df.iterrows():
        pid = row.get("PLAYER_ID")
        pos = _normalize_position(row.get("POSITION"))
        if pid is not None and pos:
            out[int(pid)] = pos
    return out


def sync_player_positions(season: str = "2025-26") -> int:
    """Walk every team_id in `players` and refresh `position` via
    `CommonTeamRoster`. Idempotent; safe to re-run. Returns the number of
    rows actually updated.

    Used because `CommonAllPlayers` (the only single-call current-season
    roster endpoint) does not return position, and the demo's hybrid
    pipeline relies on `players.position` for guard / forward / center
    intents.
    """
    client = NBAClient()

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT team_id FROM players "
                "WHERE team_id IS NOT NULL ORDER BY team_id"
            )
            team_ids = [int(r["team_id"]) for r in cur.fetchall()]

        if not team_ids:
            logger.warning("sync_player_positions: no team_ids in players table")
            return 0

        positions: dict[int, str] = {}
        for team_id in team_ids:
            try:
                positions.update(_fetch_positions_for_team(client, team_id, season))
            except Exception:  # noqa: BLE001
                logger.exception("CommonTeamRoster failed for team_id=%s", team_id)

        if not positions:
            logger.warning("sync_player_positions: no positions fetched")
            return 0

        # Batched UPDATE: one query per player_id is fine for ~600 rows on
        # a local Postgres; the network round-trip dominates anyway.
        sql = "UPDATE players SET position = %s WHERE player_id = %s"
        with conn.cursor() as cur:
            cur.executemany(sql, [(pos, pid) for pid, pos in positions.items()])
        conn.commit()
        n = len(positions)
        write_audit(
            conn,
            source="nba_api/CommonTeamRoster",
            url=None,
            content_sha256=None,
            chunk_count=n,
            status="success",
        )
    logger.info(
        "sync_player_positions(%s): refreshed %d positions across %d teams",
        season, n, len(team_ids),
    )
    return n


def sync_active_players(season: str = "2025-26") -> int:
    """Pull every active player from nba_api's CommonAllPlayers for the given
    season and UPSERT into `players`. Returns the row count.

    `position` is populated by a follow-up call to `sync_player_positions()`
    (CommonTeamRoster is the canonical source). This stays a separate step
    so callers can refresh just one of the two when needed.
    """
    from nba_api.stats.endpoints import CommonAllPlayers

    client = NBAClient()
    endpoint = client.call(
        CommonAllPlayers,
        is_only_current_season=1,
        league_id="00",
        season=season,
    )

    df = endpoint.get_data_frames()[0]
    # nba_api returns mixed case; normalize to the schema's names.
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        rows.append(
            {
                "player_id": int(row["PERSON_ID"]),
                "name": str(row.get("DISPLAY_FIRST_LAST") or row.get("DISPLAY_LAST_COMMA_FIRST") or ""),
                "team_id": int(row["TEAM_ID"]) if row.get("TEAM_ID") else None,
                "team": str(row["TEAM_ABBREVIATION"]) if row.get("TEAM_ABBREVIATION") else None,
                "position": None,             # CommonAllPlayers doesn't include position; sync_player_positions fills it
                "jersey_number": None,
                "height_inches": None,
                "weight_lbs": None,
                "birthdate": None,
                "draft_year": int(row["FROM_YEAR"]) if row.get("FROM_YEAR") else None,
                "is_active": bool(row.get("ROSTERSTATUS", 1)),
            }
        )

    with connect() as conn:
        n = upsert_players(conn, rows)
        write_audit(
            conn,
            source="nba_api/CommonAllPlayers",
            url=None,
            content_sha256=None,
            chunk_count=n,
            status="success",
        )
    logger.info("sync_active_players(%s): upserted %d players", season, n)
    return n
