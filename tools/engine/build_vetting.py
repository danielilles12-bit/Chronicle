#!/usr/bin/env python3
"""Merge auditor verdicts into tools/engine/vetting.json (29 Sep 2026 build).

Precedence, highest first:
  1. Owner-struck items (his review-board strikes, 10 Aug - 22 Sep)  -> benched
  2. Owner-approved items (aired eds 42-88, plus his explicit approvals
     in 89-90)                                                       -> vetted,
     keeping his curated opening scrap
  3. Opus spot-check verdict (15% sample)
  4. Sonnet verdict — for items the owner never saw, only
     famous == "yes" passes (the spot-check showed Sonnet's "borderline"
     passes failed a stricter read 2 times in 3)
Lifeline uses the Sonnet vetter with rules 1-2 on top. Thread boards are
added by the Thread critic step, not here (existing "thread" entries are
preserved).

Usage: python3 tools/engine/build_vetting.py VERDICT_DIR
"""
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tools/engine/vetting.json"

STRUCK = {
    "who": ["peter-paul-rubens", "titian", "claude-monet", "voltaire", "philip-ii-spain",
            "gautama-buddha", "artemisia-gentileschi", "jane-austen", "aristotle",
            "kosem-sultan", "charles-v-hre", "thomas-jefferson", "franz-kafka",
            "rembrandt-self", "kurt-cobain", "martin-van-buren", "andrew-jackson",
            "blaise-pascal", "zachary-taylor", "william-henry-harrison", "niels-bohr"],
    "what": ["cutty-sark", "forbidden-city", "lahore-fort", "persepolis", "elephanta-caves",
             "longmen-grottoes", "kaaba", "catalhoyuk", "terracotta-warrior", "port-royal",
             "st-catherines-monastery", "lighthouse-alexandria"],
    "map": ["maimonides", "themistocles", "tycho-brahe", "alcibiades", "t-s-eliot",
            "chandragupta-maurya", "kwame-nkrumah", "sun-yat-sen", "empress-matilda",
            "saint-peter"],
}
EXTRA_APPROVED = {  # owner's explicit APPROVEs on eds 89-90 (22 Sep export)
    "who": {"benjamin-franklin", "johann-sebastian-bach"},
    "what": {"westminster-abbey", "venus-willendorf", "statue-zeus-olympia",
             "gundestrup-cauldron", "palmyra"},
    "map": {"nina-simone", "richard-ii"},
}


def main():
    vd = Path(sys.argv[1])
    eds = json.loads((ROOT / "data/editions.json").read_text())["editions"]
    approved = {g: set(EXTRA_APPROVED[g]) for g in ("who", "what", "map")}
    for n in range(42, 89):
        for g in approved:
            approved[g].update(eds[str(n)][g])
    sonnet = {}
    for f in sorted(glob.glob(str(vd / "pic-*.json"))):
        for v in json.load(open(f)):
            sonnet[(v["game"], v["id"])] = v
    opus = {}
    spot = vd / "spot-opus.json"
    if spot.exists():
        for v in json.load(open(spot)):
            opus[v["id"]] = v
    old = json.loads(OUT.read_text()) if OUT.exists() else {}
    out = {"_note": "Content-engine verdicts; see tools/engine/PLAYBOOK.md s.8 and "
                    "tools/engine/build_vetting.py for precedence.",
           "who": {}, "what": {}, "map": {}, "thread": old.get("thread", {})}
    for (g, i), s in sorted(sonnet.items()):
        if i in STRUCK[g]:
            out[g][i] = {"ok": False, "by": "owner-struck"}
        elif i in approved[g]:
            out[g][i] = {"ok": True, "by": "owner-approved"}
        elif i in opus:
            o = opus[i]
            out[g][i] = {"ok": bool(o["ok"]), "start": o.get("start"), "by": "opus",
                         "why": o.get("why")}
        else:
            ok = bool(s["ok"]) and s.get("famous") == "yes"
            out[g][i] = {"ok": ok, "start": s.get("start"), "by": "sonnet",
                         "why": s.get("why")}
    for i, v in json.load(open(vd / "lifeline.json")).items():
        if i in STRUCK["map"]:
            out["map"][i] = {"ok": False, "by": "owner-struck"}
        elif i in approved["map"]:
            out["map"][i] = {"ok": True, "tier": v.get("tier"), "by": "owner-approved"}
        else:
            out["map"][i] = {"ok": bool(v["ok"]), "tier": v.get("tier"), "by": "sonnet",
                             "why": v.get("why")}
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    for g in ("who", "what", "map"):
        print(g, sum(v["ok"] for v in out[g].values()), "vetted of", len(out[g]))


if __name__ == "__main__":
    main()
