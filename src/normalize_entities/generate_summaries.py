"""Generate Opus-authored scouting summaries for the top-30 players.

For each is_top30 player:
  1. Pull their 2025-26 stat line (PPG, RPG, APG, TS%, plus-minus, games)
     from player_game_stats.
  2. Pull up to 8 existing chunks mentioning the player from articles_chunks
     (the model uses these as evidence for what's already in the corpus).
  3. Ask Claude Opus 4.7 to write a 500-word scouting summary covering
     strengths, weaknesses, playoff context, and notable trends.
  4. Insert one row into `articles` (article_type='authored_summary') and
     one row into `articles_chunks` (also tagged authored_summary). The
     chunk's text gets the contextual-retrieval prefix and a fresh Voyage
     embedding so it participates in retrieval like any other chunk.

Idempotent: re-running skips players that already have an authored summary.
Use `--force` to regenerate (helpful after the player profile changes,
e.g., mid-season trade).

Cost: roughly $0.10 per player at the Opus list price (~2K input + 700
output tokens), so about $3 to do all 30. The hourly cost circuit
breaker covers any runaway cases.
"""

from __future__ import annotations

import hashlib
import logging
import sys
from dataclasses import dataclass
from datetime import date

import anthropic
import psycopg
import typer
from psycopg.rows import dict_row
from rich.console import Console
from rich.progress import Progress

from src.config import get_settings
from src.guardrails import Model, guarded_call, record_usage
from src.ingest_prose.contextual_prefix import build_prefix
from src.ingest_prose.db import (
    connect,
    delete_chunks_for_article,
    insert_chunks,
    sha256_hex,
)
from src.ingest_prose.embedder import Embedder

logger = logging.getLogger(__name__)
console = Console()
app = typer.Typer(help="Top-30 enrichment: Opus-authored scouting summaries.")


SUMMARY_SYSTEM_PROMPT = """\
You are writing one authored scouting summary for a single NBA player, to
be retrieved by a RAG system that already indexes news, scouting writeups,
and Reddit threads. Your summary is the canonical "scouting writeup" the
system has for this player — it's what surfaces when a user asks "tell me
about X" or "how do scouts grade X."

Constraints:

1. Target 450-550 words. Tight is better than long.

2. Cover, in this order: a one-sentence "verdict" headline; offensive
   strengths; defensive strengths; weaknesses or limitations; the player's
   role in the 2025-26 season specifically (their team's success, any
   injury limits, playoff performance if applicable); notable trends from
   the corpus evidence below.

3. Quote at most one stat per paragraph. Use the stat line provided
   below — do not invent numbers. If you cite a number, the stat line
   must back it.

4. Use the corpus evidence as a fact-check, not as a citation source.
   This is YOUR analysis, not a synthesis. Don't add inline [^N]
   citations — the chunk's metadata already names this as an
   authored summary.

5. Plain prose, no bullet lists. No section headers. One paragraph per
   topic from the list above.

6. Voice: confident, specific, slightly opinionated. Like a good
   Athletic scouting blurb. Avoid AI hedging phrases ("it should be
   noted that", "while it's important to consider"). Just say it.

7. If the corpus evidence contradicts the stat line, trust the stat
   line and ignore the corpus on that point.
"""


@dataclass(frozen=True)
class TopPlayer:
    player_id: int
    name: str
    team: str | None
    position: str | None
    ppg: float | None
    rpg: float | None
    apg: float | None
    spg: float | None
    bpg: float | None
    ts_pct: float | None
    plus_minus_per_game: float | None
    games: int
    games_playoff: int


# --------------------------------------------------------------------------- #
# DB helpers
# --------------------------------------------------------------------------- #


def fetch_top30_with_stats(conn: psycopg.Connection) -> list[TopPlayer]:
    """Pull each top-30 player's season-level stat line."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
              p.player_id, p.name, p.team, p.position,
              COUNT(*) AS games,
              COUNT(*) FILTER (WHERE g.is_playoff) AS games_playoff,
              ROUND(AVG(pgs.pts)::numeric, 2)::float        AS ppg,
              ROUND(AVG(pgs.reb)::numeric, 2)::float        AS rpg,
              ROUND(AVG(pgs.ast)::numeric, 2)::float        AS apg,
              ROUND(AVG(pgs.stl)::numeric, 2)::float        AS spg,
              ROUND(AVG(pgs.blk)::numeric, 2)::float        AS bpg,
              ROUND(AVG(pgs.ts_pct)::numeric, 3)::float     AS ts_pct,
              ROUND(AVG(pgs.plus_minus)::numeric, 2)::float AS plus_minus_per_game
            FROM players p
            LEFT JOIN player_game_stats pgs
              ON pgs.player_id = p.player_id
             AND NOT pgs.is_clutch_data
            LEFT JOIN games g ON g.game_id = pgs.game_id
            WHERE p.is_top30 = TRUE
            GROUP BY p.player_id, p.name, p.team, p.position
            ORDER BY p.name
        """)
        rows = cur.fetchall()
    return [TopPlayer(**r) for r in rows]


