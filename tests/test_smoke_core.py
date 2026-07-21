#!/usr/bin/env python3
"""Core smoke suite (P4.1): first visit, the full daily, outcome economics,
mid-round resume, keyboard-only Thread. Chromium, iPhone-13 viewport.

Each scenario runs in a fresh profile. 'Today' is pinned to the newest
manifest edition so every assertion is deterministic (see helpers).
"""
import os
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
    """Face Value: wrong −15, clue −25, tear −10, give-up scores 0."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        H.open_daily(page, "who")
        H.dismiss_intro(page, timeout=1200)
        page.wait_for_selector("#view-reveal:not([hidden])")
        assert H.reveal_worth(page) == 100
        page.fill("#rv-input", "definitely not a real answer")
        page.click("#rv-guess-btn")
        page.wait_for_selector("#rv-guesses .guess-chip")
        assert H.reveal_worth(page) == 85, "wrong guess should cost 15"
        page.click("#rv-clue-a")
        page.wait_for_selector("#rv-hint-chips .hint-chip")
        assert H.reveal_worth(page) == 60, "clue A should cost 25"
        page.locator("#rv-scraps .df-scrap.tearable").first.click()
        assert H.reveal_worth(page) == 50, "tear should cost 10"
        page.click("#rv-reveal")               # give up
        page.wait_for_selector("#rv-badge:not([hidden])")
        assert "0 pts" in page.inner_text("#rv-badge").lower()
        assert "it was" in page.inner_text("#rv-feedback").lower()
        H.fail_on_errors(errors, "outcomes_reveal")


def outcomes_map(p, base):
    """Lifeline: wrong −15, initials clue −25, reveal scores 0."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        H.open_daily(page, "map")
        H.dismiss_intro(page)
        page.wait_for_selector("#view-map:not([hidden])")
        assert H.map_worth(page) == 100
        page.fill("#map-input", "definitely not a real answer")
        page.click("#map-guess-btn")
        page.wait_for_selector("#map-guesses .guess-chip")
        assert H.map_worth(page) == 85, "wrong guess should cost 15"
        page.click("#hint-ini")
        assert H.map_worth(page) == 60, "initials clue should cost 25"
        page.click("#map-reveal")
        page.wait_for_selector("#map-feedback:not([hidden])")
        assert "0 pts" in page.inner_text("#map-feedback").lower()
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
        assert page.locator("#rv-hint-chips .hint-chip").count() == 1
        assert page.locator("#rv-clue-a").is_disabled()
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
        page.click("#hint-ini")
        worth = H.map_worth(page)
        assert worth == 100 - 15 - 25, "setup arithmetic drifted"
        page.click("#map-quit")
        H.boot(page, base, DATE)
        H.open_daily(page, "map")
        page.wait_for_selector("#view-map:not([hidden])")
        assert H.map_worth(page) == worth, "worth changed across quit/reopen"
        assert page.locator("#map-guesses .guess-chip").count() == 1
        assert page.locator("#map-hint-chips .hint-chip").count() == 1
        assert page.locator("#hint-ini").is_disabled()
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


TESTS = [first_visit, daily_all_four, outcomes_reveal, outcomes_map,
         outcomes_thread, resume_reveal, resume_map, thread_keyboard]


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
