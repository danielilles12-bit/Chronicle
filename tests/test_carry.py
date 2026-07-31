#!/usr/bin/env python3
"""Carry suite: moving a player's record from one origin to another.

The whole point of the tool is that localStorage does not cross an origin, so
these scenarios are the only honest way to test it: TWO static servers on two
ports (a different port IS a different origin as far as storage is concerned),
export on A, import on B.

Covered here:
  round_trip_link        export on A -> open the link on B -> record arrives,
                         fragment scrubbed, reload does not re-prompt
  round_trip_code        the same journey with the copy-code pasted by hand
                         (the only path that works Safari -> installed iOS app)
  merge_never_lowers     importing a thinner record into a device with a
                         better streak leaves the better streak standing
  idempotent             importing the same payload twice changes nothing
  tampered_rejected      one flipped character is refused, and nothing is
                         written
  no_compression_fallback  a browser with no CompressionStream still exports,
                         and one with no DecompressionStream says so plainly
  hostile_payload_ignored  a correctly-checksummed payload full of junk loses
                         the junk and keeps the legitimate parts
  heavy_payload_sizes    a realistic heavy record still encodes, and the
                         link/code lengths are reported (see REPORT.md)
"""
import contextlib
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
import helpers as H  # noqa: E402

N = H.latest_edition()
DATE = H.edition_date(N)
GAMES = ["who", "map", "what", "thread"]


@contextlib.contextmanager
def device(p, base, dailydate=DATE, extra="", init_scripts=()):
    """One browser profile, booted on one origin.

    Wraps H.app so the request interceptor is torn down BEFORE the browser
    closes. Every scenario here opens two profiles in a row (origin A, then
    origin B), and a route handler still mid-request when the first browser
    goes away surfaces as a spurious 'Target page ... has been closed'.
    """
    with H.app(p, init_scripts=init_scripts) as (page, errors, ctx):
        H.boot(page, base, dailydate, extra=extra)
        try:
            yield page, errors
        finally:
            with contextlib.suppress(Exception):
                ctx.unroute_all(behavior="ignoreErrors")


# ---------- shared plumbing ----------
# H.seed_completion writes through the real recordDailyCompletion, which stamps
# completedOn = TODAY. That is right for "finished it just now", but it means a
# backfilled run can never be longer than the 48h repair window allows (three
# editions). A player with a 30-day streak has thirty entries each completed on
# their OWN day, so a run of any length has to be written that way.
SEED_HISTORY = """
(a) => {
  const store = __CHRONICLE_TEST__.store;
  const blob = store.readAll();
  const l = blob.dailyLedger
    || { entries: {}, streaks: {}, fullHouse: { streak: 0, lastEdition: -Infinity } };
  l.entries = l.entries || {};
  for (const g of a.games) {
    l.entries[g] = l.entries[g] || {};
    for (const n of a.editions) {
      l.entries[g][n] = {
        completedOn: n, score: a.score,
        detail: g === 'thread'
          ? { solved: true, perfect: false, mistakes: 1, guesses: [['yellow','yellow','green','yellow']] }
          : [{ id: g + '-' + n, pts: a.score, correct: true, torn: 1, wrongs: 0 }],
      };
    }
  }
  blob.dailyLedger = l;
  store.writeAll(blob);
}
"""


def seed_run(page, editions, games=GAMES, score=80):
    """A player who showed up on each of these editions, on the day."""
    page.evaluate(SEED_HISTORY,
                  {"editions": list(editions), "games": list(games), "score": score})


def seed_entry(page, game, edition, score):
    """One completion, scored, filed on its own day."""
    seed_run(page, [edition], games=[game], score=score)


def export_payload(page, destination=None):
    """The payload + link the app itself would hand a player."""
    if destination is not None:
        page.evaluate("o => __CHRONICLE_TEST__.carry.setDestination(o)", destination)
    return page.evaluate("() => __CHRONICLE_TEST__.carry.exportNow()")


