#!/usr/bin/env python3
"""Save it as an app — the install flow (js/install.js), end to end.

WHAT THIS GUARDS

The install ask is the app's biggest long-term conversion moment and it is
also the easiest thing in the app to get wrong invisibly: almost every branch
is unreachable on whatever phone you happen to be holding, which is exactly
how the old "tap Share in the bar below" survived for months while being
factually wrong on every iPhone shipped this year. So every branch is forced
and inspected here, headlessly, on every CI run.

Covered:
  1. detection — the right branch for the right browser, standalone first
  2. every screen renders, carries the house ‹ chip (the navigation contract,
     measured with test_no_dead_ends' own geometry), and its way back works
  3. timing — 2 completed games before the ask, today and Archive days both
     counting,
     decline -> strip, strip × -> one final offer at a 7-day streak, then
     silence; webviews at 1 game, at most twice
  4. the guaranteed fallback: COPY THE LINK really writes the clipboard
  5. the webview warning banner on Home (11 Aug 2026) — in-app browsers
     only, names the app, routes to the escape screen, × snoozes 7 days
  6. an installed app is NEVER pitched an install, and reports itself once

Gotcha kept from earlier sessions: inner_text() is CSS-uppercased, so all text
matching here is case-insensitive.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
import helpers as H  # noqa: E402
# The navigation contract's own measuring stick, borrowed rather than
# re-implemented: if the contract changes, these screens are held to the new
# shape automatically.
from test_no_dead_ends import assert_chip  # noqa: E402

N = H.latest_edition()
DATE = H.edition_date(N)

SCREEN = "#install-screen:not([hidden])"
STRIP = "#install-tip:not([hidden])"

# Chrome on iPhone and a desktop browser, as their UA strings really read.
UA_CRIOS = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/137.0.7151.107 "
            "Mobile/15E148 Safari/604.1")
UA_INSTAGRAM = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/22F76 "
                "Instagram 390.0.0.28.77 (iPhone14,5; iOS 18_5; en_GB)")
UA_TIKTOK = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
             "musical_ly_2023 BytedanceWebview/d8a21c")
UA_DESKTOP = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36")

# A clipboard that records instead of writing, so the fallback button can be
# asserted without granting a real permission.
CLIP_STUB = """
Object.defineProperty(navigator, 'clipboard', {
  configurable: true,
  value: { writeText: (t) => { window.__clip = t; return Promise.resolve(); } },
});"""
CLIP_REFUSES = """
Object.defineProperty(navigator, 'clipboard', {
  configurable: true,
  value: { writeText: () => Promise.reject(new Error('denied')) },
});"""
STANDALONE = "Object.defineProperty(navigator, 'standalone', {value: true});"

# The event the three game engines dispatch when a daily ends.
FINISH = ("(g) => document.dispatchEvent(new CustomEvent('gamefinished',"
          " {detail: {game: g, daily: true}}))")


def finish_game(page, game="who"):
    page.evaluate(FINISH, game)


def misc(page):
    return page.evaluate("() => __CHRONICLE_TEST__.store.getMisc()")


def set_misc(page, patch):
    page.evaluate("p => __CHRONICLE_TEST__.store.setMisc(p)", patch)


def screen_text(page):
    return page.inner_text("#install-screen").lower()


def force(page, action):
    page.evaluate("a => __CHRONICLE_TEST__.install.force[a]()", action)


def no_screen(page, label, ms=1400):
    """Nothing may appear — including after the offer's own delay."""
    page.wait_for_timeout(ms)
    assert page.locator("#install-screen").is_hidden(), (
        "%s: the install screen appeared when it should not have" % label)


