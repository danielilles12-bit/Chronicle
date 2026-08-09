#!/usr/bin/env python3
"""The two faces of Home (stranger hero rebuild, 6 Aug 2026).

A newcomer with no play history meets a hero built to convert: a real Face
Value board shown at the moment a round opens, one named game, one door, and
the other three games as compact rows underneath. A player with history meets
the classic Home — four full rows, the punch card, and each row's Archive of
past-day cards — and must never see any of the hero's furniture.

The scenarios below are the fence between those states. The stranger ones also
guard the things that break quietly: the demo image 404ing, the demo image
missing from the service worker's precache (which would leave the whole hero
blank offline), a second Face Value door creeping back in below the fold, the
CTA's two analytics events drifting — and, since 7 Aug 2026, the side-by-side
shape itself: headline in its own column to the LEFT of the four-square board,
the caption stacked directly under that headline in the same column, a board
big enough to be the picture the screen is selling, nothing spilling off a
375px screen, and the door still above the fold.
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
    ".stranger-headline": "who's under the scraps?",
    ".stranger-caption": "tear them away. name the historical figure.",
    "#stranger-play": "play face value ›",
    ".stranger-reassure": "free · no sign-up",
    ".stranger-also": "also in today's issue",
}

# The screens the hero has to hold its shape on: the narrow phone the layout
# was designed against, and a tablet, where the app column stops growing.
SHAPES = [("phone", 375, 812), ("tablet", 768, 1024)]

# Where everything in the hero actually landed, in CSS pixels. capLines counts
# the caption's rendered line boxes — the only honest way to ask "did it wrap
# where we meant it to", since the answer depends on the font that loaded.
GEOMETRY = """() => {
  const box = (s) => { const r = document.querySelector(s).getBoundingClientRect();
    return {l: r.left, r: r.right, t: r.top, b: r.bottom, w: r.width, h: r.height}; };
  const rg = document.createRange();
  rg.selectNodeContents(document.querySelector('.stranger-caption'));
  const doc = document.documentElement;
  return {
    hero: box('#stranger-hero'), head: box('.stranger-headline'),
    cap: box('.stranger-caption'),
    img: box('.stranger-demo'), cta: box('#stranger-play'),
    capLines: rg.getClientRects().length,
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
    "who": "tear back the scraps to reveal a historical figure.",
    "map": "birth. death. two pins on the map. who?",
    "what": "tear back the scraps to reveal a historical artefact or landmark.",
    "thread": "sort 16 clues into four groups, each with a hidden connection.",
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
        # 2x2 crop halved it to 600px on 7 Aug 2026, then the sharper Commons
        # original took it to 900px the same day) and this catches the stale
        # markup left behind in index.html.
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
    """The 7 Aug shape: headline in its own column on the LEFT with the caption
    stacked under it, the four-square board beside them on the RIGHT, their tops
    level so the torn square and the question read as one unit — on a narrow
    phone and on a tablet, with the door still above the fold and nothing
    hanging off the side."""
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

            # Stacked, not one long line: several lines of big type. Four is
            # the intent (WHO'S / UNDER / THE / SCRAPS?); five means the clamp
            # outgrew its column and "SCRAPS?" hyphenated, which looks broken.
            fs = float(page.evaluate(
                "getComputedStyle(document.querySelector('.stranger-headline')).fontSize")
                .replace("px", ""))
            lines = round(g["head"]["h"] / (fs * 0.94))
            assert 3 <= lines <= 4, why + "the headline is %d lines tall" % lines

            # THE CAPTION RIDES WITH THE HEADLINE (Daniel, 7 Aug 2026): same
            # column, same left edge, directly underneath — not spanning the
            # full width below the board, and never pushed away from the
            # headline by the board's spare height (grid-template-rows).
            assert abs(g["cap"]["l"] - g["head"]["l"]) <= 1, \
                why + "caption starts at %.0f but the headline at %.0f — different columns" % (
                    g["cap"]["l"], g["head"]["l"])
            assert g["cap"]["r"] <= g["img"]["l"] + 0.5, \
                why + "the caption runs under the board (ends %.0f, board starts %.0f)" % (
                    g["cap"]["r"], g["img"]["l"])
            gap = g["cap"]["t"] - g["head"]["b"]
            assert 0 <= gap <= 24, \
                why + "%.0fpx between headline and caption — they stop reading as one block" % gap
            # "About two lines" (Daniel's words): two where the column allows,
            # three on the narrowest phones. One means it stretched into a
            # banner, four means it has become a paragraph.
            assert 2 <= g["capLines"] <= 3, \
                why + "the caption wrapped over %d lines" % g["capLines"]

            # The board is the thing being sold, so it holds its half: it was
            # enlarged on 7 Aug and must not quietly shrink back.
            assert g["img"]["w"] >= g["hero"]["w"] * 0.48, \
                why + "the board is %.0f of the hero's %.0f — it has shrunk" % (
                    g["img"]["w"], g["hero"]["w"])

            # SHARP ON A GOOD PHONE. This is the first picture of the product
            # anyone sees, and a modern screen draws three device pixels per
            # CSS pixel — so the file has to carry 3x whatever it is drawn at.
            # The tablet shape is the binding one: the board stops growing at
            # its CSS cap, and the asset is cut to exactly 3x that. Enlarge the
            # board without re-shooting the asset and this fails here.
            nat = page.evaluate(
                "() => document.querySelector('.stranger-demo').naturalWidth")
            assert nat >= g["img"]["w"] * 3 - 1, \
                why + "the board is drawn at %.0fpx but the asset is only %dpx — " \
                "it will look soft at 3x; re-shoot with tools/make_demo_shot.py" % (
                    g["img"]["w"], nat)

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
            # The 3-line cap must never eat a word of it (9 Aug 2026: the
            # taglines got longer, so this is the guard that matters now).
            clipped = page.evaluate(
                """(k) => { const t = document.querySelector(
                     '[data-row="' + k + '"] .hero-tagline');
                   return t.scrollHeight - t.clientHeight; }""", key)
            assert clipped <= 1, \
                "%s tagline is cut off — %dpx of it is hidden" % (key, clipped)
            # Thread is the game we finished to get here, and since 7 Aug 2026
            # a finished card shows "Done · N pts" in place of its tagline
            # (home_card_status_and_icons owns that rule). The other three are
            # untouched, so their taglines must actually be on screen — not
            # merely present in the markup, which is all inner_text proves.
            if key != "thread":
                assert page.locator('[data-row="%s"] .hero-tagline' % key).first.is_visible(), \
                    "%s row's tagline is in the markup but not on the screen" % key

        # The regulars' furniture is all back. Since 7 Aug 2026 that means the
        # Archive's day cards (the week strip and the Back Issues bar retired
        # with the calendar screen) — six of them, newest first, in every row.
        assert page.locator("#punch-card").is_visible()
        want = list(range(N - 1, N - 7, -1))
        for key in CLASSIC_TAGLINES:
            got = page.evaluate(
                "g => [...document.querySelectorAll("
                "'[data-row=\"' + g + '\"] [data-days] [data-edition-index]')]"
                ".map(b => +b.dataset.editionIndex)", key)
            assert got == want, "%s row's Archive reads %r, expected %r" % (key, got, want)
            assert page.locator(
                '[data-row="%s"] [data-days] [data-edition-index]' % key).first.is_visible()
            assert page.locator('[data-row="%s"] .hero-edition' % key).is_visible()
        assert "№" in page.inner_text('[data-hero="who"] [data-edition]')

        # And the classic doors still work.
        page.click('[data-hero="who"]')
        page.wait_for_selector("#view-reveal:not([hidden])")
        assert page.evaluate("__CHRONICLE_TEST__.revealRound.kind") == "portrait"
        H.fail_on_errors(errors, "returning_home_unchanged")


# ---------- home_card_status_and_icons ----------
# What every game card says and shows (Daniel, 7 Aug 2026):
#   * the icon has no ink frame and is big enough to read at a glance —
#     80px on the stranger's compact cards (they were 54px and illegible),
#     136px on the returning player's, both inside a card no taller than the
#     framed version's;
#   * "Play ›" is gone everywhere — the whole card is visibly the button;
#   * the status line moved out of the bottom row to sit under the game's
#     name, where it stands in for the tagline while it has something to say:
#     "Resume today's puzzle" in both states, "Done · N pts" only for a returning
#     player (a newcomer's card is still selling the game, so it keeps its
#     one-liner);
#   * the bottom row keeps the issue number and the time whisper.
GLYPH = """(k) => {
  const card = document.querySelector('[data-hero="' + k + '"]');
  const g = card.querySelector('.hero-glyph');
  const cs = getComputedStyle(g);
  const cr = card.getBoundingClientRect(), gr = g.getBoundingClientRect();
  const ccs = getComputedStyle(card);
  return {
    w: gr.width, h: gr.height, cardH: cr.height,
    colH: card.querySelector('.hero-col').getBoundingClientRect().height,
    pad: parseFloat(ccs.paddingTop) + parseFloat(ccs.paddingBottom),
    border: cs.borderTopWidth, shadow: cs.boxShadow,
  };
}"""


def home_card_status_and_icons(p, base):
    for label, seed in (("stranger", False), ("returning", True)):
        with H.app(p) as (page, errors, _ctx):
            H.boot(page, base, DATE)
            if seed:
                H.seed_completion(page, "thread", N, score=72,
                                  detail={"solved": True, "perfect": False,
                                          "mistakes": 1, "guesses": []})
                H.boot(page, base, DATE)   # stranger mode is decided on render
                page.wait_for_selector("#stranger-hero", state="hidden")
            else:
                page.wait_for_selector("#stranger-hero:not([hidden])")
            why = label + ": "

            # No invitation text anywhere in the strip — the card is the
            # button.
            assert "play" not in page.inner_text("#home-rows").lower(), \
                why + "a 'Play ›' survives in the game cards"

            # The Archive is regulars' furniture: a newcomer sees none of it.
            n_days = page.locator("#home-rows [data-edition-index]").count()
            if seed:
                assert n_days == 4 * 6, \
                    why + "expected four rows of six day cards, found %d" % n_days
            else:
                assert n_days == 0, \
                    why + "a newcomer was shown %d past-day cards" % n_days

            # The icons: unframed, and as tall as the card's content box.
            want = 136 if seed else 80
            for key in (CLASSIC_TAGLINES if seed else dict(
                    (g, 1) for g, _, _ in OTHER_GAMES)):
                g = page.evaluate(GLYPH, key)
                assert g["border"] == "0px", \
                    why + "%s icon still has a %s frame" % (key, g["border"])
                assert g["shadow"] == "none", \
                    why + "%s icon still casts the framed print's shadow" % key
                assert g["w"] == want and g["h"] == want, \
                    why + "%s icon is %.0fx%.0f, expected %d" % (
                        key, g["w"], g["h"], want)
                # It fills the card rather than forcing it taller: the whole
                # point of moving the icon beside the bottom line.
                assert g["h"] <= g["cardH"] - g["pad"] + 1, \
                    why + "%s icon (%.0f) overflows its card's content box" % (
                        key, g["h"])
                # Slack under the icon is only allowed when the WORDS are what
                # made the card taller (Face Value's name wraps to two lines,
                # and its tagline runs to three since 9 Aug 2026). Slack with a
                # shorter text column than icon means the card grew for nothing.
                assert (g["h"] >= (g["cardH"] - g["pad"]) * 0.9
                        or g["colH"] > g["h"]), \
                    why + "%s icon (%.0f) leaves %.0fpx of card height unused" % (
                        key, g["h"], g["cardH"] - g["pad"] - g["h"])

            # The status line lives under the name, above the bottom row.
            probe = "thread" if seed else "map"
            geom = page.evaluate(
                """(k) => { const c = document.querySelector('[data-hero="' + k + '"]');
                  const b = (s) => { const e = c.querySelector(s);
                    const r = e.getBoundingClientRect();
                    return {t: r.top, b: r.bottom, shown: getComputedStyle(e).display}; };
                  return {name: b('.hero-name'), status: b('[data-status]'),
                          bottom: b('.hero-bottom')}; }""", probe)
            if seed:
                # Returning player, done game: "Done · N pts" under the name,
                # tagline gone, issue number + time whisper still below.
                assert said(page, '[data-hero="thread"] [data-status]') == "done · 72 pts", \
                    why + "the done card lost its score line"
                assert geom["status"]["t"] >= geom["name"]["b"] - 1, \
                    why + "the status sits above the game's name"
                assert geom["status"]["b"] <= geom["bottom"]["t"] + 1, \
                    why + "the status is still down in the bottom row"
                assert page.locator('[data-row="thread"] .hero-tagline').first.is_hidden(), \
                    why + "the tagline is still showing under a done card"
                edition = page.inner_text('[data-hero="thread"] [data-edition]')
                assert ("№ %d" % N) in edition and "min" in edition, \
                    why + "the bottom row lost the issue number or the time whisper: %r" % edition
            else:
                # Newcomer: silent card, one-liner intact, bottom row gone.
                assert page.inner_text('[data-hero="map"] [data-status]').strip() == "", \
                    why + "an unplayed card is talking"
                assert geom["status"]["shown"] == "none", why + "the silent status line is rendered"
                assert geom["bottom"]["shown"] == "none", \
                    why + "the newcomer's card still prices the issue"
                assert page.locator('[data-row="map"] .hero-tagline-new').is_visible(), \
                    why + "the newcomer one-liner is gone"
            H.fail_on_errors(errors, "home_card_status_and_icons/" + label)


# ---------- in_progress_replaces_the_one_liner ----------
def in_progress_replaces_the_one_liner(p, base):
    """A newcomer who starts Lifeline and comes back sees the resume prompt
    where that card's one-liner was — and only on that card.

    The wording is "Resume today's puzzle", not the old flat "In progress"
    (Daniel, 7 Aug 2026): an instruction invites where a status only reports,
    and "today's" carries the fact that it expires at midnight. The past-day
    cards say a plain "Resume" instead — see test_daily_flow.rollover — since
    "today's" would be false there."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        page.wait_for_selector("#stranger-hero:not([hidden])")
        H.open_daily(page, "map")
        H.dismiss_intro(page)
        page.wait_for_selector("#view-map:not([hidden])")
        page.click("#map-quit")
        if page.locator("#confirm-sheet:not([hidden])").count():
            page.click("#confirm-yes")
        page.wait_for_selector("#view-home:not([hidden])")
        assert page.evaluate("document.body.classList.contains('is-stranger')"), \
            "quitting a daily should not end stranger mode"

        assert said(page, '[data-hero="map"] [data-status]') == "resume today's puzzle"
        assert page.locator('[data-row="map"] .hero-tagline-new').is_hidden(), \
            "the resume prompt should stand in for the one-liner, not sit beside it"
        for key, line, _view in OTHER_GAMES:
            if key == "map":
                continue
            assert said(page, '[data-row="%s"] .hero-tagline-new' % key) == line, \
                "%s lost its one-liner to another game's progress" % key
            assert page.locator('[data-hero="%s"] [data-status]' % key).is_hidden(), \
                "%s is reporting a status it does not have" % key
        H.fail_on_errors(errors, "in_progress_replaces_the_one_liner")


TESTS = [stranger_hero, stranger_hero_side_by_side,
         stranger_rows_open_their_own_games, returning_home_unchanged,
         home_card_status_and_icons, in_progress_replaces_the_one_liner]


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
