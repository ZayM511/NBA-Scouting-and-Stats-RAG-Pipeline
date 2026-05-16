"""Central config. All environment variables are read here, nowhere else.

Importing this module triggers validation: if any required variable is missing
or malformed, the import raises and the process fails fast. That's the point.
Read this once at process start; pass the returned `Settings` instance into
business logic instead of reading `os.environ` directly.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide configuration loaded from environment variables.

    Required variables raise on import. Optional variables have sensible
    defaults documented in `.env.example`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM providers ---
    anthropic_api_key: SecretStr = Field(..., alias="ANTHROPIC_API_KEY")
    voyage_api_key: SecretStr = Field(..., alias="VOYAGE_API_KEY")
    cohere_api_key: SecretStr = Field(..., alias="COHERE_API_KEY")

    # --- Observability ---
    braintrust_api_key: SecretStr | None = Field(None, alias="BRAINTRUST_API_KEY")
    braintrust_project: str = Field("nba-rag", alias="BRAINTRUST_PROJECT")

    # --- Reddit (optional during early dev) ---
    reddit_client_id: SecretStr | None = Field(None, alias="REDDIT_CLIENT_ID")
    reddit_client_secret: SecretStr | None = Field(None, alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field("nba-rag/0.1", alias="REDDIT_USER_AGENT")

    # --- Database ---
    postgres_url: PostgresDsn = Field(..., alias="POSTGRES_URL")
    postgres_readonly_url: PostgresDsn | None = Field(None, alias="POSTGRES_READONLY_URL")

    # --- Guardrails (LLM10) ---
    max_input_tokens_per_query: int = Field(8000, alias="MAX_INPUT_TOKENS_PER_QUERY")
    max_output_tokens_per_query: int = Field(2000, alias="MAX_OUTPUT_TOKENS_PER_QUERY")
    session_cost_ceiling_usd: float = Field(0.50, alias="SESSION_COST_CEILING_USD")
    hourly_cost_circuit_breaker_usd: float = Field(
        5.00, alias="HOURLY_COST_CIRCUIT_BREAKER_USD"
    )

    # --- App ---
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field("INFO", alias="LOG_LEVEL")
    enable_live_llm_tests: bool = Field(False, alias="ENABLE_LIVE_LLM_TESTS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the validated, cached `Settings` singleton."""
    return Settings()  # type: ignore[call-arg]