# ---------------------------------------------------------------------------
# 1. detection
# ---------------------------------------------------------------------------
def detection(p, base):
    """The right branch for the browser in hand. Standalone wins over
    everything: an installed app must never be pitched an install."""
    cases = [
        (None, (), "safari", "an iPhone with no other browser token"),
        ({"user_agent": UA_CRIOS}, (), "chrome-ios", "Chrome on iPhone"),
        ({"user_agent": UA_INSTAGRAM}, (), "webview", "Instagram's browser"),
        ({"user_agent": UA_TIKTOK}, (), "webview", "TikTok's browser"),
        ({"user_agent": UA_DESKTOP}, (), "generic", "a desktop browser"),
        (None, (STANDALONE,), "installed", "the installed app"),
    ]
    for ctx_args, scripts, want, label in cases:
        with H.app(p, context_args=ctx_args, init_scripts=scripts) as (page, errors, _c):
            H.boot(page, base, DATE)
            got = page.evaluate("() => __CHRONICLE_TEST__.install.branch()")
            assert got == want, "%s should be %r, detected %r" % (label, want, got)
            H.fail_on_errors(errors, "detection:%s" % want)

    # Android's native dialog: the branch exists only once the browser has
    # actually offered it (beforeinstallprompt), never on hope.
    with H.app(p, context_args={"user_agent": UA_DESKTOP}) as (page, errors, _c):
        H.boot(page, base, DATE)
        assert page.evaluate("() => __CHRONICLE_TEST__.install.branch()") == "generic"
        page.evaluate("""() => {
          const e = new Event('beforeinstallprompt');
          e.prompt = () => { window.__prompted = true; return Promise.resolve(); };
          e.userChoice = Promise.resolve({outcome: 'accepted'});
          window.dispatchEvent(e);
        }""")
        assert page.evaluate("() => __CHRONICLE_TEST__.install.branch()") == "native", (
            "a captured beforeinstallprompt should switch on the native branch")
        H.fail_on_errors(errors, "detection:native")


# ---------------------------------------------------------------------------
# 2. every screen: content + the navigation contract
# ---------------------------------------------------------------------------
# action -> (a phrase that must be on the screen, ...)
SCREENS = [
    ("installSafari", ["save yesternerd as an app on your home screen",
                       "tap share", "add to home screen", "view more",
                       "i’ve saved it", "maybe later"]),
    ("installChromeIOS", ["tap share", "top right, next to the address bar",
                          "not the", "at the bottom", "add to home screen"]),
    ("installNative", ["save it now", "will ask you to confirm", "maybe later"]),
    ("installGeneric", ["menu", "install app", "add to home screen"]),
    ("webviewInstagram", ["instagram can’t keep apps",
                          "open in external browser", "top right",
                          "copy the link", "then paste it in safari or chrome"]),
    ("webviewGeneric", ["this in-app browser can’t keep apps",
                        "open in browser", "copy the link"]),
]


def screens_render(p, base):
    """Every branch, forced: the words that were signed off are on the screen,
    the replica glyphs are drawn, and the ‹ chip is where the contract says."""
    with H.app(p) as (page, errors, _c):
        H.boot(page, base, DATE)
        for action, phrases in SCREENS:
            force(page, action)
            page.wait_for_selector(SCREEN)
            text = screen_text(page)
            for phrase in phrases:
                assert phrase in text, "%s: %r missing from the screen" % (action, phrase)
            # The navigation contract, measured exactly as CI measures it.
            assert_chip(page, "#install-back", action)
            # Daniel's ruling: the drawn replica is bigger than the words
            # around it (body copy is 15px). The native screen is the one that
            # teaches nothing — it has a button, not a lesson, so it has no
            # replicas to measure.
            glyphs = page.evaluate(
                "() => Array.from(document.querySelectorAll('#install-screen .install-glyph'))"
                ".map(g => g.getBoundingClientRect().height)")
            if action == "installNative":
                assert not glyphs, "the native screen should teach nothing"
            else:
                assert glyphs, "%s: no replica glyph drawn" % action
                assert min(glyphs) >= 38, (
                    "%s: a replica is only %.0fpx tall — the ruling is that the "
                    "button outsizes the words" % (action, min(glyphs)))
            page.click("#install-back")
            page.wait_for_selector("#install-screen", state="hidden")
            assert page.locator("#view-home").is_visible(), (
                "%s: the way back should leave you on the surface underneath" % action)
        H.fail_on_errors(errors, "screens_render")


