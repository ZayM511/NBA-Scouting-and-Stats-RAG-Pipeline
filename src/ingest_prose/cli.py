"""CLI for prose ingestion.

Usage:
    uv run python -m src.ingest_prose.cli reddit                      # default: top 50 from r/nba (this month)
    uv run python -m src.ingest_prose.cli reddit --sub nba --sub nba-discussion --limit-per-sub 30
    uv run python -m src.ingest_prose.cli reddit --listing top --timeframe week --limit-per-sub 20
    uv run python -m src.ingest_prose.cli reddit --per-doc-sleep-seconds 25  # for Voyage free tier (3 RPM)
    uv run python -m src.ingest_prose.cli status                      # show counts in articles + articles_chunks
"""

from __future__ import annotations

import logging
import sys
import time

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn

from src.config import get_settings
from src.ingest_prose.db import connect
from src.ingest_prose.embedder import Embedder
from src.ingest_prose.pipeline import IngestResult, ingest_document
from src.ingest_prose.reddit_source import ingest_subreddits
from src.normalize_entities.resolve import AliasResolver

console = Console()
app = typer.Typer(help="Prose ingestion: Reddit, articles, scouting newsletters.")


DEFAULT_SUBS = ("nba",)


def _configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@app.command()
def reddit(
    sub: list[str] = typer.Option(
        list(DEFAULT_SUBS),
        "--sub",
        "-s",
        help="Subreddit name (without r/). Repeat the flag for multiple subs.",
    ),
    listing: str = typer.Option("top", help="hot | new | top | rising"),
    timeframe: str = typer.Option("month", help="When listing=top: hour|day|week|month|year|all"),
    limit_per_sub: int = typer.Option(50, help="Threads to fetch per subreddit (max 100)."),
    top_comments: int = typer.Option(10, help="Top-level comments to include per thread."),
    per_doc_sleep_seconds: float = typer.Option(
        0.0,
        help=(
            "Sleep this many seconds between documents. "
            "Use 25.0 if you're on Voyage's free tier (3 RPM cap). "
            "Set to 0 once you've added a payment method on Voyage's dashboard."
        ),
    ),
    dry_run: bool = typer.Option(False, help="Fetch + print but do not write to DB or embed."),
) -> None:
    """Ingest top threads from one or more subreddits into articles_chunks."""
    _configure_logging()
    console.print(
        f"[cyan]Reddit ingest: subs={sub} listing={listing} timeframe={timeframe} "
        f"limit_per_sub={limit_per_sub} top_comments={top_comments} dry_run={dry_run}[/]"
    )

    if dry_run:
        n = 0
        for doc in ingest_subreddits(
            sub,
            listing=listing,
            timeframe=timeframe,
            limit_per_sub=limit_per_sub,
            top_comments=top_comments,
        ):
            n += 1
            console.print(f"  {doc.date} | {doc.source} | {doc.title[:80]}")
        console.print(f"[green]Would ingest {n} docs.[/]")
        return

    embedder = Embedder()
    totals = {"ingested": 0, "unchanged": 0, "empty": 0, "error": 0}
    total_chunks = 0
    total_tokens = 0

    with connect() as conn:
        resolver = AliasResolver.from_db(conn)
        console.print(f"[dim]Loaded {len(resolver)} aliases.[/]")

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("({task.completed} docs)"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("reddit ingest", total=None)
            for doc in ingest_subreddits(
                sub,
                listing=listing,
                timeframe=timeframe,
                limit_per_sub=limit_per_sub,
                top_comments=top_comments,
            ):
                result = ingest_document(conn, doc, resolver=resolver, embedder=embedder)
                totals[result.status] = totals.get(result.status, 0) + 1
                total_chunks += result.chunks_inserted
                total_tokens += result.embedding_tokens
                progress.update(task, advance=1)
                if result.status == "error":
                    console.print(f"[red]error[/] {doc.url}: {result.error}")
                if per_doc_sleep_seconds > 0 and result.status == "ingested":
                    # Stay under the Voyage free-tier 3 RPM rate cap.
                    time.sleep(per_doc_sleep_seconds)

    embedder.close()
    console.print(
        f"\n[green]Done.[/] "
        f"ingested={totals['ingested']} unchanged={totals['unchanged']} "
        f"empty={totals['empty']} error={totals['error']} "
        f"| chunks_inserted={total_chunks} embedding_tokens={total_tokens}"
    )


@app.command()
def status() -> None:
    """Print row counts for the prose tables."""
    _configure_logging()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                  (SELECT COUNT(*) FROM articles)              AS articles,
                  (SELECT COUNT(*) FROM articles_chunks)       AS chunks,
                  (SELECT COUNT(DISTINCT source) FROM articles) AS sources,
                  (SELECT COUNT(*) FROM articles_chunks
                     WHERE array_length(player_ids, 1) > 0)    AS chunks_with_players
            """)
            row = cur.fetchone()
            cur.execute("""
                SELECT source, COUNT(*) AS n
                FROM articles GROUP BY source ORDER BY n DESC LIMIT 10
            """)
            by_source = cur.fetchall()

    console.print(f"[cyan]Articles:[/] {row['articles']}")
    console.print(f"[cyan]Chunks:[/] {row['chunks']}")
    console.print(f"[cyan]Distinct sources:[/] {row['sources']}")
    console.print(f"[cyan]Chunks with at least one player_id:[/] {row['chunks_with_players']}")
    console.print("\n[cyan]Top sources:[/]")
    for r in by_source:
        console.print(f"  {r['source']:<30} {r['n']}")


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main() or 0)
