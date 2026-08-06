#!/usr/bin/env python3
"""Core smoke suite (P4.1): first visit, the full daily, outcome economics,
mid-round resume, keyboard-only Thread. Chromium, iPhone-13 viewport.

Each scenario runs in a fresh profile. 'Today' is pinned to the newest
manifest edition so every assertion is deterministic (see helpers).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
import helpers as H  # noqa: E402

N = H.latest_edition()
DATE = H.edition_date(N)


# ---------- first_visit ----------
def first_visit(p, base):
    """Fresh profile: home paints, stranger CTA opens Face Value, first round
    playable with zero interstitials."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base)                     # the real today — what a stranger gets
        assert page.inner_text("#dateline").strip(), "dateline empty"
        page.wait_for_selector("#stranger-hero:not([hidden])")
        assert page.evaluate("document.body.classList.contains('is-stranger')")
        assert page.locator("#home-rows .game-row").count() == 4
        page.click("#stranger-play")
        page.wait_for_selector("#view-reveal:not([hidden])")
        assert page.locator("#intro-card").is_hidden(), "intro card interstitial shown"
        assert page.locator("#rv-scraps .df-scrap").count() == 9
        assert page.evaluate("__CHRONICLE_TEST__.revealDebug.tornCount()") == 1
        assert H.reveal_worth(page) == 100
        page.locator("#rv-scraps .df-scrap.tearable").first.click()
        assert H.reveal_worth(page) == 90, "first paid tear should cost 10"
        H.fail_on_errors(errors, "first_visit")


# ---------- the_mark_while_it_loads ----------
def the_mark_while_it_loads(p, base):
    """The opening seconds carry the Antinous and nothing else.

    The retired pink-sunglasses David has twice survived a swap by hiding in a
    file nobody re-read, and both times it landed on the LAUNCH imagery — the
    masthead mark, the home-screen icon, the iOS startup image. That is the
    first thing anyone sees, so it gets its own assertion.

    Nothing here waits on a stopwatch: the mark is asserted to be in the SERVED
    HTML, which is what makes it appear before any script runs (boot() in
    app.js leans on the same fact), and then asserted to have really painted."""
    with H.app(p) as (page, errors, _ctx):
        asked = []
        page.on("request", lambda r: asked.append(r.url))
        page.goto(H.app_url(base, DATE), wait_until="commit")

        # In the served markup, so it is up before a single data byte lands.
        html = page.evaluate("() => fetch('index.html').then(r => r.text())")
        mark = re.search(r"<img[^>]*class=\"masthead-sticker\"[^>]*>", html)
        assert mark, "no masthead mark in the served HTML — it must not wait on JS"
        assert "antinous" in mark.group(0), mark.group(0)

        # And it really painted, rather than 404ing into an empty box.
        sticker = page.locator(".masthead-sticker")
        sticker.wait_for(state="visible")
        assert page.evaluate(
            "() => { const i = document.querySelector('.masthead-sticker');"
            " return i.complete && i.naturalWidth > 0; }"), "masthead mark never painted"
        assert "antinous" in sticker.get_attribute("src"), sticker.get_attribute("src")

        # The launch imagery declared in <head>: the tab icon, the home-screen
        # icon, and the startup images iOS bakes in at install time.
        head = page.evaluate(
            "() => [...document.querySelectorAll('link[rel*=icon], link[rel*=startup-image]')]"
            "        .map(l => l.getAttribute('href'))")
        assert len(head) >= 20, "expected the full icon + startup-image set, got %d" % len(head)
        assert all("david" not in h.lower() for h in head), head

        page.wait_for_function(H.BOOTED)

        # Nothing the app fetched, at any point in the boot, was David brand art.
        brand = [u for u in asked
                 if any(d in u for d in ("/assets/brand/", "/assets/intro/",
                                         "/assets/splash/", "/icons/"))]
        assert brand, "boot fetched no brand art at all"
        stray = [u for u in brand if "david" in u.rsplit("/", 1)[-1].lower()]
        assert not stray, "boot fetched retired David brand art: %s" % stray
        H.fail_on_errors(errors, "the_mark_while_it_loads")


