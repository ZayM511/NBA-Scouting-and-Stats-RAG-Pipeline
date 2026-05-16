"""Game ingestion. Pulls per-team game logs for the season, derives the unique
game list, and UPSERTs into `games`.

Two season types are pulled: Regular Season and Playoffs (the playoff games
have `is_playoff = TRUE` and a `playoff_round`).
"""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any

from src.ingest_stats.api_client import NBAClient
from src.ingest_stats.db import connect, upsert_games, write_audit

logger = logging.getLogger(__name__)


SEASON_TYPES: tuple[str, ...] = ("Regular Season", "Playoffs", "PlayIn")
# nba_api uses "Regular Season", "Playoffs", "Pre Season". "PlayIn" isn't a
# standard season_type_all_star value; the Play-In games show up under
# "Regular Season" in LeagueGameLog historically. Keep the tuple for future use.


def _parse_matchup(matchup: str, team_abbr: str) -> tuple[str, str]:
    """nba_api's MATCHUP column reads 'GSW vs. LAL' (home) or 'GSW @ LAL' (away).
    Return (home_team, away_team) abbreviations."""
    parts = matchup.split()
    if "vs." in matchup:
        # 'GSW vs. LAL' -> home = team_abbr, away = the other
        idx = parts.index("vs.")
        away = parts[idx + 1]
        return team_abbr, away
    elif "@" in matchup:
        idx = parts.index("@")
        away = parts[idx + 1]
        return away, team_abbr
    # Fallback: treat as home (rare; usually means malformed input)
    return team_abbr, matchup


def sync_games(season: str = "2025-26", season_type: str = "Regular Season") -> int:
    """Pull every game for the given season + season_type and UPSERT into
    `games`. Returns the row count.

    nba_api's LeagueGameLog returns one row per (team, game), so 1230 games
    appear as 2460 rows in the regular season. We dedupe by game_id.
    """
    from nba_api.stats.endpoints import LeagueGameLog

    client = NBAClient()
    endpoint = client.call(
        LeagueGameLog,
        season=season,
        season_type_all_star=season_type,
        player_or_team_abbreviation="T",  # team-level
    )
    df = endpoint.get_data_frames()[0]

    games_by_id: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        game_id = str(row["GAME_ID"])
        team_abbr = str(row["TEAM_ABBREVIATION"])
        matchup = str(row["MATCHUP"])
        home_team, away_team = _parse_matchup(matchup, team_abbr)

        # game_date may be 'YYYY-MM-DD' string or already a date
        gd = row["GAME_DATE"]
        if isinstance(gd, str):
            try:
                game_date = _date.fromisoformat(gd)
            except ValueError:
                game_date = None
        else:
            game_date = gd

        # Merge home/away rows into one record
        existing = games_by_id.get(game_id, {})
        merged: dict[str, Any] = {
            "game_id": game_id,
            "date": game_date,
            "season": season,
            "season_type": season_type,
            "home_team": home_team if home_team else existing.get("home_team"),
            "away_team": away_team if away_team else existing.get("away_team"),
            "home_score": None,
            "away_score": None,
            "is_playoff": season_type == "Playoffs",
            "playoff_round": None,
            "playoff_series": None,
        }

        pts = int(row["PTS"]) if row.get("PTS") is not None else None
        if pts is not None:
            if team_abbr == merged["home_team"]:
                merged["home_score"] = pts
            elif team_abbr == merged["away_team"]:
                merged["away_score"] = pts

        # Preserve existing scores when merging the second row of a pair.
        if existing:
            merged["home_score"] = merged["home_score"] or existing.get("home_score")
            merged["away_score"] = merged["away_score"] or existing.get("away_score")

        games_by_id[game_id] = merged

    rows = list(games_by_id.values())
    with connect() as conn:
        n = upsert_games(conn, rows)
        write_audit(
            conn,
            source=f"nba_api/LeagueGameLog/{season_type}",
            url=None,
            content_sha256=None,
            chunk_count=n,
            status="success",
        )
    logger.info("sync_games(%s, %s): upserted %d games", season, season_type, n)
    return n
