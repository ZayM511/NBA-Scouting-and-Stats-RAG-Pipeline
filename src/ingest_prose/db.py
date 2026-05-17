"""Database helpers for prose ingestion. Idempotent UPSERTs for articles
and their chunks, plus an audit log row per ingest.

Articles and chunks have a 1-to-N parent-child relationship with
ON DELETE CASCADE. When an article's content changes (content_sha256
differs from what was stored), we delete the old chunks and re-insert.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg.types.json import Json  # noqa: F401  (re-exported for callers if needed)

from src.config import get_settings

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Connection
# --------------------------------------------------------------------------- #


@contextmanager
def connect():  # type: ignore[no-untyped-def]
    """Yield a psycopg connection with pgvector type registered."""
    settings = get_settings()
    with psycopg.connect(str(settings.postgres_url), row_factory=dict_row) as conn:
        register_vector(conn)
        yield conn


def sha256_hex(text: str) -> str:
    """Return the lowercase hex sha256 of `text` (UTF-8 encoded)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Articles
# --------------------------------------------------------------------------- #


def upsert_article(
    conn: psycopg.Connection,
    *,
    url: str,
    source: str,
    title: str | None,
    article_type: str,
    article_date,  # date | None
    raw_text: str,
) -> tuple[str, bool]:
    """Insert or update an article row. Returns (article_id, content_changed).

    `content_changed` is True if either the row is new OR the stored
    content_sha256 differed from the new one. Callers use this to decide
    whether to re-chunk and re-embed.
    """
    article_id = sha256_hex(url)
    content_sha = sha256_hex(raw_text or "")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT content_sha256 FROM articles WHERE article_id = %s",
            (article_id,),
        )
        row = cur.fetchone()
        existing_sha = row["content_sha256"] if row else None

        if existing_sha == content_sha:
            # Already ingested at this exact content; nothing to do.
            return article_id, False

        cur.execute(
            """
            INSERT INTO articles
                (article_id, url, title, source, article_type, date,
                 content_sha256, raw_text)
            VALUES
                (%(article_id)s, %(url)s, %(title)s, %(source)s, %(article_type)s,
                 %(date)s, %(content_sha256)s, %(raw_text)s)
            ON CONFLICT (article_id) DO UPDATE SET
                title          = EXCLUDED.title,
                source         = EXCLUDED.source,
                article_type   = EXCLUDED.article_type,
                date           = EXCLUDED.date,
                content_sha256 = EXCLUDED.content_sha256,
                raw_text       = EXCLUDED.raw_text,
                updated_at     = NOW()
            """,
            {
                "article_id": article_id,
                "url": url,
                "title": title,
                "source": source,
                "article_type": article_type,
                "date": article_date,
                "content_sha256": content_sha,
                "raw_text": raw_text,
            },
        )
    conn.commit()
    return article_id, True


# --------------------------------------------------------------------------- #
# Chunks
# --------------------------------------------------------------------------- #


def delete_chunks_for_article(conn: psycopg.Connection, article_id: str) -> int:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM articles_chunks WHERE article_id = %s", (article_id,))
        deleted = cur.rowcount
    conn.commit()
    return deleted


def insert_chunks(conn: psycopg.Connection, rows: Sequence[dict[str, Any]]) -> int:
    """Bulk-insert chunks. Each row must have:
    article_id, chunk_index, text, text_with_context, player_ids (list[int]),
    team, date, source, article_type, content_sha256, embedding (list[float]).
    """
    if not rows:
        return 0
    sql = """
        INSERT INTO articles_chunks
            (article_id, chunk_index, text, text_with_context, player_ids,
             team, date, source, article_type, content_sha256, embedding)
        VALUES
            (%(article_id)s, %(chunk_index)s, %(text)s, %(text_with_context)s,
             %(player_ids)s, %(team)s, %(date)s, %(source)s, %(article_type)s,
             %(content_sha256)s, %(embedding)s)
        ON CONFLICT (article_id, chunk_index) DO NOTHING
    """
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    conn.commit()
    return len(rows)


# --------------------------------------------------------------------------- #
# Player-name lookups (used by the contextual-prefix builder)
# --------------------------------------------------------------------------- #


def lookup_player_names(conn: psycopg.Connection, player_ids: Sequence[int]) -> dict[int, str]:
    """Map each player_id to its canonical full name."""
    if not player_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            "SELECT player_id, name FROM players WHERE player_id = ANY(%s)",
            (list(player_ids),),
        )
        return {r["player_id"]: r["name"] for r in cur.fetchall()}


# --------------------------------------------------------------------------- #
# Audit log
# --------------------------------------------------------------------------- #


def write_audit(
    conn: psycopg.Connection,
    *,
    source: str,
    url: str | None,
    content_sha256: str | None,
    chunk_count: int | None,
    status: str,
    error: str | None = None,
) -> None:
    """Append a row to ingest_audit. Never fails the caller."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingest_audit
                    (source, url, content_sha256, chunk_count, status, error)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (source, url, content_sha256, chunk_count, status, error),
            )
        conn.commit()
    except Exception:
        logger.exception("failed to write ingest_audit row; continuing")