def fetch_corpus_evidence(conn: psycopg.Connection, player_id: int, limit: int = 8) -> list[dict]:
    """Pull up to `limit` chunks mentioning this player, most recent first.
    Filters out other authored summaries (avoid feedback loops on re-run).
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, text, source, date, article_type
            FROM articles_chunks
            WHERE player_ids && ARRAY[%s]::INT[]
              AND article_type != 'authored_summary'
            ORDER BY date DESC NULLS LAST, id DESC
            LIMIT %s
        """, (player_id, limit))
        return list(cur.fetchall())


def players_with_existing_summary(conn: psycopg.Connection) -> set[int]:
    """Return the set of player_ids that already have an authored summary."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT pid
            FROM articles_chunks ac
            JOIN unnest(ac.player_ids) pid ON TRUE
            WHERE ac.article_type = 'authored_summary'
        """)
        return {int(r["pid"]) for r in cur.fetchall()}


# --------------------------------------------------------------------------- #
# Prompt building
# --------------------------------------------------------------------------- #


def build_user_message(player: TopPlayer, evidence: list[dict]) -> str:
    """Format the question + stat line + evidence chunks for the model."""
    parts = [
        f"PLAYER: {player.name}",
        f"Team: {player.team or '?'} | Position: {player.position or '?'}",
        "",
        "2025-26 STAT LINE (regular season + playoffs combined):",
        f"  Games played: {player.games} (playoff games: {player.games_playoff})",
        f"  Per game: PPG={player.ppg} RPG={player.rpg} APG={player.apg} "
        f"SPG={player.spg} BPG={player.bpg}",
        f"  True shooting: {player.ts_pct}",
        f"  Plus/minus per game: {player.plus_minus_per_game}",
        "",
        f"CORPUS EVIDENCE (up to {len(evidence)} chunks mentioning the player):",
    ]
    if not evidence:
        parts.append("(no corpus chunks yet for this player)")
    else:
        for i, ch in enumerate(evidence, start=1):
            date_str = ch["date"].isoformat() if ch["date"] else "?"
            parts.append(f"\n[{i}] source={ch['source']} date={date_str} type={ch['article_type']}")
            parts.append(ch["text"].strip())
    parts.append("\n\nWrite the 450-550 word scouting summary now. Plain prose, no headers.")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Generate + store
# --------------------------------------------------------------------------- #


