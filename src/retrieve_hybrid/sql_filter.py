"""Hybrid-route SQL filter: generate a SELECT that returns ONLY player_ids
matching the numeric criteria from the question.

This is a specialized variant of `src/retrieve_stats/sql_generator.py`. The
general stats generator can return any shape of result. For the hybrid
route we need exactly one column — `player_id` — so the downstream prose
retrieval can use the resulting set as a ChunkFilters(player_ids=...)
filter.

Same defense-in-depth: tool-use enforces the typed `sql` + `params` +
`explanation` shape; the same `review_sql()` safety layer runs before
execution; execution uses the read-only `nbarag_readonly` role.
"""

from __future__ import annotations

import logging
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
You are the SQL-filter step of a HYBRID retrieval pipeline. The user asked
a compound question that mixes a numeric filter ("guards averaging 20+
points", "players over 35 with TS% above .600") with a qualitative
criterion ("praised for off-ball movement", "written up as future Hall of
Famers"). The qualitative part is handled by the prose retrieval layer in
a follow-up step; YOUR job is only to produce the numeric narrowing.

Hard rules (the safety layer will reject any violation):

1. Return a SINGLE column named `player_id`. No other columns, no aliases.
   Use SELECT DISTINCT player_id, never SELECT *. The downstream layer
   only needs the ID set.

2. SELECT only. No INSERT, UPDATE, DELETE, DDL, COPY.

3. ONE statement, parameterized via %(name)s placeholders for any
   user-controlled values (thresholds, season names, position codes).

4. ORDER BY and LIMIT are encouraged but not required for set-style
   results. If you ORDER BY, prefer a stable ordering (player_id).

5. NEVER attempt to answer the qualitative part in SQL. Don't search
   articles_chunks here. The prose layer handles that.

6. Use the schema as documented below. Restrict to NOT
   pgs.is_clutch_data unless the question explicitly asks for clutch
   stats.

Schema:

{SCHEMA_DESCRIPTION}

Always emit the answer via the generate_sql tool. Never return prose.
"""


@dataclass(frozen=True)
class FilterResult:
    """Result of the hybrid SQL-filter step."""

    player_ids: list[int]
    sql: str
    params: dict[str, Any]
    explanation: str
    safety: Review
    status: str  # 'ok' | 'safety_rejected' | 'gen_failed' | 'exec_failed' | 'empty'
    cost_usd: float = 0.0
    error: str | None = None


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
    # being slightly off — accept 'player_id', 'PLAYER_ID', or the first
    # column if there's only one.
    player_ids = _extract_player_ids(execution.rows, execution.column_names)
    if not player_ids:
        return FilterResult(
            player_ids=[], sql=sql, params=dict(params), explanation=explanation,
            safety=safety, status="empty", cost_usd=rec.cost_usd,
        )

    return FilterResult(
        player_ids=player_ids,
        sql=sql,
        params=dict(params),
        explanation=explanation,
        safety=safety,
        status="ok",
        cost_usd=rec.cost_usd,
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
