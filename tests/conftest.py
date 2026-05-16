"""Pytest fixtures shared across the test suite."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default test env: every required key present, every guardrail loosely set.

    Individual tests override via monkeypatch if they need tighter limits or
    intentionally absent keys.
    """
    defaults = {
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "VOYAGE_API_KEY": "test-voyage-key",
        "COHERE_API_KEY": "test-cohere-key",
        "POSTGRES_URL": "postgresql://nbarag:nbarag@localhost:5432/nbarag_test",
        "MAX_INPUT_TOKENS_PER_QUERY": "8000",
        "MAX_OUTPUT_TOKENS_PER_QUERY": "2000",
        "SESSION_COST_CEILING_USD": "0.50",
        "HOURLY_COST_CIRCUIT_BREAKER_USD": "5.00",
        "LOG_LEVEL": "INFO",
        "ENABLE_LIVE_LLM_TESTS": "false",
    }
    for key, value in defaults.items():
        monkeypatch.setenv(key, value)

    # Clear the lru_cache on the settings singleton so each test gets a fresh
    # Settings object reflecting the monkeypatched env.
    from src.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def live_llm_enabled() -> bool:
    """True only when ENABLE_LIVE_LLM_TESTS=true. Used to skip integration tests."""
    return os.environ.get("ENABLE_LIVE_LLM_TESTS", "false").lower() == "true"
