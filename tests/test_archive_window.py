#!/usr/bin/env python3
"""The Archive window (Daniel, 7 Aug 2026) — locked decision #4, tightened.

THE RULE:

    ARCHIVE_FLOOR = 42        # 2026-08-10, launch day
    last  = today - 1
    first = max(ARCHIVE_FLOOR, today - 6)
    reachable archive editions = [first .. last], newest first

Two separate things are tested here, because they fail in different ways:

  * the ARITHMETIC — what the window contains on a given date, including the
    five worked examples Daniel signed off, and the 17 Aug case where 10 Aug
    finally drops off the back;
  * the GUARD — daily.canPlayEdition, which every launch path asks BEFORE
    opening a game. Hiding a card is presentation; the guard is correctness.
    CLAUDE.md forbids any casual path to unaired content, so an edition past
    today, an edition below the floor, or an edition that fell out of the
    window while a card sat on screen must all be refused by the function
    that launches, not merely by the function that draws.

The floor is checked against the epoch rather than trusted: edition n airs on
EPOCH + n days, so 2026-06-29 + 42 days must really be 2026-08-10.
"""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
import helpers as H  # noqa: E402

FLOOR = 42
SPAN = 6
LAUNCH_DAY = date(2026, 8, 10)

N = H.latest_edition()
DATE = H.edition_date(N)


def ed(d):
    """Edition index of a real calendar date, computed here rather than read
    from the app — the point is to check the app against the calendar."""
    return (d - H.EPOCH).days


# ---------- floor_is_launch_day ----------
def floor_is_launch_day(p, base):
    """ARCHIVE_FLOOR really is launch day, both ways round, and the app agrees
    with the calendar about it."""
    assert H.EPOCH + timedelta(days=FLOOR) == LAUNCH_DAY, (
        "EPOCH + %d days is %s, not launch day %s"
        % (FLOOR, H.EPOCH + timedelta(days=FLOOR), LAUNCH_DAY))
    assert ed(LAUNCH_DAY) == FLOOR
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        assert page.evaluate("__CHRONICLE_TEST__.daily.ARCHIVE_FLOOR") == FLOOR
        assert page.evaluate("__CHRONICLE_TEST__.daily.ARCHIVE_SPAN") == SPAN
        # editionIndex/editionDate must round-trip launch day to 42.
        n = page.evaluate(
            "() => __CHRONICLE_TEST__.daily.editionIndex(new Date(2026, 7, 10))")
        assert n == FLOOR, "the app puts 10 Aug 2026 at edition %r, not %d" % (n, FLOOR)
        iso = page.evaluate(
            "n => { const d = __CHRONICLE_TEST__.daily.editionDate(n);"
            " return [d.getFullYear(), d.getMonth() + 1, d.getDate()]; }", FLOOR)
        assert iso == [2026, 8, 10], "edition 42 airs on %r" % (iso,)
        # ...and both are Mondays, which is what makes the weekday ramp line up.
        assert H.EPOCH.weekday() == 0 and LAUNCH_DAY.weekday() == 0
        H.fail_on_errors(errors, "floor_is_launch_day")


# ---------- worked_examples ----------
# Daniel's table, verbatim. Dates are what a player's phone says; the editions
# are what the row of day cards must offer, newest first.
WORKED = [
    ("2026-08-10", 42, []),                            # launch day: nothing
    ("2026-08-11", 43, [42]),                          # 10 Aug
    ("2026-08-12", 44, [43, 42]),                      # 11, 10 Aug
    ("2026-08-16", 48, [47, 46, 45, 44, 43, 42]),      # the full six
    ("2026-08-17", 49, [48, 47, 46, 45, 44, 43]),      # 10 Aug is gone
]


def worked_examples(p, base):
    """The five signed-off dates, checked against the arithmetic AND against
    what Home actually draws."""
    with H.app(p) as (page, errors, _ctx):
        for iso, n, want in WORKED:
            y, m, d = (int(x) for x in iso.split("-"))
            assert ed(date(y, m, d)) == n, (
                "%s should be edition %d, the calendar says %d"
                % (iso, n, ed(date(y, m, d))))
            H.boot(page, base, iso)
            got = page.evaluate(
                "n => __CHRONICLE_TEST__.daily.archiveEditions(n)", n)
            assert got == want, (
                "%s (№ %d): archive should be %r, got %r" % (iso, n, want, got))
            assert page.evaluate("__CHRONICLE_TEST__.daily.todayIndex()") == n

            # And on screen. One completed daily takes the page out of
            # stranger mode, where the archive is deliberately hidden.
            H.seed_completion(page, "thread", n, score=80,
                              detail={"solved": True, "perfect": False,
                                      "mistakes": 1, "guesses": []})
            H.boot(page, base, iso)
            page.wait_for_selector("#home-rows[data-built]")
            drawn = page.evaluate(
                "() => [...document.querySelectorAll("
                "'[data-row=\"who\"] [data-days] [data-edition-index]')]"
                ".map(b => +b.dataset.editionIndex)")
            assert drawn == want, (
                "%s (№ %d): Face Value drew %r, expected %r" % (iso, n, drawn, want))
            # Never today, and never anything unaired.
            assert n not in drawn and all(x < n for x in drawn)
        H.fail_on_errors(errors, "worked_examples")


