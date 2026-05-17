"""Tests for the eval case set itself — stratification, well-formedness."""

from __future__ import annotations

from collections import Counter

import pytest

from src.eval.cases import (
    ALL_CASES,
    HYBRID_CASES,
    PROSE_CASES,
    STATS_CASES,
    cases_by_route,
)


def test_total_is_thirty() -> None:
    assert len(ALL_CASES) == 30


def test_stratified_ten_per_route() -> None:
    assert len(STATS_CASES) == 10
    assert len(PROSE_CASES) == 10
    assert len(HYBRID_CASES) == 10


def test_no_duplicate_case_ids() -> None:
    ids = [c.id for c in ALL_CASES]
    duplicates = [i for i, n in Counter(ids).items() if n > 1]
    assert duplicates == [], f"duplicate case_ids: {duplicates}"


def test_every_case_has_rubric() -> None:
    missing = [c.id for c in ALL_CASES if not c.rubric.strip()]
    assert missing == [], f"cases missing rubric: {missing}"


def test_every_case_has_nonempty_question() -> None:
    for c in ALL_CASES:
        assert c.question and c.question.strip(), f"empty question on {c.id}"


def test_difficulty_distribution_is_reasonable() -> None:
    counts = Counter(c.difficulty for c in ALL_CASES)
    # At least one of each difficulty across the set.
    for d in ("easy", "medium", "hard"):
        assert counts[d] >= 1, f"no cases at difficulty={d}"


def test_expected_route_matches_per_route_tuple() -> None:
    for c in STATS_CASES:
        assert c.expected_route == "stats"
    for c in PROSE_CASES:
        assert c.expected_route == "prose"
    for c in HYBRID_CASES:
        assert c.expected_route == "hybrid"


def test_cases_by_route_returns_correct_subset() -> None:
    assert cases_by_route("stats") == STATS_CASES
    assert cases_by_route("prose") == PROSE_CASES
    assert cases_by_route("hybrid") == HYBRID_CASES


def test_case_ids_use_route_prefix() -> None:
    for c in STATS_CASES:
        assert c.id.startswith("stats-"), f"bad id: {c.id}"
    for c in PROSE_CASES:
        assert c.id.startswith("prose-"), f"bad id: {c.id}"
    for c in HYBRID_CASES:
        assert c.id.startswith("hybrid-"), f"bad id: {c.id}"
