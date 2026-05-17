"""Synthesizer: turns retrieved chunks into a cited answer.

Sends the numbered chunks + the user question to Claude Opus 4.7 (with
cascade fallback to Sonnet 4.6 on failure). The model returns prose with
inline [^N] citations. We parse the citations into a separate list so the
UI can render them as interactive footnotes.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

import anthropic

from src.config import get_settings
from src.guardrails import Model, guarded_call, record_usage
from src.retrieve_hybrid.pipeline import HybridRetrievalResult
from src.retrieve_prose.filters import ScoredChunk
from src.retrieve_stats.pipeline import StatsResult
from src.synthesize.prompts import (
    HYBRID_SYNTHESIS_SYSTEM_PROMPT,
    STATS_SYNTHESIS_SYSTEM_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
    build_hybrid_user_message,
    build_stats_user_message,
    build_user_message,
)

logger = logging.getLogger(__name__)


# [^1], [^12], [^3][^7]  ←  matches each [^N] separately
_CITATION_RE = re.compile(r"\[\^(\d+)\]")


@dataclass(frozen=True)
class Citation:
    """One citation extracted from the answer text."""

    citation_index: int  # the N inside [^N]
    chunk_id: int        # the underlying articles_chunks.id


@dataclass(frozen=True)
class SynthesisResult:
    """Full synthesis output, ready for the UI's tool-use sidebar."""

    answer: str
    citations: list[Citation]
    cited_chunk_ids: list[int]  # unique, in order of first citation
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    chunks_supplied: int = 0
    declined: bool = False    # True if the model used the "not enough info" escape


# Phrases that signal the model declined. Conservative; matches the system
# prompt's mandated phrasing.
_DECLINED_MARKERS: tuple[str, ...] = (
    "don't have enough information",
    "do not have enough information",
)


