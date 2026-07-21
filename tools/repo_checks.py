#!/usr/bin/env python3
"""Repo-level CI gates (P4.2). Fast, offline, no browser:

1. Version lock — BUILD in js/app.js must equal the VERSION suffix in sw.js.
   These two ship together on every deploy; a mismatch means installed
   phones would run a mislabelled (or never-updating) build.

2. Leak guard — GitHub Pages serves this WHOLE repo, so no tracked file may
   carry unaired content beyond the manifest horizon. data/editions.json is
   the sanctioned horizon (approved future editions live there by design);
   the compiler's working files are not:
     - data/editions.proposed.json  (drafts awaiting sign-off)
     - tools/out/                   (review sheets print unaired answers)

Exits non-zero with a plain explanation on any failure.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_TRACKED = [
    ("data/editions.proposed.json", "proposed (unaired) editions"),
    ("tools/out/", "compiler output — review sheets hold unaired answers"),
]

errors = []


def check_version_lock():
    app = (ROOT / "js/app.js").read_text(encoding="utf-8")
    sw = (ROOT / "sw.js").read_text(encoding="utf-8")
    mb = re.search(r"const BUILD = '([^']+)'", app)
    mv = re.search(r"const VERSION = '([^']+)'", sw)
    if not mb or not mv:
        errors.append("could not find BUILD in js/app.js or VERSION in sw.js")
        return
    build, version = mb.group(1), mv.group(1)
    suffix = version.rsplit("-", 1)[-1]
    if suffix != build:
        errors.append(
            f"version mismatch: js/app.js BUILD is '{build}' but sw.js VERSION "
            f"is '{version}' (suffix '{suffix}') — bump them together")
    else:
        print(f"version lock OK: {build} == {version}")


def check_leaks():
    files = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
        check=True).stdout.splitlines()
    for path, why in FORBIDDEN_TRACKED:
        hits = [f for f in files
                if f == path or (path.endswith("/") and f.startswith(path))]
        for h in hits:
            errors.append(f"leak: '{h}' is tracked (deployed by Pages) — {why}")
    review = [f for f in files if re.search(r"(^|/)review-\d{4}-\d{2}-\d{2}\.html$", f)]
    for h in review:
        errors.append(f"leak: review sheet '{h}' is tracked — it prints unaired answers")
    if not errors:
        print("leak guard OK: no compiler working files tracked")


def main():
    check_version_lock()
    check_leaks()
    if errors:
        for e in errors:
            print("ERROR " + e, file=sys.stderr)
        return 1
    print("repo checks: all green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
