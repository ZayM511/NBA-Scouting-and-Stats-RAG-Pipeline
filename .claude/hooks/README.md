# .claude/hooks/

Deterministic shell scripts that run automatically on Claude Code events. Configured in `settings.json` in this folder. Unlike agents and commands, hooks are not asked; they always run.

The hooks here are bash scripts. On Windows they run via Git Bash (which ships with Git for Windows). Make sure `git` and `bash` are on your `PATH`.

## What's here

| Hook | Event | What it does |
|---|---|---|
| `block-secrets.sh` | `PreToolUse` on `Write`/`Edit` | Reads the tool's input from stdin and greps for API-key patterns. Exits non-zero (which Claude Code treats as a block) if anything matches. |
| `auto-format.sh` | `PostToolUse` on `Write`/`Edit` of `*.py` | Runs `ruff format` on the file Claude Code just touched. Keeps the codebase clean without thinking about it. |

## Event types

- **`PreToolUse`** fires *before* Claude Code calls a tool. A non-zero exit blocks the call. Use this for guardrails.
- **`PostToolUse`** fires *after* the tool returns. Exit code is informational. Use this for cleanup (formatting, indexing, notifications).

## How to extend

Add a new script in this folder, register it in `settings.json` with the right matcher pattern, and `chmod +x` it. The script should:

1. Read stdin if it needs the tool's input payload (JSON).
2. Write any feedback to stderr (Claude Code surfaces stderr in the transcript).
3. Exit 0 to allow, non-zero to block (PreToolUse) or to log a warning (PostToolUse).

## Why hooks instead of agents for safety

Agents can be talked out of their position. Hooks cannot. The block-secrets hook is bash; it greps; it exits. If the regex matches, the write does not happen, period. That's the right level for "never commit an API key."
