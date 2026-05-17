"""Fixtures for UI/Playwright tests.

These tests require:
  * the Next.js dev server reachable at NBARAG_UI_URL (defaults to
    http://localhost:3002 — port 3000 is held on this machine by an
    unrelated process)
  * the FastAPI dev server reachable on http://localhost:8000

Tests skip gracefully when the dev server is not reachable so the suite
can be run from CI without a running webapp.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
import urllib.request

UI_URL = os.environ.get("NBARAG_UI_URL", "http://localhost:3002")
API_URL = os.environ.get("NBARAG_API_URL", "http://localhost:8000")


def _reachable(url: str, timeout: float = 5.0) -> bool:
    """One-shot reachability probe with a short retry. Used by the
    session-scoped skip-if-no-server fixture; the dev servers can be slow
    to respond on the very first connection of a test run."""
    for _ in range(3):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                if 200 <= resp.status < 500:
                    return True
        except Exception:  # noqa: BLE001
            pass
    return False


@pytest.fixture(scope="session")
def ui_url() -> str:
    return UI_URL


@pytest.fixture(scope="session", autouse=True)
def _require_servers() -> None:
    if not _reachable(UI_URL):
        pytest.skip(f"Next.js dev server not reachable at {UI_URL}", allow_module_level=False)
    if not _reachable(f"{API_URL}/health"):
        pytest.skip(f"FastAPI server not reachable at {API_URL}", allow_module_level=False)


@pytest.fixture
def page() -> Iterator:
    """A fresh Playwright page per test, with a 1480x900 viewport.

    Wide enough that the responsive `lg:`/`xl:` branches of the header layout
    activate, so a test that depends on (say) the leader stat line in the
    live banner doesn't silently pass at narrow widths.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1480, "height": 900})
        page = context.new_page()
        try:
            yield page
        finally:
            context.close()
            browser.close()


@pytest.fixture
def goto_home(page, ui_url):
    """Navigate home and dismiss the intro video so subsequent assertions
    can operate against the steady-state header."""

    def _go():
        page.goto(ui_url, wait_until="domcontentloaded")
        # Intro video plays on every load. Dismiss it so the header is
        # actually visible to the test. The button has aria-label.
        skip = page.locator('button[aria-label="Skip intro video"]')
        if skip.count() > 0:
            skip.first.click()
        # Wait for header data to land.
        page.wait_for_selector('[data-testid="app-header"]', timeout=10_000)
        # The header endpoint can take a beat to land under heavy back-to-
        # back test load. Most tests don't actually need ticker data — the
        # ticker-specific ones explicitly re-wait on it. So if the strip
        # never loads in time, swallow the timeout rather than fail the
        # whole suite. Tests that need ticker content will surface their
        # own assertion errors anyway.
        try:
            page.wait_for_function(
                """() => {
                    const strip = document.querySelector('[data-testid="header-ticker-strip"]');
                    if (!strip) return false;
                    const t = strip.textContent?.trim() ?? '';
                    if (t.includes('Header data unavailable')) return true;
                    return t.length > 30;
                }""",
                timeout=15_000,
            )
        except Exception:  # noqa: BLE001
            # Test owns the failure path: a ticker-specific test will catch
            # missing content; non-ticker tests proceed.
            pass
        return page

    return _go
