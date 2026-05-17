# Top 30 Players, 2025-26

The `is_top30 = TRUE` flag on `players` controls which player rows get the deep-dive enrichment pass: play-by-play ingestion for shot heatmaps, advanced splits, and an Opus-authored scouting summary chunk.

Selection follows a two-step process:

1. **Auto-pick by composite per-game score** (formula in `src/normalize_entities/select_top30.py`).
2. **Human edit** to fix the formula's known blind spots (it over-rates pure rebounders, under-rates rookies with elite tape, and treats the bubble #28–#34 as noise).

This document records the final ranking the project ships with, plus the rationale where it differs from a pure-stats ranking.

## The composite formula (auto-pick)

```
score = pts + 0.8*reb + 1.2*ast + 2*stl + 2*blk
        - 0.8*tov - 0.5*missed_fg - 0.4*missed_ft
```

Per-game, averaged across regular season + playoffs, with `games >= 25`. Run `uv run python -m src.normalize_entities.select_top30 list-top --limit 50` to see the current ranking against live data.

## Final ranking (with human edits)

| Rank | player_id | Name | Team | Notes |
|---:|---:|---|---|---|
| 1 | 1628983 | Shai Gilgeous-Alexander | OKC | See "Why SGA at #1" below. |
| 2 | 203999 | Nikola Jokić | DEN | MVP-tier all-around. Auto-pick had him #1; SGA gets the nod for scoring at his volume + the #1-seed result. |
| 3 | 1641705 | Victor Wembanyama | SAS | DPOY-tier defense, .624 TS on 24 ppg as a 7-foot-4 forward at age 22. The future. |
| 4 | 1629029 | Luka Dončić | LAL | 33.5 ppg leads the league, but .611 TS and +2.9 on/off don't quite match the top three. |
| 5 | 203507 | Giannis Antetokounmpo | MIL | 27.6/9.8/5.4 on .677 TS. Injury-limited to 36 games; healthy he's a top-3 conversation. |
| 6 | 1630595 | Cade Cunningham | DET | Led DET back to relevance with 24.8/5.5/9.5 over 77 games. |
| 7 | 1630162 | Anthony Edwards | MIN | 27.8 ppg on .603 TS, +1.2 on/off. The face of the post-Curry West. |
| 8 | 1628369 | Jayson Tatum | BOS | 22.2/10.2/5.7 on .563 TS over 22 games since his Achilles return on 2026-03-06. Below the 25-game auto-pick threshold; included by human edit on the strength of his pre-injury body of work and his return-from-Achilles narrative. |
| 9 | 1627759 | Jaylen Brown | BOS | 28.4 ppg on .576 TS. BOS's closer while Tatum rehabbed; now their #2 again. |
| 10 | 1630178 | Tyrese Maxey | PHI | 27.7 ppg; carried PHI through Embiid's absence. |
| 11 | 202695 | Kawhi Leonard | LAC | 27.9 ppg on .630 TS over 65 games. Star when on the floor. |
| 12 | 203954 | Joel Embiid | PHI | 45 games of injury-limited dominance. |
| 13 | 1628378 | Donovan Mitchell | CLE | 27.5 ppg on .597 TS; CLE's offensive engine. |
| 14 | 201142 | Kevin Durant | HOU | 25.9 ppg on .648 TS at age 37. |
| 15 | 1630578 | Alperen Sengun | HOU | 20.4/9.0/6.1 — the modern playmaking big. |
| 16 | 1628973 | Jalen Brunson | NYK | 26.2/3.3/6.7 carried NYK to the East Finals matchup. |
| 17 | 1631114 | Jalen Williams | OKC | 17.3/4.6/5.5 on .575 TS in 35 injury-limited games. OKC's #2; the connector for the #1-seed offense and a plus defender on the wing. |
| 18 | 201939 | Stephen Curry | GSW | 26.6 ppg on .624 TS over 43 games (injury-limited). Generational shooting still alive. |
| 19 | 2544 | LeBron James | LAL | 21.3/6.2/7.2 at age 41. Statistical efficiency unprecedented for his age. |
| 20 | 201935 | James Harden | CLE | Traded LAC → CLE mid-season; 23.2 ppg on .618 TS combined. |
| 21 | 1626157 | Karl-Anthony Towns | NYK | 19.7/11.6/3.4 on .633 TS — best shooting big in the league. |
| 22 | 1628374 | Lauri Markkanen | UTA | 26.7 ppg on .612 TS in 42 games. |
| 23 | 1631094 | Paolo Banchero | ORL | 22.6/8.4/5.3 leading ORL's defensive identity. |
| 24 | 1631096 | Chet Holmgren | OKC | 17.3/8.9/1.6 with 1.9 BPG and .653 TS. All-Star starter and the rim-protecting backbone of the #1-seed OKC defense. |
| 25 | 1626164 | Devin Booker | PHX | 25.8/3.9/6.0 on .584 TS. |
| 26 | 1642843 | Cooper Flagg | DAL | **Rookie of the Year favorite.** 21.0/6.7/4.5 as a 19-year-old. Top-30 already. |
| 27 | 1628389 | Bam Adebayo | MIA | 20.1/10.0/3.2 with elite defense. Consensus top-30. |
| 28 | 1630567 | Scottie Barnes | TOR | 18.6/7.4/6.1 with elite defensive versatility. |
| 29 | 1641708 | Amen Thompson | HOU | 18.3/7.7/5.3 with 1.5 steals. The best perimeter defender under 22 in the league; still developing as a scorer. |
| 30 | 1630596 | Evan Mobley | CLE | 17.9/8.8/3.7 with 1.8 BPG. DPOY-conversation defense. |

