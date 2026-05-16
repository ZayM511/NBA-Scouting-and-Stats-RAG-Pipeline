"""CLI for stats ingestion.

Usage:
    uv run python -m src.ingest_stats.cli bootstrap          # one-time: teams + players + every game so far
    uv run python -m src.ingest_stats.cli refresh            # daily playoff refresh
    uv run python -m src.ingest_stats.cli teams
    uv run python -m src.ingest_stats.cli players
    uv run python -m src.ingest_stats.cli games --season-type Playoffs
    uv run python -m src.ingest_stats.cli player-game-stats --season-type Playoffs
"""

from __future__ import annotations

import logging
import sys

import typer
from rich.console import Console

from src.ingest_stats.games import sync_games
from src.ingest_stats.player_game_stats import sync_player_game_stats
from src.ingest_stats.players import sync_active_players
from src.ingest_stats.refresh import daily_refresh
from src.ingest_stats.teams import sync_teams

console = Console()
app = typer.Typer(help="Stats ingestion via nba_api.")

DEFAULT_SEASON = "2025-26"


def _configure_logging() -> None:
    from src.config import get_settings

    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@app.command()
def teams() -> None:
    """Refresh the 30 NBA teams. Run once per season."""
    _configure_logging()
    n = sync_teams()
    console.print(f"[green]Upserted {n} teams.[/]")


@app.command()
def players(season: str = DEFAULT_SEASON) -> None:
    """Refresh active players for the given season."""
    _configure_logging()
    n = sync_active_players(season=season)
    console.print(f"[green]Upserted {n} players for {season}.[/]")


@app.command()
def games(
    season: str = DEFAULT_SEASON,
    season_type: str = typer.Option("Regular Season", help='"Regular Season" or "Playoffs".'),
) -> None:
    """Refresh games for the given season + season_type."""
    _configure_logging()
    n = sync_games(season=season, season_type=season_type)
    console.print(f"[green]Upserted {n} games ({season}, {season_type}).[/]")


@app.command("player-game-stats")
def player_game_stats(
    season: str = DEFAULT_SEASON,
    season_type: str = typer.Option("Regular Season", help='"Regular Season" or "Playoffs".'),
) -> None:
    """Refresh per-player box scores for the given season + season_type."""
    _configure_logging()
    n = sync_player_game_stats(season=season, season_type=season_type)
    console.print(
        f"[green]Upserted {n} player-game rows ({season}, {season_type}).[/]"
    )


@app.command()
def refresh(season: str = DEFAULT_SEASON) -> None:
    """Daily refresh: games + player game stats for both season types.

    Idempotent. Schedule daily during the playoffs.
    """
    _configure_logging()
    result = daily_refresh(season=season)
    console.print(
        "[green]daily_refresh complete:[/] "
        f"games(reg)={result.games_regular} "
        f"games(po)={result.games_playoff} "
        f"stats(reg)={result.stats_regular} "
        f"stats(po)={result.stats_playoff}"
    )


@app.command()
def bootstrap(season: str = DEFAULT_SEASON) -> None:
    """One-time: teams + players + every game so far + every box score so far."""
    _configure_logging()
    console.print("[cyan]1/4[/] sync_teams ...")
    n_teams = sync_teams()
    console.print(f"[green]ok[/] {n_teams} teams")

    console.print(f"[cyan]2/4[/] sync_active_players({season}) ...")
    n_players = sync_active_players(season=season)
    console.print(f"[green]ok[/] {n_players} players")

    console.print(f"[cyan]3/4[/] sync_games({season}, both) ...")
    g_reg = sync_games(season=season, season_type="Regular Season")
    g_po = sync_games(season=season, season_type="Playoffs")
    console.print(f"[green]ok[/] {g_reg} regular, {g_po} playoff games")

    console.print(f"[cyan]4/4[/] sync_player_game_stats({season}, both) ...")
    s_reg = sync_player_game_stats(season=season, season_type="Regular Season")
    s_po = sync_player_game_stats(season=season, season_type="Playoffs")
    console.print(f"[green]ok[/] {s_reg} regular stat rows, {s_po} playoff stat rows")

    console.print("[bold green]bootstrap complete[/]")


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main() or 0)
