#!/usr/bin/env python3
"""Picture-audit contact sheets for the content engine's picture auditor.

For every Face Value / Relic item (or a chosen subset) this renders the
square play window exactly as js/revealgame.js shows it — cover-fit, biased
by fx/fy, cut into the 3x3 scrap grid — with each cell numbered 0-8 (the
0-INDEXED `start` value the data files use), the current opening scrap
outlined green and the money cell outlined pink. Cells that are nearly
uniform (blank sky, black suit, studio backdrop) are marked "flat" and
very dark cells "dark" — a mechanical hint, not a verdict.

Two items per sheet keeps a model reviewer's image budget low while the
faces stay large enough to judge.

Usage:
  python3 tools/engine/render_audit_sheets.py OUT_DIR [--ids a,b,c]
      [--editions A-B [--manifest PATH]] [--game who|what] [--per-sheet N]
Writes OUT_DIR/sheet-NNN.png and OUT_DIR/index.json (sheet -> ids).
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageStat

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from audit_start_scraps import cell_box, money_scrap, start_scrap, window_box  # noqa: E402

TILE = 450
CAP = 58
PAD = 12
GREEN = (40, 200, 110)
PINK = (255, 60, 120)


def font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def cell_flags(win):
    """Per-cell 'flat'/'dark' hints from luminance stats of the window."""
    g = win.convert("L")
    cs = win.size[0] / 3
    out = {}
    for cell in range(9):
        r, c = divmod(cell, 3)
        st = ImageStat.Stat(g.crop((int(c * cs), int(r * cs), int((c + 1) * cs), int((r + 1) * cs))))
        mean, sd = st.mean[0], st.stddev[0]
        flags = []
        if mean < 38:
            flags.append("dark")
        if sd < 14:
            flags.append("flat")
        if flags:
            out[cell] = flags
    return out


def render_tile(item, game):
    src = Image.open(ROOT / item["img"]).convert("RGB")
    w, h = src.size
    x0, y0, s = window_box(w, h, item["fx"], item["fy"])
    money = money_scrap(item["fx"], item["fy"])
    start = start_scrap(item["fx"], item["fy"], item.get("start"))
    win = src.crop((int(x0), int(y0), int(x0 + s), int(y0 + s))).resize((TILE, TILE), Image.LANCZOS)
    flags = cell_flags(win)
    tile = Image.new("RGB", (TILE, TILE + CAP), (242, 239, 230))
    d = ImageDraw.Draw(tile)
    d.text((4, 2), f'{item["id"]}', fill=(10, 10, 10), font=font(20))
    d.text((4, 26), f'{item["name"][:34]} · {game} · {item.get("difficulty")} · start={start}',
           fill=(60, 60, 60), font=font(16))
    tile.paste(win, (0, CAP))
    cs = TILE / 3
    for i in range(1, 3):
        d.line([(i * cs, CAP), (i * cs, CAP + TILE)], fill=(255, 255, 255), width=2)
        d.line([(0, CAP + i * cs), (TILE, CAP + i * cs)], fill=(255, 255, 255), width=2)
    for cell in range(9):
        r, c = divmod(cell, 3)
        bx, by = c * cs, CAP + r * cs
        if cell == start:
            d.rectangle([bx + 2, by + 2, bx + cs - 2, by + cs - 2], outline=GREEN, width=5)
        if cell == money:
            d.rectangle([bx + 7, by + 7, bx + cs - 7, by + cs - 7], outline=PINK, width=3)
        lab = str(cell) + (" S" if cell == start else "") + (" M" if cell == money else "")
        if cell in flags:
            lab += " " + "/".join(flags[cell])
        d.rectangle([bx + 4, by + 4, bx + 10 + 10 * len(lab), by + 26], fill=(0, 0, 0))
        d.text((bx + 7, by + 5), lab, fill=(255, 255, 255), font=font(17))
    return tile, {"id": item["id"], "name": item["name"], "game": game,
                  "difficulty": item.get("difficulty"), "start": start, "money": money,
                  "flat_or_dark_cells": sorted(flags), "curated_start": item.get("start")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--ids", default=None)
    ap.add_argument("--editions", default=None)
    ap.add_argument("--manifest", default=str(ROOT / "data/editions.json"),
                    help="schedule to read --editions from (e.g. the autopilot's merged.json)")
    ap.add_argument("--game", choices=["who", "what"], default=None)
    ap.add_argument("--per-sheet", type=int, default=2)
    ap.add_argument("--include-reserved", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    want = set(a.ids.split(",")) if a.ids else None
    if a.editions:
        lo, hi = map(int, a.editions.split("-"))
        eds = json.load(open(a.manifest))["editions"]
        want = (want or set()) | {i for n in range(lo, hi + 1) for g in ("who", "what")
                                  for i in eds.get(str(n), {}).get(g, [])}
    items = []
    for game in ("who", "what"):
        if a.game and a.game != game:
            continue
        for it in json.load(open(ROOT / f"data/reveal-{game}.json")):
            if want is not None and it["id"] not in want:
                continue
            if it.get("reserve") and not a.include_reserved and want is None:
                continue
            if not (ROOT / it["img"]).exists():
                continue
            items.append((game, it))
    index = []
    for k in range(0, len(items), a.per_sheet):
        chunk = items[k:k + a.per_sheet]
        tiles = [render_tile(it, g) for g, it in chunk]
        sheet = Image.new("RGB", (len(tiles) * TILE + (len(tiles) + 1) * PAD, TILE + CAP + 2 * PAD), (255, 255, 255))
        for j, (t, _) in enumerate(tiles):
            sheet.paste(t, (PAD + j * (TILE + PAD), PAD))
        name = f"sheet-{k // a.per_sheet:03d}.png"
        sheet.save(out / name, optimize=True)
        index.append({"sheet": name, "items": [m for _, m in tiles]})
    json.dump(index, open(out / "index.json", "w"), indent=1, ensure_ascii=False)
    print(f"{len(items)} items -> {len(index)} sheets in {out}")


if __name__ == "__main__":
    main()
