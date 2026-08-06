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
  * `start`. A real curated field the pipeline already supports (see
    startScrap in js/revealgame.js): it pins the scrap the GAME opens on the
    house. Nothing is torn by hand, so the board is a genuine opening state.

Both the pinned edition and the crop are injected as Playwright routes —
never written to disk. The manifest belongs to the schedule, not to marketing.

The subject is out of rotation (`"reserve": true` in data/reveal-who.json —
the live pool, not the legacy data/reveal.json), so the face on permanent
display can never also be a live puzzle.

    python3 tools/make_demo_shot.py                     # all candidates
    python3 tools/make_demo_shot.py --pick centre-eye   # write the chosen one

Candidates land in tools/out/demo-candidates/ (never served); --pick saves the
finished hero to assets/brand/demo-facevalue.webp.
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
SOURCE = os.path.join(ROOT, "assets", "img", "frida-kahlo.jpg")

SUBJECT = "frida-kahlo"
# Any aired edition works — the manifest is rewritten in flight so the pinned
# subject is the whole round list, which makes it round 1 every time.
PIN_EDITION = 22
FRAME_CSS_PX = 450          # rendered size of #rv-frame; x2 DPR = 900px shot
HERO_WIDTH = 720            # final asset width (hero image on a phone)

# Face landmarks in the 667x1000 source, measured off a gridded overlay:
#   unibrow  x 255-455, y 240-265      left eye  centre (305, 288)
#   right eye centre (420, 288)        face box  x 215-470, y 150-470
# A tile is one ninth of the board, so tile size = crop side / 3; a crop of
# ~450 makes one tile about a quarter of the face, which is the brief.
#
# name -> (crop x, crop y, crop side, start tile 0-8, what the open tile shows)
COMPOSITIONS = {
    "centre-eye": (82, 45, 450, 4,
                   "centre tile on brow + her right eye; face fills the board, "
                   "hair above and mouth below still covered"),
    "upper-eye": (82, 170, 450, 1,
                  "upper-centre tile on brow + her right eye, tighter on the "
                  "eyeline; forehead at the top edge"),
    "upper-eye-mirrored": (200, 170, 450, 1,
                           "upper-centre tile on brow + her left eye, face "
                           "shifted to the left of the board"),
    "centre-eye-tight": (112, 77, 400, 4,
                         "centre tile on brow + her right eye, zoomed in one "
                         "step further so the face crowds the frame"),
}
DEFAULT_PICK = "centre-eye"


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
    im = Image.open(SOURCE).convert("RGB").crop((x, y, x + side, y + side))
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
    # Guard: every composed crop is square, the shipped source is 534x800. If
    # the route ever stops matching again, the board quietly falls back to the
    # round's own crop and the composition is a lie — fail loudly instead.
    got = page.evaluate("""() => new Promise(res => { const i = new Image();
        i.onload = () => res([i.naturalWidth, i.naturalHeight]);
        i.onerror = () => res(null);
        i.src = getComputedStyle(document.querySelector('#rv-frame'))
                  .backgroundImage.slice(5, -2); })""")
    assert got and got[0] == got[1], (
        "the board is not showing the composed crop (image is %s) — the "
        "image route did not take" % (got,))
    # #rv-frame is min(80vw, 40dvh): pin it so every candidate is identical.
    page.evaluate("w => { const f = document.querySelector('#rv-frame');"
                  " f.style.width = w + 'px'; f.style.transition = 'none'; }",
                  FRAME_CSS_PX)
    page.wait_for_timeout(600)


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
                viewport={"width": 700, "height": int(FRAME_CSS_PX / 0.4) + 260},
                device_scale_factor=2, service_workers="block")
            page = ctx.new_page()
            open_board(page, base, manifest_json, pinned_pool(start),
                       cropped_png(x, y, side))
            torn = page.evaluate(
                "[...document.querySelectorAll('#rv-scraps .df-scrap')]"
                ".flatMap((el, i) => el.classList.contains('torn') ? [i] : [])")
            assert torn == [start], "expected only tile %d open, got %s" % (start, torn)
            shots[name] = page.locator("#rv-scraps").screenshot()
            ctx.close()
    finally:
        browser.close()
    return shots


def contact_sheet(shots, path):
    from PIL import ImageDraw
    tiles = list(shots.items())
    cell, pad, cap = 330, 14, 24
    cols = min(4, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB",
                      (cols * (cell + pad) + pad, rows * (cell + cap + pad) + pad),
                      (242, 239, 230))
    draw = ImageDraw.Draw(sheet)
    for n, (name, png) in enumerate(tiles):
        im = Image.open(io.BytesIO(png)).convert("RGB").resize((cell, cell), Image.LANCZOS)
        x = pad + (n % cols) * (cell + pad)
        y = pad + (n // cols) * (cell + cap + pad)
        sheet.paste(im, (x, y))
        draw.text((x + 2, y + cell + 6), name, fill=(11, 11, 11))
    sheet.save(path)
    return path


def write_webp(png, path, width):
    im = Image.open(io.BytesIO(png)).convert("RGB").resize((width, width), Image.LANCZOS)
    im.save(path, "WEBP", quality=88, method=6)
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

    for name, png in shots.items():
        # Candidates are written full-size AND at ship size, so what Daniel
        # picks from is what the page would actually show.
        with open(os.path.join(OUT_DIR, "%s-full.png" % name), "wb") as f:
            f.write(png)
        write_webp(png, os.path.join(OUT_DIR, "%s.webp" % name), HERO_WIDTH)
        print("%-20s %s" % (name, COMPOSITIONS[name][4]))
    print("contact sheet:", contact_sheet(shots, os.path.join(OUT_DIR, "_sheet.png")))

    if args.pick:
        write_webp(shots[args.pick], HERO_PATH, HERO_WIDTH)
        print("hero written:", HERO_PATH,
              "(%s, %.0f KB)" % (args.pick, os.path.getsize(HERO_PATH) / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
