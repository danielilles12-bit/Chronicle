#!/usr/bin/env python3
"""Letters to the Editor — the player-feedback surfaces (js/feedback.js).

Approved by Daniel 5 Aug 2026 (design-reviews/install-flow-rulings.md,
"FEEDBACK PLATE"; thinking in design-reviews/feedback-plan.md).

WHAT THIS GUARDS

  1. The one gate: the Home plate stays hidden until the player's FIRST ever
     finished daily, then shows — no timers, no counters, nothing to dismiss.
  2. The destination: every surface's link is the live Google Form with the
     version field pre-filled (BUILD + coarse device), URL-encoded — the
     whole reason a bug report becomes actionable. Nothing else rides along.
  3. The stamp is franked live: denomination = today's issue number,
     postmark = the real current date.
  4. Offline: links swap to the mailto fallback and swap back.
  5. The day-done stamp card wears the right copy per face — "Tell us where
     it hurts" belongs to the win screen (and must NOT be on the plate).
  6. Every tap fires its GoatCounter event (6f family).

Gotcha kept from earlier sessions: inner_text() is CSS-uppercased, so all
text matching here is case-insensitive.
"""
import datetime
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
import helpers as H  # noqa: E402
from test_no_dead_ends import qa_force  # noqa: E402

N = H.latest_edition()
DATE = H.edition_date(N)

# Transcribed from the live form (5 Aug 2026) — must match js/feedback.js.
FORM = ("https://docs.google.com/forms/d/e/1FAIpQLScsbY9qiaomY00CABsQqPXztvjq"
        "vTy_hO4jIa9WorckJdcOUQ/viewform")
ENTRY = "entry.2050964733"

PLATE = "#letters-plate"


def build_tag(page):
    return page.inner_text("#build-tag").strip().lower()


def href(page, sel):
    return page.evaluate("s => document.querySelector(s).getAttribute('href')", sel)


def text(page, sel):
    """textContent, dodging inner_text's CSS uppercasing."""
    return page.evaluate("s => document.querySelector(s).textContent", sel)


def expected_form_url(page):
    """What every online surface must link to: form + version field."""
    line = "%s · iPhone" % build_tag(page)          # iPhone 13 device profile
    return "%s?usp=pp_url&%s=%s" % (FORM, ENTRY, urllib.parse.quote(line, safe=""))


def tap(page, sel):
    """Click a feedback link without letting it navigate (the form is an
    external host, blocked in this harness) — the tracking listener fires
    either way."""
    page.evaluate(
        "s => document.querySelector(s).addEventListener("
        "'click', e => e.preventDefault(), {once: true})", sel)
    page.click(sel)


# ---------------------------------------------------------------------------
# 1. the plate's one honest condition
# ---------------------------------------------------------------------------
def plate_hidden_until_first_daily(p, base):
    """Fresh storage: no plate (a person who has never finished a game has
    nothing to report). One finished daily — any game — and it is furniture
    forever. The quiet doors (footer word) are always there."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        assert page.locator(PLATE).is_hidden(), (
            "the Letters plate must stay hidden before the first finished daily")
        assert page.locator("#foot-write").is_visible(), (
            "the footer 'Write to us' is the day-one stranger's one door")

        # One completed daily, through the real ledger path, then a reboot
        # (the harshest refresh): the plate is now up, permanently.
        H.seed_completion(page, "who", N)
        H.boot(page, base, DATE)
        page.wait_for_selector("%s:not([hidden])" % PLATE)

        # And it also appears without a reboot, on the next visit to Home.
        H.fail_on_errors(errors, "plate gate")
    print("PASS plate_hidden_until_first_daily")


def plate_appears_without_a_reboot(p, base):
    """The same gate, live: finishing the first daily and walking back to
    Home is enough — no reload required."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        assert page.locator(PLATE).is_hidden()
        H.seed_completion(page, "map", N)
        # Leave Home and come back — the render cycle repaints the plate.
        page.evaluate("() => __CHRONICLE_TEST__.nav.show('view-ledger')")
        page.evaluate("() => __CHRONICLE_TEST__.nav.goHome()")
        page.wait_for_selector("%s:not([hidden])" % PLATE)
        H.fail_on_errors(errors, "plate live gate")
    print("PASS plate_appears_without_a_reboot")