# ---------- daily_all_four ----------
def daily_all_four(p, base):
    """Play all four dailies correctly; verify ledger, full-house celebration,
    punch card, and locked re-entry."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)

        H.open_daily(page, "who")
        H.dismiss_intro(page, timeout=1200)    # 'who' teach-by-doing: normally none
        H.play_reveal_daily(page)
        page.click("#rv-sum-back")             # home

        H.open_daily(page, "map")
        H.dismiss_intro(page)
        H.play_map_daily(page)
        # Game two: the install screen opens over this summary (js/install.js).
        H.dismiss_install(page)
        page.click("#sum-back")

        H.open_daily(page, "what")
        H.dismiss_intro(page)
        H.play_reveal_daily(page)
        page.click("#rv-sum-back")

        board = H.thread_board(page, N)
        H.open_daily(page, "thread")
        H.dismiss_intro(page)
        H.play_thread_daily(page, board)
        assert page.inner_text("#conn-sum-total").strip() == "100"
        page.click("#conn-sum-back")           # home -> triggers the celebration

        page.wait_for_selector("#view-daydone:not([hidden])")
        assert page.inner_text("#dd-title").lower() == "you made history."

        led = H.ledger(page)
        for g in ("who", "map", "what", "thread"):
            e = led["entries"].get(g, {}).get(str(N))
            assert e, "missing ledger entry for %s" % g
            assert e["score"] > 0, "zero score recorded for %s" % g
            assert e["completedOn"] == N
        assert led["fullHouse"]["streak"] >= 1

        # P5.1: every round here was answered correctly, first try, with no
        # clues bought — each should read as a "clean" outcome, and the whole
        # (fast, headless) run as the fastest duration bucket. Expected count
        # comes from the ledger's own detail, not a hardcoded round count —
        # today's manifest edition may still be pre-recipe-change (10 rounds)
        # rather than the target 5 (P1.4).
        events = H.gc_events(page)
        game_display = {"who": "facevalue", "map": "lifeline", "what": "relic", "thread": "thread"}
        for g, name in game_display.items():
            assert ("4-dur-%s-u2" % name) in events, (
                "missing fast duration bucket for %s: %r" % (g, events))
            clean = "4-round-%s-clean" % name
            entry = led["entries"][g][str(N)]
            expected = 1 if g == "thread" else len(entry["detail"])
            assert events.count(clean) == expected, (
                "expected %d clean round outcomes for %s, got %d: %r"
                % (expected, g, events.count(clean), events))

        page.click("#dd-home")
        page.wait_for_selector("#view-home:not([hidden])")
        page.wait_for_selector("#punch-card:not([hidden])")
        assert page.locator("#punch-card .punch-day.punched").count() >= 1

        # Locked re-entry: the hero opens the read-only receipt, not the game.
        before = led["entries"]["who"][str(N)]
        H.open_daily(page, "who")
        page.wait_for_selector("#view-revealsum:not([hidden])")
        assert page.locator("#view-reveal").is_hidden(), "completed daily replayable"
        assert page.locator("#rv-sum-again").is_hidden(), "replay offered on a locked daily"
        after = H.ledger(page)["entries"]["who"][str(N)]
        assert after == before, "locked re-entry mutated the ledger entry"
        H.fail_on_errors(errors, "daily_all_four")


# ---------- outcomes ----------
def outcomes_reveal(p, base):
    """Face Value: wrong −15, clue −25, tear −10, three-choices −80 (floor
    10), wrong pick scores 0 and reveals — the give-up path since v142."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        H.open_daily(page, "who")
        H.dismiss_intro(page, timeout=1200)
        page.wait_for_selector("#view-reveal:not([hidden])")
        assert H.reveal_worth(page) == 100
        page.fill("#rv-input", "definitely not a real answer")
        page.click("#rv-guess-btn")
        H.dismiss_guess_warn(page, timeout=800)
        page.wait_for_selector("#rv-guesses .guess-chip")
        assert H.reveal_worth(page) == 85, "wrong guess should cost 15"
        page.click("#rv-clue-a")
        # Clue pricing (5 Aug 2026): the bought clue takes the button's slot.
        page.wait_for_selector("#rv-controls .hint-chip")
        assert page.locator("#rv-clue-a").is_hidden(), (
            "a bought clue must replace its control, not sit beside it")
        assert H.reveal_worth(page) == 60, "clue A should cost 25"
        page.locator("#rv-scraps .df-scrap.tearable").first.click()
        assert H.reveal_worth(page) == 50, "tear should cost 10"
        page.click("#rv-mcq")
        page.wait_for_selector("#rv-mcq-chips button")
        assert H.reveal_worth(page) == 10, (
            "three choices costs 80, floored at the 10-pt minimum")
        answer = page.evaluate("window.__CHRONICLE_TEST__.revealRound.name")
        chips = page.locator("#rv-mcq-chips button").all_inner_texts()
        wrong = next(c for c in chips if c.strip().lower() != answer.lower())
        page.click(f"#rv-mcq-chips button:has-text('{wrong}')")
        page.wait_for_selector("#rv-badge:not([hidden])")
        assert "0 pts" in page.inner_text("#rv-badge").lower()
        assert "it was" in page.inner_text("#rv-feedback").lower()
        assert "4-round-facevalue-lost" in H.gc_events(page), (
            "a wrong pick should record a lost round outcome")
        H.fail_on_errors(errors, "outcomes_reveal")


