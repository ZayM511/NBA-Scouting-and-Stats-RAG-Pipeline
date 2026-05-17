"""Tests for the synthesizer — citation parsing, decline detection, and
the Anthropic call shape. Mocks the SDK so tests don't hit the network."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pytest

from src.retrieve_prose.filters import ScoredChunk
from src.synthesize.prompts import (
    SYNTHESIS_SYSTEM_PROMPT,
    build_user_message,
)
from src.synthesize.synthesizer import (
    Synthesizer,
    _parse_citations,
)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _chunk(chunk_id: int, text: str = "some text", source: str = "r/nba") -> ScoredChunk:
    return ScoredChunk(
        chunk_id=chunk_id,
        article_id=f"art-{chunk_id}",
        text=text,
        source=source,
        article_type="reddit_thread",
        score=0.5,
        date=date(2026, 5, 1),
    )


@dataclass
class FakeBlock:
    type: str
    text: str = ""


@dataclass
class FakeUsage:
    input_tokens: int = 500
    output_tokens: int = 80


@dataclass
class FakeResponse:
    content: list[FakeBlock]
    usage: FakeUsage = None  # type: ignore[assignment]
    stop_reason: str = "end_turn"

    def __post_init__(self) -> None:
        if self.usage is None:
            self.usage = FakeUsage()


def _text_response(text: str) -> FakeResponse:
    return FakeResponse(content=[FakeBlock(type="text", text=text)])


class FakeAnthropic:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    @property
    def messages(self) -> "FakeAnthropic":
        return self

    def create(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        return self._responses.pop(0)


# ----------------------------------------------------------------------------
# build_user_message
# ----------------------------------------------------------------------------


def test_build_user_message_numbers_chunks_starting_at_1() -> None:
    msg = build_user_message(
        "What did Wemby do?",
        [_chunk(101, "Wemby had 35 PTS"), _chunk(102, "Wemby had 5 blocks")],
    )
    assert "[1]" in msg
    assert "[2]" in msg
    assert "Wemby had 35 PTS" in msg
    assert "Wemby had 5 blocks" in msg


def test_build_user_message_includes_metadata_header() -> None:
    msg = build_user_message("q", [_chunk(42, "x", source="r/nba")])
    assert "source=r/nba" in msg
    assert "chunk_id=42" in msg
    assert "date=2026-05-01" in msg


def test_build_user_message_handles_empty_chunks() -> None:
    msg = build_user_message("q", [])
    assert "no chunks were retrieved" in msg


def test_build_user_message_rejects_empty_question() -> None:
    with pytest.raises(ValueError):
        build_user_message("", [_chunk(1)])
    with pytest.raises(ValueError):
        build_user_message("   ", [_chunk(1)])


# ----------------------------------------------------------------------------
# _parse_citations
# ----------------------------------------------------------------------------


def test_parse_citations_extracts_simple_citations() -> None:
    text = "Wemby had 35 points [^1] and 5 blocks [^2]."
    chunks = [_chunk(101), _chunk(102)]
    citations, cited_ids = _parse_citations(text, chunks)
    assert len(citations) == 2
    assert citations[0].citation_index == 1
    assert citations[0].chunk_id == 101
    assert citations[1].chunk_id == 102
    assert cited_ids == [101, 102]


def test_parse_citations_handles_combined_citations() -> None:
    text = "Both sources agreed [^1][^3]."
    chunks = [_chunk(10), _chunk(20), _chunk(30)]
    citations, cited_ids = _parse_citations(text, chunks)
    assert len(citations) == 2
    assert [c.chunk_id for c in citations] == [10, 30]
    assert cited_ids == [10, 30]


def test_parse_citations_dedupes_by_chunk_id_in_cited_list() -> None:
    text = "Claim [^1]. Same point reinforced [^1] later."
    chunks = [_chunk(99)]
    citations, cited_ids = _parse_citations(text, chunks)
    assert len(citations) == 2  # both raw mentions kept
    assert cited_ids == [99]    # but only once in the unique list


def test_parse_citations_drops_out_of_range_indices() -> None:
    text = "Bad citation [^9]. Good one [^1]."
    chunks = [_chunk(7)]
    citations, cited_ids = _parse_citations(text, chunks)
    assert len(citations) == 1
    assert citations[0].chunk_id == 7
    assert cited_ids == [7]


def test_parse_citations_handles_no_citations() -> None:
    text = "An answer with no citations at all."
    chunks = [_chunk(1)]
    citations, cited_ids = _parse_citations(text, chunks)
    assert citations == []
    assert cited_ids == []


# ----------------------------------------------------------------------------
# Synthesizer
# ----------------------------------------------------------------------------


def test_synthesizer_returns_cited_answer() -> None:
    fake = FakeAnthropic([_text_response("Wemby had 35 PTS [^1].")])
    s = Synthesizer(client=fake)
    out = s.synthesize("how did wemby do?", [_chunk(101, "Wemby had 35 PTS")])
    assert "Wemby had 35 PTS" in out.answer
    assert out.cited_chunk_ids == [101]
    assert out.declined is False
    assert out.cost_usd > 0
    assert out.chunks_supplied == 1


def test_synthesizer_marks_declined_when_model_uses_escape_phrase() -> None:
    fake = FakeAnthropic([
        _text_response(
            "The retrieved sources don't have enough information on this. "
            "They cover Wemby's offense but nothing on his free throws."
        )
    ])
    s = Synthesizer(client=fake)
    out = s.synthesize("how is wemby's FT shooting?", [_chunk(101)])
    assert out.declined is True
    assert out.cited_chunk_ids == []  # no citations in the decline


def test_synthesizer_rejects_empty_question() -> None:
    fake = FakeAnthropic([])
    s = Synthesizer(client=fake)
    with pytest.raises(ValueError, match="non-empty"):
        s.synthesize("", [_chunk(1)])


def test_synthesizer_sends_system_prompt_and_user_message() -> None:
    fake = FakeAnthropic([_text_response("ok [^1].")])
    s = Synthesizer(client=fake)
    s.synthesize("q", [_chunk(1, "context")])
    call = fake.calls[0]
    assert call["system"] == SYNTHESIS_SYSTEM_PROMPT
    assert call["messages"][0]["role"] == "user"
    assert "QUESTION:" in call["messages"][0]["content"]
    assert "CONTEXT:" in call["messages"][0]["content"]
