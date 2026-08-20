#!/usr/bin/env python3
"""Daily-flow suite (P4.1): streak repair from the Archive, midnight
rollover, and Encore.

'Today' is pinned to the newest manifest edition N; the days behind it are
all aired and manifest-served, so these scenarios are deterministic.

Rewritten 7 Aug 2026 for Archive v2. What changed, and why the assertions
moved with it:

  * There is no calendar screen, no game picker and no "Back issues" bar. A
    past day is a card in its own game's row on Home, and tapping it goes
    straight into that game, that day (open_archive_edition below).
  * A past day inside the window is a REAL daily now, not practice — it
    scores and it lands in the ledger. The old "older than the repair window
    means practice" branch is gone with the picker that offered it.
  * Streaks are untouched by any of that: isStreakValid still wants a
    completion within two days of the air date, so an archive play from four
    days ago writes a score and buys no streak. daily_lock_and_repair proves
    both halves of that on the new route.
  * The window's own arithmetic (and the hard access guard) lives in
    tests/test_archive_window.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
import helpers as H  # noqa: E402

N = H.latest_edition()
DATE = H.edition_date(N)


def open_archive_edition(page, game, n):
    """Tap that game's day card for edition n, in its own row on Home. One
    tap — there is nothing in between any more."""
    sel = '[data-row="%s"] [data-days] [data-edition-index="%d"]' % (game, n)
    page.wait_for_selector(sel)
    page.click(sel)


# ---------- daily_lock_and_repair ----------
def daily_lock_and_repair(p, base):
    """A hole healed from the Archive inside the 2-day window counts toward
    the streak. An older day inside the Archive window is still fully
    playable and still scores — it simply buys no streak, because
    isStreakValid has not moved and must not."""
    with H.app(p) as (page, errors, _ctx):
        # Day N-2: complete the daily (on time). Day N: complete today's too.
        H.boot(page, base, H.edition_date(N - 2))
        H.seed_completion(page, "who", N - 2, score=70)
        H.boot(page, base, DATE)
        H.seed_completion(page, "who", N, score=70)
        led = H.ledger(page)
        assert led["streaks"]["who"]["streak"] == 1, (
            "hole at N-1 should cap the streak at 1, got %r" % led["streaks"]["who"])

        # Repair: N-1 is still inside the repair window -> completing it from
        # the Archive heals the streak to 3.
        open_archive_edition(page, "who", N - 1)
        H.dismiss_intro(page, timeout=1200)
        H.play_reveal_daily(page)
        led = H.ledger(page)
        entry = led["entries"]["who"][str(N - 1)]
        assert entry["completedOn"] == N, "repair completion mis-stamped"
        assert led["streaks"]["who"]["streak"] == 3, (
            "healed hole should give streak 3, got %r" % led["streaks"]["who"])
        assert page.evaluate(
            "__CHRONICLE_TEST__.daily.isStreakValid(%d, %d)" % (N - 1, N))

        # Beyond the REPAIR window but inside the ARCHIVE window: N-5 opens
        # as the real daily (it writes chronicle.daily.*, never a practice
        # key), records a score, and does not resurrect the streak.
        page.click("#rv-sum-home")
        page.wait_for_selector("#view-home:not([hidden])")
        open_archive_edition(page, "who", N - 5)
        H.dismiss_intro(page, timeout=1200)
        page.wait_for_selector("#view-reveal:not([hidden])")
        page.wait_for_function("__CHRONICLE_TEST__.revealDebug !== undefined")
        page.locator("#rv-scraps .df-scrap.tearable").first.click()  # persists the session
        keys = page.evaluate(
            "({daily: __CHRONICLE_TEST__.store.getDailySession('chronicle.daily.who.%d'),"
            "  practice: __CHRONICLE_TEST__.store.getDailySession('chronicle.practice.who.%d')})"
            % (N - 5, N - 5))
        assert keys["daily"] is not None, "an archive day must run as the DAILY"
        assert keys["practice"] is None, "practice has no player-facing route any more"
        assert not page.evaluate(
            "__CHRONICLE_TEST__.daily.isStreakValid(%d, %d)" % (N - 5, N))

        # Finish it: the score is recorded, the streak is NOT revived. This is
        # the streak rule falling out of the existing design, untouched.
        H.play_reveal_daily(page)
        led = H.ledger(page)
        assert str(N - 5) in led["entries"]["who"], (
            "an archive play must be recorded like any other daily")
        assert led["streaks"]["who"]["streak"] == 3, (
            "a late archive play must not extend the streak, got %r"
            % led["streaks"]["who"])
        H.fail_on_errors(errors, "daily_lock_and_repair")


# ---------- rollover ----------
def rollover(p, base):
    """Day N-1 then day N: a new issue appears; the old in-progress session
    is reachable from yesterday's day card, not today's hero card."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, H.edition_date(N - 1))
        assert H.edition_day_label(N - 1).upper() in page.inner_text("#dateline").upper()
        # Leave stranger mode (archive bars are regulars' furniture): one
        # completed daily in an unrelated game.
        H.seed_completion(page, "thread", N - 1, score=80,
                          detail={"solved": True, "perfect": False,
                                  "mistakes": 1, "guesses": []})
        H.open_daily(page, "who")
        H.dismiss_intro(page, timeout=1200)
        page.wait_for_selector("#view-reveal:not([hidden])")
        page.locator("#rv-scraps .df-scrap.tearable").first.click()
        page.click("#rv-quit")

        H.boot(page, base, DATE)               # midnight passed
        assert H.edition_day_label(N).upper() in page.inner_text("#dateline").upper()
        # The new day's card is untouched again. It used to say "Play ›"; since
        # 7 Aug 2026 an untouched card says NOTHING — the status line is silent
        # and the game's tagline holds the slot (see test_stranger_home.py:
        # home_card_status_and_icons). So "today is fresh" is now read as
        # "yesterday's In progress is gone", not as an invitation.
        cls = page.get_attribute('[data-hero="who"]', "class")
        assert "row-progress" not in cls and "row-done" not in cls, (
            "yesterday's state stuck to the new day's card: %r" % cls)
        status = page.inner_text('[data-hero="who"] [data-status]').strip()
        assert status == "", "a fresh card should say nothing, got %r" % status
        assert page.locator('[data-hero="who"] .hero-tagline').first.is_visible(), \
            "the fresh card lost its tagline"
        assert page.evaluate(
            "__CHRONICLE_TEST__.store.getDailySession('chronicle.daily.who.%d')"
            % (N - 1)) is not None, "yesterday's session lost on rollover"
        # P5.1: the boot that first notices a rolled-over in-progress daily
        # fires abandon-<game> once.
        assert "4x-abandoned-facevalue" in H.gc_events(page), (
            "rollover should fire abandon-who: %r" % H.gc_events(page))
        card = page.locator(
            '[data-row="who"] [data-days] [data-edition-index="%d"]' % (N - 1))
        assert card.count() == 1, "yesterday missing from the Archive row"
        assert "day-progress" in (card.get_attribute("class") or ""), (
            "yesterday's half-played state is not shown on its day card")
        # A half-played day card SHOWS its progress rather than saying
        # "Resume" (Daniel, 9 Aug 2026): one mark per round, the round you are
        # inside half-filled, plus the chevron that means there is play left.
        # The words survive only in the accessible name.
        marks = page.evaluate(
            """(sel) => [...document.querySelectorAll(sel + ' .cs-mark')]
                 .map(m => m.className.replace('cs-mark cs-', ''))""",
            '[data-row="who"] [data-days] [data-edition-index="%d"]' % (N - 1))
        assert marks == ["half", "todo", "todo"], (
            "a day card one tear into round 1 should read ◐ ○ ○, got %r" % marks)
        assert card.locator(".cs-chev").count() == 1, (
            "a half-played day card lost the chevron that says there is play left")
        assert "resume" not in card.inner_text().lower(), (
            "the retired Resume word is back on a day card: %r" % card.inner_text())
        assert "resume" in (card.get_attribute("aria-label") or "").lower(), (
            "a half-played day card must still say 'resume' to a screen reader")
        H.fail_on_errors(errors, "rollover")


