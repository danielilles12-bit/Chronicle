#!/usr/bin/env python3
"""Content-engine autopilot: the mechanical half of the unattended weekly run.

The judgment half (writing Thread boards, auditing pictures and distractors)
is done by Claude sub-agents between these steps; see tools/engine/PLAYBOOK.md
section 7 and tools/engine/ROUTINE.md for the full procedure.

Subcommands (run from the repo root):
  status            How many days are scheduled ahead, how many days to fill,
                    and the vetted Thread stock. Exit 0 always.
  stage [--days N]  Draft the next N days (default: whatever status says)
                    from vetted items only -> data/editions.proposed.json.
  merged            Write tools/out/engine-audit/merged.json (manifest +
                    proposals) for the audit tools and the schedule check.
  tidy-thread       After stage: hand-place held boards (vetting "place_on"),
                    and replace any board scheduled twice in the draft with
                    an unused vetted board (the compiler reuses boards past
                    the repeat floor when stock runs short).
  gate              Validate merged schedule, approve the proposals, rebuild
                    the 3-choice clues, and run every validator. Exit 1 on
                    any failure (nothing is committed by this tool).
  bump              Bump BUILD (js/app.js) and VERSION (sw.js) together.
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EPOCH = date(2026, 6, 29)
MANIFEST = ROOT / "data/editions.json"
PROPOSED = ROOT / "data/editions.proposed.json"
VETTING = ROOT / "tools/engine/vetting.json"
OUT = ROOT / "tools/out/engine-audit"
BUFFER_MIN_DAYS = 56      # top up when fewer than 8 weeks are scheduled
BUFFER_FILL_TO = 63       # ... and fill to 9 weeks, so a run adds ~a week
THREAD_TIER = ["easy", "easy", "medium", "medium", "hard", "hard", "hard"]


def today_ed():
    return (date.today() - EPOCH).days


def load(p):
    return json.loads(Path(p).read_text())


def run(cmd):
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT).returncode


def status(as_json=False):
    m = load(MANIFEST)["editions"]
    t = today_ed()
    last = max(int(k) for k in m)
    ahead = last - t
    fill = max(0, BUFFER_FILL_TO - ahead) if ahead < BUFFER_MIN_DAYS else 0
    vet = load(VETTING) if VETTING.exists() else {}
    boards = load(ROOT / "data/connections.json")
    aired = {e["thread"][0] for e in m.values() if e.get("thread")}
    stock = {"easy": 0, "medium": 0, "hard": 0}
    for b in boards:
        if b.get("reserve") or b["id"] in aired:
            continue
        if (vet.get("thread", {}).get(b["id"]) or {}).get("ok"):
            stock[b["difficulty"]] += 1
    need = {"easy": 0, "medium": 0, "hard": 0}
    for n in range(last + 1, last + 1 + fill):
        need[THREAD_TIER[n % 7]] += 1
    out = {"today_edition": t, "today": str(date.today()),
           "last_scheduled_edition": last,
           "last_scheduled_date": str(EPOCH + timedelta(days=last)),
           "days_ahead": ahead, "days_to_fill": fill,
           "thread_stock": stock, "thread_needed": need,
           "thread_boards_to_write": max(0, sum(need.values()) - sum(stock.values())),
           "vetted_pool": {g: sum(1 for v in vet.get(g, {}).values() if v.get("ok"))
                           for g in ("who", "what", "map")}}
    print(json.dumps(out, indent=1) if as_json else
          "\n".join(f"{k}: {v}" for k, v in out.items()))
    return out


def merged():
    m = load(MANIFEST)
    if PROPOSED.exists():
        for k, v in load(PROPOSED)["editions"].items():
            m["editions"].setdefault(k, {kk: vv for kk, vv in v.items()
                                         if kk in ("date", "who", "map", "what", "thread")})
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "merged.json"
    path.write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n")
    print(f"merged manifest -> {path.relative_to(ROOT)}")
    return path


def gate():
    py = sys.executable
    path = merged()
    if run([py, "tools/validate_schedule.py", "--manifest", str(path)]):
        print("GATE FAILED: merged schedule has gating errors — nothing approved.")
        return 1
    pending = [k for k in (load(PROPOSED)["editions"] if PROPOSED.exists() else {})
               if k not in load(MANIFEST)["editions"]]
    if pending:
        last = max(int(k) for k in pending)
        if run([py, "tools/compile_editions.py", "approve", "--through",
                str(EPOCH + timedelta(days=last))]):
            print("GATE FAILED: approve refused.")
            return 1
    steps = [
        [py, "tools/build_mcq.py", "--offline"],
        [py, "tools/build_mcq.py", "--check", "--offline"],
        [py, "tools/validate_reveal.py"],
        [py, "tools/validate_boards.py"],
        [py, "tools/compile_editions.py", "verify"],
        [py, "tools/validate_schedule.py"],
        [py, "tools/repo_checks.py"],
    ]
    for s in steps:
        if run(s):
            print(f"GATE FAILED at: {' '.join(s[1:])}")
            return 1
    print("GATE PASSED")
    return 0


def tidy_thread():
    from collections import Counter
    sys.path.insert(0, str(ROOT / "tools/engine"))
    from jsonio import save
    if not PROPOSED.exists():
        print("tidy-thread: no proposals")
        return 0
    p = load(PROPOSED)
    E = p["editions"]
    vet = load(VETTING).get("thread", {})
    for bid, v in vet.items():
        n = v.get("place_on")
        if n is not None and str(n) in E:
            print(f"placing held {bid} on edition {n} (was {E[str(n)]['thread'][0]})")
            E[str(n)]["thread"] = [bid]
    aired = {e["thread"][0] for e in load(MANIFEST)["editions"].values() if e.get("thread")}
    c = Counter(e["thread"][0] for e in E.values())
    spare = [b for b, v in vet.items() if v.get("ok") and b not in c and b not in aired]
    for bid in [b for b, k in c.items() if k > 1]:
        for n in sorted((int(k) for k, e in E.items() if e["thread"][0] == bid))[1:]:
            if not spare:
                print(f"tidy-thread: no spare board to replace {bid} on {n} — left as a rerun")
                continue
            E[str(n)]["thread"] = [spare.pop(0)]
            print(f"{bid} ran twice; edition {n} now {E[str(n)]['thread'][0]}")
    save(PROPOSED, p)
    return 0


def bump():
    app = ROOT / "js/app.js"
    sw = ROOT / "sw.js"
    a = app.read_text()
    n = int(re.search(r"const BUILD = 'v(\d+)';", a).group(1)) + 1
    app.write_text(re.sub(r"const BUILD = 'v\d+';", f"const BUILD = 'v{n}';", a, count=1))
    s = sw.read_text()
    sw.write_text(re.sub(r"const VERSION = 'yesternerd-v\d+';",
                         f"const VERSION = 'yesternerd-v{n}';", s, count=1))
    print(f"BUILD/VERSION -> v{n}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status")
    s.add_argument("--json", action="store_true")
    st = sub.add_parser("stage")
    st.add_argument("--days", type=int, default=None)
    sub.add_parser("merged")
    sub.add_parser("gate")
    sub.add_parser("tidy-thread")
    sub.add_parser("bump")
    a = ap.parse_args()
    if a.cmd == "status":
        status(a.json)
        return 0
    if a.cmd == "stage":
        days = a.days if a.days is not None else status()["days_to_fill"]
        if days <= 0:
            print("nothing to stage: the buffer is full")
            return 0
        return run([sys.executable, "tools/compile_editions.py", "propose",
                    "--days", str(days), "--vetted-only"])
    if a.cmd == "merged":
        merged()
        return 0
    if a.cmd == "gate":
        return gate()
    if a.cmd == "tidy-thread":
        return tidy_thread()
    if a.cmd == "bump":
        bump()
        return 0


if __name__ == "__main__":
    sys.exit(main())
