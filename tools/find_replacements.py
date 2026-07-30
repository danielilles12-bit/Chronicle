#!/usr/bin/env python3
"""Swap helper for audit-driven restaging: legal replacements for one slot.

Usage:  python3 tools/find_replacements.py <game> <tier> <edition> <drop-id>
   e.g. python3 tools/find_replacements.py who easy 46 herbert-hoover

Prints the top candidates that could legally fill the slot: right tier,
image on disk, Lifeline distance floor, dark-tone cap respected, no
same-day or adjacent-day answer/subject collision, and the repeat floor
keyed on NORMALISED NAME across every game (so `hendrix` and
`jimi-hendrix` count as the same person) with the launch blindfold applied
(editions before launch_edition are invisible). Born as scratch tooling in
the 29 Jul session; promoted because every audit round needs it.
"""
import collections
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compile_editions as C  # noqa: E402

POOLS = C.load_pools()
MAN = C.load_manifest()["editions"]
CFG = C.load_config()
FAME_IDX, TAG_IDX = C.load_signal_indices()
SAL = {(r["game"], r["id"]): r.get("salience")
       for r in json.load(open(str(C.ROOT / "tools/fame/salience.json")))["items"]}
IDX = {g: {x["id"]: x for x in POOLS[g]} for g in C.GAMES}


LAUNCH = CFG.get("launch_edition", 0)


def aired_keys(skip=None):
    """key -> [dates staged], across every game, editions >= launch only.
    Keys are BOTH the normalised display name AND the raw id string: the
    same person can differ on either axis across pools (`hendrix` vs
    `jimi-hendrix` share a name, not an id; who/`napoleon` "Napoleon" and
    map/`napoleon` "Napoleon Bonaparte" share an id, not a name). The
    compiler floors on both; so must this helper."""
    out = collections.defaultdict(list)
    for k, e in MAN.items():
        if int(k) < LAUNCH:
            continue
        d = datetime.date.fromisoformat(e["date"])
        for g in ("who", "map", "what"):
            for i in e[g]:
                if skip and (int(k), g, i) == skip:
                    continue
                it = IDX[g].get(i)
                if it:
                    out[C.normalise(it["name"])].append(d)
                    out["id:" + i].append(d)
    return out


def day_context(ed, game, drop_id):
    """Answers + variant strings already committed on ed and its neighbours."""
    answers, subjects, adj = set(), set(), set()
    for n in (ed - 1, ed, ed + 1):
        e = MAN.get(str(n))
        if not e:
            continue
        for g in ("who", "map", "what"):
            for i in e[g]:
                if n == ed and g == game and i == drop_id:
                    continue
                it = IDX[g].get(i)
                if not it:
                    continue
                target = (answers, subjects) if n == ed else (adj, adj)
                target[0].add(C.normalise(it["name"]))
                for v in it.get("variants") or []:
                    target[-1].add(C.normalise(v))
        for i in e["thread"]:
            b = IDX["thread"].get(i)
            if b:
                (subjects if n == ed else adj).update(C.thread_answer_keys(b))
    return answers, subjects, adj


def candidates(game, tier, ed, drop_id, limit=20):
    d = datetime.date.fromisoformat(MAN[str(ed)]["date"])
    aired = aired_keys(skip=(ed, game, drop_id))
    answers, subjects, adj = day_context(ed, game, drop_id)
    # tone: how many dark / power subjects the issue already carries
    e = MAN[str(ed)]
    dark = sum(1 for g in C.GAMES for i in e[g]
               if not (g == game and i == drop_id) and C.is_dark_tone(CFG, g, i))
    out = []
    for x in POOLS[game]:
        if x.get("difficulty") != tier or x.get("reserve"):
            continue
        if game in ("who", "what") and not (C.ROOT / x["img"]).exists():
            continue
        if game == "map" and C.haversine_km(x["birth"], x["death"]) < CFG["min_lifeline_km"] \
                and not x.get("allow_close"):
            continue
        nm = C.normalise(x["name"])
        gaps = [abs((d - ad).days)
                for ad in aired.get(nm, []) + aired.get("id:" + x["id"], [])]
        if gaps and min(gaps) < CFG["repeat_floor_days"]:
            continue
        if nm in answers or nm in subjects or nm in adj:
            continue
        vs = {C.normalise(v) for v in (x.get("variants") or [])}
        if vs & subjects or vs & adj:
            continue
        if C.is_dark_tone(CFG, game, x["id"]) and dark >= CFG["max_dark_tone_per_issue"]:
            continue
        sig = C.item_signal(game, x, FAME_IDX, TAG_IDX)
        out.append({
            "id": x["id"], "name": x["name"],
            "fame": sig.get("fame"), "sal": SAL.get((game, x["id"])),
            "occ": sig.get("occupation_family"), "region": sig.get("region"),
            "era": sig.get("era"),
            "gap": min(gaps) if gaps else None,
        })
    out.sort(key=lambda r: -(r["fame"] or 0))
    return out[:limit]


if __name__ == "__main__":
    game, tier, ed, drop = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    print(f"--- ed{ed} {game}/{tier}, replacing {drop} ---")
    for r in candidates(game, tier, ed, drop):
        print(f"  fame={r['fame'] or 0:5.1f} sal={(r['sal'] or 0):5.1f} "
              f"gap={str(r['gap'] or 'never'):>5}  {r['occ'] or '-':12} "
              f"{r['region'] or '-':16} {r['name']}")
