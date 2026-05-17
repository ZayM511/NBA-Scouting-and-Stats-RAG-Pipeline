# NBA Scouting + Stats Hybrid RAG

A hybrid retrieval-augmented system for the 2025-26 NBA season. A query router decides whether a question wants numeric stats from Postgres, qualitative scouting from articles, or both, then a synthesis model answers with citations from both sources.

> **Status (2026-05-17):** stats ingestion, entity normalization, and prose ingestion are live. The query router, synthesis layer, eval set, and UI come next. See [CHANGELOG.md](./CHANGELOG.md) for per-phase commit notes.

## What's working today

- **Stats DB:** 30 teams, 587 players (530 active flagged), 1,298 games (1,230 regular + 68 playoff), 28,185 box-score rows for the 2025-26 season.
- **Top-30 player flag:** the 30 hand-curated players who get deep-dive enrichment. Ranking and rationale in [docs/top30-rankings.md](./docs/top30-rankings.md).
- **Player alias map:** 1,525 aliases mapping nicknames to player_ids. `"the chef"` → Stephen Curry, `"wemby"` → Wembanyama, `"sga"` → Gilgeous-Alexander. Full coverage of the top 30; 90%+ of the rest of the active roster.
- **Prose corpus:** 197 Reddit threads across r/nba, r/Thunder, r/NBASpurs, r/NYKnicks, and r/clevelandcavs (top-of-month). 257 chunks indexed in pgvector. Cost so far: about $0.009 in Voyage embeddings.
- **Vector search works:** queries like `"Cooper Flagg's rookie season"` return the ROY-announcement chunk at 0.51 cosine similarity; `"LeBron at age 41"` returns the 41-year-old box-score thread at 0.65.

## Demo

- **Loom walkthrough (60s):** _coming soon_
- **Live demo:** _coming soon_

## Why this exists

NBA questions split into two worlds. Some are numeric ("What's Jokic's true shooting in the clutch this playoffs?") and live in a database. Others are qualitative ("How do scouts grade Wemby's defensive instincts?") and live in articles. Most RAG demos handle only one side of that split. This project routes each question to the right pipeline and synthesizes one answer that cites both.

Built around the 2025-26 NBA season. Conference Finals tip off on 2026-05-18; the daily refresh keeps the demo current through the Finals (which start 2026-06-03).

## Architecture

```
   ┌─────────────────────────────────────────────────────────────────┐
   │                        DATA LAYER (offline)                     │
   │                                                                 │
   │   nba_api ─▶ Postgres (stats: players, games, player_game_stats,│
   │                         play_by_play for top-30)                │
   │                                                                 │
   │   Articles + Reddit + scouting newsletters                      │
   │       ▼                                                         │
   │   Entity normalizer (alias map: 'the Chef' ─▶ 201939)           │
   │       ▼                                                         │
   │   Chunk @ 400 tokens, 15% overlap, contextual-retrieval prefix  │
   │       ▼                                                         │
   │   Voyage voyage-3-large (1024-dim) ─▶ Postgres + pgvector       │
   │                                                                 │
   └─────────────────────────────────────────────────────────────────┘

   ┌─────────────────────────────────────────────────────────────────┐
   │                        QUERY LAYER (online)                     │
   │                                                                 │
   │   User question                                                 │
   │       ▼                                                         │
   │   Router (Claude Sonnet 4.6)                                    │
   │     ├── STATS  ─▶ text-to-SQL ─▶ sql-reviewer agent ─▶ Postgres │
   │     ├── PROSE  ─▶ hybrid BM25 + dense ─▶ Cohere Rerank 3.5      │
   │     └── HYBRID ─▶ SQL filter, then vector search inside filter  │
   │       ▼                                                         │
   │   Synthesis (Claude Opus 4.7, cascade falls back to Sonnet)     │
   │       ▼                                                         │
   │   Cited answer + tool trace for the visible sidebar             │
   │                                                                 │
   │   Every step traced in Braintrust.                              │
   └─────────────────────────────────────────────────────────────────┘
```

