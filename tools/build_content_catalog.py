#!/usr/bin/env python3
"""Content catalogue — every pool item in one scannable markdown file.

Made for Daniel's launch-window audit (30 Jul 2026): while reviewing the
HTML sheet he wants to say "replace him with X", so this lists everything
we HAVE, per game and tier, best-known first, with where (or whether) each
item is staged in the launch window. Pre-launch airings are invisible per
the launch blindfold — anything not staged from edition 42 on is FREE.

Output goes to tools/out/ (gitignored, leak-guarded): the staging column
is unaired-answer knowledge.

Run from repo root:  python3 tools/build_content_catalog.py
"""
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compile_editions as C  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tools/out/content-catalog.md"
GAME_LABEL = {"who": "Face Value", "map": "Lifeline",
              "what": "Relic", "thread": "Thread"}


def main():
    pools = C.load_pools()
    man = C.load_manifest()["editions"]
    cfg = C.load_config()
    launch = cfg.get("launch_edition", 0)
    fame_idx, tag_idx = C.load_signal_indices()
    try:
        sal = {(r["game"], r["id"]): r.get("salience")
               for r in json.loads((ROOT / "tools/fame/salience.json")
                                   .read_text(encoding="utf-8"))["items"]}
    except Exception:
        sal = {}

    # (game, id) -> "day N (Mon 10 Aug)" for editions >= launch
    staged = {}
    for k, e in man.items():
        n = int(k)
        if n < launch:
            continue
        d = datetime.date.fromisoformat(e["date"])
        label = f"day {n - launch + 1} · {d.strftime('%a %-d %b')}"
        for g in C.GAMES:
            for i in e[g]:
                staged.setdefault((g, i), label)

    def score(g, it):
        return (C.item_signal(g, it, fame_idx, tag_idx).get("fame"),
                sal.get((g, it["id"])))

    def fmt(v):
        return "–" if v is None else f"{v:.0f}"

    today = datetime.date.today().isoformat()
    L = [f"# Dead Famous — content catalogue ({today})", ""]
    L += ["Everything in the pools, best-known first. **Bold day** = staged "
          "in the launch window (day 1 = 10 Aug). Blank = FREE to schedule. "
          "`reserved` = pulled from rotation (known-face audit) — ask before "
          "using. Fame/salience are 0–100.", ""]

    for g in ("who", "map", "what"):
        items = pools[g]
        L += [f"## {GAME_LABEL[g]} — {len(items)} items", ""]
        for tier in ("easy", "medium", "hard"):
            rows = [x for x in items if x.get("difficulty") == tier]
            rows.sort(key=lambda x: -(score(g, x)[0] or -1))
            L += [f"### {tier.capitalize()} ({len(rows)})", ""]
            if g == "map":
                L += ["| Name | fame | sal | journey | where |",
                      "|---|---|---|---|---|"]
            elif g == "what":
                L += ["| Name | kind | fame | sal | where |",
                      "|---|---|---|---|---|"]
            else:
                L += ["| Name | fame | sal | era | where |",
                      "|---|---|---|---|---|"]
            for x in rows:
                f, s = score(g, x)
                where = staged.get((g, x["id"]), "")
                if where:
                    where = f"**{where}**"
                if x.get("reserve"):
                    where = (where + " `reserved`").strip()
                name = f"{x['name']} `{x['id']}`"
                if g == "map":
                    j = (f"{x['birth']['year']} {x['birth']['place'].split(',')[0]} "
                         f"→ {x['death']['year']} {x['death']['place'].split(',')[0]}")
                    L.append(f"| {name} | {fmt(f)} | {fmt(s)} | {j} | {where} |")
                elif g == "what":
                    kind = C.item_signal(g, x, fame_idx, tag_idx).get("kind") or "–"
                    L.append(f"| {name} | {kind} | {fmt(f)} | {fmt(s)} | {where} |")
                else:
                    era = C.item_signal(g, x, fame_idx, tag_idx).get("era") or "–"
                    L.append(f"| {name} | {fmt(f)} | {fmt(s)} | {era} | {where} |")
            L.append("")

    boards = pools["thread"]
    L += [f"## Thread — {len(boards)} boards", ""]
    for tier in ("easy", "medium", "hard"):
        rows = [b for b in boards if b.get("difficulty") == tier]
        rows.sort(key=lambda b: (staged.get(("thread", b["id"]), "zzz"), b["id"]))
        L += [f"### {tier.capitalize()} ({len(rows)})", "",
              "| Board | categories | where |", "|---|---|---|"]
        for b in rows:
            labels = " / ".join(gr.get("label", "") for gr in b.get("groups", []))
            where = staged.get(("thread", b["id"]), "")
            if where:
                where = f"**{where}**"
            dark = " ☠" if C.is_dark_tone(cfg, "thread", b["id"]) else ""
            if b.get("reserve"):
                where = (where + " `reserved`").strip()
            L.append(f"| {b.get('title', b['id'])} `{b['id']}`{dark} | {labels} | {where} |")
        L.append("")

    L += ["---", "", "☠ = dark-tone tagged (max one dark subject per issue). "
          "Regenerate with `python3 tools/build_content_catalog.py`.", ""]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")
    n_items = sum(len(pools[g]) for g in C.GAMES)
    print(f"catalogue: {n_items} items -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
