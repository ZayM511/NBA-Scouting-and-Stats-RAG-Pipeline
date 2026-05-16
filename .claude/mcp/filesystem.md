# filesystem (MCP)

Anthropic's reference filesystem MCP server. Scoped read/write access to configured directories. Cleaner than letting Claude Code shell out for every file operation.

## Config (in .mcp.json)

```json
"filesystem": {
  "command": "npx",
  "args": [
    "-y",
    "@modelcontextprotocol/server-filesystem",
    "${CLAUDE_PROJECT_DIR}",
    "/tmp"
  ]
}
```

The arguments after the package name are the directories the server is allowed to touch. Two are scoped here:

- `${CLAUDE_PROJECT_DIR}` — this repo. Read/write inside.
- `/tmp` — for throwaway scratch (Playwright scripts, scratch SQL, intermediate JSON).

## Scope of access

The server can:

- Read any file under the two allowed roots.
- Write or modify any file under those roots.
- List directories.
- Move and delete files.

The server cannot:

- Touch anything outside the configured roots (including the user's home directory).
- Read environment variables.
- Run shell commands.

## What NOT to allow

Do not add these roots to the server's args:

- `/` or the user's full home (`~`). Way too broad.
- Directories with secrets (`~/.ssh`, `~/.aws`, `~/.config/gcloud`).
- Other repos you don't want Claude Code to touch.

Stick to project-scoped roots plus `/tmp`. If you need access to another path for a specific task, edit `.mcp.json`, do the task, then revert.

## When to use vs the built-in Read/Write/Edit tools

The built-in `Read`, `Write`, `Edit`, `Glob`, `Grep` tools cover ~95% of file operations and are usually faster. The filesystem MCP server is useful when:

- You need to move or rename files (the built-ins don't have a `mv` operation).
- You're orchestrating a flow that the built-ins can't express cleanly (recursive deletes, atomic renames).
- You want a structured tool surface for a long-running task (file watcher patterns).

For most day-to-day work, just use the built-ins.

## Cost / safety notes

- Every MCP server is a new attack surface. The filesystem server is the highest-impact one in this list because it can delete files. Don't give it broader roots than it needs.
- The `block-secrets.sh` hook does not intercept filesystem MCP writes — it only fires on the `Write` and `Edit` tools. If you write through this MCP server, the hook is silent. Keep that in mind.
