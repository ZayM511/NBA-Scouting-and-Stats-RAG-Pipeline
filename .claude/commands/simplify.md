---
description: Rewrite a passage in plain English. Same rate-iterate-humanize loop as smart-commit.
allowed-tools: Read, Edit
---

# /simplify

Rewrite a passage so it lands cleanly on a first read. Same draft → rate → iterate → humanize → rate → ship loop as `/smart-commit`, applied to prose instead of commit messages.

## Input

The user will paste a passage (a README paragraph, a function docstring, a complex error message) or point at one with a file:line reference.

If neither is provided, ask: "Which passage do you want simplified? Paste it, or give me a file path and line range."

## Stage 1 — Survey

If pointed at a file, `Read` enough surrounding context to understand the audience and the topic. Note:

- Who is the reader? (recruiter, future-self, someone debugging at 2am)
- What's the minimum technical vocabulary the reader has?
- What's the one thing they need to take away?

## Stage 2 — Draft

Write the rewrite. Rules:

- Cut every word that doesn't carry meaning.
- Use concrete nouns and active verbs.
- Lead with the point, then the supporting detail. Never the other way around.
- Replace jargon with the plainest accurate word.
- One idea per sentence. One topic per paragraph.

## Stage 3 — Self-rate

Score the draft 1-10 on:

- **Clarity.** Could a reader outside the team get the point?
- **Easy-to-understand.** Is the reading grade level appropriate for the audience?
- **Correctness.** Does it still say what the original said, only better?

## Stage 4 — Iterate

If any axis is below 9.5, revise. Up to five passes.

## Stage 5 — Humanize

Strip em-dashes, AI-isms (`leverage`, `utilize`, `robust`, `seamless`, `comprehensive`, `delve`, `tapestry`, `harness`), marketing speak, hedging filler. Convert passive to active.

Re-rate. All three axes must hit 9.5+.

## Stage 6 — Ship

If the user pointed at a file, propose the `Edit` with old/new strings clearly marked, then apply once they approve.

If the user pasted the passage, return the final rewrite in your response.
