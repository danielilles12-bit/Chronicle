#!/usr/bin/env python3
"""The field line (percentile board — plan of 5 Aug 2026 + Daniel's same-day
wording override).

What must hold:

  * under 10 players the results screen renders NOTHING — no line, no
    placeholder, byte-identical to the pre-feature screen;
  * 10-19 shows the honest small-field line, 20-49 approximate words,
    50+ a percentage rounded to the nearest 5 (band consts live at the top
    of js/percentile.js);
  * any failure (endpoint dark, non-200, junk body) or the opt-out toggle
    renders nothing and never blocks the flow;
  * practice and Encore runs never POST at all;
  * only TODAY's edition posts (the line says "today's players");
  * the POST carries exactly {edition, game, score, token}, and the token is
    stable within an edition (that is the dedup) while meaning nothing.

The endpoint is stubbed with page.route — the server function itself is a
curl-level check against a Cloudflare preview branch, per the plan, not a
Playwright concern. The no-dead-ends contract is asserted by its own suite
(tests/test_no_dead_ends.py), which this feature must leave green.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
import helpers as H  # noqa: E402

N = H.latest_edition()
DATE = H.edition_date(N)

THREAD_DETAIL = {"solved": True, "perfect": False, "mistakes": 1, "guesses": []}

# The exact copy, straight from js/percentile.js wording() (curly quotes and
# all) — a drifted word here should fail loudly, not fuzzily.
SMALL = "You’re among the first %d players of today’s issue."
APPROX = "Your %d beat about %d in 10 of today’s players."
PCT = "Your %d beat %d%% of today’s players."


# ---------- local plumbing ----------
def stub(page, state, calls):
    """Route /api/score at page level (beats the context-level silent stub in
    helpers): record every POST body, then answer per state['mode'] —
    'ok' (JSON from state['resp']), 'http500', 'junk', or 'abort'."""
    def handler(route):
        try:
            calls.append(json.loads(route.request.post_data))
        except Exception:
            calls.append(None)
        mode = state.get("mode", "ok")
        if mode == "abort":
            route.abort()
        elif mode == "http500":
            route.fulfill(status=500, body="")
        elif mode == "junk":
            route.fulfill(status=200, content_type="application/json",
                          body="not json {")
        else:
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(state["resp"]))
    page.route("**/api/score", handler)


def field(page, sel="#sum-field"):
    """{hidden, text} of a summary's field-line element. textContent, not
    inner_text — .df-receipt-meta is CSS-uppercased and inner_text lies."""
    return page.evaluate(
        "sel => { const el = document.querySelector(sel);"
        " return { hidden: el.hidden, text: el.textContent }; }", sel)


def open_locked_map(page):
    page.click('[data-hero="map"]')
    page.wait_for_selector("#view-mapsum:not([hidden])")


def go_home(page):
    page.click("#sum-home")
    page.wait_for_selector("#view-home:not([hidden])")


def scrub_endpoint_noise(errors):
    """Deliberate endpoint failures log resource errors; the page itself must
    stay clean. Chromium's text carries no URL, so filter by phrase."""
    errors[:] = [e for e in errors
                 if "Failed to load resource" not in e and "api/score" not in e]


