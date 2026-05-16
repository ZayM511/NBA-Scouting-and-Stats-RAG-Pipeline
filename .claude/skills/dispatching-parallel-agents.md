# Dispatching Parallel Agents

When you have three or more independent problems, dispatch focused subagents in parallel instead of solving them serially. Parallel dispatch is one of the largest productivity multipliers in agent-driven development.

This skill explains when to fan out and how, with five RAG-specific use cases.

## The rule

**Three independent tasks = parallel. Two = decide case-by-case. One = direct work.**

"Independent" means the tasks don't share state and don't need each other's output. Three eval failures across different routes are independent. Three steps in one ingestion pipeline are not.

## How to dispatch

Use a single message with multiple `Agent` tool calls. Claude Code executes them concurrently and returns when each finishes.

```
I'll run three diagnostics in parallel:
- agent A on stats route failures
- agent B on prose route failures
- agent C on hybrid route failures
```

Then make three `Agent` calls in one turn. Wait for results. Synthesize.

Each agent gets:

- A short, self-contained prompt (the agent has no conversation context).
- A specific deliverable ("report findings in under 200 words").
- Any file paths or context it needs to do the work.

## RAG-specific use cases

### 1. Re-embedding multiple corpora after an embedding-model change

If you upgrade from `voyage-3` to `voyage-3-large`, every chunk needs re-embedding. Split by table or by date range; dispatch a worker per range.

```
- Agent A: re-embed articles_chunks where date >= '2026-01-01'
- Agent B: re-embed articles_chunks where date < '2026-01-01' AND date >= '2025-10-01'
- Agent C: re-embed authored_summary chunks (top-30)
```

Each worker can report tokens consumed, time elapsed, error count.

### 2. Fixing stratified eval failures

After running the eval set, you get failures distributed across stats / prose / hybrid. Each route has different root causes (wrong SQL, wrong chunks, wrong synthesis prompt). Dispatch one agent per route.

```
- Agent A: triage stats failures, propose fixes for the SQL generator
- Agent B: triage prose failures, propose fixes for the retrieval or rerank
- Agent C: triage hybrid failures, propose fixes for the router or the filter-then-vector composition
```

Each returns a short list of "this is the bug" + "this is the fix" entries.

### 3. Testing parallel chunking experiments

When deciding between recursive-400 / recursive-512 / semantic-with-floor, you don't want to run them sequentially.

```
- Agent A: ingest a 50-article sample with strategy 1, run the eval set, report recall@5
- Agent B: same with strategy 2
- Agent C: same with strategy 3
```

Then compare the three reports.

### 4. Researching multiple library choices

Picking between three reranker providers (Cohere, Voyage, Jina) — dispatch one researcher per option to gather pricing, latency, recall numbers, integration shape. Each returns a one-page summary.

```
- Agent A: investigate Cohere Rerank 3.5 — pricing, latency p50/p95, recall on a public benchmark, integration code shape
- Agent B: same for Voyage rerank-2
- Agent C: same for Jina reranker-v2
```

### 5. Parallel article scraping across sources

Scraping The Ringer, ESPN, and The Athletic involves different selectors, rate limits, and HTML structures. Dispatch one ingest agent per source.

```
- Agent A: scrape The Ringer top-100 articles for the season
- Agent B: same for ESPN
- Agent C: same for The Athletic (handle paywall gracefully)
```

Each agent writes to a per-source staging table; the orchestrator merges them.

## When NOT to fan out

- **Sequential dependencies.** Step 2 needs step 1's output → run them in order.
- **Shared mutable state.** Multiple agents writing to the same table without coordination → races.
- **Two tasks.** The overhead of fanning out and synthesizing isn't worth it for two. Just do them yourself.
- **The user is waiting for one answer.** Fanning out is invisible to the user; sometimes the right move is to spend 30 seconds doing the thing.

## How to phrase the synthesis

After agents return, write a synthesis the user can read. Don't dump three full reports back; condense.

```
Three runs are in:

- Strategy 1 (recursive-400, 15% overlap): recall@5 = 0.78
- Strategy 2 (recursive-512, 20% overlap): recall@5 = 0.74
- Strategy 3 (semantic with 200-token floor): recall@5 = 0.81 but 2.3x slower at ingest

Recommendation: ship strategy 1 as the default, mark strategy 3 as a TODO for the
post-hybrid eval pass once we have the rerank step in.
```

## Anti-patterns

- **Fanning out three agents that all read the same file.** The overhead is wasted; one agent reading the file once is faster.
- **Returning all three reports verbatim.** Synthesize. The user delegated to you.
- **Forgetting to brief each agent.** Each agent starts fresh; it has no idea what the conversation is about. The prompt must be self-contained.
- **Parallelizing destructive operations without checking for conflicts.** Three agents all migrating the same table = corruption.
