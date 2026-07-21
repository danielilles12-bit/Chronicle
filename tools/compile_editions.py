#!/usr/bin/env python3
"""Edition compiler — the editorial pipeline for Dead Famous dailies.

Subcommands:
  freeze                    Reproduce the CURRENT client algorithm (cursor
                            arithmetic in js/daily.js) for editions 0..today
                            and record them in data/editions.json as immutable
                            historical fact. Safe to re-run: existing entries
                            are never rewritten (drift is reported, not fixed).
  propose --days N          Generate the next N unaired editions under the new
                            5 who + 5 map + 5 what + 1 thread recipe, into
                            data/editions.proposed.json (NOT the live manifest)
                            plus a human review sheet tools/out/review-<date>.html.
  approve --through DATE    Promote proposed editions with date <= DATE into
                            data/editions.json. Refuses aired dates; never
                            rewrites an existing manifest entry.

Thresholds live in tools/editions.config.json.

The freeze port mirrors js/daily.js exactly — takeWrapped / roundsCursor /
threadCursor / backfill — including pool order (DATA.reveal is
reveal-who.json ++ reveal-what.json, filtered by kind). If daily.js changes,
this file must change with it (until the client reads the manifest and the
cursor code is demoted to Encore/practice sampling).
"""
import argparse
import html
import json
import sys
import unicodedata
from collections import Counter
from datetime import date, timedelta
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data/editions.json"
PROPOSED = ROOT / "data/editions.proposed.json"
CONFIG_PATH = ROOT / "tools/editions.config.json"
OUT_DIR = ROOT / "tools/out"

# ---------------------------------------------------------------------------
# Shared calendar + recipes (EPOCH and OLD_RECIPE mirror js/daily.js)
# ---------------------------------------------------------------------------
EPOCH = date(2026, 6, 29)  # a Monday; edition n airs EPOCH + n days
TIERS = ["easy", "medium", "hard"]
GAMES = ["who", "map", "what", "thread"]

# Current client recipe: 10 rounds/game/day, [easy, medium, hard] per weekday.
OLD_RECIPE = [
    [7, 2, 1],  # Mon
    [6, 3, 1],  # Tue
    [5, 3, 2],  # Wed
    [4, 4, 2],  # Thu
    [3, 4, 3],  # Fri
    [2, 4, 4],  # Sat
    [1, 4, 5],  # Sun
]

# New recipe (approved 21 Jul 2026): 5 rounds/game/day, Mon->Sun ramp.
NEW_RECIPE = [
    [4, 1, 0],  # Mon
    [3, 2, 0],  # Tue
    [3, 1, 1],  # Wed
    [2, 2, 1],  # Thu
    [1, 3, 1],  # Fri
    [1, 2, 2],  # Sat
    [0, 2, 3],  # Sun
]

# Thread: 1 board/day, tier by weekday — unchanged across recipes.
THREAD_TIER = ["easy", "easy", "medium", "medium", "hard", "hard", "hard"]

OLD_WEEKLY_TOTAL = [sum(r[i] for r in OLD_RECIPE) for i in range(3)]  # [28,24,18]
THREAD_WEEKLY = Counter(THREAD_TIER)


def weekday(n):
    return n % 7  # editions before EPOCH are not a real case


def edition_date(n):
    return EPOCH + timedelta(days=n)


def edition_index(d):
    return (d - EPOCH).days


def today_index():
    return edition_index(date.today())


WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                 "Saturday", "Sunday"]


# ---------------------------------------------------------------------------
# Data loading (pool assembly mirrors app.js: reveal = who ++ what)
# ---------------------------------------------------------------------------
def load_json(rel):
    with open(ROOT / rel, encoding="utf-8") as f:
        return json.load(f)


def load_pools():
    figures = load_json("data/figures.json")
    reveal = load_json("data/reveal-who.json") + load_json("data/reveal-what.json")
    connections = load_json("data/connections.json")
    return {
        "map": figures,
        "who": [x for x in reveal if x.get("kind") == "portrait"],
        "what": [x for x in reveal if x.get("kind") != "portrait"],
        "thread": connections,
    }


