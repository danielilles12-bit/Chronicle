#!/usr/bin/env python3
"""Streak + persistence suite (2026-07-31 data-retention investigation).

Nails down the rules the rest of the app is built on, because they are the
ones a player notices when they go wrong and the ones nothing else asserts:

  * a completed edition every day makes the streak count up (per game and
    full house), and the number the Ledger page prints is the same number;
  * the "grace" is a REPAIR window, not a skip allowance — the exact
    semantics of daily.isStreakValid / daily.derivedStreak, boundaries
    included;
  * the obituary appears on the first day the run is genuinely beyond
    repair, not a day early, and it appears exactly once;
  * the ledger survives a reload, a second tab, and a corrupted main blob;
  * a transient localStorage READ failure never turns into a silent wipe;
  * edition arithmetic is a calendar-day count, immune to DST.

'Today' is pinned to the newest manifest edition N, so every scenario runs
over aired, manifest-served days (same convention as test_daily_flow).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
import helpers as H  # noqa: E402

N = H.latest_edition()
DATE = H.edition_date(N)

GAMES = ["who", "map", "what", "thread"]
THREAD_DETAIL = {"solved": True, "perfect": False, "mistakes": 1, "guesses": []}


# ---------- local helpers ----------
def seed_day(page, base, n, games=GAMES, score=80):
    """Boot ON edition n's own day and file those games' dailies there, so
    completedOn is stamped exactly as an on-the-day play would stamp it."""
    H.boot(page, base, H.edition_date(n))
    for g in games:
        H.seed_completion(page, g, n, score=score,
                          detail=THREAD_DETAIL if g == "thread" else [])


LIVE_STREAK = """
(a) => {
  const d = __CHRONICLE_TEST__.daily, s = __CHRONICLE_TEST__.store;
  const entries = s.getDailyLedger().entries || {};
  const valid = (e) => {
    const en = entries[a.game] && entries[a.game][e];
    return !!en && d.isStreakValid(e, en.completedOn);
  };
  return d.derivedStreak(valid, a.today).streak;
}
"""


def live_streak(page, game, today):
    """The streak DERIVED right now for `today` — the same walk ledger.js
    does when it paints Your Legacy (not the number frozen into the ledger
    by the last completion)."""
    return page.evaluate(LIVE_STREAK, {"game": game, "today": today})


def is_valid(page, air, completed_on):
    return page.evaluate(
        "__CHRONICLE_TEST__.daily.isStreakValid(%d, %d)" % (air, completed_on))


LEDGER_ROW = """
(label) => {
  const rows = Array.from(
    document.querySelectorAll('#ledger-body .ledger-table tbody tr'));
  for (const r of rows) {
    const th = r.querySelector('th');
    if (th && th.textContent.trim().toLowerCase() === label.toLowerCase())
      return Array.from(r.querySelectorAll('td')).map(td => td.textContent.trim());
  }
  return null;
}
"""


def open_ledger(page):
    """Home footer -> Your Legacy. Columns are played, win%, current, best, high."""
    page.click("#ledger-link")
    page.wait_for_selector("#view-ledger:not([hidden])")
    page.wait_for_selector("#ledger-body .ledger-table")


# ---------- streak_counts_up ----------
def streak_counts_up(p, base):
    """Four consecutive full houses: every per-game streak and the full-house
    streak read 4, the celebration says 4, and Your Legacy agrees. This is
    the rule Daniel actually watches, so it gets asserted end to end."""
    with H.app(p) as (page, errors, _ctx):
        for k in (3, 2, 1, 0):
            seed_day(page, base, N - k)

        led = H.ledger(page)
        for g in GAMES:
            assert led["streaks"][g]["streak"] == 4, (
                "%s streak should be 4, got %r" % (g, led["streaks"][g]))
            assert led["streaks"][g]["lastEdition"] == N
        assert led["fullHouse"]["streak"] == 4, (
            "full-house streak should be 4, got %r" % led["fullHouse"])
        for g in GAMES:
            assert live_streak(page, g, N) == 4, (
                "%s derives a different streak than it stored" % g)

        # The full house is celebrated with the same number.
        H.boot(page, base, DATE)
        page.wait_for_selector("#view-daydone:not([hidden])")
        assert "4 days" in page.inner_text("#dd-streak").lower(), (
            "celebration streak wrong: %r" % page.inner_text("#dd-streak"))
        page.click("#dd-home")
        page.wait_for_selector("#view-home:not([hidden])")

        # Masthead punch card: this week's holes plus the running count.
        punch = page.inner_text("#punch-card").lower()
        assert "4 running" in punch, "punch card lost the streak: %r" % punch

        # Your Legacy prints the same current streak (column 3 of each row).
        open_ledger(page)
        for label in ("Thread", "Lifeline", "Face Value", "Relic"):
            row = page.evaluate(LEDGER_ROW, label)
            assert row is not None, "no Ledger row for %s" % label
            assert row[2] == "4", (
                "Ledger current streak for %s should be 4, got %r" % (label, row))
        fh = page.inner_text(".ledger-streaks").lower()
        assert "4" in fh, "Ledger full-house streak missing: %r" % fh
        H.fail_on_errors(errors, "streak_counts_up")


# ---------- grace_is_a_repair_window ----------
def grace_is_a_repair_window(p, base):
    """The exact semantics of the 'one day of grace', asserted rather than
    assumed. isStreakValid(air, completedOn) = completedOn <= air + 2, and
    derivedStreak anchors at the newest edition inside today..today-2:

      * a day with nothing played does NOT drop the streak — the anchor keeps
        it alive for two more days;
      * on the third day the anchor is out of reach and it reads 0;
      * playing TODAY after a skipped day starts again at 1 — the window
        forgives a LATE completion, never a missing one.
    """
    with H.app(p) as (page, errors, _ctx):
        seed_day(page, base, N - 4, ["who"])
        seed_day(page, base, N - 3, ["who"])          # last play = N-3
        assert H.ledger(page)["streaks"]["who"]["streak"] == 2

        # Nothing played on N-2 or N-1: the run is still standing.
        H.boot(page, base, H.edition_date(N - 2))
        assert live_streak(page, "who", N - 2) == 2, "day +1 killed the streak"
        H.boot(page, base, H.edition_date(N - 1))
        assert live_streak(page, "who", N - 1) == 2, "day +2 killed the streak"

        # Day +3: past the anchor's reach.
        H.boot(page, base, DATE)
        assert live_streak(page, "who", N) == 0, "day +3 should read 0"

        # Playing today does NOT resume the old run — it starts a new one.
        H.seed_completion(page, "who", N, score=70)
        led = H.ledger(page)
        assert led["streaks"]["who"]["streak"] == 1, (
            "a skipped day must restart at 1, got %r" % led["streaks"]["who"])
        # ...and the older days are still on the record, just not in the chain.
        assert str(N - 3) in led["entries"]["who"]
        H.fail_on_errors(errors, "grace_is_a_repair_window")


# ---------- repair_window_boundary ----------
def repair_window_boundary(p, base):
    """A missed edition can be healed on the day after and the day after
    that (air + 2). One day later the completion is still WRITTEN — the tile
    reads Done, nothing is lost — but it buys no streak."""
    with H.app(p) as (page, errors, _ctx):
        seed_day(page, base, N - 4, ["who"])

        # (N-3)+1: repairable.
        H.boot(page, base, H.edition_date(N - 2))
        assert is_valid(page, N - 3, N - 2), "day+1 repair should be valid"
        # (N-3)+2: still repairable, the last day it counts.
        H.boot(page, base, H.edition_date(N - 1))
        assert is_valid(page, N - 3, N - 1), "day+2 repair should be valid"
        # (N-3)+3: out of the window.
        H.boot(page, base, DATE)
        assert not is_valid(page, N - 3, N), "day+3 repair should NOT count"

        H.seed_completion(page, "who", N - 3, score=60)
        led = H.ledger(page)
        assert str(N - 3) in led["entries"]["who"], (
            "a late completion must still be recorded")
        assert led["streaks"]["who"]["streak"] == 0, (
            "a late completion must not resurrect the streak, got %r"
            % led["streaks"]["who"])
        assert page.evaluate(
            "__CHRONICLE_TEST__.daily.dailyStatus('who', %d)" % (N - 3)) == "done", (
            "the archive tile should still read Done")
        H.fail_on_errors(errors, "repair_window_boundary")


# ---------- past_midnight_completion ----------
def past_midnight_completion(p, base):
    """23:58 start, 00:02 finish. The run is filed against the edition it was
    STARTED for; completedOn is the new day; it still counts (that is what
    the +2 window is for), and Home has already moved on to the new issue."""
    with H.app(p) as (page, errors, _ctx):
        seed_day(page, base, N - 2, ["who"])

        H.boot(page, base, DATE)                       # midnight has passed
        H.seed_completion(page, "who", N - 1, score=70)  # finishing yesterday's

        led = H.ledger(page)
        entry = led["entries"]["who"][str(N - 1)]
        assert entry["completedOn"] == N, (
            "a post-midnight finish should stamp the NEW day, got %r" % entry)
        assert is_valid(page, N - 1, N)
        assert led["streaks"]["who"]["streak"] == 2, (
            "yesterday's late finish should link to N-2, got %r"
            % led["streaks"]["who"])

        assert ("№ %d" % N) in page.inner_text("#dateline"), "Home stuck on the old issue"
        # Today's own Face Value is still untouched. It used to say "Play ›";
        # since 7 Aug 2026 an untouched card is silent and shows its tagline
        # instead (see test_stranger_home.py: home_card_status_and_icons), so
        # what we check is that last night's finish did not mark TODAY.
        cls = page.get_attribute('[data-hero="who"]', "class")
        assert "row-done" not in cls and "row-progress" not in cls, (
            "yesterday's late finish marked today's Face Value: %r" % cls)
        status = page.inner_text('[data-hero="who"] [data-status]').strip()
        assert status == "", "today's untouched card should say nothing: %r" % status
        assert page.locator('[data-hero="who"] .hero-tagline').first.is_visible(), \
            "today's untouched card lost its tagline"
        H.fail_on_errors(errors, "past_midnight_completion")


# ---------- obituary_threshold ----------
def obituary_threshold(p, base):
    """The wake fires on the first day the run is genuinely beyond repair
    (lastEdition + 4), never a day early, and never twice. Its share state is
    fully built when it appears."""
    last = N - 4
    with H.app(p) as (page, errors, ctx):
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=base)
        for n in (last - 2, last - 1, last):
            seed_day(page, base, n)                    # three full houses
        led = H.ledger(page)
        assert led["fullHouse"]["streak"] == 3, (
            "need a 3-day full-house run to mourn, got %r" % led["fullHouse"])
        assert led["fullHouse"]["lastEdition"] == last

        # +3: the first missed edition is still inside its own repair window.
        H.boot(page, base, H.edition_date(last + 3))
        assert page.locator("#view-daydone").is_hidden(), (
            "obituary fired a day early")
        assert page.locator("#view-home").is_visible()

        # +4: beyond repair.
        H.boot(page, base, H.edition_date(last + 4))
        page.wait_for_selector("#view-daydone:not([hidden])")
        assert "history" in page.inner_text("#dd-title").lower()
        assert "3 days" in page.inner_text("#dd-total").lower(), (
            "obituary should name the 3-day run, got %r" % page.inner_text("#dd-total"))
        assert page.evaluate(
            "document.querySelector('#view-daydone').classList.contains('obituary')")
        assert page.locator("#dd-stamp").is_visible(), "memento mori stamp missing"

        share = page.locator("#dd-share")
        assert share.is_visible(), "obituary has no share button"
        assert "obituary" in share.inner_text().lower()
        page.click("#dd-share")                        # clipboard fallback path
        page.wait_for_function(
            "document.querySelector('#dd-share').textContent"
            ".toLowerCase().indexOf('copied') === 0", timeout=8000)
        clip = page.evaluate("navigator.clipboard.readText()")
        assert str(last) in clip and str(max(0, last - 2)) in clip, (
            "the obituary share should name the run it is burying: %r" % clip[:120])
        assert "6-shared-obituary-copied" in H.gc_events(page)

        # Once, not every boot.
        H.boot(page, base, H.edition_date(last + 4))
        assert page.locator("#view-daydone").is_hidden(), "obituary nagged twice"
        H.fail_on_errors(errors, "obituary_threshold")


# ---------- ledger_survives_reload ----------
def ledger_survives_reload(p, base):
    """Entries, streaks and the derived tile states survive a full reload and
    are visible to a second tab on the same origin."""
    with H.app(p) as (page, errors, ctx):
        seed_day(page, base, N - 1)
        seed_day(page, base, N)
        before = H.ledger(page)
        assert before["fullHouse"]["streak"] == 2

        H.boot(page, base, DATE)                       # full reload
        assert H.ledger(page) == before, "the ledger changed across a reload"
        for g in GAMES:
            assert page.evaluate(
                "__CHRONICLE_TEST__.daily.dailyStatus('%s', %d)" % (g, N)) == "done"

        page.wait_for_selector("#view-daydone:not([hidden])")   # full-house screen
        page.click("#dd-home")
        page.wait_for_selector("#view-home:not([hidden])")
        for g in GAMES:
            status = page.inner_text('[data-hero="%s"] [data-status]' % g).lower()
            assert "done" in status, "%s hero lost its Done state: %r" % (g, status)

        # A second tab reads the same jar.
        page2 = ctx.new_page()
        page2.goto(H.app_url(base, DATE))
        page2.wait_for_function(H.BOOTED)
        assert H.ledger(page2)["fullHouse"]["streak"] == 2, (
            "a second tab cannot see the history")
        page2.close()
        H.fail_on_errors(errors, "ledger_survives_reload")


# ---------- backup_heals_ledger ----------
def backup_heals_ledger(p, base):
    """A corrupted main blob is rebuilt from the rolling backup with the
    STREAK RECORD intact — not just the odd misc flag."""
    with H.app(p) as (page, errors, _ctx):
        seed_day(page, base, N - 1)
        seed_day(page, base, N)
        good = page.evaluate("localStorage.getItem('chronicle.v1')")
        assert good and "dailyLedger" in good

        page.evaluate(
            "g => { localStorage.setItem('chronicle.v1', '{not json');"
            " localStorage.setItem('chronicle.v1.backup', g); }", good)

        H.boot(page, base, DATE)
        led = H.ledger(page)
        assert led["fullHouse"]["streak"] == 2, (
            "streak not recovered from backup: %r" % led["fullHouse"])
        for g in GAMES:
            assert str(N) in led["entries"][g], "%s entry lost in recovery" % g
            assert str(N - 1) in led["entries"][g]

        healed = page.evaluate("JSON.parse(localStorage.getItem('chronicle.v1'))")
        assert healed["dailyLedger"]["fullHouse"]["streak"] == 2, (
            "main blob not healed with the ledger")
        assert "9-save-recovered-from-backup" in H.gc_events(page)
        H.fail_on_errors(errors, "backup_heals_ledger")


# ---------- read_failure_never_wipes ----------
# Reads of chronicle.v1* throw on demand — Safari with site data blocked, a
# locked/corrupt WebKit storage database, a private-mode edge. __rawGet keeps
# an unpatched handle so the test can look at the real bytes afterwards.
READ_FAIL_STUB = """
(() => {
  const orig = Storage.prototype.getItem;
  window.__failReads = false;
  window.__rawGet = (k) => orig.call(localStorage, k);
  Storage.prototype.getItem = function (k) {
    if (window.__failReads && String(k).indexOf('chronicle.v1') === 0) {
      throw new DOMException('storage unavailable', 'SecurityError');
    }
    return orig.apply(this, arguments);
  };
})();
"""


def read_failure_never_wipes(p, base):
    """The nastiest silent-wipe path: every setter is read-modify-write, so a
    transient READ failure makes the app believe it is on a brand-new device.
    Whatever it writes in that state must not land on top of a real history —
    a blank blob parses perfectly, so the backup would never be consulted
    again and the loss would be permanent."""
    with H.app(p, init_scripts=(READ_FAIL_STUB,)) as (page, errors, _ctx):
        seed_day(page, base, N - 1)
        seed_day(page, base, N)
        before = page.evaluate("window.__rawGet('chronicle.v1')")
        assert '"dailyLedger"' in before

        page.evaluate("window.__failReads = true")
        assert page.evaluate(
            "__CHRONICLE_TEST__.store.getDailyLedger()")["entries"] == {}, (
            "the scenario needs reads to actually be failing")

        # Exactly what boot() and a finished game would do next.
        page.evaluate("__CHRONICLE_TEST__.store.setMisc({seenBefore: true, poison: 1})")
        page.evaluate(
            "__CHRONICLE_TEST__.daily.recordDailyCompletion("
            "'who', 999, {score: 1, detail: []})")
        page.evaluate("window.__failReads = false")

        after = page.evaluate("window.__rawGet('chronicle.v1')")
        assert after == before, (
            "a failed read was allowed to overwrite good state")
        led = H.ledger(page)
        assert led["fullHouse"]["streak"] == 2, "history lost: %r" % led["fullHouse"]
        assert "999" not in led["entries"]["who"]
        assert page.evaluate(
            "__CHRONICLE_TEST__.store.getMisc().poison") is None

        # The player is told, rather than silently played on.
        assert "9-save-failing" in H.gc_events(page), (
            "an unsaveable state should raise the save beacon: %r" % H.gc_events(page))
        assert page.locator(".df-save-toast").count() == 1
        H.fail_on_errors(errors, "read_failure_never_wipes")


# ---------- edition_math_is_dst_proof ----------
# editionIndex must be a pure calendar-day count. Using real local-midnight
# timestamps it is not: a local day is 23 or 25 hours long across a DST
# shift, so a player whose UTC offset today is LARGER than it was on EPOCH
# day lands an hour short of a whole day and Math.floor takes the index back
# a day — southern-hemisphere summer, every year.
DST_PROBE = """
() => {
  const d = __CHRONICLE_TEST__.daily;
  const bad = [];
  for (let n = 0; n <= 400; n++)
    if (d.editionIndex(d.editionDate(n)) !== n) bad.push(n);
  return {
    count: bad.length,
    first: bad.slice(0, 6),
    // 2026-11-01 is 125 calendar days after EPOCH (2026-06-29), everywhere.
    nov1: d.editionIndex(new Date(2026, 10, 1)),
    tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
  };
}
"""


def edition_math_is_dst_proof(p, base):
    """editionIndex(editionDate(n)) === n for a full year, in a northern and
    a southern timezone. Sydney is the regression: its clocks go FORWARD in
    October, past EPOCH day's offset."""
    for tz in ("Europe/London", "Australia/Sydney"):
        with H.app(p, context_args={"timezone_id": tz}) as (page, errors, _ctx):
            H.boot(page, base, DATE)
            r = page.evaluate(DST_PROBE)
            assert r["tz"] == tz, "timezone not applied: %r" % r
            assert r["count"] == 0, (
                "%s: %d editions do not round-trip, first %r" % (tz, r["count"], r["first"]))
            assert r["nov1"] == 125, (
                "%s: 2026-11-01 should be edition 125, got %r" % (tz, r["nov1"]))
            H.fail_on_errors(errors, "edition_math_is_dst_proof/" + tz)


TESTS = [streak_counts_up, grace_is_a_repair_window, repair_window_boundary,
         past_midnight_completion, obituary_threshold, ledger_survives_reload,
         backup_heals_ledger, read_failure_never_wipes,
         edition_math_is_dst_proof]


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
