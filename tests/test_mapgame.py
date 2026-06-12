#!/usr/bin/env python3
"""Play a full deterministic Map of a Life session on WebKit/iPhone:
typos, accents, variants, wrong guesses, both hints, reveals — and assert the
scoring math exactly."""
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
from helpers import server, page_on, fail_on_errors  # noqa: E402


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", s)).strip()


def typo(name):
    n = norm(name)
    if len(n) > 8:
        return n[:3] + n[4:]            # drop one letter (distance 1)
    return n[:2] + n[3] + n[2] + n[4:]  # swap two middle letters


def accentify(name):
    return name.replace("e", "é", 1) if "e" in name else name + "!"


def guess(pg, text):
    pg.fill("#map-input", text)
    pg.click("#map-guess-btn")


def round_info(pg):
    info = pg.evaluate("window.__CHRONICLE_TEST__.mapRound")
    figs = pg.evaluate("window.__CHRONICLE_TEST__.data.figures")
    fig = next(f for f in figs if f["id"] == info["id"])
    return info, fig


def main():
    with server() as base, sync_playwright() as p:
        with page_on(p, "webkit") as (pg, errors):
            pg.goto(base + "/?mapseed=42")
            pg.wait_for_selector("#card-map")
            pg.click("#card-map")
            pg.wait_for_selector("#map-start")
            pg.click("#map-start")
            pg.wait_for_selector("#map-svg circle")

            expected_total = 0
            streak = 0
            for r in range(10):
                info, fig = round_info(pg)
                assert pg.text_content("#map-progress").strip() == "Round %d of 10" % (r + 1)
                pts = 0
                if r == 0:
                    guess(pg, fig["name"])
                    pts = 100
                elif r == 1:
                    guess(pg, typo(fig["name"]))
                    pts = 100
                elif r == 2:
                    guess(pg, accentify((fig.get("variants") or [fig["name"]])[-1]))
                    pts = 100
                elif r == 3:
                    guess(pg, "zzz qqq")
                    guess(pg, "xxxx yyyy")
                    guess(pg, fig["name"].upper())
                    pts = 80
                elif r == 4:
                    pg.click("#hint-occ")
                    chip = pg.text_content(".hint-chip")
                    assert chip.strip() == fig["occupation"], chip
                    guess(pg, fig["name"])
                    pts = 75
                elif r == 5:
                    pg.click("#hint-occ")
                    pg.click("#hint-ini")
                    want = " ".join(w[0].upper() + "." for w in fig["name"].split())
                    chips = pg.locator(".hint-chip").all_text_contents()
                    assert any(want in c for c in chips), (want, chips)
                    guess(pg, fig["name"])
                    pts = 50
                elif r in (6, 7):
                    if r == 7:
                        guess(pg, "wrong answer here")
                    pg.click("#map-reveal")
                    pts = 0
                else:
                    guess(pg, fig["name"])
                    pts = 100

                correct = pts > 0
                if correct:
                    streak += 1
                    if streak >= 2:
                        pts += 10
                else:
                    streak = 0
                expected_total += pts

                pg.wait_for_selector("#map-feedback", state="visible")
                fb = pg.text_content("#map-feedback")
                assert fig["name"] in fb, "feedback must name the figure"
                if correct:
                    assert "+%d pts" % pts in fb, "expected +%d in: %s" % (pts, fb)
                shown = pg.text_content("#map-score")
                assert shown.strip() == "%d pts" % expected_total, \
                    "score %s != expected %d (round %d)" % (shown, expected_total, r + 1)
                pg.click("#map-next")

            pg.wait_for_selector("#sum-total")
            total = pg.text_content("#sum-total").strip()
            assert total == str(expected_total), (total, expected_total)
            assert pg.locator("#sum-rounds li").count() == 10
            print("session total:", total)

            # best score persists
            pg.click("#sum-home")
            pg.reload()
            pg.wait_for_selector("#card-map")
            pg.click("#card-map")
            best = pg.text_content("#map-best")
            assert str(expected_total) in best, best

            fail_on_errors(errors, "map session")

    print("MAP GAME TESTS OK (total matched: %s)" % total)


if __name__ == "__main__":
    main()