# ---------- archive_strip ----------
def archive_strip(p, base):
    """Each game's row offers exactly the reachable window, newest first, and
    never today. (The window arithmetic itself, the floor and the five worked
    dates live in tests/test_archive_window.py.)"""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        # One completed daily takes the page out of stranger mode, where the
        # Archive is deliberately hidden.
        H.seed_completion(page, "thread", N, score=80,
                          detail={"solved": True, "perfect": False,
                                  "mistakes": 1, "guesses": []})
        H.boot(page, base, DATE)
        page.wait_for_selector("#home-rows[data-built]")
        want = list(range(N - 1, N - 7, -1))
        for game in ("who", "map", "what", "thread"):
            got = page.evaluate(
                "g => [...document.querySelectorAll("
                "'[data-row=\"' + g + '\"] [data-days] [data-edition-index]')]"
                ".map(b => +b.dataset.editionIndex)", game)
            assert got == want, (
                "%s row: expected %r newest-first, got %r" % (game, want, got))
        # Today lives on the hero card and nowhere else.
        assert page.locator(
            '#home-rows [data-edition-index="%d"]' % N).count() == 0
        H.fail_on_errors(errors, "archive_strip")


# ---------- no_encore ----------
def no_encore(p, base):
    """Encore is gone (Daniel, 9 Aug 2026, reversing locked decision #6). A
    finished daily's summary offers exactly one way onward — the next game of
    TODAY's issue — plus the share and the way home. Nothing on that screen
    sends the player back into another day of the same game; anyone who wants
    that uses the game's own Archive row on Home."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        assert page.evaluate(
            "() => typeof __CHRONICLE_TEST__.daily.encoreEdition"), "unbound"
        H.seed_completion(page, "who", N, score=60)
        H.open_daily(page, "who")
        page.wait_for_selector("#view-revealsum:not([hidden])")
        assert page.locator("#rv-sum-encore").count() == 0, \
            "the Encore button is back on the Face Value summary"
        assert "encore" not in page.inner_text("#view-revealsum").lower(), \
            "the word Encore survives on a finished summary"
        # The one onward move: today's next unplayed game.
        turn = page.locator("#rv-sum-turn")
        assert turn.is_visible(), "the summary lost its forward button"
        assert "next puzzle" in turn.inner_text().lower(), turn.inner_text()
        # ...and it has to actually open that game. The button routes through
        # app.js's launchEdition (the same door the Home cards use) since v224,
        # so this walks the whole thing rather than only reading the label.
        turn.click()
        H.dismiss_intro(page)
        page.wait_for_selector("#view-map:not([hidden])", timeout=10000)
        page.wait_for_function("__CHRONICLE_TEST__.mapRound !== undefined")
        H.fail_on_errors(errors, "no_encore")


# ---------- return_milestones ----------
def return_milestones(p, base):
    """D1/D7/D30 return one-shots (P5.1) fire together on the first boot that
    crosses each threshold, counted in editions since the first-ever
    completed daily — never a wall-clock timestamp."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, H.edition_date(N - 10))
        H.seed_completion(page, "who", N - 10, score=70)
        H.boot(page, base, H.edition_date(N - 2))   # 8 editions later: crosses D1 and D7
        events = H.gc_events(page)
        assert "8-return-d1" in events, "missing ret-d1: %r" % events
        assert "8-return-d7" in events, "missing ret-d7: %r" % events
        assert "8-return-d30" not in events, "ret-d30 fired too early: %r" % events
        H.fail_on_errors(errors, "return_milestones")


