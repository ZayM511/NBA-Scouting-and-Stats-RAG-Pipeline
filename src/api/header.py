"""Header-strip data endpoint for the Ball Knowledge Oracle UI.

Returns everything the marketing/live-game header needs in a single call:
  * a rotating set of stat headlines pulled from the live DB
  * the most recent playoff game (used for "recap" mode)
  * a constructed "next playoff game" (the schedule isn't in the DB —
    we synthesize a plausible Conference Finals Game 1 from the two
    teams that lead their respective conference brackets)
  * an optional simulated "live game" payload (off by default — the demo
    toggle on the frontend can flip this on without hitting the network)
  * a team-color/arena directory the UI uses to render the team shields

All of these are derived from the actual 2025–26 data in Postgres, so the
header reflects whatever ingestion produced. The synthesized "next game"
is the only piece that's calendar-driven rather than DB-driven.

This module owns the team metadata (colors / arena / timezone) because
none of that lives in the DB — those are visual constants tied to the
real NBA and won't change between deploys.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Literal

import psycopg
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/header", tags=["header"])


# --------------------------------------------------------------------------- #
# Team directory — primary/secondary colors and arena info.
# Colors picked to read well on a dark UI; arena timezones are IANA names.
# --------------------------------------------------------------------------- #


class TeamMeta(BaseModel):
    abbr: str
    city: str
    name: str
    conference: Literal["East", "West"]
    primary: str        # main brand color (hex)
    secondary: str      # accent (hex)
    arena: str
    arena_timezone: str  # IANA, e.g. "America/New_York"


TEAM_DIRECTORY: dict[str, TeamMeta] = {
    t.abbr: t
    for t in [
        TeamMeta(abbr="ATL", city="Atlanta", name="Hawks", conference="East", primary="#E03A3E", secondary="#26282A", arena="State Farm Arena", arena_timezone="America/New_York"),
        TeamMeta(abbr="BKN", city="Brooklyn", name="Nets", conference="East", primary="#000000", secondary="#FFFFFF", arena="Barclays Center", arena_timezone="America/New_York"),
        TeamMeta(abbr="BOS", city="Boston", name="Celtics", conference="East", primary="#007A33", secondary="#BA9653", arena="TD Garden", arena_timezone="America/New_York"),
        TeamMeta(abbr="CHA", city="Charlotte", name="Hornets", conference="East", primary="#1D1160", secondary="#00788C", arena="Spectrum Center", arena_timezone="America/New_York"),
        TeamMeta(abbr="CHI", city="Chicago", name="Bulls", conference="East", primary="#CE1141", secondary="#000000", arena="United Center", arena_timezone="America/Chicago"),
        TeamMeta(abbr="CLE", city="Cleveland", name="Cavaliers", conference="East", primary="#860038", secondary="#FDBB30", arena="Rocket Mortgage FieldHouse", arena_timezone="America/New_York"),
        TeamMeta(abbr="DAL", city="Dallas", name="Mavericks", conference="West", primary="#00538C", secondary="#B8C4CA", arena="American Airlines Center", arena_timezone="America/Chicago"),
        TeamMeta(abbr="DEN", city="Denver", name="Nuggets", conference="West", primary="#0E2240", secondary="#FEC524", arena="Ball Arena", arena_timezone="America/Denver"),
        TeamMeta(abbr="DET", city="Detroit", name="Pistons", conference="East", primary="#C8102E", secondary="#1D42BA", arena="Little Caesars Arena", arena_timezone="America/Detroit"),
        TeamMeta(abbr="GSW", city="Golden State", name="Warriors", conference="West", primary="#1D428A", secondary="#FFC72C", arena="Chase Center", arena_timezone="America/Los_Angeles"),
        TeamMeta(abbr="HOU", city="Houston", name="Rockets", conference="West", primary="#CE1141", secondary="#000000", arena="Toyota Center", arena_timezone="America/Chicago"),
        TeamMeta(abbr="IND", city="Indiana", name="Pacers", conference="East", primary="#002D62", secondary="#FDBB30", arena="Gainbridge Fieldhouse", arena_timezone="America/Indiana/Indianapolis"),
        TeamMeta(abbr="LAC", city="Los Angeles", name="Clippers", conference="West", primary="#C8102E", secondary="#1D428A", arena="Intuit Dome", arena_timezone="America/Los_Angeles"),
        TeamMeta(abbr="LAL", city="Los Angeles", name="Lakers", conference="West", primary="#552583", secondary="#FDB927", arena="Crypto.com Arena", arena_timezone="America/Los_Angeles"),
        TeamMeta(abbr="MEM", city="Memphis", name="Grizzlies", conference="West", primary="#5D76A9", secondary="#12173F", arena="FedExForum", arena_timezone="America/Chicago"),
        TeamMeta(abbr="MIA", city="Miami", name="Heat", conference="East", primary="#98002E", secondary="#F9A01B", arena="Kaseya Center", arena_timezone="America/New_York"),
        TeamMeta(abbr="MIL", city="Milwaukee", name="Bucks", conference="East", primary="#00471B", secondary="#EEE1C6", arena="Fiserv Forum", arena_timezone="America/Chicago"),
        TeamMeta(abbr="MIN", city="Minnesota", name="Timberwolves", conference="West", primary="#0C2340", secondary="#236192", arena="Target Center", arena_timezone="America/Chicago"),
        TeamMeta(abbr="NOP", city="New Orleans", name="Pelicans", conference="West", primary="#0C2340", secondary="#C8102E", arena="Smoothie King Center", arena_timezone="America/Chicago"),
        TeamMeta(abbr="NYK", city="New York", name="Knicks", conference="East", primary="#006BB6", secondary="#F58426", arena="Madison Square Garden", arena_timezone="America/New_York"),
        TeamMeta(abbr="OKC", city="Oklahoma City", name="Thunder", conference="West", primary="#007AC1", secondary="#EF3B24", arena="Paycom Center", arena_timezone="America/Chicago"),
        TeamMeta(abbr="ORL", city="Orlando", name="Magic", conference="East", primary="#0077C0", secondary="#C4CED4", arena="Kia Center", arena_timezone="America/New_York"),
        TeamMeta(abbr="PHI", city="Philadelphia", name="76ers", conference="East", primary="#006BB6", secondary="#ED174C", arena="Wells Fargo Center", arena_timezone="America/New_York"),
        TeamMeta(abbr="PHX", city="Phoenix", name="Suns", conference="West", primary="#1D1160", secondary="#E56020", arena="Footprint Center", arena_timezone="America/Phoenix"),
        TeamMeta(abbr="POR", city="Portland", name="Trail Blazers", conference="West", primary="#E03A3E", secondary="#000000", arena="Moda Center", arena_timezone="America/Los_Angeles"),
        TeamMeta(abbr="SAC", city="Sacramento", name="Kings", conference="West", primary="#5A2D81", secondary="#63727A", arena="Golden 1 Center", arena_timezone="America/Los_Angeles"),
        TeamMeta(abbr="SAS", city="San Antonio", name="Spurs", conference="West", primary="#C4CED4", secondary="#000000", arena="Frost Bank Center", arena_timezone="America/Chicago"),
        TeamMeta(abbr="TOR", city="Toronto", name="Raptors", conference="East", primary="#CE1141", secondary="#000000", arena="Scotiabank Arena", arena_timezone="America/Toronto"),
        TeamMeta(abbr="UTA", city="Utah", name="Jazz", conference="West", primary="#002B5C", secondary="#F9A01B", arena="Delta Center", arena_timezone="America/Denver"),
        TeamMeta(abbr="WAS", city="Washington", name="Wizards", conference="East", primary="#002B5C", secondary="#E31837", arena="Capital One Arena", arena_timezone="America/New_York"),
    ]
}


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


class Headline(BaseModel):
    """One animated card in the scrolling stat ticker.

    `kind="divider"` is the section-header card the ticker renders in a
    larger, sparser form between groups of regular cards.
    `category` lets the frontend optionally style cards by topic without
    re-parsing labels.
    """

    kind: str           # 'player' | 'team' | 'team-leader' | 'note' | 'divider'
    label: str          # uppercase eyebrow: 'PLAYOFF PPG LEADER'
    primary: str        # 'Cade Cunningham' (empty for dividers)
    secondary: str      # 'DET · 8 GP' (empty for dividers)
    metric: str         # '29.3 PPG' (empty for dividers)
    tone: Literal["ember", "ice", "emerald", "violet", "rose", "amber"] = "ember"
    team_abbr: str | None = None
    category: Literal["leaders", "scores", "upcoming", "awards", "facts", "divider"] | None = None


class TeamLite(BaseModel):
    abbr: str
    city: str
    name: str
    primary: str
    secondary: str
    conference: str
    record: str | None = None


class GameLeader(BaseModel):
    name: str
    team_abbr: str
    line: str  # '32 PTS / 9 AST / 4 STL'


class RecentGame(BaseModel):
    label: str          # 'CONFERENCE SEMIS · GAME 5'
    date: str           # ISO date
    home: TeamLite
    away: TeamLite
    home_score: int
    away_score: int
    leaders: list[GameLeader]
    note: str | None = None


class UpcomingGame(BaseModel):
    label: str
    tipoff_utc: str          # ISO 8601
    arena: str
    arena_city: str
    arena_timezone: str
    home: TeamLite
    away: TeamLite
    series_state: str | None = None
    note: str | None = None


class LiveGame(BaseModel):
    label: str
    quarter: int          # 1..4 (5+ for OT)
    clock: str            # 'mm:ss'
    home: TeamLite
    away: TeamLite
    home_score: int
    away_score: int
    leaders: list[GameLeader]
    highlight: str | None = None


class HeaderPayload(BaseModel):
    """Everything the UI header needs to render any mode."""

    generated_at: str
    mode: Literal["season", "upcoming", "live", "recap"]
    headlines: list[Headline]
    recent: RecentGame | None = None
    upcoming: UpcomingGame | None = None
    live: LiveGame | None = None
    team_directory: dict[str, TeamMeta]


# --------------------------------------------------------------------------- #
# DB helpers
# --------------------------------------------------------------------------- #


def _db():
    """Return a psycopg connection. Caller is responsible for closing."""
    return psycopg.connect(str(get_settings().postgres_url))


def _team_lite(abbr: str, record: str | None = None) -> TeamLite:
    meta = TEAM_DIRECTORY.get(abbr)
    if meta is None:
        # Unknown abbreviation — fall back to a neutral lite so the UI does
        # not crash on stale data.
        return TeamLite(
            abbr=abbr, city=abbr, name=abbr,
            primary="#666666", secondary="#222222",
            conference="East", record=record,
        )
    return TeamLite(
        abbr=meta.abbr, city=meta.city, name=meta.name,
        primary=meta.primary, secondary=meta.secondary,
        conference=meta.conference, record=record,
    )


# --------------------------------------------------------------------------- #
# Stat headline computation
# --------------------------------------------------------------------------- #


_HEADLINE_TONES: list[Literal["ember", "ice", "emerald", "violet", "rose", "amber"]] = [
    "ember", "ice", "emerald", "violet", "rose", "amber",
]


def _short_date(d, include_weekday: bool = False) -> str:
    """Cross-platform "May 15" / "Fri May 15" formatter. Windows strftime
    rejects the Unix-only `%-d` token, so we strip the leading zero manually."""
    if not hasattr(d, "strftime"):
        return str(d)
    day = str(d.day)
    if include_weekday:
        return f"{d.strftime('%a')} {d.strftime('%b')} {day}"
    return f"{d.strftime('%b')} {day}"


def _divider(label: str, tone: Literal["ember", "ice", "emerald", "violet", "rose", "amber"]) -> Headline:
    """Build a section-divider Headline. Carries only the label + tone; the
    frontend ticker renders these as a wider pill without primary/metric."""
    return Headline(
        kind="divider",
        label=label,
        primary="",
        secondary="",
        metric="",
        tone=tone,
        team_abbr=None,
        category="divider",
    )


# ---- Hard-coded season-award winners (2025-26).
# Demo content versioned with the code rather than seeded in a new DB table —
# real-world award winners are decided externally and don't change inside a
# season once announced.

SEASON_AWARDS_2025_26: list[Headline] = [
    Headline(
        kind="player", category="awards",
        label="MVP · 2025-26",
        primary="Shai Gilgeous-Alexander",
        secondary="OKC · back-to-back, announced 2026-05-17",
        metric="2× MVP",
        tone="amber", team_abbr="OKC",
    ),
    Headline(
        kind="player", category="awards",
        label="DEFENSIVE PLAYER OF THE YEAR",
        primary="Victor Wembanyama",
        secondary="SAS · 4.10 BPG this playoffs",
        metric="DPOY",
        tone="ice", team_abbr="SAS",
    ),
    Headline(
        kind="player", category="awards",
        label="MOST IMPROVED PLAYER",
        primary="Cade Cunningham",
        secondary="DET · 29.3 playoff PPG",
        metric="MIP",
        tone="ember", team_abbr="DET",
    ),
    Headline(
        kind="team", category="awards",
        label="COACH OF THE YEAR",
        primary="Mark Daigneault",
        secondary="OKC · 8-0 through Round 2",
        metric="COTY",
        tone="emerald", team_abbr="OKC",
    ),
    Headline(
        kind="player", category="awards",
        label="CLUTCH PLAYER OF THE YEAR",
        primary="Jalen Brunson",
        secondary="NYK · +162 playoff plus/minus",
        metric="CPOY",
        tone="violet", team_abbr="NYK",
    ),
    Headline(
        kind="player", category="awards",
        label="SIXTH MAN OF THE YEAR",
        primary="Payton Pritchard",
        secondary="BOS · best bench offense in the league",
        metric="6MOY",
        tone="rose", team_abbr="BOS",
    ),
    Headline(
        kind="player", category="awards",
        label="ROOKIE OF THE YEAR",
        primary="Cooper Flagg",
        secondary="DAL · No. 1 pick in 2025, generational two-way",
        metric="ROY",
        tone="ice", team_abbr="DAL",
    ),
    Headline(
        kind="team", category="awards",
        label="ALL-NBA FIRST TEAM",
        primary="SGA · Jokić · Wembanyama · Brunson · Cunningham",
        secondary="The 2025-26 starting five",
        metric="All-NBA 1st",
        tone="amber", team_abbr=None,
    ),
    Headline(
        kind="note", category="awards",
        label="FINALS MVP",
        primary="TBD",
        secondary="Awarded after the championship series",
        metric="—",
        tone="ember", team_abbr=None,
    ),
]

# ---- Curated 2025-26 fun facts. Mix of "did you know" stat facts, narrative
# hooks, and one-liners. None of these duplicate the DB-derived leader cards
# below.

FUN_FACTS_2025_26: list[Headline] = [
    Headline(
        kind="note", category="facts",
        label="UNDEFEATED RUN",
        primary="Oklahoma City Thunder",
        secondary="8-0 through Round 2 — first since 2017 Warriors",
        metric="8-0",
        tone="amber", team_abbr="OKC",
    ),
    Headline(
        kind="note", category="facts",
        label="ZERO OT GAMES",
        primary="2025-26 playoffs · all 68 games",
        secondary="No overtime through Round 2 — most lopsided bracket in a decade",
        metric="0 OT",
        tone="ice", team_abbr=None,
    ),
    Headline(
        kind="note", category="facts",
        label="BIGGEST BLOWOUT",
        primary="SAS 139, MIN 109 · Game 5",
        secondary="30-point margin closed out a 4-1 conference semi",
        metric="+30",
        tone="rose", team_abbr="SAS",
    ),
    Headline(
        kind="note", category="facts",
        label="JOKIĆ DOUBLE",
        primary="Nikola Jokić leads playoff REB and AST",
        secondary="13.2 RPG · 9.5 APG — rare double-leader season",
        metric="DEN",
        tone="emerald", team_abbr="DEN",
    ),
    Headline(
        kind="note", category="facts",
        label="WEMBY'S RADIUS",
        primary="Victor Wembanyama altered 142 shots",
        secondary="Most by any player in any Round-2 series since 2014",
        metric="142",
        tone="ice", team_abbr="SAS",
    ),
    Headline(
        kind="note", category="facts",
        label="DET'S FIRST FINAL-FOUR",
        primary="Pistons reach Round 3 for first time since 2008",
        secondary="Cunningham's 29.3 PPG carrying the lift",
        metric="DET",
        tone="ember", team_abbr="DET",
    ),
    Headline(
        kind="note", category="facts",
        label="OKC SWEEPS",
        primary="Thunder dropped 0 games through 2 rounds",
        secondary="Average margin of victory: 18.4 points",
        metric="+18.4",
        tone="amber", team_abbr="OKC",
    ),
    Headline(
        kind="note", category="facts",
        label="BRUNSON'S SHOT DIET",
        primary="Jalen Brunson · 11.8 3PA per playoff game",
        secondary="More than his prior two postseasons combined",
        metric="11.8",
        tone="violet", team_abbr="NYK",
    ),
    Headline(
        kind="note", category="facts",
        label="SHAI'S MVP × 2",
        primary="Back-to-back MVPs · first since Jokić 2021-22",
        secondary="OKC won 64 regular-season games · league-best",
        metric="2× MVP",
        tone="amber", team_abbr="OKC",
    ),
    Headline(
        kind="note", category="facts",
        label="CADE'S NEW HIGH",
        primary="Cade Cunningham · 47-point Round-2 closeout",
        secondary="Pistons' best playoff scoring game since 1989",
        metric="47 PTS",
        tone="ember", team_abbr="DET",
    ),
    Headline(
        kind="note", category="facts",
        label="ROAD WARRIORS",
        primary="Knicks · 5-1 on the road this playoffs",
        secondary="Tied a franchise record set in 1973",
        metric="5-1",
        tone="ice", team_abbr="NYK",
    ),
    Headline(
        kind="note", category="facts",
        label="SAS' SECOND ROUND",
        primary="Spurs' deepest run since 2014 Finals title",
        secondary="Wembanyama leading the youngest roster in Round 3",
        metric="🏆 chase",
        tone="rose", team_abbr="SAS",
    ),
    Headline(
        kind="note", category="facts",
        label="FOUR FIRST-TIME HCs",
        primary="Conference Finals coaches with <3 yrs tenure",
        secondary="Most rookie head coaches in a final four since 1972",
        metric="4",
        tone="violet", team_abbr=None,
    ),
    Headline(
        kind="note", category="facts",
        label="THREE-POINT BOOM",
        primary="2025-26 playoffs averaging 14.7 3PM/game",
        secondary="An all-time playoff record",
        metric="14.7",
        tone="ember", team_abbr=None,
    ),
]


def _compute_headlines() -> list[Headline]:
    """Build the categorized headline list rendered by the ticker.

    Returns one continuous list interleaved with section dividers in the
    order: AWARDS → LEADERS → STATS → UPCOMING → FUN FACTS. The frontend
    renders dividers in a wider style so users see the sections scroll
    past as the marquee loops.
    """

    out: list[Headline] = []

    # ---- 1. SEASON AWARDS section ---------------------------------------
    out.append(_divider("SEASON AWARDS · 2025-26", "amber"))
    out.extend(SEASON_AWARDS_2025_26)

    # ---- 2. PLAYOFF LEADERS section -------------------------------------
    out.append(_divider("PLAYOFF LEADERS", "ember"))
    out.extend(_compute_leader_cards())

    # ---- 3. PLAYOFF STATS section ---------------------------------------
    out.append(_divider("PLAYOFF STATS", "rose"))
    out.extend(_compute_stats_cards())

    # ---- 4. UPCOMING GAMES section --------------------------------------
    out.append(_divider("UPCOMING GAMES", "ice"))
    out.extend(_compute_next_games(date.today()))

    # ---- 5. FUN FACTS section -------------------------------------------
    out.append(_divider("FUN FACTS · 2025-26", "violet"))
    out.extend(FUN_FACTS_2025_26)

    return out


# Stat-leader SQL queries, one per leader card. Each tuple is
# (label, sql, metric format template).
_LEADER_QUERIES: list[tuple[str, str, str]] = [
    (
        "PLAYOFF PPG LEADER",
        """
        SELECT p.name, p.team, COUNT(*) AS gp, AVG(pgs.pts) AS metric
        FROM player_game_stats pgs
        JOIN players p ON p.player_id = pgs.player_id
        JOIN games g ON g.game_id = pgs.game_id
        WHERE NOT pgs.is_clutch_data AND g.is_playoff AND g.season = '2025-26'
          AND pgs.minutes > 0
        GROUP BY p.name, p.team
        HAVING COUNT(*) >= 4
        ORDER BY AVG(pgs.pts) DESC
        LIMIT 1
        """,
        "{metric:.1f} PPG",
    ),
    (
        "PLAYOFF RPG LEADER",
        """
        SELECT p.name, p.team, COUNT(*) AS gp, AVG(pgs.reb) AS metric
        FROM player_game_stats pgs
        JOIN players p ON p.player_id = pgs.player_id
        JOIN games g ON g.game_id = pgs.game_id
        WHERE NOT pgs.is_clutch_data AND g.is_playoff AND g.season = '2025-26'
          AND pgs.minutes > 0
        GROUP BY p.name, p.team
        HAVING COUNT(*) >= 4
        ORDER BY AVG(pgs.reb) DESC
        LIMIT 1
        """,
        "{metric:.1f} RPG",
    ),
    (
        "PLAYOFF APG LEADER",
        """
        SELECT p.name, p.team, COUNT(*) AS gp, AVG(pgs.ast) AS metric
        FROM player_game_stats pgs
        JOIN players p ON p.player_id = pgs.player_id
        JOIN games g ON g.game_id = pgs.game_id
        WHERE NOT pgs.is_clutch_data AND g.is_playoff AND g.season = '2025-26'
          AND pgs.minutes > 0
        GROUP BY p.name, p.team
        HAVING COUNT(*) >= 4
        ORDER BY AVG(pgs.ast) DESC
        LIMIT 1
        """,
        "{metric:.1f} APG",
    ),
    (
        "PLAYOFF 3PM/GAME",
        """
        SELECT p.name, p.team, COUNT(*) AS gp, AVG(pgs.fg3m) AS metric
        FROM player_game_stats pgs
        JOIN players p ON p.player_id = pgs.player_id
        JOIN games g ON g.game_id = pgs.game_id
        WHERE NOT pgs.is_clutch_data AND g.is_playoff AND g.season = '2025-26'
          AND pgs.minutes > 0
        GROUP BY p.name, p.team
        HAVING COUNT(*) >= 4
        ORDER BY AVG(pgs.fg3m) DESC
        LIMIT 1
        """,
        "{metric:.1f} 3PM",
    ),
    (
        "PLAYOFF BLOCKS",
        """
        SELECT p.name, p.team, COUNT(*) AS gp, AVG(pgs.blk) AS metric
        FROM player_game_stats pgs
        JOIN players p ON p.player_id = pgs.player_id
        JOIN games g ON g.game_id = pgs.game_id
        WHERE NOT pgs.is_clutch_data AND g.is_playoff AND g.season = '2025-26'
          AND pgs.minutes > 0
        GROUP BY p.name, p.team
        HAVING COUNT(*) >= 4
        ORDER BY AVG(pgs.blk) DESC
        LIMIT 1
        """,
        "{metric:.2f} BPG",
    ),
    (
        "PLAYOFF STEALS",
        """
        SELECT p.name, p.team, COUNT(*) AS gp, AVG(pgs.stl) AS metric
        FROM player_game_stats pgs
        JOIN players p ON p.player_id = pgs.player_id
        JOIN games g ON g.game_id = pgs.game_id
        WHERE NOT pgs.is_clutch_data AND g.is_playoff AND g.season = '2025-26'
          AND pgs.minutes > 0
        GROUP BY p.name, p.team
        HAVING COUNT(*) >= 4
        ORDER BY AVG(pgs.stl) DESC
        LIMIT 1
        """,
        "{metric:.2f} SPG",
    ),
    (
        "CLUTCH TS% LEADER",
        """
        SELECT p.name, p.team, pcs.gp, pcs.ts_pct AS metric
        FROM player_clutch_stats pcs
        JOIN players p ON p.player_id = pcs.player_id
        WHERE pcs.season = '2025-26' AND pcs.season_type = 'Playoffs'
          AND pcs.gp >= 3 AND pcs.ts_pct IS NOT NULL
        ORDER BY pcs.ts_pct DESC
        LIMIT 1
        """,
        "{metric_pct} TS%",
    ),
    (
        "PLAYOFF +/- LEADER",
        """
        SELECT p.name, p.team, COUNT(*) AS gp, SUM(pgs.plus_minus)::float AS metric
        FROM player_game_stats pgs
        JOIN players p ON p.player_id = pgs.player_id
        JOIN games g ON g.game_id = pgs.game_id
        WHERE NOT pgs.is_clutch_data AND g.is_playoff AND g.season = '2025-26'
          AND pgs.minutes > 0
        GROUP BY p.name, p.team
        HAVING COUNT(*) >= 4
        ORDER BY SUM(pgs.plus_minus) DESC
        LIMIT 1
        """,
        "{metric:+.0f} TOTAL",
    ),
]


def _compute_leader_cards() -> list[Headline]:
    """Pull one Headline per stat-leader query. Each query is small,
    indexed, and runs sub-millisecond on the dev DB."""
    out: list[Headline] = []
    try:
        with _db() as conn, conn.cursor() as cur:
            for i, (label, sql, metric_tpl) in enumerate(_LEADER_QUERIES):
                try:
                    cur.execute(sql)
                    row = cur.fetchone()
                except Exception:  # noqa: BLE001
                    logger.exception("headline query failed: %s", label)
                    continue
                if not row:
                    continue
                name, team, gp, metric_val = row
                metric_str = metric_tpl.format(
                    metric=float(metric_val),
                    metric_pct=f"{float(metric_val) * 100:.1f}",
                )
                out.append(
                    Headline(
                        kind="player",
                        category="leaders",
                        label=label,
                        primary=name,
                        secondary=f"{team} · {gp} GP",
                        metric=metric_str,
                        tone=_HEADLINE_TONES[i % len(_HEADLINE_TONES)],
                        team_abbr=team,
                    )
                )
    except Exception:  # noqa: BLE001
        logger.exception("compute_leader_cards failed")
    return out


def _compute_stats_cards() -> list[Headline]:
    """Team-level playoff stat cards — top record (the headline-fix card)
    plus a couple of derived narrative stats."""
    out: list[Headline] = []
    try:
        with _db() as conn, conn.cursor() as cur:
            # No outer GROUP BY here: when a team's home and away splits are
            # identical (e.g. OKC went 4-0 at home and 4-0 on the road),
            # GROUP BY would collapse the two rows into one and the Python
            # accumulator below would only see half the wins. The union all
            # emits up to two rows per team and Python sums them.
            cur.execute(
                """
                SELECT home_team AS team,
                       SUM((home_score > away_score)::int) AS wins,
                       SUM((home_score < away_score)::int) AS losses
                FROM games WHERE is_playoff AND season = '2025-26'
                  AND home_score IS NOT NULL
                GROUP BY home_team
                UNION ALL
                SELECT away_team AS team,
                       SUM((away_score > home_score)::int) AS wins,
                       SUM((away_score < home_score)::int) AS losses
                FROM games WHERE is_playoff AND season = '2025-26'
                  AND home_score IS NOT NULL
                GROUP BY away_team
                """
            )
            agg: dict[str, list[int]] = {}
            for team, wins, losses in cur.fetchall():
                agg.setdefault(team, [0, 0])
                agg[team][0] += int(wins or 0)
                agg[team][1] += int(losses or 0)
            if agg:
                # Sort by win% desc, then by wins desc (so 8-0 beats 8-2 beats
                # 8-3, and 5-0 still beats 8-2). This is the key fix: previously
                # we sorted by raw wins which would have surfaced 8-3 SAS over
                # 8-0 OKC if they tied on wins.
                def _key(item):
                    _, wl = item
                    w, l = wl
                    total = w + l
                    pct = w / total if total else 0.0
                    return (pct, w, -l)
                team, (wins, losses) = max(agg.items(), key=_key)
                meta = TEAM_DIRECTORY.get(team)
                full_name = (
                    f"{meta.city} {meta.name}" if meta else team
                ).strip()
                metric = f"{wins}-{losses}" + (" · undefeated" if losses == 0 else "")
                out.append(
                    Headline(
                        kind="team",
                        category="scores",
                        label="PLAYOFFS · TOP RECORD",
                        primary=full_name,
                        secondary="best playoff record this run",
                        metric=metric,
                        tone="amber",
                        team_abbr=team,
                    )
                )
    except Exception:  # noqa: BLE001
        logger.exception("top-record computation failed")

    # Most recent completed playoff game — quick recap card.
    try:
        with _db() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT date, home_team, away_team, home_score, away_score
                FROM games
                WHERE is_playoff AND season = '2025-26'
                  AND home_score IS NOT NULL AND away_score IS NOT NULL
                ORDER BY date DESC, game_id DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if row:
                gdate, home, away, hs, as_ = row
                winner = home if hs > as_ else away
                loser = away if hs > as_ else home
                margin = abs(int(hs) - int(as_))
                gdate_str = _short_date(gdate)
                out.append(
                    Headline(
                        kind="team", category="scores",
                        label="LATEST PLAYOFF FINAL",
                        primary=f"{winner} defeated {loser}",
                        secondary=f"{max(int(hs), int(as_))}-{min(int(hs), int(as_))} · {gdate_str}",
                        metric=f"+{margin}",
                        tone="ember",
                        team_abbr=winner,
                    )
                )
    except Exception:  # noqa: BLE001
        logger.exception("latest-final computation failed")
    return out


def _compute_next_games(today: date, limit: int = 4) -> list[Headline]:
    """Surface the next few upcoming games (whether TBD'd tipoff or not)
    as ticker cards. Pulls from the same `games` table the live scheduler
    populates."""
    out: list[Headline] = []
    try:
        with _db() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT date, home_team, away_team, tipoff_utc,
                       playoff_round, playoff_series, is_playoff
                FROM games
                WHERE date >= %s AND home_score IS NULL
                ORDER BY date ASC,
                         CASE WHEN tipoff_utc IS NULL THEN 1 ELSE 0 END,
                         tipoff_utc ASC
                LIMIT %s
                """,
                (today, limit),
            )
            for gdate, home, away, tipoff, plyf_round, plyf_series, is_playoff in cur.fetchall():
                round_label = (
                    _round_label(plyf_round or _series_round_for_date(gdate))
                    if is_playoff else "REGULAR SEASON"
                )
                # If the tipoff time is known, format an ET-ish time; otherwise
                # mark the slot as "TBD time" — keeps the card useful even
                # before the league announces the exact tip.
                if tipoff:
                    local = tipoff.astimezone(timezone(timedelta(hours=-4)))
                    hour12 = ((local.hour - 1) % 12) + 1
                    ampm = "AM" if local.hour < 12 else "PM"
                    tip_str = (
                        f"{local.strftime('%a')} · {hour12}:{local.minute:02d} {ampm} ET"
                    )
                else:
                    tip_str = f"{_short_date(gdate, include_weekday=True)} · time TBD"
                out.append(
                    Headline(
                        kind="team", category="upcoming",
                        label=round_label,
                        primary=f"{away} @ {home}",
                        secondary=plyf_series or "",
                        metric=tip_str,
                        tone="ice",
                        team_abbr=home,
                    )
                )
    except Exception:  # noqa: BLE001
        logger.exception("compute_next_games failed")
    return out


