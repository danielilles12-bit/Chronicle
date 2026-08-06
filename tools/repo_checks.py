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

3. Deny-list guard — the host serves the whole repo either way, so the
   internal files that DO live here (plans, tools, tests, review sheets) are
   taken off the public site by the _redirects file instead. Every address in
   DENY_PATHS below must still have its rule.

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

# The single source of truth for what the public site must NOT serve. Every
# entry needs a matching line in the repo-root _redirects file; that file's
# header explains the mechanism, and tools/check_live.py proves it works
# against the deployed site.
DENY_PATHS = [
    "/audit/*",
    "/tools/*",
    "/tests/*",
    "/attic/*",
    "/design-reviews/*",
    "/CRITIC_REPORT.md",
    "/HOUSE_RULES.md",
    "/LAUNCH_CHECKLIST.md",
    "/PLAN.md",
    "/README.md",
    "/connections_audit.md",
    "/content-inventory.md",
    "/.github/*",
    "/.claude/*",
]

# Where a denied address is sent. Its whole job is to not exist, so that the
# visitor's browser is answered with a real "not found" rather than a page.
DENY_TARGET = "/nowhere"

# Pages accepts only these in a rule's third column.
REDIRECT_STATUSES = {"301", "302", "303", "307", "308"}

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


def tracked_files():
    return subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
        check=True).stdout.splitlines()


def check_leaks():
    files = tracked_files()
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


def read_redirect_rules():
    """_redirects as {source: [target, status]}, comments and blanks dropped."""
    rules = {}
    text = (ROOT / "_redirects").read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            rules[parts[0]] = parts[1:]
    return rules


def check_deny_rules():
    before = len(errors)
    if not (ROOT / "_redirects").exists():
        errors.append(
            "the _redirects file is missing — without it the live site hands "
            "out this repo's internal files (plans, tools, tests, review "
            "sheets) to anyone who asks for them by name")
        return
    rules = read_redirect_rules()
    for path in DENY_PATHS:
        rule = rules.get(path)
        if rule is None:
            errors.append(
                "_redirects has no rule for '%s', so the live site would "
                "serve it. Add this line:  %s  %s  302"
                % (path, path, DENY_TARGET))
        elif rule[0] != DENY_TARGET:
            errors.append(
                "_redirects sends '%s' to '%s'. It must go to '%s' — an "
                "address with nothing behind it, which is what makes the "
                "visitor's browser get a real 'not found'"
                % (path, rule[0], DENY_TARGET))
        elif len(rule) < 2 or rule[1] not in REDIRECT_STATUSES:
            errors.append(
                "_redirects gives '%s' the status '%s'. Cloudflare Pages "
                "accepts only %s here, and rejects anything else — use 302"
                % (path, rule[1] if len(rule) > 1 else "(none)",
                   ", ".join(sorted(REDIRECT_STATUSES))))
    # If anything ever answers the target address, every denied path quietly
    # starts working again — with no failing test to say so.
    if DENY_TARGET in rules:
        errors.append(
            "_redirects has a rule for '%s' itself — that address must stay "
            "empty, or the whole deny list stops meaning anything" % DENY_TARGET)
    stem = DENY_TARGET.lstrip("/")
    files = tracked_files()
    squatters = [f for f in files
                 if f in (stem, stem + ".html", stem + "/index.html")]
    for s in squatters:
        errors.append(
            "'%s' is tracked, so '%s' would answer with a page instead of a "
            "'not found' — and every denied path would fall through to it"
            % (s, DENY_TARGET))
    if len(errors) == before:
        print("deny list OK: all %d internal paths have a _redirects rule"
              % len(DENY_PATHS))


def main():
    check_version_lock()
    check_leaks()
    check_deny_rules()
    if errors:
        for e in errors:
            print("ERROR " + e, file=sys.stderr)
        return 1
    print("repo checks: all green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