def load_config():
    defaults = {
        "repeat_floor_days": 28,
        "repeat_target_days": 42,
        "min_lifeline_km": 250,
        "max_same_country": 3,
        "max_same_era": 3,
        "require_sources": False,
    }
    if CONFIG_PATH.exists():
        defaults.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    return defaults


# ---------------------------------------------------------------------------
# The OLD algorithm, ported line-for-line from js/daily.js
# ---------------------------------------------------------------------------
def rounds_cursor(tier, n):
    ti = TIERS.index(tier)
    if n <= 0:
        return 0
    weeks, rem = divmod(n, 7)
    total = weeks * OLD_WEEKLY_TOTAL[ti]
    for k in range(rem):
        total += OLD_RECIPE[weekday(k)][ti]
    return total


def thread_cursor(tier, n):
    if n <= 0:
        return 0
    weeks, rem = divmod(n, 7)
    total = weeks * THREAD_WEEKLY[tier]
    for k in range(rem):
        if THREAD_TIER[weekday(k)] == tier:
            total += 1
    return total


def take_wrapped(pool, start, count):
    ln = len(pool)
    if ln == 0 or count <= 0:
        return []
    return [pool[(start + i) % ln] for i in range(min(count, ln))]


def old_get_edition(game, n, pools):
    """Ordered id list for edition n under the current client algorithm."""
    items = pools[game]
    if game == "thread":
        tier = THREAD_TIER[weekday(n)]
        pool = [x for x in items if x["difficulty"] == tier]
        if not pool:
            return []
        cursor = thread_cursor(tier, n)
        return [x["id"] for x in take_wrapped(pool, cursor % len(pool), 1)]

    by_tier = {t: [x for x in items if x["difficulty"] == t] for t in TIERS}
    counts = OLD_RECIPE[weekday(n)]

    def cursor_for(t):
        ln = len(by_tier[t])
        return rounds_cursor(t, n) % ln if ln else 0

    # Pass 1: every tier's primary selection against untouched canonical pools.
    picks, used = {}, set()
    for i, tier in enumerate(TIERS):
        count = counts[i]
        p = take_wrapped(by_tier[tier], cursor_for(tier), count) if count > 0 else []
        picks[tier] = p
        used.update(x["id"] for x in p)

    # Pass 2: backfill shortfalls from the adjacent tier, in pool array order.
    for i, tier in enumerate(TIERS):
        count = counts[i]
        if count <= 0:
            continue
        short = count - len(picks[tier])
        if short > 0:
            lender = "medium" if tier in ("hard", "easy") else "easy"
            extra = [x for x in by_tier[lender] if x["id"] not in used][:short]
            used.update(x["id"] for x in extra)
            picks[tier] = picks[tier] + extra

    out = []
    for t in TIERS:
        out.extend(x["id"] for x in picks[t])
    return out


# ---------------------------------------------------------------------------
# Manifest I/O
# ---------------------------------------------------------------------------
def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"schema": 1, "recipeChangeEdition": None, "editions": {}}


def save_manifest(m):
    m["editions"] = {k: m["editions"][k]
                     for k in sorted(m["editions"], key=int)}
    MANIFEST.write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n",
                        encoding="utf-8")


# ---------------------------------------------------------------------------
# freeze
# ---------------------------------------------------------------------------
def cmd_freeze(_args):
    pools = load_pools()
    manifest = load_manifest()
    today = today_index()
    added, drifted = [], []

    for n in range(0, today + 1):
        computed = {
            "date": edition_date(n).isoformat(),
            "who": old_get_edition("who", n, pools),
            "map": old_get_edition("map", n, pools),
            "what": old_get_edition("what", n, pools),
            "thread": old_get_edition("thread", n, pools),
        }
        key = str(n)
        if key in manifest["editions"]:
            if manifest["editions"][key] != computed:
                drifted.append(n)  # report, never rewrite: aired = immutable
            continue
        manifest["editions"][key] = computed
        added.append(n)

    # recipeChangeEdition = first edition NOT produced by the old algorithm.
    # Only raised when this run froze new old-algorithm editions past it.
    change = manifest.get("recipeChangeEdition")
    floor_change = (max(added) + 1) if added else None
    if change is None:
        manifest["recipeChangeEdition"] = floor_change if floor_change is not None else today + 1
    elif floor_change is not None and floor_change > change:
        manifest["recipeChangeEdition"] = floor_change

    save_manifest(manifest)
    print(f"freeze: manifest now holds {len(manifest['editions'])} editions "
          f"(added {len(added)}: {added if added else '—'})")
    print(f"freeze: recipeChangeEdition = {manifest['recipeChangeEdition']} "
          f"({edition_date(manifest['recipeChangeEdition']).isoformat()})")
    if drifted:
        print(f"freeze: WARNING — {len(drifted)} already-frozen editions no longer "
              f"match what the current data would produce (content edits since "
              f"freezing): {drifted}. Manifest entries kept — aired is immutable.")
    return 0


