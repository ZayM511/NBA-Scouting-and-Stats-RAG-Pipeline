"""Stats retrieval path: text-to-SQL on the Postgres schema.

Generates a parameterized SQL query with Claude Sonnet 4.6, passes it to
the `sql-reviewer` agent for approval, then executes against the read/write
application connection (with a read-only role at the session level for
safety).
"""
