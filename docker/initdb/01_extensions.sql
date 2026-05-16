-- 01_extensions.sql — enable pgvector and tsvector dependencies.
-- Runs once when the Postgres container is first initialized.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;     -- fuzzy match for entity normalization
CREATE EXTENSION IF NOT EXISTS unaccent;    -- strip accents for international names
