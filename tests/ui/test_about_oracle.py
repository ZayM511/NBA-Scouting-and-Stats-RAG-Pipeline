"""UI tests for the new AboutTheOracle disclosure and related changes
(GLB orb, video poster, intro speedup).

Run with:  pytest tests/ui/test_about_oracle.py -v
"""

from __future__ import annotations

import time

import pytest


def test_about_button_is_present_and_compact(goto_home):
    page = goto_home()
    btn = page.locator('[data-testid="about-the-oracle-trigger"]')
    assert btn.count() == 1, "About The Oracle button missing"
    text = (btn.text_content() or "").upper()
    assert "ABOUT THE ORACLE" in text

    # Closed-state button should be small — significantly shorter than the
    # old always-visible card. Cap at 48px tall.
    box = btn.bounding_box()
    assert box is not None
    assert box["height"] <= 48, f"About button too tall when collapsed: {box['height']}px"


def test_about_content_hidden_when_collapsed(goto_home):
    page = goto_home()
    assert page.locator('[data-testid="about-the-oracle-content"]').count() == 0, (
        "About content should be unmounted until the disclosure is opened"
    )


def test_about_expand_reveals_statements(goto_home):
    page = goto_home()
    page.locator('[data-testid="about-the-oracle-trigger"]').click()
    page.wait_for_selector('[data-testid="about-the-oracle-content"]', timeout=5_000)
    # The first statement should appear within a couple seconds of opening
    # (it types fast, ~22ms/char).
    page.wait_for_function(
        """() => {
            const lines = document.querySelectorAll('[data-testid="about-statements"] p');
            if (!lines.length) return false;
            const first = lines[0].textContent || '';
            return first.includes('Ball Knowledge Oracle');
        }""",
        # Under back-to-back test load the typewriter (and the parent
        # panel animation) can take a beat to render. Give it real slack.
        timeout=15_000,
    )


def test_about_skip_button_completes_typing_immediately(goto_home):
    """The Skip button should finalize the typewriter to the last statement
    so users can read the whole panel without waiting."""
    page = goto_home()
    page.locator('[data-testid="about-the-oracle-trigger"]').click()
    page.wait_for_selector('[data-testid="about-skip"]', timeout=5_000)
    page.locator('[data-testid="about-skip"]').click()
    # After skipping, the last expected line must be present, fully typed.
    page.wait_for_function(
        """() => {
            const lines = document.querySelectorAll('[data-testid="about-statements"] p');
            if (lines.length < 6) return false;
            const last = lines[lines.length - 1].textContent || '';
            return last.includes('keep the receipts');
        }""",
        timeout=4_000,
    )


def test_about_collapse_restores_closed_state(goto_home):
    page = goto_home()
    trigger = page.locator('[data-testid="about-the-oracle-trigger"]')
    trigger.click()
    page.wait_for_selector('[data-testid="about-the-oracle-content"]', timeout=5_000)
    trigger.click()
    page.wait_for_function(
        """() => !document.querySelector('[data-testid="about-the-oracle-content"]')""",
        timeout=4_000,
    )


def test_about_button_aria_expanded_tracks_state(goto_home):
    """aria-expanded must flip on click — assistive tech depends on it."""
    page = goto_home()
    btn = page.locator('[data-testid="about-the-oracle-trigger"]')
    assert btn.get_attribute("aria-expanded") == "false"
    btn.click()
    page.wait_for_selector('[data-testid="about-the-oracle-content"]', timeout=4_000)
    assert btn.get_attribute("aria-expanded") == "true"


# --------------------------------------------------------------------------
# Basketball orb renders the GLB
# --------------------------------------------------------------------------


def test_basketball_orb_canvas_mounts(goto_home):
    """The home-page BasketballOrb canvas must mount with a usable size.
    Header BrandOrb also renders a tiny canvas with the same data-testid,
    so we scope to whichever canvas is the largest on the page."""
    page = goto_home()
    page.wait_for_function(
        """() => {
            const all = Array.from(document.querySelectorAll('[data-testid="basketball-orb"] canvas'));
            return all.some(c => c.width > 100 && c.height > 100);
        }""",
        timeout=10_000,
    )
    # Pick the largest matching canvas (the hero orb).
    width, height = page.evaluate(
        """() => {
            let best = {w: 0, h: 0};
            for (const c of document.querySelectorAll('[data-testid="basketball-orb"] canvas')) {
                if (c.width > best.w) best = {w: c.width, h: c.height};
            }
            return [best.w, best.h];
        }"""
    )
    assert width > 100 and height > 100, f"hero orb canvas too small: {width}x{height}"


def test_glb_asset_is_served(page, ui_url):
    """The GLB file the orb references must actually exist at /basketball_ball.glb."""
    resp = page.request.get(f"{ui_url}/basketball_ball.glb")
    assert resp.ok, f"GLB asset missing or unreadable: HTTP {resp.status}"
    # Crude sanity check: a real GLB binary starts with 'glTF'.
    body = resp.body()
    assert body[:4] == b"glTF", "Asset at /basketball_ball.glb is not a GLB file"


# --------------------------------------------------------------------------
# Intro video — faststart + poster + preload tags
# --------------------------------------------------------------------------


def test_intro_poster_is_served(page, ui_url):
    resp = page.request.get(f"{ui_url}/intro-poster.jpg")
    assert resp.ok, "intro-poster.jpg missing — video would flash black on load"


