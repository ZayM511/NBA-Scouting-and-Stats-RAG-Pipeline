"""Tests for the deterministic scorers (route accuracy, keyword recall,
hallucination guard) and the judge-output parser. Mocks Anthropic so
these tests don't hit the network."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.eval.cases import EvalCase
from src.eval.scorers import (
    _parse_judge_output,
    score_hallucination_guard,
    score_keyword_recall,
    score_route_accuracy,
)


@dataclass
class FakeRoute:
    route: str


@dataclass
class FakeResult:
    answer: str
    route: FakeRoute = None  # type: ignore[assignment]


def _case(**kw) -> EvalCase:
    defaults = {
        "id": "test-01",
        "question": "Q?",
        "expected_route": "stats",
        "difficulty": "easy",
        "must_mention": (),
        "must_not_mention": (),
        "rubric": "Test rubric.",
        "notes": "",
    }
    defaults.update(kw)
    return EvalCase(**defaults)


# ----------------------------------------------------------------------------
# route accuracy
# ----------------------------------------------------------------------------


def test_route_accuracy_matches() -> None:
    case = _case(expected_route="stats")
    result = FakeResult(answer="", route=FakeRoute(route="stats"))
    assert score_route_accuracy(case, result) == 1.0  # type: ignore[arg-type]


def test_route_accuracy_mismatches() -> None:
    case = _case(expected_route="stats")
    result = FakeResult(answer="", route=FakeRoute(route="prose"))
    assert score_route_accuracy(case, result) == 0.0  # type: ignore[arg-type]


# ----------------------------------------------------------------------------
# keyword recall
# ----------------------------------------------------------------------------


def test_keyword_recall_all_present() -> None:
    case = _case(must_mention=("curry", "wemby"))
    assert score_keyword_recall(case, "Steph Curry and Wemby both scored.") == 1.0


def test_keyword_recall_partial() -> None:
    case = _case(must_mention=("curry", "wemby", "lebron"))
    score = score_keyword_recall(case, "Steph Curry and Wemby scored.")
    assert abs(score - 2 / 3) < 1e-9


def test_keyword_recall_none_present() -> None:
    case = _case(must_mention=("curry",))
    assert score_keyword_recall(case, "Wemby had 5 blocks.") == 0.0


def test_keyword_recall_case_insensitive() -> None:
    case = _case(must_mention=("CURRY",))
    assert score_keyword_recall(case, "curry scored 30") == 1.0


def test_keyword_recall_empty_must_mention_is_full_credit() -> None:
    case = _case(must_mention=())
    assert score_keyword_recall(case, "anything") == 1.0


# ----------------------------------------------------------------------------
# hallucination guard
# ----------------------------------------------------------------------------


def test_hallucination_guard_clean_answer() -> None:
    case = _case(must_not_mention=("retired",))
    assert score_hallucination_guard(case, "Wemby blocked 5 shots.") == 1.0


def test_hallucination_guard_catches_forbidden_word() -> None:
    case = _case(must_not_mention=("retired",))
    assert score_hallucination_guard(case, "LeBron retired this season.") == 0.0


def test_hallucination_guard_empty_must_not_mention_is_full_credit() -> None:
    case = _case(must_not_mention=())
    assert score_hallucination_guard(case, "anything") == 1.0


def test_hallucination_guard_case_insensitive() -> None:
    case = _case(must_not_mention=("RETIRED",))
    assert score_hallucination_guard(case, "He retired in 2023") == 0.0


# ----------------------------------------------------------------------------
# judge output parsing
# ----------------------------------------------------------------------------


def test_parse_judge_output_well_formed() -> None:
    text = "SCORE: 0.75\nREASONING: Mostly correct, missed one citation."
    score, reasoning = _parse_judge_output(text)
    assert score == 0.75
    assert "Mostly correct" in reasoning


def test_parse_judge_output_clamps_above_one() -> None:
    score, _ = _parse_judge_output("SCORE: 1.5\nREASONING: ok")
    assert score == 1.0


def test_parse_judge_output_clamps_below_zero() -> None:
    score, _ = _parse_judge_output("SCORE: -0.2\nREASONING: ok")
    assert score == 0.0


def test_parse_judge_output_handles_missing_score() -> None:
    score, reasoning = _parse_judge_output("REASONING: no score given")
    assert score == 0.5  # default
    assert reasoning


def test_parse_judge_output_handles_garbage() -> None:
    score, reasoning = _parse_judge_output("the model wrote prose without the labels")
    assert score == 0.5
    assert "the model wrote prose" in reasoning
