#!/usr/bin/env python3
"""Photograph a REAL Face Value board for the stranger's Home hero.

The newcomer hero (index.html #stranger-hero) shows the game being played
rather than a drawing of it, so the picture has to come out of the game
itself: this script boots the actual app on a local server, opens Face Value
on a board pinned to `frida-kahlo`, and screenshots the frame's content box —
photograph plus paper scraps, no border, so the page can draw the house frame
around it in CSS at the house's own weight.

Art direction (Daniel, 6 Aug 2026): exactly ONE tile open — the state a round
actually starts in, which keeps the mystery — and that one opening must land
on the most identifying part of the face (brow + one eye), not on cheek,
shawl, hair or backdrop. Two knobs get it there, and both are the app's own
machinery rather than a fake:

  * the SOURCE CROP. A hero still does not have to use the round's crop, so
    the photograph is cropped square (public domain, Guillermo Kahlo) and
    served in place of the original. The app then cover-fits, grids and tears
    it exactly as it would any other picture. Choosing the crop chooses how
    much of the face one ninth of the board covers.
    The photograph served here is NOT the one the round plays on. The round's
    copy (assets/img/frida-kahlo.jpg) is 667x1000 — fine behind a whole board,
    but the hero shows a quarter of one, so the crop is a fraction of a
    fraction and the original's pixels run out first. Commons holds the same
    1932 Guillermo Kahlo print at 1197x1795, and tools/demo-source/ keeps that
    copy for this tool alone (see SOURCE). It is the same photograph to within
    JPEG noise — a mean absolute difference of 2.4/255 against the shipped file
    downscaled to match — so nothing about the composition changes, there are
    simply 1.79x more real pixels under it. The round's own image file is left
    exactly as content curation has it: marketing does not get to edit the
    pool's pictures.
  * `start`. A real curated field the pipeline already supports (see
    startScrap in js/revealgame.js): it pins the scrap the GAME opens on the
    house. Nothing is torn by hand, so the board is a genuine opening state.

FOUR SQUARES, NOT NINE (Daniel, 7 Aug 2026): the hero now shows a 2x2 corner
of the board — four squares tell the story and the page gets its width back
for the headline beside it. The GAME is still a 3x3 (SCRAPS = 9 in
js/revealgame.js is the only board the engine has), so the asset is a straight
CROP of a genuine nine-square render, taken at exactly 1:1 device pixels — no
resampling, no redrawing. Every scrap edge, dashed tearable border, paper
grain and torn opening in the file is the browser's own output. The quadrant
is chosen by the opening scrap: `start` must be tile 0, 1, 3 or 4, and the
crop is the 2x2 block whose TOP-LEFT square is that opening, so the revealed
eye always lands nearest the headline.

The board renders at DEVICE_SCALE=3, so the hero is 900x900 and stays sharp on
a phone that draws three device pixels per CSS pixel — this is the first thing
a newcomer ever sees of the product and a soft one undersells it.

Both the pinned edition and the crop are injected as Playwright routes —
never written to disk. The manifest belongs to the schedule, not to marketing.

The subject is out of rotation (`"reserve": true` in data/reveal-who.json —
the live pool, not the legacy data/reveal.json), so the face on permanent
display can never also be a live puzzle.

    python3 tools/make_demo_shot.py                     # all candidates
    python3 tools/make_demo_shot.py --pick corner-eye   # write the chosen one

Candidates land in tools/out/demo-candidates/ (never served) — both the cropped
2x2 that would ship and the whole nine-square board it came out of, so the crop
can be checked against its source; --pick saves the finished hero to
assets/brand/demo-facevalue.webp.
"""
import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests"))

from PIL import Image                              # noqa: E402
from playwright.sync_api import sync_playwright    # noqa: E402

import helpers as H                                # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT_DIR = os.path.join(ROOT, "tools", "out", "demo-candidates")
HERO_PATH = os.path.join(ROOT, "assets", "brand", "demo-facevalue.webp")
# Demo-only, and deliberately NOT under assets/: the high-resolution Commons
# copy of the same public-domain print (File:Frida Kahlo, by Guillermo
# Kahlo.jpg, 1197x1795, retrieved 7 Aug 2026). It exists so the hero has real
# pixels to crop into; the app never loads it, and /tools/* is 404ed on the
# public site by _redirects (enforced by tools/repo_checks.py).
SOURCE = os.path.join(ROOT, "tools", "demo-source", "frida-kahlo-commons.jpg")
# The space the face landmarks below are measured in — the round's own copy of
# the photograph. Crops are written in these coordinates and scaled to whatever
# SOURCE actually is, so a sharper original never means re-measuring a face.
LANDMARK_WIDTH = 667

