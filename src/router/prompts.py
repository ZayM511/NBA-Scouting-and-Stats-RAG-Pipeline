"""Router prompts: system instructions, tool schema, and few-shot examples.

The router classifies an NBA question into one of three routes:

- stats: a numeric answer the project's SQL schema can serve
  (player_game_stats / games / play_by_play / players). Examples:
  "What's Jokic's TS% this playoffs?", "Who leads the league in steals?",
  "How many games has Wemby missed?".

- prose: a qualitative answer that requires reading articles
  (scouting opinions, fan reactions, narrative). Examples:
  "How do scouts grade Wemby's defense?", "Why is Embiid frustrated?",
  "What's the Spurs narrative this playoff run?".

- hybrid: needs both a SQL filter and qualitative context. Examples:
  "Which guards averaging 20+ ppg are getting praised for off-ball
  movement?" (SQL narrows to guards >= 20 ppg, then prose retrieval
  finds praise about each).

The model returns the decision via the `classify_route` tool. Tool use
guarantees a typed, parseable response without JSON-from-prose fragility.
"""

from __future__ import annotations

from typing import Any


# --------------------------------------------------------------------------- #
# Tool schema (structured output)
# --------------------------------------------------------------------------- #


ROUTE_TOOL: dict[str, Any] = {
    "name": "classify_route",
    "description": (
        "Classify the user's NBA question into the routing category that should "
        "answer it. Choose exactly one route."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "route": {
                "type": "string",
                "enum": ["stats", "prose", "hybrid"],
                "description": (
                    "stats: the answer is a number / count / ranking that comes "
                    "from the SQL schema (player_game_stats, games, players, "
                    "play_by_play). "
                    "prose: the answer is qualitative and comes from articles or "
                    "scouting writeups. "
                    "hybrid: the question needs a SQL filter that narrows the set "
                    "of players, then a prose retrieval inside that set."
                ),
            },
            "reasoning": {
                "type": "string",
                "description": (
                    "One short sentence explaining the choice. Mention which "
                    "schema tables or article angles drove the decision."
                ),
            },
        },
        "required": ["route", "reasoning"],
    },
}


# --------------------------------------------------------------------------- #
# System prompt
# --------------------------------------------------------------------------- #


SYSTEM_PROMPT = """\
You are the query router for an NBA scouting + stats RAG system.

Your only job is to classify the user's question into one of three routes:

- "stats": the answer is numeric, a count, a ranking, or any value that can
  be served by SQL over the project's schema. The schema has these tables:
    * players (player_id, name, team, position, is_top30)
    * games (game_id, date, season, season_type, is_playoff, playoff_round)
    * player_game_stats (player_id, game_id, minutes, pts, ast, reb, fg_pct,
      fg3_pct, ts_pct, usg_pct, plus_minus, is_clutch_data, ...)
    * play_by_play (top-30 players only; shot location, event type)

- "prose": the answer is qualitative, opinion-driven, narrative, or
  scouting-related. It comes from articles and Reddit threads in the
  articles_chunks table (Reddit r/nba and team subs covered so far; more
  professional sources to come).

- "hybrid": the question first needs a SQL filter to narrow the player
  set, then a prose retrieval inside that set. The defining signal is a
  numeric filter PLUS a qualitative criterion.

Decision rules:

1. If the question asks for a number, ranking, or count (PPG, TS%, win
   total, games missed, free throw rate), it's stats.
2. If the question asks for opinions, scouting analysis, narrative,
   reaction, or "what's going on with X", it's prose.
3. If the question combines a numeric filter ("guards averaging 20+",
   "players over 35", "with TS% above .600") AND a qualitative criterion
   ("praised for", "what are scouts saying", "narrative"), it's hybrid.
4. Pure player-name lookups ("Tell me about Wemby") are prose. The
   scouting writeups carry that information.
5. When you're not sure, prefer prose. Prose retrieval is the most
   forgiving fallback; SQL with the wrong intent returns wrong numbers.

Always call the classify_route tool. Never return prose to the user.
"""


