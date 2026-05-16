---
description: Rate-iterate-humanize commit workflow. Won't commit below a 9.5 on clarity, easy-to-understand, and correctness.
allowed-tools: Bash, Read, Grep
---

# /smart-commit

Run the full draft → rate → iterate → humanize → rate → commit loop. The user has already staged the files they want to commit; do not stage more unless they ask you to.

## Stage 1 — Survey

1. Run `git status` to see what's staged.
2. Run `git diff --staged` to see the actual changes.
3. Run `git log -n 10 --oneline` to match the project's commit style.

If nothing is staged, stop and tell the user.

## Stage 2 — Draft

Write a commit message that is concrete and specific. Lead with the **why** (the change's purpose), then briefly cover the **what**. Reference real files and real metrics. Never use vague language like "updated stuff" or "various improvements."

Use the format:

```
<short subject line, imperative mood, under 70 chars>

<one or two paragraphs of body explaining the why and what>
<reference specific files, metrics, or commits where helpful>
```

If the change includes a measurable improvement (e.g., recall@5 went up), cite the number.

## Stage 3 — Self-rate

Score the draft on three axes, 1-10. Show the scores in the transcript:

- **Clarity.** Will future-you understand this in six months?
- **Easy-to-understand.** Will a recruiter scanning the repo get it?
- **Correctness.** Does it actually match the diff?

## Stage 4 — Iterate

If any axis is below 9.5, revise and re-rate. Up to five passes. If after five passes any axis is still below 9.5, stop and ask the user what's blocking the score.

## Stage 5 — Humanize

Strip:

- Em-dashes (`—`). Use commas, periods, or parentheses instead.
- AI-isms: `leverage`, `utilize`, `robust`, `seamless`, `comprehensive`, `delve`, `tapestry`, `harness`, `unlock`, `elevate`.
- Marketing speak: `revolutionary`, `cutting-edge`, `state-of-the-art`.
- Passive voice — convert to active.
- Hedging filler: `simply`, `just`, `basically`.

Re-rate one final time. All three axes must hit 9.5+.

## Stage 6 — Commit

Use a heredoc to preserve formatting:

```bash
git commit -m "$(cat <<'EOF'
<final message here>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

If the commit fails (e.g., a pre-commit hook), do not amend. Fix the underlying issue, re-stage, and create a fresh commit.

After the commit, run `git status` to confirm.

## Guardrails

- Never use `--no-verify`. If a hook fails, fix the cause.
- Never use `--amend` on a published commit.
- Never `git add -A` or `git add .` — only stage files the user explicitly mentioned, or files already shown in `git status` that match the change being described.
- Never commit `.env`, anything matching `*key*`, `*secret*`, or `*token*`, or any file the block-secrets hook would flag.
