# Changelog

All notable changes to this project land here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the versioning is project-phase (Phase A, B, C, ...) rather than semver — this is a portfolio build, not a library release.

## [Unreleased]

### Phase B.1–B.6 — Prose ingestion pipeline shipped (2026-05-16)

End-to-end prose ingestion landed: Reddit JSON → entity resolution → chunking → contextual-retrieval prefix → Voyage embedding → Postgres pgvector. The 5-document smoke test verified every stage works correctly against live data.

**Added**

- `src/normalize_entities/resolve.py` — `AliasResolver` loads the alias map into memory once and resolves `set[int]` of player_ids from raw text via greedy longest-match-first n-gram scanning. Handles diacritics (Dončić → doncic), apostrophes (D'Angelo Russell), hyphens (Karl-Anthony Towns), and possessives (Curry's → Curry). 25 unit tests.
- `src/ingest_prose/chunker.py` — recursive token-based splitter, 400-token target with 15% overlap by default. Recursion order: paragraph → line → sentence → word → hard-cut. Uses tiktoken cl100k_base for counting. 14 unit tests.
- `src/ingest_prose/contextual_prefix.py` — pure function that builds the contextual-retrieval prefix per chunk: `"Article from {source}, {date}, about {comma_separated_players}: {chunk_text}"`. Handles missing fields, dedupes names, collapses long player lists to "and N others". 10 unit tests.
- `src/ingest_prose/embedder.py` — Voyage AI REST wrapper (does NOT use the `voyageai` SDK because it currently fails to import on Python 3.14 due to a pydantic-v1 + `min_items` issue in its multimodal-embeddings module). Batches up to 128 texts per call, retries on 429 / 5xx, distinguishes document vs query input_type for the asymmetric Voyage models.
- `src/ingest_prose/reddit_source.py` — public-JSON ingester (no OAuth per Plan B). Pulls listing + comments per thread, builds the body as `title + selftext + top comments`, respects the 60 req/min rate limit. Validates that the User-Agent isn't a placeholder. 11 unit tests.
- `src/ingest_prose/db.py` — idempotent UPSERTs for `articles` and `articles_chunks`. Article-level skip when content_sha256 matches the stored row. On content change, deletes old chunks and inserts new ones (cascade-safe). Uses `pgvector.psycopg.register_vector` so vectors round-trip as Python lists.
- `src/ingest_prose/pipeline.py` — `ingest_document` orchestrator: upsert article → resolve players from full body → chunk → per-chunk player re-resolution → bulk name lookup → contextual prefix per chunk → one batched Voyage call → replace chunks → audit log. Structured `IngestResult` with status `ingested | unchanged | empty | error`.
- `src/ingest_prose/cli.py` — Typer CLI with `reddit` and `status` commands. `--per-doc-sleep-seconds 25` for Voyage free-tier users (caps at 3 RPM).

**Removed**

- `voyageai` dep in `pyproject.toml`. We call the Voyage REST endpoint directly instead. Saves ~30 MB of transitive deps and fixes Python 3.14 compatibility.

**Smoke test results (5 r/nba top-of-week threads):**

- 4 of 5 ingested successfully (~12 chunks total). The 5th hit Voyage's free-tier 3 RPM rate limit (no payment method on the account). Adding a card on the Voyage dashboard removes the cap (pay-as-you-go from the existing free balance).
- Entity resolution caught the right players: the Wemby flagrant thread resolved Wembanyama + Naz Reid; the LeBron sweep thread caught LeBron + Dillon Brooks; the Spurs moment-of-silence thread caught Brandon Clarke + Jason Collins.
- Vector search verification: the query *"flagrant foul ejection"* returned the Wemby flagrant chunk first at 0.60 similarity, well clear of the next match at 0.45.
- EXPLAIN at the current scale uses Seq Scan (only 12 chunks); HNSW will activate once we cross several hundred chunks.

**Known issues / follow-ups**

- Voyage free-tier rate limit slows full-corpus ingest to ~150 docs/hour. Adding a payment method removes this.
- OneDrive sync occasionally locks `.venv` files mid-install. Workaround for re-syncing: `uv sync --link-mode=copy` and `uv run --no-sync` for routine test runs. Long-term fix: move the project outside OneDrive.
- An article whose embedding call fails leaves an orphan `articles` row with zero chunks. Not load-bearing for retrieval (no chunks means no candidates returned) but worth cleaning up in Phase B.7 if we keep noticing it.

