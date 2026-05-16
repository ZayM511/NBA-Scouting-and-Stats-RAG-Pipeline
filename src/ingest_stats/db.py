"""Database helpers for stats ingestion. Idempotent UPSERTs, audit logging.

Every write goes through these helpers so the SQL stays in one place and the
sql-reviewer agent can review the patterns once instead of per-call-site.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Sequence
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from src.config import get_settings

logger = logging.getLogger(__name__)


@contextmanager
def connect():  # type: ignore[no-untyped-def]
    """Yield a psycopg connection using POSTGRES_URL from config. Closes on exit."""
    settings = get_settings()
    with psycopg.connect(str(settings.postgres_url), row_factory=dict_row) as conn:
        yield conn


# --------------------------------------------------------------------------- #
# Audit log
# --------------------------------------------------------------------------- #


def write_audit(
    conn: Connection,
    *,
    source: str,
    url: str | None,
    content_sha256: str | None,
    chunk_count: int | None,
    status: str,
    error: str | None = None,
) -> None:
    """Append a row to ingest_audit. Never fails the caller."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingest_audit
                    (source, url, content_sha256, chunk_count, status, error)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (source, url, content_sha256, chunk_count, status, error),
            )
        conn.commit()
    except Exception:
        logger.exception("failed to write ingest_audit row; continuing")


# --------------------------------------------------------------------------- #
# UPSERT helpers
# --------------------------------------------------------------------------- #


def upsert_teams(conn: Connection, rows: Sequence[dict[str, Any]]) -> int:
    """Insert or update teams. Returns row count."""
    if not rows:
        return 0
    sql = """
        INSERT INTO teams
            (team_id, abbreviation, city, name, conference, division)
        VALUES
            (%(team_id)s, %(abbreviation)s, %(city)s, %(name)s, %(conference)s, %(division)s)
        ON CONFLICT (team_id) DO UPDATE SET
            abbreviation = EXCLUDED.abbreviation,
            city         = EXCLUDED.city,
            name         = EXCLUDED.name,
            conference   = EXCLUDED.conference,
            division     = EXCLUDED.division,
            updated_at   = NOW()
    """
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    conn.commit()
    return len(rows)


def upsert_players(conn: Connection, rows: Sequence[dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = """
        INSERT INTO players
            (player_id, name, team_id, team, position, jersey_number,
             height_inches, weight_lbs, birthdate, draft_year, is_active)
        VALUES
            (%(player_id)s, %(name)s, %(team_id)s, %(team)s, %(position)s,
             %(jersey_number)s, %(height_inches)s, %(weight_lbs)s,
             %(birthdate)s, %(draft_year)s, %(is_active)s)
        ON CONFLICT (player_id) DO UPDATE SET
            name          = EXCLUDED.name,
            team_id       = EXCLUDED.team_id,
            team          = EXCLUDED.team,
            position      = EXCLUDED.position,
            jersey_number = EXCLUDED.jersey_number,
            height_inches = EXCLUDED.height_inches,
            weight_lbs    = EXCLUDED.weight_lbs,
            birthdate     = EXCLUDED.birthdate,
            draft_year    = EXCLUDED.draft_year,
            is_active     = EXCLUDED.is_active,
            updated_at    = NOW()
    """
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    conn.commit()
    return len(rows)


def upsert_games(conn: Connection, rows: Sequence[dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = """
        INSERT INTO games
            (game_id, date, season, season_type, home_team, away_team,
             home_score, away_score, is_playoff, playoff_round, playoff_series)
        VALUES
            (%(game_id)s, %(date)s, %(season)s, %(season_type)s,
             %(home_team)s, %(away_team)s,
             %(home_score)s, %(away_score)s,
             %(is_playoff)s, %(playoff_round)s, %(playoff_series)s)
        ON CONFLICT (game_id) DO UPDATE SET
            home_score    = EXCLUDED.home_score,
            away_score    = EXCLUDED.away_score,
            is_playoff    = EXCLUDED.is_playoff,
            playoff_round = EXCLUDED.playoff_round,
            playoff_series= EXCLUDED.playoff_series,
            updated_at    = NOW()
    """
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    conn.commit()
    return len(rows)


def upsert_player_game_stats(conn: Connection, rows: Sequence[dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = """
        INSERT INTO player_game_stats (
            player_id, game_id, is_clutch_data, team,
            minutes, pts, ast, reb, oreb, dreb,
            stl, blk, tov, pf,
            fgm, fga, fg_pct,
            fg3m, fg3a, fg3_pct,
            ftm, fta, ft_pct,
            ts_pct, usg_pct, plus_minus
        )
        VALUES (
            %(player_id)s, %(game_id)s, %(is_clutch_data)s, %(team)s,
            %(minutes)s, %(pts)s, %(ast)s, %(reb)s, %(oreb)s, %(dreb)s,
            %(stl)s, %(blk)s, %(tov)s, %(pf)s,
            %(fgm)s, %(fga)s, %(fg_pct)s,
            %(fg3m)s, %(fg3a)s, %(fg3_pct)s,
            %(ftm)s, %(fta)s, %(ft_pct)s,
            %(ts_pct)s, %(usg_pct)s, %(plus_minus)s
        )
        ON CONFLICT (player_id, game_id, is_clutch_data) DO UPDATE SET
            minutes    = EXCLUDED.minutes,
            pts        = EXCLUDED.pts,
            ast        = EXCLUDED.ast,
            reb        = EXCLUDED.reb,
            oreb       = EXCLUDED.oreb,
            dreb       = EXCLUDED.dreb,
            stl        = EXCLUDED.stl,
            blk        = EXCLUDED.blk,
            tov        = EXCLUDED.tov,
            pf         = EXCLUDED.pf,
            fgm        = EXCLUDED.fgm,
            fga        = EXCLUDED.fga,
            fg_pct     = EXCLUDED.fg_pct,
            fg3m       = EXCLUDED.fg3m,
            fg3a       = EXCLUDED.fg3a,
            fg3_pct    = EXCLUDED.fg3_pct,
            ftm        = EXCLUDED.ftm,
            fta        = EXCLUDED.fta,
            ft_pct     = EXCLUDED.ft_pct,
            ts_pct     = EXCLUDED.ts_pct,
            usg_pct    = EXCLUDED.usg_pct,
            plus_minus = EXCLUDED.plus_minus
    """
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    conn.commit()
    return len(rows)


def fetch_existing_game_ids(conn: Connection, season: str) -> set[str]:
    """Return the set of game_ids already in `games` for a given season."""
    with conn.cursor() as cur:
        cur.execute("SELECT game_id FROM games WHERE season = %s", (season,))
        return {r["game_id"] for r in cur.fetchall()}


def fetch_top30_player_ids(conn: Connection) -> list[int]:
    with conn.cursor() as cur:
        cur.execute("SELECT player_id FROM players WHERE is_top30 = TRUE ORDER BY player_id")
        return [r["player_id"] for r in cur.fetchall()]


# --------------------------------------------------------------------------- #
# Generic helpers
# --------------------------------------------------------------------------- #


def chunked(iterable: Iterable[Any], size: int) -> Iterable[list[Any]]:
    """Yield successive `size`-sized chunks from `iterable`."""
    batch: list[Any] = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def json_dump_safe(value: Any) -> str:
    """Stable JSON dump for hashing. Sorted keys, no whitespace."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
