# jam (MCP)

Jam.dev's MCP server. Pulls bug reports captured by the Jam browser extension straight into Claude Code context, with console logs, network requests, and repro steps included.

The workflow: when the UI breaks, you screen-record once with Jam (one click in the extension). Claude Code can then read every piece of debug context without you transcribing anything.

## Config (in .mcp.json)

```json
"jam": {
  "type": "http",
  "url": "https://mcp.jam.dev/mcp"
}
```

Hosted by Jam — no local install. Authentication is handled by the Jam extension; the MCP endpoint reads recordings you've already saved.

## Tools it exposes

- `analyzeVideo` — pull a Jam recording with console + network + user actions.
- `getConsoleLogs`, `getNetworkRequests`, `getScreenshots`, `getUserEvents`, `getMetadata`, `getDetails`, `getVideoTranscript` — granular accessors when you want only one piece.
- `listJams`, `search`, `listFolders` — discover existing recordings.
- `createComment`, `updateJam` — leave a note on a Jam from Claude Code.

## Common workflow for this project

1. Demo the UI. Something breaks (the tool-use sidebar fails to render, the SQL panel shows the wrong query, the route badge is wrong).
2. Click the Jam extension. It records the last N seconds plus the browser state.
3. Paste the Jam URL into Claude Code: "Debug this: <url>".
4. Claude Code calls `analyzeVideo`, reads the console errors, sees the failed network call, traces it back to a file in `src/`, proposes a fix.

This is the fast path for the tool-use sidebar specifically. The sidebar pulls from `/api/trace`; if it returns garbage the symptom is visual but the cause is in the backend. Jam captures both sides in one recording.

## Cost / safety notes

- Jam recordings can include anything visible in the browser. Don't capture recordings while logged into sensitive accounts you don't want shared with Claude Code's context.
- The recordings live in Jam's cloud. Treat them as you would any third-party SaaS — fine for this project (no PII in our app), not fine for an internal-document RAG.
- If you record a session that included a real API key in the console (e.g., printed accidentally), delete the Jam recording and rotate the key. Belt-and-suspenders.

## When not to use this

- If the bug is reproducible from a curl against `/api/...` — skip Jam, just write the test case.
- If the bug is in the ingestion pipeline (no browser involved) — Jam adds nothing.
