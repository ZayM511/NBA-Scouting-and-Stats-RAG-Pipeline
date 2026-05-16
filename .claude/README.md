# .claude/ — AI Tooling Layer

This directory is the AI tooling layer for the project. The code under `src/` is the project itself; everything here is the workflow built around it.

Claude Code reads `CLAUDE.md` at the repo root on every session start, and reaches into the folders below when the topic matches.

## Layout

```
.claude/
├── README.md                  # this file
├── agents/                    # specialists Claude Code delegates to
│   ├── README.md
│   ├── tdd-engineer.md
│   ├── rag-eval-reviewer.md
│   ├── security-reviewer.md
│   └── sql-reviewer.md
├── commands/                  # slash commands you invoke
│   ├── README.md
│   ├── smart-commit.md
│   ├── write-readme.md
│   ├── simplify.md
│   └── new-command.md
├── hooks/                     # deterministic scripts that always run
│   ├── README.md
│   ├── settings.json
│   ├── block-secrets.sh
│   └── auto-format.sh
├── mcp/                       # reference docs for MCP servers
│   ├── README.md
│   ├── playwright.md
│   ├── jam.md
│   ├── filesystem.md
│   ├── github.md
│   ├── postgres.md
│   ├── shadcn.md
│   └── brave-search.md
└── skills/                    # reference knowledge bases
    ├── README.md
    ├── chunking-strategies.md
    ├── voyage-embeddings-reference.md
    ├── postgres-pgvector-patterns.md
    ├── nba-entity-normalization.md
    ├── interview-talking-points.md
    ├── brainstorming.md
    ├── dispatching-parallel-agents.md
    ├── frontend-design.md
    └── playwright-browser-automation.md
```

## What lives where

| Folder | Purpose | Trigger |
|---|---|---|
| `agents/` | Narrow specialists with their own context window | Delegated by name or auto-routed |
| `commands/` | User-invoked workflows (e.g., `/smart-commit`) | Typed by the user |
| `hooks/` | Deterministic shell scripts that gate tool calls | Fired automatically on tool events |
| `mcp/` | Reference docs for each MCP server in `.mcp.json` | Read when context needs the server |
| `skills/` | Reference knowledge that agents and commands consult | Read when topic matches |

The actual MCP server config lives at the repo root in `.mcp.json` — Claude Code reads it on startup. The markdown under `.claude/mcp/` is documentation: what each server does, when to use it, what credentials it expects.

## The five artifact types in one line

- **Agents act.** Workflows I delegate to.
- **Commands invoke.** Workflows I trigger.
- **Hooks enforce.** Guardrails that always run.
- **Skills know.** Reference knowledge agents and commands read.
- **MCP servers integrate.** Bridges to external systems.
