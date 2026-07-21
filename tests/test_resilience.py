#!/usr/bin/env python3
"""Resilience suite (P4.1): share clipboard fallback, storage corruption +
quota failure, offline play of the current issue, service-worker update bar.
"""
import functools
import http.server
import os
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
        assert ("THREAD №%d" % N) in clip, "clipboard text wrong: %r" % clip[:80]
        events = H.gc_events(page)
        assert "6-shared-thread-copied" in events, (
            "copied event missing from analytics: %r" % events)
        assert "6-shared-thread" not in events, (
            "a clipboard copy must not count as a full share")
        H.fail_on_errors(errors, "share_fallback")


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
                data = data.replace(b"const VERSION = 'deadfamous-",
                                    b"const VERSION = 'deadfamous-test-", 1)
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


TESTS = [share_fallback, storage_corrupt, storage_quota,
         offline_current_issue, sw_update]


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
