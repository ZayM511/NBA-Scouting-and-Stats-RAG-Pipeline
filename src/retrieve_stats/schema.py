"""Schema description used in the SQL-gen prompt.

Kept as a Python constant rather than read from the live DB so the
prompt is stable across runs (the live DB might be empty mid-migration,
which would leave the prompt empty). When `001_init.sql` changes, this
constant has to change too — and the test in
`tests/retrieve_stats/test_schema.py` enforces that key tables and
columns appear in both places.
"""

from __future__ import annotations


# Important: keep this in sync with src/schema/migrations/001_init.sql.
# The test_schema test asserts that core tables/columns appear here.
SCHEMA_DESCRIPTION = """\
TABLES:

teams
  team_id INT PK
  abbreviation TEXT       -- e.g., 'GSW', 'LAL'
  city TEXT, name TEXT    -- city='Golden State', name='Warriors'
  conference TEXT         -- 'East' or 'West'
  division TEXT

players
  player_id INT PK
  name TEXT               -- full canonical name, e.g. 'Stephen Curry'
  team_id INT FK teams(team_id)
  team TEXT               -- denormalized abbreviation, e.g. 'GSW'
  position TEXT           -- 'G', 'F', 'C', 'G-F', etc.
  jersey_number TEXT
  height_inches INT, weight_lbs INT
  birthdate DATE
  draft_year INT
  is_active BOOLEAN       -- TRUE for current-roster players
  is_top30 BOOLEAN        -- TRUE for the 30 deep-dive players

games
  game_id TEXT PK         -- nba_api game id, e.g. '0022400123'
  date DATE
  season TEXT             -- e.g. '2025-26'
  season_type TEXT        -- 'Regular Season', 'Playoffs', 'Play-In'
  home_team TEXT, away_team TEXT   -- abbreviations
  home_score INT, away_score INT
  is_playoff BOOLEAN
  playoff_round INT       -- 1..4 (R1, R2, ConfFinals, Finals) when is_playoff

player_game_stats
  player_id INT FK players(player_id)
  game_id TEXT FK games(game_id)
  is_clutch_data BOOLEAN  -- whether this row is the clutch-only split
  team TEXT
  minutes REAL
  pts INT, ast INT, reb INT, oreb INT, dreb INT
  stl INT, blk INT, tov INT, pf INT
  fgm INT, fga INT, fg_pct REAL
  fg3m INT, fg3a INT, fg3_pct REAL
  ftm INT, fta INT, ft_pct REAL
  ts_pct REAL              -- pts / (2 * (fga + 0.44 * fta))
  usg_pct REAL             -- usage rate (NULL for non-top-30 players this season)
  plus_minus INT
  PRIMARY KEY (player_id, game_id, is_clutch_data)

play_by_play
  id BIGSERIAL PK
  game_id TEXT
  player_id INT            -- ingested only for is_top30 players
  period INT, clock TEXT
  event_type TEXT          -- 'shot', 'rebound', 'turnover', ...
  shot_x REAL, shot_y REAL -- shot location in court coords
  shot_distance REAL
  shot_made BOOLEAN
  shot_type TEXT           -- '2PT', '3PT', 'FT'

articles_chunks
  id BIGSERIAL PK
  article_id TEXT FK
  text TEXT
  player_ids INT[]         -- GIN-indexed; use && for array overlap
  team TEXT, date DATE
  source TEXT              -- 'r/nba', 'The Athletic', 'authored_summary', ...

CONVENTIONS:

- The current season is '2025-26'. Default to it unless the question
  names another season explicitly.
- Use the existing is_top30 flag for "the top 30 players" rather than
  trying to derive a top-30 list from per-game stats at query time.
- Use the GIN-friendly && operator for player_ids array filters; never
  use ANY() on the array column (would defeat the GIN index).
- For team-name queries, prefer the abbreviation column ('LAL') over
  the city/name pair.
- Playoff rounds: 1=R1, 2=R2, 3=ConferenceFinals, 4=Finals.
- For "averages", use AVG over player_game_stats rows. To exclude
  games where the player did not play, filter WHERE pgs.minutes > 0.
- For "leaders" / rankings, use ORDER BY ... DESC LIMIT N.
- Always restrict to NOT is_clutch_data unless the question explicitly
  asks for clutch stats (otherwise the same game contributes twice).

EXAMPLE WELL-FORMED QUERIES:

-- Q: Top 5 scorers per game (regular season, min 20 games)
SELECT p.name, p.team, COUNT(*) AS games, ROUND(AVG(pgs.pts)::numeric, 1) AS ppg
FROM player_game_stats pgs
JOIN players p ON p.player_id = pgs.player_id
JOIN games g ON g.game_id = pgs.game_id
WHERE NOT pgs.is_clutch_data
  AND g.season = '2025-26'
  AND g.season_type = 'Regular Season'
GROUP BY p.name, p.team
HAVING COUNT(*) >= 20
ORDER BY AVG(pgs.pts) DESC
LIMIT 5;

-- Q: Wemby's playoff blocks per game
SELECT ROUND(AVG(pgs.blk)::numeric, 2) AS bpg, COUNT(*) AS games
FROM player_game_stats pgs
JOIN players p ON p.player_id = pgs.player_id
JOIN games g ON g.game_id = pgs.game_id
WHERE p.name = 'Victor Wembanyama'
  AND NOT pgs.is_clutch_data
  AND g.is_playoff = TRUE
  AND g.season = '2025-26';
"""
