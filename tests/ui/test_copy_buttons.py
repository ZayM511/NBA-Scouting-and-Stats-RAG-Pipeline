"""End-to-end UI tests for the per-turn copy buttons.

These tests enforce that one-click copy works for:
  1. The user's question shown on each TurnCard.
  2. The synthesized answer in AnswerPanel.
  3. The trace bundle (route + SQL + retrieval + answer) in the Sidebar.

The clipboard verification reads back what the button wrote and asserts
the value matches the source content. Tests skip if either dev server
isn't reachable (handled by conftest).

Run with:  pytest tests/ui/test_copy_buttons.py -v
"""

from __future__ import annotations


SAMPLE_QUESTION = "Who leads the league in threes this playoffs?"


def _dismiss_intro(page) -> None:
    """Make sure the intro video overlay is fully gone. The conftest fires
    a single skip click, but on slow machines the modal can linger long
    enough to intercept pointer events on the textarea. Re-press until
    the dialog unmounts."""
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
    """Type `prompt` into the chat textarea and submit it."""
    _dismiss_intro(page)
    textarea = page.locator("textarea").first
    textarea.click()
    textarea.fill(prompt)
    textarea.press("Enter")


def _wait_for_pipeline_success(page, *, turn_index: int = 0, timeout_ms: int = 60_000) -> None:
    """Block until the n-th pipeline banner reports data-phase=success."""
    page.wait_for_function(
        """({ turnIndex }) => {
            const all = document.querySelectorAll('[data-testid="pipeline-progress"]');
            const el = all[turnIndex];
            return el && el.dataset.phase === 'success';
        }""",
        arg={"turnIndex": turn_index},
        timeout=timeout_ms,
    )


def _grant_clipboard(page) -> None:
    """Allow clipboard-read so the test can verify what was copied."""
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])


# --------------------------------------------------------------------------
# Core test: each turn shows three copy buttons + each writes its content.
# --------------------------------------------------------------------------


def test_copy_buttons_present_after_answer_lands(goto_home):
    """After a successful answer, every TurnCard exposes a question copy
    button, an answer copy button, and the Sidebar exposes a trace copy
    button. Each is wired to navigator.clipboard.writeText."""
    page = goto_home()
    _grant_clipboard(page)
    _submit_question(page, SAMPLE_QUESTION)
    _wait_for_pipeline_success(page, turn_index=0)

    # Question copy lives next to the question line.
    question_copy = page.locator(
        '[data-testid="copy-button"][aria-label="Copy"]'
    ).first
    assert question_copy.count() == 1, "question copy button missing"

    # Answer copy lives above the answer paragraphs in AnswerPanel.
    answer_copy = page.locator(
        '[data-testid="copy-button"][aria-label="Copy answer"]'
    ).first
    assert answer_copy.count() == 1, "answer copy button missing"

    # Trace copy lives in the Sidebar header.
    trace_copy = page.locator(
        '[data-testid="copy-button"][aria-label="Copy trace"]'
    ).first
    assert trace_copy.count() == 1, "trace copy button missing"


def test_copy_question_writes_the_exact_question(goto_home):
    """Clicking the question copy button writes the user's question
    verbatim to the clipboard."""
    page = goto_home()
    _grant_clipboard(page)
    _submit_question(page, SAMPLE_QUESTION)
    _wait_for_pipeline_success(page, turn_index=0)

    page.locator(
        '[data-testid="copy-button"][aria-label="Copy"]'
    ).first.click()
    clipboard = page.evaluate("() => navigator.clipboard.readText()")
    assert clipboard == SAMPLE_QUESTION, (
        f"clipboard did not match the question: {clipboard!r}"
    )


def test_copy_answer_writes_the_synthesis_text(goto_home):
    """Clicking the answer copy button writes the synthesized answer
    text. Answer content varies per run, so the test asserts the text
    is non-trivial and not the question itself."""
    page = goto_home()
    _grant_clipboard(page)
    _submit_question(page, SAMPLE_QUESTION)
    _wait_for_pipeline_success(page, turn_index=0)

    page.locator(
        '[data-testid="copy-button"][aria-label="Copy answer"]'
    ).first.click()
    clipboard = page.evaluate("() => navigator.clipboard.readText()")
    assert len(clipboard) > 20, f"answer clipboard too short: {clipboard!r}"
    assert clipboard != SAMPLE_QUESTION


