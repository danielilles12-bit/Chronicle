#!/usr/bin/env python3
"""Regression harness for js/match.js answer-matching rules.

Loads the real app page (so the real data files boot and registerPool runs
exactly as it does in production — 'map' for figures.json, 'who'/'what' for
reveal-who.json/reveal-what.json), then drives window.__CHRONICLE_TEST__.isMatch
directly from Python. No game UI is exercised here; test_mapgame.py and
test_reveal.py already cover the click-through paths.

Checks:
  POSITIVE - every item's own name and every variant matches itself, across
             all three pools (figures / reveal-who / reveal-what).
  BUG FIXES - the two owner-reported permanent regression cases.
  EXTRAS   - a few "sensible" containment/covers cases.
  NEGATIVE - guesses that must NOT match, including shared (non-distinctive)
             tokens, bare stopwords, too-short junk, and nonsense strings.

Prints pass/fail counts; exits nonzero if anything fails.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
from helpers import server, page_on, fail_on_errors  # noqa: E402

passed = 0
failed = 0
failures = []


def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        failures.append(label)


def is_match(pg, guess, item, pool_key=None):
    return pg.evaluate(
        "(a) => window.__CHRONICLE_TEST__.isMatch(a.guess, a.item, a.poolKey)",
        {"guess": guess, "item": item, "poolKey": pool_key},
    )


def main():
    with server() as base, sync_playwright() as p:
        with page_on(p, "webkit") as (pg, errors):
            pg.goto(base + "/")
            pg.wait_for_function("window.__CHRONICLE_TEST__ !== undefined")

            figures = pg.evaluate("window.__CHRONICLE_TEST__.data.figures")
            reveal = pg.evaluate("window.__CHRONICLE_TEST__.data.reveal")
            who = [x for x in reveal if x["kind"] == "portrait"]
            what = [x for x in reveal if x["kind"] != "portrait"]

            print("pool sizes: map=%d who=%d what=%d total=%d"
                  % (len(figures), len(who), len(what),
                     len(figures) + len(who) + len(what)))

            # ---------------- POSITIVE: everything matches itself ----------------
            pools = [("map", figures), ("who", who), ("what", what)]
            for key, items in pools:
                for it in items:
                    cands = [it["name"]] + (it.get("variants") or [])
                    for cand in cands:
                        ok = is_match(pg, cand, it, key)
                        check("%s/%s: %r matches self" % (key, it["id"], cand), ok)

            # ---------------- BUG FIXES (permanent regression cases) -------------
            parthenon = next(x for x in what if x["id"] == "parthenon")
            check("'parthenon athens' matches parthenon",
                  is_match(pg, "parthenon athens", parthenon, "what"))

            nazca = next(x for x in what if x["id"] == "nazca-lines")
            check("'nazca hummingbird' matches nazca-lines",
                  is_match(pg, "nazca hummingbird", nazca, "what"))

            # ---------------- EXTRAS: sensible additional matches -----------------
            taj = next(x for x in what if x["id"] == "taj-mahal")
            check("'the taj mahal india' matches taj-mahal",
                  is_match(pg, "the taj mahal india", taj, "what"))

            mary = next(x for x in figures if x["id"] == "mary-i")
            check("'queen mary' matches mary-i (existing behaviour)",
                  is_match(pg, "queen mary", mary, "map"))

            great_wall = next(x for x in what if x["id"] == "great-wall-china")
            check("'the great wall of china in beijing' matches great-wall-china",
                  is_match(pg, "the great wall of china in beijing", great_wall, "what"))

            school_athens = next(x for x in what if x["id"] == "school-of-athens")
            check("'school of athens fresco' matches school-of-athens (containment)",
                  is_match(pg, "school of athens fresco", school_athens, "what"))

            # ---------------- NEGATIVE: must NOT match -----------------------------
            napoleon = next(x for x in figures if x["id"] == "napoleon")
            check("'great' alone does NOT match great-wall-china (shared token)",
                  not is_match(pg, "great", great_wall, "what"))

            check("'the' alone does NOT match napoleon",
                  not is_match(pg, "the", napoleon, "map"))
            check("'the' alone does NOT match great-wall-china",
                  not is_match(pg, "the", great_wall, "what"))

            # "athens" is not a token of any parthenon variant at all (its variants
            # are just 'parthenon'/'acropolis'), and even if it were, it's shared
            # with school-of-athens -> genuinely non-distinctive either way.
            check("'athens' alone does NOT match parthenon (not distinctive/absent)",
                  not is_match(pg, "athens", parthenon, "what"))

            check("'xyz' does NOT match napoleon",
                  not is_match(pg, "xyz", napoleon, "map"))

            check("empty string does NOT match napoleon",
                  not is_match(pg, "", napoleon, "map"))

            check("short junk 'cid' below guard-rail length still exact-matches its own variant",
                  is_match(pg, "cid", {"id": "__test_cid", "name": "El Cid", "variants": ["el cid", "cid"]}, None))
            check("'xyz' (3 chars, below guard rail) does NOT containment/core-match unrelated item",
                  not is_match(pg, "xyz", napoleon, "map"))

            fail_on_errors(errors, "match harness")

    print("\n%d passed, %d failed" % (passed, failed))
    if failed:
        print("\nFAILURES:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("MATCH HARNESS OK")


if __name__ == "__main__":
    main()