# ---------- scenarios ----------
def wording_tiers_on_screen(p, base):
    """Every band, boundaries included, through the real results screen —
    a completed Lifeline daily reopened from Home (same render path as the
    live finish, renderLockedSummary)."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        state, calls = {"resp": {"below": 0, "total": 0}}, []
        stub(page, state, calls)
        H.seed_completion(page, "map", N, score=84)
        cases = [
            ({"below": 2, "total": 5}, None),
            ({"below": 8, "total": 9}, None),            # boundary: 9 is silent
            ({"below": 3, "total": 10}, SMALL % 10),     # boundary: 10 speaks
            ({"below": 18, "total": 19}, SMALL % 19),
            ({"below": 14, "total": 20}, APPROX % (84, 7)),  # boundary: words start
            ({"below": 34, "total": 49}, APPROX % (84, 7)),
            ({"below": 25, "total": 50}, PCT % (84, 50)),    # boundary: % starts
            ({"below": 170, "total": 200}, PCT % (84, 85)),
            ({"below": 172, "total": 200}, PCT % (84, 85)),  # 86 rounds to 85
        ]
        for resp, want in cases:
            state["resp"] = resp
            open_locked_map(page)
            if want is None:
                page.wait_for_timeout(500)
                got = field(page)
                assert got["hidden"] and got["text"] == "", (
                    "field %r should stay silent, got %r" % (resp, got))
            else:
                page.wait_for_selector("#sum-field:not([hidden])")
                got = field(page)
                assert got["text"] == want, (
                    "field %r: want %r got %r" % (resp, want, got["text"]))
            go_home(page)
        # analytics honesty: percentile-shown fired once per VISIBLE line only
        shown = [e for e in H.gc_events(page) if e == "4-percentile-shown"]
        assert len(shown) == len([c for c in cases if c[1]]), shown
        # one meaningless token, stable across the edition (this is the dedup)
        tokens = set(c["token"] for c in calls)
        assert len(tokens) == 1, "token should be stable within an edition: %r" % tokens
        assert all(c["edition"] == N and c["game"] == "map" and c["score"] == 84
                   for c in calls), calls[:2]
        H.fail_on_errors(errors, "wording_tiers_on_screen")


def wording_bands_exhaustive(p, base):
    """Sweep wording() itself for every total 1..60: silence below FIELD_MIN
    and the right shape (small / approx / %-to-nearest-5) above it."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        bad = page.evaluate("""
        () => {
          const px = __CHRONICLE_TEST__.percentile;
          const bad = [];
          for (let total = 1; total <= 60; total++) {
            for (const below of [0, Math.floor(total / 2), total - 1]) {
              const line = px.wording(84, below, total);
              if ((total < px.FIELD_MIN) !== (line === null)) {
                bad.push([below, total, line]); continue;
              }
              if (line === null) continue;
              if (total < px.FIELD_APPROX_MIN) {
                if (line.indexOf('among the first ' + total + ' players') === -1)
                  bad.push([below, total, line]);
              } else if (total < px.FIELD_PERCENT_MIN) {
                if (!/about [1-9] in 10|back of today|nearly all/.test(line))
                  bad.push([below, total, line]);
              } else {
                // Same two worded extremes as the approximate band, so a
                // bare 0% or 100% never reaches the screen.
                if (/back of today|nearly all/.test(line)) continue;
                const m = line.match(/beat (\\d+)% of/);
                if (!m || (+m[1]) % 5 !== 0) bad.push([below, total, line]);
                else if (+m[1] <= 0 || +m[1] >= 100) bad.push([below, total, line]);
              }
            }
          }
          return bad.slice(0, 5);
        }
        """)
        assert not bad, "wording bands broken (first offenders): %r" % bad
        H.fail_on_errors(errors, "wording_bands_exhaustive")


def failures_render_nothing(p, base):
    """Endpoint dark, non-200, junk JSON: the screen is its pre-feature self
    and the flow (summary -> Home) never blocks."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        state, calls = {"resp": {"below": 170, "total": 200}}, []
        stub(page, state, calls)
        H.seed_completion(page, "map", N, score=84)
        for mode in ("abort", "http500", "junk"):
            state["mode"] = mode
            open_locked_map(page)
            page.wait_for_timeout(600)
            got = field(page)
            assert got["hidden"] and got["text"] == "", (mode, got)
            go_home(page)
        assert "4-percentile-shown" not in H.gc_events(page)
        scrub_endpoint_noise(errors)
        H.fail_on_errors(errors, "failures_render_nothing")