def test_copy_trace_includes_question_route_and_answer(goto_home):
    """The trace copy bundle should include the question, the route name,
    and the synthesized answer in a single plain-text blob."""
    page = goto_home()
    _grant_clipboard(page)
    _submit_question(page, SAMPLE_QUESTION)
    _wait_for_pipeline_success(page, turn_index=0)

    page.locator(
        '[data-testid="copy-button"][aria-label="Copy trace"]'
    ).first.click()
    clipboard = page.evaluate("() => navigator.clipboard.readText()")
    assert SAMPLE_QUESTION in clipboard, "trace bundle missing the question"
    assert "Route:" in clipboard, "trace bundle missing the Route: header"
    assert "## Answer" in clipboard, "trace bundle missing the Answer section"


def test_copy_button_clicks_are_idempotent(goto_home):
    """Clicking the same copy button multiple times in a row keeps writing
    the same content to the clipboard. Guards against a stale state issue
    where a previous click's content lingers."""
    page = goto_home()
    _grant_clipboard(page)
    _submit_question(page, SAMPLE_QUESTION)
    _wait_for_pipeline_success(page, turn_index=0)

    btn = page.locator(
        '[data-testid="copy-button"][aria-label="Copy"]'
    ).first
    for _ in range(3):
        btn.click()
        page.wait_for_timeout(150)
        assert page.evaluate("() => navigator.clipboard.readText()") == SAMPLE_QUESTION


# --------------------------------------------------------------------------
# Each route surfaces its own trace bundle.
# --------------------------------------------------------------------------


def test_stats_route_trace_includes_sql(goto_home):
    """A stats question routes through Text-to-SQL; the trace bundle must
    include the SQL section so a viewer can replay the query."""
    page = goto_home()
    _grant_clipboard(page)
    _submit_question(
        page,
        "Who leads the league in three-point percentage this playoffs with at least 50 attempts?",
    )
    _wait_for_pipeline_success(page, turn_index=0)
    # Confirm the route is stats so the assertion below is meaningful.
    route = page.evaluate(
        """() => document.querySelector('[data-testid="pipeline-progress"]')?.dataset.route"""
    )
    assert route == "stats", f"expected stats route, got {route}"

    page.locator(
        '[data-testid="copy-button"][aria-label="Copy trace"]'
    ).first.click()
    clipboard = page.evaluate("() => navigator.clipboard.readText()")
    assert "## Stats · SQL" in clipboard, "stats trace bundle missing SQL section"


def test_hybrid_route_trace_includes_filter_and_retrieval(goto_home):
    """A hybrid question runs a SQL filter then vector retrieval; both
    halves should land in the trace bundle."""
    page = goto_home()
    _grant_clipboard(page)
    _submit_question(
        page,
        "Which guards shooting >40% from three move best off-ball?",
    )
    _wait_for_pipeline_success(page, turn_index=0)
    route = page.evaluate(
        """() => document.querySelector('[data-testid="pipeline-progress"]')?.dataset.route"""
    )
    assert route == "hybrid", f"expected hybrid route, got {route}"

    page.locator(
        '[data-testid="copy-button"][aria-label="Copy trace"]'
    ).first.click()
    clipboard = page.evaluate("() => navigator.clipboard.readText()")
    assert "## Hybrid filter" in clipboard
    assert "## Retrieval" in clipboard


def test_each_turn_in_conversation_has_its_own_copy_buttons(goto_home):
    """Submitting two questions in the same session produces two TurnCards;
    each must expose its own question + answer copy buttons. Trace copy
    lives once in the sidebar and reflects the currently selected turn."""
    page = goto_home()
    _grant_clipboard(page)
    _submit_question(page, SAMPLE_QUESTION)
    _wait_for_pipeline_success(page, turn_index=0)
    _submit_question(page, "How is SGA playing this year?")
    _wait_for_pipeline_success(page, turn_index=1)

    # 2 turns × 2 in-card buttons + 1 trace button = 5 total.
    n_buttons = page.locator('[data-testid="copy-button"]').count()
    assert n_buttons == 5, f"expected 5 copy buttons across 2 turns, got {n_buttons}"
