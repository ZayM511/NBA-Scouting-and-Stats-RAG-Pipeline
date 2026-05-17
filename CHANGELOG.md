# Changelog

All notable changes to this project land here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the versioning is project-phase (Phase A, B, C, ...) rather than semver — this is a portfolio build, not a library release.

## [Unreleased]

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
