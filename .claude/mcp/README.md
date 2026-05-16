# .claude/mcp/

Reference docs for the MCP servers wired into this project. The actual config (commands, env vars, args) lives in `.mcp.json` at the repo root — Claude Code reads it on startup. The markdown in this folder explains *what* each server does, *when* to use it, and *why* it earned a spot.

## Convention

| Lives in | What it is |
|---|---|
| `.mcp.json` | Server commands, env vars, args. Machine-readable. |
| `.claude/mcp/<name>.md` | Human-readable docs for `<name>`. |

If you add a server to `.mcp.json`, add a doc here too. If you can't justify a server in a one-page reference doc, you probably shouldn't be running it.

## Servers shipped with this project

| Server | One line |
|---|---|
| `playwright` | Microsoft's official Playwright MCP. Drives a real browser during a Claude Code task. |
| `jam` | Jam.dev MCP. Pulls bug context (console, network, repro) when the UI breaks. |
| `filesystem` | Anthropic reference filesystem MCP. Scoped read/write to repo root and `/tmp`. |
| `github` | GitHub's official MCP. Issues, PRs, repo metadata. Tracks eval regressions as issues. |
| `postgres` | Community Postgres MCP. Read-only queries against the project DB for sanity checking. |
| `shadcn` | Jpisnice's shadcn/ui MCP. Installs v4 components by natural-language prompt. |
| `brave-search` | Brave Search MCP. Finds recent NBA articles during prose ingestion and playoff dev. |

## Credential policy

Every credential in `.mcp.json` is a `${env:VAR}` reference. Never inline a token. The `block-secrets.sh` hook will reject the commit anyway, but this is the first line of defense.

Required env vars for the full set:

- `GITHUB_TOKEN` — used by `github` and (for rate limits) `shadcn`. Scope: at minimum `repo:public`, `issues:read`, `pull_requests:read`. For private repos you'll need `repo`.
- `POSTGRES_READONLY_URL` — connection string for the read-only DB role. Format: `postgresql://readonly:PASS@localhost:5432/nbarag`.
- `BRAVE_API_KEY` — free tier from brave.com/search/api.

Optional:

- `JAM_API_KEY` — only if you use Jam's authenticated endpoints; the public bug-capture flow does not require it.

## When to add a server

Add an MCP server when:

- You need Claude Code to integrate with an external system more than a few times.
- A one-off shell command would work, but it's flaky or rate-limited and a structured server handles it better.
- The capability is durable enough to be worth documenting.

Don't add a server for:

- A one-time scrape or fetch. Just write the script.
- A capability that an existing skill or command covers.
- A service that requires admin-scoped tokens. The least-privilege rule applies: if you wouldn't give the credential to a junior engineer, don't give it to an MCP server.

## Interview angle

"My `.claude/mcp/` folder documents the servers I wired in and why. Playwright for browser tasks, Jam for bug capture, Filesystem and GitHub for repo and file access, Postgres for direct DB inspection, shadcn for UI installs, Brave Search for fresh article discovery. The `.mcp.json` at the root is the actual config; the markdown here is the reference layer that explains the choices, so an interviewer can see the trade-offs at a glance."