def qa_panel_summons_every_branch(p, base):
    """Daniel's own phone QA depends on the ?qa=1 panel, so the buttons are
    tested through the panel too, exactly as he taps them."""
    labels = ["Save it · iOS Safari", "Save it · Chrome iPhone",
              "Save it · Android button", "Save it · other browser",
              "Escape · Instagram", "Escape · other app"]
    with H.app(p) as (page, errors, _c):
        H.boot(page, base, DATE, extra="&qa=1")
        page.wait_for_selector("#qa-panel")
        for label in labels:
            page.click("#qa-panel .qa-btn:has-text('%s')" % label)
            page.wait_for_selector(SCREEN)
            page.click("#install-back")
            page.wait_for_selector("#install-screen", state="hidden")
        # A forced preview is a preview: it must not spend the real ask or
        # count itself into the funnel.
        m = misc(page)
        assert not m.get("installAsked"), "QA forcing spent the player's real ask"
        assert not m.get("installEscapes"), "QA forcing counted an escape page"
        assert not [e for e in H.gc_events(page) if "install-shown" in e
                    or "webview-shown" in e], "QA forcing sent analytics"
        page.click("#qa-panel .qa-btn:has-text('Install pitch')")
        page.wait_for_selector(STRIP)
        # The webview banner too: forced in the named variant, silently.
        page.click("#qa-panel .qa-btn:has-text('Webview banner')")
        page.wait_for_selector("#webview-note:not([hidden])")
        assert "instagram" in page.inner_text("#webview-note").lower()
        assert not [e for e in H.gc_events(page) if "webview-banner" in e], (
            "QA forcing sent banner analytics")
        assert not misc(page).get("webviewNoteSnoozedAt"), (
            "QA forcing touched the banner's snooze state")
        H.fail_on_errors(errors, "qa_panel_summons_every_branch")


# ---------------------------------------------------------------------------
# 3. timing
# ---------------------------------------------------------------------------
def two_games_then_the_ask(p, base):
    """One finished game is not a habit worth protecting; two is. The ask
    arrives at the end of game 2 and names its branch to the dashboard."""
    with H.app(p) as (page, errors, _c):
        H.boot(page, base, DATE)
        finish_game(page, "who")
        no_screen(page, "after one game")
        assert misc(page).get("installGames") == 1
        finish_game(page, "map")
        page.wait_for_selector(SCREEN)
        assert "7-install-shown-ios-safari" in H.gc_events(page), (
            "the shown event should name the branch: %r" % H.gc_events(page))
        assert misc(page).get("installAsked") is True
        H.fail_on_errors(errors, "two_games_then_the_ask")


def real_games_count(p, base):
    """The end-to-end wiring: two dailies played for real (not a synthesised
    event) bring the screen up over the second summary. This is the scenario
    that would catch a game engine forgetting to announce its own ending."""
    with H.app(p) as (page, errors, _c):
        H.boot(page, base, DATE)
        H.open_daily(page, "who")
        H.dismiss_intro(page, timeout=2500)
        H.play_reveal_daily(page)
        no_screen(page, "after one real daily")

        page.click("#rv-sum-back")
        H.open_daily(page, "map")
        H.dismiss_intro(page, timeout=2500)
        H.play_map_daily(page)
        page.wait_for_selector(SCREEN)
        assert "save yesternerd as an app" in screen_text(page)
        H.fail_on_errors(errors, "real_games_count")


def a_past_day_counts_as_a_game(p, base):
    """Encore went on 9 Aug 2026, but the ruling it tested stands: today's Face
    Value and an Archive day of the SAME game are two games as far as the ask
    is concerned. Played for real, because "does a past day announce itself?"
    is exactly the kind of wiring that rots quietly."""
    with H.app(p) as (page, errors, _c):
        H.boot(page, base, DATE)
        H.open_daily(page, "who")
        H.dismiss_intro(page, timeout=2500)
        H.play_reveal_daily(page)
        assert misc(page).get("installGames") == 1
        page.click("#rv-sum-back")
        page.wait_for_selector("#view-home:not([hidden])")
        card = page.locator('[data-row="who"] [data-days] [data-edition-index]').first
        assert card.is_visible(), (
            "no past-day card to play — this scenario cannot run")
        card.click()
        H.play_reveal_daily(page)
        page.wait_for_selector(SCREEN)
        assert misc(page).get("installGames") == 2, (
            "a past day should count as a game: %r" % misc(page))
        H.fail_on_errors(errors, "a_past_day_counts_as_a_game")


def decline_leaves_the_strip(p, base):
    """"Maybe later" is not a no: it leaves one quiet line at the top of Home,
    and that line reopens the same screen."""
    with H.app(p) as (page, errors, _c):
        H.boot(page, base, DATE)
        finish_game(page, "who")
        finish_game(page, "map")
        page.wait_for_selector(SCREEN)
        page.click("#install-later")
        page.wait_for_selector("#install-screen", state="hidden")
        assert "7-install-later" in H.gc_events(page)
        page.wait_for_selector(STRIP)
        assert "show me how" in page.inner_text("#install-tip").lower()

        page.click("#install-tip-btn")
        page.wait_for_selector(SCREEN)
        assert "7-install-strip-tapped" in H.gc_events(page)
        # The ‹ chip is the same "not now" as the link under the button.
        page.click("#install-back")
        page.wait_for_selector("#install-screen", state="hidden")
        assert page.locator("#install-tip").is_visible(), (
            "backing out of the reopened screen should leave the strip in place")
        H.fail_on_errors(errors, "decline_leaves_the_strip")


