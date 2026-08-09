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


# ---------- showed-up helpers (7 Aug 2026) ----------
# One game per day, rotated, so no edition is ever a full house: the shape of a
# real casual player's week and the exact shape the display used to render as
# an empty card with no number.
def seed_showed_up(page, base, editions, score=80):
    for i, n in enumerate(editions):
        g = GAMES[i % len(GAMES)]
        seed_day(page, base, n, [g], score=score)


def punch(page):
    """What the masthead punch card is showing right now."""
    return page.evaluate("""() => {
      const el = document.querySelector('#punch-card');
      if (!el || el.hidden) return null;
      const sq = Array.from(el.querySelectorAll('.punch-day'));
      const count = el.querySelector('.punch-count');
      return {
        text: (count && count.textContent) || '',
        punched: sq.filter(s => s.classList.contains('punched')).length,
        full: sq.filter(s => s.classList.contains('full')).length,
        savable: sq.filter(s => s.classList.contains('savable')).length,
        // display:none for a first-time visitor (.is-stranger #punch-card)
        onScreen: el.offsetParent !== null,
      };
    }""")


def repair_strip(page):
    """The Home repair strip's copy, or None when it is not being offered."""
    return page.evaluate("""() => {
      const s = document.querySelector('#repair-strip');
      if (!s || s.hidden) return null;
      return { line: document.querySelector('#rp-line').innerText,
               btn: document.querySelector('#rp-btn').innerText };
    }""")


def showed_up_streak(page, today):
    return page.evaluate(
        "t => __CHRONICLE_TEST__.daily.showedUpStreak(t).streak", today)


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

        # Masthead punch card: this week's holes plus the plain streak label.
        punch = page.inner_text("#punch-card").lower()
        assert "4-day streak" in punch, "punch card lost the streak: %r" % punch

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

        assert H.edition_day_label(N).upper() in page.inner_text("#dateline").upper(), \
            "Home stuck on the old day"
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
        assert H.edition_day_label(last) in clip \
            and H.edition_day_label(max(0, last - 2)) in clip, (
            "the obituary share should name the days it is burying: %r" % clip[:120])
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


# ---------- showed_up_streak_is_what_is_displayed ----------
def showed_up_streak_is_what_is_displayed(p, base):
    """Locked decision #2, finally on screen. One game a day — a DIFFERENT game
    each day, so not one edition is a full house — must read as a live run
    everywhere, and a day scored ZERO must count exactly the same as a good one
    ("closing the issue is celebrated even with losses").

    This is the regression the whole change exists for: before it, the ledger
    derived this run and every surface printed the full-house one, so the card
    below would have shown seven blank squares and no number at all.
    """
    # Anchored on a Sunday so all six days sit inside the card's Mon–Sun week
    # (see full_house_is_marked_but_counts_as_one_day for the same trick).
    T = N - (N % 7) - 1
    with H.app(p) as (page, errors, _ctx):
        seed_showed_up(page, base, [T - 6, T - 5, T - 4, T - 3, T - 1])
        seed_day(page, base, T - 2, ["what"], score=0)   # a day lost outright

        H.boot(page, base, H.edition_date(T))             # today, still unplayed
        assert showed_up_streak(page, T) == 6, (
            "six one-game days should be a six-day run, got %r"
            % showed_up_streak(page, T))
        # The full-house streak — what every surface used to read — is nothing.
        assert H.ledger(page)["fullHouse"]["streak"] == 0, (
            "the scenario needs NO full house, else it proves nothing")

        pc = punch(page)
        assert pc and pc["onScreen"], "the punch card is missing for a regular"
        assert pc["punched"] == 6, (
            "punch card should hole six days, got %r" % pc)
        assert pc["full"] == 0, "no day was a full house here: %r" % pc
        assert "6-day streak" in pc["text"].lower(), (
            "punch card lost the showed-up run: %r" % pc["text"])
        # The zero-score day is one of the six holes, not a gap.
        assert page.evaluate(
            "n => __CHRONICLE_TEST__.daily.showedUpAt(n)", T - 2) is True, (
            "a zero-score completion must still count as showing up")
        H.fail_on_errors(errors, "showed_up_streak_is_what_is_displayed")


