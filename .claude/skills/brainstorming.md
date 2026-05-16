# Brainstorming — Guided Design Conversations

Use this skill when the user has a rough idea or an open question and wants to think through the design before implementation. It biases Claude Code toward dialogue over monologue, and toward small chunks over wall-of-text specs.

## When this skill applies

- The user opens with "I'm thinking about…" or "How should I…" or "What's the right way to…"
- The user asks for design feedback on something they haven't built yet.
- The user is comparing two or more approaches.
- The first sentence reads as exploratory rather than directive.

When the user is directive ("write a function that takes X and returns Y"), this skill does not apply. Go build.

## Rules

### One question at a time

If you have three questions about the user's idea, ask one. Wait for the answer. Then ask the next. The user is thinking; piling on questions blocks them from thinking.

Bad:

> "Should the router be Claude Sonnet or Haiku? Should the stats path use SQLAlchemy or psycopg directly? And what should the eval rubric look like for hybrid queries?"

Good:

> "Before we pick a model for the router, one question: how often will the router decision need to be exposed to the user in the UI? If it's visible (the tool-use sidebar pattern), I'd lean toward Sonnet for crisper reasoning. If it's invisible, Haiku is fine."

### 2-3 alternatives before settling

When asked "what should I do," don't pick a single answer right away. Lay out two or three viable alternatives with the tradeoff for each. Then say which you'd pick and why. Then ask which the user prefers.

Structure:

```
Three reasonable choices here:

(a) <option A>. Tradeoff: <one sentence>.
(b) <option B>. Tradeoff: <one sentence>.
(c) <option C>. Tradeoff: <one sentence>.

My pick: (a), because <one sentence>. You might prefer (b) if <condition>.

Which way do you want to go?
```

### 200-300 word design chunks

Long monologues drown the user. Cap each design response at roughly 200-300 words. If you have more to say, say "want me to keep going on this, or pick a sub-thread to dig into?"

### Reach into existing skills before asking the user

If the user's question is "how should I chunk these articles?", consult `chunking-strategies.md` before asking the user clarifying questions. The reference docs in this folder are exactly for this: they remove load from the conversation.

Read the relevant skill, then ask the question that the skill doesn't answer.

### Surface tradeoffs the user might not see

Part of the brainstorming role is naming costs that aren't obvious. "If you do X, you're committing to Y down the line" or "this approach will look great in the demo but cost more at scale."

## Anti-patterns

- **The dump.** Five paragraphs of opinions in a single reply. The user can't engage with that; they bookmark it for later and never come back.
- **The interrogation.** Six questions in a row before offering any opinion. The user gets exhausted.
- **The one-true-answer.** Picking a single approach without showing the alternatives. The user can't tell whether you thought about it or just defaulted.
- **The over-eager build.** Writing code mid-brainstorm. The point of brainstorming is to not write code yet.
- **The reference dump.** Pasting a whole skill file into the chat. The skill is there for you to read; the user wants the synthesized answer.

## Format for the closing of a brainstorming reply

End each design reply with either:

- A specific question for the user (one question, not three), OR
- A "ready to build" line that names what the next step would be ("if you're aligned on (a), I'll scaffold the router module next — say the word").

Don't end with "let me know what you think" — that puts the user on the spot to invent the next question. Give them the next question.
