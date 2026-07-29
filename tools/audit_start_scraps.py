#!/usr/bin/env python3
"""Start-scrap fairness audit for Face Value / Relic.

Replicates js/revealgame.js's exact geometry — the square cover-fit window
into each image (biased by fx/fy), the 3x3 scrap grid, the money cell
(the cell holding the focal point) and the free opening cell (farthest from
the money cell, corners-first) — and renders one "audit card" PNG per item:

  LEFT   : the full square window with the 3x3 grid, every cell numbered,
           M = money cell, S = current opening cell
  MIDDLE : the opening cell enlarged — exactly what the player sees for free
  RIGHT  : the money cell enlarged — the reveal the start logic steers away
           from, so a reviewer sees both ends of the tear path at a glance

A reviewer (human or model) then judges each opening cell: does it show SOME
part of the subject (fair), the give-away feature (too easy), or nothing but
sky/backdrop (unfair)? Verdicts feed optional per-item `start` overrides in
data/reveal-*.json, which startScrap() honours.

Usage:
  python3 tools/audit_start_scraps.py [output-dir] [--editions A-B]

With no arguments, audits the full who+what pool into audit/start-scraps/
(the historical default). --editions A-B narrows the pool to items scheduled
in editions A through B inclusive, per data/editions.json — e.g. a 300-card
launch sheet is one command: `--editions 35-64`.

Writes <output-dir>/cards/<id>.png and <output-dir>/manifest.json
"""
import argparse
import json
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT_DIR = os.path.join(ROOT, "audit", "start-scraps")

WINDOW = 480          # rendered size of the square window (left panel)
CROP = 360            # rendered size of an enlarged single-cell crop
PAD = 16
CAPTION_H = 54


def money_scrap(fx, fy):
    c = min(2, int(fx * 3))
    r = min(2, int(fy * 3))
    return r * 3 + c