SUBJECT = "frida-kahlo"
# Any aired edition works — the manifest is rewritten in flight so the pinned
# subject is the whole round list, which makes it round 1 every time.
PIN_EDITION = 22
# The scrap grid's CONTENT size in CSS px (#rv-frame is border-box, so the
# element is pinned 6px wider than this for its 3px ink border). 450 CSS px is
# the real game's board, so the scrap borders, dashes and grain keep exactly
# the proportions a player sees — DEVICE_SCALE is what buys resolution, and it
# scales every one of those details together instead of thinning the lines.
# 450 / 3 = a 150px tile, x3 DPR = 450 device px per tile, so the 2x2 crop
# below is 900x900 device px and ships without a single resampled pixel.
GRID_CSS_PX = 450
FRAME_BORDER_PX = 3
DEVICE_SCALE = 3
TILE_DEVICE_PX = GRID_CSS_PX // 3 * DEVICE_SCALE     # 450

# Face landmarks in the 667x1000 source, measured off a gridded overlay:
#   unibrow  x 255-455, y 240-265      left eye  centre (305, 288)
#   right eye centre (420, 288)        face box  x 215-470, y 150-470
#   the JOIN — where the brows meet over the nose bridge — (355, 250)
# A tile is one ninth of the board, so tile size = crop side / 3. The hero's
# 2x2 shows the face at a smaller tile than the 3x3 did, so the source crop
# tightens to compensate: crop side 360 puts as much brow-and-eye inside an
# 84px hero tile as crop side 450 put inside the old 100px one.
#
# `start` is also the crop key: the 2x2 taken is the block whose top-left
# square is the opening scrap, so start must be 0, 1, 3 or 4. Which one also
# decides how much room the composition has: the opening square is the crop's
# top-left, so the rest of the board runs down and to the RIGHT of whatever it
# frames. Tile 0 lets the source run 5/6 of the crop side to the right of the
# feature (the 667px-wide photograph caps that at side 374 for anything
# centred on the nose bridge); tile 1 centres it instead and buys the room
# back, which is the only way the widest unibrow shots fit inside the source.
#
# THE CHOICE (Daniel, 7 Aug 2026): B, brow-join-wide. Shown all three side by
# side he took the one where the brows MEET and both eyes are in the square —
# that is the thing that says Frida rather than "a face", and it is what a
# newcomer has to be able to name. A (brow-and-eye) and B2 (widest) are kept
# below only so the comparison that settled it is still on the record; neither
# is shipped again without a fresh decision.
#
# name -> (crop x, crop y, crop side, start tile, what the open tile shows)
COMPOSITIONS = {
    "brow-join-wide": (145, 180, 420, 1,
                       "SHIPPED — the join with BOTH inner brow ends and both "
                       "eyes in the square; opens on the top-centre scrap so "
                       "the crop can sit around the middle of the face"),
    "corner-eye": (245, 228, 360, 0,
                   "rejected 7 Aug (was A) — opening scrap is the board's own "
                   "top-left corner; one brow arch + her right eye centred in "
                   "it, two dashed tiles beside and below"),
    "brow-join-widest": (130, 175, 450, 1,
                         "rejected 7 Aug (was B2) — nearly the whole unibrow "
                         "and both eyes, the most unmistakably Frida but the "
                         "smallest features"),
}
DEFAULT_PICK = "brow-join-wide"


def pinned_manifest():
    with open(os.path.join(ROOT, "data", "editions.json"), encoding="utf-8") as f:
        man = json.load(f)
    man["editions"][str(PIN_EDITION)]["who"] = [SUBJECT]
    return json.dumps(man)


def pinned_pool(start):
    """reveal-who.json with the demo subject's opening scrap pinned."""
    with open(os.path.join(ROOT, "data", "reveal-who.json"), encoding="utf-8") as f:
        pool = json.load(f)
    for x in pool:
        if x["id"] == SUBJECT:
            x["start"] = start
    return json.dumps(pool)


