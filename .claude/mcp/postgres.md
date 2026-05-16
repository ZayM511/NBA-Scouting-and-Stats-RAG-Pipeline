# postgres (MCP)

Community Postgres MCP server. Direct read-only query access to the project DB so Claude Code can inspect chunks, run sanity checks, and verify schema state without copy-pasting psql output. Major productivity multiplier for a Postgres-heavy project.

## Config (in .mcp.json)

```json
"postgres": {
  "command": "npx",
  "args": [
    "-y",
    "@modelcontextprotocol/server-postgres",
    "${env:POSTGRES_READONLY_URL}"
  ]
}
```

The connection string comes from `POSTGRES_READONLY_URL`. See `.env.example` for the format.

## Connection string format

```
postgresql://<readonly_user>:<password>@<host>:<port>/<database>
```

Example for local dev:

```
postgresql://nbarag_readonly:CHANGE_ME@localhost:5432/nbarag
```

For Neon or another hosted Postgres, the URL will include `?sslmode=require`.

## READ-ONLY role enforcement (critical)

The connection string must point at a user who has `SELECT` privileges only. Create the role at DB init:

```sql
-- One-time setup in the project DB.
CREATE ROLE nbarag_readonly WITH LOGIN PASSWORD 'CHANGE_ME';
GRANT CONNECT ON DATABASE nbarag TO nbarag_readonly;
GRANT USAGE ON SCHEMA public TO nbarag_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO nbarag_readonly;
-- Future tables get the same grant automatically:
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO nbarag_readonly;
```

This is belt-and-suspenders with the `sql-reviewer` agent. The agent rejects DDL/DML on review; the DB role rejects it at execution. Both layers must hold.

## Tools it exposes

- `query` — run a SQL query, return rows.
- `list_schemas`, `list_tables`, `describe_table` — schema inspection.

That's basically it. The MCP server is intentionally narrow; it's a structured way to run read-only SQL.

## Sample queries Claude Code might run for sanity checking

### "Is the GIN index actually being used by the planner?"

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, text, source, date
FROM articles_chunks
WHERE player_ids && ARRAY[201939]::INT[]
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 10;
```

Look for `Bitmap Index Scan on articles_chunks_player_ids_gin` in the plan. If you see `Seq Scan`, the GIN isn't being used — either the index is missing, or the planner thinks a sequential scan is cheaper (which means the corpus is small enough that it doesn't matter yet).

### "How many chunks per player?"

```sql
SELECT
  p.name,
  COUNT(*) AS chunk_count
FROM articles_chunks ac
JOIN unnest(ac.player_ids) AS pid ON true
JOIN players p ON p.player_id = pid
WHERE p.is_top30 = true
GROUP BY p.name
ORDER BY chunk_count DESC
LIMIT 30;
```

Catches imbalances early. If Curry has 800 chunks and Wemby has 12, the prose path will systematically favor Curry. Time to scrape more Wemby content.

### "How fresh is the playoff coverage?"

```sql
SELECT
  source,
  MAX(date) AS most_recent,
  COUNT(*) FILTER (WHERE date >= CURRENT_DATE - INTERVAL '7 days') AS last_week_count
FROM articles_chunks
WHERE date >= '2026-04-15'  -- start of playoffs
GROUP BY source
ORDER BY most_recent DESC;
```

If the most-recent date is more than a day old during the playoffs, the daily refresh isn't running.

### "Are stats actually updating?"

```sql
SELECT MAX(date) AS latest_game FROM games WHERE is_playoff = true;
```

Should be yesterday or today during the playoffs.

## When to use vs the application code

Use the MCP server for **inspection and sanity checks** during dev. Use the application code (`src/retrieve_stats.py`, etc.) for anything that runs in production.

The MCP server is not in the runtime hot path; the application connects with its own connection pool. The MCP server is for the developer (you and Claude Code) to poke around.

## Cost / safety notes

- The read-only role is the single most important defense. Verify it works:

```sql
-- Connect as nbarag_readonly and run:
INSERT INTO players (player_id, name) VALUES (999999, 'test');
-- Should error: ERROR:  permission denied for table players
```

- Never set the MCP server's connection string to the application's write role.
- If the project ever serves multiple users (multi-tenant demo), give each tenant a separate role with row-level security; don't share the readonly role.
