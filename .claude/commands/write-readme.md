---
description: Survey the repo and write a recruiter-ready README. Rate-iterate-humanize loop, won't write below 9.5.
allowed-tools: Bash, Read, Grep, Glob, Write
---

# /write-readme

Generate the project README from the current state of the repo. Run the same draft → rate → iterate → humanize → rate → write loop as `/smart-commit`.

## Stage 1 — Survey

Read enough of the repo to write a truthful README. At minimum:

1. `git status` and `git log -n 20 --oneline` for recent direction.
2. `Glob` for `pyproject.toml`, `package.json`, `docker-compose.yml`, `CLAUDE.md`, `SECURITY.md`.
3. `Read` each one fully.
4. `Glob` for `src/**/*.py` and `Read` the top-level modules to understand the architecture.
5. `Read` any existing `README.md` to preserve sections the user has hand-written (e.g., the Loom link, screenshots, demo URL).

## Stage 2 — Draft

Structure the README in this exact order:

1. **Title and one-line description.**
2. **Demo links.** Loom video, live demo URL if deployed. Leave a placeholder if either is missing.
3. **Architecture diagram.** Reference `docs/architecture.png` if it exists, else placeholder.
4. **Sample queries.** Three or four real ones with the route they take (STATS / PROSE / HYBRID) and a screenshot of the answer if one is available.
5. **Stack.** List every tool with a one-line reason for picking it.
6. **Design decisions.** Bullet form. Chunking, embedding choice, retrieval strategy, router design.
7. **Evaluation.** Braintrust screenshots, recall@5 and MRR numbers, what improved with what change.
8. **Security.** Four to six bullets summarizing the guardrails. Link to `SECURITY.md` for details.
9. **What I tried and rejected.** Three or four short paragraphs. This section signals seniority — don't skip it.
10. **Running it locally.** `docker compose up`, env vars, `uv sync`, the commands to seed data.
11. **Project layout.** Tree of `src/` and `.claude/` at depth 2.

Tone rules:

- Recruiters scan top-down. Lead with demo links and screenshots.
- Use real numbers where they exist. If a metric isn't measured yet, mark it `(eval pending)` instead of inventing one.
- Specific beats vague. "Switched from voyage-3 to voyage-3-large; recall@5 rose from 0.61 to 0.83" beats "improved retrieval."

## Stage 3 — Self-rate

Score the draft 1-10 on:

- **Clarity.** Will a recruiter scanning get the point in 30 seconds?
- **Easy-to-understand.** Are the tradeoffs explained, or just listed?
- **Correctness.** Does every claim match the actual code, schema, and eval results?

## Stage 4 — Iterate

If any axis is below 9.5, revise. Up to five passes.

## Stage 5 — Humanize

Strip em-dashes, AI-isms (`leverage`, `utilize`, `robust`, `seamless`, `comprehensive`, `delve`, `tapestry`, `harness`), and marketing speak. Convert passive to active voice. Cut hedging filler (`simply`, `just`, `basically`).

Re-rate. All three axes must hit 9.5+.

## Stage 6 — Write

Write the file to `README.md` at the repo root. If a prior `README.md` exists, preserve any user-added sections you noticed in Stage 1 (Loom link, demo URL, custom screenshots).

After writing, `Read` the file back and show the user the final word count and section list.
