#!/usr/bin/env python3
"""No dead ends — the navigation contract (Daniel, 5 Aug 2026).

THE RULE (CLAUDE.md architecture rules; HOUSE_RULES.md "Navigation"):

    Every surface except Home carries exactly one always-visible way back,
    top-left, in the house ‹ chip language, reachable without scrolling.
    Moment screens comply via their centred Home CTA above the fold.

Why a test and not a habit: the app is deliberately hub-and-spoke — Home is
the hub, there is no menu and no tab bar — so a screen without a way back is
a trap, not a cosmetic omission. Two shipped that way inside a fortnight (the
intro overlay, then the reading pages) because "the way back" was a habit
rather than a law. This file is the law.

WHAT COUNTS AS COMPLIANT — three shapes, checked differently:

  chip    A ‹ button/link whose TOP EDGE sits in the top 25% of the viewport
          and in the left half of it, visible with the page unscrolled. Every
          view's topbar, the intro overlay, and the reading pages.
  moment  A centred CTA that lands you Home, wholly above the fold. The
          celebration/obituary screen and 404 — screens with no topbar chip
          by design, where the way out is the loud button.
  close   Sheets and overlays are not surfaces: they get an explicit Close,
          visible above the fold, that returns you to the surface underneath.

Every check has two halves: (a) the affordance is where the contract says it
is, and (b) ACTIVATING it actually lands you back on Home (or, for help
overlays and sheets, on the surface underneath). An affordance that exists
but goes nowhere is still a dead end.

Coverage is enforced, not curated: WAYS_BACK must name every .view in
index.html, so adding a view without registering its way back fails here.
Screens that only the QA panel can summon (?qa=1) are forced through it; any
that cannot be summoned headlessly log a SKIP notice rather than passing
silently.

Gotcha kept from earlier sessions: inner_text() is CSS-uppercased, so all
text matching here is case-insensitive.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
import helpers as H  # noqa: E402

N = H.latest_edition()
DATE = H.edition_date(N)

TOP_BAND = 0.25          # "top ~25% of the viewport"
LEFT_EDGE = 0.25         # "top-LEFT": anchored in the left quarter. The chip
                         # itself may be wide (the reading pages' reads
                         # "‹ Back to the games"); what the contract fixes is
                         # the corner it starts in, not how far it runs.
CHIP_GLYPH = "‹"    # ‹ — the house back-chip language

SKIPS = []               # surfaces the QA panel could not summon headlessly


# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------
def viewport(page):
    return page.evaluate("() => ({w: window.innerWidth, h: window.innerHeight})")


def visible_box(page, sel, label, timeout=5000):
    loc = page.locator(sel).first
    try:
        loc.wait_for(state="visible", timeout=timeout)
    except Exception:
        raise AssertionError("%s: no visible way back (%s)" % (label, sel))
    box = loc.bounding_box()
    assert box, "%s: %s has no box" % (label, sel)
    return box


def assert_unscrolled(page, label):
    """'Reachable without scrolling' — nothing here may need a swipe first."""
    y = page.evaluate("() => window.scrollY || 0")
    assert y == 0, "%s: measured after the page scrolled %spx" % (label, y)


def assert_chip(page, sel, label):
    """Top-left, top quarter, unscrolled, and speaks ‹."""
    assert_unscrolled(page, label)
    box = visible_box(page, sel, label)
    v = viewport(page)
    assert box["y"] >= 0, "%s: way back is off the top of the screen" % label
    assert box["y"] <= TOP_BAND * v["h"], (
        "%s: way back sits %.0f%% down the screen — the contract says the top "
        "%.0f%% (top edge at y=%.0f of %dpx)"
        % (label, 100.0 * box["y"] / v["h"], 100 * TOP_BAND, box["y"], v["h"]))
    assert 0 <= box["x"] <= LEFT_EDGE * v["w"], (
        "%s: way back is not anchored top-LEFT (starts at x=%.0f of %dpx)"
        % (label, box["x"], v["w"]))
    text = page.locator(sel).first.inner_text().strip()
    assert CHIP_GLYPH in text, (
        "%s: way back should speak the house ‹ chip language, reads %r"
        % (label, text))


def assert_moment_cta(page, sel, label):
    """A moment screen's centred Home CTA: wholly above the fold, centred."""
    assert_unscrolled(page, label)
    box = visible_box(page, sel, label)
    v = viewport(page)
    assert box["y"] >= 0 and box["y"] + box["height"] <= v["h"], (
        "%s: the Home CTA is not above the fold (y=%.0f–%.0f of %dpx)"
        % (label, box["y"], box["y"] + box["height"], v["h"]))
    centre = box["x"] + box["width"] / 2.0
    assert abs(centre - v["w"] / 2.0) <= 0.08 * v["w"], (
        "%s: the Home CTA is not centred (centre x=%.0f of %dpx)"
        % (label, centre, v["w"]))


