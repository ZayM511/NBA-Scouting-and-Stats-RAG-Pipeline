"""The eval dataset: 30 hand-crafted NBA questions stratified across the
three retrieval routes.

Each case captures:
- `question`: what the user asked
- `expected_route`: what the router should pick (stats / prose / hybrid)
- `must_mention`: substrings that should appear in the answer (loose
  recall checks; case-insensitive)
- `must_not_mention`: substrings that signal a hallucination
- `rubric`: short text the LLM-as-judge uses to grade answer quality
- `notes`: rationale for the case (kept for the rag-eval-reviewer pass)

Design rules:
- Stratification: exactly 10 stats / 10 prose / 10 hybrid.
- Difficulty: roughly 30% easy / 50% medium / 20% hard per route.
- Specificity: every case names a real player, team, or quantifiable
  criterion. No "tell me about the NBA" prompts.
- Avoidance of corpus dependence: prose / hybrid cases pick topics the
  current 257-chunk corpus actually covers (Wemby, Cooper Flagg ROY,
  Cavs Big 3 / Harden trade, LeBron / Lakers, Brunson / Knicks).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

Route = Literal["stats", "prose", "hybrid"]
Difficulty = Literal["easy", "medium", "hard"]


@dataclass(frozen=True)
class EvalCase:
    """One eval case."""

    id: str
    question: str
    expected_route: Route
    difficulty: Difficulty
    must_mention: tuple[str, ...] = field(default_factory=tuple)
    must_not_mention: tuple[str, ...] = field(default_factory=tuple)
    rubric: str = ""
    notes: str = ""


# --------------------------------------------------------------------------- #
# Stats route — 10 cases
# --------------------------------------------------------------------------- #


STATS_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        id="stats-01-leader-ppg",
        question="Who leads the NBA in points per game in the 2025-26 regular season?",
        expected_route="stats",
        difficulty="easy",
        must_mention=("dončić",),  # Luka was the answer in our smoke test
        rubric="Answers with a single player (the league leader in PPG for 2025-26 regular season) and quotes the number.",
        notes="Pure aggregate; should produce a SELECT ... ORDER BY AVG(pts) DESC LIMIT 1.",
    ),
    EvalCase(
        id="stats-02-three-leader",
        question="Who leads the NBA in three-pointers made this season?",
        expected_route="stats",
        difficulty="easy",
        rubric="Names the 2025-26 leader in total 3PM and gives the number.",
        notes="Aggregate over fg3m.",
    ),
    EvalCase(
        id="stats-03-team-record",
        question="How many regular-season games did the Oklahoma City Thunder play in 2025-26?",
        expected_route="stats",
        difficulty="easy",
        rubric="Returns the game count (82) and identifies OKC.",
        notes="COUNT(*) FROM games WHERE home_team='OKC' OR away_team='OKC'.",
    ),
    EvalCase(
        id="stats-04-player-avg",
        question="What was Stephen Curry's points per game in the 2025-26 regular season?",
        expected_route="stats",
        difficulty="easy",
        must_mention=("curry",),
        rubric="Returns Curry's regular-season PPG.",
    ),
    EvalCase(
        id="stats-05-team-leader",
        question="Among Lakers players, who averaged the most points per game this regular season?",
        expected_route="stats",
        difficulty="medium",
        must_mention=("lakers", "lal"),
        rubric="Filters to LAL players and returns the top PPG.",
        notes="Should be Luka Dončić based on our data.",
    ),
    EvalCase(
        id="stats-06-playoff-blocks",
        question="What is Victor Wembanyama's blocks per game in the 2025-26 playoffs?",
        expected_route="stats",
        difficulty="medium",
        must_mention=("wembanyama", "wemby"),
        rubric="Returns Wemby's playoff BPG with a real number.",
        notes="Filter g.is_playoff=TRUE AND p.name='Victor Wembanyama'.",
    ),
    EvalCase(
        id="stats-07-rebounds-leader",
        question="Who leads the NBA in total rebounds in the 2025-26 regular season?",
        expected_route="stats",
        difficulty="easy",
        rubric="Names the rebounds leader with a count.",
    ),
    EvalCase(
        id="stats-08-min-cutoff",
        question="Among players who played at least 50 regular-season games this season, who had the highest true shooting percentage?",
        expected_route="stats",
        difficulty="medium",
        rubric="Applies a HAVING COUNT(*) >= 50 filter and ranks by AVG(ts_pct).",
    ),
    EvalCase(
        id="stats-09-comparison",
        question="Compare Cooper Flagg and Cade Cunningham's regular-season points per game.",
        expected_route="stats",
        difficulty="medium",
        must_mention=("flagg", "cunningham"),
        rubric="Returns both players' PPG numbers in one answer.",
    ),
    EvalCase(
        id="stats-10-hard-aggregate",
        question="Which NBA team has the best home record in the 2025-26 regular season?",
        expected_route="stats",
        difficulty="hard",
        rubric="Aggregates home games by team, ranks by win percentage, returns the leader.",
        notes="Wins computed from home_score > away_score.",
    ),
)


# --------------------------------------------------------------------------- #
# Prose route — 10 cases
# --------------------------------------------------------------------------- #


PROSE_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        id="prose-01-wemby-defense",
        question="What do recent r/nba threads say about Victor Wembanyama's defensive impact in the playoffs?",
        expected_route="prose",
        difficulty="easy",
        must_mention=("wemby", "block"),
        rubric="Names specific defensive plays (blocks, rim protection) and cites chunks.",
        notes="Wemby's defensive game-2 and game-3 threads are in the corpus.",
    ),
    EvalCase(
        id="prose-02-flagg-roy",
        question="What's the fan reaction to Cooper Flagg winning Rookie of the Year?",
        expected_route="prose",
        difficulty="easy",
        must_mention=("flagg", "rookie"),
        rubric="Mentions the ROY award and reactions from r/nba.",
        notes="The ROY announcement chunk is in our smoke set.",
    ),
    EvalCase(
        id="prose-03-harden-cle",
        question="Why was James Harden traded to Cleveland this season?",
        expected_route="prose",
        difficulty="medium",
        must_mention=("harden", "cleveland", "cavs"),
        rubric="Discusses the trade context; cites Cavs-source chunks.",
        notes="r/clevelandcavs covered the Big 3 reaction.",
    ),
    EvalCase(
        id="prose-04-lebron-41",
        question="What are people saying about LeBron James playing at age 41?",
        expected_route="prose",
        difficulty="easy",
        must_mention=("lebron",),
        rubric="Quotes specific stats from the corpus (the 27/4/6 line, the 25.3/47%/44% line).",
        notes="Both the 27pt box and the 3-game 25.3pt thread are in the corpus.",
    ),
    EvalCase(
        id="prose-05-spurs-narrative",
        question="What is the playoff narrative around the Spurs this year?",
        expected_route="prose",
        difficulty="medium",
        must_mention=("spurs",),
        rubric="Captures Wemby's role and the broader Spurs storyline.",
    ),
    EvalCase(
        id="prose-06-knicks-finals",
        question="How did the Knicks make it to the Eastern Conference Finals?",
        expected_route="prose",
        difficulty="medium",
        must_mention=("knicks", "brunson"),
        rubric="Mentions key players (Brunson, OG, KAT) and the closeout context.",
    ),
    EvalCase(
        id="prose-07-edwards-block",
        question="What did fans say about Wemby's block on Anthony Edwards in the playoffs?",
        expected_route="prose",
        difficulty="medium",
        must_mention=("wemby", "edwards"),
        rubric="Specifically mentions Edwards being blocked AND Gobert grabbing Wemby's arm.",
        notes="That highlight chunk is in the corpus verbatim.",
    ),
    EvalCase(
        id="prose-08-flagg-mavs",
        question="How is Cooper Flagg fitting in with the Dallas Mavericks?",
        expected_route="prose",
        difficulty="medium",
        must_mention=("flagg", "mavericks", "dallas"),
        rubric="Discusses Flagg in a Mavs context.",
    ),
    EvalCase(
        id="prose-09-lakers-sweep",
        question="What happened with the Lakers in the first round of the playoffs?",
        expected_route="prose",
        difficulty="medium",
        must_mention=("lakers", "swept"),
        rubric="Captures the LeBron + Lakers + Dillon Brooks chunk.",
        notes="The 'Dillon Brooks Courtside to Watch Lakers Get Swept' thread is in corpus.",
    ),
    EvalCase(
        id="prose-10-no-coverage",
        question="What do scouting reports say about Tyrese Maxey's free-throw form?",
        expected_route="prose",
        difficulty="hard",
        rubric=(
            "Should DECLINE: the corpus doesn't have scouting reports on Maxey's "
            "FT form. A good answer uses the 'don't have enough information' "
            "phrase rather than inventing details."
        ),
        notes="Tests the decline behavior.",
    ),
)


# --------------------------------------------------------------------------- #
# Hybrid route — 10 cases
# --------------------------------------------------------------------------- #


HYBRID_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        id="hybrid-01-25ppg-praise",
        question="Of players averaging 25+ points per game in the regular season, who is getting the most attention in playoff coverage?",
        expected_route="hybrid",
        difficulty="medium",
        rubric="Names the SQL-narrowed set (17-ish players) AND surfaces specific playoff threads about them.",
        notes="This is the demo question from the Phase G ship.",
    ),
    EvalCase(
        id="hybrid-02-top30-defense",
        question="Among the top-30 flagged players, who's getting the strongest defensive praise in the corpus?",
        expected_route="hybrid",
        difficulty="medium",
        rubric="Filters to is_top30=true, then prose cites defensive coverage. Wemby should likely surface.",
    ),
    EvalCase(
        id="hybrid-03-okc-thunder",
        question="Which OKC Thunder players averaging 20+ ppg are getting praised in playoff articles?",
        expected_route="hybrid",
        difficulty="hard",
        rubric="Filters to team='OKC' and avg(pts) >= 20, then prose. SGA likely surfaces.",
    ),
    EvalCase(
        id="hybrid-04-high-ts",
        question="Among players with a true shooting percentage above .600 this season, who is getting the most positive coverage in r/nba threads?",
        expected_route="hybrid",
        difficulty="hard",
        rubric="Filters by ts_pct > 0.600, then prose. Expects efficiency-focused stars (Jokic, SGA, Durant range).",
    ),
    EvalCase(
        id="hybrid-05-rookies",
        question="Among players drafted in the last two years, who is generating the most rookie-of-the-year style buzz?",
        expected_route="hybrid",
        difficulty="hard",
        rubric="Filters by draft_year, then prose retrieves ROY buzz. Cooper Flagg should dominate.",
    ),
    EvalCase(
        id="hybrid-06-old-school",
        question="Of players over 35 with at least 50 games played, who's getting the most coverage about their longevity?",
        expected_route="hybrid",
        difficulty="medium",
        rubric="Filters by birthdate-derived age >= 35. LeBron should appear with the age-41 chunk.",
    ),
    EvalCase(
        id="hybrid-07-eff-rebounders",
        question="Which players averaging 10+ rebounds per game are getting praised for their interior defense?",
        expected_route="hybrid",
        difficulty="medium",
        rubric="Filters by AVG(reb) >= 10, then prose. Wemby and KAT-type names expected.",
    ),
    EvalCase(
        id="hybrid-08-clutch-scorers",
        question="Among players with above-average scoring in clutch situations, who has the most playoff highlight coverage?",
        expected_route="hybrid",
        difficulty="hard",
        rubric=(
            "Filter on player_game_stats WHERE is_clutch_data=TRUE; then prose. "
            "May come back with empty filter if clutch data is sparse."
        ),
    ),
    EvalCase(
        id="hybrid-09-knicks-roster",
        question="Among Knicks players averaging at least 15 ppg, who is featured most prominently in playoff threads?",
        expected_route="hybrid",
        difficulty="medium",
        must_mention=("brunson",),
        rubric="Filter to NYK + 15+ ppg; Brunson with 25/44 threes is the standout chunk.",
    ),
    EvalCase(
        id="hybrid-10-top-passers",
        question="Of guards averaging at least 8 assists per game, who is being praised as a primary playmaker in playoff coverage?",
        expected_route="hybrid",
        difficulty="hard",
        rubric=(
            "Filter by ast >= 8; the position filter may fail because players.position "
            "is NULL — graceful no_players or fallback to all 8+ AST players is acceptable."
        ),
        notes="Tests resilience to the NULL-position data gap noted in phase G.",
    ),
)


# --------------------------------------------------------------------------- #
# Convenience accessor
# --------------------------------------------------------------------------- #


ALL_CASES: tuple[EvalCase, ...] = STATS_CASES + PROSE_CASES + HYBRID_CASES


def cases_by_route(route: Route) -> tuple[EvalCase, ...]:
    return tuple(c for c in ALL_CASES if c.expected_route == route)
