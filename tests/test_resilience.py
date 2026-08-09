#!/usr/bin/env python3
"""Resilience suite (P4.1/P5.2): share clipboard fallback, share deep-link
landing, storage corruption + quota failure, a missing daily manifest,
offline play of the current issue, service-worker update bar.
"""
import functools
import http.server
import os
import re
import sys
import threading

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
import helpers as H  # noqa: E402

N = H.latest_edition()
DATE = H.edition_date(N)


# ---------- share_fallback ----------
def share_fallback(p, base):
    """No navigator.share (headless Chromium): the share button lands on the
    clipboard, reports 'copied', and the -copied analytics event fires."""
    with H.app(p) as (page, errors, ctx):
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=base)
        H.boot(page, base, DATE)
        assert page.evaluate("typeof navigator.share") == "undefined", (
            "this scenario expects no Web Share API")
        guesses = [["yellow"] * 4, ["green"] * 4, ["blue"] * 4, ["purple"] * 4]
        H.seed_completion(page, "thread", N, score=100,
                          detail={"solved": True, "perfect": True,
                                  "mistakes": 0, "guesses": guesses})
        H.open_daily(page, "thread")
        page.wait_for_selector("#view-connsum:not([hidden])")
        page.wait_for_selector("#conn-sum-share:not([hidden])")
        page.click("#conn-sum-share")
        page.wait_for_function(
            "document.querySelector('#conn-sum-share').textContent"
            ".indexOf('Copied') === 0")
        clip = page.evaluate("navigator.clipboard.readText()")
        assert ("THREAD %s" % H.edition_day_label(N)) in clip, \
            "clipboard text wrong: %r" % clip[:80]
        assert "?play=thread&ref=share" in clip, (
            "Thread's receipt should carry its own game deep link: %r" % clip)
        events = H.gc_events(page)
        assert "6-shared-thread-copied" in events, (
            "copied event missing from analytics: %r" % events)
        assert "6-shared-thread" not in events, (
            "a clipboard copy must not count as a full share")
        H.fail_on_errors(errors, "share_fallback")


