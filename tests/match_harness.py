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
        with page_on(p, "chromium") as (pg, errors):
            pg.goto(base + "/index.html?test=1")
            # Boot sets the hook object before the data files finish
            # downloading — wait for the pools themselves.
            pg.wait_for_function(
                "window.__CHRONICLE_TEST__ && __CHRONICLE_TEST__.data.figures"
                " && __CHRONICLE_TEST__.data.reveal")

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

            # Owner report 2026-07-15: a generic distinctive noun ("rhino")
            # must not carry a guess whose other words contradict the item.
            rhino = next(x for x in what if x["id"] == "mapungubwe-gold-rhino")
            check("'mongolian golden rhino' does NOT match mapungubwe-gold-rhino",
                  not is_match(pg, "Mongolian Golden Rhino", rhino, "what"))
            check("'golden rhino' still matches mapungubwe-gold-rhino",
                  is_match(pg, "golden rhino", rhino, "what"))
            check("'gold rhino statue' still matches mapungubwe-gold-rhino",
                  is_match(pg, "gold rhino statue", rhino, "what"))

            # Owner report 2026-07-15: doubled-letter respellings are the
            # classic name typo and must pass ("Elliott" ~ "Eliot").
            ts_eliot = next(x for x in figures if x["id"] == "t-s-eliot")
            check("'T.S.Elliott' matches t-s-eliot (doubled letters)",
                  is_match(pg, "T.S.Elliott", ts_eliot, "map"))
            check("'Elliott' matches t-s-eliot via 'eliot' variant",
                  is_match(pg, "Elliott", ts_eliot, "map"))

            # Owner report 2026-07-15 (turned out to be a stale phone cache,
            # but keep the case): the Italian name of Milan Cathedral.
            milan = next(x for x in what if x["id"] == "milan-cathedral")
            check("'Duomo di Milano' matches milan-cathedral",
                  is_match(pg, "Duomo di Milano", milan, "what"))

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

            # ---------------- REJECT LIST: every item.reject entry, auto -----------
            # Data-driven per-item rejects (js/match.js's matchesReject) are curated
            # in data/*.json — this loop auto-covers whatever's there right now,
            # across all three pools, with no hardcoded item list to maintain.
            # 0 cases (harmlessly) until the data agent starts populating `reject`.
            reject_cases = 0
            for key, items in pools:
                for it in items:
                    for rej in (it.get("reject") or []):
                        reject_cases += 1
                        check("%s/%s: reject %r does NOT match" % (key, it["id"], rej),
                              not is_match(pg, rej, it, key))
            print("reject cases checked (from item.reject entries): %d" % reject_cases)

            # ---------------- NAMED REGRESSION CASES (launch-review P0s) -----------
            # Permanent cases from the 2026-08-03 launch review. Some of these rely
            # on variant/reject additions the DATA agent is landing in parallel —
            # they may fail here until that data lands; see the session report.
            def find_or_flag(items, item_id, label):
                it = next((x for x in items if x["id"] == item_id), None)
                check("%s: item id %r exists in data" % (label, item_id), it is not None)
                return it

            escobar = find_or_flag(who, "pablo-escobar", "escobar regression case")
            if escobar:
                check("'escobar' matches pablo-escobar",
                      is_match(pg, "escobar", escobar, "who"))

            hg_wells = find_or_flag(who, "hg-wells", "hg wells regression case")
            if hg_wells:
                check("'hg wells' matches hg-wells",
                      is_match(pg, "hg wells", hg_wells, "who"))

            eisenhower = find_or_flag(who, "eisenhower", "eisenhower regression case")
            if eisenhower:
                check("'eisenhower' matches eisenhower (who)",
                      is_match(pg, "eisenhower", eisenhower, "who"))

            nga = find_or_flag(what, "national-gallery-art", "national gallery regression case")
            if nga:
                check("'national gallery washington' matches national-gallery-art",
                      is_match(pg, "national gallery washington", nga, "what"))

            pisa = find_or_flag(what, "leaning-tower-pisa", "pisa cathedral reject case")
            if pisa:
                check("'pisa cathedral' does NOT match leaning-tower-pisa (reject)",
                      not is_match(pg, "pisa cathedral", pisa, "what"))

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