def outcomes_map(p, base):
    """Lifeline: wrong −15, initials clue −25, three-choices −80 (floor 10),
    correct pick pays the floored worth without extending the streak."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        H.open_daily(page, "map")
        H.dismiss_intro(page)
        page.wait_for_selector("#view-map:not([hidden])")
        assert H.map_worth(page) == 100
        page.fill("#map-input", "definitely not a real answer")
        page.click("#map-guess-btn")
        H.dismiss_guess_warn(page, timeout=800)
        page.wait_for_selector("#map-guesses .guess-chip")
        assert H.map_worth(page) == 85, "wrong guess should cost 15"
        page.click("#hint-ini")
        assert H.map_worth(page) == 60, "initials clue should cost 25"
        page.click("#map-mcq")
        page.wait_for_selector("#map-mcq-chips button")
        assert H.map_worth(page) == 10, (
            "three choices costs 80, floored at the 10-pt minimum")
        answer = page.evaluate("window.__CHRONICLE_TEST__.mapRound.name")
        page.click(f"#map-mcq-chips button:has-text('{answer}')")
        page.wait_for_selector("#map-feedback:not([hidden])")
        fb = page.inner_text("#map-feedback").lower()
        assert "+10 pts" in fb, "correct pick should pay the floored worth"
        assert "picked from three" in fb
        events = H.gc_events(page)
        assert "4-round-lifeline-fought" in events, (
            "correct pick after a wrong guess reads as a fought round")
        assert "4-mcq-lifeline-win" in events, "mcq win should be tracked"
        H.fail_on_errors(errors, "outcomes_map")


def outcomes_thread(p, base):
    """Thread: one-away feedback, then a full loss (four mistakes, 0 pts)."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        board = H.thread_board(page, N)
        H.open_daily(page, "thread")
        H.dismiss_intro(page)
        page.wait_for_selector("#view-conn:not([hidden])")
        a, b = board["groups"][0], board["groups"][1]
        for i in range(4):                     # 3-of-A + 1-of-B, four times = loss
            H.click_tiles(page, a["items"][:3] + [b["items"][i]])
            page.click("#conn-submit")
            if i == 0:
                page.wait_for_selector("#conn-feedback:not([hidden])")
                assert page.inner_text("#conn-feedback").lower() == "one thread loose."
        page.wait_for_selector("#view-connsum:not([hidden])")
        assert page.inner_text("#conn-sum-total").strip() == "0"
        assert "snapped" in page.inner_text("#conn-sum-msg").lower()
        led = H.ledger(page)
        assert led["entries"]["thread"][str(N)]["score"] == 0
        assert "4-round-thread-lost" in H.gc_events(page), (
            "a snapped thread should record a lost round outcome")
        H.fail_on_errors(errors, "outcomes_thread")


