#!/usr/bin/env python3
"""The two faces of Home (stranger hero rebuild, 6 Aug 2026).

A newcomer with no play history meets a hero built to convert: a real Face
Value board shown at the moment a round opens, one named game, one door, and
the other three games as compact rows underneath. A player with history meets
the classic Home — four full rows, week strips, back-issue bars, punch card —
and must never see any of the hero's furniture.

The two scenarios below are the fence between those states. The stranger one
also guards the things that break quietly: the demo image 404ing, the demo
image missing from the service worker's precache (which would leave the whole
hero blank offline), a second Face Value door creeping back in below the fold,
and the CTA's two analytics events drifting.
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
HERO_COPY = {
    ".stranger-headline": "who's under the paper?",
    ".stranger-caption": "face value: tear back the scraps. name the historical figure.",
    "#stranger-play": "play face value ›",
    ".stranger-reassure": "free · no sign-up",
    ".stranger-also": "also in today's issue",
}

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
        assert page.evaluate(
            "() => { const i = document.querySelector('.stranger-demo');"
            " return i.complete && i.naturalWidth > 0; }"), "the demo board never loaded"
        src = img.get_attribute("src")
        # Explicit dimensions: the box is reserved, so nothing below the
        # picture jumps while it downloads.
        assert img.get_attribute("width") and img.get_attribute("height"), \
            "the demo board has no intrinsic size — the hero will jump as it loads"
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


TESTS = [stranger_hero, stranger_rows_open_their_own_games, returning_home_unchanged]


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