def cropped_png(x, y, side):
    """The composed square, cut at the SOURCE's own resolution.

    Crops are written in LANDMARK_WIDTH coordinates (the round's 667px copy,
    which is where the face was measured) and scaled up to whatever SOURCE is,
    so a sharper original is a one-line change rather than a re-measure. PNG
    out, because the board is about to be photographed and a second JPEG
    generation would put ringing on exactly the edges the hero is selling.
    """
    im = Image.open(SOURCE).convert("RGB")
    k = im.width / LANDMARK_WIDTH
    box = tuple(round(v * k) for v in (x, y, x + side, y + side))
    assert box[2] <= im.width and box[3] <= im.height, (
        "crop %s runs off the %dx%d source" % (box, im.width, im.height))
    im = im.crop(box)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def open_board(page, base, manifest_json, pool_json, image_png):
    page.route("**/data/editions.json*",
               lambda r: r.fulfill(status=200, content_type="application/json",
                                   body=manifest_json))
    page.route("**/data/reveal-who.json*",
               lambda r: r.fulfill(status=200, content_type="application/json",
                                   body=pool_json))
    # Both the w800 variant the loader tries first and the original it falls
    # back to; content-type is what the browser decodes by, not the extension.
    # A regex, not a glob: the glob form silently failed to match the image
    # URLs here and the app quietly rendered the uncropped original.
    page.route(re.compile(re.escape(SUBJECT)),
               lambda r: r.fulfill(status=200, content_type="image/png",
                                   body=image_png))
    H.boot(page, base, dailydate=H.edition_date(PIN_EDITION))
    # The stranger's own CTA is the door to Face Value in every build of the
    # home screen, old or new — a fresh profile is always a stranger.
    page.wait_for_selector("#stranger-play")
    page.click("#stranger-play")
    page.wait_for_selector("#view-reveal:not([hidden])")
    page.wait_for_function(
        "__CHRONICLE_TEST__.revealRound && __CHRONICLE_TEST__.revealRound.id === '%s'"
        % SUBJECT)
    page.wait_for_function(
        "getComputedStyle(document.querySelector('#rv-frame')).backgroundImage"
        ".includes('%s')" % SUBJECT)
    page.wait_for_load_state("networkidle")
    # Guard: every composed crop is square, both copies of the photograph are
    # 2:3. If the route ever stops matching again, the board quietly falls back
    # to the round's own crop and the composition is a lie — fail loudly
    # instead. The size is also proof of WHICH copy answered: a square smaller
    # than the composed side means the low-resolution round image got there
    # first and the hero would ship soft.
    got = page.evaluate("""() => new Promise(res => { const i = new Image();
        i.onload = () => res([i.naturalWidth, i.naturalHeight]);
        i.onerror = () => res(null);
        i.src = getComputedStyle(document.querySelector('#rv-frame'))
                  .backgroundImage.slice(5, -2); })""")
    want = Image.open(io.BytesIO(image_png)).width
    assert got and got[0] == got[1] == want, (
        "the board is not showing the composed crop (image is %s, expected "
        "%dpx square) — the image route did not take, or an older/smaller copy "
        "of the photograph answered first" % (got, want))
    # #rv-frame is min(80vw, 40dvh): pin it so every candidate is identical.
    # It is border-box, so the element carries its 3px ink border on top of the
    # grid — pin the outer width and the scrap grid inside lands on exactly
    # GRID_CSS_PX, which is what keeps the 2x2 crop a whole number of pixels.
    page.evaluate("w => { const f = document.querySelector('#rv-frame');"
                  " f.style.width = w + 'px'; f.style.transition = 'none'; }",
                  GRID_CSS_PX + 2 * FRAME_BORDER_PX)
    page.wait_for_timeout(600)


