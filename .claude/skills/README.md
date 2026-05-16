# .claude/skills/

Reference knowledge bases. Unlike agents (which act) and commands (which the user invokes), skills are documents Claude Code reads when the topic comes up.

`CLAUDE.md` at the repo root mentions this folder so Claude Code reaches for these when relevant. Agents and commands can also reference specific skills inline ("see chunking-strategies.md").

## What's here

| Skill | Purpose |
|---|---|
| `chunking-strategies.md` | The 2026 decision tree. Consulted before writing any chunking code. |
| `voyage-embeddings-reference.md` | Voyage model choice (voyage-3-large), free-tier limits, batching, retries. |
| `postgres-pgvector-patterns.md` | HNSW vs IVFFlat, the `<=>` vs `<->` operators, hybrid query patterns, the GIN-on-`player_ids` filter-before-vector trick. |
| `nba-entity-normalization.md` | The player alias map approach. "Steph" / "Curry" / "the Chef" → `player_id = 201939`. |
| `interview-talking-points.md` | Living doc. Seeded with build-guide v3.5 talking points. Add to it as you build. |
| `brainstorming.md` | How to run design conversations: one question at a time, 2-3 alternatives before settling, 200-300 word chunks. |
| `dispatching-parallel-agents.md` | When to fan out: 3+ independent problems, RAG use cases for parallel exploration. |
| `frontend-design.md` | The shadcn/ui + Tailwind + Framer Motion + Visx stack, the anti-patterns to avoid, project-specific component patterns. |
| `playwright-browser-automation.md` | UI testing in a real browser: screenshot capture, chat-flow validation, responsive testing. |

## Why a skills folder when Claude Code doesn't formally have "skills"

Claude Code's official primitives are `CLAUDE.md`, agents, commands, and hooks. The skills folder is a convention this project adopts as a clean home for reference documents that agents and commands can read. `CLAUDE.md` references the folder so Claude Code knows it exists. This keeps the always-on `CLAUDE.md` short while the deep reference content lives one click away.

## When to add a new skill

Add a skill when:

- You find yourself explaining the same concept (chunking, embedding choice, etc.) for the third time.
- A decision tree has more than three branches and you want it written down rather than re-derived.
- An agent's system prompt has a section that would be reusable across other agents.

Don't add a skill for:

- A single fact ("the playoff round starts May 18"). Put that in `CLAUDE.md` or a code constant.
- A workflow you invoke with a typed command. That's a `/command`.
- A check that must always run. That's a hook.
