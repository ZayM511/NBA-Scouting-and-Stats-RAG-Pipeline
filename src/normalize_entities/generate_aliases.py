"""Generate the player_aliases table via Claude Sonnet 4.6.

Each active player gets:

  1. The canonical full name (no LLM call, source='canonical').
  2. Every nickname and short form the LLM recognizes (source='llm').

The LLM is the right tool here because it knows which short-name forms
are unambiguous in popular NBA discourse: "Steph" → Curry (not Seth),
"LeBron" → LeBron James, "KD" → Kevin Durant. It also knows the local /
broadcast / r/nba nicknames ("the Joker", "the Chef", "King James") that
a static rule wouldn't catch.

Process order matters because `alias` is the primary key on
`player_aliases`. We process top-30 players first so the famous owner of
an ambiguous alias (e.g., "Curry") wins the row before any same-named
fringe player can claim it.

Cost: about $1.50 to process all 587 active players. The session-cost
guardrail is bypassed here because this is a one-time ingest, not a
user query. The hourly circuit breaker still applies via `record_usage`.

Usage:
    uv run python -m src.normalize_entities.generate_aliases sync          # all players, skip those already done
    uv run python -m src.normalize_entities.generate_aliases sync --limit 30  # smoke test on top 30 first
    uv run python -m src.normalize_entities.generate_aliases sync --force   # re-process even players with existing rows
    uv run python -m src.normalize_entities.generate_aliases status         # row counts per source
    uv run python -m src.normalize_entities.generate_aliases lookup --query "the chef"  # who does this alias resolve to?
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import anthropic
import psycopg
import typer
from psycopg.rows import dict_row
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn

from src.config import get_settings
from src.guardrails import Model, estimate_cost, record_usage

logger = logging.getLogger(__name__)
console = Console()
app = typer.Typer(help="Generate the player alias map via Claude.")

# ----------------------------------------------------------------------------
# LLM prompt
# ----------------------------------------------------------------------------

# The model picks which short forms are unambiguous; we don't auto-add last
# names because of collisions (Curry, Williams, Thompson, etc.).
PROMPT_TEMPLATE = """\
Player: {name}, position {position}, team {team}, drafted {draft_year}.

List every name and nickname this player is commonly called in NBA
broadcasts, sports media, and r/nba discussion.

EXAMPLES (do not output these; they are reference only):

- For Stephen Curry: ["Steph", "Curry", "Steph Curry", "the Chef", "Chef Curry", "Wardell"]
- For LeBron James: ["LeBron", "James", "King James", "the King", "Bron", "Bron Bron", "LBJ"]
- For Nikola Jokic: ["Jokic", "the Joker", "Joker", "Big Honey", "Nikola"]
- For Karl-Anthony Towns: ["KAT", "Towns", "Karl Towns", "Karl-Anthony Towns"]
- For Tim Hardaway Jr.: ["Tim Hardaway Jr", "Hardaway Jr", "THJ"]   (NOT just "Hardaway" because the dad shares it)
- For a fringe rookie: ["Full Name", "LastName"]                     (short list is fine)

RULES:

- Only include forms a regular NBA fan would actually use.
- Include single-name forms (last name only, first name only, nickname)
  only when they UNAMBIGUOUSLY resolve to THIS player among active NBA
  players. If "Curry" could mean Seth too, only include it for Stephen.
- Do not invent nicknames. If you are not certain a nickname is widely
  used, leave it out.
- Do not include trash-talk or insults. Public, widely-used forms only.
- Typical range is 4-12 entries. Rookies and role players get fewer.