# ---------------------------------------------------------------------------
# 2 + 3. the destination and the franked stamp
# ---------------------------------------------------------------------------
def plate_links_and_stamp(p, base):
    """The button carries the form URL with BUILD + device pre-filled and
    URL-encoded; the stamp's denomination is the live issue number and the
    postmark is the real current date. Copy is the approved plate copy —
    and 'tell us where it hurts' is NOT on it (reserved for the win screen,
    Daniel 5 Aug 2026)."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        H.seed_completion(page, "who", N)
        H.boot(page, base, DATE)
        page.wait_for_selector("%s:not([hidden])" % PLATE)

        got = href(page, "#lt-btn")
        assert got == expected_form_url(page), (
            "plate button href:\n  got      %s\n  expected %s" % (got, expected_form_url(page)))
        target = page.get_attribute("#lt-btn", "target")
        assert target == "_blank", "the form must open in a new context (swipe back intact)"

        assert H.edition_day_label(N) in text(page, "#lt-stamp-no"), (
            "stamp denomination must be the live issue number, got %r" % text(page, "#lt-stamp-no"))
        today = datetime.date.today()
        expect_pm = ("%d %s" % (today.day, today.strftime("%b"))).lower()
        # ICU's en-GB September is "Sept" where Python's %b says "Sep".
        got_pm = text(page, "#lt-postmark-date").strip().lower().replace("sept", "sep")
        assert got_pm == expect_pm, (
            "postmark must carry the real current date: got %r, expected %r"
            % (got_pm, expect_pm))

        plate_text = page.inner_text(PLATE).lower()
        for phrase in ("letters to the editor", "got opinions?", "write in.",
                       "write to the editor"):
            assert phrase in plate_text, "plate copy missing %r" % phrase
        assert "tell us where it hurts" not in plate_text, (
            "'Tell us where it hurts' is reserved for the win-screen stamp")

        tap(page, "#lt-btn")
        assert "6f-feedback-tapped-home" in H.gc_events(page)
        H.fail_on_errors(errors, "plate links")
    print("PASS plate_links_and_stamp")


def quiet_doors_link_and_count(p, base):
    """The footer word and the Legacy coupon row: same destination, their own
    tap events."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        assert href(page, "#foot-write") == expected_form_url(page)
        tap(page, "#foot-write")
        assert "6f-feedback-tapped-footer" in H.gc_events(page)

        page.evaluate("() => __CHRONICLE_TEST__.nav.show('view-ledger')")
        page.wait_for_selector("#legacy-write:visible")
        assert href(page, "#legacy-write") == expected_form_url(page)
        row = page.inner_text("#legacy-write").lower()
        assert "something to say?" in row and "write to the editor" in row
        tap(page, "#legacy-write")
        assert "6f-feedback-tapped-legacy" in H.gc_events(page)
        H.fail_on_errors(errors, "quiet doors")
    print("PASS quiet_doors_link_and_count")