**62 new tests; 123/123 total passing.**

---

### Phase A.2 — Player alias map populated (2026-05-16)

**Added**

- `src/normalize_entities/generate_aliases.py` — Typer CLI with three commands:
  - `sync` LLM-generates aliases for every active player (top-30 first so the famous owner of an ambiguous alias claims it). `--limit N` for partial runs, `--force` to re-process, `--max-cost-usd` as a hard ceiling, `--dry-run` to project cost without spending.
  - `status` prints alias counts per source plus a sample of top-30 aliases.
  - `lookup --query "..."` resolves a single alias string to its player.
- `tests/normalize_entities/test_generate_aliases.py` — 17 unit tests covering normalization (diacritics → ASCII, apostrophes/hyphens preserved, whitespace collapse), JSON parsing edge cases (code fences, prose wrappers, mixed-type arrays), and the canonical-row builder.

**Populated**

| Metric | Value |
|---|---|
| Active players processed | 530 |
| LLM coverage (top 30) | **30 / 30 (100%)** |
| LLM coverage (other active) | 453 / 500 (90.6%) |
| Total alias rows | 1,530 (530 canonical + 1,000 LLM) |
| Total cost (full run) | **$0.88** USD via Claude Sonnet 4.6 |
| Wall time | ~13 minutes (sequential, sleep_ms=0) |

The 47 players without LLM aliases (role players, two-way contracts) returned `[]` from the LLM — correct behavior, the model declined to invent nicknames it wasn't sure about. They still have their canonical full-name row, so they're searchable.

**Quality spot-check** (every entry resolves correctly):

- `the joker` → Nikola Jokić
- `the chef` / `wardell` / `chef curry` → Stephen Curry
- `the beard` → James Harden
- `wemby` → Victor Wembanyama
- `kat` → Karl-Anthony Towns
- `lbj` / `king james` / `bron bron` → LeBron James
- `kd` / `slim reaper` / `easy money sniper` → Kevin Durant
- `sga` → Shai Gilgeous-Alexander
- `the brow` → Anthony Davis
- `dame` → Damian Lillard

**Design notes**

- `ON CONFLICT (alias) DO NOTHING` plus top-30-first ordering handles disambiguation. The famous owner of "Curry" (Stephen) claims the row before Seth Curry can.
- One known disambiguation artifact: `the alien` resolved to Alperen Sengun (player_id 1630578) before Victor Wembanyama (1641705) because Sengun's id sorts first. Both get called "the alien" in fan discourse; hand-editable if we prefer Wemby as the canonical owner.
- Cost tracking went through `src.guardrails.record_usage`, so the hourly circuit breaker would have tripped if anything went wild. The per-session ceiling is intentionally bypassed for ingest paths.

---

### Phase A.1 — Top-30 player selection (2026-05-16)

**Added**

- `src/normalize_entities/select_top30.py` — Typer CLI with three commands:
  - `list-top --limit 50` prints a composite per-game ranking against the live `player_game_stats` data.
  - `apply <id> <id> ... <id30>` flips `is_top30 = TRUE` for exactly 30 player_ids (resets everyone else to FALSE).
  - `status` prints the currently flagged 30.
- `docs/top30-rankings.md` — the final ranking, the rationale for the human edits over the auto-pick, and the "Why SGA at #1" argument with counter-rebuttals to the common criticisms (foul-baiting, not-fun-to-watch, not-good-without-fouls, refs-favor-OKC).
- `tests/normalize_entities/test_select_top30.py` — covers the dataclass immutability and the apply-validation paths.

**Selected (alphabetical, 30 players):**

Alperen Sengun, Amen Thompson, Anthony Edwards, Bam Adebayo, Cade Cunningham, Chet Holmgren, Cooper Flagg, Devin Booker, Donovan Mitchell, Evan Mobley, Giannis Antetokounmpo, Jalen Brunson, Jalen Williams, James Harden, Jaylen Brown, Jayson Tatum, Joel Embiid, Karl-Anthony Towns, Kawhi Leonard, Kevin Durant, Lauri Markkanen, LeBron James, Luka Dončić, Nikola Jokić, Paolo Banchero, Scottie Barnes, Shai Gilgeous-Alexander, Stephen Curry, Tyrese Maxey, Victor Wembanyama.

