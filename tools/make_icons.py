#!/usr/bin/env python3
"""Regenerate the launch-icon set from the Antinous master.

These four PNGs are the app's LAUNCH imagery: iOS uses apple-touch-icon.png on
the home screen, Chrome/Android composes its PWA splash screen (the loading
screen) from the manifest's icon-192/512, and favicon.png is the browser tab.
So whatever this tool renders is what a player sees while the app is opening.

Until v184 this script rendered assets/icon.svg — a hand-drawn bust in PINK
SUNGLASSES, the retired pre-v91 Michelangelo's-David mark. The shipped PNGs had
long since been hand-replaced with the pop-art nerd-Antinous (Daniel's 4 Aug
2026 ruling: one saint across icon, masthead sticker, social card and splash),
but this generator was never updated with them. Running it would have quietly
put David back on the loading screen. The David SVG is gone; icons/icon-512.png
is now the master and every smaller size is derived from it, so re-running this
reproduces the Antinous and cannot resurrect the old mark.

  python3 tools/make_icons.py            # rewrite icons/ from the master
  python3 tools/make_icons.py --check    # verify only, touch nothing (CI-safe)

Pillow only — no Node, no browser.
"""
import os
import sys

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "icons")

# The master: the largest icon the app ships. Every other size is a downscale
# of it, so the set can never drift apart or drift back to a retired mark.
MASTER = os.path.join(OUT, "icon-512.png")

# name -> square size in px. icon-512 is the master and is never rewritten.
SIZES = [
    ("icon-192.png", 192),
    ("apple-touch-icon.png", 180),
    ("favicon.png", 64),
]


def render(size):
    im = Image.open(MASTER).convert("RGB")
    if im.size != (512, 512):
        raise SystemExit("master %s is %dx%d, expected 512x512" % (MASTER, *im.size))
    return im.resize((size, size), Image.LANCZOS)


def main():
    check = "--check" in sys.argv[1:]
    if not os.path.exists(MASTER):
        raise SystemExit("missing master icon: " + MASTER)
    bad = 0
    for name, size in SIZES:
        path = os.path.join(OUT, name)
        if check:
            if not os.path.exists(path):
                print("MISSING", name)
                bad += 1
                continue
            got = Image.open(path).size
            if got != (size, size):
                print("WRONG SIZE %s: %dx%d, expected %dx%d" % (name, *got, size, size))
                bad += 1
            else:
                print("ok", name, "%dx%d" % got)
            continue
        render(size).save(path)
        print("wrote", name, "%dx%d" % (size, size))
    if check:
        print("icon set: %s" % ("%d problem(s)" % bad if bad else "all green"))
        return 1 if bad else 0
    print("master left untouched:", os.path.relpath(MASTER, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
