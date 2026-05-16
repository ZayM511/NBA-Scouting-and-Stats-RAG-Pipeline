-- 001_init.sql — initial schema for the NBA Scouting + Stats Hybrid RAG.
--
-- Tables: teams, players, player_aliases, games, player_game_stats,
--         play_by_play (top-30 only), articles, articles_chunks,
--         ingest_audit, schema_migrations.
--
-- Critical indexes:
--   * HNSW on articles_chunks.embedding (vector_cosine_ops)
--   * GIN on articles_chunks.player_ids        (the main hybrid-filter path)
--   * GIN on articles_chunks.text_tsv          (BM25 / full-text search)
--
-- Run via:  uv run python -m src.schema.migrate up

BEGIN;

-- ---------------------------------------------------------------------------
-- Extensions (idempotent; also enabled by docker/initdb/01_extensions.sql)
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- ---------------------------------------------------------------------------
-- Migration tracking
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_migrations (
    id         INT PRIMARY KEY,
    name       TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Teams
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teams (
    team_id      INT PRIMARY KEY,                  -- nba_api team_id
    abbreviation TEXT NOT NULL UNIQUE,             -- e.g. 'GSW'
    city         TEXT NOT NULL,
    name         TEXT NOT NULL,                    -- 'Warriors'
    conference   TEXT CHECK (conference IN ('East', 'West')),
    division     TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Players
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS players (
    player_id      INT PRIMARY KEY,                -- nba_api player_id
    name           TEXT NOT NULL,
    team_id        INT REFERENCES teams(team_id),
    team           TEXT,                           -- denormalized abbreviation
    position       TEXT,
    jersey_number  TEXT,
    height_inches  INT,
    weight_lbs     INT,
    birthdate      DATE,
    draft_year     INT,
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    is_top30       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS players_is_top30_idx ON players (is_top30) WHERE is_top30 = TRUE;
CREATE INDEX IF NOT EXISTS players_team_idx     ON players (team);
CREATE INDEX IF NOT EXISTS players_name_trgm    ON players USING gin (name gin_trgm_ops);

-- ---------------------------------------------------------------------------
-- Player aliases  (see .claude/skills/nba-entity-normalization.md)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS player_aliases (
    alias       TEXT PRIMARY KEY,                  -- normalized: lowercase, no punctuation
    player_id   INT NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    confidence  REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    source      TEXT NOT NULL CHECK (source IN ('canonical', 'llm', 'reddit', 'manual')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS player_aliases_player_id_idx ON player_aliases (player_id);
CREATE INDEX IF NOT EXISTS player_aliases_alias_trgm     ON player_aliases USING gin (alias gin_trgm_ops);

-- ---------------------------------------------------------------------------
-- Games
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS games (
    game_id        TEXT PRIMARY KEY,               -- nba_api game_id (e.g., '0022400123')
    date           DATE NOT NULL,
    season         TEXT NOT NULL,                  -- e.g., '2025-26'
    season_type    TEXT NOT NULL CHECK (season_type IN ('Regular Season', 'Playoffs', 'Play-In', 'Preseason')),
    home_team      TEXT NOT NULL,
    away_team      TEXT NOT NULL,
    home_score     INT,
    away_score     INT,
    is_playoff     BOOLEAN NOT NULL DEFAULT FALSE,
    playoff_round  INT CHECK (playoff_round BETWEEN 1 AND 4),
    playoff_series TEXT,                           -- e.g., 'OKC-SAS-2026-WCF'
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS games_date_idx       ON games (date DESC);
CREATE INDEX IF NOT EXISTS games_season_idx     ON games (season);
CREATE INDEX IF NOT EXISTS games_playoff_idx    ON games (is_playoff, playoff_round) WHERE is_playoff = TRUE;
CREATE INDEX IF NOT EXISTS games_home_team_idx  ON games (home_team);
CREATE INDEX IF NOT EXISTS games_away_team_idx  ON games (away_team);

-- ---------------------------------------------------------------------------
-- Per-game stats. is_clutch_data flag lets us store both full-game and
-- clutch-only rows for the same (player_id, game_id) pair.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS player_game_stats (
    player_id        INT NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    game_id          TEXT NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
    is_clutch_data   BOOLEAN NOT NULL DEFAULT FALSE,
    team             TEXT NOT NULL,
    minutes          REAL,
    pts              INT,
    ast              INT,
    reb              INT,
    oreb             INT,
    dreb             INT,
    stl              INT,
    blk              INT,
    tov              INT,
    pf               INT,
    fgm              INT,
    fga              INT,
    fg_pct           REAL,
    fg3m             INT,
    fg3a             INT,
    fg3_pct          REAL,
    ftm              INT,
    fta              INT,
    ft_pct           REAL,
    ts_pct           REAL,                          -- pts / (2 * (fga + 0.44 * fta))
    usg_pct          REAL,
    plus_minus       INT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (player_id, game_id, is_clutch_data)
);

CREATE INDEX IF NOT EXISTS pgs_player_id_idx   ON player_game_stats (player_id);
CREATE INDEX IF NOT EXISTS pgs_game_id_idx     ON player_game_stats (game_id);
CREATE INDEX IF NOT EXISTS pgs_team_idx        ON player_game_stats (team);

-- ---------------------------------------------------------------------------
-- Play-by-play. Stored only for top-30 players to keep storage bounded.
-- Used for shot heatmaps and clutch event reconstruction.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS play_by_play (
    id              BIGSERIAL PRIMARY KEY,
    game_id         TEXT NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
    player_id       INT REFERENCES players(player_id) ON DELETE CASCADE,
    period          INT,
    clock           TEXT,
    event_type      TEXT,                          -- 'shot', 'rebound', 'turnover', ...
    event_action    TEXT,                          -- 'made', 'missed', 'offensive', ...
    description     TEXT,
    shot_x          REAL,
    shot_y          REAL,
    shot_distance   REAL,
    shot_made       BOOLEAN,
    shot_type       TEXT,                          -- '2PT', '3PT', 'FT'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS pbp_player_id_idx    ON play_by_play (player_id);
CREATE INDEX IF NOT EXISTS pbp_game_id_idx      ON play_by_play (game_id);
CREATE INDEX IF NOT EXISTS pbp_player_game_idx  ON play_by_play (player_id, game_id);

-- ---------------------------------------------------------------------------
-- Articles (parent table). One row per ingested document.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS articles (
    article_id      TEXT PRIMARY KEY,              -- sha256 of canonical URL
    url             TEXT NOT NULL UNIQUE,
    title           TEXT,
    source          TEXT NOT NULL,                 -- 'The Athletic', 'r/nba', ...
    article_type    TEXT NOT NULL CHECK (
        article_type IN ('news', 'scouting', 'reddit_thread', 'authored_summary')
    ),
    date            DATE,
    content_sha256  TEXT NOT NULL,                 -- detect when source text changed
    raw_text        TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS articles_date_idx   ON articles (date DESC);
CREATE INDEX IF NOT EXISTS articles_source_idx ON articles (source);
CREATE INDEX IF NOT EXISTS articles_type_idx   ON articles (article_type);

-- ---------------------------------------------------------------------------
-- Article chunks. The vector store. The hot table.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS articles_chunks (
    id                  BIGSERIAL PRIMARY KEY,
    article_id          TEXT NOT NULL REFERENCES articles(article_id) ON DELETE CASCADE,
    chunk_index         INT NOT NULL,
    text                TEXT NOT NULL,                 -- raw chunk text
    text_with_context   TEXT NOT NULL,                 -- contextual-retrieval prefixed (the embedded form)
    player_ids          INT[] NOT NULL DEFAULT '{}',   -- resolved via normalize_entities
    team                TEXT,
    date                DATE,
    source              TEXT NOT NULL,
    article_type        TEXT NOT NULL,
    content_sha256      TEXT NOT NULL,                 -- detect stale embedding
    embedding           VECTOR(1024),                  -- voyage-3-large dim
    text_tsv            TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (article_id, chunk_index)
);

-- HNSW vector index. Must come AFTER the table is created.
CREATE INDEX IF NOT EXISTS articles_chunks_embedding_hnsw
    ON articles_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- The main hybrid-filter path. Filter-then-vector is ~4000x faster than scanning.
CREATE INDEX IF NOT EXISTS articles_chunks_player_ids_gin
    ON articles_chunks USING gin (player_ids);

-- BM25 / full-text search.
CREATE INDEX IF NOT EXISTS articles_chunks_text_tsv_gin
    ON articles_chunks USING gin (text_tsv);

-- Freshness sort (playoff time-decay).
CREATE INDEX IF NOT EXISTS articles_chunks_date_idx
    ON articles_chunks (date DESC);

-- Useful filters.
CREATE INDEX IF NOT EXISTS articles_chunks_source_idx       ON articles_chunks (source);
CREATE INDEX IF NOT EXISTS articles_chunks_article_type_idx ON articles_chunks (article_type);

-- ---------------------------------------------------------------------------
-- Ingest audit log. Append-only. LLM04 mitigation.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingest_audit (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT NOT NULL,                 -- 'nba_api', 'The Athletic', 'r/nba', ...
    url             TEXT,
    content_sha256  TEXT,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    chunk_count     INT,
    status          TEXT NOT NULL CHECK (status IN ('success', 'partial', 'failed')),
    error           TEXT
);

CREATE INDEX IF NOT EXISTS ingest_audit_ingested_at_idx ON ingest_audit (ingested_at DESC);
CREATE INDEX IF NOT EXISTS ingest_audit_source_idx       ON ingest_audit (source);

-- ---------------------------------------------------------------------------
-- Grant read-only role access to the new tables. The default-privileges line
-- in docker/initdb/02_readonly_role.sql covers FUTURE tables, but tables
-- created in the same migration as a privilege grant sometimes miss it; this
-- belt-and-suspenders is cheap.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nbarag_readonly') THEN
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO nbarag_readonly;
        GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO nbarag_readonly;
    END IF;
END;
$$;

-- ---------------------------------------------------------------------------
-- Record the migration.
-- ---------------------------------------------------------------------------
INSERT INTO schema_migrations (id, name)
VALUES (1, '001_init')
ON CONFLICT (id) DO NOTHING;

COMMIT;