# ---------- full_house_is_marked_but_counts_as_one_day ----------
def full_house_is_marked_but_counts_as_one_day(p, base):
    """Prestige inside the same run. A full-house day wears a richer mark than
    a one-game day, but it is still ONE day of ONE continuous run — it must not
    count twice, and it must not start a second, rival streak display."""
    # The punch card is a Mon–Sun week, so this scenario runs on the most recent
    # SUNDAY at or before N: the whole week is on the card with nothing cut off
    # either end. (weekday(n) == n % 7 for n >= 0, because EPOCH is a Monday.)
    sunday = N - (N % 7) - 1
    assert sunday >= 42, "need a full week inside the launch era, got %d" % sunday
    week = list(range(sunday - 6, sunday))        # Mon..Sat; Sunday is 'today'
    with H.app(p) as (page, errors, _ctx):
        seed_showed_up(page, base, week)
        seed_day(page, base, week[1], GAMES)          # one full house, mid-run

        H.boot(page, base, H.edition_date(sunday))
        pc = punch(page)
        assert pc["full"] == 1, (
            "exactly one day of this week was a full house, got %r" % pc)
        assert pc["punched"] == len(week), (
            "the full-house day must still be one of the holes: %r" % pc)
        assert ("%d-day streak" % len(week)) in pc["text"].lower(), (
            "a full house must not inflate the run: %r" % pc["text"])
        # And it is the SAME element, wearing an extra class — not a second
        # display bolted on beside the run.
        assert page.evaluate(
            "() => document.querySelectorAll('#punch-card .punch-day.full:not(.punched)').length") == 0, (
            "a full-house mark that is not also a punch breaks the one run")
        H.fail_on_errors(errors, "full_house_is_marked_but_counts_as_one_day")


# ---------- celebration_and_share_carry_the_showed_up_run ----------
def celebration_and_share_carry_the_showed_up_run(p, base):
    """You Made History, its milestone postmark and its share receipt all read
    the showed-up run. Four one-game days then a full house today = a 5-day run
    (a milestone); the full-house streak is 1, which is what the screen used to
    print — and 1 is no milestone at all, so the postmark never fired either."""
    with H.app(p) as (page, errors, ctx):
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=base)
        seed_showed_up(page, base, [N - 4, N - 3, N - 2, N - 1], score=70)
        seed_day(page, base, N, GAMES)                # all four today

        H.boot(page, base, DATE)
        page.wait_for_selector("#view-daydone:not([hidden])")
        assert H.ledger(page)["fullHouse"]["streak"] == 1, (
            "the scenario needs a 1-day full-house streak to be meaningful")
        assert "5 days" in page.inner_text("#dd-streak").lower(), (
            "celebration should name the 5-day showed-up run, got %r"
            % page.inner_text("#dd-streak"))
        assert page.locator("#dd-milestone").is_visible(), (
            "day 5 is a milestone on the showed-up run")
        assert "5" in page.inner_text("#dd-milestone-n")

        page.click("#dd-share")                        # clipboard fallback path
        page.wait_for_function(
            "document.querySelector('#dd-share').textContent"
            ".toLowerCase().indexOf('copied') === 0", timeout=8000)
        clip = page.evaluate("navigator.clipboard.readText()")
        assert "5-day streak" in clip, (
            "the receipt should carry the showed-up run: %r" % clip[:160])
        H.fail_on_errors(errors, "celebration_and_share_carry_the_showed_up_run")