def toggle_off_means_no_post(p, base):
    """The home-footer toggle: off = NO request at all (not posted-but-
    hidden); back on, the same screen speaks again."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        state, calls = {"resp": {"below": 170, "total": 200}}, []
        stub(page, state, calls)
        H.seed_completion(page, "map", N, score=84)
        assert page.inner_text("#compare-toggle").strip().lower().endswith(" on")
        page.click("#compare-toggle")
        assert page.evaluate("localStorage.getItem('skipcompare')") == "t"
        open_locked_map(page)
        page.wait_for_timeout(500)
        got = field(page)
        assert got["hidden"] and not calls, (got, calls)
        go_home(page)
        page.click("#compare-toggle")
        open_locked_map(page)
        page.wait_for_selector("#sum-field:not([hidden])")
        assert len(calls) == 1, calls
        gc = H.gc_events(page)
        assert "4-percentile-opted-out" in gc and "4-percentile-opted-in" in gc
        H.fail_on_errors(errors, "toggle_off_means_no_post")


def daily_posts_encore_does_not(p, base):
    """A really-played daily posts exactly once with the exact payload shape;
    the Encore run straight after posts nothing and shows nothing."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        state, calls = {"resp": {"below": 170, "total": 200}}, []
        stub(page, state, calls)
        H.open_daily(page, "map")
        H.dismiss_intro(page)
        H.play_map_daily(page)
        page.wait_for_selector("#sum-field:not([hidden])")
        assert len(calls) == 1, calls
        body = calls[0]
        assert set(body.keys()) == {"edition", "game", "score", "token"}, body
        assert body["edition"] == N and body["game"] == "map", body
        assert isinstance(body["score"], int) and 0 <= body["score"] <= 100, body
        assert isinstance(body["token"], str) and len(body["token"]) >= 8, body
        # Encore: practice family — replayable, traceless, and silent here
        assert not page.is_hidden("#sum-encore"), "encore should be on offer"
        page.click("#sum-encore")
        H.play_map_daily(page)
        H.dismiss_install(page)   # 2nd finished game can trigger the install ask
        page.wait_for_timeout(500)
        got = field(page)
        assert len(calls) == 1 and got["hidden"], (calls, got)
        H.fail_on_errors(errors, "daily_posts_encore_does_not")


def practice_never_posts(p, base):
    """An archive practice run (past the repair window, so genuinely
    practice) completes without a single POST and without the line."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        state, calls = {"resp": {"below": 170, "total": 200}}, []
        stub(page, state, calls)
        # leave stranger mode so the archive bar is on screen
        H.seed_completion(page, "thread", N, score=100, detail=THREAD_DETAIL)
        page.evaluate("__CHRONICLE_TEST__.nav.goHome()")
        page.click('[data-archive="map"]')
        page.wait_for_selector("#view-archive:not([hidden])")
        n = N - 5   # aired, inside the trailing-7 window, PAST the repair window
        page.click('.cal-cell[data-edition="%d"]' % n)
        page.wait_for_selector("#archive-picker:not([hidden])")
        page.click('[data-practice-game="map"]')
        H.play_map_daily(page)
        page.wait_for_timeout(500)
        got = field(page)
        assert not calls and got["hidden"], (calls, got)
        H.fail_on_errors(errors, "practice_never_posts")


def only_today_posts(p, base):
    """A daily summary for any edition that is not TODAY's (repair-window
    completions, reopened past days) stays silent and sends nothing."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        state, calls = {"resp": {"below": 170, "total": 200}}, []
        stub(page, state, calls)
        page.evaluate(
            "n => __CHRONICLE_TEST__.percentile.renderFieldLine("
            "'sum-field', 'map', n, 84, true)", N - 1)
        page.wait_for_timeout(400)
        got = field(page)
        assert not calls and got["hidden"], (calls, got)
        H.fail_on_errors(errors, "only_today_posts")


def thread_and_reveal_carry_the_line(p, base):
    """The other two summary screens carry the line too, and all games of one
    edition share one token (so the server can dedup a device per day
    without ever identifying it)."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        state, calls = {"resp": {"below": 170, "total": 200}}, []
        stub(page, state, calls)
        H.seed_completion(page, "who", N, score=61)
        H.seed_completion(page, "thread", N, score=80, detail=THREAD_DETAIL)
        page.click('[data-hero="who"]')
        page.wait_for_selector("#view-revealsum:not([hidden])")
        page.wait_for_selector("#rv-sum-field:not([hidden])")
        assert field(page, "#rv-sum-field")["text"] == PCT % (61, 85)
        page.click("#rv-sum-home")
        page.wait_for_selector("#view-home:not([hidden])")
        page.click('[data-hero="thread"]')
        page.wait_for_selector("#view-connsum:not([hidden])")
        page.wait_for_selector("#conn-sum-field:not([hidden])")
        assert field(page, "#conn-sum-field")["text"] == PCT % (80, 85)
        assert len(set(c["token"] for c in calls)) == 1, calls
        assert set(c["game"] for c in calls) == {"who", "thread"}, calls
        H.fail_on_errors(errors, "thread_and_reveal_carry_the_line")


TESTS = [wording_tiers_on_screen, wording_bands_exhaustive,
         failures_render_nothing, toggle_off_means_no_post,
         daily_posts_encore_does_not, practice_never_posts,
         only_today_posts, thread_and_reveal_carry_the_line]


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