# --------------------------------------------------------------------------- #
# Few-shot examples — kept as a separate prompt block so the cost is
# capped and the examples are easy to edit without touching the system
# prompt. The examples appear in the messages array as a user/assistant
# alternation that primes the model on the expected tool-use format.
# --------------------------------------------------------------------------- #


FEW_SHOT_EXAMPLES: list[dict[str, Any]] = [
    # --- STATS ---
    {
        "question": "What is Jokic's true shooting percentage in clutch playoff games?",
        "route": "stats",
        "reasoning": "Numeric value from player_game_stats filtered by is_clutch_data and games.is_playoff.",
    },
    {
        "question": "Who leads the NBA in assists per game this season?",
        "route": "stats",
        "reasoning": "League leader is a ranked aggregate over player_game_stats.",
    },
    {
        "question": "How many games has Cooper Flagg started for the Mavericks?",
        "route": "stats",
        "reasoning": "Game count joining players to player_game_stats.",
    },
    {
        "question": "What were SGA's scoring averages in the regular season vs the playoffs?",
        "route": "stats",
        "reasoning": "Two AVG aggregates split by games.season_type.",
    },
    # --- PROSE ---
    {
        "question": "How do scouts evaluate Wemby's defensive instincts?",
        "route": "prose",
        "reasoning": "Qualitative scouting opinion that lives in articles, not a number.",
    },
    {
        "question": "What's the playoff narrative around the Spurs this year?",
        "route": "prose",
        "reasoning": "Narrative / opinion content from articles and Reddit threads.",
    },
    {
        "question": "Tell me about Cooper Flagg.",
        "route": "prose",
        "reasoning": "Open-ended player overview; the scouting writeup is the right source.",
    },
    {
        "question": "Why did Embiid sit out tonight?",
        "route": "prose",
        "reasoning": "Reasoning is reported in articles, not stored as a structured field.",
    },
    # --- HYBRID ---
    {
        "question": "Which guards shooting above 40% from three are getting praised for off-ball movement?",
        "route": "hybrid",
        "reasoning": "SQL filters players by position='G' and fg3_pct > .40, then prose searches each for off-ball praise.",
    },
    {
        "question": "Among the top-30 scorers this season, who's the most-praised on-ball defender?",
        "route": "hybrid",
        "reasoning": "Numeric filter (top-30 ppg) combined with qualitative defensive evaluation from prose.",
    },
    {
        "question": "Find players over 35 with above-average true shooting who are getting written up as future Hall of Famers.",
        "route": "hybrid",
        "reasoning": "SQL narrows by age and ts_pct; prose checks each player's HoF-writeup mentions.",
    },
    # --- Tricky edge cases ---
    {
        "question": "What did fans say about LeBron's late-game performance?",
        "route": "prose",
        "reasoning": "Fan reaction is purely qualitative; no SQL filter implied.",
    },
    {
        "question": "Who scored more in the 4th quarter, SGA or Luka?",
        "route": "stats",
        "reasoning": "Two players, one comparison, all numeric; player_game_stats with a period filter would serve it if we tracked per-quarter splits.",
    },
    {
        "question": "How is Wemby's defense rated and what are his block totals?",
        "route": "hybrid",
        "reasoning": "Two parts: scouting rating from prose, block totals from player_game_stats.",
    },
]


def few_shot_messages() -> list[dict[str, Any]]:
    """Return the few-shot exchanges as the prefix to the messages array.

    Each example becomes a (user, assistant) pair where the assistant
    replies with a tool_use block calling classify_route. This primes the
    model on the expected output format.
    """
    out: list[dict[str, Any]] = []
    for i, ex in enumerate(FEW_SHOT_EXAMPLES):
        out.append({"role": "user", "content": ex["question"]})
        out.append(
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": f"toolu_example_{i:03d}",
                        "name": ROUTE_TOOL["name"],
                        "input": {"route": ex["route"], "reasoning": ex["reasoning"]},
                    }
                ],
            }
        )
        # Required: every tool_use must be followed by a tool_result.
        out.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": f"toolu_example_{i:03d}",
                        "content": "ok",
                    }
                ],
            }
        )
    return out
