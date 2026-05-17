"""End-to-end ask pipeline: question → route → retrieve → synthesize.

Today wires the prose AND stats routes end-to-end. Hybrid still routes
correctly and returns a graceful "not yet implemented" message so the
router trace + reasoning surface in the UI even before the hybrid
retrieval module ships in Phase G.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.ingest_prose.embedder import Embedder
from src.retrieve_prose.filters import ChunkFilters
from src.retrieve_prose.hybrid_search import HybridSearchResult, hybrid_search
from src.retrieve_prose.rerank import Reranker
from src.retrieve_stats.pipeline import StatsResult, retrieve_stats
from src.retrieve_stats.sql_generator import SQLGenerator
from src.router.classifier import RouteDecision, RouterClassifier
from src.synthesize.synthesizer import SynthesisResult, Synthesizer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AskResult:
    """End-to-end result of one `ask()` call.

    `route` is always present. `retrieval` is set on the prose route,
    `stats` on the stats route, `synthesis` whenever an answer was
    produced. `not_yet_implemented=True` for routes whose retrieval
    module is still pending (today: hybrid).
    """

    question: str
    route: RouteDecision
    retrieval: HybridSearchResult | None = None
    stats: StatsResult | None = None
    synthesis: SynthesisResult | None = None
    not_yet_implemented: bool = False
    notes: str = ""

    @property
    def answer(self) -> str:
        """Convenience: the answer text, or a placeholder."""
        if self.synthesis is not None:
            return self.synthesis.answer
        if self.not_yet_implemented:
            return (
                f"This question routes to '{self.route.route}', which isn't "
                "wired into the synthesis layer yet. Routing decided: "
                f"{self.route.reasoning}"
            )
        return self.notes or "(no answer produced)"


def ask(
    question: str,
    *,
    filters: ChunkFilters | None = None,
    top_k: int = 8,
    classifier: RouterClassifier | None = None,
    embedder: Embedder | None = None,
    reranker: Reranker | None = None,
    synthesizer: Synthesizer | None = None,
    sql_generator: SQLGenerator | None = None,
    session_id: str = "ask",
) -> AskResult:
    """Run the full ask pipeline for one user question.

    Reuse the service instances across multiple `ask()` calls in one
    process so HTTP sessions and Anthropic clients stay warm.
    """
    if not question or not question.strip():
        raise ValueError("question must be non-empty")

    classifier = classifier or RouterClassifier()
    decision = classifier.classify(question, session_id=session_id)

    if decision.route == "prose":
        return _ask_prose(
            question,
            decision,
            filters=filters,
            top_k=top_k,
            embedder=embedder,
            reranker=reranker,
            synthesizer=synthesizer,
            session_id=session_id,
        )
    if decision.route == "stats":
        return _ask_stats(
            question,
            decision,
            sql_generator=sql_generator,
            synthesizer=synthesizer,
            session_id=session_id,
        )

    # hybrid — phase G
    return AskResult(
        question=question,
        route=decision,
        not_yet_implemented=True,
        notes=f"route='{decision.route}' deferred to phase G (hybrid).",
    )


# --------------------------------------------------------------------------- #
# Prose route
# --------------------------------------------------------------------------- #


def _ask_prose(
    question: str,
    decision: RouteDecision,
    *,
    filters: ChunkFilters | None,
    top_k: int,
    embedder: Embedder | None,
    reranker: Reranker | None,
    synthesizer: Synthesizer | None,
    session_id: str,
) -> AskResult:
    own_embedder = embedder is None
    own_reranker = reranker is None
    embedder = embedder or Embedder()
    reranker = reranker or Reranker()
    try:
        retrieval = hybrid_search(
            question,
            filters=filters,
            top_k=top_k,
            embedder=embedder,
            reranker=reranker,
        )
    finally:
        if own_embedder:
            embedder.close()
        if own_reranker:
            reranker.close()

    if not retrieval.chunks:
        return AskResult(
            question=question,
            route=decision,
            retrieval=retrieval,
            notes="hybrid_search returned zero chunks; nothing to synthesize.",
        )

    synthesizer = synthesizer or Synthesizer()
    result = synthesizer.synthesize(
        question, retrieval.chunks, session_id=session_id
    )
    return AskResult(
        question=question,
        route=decision,
        retrieval=retrieval,
        synthesis=result,
    )


# --------------------------------------------------------------------------- #
# Stats route
# --------------------------------------------------------------------------- #


def _ask_stats(
    question: str,
    decision: RouteDecision,
    *,
    sql_generator: SQLGenerator | None,
    synthesizer: Synthesizer | None,
    session_id: str,
) -> AskResult:
    stats = retrieve_stats(
        question, generator=sql_generator, session_id=session_id
    )

    if stats.status != "ok":
        notes = (
            f"stats path returned status={stats.status} (error: {stats.error}). "
            "No synthesis performed."
        )
        return AskResult(
            question=question,
            route=decision,
            stats=stats,
            notes=notes,
        )

    if not stats.rows:
        return AskResult(
            question=question,
            route=decision,
            stats=stats,
            notes="The query returned zero rows.",
        )

    synthesizer = synthesizer or Synthesizer()
    syn = synthesizer.synthesize_stats(question, stats, session_id=session_id)
    return AskResult(
        question=question,
        route=decision,
        stats=stats,
        synthesis=syn,
    )