# ---------- share_landing (P5.2) ----------
def share_landing(p, base):
    """A ?play=<game> deep link (Wordle convention): lands, routes into that
    game's TODAY daily regardless of any issue the sender's link carried, and
    scrubs the param. Events fire in order land -> start -> answer. An
    unrecognised game value is ignored — no route, no land event — rather
    than crashing or falling through to some default game.

    One browser, two sequential boots (same pattern as test_daily_flow's
    rollover) — each H.boot is a full page.goto/reload, which re-arms the
    GC_STUB init script for a clean window.__gc, so the two checks don't
    need separate browser launches."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE, extra="&play=nonsense")
        assert page.locator("#view-home").is_visible(), (
            "an invalid ?play= value should leave Home showing")
        assert "play=" not in page.evaluate("location.search"), (
            "an invalid ?play= value should still be scrubbed")
        assert not any(e.startswith("1-land-share-") for e in H.gc_events(page)), (
            "an invalid ?play= value must not count as a share landing")

        H.boot(page, base, DATE, extra="&play=thread")
        board = H.thread_board(page, N)
        H.dismiss_intro(page)
        page.wait_for_selector("#view-conn:not([hidden])")
        assert page.inner_text("#conn-puzzle-title").lower() == board["title"].lower(), (
            "share link should route to TODAY's Thread daily")
        assert "play=" not in page.evaluate("location.search"), (
            "share param not scrubbed from the URL")
        H.click_tiles(page, board["groups"][0]["items"])
        page.click("#conn-submit")
        events = H.gc_events(page)
        land = events.index("1-land-share-thread")
        start = events.index("3-start-from-share-thread")
        answer = events.index("3-answer-from-share-thread")
        assert land < start < answer, "share funnel events out of order: %r" % events
        H.fail_on_errors(errors, "share_landing")


# ---------- storage ----------
def storage_corrupt(p, base):
    """A corrupt main blob recovers from the backup copy and heals main."""
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, DATE)
        page.evaluate("__CHRONICLE_TEST__.store.setMisc({probe: 41})")
        good = page.evaluate("localStorage.getItem('chronicle.v1')")
        assert good and '"probe":41' in good
        page.evaluate(
            "g => { localStorage.setItem('chronicle.v1', '{corrupt![');"
            " localStorage.setItem('chronicle.v1.backup', g); }", good)
        H.boot(page, base, DATE)               # reload: loadAll must recover
        assert page.evaluate("__CHRONICLE_TEST__.store.getMisc().probe") == 41, (
            "state not recovered from backup")
        healed = page.evaluate("JSON.parse(localStorage.getItem('chronicle.v1'))")
        assert healed.get("misc", {}).get("probe") == 41, "main blob not healed"
        assert "9-save-recovered-from-backup" in H.gc_events(page)
        H.fail_on_errors(errors, "storage_corrupt")


QUOTA_STUB = """
(() => {
  const orig = Storage.prototype.setItem;
  Storage.prototype.setItem = function (k, v) {
    if (String(k).indexOf('chronicle.v1') === 0) {
      throw new DOMException('quota', 'QuotaExceededError');
    }
    return orig.apply(this, arguments);
  };
})();
"""


def storage_quota(p, base):
    """Failing writes surface the one-time 'not saving' toast."""
    with H.app(p, init_scripts=(QUOTA_STUB,)) as (page, errors, _ctx):
        H.boot(page, base, DATE)               # boot itself writes (seenBefore)
        page.wait_for_selector(".df-save-toast")
        assert page.locator('.df-save-toast[role="status"]').count() == 1
        assert "may not be saving" in page.inner_text(".df-save-toast").lower()
        assert "9-save-failing" in H.gc_events(page)
        page.click(".df-save-toast-close")
        page.wait_for_selector(".df-save-toast", state="detached")
        H.fail_on_errors(errors, "storage_quota")


# ---------- missing_manifest ----------
# Home paints from static markup + localStorage, so it is up long before the
# data files are; this is BOOTED minus the manifest, which is the one file
# this scenario never lets through.
POOLS_LOADED = ("window.__CHRONICLE_TEST__ && __CHRONICLE_TEST__.data"
                " && __CHRONICLE_TEST__.data.reveal"
                " && __CHRONICLE_TEST__.data.figures"
                " && __CHRONICLE_TEST__.data.connections")

# game key -> the view it opens, and how to read the round it is showing.
GAME_VIEWS = {
    "who": "#view-reveal",
    "map": "#view-map",
    "what": "#view-reveal",
    "thread": "#view-conn",
}

RETRY_SHOWN = (
    "g => { const el = document.querySelector("
    "'[data-hero=\"' + g + '\"] [data-status]');"
    " return !!el && (el.innerText || '').toLowerCase().indexOf('retry') !== -1; }")

# ...and the words have to be ON THE SCREEN, not just in the markup. Since
# 7 Aug 2026 a card's status line is hidden unless something switches it on
# (it stands in for the tagline instead of sitting in the bottom row), so the
# failure message is one class away from being written into an invisible
# element — exactly the bug this guards. Face Value is the one exemption: a
# newcomer's Home has no Face Value card at all, its door being the hero, so
# there is nowhere for its status to show.
RETRY_VISIBLE = (
    "g => { const row = document.querySelector('[data-row=\"' + g + '\"]');"
    " const el = document.querySelector('[data-hero=\"' + g + '\"] [data-status]');"
    " if (!row || row.offsetParent === null) return 'no-card';"
    " return (el && el.offsetParent !== null) ? 'visible' : 'hidden'; }")


def first_round_id(page, game):
    """The item the game is actually showing, however it names it."""
    if game == "thread":
        return page.inner_text("#conn-puzzle-title").strip().lower()
    hook = "mapRound" if game == "map" else "revealRound"
    return page.evaluate("h => __CHRONICLE_TEST__[h].id", hook)


def expected_first_id(page, game, n):
    if game == "thread":
        return H.thread_board(page, n)["title"].strip().lower()
    return page.evaluate("a => __CHRONICLE_TEST__.daily.getEdition(a.g, a.n)[0].id",
                         {"g": game, "n": n})


def missing_manifest(p, base):
    """data/editions.json is the only record of what an edition contains. If it
    will not download, no game may invent one: the card reports the failure and
    stays shut (it used to fall back to date arithmetic and hand out a
    different, unapproved issue). The same tap must then work once the file is
    back — the failed download is not cached as a verdict."""
    blocked = {"editions": True}

    def route(r):
        host = r.request.url.split("/")[2].split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            r.abort()                                  # hermetic, as everywhere
        elif blocked["editions"] and "/data/editions.json" in r.request.url:
            r.abort()
        else:
            r.continue_()

    # Own the routing table outright: one handler, so there is no question of
    # which of two matching handlers Playwright consults first.
    with H.app(p, block_external=False) as (page, errors, ctx):
        ctx.route("**/*", route)
        page.goto(H.app_url(base, DATE))
        page.wait_for_function(POOLS_LOADED)
        assert page.evaluate("__CHRONICLE_TEST__.data.editions") is None, (
            "this scenario is meaningless if the manifest got through")

        for game in GAME_VIEWS:
            H.open_daily(page, game)
            page.wait_for_function(RETRY_SHOWN, arg=game, timeout=15000)
            assert page.evaluate(RETRY_VISIBLE, game) in ("visible", "no-card"), (
                "%s wrote 'tap to retry' into a status line nobody can see"
                % game)
            assert page.locator("#view-home").is_visible(), (
                "%s left Home while its schedule was unreachable" % game)
            assert page.locator(GAME_VIEWS[game]).is_hidden(), (
                "%s opened a playable round with no manifest to say what "
                "belongs in it" % game)
            assert page.locator("#intro-card").is_hidden(), (
                "%s got as far as its intro card" % game)

        # Both alarms: the file failed, and an edition that should have been
        # manifest-served wasn't. The second is the one that used to mean
        # "arithmetic served a substitute" and now means "nothing was served".
        page.wait_for_function(
            "() => { const e = window.__gc || [];"
            " return e.indexOf('9-data-editions-failed') !== -1"
            " && e.indexOf('9-manifest-missing') !== -1; }", timeout=15000)

        # The file comes back. The very same tap has to work — loadFile drops
        # a failed download so the next gate refetches rather than remembering.
        blocked["editions"] = False
        # state="attached": this profile has finished nothing, so it is still
        # a stranger, and a stranger's Face Value row is hidden behind the
        # hero (its CTA is that game's door — see helpers.open_daily).
        page.wait_for_selector('[data-hero="who"]', state="attached")
        for game in GAME_VIEWS:
            H.open_daily(page, game)
            H.dismiss_intro(page)
            page.wait_for_selector("%s:not([hidden])" % GAME_VIEWS[game])
            if game != "thread":
                page.wait_for_function(
                    "h => __CHRONICLE_TEST__[h] !== undefined",
                    arg="mapRound" if game == "map" else "revealRound")
            assert first_round_id(page, game) == expected_first_id(page, game, N), (
                "%s did not open the issue the manifest names" % game)
            page.evaluate("__CHRONICLE_TEST__.nav.goHome()")
            page.wait_for_selector("#view-home:not([hidden])")

        # The blocked download is the whole point here and the browser logs it
        # as a failed resource; every OTHER console error still counts.
        H.fail_on_errors([e for e in errors if "data/editions.json" not in e],
                         "missing_manifest")


# ---------- offline_current_issue ----------
def offline_current_issue(p, base):
    """After one online load, today's dailies play fully offline (Chromium;
    WebKit stays best-effort as before)."""
    with H.app(p) as (page, errors, ctx):
        H.boot(page, base, DATE)
        page.wait_for_function(
            "navigator.serviceWorker && navigator.serviceWorker.controller !== null",
            timeout=30000)
        # Warm today's images through the (now controlling) service worker —
        # deterministic version of the app's own idle prefetch.
        expected = page.evaluate(
            """async (n) => {
                 const urls = new Set();
                 for (const g of ['who', 'what'])
                   for (const it of __CHRONICLE_TEST__.daily.getEdition(g, n))
                     if (it.img) urls.add(it.img);
                 for (const u of urls) { try { await fetch(u); } catch (e) {} }
                 return urls.size;
               }""", N)
        assert expected > 0
        page.wait_for_function(
            "exp => caches.open('df-img').then(c => c.keys())"
            ".then(k => k.length >= exp)", arg=expected, timeout=60000)

        ctx.set_offline(True)
        try:
            page.reload()
            page.wait_for_function(H.BOOTED)
            assert page.inner_text("#dateline").strip(), "home did not paint offline"
            H.open_daily(page, "who")
            H.dismiss_intro(page, timeout=1200)
            page.wait_for_selector("#view-reveal:not([hidden])")
            page.wait_for_function("__CHRONICLE_TEST__.revealDebug !== undefined")
            page.wait_for_timeout(800)         # let ensureDims settle
            assert page.locator("#rv-offline").is_hidden(), (
                "round claims its image is missing while it was prefetched")
            page.locator("#rv-scraps .df-scrap.tearable").first.click()
            assert H.reveal_worth(page) == 90, "offline round not playable"
        finally:
            ctx.set_offline(False)
        H.fail_on_errors(errors, "offline_current_issue")


# ---------- sw_update ----------
class BumpHandler(http.server.SimpleHTTPRequestHandler):
    """Serves the repo; when .bump is set, sw.js goes out with a rewritten
    VERSION — the byte-change that triggers the update flow."""
    bump = False

    def do_GET(self):
        if self.path.split("?")[0].endswith("/sw.js"):
            with open(os.path.join(H.ROOT, "sw.js"), "rb") as f:
                data = f.read()
            if type(self).bump:
                # Prefix-agnostic so a rebrand can't silently disable this test:
                # whatever the cache name is, append a marker to change the bytes.
                data, n = re.subn(rb"(const VERSION = '[^']*)'",
                                  rb"\1-test'", data, count=1)
                assert n == 1, "sw.js VERSION line not found — update this rewrite"
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()

    def log_message(self, *args):
        pass


def sw_update(p, base_unused):
    """A VERSION bump reaches a running page as the NEW EDITION bar."""
    port = H.PORT + 7
    handler = functools.partial(BumpHandler, directory=H.ROOT)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % port
    BumpHandler.bump = False
    try:
        with H.app(p) as (page, errors, _ctx):
            H.boot(page, base, DATE)
            page.wait_for_function(
                "navigator.serviceWorker && navigator.serviceWorker.controller !== null",
                timeout=30000)
            # Second load: registration now sees a controller, so the
            # controllerchange -> NEW EDITION wiring is armed (first-ever
            # visits are already newest by definition).
            page.reload()
            page.wait_for_function(H.BOOTED)
            BumpHandler.bump = True
            page.evaluate(
                "navigator.serviceWorker.getRegistration().then(r => r.update())")
            page.wait_for_selector("#new-edition", timeout=30000)
            assert "new version ready" in page.inner_text("#new-edition").lower()
            H.fail_on_errors(errors, "sw_update")
    finally:
        srv.shutdown()


TESTS = [share_fallback, share_landing, storage_corrupt, storage_quota,
         missing_manifest, offline_current_issue, sw_update]


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
