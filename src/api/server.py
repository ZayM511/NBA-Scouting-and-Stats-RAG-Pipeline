"""FastAPI server exposing the ask() pipeline for the Next.js UI.

Endpoints:
  GET  /health     liveness + ready check (does the DB respond?)
  POST /ask        run one ask() call. Body: {question, top_k?, player_ids?, source?}
                   Response shape mirrors AskResult with serializable fields.

CORS is open to localhost:3000 by default (the Next.js dev server). For
production deployment behind a single domain, set ALLOWED_ORIGINS in env
or extend `_origins()` to match.

Service instances (Embedder, Reranker, RouterClassifier, Synthesizer,
SQLGenerator) are reused across requests via FastAPI's lifespan context
so HTTP sessions and Anthropic clients stay warm between calls.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.api.header import router as header_router
from src.config import get_settings
from src.ingest_prose.embedder import Embedder
from src.ingest_stats.live import sync_live_scoreboard
from src.ingest_stats.schedule import sync_upcoming_schedule
from src.observability.braintrust_api import init as bt_init, log_ask as bt_log_ask
from src.retrieve_prose.filters import ChunkFilters
from src.retrieve_prose.rerank import Reranker
from src.retrieve_stats.sql_generator import SQLGenerator
from src.router.classifier import RouterClassifier
from src.synthesize.pipeline import AskResult, ask
from src.synthesize.synthesizer import Synthesizer

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Request / response models
# --------------------------------------------------------------------------- #


class AskRequest(BaseModel):
    """Request body for POST /ask."""

    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(8, ge=1, le=20)
    player_ids: list[int] | None = None
    source: str | None = None
    # Per-user session token used by the guardrail cost tracker. The UI mints
    # one UUID per browser session (and rotates it when the user clicks
    # "New chat"), so each UI session gets its own $0.50 ledger instead of
    # everyone sharing one global "api" bucket. Constrained to safe chars
    # so a malicious value can't be used as a log-injection vector.
    session_id: str | None = Field(None, pattern=r"^[A-Za-z0-9_\-]{1,64}$")


class RouteOut(BaseModel):
    route: str
    reasoning: str


class CitationOut(BaseModel):
    citation_index: int
    chunk_id: int


class SynthesisOut(BaseModel):
    answer: str
    citations: list[CitationOut]
    cited_chunk_ids: list[int]
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    declined: bool


class ChunkOut(BaseModel):
    chunk_id: int
    text: str
    source: str
    article_type: str
    date: str | None
    score: float
    player_ids: list[int]


class RetrievalOut(BaseModel):
    bm25_count: int
    dense_count: int
    merged_count: int
    chunks: list[ChunkOut]


class StatsOut(BaseModel):
    status: str
    sql: str | None = None
    params: dict[str, Any] | None = None
    explanation: str | None = None
    rows: list[dict[str, Any]] | None = None
    row_count: int | None = None
    elapsed_ms: float | None = None
    cost_usd: float = 0.0
    error: str | None = None


class HybridFilterOut(BaseModel):
    sql: str
    params: dict[str, Any]
    explanation: str
    player_ids: list[int]
    cost_usd: float
    status: str
    # Phase L.4: the numeric half of a hybrid answer. Surfacing the rows in
    # the UI sidebar so reviewers can see both the stats AND the prose
    # evidence the synthesis layer used.
    rows: list[dict[str, Any]] = []
    column_names: list[str] = []
    row_count: int = 0


class HybridOut(BaseModel):
    status: str
    filter: HybridFilterOut
    retrieval: RetrievalOut | None = None
    notes: str = ""


class AskResponse(BaseModel):
    """Response body for POST /ask. Mirrors AskResult plus a wall-time field."""

    question: str
    route: RouteOut
    answer: str
    synthesis: SynthesisOut | None = None
    retrieval: RetrievalOut | None = None
    stats: StatsOut | None = None
    hybrid: HybridOut | None = None
    not_yet_implemented: bool = False
    notes: str = ""
    elapsed_ms: float


class HealthResponse(BaseModel):
    status: str
    db_ok: bool
    note: str = ""


# --------------------------------------------------------------------------- #
# Lifespan: warm long-lived service instances
# --------------------------------------------------------------------------- #


class Services:
    """Container for the long-lived service instances."""

    def __init__(self) -> None:
        self.classifier = RouterClassifier()
        self.embedder = Embedder()
        self.reranker = Reranker()
        self.synthesizer = Synthesizer()
        self.sql_generator = SQLGenerator()

    def close(self) -> None:
        try:
            self.embedder.close()
        except Exception:
            logger.exception("embedder.close failed")
        try:
            self.reranker.close()
        except Exception:
            logger.exception("reranker.close failed")


_services: Services | None = None
_scheduler: AsyncIOScheduler | None = None


def _get_services() -> Services:
    if _services is None:
        raise RuntimeError("services not initialized; the lifespan didn't run")
    return _services


def _safe_live_tick() -> None:
    """Wrap sync_live_scoreboard so any failure logs but doesn't kill the job."""
    try:
        n = sync_live_scoreboard()
        logger.debug("scheduler live tick: %d games", n)
    except Exception:  # noqa: BLE001
        logger.exception("scheduler live tick raised")


