#!/usr/bin/env python3
"""Quick smoke test: boot the app on an iPhone-sized WebKit, click through the
main screens, fail on any console/page error, drop screenshots in /tmp."""
import os
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PORT = 8123


def wait_for_server(port, tries=40):
    for _ in range(tries):
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/index.html" % port, timeout=1)
            return True
        except Exception:
            time.sleep(0.25)
    return False


def main():
    srv = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--directory", ROOT],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    errors = []
    try:
        assert wait_for_server(PORT), "server did not start"
        with sync_playwright() as p:
            iphone = p.devices["iPhone 13"]
            b = p.webkit.launch()
            ctx = b.new_context(**iphone)
            pg = ctx.new_page()
            pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errors.append(str(e)))

            pg.goto("http://127.0.0.1:%d/" % PORT)
            pg.wait_for_selector("#card-crossword")
            pg.screenshot(path="/tmp/smoke-home.png")

            pg.click("#card-crossword")
            pg.wait_for_selector(".cwitem")
            pg.screenshot(path="/tmp/smoke-cwlist.png")

            pg.click(".cwitem")
            pg.wait_for_selector("#cw-grid .cell:not(.block)")
            pg.click(".kb-key")          # press Q
            pg.screenshot(path="/tmp/smoke-cwplay.png")

            pg.click("#view-cw [data-back]")
            pg.click("#view-cwlist [data-back]")
            pg.click("#card-map")
            pg.wait_for_selector("#map-start")
            pg.screenshot(path="/tmp/smoke-mapstart.png")

            pg.click("#map-start")
            pg.wait_for_selector("#map-svg circle")
            pg.wait_for_timeout(1100)    # let the zoom animation settle
            pg.fill("#map-input", "test guess")
            pg.click("#map-guess-btn")
            pg.wait_for_timeout(400)
            pg.screenshot(path="/tmp/smoke-mapround.png")

            hook = pg.evaluate("window.__CHRONICLE_TEST__ && window.__CHRONICLE_TEST__.mapRound")
            assert hook and hook.get("name"), "test hook missing"
            pg.fill("#map-input", hook["name"])
            pg.click("#map-guess-btn")
            pg.wait_for_selector("#map-feedback.good")
            pg.screenshot(path="/tmp/smoke-mapcorrect.png")

            b.close()
    finally:
        srv.terminate()

    if errors:
        print("CONSOLE ERRORS:")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    print("SMOKE OK — no console errors")


if __name__ == "__main__":
    main()