def assert_close(page, sel, label):
    """A sheet's explicit Close: visible, above the fold, no scrolling."""
    assert_unscrolled(page, label)
    box = visible_box(page, sel, label)
    v = viewport(page)
    assert box["y"] >= 0 and box["y"] + box["height"] <= v["h"], (
        "%s: the Close is not above the fold (y=%.0f–%.0f of %dpx)"
        % (label, box["y"], box["y"] + box["height"], v["h"]))


def top_left_controls(page, view_id):
    """Every visible control this view's header puts in the top-left corner.

    'Exactly one way back' is only meaningful if there is exactly one thing to
    tap there — two chips is as confusing as none. Scoped to the header
    because that is where the corner lives: a view walked cold has an empty
    body, and empty bodies float their own buttons up the screen.
    """
    return page.evaluate(
        """(args) => {
          const view = document.getElementById(args.id);
          if (!view) return [];
          const scope = view.querySelector('header') || view;
          const band = window.innerHeight * args.band;
          const left = window.innerWidth * args.left;
          return Array.from(scope.querySelectorAll('button, a[href], [role="button"]'))
            .filter(el => {
              if (el.hidden || el.closest('[hidden]')) return false;
              const r = el.getBoundingClientRect();
              if (!r.width || !r.height) return false;
              return r.top >= 0 && r.top <= band && r.left <= left;
            })
            .map(el => (el.id || el.className || el.tagName));
        }""",
        {"id": view_id, "band": TOP_BAND, "left": LEFT_EDGE})


def visible_views(page):
    return page.evaluate(
        "() => Array.from(document.querySelectorAll('.view'))"
        ".filter(v => !v.hidden).map(v => v.id)")


def assert_on(page, view_id, label):
    try:
        page.wait_for_selector("#%s:not([hidden])" % view_id, timeout=6000)
    except Exception:
        raise AssertionError(
            "%s: expected to land on %s, stuck on %r"
            % (label, view_id, visible_views(page)))
    seen = visible_views(page)
    assert seen == [view_id], "%s: expected %s, showing %r" % (label, view_id, seen)


# ---------------------------------------------------------------------------
# the QA forcing panel (?qa=1) — see js/qa.js
# ---------------------------------------------------------------------------
def qa_body(page, want_open):
    """The panel is pinned to the bottom of the screen and eats taps, so it
    is collapsed before anything underneath it is measured or clicked."""
    is_open = not page.evaluate(
        "() => document.querySelector('#qa-panel .qa-body').hasAttribute('hidden')")
    if is_open != want_open:
        page.click("#qa-panel .qa-toggle")


def qa_force(page, label, wait_selector):
    """Summon a one-shot screen. Returns False (and logs a SKIP) if the panel
    cannot produce it headlessly, so a missing screen never passes silently."""
    qa_body(page, True)
    try:
        page.click("#qa-panel .qa-btn:has-text('%s')" % label, timeout=4000)
        page.wait_for_selector(wait_selector, timeout=6000)
    except Exception as e:
        SKIPS.append("%s (QA panel could not summon it headlessly: %s)"
                     % (label, str(e).splitlines()[0][:80]))
        print("   SKIP: %s could not be forced headlessly" % label)
        qa_body(page, False)
        return False
    qa_body(page, False)
    return True


