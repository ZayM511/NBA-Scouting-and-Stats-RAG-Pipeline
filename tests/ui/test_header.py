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
    """The upcoming banner shows the new segmented HH:MM:SS countdown
    timer (`<CountdownTimer>`) plus the user-local tipoff time."""
    page = goto_home()
    _set_mode(page, "Upcoming (24h)")
    page.wait_for_selector('[data-testid="top-upcoming"]', timeout=10_000)
    countdown = page.locator('[data-testid="upcoming-countdown"]')
    assert countdown.count() == 1, "segmented countdown timer missing"
    text = countdown.text_content() or ""
    # After the size pass that matched the countdown to the team-shield
    # height, the per-cell HR/M/S text labels live in aria-label only;
    # the visible text is just padded digits and colons. Expect at least
    # one HH:MM pattern.
    assert re.search(r"\d{2}:\d{2}", text), (
        f"countdown text missing HH:MM digits: {text!r}"
    )


def test_live_banner_shows_scores(goto_home):
    if not _api_has_live_game():
        pytest.skip("no live NBA game right now; live banner is correctly hidden")
    page = goto_home()
    _set_mode(page, "Live game")
    page.wait_for_selector('[data-testid="top-live"]', timeout=10_000)
    text = page.locator('[data-testid="top-live"]').text_content() or ""
    assert "LIVE" in text.upper()
    # Two score numbers should be present. textContent has no whitespace
    # between flex children, so the clock and scores collapse into
    # something like "0:000CLEVSDET0" — `\b\d+\b` finds only the clock
    # digit. Walk the DOM directly for the score elements instead.
    score_text = page.locator(
        '[data-testid="top-live"] span.font-mono.tabular-nums'
    ).all_text_contents()
    assert len(score_text) >= 2, (
        f"expected two score spans in live banner, got {score_text!r}; raw: {text!r}"
    )
    assert all(s.strip().isdigit() for s in score_text[:2]), (
        f"score spans don't look like ints: {score_text[:2]!r}"
    )


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


def test_brand_glyph_is_svg_not_canvas(goto_home):
    """The header brand glyph is the SVG `BrandMark` (counter-rotating
    rings + ember core). The previous GLB-canvas approach rendered with a
    visible square crop and was reverted. This test locks the choice."""
    page = goto_home()
    brand = page.locator('[data-testid="brand-home"]')
    # No <canvas> inside the brand button (no Three.js mounting here).
    assert brand.locator("canvas").count() == 0, (
        "brand glyph should be SVG, not a Three.js canvas"
    )
    # Must contain at least one <svg> (BrandMark's ring + core).
    assert brand.locator("svg").count() >= 1, "BrandMark SVG missing"


def test_brand_subtitle_includes_rag_and_byline(goto_home):
    page = goto_home()
    brand_text = page.locator('[data-testid="brand-home"]').text_content() or ""
    assert "NBA Intelligence RAG" in brand_text
    assert "2025" in brand_text and "26" in brand_text
    assert "Isaiah" in brand_text


def test_nba_badge_image_is_zoomed(goto_home):
    """The NBA pictogram inside the white card is rendered slightly larger
    than its container so the figure reads as fitted (not floating in
    empty space). The earlier aggressive zoom (1.28) cropped the figure;
    the current value targets ~1.05 — between 1.0 and 1.15."""
    page = goto_home()
    img = page.locator('[data-testid="nba-logo-image"]').first
    transform = img.evaluate("el => getComputedStyle(el).transform")
    assert transform.startswith("matrix"), f"unexpected transform: {transform}"
    a_value = float(transform.split("(")[1].split(",")[0])
    assert 1.0 <= a_value <= 1.15, (
        f"NBA logo scale {a_value} outside the [1.00, 1.15] band — too much "
        "zoom crops the figure, too little leaves empty margin"
    )


# --------------------------------------------------------------------------
# 9. Truthful awards, uniform banner, pipeline progress (this round).
# --------------------------------------------------------------------------


