#!/usr/bin/env python3
"""The full verification suite (P4.1): data validators first, then the
Playwright suite against a local static server. This is what CI runs and
what the end-of-session ritual means by "run the tests".

  python3 tests/run_all.py            # everything
  python3 tests/run_all.py --fast     # validators only (no browser)
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))

VALIDATORS = [
    ("reveal data", [os.path.join(ROOT, "tools", "validate_reveal.py")]),
    ("board data", [os.path.join(ROOT, "tools", "validate_boards.py")]),
    ("image rights", [os.path.join(ROOT, "tools", "audit_rights.py")]),  # offline mode
    ("manifest verify", [os.path.join(ROOT, "tools", "compile_editions.py"), "verify"]),
    ("schedule repetition", [os.path.join(ROOT, "tools", "validate_schedule.py")]),
    ("mcq distractors", [os.path.join(ROOT, "tools", "build_mcq.py"), "--check"]),
]

BROWSER = [
    ("answer matching", [os.path.join(HERE, "match_harness.py")]),
    ("smoke: core", [os.path.join(HERE, "test_smoke_core.py")]),
    ("home: stranger", [os.path.join(HERE, "test_stranger_home.py")]),
    ("smoke: daily flow", [os.path.join(HERE, "test_daily_flow.py")]),
    ("archive window", [os.path.join(HERE, "test_archive_window.py")]),
    ("smoke: resilience", [os.path.join(HERE, "test_resilience.py")]),
    ("nav: no dead ends", [os.path.join(HERE, "test_no_dead_ends.py")]),
    ("install flow", [os.path.join(HERE, "test_install.py")]),
    ("letters/feedback", [os.path.join(HERE, "test_feedback.py")]),
    ("streaks + storage", [os.path.join(HERE, "test_streaks.py")]),
    ("carry: move record", [os.path.join(HERE, "test_carry.py")]),
]


def main():
    steps = VALIDATORS + ([] if "--fast" in sys.argv[1:] else BROWSER)
    results = []
    for name, cmd in steps:
        print("\n===== %s =====" % name, flush=True)
        rc = subprocess.run([sys.executable, "-u"] + cmd, cwd=ROOT).returncode
        results.append((name, rc))
        if rc != 0:
            print("STEP FAILED:", name)
    print("\n===== SUMMARY =====")
    bad = 0
    for name, rc in results:
        print("  %-18s %s" % (name, "PASS" if rc == 0 else "FAIL(%d)" % rc))
        bad += rc != 0
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