def strip_x_then_one_last_offer(p, base):
    """The × ends the strip for good — but a 7-day streak buys one final ask,
    once, ever. (The streak cache is written directly: the real path stamps
    completions with today's edition, so a week of history cannot be
    back-dated through it.)"""
    with H.app(p) as (page, errors, _c):
        H.boot(page, base, DATE)
        finish_game(page, "who")
        finish_game(page, "map")
        page.wait_for_selector(SCREEN)
        page.click("#install-later")
        page.wait_for_selector(STRIP)
        page.click("#install-tip-close")
        page.wait_for_selector("#install-tip", state="hidden")
        assert misc(page).get("installStripGone") is True

        # A short streak buys nothing.
        page.evaluate("""() => {
          const l = __CHRONICLE_TEST__.store.getDailyLedger();
          l.streaks.who = {streak: 4, lastEdition: 0};
          __CHRONICLE_TEST__.store.setDailyLedger(l);
        }""")
        finish_game(page, "who")
        no_screen(page, "a 4-day streak after the strip was killed")

        page.evaluate("""() => {
          const l = __CHRONICLE_TEST__.store.getDailyLedger();
          l.streaks.who = {streak: 7, lastEdition: 0};
          __CHRONICLE_TEST__.store.setDailyLedger(l);
        }""")
        finish_game(page, "who")
        page.wait_for_selector(SCREEN)
        page.click("#install-later")
        page.wait_for_selector("#install-screen", state="hidden")
        assert page.locator("#install-tip").is_hidden(), (
            "a killed strip must never come back")

        finish_game(page, "who")
        no_screen(page, "after the final offer was spent")
        H.fail_on_errors(errors, "strip_x_then_one_last_offer")


def saved_it_ends_the_asking(p, base):
    """"I've saved it" is taken at face value: no strip, no further asks."""
    with H.app(p) as (page, errors, _c):
        H.boot(page, base, DATE)
        finish_game(page, "who")
        finish_game(page, "map")
        page.wait_for_selector(SCREEN)
        page.click("#install-saved")
        page.wait_for_selector("#install-screen", state="hidden")
        assert "7-install-saved-claim" in H.gc_events(page)
        assert page.locator("#install-tip").is_hidden()
        finish_game(page, "what")
        no_screen(page, "after the player said they had saved it")
        H.fail_on_errors(errors, "saved_it_ends_the_asking")


def android_one_tap(p, base):
    """The native branch: no lesson, one button, and the OS dialog's own
    answer is what gets recorded."""
    with H.app(p, context_args={"user_agent": UA_DESKTOP}) as (page, errors, _c):
        H.boot(page, base, DATE)
        page.evaluate("""() => {
          const e = new Event('beforeinstallprompt');
          e.prompt = () => { window.__prompted = true; return Promise.resolve(); };
          e.userChoice = Promise.resolve({outcome: 'accepted'});
          window.dispatchEvent(e);
        }""")
        finish_game(page, "who")
        finish_game(page, "map")
        page.wait_for_selector(SCREEN)
        assert "7-install-shown-android-native" in H.gc_events(page)
        assert page.locator("#install-saved").count() == 0, (
            "the native screen teaches nothing and claims nothing")
        page.click("#install-now")
        page.wait_for_selector("#install-screen", state="hidden")
        assert page.evaluate("() => window.__prompted") is True, (
            "the button must open the browser's real install dialog")
        assert "7-install-android-accepted" in H.gc_events(page)
        H.fail_on_errors(errors, "android_one_tap")


# ---------------------------------------------------------------------------
# 4. the escape page
# ---------------------------------------------------------------------------
def webview_after_one_game_twice(p, base):
    """In-app browsers cannot install anything and lose the record when they
    close, so the escape page comes after ONE game — and, because it is an
    interruption, at most twice."""
    with H.app(p, context_args={"user_agent": UA_INSTAGRAM},
               init_scripts=(CLIP_STUB,)) as (page, errors, _c):
        H.boot(page, base, DATE)
        finish_game(page, "who")
        page.wait_for_selector(SCREEN)
        assert "instagram can’t keep apps" in screen_text(page)
        assert "7-webview-shown-instagram" in H.gc_events(page)
        page.click("#install-back")
        page.wait_for_selector("#install-screen", state="hidden")
        # The strip is an install offer; there is nothing to install in here.
        assert page.locator("#install-tip").is_hidden(), (
            "the install strip must never show inside an in-app browser")

        finish_game(page, "map")
        page.wait_for_selector(SCREEN)
        page.click("#install-back")
        page.wait_for_selector("#install-screen", state="hidden")

        finish_game(page, "what")
        no_screen(page, "a third game in a webview")
        assert misc(page).get("installEscapes") == 2
        H.fail_on_errors(errors, "webview_after_one_game_twice")


