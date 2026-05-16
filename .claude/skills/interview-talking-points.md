# Interview Talking Points

Living document. Seeded with the v3.5 talking points from the RAG Build Guide. Add to it as the project develops — every design decision, every alternative rejected, every metric measured.

By the time the project is ready to show, this skill is a complete interview-prep file.

## How to use this file

When prepping for an interview, scan top-to-bottom. Read the verbatim answers a couple of times so they sound natural rather than memorized. Pick the analogies that fit your speaking style.

When building, **add** to this file:

- A decision you made (what you picked, what you rejected, why)
- A metric you measured (recall@5 before and after a change, latency at p50 and p95)
- A bug that taught you something (what broke, what you changed, what the eval set caught)

## v3.5 seed answers

### When asked about MCP / Plugins / Skills experience

"I've shipped three production apps — JobFiltr, Rentvolt, and ConsentLens — that each combined multiple MCP servers, Plugins, and Skills to deliver their core functionality. That's where most of my hands-on integration experience comes from: deciding which MCP servers to wire in for which capabilities, handling the trade-offs around auth, rate limits, error surfaces, and plugin compatibility, and knowing when to consume an existing MCP server versus build a custom one. For this RAG project, my `.claude/mcp/` folder documents the servers I wired in (Playwright for browser tasks, Jam for bug capture, Filesystem and GitHub for repo and file access, Postgres for direct DB inspection, shadcn for UI installs, Brave Search for fresh article discovery) and why each one belongs."

### When asked about internal-document RAG (the LLNL-style question)

"I built two public RAG projects to prove the pipeline, and templates that show how I would adapt the same shape to an internal-document domain. I deliberately did not build a fake internal-document demo on simulated data, for two reasons. First, using a real organization's internal documents without explicit approval would violate data handling policy, and proves nothing other than poor judgment about data boundaries. Second, a synthetic version would not test the real challenge: ACL enforcement, real document format diversity, real versioning, real freshness pressure. The adaptation surface for internal-document RAG is well-defined: source ingestion, ACL metadata column with GIN-indexed `allowed_groups`, format-specific parsers, versioning and freshness handling. I would want to do that work inside your security boundary with your data and your stakeholders, not simulate it externally."

### When asked about closed-loop / on-prem deployments

"I know when to reach for self-hosted narrow models versus API-based ones. The decision tree is operational: can you send data to external APIs, is p99 latency under 100ms required, are you processing more than 10M items a month, does any specific task have a fine-tuned narrow model that beats general LLMs on your eval set. For a deployment with internal data and an enterprise Claude account, I would use the enterprise APIs where allowed and self-hosted models from HuggingFace where the data classification requires it. The architecture stays the same; the model layer is the configurable piece. Same applies to embedding: voyage-3-large for general, voyage-finance-2 or domain-tuned for specialized, self-hosted bge-large or nomic-embed-text for fully on-prem."

### When asked about reducing LLM token usage and costs

"Three patterns, all baked into my projects: per-query token caps to prevent attacks or accidents that drain budget, per-session cost ceilings to bound any single user, and a model cascade that tries Haiku first, escalates to Sonnet on failure, and only reaches Opus for the genuinely hard synthesis. There is also LLM enrichment as one-time amortized cost: I pay tokens once at ingest to extract metadata like authored summaries, and queries forever get that signal without additional LLM cost. Plus aggregate circuit breakers at the project level so that one bad day cannot run away with the budget."

### When asked about guardrails and safety

"I followed the OWASP LLM Top 10 (2025) as my framework. The biggest RAG-specific risk is LLM08, vector and embedding weaknesses, things like embedding inversion and indirect prompt injection through retrieved content. My pipeline treats every retrieved chunk as untrusted data and strips instruction-like phrases before they hit the synthesis prompt. I also enforce LLM10 with the token caps and cost cascade I just mentioned. Guardrails live in three places by design: CLAUDE.md for always-on rules Claude Code reads every session, SECURITY.md as a public policy GitHub recognizes specially, and a Security section in the README that links to both."

### When asked about your repo structure (the architect question)

