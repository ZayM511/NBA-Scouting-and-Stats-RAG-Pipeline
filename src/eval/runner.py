"""Eval runner — executes every case through ask(), scores it, and
optionally streams to Braintrust.

The Braintrust integration is best-effort: if the SDK or API key isn't
available the runner still produces local JSONL output. That way the
eval is runnable in CI without depending on Braintrust availability.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anthropic

from src.config import get_settings
from src.eval.cases import ALL_CASES, EvalCase, cases_by_route
from src.eval.scorers import ScoreBreakdown, score_case
from src.ingest_prose.embedder import Embedder
from src.retrieve_prose.rerank import Reranker
from src.retrieve_stats.sql_generator import SQLGenerator
from src.router.classifier import RouterClassifier
from src.synthesize.pipeline import AskResult, ask
from src.synthesize.synthesizer import Synthesizer

logger = logging.getLogger(__name__)


@dataclass
class CaseRun:
    """One case after execution + scoring."""

    case_id: str
    question: str
    expected_route: str
    actual_route: str
    answer: str
    cost_usd: float
    elapsed_ms: float
    scores: dict[str, float]
    judge_reasoning: str
    error: str | None = None


@dataclass
class EvalReport:
    """The aggregate output of one full eval run."""

    tag: str
    timestamp: datetime
    runs: list[CaseRun] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.runs)

    def aggregate(self, key: str) -> float:
        vals = [r.scores.get(key, 0.0) for r in self.runs if r.error is None]
        return sum(vals) / max(len(vals), 1)

    def aggregate_by_route(self, key: str) -> dict[str, float]:
        out: dict[str, list[float]] = {"stats": [], "prose": [], "hybrid": []}
        for r in self.runs:
            if r.error is None:
                out.setdefault(r.expected_route, []).append(r.scores.get(key, 0.0))
        return {k: (sum(v) / max(len(v), 1)) for k, v in out.items()}

    def total_cost(self) -> float:
        return sum(r.cost_usd for r in self.runs)


def run_eval(
    tag: str = "baseline",
    *,
    cases: Iterable[EvalCase] = ALL_CASES,
    write_braintrust: bool = True,
    output_dir: str | Path = "eval_results",
) -> EvalReport:
    """Run every case in `cases`, score them, return the aggregate report.

    A JSONL of CaseRun rows lands under `output_dir/<tag>-<utc>.jsonl`.
    If Braintrust is configured (BRAINTRUST_API_KEY set + SDK installed),
    each call is also streamed to a Braintrust experiment named
    `<BRAINTRUST_PROJECT>:<tag>`.
    """
    cases_list = list(cases)
    settings = get_settings()
    started = datetime.now(timezone.utc)
    report = EvalReport(tag=tag, timestamp=started)

    # Warm shared service instances.
    embedder = Embedder()
    reranker = Reranker()
    classifier = RouterClassifier()
    synthesizer = Synthesizer()
    sql_generator = SQLGenerator()
    judge_client = anthropic.Anthropic(api_key=settings.anthropic_api_key.get_secret_value())

    # Try to set up Braintrust. Best-effort.
    bt_logger = _maybe_braintrust(write_braintrust, settings, tag)

    for case in cases_list:
        start = time.perf_counter()
        try:
            result = ask(
                case.question,
                top_k=8,
                classifier=classifier,
                embedder=embedder,
                reranker=reranker,
                synthesizer=synthesizer,
                sql_generator=sql_generator,
                session_id=f"eval-{tag}-{case.id}",
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            breakdown = score_case(case, result, judge_client=judge_client)
            run = CaseRun(
                case_id=case.id,
                question=case.question,
                expected_route=case.expected_route,
                actual_route=result.route.route,
                answer=result.answer or "",
                cost_usd=_total_cost(result),
                elapsed_ms=elapsed_ms,
                scores=_scores_dict(breakdown),
                judge_reasoning=breakdown.judge_reasoning,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("eval case %s failed", case.id)
            elapsed_ms = (time.perf_counter() - start) * 1000
            run = CaseRun(
                case_id=case.id,
                question=case.question,
                expected_route=case.expected_route,
                actual_route="error",
                answer="",
                cost_usd=0.0,
                elapsed_ms=elapsed_ms,
                scores={
                    "route_accuracy": 0.0,
                    "keyword_recall": 0.0,
                    "hallucination_guard": 0.0,
                    "judge_score": 0.0,
                    "aggregate": 0.0,
                },
                judge_reasoning="",
                error=f"{type(exc).__name__}: {exc}",
            )
        report.runs.append(run)
        _log_case(run)
        if bt_logger is not None:
            try:
                bt_logger.log(
                    input=case.question,
                    output=run.answer,
                    expected=case.expected_route,
                    scores={k: v for k, v in run.scores.items() if k != "aggregate"},
                    metadata={
                        "case_id": case.id,
                        "actual_route": run.actual_route,
                        "expected_route": case.expected_route,
                        "judge_reasoning": run.judge_reasoning,
                        "elapsed_ms": run.elapsed_ms,
                        "cost_usd": run.cost_usd,
                        "error": run.error,
                    },
                )
            except Exception:
                logger.exception("braintrust log failed for case %s", case.id)

    # Clean up.
    embedder.close()
    reranker.close()
    if bt_logger is not None:
        try:
            bt_logger.flush()
        except Exception:
            logger.exception("braintrust flush failed")

    # Write the local JSONL artifact.
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{tag}-{started.strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for r in report.runs:
            f.write(json.dumps(asdict(r), default=str) + "\n")
    logger.info("eval results written to %s", out_path)

    return report


def _total_cost(result: AskResult) -> float:
    total = 0.0
    if result.synthesis is not None:
        total += result.synthesis.cost_usd
    if result.stats is not None and result.stats.generated is not None:
        total += result.stats.generated.cost_usd
    if result.hybrid is not None:
        total += result.hybrid.filter.cost_usd
    # Router cost is amortized inside synthesis cost ledger via record_usage,
    # but the AskResult doesn't currently expose router cost separately. The
    # session-level ledger captures it; we just don't double-count here.
    return total


def _scores_dict(b: ScoreBreakdown) -> dict[str, float]:
    return {
        "route_accuracy": b.route_accuracy,
        "keyword_recall": b.keyword_recall,
        "hallucination_guard": b.hallucination_guard,
        "judge_score": b.judge_score,
        "aggregate": b.aggregate,
    }


def _log_case(run: CaseRun) -> None:
    marker = "OK " if run.error is None else "ERR"
    logger.info(
        "%s %-24s expected=%-6s actual=%-6s agg=%.2f route_acc=%.2f kw=%.2f judge=%.2f cost=$%.5f",
        marker,
        run.case_id,
        run.expected_route,
        run.actual_route,
        run.scores.get("aggregate", 0.0),
        run.scores.get("route_accuracy", 0.0),
        run.scores.get("keyword_recall", 0.0),
        run.scores.get("judge_score", 0.0),
        run.cost_usd,
    )


def _maybe_braintrust(write: bool, settings, tag: str):  # type: ignore[no-untyped-def]
    if not write:
        return None
    if not settings.braintrust_api_key:
        logger.info("Braintrust API key not configured; skipping remote logging.")
        return None
    try:
        import braintrust
    except ImportError:
        logger.info("braintrust SDK not installed; skipping remote logging.")
        return None
    try:
        os.environ.setdefault("BRAINTRUST_API_KEY", settings.braintrust_api_key.get_secret_value())
        return braintrust.init_logger(
            project=settings.braintrust_project,
            experiment=tag,
        )
    except Exception:
        logger.exception("Failed to initialize Braintrust logger; continuing without it.")
        return None