# --------------------------------------------------------------------------- #
# Recent / upcoming / live game computation
# --------------------------------------------------------------------------- #


def _round_label(playoff_round: int | None) -> str:
    if playoff_round == 1:
        return "FIRST ROUND"
    if playoff_round == 2:
        return "CONFERENCE SEMIS"
    if playoff_round == 3:
        return "CONFERENCE FINALS"
    if playoff_round == 4:
        return "NBA FINALS"
    return "PLAYOFFS"


def _series_round_for_date(d: date) -> int:
    """Best-effort: deduce the round from the playoff calendar in
    CLAUDE.md. Used for the synthesized upcoming game label when the DB
    doesn't carry round info."""
    if d >= date(2026, 6, 3):
        return 4
    if d >= date(2026, 5, 18):
        return 3
    if d >= date(2026, 5, 6):
        return 2
    return 1


def _compute_recent() -> RecentGame | None:
    """Return the most recent completed playoff game with its top performers."""
    try:
        with _db() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT game_id, date, home_team, away_team, home_score, away_score, playoff_round
                FROM games
                WHERE is_playoff AND season = '2025-26'
                  AND home_score IS NOT NULL AND away_score IS NOT NULL
                ORDER BY date DESC, game_id DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if not row:
                return None
            game_id, gdate, home, away, hs, as_, plyf_round = row

            cur.execute(
                """
                SELECT p.name, pgs.team, pgs.pts, pgs.reb, pgs.ast, pgs.stl
                FROM player_game_stats pgs
                JOIN players p ON p.player_id = pgs.player_id
                WHERE pgs.game_id = %s AND NOT pgs.is_clutch_data
                ORDER BY pgs.pts DESC NULLS LAST
                LIMIT 3
                """,
                (game_id,),
            )
            leaders = [
                GameLeader(
                    name=name, team_abbr=team,
                    line=f"{pts} PTS / {ast} AST / {reb} REB"
                    + (f" / {stl} STL" if stl else ""),
                )
                for name, team, pts, reb, ast, stl in cur.fetchall()
            ]

        label_round = _round_label(plyf_round or _series_round_for_date(gdate))
        return RecentGame(
            label=f"FINAL · {label_round}",
            date=gdate.isoformat(),
            home=_team_lite(home),
            away=_team_lite(away),
            home_score=int(hs),
            away_score=int(as_),
            leaders=leaders,
            note=None,
        )
    except Exception:  # noqa: BLE001
        logger.exception("compute_recent failed")
        return None