def _safe_schedule_tick() -> None:
    try:
        n = sync_upcoming_schedule()
        logger.info("scheduler schedule tick: upserted %d upcoming games", n)
    except Exception:  # noqa: BLE001
        logger.exception("scheduler schedule tick raised")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize long-lived service instances on startup, close on shutdown.

    Also boots APScheduler with two jobs:
      * live: pulls today's scoreboard every 60 seconds (runs immediately)
      * schedule: pulls the next 14 days of upcoming games at startup,
        then daily at 12:00 UTC
    Both jobs use coalesce=True + max_instances=1 so a slow tick can't
    pile up workers, and both wrap failures so the API stays serving even
    when nba_api / balldontlie are down.
    """
    global _services, _scheduler
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _services = Services()
    # Initialize Braintrust here (not at import time) so unit tests that import
    # the module without an API key don't hit the network.
    bt_init()

    # Surface the active guardrail values on startup so it's obvious whether
    # a .env edit was picked up (Settings is lru_cached for the life of the
    # process — the only way to change these is to restart).
    logger.info(
        "guardrails: session_cost_ceiling_usd=$%.2f, hourly_breaker_usd=$%.2f, "
        "max_input=%d, max_output=%d",
        settings.session_cost_ceiling_usd,
        settings.hourly_cost_circuit_breaker_usd,
        settings.max_input_tokens_per_query,
        settings.max_output_tokens_per_query,
    )

    try:
        _scheduler = AsyncIOScheduler()
        _scheduler.add_job(
            _safe_live_tick,
            trigger=IntervalTrigger(seconds=60),
            id="live_scoreboard",
            coalesce=True,
            max_instances=1,
            next_run_time=datetime.now(timezone.utc),
        )
        _scheduler.add_job(
            _safe_schedule_tick,
            trigger=CronTrigger(hour=12, minute=0, timezone="UTC"),
            id="upcoming_schedule",
            coalesce=True,
            max_instances=1,
            next_run_time=datetime.now(timezone.utc) + timedelta(seconds=5),
        )
        _scheduler.start()
        logger.info("APScheduler started: live every 60s, schedule daily 12:00 UTC.")
    except Exception:  # noqa: BLE001
        logger.exception("APScheduler failed to start; live data will be stale")
        _scheduler = None

    logger.info("API services warmed.")
    try:
        yield
    finally:
        if _scheduler is not None:
            try:
                _scheduler.shutdown(wait=False)
            except Exception:  # noqa: BLE001
                logger.exception("scheduler shutdown failed")
            _scheduler = None
        if _services is not None:
            _services.close()
            _services = None


# --------------------------------------------------------------------------- #
# FastAPI app + CORS
# --------------------------------------------------------------------------- #


def _origins() -> list[str]:
    raw = os.environ.get("ALLOWED_ORIGINS", "")
    if raw.strip():
        return [o.strip() for o in raw.split(",") if o.strip()]
    # Next.js dev server falls forward through 3000..3009 when ports are busy,
    # so the allowlist covers the range to keep `npm run dev` painless.
    ports = range(3000, 3010)
    return [f"http://{host}:{p}" for host in ("localhost", "127.0.0.1") for p in ports]


app = FastAPI(
    title="NBA Scouting + Stats RAG",
    description="HTTP API for the Next.js UI. Wraps the ask() pipeline.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(header_router)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness + DB-reachable check."""
    db_ok = True
    note = ""
    try:
        import psycopg

        settings = get_settings()
        with psycopg.connect(str(settings.postgres_url)) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        db_ok = False
        note = f"db check failed: {type(exc).__name__}"
        logger.exception("/health db check failed")
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        db_ok=db_ok,
        note=note,
    )