**Diff from the pure auto-pick (formula in `select_top30.py`):**

- Dropped: Deni Avdija, Josh Giddey, Kevin Porter Jr., Pascal Siakam, Jalen Johnson, Jamal Murray.
- Added: Cooper Flagg, Bam Adebayo, Chet Holmgren, Evan Mobley, Jayson Tatum (22 games, Achilles return), Jalen Williams (35 games, injury-limited).

The two human-overrides through the 25-games floor (Tatum, Williams) are documented inline in `docs/top30-rankings.md`.

Rationale for each edit is in `docs/top30-rankings.md`.

---

### Foundation (2026-05-16) — landed across three commits

**Commit `4867689` — initial scaffold.**

- `CLAUDE.md` (always-on rules + security + chunking defaults), `SECURITY.md` (OWASP LLM Top 10 mapping + defense-in-depth + cost guardrails).
- `.claude/` tooling layer: 4 slash commands (`/smart-commit`, `/write-readme`, `/simplify`, `/new-command`), 4 agents (`tdd-engineer`, `rag-eval-reviewer`, `security-reviewer`, `sql-reviewer`), 2 hooks (`block-secrets.sh`, `auto-format.sh`), 9 skills (chunking, voyage-embeddings, pgvector patterns, NBA entity normalization, interview talking points, brainstorming, dispatching parallel agents, frontend design, playwright browser automation).
- `.mcp.json` + `.claude/mcp/` docs for 7 MCP servers (playwright, jam, filesystem, github, postgres, shadcn, brave-search).
- Postgres + pgvector via docker compose, with a read-only role created at init for the postgres MCP server.
- Schema migration `001_init.sql`: 10 tables (teams, players, player_aliases, games, player_game_stats, play_by_play, articles, articles_chunks, ingest_audit, schema_migrations) with HNSW on chunk embedding, GIN on `articles_chunks.player_ids`, GIN tsvector on chunk text.
- `src/ingest_stats/` package: rate-limited nba_api client (0.6s floor), idempotent UPSERTs, audit log, Typer CLI with `bootstrap` / `refresh` / per-entity commands.
- `src/guardrails.py`: per-query token caps, per-session cost ceiling, Haiku→Sonnet→Opus cascade, hourly aggregate cost circuit breaker, pre-flight cost projection.
- `src/config.py`: pydantic-settings env validator.
- 43-test pytest suite covering config, migration discovery, rate limiter, matchup parsing, TS% math, every guardrail path.

**Commit `a57c5f4` — drop praw, switch Reddit to public JSON endpoints.**

Reddit tightened developer registration in 2024. The public `.json` endpoints serve the same read-only data we need (subreddit feeds, individual threads, comments) at 60 req/min/IP without OAuth. Updated `pyproject.toml`, `CLAUDE.md`, `README.md`, `.env.example`, and the `ingest_prose` docstring.

**Commit `79bd1db` — fix test that was a false negative.**

`test_settings_missing_required_key_raises` deleted the env var but pydantic-settings fell back to reading the developer's `.env`. With a real `.env` present (now expected after setup), the false negative flipped to a real failure. Pass `_env_file=None` so the test isolates the missing-env case.

**Commit `fba9b36` — fix nba_api header override that broke bootstrap.**

`api_client.py` was passing its own `DEFAULT_HEADERS` dict via `kwargs.setdefault`, overriding nba_api's library-level `NBA_STATS_HEADERS` (which carry cookies + per-version tweaks). Result: every endpoint call hung past the 30s timeout. Dropped the headers override; bumped default timeout to 60s. Bootstrap now completes the full 2025-26 season ingest in about 4 seconds.

**Bootstrap result** (run on 2026-05-16, latest game 2026-05-15):

- 30 teams
- 587 active players
- 1,230 regular-season games + 68 playoff games
- 28,185 box-score rows

---

## How this changelog gets updated

Each phase commit's commit-message body is the source of truth. The `/smart-commit` workflow ensures every commit message is concrete and clear; this file rolls them up into a chronological narrative for recruiters reading the repo top-down.

When a new phase ships, add an entry under `[Unreleased]` immediately. Promote `[Unreleased]` to a dated section when the project reaches a meaningful milestone (e.g., "Phase A complete", "First demo recorded").