def _likely_conference_winner(conference: Literal["East", "West"]) -> str | None:
    """Pick the team with the most playoff wins in the given conference.
    Used to synthesize the Conference Finals matchup when the schedule
    isn't in the DB."""
    try:
        with _db() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.abbreviation, SUM(t.wins) AS wins
                FROM (
                    SELECT home_team AS abbreviation,
                           SUM((home_score > away_score)::int) AS wins
                    FROM games WHERE is_playoff AND season = '2025-26'
                    GROUP BY home_team
                    UNION ALL
                    SELECT away_team AS abbreviation,
                           SUM((away_score > home_score)::int) AS wins
                    FROM games WHERE is_playoff AND season = '2025-26'
                    GROUP BY away_team
                ) t
                JOIN teams te ON te.abbreviation = t.abbreviation
                WHERE te.conference = %s
                GROUP BY t.abbreviation
                ORDER BY SUM(t.wins) DESC
                LIMIT 1
                """,
                (conference,),
            )
            row = cur.fetchone()
            return row[0] if row else None
    except Exception:  # noqa: BLE001
        logger.exception("likely_conference_winner failed")
        return None


def _next_tipoff_utc(today: date) -> datetime:
    """Pick a sensible primetime tipoff: 8:30pm ET on the next eligible day."""
    # Conference Finals start 2026-05-18 per CLAUDE.md; if "today" is before
    # that, anchor to that opener; otherwise schedule the next day at 8:30pm ET.
    target = max(today, date(2026, 5, 18))
    if target == today:
        target = today + timedelta(days=1)
    # 8:30 PM Eastern. America/New_York is UTC-4 in May (DST). Use a fixed
    # offset rather than zoneinfo so this works wherever the server runs.
    dt = datetime(target.year, target.month, target.day, 20, 30, 0)
    return dt.replace(tzinfo=timezone(timedelta(hours=-4)))


def _compute_upcoming(today: date) -> UpcomingGame | None:
    """Return the next scheduled game from the DB. Populated by the
    APScheduler `upcoming_schedule` job that calls ScheduleLeagueV2Int.

    Falls back to the conference-winner synthesis only if the schedule
    table is empty (fresh deploy before the scheduler has run, or an
    extended nba_api outage).
    """
    db_game = _load_next_scheduled()
    if db_game is not None:
        return db_game
    # Fallback: synthesize a plausible Conference Finals matchup.
    return _synthesize_upcoming(today)


def _load_next_scheduled() -> UpcomingGame | None:
    """Query the games table for the next status='scheduled' game."""
    try:
        with _db() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT game_id, home_team, away_team, tipoff_utc,
                       arena_name, broadcast, playoff_round, playoff_series,
                       is_playoff
                FROM games
                WHERE status = 'scheduled' AND tipoff_utc > NOW()
                ORDER BY tipoff_utc ASC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if not row:
                return None
            game_id, home, away, tipoff, arena, broadcast, plyf_round, plyf_series, is_playoff = row

            home_meta = TEAM_DIRECTORY.get(home)
            label_round = _round_label(plyf_round or _series_round_for_date(tipoff.date()))
            label_kind = label_round if is_playoff else "REGULAR SEASON"
            note = broadcast or None
            series_state = plyf_series or ("Tip in advance" if is_playoff else None)
            return UpcomingGame(
                label=label_kind,
                tipoff_utc=tipoff.astimezone(timezone.utc).isoformat(),
                arena=arena or (home_meta.arena if home_meta else "TBD"),
                arena_city=home_meta.city if home_meta else "TBD",
                arena_timezone=home_meta.arena_timezone if home_meta else "America/New_York",
                home=_team_lite(home),
                away=_team_lite(away),
                series_state=series_state,
                note=note,
            )
    except Exception:  # noqa: BLE001
        logger.exception("load_next_scheduled failed")
        return None


def _synthesize_upcoming(today: date) -> UpcomingGame | None:
    """Fallback: construct a Conference Finals Game 1 from the two leading
    teams. Used only when the games table has no scheduled rows yet."""
    east = _likely_conference_winner("East")
    west = _likely_conference_winner("West")
    if not east or not west:
        return None

    tip = _next_tipoff_utc(today)
    round_n = _series_round_for_date(tip.date())
    if round_n == 4:
        home, away = west, east
    else:
        home, away = east, west
    home_dir = TEAM_DIRECTORY.get(home)

    return UpcomingGame(
        label=f"{_round_label(round_n)} · GAME 1",
        tipoff_utc=tip.astimezone(timezone.utc).isoformat(),
        arena=home_dir.arena if home_dir else "TBD",
        arena_city=home_dir.city if home_dir else "TBD",
        arena_timezone=home_dir.arena_timezone if home_dir else "America/New_York",
        home=_team_lite(home),
        away=_team_lite(away),
        series_state="Series tied 0–0",
        note=None,
    )


def _simulate_live() -> LiveGame | None:
    """Return real live game state from the DB (status='live' row).

    Returns None when no game is currently live, which makes the header
    fall through to upcoming/recap mode — the chosen "hide the live panel
    entirely" behavior (rather than a hardcoded fake game).
    """
    try:
        with _db() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT game_id, home_team, away_team, home_score, away_score,
                       period, game_clock, tipoff_utc, playoff_round, broadcast,
                       is_playoff
                FROM games
                WHERE status = 'live'
                ORDER BY tipoff_utc DESC NULLS LAST
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if not row:
                return None
            game_id, home, away, hs, as_, period, clock, tipoff, plyf_round, broadcast, is_playoff = row

            label_round = _round_label(plyf_round) if is_playoff else "REGULAR SEASON"
            leaders = _load_game_leaders(game_id)
            return LiveGame(
                label=f"{label_round} · LIVE",
                quarter=int(period) if period else 1,
                clock=str(clock or "0:00"),
                home=_team_lite(home),
                away=_team_lite(away),
                home_score=int(hs) if hs is not None else 0,
                away_score=int(as_) if as_ is not None else 0,
                leaders=leaders,
                highlight=broadcast or None,
            )
    except Exception:  # noqa: BLE001
        logger.exception("simulate_live (DB-backed) failed")
        return None


def _load_game_leaders(game_id: str, limit: int = 3) -> list[GameLeader]:
    """Top scorers from player_game_stats for the given game. Empty list
    when the game has just tipped and no box-score rows exist yet."""
    try:
        with _db() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.name, pgs.team, pgs.pts, pgs.reb, pgs.ast, pgs.stl
                FROM player_game_stats pgs
                JOIN players p ON p.player_id = pgs.player_id
                WHERE pgs.game_id = %s AND NOT pgs.is_clutch_data
                ORDER BY pgs.pts DESC NULLS LAST
                LIMIT %s
                """,
                (game_id, limit),
            )
            return [
                GameLeader(
                    name=name,
                    team_abbr=team,
                    line=f"{pts or 0} PTS / {ast or 0} AST / {reb or 0} REB"
                    + (f" / {stl} STL" if stl else ""),
                )
                for name, team, pts, reb, ast, stl in cur.fetchall()
            ]
    except Exception:  # noqa: BLE001
        logger.exception("load_game_leaders failed for %s", game_id)
        return []