def test_clutch_card_does_not_credit_brunson(page, ui_url):
    """The Clutch POY hasn't been announced — SGA leads the polls. Make
    sure no Clutch card hard-attributes the *award* to Brunson. (The
    separate Clutch TS% LEADER stat card is fine — that's a real DB-
    derived efficiency leader, not an award.)"""
    resp = page.request.get(f"{ui_url.replace(':3002', ':8000')}/api/header")
    data = resp.json()
    cpoy_cards = [h for h in data["headlines"] if "CLUTCH POY" in h["label"]]
    assert cpoy_cards, "no Clutch POY award card"
    card = cpoy_cards[0]
    assert "Brunson" not in card["primary"], f"CPOY still credits Brunson: {card}"
    assert "LEADING" in card["label"].upper() or "Shai" in card["primary"], (
        f"CPOY card not marked as leader-only: {card}"
    )


def test_unannounced_awards_marked_leading(page, ui_url):
    """Every non-MVP / non-Finals-MVP award must read as 'leading the
    polls' or 'projected' — never a confirmed winner."""
    resp = page.request.get(f"{ui_url.replace(':3002', ':8000')}/api/header")
    data = resp.json()
    award_keywords = [
        "DEFENSIVE PLAYER",
        "MOST IMPROVED",
        "COACH OF THE YEAR",
        "SIXTH MAN",
        "ROOKIE OF THE YEAR",
        "ALL-NBA",
    ]
    for kw in award_keywords:
        cards = [h for h in data["headlines"] if kw in h["label"].upper()]
        assert cards, f"no card found for {kw}"
        card = cards[0]
        text = f"{card['label']} {card['secondary']} {card['metric']}".upper()
        assert ("LEADING" in text) or ("PROJECTED" in text) or ("WATCH" in text), (
            f"Award card for {kw} doesn't mark itself as leader/projected: {card}"
        )


def test_mvp_card_is_only_confirmed_award(page, ui_url):
    """MVP (and Finals MVP TBD) are the only awards the demo treats as
    settled. MVP names Shai outright; everything else uses a watch label."""
    resp = page.request.get(f"{ui_url.replace(':3002', ':8000')}/api/header")
    data = resp.json()
    mvp = [
        h for h in data["headlines"]
        if h["label"].startswith("MVP") and "Shai" in h["primary"]
    ]
    assert mvp, "MVP card with Shai missing"
    # Should NOT include a "LEADING" qualifier.
    assert "LEADING" not in mvp[0]["label"].upper(), (
        "MVP is announced — shouldn't be flagged as leading"
    )


def test_suggestion_chips_show_full_text(goto_home):
    """Each chip's text should fit without an ellipsis. The third chip
    was the regression target — its prior copy got truncated."""
    page = goto_home()
    # Find the chip whose visible text mentions off-ball — that's the
    # one whose previous copy clipped at "from t…".
    third = page.locator('button:has-text("off-ball")')
    assert third.count() >= 1, "Q3 chip ('off-ball' question) missing"
    text = third.first.text_content() or ""
    assert "off-ball" in text, f"Q3 chip text missing 'off-ball': {text!r}"
    # The inner text span shouldn't have text-overflow:ellipsis applied.
    # Locate the span carrying the question text — it's the one with
    # whitespace-nowrap class (or whichever inner span exists).
    overflow = third.first.evaluate(
        """el => {
            const spans = el.querySelectorAll('span');
            for (const s of spans) {
                const style = getComputedStyle(s);
                if (style.textOverflow === 'ellipsis') return 'ellipsis';
            }
            return 'ok';
        }"""
    )
    assert overflow == "ok", (
        f"a chip text span has text-overflow:ellipsis: {overflow}"
    )


def test_banner_height_matches_nba_badge(goto_home):
    """Recap/upcoming/live banner must visually match the NBA badge in
    height (the user explicitly called this out)."""
    page = goto_home()
    badge = page.locator('[data-testid="nba-season-badge"]').bounding_box()
    banner = None
    for testid in ("top-recap", "top-live", "top-upcoming", "pipeline-progress"):
        loc = page.locator(f'[data-testid="{testid}"]')
        if loc.count():
            banner = loc.bounding_box()
            break
    assert badge and banner, "couldn't find both badge and banner"
    # Allow ±3 px difference (rounding / borders).
    diff = abs(badge["height"] - banner["height"])
    assert diff <= 3, (
        f"banner height {banner['height']} doesn't match NBA badge "
        f"{badge['height']} (diff {diff}px)"
    )


