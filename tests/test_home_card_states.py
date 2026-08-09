#!/usr/bin/env python3
"""One marker per puzzle: the Home card state system (Daniel, 9 Aug 2026).

Home used to report where you were in words — "Done · 33 pts" and "Resume
today's puzzle" on the big cards, "N pts" and "Resume" on the archive stubs
underneath them. Two sizes of card, two dialects, both competing with the game
names they sat under. They are replaced by one drawn language, used identically
at both sizes (js/app.js: cardState/stateHTML, css/style.css: .cs-*):

    ●  a puzzle finished          ○  a puzzle not started
    ◐  the puzzle you are inside  ›  there is still play to do
    ✓ 33 PTS  finished, and what it paid

The rule this file exists to hold is the COUNTING one. Face Value, Lifeline and
Relic run three rounds a day, so they show three marks. Thread is ONE puzzle
and shows ONE — its four groups and its four allowed mistakes are the inside of
that puzzle, and drawing them on Home as four marks would promise a player
something about how much is left that simply is not true. A regression there
would look plausible on screen, which is exactly why it is asserted from every
angle below.

Everything drawn here is aria-hidden, so each scenario also checks that the
state survived into the card's accessible name.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
import helpers as H  # noqa: E402

N = H.latest_edition()
DATE = H.edition_date(N)
GAMES = ["who", "map", "what", "thread"]
LABELS = {"who": "Face Value", "map": "Lifeline",
          "what": "Relic", "thread": "Thread"}

# Leave stranger mode without touching any of the four games under test: close
# the OLDEST reachable archive day of Thread. (One finished daily of any kind
# is what ends stranger mode; the Archive is regulars' furniture.)
LEAVE_STRANGER = """(n) => __CHRONICLE_TEST__.daily.recordDailyCompletion('thread', n,
  {score: 55, detail: {solved: true, perfect: false, mistakes: 2, guesses: []}});"""

# A half-played rounds session, written in the shape revealgame.js/mapgame.js
# actually persist: `ids` is the day's rounds, `results` the ones answered.
SEED_ROUNDS = """(a) => __CHRONICLE_TEST__.store.setDailySession(
  'chronicle.daily.' + a.g + '.' + a.n,
  {ids: ['r1', 'r2', 'r3'],
   results: Array.from({length: a.done},
     (_, i) => ({id: 'r' + (i + 1), pts: 40, correct: true})),
   score: 40 * a.done});"""

# A half-played Thread board, in connectionsgame.js's shape. `found` and
# `mistakes` are deliberately non-trivial: the display must ignore both.
SEED_THREAD = """(a) => __CHRONICLE_TEST__.store.setDailySession(
  'chronicle.daily.thread.' + a.n,
  {found: a.found, mistakes: a.mistakes, guesses: []});"""

SEED_DONE = """(a) => __CHRONICLE_TEST__.daily.recordDailyCompletion(a.g, a.n,
  {score: a.s, detail: a.g === 'thread'
     ? {solved: true, perfect: false, mistakes: 1, guesses: []}
     : [{pts: a.s, correct: true}]});"""

# One card's drawn state, whichever size it is.
STATE = """(sel) => {
  const card = document.querySelector(sel);
  if (!card) return null;
  const row = card.querySelector('.hero-state, .day-state');
  return {
    marks: [...row.querySelectorAll('.cs-mark')]
      .map(m => m.className.replace('cs-mark cs-', '')),
    chevrons: row.querySelectorAll('.cs-chev').length,
    ticks: row.querySelectorAll('.cs-tick').length,
    words: row.innerText.trim(),
    hidden: row.getAttribute('aria-hidden'),
    label: card.getAttribute('aria-label') || '',
    tagline: (() => { const t = card.querySelector('.hero-tagline');
      return t ? (t.offsetParent !== null) : null; })(),
  };
}"""

HERO = '[data-hero="%s"]'
DAY = '[data-row="%s"] [data-days] [data-edition-index="%d"]'


def state(page, sel):
    st = page.evaluate(STATE, sel)
    assert st is not None, "no card matched %s" % sel
    return st


def home(page, base):
    """Reload and land on a painted returning-player Home."""
    H.boot(page, base, DATE)
    for _ in range(4):
        if page.locator("#install-screen:not([hidden])").count():
            page.click("#install-back")
            continue
        if page.locator("#view-daydone:not([hidden])").count():
            page.click("#dd-home")
            continue
        break
    page.wait_for_selector("#view-home:not([hidden])")
    page.wait_for_selector("#home-rows[data-built]")


def regular(page, base):
    """A player with history, nothing played today."""
    H.boot(page, base, DATE)
    page.evaluate(LEAVE_STRANGER, N - 6)
    home(page, base)


# ---------- not_started ----------
def not_started(p, base):
    """Untouched cards, big and small: the description (or the weekday and
    date) plus a chevron, and nothing else. No marks — an unopened game has no
    progress to show, and three empty circles would read as "0 of 3 done",
    which is a heavier statement than silence."""
    with H.app(p) as (page, errors, _ctx):
        regular(page, base)
        for g in GAMES:
            st = state(page, HERO % g)
            assert st["marks"] == [], \
                "%s: an untouched card is showing progress marks %r" % (g, st["marks"])
            assert st["chevrons"] == 1, \
                "%s: an untouched card should offer exactly one chevron" % g
            assert st["ticks"] == 0, "%s: an untouched card has a checkmark" % g
            assert st["words"] == "", \
                "%s: an untouched card is printing %r" % (g, st["words"])
            assert st["tagline"], "%s: the tagline vanished from an untouched card" % g
            assert st["label"] == "Play today's %s" % LABELS[g], \
                "%s: untouched accessible name reads %r" % (g, st["label"])
            # ...and the same day, one row down.
            d = state(page, DAY % (g, N - 1))
            assert d["marks"] == [] and d["chevrons"] == 1 and d["words"] == "", \
                "%s: an untouched day card is not silent-plus-chevron: %r" % (g, d)
            assert "not played" in d["label"].lower(), \
                "%s: untouched day card accessible name reads %r" % (g, d["label"])
            # The weekday and the date are still the card's headline.
            card = page.locator(DAY % (g, N - 1))
            assert card.locator(".day-weekday").inner_text().strip(), \
                "%s: a day card lost its weekday" % g
            assert card.locator(".day-date").inner_text().strip(), \
                "%s: a day card lost its date" % g
        H.fail_on_errors(errors, "not_started")


# ---------- three_round_progress ----------
def three_round_progress(p, base):
    """Face Value, Lifeline and Relic: three marks, and the right three.

        inside round 1  → ◐ ○ ○
        one done        → ● ◐ ○
        two done        → ● ● ◐

    The marks are read from the REAL saved session, so each case is seeded in
    the shape the games persist rather than through a display-only hook."""
    cases = [(0, ["half", "todo", "todo"]),
             (1, ["done", "half", "todo"]),
             (2, ["done", "done", "half"])]
    with H.app(p) as (page, errors, _ctx):
        regular(page, base)
        for done, want in cases:
            for g in ("who", "map", "what"):
                page.evaluate(SEED_ROUNDS, {"g": g, "n": N, "done": done})
                page.evaluate(SEED_ROUNDS, {"g": g, "n": N - 2, "done": done})
            home(page, base)
            for g in ("who", "map", "what"):
                st = state(page, HERO % g)
                assert st["marks"] == want, \
                    "%s with %d rounds answered draws %r, expected %r" % (
                        g, done, st["marks"], want)
                assert st["chevrons"] == 1, \
                    "%s in progress lost the chevron that says there is play left" % g
                assert st["ticks"] == 0, "%s in progress is showing a checkmark" % g
                assert st["words"] == "", \
                    "%s in progress is printing %r" % (g, st["words"])
                assert st["tagline"], "%s lost its tagline while in progress" % g
                spoken = st["label"].lower()
                assert "in progress" in spoken and "resume" in spoken, \
                    "%s: in-progress accessible name reads %r" % (g, st["label"])
                if done:
                    assert "of three rounds completed" in spoken, \
                        "%s: %r does not say how far in the player is" % (g, st["label"])
                # the archive stub tells the same story at the same edition
                d = state(page, DAY % (g, N - 2))
                assert d["marks"] == want, \
                    "%s day card draws %r, expected %r" % (g, d["marks"], want)
                assert d["chevrons"] == 1 and d["words"] == "", \
                    "%s day card in progress is not marks-plus-chevron: %r" % (g, d)
                assert "resume" in d["label"].lower(), \
                    "%s: in-progress day card accessible name reads %r" % (g, d["label"])
        H.fail_on_errors(errors, "three_round_progress")


# ---------- thread_is_one_puzzle ----------
def thread_is_one_puzzle(p, base):
    """Thread shows ONE half mark, whatever is going on inside the board.

    The failure this guards is a plausible-looking one: Thread has four groups
    and four allowed mistakes, and a four-unit progress display would look
    perfectly reasonable on screen while telling the player something false —
    Home is counting PUZZLES, and Thread is one. So every board state below,
    from untouched-but-started to three groups found and three mistakes spent,
    must draw exactly one mark."""
    boards = [([], 1), (["yellow"], 0), (["yellow", "green"], 2),
              (["yellow", "green", "blue"], 3)]
    with H.app(p) as (page, errors, _ctx):
        regular(page, base)
        for found, mistakes in boards:
            page.evaluate(SEED_THREAD, {"n": N, "found": found, "mistakes": mistakes})
            page.evaluate(SEED_THREAD, {"n": N - 2, "found": found, "mistakes": mistakes})
            home(page, base)
            why = "thread with %d found / %d mistakes: " % (len(found), mistakes)
            for sel in (HERO % "thread", DAY % ("thread", N - 2)):
                st = state(page, sel)
                assert st["marks"] == ["half"], \
                    why + "drew %r, expected exactly one half mark" % st["marks"]
                assert len(st["marks"]) != 4, why + "four marks — Thread is one puzzle"
                assert st["chevrons"] == 1, why + "lost its chevron"
                assert st["words"] == "", why + "printed %r" % st["words"]
            hero = state(page, HERO % "thread")
            assert hero["tagline"], why + "the tagline vanished"
            assert "in progress" in hero["label"].lower(), \
                why + "accessible name reads %r" % hero["label"]
            # Nothing anywhere on Home counts groups or mistakes.
            assert "of four" not in page.inner_text("#home-rows").lower(), \
                why + "Home is counting Thread's groups"
        H.fail_on_errors(errors, "thread_is_one_puzzle")


# ---------- completed ----------
def completed(p, base):
    """A finished card: tagline (or weekday and date), ✓ and the real score,
    no chevron, no "Done" — and it still opens its locked result."""
    # 100 is the cap on a day's score, so the archive copy goes DOWN by one:
    # the point is that the two cards read their own day, not each other's.
    scores = {"who": 33, "map": 64, "what": 100, "thread": 72}
    with H.app(p) as (page, errors, _ctx):
        regular(page, base)
        for g, s in scores.items():
            page.evaluate(SEED_DONE, {"g": g, "n": N, "s": s})
            page.evaluate(SEED_DONE, {"g": g, "n": N - 3, "s": s - 1})
        home(page, base)
        for g, s in scores.items():
            st = state(page, HERO % g)
            assert st["marks"] == [], "%s: a finished card is showing progress marks" % g
            assert st["chevrons"] == 0, \
                "%s: a finished card still offers a chevron — there is no play left" % g
            assert st["ticks"] == 1, "%s: a finished card has no checkmark" % g
            assert st["words"] == "%d PTS" % s, \
                "%s: finished card reads %r, expected the real score %d" % (
                    g, st["words"], s)
            assert st["tagline"], "%s: the tagline vanished from a finished card" % g
            assert st["label"] == "%s, completed, %d points, view results" % (LABELS[g], s), \
                "%s: finished accessible name reads %r" % (g, st["label"])
            d = state(page, DAY % (g, N - 3))
            assert d["chevrons"] == 0 and d["ticks"] == 1, \
                "%s: a finished day card is not ✓-plus-score: %r" % (g, d)
            assert d["words"] == "%d PTS" % (s - 1), \
                "%s: finished day card reads %r" % (g, d["words"])
            assert "%d points" % (s - 1) in d["label"].lower(), \
                "%s: finished day card accessible name reads %r" % (g, d["label"])

        # No status sentence survives anywhere in the strip, at any size.
        strip = page.inner_text("#home-rows").lower()
        for word in ("done", "resume", "in progress", "untouched", "play ›"):
            assert word not in strip, "%r is still printed on Home" % word

        # ...and a finished card is still a door to its own result.
        page.click(HERO % "what")
        page.wait_for_selector("#view-revealsum:not([hidden])")
        assert "100" in page.inner_text("#rv-sum-total"), \
            "a finished hero card opened the wrong receipt"
        page.click("#rv-sum-home")
        page.wait_for_selector("#view-home:not([hidden])")
        page.click(DAY % ("thread", N - 3))
        page.wait_for_selector("#view-connsum:not([hidden])")
        assert "71" in page.inner_text("#conn-sum-total"), \
            "a finished day card opened the wrong receipt"
        H.fail_on_errors(errors, "completed")


# ---------- marks_are_decoration ----------
def marks_are_decoration(p, base):
    """Every shape is hidden from assistive technology, the cards are still
    real buttons, and the keyboard still reaches them."""
    with H.app(p) as (page, errors, _ctx):
        regular(page, base)
        page.evaluate(SEED_ROUNDS, {"g": "who", "n": N, "done": 1})
        page.evaluate(SEED_DONE, {"g": "map", "n": N, "s": 64})
        home(page, base)

        bad = page.evaluate(
            """() => [...document.querySelectorAll(
                 '#home-rows .hero-state, #home-rows .day-state')]
                 .filter(e => e.getAttribute('aria-hidden') !== 'true').length""")
        assert bad == 0, "%d state rows are not aria-hidden" % bad
        # Nothing decorative may carry text an assistive tool would read out.
        assert page.evaluate(
            """() => [...document.querySelectorAll(
                 '#home-rows .cs-mark, #home-rows .cs-chev, #home-rows .cs-tick')]
                 .every(e => e.textContent === '')"""), \
            "a state shape is carrying text"

        # Full-card buttons, and the keyboard opens one.
        tags = page.evaluate(
            """() => [...document.querySelectorAll(
                 '#home-rows .hero-card, #home-rows .day-card')].map(e => e.tagName)""")
        assert set(tags) == {"BUTTON"}, "a Home card is not a button: %r" % set(tags)
        assert H.tab_until(page, lambda i: "day-card" in (i["cls"] or "")), \
            "Tab never reached an archive card"
        page.keyboard.press("Enter")
        H.dismiss_intro(page, timeout=2500)
        page.wait_for_selector("#view-home", state="hidden")
        H.fail_on_errors(errors, "marks_are_decoration")


# ---------- loading_and_retry_still_speak ----------
def loading_and_retry_still_speak(p, base):
    """The one exception to "no words": a card that cannot load says so, on
    screen, and the tap still works once the file is back. Drawn state must
    never push that message into an invisible element."""
    blocked = {"editions": True}

    def route(r):
        host = r.request.url.split("/")[2].split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            r.abort()                                  # hermetic, as everywhere
        elif blocked["editions"] and "/data/editions.json" in r.request.url:
            r.abort()
        else:
            r.continue_()

    with H.app(p, block_external=False) as (page, errors, ctx):
        ctx.route("**/*", route)
        page.goto(H.app_url(base, DATE))
        page.wait_for_selector("#home-rows[data-built]")
        page.evaluate(LEAVE_STRANGER, N - 6)
        page.goto(H.app_url(base, DATE))
        page.wait_for_selector("#home-rows[data-built]")

        page.click(HERO % "map")
        page.wait_for_function(
            """() => (document.querySelector('[data-hero="map"] [data-status]')
                 .innerText || '').toLowerCase().includes('retry')""", timeout=15000)
        shown = page.evaluate(
            """() => { const c = document.querySelector('[data-hero="map"]');
                 const s = c.querySelector('[data-status]');
                 return {text: s.innerText, visible: s.offsetParent !== null,
                         state: c.querySelector('.hero-state').offsetParent !== null}; }""")
        assert shown["visible"], "the retry message is in the markup but not on screen"
        assert "retry" in shown["text"].lower(), shown["text"]
        assert shown["state"], "the card lost its state row while reporting a failure"

        blocked["editions"] = False
        page.click(HERO % "map")
        H.dismiss_intro(page, timeout=4000)
        page.wait_for_selector("#view-map:not([hidden])", timeout=15000)
        # The blocked download is the point here and the browser logs it as a
        # failed resource; every OTHER console error still counts.
        H.fail_on_errors([e for e in errors if "data/editions.json" not in e],
                         "loading_and_retry_still_speak")


# ---------- archive_shape_survives ----------
def archive_shape_survives(p, base):
    """Marks cost the archive nothing: same card width and height, the same
    peek of the next card, no sideways scroll — and the stubs still open the
    edition they name."""
    with H.app(p) as (page, errors, _ctx):
        regular(page, base)
        page.evaluate(SEED_DONE, {"g": "who", "n": N - 1, "s": 91})
        page.evaluate(SEED_ROUNDS, {"g": "map", "n": N - 2, "done": 2})
        home(page, base)

        geom = page.evaluate("""() => {
          const out = [];
          for (const k of ['who', 'map', 'what', 'thread']) {
            const hero = document.querySelector('[data-hero="' + k + '"]');
            const day = document.querySelector(
              '[data-row="' + k + '"] [data-days] .day-card');
            const h = hero.getBoundingClientRect(), d = day.getBoundingClientRect();
            const g = hero.querySelector('.hero-glyph').getBoundingClientRect();
            const cs = getComputedStyle(hero);
            out.push({game: k, heroH: h.height, dayW: d.width, dayH: d.height,
                      glyphH: g.height, peek: innerWidth - d.left,
                      colH: hero.querySelector('.hero-col').getBoundingClientRect().height,
                      pad: parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom),
                      dayOverflow: day.scrollWidth - day.clientWidth});
          }
          return out;
        }""")
        for r in geom:
            why = r["game"] + ": "
            assert r["dayW"] == 96, why + "the day stub is %.0fpx wide, not 96" % r["dayW"]
            assert r["dayH"] == 124, why + "the day stub is %.0fpx tall, not 124" % r["dayH"]
            assert r["dayOverflow"] <= 0, \
                why + "%.0fpx of a day card's content is off its own edge" % r["dayOverflow"]
            assert r["peek"] >= 24, \
                why + "only %.0fpx of the next card shows" % r["peek"]
            assert r["glyphH"] == 136, why + "the icon moved off 136px"
            # The bottom row is only allowed to exist inside the height the
            # picture already occupies. If it pushes the card taller, the
            # picture stops filling it — the thing both geometry guards in
            # test_stranger_home.py and test_archive_window.py are for.
            assert r["colH"] <= r["glyphH"] + 1, (
                why + "the state row grew the text column to %.1fpx, past the "
                "%.0fpx picture — the card is now taller than its own art"
                % (r["colH"], r["glyphH"]))
            assert r["heroH"] <= 173, \
                why + "the hero card grew to %.1fpx" % r["heroH"]
        assert page.evaluate(
            "() => document.documentElement.scrollWidth <= "
            "document.documentElement.clientWidth"), "Home scrolls horizontally"

        # And the stubs still do their three jobs. START an untouched day...
        page.click(DAY % ("what", N - 4))
        H.dismiss_intro(page, timeout=1500)
        page.wait_for_selector("#view-reveal:not([hidden])")
        want = page.evaluate(
            "n => __CHRONICLE_TEST__.daily.getEdition('what', n)[0].id", N - 4)
        assert page.evaluate("__CHRONICLE_TEST__.revealRound.id") == want, \
            "an untouched stub opened the wrong edition"
        page.locator("#rv-scraps .df-scrap.tearable").first.click()
        torn = page.evaluate("__CHRONICLE_TEST__.revealDebug.tornCount()")
        page.click("#rv-quit")
        page.wait_for_selector("#view-home:not([hidden])")

        # ...which now reads as one round opened, and RESUMES on the next tap.
        st = state(page, DAY % ("what", N - 4))
        assert st["marks"] == ["half", "todo", "todo"], \
            "a genuinely half-played stub draws %r" % st["marks"]
        page.click(DAY % ("what", N - 4))
        page.wait_for_selector("#view-reveal:not([hidden])")
        assert page.evaluate("__CHRONICLE_TEST__.revealRound.id") == want, \
            "the stub restarted the day instead of resuming it"
        assert page.evaluate("__CHRONICLE_TEST__.revealDebug.tornCount()") == torn, \
            "the resumed round lost the scraps that were already torn"
        page.click("#rv-quit")
        page.wait_for_selector("#view-home:not([hidden])")

        # ...and REOPENS a finished one, read-only, on its own receipt.
        page.click(DAY % ("who", N - 1))
        page.wait_for_selector("#view-revealsum:not([hidden])")
        assert "91" in page.inner_text("#rv-sum-total"), \
            "a finished stub did not reopen its own receipt"
        H.fail_on_errors(errors, "archive_shape_survives")


TESTS = [not_started, three_round_progress, thread_is_one_puzzle, completed,
         marks_are_decoration, loading_and_retry_still_speak,
         archive_shape_survives]


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
