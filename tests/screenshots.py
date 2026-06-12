#!/usr/bin/env python3
"""Capture every screen of the app into /screenshots (iPhone 13 WebKit,
plus one desktop shot)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
from helpers import ROOT, server, page_on, fail_on_errors  # noqa: E402

OUT = os.path.join(ROOT, "screenshots")


def shot(pg, name):
    pg.screenshot(path=os.path.join(OUT, name + ".png"))
    print("shot:", name)


def cw_state(pg):
    return pg.evaluate("window.__CHRONICLE_TEST__.cw")


def solve(pg):
    for _ in range(1200):
        st = cw_state(pg)
        if st["completed"]:
            return
        pg.keyboard.press(st["sol"][st["sel"]])


def main():
    os.makedirs(OUT, exist_ok=True)
    puzzles = json.load(open(os.path.join(ROOT, "data", "puzzles.json")))
    by_fmt = {f: next((z for z in puzzles if z["format"] == f), None)
              for f in ("mini", "midi", "full")}

    with server() as base, sync_playwright() as p:
        with page_on(p, "webkit") as (pg, errors):
            pg.goto(base + "/?mapseed=7")
            pg.wait_for_selector("#card-crossword")
            shot(pg, "01-home")

            pg.click("#card-crossword")
            pg.wait_for_selector(".cwitem")
            shot(pg, "02-crossword-list")

            mini = by_fmt["mini"]
            pg.click('.cwitem[data-pid="%s"]' % mini["id"])
            pg.wait_for_selector("#cw-grid .cell:not(.block)")
            for _ in range(4):
                st = cw_state(pg)
                pg.keyboard.press(st["sol"][st["sel"]])
            shot(pg, "03-crossword-mini")

            pg.click("#cw-cluelist-btn")
            pg.wait_for_selector("#cw-cluelist", state="visible")
            shot(pg, "04-clue-list")
            pg.click("#cw-cluelist [data-close-sheet]")

            pg.click("#cw-menu-btn")
            pg.wait_for_selector("#cw-sheet", state="visible")
            shot(pg, "05-check-reveal-menu")
            pg.click("#cw-sheet [data-close-sheet]")

            pg.wait_for_timeout(61_000)   # let the timer reach a believable solve time
            solve(pg)
            pg.wait_for_selector("#cw-done", state="visible")
            shot(pg, "06-crossword-complete")
            pg.click("#cw-done-back")

            for fmt, n in (("midi", "07-crossword-midi"), ("full", "08-crossword-full")):
                pz = by_fmt[fmt]
                if not pz:
                    continue
                pg.click('.cwitem[data-pid="%s"]' % pz["id"])
                pg.wait_for_selector("#cw-grid .cell:not(.block)")
                shot(pg, n)
                pg.click("#view-cw [data-back]")
            pg.click("#view-cwlist [data-back]")

            pg.click("#card-map")
            pg.wait_for_selector("#map-start")
            shot(pg, "09-map-start")
            pg.click("#map-start")
            pg.wait_for_selector("#map-svg circle")
            pg.wait_for_timeout(1100)
            shot(pg, "10-map-round")

            rounds = pg.evaluate("window.__CHRONICLE_TEST__.data.figures")
            for r in range(10):
                info = pg.evaluate("window.__CHRONICLE_TEST__.mapRound")
                fig = next(f for f in rounds if f["id"] == info["id"])
                if r == 0:
                    pg.click("#hint-occ")
                    shot(pg, "11-map-hint")
                    pg.fill("#map-input", fig["name"])
                    pg.click("#map-guess-btn")
                    pg.wait_for_selector("#map-feedback", state="visible")
                    shot(pg, "12-map-correct")
                elif r == 1:
                    pg.fill("#map-input", "not the right person")
                    pg.click("#map-guess-btn")
                    pg.wait_for_timeout(450)
                    shot(pg, "13-map-wrong-guess")
                    pg.click("#map-reveal")
                    pg.wait_for_selector("#map-feedback", state="visible")
                    shot(pg, "14-map-revealed")
                elif r < 5:
                    pg.fill("#map-input", fig["name"])
                    pg.click("#map-guess-btn")
                    pg.wait_for_selector("#map-feedback", state="visible")
                else:
                    pg.click("#map-reveal")
                    pg.wait_for_selector("#map-feedback", state="visible")
                pg.click("#map-next")
            pg.wait_for_selector("#sum-total")
            shot(pg, "15-map-summary")

            fail_on_errors(errors, "screenshots")

        with page_on(p, "chromium", device=None) as (pg, errors):
            pg.set_viewport_size({"width": 1280, "height": 800})
            pg.goto(base + "/")
            pg.wait_for_selector("#card-crossword")
            shot(pg, "16-desktop-home")
            fail_on_errors(errors, "desktop shot")

    print("SCREENSHOTS OK ->", OUT)


if __name__ == "__main__":
    main()
