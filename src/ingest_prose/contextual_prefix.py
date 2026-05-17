"""Contextual-retrieval prefix builder.

For each chunk, prepend a short context line before embedding. Format:

    Article from {source}, {date}, about {comma_separated_player_names}: {chunk_text}

This is the Anthropic (2024) contextual-retrieval pattern. Concrete
example:

    Article from The Athletic, 2026-04-12, about Victor Wembanyama: ...

Empirically delivers a 35-50% recall lift on hard queries. The prefix
is included in the embedded text (so the vector encodes the context)
but the raw chunk text stays unchanged in the `text` column for display
purposes.

Defined as a small, pure function so it's easy to unit-test and reuse
from both the article and Reddit ingestion paths.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date


# How many player names to inline. More than this and the prefix gets
# noisy (a power-rankings article mentions 50 players). When there are
# more, we say "and N others" to keep the prefix short.
MAX_PLAYERS_IN_PREFIX = 5


def build_prefix(
    *,
    source: str | None,
    article_date: date | str | None,
    player_names: Iterable[str] | None,
    chunk_text: str,
) -> str:
    """Return the embeddable string: `prefix + ": " + chunk_text`.

    Missing fields are tolerated gracefully:

    - `source=None` → "Article from an unknown source"
    - `article_date=None` → no date in the prefix
    - `player_names` empty or None → "no specific player" (the chunk
      probably covers team-level analysis or league trends)
    """
    src = source.strip() if source else "an unknown source"

    date_str: str | None = None
    if isinstance(article_date, date):
        date_str = article_date.isoformat()
    elif isinstance(article_date, str) and article_date.strip():
        date_str = article_date.strip()

    names = list(player_names or [])
    # Dedupe while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for n in names:
        if n and n not in seen:
            seen.add(n)
            unique.append(n)

    if not unique:
        players_str = "no specific player"
    elif len(unique) <= MAX_PLAYERS_IN_PREFIX:
        players_str = _comma_and(unique)
    else:
        shown = unique[:MAX_PLAYERS_IN_PREFIX]
        extras = len(unique) - MAX_PLAYERS_IN_PREFIX
        players_str = f"{_comma_and(shown)} and {extras} others"

    if date_str:
        prefix = f"Article from {src}, {date_str}, about {players_str}"
    else:
        prefix = f"Article from {src}, about {players_str}"

    return f"{prefix}: {chunk_text}"


def _comma_and(items: list[str]) -> str:
    """Format a list like 'A, B, and C'. Oxford comma."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"