def full_house_streak(page):
    return page.evaluate(
        "() => __CHRONICLE_TEST__.carry.summarise("
        "__CHRONICLE_TEST__.store.readAll()).streak")


def entry_count(page):
    return page.evaluate(
        """() => {
             const e = (__CHRONICLE_TEST__.store.getDailyLedger().entries) || {};
             return Object.keys(e).reduce(
               (s, g) => s + Object.keys(e[g] || {}).length, 0);
           }""")


def confirm_import(page):
    page.wait_for_selector("#carry-sheet:not([hidden])")
    page.wait_for_selector("#carry-confirm-row:not([hidden])")
    page.click("#carry-yes")
    page.wait_for_function(
        "() => /carried over/i.test(document.getElementById('carry-title').textContent)")


def open_carry(page):
    """Home footer -> Your Legacy -> Moving house, from wherever we are."""
    if not page.locator("#view-ledger").is_visible():
        page.click("#ledger-link")
        page.wait_for_selector("#view-ledger:not([hidden])")
    page.click("#carry-open")
    page.wait_for_selector("#carry-sheet:not([hidden])")


def paste_code(page, code):
    open_carry(page)
    page.fill("#carry-paste", code)
    page.click("#carry-paste-btn")


# ---------- round_trip_link ----------
def round_trip_link(p, base_a, base_b):
    """Export on origin A, open the link on origin B: streak and entries
    arrive, the payload is scrubbed out of the URL and out of history, and a
    reload does not offer the same import a second time."""
    with device(p, base_a) as (page, errors):
        seed_run(page, range(N - 5, N + 1))
        streak_a = full_house_streak(page)
        entries_a = entry_count(page)
        assert streak_a == 6, "seeded 6 consecutive editions, got %r" % streak_a
        assert entries_a == 24, "6 editions x 4 games, got %r" % entries_a
        out = export_payload(page, base_b)
        H.fail_on_errors(errors, "round_trip_link/export")

    assert out["link"].startswith(base_b + "/#carry="), (
        "link should point at the destination origin: %r" % out["link"][:80])

    with device(p, base_b) as (page, errors):
        # Origin B, cold: no record of its own.
        assert entry_count(page) == 0, "origin B should start empty"

        # The real link is <origin>/#carry=<payload>; the suite needs its two
        # test params on it too, so it is rebuilt with the payload the app
        # itself minted and the fragment kept last, exactly as a link arrives.
        assert out["link"].endswith("#carry=" + out["payload"])
        page.goto("%s/index.html?test=1&dailydate=%s#carry=%s"
                  % (base_b, DATE, out["payload"]))
        page.wait_for_function(H.BOOTED)
        confirm_import(page)

        assert entry_count(page) == entries_a, (
            "entries did not all arrive: %d vs %d" % (entry_count(page), entries_a))
        assert full_house_streak(page) == streak_a, (
            "streak did not survive the move: %r" % full_house_streak(page))
        assert page.evaluate("location.hash") == "", (
            "the payload is still in the URL: %r" % page.evaluate("location.hash"))
        events = H.gc_events(page)
        assert "7-carry-arrived" in events, "arrival not counted: %r" % events

        # Reload: the marker must make this a no-op, with no confirm offered.
        page.reload()
        page.wait_for_function(H.BOOTED)
        page.wait_for_timeout(300)
        assert page.locator("#carry-sheet").is_hidden(), (
            "a reload re-offered an import that already happened")
        assert entry_count(page) == entries_a, "reload changed the record"
        H.fail_on_errors(errors, "round_trip_link/import")


