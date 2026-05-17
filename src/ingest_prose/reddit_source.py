"""Reddit JSON ingester.

Reads public .json endpoints (no OAuth) per Plan B — see
`src/ingest_prose/__init__.py` for the rationale. The User-Agent header is
the only required credential; Reddit rejects requests without one.

Rate limit (no auth): 60 requests per minute per IP. We add a small per-call
sleep to stay well under (default 1.2s between calls).

Endpoints used:

    https://www.reddit.com/r/{subreddit}/{listing}.json?limit=N
      where listing ∈ {hot, new, top, rising} and N ≤ 100 per call
    https://www.reddit.com/r/{subreddit}/comments/{post_id}.json
      returns the post body + the comment tree (we keep the top-level comments)

For each ingested thread we yield a `ProseDocument` with:
    - url:           https://www.reddit.com/r/{sub}/comments/{id}/...
    - source:        'r/{subreddit}'
    - title:         the thread title
    - date:          the post creation date (UTC)
    - body:          {title}\\n\\n{selftext}\\n\\n[top comments]
    - article_type:  'reddit_thread'

The body deliberately concatenates the title, the OP's text, and the top
comments because the OP often only sets the topic ("Wemby box: 30/15/9")
while the analysis lives in the comments.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, timezone

import requests

from src.config import get_settings

logger = logging.getLogger(__name__)

REDDIT_BASE = "https://www.reddit.com"
DEFAULT_LISTING = "top"
DEFAULT_TIMEFRAME = "month"
DEFAULT_MIN_INTERVAL_SECONDS = 1.2  # 50 req/min, well under the 60 limit
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_TOP_COMMENTS = 10
MIN_BODY_CHARS = 200  # skip threads that have no real content


@dataclass(frozen=True)
class ProseDocument:
    """One ingested document, ready for the rest of the pipeline."""

    url: str
    source: str
    title: str
    date: date | None
    body: str
    article_type: str


class RedditFetcher:
    """Stateful HTTP client for Reddit's public JSON endpoints."""

    def __init__(
        self,
        user_agent: str | None = None,
        min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if user_agent is None:
            user_agent = get_settings().reddit_user_agent
        if not user_agent or "<your_reddit_username>" in user_agent:
            raise ValueError(
                "REDDIT_USER_AGENT in .env is missing or still has the placeholder. "
                "Set it to something like 'nba-rag/0.1 by your_handle'."
            )
        self._user_agent = user_agent
        self._min_interval = min_interval_seconds
        self._timeout = timeout_seconds
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": user_agent, "Accept": "application/json"})
        self._last_call: float = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()

    def _get_json(self, path: str, params: dict[str, str | int] | None = None) -> dict:
        self._throttle()
        url = f"{REDDIT_BASE}{path}"
        response = self._session.get(url, params=params, timeout=self._timeout)
        if response.status_code == 429:
            # Reddit rate-limited us. Back off harder and retry once.
            logger.warning("reddit 429 on %s; backing off 10s", url)
            time.sleep(10)
            response = self._session.get(url, params=params, timeout=self._timeout)
        response.raise_for_status()
        return response.json()

    def list_threads(
        self,
        subreddit: str,
        *,
        listing: str = DEFAULT_LISTING,
        timeframe: str = DEFAULT_TIMEFRAME,
        limit: int = 50,
    ) -> list[dict]:
        """Return the raw 'data.children' list for a listing.

        `listing` ∈ {hot, new, top, rising}. `timeframe` only applies to
        `top` (one of hour/day/week/month/year/all).
        """
        if limit > 100:
            raise ValueError("Reddit's per-call max is 100")
        params: dict[str, str | int] = {"limit": limit}
        if listing == "top":
            params["t"] = timeframe
        path = f"/r/{subreddit}/{listing}.json"
        data = self._get_json(path, params)
        children = data.get("data", {}).get("children", [])
        return [c["data"] for c in children if c.get("kind") == "t3"]

    def fetch_thread(
        self,
        permalink: str,
        *,
        top_comments: int = DEFAULT_TOP_COMMENTS,
    ) -> tuple[dict, list[dict]]:
        """Fetch one thread by its permalink. Returns (post_data, top_comments_data)."""
        # Permalinks come back like '/r/nba/comments/abc123/title/'; trim to .json
        path = permalink.rstrip("/") + ".json"
        data = self._get_json(path, params={"limit": top_comments, "depth": 1})
        # data is a 2-element list: [post_listing, comments_listing]
        if not isinstance(data, list) or len(data) < 2:
            return {}, []
        post = (data[0].get("data", {}).get("children", [{}])[0] or {}).get("data", {})
        raw_comments = data[1].get("data", {}).get("children", [])
        comments = [
            c["data"]
            for c in raw_comments
            if c.get("kind") == "t1" and c.get("data", {}).get("body")
        ][:top_comments]
        return post, comments

    def close(self) -> None:
        self._session.close()


def _build_body(post: dict, comments: list[dict]) -> str:
    """Concatenate title + selftext + top comments into one document body.

    The title is repeated outside the body field so callers don't have to
    parse — this keeps the entity-resolver step able to find player names
    even when they only appear in the title.
    """
    parts: list[str] = []
    title = (post.get("title") or "").strip()
    selftext = (post.get("selftext") or "").strip()
    if title:
        parts.append(title)
    if selftext:
        parts.append(selftext)
    if comments:
        parts.append("[top comments]")
        for c in comments:
            body = (c.get("body") or "").strip()
            if body:
                parts.append(f"- {body}")
    return "\n\n".join(parts)


def _to_date(unix_ts: float | int | None) -> date | None:
    if not unix_ts:
        return None
    try:
        return datetime.fromtimestamp(float(unix_ts), tz=timezone.utc).date()
    except (ValueError, TypeError, OSError):
        return None


def ingest_subreddit(
    subreddit: str,
    *,
    fetcher: RedditFetcher | None = None,
    listing: str = DEFAULT_LISTING,
    timeframe: str = DEFAULT_TIMEFRAME,
    limit: int = 50,
    top_comments: int = DEFAULT_TOP_COMMENTS,
    min_body_chars: int = MIN_BODY_CHARS,
) -> Iterator[ProseDocument]:
    """Yield `ProseDocument`s for the top `limit` threads in `subreddit`.

    Default settings pull r/<sub>/top/month, limit 50 threads, with up to 10
    top-level comments each. Threads with bodies under `min_body_chars` are
    skipped (low-signal photo posts, single-line score updates, etc.).
    """
    owns_fetcher = fetcher is None
    fetcher = fetcher or RedditFetcher()
    try:
        threads = fetcher.list_threads(
            subreddit, listing=listing, timeframe=timeframe, limit=limit
        )
        logger.info(
            "reddit: %d threads from r/%s (%s, %s)", len(threads), subreddit, listing, timeframe
        )
        for t in threads:
            permalink = t.get("permalink")
            if not permalink:
                continue
            post, comments = fetcher.fetch_thread(permalink, top_comments=top_comments)
            body = _build_body(post or t, comments)
            if len(body) < min_body_chars:
                continue
            doc = ProseDocument(
                url=f"{REDDIT_BASE}{permalink}",
                source=f"r/{subreddit}",
                title=(post.get("title") or t.get("title") or "").strip(),
                date=_to_date((post or t).get("created_utc")),
                body=body,
                article_type="reddit_thread",
            )
            yield doc
    finally:
        if owns_fetcher:
            fetcher.close()


def ingest_subreddits(
    subreddits: Iterable[str],
    *,
    fetcher: RedditFetcher | None = None,
    listing: str = DEFAULT_LISTING,
    timeframe: str = DEFAULT_TIMEFRAME,
    limit_per_sub: int = 50,
    top_comments: int = DEFAULT_TOP_COMMENTS,
) -> Iterator[ProseDocument]:
    """Convenience: ingest several subreddits with one fetcher."""
    owns_fetcher = fetcher is None
    fetcher = fetcher or RedditFetcher()
    try:
        for sub in subreddits:
            yield from ingest_subreddit(
                sub,
                fetcher=fetcher,
                listing=listing,
                timeframe=timeframe,
                limit=limit_per_sub,
                top_comments=top_comments,
            )
    finally:
        if owns_fetcher:
            fetcher.close()
