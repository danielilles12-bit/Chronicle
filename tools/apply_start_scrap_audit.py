#!/usr/bin/env python3
"""Apply start-scrap audit verdicts to data/reveal-*.json.

Reads the batch result files produced by the audit agents (see
tools/audit_start_scraps.py for the card generator and the rubric), validates
each recommendation, and writes a `start` override (opening-scrap cell 0-8)
onto flagged items. startScrap() in js/revealgame.js honours the override.

Usage: python3 tools/apply_start_scrap_audit.py <results-dir> <manifest.json>
Prints a per-verdict summary and the items that need manual refocusing.
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    results_dir, manifest_path = sys.argv[1], sys.argv[2]
    manifest = {r["id"]: r for r in json.load(open(manifest_path))["items"]}

    verdicts = {}
    for f in sorted(glob.glob(os.path.join(results_dir, "batch-*.json"))):
        for row in json.load(open(f)):
            verdicts[row["id"]] = row

    missing = [i for i in manifest if i not in verdicts]
    if missing:
        print(f"WARNING: {len(missing)} items have no verdict: {missing[:10]}")

    stats = {"FAIR": 0, "TOO_EASY": 0, "UNFAIR": 0, "BROKEN": 0}
    overrides = {}     # id -> start cell
    needs_refocus = []
    invalid = []
    for item_id, v in verdicts.items():
        stats[v["verdict"]] = stats.get(v["verdict"], 0) + 1
        if v["verdict"] in ("FAIR",):
            continue
        if v["verdict"] == "BROKEN":
            needs_refocus.append((item_id, "BROKEN: " + v.get("note", "")))
            continue
        ns = v.get("new_start")
        m = manifest[item_id]
        if ns is None:
            needs_refocus.append((item_id, v["verdict"] + ": " + v.get("note", "")))
            continue
        if not isinstance(ns, int) or not 0 <= ns <= 8 or ns == m["money"]:
            invalid.append((item_id, ns, "money" if ns == m["money"] else "range"))
            continue
        if ns == m["start"]:
            continue           # recommends the cell already in use: no-op
        overrides[item_id] = ns

    for fname in ("reveal-who.json", "reveal-what.json"):
        path = os.path.join(ROOT, "data", fname)
        items = json.load(open(path))
        n = 0
        for item in items:
            if item["id"] in overrides:
                item["start"] = overrides[item["id"]]
                n += 1
        json.dump(items, open(path, "w"), indent=1, ensure_ascii=False)
        print(f"{fname}: {n} start overrides written")

    print("\nverdicts:", stats)
    print(f"overrides applied: {len(overrides)}")
    if invalid:
        print(f"\nINVALID recommendations (skipped): {invalid}")
    if needs_refocus:
        print(f"\nNEEDS MANUAL REFOCUS ({len(needs_refocus)}):")
        for item_id, note in needs_refocus:
            print(f"  {item_id}: {note}")


if __name__ == "__main__":
    main()