# ---------------------------------------------------------------------------
# 4. offline: the mailto fallback
# ---------------------------------------------------------------------------
def offline_swaps_to_mailto(p, base):
    """The form needs a network; the app doesn't. Offline, every surface
    becomes the mailto (subject carries build + surface) and says so; back
    online, the form returns."""
    with H.app(p) as (page, errors, ctx):
        H.boot(page, base, DATE)
        H.seed_completion(page, "who", N)
        H.boot(page, base, DATE)
        page.wait_for_selector("%s:not([hidden])" % PLATE)

        ctx.set_offline(True)
        page.wait_for_function(
            "document.querySelector('#lt-btn').getAttribute('href').indexOf('mailto:') === 0")
        got = href(page, "#lt-btn")
        assert "daniel.illes12%40gmail.com" in got or "daniel.illes12@gmail.com" in got
        assert urllib.parse.quote(build_tag(page)) in got or build_tag(page) in got, (
            "the mailto subject must carry the build: %r" % got)
        assert page.get_attribute("#lt-btn", "target") is None, (
            "a mailto must not open a blank tab")
        assert "email the editor" in page.inner_text("#lt-btn").lower()
        assert page.locator("#lt-offline").is_visible(), (
            "offline, the plate must say why the button now opens a mail app")
        tap(page, "#lt-btn")
        assert "6f-feedback-tapped-mailto" in H.gc_events(page), (
            "an offline tap counts as mailto, never as a form tap")

        ctx.set_offline(False)
        page.wait_for_function(
            "document.querySelector('#lt-btn').getAttribute('href').indexOf('https://docs.google.com/') === 0")
        assert page.locator("#lt-offline").is_hidden()
        assert "write to the editor" in page.inner_text("#lt-btn").lower()
        H.fail_on_errors(errors, "offline fallback")
    print("PASS offline_swaps_to_mailto")


# ---------------------------------------------------------------------------
# 5 + 6. the day-done stamp card, both faces
# ---------------------------------------------------------------------------
def daydone_card_both_faces(p, base):
    """The Complaints Dept stamp card shows on both faces of the day-done
    screen with face-specific copy, links to the form, and counts its taps
    per face. The Home CTA above it must survive (the navigation contract —
    also enforced wholesale by test_no_dead_ends)."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE, extra="&qa=1")
        page.wait_for_selector("#qa-panel")

        if qa_force(page, "Full-house celebration", "#view-daydone:not([hidden])"):
            card = page.inner_text("#dd-letters").lower()
            assert "tell us where it hurts" in card, "the win face wears the reserved line"
            assert "complaints dept" in card
            assert "the editor reads every one" in card
            assert href(page, "#dd-letters") == expected_form_url(page)
            tap(page, "#dd-letters")
            assert "6f-feedback-tapped-fullhouse" in H.gc_events(page)
            page.click("#dd-home")
            page.wait_for_selector("#view-home:not([hidden])")

        if qa_force(page, "Streak obituary", "#view-daydone:not([hidden])"):
            card = page.inner_text("#dd-letters").lower()
            assert "any last words?" in card, "the obituary face asks for last words"
            assert "tell the editor what killed it" in card
            tap(page, "#dd-letters")
            assert "6f-feedback-tapped-obituary" in H.gc_events(page)
            page.click("#dd-home")
            page.wait_for_selector("#view-home:not([hidden])")

        H.fail_on_errors(errors, "day-done card")
    print("PASS daydone_card_both_faces")


# ---------------------------------------------------------------------------
# never on a play screen
# ---------------------------------------------------------------------------
def nothing_on_play_screens(p, base):
    """Feedback is furniture: no letters surface may live inside a .view-game
    (the loud/quiet law — play screens gain nothing)."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        offenders = page.evaluate(
            "() => Array.from(document.querySelectorAll("
            "'.view-game #letters-plate, .view-game #dd-letters,"
            " .view-game [id^=lt-]')).length")
        assert offenders == 0, "a feedback surface is inside a play screen"
        H.fail_on_errors(errors, "play screens")
    print("PASS nothing_on_play_screens")


def main():
    with sync_playwright() as p, H.server() as base:
        plate_hidden_until_first_daily(p, base)
        plate_appears_without_a_reboot(p, base)
        plate_links_and_stamp(p, base)
        quiet_doors_link_and_count(p, base)
        offline_swaps_to_mailto(p, base)
        daydone_card_both_faces(p, base)
        nothing_on_play_screens(p, base)
    print("OK test_feedback")


if __name__ == "__main__":
    main()