# ---------------------------------------------------------------------------
# 1. every view in index.html
# ---------------------------------------------------------------------------
# view id -> (selector for its way back, shape). view-home is the hub and is
# deliberately absent. view-mapstart/view-revealstart have no UI route today
# (free play moved behind Archive → practice) but are still shipped views, so
# they are still held to the contract — reached through the test-only router
# hook (__CHRONICLE_TEST__.nav.show).
WAYS_BACK = [
    ("view-mapstart", "#view-mapstart [data-back]", "chip"),
    ("view-map", "#map-quit", "chip"),
    ("view-mapsum", "#sum-back", "chip"),
    ("view-revealstart", "#view-revealstart [data-back]", "chip"),
    ("view-reveal", "#rv-quit", "chip"),
    ("view-revealsum", "#rv-sum-back", "chip"),
    ("view-conn", "#conn-quit", "chip"),
    ("view-connsum", "#conn-sum-back", "chip"),
    ("view-daydone", "#dd-home", "moment"),
    ("view-archive", "#view-archive [data-back]", "chip"),
    ("view-ledger", "#view-ledger [data-back]", "chip"),
]


def every_view(p, base):
    """Walk every .view in index.html: each one's way back is where the
    contract says, and each one lands on Home."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        ids = page.evaluate(
            "() => Array.from(document.querySelectorAll('.view')).map(v => v.id)")
        registered = set(v for v, _, _ in WAYS_BACK) | {"view-home"}
        missing = set(ids) - registered
        assert not missing, (
            "new view(s) with no registered way back: %s — add them to "
            "WAYS_BACK (and give them a ‹ chip)" % ", ".join(sorted(missing)))
        stale = registered - set(ids) - {"view-home"}
        assert not stale, "WAYS_BACK names views that no longer exist: %s" % stale

        for view_id, sel, shape in WAYS_BACK:
            page.evaluate("id => __CHRONICLE_TEST__.nav.show(id)", view_id)
            assert_on(page, view_id, view_id)
            if shape == "chip":
                assert_chip(page, sel, view_id)
                controls = top_left_controls(page, view_id)
                assert len(controls) == 1, (
                    "%s: expected exactly ONE way back top-left, found %d: %r"
                    % (view_id, len(controls), controls))
            else:
                assert_moment_cta(page, sel, view_id)
            page.click(sel)
            assert_on(page, "view-home", "%s -> back" % view_id)
        H.fail_on_errors(errors, "every_view")


# ---------------------------------------------------------------------------
# 2. the live game views (real content, real session)
# ---------------------------------------------------------------------------
GAMES = [
    ("who", "#view-reveal", "#rv-quit", "#rv-help"),
    ("map", "#view-map", "#map-quit", "#map-help"),
    ("what", "#view-reveal", "#rv-quit", "#rv-help"),
    ("thread", "#view-conn", "#conn-quit", "#conn-help"),
]


def live_rounds(p, base):
    """Each game's round view, opened for real: the topbar ‹ is in the corner
    and quits to Home; the "?" help overlay's ‹ returns to the round."""
    for game, view, chip, help_btn in GAMES:
        with H.app(p) as (page, errors, _ctx):
            H.boot(page, base, DATE)
            H.open_daily(page, game)
            H.dismiss_intro(page, timeout=2500)
            page.wait_for_selector(view + ":not([hidden])")
            assert_chip(page, chip, "%s round" % game)

            # Help mode: the intro reopens over the live round. Its ‹ must put
            # the round back exactly as it was — the PRIOR surface, not Home.
            page.click(help_btn)
            page.wait_for_selector("#intro-card:not([hidden])")
            assert_chip(page, "#intro-back", "%s intro (help mode)" % game)
            page.click("#intro-back")
            page.wait_for_selector("#intro-card", state="hidden")
            assert_on(page, view.lstrip("#"), "%s help -> round" % game)

            page.click(chip)
            assert_on(page, "view-home", "%s round -> back" % game)
            H.fail_on_errors(errors, "live_rounds:%s" % game)


