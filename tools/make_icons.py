#!/usr/bin/env python3
"""Render the app icon SVG to the PNG set the manifest needs."""
import os
from playwright.sync_api import sync_playwright

ROOT = os.path.join(os.path.dirname(__file__), "..")
SVG = open(os.path.join(ROOT, "assets", "icon.svg")).read()
OUT = os.path.join(ROOT, "icons")

JOBS = [
    ("icon-512.png", 512, False),
    ("icon-192.png", 192, False),
    ("apple-touch-icon.png", 180, False),
    ("favicon.png", 32, False),
    ("icon-maskable-512.png", 512, True),
]


def html_for(size, maskable):
    if maskable:
        inner = SVG.replace("<svg ", '<svg width="%d" height="%d" ' % (int(size * .78), int(size * .78)), 1)
        return ('<body style="margin:0"><div style="width:%dpx;height:%dpx;background:#f6f1e4;'
                'display:flex;align-items:center;justify-content:center">%s</div></body>'
                % (size, size, inner))
    inner = SVG.replace("<svg ", '<svg width="%d" height="%d" ' % (size, size), 1)
    return '<body style="margin:0">%s</body>' % inner


def main():
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        for name, size, maskable in JOBS:
            pg = b.new_page(viewport={"width": size, "height": size})
            pg.set_content(html_for(size, maskable))
            pg.screenshot(path=os.path.join(OUT, name), clip={"x": 0, "y": 0, "width": size, "height": size})
            pg.close()
            print("wrote", name)
        b.close()


if __name__ == "__main__":
    main()