Output: a JSON array of strings. No commentary, no markdown, no code fences.
Example output: ["Steph", "Curry", "the Chef"]
"""


# ----------------------------------------------------------------------------
# Normalization
# ----------------------------------------------------------------------------

_PUNCT_RE = re.compile(r"[^\w\s'\-]", flags=re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize_alias(alias: str) -> str:
    """Lowercase, NFKD strip diacritics, strip punctuation except '-'/'\\''.

    Apostrophes and hyphens are kept because they appear in real names
    (Karl-Anthony Towns, Shai Gilgeous-Alexander, D'Angelo Russell).
    """
    if not alias:
        return ""
    s = unicodedata.normalize("NFKD", alias)
    s = "".join(c for c in s if not unicodedata.combining(c))  # strip diacritics
    s = s.lower().strip()
    s = _PUNCT_RE.sub(" ", s)  # punct (other than ' and -) → space
    s = _WS_RE.sub(" ", s).strip()
    return s


# ----------------------------------------------------------------------------
# JSON-array parsing (robust to model wrapping in ```json ... ```)
# ----------------------------------------------------------------------------

_JSON_ARRAY_RE = re.compile(r"\[[^\[\]]*\]", flags=re.DOTALL)


def parse_alias_array(text: str) -> list[str]:
    """Pull a JSON array of strings from the model's response.

    Tolerates code fences, leading prose, trailing prose. Returns [] if
    no valid array can be extracted.
    """
    if not text:
        return []
    # Try strict parse first.
    candidate = text.strip()
    # Strip fences if present.
    candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
    candidate = re.sub(r"\s*```$", "", candidate)
    candidate = candidate.strip()
    try:
        data = json.loads(candidate)
        if isinstance(data, list) and all(isinstance(x, str) for x in data):
            return data
    except json.JSONDecodeError:
        pass
    # Fallback: regex-search for the first bracketed array.
    match = _JSON_ARRAY_RE.search(text)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, list) and all(isinstance(x, str) for x in data):
                return data
        except json.JSONDecodeError:
            pass
    return []


# ----------------------------------------------------------------------------
# DB helpers
# ----------------------------------------------------------------------------


def _connect():
    settings = get_settings()
    return psycopg.connect(str(settings.postgres_url), row_factory=dict_row)


def fetch_players(conn, *, skip_existing: bool, limit: int | None) -> list[dict]:
    """Return active players to process, top-30 first so the famous owner
    of any ambiguous alias claims it first."""
    sql_parts = [
        "SELECT p.player_id, p.name, p.team, p.position, p.draft_year",
        "FROM players p",
    ]
    if skip_existing:
        sql_parts.append(
            "LEFT JOIN (SELECT DISTINCT player_id FROM player_aliases WHERE source='llm') pa "
            "ON pa.player_id = p.player_id"
        )
    sql_parts.append("WHERE p.is_active = TRUE")
    if skip_existing:
        sql_parts.append("AND pa.player_id IS NULL")
    sql_parts.append("ORDER BY p.is_top30 DESC, p.player_id")
    if limit is not None:
        sql_parts.append("LIMIT %s")

    sql = "\n".join(sql_parts)
    args: tuple = (limit,) if limit is not None else ()

    with conn.cursor() as cur:
        cur.execute(sql, args)
        return list(cur.fetchall())


def insert_aliases(conn, rows: Iterable[dict]) -> int:
    """Insert alias rows; existing rows (by alias PK) are preserved.

    Ordering of inserts matters: we process top-30 players first, so the
    famous owner wins ambiguous aliases. ON CONFLICT DO NOTHING means a
    later player can't steal an alias the first owner claimed.
    """
    rows = list(rows)
    if not rows:
        return 0
    sql = """
        INSERT INTO player_aliases (alias, player_id, confidence, source)
        VALUES (%(alias)s, %(player_id)s, %(confidence)s, %(source)s)
        ON CONFLICT (alias) DO NOTHING
    """
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    conn.commit()
    return len(rows)


# ----------------------------------------------------------------------------
# Per-player generation
# ----------------------------------------------------------------------------


@dataclass
class AliasGenerationResult:
    player_id: int
    name: str
    aliases_attempted: int
    aliases_inserted: int
    cost_usd: float
    error: str | None = None


def canonical_rows_for(player: dict) -> list[dict]:
    """Always-safe rows: just the player's full canonical name."""
    name_norm = normalize_alias(player["name"])
    if not name_norm:
        return []
    return [{
        "alias": name_norm,
        "player_id": int(player["player_id"]),
        "confidence": 1.0,
        "source": "canonical",
    }]


def call_llm_for_aliases(
    client: anthropic.Anthropic,
    player: dict,
    model: Model = Model.SONNET,
    session_id: str = "ingest-aliases",
) -> tuple[list[str], float]:
    """Single LLM call; returns (list of aliases, cost in USD).

    Records the call against the hourly cost circuit breaker via
    record_usage. Does NOT call guard_request — this is an ingest path,
    not a query path. The session_cost_ceiling check would erroneously
    fire here.
    """
    prompt = PROMPT_TEMPLATE.format(
        name=player["name"],
        position=player.get("position") or "?",
        team=player.get("team") or "?",
        draft_year=player.get("draft_year") or "unknown",
    )
    response = client.messages.create(
        model=model.value,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text if response.content else ""
    aliases = parse_alias_array(text)

    in_tokens = response.usage.input_tokens
    out_tokens = response.usage.output_tokens
    cost = estimate_cost(model, in_tokens, out_tokens)
    record_usage(
        session_id=session_id,
        model=model,
        input_tokens=in_tokens,
        output_tokens=out_tokens,
    )
    return aliases, cost


def process_player(
    conn,
    client: anthropic.Anthropic,
    player: dict,
    model: Model = Model.SONNET,
    session_id: str = "ingest-aliases",
) -> AliasGenerationResult:
    """Generate and insert all aliases for one player."""
    rows = list(canonical_rows_for(player))

    try:
        llm_aliases, cost = call_llm_for_aliases(client, player, model, session_id)
    except Exception as exc:
        logger.exception("LLM call failed for %s (%s)", player["name"], player["player_id"])
        # Still insert the canonical row even if LLM failed.
        inserted = insert_aliases(conn, rows)
        return AliasGenerationResult(
            player_id=int(player["player_id"]),
            name=player["name"],
            aliases_attempted=len(rows),
            aliases_inserted=inserted,
            cost_usd=0.0,
            error=f"{type(exc).__name__}: {exc}",
        )

    for alias in llm_aliases:
        norm = normalize_alias(alias)
        if not norm or len(norm) < 2:
            continue
        rows.append({
            "alias": norm,
            "player_id": int(player["player_id"]),
            "confidence": 0.6,
            "source": "llm",
        })

    inserted = insert_aliases(conn, rows)
    return AliasGenerationResult(
        player_id=int(player["player_id"]),
        name=player["name"],
        aliases_attempted=len(rows),
        aliases_inserted=inserted,
        cost_usd=cost,
    )


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------


def _configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@app.command()
def sync(
    limit: int | None = typer.Option(None, help="Only process the first N players (top-30 first)."),
    force: bool = typer.Option(False, help="Re-process players who already have llm-sourced aliases."),
    max_cost_usd: float = typer.Option(5.0, help="Hard ceiling on total cost; stops if exceeded."),
    dry_run: bool = typer.Option(False, help="Print the player list and projected cost; do not call the LLM."),
    sleep_ms: int = typer.Option(50, help="Sleep between calls. 50ms keeps us well under tier-1 rate limits."),
) -> None:
    """Generate aliases for every active player.

    Idempotent: safe to re-run; existing aliases are preserved.
    Top-30 players are processed first so they claim ambiguous aliases.
    """
    _configure_logging()
    settings = get_settings()

    with _connect() as conn:
        players = fetch_players(conn, skip_existing=not force, limit=limit)

    if not players:
        console.print("[yellow]No players to process. Use --force to re-run.[/]")
        return

    projected = estimate_cost(Model.SONNET, input_tokens=250 * len(players), output_tokens=120 * len(players))
    console.print(
        f"[cyan]Will process {len(players)} players. "
        f"Projected cost: ~${projected:.4f} (cap: ${max_cost_usd:.2f}).[/]"
    )

    if dry_run:
        for p in players[:10]:
            console.print(f"  {p['player_id']:>8} {p['team'] or '?':<3} {p['name']}")
        if len(players) > 10:
            console.print(f"  ... and {len(players) - 10} more")
        return

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key.get_secret_value())

    total_cost = 0.0
    total_attempted = 0
    total_inserted = 0
    errors: list[AliasGenerationResult] = []

    with _connect() as conn:
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("aliases", total=len(players))
            for p in players:
                if total_cost > max_cost_usd:
                    console.print(f"[red]cost cap ${max_cost_usd} hit at ${total_cost:.4f}; stopping[/]")
                    break

                result = process_player(conn, client, p)
                total_cost += result.cost_usd
                total_attempted += result.aliases_attempted
                total_inserted += result.aliases_inserted
                if result.error:
                    errors.append(result)
                progress.update(
                    task,
                    advance=1,
                    description=f"aliases (${total_cost:.4f})",
                )
                if sleep_ms:
                    time.sleep(sleep_ms / 1000)

    console.print(
        f"\n[green]Done.[/] {total_inserted} aliases inserted "
        f"({total_attempted} attempted; difference are PK conflicts). "
        f"Total cost: [bold]${total_cost:.4f}[/]."
    )
    if errors:
        console.print(f"[yellow]{len(errors)} player(s) had errors:[/]")
        for e in errors[:10]:
            console.print(f"  {e.player_id} {e.name}: {e.error}")
        if len(errors) > 10:
            console.print(f"  ... and {len(errors) - 10} more")


@app.command()
def status() -> None:
    """Print alias counts per source and a sample."""
    _configure_logging()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT source, COUNT(*) AS n FROM player_aliases GROUP BY source ORDER BY source"
            )
            counts = cur.fetchall()
            cur.execute("SELECT COUNT(DISTINCT player_id) AS n FROM player_aliases")
            players_covered = cur.fetchone()["n"]
            cur.execute(
                "SELECT pa.alias, p.name FROM player_aliases pa "
                "JOIN players p ON p.player_id = pa.player_id "
                "WHERE p.is_top30 = TRUE ORDER BY p.name, pa.alias LIMIT 30"
            )
            sample = cur.fetchall()

    if not counts:
        console.print("[yellow]No aliases in the DB yet. Run `sync` first.[/]")
        return

    console.print(f"[cyan]Players covered: {players_covered}[/]")
    for c in counts:
        console.print(f"  {c['source']}: {c['n']} aliases")
    console.print("\n[cyan]Sample (top-30 players):[/]")
    for s in sample:
        console.print(f"  {s['alias']:<30} → {s['name']}")


@app.command()
def lookup(query: str = typer.Option(..., help="The alias to resolve.")) -> None:
    """Resolve a single alias string to its player(s)."""
    _configure_logging()
    norm = normalize_alias(query)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pa.alias, pa.confidence, pa.source,
                       p.player_id, p.name, p.team
                FROM player_aliases pa
                JOIN players p ON p.player_id = pa.player_id
                WHERE pa.alias = %s
                """,
                (norm,),
            )
            rows = cur.fetchall()

    if not rows:
        console.print(f"[yellow]No match for[/] '{query}' (normalized: '{norm}')")
        return
    for r in rows:
        console.print(
            f"  '{r['alias']}' → [bold]{r['name']}[/] (id={r['player_id']}, "
            f"team={r['team']}, source={r['source']}, conf={r['confidence']:.2f})"
        )


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main() or 0)
