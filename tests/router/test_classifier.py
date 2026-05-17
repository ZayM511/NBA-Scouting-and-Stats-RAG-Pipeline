"""Tests for the router classifier.

Mocks the Anthropic client so these tests don't make live API calls and
don't need ANTHROPIC_API_KEY in CI. A live smoke test lives in the CLI
`smoke` command — see `src/router/cli.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from src.router.classifier import RouterClassifier, RouterError, _extract_tool_input
from src.router.prompts import (
    FEW_SHOT_EXAMPLES,
    ROUTE_TOOL,
    SYSTEM_PROMPT,
    few_shot_messages,
)


# ----------------------------------------------------------------------------
# Prompts
# ----------------------------------------------------------------------------


def test_tool_schema_has_required_fields() -> None:
    assert ROUTE_TOOL["name"] == "classify_route"
    props = ROUTE_TOOL["input_schema"]["properties"]
    assert "route" in props and "reasoning" in props
    assert set(props["route"]["enum"]) == {"stats", "prose", "hybrid"}


def test_system_prompt_mentions_all_three_routes() -> None:
    for route in ("stats", "prose", "hybrid"):
        assert route in SYSTEM_PROMPT


def test_few_shot_covers_all_routes() -> None:
    routes = {ex["route"] for ex in FEW_SHOT_EXAMPLES}
    assert routes == {"stats", "prose", "hybrid"}


def test_few_shot_has_at_least_three_per_route() -> None:
    counts: dict[str, int] = {"stats": 0, "prose": 0, "hybrid": 0}
    for ex in FEW_SHOT_EXAMPLES:
        counts[ex["route"]] += 1
    for route, n in counts.items():
        assert n >= 3, f"only {n} examples for route={route}"


def test_few_shot_messages_alternate_user_assistant_user() -> None:
    msgs = few_shot_messages()
    assert len(msgs) == 3 * len(FEW_SHOT_EXAMPLES)
    # Pattern: user (question), assistant (tool_use), user (tool_result)
    for i, m in enumerate(msgs):
        if i % 3 == 0:
            assert m["role"] == "user"
            assert isinstance(m["content"], str)
        elif i % 3 == 1:
            assert m["role"] == "assistant"
            assert any(b.get("type") == "tool_use" for b in m["content"])
        else:
            assert m["role"] == "user"
            assert any(b.get("type") == "tool_result" for b in m["content"])


# ----------------------------------------------------------------------------
# _extract_tool_input
# ----------------------------------------------------------------------------


@dataclass
class FakeBlock:
    type: str
    name: str = ""
    input: dict | None = None


@dataclass
class FakeUsage:
    input_tokens: int = 100
    output_tokens: int = 20


@dataclass
class FakeResponse:
    content: list[FakeBlock]
    usage: FakeUsage = None  # type: ignore[assignment]
    stop_reason: str = "tool_use"

    def __post_init__(self) -> None:
        if self.usage is None:
            self.usage = FakeUsage()


def _ok_response(route: str, reasoning: str = "because") -> FakeResponse:
    return FakeResponse(
        content=[
            FakeBlock(type="tool_use", name="classify_route", input={"route": route, "reasoning": reasoning}),
        ]
    )


def test_extract_tool_input_returns_dict() -> None:
    resp = _ok_response("stats", "numeric answer")
    out = _extract_tool_input(resp, tool_name="classify_route")
    assert out == {"route": "stats", "reasoning": "numeric answer"}


def test_extract_tool_input_raises_when_no_tool_use_block() -> None:
    resp = FakeResponse(content=[FakeBlock(type="text")])
    with pytest.raises(RouterError, match="no tool_use block"):
        _extract_tool_input(resp, tool_name="classify_route")


def test_extract_tool_input_raises_on_wrong_tool_name() -> None:
    resp = FakeResponse(content=[FakeBlock(type="tool_use", name="some_other_tool", input={})])
    with pytest.raises(RouterError, match="no tool_use block"):
        _extract_tool_input(resp, tool_name="classify_route")


# ----------------------------------------------------------------------------
# RouterClassifier with a mocked Anthropic client
# ----------------------------------------------------------------------------


class FakeAnthropic:
    """Minimal stand-in for anthropic.Anthropic."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    @property
    def messages(self) -> "FakeAnthropic":
        return self  # the SDK looks like client.messages.create

    def create(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        return self._responses.pop(0)


def test_classifier_returns_route_decision() -> None:
    fake = FakeAnthropic([_ok_response("stats", "numeric")])
    c = RouterClassifier(client=fake)
    d = c.classify("What's Jokic's TS%?")
    assert d.route == "stats"
    assert d.reasoning == "numeric"
    assert d.input_tokens == 100
    assert d.output_tokens == 20
    assert d.cost_usd > 0


def test_classifier_rejects_empty_question() -> None:
    fake = FakeAnthropic([])
    c = RouterClassifier(client=fake)
    with pytest.raises(ValueError, match="non-empty"):
        c.classify("")
    with pytest.raises(ValueError, match="non-empty"):
        c.classify("   ")


def test_classifier_raises_on_invalid_route() -> None:
    fake = FakeAnthropic([_ok_response("garbage", "explanation")])
    c = RouterClassifier(client=fake)
    with pytest.raises(RouterError, match="invalid route"):
        c.classify("What's Jokic's TS%?")


def test_classifier_raises_on_empty_reasoning() -> None:
    fake = FakeAnthropic([_ok_response("stats", "")])
    c = RouterClassifier(client=fake)
    with pytest.raises(RouterError, match="reasoning"):
        c.classify("What's Jokic's TS%?")


def test_classifier_sends_tool_use_with_forced_tool_choice() -> None:
    fake = FakeAnthropic([_ok_response("prose", "qual")])
    c = RouterClassifier(client=fake)
    c.classify("How do scouts grade Wemby?")
    call = fake.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": "classify_route"}
    assert len(call["tools"]) == 1
    assert call["tools"][0]["name"] == "classify_route"
    assert call["system"] == SYSTEM_PROMPT