A polished diagram lives at `docs/architecture.png` once the rendering pass lands.

## Sample queries (planned)

| Question | Route | What gets cited |
|---|---|---|
| "What's Jokic's clutch true shooting this playoffs?" | STATS | The exact SQL that ran, with the row count returned |
| "How do scouts grade Wemby's defensive instincts?" | PROSE | Article titles + dates from The Athletic, ESPN, r/nba |
| "Which guards shooting above 40% from three are getting praised for off-ball movement?" | HYBRID | The SQL filter result plus scouting articles about each player |
| "Compare Edwards and SGA's playoff scoring efficiency, and what scouts say about each one's shot creation." | HYBRID | Stats for both + scouting prose for both |

Screenshots land in `docs/screenshots/` once the UI ships.

## Stack

| Tool | Why |
|---|---|
| Python 3.11+ with `uv` | Fast dep management, lockfile reproducibility |
| Postgres 16 + pgvector | One DB for SQL and vectors; hybrid query in one transaction |
| `nba_api` | Official NBA stats endpoints; free |
| `requests` + BeautifulSoup | Article scraping; also Reddit via the public `.json` endpoints (no OAuth — Reddit's 2024 developer rules made registration friction; the JSON path stays free and read-only) |
| Voyage `voyage-3-large` (1024-dim) | Best general-purpose embedding model in 2026 |
| Cohere Rerank 3.5 | Two-stage retrieval: cheap recall, then a smart rerank |
| Claude Sonnet 4.6 | Router and text-to-SQL generation |
| Claude Opus 4.7 | Synthesis (cascade falls back to Sonnet) |
| Claude Haiku 4.5 | Cheap pre-checks; first stop in the cost cascade |
| Braintrust | Tracing every call + stratified eval set |
| Next.js 15 + shadcn/ui + Tailwind | UI (visible tool-use sidebar) |
| Framer Motion + Visx | Transitions + the shot heatmap |

## Design decisions

- **Postgres over SQLite + separate vector DB.** One transaction, one connection pool, one auth model. The hybrid query (filter on `player_ids`, then vector-search the filtered set) is one SQL statement instead of two-system orchestration.
- **Recursive 400-token chunking with 15% overlap.** The 2026 default for generic prose. Each chunk gets a contextual-retrieval prefix (`"Article from {source}, {date}, about {players}: ..."`) before embedding, which Anthropic's 2024 paper shows delivers a 35-50% recall lift on hard queries.
- **`player_ids INT[]` with a GIN index.** Pre-filtering on player ID before vector search drops the candidate set from 200K chunks to roughly 50. That's about a 4000x speedup at the access-path level and a real accuracy lift because irrelevant chunks can't sneak into the top-K.
- **Three-route router.** Stats, prose, and hybrid each have their own path. A single retrieval strategy can't serve numeric and qualitative questions well; the router is the dispatcher.
- **LLM-as-extractor enrichment for the top 30 players.** One-time Opus authored summary per top-30 player, stored as a single high-prior chunk. The query path pays no extra LLM cost; the heavy thinking already happened.
- **Cost cascade.** Try Haiku 4.5 first. Escalate to Sonnet 4.6 only when Haiku declines or fails validation. Reach Opus 4.7 only for genuinely hard synthesis. Typical 5-10x cost reduction with minimal accuracy loss.
- **Text-to-SQL is read-only at three layers.** The DB role grants `SELECT` only, the `sql-reviewer` agent rejects DDL/DML before execution, and the connection pool uses a session-level read-only setting.

## Evaluation

The full Braintrust eval set with stratified stats / prose / hybrid coverage lands with the router and synthesis layers. Until then, this section captures spot-check retrieval quality on the live 257-chunk corpus.

**Spot-check retrievals** (against 197 r/nba and team-sub threads from May 2026):

| Query | Top match (cosine sim) | Why it's the right hit |
|---|---|---|
| `"Cooper Flagg's rookie season"` | 0.51 — ROY announcement thread | Direct news mention |
| `"LeBron at age 41"` | 0.65 — "41 years old LeBron James checks out: 27 PTS" | Box-score post |
| `"Harden trade to Cleveland"` | 0.65 — Cavs Big 3 thread | Trade context |
| `"Wemby's defensive impact at the rim"` | 0.55 — Spurs Wemby/Castle/Clingan sequence | Defensive set |
| `"playoff fatigue in the Western Conference"` | 0.54 — Wolves vs Nuggets elimination | "DENVER NUGGETS HAVE BEEN ELIMINATED" |

**The eval set, once it lands, will track**:

| Experiment | recall@5 | MRR | Notes |
|---|---|---|---|
| Baseline (no rerank) | _pending_ | _pending_ | |
| + Cohere Rerank 3.5 | _pending_ | _pending_ | |
| + Contextual-retrieval prefix | _pending_ | _pending_ | already applied to every chunk; A/B comparison is the experiment |

## Security

This project follows the **OWASP LLM Top 10 (2025)** as the threat-model framework. Every retrieved chunk is treated as untrusted input (LLM01 / LLM08); every text-to-SQL output passes through the `sql-reviewer` agent and a read-only DB role (LLM05); every LLM call goes through `src/guardrails.py` for token caps, per-session cost ceiling, and an hourly circuit breaker (LLM10).

Highlights:

- Hardcoded keys are blocked at write time by `.claude/hooks/block-secrets.sh` (PreToolUse hook on `Write` and `Edit`).
- Every retrieved chunk gets normalized (instruction-like phrases stripped) before reaching a synthesis prompt.
- Per-query cap of 8K input / 2K output tokens. Per-session cost ceiling of $0.50. Hourly aggregate circuit breaker at $5.
- Model cascade (Haiku → Sonnet → Opus) so cheap models handle cheap work.
- Public-corpus disclosure: every ingest source is public NBA content (nba_api endpoints, public articles, public Reddit posts).

Full policy: see [SECURITY.md](./SECURITY.md). For the always-on rules Claude Code reads every session, see [CLAUDE.md](./CLAUDE.md).

## What I tried and rejected

**SQLite + sqlite-vec.** Tempting because zero setup. Rejected because the project needs concurrent writes during ingestion (multiple article workers writing to `articles_chunks` simultaneously) and a single hybrid query that mixes a GIN array filter with a vector ordering. Postgres handles both natively; SQLite would have required two systems.

**Splitting vector storage into Pinecone or Weaviate.** Considered for the operations story. Rejected at this project's scale: a Postgres + pgvector hybrid query stays under a few milliseconds for the corpus size we're targeting, and the two-system orchestration would add latency, an auth surface, and a new failure mode for no measurable benefit. The interview answer holds: I'd reach for a dedicated vector DB above tens of millions of vectors, not below.

**A single retrieval pipeline that handles every question.** The first design sketch tried to run BM25 + dense + rerank for every query and let the synthesis model figure out whether to also do a SQL lookup. It was vague and slow. The three-route router is more code but the eval signal is cleaner: each route can be measured and improved separately.

**Fixed-character chunking.** The path of least resistance for generic prose. Rejected because it splits mid-sentence and mid-word, destroying meaning at chunk boundaries. Recursive chunking that respects paragraph and sentence breaks is the 2026 default and noticeably outperforms fixed-character on every dataset I've seen.

**Trusting the LLM-generated alias map without an audit pass.** The first ingest produced a top-15 mentions list where Kevin Love was #1 with 60 chunk-mentions, despite barely appearing by name. Cause: the alias generator added `love` as a 1-token nickname for Kevin Love, so every Reddit comment saying "I love this play" matched. Same issue for `green` (Jeff Green), `white` (Derrick White), `wolf` (Danny Wolf), `black` (Anthony Black). Fix: deleted the five collision-prone aliases, then re-resolved `player_ids` on the existing 257 chunks (no re-embedding needed; the vectors were already correct, only the filter column was wrong). Post-fix top mentions are exactly what you'd expect for May 2026: Wemby 46, LeBron 35, LaMelo 31, Trae 24, Harden 22, SGA 21. Lesson: LLM-generated alias maps need a single-token-word audit before going live.

**PRAW for Reddit ingestion.** Reddit tightened developer registration in 2024 and the approval queue is slow for new accounts. Rejected the OAuth flow entirely and call the public `.json` endpoints (60 req/min/IP, no auth) — same data, no waiting. PRAW can be added back in 30 minutes if developer access ever lands.

**The voyageai Python SDK.** Voyage's official SDK fails to import on Python 3.14 (pydantic v1 + `min_items` in its multimodal-embeddings module). Rejected the SDK and call the REST `/v1/embeddings` endpoint directly via `requests`. Same API surface; Python 3.14 compatibility; ~30 MB less in the dependency tree.

## Running it locally

Requires Docker, Python 3.11+, and [uv](https://docs.astral.sh/uv/) installed. Bash via Git Bash on Windows for the hooks.

```bash
# 1. Bring up Postgres + pgvector
docker compose up -d

# 2. Install deps
uv sync

# 3. Configure env vars
cp .env.example .env
# edit .env: set ANTHROPIC_API_KEY, VOYAGE_API_KEY, COHERE_API_KEY,
# REDDIT_*, GITHUB_TOKEN, BRAVE_API_KEY

# 4. Apply schema migrations
uv run python -m src.schema.migrate up

# 5. Bootstrap stats (teams + players + every game so far)
uv run python -m src.ingest_stats.cli bootstrap

# 6. (Daily during playoffs) Refresh
uv run python -m src.ingest_stats.cli refresh

# 7. Run tests
uv run pytest
```

The MCP servers wired into `.mcp.json` need `npx`/Node.js available. The Postgres MCP server needs `POSTGRES_READONLY_URL` set to the read-only role created by `docker/initdb/02_readonly_role.sql`.

## Project layout

```
nba-rag/
├── CLAUDE.md                 # always-on project memory for Claude Code
├── SECURITY.md               # OWASP LLM Top 10 mapping, threat model
├── README.md                 # this file
├── .mcp.json                 # MCP server config (7 servers)
├── docker-compose.yml        # Postgres 16 + pgvector
├── pyproject.toml            # Python deps (uv-managed)
├── docker/initdb/            # pgvector + read-only role init SQL
├── src/
│   ├── config.py             # central env-var validation
│   ├── guardrails.py         # LLM10: token caps, cost ceiling, cascade
│   ├── schema/               # migrations + runner
│   ├── ingest_stats/         # nba_api ingestion + daily refresh
│   ├── ingest_prose/         # articles + Reddit (planned)
│   ├── normalize_entities/   # player alias map (planned)
│   ├── router/               # query router (planned)
│   ├── retrieve_stats/       # text-to-SQL path (planned)
│   ├── retrieve_prose/       # hybrid BM25 + dense + rerank (planned)
│   ├── retrieve_hybrid/      # SQL filter then vector (planned)
│   ├── synthesize/           # Claude Opus 4.7 synthesis (planned)
│   └── eval/                 # Braintrust eval set (planned)
├── tests/                    # pytest suite mirrors src/
└── .claude/
    ├── agents/               # tdd-engineer, rag-eval-reviewer, security-reviewer, sql-reviewer
    ├── commands/             # /smart-commit, /write-readme, /simplify, /new-command
    ├── hooks/                # block-secrets.sh (pre), auto-format.sh (post)
    ├── mcp/                  # one-page reference per MCP server
    └── skills/               # chunking, embeddings, pgvector, normalization, talking points, ...
```

## Acknowledgements

Built with Claude Code. Architecture, chunking strategy, MCP server choices, and guardrails follow the RAG Build Guide v3.5 (Earnings Calls + NBA Hybrid).
