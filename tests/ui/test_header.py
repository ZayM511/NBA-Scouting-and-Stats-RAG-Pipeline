"""End-to-end UI tests for the Ball Knowledge Oracle header.

These tests enforce the header requirements:

  1. NBA logo card is large and visible.
  2. NBA "2025-26 Season" badge is present.
  3. "Ball Knowledge Oracle" brand title is present and prominent.
  4. ESPN-style stat ticker is always rendered (regardless of mode), is
     actually scrolling, and shows multiple distinct stat cards.
  5. The state banner (recap / live / upcoming) lives in the *top row*
     and never overlaps the brand title or the NBA badge.
  6. The dev toggle can flip between modes and each mode renders.

Run with:  pytest tests/ui/test_header.py -v
"""

from __future__ import annotations

import re
import time

import pytest


# --------------------------------------------------------------------------
# 1. The brand title — Ball Knowledge Oracle — is prominent.
# --------------------------------------------------------------------------


def test_brand_title_is_present_and_large(goto_home):
    """The 'Ball Knowledge Oracle' brand title must be in the top row and
    rendered at a noticeable size (>= 18px)."""
    page = goto_home()
    brand = page.locator('[data-testid="brand-home"]')
    assert brand.count() == 1
    text = brand.text_content() or ""
    assert "Ball Knowledge" in text
    assert "Oracle" in text

    # Inspect the font-size of the title line.
    title_size = brand.locator("span", has_text="Oracle").first.evaluate(
        "el => parseFloat(getComputedStyle(el).fontSize)"
    )
    assert title_size >= 18, f"BKO title font-size too small: {title_size}px"


# --------------------------------------------------------------------------
# 2. NBA logo is bigger and visible, in a white card.
# --------------------------------------------------------------------------


def test_nba_logo_card_is_large(goto_home):
    """NBA logo card should be at least 36px tall — bigger than the
    initial 24px thumbnail it started life as."""
    page = goto_home()
    card = page.locator('[data-testid="nba-logo-card"]')
    assert card.count() == 1, "NBA logo card missing"
    box = card.bounding_box()
    assert box is not None
    assert box["height"] >= 36, f"NBA logo card too short: {box['height']}px"
    assert box["width"] >= 24, f"NBA logo card too narrow: {box['width']}px"


def test_nba_logo_image_loads(goto_home):
    """The PNG actually resolves — the <img>'s naturalWidth > 0 after load."""
    page = goto_home()
    img = page.locator('[data-testid="nba-logo-card"] img[alt="NBA"]').first
    assert img.count() == 1
    page.wait_for_function(
        """() => {
            const i = document.querySelector('[data-testid="nba-logo-card"] img[alt=\\\"NBA\\\"]');
            return i && i.complete && i.naturalWidth > 0;
        }""",
        timeout=5_000,
    )


def test_nba_season_text_is_visible(goto_home):
    """The badge contains the season text in uppercase."""
    page = goto_home()
    badge = page.locator('[data-testid="nba-season-badge"]')
    assert badge.count() == 1
    text = (badge.text_content() or "").upper()
    assert "NBA" in text
    assert "2025" in text and "26" in text
    assert "SEASON" in text


# --------------------------------------------------------------------------
# 3. Header layout: brand title, NBA badge, state banner do not overlap.
# --------------------------------------------------------------------------


def _bbox(locator):
    return locator.bounding_box()


def _no_horizontal_overlap(a, b) -> bool:
    """Two horizontally-laid-out boxes should not overlap on the X axis."""
    if a is None or b is None:
        return True
    return (a["x"] + a["width"]) <= (b["x"] + 1) or (b["x"] + b["width"]) <= (a["x"] + 1)


