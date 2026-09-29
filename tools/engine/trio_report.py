#!/usr/bin/env python3
"""Trio report for the distractor auditor.

Usage: python3 tools/engine/trio_report.py A-B [--manifest PATH] [--all]
Lists every Face Value / Lifeline / Relic round scheduled in editions A..B
(one line per unique item, first airing shown) with its current 3-choice
distractors and whether they are owner/engine-pinned in
tools/fame/mcq_overrides.json. Pinned trios are skipped unless --all.
Also prints, per round, the names that must NOT be used as distractors
(answers on the same day and the days either side).
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("range")
    ap.add_argument("--manifest", default=str(ROOT / "data/editions.json"))
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    lo, hi = map(int, a.range.split("-"))
    eds = json.load(open(a.manifest))["editions"]
    pools = {"who": json.load(open(ROOT / "data/reveal-who.json")),
             "what": json.load(open(ROOT / "data/reveal-what.json")),
             "map": json.load(open(ROOT / "data/figures.json"))}
    idx = {g: {x["id"]: x for x in p} for g, p in pools.items()}
    pins = json.load(open(ROOT / "tools/fame/mcq_overrides.json"))

    def names(n):
        e = eds.get(str(n)) or {}
        return [idx[g][i]["name"] for g in ("who", "map", "what") for i in e.get(g, []) if i in idx[g]]

    seen = set()
    for n in range(lo, hi + 1):
        e = eds.get(str(n))
        if not e:
            continue
        banned = sorted(set(names(n - 1) + names(n) + names(n + 1)))
        for g in ("who", "map", "what"):
            for i in e.get(g, []):
                if (g, i) in seen:
                    continue
                seen.add((g, i))
                x = idx[g].get(i)
                if not x:
                    continue
                pinned = i in pins.get(g, {})
                if pinned and not a.all:
                    continue
                if g == "map":
                    ctx = (f"b. {x['birth'].get('place')} {x['birth'].get('year')} → "
                           f"d. {x['death'].get('place')} {x['death'].get('year')} · {x.get('occupation', '')}")
                else:
                    ctx = (x.get("blurb") or "").split("·")[0].strip()
                print(f"ed {n} {e['date']} | {g} | {i} | {x['name']} | {x.get('difficulty')} | {ctx} | "
                      f"now: {x.get('mcq')}{' (PINNED)' if pinned else ''} | avoid: {'; '.join(banned)}")


if __name__ == "__main__":
    main()
