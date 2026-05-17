"""Query-router classifier.

Wraps Claude Sonnet 4.6 with a tool-use call to return a structured
route decision. Routes through `src.guardrails.guarded_call` so token
caps + cost ceiling + circuit breaker all apply.

Usage:
    classifier = RouterClassifier()
    decision = classifier.classify("What's Jokic's TS%?")
    # → RouteDecision(route='stats', reasoning='...', ...)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

import anthropic

from src.config import get_settings
from src.guardrails import Model, guarded_call, record_usage
from src.router.prompts import ROUTE_TOOL, SYSTEM_PROMPT, few_shot_messages

logger = logging.getLogger(__name__)

Route = Literal["stats", "prose", "hybrid"]


@dataclass(frozen=True)
class RouteDecision:
    """Result of classifying one question."""

    route: Route
    reasoning: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class RouterError(Exception):
    """Raised when the model returns an unparseable or invalid response."""


class RouterClassifier:
    """Classifier instance. Reuse one per session."""

    def __init__(
        self,
        model: Model = Model.SONNET,
        client: anthropic.Anthropic | None = None,
        max_output_tokens: int = 200,
    ) -> None:
        self.model = model
        self.max_output_tokens = max_output_tokens
        if client is None:
            settings = get_settings()
            client = anthropic.Anthropic(
                api_key=settings.anthropic_api_key.get_secret_value()
            )
        self._client = client
        # Precompute the few-shot prefix so we don't rebuild on every call.
        self._few_shot = few_shot_messages()

    def classify(
        self,
        question: str,
        *,
        session_id: str = "router",
    ) -> RouteDecision:
        """Classify one question into stats / prose / hybrid.

        Raises RouterError if the model returns an invalid tool input.
        """
        if not question or not question.strip():
            raise ValueError("question must be a non-empty string")

        messages = [
            *self._few_shot,
            {"role": "user", "content": question.strip()},
        ]

        # Estimate input text for the guardrail. We approximate by joining
        # the system prompt + few-shot content + the user question.
        approx_input = (
            SYSTEM_PROMPT
            + "\n\n"
            + "\n".join(str(m.get("content", "")) for m in messages)
        )

        with guarded_call(
            session_id=session_id,
            model=self.model,
            input_text=approx_input,
            max_output_tokens=self.max_output_tokens,
        ):
            response = self._client.messages.create(
                model=self.model.value,
                max_tokens=self.max_output_tokens,
                system=SYSTEM_PROMPT,
                tools=[ROUTE_TOOL],
                tool_choice={"type": "tool", "name": ROUTE_TOOL["name"]},
                messages=messages,
            )

        # Find the tool_use block; with tool_choice="tool" we expect exactly one.
        tool_input = _extract_tool_input(response, tool_name=ROUTE_TOOL["name"])
        route = tool_input.get("route")
        reasoning = tool_input.get("reasoning", "").strip()

        if route not in ("stats", "prose", "hybrid"):
            raise RouterError(
                f"model returned invalid route={route!r}; expected stats/prose/hybrid"
            )
        if not reasoning:
            raise RouterError("model omitted reasoning")

        in_tokens = response.usage.input_tokens
        out_tokens = response.usage.output_tokens
        rec = record_usage(
            session_id=session_id,
            model=self.model,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
        )

        return RouteDecision(
            route=route,  # type: ignore[arg-type]
            reasoning=reasoning,
            model=self.model.value,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_usd=rec.cost_usd,
        )


def _extract_tool_input(response: Any, *, tool_name: str) -> dict[str, Any]:
    """Pull the tool_use input dict from an Anthropic response.

    Raises RouterError if no matching tool_use block is found.
    """
    blocks = getattr(response, "content", None) or []
    for block in blocks:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", "") == tool_name:
            return dict(block.input or {})
    raise RouterError(
        f"no tool_use block named {tool_name!r} in response; "
        f"stop_reason={getattr(response, 'stop_reason', '?')}"
    )
