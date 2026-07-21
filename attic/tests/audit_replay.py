#!/usr/bin/env python3
"""Replay the owner's 100-verdict calibration audit against the live
js/match.js engine (boots the real app/data, same technique as
match_harness.py) and report agreement vs ownerVerdict, per category and
overall, plus a list of any remaining disagreements.

Usage: python3 tests/audit_replay.py [path/to/audit-results.json]
Defaults to the scratchpad copy used during the match-tuning session.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
from helpers import server, page_on, fail_on_errors  # noqa: E402

DEFAULT_AUDIT = (
    "/private/tmp/claude-501/-Users-danielilles-Desktop-History-quiz-app/"
    "e42ec358-6539-4b97-9a3f-55c0efd8dd0f/scratchpad/audit-results.json"
)

# Cases the owner explicitly retained as intentional leniency (a real name
# fragment that's still stored as a literal variant, kept by decision) —
# these are expected to still disagree and are not counted as failures.
INTENDED_EXCEPTIONS = {
    ("thomas-jefferson", "jefferson"),
    ("confucius", "kong qiu"),
}


def is_match(pg, guess, item, pool_key):
    return pg.evaluate(
        "(a) => window.__CHRONICLE_TEST__.isMatch(a.guess, a.item, a.poolKey)",
        {"guess": guess, "item": item, "poolKey": pool_key},
    )


def main():
    audit_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_AUDIT
    with open(audit_path) as f:
        cases = json.load(f)

    with server() as base, sync_playwright() as p:
        with page_on(p, "webkit") as (pg, errors):
            pg.goto(base + "/")
            pg.wait_for_function("window.__CHRONICLE_TEST__ !== undefined")

            figures = pg.evaluate("window.__CHRONICLE_TEST__.data.figures")
            reveal = pg.evaluate("window.__CHRONICLE_TEST__.data.reveal")
            who = [x for x in reveal if x["kind"] == "portrait"]
            what = [x for x in reveal if x["kind"] != "portrait"]
            by_pool = {"map": (figures, "map"), "who": (who, "who"), "what": (what, "what")}

            per_cat = {}
            disagreements = []
            expected_exceptions_seen = []
            total = 0
            agree = 0

            for case in cases:
                items, pool_key = by_pool[case["game"]]
                item = next((x for x in items if x["id"] == case["itemId"]), None)
                if item is None:
                    print("WARNING: itemId not found: %s (%s)" % (case["itemId"], case["game"]))
                    continue
                new_verdict = is_match(pg, case["guess"], item, pool_key)
                owner = case["ownerVerdict"]
                total += 1
                cat = case["category"]
                per_cat.setdefault(cat, [0, 0])  # [agree, total]
                per_cat[cat][1] += 1
                if new_verdict == owner:
                    agree += 1
                    per_cat[cat][0] += 1
                else:
                    key = (case["itemId"], case["guess"])
                    entry = {
                        "itemId": case["itemId"],
                        "guess": case["guess"],
                        "category": cat,
                        "ownerVerdict": owner,
                        "oldEngineVerdict": case.get("engineVerdict"),
                        "newEngineVerdict": new_verdict,
                    }
                    if key in INTENDED_EXCEPTIONS:
                        expected_exceptions_seen.append(entry)
                    else:
                        disagreements.append(entry)

            fail_on_errors(errors, "audit replay")

    print("=" * 70)
    print("AUDIT REPLAY RESULTS")
    print("=" * 70)
    print("\nPer-category agreement:")
    for cat in sorted(per_cat):
        a, t = per_cat[cat]
        print("  %-20s %d/%d" % (cat, a, t))

    print("\nOverall: %d/%d agree with owner (%.1f%%)" % (agree, total, 100.0 * agree / total))

    print("\nIntended exceptions (retained by decision, expected to disagree):")
    if expected_exceptions_seen:
        for e in expected_exceptions_seen:
            print("  - %s guess=%r category=%s ownerVerdict=%s engineVerdict=%s"
                  % (e["itemId"], e["guess"], e["category"], e["ownerVerdict"], e["newEngineVerdict"]))
    else:
        print("  (none seen — check INTENDED_EXCEPTIONS is still accurate)")

    print("\nUNEXPECTED remaining disagreements:")
    if disagreements:
        for d in disagreements:
            print("  - %s guess=%r category=%s ownerVerdict=%s oldEngine=%s newEngine=%s"
                  % (d["itemId"], d["guess"], d["category"], d["ownerVerdict"],
                     d["oldEngineVerdict"], d["newEngineVerdict"]))
    else:
        print("  (none)")

    print()
    if disagreements:
        print("FAIL: %d unexpected disagreement(s)" % len(disagreements))
        sys.exit(1)
    print("AUDIT REPLAY OK (only intended exceptions remain)")


if __name__ == "__main__":
    main()
