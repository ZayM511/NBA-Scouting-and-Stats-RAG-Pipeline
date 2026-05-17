-- 002_player_clutch_stats.sql
-- Season-aggregate clutch stats per player + season + season_type. Sourced
-- from nba_api LeagueDashPlayerClutch (default: last 5 minutes, score within
-- 5). One API call per (season, season_type) returns every player; we
-- filter to the active roster on insert.
--
-- "Clutch" here matches the NBA's standard definition: the last 5 minutes
-- of regulation or overtime with score margin <= 5 points.

BEGIN;

CREATE TABLE IF NOT EXISTS player_clutch_stats (
    player_id     INT  NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    season        TEXT NOT NULL,                                -- e.g., '2025-26'
    season_type   TEXT NOT NULL CHECK (season_type IN ('Regular Season', 'Playoffs')),
    -- Totals (NOT per-game). Per-game derivations: divide by gp.
    gp            INT  NOT NULL DEFAULT 0,                      -- games played WITH clutch minutes
    min_total     REAL NOT NULL DEFAULT 0,                      -- total clutch minutes
    pts           INT  NOT NULL DEFAULT 0,
    fgm           INT  NOT NULL DEFAULT 0,
    fga           INT  NOT NULL DEFAULT 0,
    fg3m          INT  NOT NULL DEFAULT 0,
    fg3a          INT  NOT NULL DEFAULT 0,
    ftm           INT  NOT NULL DEFAULT 0,
    fta           INT  NOT NULL DEFAULT 0,
    oreb          INT  NOT NULL DEFAULT 0,
    dreb          INT  NOT NULL DEFAULT 0,
    reb           INT  NOT NULL DEFAULT 0,
    ast           INT  NOT NULL DEFAULT 0,
    tov           INT  NOT NULL DEFAULT 0,
    stl           INT  NOT NULL DEFAULT 0,
    blk           INT  NOT NULL DEFAULT 0,
    pf            INT  NOT NULL DEFAULT 0,
    pfd           INT  NOT NULL DEFAULT 0,
    plus_minus    INT  NOT NULL DEFAULT 0,
    -- Pre-derived shooting metrics (cached so text-to-SQL doesn't have to
    -- recompute). Use the canonical formulas:
    --   TS%  = pts / (2 * (fga + 0.44 * fta))
    --   eFG% = (fgm + 0.5 * fg3m) / fga
    -- Stored as decimals 0..1 (multiply by 100 to display as a percentage).
    ts_pct        REAL,                                          -- nullable: undefined when fga + fta = 0
    efg_pct       REAL,                                          -- nullable: undefined when fga = 0
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (player_id, season, season_type)
);

CREATE INDEX IF NOT EXISTS player_clutch_stats_season_idx
    ON player_clutch_stats (season, season_type);

INSERT INTO schema_migrations (id, name) VALUES (2, 'player_clutch_stats')
    ON CONFLICT (id) DO NOTHING;

COMMIT;
