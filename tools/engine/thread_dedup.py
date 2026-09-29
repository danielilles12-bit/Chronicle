#!/usr/bin/env python3
"""Dedup check for candidate Thread boards against the whole pool.

Usage: python3 tools/engine/thread_dedup.py CANDIDATES.json [CANDIDATES2.json ...]
Each file holds a JSON list of boards in the data/connections.json shape
(title, difficulty, groups[{colour,label,items}]; id optional).

Reports, per candidate board:
  TILE   a tile already used on existing boards (count + ids). 3+ = reject.
  LABEL  a group label that shares most of its words with an existing label.
  CROSS  a tile or near-identical label shared with ANOTHER candidate.
Exit code 0 always — this is a report, the writer/critic decides.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STOP = {"the", "of", "a", "an", "and", "in", "to", "for", "by", "on", "their",
        "who", "that", "were", "was", "are", "is", "famous", "known", "as", "with"}


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", s.lower().replace("&", "and")).strip()


def toks(label):
    return {t for t in norm(label).split() if t not in STOP and len(t) > 2}


def sim(a, b):
    ta, tb = toks(a), toks(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def main():
    pool = json.load(open(ROOT / "data/connections.json"))
    tiles, labels = {}, []
    for b in pool:
        for g in b["groups"]:
            labels.append((g["label"], b["id"], b.get("title", "")))
            for t in g["items"]:
                tiles.setdefault(norm(t), []).append(b["id"])
    cands = []
    for f in sys.argv[1:]:
        for b in json.load(open(f)):
            cands.append((Path(f).name, b))
    cand_tiles = {}
    for src, b in cands:
        for g in b["groups"]:
            for t in g["items"]:
                cand_tiles.setdefault(norm(t), []).append(b.get("title"))
    for src, b in cands:
        lines = []
        for g in b["groups"]:
            for t in g["items"]:
                hits = tiles.get(norm(t), [])
                if hits:
                    lines.append(f"  TILE  {t!r} on {len(hits)} existing: {', '.join(sorted(set(hits))[:6])}"
                                 + ("   <-- REJECT (3+)" if len(set(hits)) >= 3 else ""))
                others = [x for x in cand_tiles.get(norm(t), []) if x != b.get("title")]
                if others:
                    lines.append(f"  CROSS tile {t!r} also in candidate(s): {', '.join(others)}")
            for lab, bid, title in labels:
                s = sim(g["label"], lab)
                if s >= 0.6:
                    lines.append(f"  LABEL {g['label']!r} ~ {lab!r} ({bid} {title})")
            for src2, b2 in cands:
                if b2 is b:
                    continue
                for g2 in b2["groups"]:
                    if sim(g["label"], g2["label"]) >= 0.75:
                        lines.append(f"  CROSS label {g['label']!r} ~ {g2['label']!r} in {b2.get('title')}")
        print(f"[{src}] {b.get('title')} ({b.get('difficulty')}): "
              + ("clean" if not lines else f"{len(lines)} note(s)"))
        for ln in lines:
            print(ln)


if __name__ == "__main__":
    main()
