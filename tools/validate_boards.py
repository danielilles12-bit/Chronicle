#!/usr/bin/env python3
"""Structural validator for data/connections.json and data/chrono.json.

Run from repo root: python3 tools/validate_boards.py
Exits non-zero on any ERROR. WARNs don't fail the build but should be read.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trust_schema import validate_trust_fields  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
COLOURS = {"yellow", "green", "blue", "purple"}
DIFFICULTIES = {"easy", "medium", "hard"}

errors = []
warns = []


def err(msg):
    errors.append(msg)


def warn(msg):
    warns.append(msg)


def check_connections(boards):
    ids = [b.get("id") for b in boards]
    for dup, n in Counter(ids).items():
        if n > 1:
            err(f"connections: duplicate id {dup}")
    titles = [b.get("title", "").strip().lower() for b in boards]
    for dup, n in Counter(titles).items():
        if n > 1:
            err(f"connections: duplicate title '{dup}'")

    label_seen = {}
    item_boards = {}
    for b in boards:
        bid = b.get("id", "?")
        if not re.fullmatch(r"conn-\d{3}", bid):
            err(f"connections {bid}: bad id format")
        if b.get("difficulty") not in DIFFICULTIES:
            err(f"connections {bid}: bad difficulty {b.get('difficulty')!r}")
        groups = b.get("groups", [])
        if len(groups) != 4:
            err(f"connections {bid}: {len(groups)} groups (want 4)")
            continue
        if {g.get("colour") for g in groups} != COLOURS:
            err(f"connections {bid}: colours must be exactly {sorted(COLOURS)}")
        all_items = []
        for g in groups:
            label = (g.get("label") or "").strip()
            if not label:
                err(f"connections {bid}: empty group label")
            key = label.lower()
            if key in label_seen and label_seen[key] != bid:
                warn(f"connections {bid}: label '{label}' also in {label_seen[key]}")
            label_seen[key] = bid
            items = g.get("items", [])
            if len(items) != 4:
                err(f"connections {bid} [{label}]: {len(items)} items (want 4)")
            for it in items:
                if not isinstance(it, str) or not it.strip():
                    err(f"connections {bid} [{label}]: empty/non-string item")
                all_items.append(it.strip().lower())
                item_boards.setdefault(it.strip().lower(), set()).add(bid)
            # Self-labeling groups (Daniel, 30 Jul 2026): tiles that repeat a
            # label word ("First Crusade" under "Numbered medieval Crusades",
            # "Ping-Pong Diplomacy" under a diplomacy label) sort themselves —
            # no history needed. NYT boards never do this; flag it.
            stop = {"the", "of", "a", "an", "in", "on", "and", "that", "with",
                    "for", "also", "once", "was", "were", "named", "known",
                    "famous", "kinds", "types", "ways", "things", "from"}
            label_toks = {t.rstrip("s") for t in re.findall(r"[a-z]+", label.lower())
                          if len(t) > 3 and t not in stop}
            selfing = sum(
                1 for it in items if isinstance(it, str) and label_toks
                & {t.rstrip("s") for t in re.findall(r"[a-z]+", it.lower())})
            if selfing >= 3:
                warn(f"connections {bid} [{label}]: {selfing}/4 tiles repeat a "
                     f"label word — self-labeling group, sortable without knowledge")
            shared = Counter(t.rstrip("s") for it in items if isinstance(it, str)
                             for t in {w for w in re.findall(r"[a-z]+", it.lower())
                                       if len(w) > 3 and w not in stop})
            for tok, cnt in shared.items():
                if cnt == 4:
                    warn(f"connections {bid} [{label}]: all four tiles share "
                         f"'{tok}' — self-sorting surface")
        for dup, n in Counter(all_items).items():
            if n > 1:
                err(f"connections {bid}: item '{dup}' appears in more than one group")
        validate_trust_fields(b, f"connections {bid}", err, warn, has_images=False)
    for item, where in item_boards.items():
        if len(where) > 2:
            warn(f"connections: item '{item}' used in {len(where)} boards: {sorted(where)}")


def check_chrono(puzzles):
    ids = [p.get("id") for p in puzzles]
    for dup, n in Counter(ids).items():
        if n > 1:
            err(f"chrono: duplicate id {dup}")
    titles = [p.get("title", "").strip().lower() for p in puzzles]
    for dup, n in Counter(titles).items():
        if n > 1:
            err(f"chrono: duplicate title '{dup}'")
    for p in puzzles:
        pid = p.get("id", "?")
        if not re.fullmatch(r"chrono-\d{3}", pid):
            err(f"chrono {pid}: bad id format")
        if p.get("difficulty") not in DIFFICULTIES:
            err(f"chrono {pid}: bad difficulty {p.get('difficulty')!r}")
        items = p.get("items", [])
        if len(items) != 5:
            err(f"chrono {pid}: {len(items)} items (want 5)")
        keys = []
        for it in items:
            if not (it.get("label") or "").strip():
                err(f"chrono {pid}: empty item label")
            if not (it.get("hint") or "").strip():
                err(f"chrono {pid}: empty hint on '{it.get('label')}'")
            y = it.get("year")
            if not isinstance(y, int) or not (-4000 <= y <= 2026):
                err(f"chrono {pid}: implausible year {y!r} on '{it.get('label')}'")
            m, d = it.get("month", 0), it.get("day", 0)
            if m and not (1 <= m <= 12):
                err(f"chrono {pid}: bad month {m!r} on '{it.get('label')}'")
            if d and not (1 <= d <= 31):
                err(f"chrono {pid}: bad day {d!r} on '{it.get('label')}'")
            keys.append((y, m or 0, d or 0))
        # The engine sorts by (year, month, day) and falls back to array order
        # on exact ties, so ties must be resolvable and arrays chronological.
        for key, n in Counter(keys).items():
            if n > 1:
                y, m, d = key
                if m == 0:
                    err(f"chrono {pid}: items share year {y} — add 'month' to order them")
                elif d == 0:
                    err(f"chrono {pid}: items share {y}-{m:02d} — add 'day' to order them")
                else:
                    warn(f"chrono {pid}: exact date tie {key} — array order decides; "
                         f"make sure hints disambiguate")


def main():
    conn = json.loads((ROOT / "data/connections.json").read_text())
    check_connections(conn)
    # chrono was removed from the app in v97; validate its data only if present
    chrono_path = ROOT / "data/chrono.json"
    chrono = json.loads(chrono_path.read_text()) if chrono_path.exists() else []
    if chrono:
        check_chrono(chrono)
    for w in warns:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"{len(conn)} connections boards, {len(chrono)} chrono puzzles — "
          f"{len(errors)} errors, {len(warns)} warnings")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
