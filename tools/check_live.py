#!/usr/bin/env python3
"""Is the live site really hiding its internal files? Read-only, stdlib only.

Run this AFTER a deploy has landed — never in CI, which runs before the new
files reach Cloudflare and would only ever check the previous version.

  python3 tools/check_live.py
  python3 tools/check_live.py https://fix-prelaunch-hardening.yesternerd.pages.dev

Two questions, in plain terms:

  1. Every address on the deny list (tools/repo_checks.py DENY_PATHS) must end
     up as "not found". The rules in _redirects bounce these to /nowhere,
     which does not exist, so the honest answer is a 404 — that is what this
     looks for, following the bounce to wherever it lands.

  2. The handful of files the app itself cannot run without must still be
     there. A deny rule with one character wrong could take the whole site
     down, and this is the check that would say so.

Exits non-zero if anything is wrong, and prints a line per address either way.
"""
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from repo_checks import DENY_PATHS  # noqa: E402  (one list, two checkers)

DEFAULT_BASE = "https://yesternerd.app"

# Cloudflare answers a bare Python request with 403 before it ever reaches the
# site, which would read as a false pass. Ask the way a browser asks.
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# A wildcard rule can only be tested through a real file behind it, so each
# one names files that genuinely exist in the repo today. If one of these is
# ever renamed away, the probe stops proving anything — pick another.
WILDCARD_PROBES = {
    "/audit/*": ["/audit/review.html", "/audit/review", "/audit/new-figures.json"],
    "/tools/*": ["/tools/editions.config.json", "/tools/repo_checks.py"],
    "/tests/*": ["/tests/run_all.py"],
    "/attic/*": ["/attic/README.md"],
    "/design-reviews/*": ["/design-reviews/feedback-plan.md"],
    "/.github/*": ["/.github/workflows/ci.yml"],
    "/.claude/*": ["/.claude/settings.json"],
}

# The app stops working without these, so a deny rule must never catch them.
MUST_SERVE = ["/", "/js/app.js", "/sw.js", "/data/editions.json", "/privacy.html"]

REDIRECTS = (301, 302, 303, 307, 308)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Hand back the redirect instead of following it."""

    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def one_hop(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with OPENER.open(req, timeout=30) as r:
            return r.status, r.headers.get("Location")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location")


def fetch(url, max_hops=5):
    """Final status code, plus the hops it took to get there.

    Redirects are followed by hand: Python 3.9's urllib does not follow a 308
    at all, and the route an address takes is worth printing either way.
    """
    hops = []
    for _ in range(max_hops):
        code, location = one_hop(url)
        hops.append((url, code))
        if code in REDIRECTS and location:
            url = urllib.parse.urljoin(url, location)
            continue
        return code, hops
    return None, hops


def trail(hops):
    """'302 -> /nowhere 404', short enough to read at a glance."""
    out = []
    for i, (url, code) in enumerate(hops):
        where = urllib.parse.urlsplit(url).path or "/"
        out.append("%s%s" % ("" if i == 0 else where + " ", code))
    return " -> ".join(out)


def main():
    base = (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE).rstrip("/")
    print("checking %s\n" % base)
    failures = 0

    print("must be hidden (expect: not found)")
    for rule in DENY_PATHS:
        probes = WILDCARD_PROBES.get(rule, [rule]) if rule.endswith("*") else [rule]
        if rule.endswith("*") and rule not in WILDCARD_PROBES:
            print("  SKIP %-38s no probe file listed for this rule" % rule)
            failures += 1
            continue
        for path in probes:
            code, hops = fetch(base + path)
            ok = code == 404
            failures += not ok
            print("  %-4s %-38s %s" % ("PASS" if ok else "FAIL", path, trail(hops)))

    print("\nmust keep working (expect: 200)")
    for path in MUST_SERVE:
        code, hops = fetch(base + path)
        ok = code == 200
        failures += not ok
        print("  %-4s %-38s %s" % ("PASS" if ok else "FAIL", path, trail(hops)))

    if failures:
        print("\n%d check(s) failed — the site is not in the state it should "
              "be in. Anything under 'must be hidden' that is not a 404 is "
              "still being served to the public." % failures)
        return 1
    print("\nall clear: internal files are not reachable, the app is.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