"My `.claude/` directory has five kinds of artifacts. Agents are specialists I delegate to. Commands are workflows I invoke. Hooks are guardrails that always run. Skills are the knowledge layer they all read from. MCP servers are the integration layer that connects Claude Code to external systems. The separation maps to how production AI teams structure their tooling: act, invoke, enforce, know, integrate. The whole thing is documented and self-explanatory if someone clones the repo."

### When asked about your evaluation methodology

"I treat evals like tests. I maintain a 30-question dataset in Braintrust, stratified across the routes my system actually serves — stats, prose, and hybrid. After every meaningful pipeline change, I run the full eval set and compare to the previous baseline. The README has screenshots of three experiments that mattered: a failed trace showing how I debugged it, an A/B comparison showing the reranker improved recall@5 from 0.61 to 0.83, and the eval overview with pass/fail per route. Anyone can ship a working pipeline; measuring whether it stays working is what separates a demo from production work."

## Simplified analogies

Pick the ones that feel natural and rotate them in when explaining to non-ML stakeholders.

- **Embeddings.** "Picture every chunk of text as a dot on a map. Texts about similar things end up near each other. Embeddings are how I draw the map. Search becomes: which dots are closest to my question?"
- **Hybrid retrieval.** "BM25 is a librarian who matches the exact words on your card. Vector search is a librarian who knows what the book is about. The reranker is the senior librarian who sees both lists and tells you which books actually answer your question."
- **Reranker.** "Cheap retrieval is a wide net — pulls in 50 candidates. The reranker is the slow, smart pass that re-sorts those 50. Two-stage retrieval is how you get both speed and accuracy."
- **Metadata filtering.** "You don't search every book in the library for an article about Wemby. You walk to the Spurs shelf first, then to 2026, then to the Wemby section. Metadata filtering is that walk."
- **LLM enrichment.** "Pre-cooking. Instead of asking Claude to write a scouting summary every time someone queries, I wrote them once at ingest time. Query-time stays fast because the hard thinking already happened."
- **Query routing (NBA).** "Triage at the ER. Numeric questions go to the stats database. Qualitative questions go to the scouting articles. Hybrid questions need both. The router is the triage nurse — small model, fast, makes the dispatch decision."
- **Why Postgres + pgvector.** "I wanted my SQL and my vectors in the same place, in the same query, in the same transaction. Splitting them across two systems is a tax I didn't want to pay."
- **Braintrust.** "Tests, but for AI. Software engineers write unit tests. AI engineers write eval sets. Braintrust is what makes the eval set run automatically, track regressions, and let me compare experiments side by side."

## The 60-second pitch for this project

"NBA questions split into two worlds. Some are numeric — what's Jokic's true shooting in the clutch? — and live in a database. Others are qualitative — how do scouts grade Wemby's defensive instincts? — and live in articles. Most production AI systems hit this same wall: they have SQL data and documents, and most RAG demos handle only one. I built a router that classifies each question and dispatches to text-to-SQL, vector search, or both — and synthesizes a single answer that cites both the stats and the articles. Built for the 2025-26 season, live-updated for the playoffs going on right now."

## My design decisions log (add as I build)

| Decision | What I picked | What I rejected | Why |
|---|---|---|---|
| Database | Postgres + pgvector | SQLite + sqlite-vec; separate vector DB | One transaction, one connection pool, hybrid query in one SQL statement |
| Embedding model | voyage-3-large | voyage-3 (cheaper but 75% quality); OpenAI text-embedding-3 | Best general-purpose, no NBA-domain model exists |
| Chunking | Recursive 400-token, 15% overlap | Semantic chunking | 2026 default, semantic produces tiny fragments without a floor |
| Router model | Claude Sonnet 4.6 | Haiku 4.5 only | Sonnet has better few-shot reasoning for the 3-way classification; cascade falls back to Sonnet anyway |
| (add more as you build) | | | |

## Metrics I've measured (add as I build)

| Change | Metric | Before | After | Notes |
|---|---|---|---|---|
| Contextual retrieval prefix | recall@5 | TBD | TBD | Expect 35-50% improvement per Anthropic 2024 |
| (add more as you build) | | | | |

## Bugs that taught me something (add as I build)

(Write a short story for each meaningful bug. What broke, what you changed, what the eval set caught. These are the most memorable interview material.)
