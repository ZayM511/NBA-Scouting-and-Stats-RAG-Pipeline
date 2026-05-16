# shadcn (MCP)

The shadcn/ui MCP server, by Jpisnice. Lets Claude Code browse, search, and install shadcn/ui v4 components by natural-language prompt during the UI phase. Beats freelancing component paths or guessing demo code.

## Config (in .mcp.json)

```json
"shadcn": {
  "command": "npx",
  "args": [
    "-y",
    "@jpisnice/shadcn-ui-mcp-server",
    "--framework",
    "react"
  ],
  "env": {
    "GITHUB_PERSONAL_ACCESS_TOKEN": "${env:GITHUB_TOKEN}"
  }
}
```

## Framework flag

`--framework react` is the right choice for this project (Next.js 15 App Router uses React). Other options exist (Vue, Svelte) but they don't apply here.

## Why the GitHub token

The server fetches component source from the shadcn/ui GitHub repo. Without a token, GitHub's rate limit is 60 requests per hour per IP — easy to hit during a UI session. With a token (any scope-less PAT works), the limit jumps to 5000/hour.

The token does **not** need write scope. A read-only PAT with no scopes selected is fine. Reuse the `GITHUB_TOKEN` you already set for the `github` MCP server if you want.

## Tools it exposes

- `list_components` — what's available.
- `search_components` — find by keyword ("card", "table", "sheet").
- `get_component` — fetch a specific component's source and dependencies.
- `list_blocks` — get larger pre-built patterns (dashboards, login forms, settings panels).
- `get_block` — fetch a specific block.

## Example natural-language prompts

- "Install Avatar."
- "Show me radar chart blocks."
- "Find dashboard layouts that include a sidebar and a chat area."
- "I need a sheet that opens from the right and contains a list of cards. What's the canonical shadcn pattern?"
- "Install HoverCard so I can use it for citation chips."

Claude Code translates these into MCP calls, fetches the component, and either drops the source into your project or proposes the install command (`npx shadcn@latest add hover-card`).

## When to use

- **During the UI phase only.** Don't run the server during ingestion or retrieval work. It's overhead for nothing.
- When you need a component and don't already know its exact name.
- When you want to see how shadcn composes components into larger blocks (the blocks library is the underrated part).

## Anti-patterns

- **Copy-pasting from web docs while the MCP server is right there.** The server's `get_component` gives you the canonical version pinned to a specific shadcn release. Web docs may drift.
- **Installing every component "just in case."** Each component is code you now own. Install what you use.

## Interview angle

"During the UI phase I added the shadcn MCP server so Claude Code could browse and install components by prompt. Instead of pasting from web docs, I asked for the component I needed — citation chips, route badges, the tool-use sidebar shell — and the server fetched the canonical source pinned to a specific release. It's the kind of integration that compresses a half-day of UI scaffolding into thirty minutes."