def first_run_intro(p, base):
    """The first-run intro overlay: ‹ goes Home, and costs nothing — the card
    is not marked seen, so the next tap on the game shows it again."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        H.open_daily(page, "map")
        page.wait_for_selector("#intro-card:not([hidden])")
        assert_chip(page, "#intro-back", "intro (first run)")
        page.click("#intro-back")
        page.wait_for_selector("#intro-card", state="hidden")
        assert_on(page, "view-home", "intro first run -> back")
        assert not page.evaluate(
            "() => (__CHRONICLE_TEST__.store.getMisc().introSeen || {}).map"), (
            "backing out of the first-run intro should not mark it seen")
        H.fail_on_errors(errors, "first_run_intro")


def played_summary(p, base):
    """A summary reached by actually finishing a daily still has its chip, and
    the chip goes Home (not back into the spent round)."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        H.open_daily(page, "who")
        H.dismiss_intro(page, timeout=1200)
        H.play_reveal_daily(page)
        assert_chip(page, "#rv-sum-back", "Face Value summary (played)")
        page.click("#rv-sum-back")
        assert_on(page, "view-home", "played summary -> back")
        H.fail_on_errors(errors, "played_summary")


# ---------------------------------------------------------------------------
# 3. ledger, archive, and the sheets that open over them
# ---------------------------------------------------------------------------
def ledger_and_sheets(p, base):
    """Your Legacy and Back Issues carry chips; the carry sheet and the
    archive picker carry a Close that returns to the surface underneath."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        page.click("#ledger-link")
        assert_on(page, "view-ledger", "ledger")
        assert_chip(page, "#view-ledger [data-back]", "Your Legacy")

        page.click("#carry-open")
        page.wait_for_selector("#carry-sheet:not([hidden])")
        assert_close(page, "#carry-close", "carry sheet")
        page.click("#carry-close")
        page.wait_for_selector("#carry-sheet", state="hidden")
        assert_on(page, "view-ledger", "carry close -> ledger")

        page.click("#view-ledger [data-back]")
        assert_on(page, "view-home", "ledger -> back")

        # The archive bar is regulars' furniture: one completed daily, then a
        # reload, takes the page out of stranger mode.
        H.seed_completion(page, "thread", N, score=80,
                          detail={"solved": True, "perfect": False,
                                  "mistakes": 1, "guesses": []})
        H.boot(page, base, DATE)
        page.click('[data-archive="who"]')
        assert_on(page, "view-archive", "archive")
        assert_chip(page, "#view-archive [data-back]", "Back Issues")

        page.click('#archive-list [data-edition="%d"]' % (N - 1))
        page.wait_for_selector("#archive-picker:not([hidden])")
        assert_close(page, "#archive-picker-close", "archive picker sheet")
        page.click("#archive-picker-close")
        page.wait_for_selector("#archive-picker", state="hidden")
        assert_on(page, "view-archive", "picker close -> archive")

        page.click("#view-archive [data-back]")
        assert_on(page, "view-home", "archive -> back")
        H.fail_on_errors(errors, "ledger_and_sheets")


# ---------------------------------------------------------------------------
# 4. the one-shot screens, forced through the QA panel
# ---------------------------------------------------------------------------
def moment_screens(p, base):
    """Celebration and obituary: no topbar chip by design, so the contract is
    met by the centred Home CTA above the fold — and it must work."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE, extra="&qa=1")
        page.wait_for_selector("#qa-panel")
        for label in ("Full-house celebration", "Streak obituary"):
            if not qa_force(page, label, "#view-daydone:not([hidden])"):
                continue
            assert_moment_cta(page, "#dd-home", label)
            # The × in the topbar is the second door on these screens; it is
            # always visible, so check it is really there and really closes.
            assert page.locator("#dd-close").is_visible(), (
                "%s: the topbar × is missing" % label)
            page.click("#dd-home")
            assert_on(page, "view-home", "%s -> Home" % label)
        H.fail_on_errors(errors, "moment_screens")


