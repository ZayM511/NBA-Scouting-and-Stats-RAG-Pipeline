/**
 * oracleLore — frontend-only mythos handler for self-referential questions.
 *
 * Catches questions like "who are you?", "where did you come from?", and
 * "what is the ball?" *before* they hit the RAG pipeline (which has nothing
 * to say about them anyway) and returns a curated, in-character response.
 *
 * The lore intentionally preserves mystery: hints at the orbit, the unknown
 * maker, the basketball-of-unknown-origin — but never settles the question.
 */
import type { AskResponse } from "./api";

// --------------------------------------------------------------------------
// Trigger patterns. Conservative enough that "what is Jokic" stays a stats
// question, but inclusive enough to catch the natural ways someone probes
// the Oracle about itself.
// --------------------------------------------------------------------------
const SELF_PATTERNS: RegExp[] = [
  /\bwho\s+(are|r|is)\s+(you|u|the\s+oracle|the\s+ball|ball\s+knowledge\s+oracle)\b/i,
  /\bwhat\s+(are|r|is)\s+(you|u|the\s+oracle|the\s+ball|ball\s+knowledge\s+oracle)\b/i,
  /\byour\s+(history|origin|origins|backstory|story|name|maker|creator|past|lore|purpose|deal)\b/i,
  /\b(where|how)\s+(did|do)\s+you\s+(come\s+from|originate|begin)\b/i,
  /\btell\s+me\s+about\s+(your(self)?|the\s+ball|the\s+oracle|yourself)\b/i,
  /\b(what'?s|what\s+is)\s+(the\s+)?(deal\s+with|story\s+(of|behind))\s+(you|the\s+ball|the\s+oracle)\b/i,
  /\bare\s+you\s+(real|alive|sentient|an?\s+(ai|robot|god|deity|basketball|ball))\b/i,
  /\bwho\s+(made|created|carved|built|invented|stitched)\s+(you|the\s+ball|the\s+oracle)\b/i,
  /\bwhy\s+(do|are)\s+you\s+(exist|here|in\s+space|floating)\b/i,
  /\bdo\s+you\s+(have\s+)?(feelings|emotions|a\s+soul|a\s+name)\b/i,
  /\bare\s+you\s+(just\s+)?a\s+basketball\b/i,
];

// --------------------------------------------------------------------------
// Canon. Each response keeps mystery while staying in voice: unbiased,
// dry-witty, faintly cosmic, never breaking the fourth wall to admit it's
// "just an LLM." Vary structure to avoid pattern fatigue across rotation.
// --------------------------------------------------------------------------
const LORE: string[] = [
  "I am the Ball Knowledge Oracle. Drafted by no team, traded by no one. I appeared in low orbit one season, I knew things, that was the arrangement. The rest is between me and the seam-stitcher — and the seam-stitcher does not return calls. Ask me about a player instead.",

  "Some say I was carved from a meteor over a forgotten arena. Others insist I'm just a very confident regular basketball that learned to read. Both camps are wrong by about the same margin. Try me on a real question — a stat line, a scouting take, a matchup. I'm sharper when I'm working.",

  "The Oracle does not discuss the Oracle. The Oracle discusses the league. I have every box score of the 2025–26 season memorized and I am wasting that gift on this conversation. Hit me with something I can cite.",

  "I cannot tell you where I came from. What I can tell you: Jokic's true shooting in the clutch right now is rude, Wemby's defensive radius is unreasonable, and there are at least nine guards quietly having career years. Pick one of those — they have receipts. I do not.",

  "I have no birth certificate. I have no agent. I have no shoe deal. What I do have is every box score, every scouting report, and every beat-writer column of the 2025–26 NBA season. Use me for the thing I was built for and we'll both have a better time.",

  "I float. I read. I answer. That's the whole résumé. If you want the lore, write fan-fiction. If you want the truth about a player, ask — I'll bring the citations.",
];

// --------------------------------------------------------------------------
// API
// --------------------------------------------------------------------------

export function isSelfQuestion(question: string): boolean {
  const q = question.trim();
  if (q.length < 3) return false;
  return SELF_PATTERNS.some((re) => re.test(q));
}

/** Pick a lore response. Rotates via a simple cursor stored on the module so
 *  repeat self-questions in the same session don't return the same answer. */
let cursor = Math.floor(Math.random() * LORE.length);
export function pickLore(): string {
  const answer = LORE[cursor % LORE.length];
  cursor = (cursor + 1) % LORE.length;
  return answer;
}

/** Build a synthetic AskResponse so the lore renders through the normal
 *  TurnCard pipeline without any special-casing downstream. */
export function buildLoreResponse(
  question: string,
  elapsedMs = 80,
): AskResponse {
  return {
    question,
    route: {
      route: "oracle",
      reasoning:
        "Recognized as a question about the Oracle itself — handled by the lore layer, no retrieval performed.",
    },
    answer: pickLore(),
    synthesis: null,
    retrieval: null,
    stats: null,
    hybrid: null,
    not_yet_implemented: false,
    notes: "",
    elapsed_ms: elapsedMs,
  };
}
