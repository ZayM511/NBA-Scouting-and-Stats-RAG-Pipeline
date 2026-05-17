"""Cohere Rerank 3.5 wrapper (REST API).

Calls https://api.cohere.com/v2/rerank directly via `requests` so we
avoid the cohere SDK's transitive deps (we already had two SDK-vs-3.14
incompatibility surprises with voyageai; the REST API is one fewer thing
to debug). The rerank endpoint takes a query and a list of documents
(strings) and returns a list of {index, relevance_score} sorted by
relevance descending.

Batch limit: 1000 documents per call. Project queries are well under.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import get_settings
from src.retrieve_prose.filters import ScoredChunk

logger = logging.getLogger(__name__)


COHERE_RERANK_ENDPOINT = "https://api.cohere.com/v2/rerank"
DEFAULT_MODEL = "rerank-v3.5"
DEFAULT_TIMEOUT_SECONDS = 30
MAX_DOCS_PER_CALL = 1000


class CohereError(Exception):
    """Raised on Cohere API failure."""


class CohereRateLimitError(CohereError):
    """Raised on 429. Retryable."""


class CohereServerError(CohereError):
    """Raised on 5xx. Retryable."""


_RETRYABLE: tuple[type[BaseException], ...] = (
    CohereRateLimitError,
    CohereServerError,
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
)


@dataclass(frozen=True)
class RerankResult:
    """One rerank result row."""

    original_index: int
    relevance_score: float


class Reranker:
    """Stateful Cohere Rerank client. Reuse one instance per session."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if api_key is None:
            api_key = get_settings().cohere_api_key.get_secret_value()
        self.model = model
        self._timeout = timeout_seconds
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "nba-rag/0.1",
            }
        )

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(_RETRYABLE),
        reraise=True,
    )
    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_k: int | None = None,
    ) -> list[RerankResult]:
        """Return reranked results sorted by descending relevance.

        Returns at most `top_k` entries if provided, otherwise all
        documents. `original_index` indexes into the input `documents`
        list.
        """
        if not documents:
            return []
        if len(documents) > MAX_DOCS_PER_CALL:
            raise ValueError(
                f"too many docs ({len(documents)} > {MAX_DOCS_PER_CALL})"
            )

        body = {
            "model": self.model,
            "query": query,
            "documents": list(documents),
        }
        if top_k is not None:
            body["top_n"] = top_k

        response = self._session.post(
            COHERE_RERANK_ENDPOINT, json=body, timeout=self._timeout
        )
        if response.status_code == 429:
            raise CohereRateLimitError(f"429: {response.text[:300]}")
        if response.status_code >= 500:
            raise CohereServerError(f"{response.status_code}: {response.text[:300]}")
        if response.status_code >= 400:
            raise CohereError(f"{response.status_code}: {response.text[:300]}")

        payload = response.json()
        results = payload.get("results", [])
        return [
            RerankResult(
                original_index=int(r["index"]),
                relevance_score=float(r["relevance_score"]),
            )
            for r in results
        ]

    def rerank_chunks(
        self,
        query: str,
        chunks: Sequence[ScoredChunk],
        *,
        top_k: int = 10,
    ) -> list[ScoredChunk]:
        """Convenience: rerank `ScoredChunk` objects directly.

        Each output chunk's `score` is replaced by the rerank relevance.
        Order matches Cohere's relevance ranking. Returns up to `top_k`.
        """
        if not chunks:
            return []
        results = self.rerank(query, [c.text for c in chunks], top_k=top_k)
        out: list[ScoredChunk] = []
        for r in results:
            base = chunks[r.original_index]
            out.append(
                ScoredChunk(
                    chunk_id=base.chunk_id,
                    article_id=base.article_id,
                    text=base.text,
                    source=base.source,
                    article_type=base.article_type,
                    score=r.relevance_score,
                    date=base.date,
                    player_ids=base.player_ids,
                )
            )
        return out

    def close(self) -> None:
        self._session.close()