# ---------- round_trip_code ----------
def round_trip_code(p, base_a, base_b):
    """The copy-code path, which is the ONLY one that works for Safari -> an
    installed iOS app (tapping a link there opens the browser, not the app)."""
    with device(p, base_a) as (page, errors):
        # This one goes through the app's OWN write path (recordDailyCompletion)
        # rather than a hand-built ledger, so the export is proven against data
        # the game itself produced.
        for n in range(N - 2, N + 1):
            for g in GAMES:
                H.seed_completion(page, g, n, score=80)
        expected = entry_count(page)
        assert expected == 12
        out = export_payload(page)
        # What the sheet actually shows a player must be the same string.
        page.click("#ledger-link")
        page.click("#carry-open")
        page.wait_for_selector("#carry-export-panel:not([hidden])")
        page.wait_for_function(
            "() => document.getElementById('carry-payload').value.length > 20")
        shown = page.evaluate("document.getElementById('carry-payload').value")
        assert shown.count(".") >= 3 and shown.startswith("1."), (
            "code is not in the documented wire format: %r" % shown[:40])
        manifest = page.inner_text("#carry-manifest").lower()
        assert "issue" in manifest, "the sheet should say what travels: %r" % manifest
        H.fail_on_errors(errors, "round_trip_code/export")

    with device(p, base_b) as (page, errors):
        paste_code(page, out["payload"])
        confirm_import(page)
        assert entry_count(page) == expected, (
            "pasted code did not deliver: %d vs %d" % (entry_count(page), expected))
        H.fail_on_errors(errors, "round_trip_code/import")


# ---------- merge_never_lowers ----------
def merge_never_lowers(p, base_a, base_b):
    """Origin B already has the better run. Importing a thinner, older record
    must ADD its editions without ever shortening what B had, and a same-day
    conflict must resolve to the richer entry (higher score wins)."""
    with device(p, base_a) as (page, errors):
        # A: two old, disconnected editions, plus a WEAK duplicate of one that
        # B also holds — the conflict case.
        seed_run(page, [N - 20, N - 19])
        seed_entry(page, "who", N - 2, score=10)
        out = export_payload(page)
        H.fail_on_errors(errors, "merge_never_lowers/export")

    with device(p, base_b) as (page, errors):
        seed_run(page, range(N - 4, N + 1))       # a live 5-day run
        seed_entry(page, "who", N - 2, score=95)  # B's copy is the better one
        before_streak = full_house_streak(page)
        before_entries = entry_count(page)
        assert before_streak == 5

        paste_code(page, out["payload"])
        confirm_import(page)

        after_streak = full_house_streak(page)
        assert after_streak >= before_streak, (
            "the merge LOWERED a streak: %d -> %d" % (before_streak, after_streak))
        assert after_streak == 5, (
            "old, disconnected editions should not extend today's run: %r" % after_streak)
        # 2 editions x 4 games arrived; the duplicate (who, N-2) is not new.
        assert entry_count(page) == before_entries + 8, (
            "entries not unioned: %d -> %d" % (before_entries, entry_count(page)))
        kept = page.evaluate(
            "n => __CHRONICLE_TEST__.store.getDailyEntry('who', n).score", N - 2)
        assert kept == 95, "a weaker duplicate overwrote the better record: %r" % kept
        # And the older editions really did land.
        assert page.evaluate(
            "n => !!__CHRONICLE_TEST__.store.getDailyEntry('map', n)", N - 20), (
            "the arriving record's own editions did not land")
        H.fail_on_errors(errors, "merge_never_lowers/import")


# ---------- idempotent ----------
def idempotent(p, base_a, base_b):
    """Twice is once. The second import reports 'already here' and writes
    nothing — no doubled counters, no changed streak."""
    with device(p, base_a) as (page, errors):
        seed_run(page, range(N - 2, N + 1))
        out = export_payload(page)
        H.fail_on_errors(errors, "idempotent/export")

    with device(p, base_b) as (page, errors):
        paste_code(page, out["payload"])
        confirm_import(page)
        first = page.evaluate("__CHRONICLE_TEST__.store.readAll()")

        page.click("#carry-close")
        paste_code(page, out["payload"])
        page.wait_for_selector("#carry-sheet:not([hidden])")
        page.wait_for_function(
            "() => /already/i.test(document.getElementById('carry-title').textContent)")
        assert page.locator("#carry-confirm-row").is_hidden(), (
            "a repeat import should not offer a confirm at all")
        second = page.evaluate("__CHRONICLE_TEST__.store.readAll()")
        assert first == second, "a repeat import changed stored state"
        assert "7-carry-already-here" in H.gc_events(page)
        H.fail_on_errors(errors, "idempotent/repeat")


