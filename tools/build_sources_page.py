#!/usr/bin/env python3
"""Generate the image credit register on sources.html from the app's own
data files (P3.4). Never hand-edit the table — re-run this script instead,
same as tools/build_map.py owns worldmap.json.

Rewrites only the block between the <!-- BUILD:REGISTER:START/END --> HTML
comments in sources.html; everything else in the file (masthead, intro
copy, footer nav) is left untouched.

Usage: python3 tools/build_sources_page.py
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "sources.html"
START, END = "<!-- BUILD:REGISTER:START -->", "<!-- BUILD:REGISTER:END -->"

TABLES = [
    ("Face Value — portraits", "data/reveal-who.json"),
    ("Relic — artefacts, places & art", "data/reveal-what.json"),
]


def esc(s):
    return html.escape(str(s or ""), quote=False)


def row(rec):
    name = esc(rec.get("name"))
    author = esc(rec.get("image_author") or rec.get("attribution") or "Unknown")
    license_label = esc(rec.get("image_license") or rec.get("license") or "")
    license_url = rec.get("image_license_url")
    source_url = rec.get("image_source_url")

    license_cell = f'<a href="{esc(license_url)}" target="_blank" rel="noopener">{license_label}</a>' \
        if license_url else license_label
    source_cell = f'<a href="{esc(source_url)}" target="_blank" rel="noopener">Wikimedia Commons</a>' \
        if source_url else "Wikimedia Commons"

    return (f"      <tr><td class=\"reg-name\">{name}</td><td>{author}</td>"
            f"<td>{license_cell}</td><td>{source_cell}</td></tr>")


def build_table(title, rel_path):
    items = json.loads((ROOT / rel_path).read_text(encoding="utf-8"))
    items = sorted(items, key=lambda x: x.get("name", "").lower())
    rows = "\n".join(row(r) for r in items)
    return (
        f'    <h3 style="font-family:var(--ch-font-ui);font-size:13px;'
        f'text-transform:uppercase;letter-spacing:.04em;color:var(--ch-text-muted);'
        f'margin:20px 0 6px">{esc(title)} ({len(items)})</h3>\n'
        f'    <div class="reg-table-wrap"><table class="reg-table">\n'
        f'      <tr><th>Name</th><th>Author</th><th>Licence</th><th>Source</th></tr>\n'
        f'{rows}\n'
        f'    </table></div>'
    )


def main():
    total = 0
    blocks = []
    for title, rel_path in TABLES:
        items = json.loads((ROOT / rel_path).read_text(encoding="utf-8"))
        total += len(items)
        blocks.append(build_table(title, rel_path))

    # Wrapped in #reg-register (5 Aug 2026) so the search box's script — a
    # hand-written progressive enhancement living OUTSIDE this generated
    # block, in sources.html itself — has one stable container to scope its
    # row-collection to, however the tables/headings inside get reshuffled.
    register = (
        '    <div id="reg-register">\n'
        f'    <p><small>Every image, generated from the app\'s data files. '
        f'Public-domain images need no attribution; the photographer is shown '
        f'anyway where Commons records one.</small></p>\n'
        + "\n".join(blocks)
        + '\n    </div>'
    )

    text = PAGE.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(text):
        print(f"error: markers {START!r}/{END!r} not found in {PAGE}", file=sys.stderr)
        return 1
    new_text = pattern.sub(f"{START}\n{register}\n{END}", text, count=1)
    PAGE.write_text(new_text, encoding="utf-8")
    print(f"Wrote {total} rows across {len(TABLES)} tables to {PAGE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
