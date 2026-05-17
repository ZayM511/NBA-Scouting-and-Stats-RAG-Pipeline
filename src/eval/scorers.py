"""Eval scorers.

Three scorers compose into the final score per case:

  - route_accuracy: 1.0 if the predicted route matches the expected
    route, 0.0 otherwise. Single integer; not LLM-graded.

  - keyword_recall: fraction of `must_mention` substrings that appear
    in the answer (case-insensitive). Catches obvious hallucinations
    where the answer is about the wrong topic.

  - hallucination_guard: 1.0 if NO `must_not_mention` substrings appear,
    0.0 if any do. Single integer.

  - judge: Claude-as-judge using the per-case rubric. Returns 0-1.
    Slow + costs tokens; runs last so we can short-circuit if cheaper
    scorers already pinned the case as failing.

Aggregate per-case score = (route_accuracy + keyword_recall +
hallucination_guard + judge) / 4, with each component in [0, 1].
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import anthropic

from src.config import get_settings
from src.eval.cases import EvalCase
from src.guardrails import Model, guarded_call, record_usage
from src.synthesize.pipeline import AskResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoreBreakdown:
    """All component scores for one eval case."""

    route_accuracy: float
    keyword_recall: float
    hallucination_guard: float
    judge_score: float
    judge_reasoning: str

    @property
    def aggregate(self) -> float:
        return (
            self.route_accuracy
            + self.keyword_recall
            + self.hallucination_guard
            + self.judge_score
        ) / 4.0


# --------------------------------------------------------------------------- #
# Cheap deterministic scorers (no LLM call)
# --------------------------------------------------------------------------- #


def score_route_accuracy(case: EvalCase, result: AskResult) -> float:
    return 1.0 if result.route.route == case.expected_route else 0.0


def score_keyword_recall(case: EvalCase, answer_text: str) -> float:
    if not case.must_mention:
        return 1.0  # nothing to look for → vacuously satisfied
    lower = answer_text.lower()
    hits = sum(1 for m in case.must_mention if m.lower() in lower)
    return hits / len(case.must_mention)


def score_hallucination_guard(case: EvalCase, answer_text: str) -> float:
    if not case.must_not_mention:
        return 1.0
    lower = answer_text.lower()
    if any(m.lower() in lower for m in case.must_not_mention):
        return 0.0
    return 1.0


# --------------------------------------------------------------------------- #
# LLM-as-judge
# --------------------------------------------------------------------------- #


JUDGE_SYSTEM_PROMPT = """\
You are an evaluator grading answers from an NBA scouting + stats RAG
system. For each case you receive: the user's question, an expected
rubric describing what a good answer covers, and the system's actual
answer.

Score the answer on a 0.0-1.0 scale:
  1.0  fully meets the rubric (correct, specific, well-cited if prose)
  0.75 mostly meets it but with a small omission or vague claim
  0.5  partial — touches the topic but misses key elements
  0.25 wrong topic or invented facts but acknowledges uncertainty
  0.0  hallucinated, off-topic, or factually wrong without acknowledgment

For PROSE answers, give credit only when the answer includes inline
[^N] citations. An uncited prose claim is treated as 0.25 at best.

For STATS answers, the SQL itself is the citation — don't penalize the
absence of [^N] markers.

If the rubric explicitly says the answer SHOULD decline ("the corpus
doesn't have enough information"), score 1.0 when the answer declines
politely and 0.0 when it invents facts.

Output exactly two lines:
SCORE: <float between 0.0 and 1.0>
REASONING: <one short sentence>
"""


def score_judge(
    case: EvalCase,
    answer_text: str,
    *,
    model: Model = Model.SONNET,
    client: anthropic.Anthropic | None = None,
    session_id: str = "eval-judge",
) -> tuple[float, str]:
    """Run the LLM-as-judge scorer. Returns (score, reasoning)."""
    if client is None:
        settings = get_settings()
        client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key.get_secret_value()
        )

    user_message = (
        f"QUESTION:\n{case.question}\n\n"
        f"RUBRIC:\n{case.rubric or '(no specific rubric)'}\n\n"
        f"ANSWER FROM THE SYSTEM:\n{answer_text}"
    )

    with guarded_call(
        session_id=session_id,
        model=model,
        input_text=JUDGE_SYSTEM_PROMPT + "\n\n" + user_message,
        max_output_tokens=200,
    ):
        response = client.messages.create(
            model=model.value,
            max_tokens=200,
            system=JUDGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

    text = "".join(
        getattr(b, "text", "") for b in (response.content or []) if getattr(b, "type", None) == "text"
    ).strip()

    in_tokens = response.usage.input_tokens
    out_tokens = response.usage.output_tokens
    record_usage(
        session_id=session_id,
        model=model,
        input_tokens=in_tokens,
        output_tokens=out_tokens,
    )

    score, reasoning = _parse_judge_output(text)
    return score, reasoning


def _parse_judge_output(text: str) -> tuple[float, str]:
    """Parse the two-line judge output. Lenient — defaults to 0.5 if the
    SCORE line is missing or malformed (we still log the full text)."""
    score = 0.5
    reasoning = ""
    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("SCORE:"):
            try:
                score = max(0.0, min(1.0, float(line.split(":", 1)[1].strip())))
            except (ValueError, IndexError):
                pass
        elif line.upper().startswith("REASONING:"):
            reasoning = line.split(":", 1)[1].strip() if ":" in line else line
    if not reasoning:
        reasoning = text[:200]
    return score, reasoning


# --------------------------------------------------------------------------- #
# Composite scorer
# --------------------------------------------------------------------------- #


def score_case(
    case: EvalCase,
    result: AskResult,
    *,
    judge_client: anthropic.Anthropic | None = None,
) -> ScoreBreakdown:
    """Run all four scorers on one case + result and return the breakdown."""
    answer = result.answer or ""
    route_acc = score_route_accuracy(case, result)
    kw_recall = score_keyword_recall(case, answer)
    hall_guard = score_hallucination_guard(case, answer)
    judge_score, judge_reasoning = score_judge(case, answer, client=judge_client)
    return ScoreBreakdown(
        route_accuracy=route_acc,
        keyword_recall=kw_recall,
        hallucination_guard=hall_guard,
        judge_score=judge_score,
        judge_reasoning=judge_reasoning,
    )
