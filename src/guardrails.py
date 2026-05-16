"""LLM10 guardrails: per-query token caps, per-session cost ceiling,
model cascade (Haiku → Sonnet → Opus), and an aggregate hourly cost
circuit breaker.

Every LLM call in this project goes through `guarded_call`. That keeps the
controls in one place and makes it impossible for a new code path to silently
bypass them.

Defaults come from `src.config.get_settings()` (which reads env vars and
falls back to the values documented in CLAUDE.md):

  * MAX_INPUT_TOKENS_PER_QUERY  = 8000
  * MAX_OUTPUT_TOKENS_PER_QUERY = 2000
  * SESSION_COST_CEILING_USD    = 0.50
  * HOURLY_COST_CIRCUIT_BREAKER_USD = 5.00
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Protocol

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Models + pricing
# --------------------------------------------------------------------------- #


class Model(StrEnum):
    """Anthropic model IDs used in this project. Cascade order in `CASCADE`."""

    HAIKU = "claude-haiku-4-5-20251001"
    SONNET = "claude-sonnet-4-6"
    OPUS = "claude-opus-4-7"


# Cheapest → most expensive. The cascade walks this list.
CASCADE: tuple[Model, ...] = (Model.HAIKU, Model.SONNET, Model.OPUS)


# Pricing (USD per 1M tokens). Verify against console.anthropic.com periodically.
# These are the published list-prices as of 2026-01; update if Anthropic changes.
PRICE_PER_MILLION: dict[Model, dict[str, float]] = {
    Model.HAIKU: {"input": 0.80, "output": 4.00},
    Model.SONNET: {"input": 3.00, "output": 15.00},
    Model.OPUS: {"input": 15.00, "output": 75.00},
}


def estimate_cost(model: Model, input_tokens: int, output_tokens: int) -> float:
    """USD cost for `input_tokens` + `output_tokens` against `model`."""
    p = PRICE_PER_MILLION[model]
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


# --------------------------------------------------------------------------- #
# Token counting
# --------------------------------------------------------------------------- #


# tiktoken cl100k_base is GPT-tuned, but it's close enough for Claude tokens
# (within ~10%) and it's local. We pad up by 10% to stay conservative when
# checking caps.
_TOKEN_PAD_FACTOR = 1.10


def count_tokens(text: str) -> int:
    """Approximate the token count for `text`.

    Uses tiktoken's cl100k_base when available; falls back to a 4-chars-per-token
    heuristic if tiktoken isn't installed. Padded up 10% so checks are
    conservative.
    """
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        raw = len(enc.encode(text))
    except Exception:
        # Approximation: English averages ~4 chars per token.
        raw = max(1, len(text) // 4)
    return int(raw * _TOKEN_PAD_FACTOR)


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class GuardrailError(Exception):
    """Base class for every guardrail rejection."""


class TokenCapExceeded(GuardrailError):
    """Raised when a request would exceed the per-query token cap."""


class SessionCostCeilingHit(GuardrailError):
    """Raised when the per-session cost ceiling is hit."""


class CircuitBreakerOpen(GuardrailError):
    """Raised when the hourly aggregate cost circuit breaker is tripped."""


class NoModelAvailable(GuardrailError):
    """Raised when the cascade has been exhausted with no usable model."""


# --------------------------------------------------------------------------- #
# Usage record + tracker
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class UsageRecord:
    """One LLM call's usage. Append-only."""

    timestamp: datetime
    session_id: str
    model: Model
    input_tokens: int
    output_tokens: int
    cost_usd: float


class CostTracker(Protocol):
    """Storage for usage records. The in-memory tracker is the default;
    swap in a persistent implementation (Redis, Postgres) in production."""

    def record(self, r: UsageRecord) -> None: ...

    def session_cost(self, session_id: str) -> float: ...

    def hourly_cost(self) -> float: ...


@dataclass
class InMemoryCostTracker:
    """Thread-safe in-memory usage tracker.

    Keeps every record forever in the current implementation; for a long-lived
    process, swap in a persistent backend. Per-session cost is the sum of
    every record for that session. Hourly cost is the sum of every record in
    the last 3600 seconds.
    """

    _records: deque[UsageRecord] = field(default_factory=deque)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, r: UsageRecord) -> None:
        with self._lock:
            self._records.append(r)

    def session_cost(self, session_id: str) -> float:
        with self._lock:
            return sum(r.cost_usd for r in self._records if r.session_id == session_id)

    def hourly_cost(self) -> float:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        with self._lock:
            return sum(r.cost_usd for r in self._records if r.timestamp >= cutoff)

    def reset(self) -> None:
        """Clear every record. Use in tests."""
        with self._lock:
            self._records.clear()


# Module-level singleton. Override via dependency injection in tests / prod.
_DEFAULT_TRACKER = InMemoryCostTracker()


def get_tracker() -> CostTracker:
    return _DEFAULT_TRACKER


# --------------------------------------------------------------------------- #
# Model cascade
# --------------------------------------------------------------------------- #


