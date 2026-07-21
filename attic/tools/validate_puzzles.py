#!/usr/bin/env python3
"""Crossword validator. Every shipped puzzle must pass every check.

Checks per puzzle:
  - grid is size x size, chars are A-Z or '#'
  - every horizontal/vertical run of white cells is >= 3 long
    (this also guarantees full interlock: every cell is in an across AND a down answer)
  - white cells form a single connected component
  - 180-degree rotational symmetry for grids of size >= 11
  - derived numbering/answers match the clue list exactly (positions, numbers, text)
  - no duplicate answers within a puzzle
  - every clue is non-empty and does not contain its own answer
Global: unique puzzle ids. Exits non-zero on any failure.
"""
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
PUZZLES = os.path.join(ROOT, "data", "puzzles.json")


def runs(grid, size):
    """Yield (direction, row, col, word) for every maximal white run."""
    for r in range(size):
        c = 0
        while c < size:
            if grid[r][c] != "#":
                start = c
                while c < size and grid[r][c] != "#":
                    c += 1
                yield ("across", r, start, grid[r][start:c])
            else:
                c += 1
    for c in range(size):
        r = 0
        while r < size:
            if grid[r][c] != "#":
                start = r
                while r < size and grid[r][c] != "#":
                    r += 1
                yield ("down", start, c, "".join(grid[i][c] for i in range(start, r)))
            else:
                r += 1


def numbering(grid, size):
    """Standard crossword numbering -> {(dir, num): (row, col, answer)}."""
    out = {}
    num = 0
    for r in range(size):
        for c in range(size):
            if grid[r][c] == "#":
                continue
            starts_across = (c == 0 or grid[r][c - 1] == "#") and c + 1 < size and grid[r][c + 1] != "#"
            starts_down = (r == 0 or grid[r - 1][c] == "#") and r + 1 < size and grid[r + 1][c] != "#"
            if starts_across or starts_down:
                num += 1
                if starts_across:
                    cc = c
                    while cc < size and grid[r][cc] != "#":
                        cc += 1
                    out[("across", num)] = (r, c, grid[r][c:cc])
                if starts_down:
                    rr = r
                    while rr < size and grid[rr][c] != "#":
                        rr += 1
                    out[("down", num)] = (r, c, "".join(grid[i][c] for i in range(r, rr)))
    return out


def connected(grid, size):
    whites = {(r, c) for r in range(size) for c in range(size) if grid[r][c] != "#"}
    if not whites:
        return False
    stack = [next(iter(whites))]
    seen = set(stack)
    while stack:
        r, c = stack.pop()
        for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if (nr, nc) in whites and (nr, nc) not in seen:
                seen.add((nr, nc))
                stack.append((nr, nc))
    return seen == whites


def check_puzzle(p, errors):
    pid = p.get("id", "<no id>")

    def err(msg):
        errors.append("[%s] %s" % (pid, msg))

    size = p.get("size")
    grid = p.get("grid", [])
    if not isinstance(size, int) or len(grid) != size or any(len(row) != size for row in grid):
        err("grid is not %s x %s" % (size, size))
        return
    if any(not re.fullmatch(r"[A-Z#]+", row) for row in grid):
        err("grid contains characters other than A-Z and #")
        return

    for d, r, c, word in runs(grid, size):
        if len(word) < 3:
            err("run of length %d (<3) at %s (%d,%d): %r" % (len(word), d, r, c, word))

    if not connected(grid, size):
        err("white cells are not a single connected region")

    if size >= 11:
        for r in range(size):
            for c in range(size):
                a, b = grid[r][c] == "#", grid[size - 1 - r][size - 1 - c] == "#"
                if a != b:
                    err("not rotationally symmetric at (%d,%d)" % (r, c))

    derived = numbering(grid, size)
    listed = {}
    for d in ("across", "down"):
        for cl in p.get("clues", {}).get(d, []):
            key = (d, cl.get("num"))
            if key in listed:
                err("duplicate clue entry %s %s" % key)
            listed[key] = cl
    if set(listed) != set(derived):
        missing = sorted(set(derived) - set(listed))
        extra = sorted(set(listed) - set(derived))
        if missing:
            err("clues missing for %s" % missing)
        if extra:
            err("clues that match no slot: %s" % extra)
    for key in set(listed) & set(derived):
        r, c, ans = derived[key]
        cl = listed[key]
        if cl.get("row") != r or cl.get("col") != c:
            err("%s %s position %s,%s != derived %s,%s" % (key[0], key[1], cl.get("row"), cl.get("col"), r, c))
        if cl.get("answer") != ans:
            err("%s %s answer %r != grid letters %r" % (key[0], key[1], cl.get("answer"), ans))
        text = (cl.get("clue") or "").strip()
        if not text:
            err("%s %s has an empty clue" % key)
        elif ans and ans.lower() in re.sub(r"[^a-z]", "", text.lower()):
            err("%s %s clue contains its own answer (%s)" % (key[0], key[1], ans))

    answers = [v[2] for v in derived.values()]
    dupes = {a for a in answers if answers.count(a) > 1}
    if dupes:
        err("duplicate answers in puzzle: %s" % sorted(dupes))


def main():
    with open(PUZZLES) as f:
        puzzles = json.load(f)
    errors = []
    ids = [p.get("id") for p in puzzles]
    if len(ids) != len(set(ids)):
        errors.append("duplicate puzzle ids")
    for p in puzzles:
        check_puzzle(p, errors)
    counts = {}
    for p in puzzles:
        counts[p.get("format")] = counts.get(p.get("format"), 0) + 1
    print("puzzles:", counts)
    if errors:
        print("\nFAILURES (%d):" % len(errors))
        for e in errors:
            print(" -", e)
        sys.exit(1)
    print("ALL PUZZLES VALID")


if __name__ == "__main__":
    main()
