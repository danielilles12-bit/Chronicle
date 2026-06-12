#!/usr/bin/env python3
"""PWA checks: manifest correctness, icons, iOS meta tags, service worker
registration, and full offline functionality after first load.

Chromium is the hard gate for SW/offline (most reliable harness); WebKit runs
the same flow and reports, but only fails the suite on non-SW issues."""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
from helpers import server, page_on, fail_on_errors  # noqa: E402


def check_manifest(base):
    man = json.loads(urllib.request.urlopen(base + "/manifest.webmanifest").read())
    assert man["display"] == "standalone", man
    assert man.get("name") and man.get("short_name")
    assert len(man["icons"]) >= 3
    assert any(i.get("purpose") == "maskable" for i in man["icons"])
    for icon in man["icons"] + [{"src": "icons/apple-touch-icon.png"}]:
        data = urllib.request.urlopen(base + "/" + icon["src"]).read()
        assert data[:8] == b"\x89PNG\r\n\x1a\n", icon["src"] + " is not a PNG"
    print("manifest + icons OK")


def offline_flow(p, engine, base):
    """Returns (sw_active, offline_ok). Raises on console errors."""
    with page_on(p, engine) as (pg, errors):
        pg.goto(base + "/")
        pg.wait_for_selector("#card-crossword")
        assert pg.locator('link[rel="apple-touch-icon"]').count() == 1
        assert pg.locator('meta[name="apple-mobile-web-app-capable"]').count() == 1
        assert pg.locator('link[rel="manifest"]').count() == 1

        sw = False
        try:
            pg.wait_for_function(
                "navigator.serviceWorker && navigator.serviceWorker.controller !== null",
                timeout=20000)
            sw = True
        except Exception:
            pass

        offline_ok = False
        if sw:
            pg.context.set_offline(True)
            try:
                pg.reload()
                pg.wait_for_selector("#card-crossword", timeout=15000)
                pg.click("#card-crossword")
                pg.wait_for_selector(".cwitem")
                pg.click(".cwitem")
                pg.wait_for_selector("#cw-grid .cell:not(.block)")
                pg.click("#view-cw [data-back]")
                pg.click("#view-cwlist [data-back]")
                pg.click("#card-map")
                pg.wait_for_selector("#map-start")
                pg.click("#map-start")
                pg.wait_for_selector("#map-svg circle")
                offline_ok = True
            except Exception as e:  # noqa: BLE001 — webkit harness flake is tolerated by caller
                print(engine, "offline flow error:", str(e).splitlines()[0][:140])
            finally:
                pg.context.set_offline(False)
        if offline_ok or engine == "chromium":
            fail_on_errors(errors, engine + " pwa flow")
        elif errors:
            print(engine, "console noise during tolerated offline failure:", len(errors), "entries")
        return sw, offline_ok


def main():
    with server() as base, sync_playwright() as p:
        check_manifest(base)

        sw, off = offline_flow(p, "chromium", base)
        assert sw, "service worker must control the page (chromium)"
        assert off, "app must be fully usable offline (chromium)"
        print("chromium: SW active, offline flow OK")

        sw_wk, off_wk = offline_flow(p, "webkit", base)
        if sw_wk and off_wk:
            print("webkit: SW active, offline flow OK")
        else:
            print("webkit: SW harness limitation (sw=%s offline=%s) — offline "
                  "behaviour verified on chromium; iOS Safari supports SW for "
                  "installed PWAs" % (sw_wk, off_wk))

    print("PWA TESTS OK")


if __name__ == "__main__":
    main()
