"""Eval CLI.

Usage:
    uv run python -m src.eval.cli run --tag baseline
    uv run python -m src.eval.cli run --route prose --tag prose-only
    uv run python -m src.eval.cli list
"""

from __future__ import annotations

import logging
import sys

import typer
from rich.console import Console
from rich.table import Table

from src.config import get_settings
from src.eval.cases import ALL_CASES, cases_by_route
from src.eval.runner import run_eval

console = Console()
app = typer.Typer(help="Run the project's eval suite.")


def _configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@app.command(name="run")
def run_cmd(
    tag: str = typer.Option("baseline", help="Experiment tag (used as the Braintrust experiment name)."),
    route: str | None = typer.Option(None, help="Only run cases for one route: stats / prose / hybrid."),
    no_braintrust: bool = typer.Option(False, help="Skip Braintrust streaming even if the SDK is installed."),
) -> None:
    """Run the eval set and print the aggregate report."""
    _configure_logging()
    if route is not None and route not in ("stats", "prose", "hybrid"):
        console.print(f"[red]unknown route: {route!r}[/]")
        raise typer.Exit(code=1)

    cases = cases_by_route(route) if route else ALL_CASES  # type: ignore[arg-type]
    console.print(f"[cyan]Running {len(cases)} cases (tag={tag!r})...[/]\n")
    report = run_eval(tag=tag, cases=cases, write_braintrust=not no_braintrust)

    _print_summary(report)


@app.command(name="list")
def list_cmd() -> None:
    """List all eval cases."""
    _configure_logging()
    table = Table(title=f"Eval cases ({len(ALL_CASES)})")
    table.add_column("ID")
    table.add_column("Route")
    table.add_column("Diff.")
    table.add_column("Question", overflow="fold")
    for c in ALL_CASES:
        table.add_row(
            c.id,
            c.expected_route,
            c.difficulty,
            c.question,
        )
    console.print(table)


def _print_summary(report) -> None:  # type: ignore[no-untyped-def]
    table = Table(title=f"Eval results ({report.tag})")
    table.add_column("Case", overflow="fold")
    table.add_column("Route", justify="center")
    table.add_column("Actual", justify="center")
    table.add_column("Agg.", justify="right")
    table.add_column("RouteAcc", justify="right")
    table.add_column("KW", justify="right")
    table.add_column("HallGuard", justify="right")
    table.add_column("Judge", justify="right")
    table.add_column("Cost", justify="right")
    table.add_column("ms", justify="right")

    for r in report.runs:
        marker = "[red]err[/]" if r.error else ""
        scores = r.scores
        table.add_row(
            r.case_id,
            r.expected_route,
            f"{marker}{r.actual_route}",
            f"{scores.get('aggregate', 0.0):.2f}",
            f"{scores.get('route_accuracy', 0.0):.2f}",
            f"{scores.get('keyword_recall', 0.0):.2f}",
            f"{scores.get('hallucination_guard', 0.0):.2f}",
            f"{scores.get('judge_score', 0.0):.2f}",
            f"${r.cost_usd:.4f}",
            f"{r.elapsed_ms:.0f}",
        )
    console.print(table)

    agg = report.aggregate("aggregate")
    route_acc = report.aggregate("route_accuracy")
    kw = report.aggregate("keyword_recall")
    hall = report.aggregate("hallucination_guard")
    judge = report.aggregate("judge_score")
    console.print(
        f"\n[bold]Aggregate (n={report.n}): "
        f"agg={agg:.3f} route_acc={route_acc:.3f} kw_recall={kw:.3f} "
        f"hall_guard={hall:.3f} judge={judge:.3f}[/]"
    )

    by_route_agg = report.aggregate_by_route("aggregate")
    by_route_acc = report.aggregate_by_route("route_accuracy")
    by_route_judge = report.aggregate_by_route("judge_score")
    console.print("[bold]Per-route averages:[/]")
    for r in ("stats", "prose", "hybrid"):
        console.print(
            f"  {r}: agg={by_route_agg.get(r, 0.0):.3f} "
            f"route_acc={by_route_acc.get(r, 0.0):.3f} "
            f"judge={by_route_judge.get(r, 0.0):.3f}"
        )
    console.print(f"\n[dim]Total cost: ${report.total_cost():.4f}[/]")


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main() or 0)
