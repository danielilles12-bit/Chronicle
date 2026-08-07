#!/usr/bin/env python3
"""Photograph the REAL tear board with candidate paper-scrap CSS applied.

MOCKUP HARNESS — nothing this writes is served. It exists so the paper-scraps
art direction is argued from renders of the actual game rather than from
paintings of it: every picture below is Chromium's own output, on a real
board, with real adjacency, real `tearable`/`locked` states and the real
tear transition. The only thing injected is a stylesheet.

  python3 tools/mockup_scraps.py                  # everything
  python3 tools/mockup_scraps.py --only 1 3       # just those candidates

Candidates (design-reviews/paper-scraps-2026-08-07/css/, cumulative — 2 is
the delta on 1, 3 is the delta on 2, exactly as the patch files apply):

  0  current      untouched baseline
  1  cheap-80     one printer's mark instead of nine watermarks; nine paper
                  shades, grain angles, dot offsets and rotations; hard ink
                  shadow + reversed paint order
  2  printed      + one faint composition printed across the whole cover,
                  divided by the nine scraps (print furniture only)
  3  stretch      + ragged edges, magenta underside, lifted curling corner

Two subjects, both `reserve: true` in the live pools (out of rotation, so no
mockup can leak an unaired answer): van-gogh-self for Face Value and
olmec-colossal-head for Relic. Same subject across all four candidates, so
the comparison is honest.

Three states per candidate per game:
  open   the board as a round actually opens — one scrap torn by the game,
         its neighbours dashed (`tearable`), the other six `locked`
  mid     four more scraps torn along a legal adjacency path
  deny    a blocked tap: the shake at its extreme, plus the reduced-motion
          held outline, so both readings can be checked against the paper

Everything lands in design-reviews/paper-scraps-2026-08-07/renders/.
"""
import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests"))

from PIL import Image, ImageDraw                 # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

import helpers as H                              # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
REVIEW = os.path.join(ROOT, "design-reviews", "paper-scraps-2026-08-07")
CSS_DIR = os.path.join(REVIEW, "css")
OUT = os.path.join(REVIEW, "renders")

# The board's real size in the installed app: #rv-frame is min(80vw, 40dvh),
# and at 390x844 (iPhone 13, no browser chrome) 80vw wins -> 312 CSS px of
# grid inside a 3px ink border. Rendered at device pixel ratio 3 like the
# phone does, then resampled down for the two deliverable sizes.
VIEWPORT = {"width": 390, "height": 844}
DPR = 3
FRAME_CSS_PX = 312          # border-box: 306 of grid inside a 3px ink border

PIN_EDITION = 60            # any aired edition; the manifest is rewritten in flight
SUBJECTS = {"who": "van-gogh-self", "what": "olmec-colossal-head"}
POOL_FILE = {"who": "reveal-who.json", "what": "reveal-what.json"}
GAME_LABEL = {"who": "Face Value", "what": "Relic"}

CANDIDATES = [
    ("0-current", [], "current"),
    ("1-cheap-80", ["candidate-1-cheap-80.css"], "the cheap 80%"),
    ("2-printed-sheet", ["candidate-1-cheap-80.css",
                         "candidate-2-printed-sheet.css"], "one printed sheet"),
    ("3-stretch", ["candidate-1-cheap-80.css",
                   "candidate-2-printed-sheet.css",
                   "candidate-3-stretch.css"], "the stretch"),
]

# Mid-game = four more tears, each of them a legal one: at every step the
# harness reads which scraps the GAME says are tearable and takes the one
# nearest the middle of the board, the way a player heading for the face
# does. Nothing is forced, so the state is one a player could have reached.
MID_TEARS = 4


def pinned_manifest():
    with open(os.path.join(ROOT, "data", "editions.json"), encoding="utf-8") as f:
        man = json.load(f)
    ed = man["editions"][str(PIN_EDITION)]
    ed["who"] = [SUBJECTS["who"]]
    ed["what"] = [SUBJECTS["what"]]
    return json.dumps(man)


def css_for(files):
    out = []
    for name in files:
        with open(os.path.join(CSS_DIR, name), encoding="utf-8") as f:
            out.append(f.read())
    return "\n".join(out)


