"""Braintrust instrumentation for the live API server.

The eval runner already streams experiment runs to Braintrust under the
`nba-rag` project; this module streams *production* `/ask` calls to the
same project as ordinary logger events. That gives a single pane of glass
across batch evals and the user-facing UI traffic.

Design notes:
  * The logger is initialized lazily, once, behind a module-level singleton.
    A missing API key or SDK import error degrades to a no-op so the server
    stays up regardless of Braintrust availability.
  * `log_ask()` wraps one `/ask` call in a single span with the question
    as input, the full serialized response as output, and the high-signal
    fields (route, costs, latencies, cited chunk ids) hoisted into metadata
    so they're filterable in the Braintrust UI.
  * We deliberately do NOT log retrieved chunk text in metadata — it can
    be large and is already in `output.retrieval.chunks`. Cite ids are
    enough for filtering.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from src.config import get_settings

logger = logging.getLogger(__name__)

_initialized = False
_bt_logger: Any | None = None  # braintrust.Logger when active, else None


def init() -> Any | None:
    """Initialize the Braintrust logger once. Idempotent.

    Returns the logger instance on success, or None if Braintrust is
    unavailable (missing key, missing SDK, init failure). Subsequent calls
    return the cached instance.
    """
    global _initialized, _bt_logger
    if _initialized:
        return _bt_logger
    _initialized = True

    settings = get_settings()
    if not settings.braintrust_api_key:
        logger.info("BRAINTRUST_API_KEY not set; /ask Braintrust logging disabled.")
        return None

    try:
        import braintrust
    except ImportError:
        logger.info("braintrust SDK not installed; /ask Braintrust logging disabled.")
        return None

    try:
        os.environ.setdefault(
            "BRAINTRUST_API_KEY",
            settings.braintrust_api_key.get_secret_value(),
        )
        _bt_logger = braintrust.init_logger(project=settings.braintrust_project)
        logger.info(
            "Braintrust API logger ready (project=%s).",
            settings.braintrust_project,
        )
        return _bt_logger
    except Exception:
        logger.exception("Braintrust init failed; continuing without logging.")
        return None


def log_ask(
    *,
    question: str,
    filters: dict[str, Any],
    top_k: int,
    response_payload: dict[str, Any],
    elapsed_ms: float,
) -> None:
    """Emit one Braintrust span for a single /ask call. No-op if unavailable.

    `response_payload` should be the already-serialized AskResponse dict so
    the Braintrust UI shows exactly what the client saw.
    """
    if _bt_logger is None:
        return
    try:
        route = response_payload.get("route", {}) or {}
        synth = response_payload.get("synthesis") or {}
        stats = response_payload.get("stats") or {}
        hybrid = response_payload.get("hybrid") or {}
        hybrid_filter = (hybrid.get("filter") or {}) if isinstance(hybrid, dict) else {}

        cost_usd = float(
            (synth.get("cost_usd") or 0.0)
            + (stats.get("cost_usd") or 0.0)
            + (hybrid_filter.get("cost_usd") or 0.0)
        )

        metadata: dict[str, Any] = {
            "origin": "api/ask",
            "route": route.get("route"),
            "router_reasoning": route.get("reasoning"),
            "model": synth.get("model"),
            "input_tokens": synth.get("input_tokens"),
            "output_tokens": synth.get("output_tokens"),
            "cost_usd": cost_usd,
            "elapsed_ms": elapsed_ms,
            "cited_chunk_ids": synth.get("cited_chunk_ids", []),
            "not_yet_implemented": bool(response_payload.get("not_yet_implemented", False)),
            "top_k": top_k,
            "filters": filters,
        }

        span = _bt_logger.start_span(name="api.ask")
        span.log(
            input={"question": question, "top_k": top_k, "filters": filters},
            output=response_payload,
            metadata=metadata,
        )
        span.end()
        # Flush asynchronously; failures here are non-fatal.
        try:
            _bt_logger.flush()
        except Exception:
            logger.debug("Braintrust flush failed; will retry on next event.")
    except Exception:
        logger.exception("Braintrust log_ask failed; continuing.")