def quadrant(png, start):
    """The 2x2 block of a nine-square board whose top-left square is `start`.

    A straight pixel crop of the browser's own render — the hero must not
    contain one redrawn or resampled scrap edge.
    """
    assert start in (0, 1, 3, 4), (
        "start tile %d has no 2x2 block below-and-right of it; the opening "
        "scrap must be tile 0, 1, 3 or 4" % start)
    im = Image.open(io.BytesIO(png)).convert("RGB")
    assert im.width == im.height == 3 * TILE_DEVICE_PX, (
        "board render is %s, expected %d square — the 2x2 crop would land off "
        "the scrap edges" % (im.size, 3 * TILE_DEVICE_PX))
    left, top = (start % 3) * TILE_DEVICE_PX, (start // 3) * TILE_DEVICE_PX
    cut = im.crop((left, top, left + 2 * TILE_DEVICE_PX, top + 2 * TILE_DEVICE_PX))
    buf = io.BytesIO()
    cut.save(buf, "PNG")
    return buf.getvalue()


def collect(p, base, manifest_json):
    shots = {}
    browser = p.chromium.launch()
    try:
        for name, (x, y, side, start, _desc) in COMPOSITIONS.items():
            # service_workers="block": sw.js claims the page a second or two
            # into the visit and then answers the round's image request
            # itself, out of reach of page.route — which is exactly how the
            # first pass silently photographed the uncropped original. The
            # app registers the worker inside a .catch(), so blocking it
            # changes nothing else about the run.
            ctx = browser.new_context(
                viewport={"width": 700, "height": int(GRID_CSS_PX / 0.4) + 260},
                device_scale_factor=DEVICE_SCALE, service_workers="block")
            page = ctx.new_page()
            open_board(page, base, manifest_json, pinned_pool(start),
                       cropped_png(x, y, side))
            torn = page.evaluate(
                "[...document.querySelectorAll('#rv-scraps .df-scrap')]"
                ".flatMap((el, i) => el.classList.contains('torn') ? [i] : [])")
            assert torn == [start], "expected only tile %d open, got %s" % (start, torn)
            board = page.locator("#rv-scraps").screenshot()
            shots[name] = (board, quadrant(board, start))
            ctx.close()
    finally:
        browser.close()
    return shots


def contact_sheet(shots, path):
    """Every candidate as it would ship (the 2x2) over the board it came from."""
    from PIL import ImageDraw
    tiles = list(shots.items())
    cell, pad, cap = 300, 14, 24
    cols = min(4, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    row_h = cell + cap + cell * 2 // 3 + cap + pad
    sheet = Image.new("RGB", (cols * (cell + pad) + pad, rows * row_h + pad),
                      (242, 239, 230))
    draw = ImageDraw.Draw(sheet)
    for n, (name, (board, cut)) in enumerate(tiles):
        x = pad + (n % cols) * (cell + pad)
        y = pad + (n // cols) * row_h
        big = Image.open(io.BytesIO(cut)).convert("RGB").resize((cell, cell), Image.LANCZOS)
        sheet.paste(big, (x, y))
        draw.text((x + 2, y + cell + 6), name + "  (ships)", fill=(11, 11, 11))
        small = cell * 2 // 3
        src = Image.open(io.BytesIO(board)).convert("RGB").resize((small, small), Image.LANCZOS)
        sheet.paste(src, (x, y + cell + cap))
        draw.text((x + 2, y + cell + cap + small + 6), "  from this board", fill=(90, 90, 90))
    sheet.save(path)
    return path


# The hero is the one picture a newcomer judges the product by, so it is
# encoded for the eye and not for the byte count. q94 measures 47.3 dB PSNR
# against the raw render — past the point where a difference is visible — and
# lands near 57 KB, well inside the 80 KB the hero is allowed. q88 saved 20 KB
# and put visible mush in the paper grain and along the dashed tear lines,
# which are precisely the details that make the board look like a real object.
WEBP_QUALITY = 94


def write_webp(png, path, width=None):
    """WEBP of the crop. At the shipping size this resamples nothing: the
    render is already 1 device pixel per asset pixel."""
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if width and width != im.width:
        im = im.resize((width, width), Image.LANCZOS)
    im.save(path, "WEBP", quality=WEBP_QUALITY, method=6)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick", choices=sorted(COMPOSITIONS), help="composition to ship")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    manifest_json = pinned_manifest()
    with H.server() as base:
        with sync_playwright() as p:
            shots = collect(p, base, manifest_json)

    for name, (board, cut) in shots.items():
        # Both halves of the evidence: the 2x2 exactly as it would ship, and
        # the whole nine-square board it was cut out of.
        with open(os.path.join(OUT_DIR, "%s-board.png" % name), "wb") as f:
            f.write(board)
        with open(os.path.join(OUT_DIR, "%s-full.png" % name), "wb") as f:
            f.write(cut)
        write_webp(cut, os.path.join(OUT_DIR, "%s.webp" % name))
        print("%-20s %s" % (name, COMPOSITIONS[name][4]))
    print("contact sheet:", contact_sheet(shots, os.path.join(OUT_DIR, "_sheet.png")))

    if args.pick:
        write_webp(shots[args.pick][1], HERO_PATH)
        print("hero written:", HERO_PATH,
              "(%s, %dpx, %.0f KB)"
              % (args.pick, 2 * TILE_DEVICE_PX, os.path.getsize(HERO_PATH) / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