# ---------- resume_integrity ----------
def resume_reveal(p, base):
    """Face Value mid-round quit with 2 tears + 1 wrong + 1 clue resumes
    score-identical."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        H.open_daily(page, "who")
        H.dismiss_intro(page, timeout=1200)
        page.wait_for_selector("#view-reveal:not([hidden])")
        page.locator("#rv-scraps .df-scrap.tearable").first.click()
        page.locator("#rv-scraps .df-scrap.tearable").first.click()
        page.fill("#rv-input", "definitely not a real answer")
        page.click("#rv-guess-btn")
        H.dismiss_guess_warn(page, timeout=800)
        page.click("#rv-clue-a")
        worth = H.reveal_worth(page)
        assert worth == 100 - 20 - 15 - 25, "setup arithmetic drifted"
        page.click("#rv-quit")
        H.boot(page, base, DATE)               # full reload: cold resume
        H.open_daily(page, "who")
        page.wait_for_selector("#view-reveal:not([hidden])")
        page.wait_for_function("__CHRONICLE_TEST__.revealDebug !== undefined")
        assert H.reveal_worth(page) == worth, "worth changed across quit/reopen"
        assert page.evaluate("__CHRONICLE_TEST__.revealDebug.tornCount()") == 3
        assert page.locator("#rv-guesses .guess-chip").count() == 1
        assert page.locator("#rv-controls .hint-chip").count() == 1
        assert page.locator("#rv-clue-a").is_hidden()
        assert "3-resume-facevalue" in H.gc_events(page), (
            "resuming a saved daily should fire resume-who")
        H.fail_on_errors(errors, "resume_reveal")


def resume_map(p, base):
    """Lifeline mid-round quit with 1 wrong + 1 clue resumes score-identical."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        H.open_daily(page, "map")
        H.dismiss_intro(page)
        page.wait_for_selector("#view-map:not([hidden])")
        page.fill("#map-input", "definitely not a real answer")
        page.click("#map-guess-btn")
        H.dismiss_guess_warn(page, timeout=800)
        page.click("#hint-ini")
        worth = H.map_worth(page)
        assert worth == 100 - 15 - 25, "setup arithmetic drifted"
        page.click("#map-quit")
        H.boot(page, base, DATE)
        H.open_daily(page, "map")
        page.wait_for_selector("#view-map:not([hidden])")
        assert H.map_worth(page) == worth, "worth changed across quit/reopen"
        assert page.locator("#map-guesses .guess-chip").count() == 1
        assert page.locator("#map-hints .hint-chip").count() == 1
        assert page.locator("#hint-ini").is_hidden()
        assert "3-resume-lifeline" in H.gc_events(page), (
            "resuming a saved daily should fire resume-map")
        H.fail_on_errors(errors, "resume_map")


# ---------- thread_keyboard ----------
def thread_keyboard(p, base):
    """Complete a Thread board with the keyboard only."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        board = H.thread_board(page, N)
        H.open_daily(page, "thread")
        try:
            page.wait_for_selector("#intro-card:not([hidden])", timeout=3000)
            assert H.tab_until(page, lambda i: i["id"] == "intro-play")
            page.keyboard.press("Enter")
            page.wait_for_selector("#intro-card", state="hidden")
        except AssertionError:
            raise
        except Exception:
            pass                               # intro already seen: straight in
        page.wait_for_selector("#view-conn:not([hidden])")
        for g in board["groups"]:
            for item in g["items"]:
                ok = H.tab_until(
                    page, lambda i, item=item:
                    "conn-tile" in i["cls"] and i["text"] == item)
                assert ok, "could not Tab to tile %r" % item
                page.keyboard.press("Space")
            assert H.tab_until(page, lambda i: i["id"] == "conn-submit")
            page.keyboard.press("Enter")
            if g is not board["groups"][-1]:
                page.wait_for_selector("#conn-found .conn-group-%s" % g["colour"])
        page.wait_for_selector("#view-connsum:not([hidden])")
        assert page.inner_text("#conn-sum-total").strip() == "100"
        H.fail_on_errors(errors, "thread_keyboard")


# ---------- clue_prices_are_true ----------
def clue_prices_are_true(p, base):
    """Clue pricing (Daniel, 5 Aug 2026): no control may quote a deduction the
    10-point floor would swallow. The rescue always shows what it LEAVES; an
    ordinary clue switches from "−25" to "· leaves 10" once the floor bites;
    the worth line says MINIMUM at the bottom; and Relic says WORTH, not INK."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        H.open_daily(page, "who")
        H.dismiss_intro(page, timeout=1200)
        page.wait_for_selector("#view-reveal:not([hidden])")
        # Untouched round: 100 − 80 = 20, and that is what the button says.
        assert "drops to 20" in page.inner_text("#rv-mcq").lower(), \
            page.inner_text("#rv-mcq")
        assert "each tear" in page.inner_text("#rv-worth").lower()
        # Spend 25: the rescue's real remainder is now the floor, not 100 − 80.
        page.click("#rv-clue-a")
        page.wait_for_selector("#rv-controls .hint-chip")
        assert "drops to 10" in page.inner_text("#rv-mcq").lower(), \
            page.inner_text("#rv-mcq")
        # Drive to the floor: every remaining price becomes an outcome.
        for i in range(6):
            page.fill("#rv-input", "definitely not the answer %d" % i)
            page.click("#rv-guess-btn")
            H.dismiss_guess_warn(page, timeout=800)
        assert H.reveal_worth(page) == 10
        worth = page.inner_text("#rv-worth").lower()
        assert "minimum" in worth and "each tear" not in worth, worth
        assert "drops to 10" in page.inner_text("#rv-clue-b").lower(), \
            "a clue the floor would truncate must not quote its nominal price"
        assert "guess" == page.inner_text("#rv-guess-btn").strip().lower(), \
            "the Guess button carries no price now — the warning sheet does it"
        # Relic shares the label (the old "INK" variant is gone).
        page.click("#rv-quit")
        H.open_daily(page, "what")
        H.dismiss_intro(page, timeout=1200)
        page.wait_for_selector("#view-reveal:not([hidden])")
        assert page.inner_text("#rv-worth").lower().startswith("worth"), \
            page.inner_text("#rv-worth")
        H.fail_on_errors(errors, "clue_prices_are_true")


