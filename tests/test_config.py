"""Smoke tests for src.config — proves the env-var validation works."""

from __future__ import annotations

import pytest

from src.config import Settings, get_settings


def test_settings_load_with_defaults() -> None:
    settings = get_settings()
    assert settings.max_input_tokens_per_query == 8000
    assert settings.max_output_tokens_per_query == 2000
    assert settings.session_cost_ceiling_usd == 0.50
    assert settings.hourly_cost_circuit_breaker_usd == 5.00


def test_settings_secrets_are_secret_str() -> None:
    settings = get_settings()
    # SecretStr keeps the value out of repr / str output.
    assert "test-anthropic-key" not in repr(settings)
    assert settings.anthropic_api_key.get_secret_value() == "test-anthropic-key"


def test_settings_missing_required_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # Drop the env var AND tell pydantic to ignore the .env file so the
    # check actually tests "the key is missing." Otherwise the developer's
    # local .env shadows the test.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(Exception):  # pydantic ValidationError
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_overrides_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_INPUT_TOKENS_PER_QUERY", "4096")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.max_input_tokens_per_query == 4096