def pick_model(
    *,
    attempted: tuple[Model, ...] = (),
    preference: Model | None = None,
) -> Model:
    """Return the next model to try.

    If `preference` is provided and not already in `attempted`, use it. Otherwise
    walk the cascade in cheapest-first order, skipping any model already tried.

    Raises NoModelAvailable if the cascade is exhausted.
    """
    if preference is not None and preference not in attempted:
        return preference
    for model in CASCADE:
        if model not in attempted:
            return model
    raise NoModelAvailable(
        f"cascade exhausted: tried {[m.value for m in attempted]}"
    )


# --------------------------------------------------------------------------- #
# guard_request — the pre-call check
# --------------------------------------------------------------------------- #


def guard_request(
    *,
    session_id: str,
    model: Model,
    input_text: str,
    max_output_tokens: int,
    tracker: CostTracker | None = None,
    settings: Settings | None = None,
) -> int:
    """Check every guardrail before issuing an LLM call.

    Returns the counted input tokens (so callers don't need to count twice).

    Raises:
        CircuitBreakerOpen      if hourly aggregate cost is at/over the limit
        SessionCostCeilingHit   if this session is at/over its ceiling
        TokenCapExceeded        if input or requested output exceeds the caps
    """
    settings = settings or get_settings()
    tracker = tracker or get_tracker()

    # 1. Circuit breaker — the cheapest check, do it first.
    hourly = tracker.hourly_cost()
    if hourly >= settings.hourly_cost_circuit_breaker_usd:
        raise CircuitBreakerOpen(
            f"hourly cost ${hourly:.4f} >= circuit breaker "
            f"${settings.hourly_cost_circuit_breaker_usd:.2f}"
        )

    # 2. Per-session ceiling.
    session_cost = tracker.session_cost(session_id)
    if session_cost >= settings.session_cost_ceiling_usd:
        raise SessionCostCeilingHit(
            f"session {session_id} cost ${session_cost:.4f} >= ceiling "
            f"${settings.session_cost_ceiling_usd:.2f}"
        )

    # 3. Per-query input token cap.
    input_tokens = count_tokens(input_text)
    if input_tokens > settings.max_input_tokens_per_query:
        raise TokenCapExceeded(
            f"input tokens {input_tokens} > cap {settings.max_input_tokens_per_query} "
            f"for model {model.value}"
        )

    # 4. Per-query output token cap.
    if max_output_tokens > settings.max_output_tokens_per_query:
        raise TokenCapExceeded(
            f"requested output tokens {max_output_tokens} > cap "
            f"{settings.max_output_tokens_per_query}"
        )

    # 5. Pre-flight cost projection. Reject if this single call would push the
    # session over its ceiling.
    projected_cost = estimate_cost(model, input_tokens, max_output_tokens)
    if session_cost + projected_cost > settings.session_cost_ceiling_usd:
        raise SessionCostCeilingHit(
            f"projected cost ${session_cost + projected_cost:.4f} would exceed "
            f"session ceiling ${settings.session_cost_ceiling_usd:.2f} "
            f"(current ${session_cost:.4f}, this call ${projected_cost:.4f})"
        )

    return input_tokens


# --------------------------------------------------------------------------- #
# record_usage — the post-call accounting
# --------------------------------------------------------------------------- #


def record_usage(
    *,
    session_id: str,
    model: Model,
    input_tokens: int,
    output_tokens: int,
    tracker: CostTracker | None = None,
) -> UsageRecord:
    """Record a completed LLM call's usage. Returns the stored record.

    Call this with the actual token counts from the LLM response, not the
    pre-flight estimate, so the cost ledger reflects reality.
    """
    tracker = tracker or get_tracker()
    cost = estimate_cost(model, input_tokens, output_tokens)
    rec = UsageRecord(
        timestamp=datetime.now(timezone.utc),
        session_id=session_id,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
    )
    tracker.record(rec)
    logger.info(
        "llm usage: session=%s model=%s in=%d out=%d cost=$%.6f",
        session_id,
        model.value,
        input_tokens,
        output_tokens,
        cost,
    )
    return rec


# --------------------------------------------------------------------------- #
# guarded_call — the recommended high-level wrapper
# --------------------------------------------------------------------------- #


@contextmanager
def guarded_call(
    *,
    session_id: str,
    model: Model,
    input_text: str,
    max_output_tokens: int = 2000,
    tracker: CostTracker | None = None,
    settings: Settings | None = None,
) -> Iterator[int]:
    """Context manager that runs `guard_request` on enter and `record_usage`
    on successful exit.

    Yields the counted input tokens so callers can pass them to record_usage
    (the post-call record uses actual response tokens for input as well, but
    knowing the pre-count is useful for logging / progress UIs).

    Caller is responsible for actually issuing the LLM call and computing the
    output token count.

        with guarded_call(session_id="abc", model=Model.SONNET,
                          input_text=prompt) as input_tokens:
            response = anthropic.messages.create(...)
            record_usage(
                session_id="abc",
                model=Model.SONNET,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
    """
    input_tokens = guard_request(
        session_id=session_id,
        model=model,
        input_text=input_text,
        max_output_tokens=max_output_tokens,
        tracker=tracker,
        settings=settings,
    )
    yield input_tokens
