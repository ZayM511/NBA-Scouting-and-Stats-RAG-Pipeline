"""Programmatic SQL safety checks.

Defense-in-depth alongside the read-only Postgres role
(`nbarag_readonly` granted SELECT only). Even if the LLM produces a DDL
or DML statement, the DB will refuse to execute it; this layer rejects
the same statements BEFORE we send anything to the DB, so the failure
surfaces in the application layer with a clear message instead of as a
generic 42501 (insufficient_privilege).

Checks (current rules):

  C1. No forbidden keywords as actual tokens (DDL, DML, COPY, GRANT,
      REVOKE, file-read functions). Substrings inside string literals
      are tolerated by intent — a SELECT on a row that contains the
      word 'DELETE' is fine.
  C2. Single statement. We allow one optional trailing semicolon and
      anything after that semicolon must be whitespace or a comment.
  C3. Starts with a SELECT or WITH (a CTE that opens a query).
  C4. No raw user values inlined: enforced by requiring the SQL to be
      parameterized when the model declared a non-empty `params` dict.
      (We can't tell from the SQL alone whether a literal was
      user-controlled; the contract is the model attests via params.)

Returns a `Review` with `approved: bool`, `reasons: list[str]`. Caller
should refuse to execute when `approved == False`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# Token-aware SQL stripping. The naive `.upper().find('DROP')` would
# match inside string literals ('I love a DROP step'). We strip strings
# and line/block comments before searching for forbidden keywords.
# --------------------------------------------------------------------------- #

_SINGLE_QUOTED = re.compile(r"'(?:''|[^'])*'", flags=re.DOTALL)
_DOUBLE_QUOTED = re.compile(r'"(?:""|[^"])*"', flags=re.DOTALL)
_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", flags=re.DOTALL)


def _strip_strings_and_comments(sql: str) -> str:
    """Replace string literals and comments with empty space so keyword
    scans don't false-match on `'... DELETE ...'` etc."""
    s = _BLOCK_COMMENT.sub(" ", sql)
    s = _LINE_COMMENT.sub(" ", s)
    s = _SINGLE_QUOTED.sub("''", s)
    s = _DOUBLE_QUOTED.sub('""', s)
    return s


# Keywords that must never appear as tokens (after strip).
FORBIDDEN_KEYWORDS: tuple[str, ...] = (
    "INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT", "REPLACE",
    "CREATE", "DROP", "ALTER", "TRUNCATE",
    "GRANT", "REVOKE",
    "COPY",
    "VACUUM", "ANALYZE", "REINDEX",
    "PG_READ_BINARY_FILE", "PG_READ_FILE", "PG_LS_DIR",
    "LO_IMPORT", "LO_EXPORT",
    "DO ",  # PL/pgSQL DO block
)


@dataclass
class Review:
    """Result of the safety check."""

    approved: bool
    reasons: list[str] = field(default_factory=list)
    sql_normalized: str = ""


def review_sql(sql: str, *, params: dict | None = None) -> Review:
    """Run all safety checks on a candidate SQL string."""
    reasons: list[str] = []
    if not sql or not sql.strip():
        return Review(approved=False, reasons=["empty sql"])

    stripped = _strip_strings_and_comments(sql)
    normalized = stripped.upper()

    # C1: forbidden keywords as tokens (word-boundary match).
    for kw in FORBIDDEN_KEYWORDS:
        # Match KW as a whole word (or `DO ` followed by anything).
        pattern = r"\b" + re.escape(kw.strip()) + r"\b"
        if re.search(pattern, normalized):
            reasons.append(f"forbidden keyword: {kw.strip()}")

    # C2: single statement. Strip the optional trailing ; and anything
    # after it must be whitespace.
    body, _, tail = stripped.rstrip().rstrip(";").rpartition(";")
    if body and tail.strip():
        # There's content after a semicolon that isn't the trailing one.
        reasons.append("multi-statement query")

    # C3: starts with SELECT or WITH.
    leading = stripped.lstrip().upper()
    if not (leading.startswith("SELECT") or leading.startswith("WITH")):
        reasons.append(f"query must start with SELECT or WITH (saw: {leading[:20]!r})")

    # C4: if params were declared, the SQL must reference at least one
    # named placeholder. Doesn't catch malicious cases on its own; the
    # read-only role is the actual defense. This is a "model attested it
    # uses params; verify it actually does" check.
    if params:
        if not any(f"%({name})s" in sql for name in params):
            reasons.append(
                "model declared params but no %(name)s placeholders appear in sql"
            )

    return Review(
        approved=not reasons,
        reasons=reasons,
        sql_normalized=stripped.strip(),
    )
