"""End-to-end UI tests for the "How I Built This" page + entry button.

Coverage:
  1. The entry button appears on the home page (no conversation yet)
     and is anchored to the top of the trace sidebar.
  2. The button hides once a turn lands so it doesn't compete with the
     trace surface.
  3. The /build route renders all expected sections.
  4. The illustrated pipeline diagram renders every expected stage card
     (user-question, router, stats, prose, hybrid, synthesis, answer).
  5. The "View on GitHub" links point at the public repo and open in a
     new tab.
  6. The back link returns to /.

Run with:  pytest tests/ui/test_build_page.py -v
"""

from __future__ import annotations


REPO_URL = "https://github.com/ZayM511/NBA-Scouting-and-Stats-RAG-Pipeline"
SAMPLE_QUESTION = "Who leads the league in threes this playoffs?"


def _dismiss_intro(page) -> None:
    """Make sure the intro video overlay is fully gone."""
    for _ in range(10):
        if page.locator('[data-testid="intro-video"]').count() == 0:
            return
        skip = page.locator('button[aria-label="Skip intro video"]')
        if skip.count() > 0:
            try:
                skip.first.click(timeout=1_000)
            except Exception:  # noqa: BLE001
                pass
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)


def _submit_question(page, prompt: str) -> None:
    _dismiss_intro(page)
    textarea = page.locator("textarea").first
    textarea.click()
    textarea.fill(prompt)
    textarea.press("Enter")


def _wait_for_pipeline_success(page, *, turn_index: int = 0, timeout_ms: int = 60_000) -> None:
    page.wait_for_function(
        """({ turnIndex }) => {
            const all = document.querySelectorAll('[data-testid="pipeline-progress"]');
            const el = all[turnIndex];
            return el && el.dataset.phase === 'success';
        }""",
        arg={"turnIndex": turn_index},
        timeout=timeout_ms,
    )


# --------------------------------------------------------------------------
# Entry button on the home page.
# --------------------------------------------------------------------------


def test_build_entry_button_visible_on_home(goto_home):
    """A single BuildEntryButton is rendered at the top of the trace
    sidebar on the home screen and links to /build."""
    page = goto_home()
    _dismiss_intro(page)
    btn = page.locator('[data-testid="build-entry-button"]').first
    assert btn.count() == 1, "BuildEntryButton missing on home"
    assert btn.get_attribute("href") == "/build"
    text = btn.text_content() or ""
    assert "How I Built This" in text


def test_build_entry_button_hidden_after_question(goto_home):
    """Once a question lands and the trace fills up, the entry button is
    no longer rendered. (The aside switches from EmptyTrace to the
    populated Trace view.)"""
    page = goto_home()
    _submit_question(page, SAMPLE_QUESTION)
    _wait_for_pipeline_success(page, turn_index=0)
    # Give the React render one extra tick after the phase flips so the
    # Sidebar has time to swap its branch from EmptyTrace to Trace.
    page.wait_for_timeout(300)
    btn = page.locator('[data-testid="build-entry-button"]')
    assert btn.count() == 0, "BuildEntryButton should hide after a turn lands"


# --------------------------------------------------------------------------
# /build page itself.
# --------------------------------------------------------------------------


def test_build_page_renders(page, ui_url):
    """Direct navigation to /build renders the title, the diagram, and
    the page-level metadata."""
    page.goto(f"{ui_url}/build", wait_until="domcontentloaded")
    page.wait_for_selector("h1", timeout=5_000)
    h1 = page.locator("h1").first.text_content() or ""
    assert "How I Built This" in h1
    title = page.title() or ""
    assert "How I Built This" in title


def test_build_page_diagram_has_every_stage(page, ui_url):
    """The illustrated pipeline diagram renders each named stage of the
    DAG. This is what conveys the architecture at a glance, so a
    regression here is high-priority."""
    page.goto(f"{ui_url}/build", wait_until="domcontentloaded")
    page.wait_for_selector('[data-testid="build-pipeline-diagram"]', timeout=5_000)
    expected = {
        "user-question",
        "router",
        "stats",
        "prose",
        "hybrid",
        "synthesis",
        "answer",
    }
    diagram = page.locator('[data-testid="build-pipeline-diagram"]').first
    stages = diagram.locator("[data-stage]").all()
    rendered = {s.get_attribute("data-stage") for s in stages}
    assert expected.issubset(rendered), (
        f"missing diagram stages: expected {expected}, got {rendered}"
    )


def test_build_page_github_links_point_at_repo(page, ui_url):
    """The header "View on GitHub" link and the closing CTA both point
    at the public repo, both open in a new tab."""
    page.goto(f"{ui_url}/build", wait_until="domcontentloaded")
    header_link = page.locator('[data-testid="build-github-link"]').first
    footer_link = page.locator('[data-testid="build-footer-github-link"]').first
    assert header_link.get_attribute("href") == REPO_URL
    assert header_link.get_attribute("target") == "_blank"
    assert footer_link.get_attribute("href") == REPO_URL
    assert footer_link.get_attribute("target") == "_blank"


def test_build_page_back_link_returns_home(page, ui_url):
    """The Back link in the page header navigates back to /."""
    page.goto(f"{ui_url}/build", wait_until="domcontentloaded")
    back = page.get_by_role("link", name="Back to the Oracle")
    assert back.count() >= 1
    back.first.click()
    page.wait_for_url(f"{ui_url}/", timeout=5_000)
