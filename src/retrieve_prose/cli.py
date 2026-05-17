"""CLI for prose retrieval. Lets you compare BM25 / dense / hybrid for any query.

Usage:
    uv run python -m src.retrieve_prose.cli search "wemby defense"
    uv run python -m src.retrieve_prose.cli search "cooper flagg roy" --top-k 5
    uv run python -m src.retrieve_prose.cli search "scouting on harden trade" --strategy dense
    uv run python -m src.retrieve_prose.cli search "lebron at 41" --player 2544
    uv run python -m src.retrieve_prose.cli compare "wemby defense"   # side-by-side BM25 vs dense vs hybrid
"""

from __future__ import annotations

import logging
import sys
from typing import Literal

import typer
from rich.console import Console
from rich.table import Table

from src.config import get_settings
from src.ingest_prose.embedder import Embedder
from src.retrieve_prose.bm25 import search_bm25
from src.retrieve_prose.dense import search_dense
from src.retrieve_prose.filters import ChunkFilters
from src.retrieve_prose.hybrid_search import hybrid_search
from src.retrieve_prose.rerank import Reranker

console = Console()
app = typer.Typer(help="Prose retrieval: BM25, dense, hybrid + rerank.")

Strategy = Literal["bm25", "dense", "hybrid"]


def _configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@app.command()
def search(
    query: str = typer.Argument(..., help="The retrieval query."),
    strategy: str = typer.Option("hybrid", help="bm25 | dense | hybrid"),
    top_k: int = typer.Option(5, help="Number of results to print."),
    player: list[int] | None = typer.Option(None, "--player", help="Filter to chunks mentioning these player_ids."),
    source: str | None = typer.Option(None, help="Filter by source (e.g., 'r/nba')."),
) -> None:
    """Run one retrieval. Strategy is bm25, dense, or hybrid (default)."""
    _configure_logging()
    filters = ChunkFilters(player_ids=player, source=source)
    if strategy == "bm25":
        chunks = search_bm25(query, filters=filters, top_k=top_k)
        _print_chunks("BM25", query, chunks)
    elif strategy == "dense":
        chunks = search_dense(query, filters=filters, top_k=top_k)
        _print_chunks("Dense", query, chunks)
    elif strategy == "hybrid":
        result = hybrid_search(query, filters=filters, top_k=top_k)
        _print_chunks(
            f"Hybrid (bm25={result.bm25_count}, dense={result.dense_count}, "
            f"merged={result.merged_count})",
            query,
            result.chunks,
        )
    else:
        console.print(f"[red]unknown strategy {strategy!r}; use bm25 | dense | hybrid[/]")
        raise typer.Exit(code=1)


@app.command()
def compare(
    query: str = typer.Argument(..., help="The retrieval query."),
    top_k: int = typer.Option(5, help="Results per strategy."),
    player: list[int] | None = typer.Option(None, "--player"),
) -> None:
    """Side-by-side: BM25 vs Dense vs Hybrid+Rerank."""
    _configure_logging()
    filters = ChunkFilters(player_ids=player)

    embedder = Embedder()
    reranker = Reranker()
    try:
        bm25 = search_bm25(query, filters=filters, top_k=top_k)
        dense = search_dense(query, filters=filters, top_k=top_k, embedder=embedder)
        hybrid = hybrid_search(
            query, filters=filters, top_k=top_k,
            embedder=embedder, reranker=reranker,
        )
    finally:
        embedder.close()
        reranker.close()

    _print_chunks("BM25", query, bm25)
    _print_chunks("Dense", query, dense)
    _print_chunks(
        f"Hybrid+Rerank (bm25={hybrid.bm25_count}, dense={hybrid.dense_count}, "
        f"merged={hybrid.merged_count})",
        query,
        hybrid.chunks,
    )


def _print_chunks(label: str, query: str, chunks: list) -> None:
    console.print(f"\n[bold cyan]{label}[/]  query={query!r}")
    if not chunks:
        console.print("  [yellow](no results)[/]")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("Score", justify="right")
    table.add_column("Date", justify="right")
    table.add_column("Source")
    table.add_column("Snippet", overflow="fold")
    for c in chunks:
        snippet = c.text[:180].replace("\n", " ")
        table.add_row(
            f"{c.score:.4f}",
            str(c.date) if c.date else "?",
            c.source,
            snippet,
        )
    console.print(table)


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main() or 0)
