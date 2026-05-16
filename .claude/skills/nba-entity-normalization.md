# NBA Entity Normalization

Player names are the central join key for the entire prose pipeline. Get this right and a query for "the Chef" pulls Curry's articles; get it wrong and the system looks broken.

This skill explains the approach. The implementation lives in `src/normalize_entities/`.

## The problem

Articles refer to the same player in many ways:

- Full name: "Stephen Curry"
- Last name: "Curry"
- First name (rare, mostly Reddit): "Steph"
- Nicknames: "the Chef", "Chef Curry", "Wardell"
- Misspellings: "Steph Curry" vs "Stephen Curry" vs "Steph Curry "
- Honorifics: "Mr. Curry" (rare)
- Possessives: "Curry's", "Steph's"
- Other languages and transliterations for international players

For Wemby alone you'll see: "Victor Wembanyama", "Wembanyama", "Wemby", "Wemba" (typo), "the Alien", "Vic".

Every chunk needs a canonical `player_ids INT[]` column so we can filter to all chunks about a player regardless of how the article phrased it.

## The approach

Three-stage pipeline:

### Stage 1 — Build an alias map (offline, one-time per season + refreshed weekly)

For every active player in `players`:

1. Start from the canonical name from `nba_api`.
2. Add the last name alone, the first name alone, and common short forms.
3. Ask Claude (Sonnet 4.6) to generate likely nicknames given the player's name, position, and team. Prompt format:

```
Player: <full_name>, <position>, <team>, <years_in_league> seasons in the league.
List the 5-15 nicknames most likely to appear in NBA media coverage and on r/nba.
Output: JSON array of strings, no commentary.
```

4. Verify against a small Reddit sample (search r/nba for the player's name; collect the nicknames that show up at least three times in the past month).
5. Manually add any obvious misses for the top 30 players.

Store as:

```sql
CREATE TABLE player_aliases (
  alias TEXT PRIMARY KEY,             -- normalized: lowercase, no punctuation
  player_id INT NOT NULL REFERENCES players(player_id),
  confidence REAL NOT NULL,           -- 1.0 = canonical, 0.6 = LLM-generated unverified
  source TEXT NOT NULL                -- 'canonical', 'llm', 'reddit', 'manual'
);

CREATE INDEX player_aliases_player_id_idx ON player_aliases (player_id);
```

Normalize the `alias` field consistently: lowercase, strip punctuation, NFC-unicode, single spaces.

### Stage 2 — Run the normalizer on every ingested chunk

For each new chunk:

1. Tokenize the text into n-grams (1- to 4-word windows).
2. Lowercase and strip punctuation each n-gram, same normalization as Stage 1.
3. Look up each n-gram in `player_aliases`.
4. Collect the hit `player_id`s, dedupe, store as `player_ids INT[]`.

Disambiguation rules:

- If "Curry" appears and the article also mentions "Warriors" or "Steph" or any other Curry alias, pin to `player_id = 201939` (Stephen Curry).
- If "Curry" appears alone with no team context, look at neighboring named players to decide between Stephen Curry and Seth Curry. If still ambiguous, mark `confidence = 0.5` and store both.
- If a chunk has more than 8 player hits, it's probably a power-rankings article; mark `article_type = 'rankings'` and keep all hits.

### Stage 3 — Verify on a held-out set

Hand-tag 50 articles with the players they mention. Run the normalizer. Compute precision (hits that are correct) and recall (correct hits found). Target: precision > 0.95, recall > 0.90 on the top 30 players. Lower bars are acceptable for fringe players.

## Concrete example

Article text (excerpt):

> "Steph dropped 42 last night, but the Warriors still lost. Wiseman didn't see the floor.
> The Chef has been hot from deep all month."

Normalizer output:

- "Steph" → `201939` (Stephen Curry)
- "Warriors" → not a player, ignored at the player layer (but `team = 'GSW'` set on the chunk)
- "Wiseman" → `1630164` (James Wiseman)
- "The Chef" → `201939` (Stephen Curry, again — deduped)

Stored: `player_ids = ARRAY[201939, 1630164]`, `team = 'GSW'`.

## Edge cases worth coding tests for

- **Possessives.** "Curry's three" → strip the `'s` before lookup.
- **All-caps.** "WEMBANYAMA WAS UNREAL" → normalize to lowercase first.
- **Hyphenated names.** "Karl-Anthony Towns" — keep the hyphen; the alias map should include both "Karl-Anthony Towns" and "KAT".
- **Apostrophes in names.** "Shai Gilgeous-Alexander" → handle `'` and `'` (the curly apostrophe).
- **Numbers in chunks.** "Player 23 led the team" — don't try to map jersey numbers to players; too ambiguous across teams.
- **First-name-only collisions.** "Anthony" alone — could be Anthony Edwards or Carmelo Anthony or several others. Require a second signal (last name nearby, team mention) before claiming a hit.
- **Suffixes.** "Tim Hardaway Jr." vs "Tim Hardaway" — the suffix matters; store as two separate canonical names.
- **International transliterations.** "Luka Dončić" vs "Luka Doncic" — normalize the special characters before lookup.

## Why this matters for the project pitch

In interviews, this is one of the strongest stories. Entity linking is a real problem every sports data company solves; the existence of the alias map signals you've shipped data systems rather than just done tutorials.

The two-sentence version: *"I built a player alias map that resolves every name variant — including nicknames and Reddit slang — to a canonical player_id. That's what lets a query for 'the Chef' pull all of Curry's articles. Entity linking is the unsexy gold of any sports RAG system."*

## Refresh cadence

- Initial build at the start of the season.
- Weekly delta refresh during the regular season (new players, trades, new nicknames).
- Daily delta refresh during the playoffs (new playoff-context nicknames appear fast).
- Monthly precision/recall audit on a fresh 50-article sample.
