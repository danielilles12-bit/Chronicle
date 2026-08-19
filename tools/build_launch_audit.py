#!/usr/bin/env python3
"""Launch-window content audit sheet — one page, 30 days, feedback capture.

Renders every round of editions N..N+29 (default: the 30 days from launch,
edition 42 / 2026-08-10) as a reviewable card deck:

  Face Value / Relic  the OPENING SCRAP exactly as the player first sees it
                      (revealgame.js geometry, cover-fit square window biased
                      to fx/fy, 3x3 grid, curated `start` override honoured),
                      with the answer printed underneath. Every cell is
                      clickable, so the reviewer can nominate a different
                      opening scrap without playing a round.
  Lifeline            birth -> death with years and places, answer underneath.
  Thread              already solved: all four groups, labels and tiles.

The reviewer types free-text notes anywhere, nominates start scraps by
clicking, and hits "Copy all feedback" to get one markdown block to paste
back. Notes autosave to localStorage, so the sheet survives a reload.

Output lands in tools/out/ — gitignored and CI-enforced (tools/repo_checks.py)
because it prints UNAIRED answers and Pages serves the whole repo.

Usage:
  python3 tools/build_launch_audit.py [--from 42] [--days 30] [--out PATH]
"""
import argparse
import datetime
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compile_editions as C  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DEFAULT = ROOT / "tools/out/launch-window-audit.html"
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday"]
GAME_LABEL = {"who": "Face Value", "map": "Lifeline",
              "what": "Relic", "thread": "Thread"}
GLYPH = {"yellow": "●", "green": "▲", "blue": "■", "purple": "✦"}


# --- revealgame.js geometry, ported verbatim -------------------------------
def money_scrap(item):
    c = min(2, int(item["fx"] * 3))
    r = min(2, int(item["fy"] * 3))
    return r * 3 + c