def open_round(page, base, game, manifest_json):
    page.route("**/data/editions.json*",
               lambda r: r.fulfill(status=200, content_type="application/json",
                                   body=manifest_json))
    H.boot(page, base, dailydate=H.edition_date(PIN_EDITION))
    # The four hero cards are regulars' furniture: a fresh profile gets the
    # stranger's single CTA instead, and that CTA only opens Face Value. One
    # seeded THREAD completion (a game these renders never touch) plus a
    # reload puts both hero cards on screen.
    H.seed_completion(page, "thread", PIN_EDITION - 1, score=80, detail=[])
    H.boot(page, base, dailydate=H.edition_date(PIN_EDITION))
    H.open_daily(page, game)
    # Relic still shows its rules card first and defers the board behind that
    # tap (Face Value teaches by doing and skips it), so the intro has to be
    # cleared BEFORE waiting on the view.
    H.dismiss_intro(page)
    page.wait_for_selector("#view-reveal:not([hidden])")
    page.wait_for_function(
        "__CHRONICLE_TEST__.revealRound && __CHRONICLE_TEST__.revealRound.id === '%s'"
        % SUBJECTS[game])
    page.wait_for_function(
        "getComputedStyle(document.querySelector('#rv-frame')).backgroundImage"
        ".includes('%s')" % SUBJECTS[game])
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)


def scrap_states(page):
    return page.evaluate("""() => {
      const out = {torn: [], tearable: [], locked: []};
      document.querySelectorAll('#rv-scraps .df-scrap').forEach(el => {
        const i = +el.dataset.i;
        if (el.classList.contains('torn')) out.torn.push(i);
        else if (el.classList.contains('tearable')) out.tearable.push(i);
        if (el.classList.contains('locked')) out.locked.push(i);
      });
      return out;
    }""")


def shoot(page):
    """The frame exactly as it sits on the phone, at 3x device pixels."""
    return page.locator("#rv-frame").screenshot()


