"""Voyage AI embedding wrapper (REST API).

Calls the Voyage embeddings REST endpoint directly via `requests`, sidestepping
the voyageai Python SDK because it currently fails to import on Python 3.14
(pydantic-v1 + `min_items` issue in the multimodal-embeddings module). The
REST API is stable and well-documented, so the wrapper is simple and
maintainable.

See `.claude/skills/voyage-embeddings-reference.md` for the broader background
(which model when, free-tier limits, etc.).

Defaults:

- Model: voyage-3-large (1024-dim). The project's primary embedding model.
- Batch size: 128 texts (the API max).
- Retry: exponential backoff on 429 / 5xx.

Use `Embedder.embed_documents(texts)` at ingest time (input_type="document")
and `Embedder.embed_query(text)` at retrieval time (input_type="query").
Voyage models are asymmetric — using the wrong input_type costs ~5-10% recall.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import get_settings

logger = logging.getLogger(__name__)


DEFAULT_MODEL = "voyage-3-large"
EMBEDDING_DIM = 1024
DEFAULT_BATCH_SIZE = 128
VOYAGE_ENDPOINT = "https://api.voyageai.com/v1/embeddings"


class VoyageError(Exception):
    """Raised when the Voyage API returns a non-success status."""


class VoyageRateLimitError(VoyageError):
    """Raised on 429. Retryable."""


class VoyageServerError(VoyageError):
    """Raised on 5xx. Retryable."""


_RETRYABLE: tuple[type[BaseException], ...] = (
    VoyageRateLimitError,
    VoyageServerError,
    requests.exceptions.ConnectionError,
    requests.exceptions.ReadTimeout,
    requests.exceptions.Timeout,
)


@dataclass
class EmbeddingBatch:
    """Result of embedding a batch."""

    vectors: list[list[float]]
    total_tokens: int


class Embedder:
    """Stateful HTTP client for Voyage embeddings. Reuse one instance per run."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        timeout_seconds: int = 60,
    ) -> None:
        self.model = model
        if api_key is None:
            api_key = get_settings().voyage_api_key.get_secret_value()
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "nba-rag/0.1 (+https://github.com/ZayM511/NBA-Scouting-and-Stats-RAG-Pipeline)",
            }
        )

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(_RETRYABLE),
        reraise=True,
    )
    def _embed_batch(
        self,
        texts: list[str],
        input_type: Literal["document", "query"],
    ) -> EmbeddingBatch:
        if not texts:
            return EmbeddingBatch(vectors=[], total_tokens=0)

        body = {
            "input": texts,
            "model": self.model,
            "input_type": input_type,
        }
        try:
            response = self._session.post(VOYAGE_ENDPOINT, json=body, timeout=self._timeout)
        except requests.exceptions.RequestException as exc:
            logger.warning("voyage request failed: %s", exc)
            raise

        if response.status_code == 429:
            raise VoyageRateLimitError(f"429: {response.text[:300]}")
        if response.status_code >= 500:
            raise VoyageServerError(f"{response.status_code}: {response.text[:300]}")
        if response.status_code >= 400:
            raise VoyageError(f"{response.status_code}: {response.text[:300]}")

        data = response.json()
        vectors = [item["embedding"] for item in data["data"]]
        total_tokens = int(data.get("usage", {}).get("total_tokens", 0))
        return EmbeddingBatch(vectors=vectors, total_tokens=total_tokens)

    def embed_documents(
        self,
        texts: Iterable[str],
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> EmbeddingBatch:
        """Embed an iterable of document texts in batches.

        Returns a single `EmbeddingBatch` with all vectors and a summed
        token count. Order matches the input order.
        """
        texts_list = list(texts)
        if not texts_list:
            return EmbeddingBatch(vectors=[], total_tokens=0)

        all_vectors: list[list[float]] = []
        total_tokens = 0
        for start in range(0, len(texts_list), batch_size):
            batch = texts_list[start : start + batch_size]
            result = self._embed_batch(batch, input_type="document")
            all_vectors.extend(result.vectors)
            total_tokens += result.total_tokens
            logger.debug(
                "embed_documents: batch %d-%d done (%d tokens)",
                start,
                start + len(batch) - 1,
                result.total_tokens,
            )
        return EmbeddingBatch(vectors=all_vectors, total_tokens=total_tokens)

    def embed_query(self, text: str) -> list[float]:
        """Embed a single retrieval-time query. Uses input_type='query' so
        the asymmetric model produces the right vector geometry."""
        result = self._embed_batch([text], input_type="query")
        return result.vectors[0]

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._session.close()
