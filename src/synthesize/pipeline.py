"""End-to-end ask pipeline: question → route → retrieve → synthesize.

Today only the prose route runs end-to-end. Stats and hybrid return a
`NotImplementedRouteResult` with a polite message — the synthesis layer
plus the router decision are still present so the UI's tool-use sidebar
can show the routing trace even for the not-yet-implemented routes.

When E (stats text-to-SQL) and G (hybrid SQL-filter-then-vector) land,
each gets a branch in `ask()` and the pipeline is complete.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.ingest_prose.embedder import Embedder
from src.retrieve_prose.filters import ChunkFilters, ScoredChunk
from src.retrieve_prose.hybrid_search import HybridSearchResult, hybrid_search
from src.retrieve_prose.rerank import Reranker
from src.router.classifier import RouteDecision, RouterClassifier
from src.synthesize.synthesizer import SynthesisResult, Synthesizer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AskResult:
    """End-to-end result of one `ask()` call.

    Holds the route decision (always present), the retrieval trace (set
    only for the prose route today), the synthesis result (set when an
    answer was produced), and a not_yet_implemented flag for the routes
    that don't have their retrieval module wired in yet.
    """

    question: str
    route: RouteDecision
    retrieval: HybridSearchResult | None
    synthesis: SynthesisResult | None
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
        return "(no answer produced)"


def ask(
    question: str,
    *,
    filters: ChunkFilters | None = None,
    top_k: int = 8,
    classifier: RouterClassifier | None = None,
    embedder: Embedder | None = None,
    reranker: Reranker | None = None,
    synthesizer: Synthesizer | None = None,
    session_id: str = "ask",
) -> AskResult:
    """Run the full ask pipeline for one user question.

    Reuse the four service instances across multiple `ask()` calls in
    one process so HTTP sessions and Anthropic clients stay warm.
    """
    if not question or not question.strip():
        raise ValueError("question must be non-empty")

    classifier = classifier or RouterClassifier()
    decision = classifier.classify(question, session_id=session_id)

    # Only the prose route has its retrieval + synthesis path implemented today.
    if decision.route != "prose":
        return AskResult(
            question=question,
            route=decision,
            retrieval=None,
            synthesis=None,
            not_yet_implemented=True,
            notes=(
                f"route='{decision.route}' deferred to phase E (stats) "
                "or phase G (hybrid)."
            ),
        )

    # Prose: hybrid search → synthesize.
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
            synthesis=None,
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