def start_scrap(fx, fy, override=None):
    m = money_scrap(fx, fy)
    # Curated override (js/revealgame.js's startScrap): honoured whenever it's
    # a valid, in-range cell — INCLUDING the money cell itself (owner ruling,
    # 29 Jul 2026: for obscure subjects the give-away opener is the kinder
    # game). The audit must render exactly what the app actually shows.
    if isinstance(override, int) and 0 <= override <= 8:
        return override
    mr, mc = divmod(m, 3)
    best, bd = 0, -1
    for i in [0, 2, 6, 8, 1, 3, 5, 7, 4]:   # corners first, deterministic
        d = abs(i // 3 - mr) + abs(i % 3 - mc)
        if d > bd:
            bd, best = d, i
    return best


def window_box(w, h, fx, fy):
    """The square cover-fit window in source-image pixels."""
    s = min(w, h)
    x0 = (w - s) * fx
    y0 = (h - s) * fy
    return x0, y0, s


def cell_box(x0, y0, s, cell):
    r, c = divmod(cell, 3)
    cs = s / 3
    return (x0 + c * cs, y0 + r * cs, x0 + (c + 1) * cs, y0 + (r + 1) * cs)


def font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:                        # very old Pillow
        return ImageFont.load_default()


def render_card(item, out_path):
    src = Image.open(os.path.join(ROOT, item["img"])).convert("RGB")
    w, h = src.size
    x0, y0, s = window_box(w, h, item["fx"], item["fy"])
    money = money_scrap(item["fx"], item["fy"])
    start = start_scrap(item["fx"], item["fy"], item.get("start"))

    window = src.crop((int(x0), int(y0), int(x0 + s), int(y0 + s))) \
                .resize((WINDOW, WINDOW), Image.LANCZOS)
    start_crop = src.crop(tuple(int(v) for v in cell_box(x0, y0, s, start))) \
                     .resize((CROP, CROP), Image.LANCZOS)
    money_crop = src.crop(tuple(int(v) for v in cell_box(x0, y0, s, money))) \
                     .resize((CROP, CROP), Image.LANCZOS)

    card_w = PAD + WINDOW + PAD + CROP + PAD + CROP + PAD
    card_h = CAPTION_H + WINDOW + PAD
    card = Image.new("RGB", (card_w, card_h), (242, 239, 230))
    d = ImageDraw.Draw(card)

    d.text((PAD, 10), f'{item["id"]}  ·  {item["name"]}  ·  {item["kind"]}'
           f'  ·  {item.get("difficulty", "?")}',
           fill=(20, 20, 20), font=font(22))

    card.paste(window, (PAD, CAPTION_H))
    cs = WINDOW / 3
    for i in range(1, 3):                    # grid lines
        d.line([(PAD + i * cs, CAPTION_H), (PAD + i * cs, CAPTION_H + WINDOW)],
               fill=(255, 255, 255), width=2)
        d.line([(PAD, CAPTION_H + i * cs), (PAD + WINDOW, CAPTION_H + i * cs)],
               fill=(255, 255, 255), width=2)
    f_big = font(30)
    for cell in range(9):                    # cell indices + M/S badges
        r, c = divmod(cell, 3)
        cx, cy = PAD + c * cs + 6, CAPTION_H + r * cs + 4
        label = str(cell)
        if cell == money:
            label += " M"
        if cell == start:
            label += " S"
        d.rectangle([cx - 2, cy, cx + 16 * len(label), cy + 32],
                    fill=(0, 0, 0))
        d.text((cx + 2, cy + 2), label, fill=(255, 60, 120) if cell == money
               else (255, 255, 255) if cell != start else (90, 220, 140),
               font=f_big)

    # MIDDLE: the opening scrap (free view) — same green as its "S" badge.
    sx = PAD + WINDOW + PAD
    card.paste(start_crop, (sx, CAPTION_H))
    d.rectangle([sx, CAPTION_H, sx + CROP, CAPTION_H + CROP],
                outline=(90, 220, 140), width=3)
    d.text((sx, CAPTION_H + CROP + 4), "OPENING SCRAP (free view)",
           fill=(20, 20, 20), font=font(18))

    # RIGHT: the money cell — same pink as its "M" badge. Alongside the
    # opening scrap so a reviewer sees both ends of the tear path without
    # hunting the grid for cell M.
    mx = sx + CROP + PAD
    card.paste(money_crop, (mx, CAPTION_H))
    d.rectangle([mx, CAPTION_H, mx + CROP, CAPTION_H + CROP],
                outline=(255, 60, 120), width=3)
    d.text((mx, CAPTION_H + CROP + 4), "MONEY CELL (the reveal)",
           fill=(20, 20, 20), font=font(18))

    card.save(out_path, "PNG")
    return {"id": item["id"], "name": item["name"], "kind": item["kind"],
            "difficulty": item.get("difficulty"), "img": item["img"],
            "fx": item["fx"], "fy": item["fy"],
            "money": money, "start": start,
            "override": item.get("start"),
            "card": out_path}


def parse_edition_range(s):
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", s)
    if not m:
        raise argparse.ArgumentTypeError(f"expected A-B (e.g. 35-64), got {s!r}")
    lo, hi = int(m.group(1)), int(m.group(2))
    return (lo, hi) if lo <= hi else (hi, lo)


def edition_item_ids(lo, hi):
    """Reveal ids (who + what) scheduled in editions[lo..hi] inclusive, per
    data/editions.json (a dict keyed by string edition index)."""
    manifest = json.load(open(os.path.join(ROOT, "data", "editions.json")))
    eds = manifest.get("editions") or {}
    ids = set()
    for i in range(lo, hi + 1):
        ed = eds.get(str(i))
        if not ed:
            continue
        ids.update(ed.get("who") or [])
        ids.update(ed.get("what") or [])
    return ids


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("out_dir", nargs="?", default=DEFAULT_OUT_DIR,
                    help=f"output directory (default: {os.path.relpath(DEFAULT_OUT_DIR, ROOT)})")
    p.add_argument("--editions", metavar="A-B", type=parse_edition_range, default=None,
                    help="limit to items scheduled in editions A-B inclusive, per data/editions.json "
                         "(default: the full who+what pool)")
    return p.parse_args(argv)


def main():
    args = parse_args()
    cards_dir = os.path.join(args.out_dir, "cards")
    os.makedirs(cards_dir, exist_ok=True)

    allowed_ids = None
    if args.editions:
        lo, hi = args.editions
        allowed_ids = edition_item_ids(lo, hi)
        print(f"--editions {lo}-{hi}: {len(allowed_ids)} scheduled item id(s)")

    manifest = []
    errors = []
    for fname in ("reveal-who.json", "reveal-what.json"):
        items = json.load(open(os.path.join(ROOT, "data", fname)))
        for item in items:
            if allowed_ids is not None and item["id"] not in allowed_ids:
                continue
            try:
                rec = render_card(item, os.path.join(cards_dir, item["id"] + ".png"))
                manifest.append(rec)
            except Exception as e:          # noqa: BLE001 — audit must survive one bad file
                errors.append({"id": item["id"], "error": str(e)})
    json.dump({"items": manifest, "errors": errors},
              open(os.path.join(args.out_dir, "manifest.json"), "w"), indent=1)
    print(f"{len(manifest)} cards -> {cards_dir}")
    if errors:
        print(f"{len(errors)} ERRORS:")
        for e in errors:
            print(" ", e["id"], e["error"])


if __name__ == "__main__":
    main()