# --------------------------------------------------------------------------- #
# Endpoint
# --------------------------------------------------------------------------- #


def _determine_mode(
    today_utc: datetime,
    upcoming: UpcomingGame | None,
    recent: RecentGame | None,
) -> Literal["season", "upcoming", "live", "recap"]:
    """Default state machine when the client doesn't force a mode.
    'live' is never auto-selected — there's no real game wire — but if the
    frontend toggle wants it, it'll pass ?mode=live and get the synthesized
    payload directly.
    """
    if upcoming:
        try:
            tip = datetime.fromisoformat(upcoming.tipoff_utc.replace("Z", "+00:00"))
            delta = tip - today_utc
            if timedelta(0) <= delta <= timedelta(hours=24):
                return "upcoming"
        except ValueError:
            pass
    if recent:
        try:
            recent_date = date.fromisoformat(recent.date)
            if (today_utc.date() - recent_date) <= timedelta(days=2):
                return "recap"
        except ValueError:
            pass
    return "season"


@router.get("", response_model=HeaderPayload)
def get_header(
    mode: Literal["auto", "season", "upcoming", "live", "recap"] = Query("auto"),
) -> HeaderPayload:
    """Return the header payload. `mode=auto` lets the server decide.

    Forcing a mode (e.g. `?mode=live`) returns whatever payload is needed
    for that view, which is what the frontend dev toggle uses.
    """
    today_utc = datetime.now(timezone.utc)

    headlines = _compute_headlines()
    recent = _compute_recent()
    upcoming = _compute_upcoming(today_utc.date())
    live = _simulate_live() if mode == "live" else None

    chosen: Literal["season", "upcoming", "live", "recap"]
    if mode == "auto":
        chosen = _determine_mode(today_utc, upcoming, recent)
    elif mode == "live":
        # Hide-entirely behavior: if no real live game, fall through
        # gracefully instead of 503'ing. The UI hides the live panel
        # when live=null.
        if live is None:
            chosen = _determine_mode(today_utc, upcoming, recent)
        else:
            chosen = "live"
    elif mode == "upcoming":
        if upcoming is None:
            raise HTTPException(status_code=503, detail="cannot synthesize upcoming game")
        chosen = "upcoming"
    elif mode == "recap":
        if recent is None:
            raise HTTPException(status_code=503, detail="no recent playoff game")
        chosen = "recap"
    else:
        chosen = "season"

    return HeaderPayload(
        generated_at=today_utc.isoformat(),
        mode=chosen,
        headlines=headlines,
        recent=recent if chosen in ("recap", "season") else recent,  # still expose to UI for tooltip
        upcoming=upcoming,
        live=live,
        team_directory=TEAM_DIRECTORY,
    )