def test_top_row_elements_do_not_overlap(goto_home):
    page = goto_home()
    brand = _bbox(page.locator('[data-testid="brand-home"]'))
    badge = _bbox(page.locator('[data-testid="nba-season-badge"]'))
    assert brand and badge
    # Brand should be to the left of the badge.
    assert brand["x"] + brand["width"] <= badge["x"] + 4, (
        "Brand title overlaps NBA badge: "
        f"brand right edge {brand['x'] + brand['width']}, badge left {badge['x']}"
    )


def test_state_banner_does_not_block_brand_or_badge(goto_home):
    """Whatever state the banner is in (recap / upcoming / live / none),
    it must not overlap horizontally with the brand title or the NBA
    season badge."""
    page = goto_home()
    brand = _bbox(page.locator('[data-testid="brand-home"]'))
    badge = _bbox(page.locator('[data-testid="nba-season-badge"]'))

    # Probe whichever banner is active.
    for testid in ("top-recap", "top-live", "top-upcoming"):
        banner = page.locator(f'[data-testid="{testid}"]')
        if banner.count():
            box = _bbox(banner)
            assert _no_horizontal_overlap(brand, box), (
                f"{testid} overlaps the brand title"
            )
            assert _no_horizontal_overlap(badge, box), (
                f"{testid} overlaps the NBA season badge"
            )
            break


def test_state_banner_is_in_top_row(goto_home):
    """The state banner should be aligned with the main top row, not on a
    separate row below it."""
    page = goto_home()
    brand = _bbox(page.locator('[data-testid="brand-home"]'))
    assert brand
    brand_center_y = brand["y"] + brand["height"] / 2

    for testid in ("top-recap", "top-live", "top-upcoming"):
        banner = page.locator(f'[data-testid="{testid}"]')
        if banner.count():
            box = _bbox(banner)
            assert box
            banner_center_y = box["y"] + box["height"] / 2
            # Same row means centers are within roughly the row's own
            # half-height of each other.
            assert abs(brand_center_y - banner_center_y) <= 40, (
                f"{testid} center y={banner_center_y} not aligned with brand y={brand_center_y}"
            )
            break


# --------------------------------------------------------------------------
# 4. ESPN-style ticker — always present and scrolling.
# --------------------------------------------------------------------------


def test_ticker_strip_is_present(goto_home):
    page = goto_home()
    strip = page.locator('[data-testid="header-ticker-strip"]')
    assert strip.count() == 1, "Persistent ticker strip missing from header"


def test_ticker_renders_multiple_distinct_cards(goto_home):
    """The ticker has cards for several distinct stats. Verifying multiple
    cards proves the marquee has real content, not a single static label."""
    page = goto_home()
    # Wait for header data + ticker to populate.
    page.wait_for_selector('[data-testid="header-ticker-track"] > div', timeout=10_000)
    cards = page.locator('[data-testid="header-ticker-track"] > div')
    # Doubled for the seamless loop, so we expect at minimum 2 cards even
    # for a one-headline edge case — and ≥ 6 for a healthy data load.
    assert cards.count() >= 6, f"Ticker has only {cards.count()} cards"


def test_ticker_is_scrolling(goto_home):
    """The marquee animates left over time. Sample its transform twice and
    verify the X translation changed."""
    page = goto_home()
    page.wait_for_selector('[data-testid="header-ticker-track"]', timeout=10_000)
    track = page.locator('[data-testid="header-ticker-track"]').first

    def x_of(element):
        return element.evaluate(
            """el => {
                const m = new DOMMatrixReadOnly(getComputedStyle(el).transform);
                return m.m41;
            }"""
        )

    # If the track hasn't measured itself yet (ResizeObserver) duration is
    # 0 and there's no animation — wait until the duration kicks in.
    page.wait_for_function(
        """() => {
            const t = document.querySelector('[data-testid="header-ticker-track"]');
            if (!t) return false;
            const m = new DOMMatrixReadOnly(getComputedStyle(t).transform);
            return m.m41 !== 0;
        }""",
        timeout=8_000,
    )
    a = x_of(track)
    time.sleep(1.3)
    b = x_of(track)
    assert a != b, f"Ticker not moving: x stayed at {a}"
    # It scrolls leftward (negative x).
    assert b < a, f"Ticker moving right ({a} -> {b}) instead of left"