@app.post("/ask", response_model=AskResponse)
def ask_endpoint(req: AskRequest) -> AskResponse:
    """Run one full ask() pipeline call and return a serializable response."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question must be non-empty")

    services = _get_services()
    filters = ChunkFilters(player_ids=req.player_ids, source=req.source)

    start = time.perf_counter()
    try:
        result = ask(
            req.question,
            filters=filters,
            top_k=req.top_k,
            classifier=services.classifier,
            embedder=services.embedder,
            reranker=services.reranker,
            synthesizer=services.synthesizer,
            sql_generator=services.sql_generator,
            session_id=req.session_id or "api",
        )
    except Exception as exc:
        logger.exception("ask endpoint failed")
        # Translate upstream credential failures (Anthropic, Voyage, Cohere)
        # into a clean 503 the UI can present without exposing the raw
        # provider payload. Matches by exception class name + message so
        # adding a new provider doesn't break this branch.
        cls = type(exc).__name__
        msg = str(exc)
        is_auth_failure = (
            cls in {"AuthenticationError", "PermissionDeniedError"}
            or "x-api-key" in msg.lower()
            or "authentication_error" in msg.lower()
            or "401" in msg.split(":")[0]
        )
        if is_auth_failure:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "llm_unauthenticated",
                    "message": (
                        "The Oracle's LLM provider rejected its API key. "
                        "Update ANTHROPIC_API_KEY (or the relevant provider key) "
                        "in .env and restart the FastAPI server."
                    ),
                },
            ) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    elapsed_ms = (time.perf_counter() - start) * 1000

    response = _to_response(req.question, result, elapsed_ms)

    # Fire-and-forget Braintrust span. Serialize via model_dump so the trace
    # mirrors what the client receives — easier to debug from the UI.
    bt_log_ask(
        question=req.question,
        filters={"player_ids": req.player_ids, "source": req.source},
        top_k=req.top_k,
        response_payload=response.model_dump(),
        elapsed_ms=elapsed_ms,
    )

    return response


# --------------------------------------------------------------------------- #
# Serialization helpers
# --------------------------------------------------------------------------- #


def _to_response(question: str, result: AskResult, elapsed_ms: float) -> AskResponse:
    return AskResponse(
        question=question,
        route=RouteOut(route=result.route.route, reasoning=result.route.reasoning),
        answer=result.answer,
        synthesis=_synthesis_out(result),
        retrieval=_retrieval_out(result),
        stats=_stats_out(result),
        hybrid=_hybrid_out(result),
        not_yet_implemented=result.not_yet_implemented,
        notes=result.notes,
        elapsed_ms=elapsed_ms,
    )


def _synthesis_out(result: AskResult) -> SynthesisOut | None:
    s = result.synthesis
    if s is None:
        return None
    return SynthesisOut(
        answer=s.answer,
        citations=[CitationOut(citation_index=c.citation_index, chunk_id=c.chunk_id) for c in s.citations],
        cited_chunk_ids=s.cited_chunk_ids,
        model=s.model,
        input_tokens=s.input_tokens,
        output_tokens=s.output_tokens,
        cost_usd=s.cost_usd,
        declined=s.declined,
    )


def _retrieval_out(result: AskResult) -> RetrievalOut | None:
    r = result.retrieval
    if r is None:
        return None
    return RetrievalOut(
        bm25_count=r.bm25_count,
        dense_count=r.dense_count,
        merged_count=r.merged_count,
        chunks=[_chunk_out(c) for c in r.chunks],
    )


def _chunk_out(c) -> ChunkOut:  # type: ignore[no-untyped-def]
    return ChunkOut(
        chunk_id=c.chunk_id,
        text=c.text,
        source=c.source,
        article_type=c.article_type,
        date=c.date.isoformat() if c.date else None,
        score=c.score,
        player_ids=c.player_ids,
    )


def _stats_out(result: AskResult) -> StatsOut | None:
    s = result.stats
    if s is None:
        return None
    return StatsOut(
        status=s.status,
        sql=s.generated.sql if s.generated else None,
        params=s.generated.params if s.generated else None,
        explanation=s.generated.explanation if s.generated else None,
        rows=s.execution.rows if s.execution else None,
        row_count=s.execution.row_count if s.execution else None,
        elapsed_ms=s.execution.elapsed_ms if s.execution else None,
        cost_usd=s.generated.cost_usd if s.generated else 0.0,
        error=s.error,
    )


def _hybrid_out(result: AskResult) -> HybridOut | None:
    h = result.hybrid
    if h is None:
        return None
    return HybridOut(
        status=h.status,
        filter=HybridFilterOut(
            sql=h.filter.sql,
            params=h.filter.params,
            explanation=h.filter.explanation,
            player_ids=h.filter.player_ids,
            cost_usd=h.filter.cost_usd,
            status=h.filter.status,
            rows=h.filter.rows,
            column_names=h.filter.column_names,
            row_count=len(h.filter.rows),
        ),
        retrieval=_retrieval_out_from(h.retrieval) if h.retrieval else None,
        notes=h.notes,
    )


def _retrieval_out_from(r) -> RetrievalOut:  # type: ignore[no-untyped-def]
    return RetrievalOut(
        bm25_count=r.bm25_count,
        dense_count=r.dense_count,
        merged_count=r.merged_count,
        chunks=[_chunk_out(c) for c in r.chunks],
    )
