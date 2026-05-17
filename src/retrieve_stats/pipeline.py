"""Stats retrieval pipeline: question → SQL gen → safety review → execute.

This is the path the router dispatches to when it picks `route="stats"`.
The output is a `StatsResult` that the synthesizer turns into a cited
natural-language answer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.retrieve_stats.executor import (
    ExecutionResult,
    SQLExecutionError,
    execute_sql,
)
from src.retrieve_stats.sql_generator import (
    GeneratedSQL,
    SQLGenerationError,
    SQLGenerator,
)
from src.retrieve_stats.sql_safety import Review, review_sql

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StatsResult:
    """Full result of one stats-route query for the UI sidebar."""

    question: str
    generated: GeneratedSQL | None
    safety: Review | None
    execution: ExecutionResult | None
    status: str  # 'ok' | 'safety_rejected' | 'gen_failed' | 'exec_failed'
    error: str | None = None

    @property
    def rows(self) -> list[dict[str, Any]]:
        return self.execution.rows if self.execution else []


def retrieve_stats(
    question: str,
    *,
    generator: SQLGenerator | None = None,
    session_id: str = "stats",
) -> StatsResult:
    """Run the full stats path: generate → review → execute.

    Reuse a `generator` across calls so the Anthropic client stays warm.
    """
    if not question or not question.strip():
        raise ValueError("question must be non-empty")

    # 1. Generate SQL.
    gen = generator or SQLGenerator()
    try:
        generated = gen.generate(question, session_id=session_id)
    except SQLGenerationError as exc:
        return StatsResult(
            question=question,
            generated=None,
            safety=None,
            execution=None,
            status="gen_failed",
            error=str(exc),
        )

    # 2. Safety review.
    safety = review_sql(generated.sql, params=generated.params)
    if not safety.approved:
        return StatsResult(
            question=question,
            generated=generated,
            safety=safety,
            execution=None,
            status="safety_rejected",
            error="; ".join(safety.reasons),
        )

    # 3. Execute against the read-only role.
    try:
        execution = execute_sql(generated.sql, generated.params)
    except SQLExecutionError as exc:
        return StatsResult(
            question=question,
            generated=generated,
            safety=safety,
            execution=None,
            status="exec_failed",
            error=str(exc),
        )

    return StatsResult(
        question=question,
        generated=generated,
        safety=safety,
        execution=execution,
        status="ok",
    )
