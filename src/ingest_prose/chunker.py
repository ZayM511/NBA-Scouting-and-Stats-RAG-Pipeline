"""Recursive token-based text chunker.

Splits prose into chunks of approximately `target_tokens` (default 400),
with `overlap_ratio` (default 0.15 = 60-token) overlap between adjacent
chunks. Uses tiktoken's cl100k_base encoder for token counting (close
enough to Claude's tokenizer for chunking-budget purposes; we pad up by
10% elsewhere where exactness matters).

The recursion order is: paragraph (\\n\\n) → line (\\n) → sentence (. )
→ word (space) → hard char cut. Splits at the largest separator that
keeps every piece under the target.

This follows the 2026 default chunking strategy from
`.claude/skills/chunking-strategies.md`: recursive 400-token with 15%
overlap, for generic prose (articles, Reddit threads).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache

logger = logging.getLogger(__name__)


DEFAULT_TARGET_TOKENS = 400
DEFAULT_OVERLAP_RATIO = 0.15

# Separators tried in order, longest first. Each step is more granular.
_SEPARATORS: tuple[str, ...] = ("\n\n", "\n", ". ", " ")


@lru_cache(maxsize=1)
def _get_encoder():  # type: ignore[no-untyped-def]
    """Lazy-load the tiktoken encoder; cache the instance."""
    import tiktoken

    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Return the tiktoken cl100k_base token count for `text`."""
    if not text:
        return 0
    return len(_get_encoder().encode(text))


@dataclass(frozen=True)
class Chunk:
    """One chunk of text, plus its token count and position in the source."""

    text: str
    token_count: int
    chunk_index: int


def _split_on(text: str, separator: str) -> list[str]:
    """Split `text` on `separator`, preserving the separator on each piece
    except the last (so the join is lossless)."""
    if not separator:
        return [text]
    parts = text.split(separator)
    if len(parts) <= 1:
        return parts
    out: list[str] = []
    for i, p in enumerate(parts):
        if i < len(parts) - 1:
            out.append(p + separator)
        else:
            out.append(p)
    return [p for p in out if p]


def _split_recursive(text: str, target_tokens: int, separators: tuple[str, ...]) -> list[str]:
    """Recursively split `text` until every piece is under `target_tokens`.

    Returns the list of sub-pieces (each individually under the target,
    if possible). Doesn't apply overlap or grouping — that's the next pass.
    """
    if count_tokens(text) <= target_tokens or not separators:
        return [text]

    sep = separators[0]
    rest = separators[1:]
    pieces = _split_on(text, sep)

    # If splitting on this separator didn't help (single piece), descend.
    if len(pieces) == 1:
        return _split_recursive(text, target_tokens, rest)

    out: list[str] = []
    for piece in pieces:
        if count_tokens(piece) <= target_tokens:
            out.append(piece)
        else:
            out.extend(_split_recursive(piece, target_tokens, rest))
    return out


def _hard_split(text: str, target_tokens: int) -> list[str]:
    """Last-resort: split on token boundaries directly. Used when no
    separator-based split could get pieces under the target (very long words
    or non-whitespace prose)."""
    enc = _get_encoder()
    tokens = enc.encode(text)
    pieces: list[str] = []
    for start in range(0, len(tokens), target_tokens):
        chunk_tokens = tokens[start : start + target_tokens]
        pieces.append(enc.decode(chunk_tokens))
    return pieces


def _group_with_overlap(
    pieces: list[str],
    target_tokens: int,
    overlap_tokens: int,
) -> list[Chunk]:
    """Group small pieces into chunks of ~target_tokens, with overlap.

    The overlap is implemented by prepending the trailing N tokens of the
    previous chunk to the next one. This keeps a "context bridge" so an idea
    spanning a chunk boundary appears in both contexts.
    """
    if not pieces:
        return []

    enc = _get_encoder()
    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_tokens = 0
    overlap_text: str | None = None

    def flush() -> None:
        nonlocal buf, buf_tokens, overlap_text
        if not buf:
            return
        text = "".join(buf).strip()
        if not text:
            buf = []
            buf_tokens = 0
            return
        chunk = Chunk(text=text, token_count=count_tokens(text), chunk_index=len(chunks))
        chunks.append(chunk)
        # Compute the overlap text for the NEXT chunk: trailing N tokens.
        if overlap_tokens > 0:
            tail_tokens = enc.encode(text)[-overlap_tokens:]
            overlap_text = enc.decode(tail_tokens)
        else:
            overlap_text = None
        buf = []
        buf_tokens = 0

    for piece in pieces:
        if not piece.strip():
            continue
        piece_tokens = count_tokens(piece)
        # A single piece is bigger than the target, hard-split it.
        if piece_tokens > target_tokens:
            flush()
            for hard_piece in _hard_split(piece, target_tokens):
                flush()
                buf = [hard_piece]
                buf_tokens = count_tokens(hard_piece)
                flush()
            continue
        if buf_tokens + piece_tokens > target_tokens:
            flush()
            # Seed the next buffer with the overlap text from the previous chunk.
            if overlap_text:
                buf = [overlap_text + " "]
                buf_tokens = count_tokens(overlap_text)
        buf.append(piece)
        buf_tokens += piece_tokens

    flush()
    # Re-index in case empty chunks were skipped during flushes.
    return [Chunk(text=c.text, token_count=c.token_count, chunk_index=i) for i, c in enumerate(chunks)]


def chunk_text(
    text: str,
    *,
    target_tokens: int = DEFAULT_TARGET_TOKENS,
    overlap_ratio: float = DEFAULT_OVERLAP_RATIO,
) -> list[Chunk]:
    """Chunk `text` into ~`target_tokens` pieces with `overlap_ratio` overlap.

    Returns a list of `Chunk` objects with consecutive `chunk_index` values
    starting at 0. Empty input returns an empty list. Whitespace-only input
    returns an empty list.

    The total returned token count exceeds the source by approximately
    overlap_ratio (since the overlap bridges appear in both chunks).
    """
    if not text or not text.strip():
        return []
    if target_tokens <= 0:
        raise ValueError(f"target_tokens must be positive, got {target_tokens}")
    if not 0 <= overlap_ratio < 1:
        raise ValueError(f"overlap_ratio must be in [0, 1), got {overlap_ratio}")

    overlap_tokens = int(target_tokens * overlap_ratio)

    # Short-circuit: input already fits.
    total = count_tokens(text)
    if total <= target_tokens:
        clean = text.strip()
        return [Chunk(text=clean, token_count=count_tokens(clean), chunk_index=0)]

    # Phase 1: recursive split to pieces that each fit.
    pieces = _split_recursive(text, target_tokens, _SEPARATORS)

    # Phase 2: group adjacent pieces into chunks of ~target_tokens, with overlap.
    return _group_with_overlap(pieces, target_tokens, overlap_tokens)