# ---------------------------------------------------------------------------
# propose helpers
# ---------------------------------------------------------------------------
def normalise(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = "".join(c if c.isalnum() else " " for c in s)
    return " ".join(s.split())


def haversine_km(a, b):
    la1, lo1, la2, lo2 = map(radians, [a["lat"], a["lon"], b["lat"], b["lon"]])
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * asin(sqrt(h))


def figure_country(fig):
    place = (fig.get("birth") or {}).get("place") or ""
    return place.split(",")[-1].strip() or None


def figure_era(fig):
    y = (fig.get("birth") or {}).get("year")
    if not isinstance(y, int):
        return None
    if y < 0:
        return f"{(abs(y) - 1) // 100 + 1}th c. BC"
    return f"{(y - 1) // 100 + 1}th c. AD"


def money_scrap(item):
    c = min(2, int(item["fx"] * 3))
    r = min(2, int(item["fy"] * 3))
    return r * 3 + c


def start_scrap(item):
    """The scrap that opens torn — curated `start` override, else the cell
    farthest from the money shot (corners first). Mirrors js/revealgame.js."""
    m = money_scrap(item)
    s = item.get("start")
    if isinstance(s, int) and 0 <= s <= 8 and s != m:
        return s
    mr, mc = divmod(m, 3)
    best, bd = 0, -1
    for i in [0, 2, 6, 8, 1, 3, 5, 7, 4]:
        d = abs(i // 3 - mr) + abs(i % 3 - mc)
        if d > bd:
            bd, best = d, i
    return best


def airing_history(manifest):
    """(game, id) -> latest aired date, from every manifest edition."""
    last = {}
    for key, ed in manifest["editions"].items():
        d = date.fromisoformat(ed["date"])
        for game in GAMES:
            for item_id in ed.get(game, []):
                k = (game, item_id)
                if k not in last or d > last[k]:
                    last[k] = d
    return last


class Shortage(Exception):
    def __init__(self, n, game, tier, need, got):
        self.n, self.game, self.tier, self.need, self.got = n, game, tier, need, got
        super().__init__(
            f"edition {n} ({edition_date(n).isoformat()}): {game}/{tier} needs "
            f"{need}, only {got} eligible even after adjacent-tier backfill")


def thread_answer_keys(board):
    keys = set()
    for g in board.get("groups", []):
        keys.add(normalise(g.get("label", "")))
        for it in g.get("items", []):
            keys.add(normalise(it))
    keys.discard("")
    return keys


# ---------------------------------------------------------------------------
# propose
# ---------------------------------------------------------------------------
def cmd_propose(args):
    cfg = load_config()
    pools = load_pools()
    manifest = load_manifest()
    if not manifest["editions"]:
        print("propose: manifest is empty — run `freeze` first so repeat "
              "history reflects what actually aired.", file=sys.stderr)
        return 1

    today = today_index()
    last_aired = airing_history(manifest)
    start = max([int(k) for k in manifest["editions"]] + [today]) + 1

    floor = cfg["repeat_floor_days"]
    target = cfg["repeat_target_days"]

    by_tier = {g: {t: [x for x in pools[g] if x["difficulty"] == t] for t in TIERS}
               for g in ("who", "map", "what")}
    thread_by_tier = {t: [x for x in pools["thread"] if x["difficulty"] == t]
                      for t in TIERS}
    id_index = {g: {x["id"]: x for x in pools[g]} for g in GAMES}

    def gap_days(game, item_id, on_date):
        la = last_aired.get((game, item_id))
        return None if la is None else (on_date - la).days

    def eligible(game, item, on_date, day_answers, extra_reject):
        """Hard constraints only. Returns (ok, reason)."""
        g = gap_days(game, item["id"], on_date)
        if g is not None and g < floor:
            return False, f"aired {g}d ago (floor {floor})"
        if game in ("who", "what"):
            if not (ROOT / item["img"]).exists():
                return False, "image missing on disk"
        if game == "map":
            if haversine_km(item["birth"], item["death"]) < cfg["min_lifeline_km"] \
                    and not item.get("allow_close"):
                return False, f"birth-death < {cfg['min_lifeline_km']}km"
        if cfg["require_sources"] and not item.get("source"):
            return False, "unsourced (require_sources on)"
        if game == "thread":
            if thread_answer_keys(item) & day_answers:
                return False, "tile/label collides with today's answers"
        else:
            if normalise(item["name"]) in day_answers:
                return False, "answer already used today"
        if extra_reject and item["id"] in extra_reject:
            return False, "already picked today"
        return True, ""

    def ranked(pool, game, on_date):
        """Never-aired first, then longest-since-aired, then pool order."""
        def key(pair):
            i, item = pair
            la = last_aired.get((game, item["id"]))
            return (0 if la is None else 1, la or date.min, i)
        return [item for _, item in sorted(enumerate(pool), key=key)]

    editions = {}
    warnings = {}   # str(n) -> [ {kind, game, id, text} ]
    stopped_short = None

    for n in range(start, start + args.days):
        on_date = edition_date(n)
        wd = weekday(n)
        day_answers = set()
        picked_today = {g: [] for g in GAMES}
        warns = []

        def note(kind, game, item_id, text):
            warns.append({"kind": kind, "game": game, "id": item_id, "text": text})

        def soft_checks(game, item):
            g = gap_days(game, item["id"], on_date)
            if g is not None and g < target:
                note("repeat-target", game, item["id"],
                     f"last aired {g} days ago (target {target})")
            if game in ("who", "what") and not item.get("license"):
                note("licence-missing", game, item["id"], "no licence field")

        try:
            # --- Thread first: one board, least flexible pool -------------
            tier = THREAD_TIER[wd]
            board = None
            for cand in ranked(thread_by_tier[tier], "thread", on_date):
                ok, _ = eligible("thread", cand, on_date, day_answers, None)
                if ok:
                    board = cand
                    break
            if board is None:
                raise Shortage(n, "thread", tier, 1, 0)
            picked_today["thread"] = [board["id"]]
            day_answers |= thread_answer_keys(board)
            soft_checks("thread", board)

            # --- Rounds games: who, map, what -----------------------------
            # Two passes, like the client: every tier's PRIMARY quota is
            # served from its own pool first, then shortfalls backfill from
            # the adjacent tier — so a starved easy tier can never strip the
            # medium pool before medium's own quota is met.
            for game in ("who", "map", "what"):
                counts = NEW_RECIPE[wd]
                chosen_ids = set()
                got_by_tier = {t: [] for t in TIERS}
                for ti, tier in enumerate(TIERS):
                    need = counts[ti]
                    for cand in ranked(by_tier[game][tier], game, on_date):
                        if len(got_by_tier[tier]) == need:
                            break
                        ok, _ = eligible(game, cand, on_date, day_answers, chosen_ids)
                        if ok:
                            got_by_tier[tier].append(cand)
                            chosen_ids.add(cand["id"])
                            day_answers.add(normalise(cand["name"]))
                # Backfill pass: the repeat floor is sacred; the difficulty
                # mix bends first (flagged for the review sheet).
                for ti, tier in enumerate(TIERS):
                    need = counts[ti]
                    if len(got_by_tier[tier]) >= need:
                        continue
                    lender = "medium" if tier in ("hard", "easy") else "easy"
                    for cand in ranked(by_tier[game][lender], game, on_date):
                        if len(got_by_tier[tier]) == need:
                            break
                        ok, _ = eligible(game, cand, on_date, day_answers, chosen_ids)
                        if ok:
                            got_by_tier[tier].append(cand)
                            chosen_ids.add(cand["id"])
                            day_answers.add(normalise(cand["name"]))
                            note("tier-backfill", game, cand["id"],
                                 f"{lender} item in a {tier} slot — {tier} "
                                 f"pool blocked by the {floor}-day floor")
                    if len(got_by_tier[tier]) < need:
                        raise Shortage(n, game, tier, need, len(got_by_tier[tier]))
                chosen = []
                for tier in TIERS:
                    for item in got_by_tier[tier]:
                        soft_checks(game, item)
                    chosen.extend(got_by_tier[tier])
                picked_today[game] = [x["id"] for x in chosen]

            # --- Edition-level spread warnings (Lifeline figures only:
            # who/what records carry no country/era fields until Phase 3) ---
            figs = [id_index["map"][i] for i in picked_today["map"]]
            for label, fn, cap in (("country", figure_country, cfg["max_same_country"]),
                                   ("era", figure_era, cfg["max_same_era"])):
                c = Counter(v for v in (fn(f) for f in figs) if v)
                for val, cnt in c.items():
                    if cnt > cap:
                        note(f"{label}-cluster", "map", None,
                             f"{cnt} Lifeline figures share {label} “{val}”")

        except Shortage as sh:
            stopped_short = sh
            break

        editions[str(n)] = {
            "date": on_date.isoformat(),
            "who": picked_today["who"],
            "map": picked_today["map"],
            "what": picked_today["what"],
            "thread": picked_today["thread"],
        }
        if warns:
            warnings[str(n)] = warns
        # Airings inside the proposal window count toward later days' gaps.
        for game in GAMES:
            for item_id in picked_today[game]:
                last_aired[(game, item_id)] = on_date

    proposed = {
        "schema": 1,
        "recipeChangeEdition": start,
        "generatedOn": date.today().isoformat(),
        "config": cfg,
        "editions": editions,
        "warnings": warnings,
    }
    PROPOSED.write_text(json.dumps(proposed, indent=1, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    sheet = write_review_sheet(proposed, pools, id_index, manifest)

    n_warn = sum(len(v) for v in warnings.values())
    print(f"propose: {len(editions)} editions written to "
          f"{PROPOSED.relative_to(ROOT)} (editions {start}–{start + len(editions) - 1})")
    print(f"propose: review sheet -> {sheet.relative_to(ROOT)}")
    print(f"propose: {n_warn} soft warnings across {len(warnings)} editions")
    for kind, cnt in Counter(w["kind"] for v in warnings.values() for w in v).most_common():
        print(f"  {kind}: {cnt}")
    if stopped_short is not None:
        print(f"propose: STOPPED EARLY — {stopped_short}", file=sys.stderr)
        print("  Remedies: wait for floor re-eligibility, add a content batch, "
              "or adjust tools/editions.config.json.", file=sys.stderr)
        return 2
    return 0


# ---------------------------------------------------------------------------
# review sheet
# ---------------------------------------------------------------------------
COLOUR_HEX = {"yellow": "#E7C24A", "green": "#69A85C", "blue": "#5B8DC9",
              "purple": "#9B6BB3"}


def scrap_grid_svg(open_cell, money_cell):
    cells = []
    for i in range(9):
        r, c = divmod(i, 3)
        fill = "#E02020" if i == open_cell else ("#0B0B0B" if i == money_cell else "#D8D3C4")
        cells.append(f'<rect x="{c * 11}" y="{r * 11}" width="10" height="10" fill="{fill}"/>')
    return (f'<svg width="32" height="32" viewBox="0 0 32 32" '
            f'title="red = opens torn, black = money shot">{"".join(cells)}</svg>')


def gap_label(gap):
    return "never aired" if gap is None else f"aired {gap}d ago"


def write_review_sheet(proposed, pools, id_index, manifest):
    cfg = proposed["config"]
    history = airing_history(manifest)  # pre-proposal history only

    def gap_at(game, item_id, on_date):
        la = history.get((game, item_id))
        return None if la is None else (on_date - la).days

    rows = []
    e = html.escape
    for key in sorted(proposed["editions"], key=int):
        ed = proposed["editions"][key]
        n = int(key)
        on_date = date.fromisoformat(ed["date"])
        warns = proposed["warnings"].get(key, [])
        backfilled = {w["id"] for w in warns if w["kind"] == "tier-backfill"}

        rows.append(f'<section class="edition"><h2>№ {n} — '
                    f'{WEEKDAY_NAMES[weekday(n)]} {e(ed["date"])}</h2>')
        if warns:
            items = "".join(f'<li><b>{e(w["kind"])}</b>'
                            f'{" · " + e(w["id"]) if w["id"] else ""}'
                            f' — {e(w["text"])}</li>' for w in warns)
            rows.append(f'<div class="warnbox"><b>{len(warns)} warning'
                        f'{"s" if len(warns) != 1 else ""}</b><ul>{items}</ul></div>')

        for game, title in (("who", "Face Value"), ("what", "Relic")):
            rows.append(f"<h3>{title}</h3><div class='cards'>")
            for item_id in ed[game]:
                it = id_index[game][item_id]
                gp = gap_at(game, item_id, on_date)
                flag = ' <span class="bf">TIER BACKFILL</span>' if item_id in backfilled else ""
                rows.append(
                    f'<div class="card"><img src="../../{e(it["img"])}" loading="lazy" alt="">'
                    f'<div><b>{e(it["name"])}</b> <i>({e(it["difficulty"])})</i>{flag}<br>'
                    f'{scrap_grid_svg(start_scrap(it), money_scrap(it))}<br>'
                    f'<small>{e(it.get("blurb", ""))}</small><br>'
                    f'<small class="meta">{e(it.get("license") or "NO LICENCE")} · '
                    f'{e(it.get("attribution", ""))} · {gap_label(gp)}</small></div></div>')
            rows.append("</div>")

        rows.append("<h3>Lifeline</h3><table><tr><th>figure</th><th>tier</th>"
                    "<th>birth → death</th><th>km</th><th>history</th></tr>")
        for item_id in ed["map"]:
            it = id_index["map"][item_id]
            km = haversine_km(it["birth"], it["death"])
            gp = gap_at("map", item_id, on_date)
            flag = ' <span class="bf">TIER BACKFILL</span>' if item_id in backfilled else ""
            rows.append(
                f'<tr><td><b>{e(it["name"])}</b>{flag}<br><small>{e(it.get("occupation", ""))}</small></td>'
                f'<td>{e(it["difficulty"])}</td>'
                f'<td><small>{e(it["birth"]["place"])} {it["birth"]["year"]} → '
                f'{e(it["death"]["place"])} {it["death"]["year"]}</small></td>'
                f'<td>{km:,.0f}</td><td><small>{gap_label(gp)}</small></td></tr>')
        rows.append("</table>")

        board = id_index["thread"][ed["thread"][0]]
        gp = gap_at("thread", board["id"], on_date)
        rows.append(f'<h3>Thread — “{e(board.get("title", board["id"]))}” '
                    f'<i>({e(board["difficulty"])}, {gap_label(gp)})</i></h3>')
        for g in board["groups"]:
            hexc = COLOUR_HEX.get(g.get("colour"), "#999")
            rows.append(f'<div class="tgroup" style="border-left:14px solid {hexc}">'
                        f'<b>{e(g["label"])}</b>: {e(" · ".join(g["items"]))}</div>')
        rows.append("</section>")

    n_warn = sum(len(v) for v in proposed["warnings"].values())
    doc = f"""<!doctype html><meta charset="utf-8">
<title>Dead Famous — edition review {e(proposed['generatedOn'])}</title>
<style>
 body {{ font: 15px/1.45 -apple-system, sans-serif; background: #F2EFE6;
        color: #0B0B0B; max-width: 980px; margin: 2rem auto; padding: 0 1rem; }}
 h1 {{ font-size: 1.6rem }} h2 {{ border-bottom: 3px solid #0B0B0B; padding-bottom: .2rem }}
 h3 {{ margin: 1rem 0 .4rem }}
 .cards {{ display: flex; flex-wrap: wrap; gap: .8rem }}
 .card {{ display: flex; gap: .6rem; width: 30rem; background: #fff;
         border: 1px solid #C9C4B4; padding: .5rem }}
 .card img {{ width: 84px; height: 84px; object-fit: cover; flex: none }}
 .meta {{ color: #6B675C }}
 table {{ border-collapse: collapse; width: 100% }}
 td, th {{ border: 1px solid #C9C4B4; padding: .3rem .5rem; text-align: left;
          vertical-align: top; background: #fff }}
 .warnbox {{ background: #FBE9E9; border: 2px solid #E02020; padding: .5rem .8rem;
            margin: .6rem 0 }}
 .warnbox ul {{ margin: .3rem 0 0 1.2rem; padding: 0 }}
 .bf {{ background: #E02020; color: #fff; font-size: .7rem; padding: 0 .3rem }}
 .tgroup {{ background: #fff; border: 1px solid #C9C4B4; padding: .35rem .6rem;
           margin: .25rem 0 }}
 .config {{ color: #6B675C; font-size: .85rem }}
</style>
<h1>Edition review — proposed {e(proposed['generatedOn'])}</h1>
<p class="config">Recipe 5 who + 5 map + 5 what + 1 thread ·
floor {cfg['repeat_floor_days']}d · target {cfg['repeat_target_days']}d ·
min Lifeline {cfg['min_lifeline_km']}km · {len(proposed['editions'])} editions ·
{n_warn} warnings. Legend: scrap grid — <span style="color:#E02020">red</span>
opens torn, black is the money shot.</p>
{''.join(rows)}
"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"review-{proposed['generatedOn']}.html"
    out.write_text(doc, encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# approve
# ---------------------------------------------------------------------------
def cmd_approve(args):
    through = date.fromisoformat(args.through)
    if not PROPOSED.exists():
        print("approve: no data/editions.proposed.json — run propose first.",
              file=sys.stderr)
        return 1
    proposed = json.loads(PROPOSED.read_text(encoding="utf-8"))
    manifest = load_manifest()
    today = date.today()
    promoted, skipped = [], []

    for key in sorted(proposed["editions"], key=int):
        ed = proposed["editions"][key]
        d = date.fromisoformat(ed["date"])
        if d > through:
            continue
        if d <= today:
            print(f"approve: REFUSED edition {key} ({ed['date']}) — that date "
                  f"has already aired; aired editions are immutable. Re-run "
                  f"freeze and propose.", file=sys.stderr)
            return 1
        if key in manifest["editions"]:
            if manifest["editions"][key] == ed:
                skipped.append(key)
                continue
            print(f"approve: REFUSED edition {key} — already in the manifest "
                  f"with different content; manifest entries are immutable.",
                  file=sys.stderr)
            return 1
        manifest["editions"][key] = ed
        promoted.append(key)

    if promoted and manifest.get("recipeChangeEdition") is None:
        manifest["recipeChangeEdition"] = min(int(k) for k in promoted)
    save_manifest(manifest)
    print(f"approve: promoted {len(promoted)} editions through {args.through}"
          f"{' (' + ', '.join(promoted) + ')' if promoted else ''}")
    if skipped:
        print(f"approve: {len(skipped)} already present and identical, skipped")
    if not promoted and not skipped:
        print("approve: nothing to promote in that date range")
    return 0


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("freeze", help="freeze editions 0..today under the current "
                                  "client algorithm")
    p = sub.add_parser("propose", help="draft the next N unaired editions")
    p.add_argument("--days", type=int, default=14)
    a = sub.add_parser("approve", help="promote proposed editions into the manifest")
    a.add_argument("--through", required=True, metavar="YYYY-MM-DD")
    args = ap.parse_args()
    return {"freeze": cmd_freeze, "propose": cmd_propose,
            "approve": cmd_approve}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
