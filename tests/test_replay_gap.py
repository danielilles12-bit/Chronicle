#!/usr/bin/env python3
"""The curation-gap safety net (29 Sep 2026).

The schedule is now topped up by an unattended weekly run. If that run ever
stops and a day arrives with no manifest entry, js/daily.js must NOT cut an
uncurated issue from the raw pools: it replays an approved issue from a
whole number of 13-week (91-day) cycles earlier — same weekday, so Thread
keeps its tier — never reaching back before launch day (edition 42).

Checks, against the real manifest:
  * the arithmetic: a gap two days past the manifest's end replays
    n - 91k, the nearest such edition the manifest holds, >= 42;
  * a day too early for any cycle to land (n - 91 < 42) gets null, so the
    old history arithmetic keeps serving pre-manifest days untouched;
  * getEdition for every game on the gap day returns exactly the replayed
    edition's items, in order.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
import helpers as H  # noqa: E402

LAST = H.latest_edition()
EDS = H.manifest()["editions"]


def expected_replay(n):
    m = n - 91
    while m >= 42:
        if str(m) in EDS:
            return m
        m -= 91
    return None


def gap_replays_approved_issue(p, base):
    gap = LAST + 2
    want = expected_replay(gap)
    assert want is not None, "manifest too short for a 13-week replay"
    with H.app(p) as (page, errors, _ctx):
        H.boot(page, base, H.edition_date(LAST))
        got = page.evaluate("n => __CHRONICLE_TEST__.daily.replayEditionFor(n)", gap)
        assert got == want, "gap %d replays %r, expected %r" % (gap, got, want)
        assert (gap - got) % 91 == 0 and got >= 42
        for game in ("who", "map", "what", "thread"):
            ids = page.evaluate(
                "a => __CHRONICLE_TEST__.daily.getEdition(a[0], a[1]).map(x => x.id)",
                [game, gap])
            assert ids == EDS[str(want)][game], (
                "%s on gap day %d served %r, not edition %d's %r"
                % (game, gap, ids, want, EDS[str(want)][game]))
        early = page.evaluate("n => __CHRONICLE_TEST__.daily.replayEditionFor(n)", 100)
        assert early is None, "edition 100 has no 13-week predecessor >= 42, got %r" % early
        H.fail_on_errors(errors, "gap_replays_approved_issue")


TESTS = [gap_replays_approved_issue]


def main():
    failures = []
    with H.server() as base, sync_playwright() as p:
        for t in TESTS:
            print("--", t.__name__)
            try:
                t(p, base)
                print("   PASS")
            except Exception as e:
                failures.append((t.__name__, e))
                print("   FAIL:", e)
    if failures:
        print("\n%d/%d scenarios failed" % (len(failures), len(TESTS)))
        sys.exit(1)
    print("\nall %d scenarios passed" % len(TESTS))


if __name__ == "__main__":
    main()
