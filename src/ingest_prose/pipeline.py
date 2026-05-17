"""End-to-end prose ingestion pipeline.

For each `ProseDocument`:

    1. Upsert the article; bail out early if the content hash matches the
       stored row (already ingested, nothing changed).
    2. Resolve player_ids from the full article body (used as a fallback
       when a chunk mentions no player by name).
    3. Chunk the body into ~400-token pieces with 15% overlap.
    4. For each chunk, resolve player_ids from the chunk text. If empty,
       fall back to the article-level player_ids.
    5. Build the contextual-retrieval prefix per chunk (source, date,
       comma-separated player names, then the chunk).
    6. Embed all chunk prefixes in one batched Voyage call.
    7. Delete any previous chunks for this article, insert the new ones.
    8. Write a row to `ingest_audit`.

Idempotency: re-running the pipeline on the same `ProseDocument` is a
no-op when the body is byte-identical. When the body changes, the old
chunks are deleted and the new ones replace them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import psycopg

from src.ingest_prose.chunker import Chunk, chunk_text
from src.ingest_prose.contextual_prefix import build_prefix
from src.ingest_prose.db import (
    delete_chunks_for_article,
    insert_chunks,
    lookup_player_names,
    sha256_hex,
    upsert_article,
    write_audit,
)
from src.ingest_prose.embedder import Embedder
from src.ingest_prose.reddit_source import ProseDocument
from src.normalize_entities.resolve import AliasResolver

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestResult:
    """Outcome of ingesting one document."""

    article_id: str
    url: str
    status: str  # 'ingested' | 'unchanged' | 'empty' | 'error'
    chunks_inserted: int
    embedding_tokens: int
    error: str | None = None


def ingest_document(
    conn: psycopg.Connection,
    doc: ProseDocument,
    *,
    resolver: AliasResolver,
    embedder: Embedder,
    target_tokens: int = 400,
    overlap_ratio: float = 0.15,
) -> IngestResult:
    """Run the full pipeline for one document. Returns a structured result."""
    article_id = sha256_hex(doc.url)
    try:
        article_id, changed = upsert_article(
            conn,
            url=doc.url,
            source=doc.source,
            title=doc.title or None,
            article_type=doc.article_type,
            article_date=doc.date,
            raw_text=doc.body,
        )

        if not changed:
            write_audit(
                conn,
                source=doc.source,
                url=doc.url,
                content_sha256=sha256_hex(doc.body),
                chunk_count=None,
                status="success",
            )
            return IngestResult(
                article_id=article_id,
                url=doc.url,
                status="unchanged",
                chunks_inserted=0,
                embedding_tokens=0,
            )

        # Resolve players from the full body (used as fallback for chunks).
        article_player_ids = sorted(resolver.resolve(doc.body))

        chunks = chunk_text(doc.body, target_tokens=target_tokens, overlap_ratio=overlap_ratio)
        if not chunks:
            write_audit(
                conn,
                source=doc.source,
                url=doc.url,
                content_sha256=sha256_hex(doc.body),
                chunk_count=0,
                status="success",
            )
            return IngestResult(
                article_id=article_id,
                url=doc.url,
                status="empty",
                chunks_inserted=0,
                embedding_tokens=0,
            )

        # Per-chunk player resolution.
        per_chunk_players: list[list[int]] = []
        for ch in chunks:
            chunk_players = sorted(resolver.resolve(ch.text))
            if not chunk_players:
                chunk_players = article_player_ids
            per_chunk_players.append(chunk_players)

        # Bulk name lookup for the contextual prefixes.
        all_player_ids = {pid for plist in per_chunk_players for pid in plist}
        name_map = lookup_player_names(conn, list(all_player_ids))

        prefixed_texts: list[str] = []
        for ch, players in zip(chunks, per_chunk_players, strict=False):
            names = [name_map[pid] for pid in players if pid in name_map]
            prefixed = build_prefix(
                source=doc.source,
                article_date=doc.date,
                player_names=names,
                chunk_text=ch.text,
            )
            prefixed_texts.append(prefixed)

        # One batched embedding call for the whole article.
        embed_result = embedder.embed_documents(prefixed_texts)

        chunk_rows = []
        for ch, players, prefixed, vector in zip(
            chunks, per_chunk_players, prefixed_texts, embed_result.vectors, strict=False
        ):
            chunk_rows.append({
                "article_id": article_id,
                "chunk_index": ch.chunk_index,
                "text": ch.text,
                "text_with_context": prefixed,
                "player_ids": players,
                "team": None,  # team-derivation is a phase-B-stretch
                "date": doc.date,
                "source": doc.source,
                "article_type": doc.article_type,
                "content_sha256": sha256_hex(ch.text),
                "embedding": vector,
            })

        # Replace any existing chunks (in case of content update).
        delete_chunks_for_article(conn, article_id)
        inserted = insert_chunks(conn, chunk_rows)

        write_audit(
            conn,
            source=doc.source,
            url=doc.url,
            content_sha256=sha256_hex(doc.body),
            chunk_count=inserted,
            status="success",
        )

        return IngestResult(
            article_id=article_id,
            url=doc.url,
            status="ingested",
            chunks_inserted=inserted,
            embedding_tokens=embed_result.total_tokens,
        )

    except Exception as exc:
        logger.exception("ingest_document failed for %s", doc.url)
        write_audit(
            conn,
            source=doc.source,
            url=doc.url,
            content_sha256=None,
            chunk_count=None,
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
        )
        return IngestResult(
            article_id=article_id,
            url=doc.url,
            status="error",
            chunks_inserted=0,
            embedding_tokens=0,
            error=str(exc),
        )