def copy_the_link(p, base):
    """The guaranteed fallback. Escaping an in-app browser cannot be scripted
    in 2026, so the link in the clipboard is the one thing that always works."""
    with H.app(p, context_args={"user_agent": UA_INSTAGRAM},
               init_scripts=(CLIP_STUB,)) as (page, errors, _c):
        H.boot(page, base, DATE)
        force(page, "webviewInstagram")
        page.wait_for_selector(SCREEN)
        page.click("#install-copy")
        page.wait_for_function("() => window.__clip")
        assert page.evaluate("() => window.__clip") == "https://yesternerd.app/", (
            "the copied link must be the app's own address, absolute")
        assert "7-webview-link-copied" in H.gc_events(page)
        assert "copied" in page.inner_text("#install-copy").lower()
        H.fail_on_errors(errors, "copy_the_link")

    # A webview that withholds the clipboard still has to leave a way out:
    # the address, selected, ready for a long-press → Copy.
    with H.app(p, context_args={"user_agent": UA_INSTAGRAM},
               init_scripts=(CLIP_REFUSES,)) as (page, errors, _c):
        H.boot(page, base, DATE)
        force(page, "webviewInstagram")
        page.wait_for_selector(SCREEN)
        page.click("#install-copy")
        page.wait_for_selector("#install-url:not([hidden])")
        assert page.input_value("#install-url") == "https://yesternerd.app/"
        assert "select it" in page.inner_text("#install-copy").lower()
        H.fail_on_errors(errors, "copy_the_link_refused")


# ---------------------------------------------------------------------------
# 5. the webview warning banner on Home (11 Aug 2026)
# ---------------------------------------------------------------------------
NOTE = "#webview-note:not([hidden])"
DAY_MS = 24 * 60 * 60 * 1000


def webview_banner_warns_and_routes(p, base):
    """Inside Instagram's browser the banner is up from the first paint: it
    names the app in hand, fires its shown beacon once per session, lives on
    Home and nowhere else, and its button opens the SAME escape screen the
    end-of-game offer uses — without spending that offer's twice-per-device
    cap or counting as an install 'maybe later'."""
    with H.app(p, context_args={"user_agent": UA_INSTAGRAM}) as (page, errors, _c):
        H.boot(page, base, DATE)
        page.wait_for_selector(NOTE)
        text = page.inner_text("#webview-note").lower()
        assert "instagram" in text, "the banner should name the app in hand"
        assert "streaks can die in here" in text
        assert "show me out" in text
        assert H.gc_events(page).count("7-webview-banner-shown") == 1

        # A strip, not a screen: it lives inside Home and leaves with it.
        page.evaluate("() => __CHRONICLE_TEST__.nav.show('view-ledger')")
        assert page.locator("#webview-note").is_hidden(), (
            "the banner belongs to Home, not to other views")
        page.evaluate("() => __CHRONICLE_TEST__.nav.goHome()")
        page.wait_for_selector(NOTE)
        assert H.gc_events(page).count("7-webview-banner-shown") == 1, (
            "shown is once per SESSION, not once per Home repaint")

        # The door: the existing escape surface, nothing duplicated.
        page.click("#webview-note-btn")
        page.wait_for_selector(SCREEN)
        assert "instagram can’t keep apps" in screen_text(page)
        assert "open in external browser" in screen_text(page)
        assert "copy the link" in screen_text(page)
        assert "7-webview-banner-tapped" in H.gc_events(page)
        assert not misc(page).get("installEscapes"), (
            "a player-opened escape must not spend the auto-offer's cap")
        assert "7-webview-shown-instagram" not in H.gc_events(page), (
            "webview-shown is the auto-offer's own funnel, not the banner's")

        # Backing out lands on Home with the banner still up — and closing a
        # door you opened yourself is not an install "maybe later".
        page.click("#install-back")
        page.wait_for_selector("#install-screen", state="hidden")
        page.wait_for_selector(NOTE)
        assert "7-install-later" not in H.gc_events(page)
        assert not misc(page).get("installLater")

        # The auto-offer is untouched by any of this: one finished game still
        # brings the escape page, counted as ever.
        finish_game(page, "who")
        page.wait_for_selector(SCREEN)
        assert "7-webview-shown-instagram" in H.gc_events(page)
        assert misc(page).get("installEscapes") == 1
        H.fail_on_errors(errors, "webview_banner_warns_and_routes")


