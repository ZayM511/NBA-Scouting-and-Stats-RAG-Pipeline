"""Unit tests for the pure parts of select_top30 (apply validation +
ranking dataclass). The DB-touching parts are covered by integration runs."""

from __future__ import annotations

import pytest

from src.normalize_entities.select_top30 import PlayerRanking, apply_top30


def test_player_ranking_is_immutable() -> None:
    r = PlayerRanking(
        rank=1, player_id=2544, name="LeBron James", team="LAL",
        games=70, ppg=25.0, rpg=8.0, apg=8.0, spg=1.2, bpg=0.6,
        tspct=0.60, plus_minus_per_game=5.0, score=42.7,
    )
    with pytest.raises(Exception):  # frozen dataclass
        r.rank = 2  # type: ignore[misc]


def test_apply_rejects_wrong_count() -> None:
    with pytest.raises(ValueError, match="expected exactly 30 player_ids"):
        apply_top30([1, 2, 3])

    with pytest.raises(ValueError, match="expected exactly 30 player_ids"):
        apply_top30(list(range(40)))


def test_apply_rejects_empty() -> None:
    with pytest.raises(ValueError, match="expected exactly 30 player_ids"):
        apply_top30([])