## Human edits to the auto-pick

The formula's blind spots showed up in three places. Edits made:

**Dropped from auto-pick:**
- Deni Avdija (POR, auto-rank 17) — the formula overweights rebounds+assists for a forward who is not a top-30 player by any consensus ranking
- Josh Giddey (CHI, auto-rank 24) — triple-double-shaped boxes inflated his score; not yet a top-30 player
- Kevin Porter Jr. (MIL, auto-rank 29) — elite steal rate caught by the formula, but limited games and not a top-30 player
- Pascal Siakam (IND, auto-rank 30) — bubble pick with -3.7 on/off
- Jalen Johnson (ATL, auto-rank 8) — formula loved his rebounds+assists volume, but he is not yet a true top-tier name; the per-game composite over-rewarded triple-double-shaped boxes
- Jamal Murray (DEN, auto-rank 13) — strong secondary scorer on a Jokic-led team, but consensus rankings don't put him this high; cut to make room for Jalen Williams

**Added (replacements):**
- Cooper Flagg (DAL, auto-rank 34) — ROY favorite. Demoable.
- Bam Adebayo (MIA, auto-rank 31) — consensus top-30 lock; the formula just missed.
- Chet Holmgren (OKC, auto-rank 41) — All-Star starter; the formula doesn't reward shot-blocking enough.
- Evan Mobley (CLE, auto-rank 35) — DPOY conversation; under-rewarded by box-score-only scoring.
- Jayson Tatum (BOS, did not appear in auto-pick due to 22-game count after his 2026-03-06 Achilles return) — included on the strength of his pre-injury body of work and the return-from-Achilles arc. Auto-pick filter was `games >= 25`; the human edit overrides for a clear top-10 player.
- Jalen Williams (OKC, did not appear in auto-pick due to a 35-game injury-limited season) — OKC's #2 connector. The composite formula missed him because of game count; the human edit corrects.

## Why SGA at #1 (and Jokic at #2)

The composite formula put Jokic at #1 on the strength of his rebounding and playmaking. The human ranking flips them. Four arguments:

1. **Scoring at SGA's volume and efficiency is rare.** 30.9 ppg on .677 TS. Only Jokic (.676) matches the efficiency, and he's at 27.5 ppg. Curry, Durant, and Embiid have hit similar efficiency, but at lower volumes.

2. **Team result.** OKC clinched the #1 seed in the West. Top-player conversations weight team outcomes, and OKC's regular season was the cleanest top-line result of the year.

3. **On/off impact.** SGA +11.3 per game vs Jokic +7.6. The bigger team-level swing belongs to SGA.

4. **Defensive lineup gravity.** SGA's POA defense isn't elite, but he plays passable team defense alongside OKC's defensive structure (Holmgren, Caruso, Dort). Jokic's defense is a known limitation that DEN navigates around. Both players' teams have figured out how to hide their defensive weaknesses, but SGA's defensive overhead is smaller.

### Counter-arguments to the common SGA criticisms

These objections show up online and in casual fan discourse. They are weaker than they sound.

**"He's a foul baiter."** The criticism conflates *how* a player draws contact with *whether* the contact happened. The NBA's officials called the fouls because contact occurred. Skilled initiation of contact has been rewarded across eras — Jordan in 1987 averaged 11.9 free throw attempts per game; Harden hit .442 FT/FGA in 2018-19. SGA's FT rate is .378 FT/FGA. Drawing fouls is a skill, not a flaw, and SGA's career-long pattern shows it's a deliberate, repeatable choice, not officiating accident.

**"He's not fun to watch."** Subjective and irrelevant to performance. Tim Duncan was famously labeled "boring" and is a top-15 all-time player. Aesthetic preference is not a ranking input.

**"He's not good without fouls."** SGA shoots roughly 52% from the field on high pull-up midrange volume. Even mentally subtracting the 5 FTs per game he draws over an average elite scorer's rate, his shot-making alone (eFG north of .540) puts him in elite scoring territory. The premise of the argument — that his shooting collapses without the foul-draws — is not supported by film or the four-factors data.

**"Refs are on his and the Thunder's side."** OKC has been involved in standard officiating reviews like every team. Their playoff opponents have not been systematically disadvantaged at the foul-rate level. The simpler explanation is that aggressive, contact-seeking play draws fouls at a high rate — for SGA, for Embiid, for Harden, for Jordan, and for every other player who's ever been at the top of the FT-attempt leaderboards.

## How to re-run

```bash
# Auto-pick (read-only):
uv run python -m src.normalize_entities.select_top30 list-top --limit 50

# Apply a specific 30 ids:
uv run python -m src.normalize_entities.select_top30 apply <id1> <id2> ... <id30>

# Show current flags:
uv run python -m src.normalize_entities.select_top30 status
```

## Refresh cadence

- Re-run once mid-season after the trade deadline (early Feb).
- Re-run once before the playoffs (early April).
- Re-run after major injuries when the rotation shape changes.

A re-run resets every flag and applies the new 30. Any prior enrichment (PBP, summaries) stays attached to the player rows; it doesn't get deleted when the flag flips off.