# ---------- return_age_histogram ----------
def return_age_histogram(p, base):
    """The retention histogram (20 Aug 2026): each returning day files the
    device into an age band (editions since first seen), at most once per
    local day. A device from before the stamp existed backfills from its
    earliest completed daily; a brand-new device's first day is silent."""
    with H.app(p) as (page, errors, _ctx):
        # Ten editions of history, then wipe the stamp to impersonate a
        # device that predates the feature — the ledger must answer for it.
        H.boot(page, base, H.edition_date(N - 10))
        H.seed_completion(page, "who", N - 10, score=70)
        page.evaluate(
            "__CHRONICLE_TEST__.store.setMisc("
            "{ firstSeenOn: undefined, retAgeDay: undefined })")
        H.boot(page, base, DATE)
        events = H.gc_events(page)
        assert "8-return-age-d08-30" in events, \
            "backfilled device missing its age band: %r" % events
        assert page.evaluate(
            "__CHRONICLE_TEST__.store.getMisc().firstSeenOn") == N - 10, \
            "backfill did not persist the ledger's first edition"
        # Same local day again: the band fires once per day, not per open.
        H.boot(page, base, DATE)
        events = H.gc_events(page)
        assert not any("return-age" in e for e in events), \
            "age band re-fired on a same-day open: %r" % events
    with H.app(p) as (page, errors, _ctx):
        # A brand-new device: day 0 is an arrival, not a return...
        H.boot(page, base, H.edition_date(N - 1))
        events = H.gc_events(page)
        assert not any("return-age" in e for e in events), \
            "day-0 boot counted as a return: %r" % events
        # ...and the next morning it is the youngest band, with no ledger
        # entry ever written (the stamp alone carries the age).
        H.boot(page, base, DATE)
        events = H.gc_events(page)
        assert "8-return-age-d01" in events, \
            "next-day return missing d01: %r" % events
        H.fail_on_errors(errors, "return_age_histogram")


TESTS = [daily_lock_and_repair, rollover, archive_strip, no_encore, return_milestones,
         return_age_histogram]


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