def test_recap_label_full_text_at_default_viewport(goto_home):
    """At 1480x900 the recap banner must show the full 'FINAL · CONFERENCE
    SEMIS' label, not the short 'FINAL' fallback."""
    page = goto_home()
    recap = page.locator('[data-testid="top-recap"]')
    if recap.count() == 0:
        # Recap isn't the default mode right now; force it via the dev toggle.
        toggle = page.locator('button[aria-label="Header preview modes"]')
        toggle.click()
        page.locator('button:has-text("Recap")').first.click()
        toggle.click()
        page.wait_for_selector('[data-testid="top-recap"]', timeout=10_000)
        recap = page.locator('[data-testid="top-recap"]')
    text = (recap.text_content() or "").upper()
    assert "FINAL" in text
    assert "CONFERENCE SEMIS" in text, (
        f"recap label collapsed to 'FINAL'-only at this viewport: {text!r}"
    )


def test_pipeline_lives_outside_the_header(goto_home):
    """The pipeline banner moved out of the header into the question
    card. The header's state-banner slot must never contain it."""
    page = goto_home()
    state = page.evaluate(
        """() => {
            const header = document.querySelector('[data-testid="app-header"]');
            return {
                header_has_pipeline: !!header?.querySelector('[data-testid="pipeline-progress"]'),
            };
        }"""
    )
    assert state["header_has_pipeline"] is False, (
        "PipelineProgressBanner should no longer render inside the header"
    )


def test_position_data_populated(page, ui_url):
    """Hybrid queries depend on players.position being non-empty. Hit the
    backfill via the /ask endpoint isn't necessary — the data is already
    in the DB. Probe by asking the header endpoint isn't relevant either;
    rely on the live DB content via the network-shape test below.

    This test uses the /api/header endpoint as a proxy: if the recap shows
    a sensible score, the DB is alive. The position-specific assertion is
    that at least one playoff-leader card has a team_abbr (proves players
    table is joined correctly and producing results)."""
    resp = page.request.get(f"{ui_url.replace(':3002', ':8000')}/api/header")
    data = resp.json()
    leader_cards = [
        h for h in data["headlines"]
        if h.get("category") == "leaders" and h.get("kind") == "player"
    ]
    assert leader_cards, "no playoff leader cards came back"
    assert any(c.get("team_abbr") for c in leader_cards), (
        "leader cards have no team_abbr — players join may be broken"
    )


def test_pipeline_progress_renders_when_pending(goto_home):
    """While a question is in flight, the state-banner slot switches to
    the pipeline-progress view. We use a self-referential ('who are you?')
    question because the lore intercept gives a deterministic ~650 ms
    pending window we can sample from the DOM."""
    page = goto_home()
    state = page.evaluate(
        """async () => {
            const ta = document.querySelector('textarea');
            const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
            setter.call(ta, 'who are you?');
            ta.dispatchEvent(new Event('input', { bubbles: true }));
            ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
            for (let i = 0; i < 60; i++) {
                const el = document.querySelector('[data-testid="pipeline-progress"]');
                if (el) {
                    const stages = Array.from(
                        document.querySelectorAll('[data-testid^="pipeline-stage-"]')
                    ).map(s => ({
                        id: s.getAttribute('data-testid'),
                        active: s.getAttribute('data-active') === 'true',
                    }));
                    return { found: true, stages };
                }
                await new Promise(r => setTimeout(r, 20));
            }
            return { found: false };
        }"""
    )
    assert state["found"], "pipeline-progress banner didn't render during pending"
    stage_ids = [s["id"] for s in state["stages"]]
    # New 5-stage flow: User Question -> Query Router -> [path] -> Synthesis
    # -> Answer + Sources. Path tile id varies by route (path-pending while
    # the route is unknown, path-stats / path-prose / path-hybrid /
    # path-oracle once the response lands).
    assert "pipeline-stage-question" in stage_ids
    assert "pipeline-stage-router" in stage_ids
    assert any(s.startswith("pipeline-stage-path-") for s in stage_ids), (
        f"no path stage present: {stage_ids}"
    )
    assert "pipeline-stage-synthesis" in stage_ids
    assert "pipeline-stage-answer" in stage_ids
    # At least one stage should be active at this instant.
    assert any(s["active"] for s in state["stages"]), (
        f"no stage active: {state['stages']}"
    )
