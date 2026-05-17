"""CLI for the end-to-end ask pipeline.

Usage:
    uv run python -m src.synthesize.cli ask "How is Wemby's defense rated?"
    uv run python -m src.synthesize.cli ask "Cooper Flagg rookie year" --top-k 5
    uv run python -m src.synthesize.cli ask "..." --player 1641705   # filter chunks by player
"""

from __future__ import annotations

import logging
import sys

import typer
from rich.console import Console
from rich.panel import Panel

from src.config import get_settings
from src.retrieve_prose.filters import ChunkFilters
from src.synthesize.pipeline import ask

console = Console()
app = typer.Typer(help="End-to-end ask: route → retrieve → synthesize.")


def _configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@app.command(name="ask")
def ask_cmd(
    question: str = typer.Argument(..., help="The user's NBA question."),
    top_k: int = typer.Option(8, help="Chunks to send to the synthesizer."),
    player: list[int] | None = typer.Option(None, "--player", help="Filter chunks to these player_ids."),
    source: str | None = typer.Option(None, help="Filter chunks by source (e.g., 'r/nba')."),
) -> None:
    """Ask the system one question. Prints route, citations, and the answer."""
    _configure_logging()
    filters = ChunkFilters(player_ids=player, source=source)
    result = ask(question, filters=filters, top_k=top_k)

    # Route panel — the visible tool-use sidebar's "ROUTE" badge equivalent.
    console.print(
        Panel(
            f"[bold]{result.route.route.upper()}[/]\n[dim]{result.route.reasoning}[/]",
            title="Router",
            border_style="cyan",
        )
    )

    if result.not_yet_implemented:
        console.print(f"\n[yellow]{result.notes}[/]")
        console.print(f"\n[bold]{result.answer}[/]")
        return

    if result.retrieval is None or not result.retrieval.chunks:
        console.print("\n[yellow]No chunks retrieved.[/]")
        if result.retrieval is not None:
            console.print(
                f"  bm25={result.retrieval.bm25_count} "
                f"dense={result.retrieval.dense_count} "
                f"merged={result.retrieval.merged_count}"
            )
        return

    # Retrieval panel — the sidebar's "CHUNKS" list.
    chunk_lines = []
    for i, ch in enumerate(result.retrieval.chunks, start=1):
        snippet = ch.text[:120].replace("\n", " ")
        chunk_lines.append(
            f"[bold]#{i}[/] [dim]score={ch.score:.3f} src={ch.source} date={ch.date}[/]\n  {snippet}..."
        )
    console.print(
        Panel(
            "\n".join(chunk_lines),
            title=(
                f"Retrieved chunks (bm25={result.retrieval.bm25_count} "
                f"dense={result.retrieval.dense_count} "
                f"merged={result.retrieval.merged_count} → top {len(result.retrieval.chunks)})"
            ),
            border_style="magenta",
        )
    )

    # Answer panel — the main chat area.
    if result.synthesis is not None:
        body = result.synthesis.answer
        footer = (
            f"\n\n[dim]model={result.synthesis.model} "
            f"in={result.synthesis.input_tokens} "
            f"out={result.synthesis.output_tokens} "
            f"cost=${result.synthesis.cost_usd:.6f} "
            f"declined={result.synthesis.declined}[/]"
        )
        console.print(
            Panel(
                body + footer,
                title=f"Answer ({len(result.synthesis.cited_chunk_ids)} cited chunks)",
                border_style="green",
            )
        )


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main() or 0)
