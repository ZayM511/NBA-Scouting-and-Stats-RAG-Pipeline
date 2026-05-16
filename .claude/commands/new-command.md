---
description: Create a new slash command. Meta-command for when you find yourself doing the same workflow three times.
allowed-tools: Read, Write, Glob
---

# /new-command

Create a new slash command in `.claude/commands/`. Use this when you notice you've done the same workflow three or more times.

## Stage 1 — Interview

Ask the user three questions, one at a time:

1. **What does the command do?** Get the one-line description that goes in the frontmatter.
2. **What's the trigger and the inputs?** Does the user invoke it with arguments? Does it read from staged changes? Does it pick up where the conversation left off?
3. **What's the success criterion?** What does "done" look like? Is there a quality bar like the 9.5 cutoff in `/smart-commit`?

Don't skip ahead. Each answer informs the next question.

## Stage 2 — Survey existing commands

`Glob` `.claude/commands/*.md` and `Read` each. The new command should match the style of the existing ones:

- YAML frontmatter with `description` and `allowed-tools`.
- A stage-by-stage breakdown.
- Concrete success criteria.
- A guardrails section at the end.

## Stage 3 — Draft

Write the command file as `.claude/commands/<kebab-case-name>.md`. Include:

```yaml
---
description: <one-line, ends with a period>
allowed-tools: <minimum set this command needs, comma-separated>
---

# /<name>

<one-paragraph intro: what this command is for, when to use it>

## Stage 1 — <name>
...

## Stage 2 — <name>
...

## Guardrails
...
```

## Stage 4 — Self-rate

Score 1-10 on:

- **Clarity.** Is each stage's purpose obvious?
- **Easy-to-understand.** Can a fresh reader run this command and get the right output?
- **Correctness.** Are the allowed-tools actually the ones the command needs? Are the guardrails strict enough?

Iterate until all three are 9.5+.

## Stage 5 — Humanize

Strip em-dashes, AI-isms, marketing speak. Convert passive to active.

## Stage 6 — Ship

`Write` the file. Then list it next to existing commands so the user sees the full set.

## Naming

- Kebab-case. Short. Imperative when it makes sense (`/simplify`, `/write-readme`).
- Don't shadow existing commands.
- If the command does something destructive or expensive, name it accordingly (`/full-reindex`, not `/refresh`).