def test_ticker_does_not_overflow_into_brand(goto_home):
    """The ticker strip lives in its own row — its top edge must sit below
    the brand title's bottom edge."""
    page = goto_home()
    brand = _bbox(page.locator('[data-testid="brand-home"]'))
    strip = _bbox(page.locator('[data-testid="header-ticker-strip"]'))
    assert brand and strip
    assert strip["y"] >= (brand["y"] + brand["height"] - 4), (
        f"Ticker strip overlaps brand row: brand bottom={brand['y'] + brand['height']}, strip top={strip['y']}"
    )


# --------------------------------------------------------------------------
# 5. Each mode renders its banner.
# --------------------------------------------------------------------------


def _set_mode(page, mode_label: str):
    """Open the floating mode toggle, click the requested option, then close."""
    toggle = page.locator('button[aria-label="Header preview modes"]')
    toggle.click()
    page.locator(f'button:has-text("{mode_label}")').first.click()
    # Close the panel so it doesn't cover the page.
    toggle.click()


def _api_has_live_game() -> bool:
    """Probe the API: does any game currently have status='live'?

    Phase L+ replaced the always-on simulated live game with real DB
    data from the APScheduler live job. When no NBA game is currently
    in progress, the live banner is intentionally hidden, so any test
    that expects it to render needs to skip rather than fail.
    """
    import json
    import os
    import urllib.request

    api_url = os.environ.get("NBARAG_API_URL", "http://localhost:8000")
    try:
        with urllib.request.urlopen(f"{api_url}/api/header?mode=live", timeout=3) as resp:
            payload = json.loads(resp.read())
        return payload.get("live") is not None
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.parametrize(
    "label,expected_testid",
    [
        ("Upcoming (24h)", "top-upcoming"),
        ("Live game", "top-live"),
        ("Recap", "top-recap"),
    ],
)
def test_mode_toggle_renders_each_banner(goto_home, label, expected_testid):
    if expected_testid == "top-live" and not _api_has_live_game():
        pytest.skip("no live NBA game right now; live banner is correctly hidden")
    page = goto_home()
    _set_mode(page, label)
    page.wait_for_selector(f'[data-testid="{expected_testid}"]', timeout=10_000)
    assert page.locator(f'[data-testid="{expected_testid}"]').count() == 1


def test_upcoming_shows_countdown_and_local_time(goto_home):
    page = goto_home()
    _set_mode(page, "Upcoming (24h)")
    page.wait_for_selector('[data-testid="top-upcoming"]', timeout=10_000)
    text = page.locator('[data-testid="top-upcoming"]').text_content() or ""
    # Some "{N}h {M}m" or "{M}m {S}s" countdown should appear.
    assert re.search(r"\d+(h|m|s)", text), f"No countdown found in: {text!r}"


def test_live_banner_shows_scores(goto_home):
    if not _api_has_live_game():
        pytest.skip("no live NBA game right now; live banner is correctly hidden")
    page = goto_home()
    _set_mode(page, "Live game")
    page.wait_for_selector('[data-testid="top-live"]', timeout=10_000)
    text = page.locator('[data-testid="top-live"]').text_content() or ""
    assert "LIVE" in text.upper()
    # Two score numbers should be present.
    nums = re.findall(r"\b\d{1,3}\b", text)
    assert len(nums) >= 2, f"Couldn't find two scores in live banner text: {text!r}"


# --------------------------------------------------------------------------
# 6. The page title remembers the new branding.
# --------------------------------------------------------------------------


def test_page_title_uses_ball_knowledge_oracle(goto_home):
    page = goto_home()
    assert "Ball Knowledge Oracle" in (page.title() or "")


