#!/usr/bin/env python3
"""Daily-calendar suite (P4.1): streak repair via the archive, midnight
rollover, the 7-day archive window, Encore's aired-only guarantee.

'Today' is pinned to the newest manifest edition N; the days behind it are
all aired and manifest-served, so these scenarios are deterministic.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
import helpers as H  # noqa: E402

N = H.latest_edition()
DATE = H.edition_date(N)


def open_archive_edition(page, game, n):
    """Home -> a row's Back issues -> tap the calendar cell for edition n ->
    pick the game in the sheet."""
    page.click('[data-archive="%s"]' % game)
    page.wait_for_selector("#view-archive:not([hidden])")
    page.click('#archive-list [data-edition="%d"]' % n)
    page.wait_for_selector("#archive-picker:not([hidden])")
    page.click('[data-practice-game="%s"]' % game)


# ---------- daily_lock_and_repair ----------
def daily_lock_and_repair(p, base):
    """A hole healed from the archive inside the 2-day window counts toward
    the streak; an older edition launches as practice and never touches the
    ledger."""
    with H.app(p) as (page, errors, _ctx):
        # Day N-2: complete the daily (on time). Day N: complete today's too.
        H.boot(page, base, H.edition_date(N - 2))
        H.seed_completion(page, "who", N - 2, score=70)
        H.boot(page, base, DATE)
        H.seed_completion(page, "who", N, score=70)
        led = H.ledger(page)
        assert led["streaks"]["who"]["streak"] == 1, (
            "hole at N-1 should cap the streak at 1, got %r" % led["streaks"]["who"])

        # Repair: N-1 is still inside the window -> the archive serves the
        # real DAILY; completing it heals the streak to 3.
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

        # Beyond the window: an older edition is practice — no ledger trace.
        page.click("#rv-sum-home")
        page.wait_for_selector("#view-home:not([hidden])")
        open_archive_edition(page, "who", N - 5)
        page.wait_for_selector("#view-reveal:not([hidden])")
        page.wait_for_function("__CHRONICLE_TEST__.revealDebug !== undefined")
        page.locator("#rv-scraps .df-scrap.tearable").first.click()  # persists the session
        keys = page.evaluate(
            "({daily: __CHRONICLE_TEST__.store.getDailySession('chronicle.daily.who.%d'),"
            "  practice: __CHRONICLE_TEST__.store.getDailySession('chronicle.practice.who.%d')})"
            % (N - 5, N - 5))
        assert keys["practice"] is not None, "old edition should run as practice"
        assert keys["daily"] is None, "old edition must NOT run as the daily"
        assert not page.evaluate(
            "__CHRONICLE_TEST__.daily.isStreakValid(%d, %d)" % (N - 5, N))
        assert H.ledger(page)["entries"]["who"].get(str(N - 5)) is None
        H.fail_on_errors(errors, "daily_lock_and_repair")


# ---------- rollover ----------
def rollover(p, base):
    """Day N-1 then day N: a new issue appears; the old in-progress session
    is reachable from the archive, not today's front page."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, H.edition_date(N - 1))
        assert ("№ %d" % (N - 1)) in page.inner_text("#dateline")
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
        assert ("№ %d" % N) in page.inner_text("#dateline")
        status = page.inner_text('[data-hero="who"] [data-status]')
        assert "play" in status.lower(), "new day's hero should invite, got %r" % status
        assert page.evaluate(
            "__CHRONICLE_TEST__.store.getDailySession('chronicle.daily.who.%d')"
            % (N - 1)) is not None, "yesterday's session lost on rollover"
        # P5.1: the boot that first notices a rolled-over in-progress daily
        # fires abandon-<game> once.
        assert "4x-abandoned-facevalue" in H.gc_events(page), (
            "rollover should fire abandon-who: %r" % H.gc_events(page))
        page.click('[data-archive="who"]')
        page.wait_for_selector("#view-archive:not([hidden])")
        cell = page.locator('#archive-list [data-edition="%d"]' % (N - 1))
        assert cell.count() == 1, "yesterday missing from the archive"
        assert cell.locator(".archive-dot.progress").count() == 1, (
            "yesterday's in-progress state not shown in the archive")
        H.fail_on_errors(errors, "rollover")


# ---------- archive_window ----------
def archive_window(p, base):
    """Exactly the 7 trailing aired days are tappable; today is marked but
    not tappable; nothing future, nothing older."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        # Leave stranger mode so the archive bar is on screen (a reload —
        # stranger mode is evaluated when Home renders).
        H.seed_completion(page, "thread", N, score=80,
                          detail={"solved": True, "perfect": False,
                                  "mistakes": 1, "guesses": []})
        H.boot(page, base, DATE)
        page.click('[data-archive="who"]')
        page.wait_for_selector("#view-archive:not([hidden])")
        editions = page.evaluate(
            "Array.from(document.querySelectorAll("
            "'#archive-list button[data-edition]')).map(b => +b.dataset.edition)")
        assert sorted(editions) == list(range(N - 7, N)), (
            "tappable window should be %d..%d, got %r" % (N - 7, N - 1, sorted(editions)))
        assert page.locator("#archive-list .cal-cell.today").count() == 1
        assert page.locator('#archive-list button[data-edition="%d"]' % N).count() == 0
        H.fail_on_errors(errors, "archive_window")


# ---------- encore ----------
def encore(p, base):
    """Encore serves only previously-aired ids, never today's or unaired."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        # The pool the rules allow: everything aired on editions 0..N, minus
        # today's own items.
        allowed = page.evaluate(
            """(n) => {
                 const d = __CHRONICLE_TEST__.daily;
                 const today = new Set(d.getEdition('who', n).map(x => x.id));
                 const aired = new Set();
                 for (let e = 0; e <= n; e++)
                   for (const it of d.getEdition('who', e))
                     if (!today.has(it.id)) aired.add(it.id);
                 return [...aired];
               }""", N)
        allowed = set(allowed)
        for _ in range(5):                     # Encore resamples every call
            ids = page.evaluate(
                "n => __CHRONICLE_TEST__.daily.encoreItems('who', n).map(x => x.id)", N)
            assert ids and set(ids) <= allowed, (
                "encore leaked non-aired ids: %r" % (set(ids) - allowed))

        # The UI path: a finished daily offers Encore; its first round is an
        # aired item too.
        H.seed_completion(page, "who", N, score=60)
        H.open_daily(page, "who")
        page.wait_for_selector("#view-revealsum:not([hidden])")
        page.wait_for_selector("#rv-sum-encore:not([hidden])")
        page.click("#rv-sum-encore")
        page.wait_for_selector("#view-reveal:not([hidden])")
        page.wait_for_function("__CHRONICLE_TEST__.revealRound !== undefined")
        rid = page.evaluate("__CHRONICLE_TEST__.revealRound.id")
        assert rid in allowed, "encore round %r not from the aired pool" % rid
        H.fail_on_errors(errors, "encore")


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


TESTS = [daily_lock_and_repair, rollover, archive_window, encore, return_milestones]


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
