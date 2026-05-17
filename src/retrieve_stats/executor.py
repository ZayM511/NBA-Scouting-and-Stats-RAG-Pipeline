"""Execute approved SQL against the read-only Postgres role.

Connects via `POSTGRES_READONLY_URL` (the nbarag_readonly role created
by `docker/initdb/02_readonly_role.sql`). Even if the safety check
missed something and a DDL/DML statement slipped through, the role's
permissions reject it at the engine level.

Falls back to `POSTGRES_URL` only when the read-only URL is not
configured, with a clear warning. In normal operation the URL should
always be the read-only one.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_settings

logger = logging.getLogger(__name__)


DEFAULT_QUERY_TIMEOUT_MS = 10_000  # 10 seconds; tunable
MAX_ROWS_RETURNED = 1000


@dataclass(frozen=True)
class ExecutionResult:
    """Outcome of running one SQL statement."""

    rows: list[dict[str, Any]]
    column_names: list[str]
    row_count: int
    elapsed_ms: float
    truncated: bool = False
    error: str | None = None


class SQLExecutionError(Exception):
    """Raised when execution fails (timeout, DB error, etc.)."""


def execute_sql(
    sql: str,
    params: dict[str, Any] | None = None,
    *,
    timeout_ms: int = DEFAULT_QUERY_TIMEOUT_MS,
    max_rows: int = MAX_ROWS_RETURNED,
) -> ExecutionResult:
    """Run a read-only SELECT. Returns rows + metadata or raises.

    The connection uses the read-only role; user-supplied params bind via
    psycopg's parameter mechanism (no string concatenation).
    """
    settings = get_settings()
    url = settings.postgres_readonly_url
    if url is None:
        logger.warning(
            "POSTGRES_READONLY_URL not configured; falling back to POSTGRES_URL. "
            "This loses the read-only-role safety net."
        )
        url = settings.postgres_url

    start = time.perf_counter()
    try:
        with psycopg.connect(
            str(url),
            row_factory=dict_row,
            options=f"-c statement_timeout={timeout_ms}",
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or {})
                rows = cur.fetchmany(max_rows + 1)
                column_names = (
                    [d.name for d in cur.description] if cur.description else []
                )
                truncated = len(rows) > max_rows
                if truncated:
                    rows = rows[:max_rows]
    except psycopg.errors.InsufficientPrivilege as exc:
        raise SQLExecutionError(
            "Postgres rejected the query due to insufficient privileges "
            "(this is the read-only role's safety net firing): " + str(exc)
        ) from exc
    except psycopg.Error as exc:
        raise SQLExecutionError(f"{type(exc).__name__}: {exc}") from exc

    elapsed_ms = (time.perf_counter() - start) * 1000
    return ExecutionResult(
        rows=list(rows),
        column_names=column_names,
        row_count=len(rows),
        elapsed_ms=elapsed_ms,
        truncated=truncated,
    )
