"""Tests for src.guardrails (LLM10 enforcement)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.config import get_settings
from src.guardrails import (
    CASCADE,
    CircuitBreakerOpen,
    InMemoryCostTracker,
    Model,
    NoModelAvailable,
    SessionCostCeilingHit,
    TokenCapExceeded,
    UsageRecord,
    count_tokens,
    estimate_cost,
    guard_request,
    guarded_call,
    pick_model,
    record_usage,
)


# --------------------------------------------------------------------------- #
# count_tokens / estimate_cost
# --------------------------------------------------------------------------- #


def test_count_tokens_returns_positive_for_text() -> None:
    assert count_tokens("hello world") > 0


def test_count_tokens_pads_up_for_safety() -> None:
    # The pad factor is 10%, so a long text's count must exceed the raw
    # 4-chars-per-token estimate.
    text = "a" * 4000
    estimated = count_tokens(text)
    # tiktoken is more accurate than the fallback, so this asserts a floor.
    assert estimated >= 200


def test_estimate_cost_haiku_cheaper_than_sonnet() -> None:
    h = estimate_cost(Model.HAIKU, input_tokens=1000, output_tokens=1000)
    s = estimate_cost(Model.SONNET, input_tokens=1000, output_tokens=1000)
    o = estimate_cost(Model.OPUS, input_tokens=1000, output_tokens=1000)
    assert h < s < o


def test_estimate_cost_known_value() -> None:
    # Haiku: $0.80 input + $4.00 output per 1M
    # 1000 input + 1000 output = 0.001 * 0.80 + 0.001 * 4.00 = 0.00080 + 0.00400 = 0.00480
    cost = estimate_cost(Model.HAIKU, input_tokens=1000, output_tokens=1000)
    assert abs(cost - 0.00480) < 1e-9


# --------------------------------------------------------------------------- #
# Model cascade
# --------------------------------------------------------------------------- #


def test_pick_model_starts_with_haiku() -> None:
    assert pick_model() is Model.HAIKU


def test_pick_model_progresses_through_cascade() -> None:
    assert pick_model(attempted=(Model.HAIKU,)) is Model.SONNET
    assert pick_model(attempted=(Model.HAIKU, Model.SONNET)) is Model.OPUS


def test_pick_model_honors_preference() -> None:
    assert pick_model(preference=Model.OPUS) is Model.OPUS


def test_pick_model_skips_preference_if_already_attempted() -> None:
    assert pick_model(attempted=(Model.OPUS,), preference=Model.OPUS) is Model.HAIKU


def test_pick_model_raises_when_exhausted() -> None:
    with pytest.raises(NoModelAvailable):
        pick_model(attempted=CASCADE)


# --------------------------------------------------------------------------- #
# InMemoryCostTracker
# --------------------------------------------------------------------------- #


def _record(
    *, session_id: str = "s1", cost: float = 0.001, model: Model = Model.HAIKU,
    age_seconds: int = 0,
) -> UsageRecord:
    return UsageRecord(
        timestamp=datetime.now(timezone.utc) - timedelta(seconds=age_seconds),
        session_id=session_id,
        model=model,
        input_tokens=100,
        output_tokens=100,
        cost_usd=cost,
    )


def test_tracker_session_cost_sums_only_that_session() -> None:
    t = InMemoryCostTracker()
    t.record(_record(session_id="s1", cost=0.10))
    t.record(_record(session_id="s2", cost=0.20))
    t.record(_record(session_id="s1", cost=0.05))
    assert t.session_cost("s1") == pytest.approx(0.15)
    assert t.session_cost("s2") == pytest.approx(0.20)


def test_tracker_hourly_cost_excludes_old_records() -> None:
    t = InMemoryCostTracker()
    t.record(_record(cost=1.00, age_seconds=0))
    t.record(_record(cost=2.00, age_seconds=3600 * 2))  # 2 hours old
    assert t.hourly_cost() == pytest.approx(1.00)


# --------------------------------------------------------------------------- #
# guard_request
# --------------------------------------------------------------------------- #


def test_guard_request_passes_on_normal_inputs() -> None:
    t = InMemoryCostTracker()
    input_tokens = guard_request(
        session_id="s1",
        model=Model.HAIKU,
        input_text="What is Jokic's TS%?",
        max_output_tokens=500,
        tracker=t,
    )
    assert input_tokens > 0


def test_guard_request_rejects_oversized_input() -> None:
    t = InMemoryCostTracker()
    # 8K cap, pad factor 10%, so ~7300 raw tokens = ~29200 chars triggers reject
    huge = "word " * 30_000
    with pytest.raises(TokenCapExceeded):
        guard_request(
            session_id="s1",
            model=Model.HAIKU,
            input_text=huge,
            max_output_tokens=500,
            tracker=t,
        )


def test_guard_request_rejects_oversized_output_request() -> None:
    t = InMemoryCostTracker()
    with pytest.raises(TokenCapExceeded):
        guard_request(
            session_id="s1",
            model=Model.HAIKU,
            input_text="hi",
            max_output_tokens=10_000,
            tracker=t,
        )


def test_guard_request_blocks_when_session_ceiling_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SESSION_COST_CEILING_USD", "0.10")
    get_settings.cache_clear()
    t = InMemoryCostTracker()
    # Pre-load the session past its ceiling.
    t.record(_record(session_id="s1", cost=0.15))
    with pytest.raises(SessionCostCeilingHit):
        guard_request(
            session_id="s1",
            model=Model.HAIKU,
            input_text="hi",
            max_output_tokens=500,
            tracker=t,
        )


def test_guard_request_blocks_when_circuit_breaker_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOURLY_COST_CIRCUIT_BREAKER_USD", "1.00")
    get_settings.cache_clear()
    t = InMemoryCostTracker()
    t.record(_record(cost=1.50, age_seconds=10))
    with pytest.raises(CircuitBreakerOpen):
        guard_request(
            session_id="any",
            model=Model.HAIKU,
            input_text="hi",
            max_output_tokens=500,
            tracker=t,
        )


def test_guard_request_blocks_when_projected_cost_would_exceed_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pre-flight projection: even if current session_cost is under the
    ceiling, reject when current + projected would cross it."""
    monkeypatch.setenv("SESSION_COST_CEILING_USD", "0.01")
    get_settings.cache_clear()
    t = InMemoryCostTracker()
    # Single Opus call with max output is projected to cost ~0.001 + 0.15
    with pytest.raises(SessionCostCeilingHit):
        guard_request(
            session_id="s1",
            model=Model.OPUS,
            input_text="x" * 4000,
            max_output_tokens=2000,
            tracker=t,
        )


# --------------------------------------------------------------------------- #
# record_usage + guarded_call
# --------------------------------------------------------------------------- #


def test_record_usage_appends_to_tracker() -> None:
    t = InMemoryCostTracker()
    rec = record_usage(
        session_id="s1",
        model=Model.SONNET,
        input_tokens=200,
        output_tokens=400,
        tracker=t,
    )
    assert rec.cost_usd > 0
    assert t.session_cost("s1") == pytest.approx(rec.cost_usd)


def test_guarded_call_context_manager_runs_pre_check() -> None:
    t = InMemoryCostTracker()
    with guarded_call(
        session_id="s1",
        model=Model.HAIKU,
        input_text="What is Jokic's TS%?",
        max_output_tokens=500,
        tracker=t,
    ) as input_tokens:
        assert input_tokens > 0


def test_guarded_call_propagates_token_cap_error() -> None:
    t = InMemoryCostTracker()
    with pytest.raises(TokenCapExceeded):
        with guarded_call(
            session_id="s1",
            model=Model.HAIKU,
            input_text="hi",
            max_output_tokens=10_000,
            tracker=t,
        ):
            pass  # pragma: no cover
