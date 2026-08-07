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

4. Brand-mark guard — the house mark is the bespectacled Antinous (Daniel,
   4 Aug 2026). The retired pink-sunglasses Michelangelo's-David crept back
   twice by being left behind in a file nobody was reading: once in the sw
   precache list, once as the icon generator's source art. Both fed the
   LAUNCH imagery — home-screen icon, Android PWA splash, iOS startup image —
   so a leftover David shows up while the app is opening, which is the worst
   possible place for a retired logo. This gate fails the build if a David
   brand asset is tracked again, or if any runtime file names one.

5. File-size guard — Cloudflare Pages refuses to publish ANY single file over
   25 MiB, and it fails the whole deploy, not just that file. The "Sharper
   pictures" commit (e4748ec3, 7 Aug 2026) re-sourced 97 photographs at full
   museum resolution and committed three of 59, 59 and 29 MB; every deploy
   failed from then on, and the live site went on quietly serving an older
   build while the repo looked perfectly healthy. Nothing in CI noticed,
   because nothing was measuring file size. This gate does.

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

# ---------- brand-mark guard ----------
# Directories that hold BRAND art only. Content photographs live in
# assets/img/ and are deliberately excluded: David Hume, Jacques-Louis David
# and Michelangelo's David are all legitimate puzzle subjects, and sources.html
# credits them by name. This gate is about the logo, not about history.
BRAND_DIRS = ("assets/brand/", "assets/intro/", "assets/splash/", "icons/")

# Retired art, by exact path. assets/icon.svg was the icon generator's source:
# a hand-drawn bust in pink sunglasses that never reached the site, but that
# tools/make_icons.py would have rendered straight onto the home-screen icon
# and the Android launch screen. Named here so it cannot quietly come back.
RETIRED_ASSETS = [
    ("assets/icon.svg", "the pink-sunglasses David the icon generator drew from — "
                        "icons/icon-512.png is the master now"),
]

# The runtime app: what a browser actually downloads and runs. A reference to
# a David brand asset in any of these is what puts the old mark on screen.
RUNTIME_FILES = ("index.html", "sw.js", "manifest.webmanifest",
                 "css/style.css", "css/brand-tokens.css", "css/pages.css")
RUNTIME_DIRS = ("js/",)

# The launch/loading imagery, and what must be behind it. Every one of these
# files is something a player sees while the app is opening.
LAUNCH_ASSETS = [
    "icons/icon-512.png",        # Android/Chrome PWA splash + manifest
    "icons/icon-192.png",        # manifest
    "icons/apple-touch-icon.png",  # iOS home screen
    "icons/favicon.png",         # browser tab
    "assets/brand/antinous-sticker.png",  # the masthead mark, precached
]

# ---------- file-size guard ----------
# What the host actually refuses. Cloudflare Pages rejects any single file
# larger than this, and the rejection fails the entire deployment.
HOST_MAX_BYTES = 25 * 1024 * 1024        # 25 MiB
# Where we fail instead: comfortably below the host's limit, so a file that
# creeps upward is caught here, on a branch, rather than by a red deploy after
# a merge. A picture has no business being anywhere near either number —
# the biggest thing the site legitimately serves is a few hundred KB.
SAFE_MAX_BYTES = 20 * 1024 * 1024        # 20 MiB

errors = []


def check_file_sizes():
    """No tracked file may approach the host's per-file publishing limit."""
    before = len(errors)
    oversized = []
    for f in tracked_files():
        p = ROOT / f
        if not p.is_file():
            continue          # tracked but deleted in the working tree
        n = p.stat().st_size
        if n > SAFE_MAX_BYTES:
            oversized.append((n, f))
    for n, f in sorted(oversized, reverse=True):
        errors.append(
            "'%s' is %.1f MB. Cloudflare Pages refuses to publish any file "
            "over %d MB and fails the WHOLE deploy when it finds one, so this "
            "would stop every update reaching phones — the site would keep "
            "serving the last build that worked. Shrink it before merging; "
            "for a picture in assets/img/ that is "
            "'python3 tools/build_image_variants.py --cap-originals'."
            % (f, n / 1048576, HOST_MAX_BYTES // 1048576))
    if len(errors) == before:
        print("file size OK: nothing tracked is over %d MB"
              % (SAFE_MAX_BYTES // 1048576))


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
    # Counts only ITS OWN failures: this used to test the shared error list,
    # so any earlier check failing would silently suppress this one's "OK".
    before = len(errors)
    files = tracked_files()
    for path, why in FORBIDDEN_TRACKED:
        hits = [f for f in files
                if f == path or (path.endswith("/") and f.startswith(path))]
        for h in hits:
            errors.append(f"leak: '{h}' is tracked (deployed by Pages) — {why}")
    review = [f for f in files if re.search(r"(^|/)review-\d{4}-\d{2}-\d{2}\.html$", f)]
    for h in review:
        errors.append(f"leak: review sheet '{h}' is tracked — it prints unaired answers")
    if len(errors) == before:
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


def check_brand_mark():
    """No retired-David brand art tracked, and none named by the runtime."""
    before = len(errors)
    files = tracked_files()

    # 1. No David brand asset back on disk, under any of the brand paths.
    for f in files:
        if not f.startswith(BRAND_DIRS):
            continue
        if "david" in f.rsplit("/", 1)[-1].lower():
            errors.append(
                "brand art '%s' is tracked. The house mark is the bespectacled "
                "Antinous (Daniel, 4 Aug 2026); the pink-sunglasses David is "
                "retired. Brand art lives under %s — content photographs of "
                "people called David belong in assets/img/."
                % (f, ", ".join(BRAND_DIRS)))

    # 2. Retired art stays retired, by exact path.
    for path, why in RETIRED_ASSETS:
        if path in files:
            errors.append("'%s' is tracked again — %s" % (path, why))

    # 3. No runtime file may point at one.
    targets = [f for f in RUNTIME_FILES if (ROOT / f).exists()]
    targets += [f for f in files if f.startswith(RUNTIME_DIRS) and f.endswith(".js")]
    ref = re.compile(r"(?:assets/(?:brand|intro|splash)|icons)/[^\"'\s)]*david[^\"'\s)]*"
                     r"|assets/icon\.svg", re.I)
    for f in sorted(set(targets)):
        for n, line in enumerate((ROOT / f).read_text(encoding="utf-8").splitlines(), 1):
            hit = ref.search(line)
            if hit:
                errors.append(
                    "%s:%d references the retired David mark ('%s'). The app's "
                    "launch imagery comes off these files, so this would show "
                    "the old logo while the app is opening."
                    % (f, n, hit.group(0)))

    # 4. The launch imagery must actually exist — a 404 here is a blank or
    #    fallback splash on a phone, which is how the last swap got missed.
    for a in LAUNCH_ASSETS:
        if not (ROOT / a).exists():
            errors.append(
                "launch asset '%s' is missing — it is what a player sees while "
                "the app is opening" % a)

    if len(errors) == before:
        print("brand mark OK: Antinous only, all %d launch assets present"
              % len(LAUNCH_ASSETS))


def main():
    check_version_lock()
    check_file_sizes()
    check_leaks()
    check_deny_rules()
    check_brand_mark()
    if errors:
        for e in errors:
            print("ERROR " + e, file=sys.stderr)
        return 1
    print("repo checks: all green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
