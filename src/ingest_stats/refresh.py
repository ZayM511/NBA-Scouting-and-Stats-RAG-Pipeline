"""Daily refresh orchestrator.

Schedule this via cron, GitHub Actions, or a desktop scheduler during the
playoffs. It pulls the latest games and player game stats. Teams and players
are refreshed less often (weekly), which the CLI exposes separately.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.ingest_stats.games import sync_games
from src.ingest_stats.player_game_stats import sync_player_game_stats

logger = logging.getLogger(__name__)


@dataclass
class RefreshResult:
    games_regular: int
    games_playoff: int
    stats_regular: int
    stats_playoff: int

    @property
    def total(self) -> int:
        return self.games_regular + self.games_playoff + self.stats_regular + self.stats_playoff


def daily_refresh(season: str = "2025-26") -> RefreshResult:
    """Refresh games + per-player box scores for both season types.

    Idempotent: re-running on the same day produces the same DB state. The
    UPSERTs handle in-progress games (the second run updates the score).
    """
    logger.info("daily_refresh starting for season %s", season)

    games_reg = sync_games(season=season, season_type="Regular Season")
    games_po = sync_games(season=season, season_type="Playoffs")
    stats_reg = sync_player_game_stats(season=season, season_type="Regular Season")
    stats_po = sync_player_game_stats(season=season, season_type="Playoffs")

    result = RefreshResult(
        games_regular=games_reg,
        games_playoff=games_po,
        stats_regular=stats_reg,
        stats_playoff=stats_po,
    )
    logger.info(
        "daily_refresh complete: %d total rows touched "
        "(games_reg=%d games_po=%d stats_reg=%d stats_po=%d)",
        result.total,
        result.games_regular,
        result.games_playoff,
        result.stats_regular,
        result.stats_playoff,
    )
    return result