# ---------- launch_day_has_no_day_cards ----------
def launch_day_has_no_day_cards(p, base):
    """10 Aug: every row is the hero card alone — no empty strip, no stubs."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, "2026-08-10")
        H.seed_completion(page, "thread", FLOOR, score=80,
                          detail={"solved": True, "perfect": False,
                                  "mistakes": 1, "guesses": []})
        H.boot(page, base, "2026-08-10")
        page.wait_for_selector("#home-rows[data-built]")
        assert page.locator("#home-rows [data-edition-index]").count() == 0, (
            "launch day should show no past-day cards at all")
        assert page.locator("#home-rows .game-row.has-days").count() == 0, (
            "a row with nothing behind it should not hold a gap open")
        H.fail_on_errors(errors, "launch_day_has_no_day_cards")


# ---------- the_guard ----------
def the_guard(p, base):
    """canPlayEdition is the hard gate, and it fails closed."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        can = lambda n: page.evaluate(                       # noqa: E731
            "n => __CHRONICLE_TEST__.daily.canPlayEdition(n)", n)

        assert can(N), "today must always be playable"
        for k in range(1, SPAN + 1):
            assert can(N - k), "N-%d is inside the window" % k
        assert not can(N - SPAN - 1), "N-7 is outside the window"
        assert not can(N + 1), "TOMORROW must never be reachable"
        assert not can(N + 30), "unaired editions must never be reachable"
        assert not can(-1) and not can(0.5) and not can(None)

        # The floor: from launch day + 3, edition 41 (the last pre-launch
        # issue) is one day inside a plain "today - 6" window and must still
        # be refused. That is the whole reason the floor exists.
        assert page.evaluate(
            "() => __CHRONICLE_TEST__.daily.canPlayEdition(41, 47)") is False, (
            "edition 41 is pre-launch content and must never be reachable")
        assert page.evaluate(
            "() => __CHRONICLE_TEST__.daily.canPlayEdition(42, 47)") is True

        # Before launch day the floor must not lock a player out of TODAY.
        assert page.evaluate(
            "() => __CHRONICLE_TEST__.daily.canPlayEdition(41, 41)") is True, (
            "the floor governs the archive, never the issue of the day")
        H.fail_on_errors(errors, "the_guard")