def tear_inward(page, n):
    """Tear via the game's own tearScrap — adjacency and scoring untouched."""
    for _ in range(n):
        options = scrap_states(page)["tearable"]
        if not options:
            break
        nearest = min(options, key=lambda i: abs(i // 3 - 1) + abs(i % 3 - 1))
        page.evaluate("i => __CHRONICLE_TEST__.revealDebug.tear(i)", nearest)
        page.wait_for_timeout(340)   # let the .28s tear transition finish


def deny_frames(page):
    """The blocked tap, in both readings.

    The shake is a .28s animation, so the moving version is frozen at the
    keyframe's extreme rather than caught mid-flight (same declaration the
    animation applies at 30%). The reduced-motion version is the real thing:
    .deny-static is added on a JS timer and simply held.
    """
    st = scrap_states(page)
    victim = st["locked"][0] if st["locked"] else st["tearable"][0]
    page.add_style_tag(content=".df-scrap.deny { animation: none !important;"
                               " translate: -5px 0 !important; }")
    page.evaluate("i => document.querySelector('#rv-scraps [data-i=\"'+i+'\"]')"
                  ".classList.add('deny')", victim)
    page.wait_for_timeout(120)
    shake = shoot(page)
    page.evaluate("i => document.querySelector('#rv-scraps [data-i=\"'+i+'\"]')"
                  ".classList.add('deny-static')", victim)
    # .deny-static only paints under a reduced-motion media query, so force
    # the rule on for the still rather than relaunching the whole context.
    page.add_style_tag(content=".df-scrap.deny-static { outline: 3px solid"
                               " var(--ch-gold) !important; outline-offset: -3px; }")
    page.wait_for_timeout(120)
    held = shoot(page)
    return shake, held, victim


def resize(png, px):
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if im.width != px:
        im = im.resize((px, px), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def write(png, name, px):
    """Individual renders ship as WEBP at quality 95.

    Losslessly these are ~24 MB of dot-textured cream paper for a review that
    will be looked at once; at q95 the same 70 pictures are about a tenth of
    that and nothing visible survives the difference. The contact sheets stay
    PNG — they carry label text.
    """
    path = os.path.join(OUT, name)
    im = Image.open(io.BytesIO(resize(png, px))).convert("RGB")
    im.save(path, "WEBP", quality=95, method=6)
    return path


def run_candidate(p, base, key, files, game, manifest_json):
    """One candidate, one game: open state, mid state, both deny readings."""
    browser = p.chromium.launch()
    opts = dict(p.devices["iPhone 13"])
    opts.update(viewport=VIEWPORT, device_scale_factor=DPR,
                service_workers="block")
    ctx = browser.new_context(**opts)
    ctx.add_init_script(H.GC_STUB)
    css = css_for(files)
    if css:
        ctx.add_init_script(
            "window.addEventListener('DOMContentLoaded', () => {"
            " const s = document.createElement('style');"
            " s.id = 'mockup-scraps'; s.textContent = %s;"
            " document.head.appendChild(s); });" % json.dumps(css))
    page = ctx.new_page()
    try:
        open_round(page, base, game, manifest_json)
        got = page.evaluate(
            "Math.round(document.querySelector('#rv-frame')"
            ".getBoundingClientRect().width)")
        assert got == FRAME_CSS_PX, (
            "frame is %spx, expected %dpx — the renders would not be at phone "
            "size" % (got, FRAME_CSS_PX))
        if css:
            assert page.evaluate("!!document.getElementById('mockup-scraps')"), \
                "candidate stylesheet did not attach"
        states = {"open": scrap_states(page)}
        shots = {"open": shoot(page)}
        shake, held, victim = deny_frames(page)
        shots["deny-shake"], shots["deny-held"] = shake, held
        page.evaluate("document.querySelector('#rv-scraps [data-i=\"'+%d+'\"]')"
                      ".classList.remove('deny','deny-static')" % victim)
        # drop the two stills' helper styles before the mid-game shot
        page.evaluate("""() => [...document.querySelectorAll('style')]
            .filter(s => s.textContent.includes('.df-scrap.deny'))
            .forEach(s => s.remove())""")
        tear_inward(page, MID_TEARS)
        states["mid"] = scrap_states(page)
        shots["mid"] = shoot(page)
        # a whole-phone shot for context, once per candidate (Face Value only)
        if game == "who":
            shots["phone"] = page.locator("#view-reveal").screenshot()
        return shots, states, victim
    finally:
        browser.close()


LABEL_H = 40


def contact_sheet(cells, path, title, cell_px=300):
    """current | 1 | 2 | 3 across, one row per state."""
    rows = list(cells)                      # [(row label, [(col label, png)])]
    cols = max(len(r[1]) for r in rows)
    pad, head = 16, 46
    w = pad + cols * (cell_px + pad)
    h = head + pad + len(rows) * (cell_px + LABEL_H + pad)
    sheet = Image.new("RGB", (w, h), (242, 239, 230))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 14), title, fill=(11, 11, 11))
    for r, (rlabel, row) in enumerate(rows):
        y = head + pad + r * (cell_px + LABEL_H + pad)
        for c, (clabel, png) in enumerate(row):
            x = pad + c * (cell_px + pad)
            im = Image.open(io.BytesIO(png)).convert("RGB").resize(
                (cell_px, cell_px), Image.LANCZOS)
            sheet.paste(im, (x, y))
            d.text((x + 2, y + cell_px + 6), "%s" % clabel, fill=(11, 11, 11))
            d.text((x + 2, y + cell_px + 20), rlabel, fill=(110, 110, 110))
    sheet.save(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None,
                    help="candidate keys to render (0 1 2 3)")
    args = ap.parse_args()

    picked = [c for c in CANDIDATES
              if args.only is None or c[0][0] in args.only or c[0] in args.only]
    os.makedirs(OUT, exist_ok=True)
    manifest_json = pinned_manifest()

    made, report = [], []
    with H.server() as base:
        with sync_playwright() as p:
            store = {}
            for key, files, blurb in picked:
                for game in ("who", "what"):
                    shots, states, victim = run_candidate(
                        p, base, key, files, game, manifest_json)
                    store[(key, game)] = shots
                    report.append((key, game, states, victim))
                    for state, png in shots.items():
                        if state == "phone":
                            made.append(write(png, "%s_%s_phone.webp" % (key, game),
                                              Image.open(io.BytesIO(png)).width))
                            continue
                        made.append(write(
                            png, "%s_%s_%s_1x-phone-size.webp" % (key, game, state),
                            FRAME_CSS_PX))
                        made.append(write(
                            png, "%s_%s_%s_2x.webp" % (key, game, state),
                            FRAME_CSS_PX * 2))
                    print("rendered %-16s %-4s  %s" % (key, game, blurb))

    keys = [k for k, _f, _b in picked]
    for game in ("who", "what"):
        rows = []
        for state, rlabel in (("open", "opening state — 1 torn by the game"),
                              ("mid", "mid-game — 5 torn"),
                              ("deny-shake", "blocked tap (shake, held at its extreme)"),
                              ("deny-held", "blocked tap (reduced motion: held outline)")):
            row = [(k, store[(k, game)][state]) for k in keys
                   if (k, game) in store]
            rows.append((rlabel, row))
        path = os.path.join(OUT, "_contact-sheet_%s.png" % game)
        contact_sheet(rows, path,
                      "Yesternerd paper scraps - %s (%s) - board at 300px"
                      % (GAME_LABEL[game], SUBJECTS[game]))
        made.append(path)
        print("contact sheet:", path)

    print("\nscrap states seen (proof the mechanic still reads):")
    for key, game, states, victim in report:
        print("  %-16s %-4s open: torn=%s tearable=%s locked=%s | "
              "mid: torn=%s | deny on %d"
              % (key, game, states["open"]["torn"], states["open"]["tearable"],
                 states["open"]["locked"], states["mid"]["torn"], victim))
    print("\n%d files in %s" % (len(made), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