def home_strips(p, base):
    """The install pitch and the edition-closed strip are not surfaces — they
    are strips ON Home, the hub. Forcing them must leave you on Home, with
    Home's own furniture intact and the pitch dismissable."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE, extra="&qa=1")
        page.wait_for_selector("#qa-panel")

        if qa_force(page, "Install pitch", "#install-tip:not([hidden])"):
            assert_on(page, "view-home", "install pitch")
            assert page.locator("#install-tip-close").is_visible(), (
                "the install pitch has no dismiss")
            page.click("#install-tip-close")
            page.wait_for_selector("#install-tip", state="hidden")
            assert_on(page, "view-home", "install pitch dismissed")

        if qa_force(page, "Edition-closed strip", "#issue-closed:not([hidden])"):
            assert_on(page, "view-home", "edition-closed strip")
            assert page.locator("#home-rows .game-row").count() == 4, (
                "the edition-closed strip should sit above Home, not replace it")

        if qa_force(page, "New edition bar", "#new-edition"):
            assert_on(page, "view-home", "new edition bar")
        H.fail_on_errors(errors, "home_strips")


# ---------------------------------------------------------------------------
# 5. the static pages (no app shell, no router)
# ---------------------------------------------------------------------------
def reading_page_files():
    """The reading pages, DISCOVERED rather than listed — a page added later
    cannot quietly skip the contract, which is how the last two dead ends got
    in. A reading page is a root-level .html using the .page-main shell;
    index.html and 404.html have their own shapes and their own scenarios.

    Tracked files only: an uncommitted draft in a working tree is not shipping
    yet, and CI would not see it either. It comes under the contract the
    moment it is committed.
    """
    import subprocess
    names = []
    try:
        out = subprocess.run(["git", "ls-files", "*.html"], cwd=H.ROOT,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=30)
        candidates = [n for n in out.stdout.decode("utf-8").split()
                      if "/" not in n] if out.returncode == 0 else []
    except Exception:
        candidates = []
    if not candidates:                       # no git: fall back to the folder
        candidates = [n for n in os.listdir(H.ROOT) if n.endswith(".html")]
    for name in sorted(candidates):
        with open(os.path.join(H.ROOT, name), encoding="utf-8") as f:
            if 'class="page-main"' in f.read():
                names.append(name)
    return names


def reading_pages(p, base):
    """Every reading page: a ‹ chip under the masthead that goes to the app.
    The bottom .page-nav does not count — Sources is ~900 rows long and the
    installed app has no browser chrome to fall back on."""
    pages = reading_page_files()
    assert len(pages) >= 5, (
        "only found %d reading pages (%r) — discovery is broken, and a broken "
        "discovery tests nothing" % (len(pages), pages))
    print("   pages:", ", ".join(pages))
    with H.app(p) as (page, errors, _ctx):
        for f in pages:
            page.goto(base + "/" + f)
            page.wait_for_selector(".page-back a")
            assert_chip(page, ".page-back a", f)
            page.click(".page-back a")
            # #view-home carries no [hidden] in the markup, so waiting on the
            # view alone would pass before the app had booted: wait for the
            # marker renderGameRows sets once Home's furniture is built. Not
            # the rows themselves — a newcomer's Face Value row is hidden
            # behind the stranger hero, and it is the first one in the DOM.
            page.wait_for_selector("#home-rows[data-built]", timeout=15000)
            assert page.locator("#home-rows .game-row").count() == 4, (
                "%s: the way back did not land on a painted Home" % f)
        H.fail_on_errors(errors, "reading_pages")


def not_found(p, base):
    """404: no topbar, so the loud centred pill is the way back — above the
    fold, and it really goes home."""
    with H.app(p) as (page, errors, _ctx):
        page.goto(base + "/404.html")
        page.wait_for_selector(".notfound-main a.pill")
        assert_moment_cta(page, ".notfound-main a.pill", "404")
        text = page.inner_text(".notfound-main a.pill").lower()
        assert "back" in text, "404 pill should say where it goes, reads %r" % text
        page.click(".notfound-main a.pill")
        page.wait_for_selector("#home-rows[data-built]", timeout=15000)
        H.fail_on_errors(errors, "not_found")


# ---------------------------------------------------------------------------
# 6. the OS back gesture (Android back button / iPhone swipe-back)
# ---------------------------------------------------------------------------
def os_back_gesture(p, base):
    """The phone's own back must walk the app's views, not leave the app.
    js/app.js pushes a history entry per view enter and pops the trail on
    popstate; this is the guard on that wiring."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        H.open_daily(page, "who")
        H.dismiss_intro(page, timeout=1200)
        page.wait_for_selector("#view-reveal:not([hidden])")
        assert page.evaluate("() => __CHRONICLE_TEST__.nav.trail().length") == 2, (
            "entering a game should push one entry onto the view trail")
        page.go_back()
        assert_on(page, "view-home", "OS back from a game")

        # Two views deep: back walks them one at a time, in order.
        page.click("#ledger-link")
        assert_on(page, "view-ledger", "ledger")
        page.evaluate("() => __CHRONICLE_TEST__.nav.show('view-archive')")
        assert_on(page, "view-archive", "archive")
        page.go_back()
        assert_on(page, "view-ledger", "OS back -> prior surface")
        page.go_back()
        assert_on(page, "view-home", "OS back -> Home")
        H.fail_on_errors(errors, "os_back_gesture")


