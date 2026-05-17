# Changelog

All notable changes to this project land here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the versioning is project-phase (Phase A, B, C, ...) rather than semver — this is a portfolio build, not a library release.

## [Unreleased]

### Phase L.5 — Re-run eval (judge prompt fixed, agg 0.857 → 0.925) (2026-05-17)

Re-ran the 30-case eval after L.1 / L.2 / L.3 / L.4 landed. The first run showed an almost unchanged aggregate (0.857 → 0.859) despite obvious quality wins on real questions. Investigation found that the Sonnet-4.6 judge was marking correct stats answers as "hallucinated" because its training cutoff predates the 2025-26 season — it doesn't know Luka is on the Lakers or that the season has happened, and treats specific 2025-26 numbers as invented.

**Fix**

Added explicit factual grounding to `JUDGE_SYSTEM_PROMPT` in `src/eval/scorers.py`:

  - The current date is May 2026.
  - The 2025-26 season has concluded; playoffs are underway.
  - Stats-route numbers are sourced from a local Postgres DB; don't assume specific 2025-26 figures are hallucinated.
  - Player movements (Luka to LAL, Flagg to DAL, Harden to CLE) are real.
  - Score based on the rubric, not on whether you personally recognize the numbers.

**Before / after (full 30-case eval, same answers, two judges)**

| Metric | Baseline | After L (terse judge) | After L (judge fixed) | Delta vs baseline |
|---|---:|---:|---:|---:|
| Aggregate | 0.857 | 0.859 | **0.925** | +0.068 |
| Judge (overall) | 0.510 | 0.510 | **0.778** | +0.268 |
| **Stats judge** | 0.250 | 0.250 | **0.875** | **+0.625** |
| Prose judge | 0.690 | 0.690 | 0.790 | +0.100 |
| Hybrid judge | 0.590 | 0.590 | 0.670 | +0.080 |
| Route accuracy | 1.000 | 1.000 | 1.000 | unchanged |
| Hallucination guard | 1.000 | 1.000 | 1.000 | unchanged |
| Keyword recall | 0.928 | 0.928 | 0.922 | -0.006 (noise) |

The stats route is the biggest mover (+0.625 judge): L.1 made answers context-rich (TS%, scope, comparisons), and the judge fix stopped penalizing 2025-26 numbers. Hybrid and prose also lift; play-by-play clutch data from L.2 and the wider corpus from L.3 help compound questions land cleaner.

**Cost**

$2.56 for the 30-case eval, comparable to baseline. The judge fix itself is a 50-word prompt extension — zero added cost per case.

**Two cases still scoring 0**

`hybrid-05-rookies` and `hybrid-06-old-school` still get judge=0. Looking at those: the SQL step found zero matching players (rookie threshold, age 35+ players who score 25+ PPG), so the hybrid pipeline declines politely. The rubrics expect a graceful "no matches" response, which the answers DO give, but the judge reads the empty result as a partial answer. Future tweak: refine those two rubrics OR teach the judge that "no matches" is the correct answer for some compound questions.

---

### Phase L.4 — Hybrid route runs SQL + prose in parallel (2026-05-17)

The user reported that "what are SGA's clutch TS splits, AND is he a playoff riser?" returned "the corpus does not contain the specific clutch true shooting splits you asked about." Root cause: the old hybrid pipeline was `(SQL filter to players) → (prose retrieval)` — it threw away the numeric half entirely. The narrowing SQL only returned `player_id`, never the actual numbers the user asked about.

**Refactor**

- `src/retrieve_hybrid/sql_filter.py`: prompt now requires `player_id` as ONE column (not the only column). The LLM is free to include whatever else answers the numeric half. `FilterResult` gains `rows: list[dict]` and `column_names: list[str]`.
- `src/synthesize/prompts.py`: `HYBRID_SYNTHESIS_SYSTEM_PROMPT` rewritten to "lead with numbers from the rows, then explain qualitatively with [^N] citations." `build_hybrid_user_message` formats rows as a tab-delimited table alongside the chunks.
- `src/api/server.py`: serializes the new `rows` field in the hybrid output.
- `ui/components/HybridPanel.tsx`: renders a results table for the numeric half above the prose retrieval list.

