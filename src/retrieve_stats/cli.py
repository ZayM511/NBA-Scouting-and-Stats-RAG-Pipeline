"""CLI for the stats path.

Usage:
    uv run python -m src.retrieve_stats.cli "Who leads the NBA in three-pointers made?"
    uv run python -m src.retrieve_stats.cli "Wemby's playoff blocks per game"
"""

from __future__ import annotations

import logging
import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config import get_settings
from src.retrieve_stats.pipeline import retrieve_stats

console = Console()
app = typer.Typer(help="Stats retrieval: SQL generation, safety review, execution.")


def _configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@app.command(name="query")
def query_cmd(question: str = typer.Argument(..., help="The NBA stats question.")) -> None:
    """Run one stats query end-to-end."""
    _configure_logging()
    result = retrieve_stats(question)

    if result.generated:
        console.print(
            Panel(
                f"{result.generated.sql}\n\nparams={result.generated.params}\n\n"
                f"[dim]{result.generated.explanation}[/]",
                title=f"Generated SQL (cost=${result.generated.cost_usd:.6f})",
                border_style="cyan",
            )
        )

    if result.safety:
        if result.safety.approved:
            console.print("[green]SAFETY: approved[/]")
        else:
            console.print(
                Panel(
                    "\n".join(f"- {r}" for r in result.safety.reasons),
                    title="SAFETY rejected",
                    border_style="red",
                )
            )

    if result.status == "ok" and result.execution:
        exec_ = result.execution
        table = Table(title=f"Rows ({exec_.row_count} returned in {exec_.elapsed_ms:.1f}ms)")
        for col in exec_.column_names:
            table.add_column(col)
        for row in exec_.rows[:50]:
            table.add_row(*[str(row.get(c, "")) for c in exec_.column_names])
        console.print(table)
        if exec_.truncated:
            console.print("[yellow]results truncated[/]")
    elif result.status != "ok":
        console.print(f"[red]{result.status}:[/] {result.error}")


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main() or 0)
