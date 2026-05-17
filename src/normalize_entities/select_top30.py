"""Pick the top-30 players for the season and flag them `is_top30 = TRUE`.

The flag drives deep-dive enrichment: play-by-play ingest, advanced splits,
and the per-player authored scouting summary.

Selection is a composite score per game, weighted to approximate a simple
"impact per minute" without needing the advanced metrics (we don't have
USG%, ORTG, DRTG ingested yet — those come with the play-by-play pass).

The score per game is:

    score = pts + 0.8*reb + 1.2*ast + 2*stl + 2*blk
            - 0.8*tov - 0.5*missed_fg - 0.4*missed_ft

Per-game averages are computed across regular-season + playoff games for
players with at least `min_games`. We rank by composite per-game score, not
volume, so players who missed time but played well still appear.

Usage:
    uv run python -m src.normalize_entities.select_top30 list           # top 50, print to terminal
    uv run python -m src.normalize_entities.select_top30 apply <id> <id> ... <id>   # set is_top30=TRUE for given player_ids
    uv run python -m src.normalize_entities.select_top30 status         # show current is_top30 players
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import psycopg
import typer
from psycopg.rows import dict_row
from rich.console import Console
from rich.table import Table

from src.config import get_settings

console = Console()
app = typer.Typer(help="Select and apply the top-30 player flag.")


# ---------------------------------------------------------------------------
# Composite score
# ---------------------------------------------------------------------------

DEFAULT_MIN_GAMES = 25


@dataclass(frozen=True)
class PlayerRanking:
    rank: int
    player_id: int
    name: str
    team: str | None
    games: int
    ppg: float
    rpg: float
    apg: float
    spg: float
    bpg: float
    tspct: float
    plus_minus_per_game: float
    score: float


def rank_players(min_games: int = DEFAULT_MIN_GAMES, limit: int = 50) -> list[PlayerRanking]:
    """Query player_game_stats, compute the composite per-game score, return
    the top `limit` players who played at least `min_games`.
    """
    settings = get_settings()
    sql = """
        WITH agg AS (
            SELECT
                pgs.player_id,
                COUNT(*) AS games,
                AVG(pgs.pts)                       AS ppg,
                AVG(pgs.reb)                       AS rpg,
                AVG(pgs.ast)                       AS apg,
                AVG(pgs.stl)                       AS spg,
                AVG(pgs.blk)                       AS bpg,
                AVG(pgs.ts_pct)                    AS tspct,
                AVG(pgs.plus_minus)                AS plus_minus_per_game,
                AVG(pgs.tov)                       AS topg,
                AVG(COALESCE(pgs.fga, 0) - COALESCE(pgs.fgm, 0)) AS missed_fg_per_game,
                AVG(COALESCE(pgs.fta, 0) - COALESCE(pgs.ftm, 0)) AS missed_ft_per_game,
                MODE() WITHIN GROUP (ORDER BY pgs.team) AS team
            FROM player_game_stats pgs
            WHERE NOT pgs.is_clutch_data
            GROUP BY pgs.player_id
            HAVING COUNT(*) >= %s
        ),
        scored AS (
            SELECT
                a.*,
                (
                    a.ppg
                    + 0.8 * a.rpg
                    + 1.2 * a.apg
                    + 2.0 * a.spg
                    + 2.0 * a.bpg
                    - 0.8 * a.topg
                    - 0.5 * a.missed_fg_per_game
                    - 0.4 * a.missed_ft_per_game
                ) AS score
            FROM agg a
        )
        SELECT
            ROW_NUMBER() OVER (ORDER BY s.score DESC) AS rank,
            s.player_id,
            p.name,
            s.team,
            s.games,
            ROUND(s.ppg::numeric, 1)::float                AS ppg,
            ROUND(s.rpg::numeric, 1)::float                AS rpg,
            ROUND(s.apg::numeric, 1)::float                AS apg,
            ROUND(s.spg::numeric, 1)::float                AS spg,
            ROUND(s.bpg::numeric, 1)::float                AS bpg,
            COALESCE(ROUND(s.tspct::numeric, 3)::float, 0) AS tspct,
            ROUND(s.plus_minus_per_game::numeric, 1)::float AS plus_minus_per_game,
            ROUND(s.score::numeric, 2)::float              AS score
        FROM scored s
        JOIN players p ON p.player_id = s.player_id
        ORDER BY s.score DESC
        LIMIT %s
    """
    with psycopg.connect(str(settings.postgres_url), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (min_games, limit))
            rows = cur.fetchall()
    return [PlayerRanking(**row) for row in rows]


# ---------------------------------------------------------------------------
# Apply / status
# ---------------------------------------------------------------------------


def apply_top30(player_ids: list[int]) -> int:
    """Set `is_top30 = TRUE` for every player_id in the list, FALSE for
    everyone else. Returns the count of players flagged."""
    if len(player_ids) != 30:
        raise ValueError(f"expected exactly 30 player_ids, got {len(player_ids)}")

    settings = get_settings()
    with psycopg.connect(str(settings.postgres_url), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            # First confirm every id is a real player.
            cur.execute(
                "SELECT player_id FROM players WHERE player_id = ANY(%s)",
                (player_ids,),
            )
            found = {r["player_id"] for r in cur.fetchall()}
            missing = set(player_ids) - found
            if missing:
                raise ValueError(f"player_ids not found in `players`: {sorted(missing)}")

            # Reset everyone, flag the chosen 30.
            cur.execute("UPDATE players SET is_top30 = FALSE WHERE is_top30 = TRUE")
            cur.execute(
                "UPDATE players SET is_top30 = TRUE WHERE player_id = ANY(%s)",
                (player_ids,),
            )
            conn.commit()
    return len(player_ids)


def current_top30() -> list[dict]:
    settings = get_settings()
    with psycopg.connect(str(settings.postgres_url), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT player_id, name, team FROM players WHERE is_top30 = TRUE ORDER BY name"
            )
            return list(cur.fetchall())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_ranking_table(rankings: list[PlayerRanking], highlight_top: int = 30) -> None:
    table = Table(title=f"Player ranking (composite per-game score, top {len(rankings)})")
    for col, justify in [
        ("#", "right"),
        ("player_id", "right"),
        ("Name", "left"),
        ("Team", "left"),
        ("G", "right"),
        ("PPG", "right"),
        ("RPG", "right"),
        ("APG", "right"),
        ("SPG", "right"),
        ("BPG", "right"),
        ("TS%", "right"),
        ("+/-/g", "right"),
        ("Score", "right"),
    ]:
        table.add_column(col, justify=justify)

    for r in rankings:
        style = "bold cyan" if r.rank <= highlight_top else "dim"
        table.add_row(
            str(r.rank),
            str(r.player_id),
            r.name,
            r.team or "?",
            str(r.games),
            f"{r.ppg:.1f}",
            f"{r.rpg:.1f}",
            f"{r.apg:.1f}",
            f"{r.spg:.1f}",
            f"{r.bpg:.1f}",
            f"{r.tspct:.3f}",
            f"{r.plus_minus_per_game:+.1f}",
            f"{r.score:.2f}",
            style=style,
        )
    console.print(table)


@app.command()
def list_top(
    limit: int = typer.Option(50, help="How many ranked rows to print."),
    min_games: int = typer.Option(DEFAULT_MIN_GAMES, help="Minimum games played to qualify."),
) -> None:
    """Print the top `limit` players by composite score (cyan = top 30 default)."""
    rankings = rank_players(min_games=min_games, limit=limit)
    if not rankings:
        console.print("[red]No rankings produced. Did you run `bootstrap` first?[/]")
        raise typer.Exit(code=1)
    _print_ranking_table(rankings)
    console.print(
        f"\n[dim]To apply a specific list of player_ids, run:[/]\n"
        f"  uv run python -m src.normalize_entities.select_top30 apply <id1> <id2> ... <id30>"
    )


@app.command()
def apply(player_ids: list[int] = typer.Argument(..., help="Exactly 30 player_ids.")) -> None:
    """Flag exactly 30 player_ids as is_top30=TRUE (and clear all others)."""
    n = apply_top30(player_ids)
    console.print(f"[green]Flagged {n} players as is_top30 = TRUE.[/]")


@app.command()
def status() -> None:
    """Print the players currently flagged is_top30 = TRUE."""
    rows = current_top30()
    if not rows:
        console.print("[yellow]No players are currently flagged is_top30 = TRUE.[/]")
        return
    table = Table(title=f"is_top30 = TRUE ({len(rows)} players)")
    table.add_column("player_id", justify="right")
    table.add_column("Name")
    table.add_column("Team")
    for r in rows:
        table.add_row(str(r["player_id"]), r["name"], r["team"] or "?")
    console.print(table)


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main() or 0)