# ---------- the_rescue_closes_the_shop ----------
def _pick_chip(page, wrap, name):
    """Click the chip whose text is `name`. inner_text comes back CSS-
    uppercased, so match case-insensitively and click by index rather than
    by a :has-text() selector (names carry apostrophes)."""
    chips = [c.strip().lower() for c in page.locator(wrap + " button").all_inner_texts()]
    page.locator(wrap + " button").nth(chips.index(name.strip().lower())).click()


def rescue_closes_reveal(p, base):
    """Face Value: the three-choices rescue drops the round to its floor, so
    every other clue and every further tear would cost NOTHING. Buying it
    therefore closes them (Daniel, 5 Aug 2026): the clue slips go out of
    service and stop quoting prices they cannot charge, the picture freezes
    where the player paid to leave it, and a resumed session comes back
    locked — while what an honest player scores is untouched (a clean round
    plus the rescue still pays 20)."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        H.open_daily(page, "who")
        H.dismiss_intro(page, timeout=1200)
        page.wait_for_selector("#view-reveal:not([hidden])")
        assert H.reveal_worth(page) == 100
        assert page.locator("#rv-scraps .df-scrap.tearable").count() > 0

        page.click("#rv-mcq")
        page.wait_for_selector("#rv-mcq-chips button")
        assert H.reveal_worth(page) == 20, "an untouched round plus the rescue is worth 20"

        # The clue slips: dead, and quoting nothing.
        for sel in ("#rv-clue-a", "#rv-clue-b"):
            assert page.locator(sel).is_disabled(), (
                "%s is still buyable after the rescue — a free clue" % sel)
        label = page.inner_text("#rv-clue-a").lower()      # slip A always has content
        assert label.strip(), "a locked slip must still say what it was"
        assert "−" not in label and "drops to" not in label, (
            "a locked slip must not quote a price it can no longer charge: %r" % label)

        # The picture: frozen. Nothing tearable, every untorn scrap a real
        # disabled control, and a tap on one moves neither grid nor worth.
        assert page.locator("#rv-scraps .df-scrap.tearable").count() == 0
        assert page.locator('#rv-scraps .df-scrap[aria-disabled="true"]').count() == 8
        torn = page.evaluate("__CHRONICLE_TEST__.revealDebug.tornCount()")
        # force=True: aria-disabled already makes Playwright (and a screen
        # reader) refuse the control, so the tap has to be forced past the
        # actionability check to prove the handler itself also refuses.
        page.locator("#rv-scraps .df-scrap.locked").first.click(force=True)
        assert page.evaluate("__CHRONICLE_TEST__.revealDebug.tornCount()") == torn, (
            "a scrap still tore after the rescue — the free-reveal exploit")
        assert H.reveal_worth(page) == 20
        worth_line = page.inner_text("#rv-worth").lower()
        assert "each tear" not in worth_line, (
            "the worth line still prices a tear nobody can make: %r" % worth_line)

        # Quit mid-rescue, come back cold: same three choices, still locked.
        page.click("#rv-quit")
        H.boot(page, base, DATE)
        H.open_daily(page, "who")
        page.wait_for_selector("#view-reveal:not([hidden])")
        page.wait_for_function("__CHRONICLE_TEST__.revealDebug !== undefined")
        assert page.locator("#rv-mcq-chips button").count() == 3
        assert H.reveal_worth(page) == 20, "worth changed across quit/reopen"
        for sel in ("#rv-clue-a", "#rv-clue-b"):
            assert page.locator(sel).is_disabled(), (
                "a resumed rescue re-opened %s" % sel)
        assert page.locator("#rv-scraps .df-scrap.tearable").count() == 0, (
            "a resumed rescue re-opened the picture")

        # And it pays exactly what it paid before the lock existed.
        answer = page.evaluate("__CHRONICLE_TEST__.revealRound.name")
        _pick_chip(page, "#rv-mcq-chips", answer)
        page.wait_for_selector("#rv-badge:not([hidden])")
        assert "+20 pts" in page.inner_text("#rv-badge").lower(), page.inner_text("#rv-badge")
        assert "picked from three" in page.inner_text("#rv-feedback").lower()

        # Answered: the next round opens its shop again.
        last = "results" in page.inner_text("#rv-next").lower()
        page.click("#rv-next")
        if not last:
            page.wait_for_selector("#rv-scraps .df-scrap.tearable")
            assert page.locator("#rv-clue-a").is_enabled(), "clues stayed shut into the next round"
            assert H.reveal_worth(page) == 100
        H.fail_on_errors(errors, "rescue_closes_reveal")


def rescue_closes_map(p, base):
    """Lifeline: same ruling, and it has no scraps — the two clue slips are
    the whole of the shop. They close when the rescue opens, stay closed
    across a quit/resume, and the pick still pays the same 20."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        H.open_daily(page, "map")
        H.dismiss_intro(page)
        page.wait_for_selector("#view-map:not([hidden])")
        assert H.map_worth(page) == 100

        page.click("#map-mcq")
        page.wait_for_selector("#map-mcq-chips button")
        assert H.map_worth(page) == 20, "an untouched round plus the rescue is worth 20"
        for sel in ("#hint-occ", "#hint-ini"):
            assert page.locator(sel).is_disabled(), (
                "%s is still buyable after the rescue — a free clue" % sel)
            label = page.inner_text(sel).lower()
            assert label.strip(), "a locked slip must still say what it was"
            assert "−" not in label and "drops to" not in label, (
                "a locked slip must not quote a price it can no longer charge: %r" % label)

        page.click("#map-quit")
        H.boot(page, base, DATE)
        H.open_daily(page, "map")
        page.wait_for_selector("#view-map:not([hidden])")
        assert page.locator("#map-mcq-chips button").count() == 3
        assert H.map_worth(page) == 20, "worth changed across quit/reopen"
        for sel in ("#hint-occ", "#hint-ini"):
            assert page.locator(sel).is_disabled(), "a resumed rescue re-opened %s" % sel

        answer = page.evaluate("__CHRONICLE_TEST__.mapRound.name")
        _pick_chip(page, "#map-mcq-chips", answer)
        page.wait_for_selector("#map-feedback:not([hidden])")
        fb = page.inner_text("#map-feedback").lower()
        assert "+20 pts" in fb, "correct pick should still pay the floored worth: %r" % fb
        assert "picked from three" in fb
        H.fail_on_errors(errors, "rescue_closes_map")


TESTS = [first_visit, the_mark_while_it_loads, daily_all_four, outcomes_reveal,
         outcomes_map, outcomes_thread, resume_reveal, resume_map,
         thread_keyboard, clue_prices_are_true, rescue_closes_reveal,
         rescue_closes_map]


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
