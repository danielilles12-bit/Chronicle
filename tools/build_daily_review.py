#!/usr/bin/env python3
"""One-day review board — ten puzzles, one edition, five minutes to approve.

The 30-day / 300-round launch audit (build_launch_audit.py) worked but wore
Daniel out. From now on he reviews exactly one day at a time, the evening
before it airs: 3 Face Value + 3 Lifeline + 3 Relic + 1 Thread. This script
renders that single edition as one self-contained HTML file with everything
he needs on the page — nothing to look up elsewhere.

Reuses, verbatim where possible:
  - compile_editions.py           edition/pool loading, money_scrap/
                                   start_scrap geometry, haversine_km
  - build_launch_audit.py         the opening-scrap card shape
  - SCRATCH/build_picker.py       the clickable nine-cell opener grid,
                                   pink "M" money badge, "show whole
                                   picture" toggle, localStorage pattern,
                                   the export overlay (NOT clipboard/
                                   window.open — both are blocked in the
                                   sandboxed frame this gets published into)
  - js/mapgame.js                 the equirectangular projection used to
                                   plot birth/death pins (proj(): x=(lon+180)
                                   /360*1000, y=(90-lat)/180*500) and
                                   data/worldmap.json for the coastline

Output is written for direct Claude-Artifact publishing: no <!DOCTYPE>,
<html>, <head> or <body> — just <title>, <style>, markup, <script>.
Default output lands in tools/out/ — gitignored and CI-enforced (repo_checks
.py) because it shows UNAIRED answers and Pages serves the whole repo.

Usage:
  python3 tools/build_daily_review.py --edition 42
  python3 tools/build_daily_review.py --date 2026-08-10
  python3 tools/build_daily_review.py --tomorrow          # default
  python3 tools/build_daily_review.py --tomorrow --out /some/path.html
"""
import argparse
import base64
import datetime
import html
import io
import json
import random
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compile_editions as C  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "tools/out"
GAME_LABEL = {"who": "Face Value", "map": "Lifeline",
              "what": "Relic", "thread": "Thread"}
IMG_MAX_EDGE = 700
GLYPH = {"yellow": "●", "green": "▲", "blue": "■", "purple": "✦"}

MAP_W, MAP_H = 1000, 500


def e(s):
    return html.escape(str(s if s is not None else ""), quote=True)


# --- date / edition resolution ----------------------------------------------
def resolve_edition(args, manifest):
    eds = manifest["editions"]
    if args.edition is not None:
        n = args.edition
    elif args.date:
        d = args.date
        n = None
        for k, v in eds.items():
            if v["date"] == d:
                n = int(k)
                break
        if n is None:
            print(f"build_daily_review: no edition in the manifest airs on "
                  f"{d} — run compile_editions.py propose/approve first",
                  file=sys.stderr)
            return None
    else:  # --tomorrow (default)
        n = C.today_index() + 1
    if str(n) not in eds:
        print(f"build_daily_review: edition {n} is not in the manifest — "
              f"run compile_editions.py propose/approve first", file=sys.stderr)
        return None
    return n


# --- revealgame.js geometry, ported verbatim (matches build_launch_audit.py
# and SCRATCH/build_picker.py) ------------------------------------------------
def money_scrap(item):
    c = min(2, int(item["fx"] * 3))
    r = min(2, int(item["fy"] * 3))
    return r * 3 + c