# ---------- tampered_rejected ----------
def tampered_rejected(p, base_a, base_b):
    """Corrupt, truncated, foreign-version and outright nonsense codes are all
    refused in plain words, and none of them writes a byte."""
    with device(p, base_a) as (page, errors):
        seed_run(page, range(N - 2, N + 1))
        out = export_payload(page)
        H.fail_on_errors(errors, "tampered_rejected/export")

    good = out["payload"]
    head, sep, tail = good.rpartition(".")
    flipped = head + sep + ("B" if tail[0] != "B" else "C") + tail[1:]
    bad_codes = [
        ("flipped byte", flipped),
        ("truncated", good[: len(good) // 2]),
        ("wrong schema", "9" + good[1:]),
        ("nonsense", "have a lovely day"),
        ("empty-ish", "1.j.00000000.e30"),   # valid frame, {} inside
    ]

    with device(p, base_b) as (page, errors):
        seed_run(page, [N])
        before = page.evaluate("__CHRONICLE_TEST__.store.readAll()")
        for label, code in bad_codes:
            paste_code(page, code)
            page.wait_for_selector("#carry-sheet:not([hidden])")
            page.wait_for_function(
                "() => document.getElementById('carry-import-panel').hidden === false")
            assert page.locator("#carry-confirm-row").is_hidden(), (
                "%s was offered for import" % label)
            lede = page.inner_text("#carry-lede")
            assert len(lede) > 10, "%s got no explanation: %r" % (label, lede)
            after = page.evaluate("__CHRONICLE_TEST__.store.readAll()")
            assert after == before, "%s wrote to storage" % label
            # Checked per code, not once at the end: a rejected payload that
            # throws would otherwise show up only as a mystery storage write
            # (app.js files crashes into misc.lastError).
            H.fail_on_errors(errors, "tampered_rejected/" + label)
            page.click("#carry-close")
        assert "9-carry-code-rejected" in H.gc_events(page)
        # A tampered payload arriving as a LINK is refused the same way, and
        # is still scrubbed out of the URL.
        page.goto("%s/index.html?test=1&dailydate=%s#carry=%s" % (base_b, DATE, flipped))
        page.wait_for_function(H.BOOTED)
        page.wait_for_selector("#carry-sheet:not([hidden])")
        assert page.locator("#carry-confirm-row").is_hidden()
        assert page.evaluate("location.hash") == "", "a bad payload stayed in the URL"
        assert page.evaluate("__CHRONICLE_TEST__.store.readAll()") == before
        H.fail_on_errors(errors, "tampered_rejected")


# ---------- no_compression_fallback ----------
NO_COMPRESSION = "delete window.CompressionStream;"


def no_compression_fallback(p, base_a, base_b):
    """An old browser with no CompressionStream still exports — as plain
    base64 JSON, flagged 'j' — and a modern browser reads it back. This is the
    iPhone-on-an-old-iOS case, and it must not be a dead end."""
    with device(p, base_a, init_scripts=(NO_COMPRESSION,)) as (page, errors):
        assert page.evaluate("typeof CompressionStream") == "undefined"
        seed_run(page, range(N - 5, N + 1))
        expected = entry_count(page)
        out = export_payload(page)
        assert out["payload"].startswith("1.j."), (
            "no CompressionStream should mean the plain-JSON encoding: %r"
            % out["payload"][:8])
        H.fail_on_errors(errors, "no_compression_fallback/export")

    with device(p, base_b) as (page, errors):
        paste_code(page, out["payload"])
        confirm_import(page)
        assert entry_count(page) == expected, "uncompressed payload did not arrive"
        H.fail_on_errors(errors, "no_compression_fallback/import")

    # And the reverse: a compressed code landing on a browser that cannot
    # unpack it says so plainly instead of failing silently.
    with device(p, base_a) as (page, errors):
        seed_run(page, range(N - 2, N + 1))
        squeezed = export_payload(page)
        assert squeezed["payload"].startswith("1.d.")
        H.fail_on_errors(errors, "no_compression_fallback/squeeze")

    with device(p, base_b,
                init_scripts=("delete window.DecompressionStream;",)) as (page, errors):
        paste_code(page, squeezed["payload"])
        page.wait_for_selector("#carry-sheet:not([hidden])")
        assert page.locator("#carry-confirm-row").is_hidden()
        assert "too old" in page.inner_text("#carry-lede").lower(), (
            "an un-unpackable code should name the reason: %r"
            % page.inner_text("#carry-lede"))
        H.fail_on_errors(errors, "no_compression_fallback/no-unzip")


# ---------- hostile_payload_ignored ----------
def hostile_payload_ignored(p, base_a, _base_b):
    """A payload with a VALID checksum but hostile contents. Everything not on
    the whitelist is dropped, __proto__ never reaches Object.prototype, and the
    good parts of the same payload still land — a strict validator that simply
    refused everything would be easy and useless."""
    with device(p, base_a) as (page, errors):
        seed_run(page, [N])
        code = page.evaluate(
            """async n => {
                 const body = JSON.parse(JSON.stringify({
                   v: 1, at: Date.now(),
                   state: {
                     dailyLedger: { entries: {
                       who: { [n - 1]: { completedOn: n - 1, score: 70 },
                              'not-a-number': { completedOn: n, score: 99 } },
                       nonsense: { 5: { completedOn: 5, score: 1 } } },
                       streaks: { who: { streak: 9999, lastEdition: n } },
                       fullHouse: { streak: 9999, lastEdition: n } },
                     misc: { seenBefore: true, evil: 'hello',
                             soundMuted: 'not a boolean' },
                     map: { bestScore: 55, sneaky: 'x' },
                     somethingElse: { a: 1 },
                   },
                   flags: { skipgc: 't', 'made.up': 'x' },
                 }));
                 body.state.__proto__ = { polluted: true };
                 body.state.misc.constructor = { polluted: true };
                 return __CHRONICLE_TEST__.carry.encode(body);
               }""", N)
        paste_code(page, code)
        confirm_import(page)

        assert page.evaluate("({}).polluted === undefined"), (
            "Object.prototype was polluted by an imported payload")
        blob = page.evaluate("__CHRONICLE_TEST__.store.readAll()")
        assert "nonsense" not in blob["dailyLedger"]["entries"], "unknown game key stored"
        assert "not-a-number" not in blob["dailyLedger"]["entries"]["who"], (
            "non-numeric edition key stored")
        assert "somethingElse" not in blob, "unknown top-level key stored"
        assert "evil" not in blob["misc"], "unknown misc key stored"
        assert "polluted" not in blob["misc"], "prototype key stored as data"
        assert blob["misc"].get("soundMuted") is None, "mistyped value accepted"
        assert "sneaky" not in blob["map"], "unknown stats field stored"
        # The claimed 9999 streak is a cache, and caches are recomputed.
        assert blob["dailyLedger"]["streaks"]["who"]["streak"] < 9999, (
            "an incoming payload dictated a streak instead of earning it")
        # ...and the legitimate parts of the same payload still landed.
        assert page.evaluate(
            "n => !!__CHRONICLE_TEST__.store.getDailyEntry('who', n)", N - 1), (
            "a hostile payload's valid entries were thrown out too")
        assert blob["map"]["bestScore"] == 55, "valid stats did not land"
        H.fail_on_errors(errors, "hostile_payload_ignored")


# ---------- heavy_payload_sizes ----------
# A heavy record is the interesting case: if a year of history cannot fit in a
# URL, the UI has to lead with the copy-code. These numbers are reproduced in
# tools/out/handoff-tool-2026-07-31/REPORT.md.
SIZE_CASES = [30, 90, 180, 365]


def heavy_payload_sizes(p, base_a, _base_b):
    with device(p, base_a) as (page, errors):
        print("      editions | entries |  JSON  | deflate |   raw  |  link  | fits URL")
        for count in SIZE_CASES:
            page.evaluate(
                """c => {
                     const store = __CHRONICLE_TEST__.store;
                     const blob = store.readAll();
                     const entries = {};
                     const games = ['who', 'map', 'what', 'thread'];
                     const today = __CHRONICLE_TEST__.daily.todayIndex();
                     for (const g of games) {
                       entries[g] = {};
                       for (let i = 0; i < c; i++) {
                         const n = today - i;
                         const e = { completedOn: n, score: 60 + (i % 41) };
                         if (g === 'thread') {
                           e.detail = { solved: true, perfect: i % 3 === 0,
                             mistakes: i % 4,
                             guesses: [['yellow','yellow','yellow','yellow'],
                                       ['green','green','blue','green'],
                                       ['blue','blue','blue','purple'],
                                       ['purple','purple','purple','purple']] };
                         } else {
                           e.detail = [0, 1, 2].map(r => ({
                             id: g + '-figure-' + ((i * 3 + r) % 400),
                             pts: 40 + ((i + r) % 61), correct: r !== 2,
                             torn: (i + r) % 6, wrongs: r % 3, hints: r % 2 }));
                         }
                         entries[g][n] = e;
                       }
                     }
                     blob.dailyLedger = { entries, streaks: {},
                                          fullHouse: { streak: c, lastEdition: today } };
                     blob.misc = Object.assign(blob.misc || {},
                       { seenBefore: true, soundMuted: false,
                         introSeen: { who: true, map: true, what: true, thread: true },
                         retFired: ['ret-d1', 'ret-d7', 'ret-d30'] });
                     store.writeAll(blob);
                   }""", count)
            m = page.evaluate(
                """async () => {
                     const c = __CHRONICLE_TEST__.carry;
                     const body = c.buildState();
                     const payload = await c.encode(body);
                     return { json: JSON.stringify(body).length,
                              payload: payload.length,
                              link: c.linkFor(payload).length,
                              max: c.maxUrl };
                   }""")
            entries = count * 4
            # What the same record costs with no CompressionStream: base64url
            # of the raw JSON (4 chars per 3 bytes) plus the 12-char header.
            raw = -(-m["json"] * 4 // 3) + 12
            print("      %8d | %7d | %6d | %7d | %6d | %6d | %s"
                  % (count, entries, m["json"], m["payload"], raw, m["link"],
                     "yes" if m["link"] <= m["max"] else "NO — code path"))
            # Round-trip the heaviest shape through decode+validate so the
            # measurement is of something that actually works.
            ok = page.evaluate(
                """async () => {
                     const c = __CHRONICLE_TEST__.carry;
                     const payload = await c.encode(c.buildState());
                     const res = await c.decode(payload);
                     if (!res.ok) return 'decode failed: ' + res.reason;
                     const clean = c.validate(res.body);
                     const games = ['who', 'map', 'what', 'thread'];
                     const n = games.reduce((s, g) => s + Object.keys(
                       clean.state.dailyLedger.entries[g] || {}).length, 0);
                     return n;
                   }""")
            assert ok == entries, (
                "heavy payload lost entries at %d editions: %r" % (count, ok))
        H.fail_on_errors(errors, "heavy_payload_sizes")


TESTS = [round_trip_link, round_trip_code, merge_never_lowers, idempotent,
         tampered_rejected, no_compression_fallback, hostile_payload_ignored,
         heavy_payload_sizes]


def main():
    failures = []
    # Two origins. Same bytes, different ports — which is exactly the wall the
    # carry tool exists to get over.
    with H.server(H.PORT) as base_a, H.server(H.PORT + 11) as base_b, sync_playwright() as p:
        for t in TESTS:
            print("--", t.__name__)
            try:
                t(p, base_a, base_b)
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