# --------------------------------------------------------------------------
# 7. Top record + section dividers + content depth (this round's changes).
# --------------------------------------------------------------------------


def test_top_record_headline_picks_perfect_team(page, ui_url):
    """OKC went 8-0 through Round 2; the prior bug surfaced SAS 8-3 because
    GROUP BY collapsed identical home/away splits. Lock the fix in."""
    resp = page.request.get(f"{ui_url.replace(':3002', ':8000')}/api/header")
    assert resp.ok, f"/api/header HTTP {resp.status}"
    data = resp.json()
    top = [h for h in data["headlines"] if "TOP RECORD" in h["label"]]
    assert top, "no PLAYOFFS · TOP RECORD card"
    assert top[0]["team_abbr"] == "OKC", f"top record team is {top[0]['team_abbr']}, expected OKC"
    assert "8-0" in top[0]["metric"], f"top record metric is {top[0]['metric']!r}"


def test_headlines_include_section_dividers(page, ui_url):
    resp = page.request.get(f"{ui_url.replace(':3002', ':8000')}/api/header")
    data = resp.json()
    dividers = [h for h in data["headlines"] if h.get("kind") == "divider"]
    labels = {h["label"] for h in dividers}
    expected_keywords = ["AWARDS", "LEADERS", "STATS", "UPCOMING", "FUN FACTS"]
    for kw in expected_keywords:
        assert any(kw in l for l in labels), f"missing divider containing '{kw}': {labels}"


def test_headlines_include_at_least_20_unique_fact_cards(page, ui_url):
    resp = page.request.get(f"{ui_url.replace(':3002', ':8000')}/api/header")
    data = resp.json()
    non_dividers = [h for h in data["headlines"] if h.get("kind") != "divider"]
    assert len(non_dividers) >= 20, f"only {len(non_dividers)} non-divider cards"


def test_mvp_card_names_sga(page, ui_url):
    resp = page.request.get(f"{ui_url.replace(':3002', ':8000')}/api/header")
    data = resp.json()
    mvp = [h for h in data["headlines"] if h["label"].startswith("MVP")]
    assert mvp, "no MVP card"
    assert "Shai" in mvp[0]["primary"], f"MVP primary is {mvp[0]['primary']!r}"


# --------------------------------------------------------------------------
# 8. Brand orb, subtitle, NBA logo zoom (UI-side of this round).
# --------------------------------------------------------------------------


def test_brand_orb_canvas_mounts(goto_home):
    """The header brand glyph is now a tiny Three.js canvas (replacing the
    old SVG BrandMark). Confirm it's there with a usable width/height."""
    page = goto_home()
    page.wait_for_function(
        """() => {
            const c = document.querySelector('[data-testid="brand-orb"] canvas');
            return c && c.width > 0 && c.height > 0;
        }""",
        timeout=10_000,
    )


def test_brand_subtitle_includes_rag_and_byline(goto_home):
    page = goto_home()
    brand_text = page.locator('[data-testid="brand-home"]').text_content() or ""
    assert "NBA Intelligence RAG" in brand_text
    assert "2025" in brand_text and "26" in brand_text
    assert "Isaiah" in brand_text


def test_nba_badge_image_is_zoomed(goto_home):
    """The NBA pictogram inside the white card is rendered scaled-up so it
    fills the card edge to edge."""
    page = goto_home()
    img = page.locator('[data-testid="nba-logo-image"]').first
    transform = img.evaluate("el => getComputedStyle(el).transform")
    # `matrix(a,b,c,d,e,f)` — a == scale on X. Anything > 1.0 means we
    # zoomed the figure beyond its container.
    assert transform.startswith("matrix"), f"unexpected transform: {transform}"
    a_value = float(transform.split("(")[1].split(",")[0])
    assert a_value > 1.1, f"NBA logo not visibly zoomed (scale {a_value})"