def chip_after_going_home(p, base):
    """Regression, 5 Aug 2026. Some screens send you Home outright rather than
    one step back (every summary's ‹, the moment screens' Home CTA). After one
    of those, the NEXT view's chip must still work on the FIRST tap.

    It did not: goHome() emptied the view trail but left the browser-history
    entry claiming its old depth, so the following view pushed a shallower
    depth on top of a deeper one and back() walked into an entry that popped
    nothing. The chip looked fine and did nothing — the exact failure the
    navigation contract exists to prevent."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        page.evaluate("() => __CHRONICLE_TEST__.nav.show('view-mapsum')")
        assert_on(page, "view-mapsum", "summary")
        page.click("#sum-back")                       # goHome(), not back()
        assert_on(page, "view-home", "summary -> Home")

        page.click("#ledger-link")
        assert_on(page, "view-ledger", "Home -> Your Legacy")
        page.click("#view-ledger [data-back]")        # ONE tap
        assert_on(page, "view-home", "Your Legacy -> ‹ on the first tap")
        H.fail_on_errors(errors, "chip_after_going_home")


TESTS = [every_view, live_rounds, first_run_intro, played_summary,
         ledger_and_sheets, moment_screens, home_strips, reading_pages,
         not_found, os_back_gesture, chip_after_going_home]


def main():
    failures = []
    with H.server() as base, sync_playwright() as p:
        for t in TESTS:
            print("--", t.__name__)
            try:
                t(p, base)
                print("   PASS")
            except Exception as e:
                failures.append((t.__name__, e))
                print("   FAIL:", e)
    for s in SKIPS:
        print("NOTICE skipped: %s" % s)
    if failures:
        print("\n%d/%d scenarios failed: %s"
              % (len(failures), len(TESTS), ", ".join(n for n, _ in failures)))
        sys.exit(1)
    print("\nall %d scenarios passed" % len(TESTS))


if __name__ == "__main__":
    main()