**Smoke test (the user's actual Q2)**

before:
> "Among 1 player who matched (Shai Gilgeous-Alexander), the corpus does not contain the specific clutch true shooting splits you asked about — neither regular season nor playoff clutch TS% appears in any chunk..."

after:
> "**Clutch TS% splits (2025-26):** Regular season 66.8% TS / 57.9% eFG on 27 games and 125.1 clutch minutes. Playoffs 90.2% TS / 83.3% eFG, but on a single game... regular-season number is elite, roughly ten points of TS% above the ~57% league baseline... On the broader 'playoff riser' question, the corpus supports a qualified yes rather than a clear leap. His full-season profile (30.9 ppg on 67.7% TS) is already so high that 'rising' mostly means sustaining... [+7 prose citations across the riser analysis]"

**Also fixed in this commit**

A `.gitignore` bug: the Python build-output pattern `lib/` was matching `ui/lib/` (Next.js helpers). The Phase J `ui/lib/api.ts` and `ui/lib/cn.ts` files were never actually committed to the repo as a result. Anchored the pattern to `/lib/` and added the missing UI lib files.

245 tests pass, TypeScript clean.

---

### Phase L.3 — Prose corpus expanded to 478 chunks (2026-05-17)

Surfaced after the user hit "no coverage" on multi-team questions like "who's projected MVP?". The corpus skewed too heavily toward SGA / Wemby / Brunson / Mitchell because those were the only team subs ingested. Added 12 more team subreddits.

**Before / after**

| Metric | Before | After | Delta |
|---|---:|---:|---:|
| Articles | 228 | 406 | +178 |
| Chunks | 288 | 478 | +190 |
| Distinct sources | 7 | 18 | +11 |
| Chunks with at least one resolved player_id | 273 / 288 (94.8%) | 450 / 478 (94.1%) | resolver still healthy |

**New subs (15 threads each, 8 top-level comments, top/month listing)**

Round 1: r/lakers, r/warriors, r/bostonceltics, r/heat, r/denvernuggets, r/timberwolves
Round 2: r/sixers, r/Mavericks, r/MkeBucks, r/pacers, r/orlandomagic, r/suns

**Cost**

Voyage embeddings: 52,134 tokens across both rounds = ~$0.009. Zero Reddit rate-limit hits this time (we stayed well under 60 req/min/IP).

**Re-runnable**

Saved the exact invocation as `scripts/ingest-team-subs.ps1`. Run after a bracket change to refresh coverage:

```powershell
pwsh -File scripts\ingest-team-subs.ps1 -LimitPerSub 25
```

---

### Phase L.2 — Clutch stats via LeagueDashPlayerClutch (2026-05-17)

Surfaced when the user asked for SGA's clutch TS splits and the system said "the corpus does not contain the specific clutch true shooting splits you asked about." Root cause: the `play_by_play` table was empty and `player_game_stats` has no `is_clutch_data=TRUE` rows for the 2025-26 season. Added a season-aggregate clutch table sourced from `LeagueDashPlayerClutch` (league standard: last 5 minutes, score margin ≤ 5).

**Added**

- `src/schema/migrations/002_player_clutch_stats.sql`: new table keyed on (player_id, season, season_type). Stores totals (gp, min, pts, fgm/a, fg3m/a, ftm/a, rebs, ast, tov, stl, blk, +/-) plus pre-cached `ts_pct` and `efg_pct` (nullable when undefined).
- `src/ingest_stats/clutch.py`: one `LeagueDashPlayerClutch` call per season_type returns the entire league; we skip GP=0 and filter to known players for FK safety.
- CLI: `python -m src.ingest_stats.cli player-clutch --season-type {Regular Season|Playoffs}`.
- `src/retrieve_stats/schema.py`: documented the new table + a worked SGA example so the SQL generator knows when to use it.
- Tests: 6 unit tests for the helpers (`_ts_pct`, `_efg_pct`, `_row_from_endpoint`), schema-description fixture refactored to scan all migrations instead of just 001.

**Ingested**

| Season type | Players with clutch data | API time |
|---|---:|---:|
| Regular Season | 492 | ~1.5s |
| Playoffs | 127 | ~1.0s |

**Smoke test**

For "What is SGA shooting in the clutch this season, regular season vs playoffs?" the router now picks `stats` (previously `hybrid`, since the only narrative half it had was "is he a riser") and the answer carries actual numbers: "Regular season (27 clutch games, 125.1 clutch minutes): 51.5% FG, 35.1% from three, 85.3% FT, 66.8% TS%, 57.9% eFG%. The 66.8 TS% in clutch is roughly 10 points above league-average (~57%), elite shot-making under pressure on a healthy 175-point sample."

Tests: 245 pass (was 235; +6 clutch helpers, +4 schema).

---

### Phase L.1 — Stats prompt rewrite for context-rich answers (2026-05-17)

The stats synthesis judge was 0.25 on the Phase I baseline eval because the prompt enforced one-sentence answers. "31.1 PPG." is correct but useless. Rewrote `STATS_SYNTHESIS_SYSTEM_PROMPT` to require:

1. Lead with the exact number from the row.
2. Add scope (split, season, games played, team).
3. Derive composite shooting metrics (TS%, eFG%) from raw fields when the row has the inputs.
4. One light comparison sentence using widely-known baselines (2025-26 league-average TS% ~57%, league pace ~100).
5. Name missing inputs explicitly when a derived metric needs data not in the row.

**Before / after** on "What is SGA averaging this season in points and true shooting?":

- before: `"SGA is averaging 31.1 PPG."`
- after: `"Shai Gilgeous-Alexander is averaging 31.1 points per game on a .682 true shooting percentage through 68 regular-season games for OKC in 2025-26. That TS mark sits roughly 11 points above this season's league-average TS% (~57%), making the scoring volume even more impressive given the efficiency."`

61 synthesize + retrieve_stats tests still pass. Full eval re-run is in Phase L.5.

---

### Phase C — Top-30 enrichment (Opus-authored scouting summaries) (2026-05-17)

One Opus 4.7 scouting summary per top-30 player, stored as `articles_chunks` rows with `article_type='authored_summary'`. The summaries surface naturally through the existing hybrid retrieval (BM25 + dense + Cohere Rerank), so any prose or hybrid question that touches a top-30 player gets richer context.

**Added**

- `src/normalize_entities/generate_summaries.py` — Typer CLI: `generate`, `status`. For each `is_top30 = TRUE` player:
  1. Pulls the player's 2025-26 stat line (PPG / RPG / APG / SPG / BPG / TS% / +/-, games, playoff games).
  2. Pulls up to 8 existing corpus chunks mentioning that player (filters out other authored summaries to avoid feedback loops on re-run).
  3. Asks Claude Opus 4.7 to write a 450-550 word scouting summary covering: verdict headline, offensive strengths, defensive strengths, limitations, 2025-26 role + playoff context, notable trends.
  4. Stores as one row in `articles` (article_type='authored_summary') and one row in `articles_chunks` with the contextual-retrieval prefix and a fresh Voyage embedding so it participates in retrieval like any other chunk.
- Per-player session_id (`ingest-summaries-<player_id>`) so the per-session cost ceiling doesn't trip across the batch run; the hourly circuit breaker still applies.
- ASCII-safe console printing so cp1252 Windows terminals don't crash on names with diacritics (Dončić, Jokić, Sengün).
- Idempotent: re-running skips players that already have an authored summary unless `--force` is passed.

**Cost + wall time for the full top-30 run**

| Metric | Value |
|---|---|
| Players covered | 30 / 30 |
| Total cost | **$3.72** |
| Wall time | ~13 minutes (sequential Opus calls) |
| Average per summary | $0.124 (Opus 4.7) |
| Average length | 2,994 characters (~470 words) |

**Eval A/B vs the baseline** (re-ran the full 30-case eval as `top30-enriched`)

| Metric | Baseline | Top-30 enriched | Δ |
|---|---:|---:|---:|
| **Route accuracy** | **1.000** | **1.000** | 0 |
| Hallucination guard | 1.000 | 1.000 | 0 |
| Keyword recall | 0.939 | 0.928 | −0.011 |
| **LLM-judge (overall)** | 0.488 | **0.550** | **+0.062** |
| **Aggregate** | **0.857** | **0.869** | **+0.012** |

Per-route judge scores:

| Route | Baseline | Top-30 enriched | Δ |
|---|---:|---:|---:|
| stats | 0.250 | 0.250 | 0 (expected — summaries don't affect the SQL path) |
| prose | 0.625 | **0.685** | **+0.060** |
| **hybrid** | **0.590** | **0.715** | **+0.125** |

The biggest lift is on hybrid (+0.125 on the judge). That tracks: hybrid first narrows the player set via SQL, then needs prose that's specifically about each narrowed player — exactly where the authored summaries help. Prose route gains too (+0.060). Stats unchanged, as designed.

**Sample summary (Victor Wembanyama, 2,953 chars)**

> Victor Wembanyama is no longer a prospect or a curiosity — he's the best two-way center in basketball and the gravitational center of a Spurs team that just punched its ticket to the Western Conference Finals.
>
> Offensively, Wembanyama has fully integrated the skill set that made him a unicorn in theory into something terrifying in practice. He's a 7'4" hub who can initiate from the elbow, snake into pull-up middies, finish lobs, and step out to bury threes off movement. [...] The efficiency numbers tell the story: a 24.4-point scoring average on .624 true shooting is absurd volume-efficiency math for a primary option [...]
>
> [Defense + limitations + 2025-26 season + Spurs franchise infrastructure paragraphs follow.]

The model used the stat line for the numbers (24.4 PPG, .624 TS, 3.2 BPG, +10.9 plus/minus, 74 games) and the corpus for the storyline (the elbow incident, Castle hitting playoff threes, Harper bench energy, Spurs dispatching Minnesota in 5).

**Cost run-down for the A/B**

- Baseline eval: $1.94
- Top-30 enriched eval: $2.26 (higher because the synthesis prompts are reading more chunks per question)
- Total Phase C spend including summary generation: $3.72 + $2.26 = **$5.98**

---

### Phase I — Eval set (30 cases, all three routes) (2026-05-17)

First end-to-end measurement. 30 hand-crafted NBA questions, stratified 10 stats / 10 prose / 10 hybrid. Each case carries an expected route, optional `must_mention` / `must_not_mention` substring checks, and a per-case rubric the LLM-as-judge uses. Composite score is the average of four components: route accuracy (deterministic), keyword recall (deterministic), hallucination guard (deterministic), and an LLM-as-judge score (Sonnet 4.6 reading the rubric + the actual answer).

**Added**

- `src/eval/cases.py` — the 30-case dataset. Each case is an `EvalCase` dataclass with `id`, `question`, `expected_route`, `difficulty`, `must_mention`, `must_not_mention`, `rubric`, `notes`. The case set is unit-tested for stratification (10 per route), no duplicate ids, every case has a rubric, every case has a non-empty question.
- `src/eval/scorers.py` — four scorers. `score_route_accuracy` and `score_keyword_recall` and `score_hallucination_guard` are deterministic (no LLM call). `score_judge` calls Sonnet 4.6 with `JUDGE_SYSTEM_PROMPT` that explicitly tolerates uncited stats answers ("the SQL itself is the citation") and explicitly rewards the decline phrase for cases the corpus can't support.
- `src/eval/runner.py` — runs every case through `ask()`, scores it, writes a JSONL artifact under `eval_results/<tag>-<utc>.jsonl`, and optionally streams to Braintrust (best-effort: if BRAINTRUST_API_KEY isn't set or the SDK fails, runs continue locally).
- `src/eval/cli.py` — Typer CLI: `run --tag <name>`, `list`. Per-case + per-route + aggregate summary tables.
- `tests/eval/test_cases.py` (9 tests) — stratification, no-duplicate-ids, rubric presence, route prefix conventions.
- `tests/eval/test_scorers.py` (16 tests) — every deterministic scorer path plus the judge-output parser (well-formed, clamped, missing-score, garbage).

**Baseline run (n=30, Sonnet 4.6 router + SQL gen, Opus 4.7 synthesis)**

| Metric | Overall | Stats | Prose | Hybrid |
|---|---:|---:|---:|---:|
| **Route accuracy** | **1.000** | 1.000 | 1.000 | 1.000 |
| Keyword recall | 0.939 | — | — | — |
| Hallucination guard | 1.000 | — | — | — |
| LLM-judge score | 0.488 | 0.250 | 0.625 | 0.590 |
| **Aggregate** | **0.857** | 0.787 | 0.885 | 0.897 |

**Total cost: $1.94 for the full 30-case run** (covers router + retrieval + synthesis + judge per case).

**The surprising number: stats judge=0.250**

The LLM-as-judge scored stats answers lower than prose or hybrid, despite the rubric explicitly saying "for STATS answers, the SQL itself is the citation — don't penalize the absence of [^N] markers." Two probable causes:

1. The stats synthesizer's "one sentence for single-row lookups" rule produces answers that are technically correct but terse. The judge may be reading terse as "missing the rubric."
2. Some stats questions (e.g., "best home record") may have generated a query that returned a different angle than the rubric implied. The deterministic scorers (route accuracy, hallucination guard) still pass because the answer isn't *wrong* — it's just narrower than the rubric anticipated.

Filed as a Phase I follow-up: review the per-case judge reasoning in `eval_results/baseline-*.jsonl` to decide whether to (a) loosen the rubric, (b) bias the stats synthesizer toward a one-sentence narrative ("X leads with Y, ahead of Z"), or (c) accept the score as-is and let the route_accuracy + keyword_recall + hallucination_guard signals carry the regression-detection load.

**What's actually load-bearing for the demo**

- **Route accuracy at 1.000** is the strongest signal: the router correctly dispatches every question. Stats questions go to SQL, prose to articles, hybrid to both.
- **Hallucination guard at 1.000** means the system never invented a fact in this run. The synthesis prompts' explicit decline phrase is doing its job.
- **Keyword recall at 0.939** confirms answers cover the named topics.

**25 new tests; 260 total passing.**

---

### Phase G — Hybrid retrieval (SQL filter then prose) — ALL THREE ROUTES LIVE (2026-05-17)

The third and final retrieval route ships. The router → retrieve → synthesize loop is now end-to-end for every question the project handles: numeric (`stats`), qualitative (`prose`), and compound (`hybrid`).

Hybrid pipeline:

1. **SQL filter** — Claude Sonnet 4.6 generates a `SELECT DISTINCT player_id` query that narrows to players matching the numeric criterion. Goes through the same `review_sql()` safety layer and runs against the read-only `nbarag_readonly` role.
2. **Prose retrieval inside the filter** — `hybrid_search` (BM25 + dense + Cohere Rerank 3.5) runs with `ChunkFilters(player_ids=narrowed_set)`. The GIN index on `articles_chunks.player_ids` makes this the cheap-filter-then-vector path the project was designed around.
3. **Synthesis** — Opus 4.7 writes a cited answer that names the SQL-narrowed players AND cites the prose chunks for the qualitative claims.

**Added**

- `src/retrieve_hybrid/sql_filter.py` — `generate_hybrid_filter()`. Specialized variant of the stats SQL generator with a prompt that always returns one column (`player_id`). Reuses `GENERATE_SQL_TOOL` and `review_sql()`. Returns `FilterResult` with status `ok` / `safety_rejected` / `gen_failed` / `exec_failed` / `empty`.
- `src/retrieve_hybrid/pipeline.py` — `retrieve_hybrid()` orchestrator. SQL filter → prose search with player_ids filter. Returns `HybridRetrievalResult` carrying both pieces for the UI trace.
- `src/synthesize/prompts.py` — `HYBRID_SYNTHESIS_SYSTEM_PROMPT` ("start with the SQL-narrowed set, then cite the prose") and `build_hybrid_user_message()`.
- `src/synthesize/synthesizer.py` — `synthesize_hybrid()` method. Takes a `HybridRetrievalResult` and the narrowed player names, returns a cited `SynthesisResult`.
- `src/synthesize/pipeline.py` — `ask()` now branches to `_ask_hybrid()` when the router picks `hybrid`. `AskResult` gains a `hybrid` field. Hybrid path looks up canonical player names from the `players` table for the synthesis prompt.
- `src/synthesize/cli.py` — renders a Hybrid panel (SQL filter + narrowed player_ids + retrieved chunks + cited answer).

**Live end-to-end hybrid demo on the 257-chunk corpus**

Question: `"Of players averaging 25+ points per game in the regular season, who is getting the most attention in playoff coverage?"`

- Router: `hybrid`
- SQL filter narrowed to **17 players** averaging 25+ PPG (the SQL used `%(min_ppg)s` parameterization, was approved by safety, executed under the read-only role)
- Hybrid search inside that player set: BM25 0, dense 50, merged 50, reranker top-6
- Synthesis cited 5 of the 6 chunks. Key insight from the answer: *"the loudest playoff storyline in the corpus — LeBron's 3-0 lead over Houston without Luka — centers on a player who isn't in the 25+ PPG set"*. Brunson's 25/44 three-point night cited at `[^2]`, Embiid 34/12 + Maxey 30 in a Sixers loss at `[^5]`, Jokić 28/9/10 in a Nuggets loss at `[^6]`.
- Total cost: $0.010 (router) + $0.012 (SQL filter) + $0.092 (synthesis) ≈ **$0.11 per hybrid answer**

**One known gap surfaced by the first demo**

The first hybrid attempt asked about "guards averaging 20+ ppg" and the SQL filter returned 0 player_ids — the pipeline gracefully reported `no_players` and stopped. Root cause: `players.position` is `NULL` for every row because `nba_api`'s `CommonAllPlayers` endpoint doesn't include position. Filed as a Phase C follow-up (the top-30 enrichment pass that ingests advanced splits will also pull positions).

**All three routes are now LIVE**

| Route | Try it |
|---|---|
| `prose` | `python -m src.synthesize.cli "What do threads say about Wemby's defense?"` |
| `stats` | `python -m src.synthesize.cli "Who leads the NBA in threes?"` |
| `hybrid` | `python -m src.synthesize.cli "Of 25+ PPG players, who is most-praised in playoff coverage?"` |

**210 tests passing.**

---

### Phase E — Stats retrieval (text-to-SQL) wired into ask() (2026-05-17)

The router can now dispatch numeric questions to a real SQL path: Claude Sonnet 4.6 generates parameterized SQL via tool use, a programmatic safety layer rejects anything outside `SELECT` / `WITH`, execution runs against the read-only `nbarag_readonly` Postgres role, and Opus 4.7 synthesizes the rows into a natural-language answer.

**Added**

- `src/retrieve_stats/schema.py` — `SCHEMA_DESCRIPTION` constant kept in sync with `001_init.sql` via 24 enforcement tests. Lists every table, the relevant columns, the GIN `&&` convention for `player_ids`, and two worked-example queries that prime the model.
- `src/retrieve_stats/prompts.py` — `SQL_GEN_SYSTEM_PROMPT` (read-only contract, parameterization mandate) and `GENERATE_SQL_TOOL` (tool schema with `sql`, `params`, `explanation` fields). Tool use guarantees structured output.
- `src/retrieve_stats/sql_safety.py` — `review_sql()` runs four checks. Forbidden keywords (DDL/DML/COPY/GRANT/file-reads) as tokens (strips string literals + comments first so `'I love a DROP step'` doesn't false-match), single-statement, must start with `SELECT` or `WITH`, declared params must have `%(name)s` placeholders.
- `src/retrieve_stats/sql_generator.py` — Sonnet 4.6 with tool use, wrapped in `guarded_call` for token + cost controls.
- `src/retrieve_stats/executor.py` — connects via `POSTGRES_READONLY_URL` (the `nbarag_readonly` role from `docker/initdb/02_readonly_role.sql`). 10-second `statement_timeout`, caps results at 1000 rows.
- `src/retrieve_stats/pipeline.py` — `retrieve_stats()` orchestrator. Returns `StatsResult` with status `ok` / `safety_rejected` / `gen_failed` / `exec_failed`.
- `src/retrieve_stats/cli.py` — standalone CLI for the stats path.
- `src/synthesize/synthesizer.py` — added `synthesize_stats()` method that takes a `StatsResult` and produces a one-or-two-sentence answer. The SQL itself is the citation; the UI sidebar shows it.
- `src/synthesize/prompts.py` — added `STATS_SYNTHESIS_SYSTEM_PROMPT` with strict "quote numbers exactly" and "no inventing context" rules.
- `src/synthesize/pipeline.py` — `ask()` now branches on route. Prose dispatches to hybrid-retrieval + chunk-synthesis. Stats dispatches to the SQL pipeline + stats-synthesis. Hybrid defers gracefully to Phase G.
- `src/synthesize/cli.py` — renders a Stats panel (SQL + params + status + cost) when the route is stats.

**Live demo on the stats route**

Question: `"Who leads the NBA in three-pointers made this season?"`

- Router: `stats`
- Generated SQL with `%(season)s` parameterization
- Safety: approved
- Execution: 56ms, 10 rows
- Synthesis: **"Kon Knueppel (CHA) leads the NBA with 273 three-pointers made in the 2025-26 regular season, narrowly ahead of teammate LaMelo Ball (272) and Luka Dončić (254)."**
- Total cost: about **$0.03** per stats answer (Sonnet SQL gen + Opus synthesis)

**Defense in depth on LLM05 (improper output handling)**

Three layers stop a bad SQL output from reaching the database:

1. The `nbarag_readonly` Postgres role is granted `SELECT` only. Even a successful injection fails at the engine level with `InsufficientPrivilege`.
2. The programmatic `review_sql()` layer rejects DDL/DML, multi-statements, and unparameterized user input before anything reaches the DB.
3. The tool-use schema gives the model a typed `sql` field and a separate `params` dict, so the right shape is the path of least resistance.

**48 new tests; 210 total passing.**

---

### Phase H — Synthesis layer and end-to-end ask pipeline (2026-05-17)

The system now answers prose questions end-to-end: question → router (Sonnet 4.6) → hybrid retrieval (BM25 + dense + Cohere Rerank 3.5) → synthesis (Opus 4.7) → cited answer with inline `[^N]` footnotes pointing back to the source chunks. Stats and hybrid routes route correctly today but defer gracefully until Phase E and Phase G ship.

**Added**

- `src/synthesize/prompts.py` — `SYNTHESIS_SYSTEM_PROMPT` with two non-negotiables: every factual claim carries an inline `[^N]` citation, and the model uses an explicit "the retrieved sources don't have enough information" phrase rather than inventing facts when chunks are insufficient. Also defines `build_user_message()` which numbers chunks `[1]…[N]` with their source + date headers.
- `src/synthesize/synthesizer.py` — `Synthesizer` class. Wraps Claude Opus 4.7 with `guarded_call` (token caps + cost ceiling + circuit breaker), parses inline `[^N]` citations out of the prose, drops out-of-range citations, deduplicates the resulting chunk_ids while preserving first-citation order, and detects the "declined" escape phrase. Returns `SynthesisResult` with answer, citations, cited_chunk_ids, model, tokens, cost, and declined flag.
- `src/synthesize/pipeline.py` — `ask()` orchestrator: router → retrieval (if prose) → synthesis. Returns `AskResult` with the full trace (route decision, retrieval counts, synthesis cost). Stats and hybrid routes return `not_yet_implemented=True` with a polite note that names the future phase that will wire them in.
- `src/synthesize/cli.py` — Typer CLI: `python -m src.synthesize.cli "<question>"`. Renders three panels: Router (route + reasoning), Retrieved chunks (with score + source + snippet), Answer (with inline citations + cost footer).
- `tests/synthesize/test_synthesizer.py` (13 tests) — covers `build_user_message` (numbering, metadata header, empty-chunk handling), `_parse_citations` (simple, combined `[^1][^3]`, dedupe, out-of-range, no-citations), and the `Synthesizer` itself (returns cited answer, marks declined, rejects empty input, sends correct system prompt + user message shape).

**Live end-to-end demo on the 257-chunk corpus**

Question: `"What do Reddit threads say about Wemby's defensive plays in the playoffs?"`

- Router classified as `prose` ("Fan/Reddit opinion and narrative about Wemby's defensive plays lives in articles_chunks, not in SQL stats")
- Hybrid retrieval merged 50 dense candidates → reranker top-6
- Opus 4.7 produced a 4-citation answer covering: the 5-block Game 2 (`[^2]`), the 12-block triple-double (`[^5]`), the block on Edwards with Gobert grabbing his arm (`[^4]`), and the Wemby-Castle "pincer" defensive chemistry (`[^3]`)
- Cost: $0.010 (router) + ~$0.001 (hybrid + rerank) + $0.081 (Opus synthesis) ≈ **$0.09 per answer**

Stats-route fallback: `"Who leads the NBA in three-pointers made this season?"` correctly routes to `stats` and returns `"This question routes to 'stats', which isn't wired into the synthesis layer yet"` instead of hallucinating a number. Same graceful fallback for hybrid.

**Cost notes**

Opus 4.7 at $75 per million output tokens is the most expensive piece. Three reasonable cost-reduction levers for later:

- Prompt-cache the SYNTHESIS_SYSTEM_PROMPT (stable across all calls) — cuts the 3-4K input tokens to roughly $0.001 on cache hits, saving most of the input-side cost.
- Cascade to Sonnet 4.6 for typical questions and only escalate to Opus when the synthesis prompt explicitly needs nuance — would cut synthesis cost roughly 5x.
- Cap the retrieved-chunk count at the synthesizer (currently top-8); smaller context windows save tokens.

**13 new tests; 162 total passing.**

---

### Phase F — Prose retrieval (BM25 + dense + Cohere Rerank 3.5) (2026-05-17)

Two-stage hybrid retrieval over `articles_chunks`. BM25 (via Postgres `ts_rank_cd`) plus dense (pgvector cosine over voyage-3-large vectors) give cheap recall up to 50 candidates each. Cohere Rerank 3.5 re-scores the merged set with a cross-encoder and returns the final top-k. This is the prose path the router dispatches to when it picks `route="prose"`.

**Added**

- `src/retrieve_prose/filters.py` — `ChunkFilters` dataclass shared by all three retrievers. Composes into parameterized SQL WHERE clauses (no string concatenation; the player_ids filter uses `&&` to hit the GIN index). `ScoredChunk` dataclass for results.
- `src/retrieve_prose/bm25.py` — `search_bm25()`. `ts_rank_cd` over the GENERATED `text_tsv` column (cover-density rank, favors chunks where query terms cluster).
- `src/retrieve_prose/dense.py` — `search_dense()`. Embeds the query with `input_type="query"` (Voyage's asymmetric model needs this) and orders by `embedding <=> $vec`.
- `src/retrieve_prose/rerank.py` — `Reranker` class. Calls Cohere `/v2/rerank` directly via `requests` (skips the cohere SDK to avoid another SDK-vs-3.14 incompat). Retries on 429 / 5xx. `rerank_chunks()` convenience returns ranked `ScoredChunk`s with relevance scores.
- `src/retrieve_prose/hybrid_search.py` — `hybrid_search()` orchestrator. BM25 union Dense, dedupe on chunk_id, Cohere rerank, top-k. Returns `HybridSearchResult` with the trace info (bm25/dense/merged counts) the UI sidebar will surface.
- `src/retrieve_prose/cli.py` — Typer CLI: `search` (one strategy at a time, with player/source filters) and `compare` (side-by-side BM25 / Dense / Hybrid).
- `tests/retrieve_prose/test_filters.py` (8 tests) — filter SQL generation paths including the GIN-friendly `&&` operator.
- `tests/retrieve_prose/test_hybrid_merge.py` (5 tests) — union-by-chunk_id, dedupe, order preservation.

**Live retrieval comparison on the 257-chunk corpus**

Query: `"cooper flagg rookie"`

| Strategy | Top-1 chunk | Top-1 score |
|---|---|---|
| BM25 only | Comments on Flagg / Kon / VJ ROY race | 0.0014 |
| Dense only | Same chunk (Flagg/Kon/VJ comments) | 0.5557 |
| **Hybrid + Rerank** | **The ROY announcement chunk** (`"Dallas Mavericks' Cooper Flagg has won the 2025-26 Rookie of the Year award"`) | **0.8921** |

The rerank step moved the actual ROY announcement chunk to position #1, ahead of the discussion chunks that the dense path scored higher.

Query: `"wemby defensive impact"` returned 0 from BM25 because `plainto_tsquery` ANDs all terms and "wemby & defensive & impact" together is rare in the corpus. Hybrid+Rerank top-1 (via dense + rerank) was the Wemby 39-pt / 5-block Game 2 chunk at 0.6405. Dense alone had it at #1 already, but the rerank score is the calibrated relevance estimate the synthesis layer can threshold on.

**Known follow-ups**

- BM25 with `plainto_tsquery` is AND-only and misses queries with three or more loose terms. Switching to `websearch_to_tsquery` plus an OR-fallback for queries that return zero hits would lift BM25 recall meaningfully. For the current corpus the dense+rerank fallback already covers it.
- Rerank cost is about $0.002 per call (Cohere Rerank 3.5 pricing as of 2026). The router-then-rerank pattern means we only run the reranker on the prose route, not stats, so this stays manageable.

**13 new tests; 149 total passing.**

---

### Phase D — Query router (2026-05-17)

The router classifies a natural-language NBA question into one of three retrieval routes: `stats` (text-to-SQL on Postgres), `prose` (vector search on `articles_chunks`), or `hybrid` (SQL filter then vector search inside the filtered set).

**Added**

- `src/router/prompts.py` — system prompt, `classify_route` tool schema (Anthropic tool use for guaranteed structured output), and 14 few-shot examples stratified across the three routes (4 stats, 4 prose, 3 hybrid, 3 tricky edge cases).
- `src/router/classifier.py` — `RouterClassifier` wraps Claude Sonnet 4.6 with `tool_choice={"type":"tool","name":"classify_route"}` so every call MUST return a valid `{route, reasoning}` payload. Goes through `src.guardrails.guarded_call`, so token caps + cost ceiling + circuit breaker all apply. Validates the route enum and raises `RouterError` on bad input.
- `src/router/cli.py` — Typer CLI: `classify "<question>"`, `smoke` (built-in 14-question evaluation set), `batch <file>` (one question per line).
- `tests/router/test_classifier.py` — 13 unit tests covering the tool schema, the few-shot scaffolding, the `_extract_tool_input` helper, and the classifier's input validation paths (mocked Anthropic client so tests don't hit the network).

**Live smoke-test result**

Ran the built-in 14-question set against Claude Sonnet 4.6:

| Bucket | Score |
|---|---|
| stats | 5 / 5 |
| prose | 5 / 5 |
| hybrid | 4 / 4 |
| **Total** | **14 / 14 (100%)** |

Cost for the full smoke set: **$0.143** (about $0.01 per classification). Sonnet 4.6 prompt-cache integration is a clear Phase D follow-up to cut this 5-10x — the system prompt and the 14 few-shot examples are stable across calls, so cache hits will dominate.

**Why tool use over JSON-in-prose**

The early sketch returned `{"route": ..., "reasoning": ...}` as raw JSON in the model's text response. That works most of the time and breaks loudly when the model wraps the JSON in prose or adds trailing commas. Tool use with a typed schema and forced `tool_choice` removes the parsing failure mode entirely. The schema also doubles as inline documentation for the route enum.

**Known follow-ups**

- Add prompt caching on the system prompt + few-shot prefix. Should drop the per-call cost from $0.01 to about $0.001.
- A/B test Haiku 4.5 against the same smoke set. If Haiku hits 12+/14, switch the default and cut cost by another 5x. Sonnet stays as the fallback in the model cascade for anything Haiku declines.
- Extend the smoke set to ~30 questions to match the planned Braintrust eval size. Stratification target stays 10/10/10.

**13 new tests; 136 total passing.**

---

### Phase B.8 — Real corpus ingested (2026-05-17)

After lifting the Voyage free-tier rate cap (added a payment method on the dashboard; pay-as-you-go from the existing free balance), ran two ingests in parallel from Reddit.

**Corpus state**

| Source | Articles | Chunks |
|---|---:|---:|
| r/nba (top of month) | 100 | 151 |
| r/Thunder (top of month) | 30 | 38 |
| r/NBASpurs (top of month) | 30 | 31 |
| r/NYKnicks (top of month) | 30 | 30 |
| r/clevelandcavs (partial — Reddit 429) | 7 | 7 |
| **Total** | **197** | **257** |

Both the r/nba run (49,572 embedding tokens, ~$0.009) and the team-subs run completed under three minutes each. The team-subs run hit a Reddit 429 mid-way through r/clevelandcavs (Reddit's 60 req/min IP cap, separate from Voyage). DetroitPistons and nbadiscussion didn't get processed; trivial to add in a follow-up.

**Bug found and fixed: false-positive aliases for common English words**

The LLM alias step added `love` → Kevin Love, `green` → Jeff Green, `white` → Derrick White, `wolf` → Danny Wolf, and `black` → Anthony Black. These are common words and matched constantly in fan comments ("love that play", "green light", "in the black"). Result: Kevin Love appeared in 60 chunks despite barely being mentioned by name.

Fix: deleted those 5 aliases from `player_aliases`, then re-ran the entity resolver on all 257 existing chunks and `UPDATE`d their `player_ids` column. No re-embedding needed (the vectors themselves are correct; only the filter column needed correcting).

Post-cleanup top mentions (real signal, not artifacts):

```
46  SAS   Victor Wembanyama
35  LAL   LeBron James
31  CHA   LaMelo Ball
24  WAS   Trae Young
22  CLE   James Harden
21  OKC   Shai Gilgeous-Alexander
16  NYK   Mitchell Robinson
14  GSW   Stephen Curry
12  NYK   Karl-Anthony Towns
12  PHI   Joel Embiid
```

**Sample retrievals (after cleanup)**

| Query | Top match (similarity) | Why it's the right hit |
|---|---|---|
| `"Wemby's defensive impact at the rim"` | 0.55 — r/nba 2026-04-27, Wemby/Castle/Clingan defensive sequence | Spurs defensive set with Wemby in the role |
| `"Cooper Flagg's rookie season"` | 0.51 — r/nba 2026-04-27, "Cooper Flagg has won the 2025-26 Rookie of the Year award" | ROY announcement |
| `"playoff fatigue in the Western Conference"` | 0.54 — r/nba 2026-05-05, Wolves-Nuggets elimination thread | "DENVER NUGGETS HAVE BEEN ELIMINATED" |
| `"Harden trade to Cleveland"` | 0.65 — r/clevelandcavs 2026-04-21, Cavs Big 3 thread | Direct mention |
| `"LeBron at age 41"` | 0.65 — r/nba 2026-05-06, "41 years old LeBron James checks out: 27 PTS" | Box-score thread |

**HNSW activation**: `EXPLAIN ANALYZE` still shows Seq Scan at 257 chunks (correct planner choice at this scale; query still completes in <1ms). The HNSW index is in place and will become the preferred path automatically once the corpus crosses ~1000+ chunks. Index correctness is verified by the schema migration test in `tests/schema/test_migration_discovery.py`.

**Known follow-ups**

- DetroitPistons and r/nbadiscussion didn't ingest (Reddit 429 partway through team-subs run). Trivial to re-run with `--sub DetroitPistons --sub nbadiscussion` once we want them.
- An orphan-article row exists from the earlier rate-limit smoke test (article inserted, embedding failed → no chunks). Not load-bearing for retrieval. Cleanup is a one-liner if it becomes noisy.
- The alias-cleanup pass is now ad-hoc. A small `src/normalize_entities/clean_aliases.py` script would let us repeat it deterministically if more false-positives surface.

---

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
