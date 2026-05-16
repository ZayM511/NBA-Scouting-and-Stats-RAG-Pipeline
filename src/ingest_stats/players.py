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


def sync_active_players(season: str = "2025-26") -> int:
    """Pull every active player from nba_api's CommonAllPlayers for the given
    season and UPSERT into `players`. Returns the row count.
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
                "position": None,             # CommonAllPlayers doesn't include position; enriched later
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