def start_scrap(item):
    m = money_scrap(item)
    override = item.get("start")
    # money-cell overrides are legal (owner ruling 29 Jul 2026, revealgame.js)
    if isinstance(override, int) and 0 <= override <= 8:
        return override
    mr, mc = divmod(m, 3)
    best, bd = 0, -1
    for i in (0, 2, 6, 8, 1, 3, 5, 7, 4):      # corners first, deterministic
        d = abs(i // 3 - mr) + abs(i % 3 - mc)
        if d > bd:
            bd, best = d, i
    return best


def img_url(item):
    """Prefer the w800 webp the app itself serves; fall back to the original."""
    stem = Path(item["img"]).stem
    web = ROOT / "assets/img/w800" / f"{stem}.webp"
    rel = f"assets/img/w800/{stem}.webp" if web.exists() else item["img"]
    return "../../" + rel


def collect(start_ed, days):
    pools = C.load_pools()
    man = C.load_manifest()["editions"]
    fame_idx, tag_idx = C.load_signal_indices()
    idx = {g: {x["id"]: x for x in pools[g]} for g in C.GAMES}
    try:
        sal = {(r["game"], r["id"]): r.get("salience")
               for r in json.loads((ROOT / "tools/fame/salience.json")
                                   .read_text(encoding="utf-8"))["items"]}
    except Exception:
        sal = {}

    out = []
    for n in range(start_ed, start_ed + days):
        e = man.get(str(n))
        if not e:
            print(f"build_launch_audit: edition {n} is not in the manifest — "
                  f"run `compile_editions.py propose/approve` first",
                  file=sys.stderr)
            return None
        d = datetime.date.fromisoformat(e["date"])
        day = {"ed": n, "date": e["date"], "weekday": WEEKDAYS[d.weekday()],
               "nice": d.strftime("%-d %B %Y"), "games": {}}
        for g in ("who", "map", "what", "thread"):
            rounds = []
            for iid in e[g]:
                it = idx[g].get(iid)
                if not it:
                    rounds.append({"id": iid, "broken": True})
                    continue
                sig = C.item_signal(g, it, fame_idx, tag_idx)
                r = {"id": iid, "game": g,
                     "name": it.get("name") or it.get("title") or iid,
                     "difficulty": it.get("difficulty") or "?",
                     "fame": sig.get("fame"), "sal": sal.get((g, iid)),
                     "region": sig.get("region"), "era": sig.get("era"),
                     "occ": sig.get("occupation_family"),
                     "mcq": it.get("mcq") or []}
                if g in ("who", "what"):
                    r.update({"img": img_url(it), "fx": it["fx"], "fy": it["fy"],
                              "money": money_scrap(it), "start": start_scrap(it),
                              "curated": isinstance(it.get("start"), int),
                              "blurb": it.get("blurb", ""),
                              "years": it.get("years", "")})
                elif g == "map":
                    r.update({"birth": it["birth"], "death": it["death"],
                              "occupation": it.get("occupation", ""),
                              "fact": it.get("fact", ""),
                              "km": round(C.haversine_km(it["birth"], it["death"]))})
                else:
                    r.update({"title": it.get("title", ""),
                              "groups": it.get("groups", [])})
                rounds.append(r)
            day["games"][g] = rounds
        out.append(day)
    return out


# --- rendering -------------------------------------------------------------
def e(s):
    return html.escape(str(s if s is not None else ""))


def sig_line(r):
    bits = []
    if r.get("fame") is not None:
        bits.append(f"fame {r['fame']:.0f}")
    if r.get("sal") is not None:
        bits.append(f"salience {r['sal']:.0f}")
    for k in ("region", "era", "occ"):
        if r.get(k):
            bits.append(e(r[k]))
    return " · ".join(bits)


def image_round(r, key):
    cells = "".join(
        f'<button class="cell{" money" if i == r["money"] else ""}" data-i="{i}" '
        f'type="button" aria-label="Open scrap {i + 1} instead"></button>'
        for i in range(9))
    curated = ('<span class="pill curated">curated start</span>' if r["curated"]
               else '<span class="pill auto">auto start</span>')
    return f"""
<div class="round img-round" data-key="{key}" data-start="{r['start']}"
     data-orig="{r['start']}" data-money="{r['money']}">
  <div class="scrapwrap">
    <div class="window" style="background-image:url('{e(r['img'])}');
         background-position:{r['fx'] * 100:.1f}% {r['fy'] * 100:.1f}%">
      <div class="grid">{cells}</div>
    </div>
    <label class="peek"><input type="checkbox" class="revealall"> show whole picture</label>
  </div>
  <div class="meta">
    <div class="tier t-{e(r['difficulty'])}">{e(r['difficulty'])}</div>
    <h4>{e(r['name'])}</h4>
    <p class="blurb">{e(r['blurb'])}</p>
    <p class="sig">{sig_line(r)}</p>
    <p class="mcqline">3-choice clue: <b>{e(r['name'])}</b> vs {e(' vs '.join(r['mcq']) if r['mcq'] else '(none)')}</p>
    <p class="startline">{curated}
       <span class="startnow">opens on scrap <b>{r['start'] + 1}</b></span>
       <button type="button" class="reset" hidden>reset</button></p>
    <textarea class="fb" data-key="{key}" rows="2"
      placeholder="Notes on this round…"></textarea>
  </div>
</div>"""


def map_round(r, key):
    b, d = r["birth"], r["death"]
    return f"""
<div class="round map-round">
  <div class="journey">
    <div class="leg"><span class="dot born"></span><b>{b['year']}</b>
      <span>{e(b['place'])}</span></div>
    <div class="legline"><span>{r['km']:,} km</span></div>
    <div class="leg"><span class="dot died"></span><b>{d['year']}</b>
      <span>{e(d['place'])}</span></div>
  </div>
  <div class="meta">
    <div class="tier t-{e(r['difficulty'])}">{e(r['difficulty'])}</div>
    <h4>{e(r['name'])}</h4>
    <p class="blurb">{e(r['occupation'])}</p>
    <p class="fact">{e(r['fact'])}</p>
    <p class="sig">{sig_line(r)}</p>
    <p class="mcqline">3-choice clue: <b>{e(r['name'])}</b> vs {e(' vs '.join(r['mcq']) if r['mcq'] else '(none)')}</p>
    <textarea class="fb" data-key="{key}" rows="2"
      placeholder="Notes on this round…"></textarea>
  </div>
</div>"""


def thread_round(r, key):
    groups = "".join(f"""
    <div class="tgroup g-{e(g.get('colour'))}">
      <div class="tlabel"><span class="tglyph">{GLYPH.get(g.get('colour'), '')}</span>
        {e(g.get('label'))}</div>
      <div class="tiles">{''.join(f'<span>{e(t)}</span>' for t in g.get('items', []))}</div>
    </div>""" for g in r["groups"])
    return f"""
<div class="round thread-round">
  <div class="meta wide">
    <div class="tier t-{e(r['difficulty'])}">{e(r['difficulty'])}</div>
    <h4>{e(r['name'])} <span class="bid">{e(r['id'])}</span></h4>
    <div class="tgroups">{groups}</div>
    <textarea class="fb" data-key="{key}" rows="3"
      placeholder="Notes on this board — labels fair? tiles ambiguous? too easy/hard?"></textarea>
  </div>
</div>"""


def render(days, start_ed):
    cards = []
    for n, day in enumerate(days, 1):
        secs = []
        for g in ("who", "map", "what", "thread"):
            rounds = []
            for j, r in enumerate(day["games"][g]):
                key = f"ed{day['ed']}.{g}.{j}"
                if r.get("broken"):
                    rounds.append(f'<div class="round broken">missing from pool: '
                                  f'{e(r["id"])}</div>')
                elif g == "thread":
                    rounds.append(thread_round(r, key))
                elif g == "map":
                    rounds.append(map_round(r, key))
                else:
                    rounds.append(image_round(r, key))
            secs.append(f'<section class="game game-{g}">'
                        f'<h3>{GAME_LABEL[g]}</h3>{"".join(rounds)}</section>')
        cards.append(f"""
<article class="day" id="day{n}">
  <header class="dayhead">
    <div class="dnum">Day {n}</div>
    <h2>{e(day['weekday'])} {e(day['nice'])}</h2>
    <div class="edno">edition {day['ed']}</div>
  </header>
  {''.join(secs)}
  <div class="daynote">
    <textarea class="fb" data-key="ed{day['ed']}.day" rows="2"
      placeholder="Notes on the whole issue — balance, tone, anything repeated…"></textarea>
  </div>
</article>""")

    nav = "".join(f'<a href="#day{i}">{i}</a>' for i in range(1, len(days) + 1))
    return TEMPLATE.format(
        cards="".join(cards), nav=nav, n=len(days),
        first=days[0]["nice"], last=days[-1]["nice"], start_ed=start_ed,
        generated=datetime.date.today().isoformat())


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Dead Famous — launch window content audit</title>
<style>
:root{{
  --paper:#F2EFE6;--cream:#FFFFFF;--ink:#0B0B0B;--muted:#6B675C;--soft:#CFC9B8;
  --pink:#D6008F;--red:#E02020;--blue:#0093B8;--yellow:#FFE93B;
  --t-yellow:#FFE93B;--t-green:#4CDB86;--t-blue:#2FC9E8;--t-purple:#C79BFF;
  --ui:'Helvetica Neue',Arial,sans-serif;
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:var(--ui);
  font-size:15px;line-height:1.5;-webkit-font-smoothing:antialiased}}
a{{color:var(--pink)}}
.top{{position:sticky;top:0;z-index:20;background:var(--ink);color:var(--paper);
  padding:10px 16px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}}
.top h1{{font-size:15px;margin:0;letter-spacing:.02em;text-transform:uppercase}}
.top .sp{{flex:1}}
.top button{{font:inherit;font-size:13px;font-weight:700;padding:7px 12px;
  border:2px solid var(--paper);background:var(--yellow);color:var(--ink);
  cursor:pointer;border-radius:2px}}
.top button.ghost{{background:transparent;color:var(--paper)}}
.count{{font-size:12px;color:#D8D4C6}}
.nav{{padding:8px 16px;background:var(--cream);border-bottom:2px solid var(--ink);
  position:sticky;top:44px;z-index:19;font-size:12px;overflow-x:auto;white-space:nowrap}}
.nav a{{display:inline-block;min-width:24px;text-align:center;padding:2px 4px;
  color:var(--ink);text-decoration:none;border:1px solid var(--soft);margin-right:3px}}
.nav a:hover{{background:var(--yellow)}}
.intro{{max-width:900px;margin:20px auto;padding:0 16px}}
.intro h2{{font-size:19px;margin:.6em 0 .3em}}
.intro li{{margin:.25em 0}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 16px 120px}}
.day{{background:var(--cream);border:2px solid var(--ink);margin:26px 0;
  box-shadow:5px 5px 0 rgba(11,11,11,.14);scroll-margin-top:92px}}
.dayhead{{display:flex;align-items:baseline;gap:12px;padding:12px 16px;
  border-bottom:2px solid var(--ink);background:var(--ink);color:var(--paper);
  flex-wrap:wrap}}
.dayhead h2{{font-size:17px;margin:0;flex:1}}
.dnum{{background:var(--yellow);color:var(--ink);font-weight:800;font-size:12px;
  padding:3px 8px}}
.edno{{font-size:12px;color:#D8D4C6}}
.game{{padding:14px 16px;border-bottom:1px dashed var(--soft)}}
.game:last-of-type{{border-bottom:0}}
.game h3{{font-size:12px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--muted);margin:0 0 12px}}
.round{{display:flex;gap:16px;padding:12px 0;border-top:1px solid #EDE9DC}}
.round:first-of-type{{border-top:0}}
.meta{{flex:1;min-width:0}}
.meta.wide{{width:100%}}
.meta h4{{margin:2px 0 4px;font-size:20px;line-height:1.2}}
.bid{{font-size:11px;color:var(--muted);font-weight:400}}
.blurb{{margin:0 0 4px;font-size:13.5px;color:#2A2A26}}
.fact{{margin:0 0 4px;font-size:13px;color:#2A2A26;font-style:italic}}
.sig{{margin:0 0 6px;font-size:11.5px;color:var(--muted);letter-spacing:.02em}}
.tier{{display:inline-block;font-size:10px;font-weight:800;text-transform:uppercase;
  letter-spacing:.1em;padding:2px 7px;border:1.5px solid var(--ink)}}
.t-easy{{background:#4CDB86}} .t-medium{{background:var(--yellow)}}
.t-hard{{background:var(--pink);color:#fff;border-color:var(--pink)}}
/* --- scrap window ------------------------------------------------------ */
.scrapwrap{{width:230px;flex:0 0 230px}}
.window{{position:relative;width:230px;height:230px;background-size:cover;
  background-color:#111;border:2px solid var(--ink)}}
.grid{{position:absolute;inset:0;display:grid;grid-template-columns:repeat(3,1fr);
  grid-template-rows:repeat(3,1fr)}}
.cell{{border:0;padding:0;cursor:pointer;background:#E9E4D3;
  box-shadow:inset 0 0 0 1px rgba(11,11,11,.18);transition:opacity .12s}}
.cell.open{{background:transparent;box-shadow:inset 0 0 0 2px var(--pink)}}
.cell:hover{{opacity:.72}}
.window.all .cell{{background:transparent;box-shadow:inset 0 0 0 1px rgba(11,11,11,.12)}}
.window.all .cell.open{{box-shadow:inset 0 0 0 2px var(--pink)}}
.window.all .cell.money{{box-shadow:inset 0 0 0 2px var(--blue)}}
.peek{{display:block;font-size:11.5px;color:var(--muted);margin-top:6px;cursor:pointer}}
.mcqline{{margin:0 0 5px;font-size:12px;color:#2A2A26}}
.mcqline b{{color:var(--pink)}}
.startline{{margin:0 0 8px;font-size:12px;display:flex;gap:8px;align-items:center;
  flex-wrap:wrap}}
.pill{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;
  padding:2px 6px;border:1px solid var(--soft);color:var(--muted)}}
.pill.curated{{border-color:var(--ink);color:var(--ink)}}
.startnow.changed{{background:var(--yellow);padding:1px 5px;font-weight:700}}
.reset{{font:inherit;font-size:11px;padding:1px 6px;cursor:pointer;
  border:1px solid var(--soft);background:transparent}}
/* --- lifeline ---------------------------------------------------------- */
.map-round .journey{{width:230px;flex:0 0 230px;border:2px solid var(--ink);
  background:#EDE9DC;padding:14px 12px;font-size:13px}}
.leg{{display:flex;gap:7px;align-items:baseline}}
.leg span:last-child{{color:#2A2A26}}
.dot{{width:9px;height:9px;border-radius:50%;flex:0 0 9px;display:inline-block}}
.dot.born{{background:var(--blue)}} .dot.died{{background:var(--red)}}
.legline{{margin:6px 0 6px 4px;padding-left:12px;border-left:2px dotted var(--muted);
  font-size:11px;color:var(--muted)}}
/* --- thread ------------------------------------------------------------ */
.tgroups{{display:grid;gap:6px;margin:8px 0 10px}}
.tgroup{{border:1.5px solid var(--ink);padding:7px 10px}}
.g-yellow{{background:var(--t-yellow)}} .g-green{{background:var(--t-green)}}
.g-blue{{background:var(--t-blue)}} .g-purple{{background:var(--t-purple)}}
.tlabel{{font-weight:800;font-size:12px;text-transform:uppercase;letter-spacing:.06em}}
.tglyph{{margin-right:6px;opacity:.65}}
.tiles{{display:flex;flex-wrap:wrap;gap:5px;margin-top:5px}}
.tiles span{{background:rgba(255,255,255,.72);border:1px solid rgba(11,11,11,.35);
  padding:2px 7px;font-size:12.5px}}
/* --- feedback ---------------------------------------------------------- */
textarea.fb{{width:100%;font:inherit;font-size:13px;padding:7px 9px;
  border:1.5px solid var(--soft);background:#FCFBF7;resize:vertical}}
textarea.fb:focus{{outline:2px solid var(--pink);border-color:var(--pink)}}
textarea.fb.filled{{border-color:var(--pink);background:#FFF8FC}}
.daynote{{padding:12px 16px;background:#F7F5EE;border-top:2px solid var(--ink)}}
.broken{{color:var(--red);font-weight:700}}
@media (max-width:720px){{
  .round{{flex-direction:column}}
  .scrapwrap,.window,.map-round .journey{{width:100%;flex:1 1 auto}}
  .window{{height:min(78vw,320px)}}
}}
#toast{{position:fixed;left:50%;bottom:26px;transform:translateX(-50%);
  background:var(--ink);color:var(--paper);padding:10px 18px;font-size:13px;
  z-index:60;opacity:0;pointer-events:none;transition:opacity .2s}}
#toast.on{{opacity:1}}
</style></head><body>

<div class="top">
  <h1>Launch window audit</h1>
  <span class="count" id="count">0 notes</span>
  <span class="sp"></span>
  <button type="button" id="copy">Copy all feedback</button>
  <button type="button" class="ghost" id="clear">Clear</button>
</div>
<div class="nav">{nav}</div>

<div class="intro">
  <p><b>{n} days — {first} to {last}</b> (editions {start_ed}+). Generated
  {generated}. Nothing here is live: notes stay in this browser until you press
  <b>Copy all feedback</b>.</p>
  <h2>How to read a Face Value / Relic card</h2>
  <ul>
    <li>The square is the <b>exact window the player sees</b>, with the one
      scrap the game opens for free already torn — pink outline. Everything
      else is still covered.</li>
    <li><b>Click any other cell</b> to nominate it as the opening scrap
      instead. The nomination is recorded; nothing changes in the app until
      you send the notes back.</li>
    <li>Tick <i>show whole picture</i> to see what is under the rest, with the
      <span style="color:#0093B8">blue</span> outline marking the money
      shot — the cell the opening scrap is deliberately placed far from.</li>
  </ul>
  <h2>Thread</h2>
  <p>Boards are shown already solved, so you can judge the categories and
  tiles without playing.</p>
</div>

<div class="wrap">{cards}</div>
<div id="toast"></div>

<script>
const KEY='df-launch-audit-v3';
const store=JSON.parse(localStorage.getItem(KEY)||'{{}}');

function save(){{localStorage.setItem(KEY,JSON.stringify(store));count();}}
function count(){{
  const n=Object.keys(store).filter(k=>{{
    const v=store[k];
    return (v&&v.note&&v.note.trim())||(v&&v.start!==undefined&&v.start!==null);
  }}).length;
  document.getElementById('count').textContent=n+(n===1?' card marked':' cards marked');
}}
function toast(m){{const t=document.getElementById('toast');t.textContent=m;
  t.classList.add('on');setTimeout(()=>t.classList.remove('on'),1600);}}
function rec(k){{return store[k]||(store[k]={{}});}}

// --- notes -----------------------------------------------------------------
document.querySelectorAll('textarea.fb').forEach(t=>{{
  const k=t.dataset.key;
  if(store[k]&&store[k].note){{t.value=store[k].note;t.classList.add('filled');}}
  t.addEventListener('input',()=>{{
    rec(k).note=t.value;
    t.classList.toggle('filled',!!t.value.trim());
    save();
  }});
}});

// --- scrap windows ---------------------------------------------------------
document.querySelectorAll('.img-round').forEach(r=>{{
  const k=r.dataset.key, orig=+r.dataset.orig, money=+r.dataset.money;
  const win=r.querySelector('.window'), cells=[...r.querySelectorAll('.cell')];
  const label=r.querySelector('.startnow'), reset=r.querySelector('.reset');
  function paint(){{
    const cur=(store[k]&&store[k].start!==undefined&&store[k].start!==null)
      ? store[k].start : orig;
    cells.forEach((c,i)=>c.classList.toggle('open',i===cur));
    const moved=cur!==orig;
    label.innerHTML=moved
      ? 'opens on scrap <b>'+(cur+1)+'</b> (was '+(orig+1)+')'
      : 'opens on scrap <b>'+(cur+1)+'</b>';
    label.classList.toggle('changed',moved);
    reset.hidden=!moved;
  }}
  cells.forEach((c,i)=>c.addEventListener('click',()=>{{
    if(i===money){{
      if(!confirm('That is the money shot — opening there gives the answer '
        +'away for free. Nominate it anyway?')) return;
    }}
    rec(k).start=(i===orig)?null:i;
    save();paint();
  }}));
  reset.addEventListener('click',()=>{{rec(k).start=null;save();paint();}});
  r.querySelector('.revealall').addEventListener('change',ev=>{{
    win.classList.toggle('all',ev.target.checked);
  }});
  paint();
}});

// --- export ----------------------------------------------------------------
function build(){{
  const out=['# Dead Famous — launch window feedback','',
    'Generated {generated}. Reviewer notes follow, grouped by edition.',''];
  const days=[...document.querySelectorAll('.day')];
  let any=false;
  days.forEach(day=>{{
    const lines=[];
    day.querySelectorAll('.img-round').forEach(r=>{{
      const k=r.dataset.key, s=store[k];
      if(s&&s.start!==undefined&&s.start!==null){{
        const nm=r.querySelector('h4').textContent.trim();
        lines.push('- START SCRAP · '+nm+' ('+k+'): use scrap '+(s.start+1)
          +' instead of '+(+r.dataset.orig+1));
      }}
    }});
    day.querySelectorAll('textarea.fb').forEach(t=>{{
      const v=(store[t.dataset.key]||{{}}).note;
      if(v&&v.trim()){{
        const card=t.closest('.round')||t.closest('.daynote');
        const h=card&&card.querySelector('h4');
        const who=h?h.textContent.trim():'whole issue';
        lines.push('- '+who+' ('+t.dataset.key+'): '+v.trim().replace(/\\n+/g,' '));
      }}
    }});
    if(lines.length){{
      any=true;
      const head=day.querySelector('.dayhead h2').textContent.trim();
      const num=day.querySelector('.dnum').textContent.trim();
      const ed=day.querySelector('.edno').textContent.trim();
      out.push('## '+num+' — '+head+' ('+ed+')','',...lines,'');
    }}
  }});
  if(!any) out.push('_No notes recorded._');
  return out.join('\\n');
}}
document.getElementById('copy').addEventListener('click',async()=>{{
  const text=build();
  try{{await navigator.clipboard.writeText(text);toast('Copied — paste it back to Claude');}}
  catch(err){{
    const w=window.open('','_blank');
    w.document.write('<pre style="white-space:pre-wrap;font:13px/1.5 monospace;'
      +'padding:20px">'+text.replace(/[<&]/g,c=>c==='<'?'&lt;':'&amp;')+'</pre>');
    toast('Clipboard blocked — copy from the new tab');
  }}
}});
document.getElementById('clear').addEventListener('click',()=>{{
  if(!confirm('Delete every note and start-scrap nomination on this sheet?'))return;
  localStorage.removeItem(KEY);location.reload();
}});
count();
</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", type=int, default=42,
                    help="first edition (default 42 = launch day, 2026-08-10)")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    a = ap.parse_args()

    days = collect(a.start, a.days)
    if days is None:
        return 1
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(days, a.start), encoding="utf-8")
    rounds = sum(len(d["games"][g]) for d in days for g in C.GAMES)
    print(f"launch audit: {len(days)} editions, {rounds} rounds -> "
          f"{out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
