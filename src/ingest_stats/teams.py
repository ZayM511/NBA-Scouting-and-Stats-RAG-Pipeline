"""Team ingestion. One-shot job; teams don't change mid-season except for
the very rare relocation or name change.
"""

from __future__ import annotations

import logging
from typing import Any

from src.ingest_stats.api_client import NBAClient
from src.ingest_stats.db import connect, upsert_teams, write_audit

logger = logging.getLogger(__name__)


# Static map of nba_api team_id -> (conference, division). nba_api's
# CommonTeamYears doesn't carry conference/division reliably for the current
# season, so we hardcode the 30-team map. Update only on realignment.
TEAM_METADATA: dict[int, dict[str, str]] = {
    1610612737: {"conference": "East", "division": "Southeast"},   # ATL
    1610612738: {"conference": "East", "division": "Atlantic"},    # BOS
    1610612751: {"conference": "East", "division": "Atlantic"},    # BKN
    1610612766: {"conference": "East", "division": "Southeast"},   # CHA
    1610612741: {"conference": "East", "division": "Central"},     # CHI
    1610612739: {"conference": "East", "division": "Central"},     # CLE
    1610612742: {"conference": "West", "division": "Southwest"},   # DAL
    1610612743: {"conference": "West", "division": "Northwest"},   # DEN
    1610612765: {"conference": "East", "division": "Central"},     # DET
    1610612744: {"conference": "West", "division": "Pacific"},     # GSW
    1610612745: {"conference": "West", "division": "Southwest"},   # HOU
    1610612754: {"conference": "East", "division": "Central"},     # IND
    1610612746: {"conference": "West", "division": "Pacific"},     # LAC
    1610612747: {"conference": "West", "division": "Pacific"},     # LAL
    1610612763: {"conference": "West", "division": "Southwest"},   # MEM
    1610612748: {"conference": "East", "division": "Southeast"},   # MIA
    1610612749: {"conference": "East", "division": "Central"},     # MIL
    1610612750: {"conference": "West", "division": "Northwest"},   # MIN
    1610612740: {"conference": "West", "division": "Southwest"},   # NOP
    1610612752: {"conference": "East", "division": "Atlantic"},    # NYK
    1610612760: {"conference": "West", "division": "Northwest"},   # OKC
    1610612753: {"conference": "East", "division": "Southeast"},   # ORL
    1610612755: {"conference": "East", "division": "Atlantic"},    # PHI
    1610612756: {"conference": "West", "division": "Pacific"},     # PHX
    1610612757: {"conference": "West", "division": "Northwest"},   # POR
    1610612758: {"conference": "West", "division": "Pacific"},     # SAC
    1610612759: {"conference": "West", "division": "Southwest"},   # SAS
    1610612761: {"conference": "East", "division": "Atlantic"},    # TOR
    1610612762: {"conference": "West", "division": "Northwest"},   # UTA
    1610612764: {"conference": "East", "division": "Southeast"},   # WAS
}


def sync_teams() -> int:
    """Fetch all 30 NBA teams from nba_api and UPSERT into `teams`. Returns
    the row count."""
    # Import inside the function so tests can collect without nba_api installed.
    from nba_api.stats.static import teams as static_teams

    client = NBAClient()  # not strictly needed for the static endpoint, but
    _ = client  # the rate limiter is still useful if we expand to dynamic calls

    raw = static_teams.get_teams()
    rows: list[dict[str, Any]] = []
    for t in raw:
        team_id: int = t["id"]
        meta = TEAM_METADATA.get(team_id, {})
        rows.append(
            {
                "team_id": team_id,
                "abbreviation": t["abbreviation"],
                "city": t["city"],
                "name": t["nickname"],
                "conference": meta.get("conference"),
                "division": meta.get("division"),
            }
        )

    with connect() as conn:
        n = upsert_teams(conn, rows)
        write_audit(
            conn,
            source="nba_api/static/teams",
            url=None,
            content_sha256=None,
            chunk_count=n,
            status="success",
        )
    logger.info("sync_teams: upserted %d teams", n)
    return n
