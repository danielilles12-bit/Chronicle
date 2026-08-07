#!/usr/bin/env python3
"""The two faces of Home (stranger hero rebuild, 6 Aug 2026).

A newcomer with no play history meets a hero built to convert: a real Face
Value board shown at the moment a round opens, one named game, one door, and
the other three games as compact rows underneath. A player with history meets
the classic Home — four full rows, week strips, back-issue bars, punch card —
and must never see any of the hero's furniture.

The scenarios below are the fence between those states. The stranger ones also
guard the things that break quietly: the demo image 404ing, the demo image
missing from the service worker's precache (which would leave the whole hero
blank offline), a second Face Value door creeping back in below the fold, the
CTA's two analytics events drifting — and, since 7 Aug 2026, the side-by-side
shape itself: headline in its own column to the LEFT of the four-square board,
nothing spilling off a 375px screen, and the door still above the fold.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
import helpers as H  # noqa: E402

N = H.latest_edition()
DATE = H.edition_date(N)

# The hero's copy, as a reader sees it. inner_text comes back CSS-uppercased,
# and the markup uses typographic apostrophes, so both are normalised away.
# The caption stopped naming Face Value on 7 Aug 2026 — the button underneath
# it already does, and twice is redundant.
HERO_COPY = {
    ".stranger-headline": "who's under the paper?",
    ".stranger-caption": "tear back the scraps. name the historical figure.",
    "#stranger-play": "play face value ›",
    ".stranger-reassure": "free · no sign-up",
    ".stranger-also": "also in today's issue",
}

# The screens the hero has to hold its shape on: the narrow phone the layout
# was designed against, and a tablet, where the app column stops growing.
SHAPES = [("phone", 375, 812), ("tablet", 768, 1024)]

# Where everything in the hero actually landed, in CSS pixels.
GEOMETRY = """() => {
  const box = (s) => { const r = document.querySelector(s).getBoundingClientRect();
    return {l: r.left, r: r.right, t: r.top, b: r.bottom, w: r.width, h: r.height}; };
  const doc = document.documentElement;
  return {
    hero: box('#stranger-hero'), head: box('.stranger-headline'),
    img: box('.stranger-demo'), cta: box('#stranger-play'),
    vh: innerHeight, scrollW: doc.scrollWidth, clientW: doc.clientWidth,
  };
}"""

# Contrast of the door's letters against its own plate. The magenta CTA
# inherited .pill.primary's cream text until Daniel called it on 7 Aug 2026:
# cream on print magenta is 2.7:1, the palest thing on a newcomer's screen.
# Ink on the same plate is 6.5:1, so 4.5 cleanly separates the two.
CTA_CONTRAST = """() => {
  const cs = getComputedStyle(document.querySelector('#stranger-play'));
  const lum = (c) => { const [r, g, b] = c.match(/\\d+/g).slice(0, 3).map(Number)
      .map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const a = lum(cs.color), b = lum(cs.backgroundColor);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}"""

# Row key -> (the one-liner it shows a newcomer, the view its tap must open).
OTHER_GAMES = [
    ("map", "birth. death. two dots. who?", "view-map"),
    ("what", "uncover an artefact. name it.", "view-reveal"),
    ("thread", "sort 16 terms into four groups.", "view-conn"),
]

# The classic Home's own taglines, which a returning player must still get.
CLASSIC_TAGLINES = {
    "who": "a famous face, one scrap at a time.",
    "map": "born here, died there. name the figure.",
    "what": "a famous artefact, one scrap at a time.",
    "thread": "group 16 clues into four hidden categories.",
}


def said(page, sel):
    return re.sub(r"[’‘]", "'", page.inner_text(sel)).strip().lower()


# ---------- stranger_hero ----------
def stranger_hero(p, base):
    """Fresh profile: the hero paints in full, its picture really loads, its
    door opens Face Value, and Face Value has exactly one door."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        page.wait_for_selector("#stranger-hero:not([hidden])")
        assert page.evaluate("document.body.classList.contains('is-stranger')")

        for sel, want in HERO_COPY.items():
            assert said(page, sel) == want, "%s reads %r, expected %r" % (sel, said(page, sel), want)

        # Five things and no sixth. A "GAME PREVIEW" stamp stood above the
        # headline until Daniel cut it on 6 Aug 2026: the picture explains
        # itself, and a label about the picture is one more thing to read
        # before the button. Nothing may take its place either.
        assert page.locator("#stranger-hero .df-stamp").count() == 0, \
            "a stamp is back above the headline"
        first = page.evaluate(
            "document.querySelector('#stranger-hero').firstElementChild.className")
        assert "stranger-headline" in first, \
            "something stands between the masthead and the headline: %r" % first

        # The demo board: fetched, decoded, painted — not a broken-image box.
        img = page.locator(".stranger-demo")
        img.wait_for(state="visible")
        natural = page.evaluate(
            "() => { const i = document.querySelector('.stranger-demo');"
            " return i.complete && i.naturalWidth > 0"
            "   ? [i.naturalWidth, i.naturalHeight] : null; }")
        assert natural, "the demo board never loaded"
        src = img.get_attribute("src")
        # Explicit dimensions, and TRUE ones: the box the page reserves has to
        # be the shape of the picture that lands in it, or the headline and the
        # button jump as it downloads. Re-shoot the asset at another size (the
        # 2x2 crop halved it on 7 Aug 2026) and this catches the stale markup.
        assert [img.get_attribute("width"), img.get_attribute("height")] == \
            [str(n) for n in natural], \
            "width/height say %s but the asset is %s — the reserved box is wrong" % (
                [img.get_attribute("width"), img.get_attribute("height")], natural)
        assert natural[0] == natural[1], \
            "the demo board is %s, not square — the scrap grid it is cut from is" % (natural,)
        # Offline is the house promise, and the hero is the whole screen for a
        # newcomer: the picture has to ship with the shell.
        with open(os.path.join(H.ROOT, "sw.js"), encoding="utf-8") as f:
            assert src in f.read(), "%s is not in the sw.js precache list" % src

        # No two doors to one game: Face Value's own row is gone from the
        # strip below, and exactly one tappable control on the page opens it.
        assert page.locator('[data-row="who"]').is_hidden(), \
            "Face Value has a second door below the hero"
        assert "face value" not in page.inner_text("#home-rows").lower(), \
            "Face Value is still named in the row strip below the hero"
        doors = page.evaluate(
            "() => [...document.querySelectorAll('#view-home button')]"
            "  .filter(b => b.offsetParent !== null"
            "            && /face value/i.test(b.innerText)).length")
        assert doors == 1, "%d tappable Face Value doors on the stranger's Home" % doors

        # The other three are present, in order, each with its newcomer line.
        rows = page.evaluate(
            "() => [...document.querySelectorAll('#home-rows .game-row')]"
            "  .filter(r => getComputedStyle(r).display !== 'none')"
            "  .map(r => r.dataset.row)")
        assert rows == [g for g, _, _ in OTHER_GAMES], rows
        for key, line, _view in OTHER_GAMES:
            assert said(page, '[data-row="%s"] .hero-tagline-new' % key) == line
        # The time whisper and the issue number are off this screen: it prices
        # nothing but the one game it is selling.
        assert page.locator('[data-row="map"] .hero-edition').is_hidden()

        # The door itself: same two events as before the rebuild, then Face Value.
        page.click("#stranger-play")
        page.wait_for_selector("#view-reveal:not([hidden])")
        assert page.evaluate("__CHRONICLE_TEST__.revealRound.kind") == "portrait", \
            "the CTA opened something other than Face Value"
        events = H.gc_events(page)
        for want in ("3-tapped-play-today", "3-started-facevalue"):
            assert want in events, "missing %s: %r" % (want, events)
        H.fail_on_errors(errors, "stranger_hero")


# ---------- stranger_hero_side_by_side ----------
def stranger_hero_side_by_side(p, base):
    """The 7 Aug shape: headline in its own column on the LEFT, the four-square
    board beside it on the RIGHT, their tops level so the torn square and the
    question read as one unit — on a narrow phone and on a tablet, with the
    door still above the fold and nothing hanging off the side."""
    for label, w, h in SHAPES:
        with H.app(p, context_args={"viewport": {"width": w, "height": h}}) \
                as (page, errors, _ctx):
            H.boot(page, base, DATE)
            page.wait_for_selector("#stranger-hero:not([hidden])")
            page.locator(".stranger-demo").wait_for(state="visible")
            page.wait_for_function(
                "() => { const i = document.querySelector('.stranger-demo');"
                " return i.complete && i.naturalWidth > 0; }")
            g = page.evaluate(GEOMETRY)
            why = "%s (%dx%d): " % (label, w, h)

            # Two columns, not a stack: the headline ENDS before the board
            # BEGINS, and neither is wide enough to be the full hero.
            assert g["head"]["r"] <= g["img"]["l"] + 0.5, \
                why + "the headline runs into the board (ends %.0f, board starts %.0f)" % (
                    g["head"]["r"], g["img"]["l"])
            assert g["img"]["l"] - g["head"]["r"] >= 8, \
                why + "only %.0fpx between the headline and the board" % (
                    g["img"]["l"] - g["head"]["r"])
            for name, part in (("headline", g["head"]), ("board", g["img"])):
                assert part["w"] < g["hero"]["w"] * 0.62, \
                    why + "the %s is %.0f of the hero's %.0f — the columns collapsed" % (
                        name, part["w"], g["hero"]["w"])
            # Headline on the left, board on the right — not the other way up.
            assert g["head"]["l"] < g["img"]["l"], why + "the board is left of the headline"

            # Level tops: the torn square is the board's top-left corner, so
            # the question sits right beside the hole it asks about.
            assert abs(g["head"]["t"] - g["img"]["t"]) <= 6, \
                why + "headline top %.0f vs board top %.0f — they don't read as one unit" % (
                    g["head"]["t"], g["img"]["t"])

            # Stacked, not one long line: several lines of big type.
            fs = float(page.evaluate(
                "getComputedStyle(document.querySelector('.stranger-headline')).fontSize")
                .replace("px", ""))
            lines = round(g["head"]["h"] / (fs * 0.94))
            assert lines >= 3, why + "the headline is only %d line(s) tall" % lines

            # A square board (it is cut from a square scrap grid), inside the
            # page, with no sideways scroll anywhere.
            assert abs(g["img"]["w"] - g["img"]["h"]) <= 1, \
                why + "the board renders %.0fx%.0f, not square" % (g["img"]["w"], g["img"]["h"])
            assert g["img"]["r"] <= g["hero"]["r"] + 0.5, why + "the board overhangs the gutter"
            assert g["scrollW"] <= g["clientW"], \
                why + "the page scrolls sideways (%d > %d)" % (g["scrollW"], g["clientW"])

            # The whole point of the rebuild: the door is visible without a
            # scroll, and its letters are legible on the magenta.
            assert g["cta"]["b"] <= g["vh"], \
                why + "the door ends at %.0f, below the %.0f fold" % (g["cta"]["b"], g["vh"])
            contrast = page.evaluate(CTA_CONTRAST)
            assert contrast >= 4.5, \
                why + "the door's letters are %.1f:1 against their own plate — ink, not cream" % contrast
            H.fail_on_errors(errors, "stranger_hero_side_by_side/%s" % label)


# ---------- stranger_rows_open_their_own_games ----------
def stranger_rows_open_their_own_games(p, base):
    """Each compact row is a real door into its own game, not decoration."""
    with H.app(p) as (page, errors, _ctx):
        for key, _line, view in OTHER_GAMES:
            H.boot(page, base, DATE)           # still a stranger: nothing finished
            page.wait_for_selector("#stranger-hero:not([hidden])")
            H.open_daily(page, key)
            H.dismiss_intro(page)
            page.wait_for_selector("#%s:not([hidden])" % view)
            if view == "view-reveal":
                assert page.evaluate("__CHRONICLE_TEST__.revealRound.kind") != "portrait", \
                    "the Relic row opened Face Value"
        H.fail_on_errors(errors, "stranger_rows_open_their_own_games")


# ---------- returning_home_unchanged ----------
def returning_home_unchanged(p, base):
    """One finished daily and Home is the classic screen again — all four
    games, their own taglines, and none of the hero's furniture."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        H.seed_completion(page, "thread", N, score=80,
                          detail={"solved": True, "perfect": False,
                                  "mistakes": 1, "guesses": []})
        H.boot(page, base, DATE)               # stranger mode is decided on render
        page.wait_for_selector("#stranger-hero", state="hidden")
        assert not page.evaluate("document.body.classList.contains('is-stranger')")

        # Every one of the hero's parts is off the page.
        for sel in list(HERO_COPY) + [".stranger-demo"]:
            assert page.locator(sel).is_hidden(), "%s survives into the classic Home" % sel

        # All four rows, in the house order, with the house taglines.
        rows = page.evaluate(
            "() => [...document.querySelectorAll('#home-rows .game-row')]"
            "  .filter(r => getComputedStyle(r).display !== 'none')"
            "  .map(r => r.dataset.row)")
        assert rows == ["who", "map", "what", "thread"], rows
        for key, tagline in CLASSIC_TAGLINES.items():
            assert said(page, '[data-row="%s"] .hero-tagline' % key) == tagline, \
                "%s row lost its tagline: %r" % (key, said(page, '[data-row="%s"] .hero-tagline' % key))
            assert page.locator('[data-row="%s"] .hero-tagline-new' % key).is_hidden(), \
                "the newcomer one-liner leaked into the classic %s row" % key

        # The regulars' furniture is all back.
        assert page.locator("#punch-card").is_visible()
        for key in CLASSIC_TAGLINES:
            assert page.locator('[data-row="%s"] [data-week]' % key).is_visible()
            assert page.locator('[data-archive="%s"]' % key).is_visible()
            assert page.locator('[data-row="%s"] .hero-edition' % key).is_visible()
        assert "№" in page.inner_text('[data-hero="who"] [data-edition]')

        # And the classic doors still work.
        page.click('[data-hero="who"]')
        page.wait_for_selector("#view-reveal:not([hidden])")
        assert page.evaluate("__CHRONICLE_TEST__.revealRound.kind") == "portrait"
        H.fail_on_errors(errors, "returning_home_unchanged")


TESTS = [stranger_hero, stranger_hero_side_by_side,
         stranger_rows_open_their_own_games, returning_home_unchanged]


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
    if failures:
        print("\n%d/%d scenarios failed: %s"
              % (len(failures), len(TESTS), ", ".join(n for n, _ in failures)))
        sys.exit(1)
    print("\nall %d scenarios passed" % len(TESTS))


if __name__ == "__main__":
    main()
