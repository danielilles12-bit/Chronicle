#!/usr/bin/env python3
"""The Challenge Rally (Daniel, 19 Aug 2026).

A share link now carries the dare — ?play=<game>&e=<edition>&s=<score> — and
this suite is the rail on everything the link promises:

- the recipient opens the EXACT challenged day while it is reachable, greeted
  by the score to beat (strip in the game, stamp on a first-timer's intro);
- the recipient's own today answers everything else: a future edition (sender
  past their midnight / ahead a timezone) NEVER unlocks early, an expired one
  bridges honestly — no choice screens, no lies;
- garbage params degrade to a plain arrival (links are text anyone can edit);
- a challenged receipt answers the dare: verdict line, "Send your score back ›",
  sendback (not share) analytics;
- a full-house dare (e+s, no game) lands as the N/400 strip on Home;
- and the 19 Aug full-house ruling: ALL FOUR PLAYED closes the house — a day
  with losses gets the same You Made History as a sweep (the "Some got away"
  strip is gone).

See HOUSE_RULES.md "Sharing (what a share actually is)" and "Full house
means played, not won".
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
import helpers as H  # noqa: E402

N = H.latest_edition()
DATE = H.edition_date(N)


def challenge_opens_named_day(p, base):
    """A dare on YESTERDAY's Relic: the intro wears the 87/100 stamp for a
    first-timer, and the game itself wears the strip — naming the day, since
    it isn't today's puzzle."""
    y = N - 1
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE, extra="&play=what&e=%d&s=87" % y)
        page.wait_for_selector("#intro-card:not([hidden])")
        assert page.locator("#intro-challenge").is_visible(), (
            "a first-timer's intro must wear the challenge stamp")
        assert "87/100 TO BEAT" in page.inner_text("#intro-challenge"), (
            "stamp lost the score: %r" % page.inner_text("#intro-challenge"))
        page.click("#intro-play")
        page.wait_for_selector("#view-reveal:not([hidden])")
        strip = page.locator("#view-reveal .challenge-strip")
        assert strip.is_visible(), "the challenged game must wear the strip"
        text = strip.inner_text()
        assert "87/100" in text and "RELIC" in text.upper(), (
            "strip lost the dare: %r" % text)
        events = H.gc_events(page)
        for ev in ("1-land-share-relic", "1-land-challenge-relic",
                   "3-start-from-share-relic"):
            assert ev in events, "missing %s in %r" % (ev, events)
        assert not page.evaluate(
            "new URLSearchParams(location.search).has('e')"), (
            "challenge params must be scrubbed after routing")
        H.fail_on_errors(errors, "challenge_opens_named_day")
    print("PASS challenge_opens_named_day")


def future_and_expired_links_clamp(p, base):
    """e beyond the recipient's today (unaired) or past the archive window:
    both open TODAY with the honest bridged strip — never tomorrow's puzzle,
    never a refusal."""
    for e, label in ((N + 1, "future"), (N - 10, "expired")):
        with H.app(p) as (page, errors, _ctx):
            H.boot(page, base, DATE, extra="&play=what&e=%d&s=64" % e)
            H.dismiss_intro(page)
            page.wait_for_selector("#view-reveal:not([hidden])")
            strip = page.locator("#view-reveal .challenge-strip")
            assert strip.is_visible(), "%s link should still carry the dare" % label
            text = strip.inner_text().upper()
            assert "ANOTHER DAY" in text and "TODAY" in text, (
                "%s link must bridge honestly, got %r" % (label, text))
            H.fail_on_errors(errors, "clamp_" + label)
    print("PASS future_and_expired_links_clamp")


def garbage_params_degrade(p, base):
    """Links are plain text anyone can edit: a nonsense score means a plain
    arrival — game opens, no strip, no challenge landing counted."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE, extra="&play=what&e=abc&s=banana")
        H.dismiss_intro(page)
        page.wait_for_selector("#view-reveal:not([hidden])")
        strip = page.locator("#view-reveal .challenge-strip")
        assert strip.count() == 0 or not strip.is_visible(), (
            "garbage params must not conjure a dare")
        events = H.gc_events(page)
        assert "1-land-share-relic" in events, "still a share landing"
        assert not any(e.startswith("1-land-challenge") for e in events), (
            "garbage params must not count as a challenge landing: %r" % events)
        H.fail_on_errors(errors, "garbage_params_degrade")
    print("PASS garbage_params_degrade")