def start_scrap(item):
    m = money_scrap(item)
    override = item.get("start")
    if isinstance(override, int) and 0 <= override <= 8:
        return override
    mr, mc = divmod(m, 3)
    best, bd = 0, -1
    for i in (0, 2, 6, 8, 1, 3, 5, 7, 4):      # corners first, deterministic
        d = abs(i // 3 - mr) + abs(i % 3 - mc)
        if d > bd:
            bd, best = d, i
    return best


# --- image embedding: native size reported, then downscaled to 700px long
# edge for embedding (the scrap geometry is fractional, so a small preview
# maps exactly onto the full-size original) -----------------------------------
_img_cache = {}


def embed_image(item):
    key = item["id"]
    if key in _img_cache:
        return _img_cache[key]
    path = ROOT / item["img"]
    if not path.exists():
        print(f"ERROR: image missing for {key}: {path}", file=sys.stderr)
        sys.exit(1)
    with Image.open(path) as im:
        native_w, native_h = im.size
        im = im.convert("RGB")
        scale = min(1.0, IMG_MAX_EDGE / max(native_w, native_h))
        if scale < 1.0:
            im = im.resize((max(1, round(native_w * scale)),
                             max(1, round(native_h * scale))), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=86)
        uri = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    result = (uri, native_w, native_h)
    _img_cache[key] = result
    return result


def rights_line(item):
    author = item.get("image_author") or item.get("attribution") or "unknown"
    lic = item.get("image_license") or item.get("license") or "unknown licence"
    return f"{author} · {lic}"


# --- Lifeline mini map (js/mapgame.js proj(), ported verbatim) ---------------
def proj(lon, lat):
    return ((lon + 180) / 360 * MAP_W, (90 - lat) / 180 * MAP_H)


def map_svg(fig, uid):
    b = proj(fig["birth"]["lon"], fig["birth"]["lat"])
    d = proj(fig["death"]["lon"], fig["death"]["lat"])
    x0 = min(b[0], d[0]) - 60
    x1 = max(b[0], d[0]) + 60
    y0 = min(b[1], d[1]) - 45
    y1 = max(b[1], d[1]) + 45
    w = max(x1 - x0, 160)
    h = max(y1 - y0, 100)
    # keep roughly 2:1 so the coastline doesn't look squashed
    if w / h < 1.8:
        w = h * 1.8
    x0 = min(b[0], d[0]) - (w - abs(b[0] - d[0])) / 2
    y0 = min(b[1], d[1]) - (h - abs(b[1] - d[1])) / 2
    vb = f"{x0:.1f} {y0:.1f} {w:.1f} {h:.1f}"
    return f"""<svg class="mini-map" viewBox="{vb}" role="img"
    aria-label="Born {e(fig['birth']['place'])}, died {e(fig['death']['place'])}">
  <rect x="{x0 - 200:.1f}" y="{y0 - 200:.1f}" width="{w + 400:.1f}" height="{h + 400:.1f}" class="sea"></rect>
  <use href="#worldland" class="land"></use>
  <line x1="{b[0]:.1f}" y1="{b[1]:.1f}" x2="{d[0]:.1f}" y2="{d[1]:.1f}" class="journey-line"></line>
  <circle cx="{b[0]:.1f}" cy="{b[1]:.1f}" r="6" class="mk-birth"></circle>
  <circle cx="{d[0]:.1f}" cy="{d[1]:.1f}" r="9" class="mk-death-ring"></circle>
  <circle cx="{d[0]:.1f}" cy="{d[1]:.1f}" r="3.2" class="mk-death"></circle>
</svg>"""


# --- card builders -------------------------------------------------------------
def scrap_window(item, key, size=230):
    money = money_scrap(item)
    start = start_scrap(item)
    uri, nat_w, nat_h = embed_image(item)
    cells = "".join(
        f'<button type="button" class="cell{" money" if i == money else ""}" '
        f'data-i="{i}" aria-label="Open scrap {i + 1} of 9'
        f'{" — this is the money shot" if i == money else ""}"></button>'
        for i in range(9)
    )
    win = f"""<div class="scrapwrap opener" style="width:{size}px;flex:0 0 {size}px"
  data-key="{e(key)}" data-orig="{start}" data-money="{money}">
  <div class="window" style="width:{size}px;height:{size}px;background-image:url('{uri}');
       background-position:{item['fx'] * 100:.1f}% {item['fy'] * 100:.1f}%">
    <div class="grid">{cells}</div>
  </div>
  <p class="startline"></p>
  <label class="peek"><input type="checkbox" class="revealall"> show whole picture</label>
</div>"""
    return win, nat_w, nat_h


def image_card(r, key, n, game_key):
    win, nat_w, nat_h = scrap_window(r, key)
    variants = ", ".join(r.get("variants", [])) or "—"
    correct = r["name"]
    d1, d2 = (r.get("mcq") or ["", ""])[:2] + [""] * max(0, 2 - len(r.get("mcq") or []))
    return f"""
<article class="card" data-key="{e(key)}" data-n="{n}" data-game="{e(GAME_LABEL[game_key])}"
  data-name="{e(r['name'])}">
  <header class="cardhead">
    <span class="numpill">{n}</span>
    <span class="gamepill">{e(GAME_LABEL[game_key])}</span>
    <span class="tier t-{e(r['difficulty'])}">{e(r['difficulty'])}</span>
  </header>
  <div class="cardbody">
    {win}
    <div class="meta">
      <h3>{e(r['name'])}</h3>
      <p class="variants">accepts: {e(variants)}</p>
      <label class="fieldlabel">Blurb / fun fact</label>
      <textarea class="edit blurb-edit" data-key="{e(key)}" data-field="blurb"
        rows="3">{e(r.get('blurb', ''))}</textarea>
      <label class="fieldlabel">3-choice clue</label>
      <div class="mcqrow">
        <label class="mcqfield"><span>correct</span>
          <input type="text" class="edit mcq-edit" data-key="{e(key)}" data-field="mcqCorrect"
            value="{e(correct)}"></label>
        <label class="mcqfield"><span>distractor</span>
          <input type="text" class="edit mcq-edit" data-key="{e(key)}" data-field="mcq0"
            value="{e(d1)}"></label>
        <label class="mcqfield"><span>distractor</span>
          <input type="text" class="edit mcq-edit" data-key="{e(key)}" data-field="mcq1"
            value="{e(d2)}"></label>
      </div>
      <p class="imginfo">image {nat_w}×{nat_h}px · {e(rights_line(r))}</p>
      {decision_controls(key)}
    </div>
  </div>
</article>"""


def lifeline_card(r, key, n):
    fig = r
    km = round(C.haversine_km(fig["birth"], fig["death"]))
    variants = ", ".join(fig.get("variants", [])) or "—"
    correct = fig["name"]
    d1, d2 = (fig.get("mcq") or ["", ""])[:2] + [""] * max(0, 2 - len(fig.get("mcq") or []))
    return f"""
<article class="card" data-key="{e(key)}" data-n="{n}" data-game="Lifeline"
  data-name="{e(fig['name'])}">
  <header class="cardhead">
    <span class="numpill">{n}</span>
    <span class="gamepill">Lifeline</span>
    <span class="tier t-{e(fig['difficulty'])}">{e(fig['difficulty'])}</span>
  </header>
  <div class="cardbody">
    <div class="mapwrap">
      {map_svg(fig, key)}
      <div class="journeytext">
        <p class="leg"><span class="dot born"></span><b>{fig['birth']['year']}</b>
          {e(fig['birth']['place'])}</p>
        <p class="legdist">{km:,} km</p>
        <p class="leg"><span class="dot died"></span><b>{fig['death']['year']}</b>
          {e(fig['death']['place'])}</p>
      </div>
    </div>
    <div class="meta">
      <h3>{e(fig['name'])}</h3>
      <p class="variants">accepts: {e(variants)}</p>
      <p class="occline">claim to fame (as the player sees it): {e(fig.get('occupation', ''))}</p>
      <label class="fieldlabel">Fact</label>
      <textarea class="edit blurb-edit" data-key="{e(key)}" data-field="blurb"
        rows="3">{e(fig.get('fact', ''))}</textarea>
      <label class="fieldlabel">3-choice clue</label>
      <div class="mcqrow">
        <label class="mcqfield"><span>correct</span>
          <input type="text" class="edit mcq-edit" data-key="{e(key)}" data-field="mcqCorrect"
            value="{e(correct)}"></label>
        <label class="mcqfield"><span>distractor</span>
          <input type="text" class="edit mcq-edit" data-key="{e(key)}" data-field="mcq0"
            value="{e(d1)}"></label>
        <label class="mcqfield"><span>distractor</span>
          <input type="text" class="edit mcq-edit" data-key="{e(key)}" data-field="mcq1"
            value="{e(d2)}"></label>
      </div>
      {decision_controls(key)}
    </div>
  </div>
</article>"""


def thread_card(r, key, n):
    groups = r.get("groups", [])
    solved = "".join(f"""
    <div class="tgroup g-{e(g.get('colour'))}">
      <div class="tlabelrow">
        <span class="tglyph">{GLYPH.get(g.get('colour'), '')}</span>
        <input type="text" class="edit label-edit" data-key="{e(key)}"
          data-field="label{i}" value="{e(g.get('label'))}">
      </div>
      <div class="tiles">{''.join(f'<span>{e(t)}</span>' for t in g.get('items', []))}</div>
    </div>""" for i, g in enumerate(groups))

    all_tiles = [t for g in groups for t in g.get("items", [])]
    rng = random.Random(r["id"])
    shuffled = all_tiles[:]
    rng.shuffle(shuffled)
    opener_tiles = "".join(f'<span>{e(t)}</span>' for t in shuffled)

    return f"""
<article class="card thread" data-key="{e(key)}" data-n="{n}" data-game="Thread"
  data-name="{e(r.get('title', r.get('id')))}">
  <header class="cardhead">
    <span class="numpill">{n}</span>
    <span class="gamepill">Thread</span>
    <span class="tier t-{e(r['difficulty'])}">{e(r['difficulty'])}</span>
  </header>
  <div class="cardbody wide">
    <h3>{e(r.get('title', ''))}</h3>
    <label class="fieldlabel">First seen — sixteen tiles, shuffled</label>
    <div class="openertiles">{opener_tiles}</div>
    <label class="fieldlabel">Solved — four groups</label>
    <div class="tgroups">{solved}</div>
    {decision_controls(key)}
  </div>
</article>"""


def decision_controls(key):
    return f"""
<div class="decision" data-key="{e(key)}">
  <div class="decisionbtns">
    <button type="button" class="decbtn approve" data-status="approve">Approve</button>
    <button type="button" class="decbtn flag" data-status="flag">Flag</button>
  </div>
  <textarea class="edit note-edit" data-key="{e(key)}" data-field="note" rows="2"
    placeholder="Notes on this round…"></textarea>
</div>"""


# --- data collection -----------------------------------------------------------
def collect(n, manifest):
    e_ = manifest["editions"][str(n)]
    pools = C.load_pools()
    idx = {g: {x["id"]: x for x in pools[g]} for g in C.GAMES}
    d = datetime.date.fromisoformat(e_["date"])
    day = {"ed": n, "date": e_["date"], "weekday": C.WEEKDAY_NAMES[d.weekday()],
           "nice": d.strftime("%-d %B %Y"), "games": {}}
    for g in ("who", "map", "what", "thread"):
        rounds = []
        for iid in e_[g]:
            it = idx[g].get(iid)
            if not it:
                print(f"ERROR: {g}.{iid} is in edition {n} but missing from "
                      f"its pool", file=sys.stderr)
                sys.exit(1)
            rounds.append(it)
        day["games"][g] = rounds
    return day


# --- page assembly ---------------------------------------------------------
CSS = r"""
:root{
  --paper:#F2EFE6;--cream:#FFFFFF;--ink:#0B0B0B;--muted:#6B675C;--soft:#CFC9B8;
  --pink:#D6008F;--red:#E02020;--blue:#0093B8;--yellow:#FFE93B;--green:#3FA84A;
  --t-yellow:#FFE93B;--t-green:#4CDB86;--t-blue:#2FC9E8;--t-purple:#C79BFF;
  --ui:'Helvetica Neue',Arial,sans-serif;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--ui);
  font-size:15px;line-height:1.5;-webkit-font-smoothing:antialiased;
  overflow-x:hidden}
a{color:var(--pink)}
:focus-visible{outline:3px solid var(--blue);outline-offset:2px}

.top{position:sticky;top:0;z-index:30;background:var(--ink);color:var(--paper);
  padding:10px 16px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.top h1{font-size:14px;margin:0;letter-spacing:.02em;text-transform:uppercase}
.top .sp{flex:1}
.top button{font:inherit;font-size:13px;font-weight:700;padding:8px 14px;
  border:2px solid var(--paper);background:var(--yellow);color:var(--ink);
  cursor:pointer;border-radius:2px}
.count{font-size:12.5px;color:#D8D4C6;white-space:nowrap;font-weight:700}

.masthead{max-width:900px;margin:22px auto 6px;padding:0 16px}
.masthead .ed{font-size:12px;font-weight:800;text-transform:uppercase;
  letter-spacing:.1em;color:var(--muted)}
.masthead h1{font-size:26px;margin:.15em 0;line-height:1.15}
.masthead p{margin:0;font-size:13.5px;color:var(--muted)}

.wrap{max-width:900px;margin:0 auto;padding:10px 16px 140px}

.card{background:var(--cream);border:2px solid var(--ink);margin:0 0 22px;
  box-shadow:5px 5px 0 rgba(11,11,11,.14);scroll-margin-top:60px}
.card.thread{}

.cardhead{display:flex;align-items:center;gap:8px;flex-wrap:wrap;
  padding:10px 14px;border-bottom:2px solid var(--ink);background:#F7F5EE}
.numpill{font-size:11px;font-weight:800;background:var(--ink);color:var(--paper);
  padding:3px 8px;min-width:22px;text-align:center}
.gamepill{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
  border:1.5px solid var(--ink);padding:2px 8px}
.tier{display:inline-block;font-size:10px;font-weight:800;text-transform:uppercase;
  letter-spacing:.1em;padding:2px 7px;border:1.5px solid var(--ink)}
.t-easy{background:#4CDB86} .t-medium{background:var(--yellow)}
.t-hard{background:var(--pink);color:#fff;border-color:var(--pink)}

.cardbody{display:flex;gap:16px;padding:14px;flex-wrap:wrap}
.cardbody.wide{display:block}
.meta{flex:1;min-width:220px}
.meta h3{margin:2px 0 4px;font-size:19px}
.cardbody.wide h3{font-size:19px;margin:2px 0 10px}
.variants{margin:0 0 8px;font-size:12px;color:var(--muted)}
.occline{margin:0 0 8px;font-size:13px}

.fieldlabel{display:block;font-size:10.5px;font-weight:800;text-transform:uppercase;
  letter-spacing:.08em;color:var(--muted);margin:8px 0 4px}
textarea.edit,input.edit{width:100%;font:inherit;font-size:13px;padding:7px 9px;
  border:1.5px solid var(--soft);background:#FCFBF7;resize:vertical}
textarea.edit:focus,input.edit:focus{border-color:var(--pink);outline:2px solid var(--pink)}
textarea.edit.changed,input.edit.changed{border-color:var(--pink);background:#FFF8FC}
.mcqrow{display:flex;gap:8px;flex-wrap:wrap}
.mcqfield{flex:1 1 140px;font-size:11px;color:var(--muted)}
.mcqfield span{display:block;margin-bottom:2px}
.imginfo{margin:8px 0 0;font-size:11.5px;color:var(--muted)}

/* --- scrap window ------------------------------------------------------ */
.scrapwrap{display:block}
.window{position:relative;background-size:cover;background-color:#111;
  border:2px solid var(--ink)}
.grid{position:absolute;inset:0;display:grid;grid-template-columns:repeat(3,1fr);
  grid-template-rows:repeat(3,1fr)}
.cell{position:relative;display:block;width:100%;height:100%;margin:0;padding:0;
  border:0;font:inherit;background:#E9E4D3;box-shadow:inset 0 0 0 1px rgba(11,11,11,.18);
  cursor:pointer;transition:opacity .12s}
.cell:hover{opacity:.72}
.cell:focus-visible{outline:3px solid var(--blue);outline-offset:-3px;z-index:3}
.cell.open{background:transparent;box-shadow:inset 0 0 0 2px var(--pink)}
.window.all .cell{background:transparent;box-shadow:inset 0 0 0 1px rgba(11,11,11,.12)}
.window.all .cell.open{box-shadow:inset 0 0 0 2px var(--pink)}
.cell.money::after{content:'M';position:absolute;top:1px;right:1px;z-index:2;
  width:15px;height:13px;line-height:13px;text-align:center;font-size:9px;font-weight:800;
  color:#fff;background:var(--pink);box-shadow:0 0 0 1px rgba(255,255,255,.85);
  pointer-events:none}
.peek{display:block;font-size:11px;color:var(--muted);margin-top:6px;cursor:pointer}
.startline{margin:6px 0 0;font-size:11px;color:var(--muted);display:flex;gap:6px;
  align-items:center;flex-wrap:wrap;min-height:1.4em}
.startline b{color:var(--ink)}
.deflabel{font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
  color:var(--muted);border:1px solid var(--soft);padding:1px 5px}
.startline .reset{font:inherit;font-size:10.5px;padding:1px 6px;cursor:pointer;
  border:1px solid var(--soft);background:transparent;color:var(--ink)}
.startline .reset:hover{border-color:var(--ink)}

/* --- lifeline map ------------------------------------------------------- */
.mapwrap{width:230px;flex:0 0 230px}
.mini-map{width:230px;height:170px;display:block;border:2px solid var(--ink);
  background:#DCEBEF}
.sea{fill:#DCEBEF}
.land{fill:#F2EFE6;stroke:#B9C6C4;stroke-width:1}
.journey-line{stroke:var(--ink);stroke-width:1.4;stroke-dasharray:3 2}
.mk-birth{fill:var(--red)}
.mk-death{fill:var(--blue)}
.mk-death-ring{fill:none;stroke:var(--blue);stroke-width:1.6}
.journeytext{margin-top:8px;font-size:12.5px}
.leg{display:flex;gap:6px;align-items:baseline;margin:0}
.dot{width:9px;height:9px;border-radius:50%;flex:0 0 9px;display:inline-block}
.dot.born{background:var(--red)} .dot.died{background:var(--blue)}
.legdist{margin:4px 0 4px 15px;font-size:11px;color:var(--muted)}

/* --- thread -------------------------------------------------------------- */
.openertiles{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px}
.openertiles span{background:#E9E4D3;border:1px solid rgba(11,11,11,.3);
  padding:4px 9px;font-size:12.5px}
.tgroups{display:grid;gap:6px;margin:6px 0 4px}
.tgroup{border:1.5px solid var(--ink);padding:8px 10px}
.g-yellow{background:var(--t-yellow)} .g-green{background:var(--t-green)}
.g-blue{background:var(--t-blue)} .g-purple{background:var(--t-purple)}
.tlabelrow{display:flex;align-items:center;gap:6px}
.tglyph{opacity:.65;flex:0 0 auto}
.tlabelrow input.edit{background:rgba(255,255,255,.75);font-weight:800;font-size:12.5px;
  text-transform:uppercase;letter-spacing:.05em;border:1.5px solid transparent;padding:3px 6px}
.tlabelrow input.edit:focus,.tlabelrow input.edit.changed{border-color:var(--ink);
  background:#fff}
.tiles{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px}
.tiles span{background:rgba(255,255,255,.72);border:1px solid rgba(11,11,11,.35);
  padding:2px 7px;font-size:12.5px}

/* --- decision ------------------------------------------------------------ */
.decision{margin-top:12px;padding-top:10px;border-top:1px dashed var(--soft)}
.decisionbtns{display:flex;gap:8px;margin-bottom:8px}
.decbtn{font:inherit;font-size:12.5px;font-weight:800;text-transform:uppercase;
  letter-spacing:.05em;padding:7px 14px;border:2px solid var(--ink);background:#fff;
  cursor:pointer;color:var(--ink)}
.decbtn.approve.active{background:var(--green);color:#fff;border-color:var(--green)}
.decbtn.flag.active{background:var(--pink);color:#fff;border-color:var(--pink)}
.note-edit{min-height:2.4em}

#toast{position:fixed;left:50%;bottom:26px;transform:translateX(-50%);
  background:var(--ink);color:var(--paper);padding:10px 18px;font-size:13px;
  z-index:60;opacity:0;pointer-events:none;transition:opacity .2s}
#toast.on{opacity:1}

.overlay{position:fixed;inset:0;background:rgba(11,11,11,.72);z-index:100;
  display:none;align-items:center;justify-content:center;padding:20px}
.overlay.on{display:flex}
.overlaybox{background:var(--cream);border:2px solid var(--ink);max-width:640px;width:100%;
  padding:18px;box-shadow:6px 6px 0 rgba(11,11,11,.25)}
.overlaybox p{margin:0 0 10px;font-size:13.5px}
.overlaybox textarea{width:100%;height:320px;font:12.5px/1.5 ui-monospace,Menlo,monospace;
  padding:10px;border:1.5px solid var(--soft);resize:vertical}
.overlaybox button{margin-top:12px;font:inherit;font-size:13px;font-weight:700;padding:8px 16px;
  border:2px solid var(--ink);background:var(--yellow);cursor:pointer}

@media (max-width:640px){
  .cardbody{flex-direction:column}
  .scrapwrap,.window,.mapwrap,.mini-map{width:100% !important;flex:1 1 auto !important}
  .window{height:min(78vw,320px) !important}
  .mini-map{height:min(56vw,230px) !important}
}
"""


def build_js(edition_n):
    key = f"yn-daily-review-v1-ed{edition_n}"
    return r"""
const KEY='__KEY__';
const store=JSON.parse(localStorage.getItem(KEY)||'{}');
function rec(k){return store[k]||(store[k]={});}
function save(){localStorage.setItem(KEY,JSON.stringify(store));updateCount();}

function updateCount(){
  const cards=[...document.querySelectorAll('.card')];
  const n=cards.filter(c=>{
    const k=c.dataset.key; const s=store[k];
    return s&&s.status==='approve';
  }).length;
  document.getElementById('count').textContent=n+' of '+cards.length+' approved';
}

// --- opener (scrap-picking) windows -----------------------------------------
document.querySelectorAll('.opener').forEach(w=>{
  const key=w.dataset.key;
  if(!key) return;
  const orig=+w.dataset.orig;
  const cells=[...w.querySelectorAll('.cell')];
  const label=w.querySelector('.startline');
  function current(){
    const v=rec(key).opener;
    return (v===undefined||v===null)?orig:v;
  }
  function paint(){
    const cur=current();
    cells.forEach((c,i)=>c.classList.toggle('open',i===cur));
    const moved=(cur!==orig);
    if(label){
      label.innerHTML='opens on scrap <b>'+(cur+1)+'</b> of 9 '
        +(moved?'<button type="button" class="reset">reset</button>'
                :'<span class="deflabel">default</span>');
      if(moved){
        label.querySelector('.reset').addEventListener('click',ev=>{
          ev.preventDefault();
          delete rec(key).opener;
          save(); paint();
        });
      }
    }
  }
  cells.forEach((c,i)=>c.addEventListener('click',()=>{
    if(i===orig) delete rec(key).opener; else rec(key).opener=i;
    save(); paint();
  }));
  paint();
});

document.querySelectorAll('.revealall').forEach(cb=>{
  const win=cb.closest('.scrapwrap').querySelector('.window');
  cb.addEventListener('change',ev=>{ win.classList.toggle('all',ev.target.checked); });
});

// --- editable text fields (blurb/fact, mcq options, thread labels, notes) --
document.querySelectorAll('.edit').forEach(el=>{
  const k=el.dataset.key, f=el.dataset.field;
  const orig=el.tagName==='TEXTAREA'?el.textContent:el.value;
  el.dataset.orig=orig;
  const s=store[k];
  if(s&&s[f]!==undefined){
    el.value=s[f];
    el.classList.toggle('changed',s[f]!==orig);
  }
  el.addEventListener('input',()=>{
    const R=rec(k);
    if(el.value===el.dataset.orig) delete R[f]; else R[f]=el.value;
    el.classList.toggle('changed',el.value!==el.dataset.orig);
    save();
  });
});

// --- approve / flag ----------------------------------------------------------
document.querySelectorAll('.decision').forEach(d=>{
  const k=d.dataset.key;
  const btns=[...d.querySelectorAll('.decbtn')];
  function paint(){
    const st=(store[k]||{}).status;
    btns.forEach(b=>b.classList.toggle('active',b.dataset.status===st));
  }
  btns.forEach(b=>b.addEventListener('click',()=>{
    const R=rec(k);
    R.status=(R.status===b.dataset.status)?undefined:b.dataset.status;
    if(R.status===undefined) delete R.status;
    save(); paint();
  }));
  paint();
});

// --- export: rendered into a visible, focused, fully-selected textarea
// overlay — navigator.clipboard and window.open are both blocked in the
// sandboxed frame this page gets published into, so neither is the
// mechanism; a caught-and-ignored clipboard attempt is just a bonus. -------
function fieldLine(prefix, key, field, label){
  const s=store[key];
  if(s&&s[field]!==undefined) return prefix+label+' edited: "'+s[field].trim()+'"';
  return null;
}
function openerLine(card){
  const win=card.querySelector('.opener');
  if(!win) return null;
  const key=win.dataset.key, orig=+win.dataset.orig;
  const s=store[key];
  if(s&&s.opener!==undefined&&s.opener!==null&&s.opener!==orig){
    return 'opener moved to scrap '+(s.opener+1)+' of 9 (was '+(orig+1)+')';
  }
  return null;
}
function buildExport(){
  const now=new Date();
  const lines=['YESTERNERD — ONE-DAY REVIEW','Exported: '+now.toLocaleString(),''];
  document.querySelectorAll('.card').forEach(card=>{
    const k=card.dataset.key, s=store[k]||{};
    const game=card.dataset.game, name=card.dataset.name;
    const tag=s.status==='approve'?'[APPROVE]':s.status==='flag'?'[FLAG]   ':'[UNDECIDED]';
    let line=tag+' '+game+' · '+name;
    const extras=[];
    const op=openerLine(card);
    if(op) extras.push(op);
    if(s.blurb!==undefined){
      extras.push('blurb edited: "'+s.blurb.trim().replace(/\s+/g,' ')+'"');
    }
    const d0=card.querySelector('.mcq-edit[data-field="mcq0"]');
    const d1=card.querySelector('.mcq-edit[data-field="mcq1"]');
    const corrEl=card.querySelector('.mcq-edit[data-field="mcqCorrect"]');
    const mcqChanged=(s.mcq0!==undefined)||(s.mcq1!==undefined)||(s.mcqCorrect!==undefined);
    if(mcqChanged){
      const vals=[];
      if(corrEl && s.mcqCorrect!==undefined) vals.push(corrEl.value);
      if(d0) vals.push(d0.value);
      if(d1) vals.push(d1.value);
      extras.push('options edited: '+vals.join(', '));
    }
    const labelEdits=[];
    card.querySelectorAll('.label-edit').forEach((inp,i)=>{
      const f=inp.dataset.field;
      if(s[f]!==undefined) labelEdits.push('"'+inp.value+'"');
    });
    if(labelEdits.length) extras.push('group label'+(labelEdits.length>1?'s':'')+' edited: '+labelEdits.join(', '));
    extras.forEach(x=>{ line+=' — '+x; });
    if(s.note&&s.note.trim()) line+=' — "'+s.note.trim().replace(/\s+/g,' ')+'"';
    lines.push(line);
  });
  return lines.join('\n');
}
document.getElementById('copy').addEventListener('click',()=>{
  const text=buildExport();
  const ta=document.getElementById('exportText');
  ta.value=text;
  document.getElementById('exportOverlay').classList.add('on');
  ta.focus();
  ta.select();
  try{
    if(navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(text).catch(function(){});
    }
  }catch(err){}
});
document.getElementById('closeExport').addEventListener('click',()=>{
  document.getElementById('exportOverlay').classList.remove('on');
});
document.getElementById('exportOverlay').addEventListener('click',ev=>{
  if(ev.target.id==='exportOverlay') ev.target.classList.remove('on');
});

updateCount();
""".replace("__KEY__", key)


def render(day):
    order = [("who", "Face Value"), ("map", "Lifeline"),
             ("what", "Relic"), ("thread", "Thread")]
    cards = []
    n = 0
    world_land = json.loads((ROOT / "data/worldmap.json").read_text(encoding="utf-8"))["land"]
    for g, _label in order:
        for r in day["games"][g]:
            n += 1
            key = f"{g}.{r['id']}"
            if g == "thread":
                cards.append(thread_card(r, key, n))
            elif g == "map":
                cards.append(lifeline_card(r, key, n))
            else:
                cards.append(image_card(r, key, n, g))

    title = f"Yesternerd — {day['weekday']} {day['nice']}"
    body = f"""<title>{e(title)}</title>
<style>{CSS}</style>

<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <defs><path id="worldland" d="{world_land}"></path></defs>
</svg>

<div class="top">
  <h1>One-day review</h1>
  <span class="count" id="count">0 of 10 approved</span>
  <span class="sp"></span>
  <button type="button" id="copy">Copy decisions</button>
</div>

<div class="masthead">
  <div class="ed">Edition {day['ed']}</div>
  <h1>{e(day['weekday'])}, {e(day['nice'])}</h1>
  <p>10 puzzles — 3 Face Value, 3 Lifeline, 3 Relic, 1 Thread. Nothing is
  decided until you touch it: hit <b>Approve</b> or <b>Flag</b> on each card,
  edit anything that needs fixing right on the card, then <b>Copy decisions</b>
  for a complete instruction set.</p>
</div>

<div class="wrap">{''.join(cards)}</div>

<div id="toast"></div>
<div class="overlay" id="exportOverlay">
  <div class="overlaybox">
    <p>Everything below is already selected — press <b>Cmd+C</b> (or Ctrl+C) to
    copy, then paste it wherever you like.</p>
    <textarea id="exportText" readonly></textarea>
    <button type="button" id="closeExport">Close</button>
  </div>
</div>

<script>{build_js(day['ed'])}</script>
"""
    return body


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--edition", type=int, help="edition number")
    g.add_argument("--date", help="air date, YYYY-MM-DD")
    g.add_argument("--tomorrow", action="store_true",
                    help="tomorrow's edition (default if nothing else given)")
    ap.add_argument("--out", help="output path (default tools/out/daily-review-<date>.html)")
    a = ap.parse_args()

    manifest = C.load_manifest()
    n = resolve_edition(a, manifest)
    if n is None:
        return 1

    day = collect(n, manifest)
    html_out = render(day)

    out = Path(a.out) if a.out else OUT_DIR / f"daily-review-{day['date']}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_out, encoding="utf-8")

    size = out.stat().st_size
    print(f"daily review: edition {n} ({day['weekday']} {day['nice']}), 10 rounds -> "
          f"{out.relative_to(ROOT) if out.is_relative_to(ROOT) else out} "
          f"({size:,} bytes, {size / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