def test_layout_preloads_video_and_poster(page, ui_url):
    """The <head> ships `<link rel=preload>` tags for both the poster and
    the video so they begin downloading during HTML parse."""
    page.goto(ui_url, wait_until="domcontentloaded")
    preloads = page.locator('link[rel="preload"]')
    hrefs = [preloads.nth(i).get_attribute("href") for i in range(preloads.count())]
    assert any(h and h.endswith("/intro.mp4") for h in hrefs), (
        "Missing <link rel=preload as=video> for /intro.mp4"
    )
    assert any(h and h.endswith("/intro-poster.jpg") for h in hrefs), (
        "Missing <link rel=preload as=image> for /intro-poster.jpg"
    )


def test_intro_video_under_size_budget(page, ui_url):
    """The intro is a 15-second background overlay — re-encoded for snappy
    streaming. Lock in the size budget so a future re-encode can't silently
    regress back to the old 7 MB build."""
    resp = page.request.get(f"{ui_url}/intro.mp4")
    assert resp.ok, f"intro.mp4 not served: HTTP {resp.status}"
    size = len(resp.body())
    # 3 MB ceiling. Current re-encode lands around 2.6 MB.
    assert size < 3 * 1024 * 1024, (
        f"intro.mp4 grew to {size} bytes (>{3 * 1024 * 1024}); re-encode at "
        "lower bitrate or shorten."
    )


def test_about_has_seven_statements(goto_home):
    """The pass added a new statement at index 1, bringing the total to 7."""
    page = goto_home()
    page.locator('[data-testid="about-the-oracle-trigger"]').click()
    page.wait_for_selector('[data-testid="about-skip"]', timeout=5_000)
    page.locator('[data-testid="about-skip"]').click()
    page.wait_for_function(
        """() => document.querySelectorAll('[data-testid="about-statements"] p').length >= 7""",
        timeout=4_000,
    )


def test_about_second_line_is_the_new_bar(goto_home):
    """The new statement should appear immediately after the identity line."""
    page = goto_home()
    page.locator('[data-testid="about-the-oracle-trigger"]').click()
    page.wait_for_selector('[data-testid="about-skip"]', timeout=5_000)
    page.locator('[data-testid="about-skip"]').click()
    page.wait_for_function(
        """() => {
            const ps = document.querySelectorAll('[data-testid="about-statements"] p');
            if (ps.length < 2) return false;
            const t = ps[1].textContent || '';
            return t.includes('know ball') && t.includes('one') && t.includes('more ball than you');
        }""",
        timeout=4_000,
    )


def test_about_first_line_is_orange_bold(goto_home):
    """The identity line gets a hard orange + bold treatment so it pops."""
    page = goto_home()
    page.locator('[data-testid="about-the-oracle-trigger"]').click()
    page.wait_for_selector('[data-testid="about-statements"] p', timeout=5_000)
    first = page.locator('[data-testid="about-statements"] p').first
    color = first.evaluate("el => getComputedStyle(el).color")
    weight = first.evaluate("el => parseInt(getComputedStyle(el).fontWeight, 10)")
    # `#ffb380` → rgb(255, 179, 128)
    assert color.replace(" ", "") == "rgb(255,179,128)", (
        f"first line color {color!r} != orange ember"
    )
    assert weight >= 700, f"first line fontWeight {weight} < 700"


def test_about_panel_is_scrollable(goto_home):
    """A long passes shouldn't overflow the viewport — the panel scrolls."""
    page = goto_home()
    page.locator('[data-testid="about-the-oracle-trigger"]').click()
    page.wait_for_selector('[data-testid="about-statements"]', timeout=5_000)
    overflow_y = page.locator('[data-testid="about-statements"]').evaluate(
        "el => getComputedStyle(el).overflowY"
    )
    assert overflow_y in ("auto", "scroll"), f"overflow-y is {overflow_y!r}"
    max_h = page.locator('[data-testid="about-statements"]').evaluate(
        "el => parseFloat(getComputedStyle(el).maxHeight) || 0"
    )
    assert max_h > 100, f"maxHeight is {max_h}px — expected a real cap"


def test_about_explicit_close_button_collapses_panel(goto_home):
    page = goto_home()
    trigger = page.locator('[data-testid="about-the-oracle-trigger"]')
    trigger.click()
    page.wait_for_selector('[data-testid="about-close"]', timeout=5_000)
    page.locator('[data-testid="about-close"]').click()
    page.wait_for_function(
        """() => !document.querySelector('[data-testid="about-the-oracle-content"]')""",
        timeout=4_000,
    )
    assert trigger.get_attribute("aria-expanded") == "false"


def test_intro_video_has_faststart_moov(ui_url):
    """The MP4 must have its moov atom near the front. Without faststart,
    the browser has to download the whole file before it can play."""
    import urllib.request

    with urllib.request.urlopen(f"{ui_url}/intro.mp4", timeout=10) as resp:
        head = resp.read(8192)
    # The first non-mdat box should be moov for faststart. Scan box headers
    # until we hit a 'moov' or run out of header bytes.
    pos = 0
    found_moov_before_mdat = False
    while pos + 8 <= len(head):
        size = int.from_bytes(head[pos:pos + 4], "big")
        kind = head[pos + 4:pos + 8]
        if kind == b"moov":
            found_moov_before_mdat = True
            break
        if kind == b"mdat":
            break
        if size <= 0:
            break
        pos += size
    assert found_moov_before_mdat, (
        "MP4 has mdat before moov — intro will buffer the entire file before playback"
    )