class Synthesizer:
    """Stateful Anthropic client wrapper. Reuse one per session."""

    def __init__(
        self,
        model: Model = Model.OPUS,
        client: anthropic.Anthropic | None = None,
        max_output_tokens: int = 1024,
    ) -> None:
        self.model = model
        self.max_output_tokens = max_output_tokens
        if client is None:
            settings = get_settings()
            client = anthropic.Anthropic(
                api_key=settings.anthropic_api_key.get_secret_value()
            )
        self._client = client

    def synthesize(
        self,
        question: str,
        chunks: Sequence[ScoredChunk],
        *,
        session_id: str = "synthesize",
    ) -> SynthesisResult:
        """Generate a cited answer from `question` + `chunks`.

        Raises ValueError if the question is empty. Returns a `declined=True`
        result if the chunks don't support an answer (the model says so
        explicitly).
        """
        if not question or not question.strip():
            raise ValueError("question must be non-empty")

        user_message = build_user_message(question, chunks)

        with guarded_call(
            session_id=session_id,
            model=self.model,
            input_text=SYNTHESIS_SYSTEM_PROMPT + "\n\n" + user_message,
            max_output_tokens=self.max_output_tokens,
        ):
            response = self._client.messages.create(
                model=self.model.value,
                max_tokens=self.max_output_tokens,
                system=SYNTHESIS_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

        answer_text = _extract_text(response)
        citations, cited_chunk_ids = _parse_citations(answer_text, chunks)
        declined = _looks_declined(answer_text)

        in_tokens = response.usage.input_tokens
        out_tokens = response.usage.output_tokens
        rec = record_usage(
            session_id=session_id,
            model=self.model,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
        )

        return SynthesisResult(
            answer=answer_text,
            citations=citations,
            cited_chunk_ids=cited_chunk_ids,
            model=self.model.value,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_usd=rec.cost_usd,
            chunks_supplied=len(chunks),
            declined=declined,
        )

    def synthesize_stats(
        self,
        question: str,
        stats: StatsResult,
        *,
        session_id: str = "synthesize-stats",
    ) -> SynthesisResult:
        """Summarize stats rows as a short prose answer.

        The SQL itself is the citation; the UI shows it in the tool-use
        sidebar. The synthesizer's job is to translate row data into a
        natural answer that quotes the right numbers without inventing
        any.

        Raises ValueError if the question is empty or if `stats` is
        missing the generated SQL or the execution result (caller should
        only invoke after stats.status == 'ok').
        """
        if not question or not question.strip():
            raise ValueError("question must be non-empty")
        if stats.execution is None or stats.generated is None:
            raise ValueError("stats result must have generated SQL and execution")

        user_message = build_stats_user_message(question, stats)

        with guarded_call(
            session_id=session_id,
            model=self.model,
            input_text=STATS_SYNTHESIS_SYSTEM_PROMPT + "\n\n" + user_message,
            max_output_tokens=self.max_output_tokens,
        ):
            response = self._client.messages.create(
                model=self.model.value,
                max_tokens=self.max_output_tokens,
                system=STATS_SYNTHESIS_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

        answer_text = _extract_text(response)
        in_tokens = response.usage.input_tokens
        out_tokens = response.usage.output_tokens
        rec = record_usage(
            session_id=session_id,
            model=self.model,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
        )

        return SynthesisResult(
            answer=answer_text,
            citations=[],         # stats: the SQL itself is the citation
            cited_chunk_ids=[],
            model=self.model.value,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_usd=rec.cost_usd,
            chunks_supplied=0,    # stats: rows, not chunks
            declined=_looks_declined(answer_text),
        )

    def synthesize_hybrid(
        self,
        question: str,
        hybrid: HybridRetrievalResult,
        narrowed_player_names: list[str],
        *,
        session_id: str = "synthesize-hybrid",
    ) -> SynthesisResult:
        """Synthesize a cited answer combining the SQL-narrowed player set
        with prose retrieval results.

        Raises ValueError on empty question or when hybrid.retrieval is None.
        """
        if not question or not question.strip():
            raise ValueError("question must be non-empty")
        if hybrid.retrieval is None:
            raise ValueError("hybrid result must have a retrieval object")

        chunks = hybrid.retrieval.chunks
        user_message = build_hybrid_user_message(
            question,
            narrowed_player_names=narrowed_player_names,
            sql=hybrid.filter.sql,
            sql_explanation=hybrid.filter.explanation,
            chunks=chunks,
        )

        with guarded_call(
            session_id=session_id,
            model=self.model,
            input_text=HYBRID_SYNTHESIS_SYSTEM_PROMPT + "\n\n" + user_message,
            max_output_tokens=self.max_output_tokens,
        ):
            response = self._client.messages.create(
                model=self.model.value,
                max_tokens=self.max_output_tokens,
                system=HYBRID_SYNTHESIS_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

        answer_text = _extract_text(response)
        citations, cited_chunk_ids = _parse_citations(answer_text, chunks)
        declined = _looks_declined(answer_text)

        in_tokens = response.usage.input_tokens
        out_tokens = response.usage.output_tokens
        rec = record_usage(
            session_id=session_id,
            model=self.model,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
        )
        return SynthesisResult(
            answer=answer_text,
            citations=citations,
            cited_chunk_ids=cited_chunk_ids,
            model=self.model.value,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_usd=rec.cost_usd,
            chunks_supplied=len(chunks),
            declined=declined,
        )


def _extract_text(response: anthropic.types.Message) -> str:
    """Concatenate all text blocks in the response."""
    parts: list[str] = []
    for block in response.content or []:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", ""))
    return "".join(parts).strip()


def _parse_citations(
    answer_text: str, chunks: Sequence[ScoredChunk]
) -> tuple[list[Citation], list[int]]:
    """Extract every [^N] citation from `answer_text`. Returns:
    - all citations, in order of appearance
    - unique chunk_ids, in order of first appearance
    """
    citations: list[Citation] = []
    seen: set[int] = set()
    ordered_chunk_ids: list[int] = []
    n_chunks = len(chunks)

    for match in _CITATION_RE.finditer(answer_text):
        idx = int(match.group(1))
        if idx < 1 or idx > n_chunks:
            # Out-of-range citation. Surface for debugging; the synthesis
            # prompt forbids these, but the model occasionally slips.
            logger.warning(
                "synthesis: citation [^%d] out of range (have %d chunks)",
                idx,
                n_chunks,
            )
            continue
        chunk_id = chunks[idx - 1].chunk_id
        citations.append(Citation(citation_index=idx, chunk_id=chunk_id))
        if chunk_id not in seen:
            seen.add(chunk_id)
            ordered_chunk_ids.append(chunk_id)
    return citations, ordered_chunk_ids


def _looks_declined(answer_text: str) -> bool:
    lower = answer_text.lower()
    return any(marker in lower for marker in _DECLINED_MARKERS)
