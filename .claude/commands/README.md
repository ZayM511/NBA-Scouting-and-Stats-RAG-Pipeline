# .claude/commands/

User-invoked slash commands. Type `/<name>` in Claude Code to run one. Each `.md` file in this folder becomes a command of the same name.

## What's here

| Command | What it does |
|---|---|
| `/smart-commit` | Draft → rate → iterate → humanize → commit. Won't commit a message scoring below 9.5 on clarity, easy-to-understand, and correctness. |
| `/write-readme` | Survey the repo and write a recruiter-ready README. Same rate-iterate-humanize loop as smart-commit. |
| `/simplify` | Rewrite a passage in plain English. Same loop. Useful for tightening README sections or explaining a complex function. |
| `/new-command` | Meta-command for creating new slash commands when you notice a workflow you do three or more times. |

## How they work

Each command runs a four-stage loop inside a single Claude Code turn:

1. **Draft.** Generate concrete, specific output. Reference real files, real metrics, real changes.
2. **Self-rate.** Score the draft 1-10 on clarity, easy-to-understand, and correctness. Scores show up in the transcript.
3. **Iterate.** If any axis is below 9.5, revise. Up to five passes.
4. **Humanize.** Strip em-dashes, AI-isms (`leverage`, `utilize`, `robust`, `seamless`, `comprehensive`, `delve`, `tapestry`, `harness`), passive voice, marketing speak. Re-rate. Ship only when all three axes are 9.5+.

You can read every iteration in the transcript. If a self-rating looks off, intervene.

## Why slash commands beat git hooks for this

A pre-commit-msg git hook would have to call the Anthropic API itself, manage retries, and silently fail on a network blip. Slash commands run inside Claude Code with full repo context and a visible thinking process. Easier to debug. Easier to trust.

## Rules

- Never use plain `git commit` on this project. Always `/smart-commit`.
- Run `/write-readme` at the end of each major phase: scaffold, ingestion, retrieval, eval, UI.