# ---------- stale_card_fails_closed ----------
def stale_card_fails_closed(p, base):
    """A card that outlived its window — the midnight-rollover case — must not
    open a game, even though the button is still sitting there. The refusal
    lives in the launch path, so calling it directly is the honest test."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        H.seed_completion(page, "thread", N, score=80,
                          detail={"solved": True, "perfect": False,
                                  "mistakes": 1, "guesses": []})
        H.boot(page, base, DATE)
        page.wait_for_selector("#home-rows[data-built]")

        # Every engine's daily entry point refuses out-of-window editions —
        # not just app.js's launcher, because these are what a stale card, a
        # share route or a resumed session would reach.
        for game, view in (("who", "view-reveal"), ("what", "view-reveal"),
                           ("map", "view-map"), ("thread", "view-conn")):
            page.evaluate(
                "a => __CHRONICLE_TEST__.nav.goHome()", None)
            page.evaluate(
                """a => { const d = __CHRONICLE_TEST__.daily;
                     window.__blocked = d.canPlayEdition(a.n); }""",
                {"n": N + 1})
            assert page.evaluate("window.__blocked") is False
            # Tomorrow's edition, asked for directly.
            page.evaluate("a => __CHRONICLE_TEST__.launch(a.g, a.n)",
                          {"g": game, "n": N + 1})
            page.wait_for_timeout(150)
            assert page.locator("#%s" % view).is_hidden(), (
                "%s opened an unaired edition" % game)
            assert page.locator("#view-home").is_visible(), (
                "%s left the player somewhere other than Home" % game)
            # And an edition that has fallen out of the back of the window.
            page.evaluate("a => __CHRONICLE_TEST__.launch(a.g, a.n)",
                          {"g": game, "n": N - SPAN - 1})
            page.wait_for_timeout(150)
            assert page.locator("#%s" % view).is_hidden(), (
                "%s opened an edition older than the window" % game)
        H.fail_on_errors(errors, "stale_card_fails_closed")


# ---------- day_card_shape ----------
def day_card_shape(p, base):
    """What a past-day card says and how big it is (Daniel, 7 Aug 2026).

    Three rulings live here, all reversals of a first cut he saw and rejected:
      * an UNTOUCHED day says nothing at all — no status line in the markup.
        "Untouched" appeared 24 times on one screen and read cold; weekday and
        date are label enough, and the silence is what lets a score or a
        Resume carry. Screen readers still get the state from aria-label.
      * the stubs are SHORTER than the hero card, so they read as torn-off
        stubs rather than big empty rectangles.
      * the hero gives up enough width that the next card visibly peeks —
        that peek is the only thing saying the row scrolls. It must NOT be
        paid for out of the icon (settled at 136px, filling the card): the
        space came from the card's own padding, so the icon still fills it.
    """
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        page.evaluate("""() => { const d = __CHRONICLE_TEST__.daily, n = d.todayIndex();
          d.recordDailyCompletion('thread', n, {score: 80,
            detail: {solved: true, perfect: false, mistakes: 1, guesses: []}});
          d.recordDailyCompletion('who', n - 1, {score: 91, detail: []});
          __CHRONICLE_TEST__.store.setDailySession(
            'chronicle.daily.who.' + (n - 2), {ids: ['x'], results: []}); }""")
        H.boot(page, base, DATE)
        page.wait_for_selector("#home-rows[data-built]")

        strip = page.inner_text("#home-rows").lower()
        assert "untouched" not in strip, "the retired Untouched label is back"
        assert "unplayed" not in strip, "an unplayed day should say nothing at all"

        # Only the two cards with something to say carry a status line.
        cards = page.locator("#home-rows .day-card").count()
        lines = page.locator("#home-rows .day-status").count()
        assert cards == 24, "expected 4 rows x 6 days, found %d" % cards
        assert lines == 2, (
            "%d of %d day cards are talking; only the finished one and the "
            "half-played one should" % (lines, cards))
        assert page.locator(
            "#home-rows .day-card.day-fresh .day-status").count() == 0

        # ...but the state is still spoken.
        label = page.get_attribute(
            '[data-row="map"] [data-days] .day-card', "aria-label").lower()
        assert "not played" in label, (
            "a silent card must still name its state to a screen reader: %r" % label)

        geom = page.evaluate("""() => {
          const out = [];
          for (const k of ['who', 'map', 'what', 'thread']) {
            const hero = document.querySelector('[data-hero="' + k + '"]');
            const glyph = hero.querySelector('.hero-glyph');
            const day = document.querySelector('[data-row="' + k + '"] .day-card');
            const h = hero.getBoundingClientRect();
            const g = glyph.getBoundingClientRect();
            const d = day.getBoundingClientRect();
            const cs = getComputedStyle(hero);
            out.push({game: k, heroH: h.height, glyphH: g.height, dayH: d.height,
                      peek: window.innerWidth - d.left,
                      pad: parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom)});
          }
          return out;
        }""")
        for r in geom:
            why = r["game"] + ": "
            assert r["glyphH"] == 136, why + "the icon moved off 136px (%.0f)" % r["glyphH"]
            assert r["glyphH"] >= (r["heroH"] - r["pad"]) * 0.9, (
                why + "the peek was paid for out of the icon — it now fills only "
                "%.0f%% of the card" % (100 * r["glyphH"] / (r["heroH"] - r["pad"])))
            assert r["dayH"] < r["heroH"] - 20, (
                why + "the day stub (%.0f) is not visibly shorter than the hero "
                "card (%.0f)" % (r["dayH"], r["heroH"]))
            assert r["peek"] >= 24, (
                why + "only %.0fpx of the next card shows — too thin to say the "
                "row scrolls" % r["peek"])
        # And none of it makes the page itself scroll sideways.
        assert page.evaluate(
            "() => document.documentElement.scrollWidth <= "
            "document.documentElement.clientWidth"), "Home scrolls horizontally"
        H.fail_on_errors(errors, "day_card_shape")


TESTS = [floor_is_launch_day, worked_examples, launch_day_has_no_day_cards,
         the_guard, stale_card_fails_closed, day_card_shape]


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
