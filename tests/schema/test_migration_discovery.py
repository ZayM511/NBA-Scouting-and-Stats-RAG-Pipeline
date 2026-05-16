"""Tests for the migration discovery logic. The migrate command itself needs
a real Postgres; we cover the pure logic here so unit tests stay fast.
"""

from __future__ import annotations

from src.schema.migrate import discover_migrations


def test_discovers_init_migration() -> None:
    migrations = discover_migrations()
    assert any(m.id == 1 and m.name == "001_init" or m.name == "init" for m in migrations), (
        f"Expected 001_init, got {[(m.id, m.name) for m in migrations]}"
    )


def test_migrations_sorted_by_id() -> None:
    migrations = discover_migrations()
    ids = [m.id for m in migrations]
    assert ids == sorted(ids), "discover_migrations must return in id-ascending order"


def test_init_migration_contains_required_tables() -> None:
    migrations = discover_migrations()
    init = next((m for m in migrations if m.id == 1), None)
    assert init is not None, "001_init.sql is missing"
    sql = init.sql.lower()
    for table in [
        "teams",
        "players",
        "player_aliases",
        "games",
        "player_game_stats",
        "play_by_play",
        "articles",
        "articles_chunks",
        "ingest_audit",
        "schema_migrations",
    ]:
        assert f"create table if not exists {table}" in sql, f"missing table: {table}"


def test_init_migration_creates_critical_indexes() -> None:
    migrations = discover_migrations()
    init = next((m for m in migrations if m.id == 1), None)
    assert init is not None
    sql = init.sql.lower()
    # HNSW on the chunk embeddings
    assert "using hnsw (embedding vector_cosine_ops)" in sql
    # GIN on player_ids array
    assert "using gin (player_ids)" in sql
    # GIN on the tsvector for full-text search
    assert "using gin (text_tsv)" in sql


def test_init_migration_uses_1024_dim_vectors() -> None:
    """voyage-3-large produces 1024-dim embeddings; the schema must match."""
    migrations = discover_migrations()
    init = next((m for m in migrations if m.id == 1), None)
    assert init is not None
    assert "vector(1024)" in init.sql.lower()


def test_init_migration_enforces_playoff_round_range() -> None:
    migrations = discover_migrations()
    init = next((m for m in migrations if m.id == 1), None)
    assert init is not None
    assert "playoff_round between 1 and 4" in init.sql.lower()