def generate_summary(
    client: anthropic.Anthropic,
    player: TopPlayer,
    evidence: list[dict],
    *,
    model: Model = Model.OPUS,
    max_output_tokens: int = 1024,
    session_id: str = "ingest-summaries",
) -> tuple[str, int, int, float]:
    """Single Opus call. Returns (summary_text, in_tokens, out_tokens, cost)."""
    user_message = build_user_message(player, evidence)

    with guarded_call(
        session_id=session_id,
        model=model,
        input_text=SUMMARY_SYSTEM_PROMPT + "\n\n" + user_message,
        max_output_tokens=max_output_tokens,
    ):
        response = client.messages.create(
            model=model.value,
            max_tokens=max_output_tokens,
            system=SUMMARY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

    text = "".join(
        getattr(b, "text", "") for b in (response.content or []) if getattr(b, "type", None) == "text"
    ).strip()

    in_tokens = response.usage.input_tokens
    out_tokens = response.usage.output_tokens
    rec = record_usage(
        session_id=session_id,
        model=model,
        input_tokens=in_tokens,
        output_tokens=out_tokens,
    )
    return text, in_tokens, out_tokens, rec.cost_usd


def store_summary(
    conn: psycopg.Connection,
    player: TopPlayer,
    summary_text: str,
    *,
    embedder: Embedder,
) -> str:
    """Insert (or replace) the authored summary for `player`.

    Returns the article_id. Idempotent: if the same player already has a
    summary, the old article + chunks are deleted and the new one inserted.
    """
    # Article id is deterministic per player so re-runs replace cleanly.
    pseudo_url = f"authored://summary/{player.player_id}"
    article_id = sha256_hex(pseudo_url)
    today = date.today()
    content_sha = sha256_hex(summary_text)

    with conn.cursor() as cur:
        # Wipe any previous summary article + cascade-delete its chunks.
        cur.execute("DELETE FROM articles WHERE article_id = %s", (article_id,))
        cur.execute(
            """
            INSERT INTO articles
                (article_id, url, title, source, article_type, date,
                 content_sha256, raw_text)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                article_id,
                pseudo_url,
                f"Scouting summary: {player.name}",
                "authored_summary",
                "authored_summary",
                today,
                content_sha,
                summary_text,
            ),
        )

    # Build the contextual-retrieval prefix for the chunk.
    text_with_context = build_prefix(
        source="authored_summary",
        article_date=today,
        player_names=[player.name],
        chunk_text=summary_text,
    )

    # Embed the prefixed text.
    embedded = embedder.embed_documents([text_with_context])
    if not embedded.vectors:
        raise RuntimeError("embedder returned no vector")

    insert_chunks(conn, [{
        "article_id": article_id,
        "chunk_index": 0,
        "text": summary_text,
        "text_with_context": text_with_context,
        "player_ids": [player.player_id],
        "team": player.team,
        "date": today,
        "source": "authored_summary",
        "article_type": "authored_summary",
        "content_sha256": content_sha,
        "embedding": embedded.vectors[0],
    }])
    return article_id


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@app.command(name="generate")
def generate_cmd(
    limit: int | None = typer.Option(None, help="Stop after N players."),
    force: bool = typer.Option(False, help="Regenerate even for players who already have a summary."),
    max_cost_usd: float = typer.Option(5.0, help="Hard ceiling on total cost; stops if exceeded."),
) -> None:
    """Generate authored summaries for the top-30 players (idempotent)."""
    _configure_logging()
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
    embedder = Embedder()
    total_cost = 0.0
    done = 0
    skipped = 0

    with connect() as conn:
        players = fetch_top30_with_stats(conn)
        existing = set() if force else players_with_existing_summary(conn)

    to_process = [p for p in players if p.player_id not in existing]
    if limit is not None:
        to_process = to_process[:limit]

    console.print(
        f"[cyan]Top-30 enrichment: {len(to_process)} to generate "
        f"({len(players) - len(to_process)} already have summaries; "
        f"cap ${max_cost_usd}).[/]"
    )

    with Progress(console=console) as progress:
        task = progress.add_task("summaries", total=len(to_process))
        for player in to_process:
            if total_cost > max_cost_usd:
                console.print(f"[red]cost cap ${max_cost_usd} hit at ${total_cost:.4f}; stopping[/]")
                break
            try:
                with connect() as conn:
                    evidence = fetch_corpus_evidence(conn, player.player_id, limit=8)
                # Per-player session_id so the per-session cost ceiling doesn't
                # trip mid-run (this is a one-time ingest path, not a user
                # query). The hourly circuit breaker still applies.
                per_player_session = f"ingest-summaries-{player.player_id}"
                summary, in_tok, out_tok, cost = generate_summary(
                    client, player, evidence, session_id=per_player_session
                )
                with connect() as conn:
                    store_summary(conn, player, summary, embedder=embedder)
                total_cost += cost
                done += 1
                # ASCII-only console print to avoid cp1252 crashes on Windows
                # when player names contain diacritics (Doncic, Jokic, etc.).
                safe_name = player.name.encode("ascii", "replace").decode("ascii")
                console.print(
                    f"  [green]ok[/]  {safe_name:<28} {len(summary)} chars  "
                    f"in={in_tok} out={out_tok}  ${cost:.4f}  (running ${total_cost:.4f})"
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("failed to generate summary for %s", player.name)
                console.print(f"  [red]ERR[/] {player.name}: {exc}")
            finally:
                progress.update(task, advance=1)

    embedder.close()
    console.print(
        f"\n[bold]Done.[/] {done} summaries generated, {skipped} skipped. "
        f"Total cost: ${total_cost:.4f}"
    )


@app.command(name="status")
def status_cmd() -> None:
    """How many top-30 players have an authored summary?"""
    _configure_logging()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                  (SELECT COUNT(*) FROM players WHERE is_top30) AS total_top30,
                  (SELECT COUNT(DISTINCT pid)
                     FROM articles_chunks ac
                     JOIN unnest(ac.player_ids) pid ON TRUE
                     WHERE ac.article_type = 'authored_summary'
                       AND pid IN (SELECT player_id FROM players WHERE is_top30)
                  ) AS with_summary
            """)
            row = cur.fetchone()
    console.print(
        f"[cyan]Top-30 with authored summaries: "
        f"{row['with_summary']} / {row['total_top30']}[/]"
    )


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main() or 0)
