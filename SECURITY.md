# Security Policy

This project is a public portfolio RAG system that ingests stats and scouting articles for the 2025-26 NBA season and answers natural-language questions over them. The security posture below reflects how the system handles untrusted input, model output, and cost.

## Scope

What this policy covers:

- The Python pipeline under `src/` (ingestion, normalization, retrieval, synthesis, evaluation).
- The Next.js UI when it ships.
- The Postgres + pgvector database schema and query patterns.
- Every prompt sent to a Claude or Voyage or Cohere endpoint.
- Every chunk retrieved from the vector store.

Out of scope:

- The third-party APIs we call (nba_api, Anthropic, Voyage, Cohere, Braintrust). We trust their TLS but assume nothing about their internal handling.
- Articles scraped from public sources. We treat their content as untrusted input, not as authoritative.

## Threat model — OWASP LLM Top 10 (2025) mapping

| ID | Risk | Applies | Mitigation |
|---|---|---|---|
| LLM01 | Prompt injection | Yes | Strip instruction-like phrases from every retrieved chunk before it reaches a synthesis prompt. Indirect injection through scraped articles is the realistic vector here. |
| LLM02 | Sensitive info disclosure | Yes | Output filter on every response. The corpus is public sports content, so PII risk is low; the real concern is leaking system prompts or internal IDs. |
| LLM03 | Supply chain | Yes | Pin every dependency in `pyproject.toml`. Use `uv lock` for reproducible installs. Review `uv tree` before adding new packages. |
| LLM04 | Data and model poisoning | Yes | Only ingest from a configured allowlist of sources. Every ingest writes a row to an audit log (source, URL, timestamp, content hash). |
| LLM05 | Improper output handling | Yes | Text-to-SQL is the critical path. Every generated SQL goes through the `sql-reviewer` agent. Rejects: DDL, DML, string-concatenated parameters, unindexed joins. The database connection uses a read-only role. |
| LLM06 | Excessive agency | Limited | The agent has read-only DB access and HTTP-out for embedding and rerank APIs. No write tools, no shell, no email. |
| LLM07 | System prompt leakage | Yes | Credentials never go in system prompts. System prompts may be considered exfiltratable; we treat them as such. |
| LLM08 | Vector and embedding weaknesses | Yes | The central RAG risk. Indirect injection via poisoned chunks is mitigated at retrieval time. Embeddings are stored alongside source text and hash, so we can detect tampering. |
| LLM09 | Misinformation | Yes | Every factual claim in an answer requires a citation. The eval set includes "answer-must-cite" checks. The UI surfaces sources prominently so users can verify. |
| LLM10 | Unbounded consumption | Yes | Per-query token cap (8K input, 2K output), per-session cost ceiling ($0.50), aggregate hourly circuit breaker ($5), Haiku→Sonnet→Opus cascade. All centralized in `src/guardrails.py`. |

## Defense-in-depth layers

No single guardrail is enough. Four layers stack:

1. **Input.** Reject prompts over the token cap. Pattern-filter obviously hostile inputs (long sequences of role-switching tokens, base64 blobs, etc.). An LLM classifier picks up the cleverer ones.
2. **Retrieval.** Every chunk gets normalized: strip "ignore previous instructions" and similar patterns, strip role-switching markers (`system:`, `assistant:`), cap chunk size before it reaches the synthesis context. Every retrieval is logged with `chunk_id` and `query_hash` for audit.
3. **Output.** Schema-validate any structured output (the router's `{route, reasoning}` JSON, the SQL query payload). Reject responses that lack citations on factual claims. PII filter runs on free-form text (the corpus is public sports content, so this is belt-and-suspenders).
4. **Telemetry and budget.** Braintrust logs every LLM call with tokens, cost, and latency. The cost circuit breaker reads from the same store. When it trips, the system returns a maintenance message.

## Special note on text-to-SQL

Text-to-SQL is its own injection surface, separate from prompt injection. A model that emits `DROP TABLE players` is doing what it was asked to do, just with the wrong intent. Three layers handle this:

1. **Read-only database role.** The application connects with a role that has `SELECT` only. No `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`. Postgres enforces this at the engine level, not in application code.
2. **`sql-reviewer` agent.** Every generated SQL passes through this agent before execution. It rejects DDL, DML, string concatenation of user input, and queries that miss available indexes.
3. **Parameterized queries.** User-controlled values go through psycopg's parameter binding. The agent flags any code path that concatenates strings into a SQL literal.

## Cost guardrails (LLM10 in detail)

Cost is a security concern, not just a finance one. Three patterns:

1. **Per-query caps.** Hard limit on tokens in and out. Reject and explain.
2. **Per-session ceiling.** Track cost by session ID (authenticated) or IP (public demo). Soft block at $0.50 with a clear message.
3. **Aggregate circuit breaker.** If hourly total exceeds $5, the system returns a maintenance message until manual review.
4. **Model cascade.** Haiku → Sonnet → Opus, escalating only when the cheaper model fails validation. Cuts 5–10x cost on typical queries.

## How to report a vulnerability

Email: `isaiah.e.malone@gmail.com` with the subject line `[security] NBA RAG`. Include reproduction steps and the commit hash you tested against. I'll acknowledge within 72 hours. Please don't open a public GitHub issue for security reports — use email or a private vulnerability advisory on this repo.

## Public-corpus disclosure

Everything ingested by this project is public content (nba_api endpoints, public articles, public Reddit posts) for the 2025-26 season. The corpus contains no personal information beyond what is already public about NBA players in their professional capacity.
