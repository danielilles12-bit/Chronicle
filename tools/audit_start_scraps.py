#!/usr/bin/env python3
"""Start-scrap fairness audit for Face Value / Relic.

Replicates js/revealgame.js's exact geometry — the square cover-fit window
into each image (biased by fx/fy), the 3x3 scrap grid, the money cell
(the cell holding the focal point) and the free opening cell (farthest from
the money cell, corners-first) — and renders one "audit card" PNG per item:

  LEFT  : the full square window with the 3x3 grid, every cell numbered,
          M = money cell, S = current opening cell
  RIGHT : the opening cell enlarged — exactly what the player sees for free

A reviewer (human or model) then judges each opening cell: does it show SOME
part of the subject (fair), the give-away feature (too easy), or nothing but
sky/backdrop (unfair)? Verdicts feed optional per-item `start` overrides in
data/reveal-*.json, which startScrap() honours.

Usage: python3 tools/audit_start_scraps.py <output-dir>
Writes <output-dir>/cards/<id>.png and <output-dir>/manifest.json
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WINDOW = 480          # rendered size of the square window (left panel)
CROP = 360            # rendered size of the opening-cell crop (right panel)
PAD = 16
CAPTION_H = 54


def money_scrap(fx, fy):
    c = min(2, int(fx * 3))
    r = min(2, int(fy * 3))
    return r * 3 + c


def start_scrap(fx, fy, override=None):
    m = money_scrap(fx, fy)
    # Curated override (js/revealgame.js's startScrap): honoured whenever it's
    # a valid, in-range cell that isn't the money cell itself — the audit must
    # render exactly what the app actually shows, not the calculated default
    # an override was written to replace.
    if isinstance(override, int) and 0 <= override <= 8 and override != m:
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
    crop = src.crop(tuple(int(v) for v in cell_box(x0, y0, s, start))) \
              .resize((CROP, CROP), Image.LANCZOS)

    card_w = PAD + WINDOW + PAD + CROP + PAD
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

    cx = PAD + WINDOW + PAD
    card.paste(crop, (cx, CAPTION_H))
    d.rectangle([cx, CAPTION_H, cx + CROP, CAPTION_H + CROP],
                outline=(0, 0, 0), width=3)
    d.text((cx, CAPTION_H + CROP + 4), "OPENING SCRAP (free view)",
           fill=(20, 20, 20), font=font(18))

    card.save(out_path, "PNG")
    return {"id": item["id"], "name": item["name"], "kind": item["kind"],
            "difficulty": item.get("difficulty"), "img": item["img"],
            "fx": item["fx"], "fy": item["fy"],
            "money": money, "start": start,
            "override": item.get("start"),
            "card": out_path}


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "audit", "start-scraps")
    cards_dir = os.path.join(out_dir, "cards")
    os.makedirs(cards_dir, exist_ok=True)
    manifest = []
    errors = []
    for fname in ("reveal-who.json", "reveal-what.json"):
        items = json.load(open(os.path.join(ROOT, "data", fname)))
        for item in items:
            try:
                rec = render_card(item, os.path.join(cards_dir, item["id"] + ".png"))
                manifest.append(rec)
            except Exception as e:          # noqa: BLE001 — audit must survive one bad file
                errors.append({"id": item["id"], "error": str(e)})
    json.dump({"items": manifest, "errors": errors},
              open(os.path.join(out_dir, "manifest.json"), "w"), indent=1)
    print(f"{len(manifest)} cards -> {cards_dir}")
    if errors:
        print(f"{len(errors)} ERRORS:")
        for e in errors:
            print(" ", e["id"], e["error"])


if __name__ == "__main__":
    main()
