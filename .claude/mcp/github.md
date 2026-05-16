# github (MCP)

GitHub's official MCP server. Lets Claude Code read issues, pull requests, and repo metadata directly — especially useful when tracking eval regressions or design decisions as GitHub issues.

## Config (in .mcp.json)

```json
"github": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-github"],
  "env": {
    "GITHUB_PERSONAL_ACCESS_TOKEN": "${env:GITHUB_TOKEN}"
  }
}
```

The token comes from the `GITHUB_TOKEN` env var. Set it in your shell or your `.env` (which is gitignored).

## Token scope

Use a fine-grained personal access token with the **minimum** scopes needed:

- `contents:read` — read repo files.
- `metadata:read` — repo metadata.
- `issues:read`, `issues:write` — create and comment on issues.
- `pull_requests:read`, `pull_requests:write` — create PRs from Claude Code.

Do **not** grant:

- `admin:*` — never.
- `delete_repo` — never.
- `workflow` — only if Claude Code needs to edit CI YAML, otherwise skip.

For this project's public-portfolio repo, restrict the token to **this repo only** (fine-grained tokens let you scope per-repo). One token, one repo, narrow scopes.

## Tools it exposes

- `search_repositories`, `get_repository`, `list_branches` — repo discovery.
- `get_file_contents`, `list_files` — read files (less direct than the built-in Read tool, but useful when working across multiple repos).
- `create_issue`, `update_issue`, `list_issues`, `get_issue`, `add_issue_comment` — issue management.
- `create_pull_request`, `update_pull_request`, `list_pull_requests`, `get_pull_request_files` — PR management.
- `create_branch`, `push_files` — bypass local git when you need to.

## Why this matters for the project

The interview-grade workflow: every eval regression becomes a GitHub issue. Claude Code creates the issue with the failing query, the expected vs actual answer, and the trace URL. You triage the issue list, fix the underlying bug, close the issue with the commit SHA.

That visible issue list — open, in-progress, closed with linked commits — is the recruiter-visible artifact that says "this person treats their portfolio like a product." Most candidates ship a working repo with no issue history.

## When to use vs the `gh` CLI

The built-in `Bash` tool plus the `gh` CLI cover most GitHub work. Reach for the MCP server when:

- You're doing a long-running flow that touches the same repo many times (issue triage, PR review).
- You're working across multiple repos and want one tool surface.
- The `gh` CLI requires interactive auth that's awkward in an agent session.

For one-off commits or PR creation, `gh` from `Bash` is usually faster.

## Cost / safety notes

- The token is a credential. The `block-secrets.sh` hook will catch it if it ever lands in a file; do not test that defense by trying it.
- Treat the MCP server's write capabilities as if they were yours. If you would not click "close issue" on someone's repo, do not let Claude Code do it.
- Audit the issue / PR feed regularly. If an automated agent ever opens a wrong PR, the public visibility is the worst-case.
