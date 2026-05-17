"""Entity resolution: raw text → set of player_ids mentioned.

Uses the `player_aliases` table populated by `generate_aliases.py`. The
algorithm:

  1. Normalize the input text the same way the aliases were normalized at
     ingest time (lowercase, strip diacritics, collapse whitespace, strip
     possessive 's, keep apostrophes and hyphens that appear in real
     names).
  2. Tokenize on word boundaries that respect apostrophes and hyphens.
  3. Slide n-gram windows over the tokens, longest-first, looking up each
     candidate in the alias map. Mark consumed positions so the same
     tokens can't double-count.

Longest-first matching prevents "stephen curry" from being parsed as two
separate matches ("stephen" → nothing, "curry" → Steph). It also prevents
"the chef curry" from over-counting Curry once via "the chef" and again
via "curry".

`AliasResolver` loads the full alias map into memory once. For a ~1,500-
row alias table that's trivial (under 100 KB) and makes per-text resolves
O(tokens * max_alias_length) with a hash-table lookup at the leaf.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field

import psycopg
from psycopg.rows import dict_row

from src.config import get_settings

logger = logging.getLogger(__name__)

# Same normalization rules as src.normalize_entities.generate_aliases.normalize_alias.
_PUNCT_RE = re.compile(r"[^\w\s'\-]", flags=re.UNICODE)
_WS_RE = re.compile(r"\s+")
_POSSESSIVE_RE = re.compile(r"'s$")
_TOKEN_RE = re.compile(r"[\w'-]+", flags=re.UNICODE)


def _normalize_text(text: str) -> str:
    """Lowercase, strip diacritics, normalize whitespace, drop punctuation
    other than apostrophes and hyphens. Matches `normalize_alias`."""
    if not text:
        return ""
    s = unicodedata.normalize("NFKD", text)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def _tokenize(normalized_text: str) -> list[str]:
    """Tokenize an already-normalized string. Strips possessive 's from
    each token (so "Curry's three" → ["curry", "three"])."""
    tokens = _TOKEN_RE.findall(normalized_text)
    out: list[str] = []
    for t in tokens:
        # Strip possessive 's so "curry's" matches "curry".
        cleaned = _POSSESSIVE_RE.sub("", t)
        if cleaned:
            out.append(cleaned)
    return out


@dataclass
class AliasResolver:
    """In-memory alias map keyed by normalized alias string."""

    alias_to_player_id: dict[str, int]
    max_alias_token_count: int = 0
    _confidence: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.max_alias_token_count and self.alias_to_player_id:
            self.max_alias_token_count = max(
                len(alias.split()) for alias in self.alias_to_player_id
            )

    @classmethod
    def from_db(cls, conn: psycopg.Connection | None = None) -> "AliasResolver":
        """Load every row in `player_aliases` into memory.

        Pass an existing connection to reuse a transaction; otherwise opens
        its own connection via the central config.
        """
        if conn is None:
            settings = get_settings()
            with psycopg.connect(str(settings.postgres_url), row_factory=dict_row) as own:
                return cls._load(own)
        return cls._load(conn)

    @classmethod
    def _load(cls, conn: psycopg.Connection) -> "AliasResolver":
        with conn.cursor() as cur:
            cur.execute(
                "SELECT alias, player_id, confidence FROM player_aliases ORDER BY alias"
            )
            rows = cur.fetchall()
        alias_to_id = {r["alias"]: int(r["player_id"]) for r in rows}
        confidence = {r["alias"]: float(r["confidence"]) for r in rows}
        max_len = max((len(a.split()) for a in alias_to_id), default=0)
        return cls(
            alias_to_player_id=alias_to_id,
            max_alias_token_count=max_len,
            _confidence=confidence,
        )

    def resolve(self, text: str) -> set[int]:
        """Return the set of player_ids mentioned in `text`.

        Longest-match-first n-gram scan. A consumed token can't participate
        in any other match (avoids double-counting).
        """
        if not text or not self.alias_to_player_id:
            return set()

        normalized = _normalize_text(text)
        tokens = _tokenize(normalized)
        if not tokens:
            return set()

        found: set[int] = set()
        consumed: set[int] = set()
        max_n = self.max_alias_token_count
        n_tokens = len(tokens)

        i = 0
        while i < n_tokens:
            if i in consumed:
                i += 1
                continue
            matched = False
            # Try the longest window first, shrink down to 1 if no hit.
            upper = min(max_n, n_tokens - i)
            for n in range(upper, 0, -1):
                window_range = range(i, i + n)
                if any(pos in consumed for pos in window_range):
                    continue
                candidate = " ".join(tokens[i : i + n])
                pid = self.alias_to_player_id.get(candidate)
                if pid is not None:
                    found.add(pid)
                    consumed.update(window_range)
                    i += n
                    matched = True
                    break
            if not matched:
                i += 1
        return found

    def resolve_with_aliases(self, text: str) -> list[tuple[str, int]]:
        """Same as `resolve` but returns the matched (alias, player_id) pairs
        in order of appearance. Useful for debugging which alias triggered."""
        if not text or not self.alias_to_player_id:
            return []
        normalized = _normalize_text(text)
        tokens = _tokenize(normalized)
        if not tokens:
            return []

        out: list[tuple[str, int]] = []
        consumed: set[int] = set()
        max_n = self.max_alias_token_count
        n_tokens = len(tokens)

        i = 0
        while i < n_tokens:
            if i in consumed:
                i += 1
                continue
            matched = False
            upper = min(max_n, n_tokens - i)
            for n in range(upper, 0, -1):
                window_range = range(i, i + n)
                if any(pos in consumed for pos in window_range):
                    continue
                candidate = " ".join(tokens[i : i + n])
                pid = self.alias_to_player_id.get(candidate)
                if pid is not None:
                    out.append((candidate, pid))
                    consumed.update(window_range)
                    i += n
                    matched = True
                    break
            if not matched:
                i += 1
        return out

    def __len__(self) -> int:
        return len(self.alias_to_player_id)
