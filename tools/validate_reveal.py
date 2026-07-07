#!/usr/bin/env python3
"""Validator for reveal-who.json, reveal-what.json and figures.json.

Run from repo root: python3 tools/validate_reveal.py
Exits non-zero on any ERROR.
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIFFICULTIES = {"easy", "medium", "hard"}

errors, warns = [], []
err = errors.append
warn = warns.append


def check_reveal(path):
    items = json.loads((ROOT / path).read_text())
    for dup, n in Counter(x.get("id") for x in items).items():
        if n > 1:
            err(f"{path}: duplicate id {dup}")
    variant_owner = {}
    for it in items:
        iid = it.get("id", "?")
        for field in ("name", "kind", "img", "blurb", "license", "source"):
            if not str(it.get(field) or "").strip():
                err(f"{path} {iid}: missing {field}")
        if it.get("difficulty") not in DIFFICULTIES:
            err(f"{path} {iid}: bad difficulty {it.get('difficulty')!r}")
        img = ROOT / it.get("img", "")
        if not img.is_file():
            err(f"{path} {iid}: image file missing: {it.get('img')}")
        elif img.stat().st_size < 20_000:
            warn(f"{path} {iid}: image suspiciously small ({img.stat().st_size} bytes)")
        for coord in ("fx", "fy"):
            v = it.get(coord)
            if not isinstance(v, (int, float)) or not (0.0 <= v <= 1.0):
                err(f"{path} {iid}: {coord} out of range: {v!r}")
        fr = it.get("frac")
        if not isinstance(fr, (int, float)) or not (0.05 <= fr <= 1.0):
            err(f"{path} {iid}: frac out of range: {fr!r}")
        vs = it.get("variants") or []
        if not vs:
            err(f"{path} {iid}: no variants")
        for v in vs:
            if v != v.lower().strip():
                err(f"{path} {iid}: variant not normalized: {v!r}")
            if v in variant_owner and variant_owner[v] != iid:
                warn(f"{path}: variant {v!r} shared by {variant_owner[v]} and {iid} "
                     f"(allowed — matcher is per-item — but check it's intentional)")
            variant_owner[v] = iid
    return len(items)


def check_figures():
    figs = json.loads((ROOT / "data/figures.json").read_text())
    for dup, n in Counter(f.get("id") for f in figs).items():
        if n > 1:
            err(f"figures: duplicate id {dup}")
    for dup, n in Counter(f.get("name", "").lower() for f in figs).items():
        if n > 1:
            err(f"figures: duplicate name {dup!r}")
    variant_owner = {}
    for f in figs:
        fid = f.get("id", "?")
        if f.get("difficulty") not in DIFFICULTIES:
            err(f"figures {fid}: bad difficulty")
        if not str(f.get("occupation") or "").strip():
            err(f"figures {fid}: missing occupation")
        for v in f.get("variants") or []:
            if v != v.lower().strip():
                err(f"figures {fid}: variant not normalized: {v!r}")
            if v in variant_owner and variant_owner[v] != fid:
                warn(f"figures: variant {v!r} shared by {variant_owner[v]} and {fid} "
                     f"(allowed — matcher is per-item — but check it's intentional)")
            variant_owner[v] = fid
        for end in ("birth", "death"):
            e = f.get(end) or {}
            y = e.get("year")
            if not isinstance(y, int) or not (-4000 <= y <= 2026):
                err(f"figures {fid}: bad {end} year {y!r}")
            if not str(e.get("place") or "").strip():
                err(f"figures {fid}: missing {end} place")
            lat, lon = e.get("lat"), e.get("lon")
            if not isinstance(lat, (int, float)) or not (-90 <= lat <= 90):
                err(f"figures {fid}: bad {end} lat {lat!r}")
            if not isinstance(lon, (int, float)) or not (-180 <= lon <= 180):
                err(f"figures {fid}: bad {end} lon {lon!r}")
        by = (f.get("birth") or {}).get("year")
        dy = (f.get("death") or {}).get("year")
        if isinstance(by, int) and isinstance(dy, int) and by >= dy:
            err(f"figures {fid}: birth {by} not before death {dy}")
    return len(figs)


def main():
    nwho = check_reveal("data/reveal-who.json")
    nwhat = check_reveal("data/reveal-what.json")
    nfig = check_figures()
    for w in warns:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"reveal-who {nwho}, reveal-what {nwhat}, figures {nfig} — "
          f"{len(errors)} errors, {len(warns)} warnings")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