def sendback_verdict_on_the_receipt(p, base):
    """Finish the dared puzzle: the receipt shows the verdict, the button says
    Send yours back ›, and the copy counts as sendback — never plain share."""
    with H.app(p) as (page, errors, ctx):
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=base)
        H.boot(page, base, DATE, extra="&play=what&e=%d&s=1" % N)
        H.dismiss_intro(page)
        H.play_reveal_daily(page)
        page.wait_for_selector("#rv-sum-share:not([hidden])")
        verdict = page.locator("#rv-sum-challenge-verdict")
        assert verdict.is_visible(), "challenged receipt must show the verdict"
        assert "/100" in verdict.inner_text(), (
            "verdict lost its scores: %r" % verdict.inner_text())
        # inner_text arrives CSS-uppercased (see test_stranger_home).
        assert page.inner_text("#rv-sum-share").strip().upper().startswith("SEND YOUR SCORE BACK"), (
            "challenged receipt's button must offer the send-back, got %r"
            % page.inner_text("#rv-sum-share"))
        events = H.gc_events(page)
        assert "4-challenge-relic-beat" in events, (
            "a 1/100 dare against a clean run must verdict as beat: %r" % events)
        page.click("#rv-sum-share")
        page.wait_for_function(
            "document.querySelector('#rv-sum-share').textContent"
            ".indexOf('Copied') === 0")
        clip = page.evaluate("navigator.clipboard.readText()")
        assert "/play/relic?e=%d&s=" % N in clip, (
            "the send-back must dare the SAME day back: %r" % clip)
        events = H.gc_events(page)
        assert any(e.startswith("6-sendback-relic") for e in events), (
            "a challenged share must count as sendback: %r" % events)
        assert "6-shared-relic" not in events, (
            "a challenged share must not also count as a plain share")
        H.fail_on_errors(errors, "sendback_verdict_on_the_receipt")
    print("PASS sendback_verdict_on_the_receipt")


def day_challenge_lands_on_home(p, base):
    """e+s with no game named: the whole issue is the dare — Home wears the
    N/400 strip and the landing is counted."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE, extra="&e=%d&s=291" % N)
        page.wait_for_selector("#challenge-strip:not([hidden])")
        text = page.inner_text("#challenge-strip")
        assert "291/400" in text, "Home strip lost the day dare: %r" % text
        assert "1-land-challenge-day" in H.gc_events(page)
        assert not page.evaluate(
            "new URLSearchParams(location.search).has('s')"), (
            "day-challenge params must be scrubbed after routing")
        H.fail_on_errors(errors, "day_challenge_lands_on_home")
    print("PASS day_challenge_lands_on_home")


THREAD_LOSS = {"solved": False, "perfect": False, "mistakes": 4,
               "guesses": [["yellow"] * 4] * 4}


def losses_still_close_the_house(p, base):
    """Full house means PLAYED, not won (19 Aug 2026): three wins and a lost
    Thread still end the day in You Made History — same screen, same
    Challenge a friend share, no quiet consolation strip anywhere."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        for g in ("who", "map", "what"):
            H.seed_completion(page, g, N, score=80, detail=[])
        H.seed_completion(page, "thread", N, score=0, detail=THREAD_LOSS)
        H.boot(page, base, DATE)
        page.wait_for_selector("#view-daydone:not([hidden])")
        assert page.inner_text("#dd-title").strip().upper() == "YOU MADE HISTORY.", (
            "a day with a loss must celebrate exactly like a sweep, got %r"
            % page.inner_text("#dd-title"))
        page.wait_for_selector("#dd-share:not([hidden])")
        assert page.inner_text("#dd-share").strip().upper() == "CHALLENGE A FRIEND", (
            "the day-done share is challenge-first, got %r"
            % page.inner_text("#dd-share"))
        assert page.locator("#issue-closed").count() == 0, (
            "the retired 'Some got away' strip must stay gone")
        H.fail_on_errors(errors, "losses_still_close_the_house")
    print("PASS losses_still_close_the_house")


