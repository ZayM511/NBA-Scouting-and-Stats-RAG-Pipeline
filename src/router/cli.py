"""Router CLI.

Usage:
    uv run python -m src.router.cli classify "What's Jokic's TS%?"
    uv run python -m src.router.cli smoke         # runs the built-in 18-question smoke set
    uv run python -m src.router.cli batch path/to/questions.txt   # one question per line
"""

from __future__ import annotations

import logging
import sys
from collections import Counter
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from src.config import get_settings
from src.router.classifier import RouterClassifier, RouterError

console = Console()
app = typer.Typer(help="Query router classifier.")


# Smoke set: a mix the classifier should get mostly right out of the box.
# Stratified roughly 1/3 each across the three routes.
SMOKE_SET: list[tuple[str, str]] = [
    # stats
    ("What's Jokic's true shooting in the clutch playoff games?", "stats"),
    ("Who leads the NBA in three-pointers made this season?", "stats"),
    ("How many games has Wemby missed?", "stats"),
    ("Compare Anthony Edwards and SGA's playoff scoring averages.", "stats"),
    ("What was Curry's free-throw percentage last month?", "stats"),
    # prose
    ("How do scouts grade Wemby's defensive instincts?", "prose"),
    ("What is the playoff narrative for the Spurs?", "prose"),
    ("Why has Embiid been frustrated this season?", "prose"),
    ("What did fans say about LeBron's late-game shot last night?", "prose"),
    ("Tell me about Cooper Flagg.", "prose"),
    # hybrid
    ("Which guards shooting above 40% from three are getting praised for off-ball movement?", "hybrid"),
    ("Among the top-30 scorers, who is the most-praised on-ball defender?", "hybrid"),
    ("Find players over 35 with high TS% who are written up as future Hall of Famers.", "hybrid"),
    ("How is Wemby's defense rated, and what are his block totals?", "hybrid"),
]


def _configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@app.command()
def classify(question: str = typer.Argument(..., help="The user's question.")) -> None:
    """Classify a single question. Prints route + reasoning + cost."""
    _configure_logging()
    classifier = RouterClassifier()
    try:
        decision = classifier.classify(question)
    except RouterError as exc:
        console.print(f"[red]router error:[/] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(
        f"[cyan]route[/]     [bold]{decision.route}[/]\n"
        f"[cyan]reasoning[/] {decision.reasoning}\n"
        f"[dim]cost=${decision.cost_usd:.6f} "
        f"in={decision.input_tokens} out={decision.output_tokens}[/]"
    )


@app.command()
def smoke() -> None:
    """Run the built-in 14-question smoke set; prints route accuracy + cost."""
    _configure_logging()
    classifier = RouterClassifier()

    table = Table(title="Router smoke test")
    table.add_column("#", justify="right")
    table.add_column("Expected")
    table.add_column("Got")
    table.add_column("Question")
    table.add_column("Reasoning", overflow="fold")

    by_expected = Counter()
    by_correct = Counter()
    total_cost = 0.0

    for i, (q, expected) in enumerate(SMOKE_SET, start=1):
        try:
            d = classifier.classify(q)
        except RouterError as exc:
            console.print(f"[red]error on {q!r}: {exc}[/]")
            continue
        by_expected[expected] += 1
        match = d.route == expected
        if match:
            by_correct[expected] += 1
        total_cost += d.cost_usd
        marker = "[green]✓[/]" if match else "[red]✗[/]"
        table.add_row(
            str(i),
            expected,
            f"{marker} {d.route}",
            q if len(q) <= 70 else q[:67] + "...",
            d.reasoning,
        )

    console.print(table)

    correct = sum(by_correct.values())
    total = sum(by_expected.values())
    console.print(
        f"\n[bold]Accuracy: {correct}/{total} ({100 * correct / max(total, 1):.0f}%)[/]"
    )
    for route in ("stats", "prose", "hybrid"):
        c, t = by_correct[route], by_expected[route]
        console.print(f"  {route}: {c}/{t}")
    console.print(f"[dim]Total cost: ${total_cost:.6f}[/]")


@app.command()
def batch(path: Path = typer.Argument(..., help="One question per line.")) -> None:
    """Classify a file of questions; one per line."""
    _configure_logging()
    classifier = RouterClassifier()
    counts: Counter[str] = Counter()
    total_cost = 0.0
    for line in path.read_text(encoding="utf-8").splitlines():
        q = line.strip()
        if not q or q.startswith("#"):
            continue
        try:
            d = classifier.classify(q)
        except RouterError as exc:
            console.print(f"[red]error[/] {q[:60]!r}: {exc}")
            continue
        counts[d.route] += 1
        total_cost += d.cost_usd
        console.print(f"{d.route:6s}  {q}")
    console.print(
        f"\n[bold]Totals:[/] stats={counts['stats']} prose={counts['prose']} hybrid={counts['hybrid']} "
        f"cost=${total_cost:.4f}"
    )


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main() or 0)
