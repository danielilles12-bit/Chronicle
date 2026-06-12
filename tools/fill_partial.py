#!/usr/bin/env python3
"""Complete a partially specified grid: '#' block, '.' empty, letters pinned.

  python3 tools/fill_partial.py --rows '##ERA,TUDOR,.....,.....,RA.##' [--tries 40]

Prints completed grids (best first by total word score)."""
import argparse
import random
import sys
import time
import os

sys.path.insert(0, os.path.dirname(__file__))
from fill_grid import load_freq, load_vocab, Filler, build_slots, grid_answers  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True, help="comma-separated rows")
    ap.add_argument("--tries", type=int, default=30)
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    rows = [r.strip().upper() for r in args.rows.split(",")]
    n = len(rows)
    assert all(len(r) == n for r in rows), "grid must be square"
    pattern = ["".join("#" if ch == "#" else "." for ch in row) for row in rows]

    rng = random.Random(args.seed)
    freq = load_freq()
    words, score, quality, mode = load_vocab(freq)
    filler = Filler(words, score, rng)

    pinned = {}
    for r in range(n):
        for c in range(n):
            if rows[r][c] not in "#.":
                pinned[(r, c)] = rows[r][c]

    seen = set()
    results = []
    deadline = time.time() + args.seconds
    for _ in range(args.tries):
        if time.time() > deadline:
            break
        filled = filler.fill(pattern, [], min(time.time() + 8, deadline), pinned=pinned)
        if filled and tuple(filled) not in seen:
            seen.add(tuple(filled))
            total = sum(quality(a[3]) for a in grid_answers(filled))
            results.append((total, filled))

    results.sort(reverse=True)
    for total, g in results[:6]:
        answers = grid_answers(g)
        print("---- total quality %d" % total)
        for row in g:
            print("   ", " ".join(row))
        worst = sorted(answers, key=lambda a: quality(a[3]))[:6]
        print("    weakest:", ", ".join("%s(%d)" % (a[3], quality(a[3])) for a in worst))
    if not results:
        print("NO FILL FOUND")


if __name__ == "__main__":
    main()
