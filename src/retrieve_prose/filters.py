"""Filter dataclass shared by BM25, dense, and hybrid retrievers.

Filters compose into SQL WHERE clauses uniformly. Every field is optional;
omitted fields impose no constraint. The point of putting them in one
place is so the three retrievers can't drift apart on what they support.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class ChunkFilters:
    """Optional filters applied to articles_chunks before scoring.

    `player_ids`: ARRAY overlap (`&&`). Uses the GIN index on player_ids.
    `team`:       exact match.
    `source`:     exact match (e.g., 'r/nba').
    `article_type`: one of 'news', 'scouting', 'reddit_thread', 'authored_summary'.
    `date_from` / `date_to`: inclusive date bounds.
    """

    player_ids: Sequence[int] | None = None
    team: str | None = None
    source: str | None = None
    article_type: str | None = None
    date_from: date | None = None
    date_to: date | None = None

    def to_sql_clauses(
        self, table_alias: str = "ac"
    ) -> tuple[list[str], dict[str, object]]:
        """Return (clauses, params) for use inside a WHERE.

        `clauses` are joined with AND by the caller. `params` is a dict
        keyed by named placeholders.
        """
        clauses: list[str] = []
        params: dict[str, object] = {}

        if self.player_ids:
            clauses.append(f"{table_alias}.player_ids && %(player_ids)s::INT[]")
            params["player_ids"] = list(self.player_ids)
        if self.team:
            clauses.append(f"{table_alias}.team = %(team)s")
            params["team"] = self.team
        if self.source:
            clauses.append(f"{table_alias}.source = %(source)s")
            params["source"] = self.source
        if self.article_type:
            clauses.append(f"{table_alias}.article_type = %(article_type)s")
            params["article_type"] = self.article_type
        if self.date_from:
            clauses.append(f"{table_alias}.date >= %(date_from)s")
            params["date_from"] = self.date_from
        if self.date_to:
            clauses.append(f"{table_alias}.date <= %(date_to)s")
            params["date_to"] = self.date_to
        return clauses, params


@dataclass(frozen=True)
class ScoredChunk:
    """One retrieved chunk + its score and key metadata.

    `score` semantics depend on the retriever (BM25 rank, cosine similarity,
    rerank relevance). The hybrid path uses the rerank score as the final
    ordering signal.
    """

    chunk_id: int
    article_id: str
    text: str
    source: str
    article_type: str
    score: float
    date: date | None = None
    player_ids: list[int] = field(default_factory=list)