def day_rally_closes(p, base):
    """A full-house dare is remembered across sittings (misc.dayChallenge)
    and answered on the celebration: /400 verdict, Send your score back,
    strip retired once the issue is closed."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE, extra="&e=%d&s=100" % N)   # sitting one
        page.wait_for_selector("#challenge-strip:not([hidden])")
        for g in ("who", "map", "what"):
            H.seed_completion(page, g, N, score=80, detail=[])
        H.seed_completion(page, "thread", N, score=0, detail=THREAD_LOSS)
        H.boot(page, base, DATE)                             # sitting two
        page.wait_for_selector("#view-daydone:not([hidden])")
        assert page.locator("#dd-challenge-verdict").is_visible(), (
            "the celebration must answer a remembered day dare")
        vt = page.inner_text("#dd-challenge-verdict")
        assert "/400" in vt and "240" in vt, (
            "day verdict lost its numbers: %r" % vt)
        assert page.inner_text("#dd-share").strip().upper().startswith("SEND YOUR SCORE BACK"), (
            "day-done share must become the send-back, got %r"
            % page.inner_text("#dd-share"))
        assert "4-challenge-day-beat" in H.gc_events(page), (
            "240 against a 100 dare must verdict as beat: %r" % H.gc_events(page))
        page.click("#dd-home")
        assert not page.locator("#challenge-strip").is_visible(), (
            "the strip retires once the issue is closed")
        H.fail_on_errors(errors, "day_rally_closes")
    print("PASS day_rally_closes")


def landing_pages_carry_the_cards(p, base):
    """Build 2: /play/<slug> serves each game's own preview card to crawlers
    (static og: tags — no JS required) and bounces humans into the challenged
    game with every param preserved."""
    import urllib.request
    for slug in ("face-value", "lifeline", "relic", "thread"):
        html = urllib.request.urlopen("%s/play/%s/" % (base, slug)).read().decode()
        assert ('og:image" content="https://yesternerd.app/assets/brand/card-%s.jpg"'
                % slug) in html, "%s landing lost its card" % slug
        assert 'property="og:title"' in html and 'name="twitter:card"' in html, (
            "%s landing lost its preview tags" % slug)
    with H.app(p) as (page, errors, _ctx):
        page.goto("%s/play/relic/?e=%d&s=87&dailydate=%s" % (base, N, DATE))
        H.dismiss_intro(page)
        page.wait_for_selector("#view-reveal:not([hidden])")
        strip = page.locator("#view-reveal .challenge-strip")
        assert strip.is_visible() and "87/100" in strip.inner_text(), (
            "the landing page must deliver the dare into the app")
        H.fail_on_errors(errors, "landing_pages_carry_the_cards")
    print("PASS landing_pages_carry_the_cards")


TESTS = [
    challenge_opens_named_day,
    future_and_expired_links_clamp,
    garbage_params_degrade,
    sendback_verdict_on_the_receipt,
    day_challenge_lands_on_home,
    losses_still_close_the_house,
    day_rally_closes,
    landing_pages_carry_the_cards,
]


def main():
    failed = []
    with H.server() as base:
        with sync_playwright() as p:
            for t in TESTS:
                try:
                    t(p, base)
                except Exception as e:
                    failed.append(t.__name__)
                    print("FAIL %s: %s" % (t.__name__, e))
    print("\n%d/%d challenge scenarios passed" % (len(TESTS) - len(failed), len(TESTS)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
