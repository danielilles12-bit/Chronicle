#!/usr/bin/env python3
"""Crossword construction: symmetric pattern generation + backtracking fill.

Vocabulary, best first:
  1. Crossword Nexus collaborative wordlist (scored; cached by wordlist_ext.py)
     — trimmed to the best-scoring words per length.
  2. Fallback: /usr/share/dict/words lowercase entries gated by corpus frequency.
Curated history answers always get top priority. Finished grids are REJECTED
if any answer scores below the quality gate.

  python3 tools/fill_grid.py --size 15 --count 3 --max-seconds 1500 --out tools/out/fulls.json
"""
import argparse
import json
import os
import random
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from history_words import HISTORY_WORDS  # noqa: E402
from wordlist_ext import get_external_words  # noqa: E402

CACHE = os.path.join(os.path.dirname(__file__), "cache")
FREQ_URL = "https://norvig.com/ngrams/count_1w.txt"
HISTORY = set(HISTORY_WORDS)
HISTORY_BONUS = 10 ** 13

BAN = {
    "YEE", "NAA", "SES", "AWS", "ULE", "TOS", "ANS", "EDS", "TES", "YAD",
    "SHI", "SIA", "HIA", "INO", "ATI", "ABO", "NIG", "SEG", "LAZ", "SUZ",
    "DHU", "AHO", "TOL", "ARN", "SAA", "CEP", "ORGIA", "BREBA", "ARTAL",
    "ALYA", "ADDY", "ABUNA", "OFTER", "BOIST", "HILSA", "EUSOL", "IDOSE",
    "ALEA", "KELL", "MERAK", "SAYA", "NOMOS", "RECTA", "UNIES", "LIGNE",
    "AREAL", "MADI", "IYO", "GAU", "SIL", "OAM", "AUM", "WAAR", "NEAS",
    "LOMA", "ELLES", "MEESE", "REDES", "ALWAY", "YAT", "ANAS", "ACYL",
    "CORSE", "RIES", "OMER", "BES",
}

PER_LEN_CAP = {3: 1200, 4: 2500, 5: 4000, 6: 5000, 7: 5000, 8: 4000,
               9: 3000, 10: 2500, 11: 2000, 12: 1500, 13: 1200, 14: 1000, 15: 1000}


def load_freq():
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, "count_1w.txt")
    if not os.path.exists(path):
        print("fetching frequency list...", file=sys.stderr)
        with urllib.request.urlopen(FREQ_URL, timeout=120) as r, open(path, "wb") as f:
            f.write(r.read())
    freq = {}
    with open(path) as f:
        for i, line in enumerate(f):
            w = line.split("\t")[0].strip().upper()
            if w.isalpha():
                freq.setdefault(w, 350_000 - i)
    return freq


def min_freq_for_len(n):
    if n <= 4:
        return 250_000
    if n <= 7:
        return 200_000
    return 100_000


def load_vocab(freq):
    """Returns (words, score_fn, quality_fn, mode)."""
    ext = get_external_words()
    if ext:
        buckets = {}
        for w, s in ext.items():
            if (s >= (60 if len(w) <= 4 else 50) and w.isalpha()
                    and 3 <= len(w) <= 15 and w not in BAN):
                buckets.setdefault(len(w), []).append(w)
        words = set()
        for ln, lst in buckets.items():
            lst.sort(key=lambda w: (ext[w], freq.get(w, 0)), reverse=True)
            words.update(lst[:PER_LEN_CAP.get(ln, 1000)])
        words |= {w for w in HISTORY if 3 <= len(w) <= 15}
        words -= BAN

        def score(w):
            return ((HISTORY_BONUS if w in HISTORY else 0)
                    + ext.get(w, 50) * 1_000_000 + min(freq.get(w, 0), 999_999))

        def quality(w):
            return ext.get(w, 60 if w in HISTORY else 0)

        return words, score, quality, "xwordlist"

    # fallback: lowercase dictionary words gated by web frequency
    with open("/usr/share/dict/words") as f:
        lower = {w.strip().upper() for w in f
                 if w.strip().isalpha() and w.strip().islower()}
    words = set()
    for w in lower:
        if 3 <= len(w) <= 15 and freq.get(w, 0) >= min_freq_for_len(len(w)):
            words.add(w)
    for w in lower:
        p = w + "S"
        if 3 <= len(p) <= 15 and p not in words and freq.get(p, 0) >= 250_000:
            words.add(p)
    words |= {w for w in HISTORY if 3 <= len(w) <= 15}

    def score(w):
        return (HISTORY_BONUS if w in HISTORY else 0) + freq.get(w, 1)

    def quality(w):
        return freq.get(w, 0) // 4000   # roughly maps to a 0-90 scale

    return words - BAN, score, quality, "freq"


# ---------- pattern helpers ----------

def runs_ok(rows):
    n = len(rows)
    cols = ["".join(rows[r][c] for r in range(n)) for c in range(n)]
    for line in list(rows) + cols:
        for part in line.split("#"):
            if 0 < len(part) < 3:
                return False
    return True


def connected_ok(rows):
    n = len(rows)
    whites = {(r, c) for r in range(n) for c in range(n) if rows[r][c] != "#"}
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


def build_slots(rows):
    n = len(rows)
    slots = []
    for r in range(n):
        c = 0
        while c < n:
            if rows[r][c] != "#":
                s = c
                while c < n and rows[r][c] != "#":
                    c += 1
                if c - s >= 3:
                    slots.append({"dir": "across", "r": r, "c": s,
                                  "cells": [(r, x) for x in range(s, c)], "len": c - s})
            else:
                c += 1
    for c in range(n):
        r = 0
        while r < n:
            if rows[r][c] != "#":
                s = r
                while r < n and rows[r][c] != "#":
                    r += 1
                if r - s >= 3:
                    slots.append({"dir": "down", "r": s, "c": c,
                                  "cells": [(x, c) for x in range(s, r)], "len": r - s})
            else:
                r += 1
    return slots


def gen_pattern(n, blocks_target, rng, by_len):
    for _ in range(80):
        pat = [["."] * n for _ in range(n)]
        blocks = 0
        tries = 0
        while blocks < blocks_target and tries < 900:
            tries += 1
            r, c = rng.randrange(n), rng.randrange(n)
            pair = {(r, c), (n - 1 - r, n - 1 - c)}
            if any(pat[a][b] == "#" for a, b in pair):
                continue
            for a, b in pair:
                pat[a][b] = "#"
            rows = ["".join(row) for row in pat]
            if runs_ok(rows) and connected_ok(rows):
                blocks += len(pair)
            else:
                for a, b in pair:
                    pat[a][b] = "."
        rows = ["".join(row) for row in pat]
        if blocks < blocks_target - 3:
            continue
        slots = build_slots(rows)
        if any(len(by_len.get(s["len"], ())) < 150 for s in slots):
            continue
        longs = sum(1 for s in slots if s["len"] >= 8)
        if n >= 11 and not (2 <= longs <= 6):
            continue
        return rows
    return None


# ---------- fill ----------

class Filler:
    def __init__(self, words, score, rng):
        self.rng = rng
        self.score = score
        self.by_len = {}
        self.by_lpc = {}
        for w in words:
            self.by_len.setdefault(len(w), []).append(w)
            for i, ch in enumerate(w):
                self.by_lpc.setdefault((len(w), i, ch), set()).add(w)
        for lst in self.by_len.values():
            lst.sort(key=score, reverse=True)

    def _pool(self, slot, grid):
        fixed = [(i, grid[cell]) for i, cell in enumerate(slot["cells"]) if grid[cell]]
        if not fixed:
            return None
        sets_ = []
        for i, ch in fixed:
            s = self.by_lpc.get((slot["len"], i, ch))
            if not s:
                return set()
            sets_.append(s)
        sets_.sort(key=len)
        inter = sets_[0]
        for s in sets_[1:]:
            inter = inter & s
            if not inter:
                return inter
        return inter

    def count(self, slot, grid, used):
        pool = self._pool(slot, grid)
        if pool is None:
            return len(self.by_len.get(slot["len"], ()))
        if len(pool) < 40 and used:
            return sum(1 for w in pool if w not in used)
        return len(pool)

    def candidates(self, slot, grid, used, limit):
        pool = self._pool(slot, grid)
        if pool is None:
            out = [w for w in self.by_len.get(slot["len"], ()) if w not in used]
            return out[:limit]
        out = sorted((w for w in pool if w not in used), key=self.score, reverse=True)
        return out[:limit]

    def fill(self, rows, seeds, deadline, pinned=None, max_nodes=250_000):
        slots = build_slots(rows)
        cell2slots = {}
        for idx, s in enumerate(slots):
            for cell in s["cells"]:
                cell2slots.setdefault(cell, []).append(idx)
        grid = {cell: None for s in slots for cell in s["cells"]}
        if pinned:
            for cell, ch in pinned.items():
                if cell in grid:
                    grid[cell] = ch
        used = set()
        assigned = {}
        self.nodes = 0

        def slot_word(idx):
            return "".join(grid[c] or "." for c in slots[idx]["cells"])

        # mark slots already complete via pins
        for idx in range(len(slots)):
            w = slot_word(idx)
            if "." not in w:
                assigned[idx] = w
                used.add(w)

        def place(idx, word):
            changed = []
            for cell, ch in zip(slots[idx]["cells"], word):
                if grid[cell] is None:
                    grid[cell] = ch
                    changed.append(cell)
            assigned[idx] = word
            used.add(word)
            return changed

        def unplace(idx, word, changed):
            for cell in changed:
                grid[cell] = None
            del assigned[idx]
            used.discard(word)

        def crossings_alive(changed):
            for cell in changed:
                for j in cell2slots[cell]:
                    if j not in assigned and self.count(slots[j], grid, used) == 0:
                        return False
            return True

        order = sorted(range(len(slots)), key=lambda i: -slots[i]["len"])
        placed = 0
        for idx in order:
            if placed >= 3 or slots[idx]["len"] < 8:
                break
            if idx in assigned:
                continue
            for w in seeds:
                if len(w) == slots[idx]["len"] and w not in used:
                    pool = self._pool(slots[idx], grid)
                    if pool is not None and w not in pool:
                        continue
                    changed = place(idx, w)
                    if crossings_alive(changed):
                        placed += 1
                        break
                    unplace(idx, w, changed)

        def solve():
            self.nodes += 1
            if self.nodes > max_nodes or time.time() > deadline:
                return None
            best_idx, best_count = None, None
            for idx, s in enumerate(slots):
                if idx in assigned:
                    continue
                cnt = self.count(s, grid, used)
                if cnt == 0:
                    return False
                if best_count is None or cnt < best_count:
                    best_idx, best_count = idx, cnt
                    if cnt <= 2:
                        break
            if best_idx is None:
                return True
            cands = self.candidates(slots[best_idx], grid, used, 36)
            head = cands[:10]
            self.rng.shuffle(head)
            for w in head + cands[10:]:
                changed = place(best_idx, w)
                if crossings_alive(changed):
                    res = solve()
                    if res:
                        return True
                    if res is None:
                        unplace(best_idx, w, changed)
                        return None
                unplace(best_idx, w, changed)
            return False

        if not solve():
            return None
        n = len(rows)
        return ["".join(grid.get((r, c)) or "#" for c in range(n)) for r in range(n)]


def grid_answers(rows):
    return [(s["dir"], s["r"], s["c"],
             "".join(rows[r][c] for r, c in s["cells"])) for s in build_slots(rows)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, required=True)
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--max-seconds", type=int, default=300)
    ap.add_argument("--blocks", type=int, default=None)
    ap.add_argument("--quality", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    freq = load_freq()
    words, score, quality, mode = load_vocab(freq)
    print("vocab size:", len(words), "mode:", mode, file=sys.stderr)
    filler = Filler(words, score, rng)

    n = args.size
    blocks = args.blocks if args.blocks is not None else {15: 40, 11: 26, 7: 10, 5: 4}.get(n, max(4, n * n // 6))
    if args.quality is not None:
        gate = args.quality
    elif mode == "xwordlist":
        gate = 52 if n >= 11 else 60
    else:
        gate = 40 if n >= 11 else 58

    results = []
    t_end = time.time() + args.max_seconds
    attempt = 0
    while len(results) < args.count and time.time() < t_end:
        attempt += 1
        rows = gen_pattern(n, blocks, rng, filler.by_len)
        if rows is None:
            print("attempt %d: no pattern" % attempt, file=sys.stderr)
            continue
        seeds = [w for w in HISTORY_WORDS if len(w) >= 8]
        rng.shuffle(seeds)
        per_try = 45 if n >= 11 else 8
        filled = filler.fill(rows, seeds, min(time.time() + per_try, t_end))
        if not filled:
            print("attempt %d: fail (nodes=%d)" % (attempt, filler.nodes), file=sys.stderr)
            continue
        answers = grid_answers(filled)
        bad = [a[3] for a in answers if a[3] not in HISTORY and quality(a[3]) < gate]
        if bad:
            print("attempt %d: rejected (junk: %s)" % (attempt, bad[:6]), file=sys.stderr)
            continue
        results.append({
            "size": n,
            "grid": filled,
            "answers": [{"dir": d, "r": r, "c": c, "answer": a, "q": quality(a)}
                        for d, r, c, a in answers],
        })
        print("attempt %d: SUCCESS (%d/%d)" % (attempt, len(results), args.count), file=sys.stderr)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(results, f, indent=1)
    print("wrote %d grids -> %s" % (len(results), args.out))
    sys.exit(0 if len(results) >= args.count else 2)


if __name__ == "__main__":
    main()