def webview_banner_snooze_seven_days(p, base):
    """The × is a snooze, not an execution: gone for a week, remembered
    across launches, back on day eight — the app can't be installed in there,
    so the warning has to be allowed to return."""
    with H.app(p, context_args={"user_agent": UA_INSTAGRAM}) as (page, errors, _c):
        H.boot(page, base, DATE)
        page.wait_for_selector(NOTE)
        page.click("#webview-note-close")
        page.wait_for_selector("#webview-note", state="hidden")
        assert "7-webview-banner-dismissed" in H.gc_events(page)
        assert misc(page).get("webviewNoteSnoozedAt"), (
            "the snooze must persist in the misc blob")

        H.boot(page, base, DATE)          # relaunch, same device: still quiet
        page.wait_for_timeout(600)
        assert page.locator("#webview-note").is_hidden()
        assert "7-webview-banner-shown" not in H.gc_events(page)

        # Day six: still snoozed.
        set_misc(page, {"webviewNoteSnoozedAt":
                        page.evaluate("() => Date.now() - 6 * %d" % DAY_MS)})
        H.boot(page, base, DATE)
        page.wait_for_timeout(600)
        assert page.locator("#webview-note").is_hidden(), (
            "six days is inside the week")

        # Day eight: a warning again.
        set_misc(page, {"webviewNoteSnoozedAt":
                        page.evaluate("() => Date.now() - 8 * %d" % DAY_MS)})
        H.boot(page, base, DATE)
        page.wait_for_selector(NOTE)
        H.fail_on_errors(errors, "webview_banner_snooze_seven_days")


def webview_banner_nowhere_else(p, base):
    """Real browsers never see it, and neither does the installed app — even
    one whose UA still carries a webview token (standalone wins, as it does
    for every other branch)."""
    cases = [
        (None, (), "iOS Safari"),
        ({"user_agent": UA_DESKTOP}, (), "a desktop browser"),
        ({"user_agent": UA_INSTAGRAM}, (STANDALONE,), "standalone beats webview"),
    ]
    for ctx_args, scripts, label in cases:
        with H.app(p, context_args=ctx_args, init_scripts=scripts) as (page, errors, _c):
            H.boot(page, base, DATE)
            page.wait_for_timeout(400)
            assert page.locator("#webview-note").is_hidden(), (
                "%s: the banner showed outside an in-app browser" % label)
            assert "7-webview-banner-shown" not in H.gc_events(page), label
            H.fail_on_errors(errors, "webview_banner_nowhere_else:%s" % label)


# ---------------------------------------------------------------------------
# 6. the installed app
# ---------------------------------------------------------------------------
def never_in_the_installed_app(p, base):
    """Nothing at all, ever — and the one honest success beacon, fired once."""
    with H.app(p, init_scripts=(STANDALONE,)) as (page, errors, ctx):
        H.boot(page, base, DATE)
        assert "7-installed" in H.gc_events(page), (
            "the first standalone launch should report the install")
        finish_game(page, "who")
        finish_game(page, "map")
        no_screen(page, "the installed app")
        assert page.locator("#install-tip").is_hidden()
        set_misc(page, {"installLater": True})   # even with a strip owed
        H.boot(page, base, DATE)                 # a second launch, same device
        assert page.locator("#install-tip").is_hidden(), (
            "the installed app must never show the strip either")
        assert "7-installed" not in H.gc_events(page), (
            "install-confirmed is a one-shot per device, not per launch: %r"
            % H.gc_events(page))
        H.fail_on_errors(errors, "never_in_the_installed_app")


TESTS = [detection, screens_render, qa_panel_summons_every_branch,
         two_games_then_the_ask, real_games_count, a_past_day_counts_as_a_game,
         decline_leaves_the_strip, strip_x_then_one_last_offer,
         saved_it_ends_the_asking, android_one_tap,
         webview_after_one_game_twice, copy_the_link,
         webview_banner_warns_and_routes, webview_banner_snooze_seven_days,
         webview_banner_nowhere_else,
         never_in_the_installed_app]


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
