"""Hybrid-route SQL: generate a SELECT that answers the numeric half of a
compound question AND identifies the players whose prose chunks should be
retrieved for the qualitative half.

This is a specialized variant of `src/retrieve_stats/sql_generator.py`. The
hybrid SQL is required to include a `player_id` column (so we can narrow
the prose retrieval to those players), and is free to include any other
columns that help answer the numeric half. The full result rows are
handed to the synthesis step alongside the prose chunks.

Same defense-in-depth: tool-use enforces the typed `sql` + `params` +
`explanation` shape; the same `review_sql()` safety layer runs before
execution; execution uses the read-only `nbarag_readonly` role.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import anthropic

from src.config import get_settings
from src.guardrails import Model, guarded_call, record_usage
from src.retrieve_stats.executor import SQLExecutionError, execute_sql
from src.retrieve_stats.prompts import GENERATE_SQL_TOOL
from src.retrieve_stats.schema import SCHEMA_DESCRIPTION
from src.retrieve_stats.sql_generator import _extract_tool_input
from src.retrieve_stats.sql_safety import Review, review_sql

logger = logging.getLogger(__name__)


HYBRID_SQL_GEN_SYSTEM_PROMPT = f"""\
You are the SQL step of a HYBRID retrieval pipeline. The user asked a
compound question that mixes a numeric data need ("clutch TS splits for
SGA", "guards averaging 20+ points") with a qualitative criterion
("praised for off-ball movement", "is he a playoff riser"). The
qualitative part is answered by the prose retrieval step in parallel;
your job is the numeric half and the player set the prose step should
focus on.

Hard rules (the safety layer will reject any violation):

1. INCLUDE `player_id` as one of the SELECT columns. The downstream
   prose step uses these IDs to filter chunks. The column must be named
   exactly `player_id`.

2. INCLUDE whatever other columns answer the user's numeric question.
   - Single-player lookups (clutch splits, season averages): include
     the split column (season_type, etc.) and the relevant metrics
     (gp, pts, fga, fta, ts_pct, etc.).
   - Multi-player rankings ("top scorers shooting >40% from 3"):
     include name, the filter metrics, and ORDER BY + LIMIT to a
     sensible cap (default 10 if unspecified).

3. SELECT only. No INSERT, UPDATE, DELETE, DDL, COPY.

4. ONE statement, parameterized via %(name)s placeholders for any
   user-controlled values (thresholds, season names, position codes).

5. NEVER attempt to answer the qualitative part in SQL. Don't search
   articles_chunks here. The prose layer handles that.

6. Use the schema as documented below.
   - For clutch questions use `player_clutch_stats` (season aggregate).
   - For full-season averages use `player_game_stats` with NOT
     pgs.is_clutch_data and AVG / SUM aggregations.
   - For comparison questions, include both the filter metric AND any
     supporting metric the user might want context on.

Schema:

{SCHEMA_DESCRIPTION}

Always emit the answer via the generate_sql tool. Never return prose.
"""


@dataclass(frozen=True)
class FilterResult:
    """Result of the hybrid SQL step.

    `player_ids` is the deduplicated player set used to filter prose
    retrieval. `rows` is the full result table the synthesis step uses
    to answer the numeric half of the question.
    """

    player_ids: list[int]
    sql: str
    params: dict[str, Any]
    explanation: str
    safety: Review
    status: str  # 'ok' | 'safety_rejected' | 'gen_failed' | 'exec_failed' | 'empty'
    cost_usd: float = 0.0
    error: str | None = None
    rows: list[dict[str, Any]] = field(default_factory=list)
    column_names: list[str] = field(default_factory=list)


class HybridFilterError(Exception):
    """Raised on unrecoverable failure of the hybrid filter step."""


def generate_hybrid_filter(
    question: str,
    *,
    model: Model = Model.SONNET,
    client: anthropic.Anthropic | None = None,
    session_id: str = "hybrid-filter",
    max_output_tokens: int = 1024,
) -> FilterResult:
    """Generate + safety-review + execute the hybrid SQL filter.

    Returns a FilterResult. Caller should check `status == 'ok'` before
    using `player_ids`. Empty results (`status == 'empty'`) are not
    errors — the question just narrowed to nothing.
    """
    if not question or not question.strip():
        raise ValueError("question must be non-empty")

    if client is None:
        settings = get_settings()
        client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key.get_secret_value()
        )

    user_message = question.strip()

    with guarded_call(
        session_id=session_id,
        model=model,
        input_text=HYBRID_SQL_GEN_SYSTEM_PROMPT + "\n\n" + user_message,
        max_output_tokens=max_output_tokens,
    ):
        response = client.messages.create(
            model=model.value,
            max_tokens=max_output_tokens,
            system=HYBRID_SQL_GEN_SYSTEM_PROMPT,
            tools=[GENERATE_SQL_TOOL],
            tool_choice={"type": "tool", "name": GENERATE_SQL_TOOL["name"]},
            messages=[{"role": "user", "content": user_message}],
        )

    tool_input = _extract_tool_input(response, tool_name=GENERATE_SQL_TOOL["name"])
    sql = (tool_input.get("sql") or "").strip()
    params = tool_input.get("params") or {}
    explanation = (tool_input.get("explanation") or "").strip()

    in_tokens = response.usage.input_tokens
    out_tokens = response.usage.output_tokens
    rec = record_usage(
        session_id=session_id,
        model=model,
        input_tokens=in_tokens,
        output_tokens=out_tokens,
    )

    if not sql:
        return FilterResult(
            player_ids=[], sql="", params={}, explanation="",
            safety=Review(approved=False, reasons=["empty sql"]),
            status="gen_failed", cost_usd=rec.cost_usd,
            error="empty sql from model",
        )

    # Safety check.
    safety = review_sql(sql, params=params)
    if not safety.approved:
        return FilterResult(
            player_ids=[], sql=sql, params=dict(params), explanation=explanation,
            safety=safety, status="safety_rejected", cost_usd=rec.cost_usd,
            error="; ".join(safety.reasons),
        )

    # Extra check unique to the hybrid filter: the SQL must reference
    # only the player_id column. We don't parse the SQL; just look at
    # what the executor returns.
    try:
        execution = execute_sql(sql, dict(params))
    except SQLExecutionError as exc:
        return FilterResult(
            player_ids=[], sql=sql, params=dict(params), explanation=explanation,
            safety=safety, status="exec_failed", cost_usd=rec.cost_usd,
            error=str(exc),
        )

    # Pull player_ids out of the rows. Be forgiving about the column name
    # being slightly off: accept 'player_id', 'PLAYER_ID', or the first
    # column if there's only one.
    player_ids = _extract_player_ids(execution.rows, execution.column_names)
    if not player_ids and _has_position_predicate(sql):
        # Defensive retry: positions can be sparsely populated when a roster
        # ingest lags the question. If the only predicate that could have
        # excluded everyone is `players.position`, retry once without it.
        # If the retry returns rows, take those; otherwise fall through to
        # the original empty status (so the user still sees a clear "no
        # players matched" message).
        retry_sql = _strip_position_predicate(sql)
        if retry_sql != sql:
            logger.info(
                "hybrid filter: empty result with a position predicate, "
                "retrying without it",
            )
            try:
                retry_exec = execute_sql(retry_sql, dict(params))
                retry_ids = _extract_player_ids(retry_exec.rows, retry_exec.column_names)
                if retry_ids:
                    return FilterResult(
                        player_ids=retry_ids,
                        sql=retry_sql,
                        params=dict(params),
                        explanation=(
                            (explanation + " " if explanation else "")
                            + "(position predicate dropped — retried after empty result)"
                        ).strip(),
                        safety=safety,
                        status="ok",
                        cost_usd=rec.cost_usd,
                        rows=list(retry_exec.rows),
                        column_names=list(retry_exec.column_names),
                    )
            except SQLExecutionError:
                logger.exception("hybrid filter: position-strip retry failed")
    if not player_ids:
        return FilterResult(
            player_ids=[], sql=sql, params=dict(params), explanation=explanation,
            safety=safety, status="empty", cost_usd=rec.cost_usd,
            rows=list(execution.rows), column_names=list(execution.column_names),
            error="the numeric filter matched zero players (tried with and without the position predicate)" if _has_position_predicate(sql) else None,
        )

    return FilterResult(
        player_ids=player_ids,
        sql=sql,
        params=dict(params),
        explanation=explanation,
        safety=safety,
        status="ok",
        cost_usd=rec.cost_usd,
        rows=list(execution.rows),
        column_names=list(execution.column_names),
    )


def _extract_player_ids(rows: list[dict[str, Any]], cols: list[str]) -> list[int]:
    """Pull integer player_ids out of the rows, deduplicated, preserving
    first-seen order."""
    if not rows or not cols:
        return []
    # Prefer the canonical 'player_id' column, then case-insensitive match,
    # then fall back to the first column if there's only one.
    target_col: str | None = None
    for c in cols:
        if c == "player_id":
            target_col = c
            break
    if target_col is None:
        for c in cols:
            if c.lower() == "player_id":
                target_col = c
                break
    if target_col is None and len(cols) == 1:
        target_col = cols[0]
    if target_col is None:
        logger.warning(
            "hybrid filter: no player_id-like column in result (cols=%s)", cols
        )
        return []

    seen: set[int] = set()
    out: list[int] = []
    for r in rows:
        v = r.get(target_col)
        if v is None:
            continue
        try:
            pid = int(v)
        except (TypeError, ValueError):
            continue
        if pid not in seen:
            seen.add(pid)
            out.append(pid)
    return out


# Matches a single position predicate like `p.position LIKE '%G%'`,
# `players.position = 'G'`, or `position IN ('G','G-F')`. Captures the
# whole predicate so we can splice it out along with any leading/trailing
# AND/OR connectors.
_POSITION_PREDICATE_RE = re.compile(
    r"""
    (?:\bAND\s+|\bOR\s+)?                # optional preceding connector
    \(?                                  # optional opening paren
    \s*(?:[a-z_][\w]*\.)?position\s*     # optional alias.position
    (?:LIKE|=|IN|!=|<>)\s*               # operator
    (?:%\([^)]+\)s|'[^']*'|\([^)]*\))    # %(name)s OR 'literal' OR (IN list)
    \s*\)?                               # optional closing paren
    (?:\s+(?:AND|OR)\s+)?                # optional trailing connector
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _has_position_predicate(sql: str) -> bool:
    """Best-effort: does this SQL reference players.position in a filter?"""
    return bool(re.search(r"\bposition\s*(?:LIKE|=|IN|!=|<>)", sql, re.IGNORECASE))


def _strip_position_predicate(sql: str) -> str:
    """Remove every `players.position` filter predicate from a SELECT,
    leaving the rest of the WHERE clause structurally valid.

    Best-effort regex strip; not a parser. The downstream executor still
    catches any malformed result (rare in practice — the LLM-generated SQL
    uses well-formed `p.position LIKE …` predicates almost without
    exception)."""
    cleaned = _POSITION_PREDICATE_RE.sub(" ", sql)
    # Tidy up WHERE chains: empty WHEREs, dangling AND/OR, double spaces.
    cleaned = re.sub(r"\bWHERE\s+(?:AND|OR)\s+", "WHERE ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(AND|OR)\s+(?:AND|OR)\b", r"\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bWHERE\s+(GROUP|ORDER|HAVING|LIMIT|$)", r"\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned
