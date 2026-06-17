#!/usr/bin/env python3
"""Run the full verification suite: puzzle validator + all Playwright tests."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")

STEPS = [
    ("validator", os.path.join(ROOT, "tools", "validate_puzzles.py")),
    ("crosswords", os.path.join(HERE, "test_crosswords.py")),
    ("map game", os.path.join(HERE, "test_mapgame.py")),
    ("zoom in", os.path.join(HERE, "test_reveal.py")),
    ("pwa/offline", os.path.join(HERE, "test_pwa.py")),
    ("screenshots", os.path.join(HERE, "screenshots.py")),
]


def main():
    results = []
    for name, path in STEPS:
        print("\n===== %s =====" % name)
        rc = subprocess.run([sys.executable, "-u", path]).returncode
        results.append((name, rc))
        if rc != 0:
            print("STEP FAILED:", name)
    print("\n===== SUMMARY =====")
    bad = 0
    for name, rc in results:
        print("  %-12s %s" % (name, "PASS" if rc == 0 else "FAIL(%d)" % rc))
        bad += rc != 0
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
