"""Generate parameterized SQL for a user question via Claude Sonnet 4.6.

Uses Anthropic tool use so the response always parses into {sql, params,
explanation}. Goes through `guarded_call` so cost and token caps apply.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import anthropic

from src.config import get_settings
from src.guardrails import Model, guarded_call, record_usage
from src.retrieve_stats.prompts import GENERATE_SQL_TOOL, SQL_GEN_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeneratedSQL:
    """The model's SQL proposal plus its trace."""

    sql: str
    params: dict[str, Any]
    explanation: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class SQLGenerationError(Exception):
    """Raised when the model returns an unparseable response."""


class SQLGenerator:
    """Stateful Anthropic client wrapper. Reuse one per session."""

    def __init__(
        self,
        model: Model = Model.SONNET,
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

    def generate(
        self,
        question: str,
        *,
        session_id: str = "stats-sql",
    ) -> GeneratedSQL:
        """Generate one parameterized SELECT query for `question`."""
        if not question or not question.strip():
            raise ValueError("question must be non-empty")

        user_message = question.strip()

        with guarded_call(
            session_id=session_id,
            model=self.model,
            input_text=SQL_GEN_SYSTEM_PROMPT + "\n\n" + user_message,
            max_output_tokens=self.max_output_tokens,
        ):
            response = self._client.messages.create(
                model=self.model.value,
                max_tokens=self.max_output_tokens,
                system=SQL_GEN_SYSTEM_PROMPT,
                tools=[GENERATE_SQL_TOOL],
                tool_choice={"type": "tool", "name": GENERATE_SQL_TOOL["name"]},
                messages=[{"role": "user", "content": user_message}],
            )

        tool_input = _extract_tool_input(response, tool_name=GENERATE_SQL_TOOL["name"])
        sql = (tool_input.get("sql") or "").strip()
        params = tool_input.get("params") or {}
        explanation = (tool_input.get("explanation") or "").strip()

        if not sql:
            raise SQLGenerationError("model returned empty sql")
        if not isinstance(params, dict):
            raise SQLGenerationError(f"params must be a dict, got {type(params).__name__}")
        if not explanation:
            raise SQLGenerationError("model omitted explanation")

        in_tokens = response.usage.input_tokens
        out_tokens = response.usage.output_tokens
        rec = record_usage(
            session_id=session_id,
            model=self.model,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
        )
        return GeneratedSQL(
            sql=sql,
            params=dict(params),
            explanation=explanation,
            model=self.model.value,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_usd=rec.cost_usd,
        )


def _extract_tool_input(response: Any, *, tool_name: str) -> dict[str, Any]:
    blocks = getattr(response, "content", None) or []
    for block in blocks:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", "") == tool_name:
            return dict(block.input or {})
    raise SQLGenerationError(
        f"no tool_use block named {tool_name!r}; stop_reason="
        f"{getattr(response, 'stop_reason', '?')}"
    )
