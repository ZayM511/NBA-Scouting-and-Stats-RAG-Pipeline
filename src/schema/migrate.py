"""Migration runner.

Applies every `.sql` file under `src/schema/migrations/` in lexicographic
order, skipping migrations whose `id` (the leading number) is already in
`schema_migrations`.

Usage:
    uv run python -m src.schema.migrate up      # apply pending migrations
    uv run python -m src.schema.migrate status  # show applied vs pending

Why raw SQL and not Alembic: the project schema is small (one init + a few
deltas), and raw SQL keeps the pgvector + GIN + HNSW syntax visible. Alembic's
abstraction over those would be a tax for no benefit.
"""

from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg
import typer
from rich.console import Console
from rich.table import Table

from src.config import get_settings

logger = logging.getLogger(__name__)
console = Console()
app = typer.Typer(help="Database migration runner.")

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
MIGRATION_FILENAME_RE = re.compile(r"^(\d+)_(.+)\.sql$")


@dataclass(frozen=True)
class Migration:
    id: int
    name: str
    path: Path

    @property
    def sql(self) -> str:
        return self.path.read_text(encoding="utf-8")


def discover_migrations() -> list[Migration]:
    """Return every migration on disk, sorted by id."""
    out: list[Migration] = []
    if not MIGRATIONS_DIR.exists():
        return out
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        match = MIGRATION_FILENAME_RE.match(path.name)
        if not match:
            logger.warning("skipping non-migration file: %s", path.name)
            continue
        out.append(Migration(id=int(match.group(1)), name=match.group(2), path=path))
    return out


def applied_ids(conn: psycopg.Connection) -> set[int]:
    """Return ids already applied. Returns empty set if the tracking table
    does not exist yet (first run)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'schema_migrations'
            )
            """
        )
        row = cur.fetchone()
        exists = bool(row[0]) if row else False
        if not exists:
            return set()
        cur.execute("SELECT id FROM schema_migrations")
        return {row[0] for row in cur.fetchall()}


@app.command()
def up() -> None:
    """Apply every pending migration in order."""
    settings = get_settings()
    discovered = discover_migrations()
    if not discovered:
        console.print("[yellow]No migrations found under src/schema/migrations/[/]")
        return

    with psycopg.connect(str(settings.postgres_url), autocommit=False) as conn:
        already = applied_ids(conn)
        pending = [m for m in discovered if m.id not in already]
        if not pending:
            console.print("[green]Schema is up to date.[/]")
            return
        for migration in pending:
            console.print(f"[cyan]Applying[/] {migration.id:03d}_{migration.name} ...")
            with conn.cursor() as cur:
                cur.execute(migration.sql)
            conn.commit()
            console.print(f"[green]OK[/] {migration.id:03d}_{migration.name}")
    console.print(f"[green]Applied {len(pending)} migration(s).[/]")


@app.command()
def status() -> None:
    """Print applied vs pending migrations."""
    settings = get_settings()
    discovered = discover_migrations()
    with psycopg.connect(str(settings.postgres_url), autocommit=True) as conn:
        already = applied_ids(conn)

    table = Table(title="Migrations")
    table.add_column("ID", justify="right")
    table.add_column("Name")
    table.add_column("Status")
    for m in discovered:
        marker = "[green]applied[/]" if m.id in already else "[yellow]pending[/]"
        table.add_row(f"{m.id:03d}", m.name, marker)
    console.print(table)


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main() or 0)