# ---------- obituary_buries_the_showed_up_run ----------
def obituary_buries_the_showed_up_run(p, base):
    """A three-day one-game-a-morning run, no full house anywhere. It dies the
    same way, and now it gets the same wake — before this, maybeMourn read the
    full-house streak, so this player's run ended in total silence."""
    last = N - 4
    with H.app(p) as (page, errors, _ctx):
        seed_showed_up(page, base, [last - 2, last - 1, last])
        assert H.ledger(page)["fullHouse"]["streak"] == 0, (
            "the scenario needs no full house at all")

        H.boot(page, base, H.edition_date(last + 3))    # still repairable
        assert page.locator("#view-daydone").is_hidden(), "wake held a day early"

        H.boot(page, base, H.edition_date(last + 4))    # beyond repair
        page.wait_for_selector("#view-daydone:not([hidden])")
        assert "history" in page.inner_text("#dd-title").lower()
        assert "3 days" in page.inner_text("#dd-total").lower(), (
            "the wake should name the 3-day run, got %r"
            % page.inner_text("#dd-total"))
        H.fail_on_errors(errors, "obituary_buries_the_showed_up_run")


# ---------- never_shows_a_zero ----------
def never_shows_a_zero(p, base):
    """No player is ever shown a "0". A first-time visitor never sees the card
    at all; a player whose run has just died gets a quiet line instead."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)                       # brand new
        pc = punch(page)
        assert pc is None or not pc["onScreen"], (
            "a stranger should not be shown the punch card: %r" % pc)

        # A run, then four days of nothing: dead, and past repair.
        seed_showed_up(page, base, [N - 8, N - 7, N - 6])
        H.boot(page, base, DATE)
        assert showed_up_streak(page, N) == 0, "the scenario needs a dead run"
        # A moment screen may open over Home (the wake); the card is behind it.
        pc = punch(page)
        assert pc is not None, "the punch card vanished for a regular"
        assert "0" not in pc["text"], (
            "a dead run must never be printed as a zero: %r" % pc["text"])
        # With no streak the label is absent entirely — silence, not a notice of
        # failure, and not the old "No run yet" (Daniel, 7 Aug 2026).
        assert "streak" not in pc["text"].lower(), (
            "a dead run should carry no streak label at all, got %r" % pc["text"])
        H.fail_on_errors(errors, "never_shows_a_zero")


# ---------- repair_strip_shows_only_when_all_four_conditions_hold ----------
def repair_strip_shows_only_when_all_four_conditions_hold(p, base):
    """The repair window, made visible. The strip needs ALL of: a missed
    edition still inside the two-day window, genuinely reachable, a real run at
    stake, and not already repaired. It carries the deadline and the number it
    is protecting, its button goes into that day's first unplayed game, and it
    disappears by itself the moment the day is repaired."""
    with H.app(p) as (page, errors, _ctx):
        # Five showed-up days, a hole at N-2, and today untouched.
        seed_showed_up(page, base, [N - 6, N - 5, N - 4, N - 3])
        seed_day(page, base, N - 1, ["thread"])
        H.boot(page, base, DATE)

        assert showed_up_streak(page, N) == 1, (
            "the gap should already have collapsed the live run to 1, got %r"
            % showed_up_streak(page, N))
        strip = repair_strip(page)
        assert strip is not None, "the repair strip did not appear"
        day = page.evaluate("n => __CHRONICLE_TEST__.daily.weekdayName(n)", N - 2)
        assert day.lower() in strip["line"].lower(), (
            "the strip should name the day it is offering: %r" % strip)
        assert "tonight" in strip["line"].lower(), (
            "a day at its last chance closes TONIGHT: %r" % strip)
        assert "6-day" in strip["line"].lower(), (
            "the strip should price the run it saves: %r" % strip)
        assert day.lower() in strip["btn"].lower(), (
            "the button should name the day: %r" % strip)

        # The button is the day cards' route, not a second one: it opens that
        # edition's first unplayed game through the same guarded launch path.
        page.click("#rp-btn")
        H.dismiss_intro(page)
        page.wait_for_selector("#view-reveal:not([hidden])")
        page.wait_for_function("__CHRONICLE_TEST__.revealRound !== undefined")
        want = page.evaluate(
            "n => __CHRONICLE_TEST__.daily.getEdition('who', n).map(x => x.id)", N - 2)
        got = page.evaluate("__CHRONICLE_TEST__.revealRound.id")
        assert got in want, (
            "the strip opened the wrong day: round %r is not in edition %d"
            % (got, N - 2))

        # Repaired: the strip retires itself, and the run is whole again.
        H.boot(page, base, DATE)
        H.seed_completion(page, "who", N - 2, score=44)
        H.boot(page, base, DATE)
        assert repair_strip(page) is None, (
            "the strip should be gone once the day is repaired")
        assert showed_up_streak(page, N) == 6, (
            "the repair should have restored the six-day run, got %r"
            % showed_up_streak(page, N))
        assert "6-day streak" in punch(page)["text"].lower()
        H.fail_on_errors(errors, "repair_strip/appears-and-retires")

    # Nothing at stake: one lonely day behind the gap is not a run to nag about.
    with H.app(p) as (page, errors, _ctx):
        seed_day(page, base, N - 1, ["who"])
        H.boot(page, base, DATE)
        assert repair_strip(page) is None, (
            "the strip nagged a player with nothing at stake")
        H.fail_on_errors(errors, "repair_strip/nothing-at-stake")

    # Past repair: a gap older than the two-day window is never offered, and a
    # gap the player has already filled is never offered either.
    with H.app(p) as (page, errors, _ctx):
        seed_showed_up(page, base, [N - 6, N - 5, N - 4])   # hole at N-3
        seed_day(page, base, N - 2, ["map"])
        seed_day(page, base, N - 1, ["what"])
        H.boot(page, base, DATE)
        assert repair_strip(page) is None, (
            "a gap outside the two-day window must not be offered")
        assert punch(page)["savable"] == 0, (
            "nothing is savable, so no square should be marked savable")
        H.fail_on_errors(errors, "repair_strip/past-repair")


# ---------- late_archive_play_cannot_revive_a_dead_run ----------
def late_archive_play_cannot_revive_a_dead_run(p, base):
    """The kind display must not become a loophole. Playing an old edition from
    the Archive still writes the entry and still reads Done — but outside the
    two-day window it buys no run, for the showed-up streak exactly as for the
    per-game ones. isStreakValid is untouched, and this proves it."""
    with H.app(p) as (page, errors, _ctx):
        seed_showed_up(page, base, [N - 6, N - 5])
        H.boot(page, base, DATE)
        assert showed_up_streak(page, N) == 0, "the run should already be dead"

        # Today, from the Archive, finish edition N-4: air + 2 = N-2 < N.
        H.seed_completion(page, "who", N - 4, score=90)
        assert page.evaluate(
            "__CHRONICLE_TEST__.daily.dailyStatus('who', %d)" % (N - 4)) == "done", (
            "the archive record must still be kept")
        assert showed_up_streak(page, N) == 0, (
            "a late archive play resurrected a dead run: %r"
            % showed_up_streak(page, N))
        # Still dead, so the masthead carries no streak label at all.
        assert "streak" not in punch(page)["text"].lower(), (
            "a late archive play must not put a streak back on the masthead: %r"
            % punch(page))

        # The day INSIDE the window still heals, so the window itself is intact.
        H.seed_completion(page, "map", N - 2, score=30)
        assert showed_up_streak(page, N) == 1, (
            "a completion inside the window should still count: %r"
            % showed_up_streak(page, N))
        H.fail_on_errors(errors, "late_archive_play_cannot_revive_a_dead_run")


TESTS = [streak_counts_up, grace_is_a_repair_window, repair_window_boundary,
         past_midnight_completion, obituary_threshold, ledger_survives_reload,
         backup_heals_ledger, read_failure_never_wipes,
         edition_math_is_dst_proof,
         # The showed-up display (7 Aug 2026)
         showed_up_streak_is_what_is_displayed,
         full_house_is_marked_but_counts_as_one_day,
         celebration_and_share_carry_the_showed_up_run,
         obituary_buries_the_showed_up_run,
         never_shows_a_zero,
         repair_strip_shows_only_when_all_four_conditions_hold,
         late_archive_play_cannot_revive_a_dead_run]


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
