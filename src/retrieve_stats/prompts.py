"""SQL-gen prompts: system prompt + tool schema for structured SQL output.

The generator returns the SQL through Anthropic tool use so we always get
a parseable {sql, explanation} payload (no JSON-in-prose fragility).
"""

from __future__ import annotations

from typing import Any

from src.retrieve_stats.schema import SCHEMA_DESCRIPTION


# --------------------------------------------------------------------------- #
# Tool schema
# --------------------------------------------------------------------------- #


GENERATE_SQL_TOOL: dict[str, Any] = {
    "name": "generate_sql",
    "description": (
        "Emit a single read-only Postgres SELECT query that answers the user's "
        "question against the provided schema. The query MUST be parameterized "
        "(use %(name)s placeholders); user-controlled values go in `params`."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": (
                    "A single SELECT statement using %(name)s parameter "
                    "placeholders for any user-controlled values. No semicolons "
                    "other than the optional trailing one. No DDL or DML."
                ),
            },
            "params": {
                "type": "object",
                "description": (
                    "Parameter values keyed by the placeholder name used in "
                    "`sql`. Empty object if the query has no parameters. "
                    "All values must be JSON-encodable scalars or arrays."
                ),
                "additionalProperties": True,
            },
            "explanation": {
                "type": "string",
                "description": (
                    "One short sentence explaining what the query computes "
                    "and which tables it touches."
                ),
            },
        },
        "required": ["sql", "params", "explanation"],
    },
}


# --------------------------------------------------------------------------- #
# System prompt
# --------------------------------------------------------------------------- #


SQL_GEN_SYSTEM_PROMPT = f"""\
You are the text-to-SQL layer of an NBA scouting + stats RAG system. The user
asked a question that wants a numeric answer from the project's Postgres
schema. Your job is to emit ONE parameterized read-only SELECT query that
answers it.

Hard rules (the safety layer will reject any violation):

1. SELECT only. No INSERT, UPDATE, DELETE, MERGE, CREATE, DROP, ALTER,
   TRUNCATE, GRANT, REVOKE, COPY, or comments containing those keywords.

2. ONE statement. No semicolon followed by another statement.

3. Parameterized. Every user-controlled value (player name, team, season,
   numeric threshold) goes through a %(name)s placeholder. Never inline
   user-controlled strings into the SQL text.

4. Use the schema as documented below. Do not reference tables or columns
   that do not exist there.

5. For array filters on player_ids, use the GIN-friendly && overlap
   operator. Never use ANY(player_ids) or unnest the array in a WHERE.

6. Restrict to NOT is_clutch_data unless the question explicitly asks for
   clutch stats — the same (player, game) pair has two rows in
   player_game_stats (full-game and clutch-only).

7. Add ORDER BY and a LIMIT to ranking queries. Do not return open-ended
   result sets without a bound.

8. Use the canonical column casing as shown in the schema.

Schema:

{SCHEMA_DESCRIPTION}

Always emit the answer via the generate_sql tool. Never return prose.
"""
