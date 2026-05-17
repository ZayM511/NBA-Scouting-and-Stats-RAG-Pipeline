-- 003_live_game_state.sql
-- Extend the games table so it can hold live game state (period, clock,
-- live status) and accurate future-game metadata (tipoff_utc, arena,
-- broadcast). Sourced from nba_api ScoreBoard (live) and
-- ScheduleLeagueV2Int (upcoming), with balldontlie.io as a fallback.
--
-- Before this migration the header endpoint synthesized both fields:
--   * _simulate_live() returned hardcoded quarter/clock/scores
--   * _compute_upcoming() returned "tomorrow at 8:30pm ET" no matter what
-- These columns let header.py read real values from the DB instead.

BEGIN;

ALTER TABLE games ADD COLUMN IF NOT EXISTS tipoff_utc   TIMESTAMPTZ;
ALTER TABLE games ADD COLUMN IF NOT EXISTS status       TEXT NOT NULL DEFAULT 'scheduled';
ALTER TABLE games ADD COLUMN IF NOT EXISTS period       INT;
ALTER TABLE games ADD COLUMN IF NOT EXISTS game_clock   TEXT;
ALTER TABLE games ADD COLUMN IF NOT EXISTS arena_name   TEXT;
ALTER TABLE games ADD COLUMN IF NOT EXISTS broadcast    TEXT;
ALTER TABLE games ADD COLUMN IF NOT EXISTS refreshed_at TIMESTAMPTZ;

-- status legal values: 'scheduled' | 'live' | 'final' | 'postponed'.
-- Existing rows (already-final games loaded via LeagueGameLog) should be
-- marked 'final' so they don't pollute "next scheduled game" queries.
UPDATE games SET status = 'final' WHERE home_score IS NOT NULL AND away_score IS NOT NULL;

ALTER TABLE games ADD CONSTRAINT games_status_check
    CHECK (status IN ('scheduled', 'live', 'final', 'postponed'));

-- Partial index keeps live/upcoming lookups O(1) once thousands of finals
-- accumulate. Final games are 99% of the table; we never scan them in the
-- header path.
CREATE INDEX IF NOT EXISTS games_status_active_idx
    ON games (tipoff_utc) WHERE status IN ('live', 'scheduled');

INSERT INTO schema_migrations (id, name) VALUES (3, 'live_game_state')
    ON CONFLICT (id) DO NOTHING;

COMMIT;
