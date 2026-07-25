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
  review                    Re-render the review sheet from the EXISTING
                            proposals file without re-rolling any content
                            (e.g. after a sheet-template change).
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trust_schema import is_sourced  # noqa: E402

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
        # --- Part B taste rules (24 Jul 2026 owner brief) -------------------
        # Variety caps, applied per 5-item game-round (who/map/what each
        # scored separately; see tools/fame/tags.json for region/era/
        # occupation_family — items with no tag data are wildcards, never
        # blocked). Caps relax (log a warning, never a hard failure) only if
        # a thin pool genuinely can't fill the day's quota otherwise.
        "max_region_per_round": 2,        # >2 items sharing one macroregion in a round gets skipped
        "max_occupation_per_round": 1,    # >1 item sharing one occupation_family (who/map only — objects have no occupation_family) gets skipped
        "min_era_diversity_per_round": 2, # best-effort goal, nudged for via ranking bias, not a hard block
        "era_novelty_bonus": 8.0,         # ranking nudge size (same units as western_bias_weight below) toward a not-yet-represented era when a round is short of min_era_diversity_per_round
        # Guaranteed "banker": every who/what day must contain >=1 item this
        # confidently recognisable (never five genuine unknowns in one day).
        "banker_fame_threshold": 75,      # fame score 0-100 (tools/fame/fame_scores.json) counting as a "banker" — ~top quartile across every class as of the 22 Jul fame run
        "banker_pv_pct_preference": 60,   # soft tiebreak only: among banker-repair candidates, prefer higher pv_pct
        # Western-audience (UK/Europe/US) recognisability weighting: on
        # non-Sunday, non-hard slots, nudge ranking toward higher pv_pct
        # (English-Wikipedia-specific recognisability) among similarly-famous
        # candidates — a soft bias on selection ORDER, never a hard filter.
        "icon_fame_threshold": 90,        # fame score at/above which an item is an "icon" (Great Wall, Taj Mahal, Angkor Wat...) exempt from the pv_pct tiebreak — ~top decile across every class
        "western_bias_weight": 0.5,       # pv_pct (0-100) x this = ranking nudge; 0 disables the bias entirely
        "western_bias_hard_exempt": True,    # 'hard' tier slots never get the bias — reserved for deeper/international cuts
        "western_bias_sunday_exempt": True,  # Sunday's slots never get the bias — the week's deepest-cut day
        # --- Tone / composition caps (25 Jul 2026) --------------------------
        # Sanctioned by the launch review, which asked to "cap all-power-
        # figure human slates" and "prevent any one dark theme from
        # swallowing an edition", having found that "executions,
        # assassinations, dictatorship, body parts and mass death recur
        # frequently enough that darkness stops feeling like contrast".
        #
        # TONE IS NOT DIFFICULTY. `difficulty` describes how hard a round is
        # to guess; tone describes how heavy the issue feels. They are
        # different concerns and get different controls, so nothing here
        # touches a difficulty label. Right now the Face Value easy pool
        # alone holds Hitler, Stalin, Mao, Mussolini, Lenin, Pinochet, Idi
        # Amin, Gaddafi, Khomeini, bin Laden, Escobar, Che Guevara and the
        # Shah — about one item in ten — and nothing stopped several of them
        # landing on the same day.
        "max_dark_tone_per_issue": 1,     # HARD cap, never relaxed: at most this many tagged subjects across the WHOLE issue (who+map+what+thread together)
        "max_power_share_per_issue": 0.4,  # SOFT cap (relaxes like the variety caps if a tier can't otherwise fill): share of the issue's HUMAN answers (who+map = 10 slots) that may be rulers/statesmen/commanders. 0.4 -> 4 of 10. Measured over settled editions 24-64 the median day already sits at 0.29 and only 7 of 41 days exceed 0.4, so this trims the lopsided days without starving normal ones.
        "power_occupation_families": ["ruler", "statesman", "military"],  # matched against tools/fame/tags.json occupation_family; an item with no tag match is a wildcard, never blocked
        # The curated tag list itself lives in tools/editions.config.json —
        # that is the owner-editable place to disagree with a call. Empty
        # here so a missing config file degrades to "no opinion" rather than
        # crashing, exactly like the fame/tags signals above.
        "dark_tone_ids": {},
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
# Part B signals — tools/fame/{fame_scores,tags}.json (24 Jul 2026 content
# audit byproducts, NOT core game data). Every rule below that reads a
# signal must degrade gracefully when it's missing: a record with no match
# is a wildcard, never a rejection, and the files being absent entirely just
# disables the taste rules rather than crashing propose.
# ---------------------------------------------------------------------------
FAME_SCORES_PATH = ROOT / "tools/fame/fame_scores.json"
TAGS_PATH = ROOT / "tools/fame/tags.json"


def load_signal_indices():
    """normalise(name-or-variant) -> fame_scores record / tags record.

    Live data records don't carry a wiki_title, so this fuzzy-matches on
    display text: each live item's own name, then its variants in order,
    against fame_scores.json's (name, wiki_title) and tags.json's
    (people ++ objects) keys. First hit wins. Coverage measured 24 Jul 2026:
    ~97-100% of who/what/map on fame/pv_pct, ~71-89% on era/region/
    occupation — the remainder simply carry no signal (see item_signal)."""
    fame_idx, tag_idx = {}, {}
    try:
        scores = json.loads(FAME_SCORES_PATH.read_text(encoding="utf-8"))["scores"]
        for r in scores:
            for key in (r.get("name"), r.get("wiki_title")):
                if key:
                    fame_idx.setdefault(normalise(key), r)
    except Exception as e:
        print(f"propose: WARNING — could not load {FAME_SCORES_PATH.relative_to(ROOT)}: "
              f"{e} (fame/pv_pct signals disabled for this run)", file=sys.stderr)
    try:
        tags = json.loads(TAGS_PATH.read_text(encoding="utf-8"))
        for k, v in tags.get("people", {}).items():
            tag_idx.setdefault(normalise(k), v)
        for k, v in tags.get("objects", {}).items():
            tag_idx.setdefault(normalise(k), v)
    except Exception as e:
        print(f"propose: WARNING — could not load {TAGS_PATH.relative_to(ROOT)}: "
              f"{e} (region/era/occupation signals disabled for this run)", file=sys.stderr)
    return fame_idx, tag_idx


_SIGNAL_CACHE = {}  # (game, id) -> merged signal dict, memoised per process


def item_signal(game, item, fame_idx, tag_idx):
    """Best-effort signal lookup for one live item. Returns a dict with
    whatever of {fame, pv_pct, era, region, occupation_family, kind} could be
    matched; unresolved keys are None. Callers MUST treat None as 'no
    opinion' — never as a reason to exclude or penalise the item."""
    key = (game, item["id"])
    cached = _SIGNAL_CACHE.get(key)
    if cached is not None:
        return cached
    names = [item.get("name")] + list(item.get("variants") or [])
    fame_rec = tag_rec = None
    for nm in names:
        if not nm:
            continue
        nk = normalise(nm)
        if fame_rec is None:
            fame_rec = fame_idx.get(nk)
        if tag_rec is None:
            tag_rec = tag_idx.get(nk)
        if fame_rec is not None and tag_rec is not None:
            break
    sig = {
        "fame": (fame_rec or {}).get("fame"),
        "pv_pct": (fame_rec or {}).get("pv_pct"),
        "era": (tag_rec or {}).get("era"),
        "region": (tag_rec or {}).get("region"),
        "occupation_family": (tag_rec or {}).get("occupation_family"),
        "kind": (tag_rec or {}).get("kind"),
    }
    _SIGNAL_CACHE[key] = sig
    return sig


# ---------------------------------------------------------------------------
# Tone classification (25 Jul 2026).
#
# TWO mechanisms, deliberately, because the two questions have different
# shapes:
#
#  1. "Is this a dark-tone subject?" cannot be inferred from any field we
#     hold. Occupation says `statesman` for Hitler, Lincoln and Gandhi
#     alike; fame and salience say nothing about tone at all. Guessing from
#     names or blurb text would be a fragile detector producing confident
#     nonsense. So it is a CURATED ID LIST in tools/editions.config.json —
#     the cheapest reliable mechanism, auditable at a glance, and editable
#     by the owner without touching code. ~84 tagged ids across four pools
#     of ~1,500 items.
#
#  2. "Is this a ruler or a commander?" IS already a field —
#     tags.json occupation_family — so that cap needs no curation at all
#     and keeps working for items added after this list was written.
#
# Together they cover both failure modes: the list catches the specific
# subjects that make an issue grim, and the occupation share catches the
# broader "history as nothing but kings and generals" drift even among
# entirely benign figures.
# ---------------------------------------------------------------------------
def is_dark_tone(cfg, game, item_id):
    """True if this exact pool item carries the curated dark-tone tag.
    Unknown ids are untagged — never a rejection, same convention as every
    other signal here."""
    tags = cfg.get("dark_tone_ids") or {}
    return item_id in set(tags.get(game) or ())


def is_power_figure(sig, cfg):
    """True if the item's occupation_family is a ruler/statesman/commander
    family. None (no tag match) is 'no opinion' and never counts."""
    fam = sig.get("occupation_family")
    return bool(fam) and fam in set(cfg.get("power_occupation_families") or ())


def western_bias_score(sig, cfg):
    """Lower sorts earlier (preferred) in `ranked`. Zero (neutral) when
    there's no fame signal at all, or when the item is famous enough to be
    an "icon" that transcends English-Wikipedia-specific traffic (Part B
    rule 5) — pv_pct only nudges the broad "solidly good, not one-name-
    famous" middle of the pool, never icons and never unmatched items."""
    fame, pv = sig.get("fame"), sig.get("pv_pct")
    if fame is None or pv is None or fame >= cfg["icon_fame_threshold"]:
        return 0.0
    return -pv * cfg["western_bias_weight"]


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
    fame_idx, tag_idx = load_signal_indices()

    # Reserve mechanism (Part A, 24 Jul 2026): "reserve": true on a live
    # record pulls it out of every normal-day candidate pool below — it
    # simply never appears in by_tier/thread_by_tier, so it can never be
    # picked by propose. It is NOT removed from the data files, and it is
    # NOT filtered out of `pools`/`id_index` (unfiltered — freeze, verify and
    # the review sheet all resolve ids against the full pool, since already-
    # approved manifest editions may legitimately reference a now-reserved
    # id). Encore (js/daily.js encoreItems) replays past editions by id and
    # never looks at this field either way, so a reserved item that has
    # aired at least once keeps working there with zero extra code.
    by_tier = {g: {t: [x for x in pools[g] if x["difficulty"] == t and not x.get("reserve")]
                   for t in TIERS}
               for g in ("who", "map", "what")}
    thread_by_tier = {t: [x for x in pools["thread"] if x["difficulty"] == t and not x.get("reserve")]
                      for t in TIERS}
    id_index = {g: {x["id"]: x for x in pools[g]} for g in GAMES}

    def gap_days(game, item_id, on_date):
        la = last_aired.get((game, item_id))
        return None if la is None else (on_date - la).days

    def eligible(game, item, on_date, day_answers, extra_reject, day_subjects=None):
        """Hard constraints only. Returns (ok, reason).

        require_sources is checked here, inside propose, which by
        construction only ever considers unaired editions after `start`
        (today or later) — freeze (past/aired editions) and approve
        (promoting an already-generated proposal) never call this, so
        flipping the flag on automatically scopes it to editions proposed
        from now on without any extra date bookkeeping (P3.6).

        day_subjects (Part B rule 2, 24 Jul 2026): the union of every
        variant string already committed today, across every game including
        Thread — the "same underlying subject" heuristic. If none of
        `item`'s own variants overlap it, it's unrelated to anything already
        scheduled today; an overlap means some other candidate already
        picked today shares a distinctive alias with this one (e.g. two
        different Pompeii artefacts), so it's rejected same as a straight
        answer collision. Deliberately coarse per spec — flagged in the
        compiler's report, not hardened into a fragile detector."""
        g = gap_days(game, item["id"], on_date)
        if g is not None and g < floor:
            return False, f"aired {g}d ago (floor {floor})"
        # Tone cap, HARD and never relaxed (unlike the variety caps): the
        # dark-tone pool is a small tagged minority of every game's pool, so
        # there is always an untagged alternative and bending this could
        # only ever be a convenience, never a necessity. Checked here rather
        # than in caps_ok() so it also governs Thread board selection and
        # the guaranteed-banker repair, both of which bypass caps_ok.
        if is_dark_tone(cfg, game, item["id"]) \
                and day_tone["dark"] >= cfg["max_dark_tone_per_issue"]:
            reason = (f"tone cap: this issue already has "
                      f"{day_tone['dark']} dark-tone subject"
                      f"{'s' if day_tone['dark'] != 1 else ''} "
                      f"(max {cfg['max_dark_tone_per_issue']})")
            tone_rejects.setdefault((game, item["id"]),
                                    (item.get("name") or item["id"], reason))
            return False, reason
        if game in ("who", "what"):
            if not (ROOT / item["img"]).exists():
                return False, "image missing on disk"
        if game == "map":
            if haversine_km(item["birth"], item["death"]) < cfg["min_lifeline_km"] \
                    and not item.get("allow_close"):
                return False, f"birth-death < {cfg['min_lifeline_km']}km"
        if cfg["require_sources"] and not is_sourced(item):
            return False, "unsourced or unconfident (require_sources on — " \
                          "needs fact_sources[] + a confidence tag; see P3.1/P3.6)"
        if game == "thread":
            keys = thread_answer_keys(item)
            if keys & day_answers:
                return False, "tile/label collides with today's answers"
            if day_subjects and keys & day_subjects:
                return False, "tile/label shares a subject with today's picks"
        else:
            if normalise(item["name"]) in day_answers:
                return False, "answer already used today"
            if day_subjects:
                item_variants = {normalise(v) for v in item.get("variants") or []}
                if item_variants & day_subjects:
                    return False, "shares a distinctive variant with today's picks (same subject)"
        if extra_reject and item["id"] in extra_reject:
            return False, "already picked today"
        return True, ""

    def ranked(pool, game, on_date, bias_fn=None):
        """Never-aired first, then longest-since-aired, then the Part B
        ranking bias (western-audience pv_pct tiebreak + era-novelty nudge,
        24 Jul 2026 — zero for every candidate when bias_fn is None), then
        pool order (curated best-first, per QUALITY_RUBRIC.md). Because most
        of a growing pool is never-aired, the first two keys tie for the
        bulk of candidates and the bias becomes the real differentiator —
        which is exactly where it should matter most: picking what enters
        rotation for the first time."""
        def key(pair):
            i, item = pair
            la = last_aired.get((game, item["id"]))
            b = bias_fn(item) if bias_fn else 0.0
            return (0 if la is None else 1, la or date.min, b, i)
        return [item for _, item in sorted(enumerate(pool), key=key)]

    editions = {}
    warnings = {}   # str(n) -> [ {kind, game, id, text} ]
    stopped_short = None

    for n in range(start, start + args.days):
        on_date = edition_date(n)
        wd = weekday(n)
        day_answers = set()
        day_subjects = set()  # Part B rule 2: variants of every item picked
                               # today, any game — the "same underlying
                               # subject" net (see eligible()'s day_subjects)
        picked_today = {g: [] for g in GAMES}
        warns = []

        # --- tone state, ISSUE-level (25 Jul 2026) ------------------------
        # Counted across the whole issue rather than per game, because the
        # failure the launch review named is an EDITION that reads as one
        # dark theme — Hitler in Face Value plus Stalin in Lifeline plus a
        # board about assassinations is exactly the day being guarded
        # against, and no per-game counter would ever see it.
        day_tone = {"dark": 0, "power": 0}
        # Rejections are recorded, not silent: one entry per (game, id) per
        # day, surfaced as warnings on the review sheet and as an aggregate
        # on stdout.
        tone_rejects = {}

        # The power-share denominator is known before any pick is made: the
        # issue's human answers are the who quota plus the map quota, which
        # the recipe fixes at 5 + 5. Deriving it from the recipe rather than
        # hard-coding 10 keeps this correct if the recipe ever changes.
        human_slots = sum(NEW_RECIPE[wd]) * 2
        power_cap = int(cfg["max_power_share_per_issue"] * human_slots)

        def note(kind, game, item_id, text):
            warns.append({"kind": kind, "game": game, "id": item_id, "text": text})

        def soft_checks(game, item):
            g = gap_days(game, item["id"], on_date)
            if g is not None and g < target:
                note("repeat-target", game, item["id"],
                     f"last aired {g} days ago (target {target})")
            if game in ("who", "what") and not item.get("license"):
                note("licence-missing", game, item["id"], "no licence field")

        def ensure_banker(game, chosen, chosen_ids):
            """Part B rule 3 (who/what only): every day needs >=1 item at or
            above banker_fame_threshold — never five genuine unknowns. If the
            round as picked has none, try swapping the LOWEST-fame pick
            *within its own tier* (so the day's difficulty mix survives) for
            the best eligible candidate anywhere in the pool. Among fame-
            qualified candidates, banker_pv_pct_preference is a soft
            tiebreak: an English-Wikipedia-legible pick (pv_pct at or above
            the preference) is offered before a candidate that only clears
            the fame bar on strength of a less Western-recognisable record —
            fame is still the hard gate, pv_pct only reorders who's tried
            first among those that already pass it. Best-effort: if no safe
            swap exists this never raises Shortage, it just flags the day
            for a human look."""
            def fame_of(it):
                return item_signal(game, it, fame_idx, tag_idx).get("fame")

            def pv_of(it):
                return item_signal(game, it, fame_idx, tag_idx).get("pv_pct")

            def is_banker(it):
                f = fame_of(it)
                return f is not None and f >= cfg["banker_fame_threshold"]

            if any(is_banker(it) for it in chosen):
                return chosen
            # Pre-filter to fame-qualified candidates (the hard gate), THEN
            # order by the pv_pct preference bucket, THEN by fame within
            # each bucket — filtering first keeps this correct regardless of
            # how the two orderings interact (no reliance on one sorted
            # pass staying monotonic in fame).
            qualified = [it for t in TIERS for it in by_tier[game][t] if is_banker(it)]

            def pv_bucket(it):
                pv = pv_of(it)
                return 0 if (pv is not None and pv >= cfg["banker_pv_pct_preference"]) else 1

            pool = sorted(qualified,
                          key=lambda it: (pv_bucket(it), -fame_of(it)))
            for cand in pool:
                f = fame_of(cand)
                if cand["id"] in chosen_ids:
                    continue
                same_tier = [it for it in chosen if it["difficulty"] == cand["difficulty"]] or chosen
                weakest = min(same_tier, key=lambda it: (fame_of(it) if fame_of(it) is not None else -1))
                w_variants = {normalise(v) for v in weakest.get("variants") or []}
                # The tone counters have to come off with the item being
                # swapped out, or the cap would be evaluated against a state
                # that includes a pick we are in the middle of withdrawing —
                # a banker repair that removes Hitler must be allowed to
                # bring in another dark-tone subject if it needs to.
                w_dark = is_dark_tone(cfg, game, weakest["id"])
                w_power = is_power_figure(
                    item_signal(game, weakest, fame_idx, tag_idx), cfg)
                chosen_ids.discard(weakest["id"])
                day_answers.discard(normalise(weakest["name"]))
                day_subjects.difference_update(w_variants)
                if w_dark:
                    day_tone["dark"] -= 1
                if w_power:
                    day_tone["power"] -= 1
                ok, _ = eligible(game, cand, on_date, day_answers, chosen_ids, day_subjects)
                if not ok:
                    chosen_ids.add(weakest["id"])
                    day_answers.add(normalise(weakest["name"]))
                    day_subjects.update(w_variants)
                    if w_dark:
                        day_tone["dark"] += 1
                    if w_power:
                        day_tone["power"] += 1
                    continue
                chosen_ids.add(cand["id"])
                day_answers.add(normalise(cand["name"]))
                day_subjects.update(normalise(v) for v in cand.get("variants") or [])
                if is_dark_tone(cfg, game, cand["id"]):
                    day_tone["dark"] += 1
                if is_power_figure(item_signal(game, cand, fame_idx, tag_idx), cfg):
                    day_tone["power"] += 1
                note("banker-repair", game, cand["id"],
                     f"swapped in as the day's guaranteed banker (fame {f:.1f}), "
                     f"replacing {weakest['id']}")
                return [cand if it is weakest else it for it in chosen]
            note("no-banker", game, None,
                 "no top-quartile-fame item available for this day's round "
                 "even after a repair attempt — flagging for manual review")
            return chosen

        try:
            # --- Thread first: one board, least flexible pool -------------
            tier = THREAD_TIER[wd]
            board = None
            for cand in ranked(thread_by_tier[tier], "thread", on_date):
                ok, _ = eligible("thread", cand, on_date, day_answers, None, day_subjects)
                if ok:
                    board = cand
                    break
            if board is None:
                raise Shortage(n, "thread", tier, 1, 0)
            picked_today["thread"] = [board["id"]]
            day_answers |= thread_answer_keys(board)
            day_subjects |= thread_answer_keys(board)
            # Thread is picked FIRST, so a dark-themed board (assassinations,
            # the Terror, the witch hunts, plague) spends the issue's single
            # dark-tone allowance before any portrait is chosen. That
            # ordering is deliberate: Thread has the least flexible pool, so
            # it should be the one that gets to claim the allowance.
            if is_dark_tone(cfg, "thread", board["id"]):
                day_tone["dark"] += 1
            soft_checks("thread", board)

            # --- Rounds games: who, map, what -----------------------------
            # Two passes, like the client: every tier's PRIMARY quota is
            # served from its own pool first, then shortfalls backfill from
            # the adjacent tier — so a starved easy tier can never strip the
            # medium pool before medium's own quota is met. Part B layers
            # three more things into this same pass structure: variety caps
            # (region/occupation — strict first, relaxed only if a tier
            # can't otherwise be filled), a ranking bias (western-audience
            # pv_pct tiebreak + era-novelty nudge, rules 1 & 5), and — after
            # both passes — a guaranteed-banker repair (rule 3).
            for game in ("who", "map", "what"):
                counts = NEW_RECIPE[wd]
                chosen_ids = set()
                round_region = Counter()   # macroregion -> count so far this round
                round_occ = Counter()      # occupation_family -> count so far (who/map)
                round_era = set()          # eras already represented this round
                got_by_tier = {t: [] for t in TIERS}

                def bias_for(tier):
                    exempt = (cfg["western_bias_sunday_exempt"] and wd == 6) or \
                             (cfg["western_bias_hard_exempt"] and tier == "hard")
                    want_era = len(round_era) < cfg["min_era_diversity_per_round"]

                    def bias(item):
                        sig = item_signal(game, item, fame_idx, tag_idx)
                        score = 0.0 if exempt else western_bias_score(sig, cfg)
                        if want_era and sig.get("era") and sig["era"] not in round_era:
                            score -= cfg["era_novelty_bonus"]
                        return score
                    return bias

                def caps_ok(item, relax=0):
                    """relax is a LADDER, not a switch:
                       0 — every cap applies;
                       1 — the region/occupation variety caps bend;
                       2 — the rulers-and-commanders share bends too.
                    Tone is the last thing to give, because a day that is
                    merely repetitive in region is a smaller failure than a
                    day that is all kings and generals. (The dark-tone cap
                    lives in eligible() and bends at no level at all.)"""
                    sig = item_signal(game, item, fame_idx, tag_idx)
                    if relax < 1:
                        region = sig.get("region")
                        if region and round_region[region] >= cfg["max_region_per_round"]:
                            return False
                        occ = sig.get("occupation_family") if game in ("who", "map") else None
                        if occ and round_occ[occ] >= cfg["max_occupation_per_round"]:
                            return False
                    if relax >= 2:
                        return True
                    # Rulers-and-commanders share of the issue's human
                    # answers. SOFT, and lives here rather than in
                    # eligible() precisely so it participates in the
                    # existing relax_caps escape hatch: a thin tier that
                    # genuinely cannot fill any other way bends this and
                    # says so, rather than raising Shortage.
                    if game in ("who", "map") and is_power_figure(sig, cfg) \
                            and day_tone["power"] >= power_cap:
                        reason = (f"tone cap: {day_tone['power']} of this "
                                  f"issue's {human_slots} human answers are "
                                  f"already rulers/commanders (max {power_cap})")
                        tone_rejects.setdefault(
                            (game, item["id"]),
                            (item.get("name") or item["id"], reason))
                        return False
                    return True

                def commit(item):
                    chosen_ids.add(item["id"])
                    day_answers.add(normalise(item["name"]))
                    day_subjects.update(normalise(v) for v in item.get("variants") or [])
                    sig = item_signal(game, item, fame_idx, tag_idx)
                    if sig.get("region"):
                        round_region[sig["region"]] += 1
                    if sig.get("occupation_family"):
                        round_occ[sig["occupation_family"]] += 1
                    if sig.get("era"):
                        round_era.add(sig["era"])
                    if is_dark_tone(cfg, game, item["id"]):
                        day_tone["dark"] += 1
                    if game in ("who", "map") and is_power_figure(sig, cfg):
                        day_tone["power"] += 1

                def fill(pool_tier, need, slot_tier, relax=0, backfill_note_tier=None):
                    """Pick up to `need` items from by_tier[game][pool_tier],
                    one at a time (so caps/era-novelty react after each
                    pick). slot_tier is the day's REQUESTED tier — the
                    western-bias exemption depends on that, not on which
                    pool a backfilled item is borrowed from."""
                    got = []
                    for _ in range(need):
                        cand_pool = ranked(by_tier[game][pool_tier], game, on_date,
                                          bias_fn=bias_for(slot_tier))
                        pick = None
                        for cand in cand_pool:
                            if cand["id"] in chosen_ids:
                                continue
                            ok, _ = eligible(game, cand, on_date, day_answers,
                                             chosen_ids, day_subjects)
                            if not ok:
                                continue
                            if not caps_ok(cand, relax):
                                continue
                            pick = cand
                            break
                        if pick is None:
                            break
                        commit(pick)
                        if backfill_note_tier:
                            note("tier-backfill", game, pick["id"],
                                 f"{pool_tier} item in a {backfill_note_tier} slot — "
                                 f"{backfill_note_tier} pool blocked by the {floor}-day floor")
                        got.append(pick)
                    return got

                def relax_ladder(pool_tier, short, slot_tier, where,
                                 backfill_note_tier=None):
                    """Bend one rung at a time and report which rung it was.
                    Before 25 Jul 2026 this was a single boolean that dropped
                    every cap at once — which silently took the tone cap with
                    it, so an edition could end up all rulers with only a
                    'relaxed the region/occupation caps' note to show for it."""
                    got = []
                    for rung, kind, what in (
                            (1, "variety-cap-relaxed",
                             "the region/occupation caps"),
                            (2, "tone-cap-relaxed",
                             "the rulers-and-commanders share cap (the "
                             "dark-tone cap still held)")):
                        if short <= 0:
                            break
                        extra = fill(pool_tier, short, slot_tier, relax=rung,
                                     backfill_note_tier=backfill_note_tier)
                        if extra:
                            note(kind, game, None,
                                 f"{where}: relaxed {what} to fill "
                                 f"{len(extra)} more slot(s)")
                        got += extra
                        short -= len(extra)
                    return got

                for ti, tier in enumerate(TIERS):
                    need = counts[ti]
                    if need <= 0:
                        continue
                    got_by_tier[tier] = fill(tier, need, tier, relax=0)
                    short = need - len(got_by_tier[tier])
                    if short > 0:
                        got_by_tier[tier] += relax_ladder(tier, short, tier, tier)
                # Backfill pass: the repeat floor is sacred; the difficulty
                # mix bends next (flagged); variety caps bend last of all,
                # and only inside this already-relaxed backfill (flagged
                # separately so the two are never confused on the sheet).
                for ti, tier in enumerate(TIERS):
                    need = counts[ti]
                    if need <= 0 or len(got_by_tier[tier]) >= need:
                        continue
                    lender = "medium" if tier in ("hard", "easy") else "easy"
                    short = need - len(got_by_tier[tier])
                    extra = fill(lender, short, tier, relax=0, backfill_note_tier=tier)
                    if len(extra) < short:
                        extra += relax_ladder(lender, short - len(extra), tier,
                                              f"{tier} backfill",
                                              backfill_note_tier=tier)
                    got_by_tier[tier] += extra
                    if len(got_by_tier[tier]) < need:
                        raise Shortage(n, game, tier, need, len(got_by_tier[tier]))

                chosen = []
                for tier in TIERS:
                    chosen.extend(got_by_tier[tier])
                if game in ("who", "what"):
                    chosen = ensure_banker(game, chosen, chosen_ids)
                for item in chosen:
                    soft_checks(game, item)
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

            # --- tone: what the cap did, and what the day ended up like ---
            # Rejections are reported, never silent — the whole point of a
            # taste rule is that a human can see it firing and disagree.
            for (rej_game, rej_id), (rej_name, rej_reason) in sorted(
                    tone_rejects.items()):
                note("tone-cap", rej_game, rej_id,
                     f"“{rej_name}” skipped — {rej_reason}")
            note("tone-summary", None, None,
                 f"issue tone: {day_tone['dark']} dark-tone subject"
                 f"{'s' if day_tone['dark'] != 1 else ''} "
                 f"(max {cfg['max_dark_tone_per_issue']}), "
                 f"{day_tone['power']}/{human_slots} human answers are "
                 f"rulers/commanders (max {power_cap})")

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
    # --out lets a batch be generated and inspected without touching the
    # live proposals file — the dry run used to demonstrate a rule change.
    out_path = Path(args.out).resolve() if getattr(args, "out", None) else PROPOSED
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(proposed, indent=1, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    sheet = write_review_sheet(proposed, pools, id_index, manifest,
                               name_hint=(out_path.stem
                                          if out_path != PROPOSED else None))

    n_warn = sum(len(v) for v in warnings.values())
    try:
        shown = out_path.relative_to(ROOT)
    except ValueError:
        shown = out_path
    print(f"propose: {len(editions)} editions written to "
          f"{shown} (editions {start}–{start + len(editions) - 1})")
    print(f"propose: review sheet -> {sheet.relative_to(ROOT)}")
    print(f"propose: {n_warn} soft warnings across {len(warnings)} editions")
    for kind, cnt in Counter(w["kind"] for v in warnings.values() for w in v).most_common():
        print(f"  {kind}: {cnt}")

    # --- tone report: never let a taste rule fire silently ----------------
    tone_hits = [(k, w) for k, v in warnings.items() for w in v
                 if w["kind"] == "tone-cap"]
    print(f"\npropose: tone cap rejected {len(tone_hits)} candidate(s) across "
          f"{len(set(k for k, _ in tone_hits))} edition(s) "
          f"(max_dark_tone_per_issue={cfg['max_dark_tone_per_issue']}, "
          f"max_power_share_per_issue={cfg['max_power_share_per_issue']} "
          f"→ {int(cfg['max_power_share_per_issue'] * 10)} of 10 human answers)")
    for k, w in tone_hits:
        print(f"  № {k} ({editions[k]['date']}) {w['game']}/{w['id']}: {w['text']}")
    if not tone_hits:
        print("  (no candidate was blocked on tone in this batch)")
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

# Verdict/comment widget injected under every puzzle. State lives in the
# browser's localStorage (survives refresh); "Copy"/"Save" export only the
# flagged/commented items as plain text for Daniel to hand back in chat.
RV_JS = r"""
(function () {
  var NS = "dfrv:" + RVGEN + ":";
  function get(k) {
    try { return JSON.parse(localStorage.getItem(NS + k)) || {}; }
    catch (e) { return {}; }
  }
  function set(k, v) {
    try { localStorage.setItem(NS + k, JSON.stringify(v)); } catch (e) {}
  }
  var VERDICTS = [["air", "✅ fine"], ["swap", "🔄 swap"],
                  ["fix", "✏️ fix"]];
  var els = Array.prototype.slice.call(document.querySelectorAll(".rv"));
  els.forEach(function (el) {
    var key = el.dataset.rv;
    var btns = document.createElement("div");
    btns.className = "vbtns";
    VERDICTS.forEach(function (v) {
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = v[1];
      b.dataset.v = v[0];
      if (get(key).v === v[0]) b.classList.add("on");
      b.onclick = function () {
        var st = get(key);
        st.v = st.v === v[0] ? "" : v[0];
        set(key, st);
        Array.prototype.forEach.call(btns.children, function (x) {
          x.classList.toggle("on", x.dataset.v === st.v);
        });
        paint();
      };
      btns.appendChild(b);
    });
    var ta = document.createElement("textarea");
    ta.placeholder = "comment…";
    ta.value = get(key).c || "";
    ta.oninput = function () {
      var st = get(key);
      st.c = ta.value;
      set(key, st);
      paint();
    };
    el.appendChild(btns);
    el.appendChild(ta);
  });

  var bar = document.createElement("div");
  bar.id = "rvbar";
  var count = document.createElement("span");
  var copyB = document.createElement("button");
  copyB.textContent = "Copy verdicts";
  var saveB = document.createElement("button");
  saveB.textContent = "Save verdicts file";
  bar.appendChild(count);
  bar.appendChild(copyB);
  bar.appendChild(saveB);
  document.body.appendChild(bar);

  function collect() {
    var flags = 0, byEd = {}, order = [];
    els.forEach(function (el) {
      var st = get(el.dataset.rv);
      var note = (st.c || "").trim();
      var flagged = st.v === "swap" || st.v === "fix";
      el.classList.toggle("flagged", flagged);
      if (!flagged && !note) return;
      flags++;
      var parts = (el.dataset.rvl || el.dataset.rv).split(" · ");
      var ed = parts[0];
      if (!byEd[ed]) { byEd[ed] = []; order.push(ed); }
      byEd[ed].push("  [" + (st.v || "note") + "] " +
        parts.slice(1).join(" · ") + (note ? " — " + note : ""));
    });
    var out = ["Dead Famous edition review " + RVGEN + " — verdicts"];
    order.forEach(function (ed) {
      out.push(ed);
      out.push.apply(out, byEd[ed]);
    });
    out.push(flags ? "(everything not listed: fine to air)"
                   : "(no flags — everything fine to air)");
    return { text: out.join("\n"), flags: flags };
  }
  function paint() {
    count.textContent = collect().flags + " flagged / commented";
  }
  copyB.onclick = function () {
    var t = collect().text;
    function ok() {
      copyB.textContent = "Copied ✓";
      setTimeout(function () { copyB.textContent = "Copy verdicts"; }, 1500);
    }
    function fallback() {
      var ta = document.createElement("textarea");
      ta.value = t;
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); ok(); } catch (e) { alert(t); }
      document.body.removeChild(ta);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(t).then(ok, fallback);
    } else fallback();
  };
  saveB.onclick = function () {
    var blob = new Blob([collect().text], { type: "text/plain" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "deadfamous-verdicts-" + RVGEN + ".txt";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };
  paint();
})();
"""


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


def write_review_sheet(proposed, pools, id_index, manifest, name_hint=None):
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
                    f'{e(it.get("attribution", ""))} · {gap_label(gp)}</small>'
                    f'<div class="rv" data-rv="{n}:{game}:{e(item_id)}"'
                    f' data-rvl="№ {n} · {title} · {e(it["name"])}"></div>'
                    f'</div></div>')
            rows.append("</div>")

        rows.append("<h3>Lifeline</h3><table><tr><th>figure</th><th>tier</th>"
                    "<th>birth → death</th><th>km</th><th>history</th>"
                    "<th>your verdict</th></tr>")
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
                f'<td>{km:,.0f}</td><td><small>{gap_label(gp)}</small></td>'
                f'<td class="rvcell"><div class="rv" data-rv="{n}:map:{e(item_id)}"'
                f' data-rvl="№ {n} · Lifeline · {e(it["name"])}"></div></td></tr>')
        rows.append("</table>")

        board = id_index["thread"][ed["thread"][0]]
        gp = gap_at("thread", board["id"], on_date)
        rows.append(f'<h3>Thread — “{e(board.get("title", board["id"]))}” '
                    f'<i>({e(board["difficulty"])}, {gap_label(gp)})</i></h3>')
        for g in board["groups"]:
            hexc = COLOUR_HEX.get(g.get("colour"), "#999")
            rows.append(f'<div class="tgroup" style="border-left:14px solid {hexc}">'
                        f'<b>{e(g["label"])}</b>: {e(" · ".join(g["items"]))}</div>')
        rows.append(f'<div class="rv rvwide" data-rv="{n}:thread:{e(board["id"])}"'
                    f' data-rvl="№ {n} · Thread · {e(board.get("title", board["id"]))}"></div>')
        rows.append("</section>")

    rows.append('<section class="edition"><h2>Anything else</h2>'
                '<div class="rv rvwide" data-rv="general"'
                ' data-rvl="General · overall notes"></div></section>')

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
 .rv {{ margin-top: .4rem }}
 .rv .vbtns {{ display: flex; gap: .3rem; margin-bottom: .25rem }}
 .rv button {{ font: inherit; font-size: .75rem; padding: .1rem .5rem;
              border: 1px solid #C9C4B4; background: #F7F5EC; cursor: pointer }}
 .rv button.on {{ background: #0B0B0B; color: #fff; border-color: #0B0B0B }}
 .rv textarea {{ width: 100%; box-sizing: border-box; min-height: 2.1rem;
                font: inherit; font-size: .8rem; border: 1px solid #C9C4B4;
                padding: .25rem .4rem; background: #FFFDF6; resize: vertical }}
 .rv.flagged textarea {{ border-color: #E02020; border-width: 2px }}
 .rvcell {{ min-width: 11rem }}
 .rvwide {{ max-width: 40rem }}
 #rvbar {{ position: fixed; bottom: 0; left: 0; right: 0; background: #0B0B0B;
          color: #F2EFE6; display: flex; gap: .8rem; align-items: center;
          padding: .5rem 1rem; font-size: .85rem; z-index: 9 }}
 #rvbar button {{ font: inherit; padding: .25rem .8rem; cursor: pointer;
                 border: 2px solid #F2EFE6; background: transparent; color: #F2EFE6 }}
 #rvbar button:hover {{ background: #F2EFE6; color: #0B0B0B }}
 body {{ padding-bottom: 4.5rem }}
</style>
<h1>Edition review — proposed {e(proposed['generatedOn'])}</h1>
<p class="config">Recipe 5 who + 5 map + 5 what + 1 thread ·
floor {cfg['repeat_floor_days']}d · target {cfg['repeat_target_days']}d ·
min Lifeline {cfg['min_lifeline_km']}km · {len(proposed['editions'])} editions ·
{n_warn} warnings. Legend: scrap grid — <span style="color:#E02020">red</span>
opens torn, black is the money shot.</p>
{''.join(rows)}
"""
    doc += ("<script>var RVGEN = "
            + json.dumps(proposed["generatedOn"])
            + ";" + RV_JS + "</script>\n")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"review-{proposed['generatedOn']}"
    if name_hint:
        stem += f"-{name_hint}"
    out = OUT_DIR / f"{stem}.html"
    out.write_text(doc, encoding="utf-8")
    return out


def cmd_review(_args):
    """Re-render the review sheet from the existing proposals file. Never
    touches the proposals themselves — safe after a sheet-template change."""
    if not PROPOSED.exists():
        print("review: no data/editions.proposed.json — run propose first.",
              file=sys.stderr)
        return 1
    proposed = json.loads(PROPOSED.read_text(encoding="utf-8"))
    pools = load_pools()
    id_index = {g: {x["id"]: x for x in pools[g]} for g in GAMES}
    sheet = write_review_sheet(proposed, pools, id_index, load_manifest())
    print(f"review: sheet re-rendered -> {sheet.relative_to(ROOT)}")
    return 0


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
# verify — the CI/test gate (P4.1/P4.2). Read-only, offline, fast.
# ---------------------------------------------------------------------------
def cmd_verify(args):
    """Check the manifest end-to-end: parses, contiguous, dates match the
    epoch, every id resolves, every who/what image exists, recipe sizes hold
    for compiled editions, and no answer appears in two games on one day.
    Collisions in LEGACY editions (n < recipeChangeEdition, frozen history
    produced by the old collision-blind algorithm) are warnings; in compiled
    editions they are errors. Exits non-zero on any error."""
    manifest_path = Path(args.manifest) if args.manifest else MANIFEST
    errors, warns = [], []
    err, warn = errors.append, warns.append

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:  # unreadable manifest = nothing airs tomorrow
        print(f"verify: FATAL — cannot read {manifest_path}: {e}", file=sys.stderr)
        return 1
    editions = manifest.get("editions")
    change = manifest.get("recipeChangeEdition")
    if not isinstance(editions, dict) or not editions:
        print("verify: FATAL — manifest has no editions", file=sys.stderr)
        return 1
    if not isinstance(change, int):
        err(f"recipeChangeEdition is {change!r}, expected an int")
        change = 10 ** 9  # treat everything as legacy so checks still run

    pools = load_pools()
    by_id = {g: {x["id"]: x for x in pools[g]} for g in GAMES}

    keys = sorted(int(k) for k in editions)
    if keys != list(range(keys[0], keys[-1] + 1)):
        err(f"editions are not contiguous: {keys[0]}..{keys[-1]} has holes")
    if keys and keys[0] != 0:
        warn(f"manifest starts at edition {keys[0]}, not 0")

    for k in keys:
        ed = editions[str(k)]
        legacy = k < change
        where = f"edition {k} ({ed.get('date', '?')})"
        if ed.get("date") != edition_date(k).isoformat():
            err(f"{where}: date should be {edition_date(k).isoformat()}")

        names = {}  # normalised display name -> (game, id), cross-game collision net
        for game in GAMES:
            ids = ed.get(game) or []
            if len(set(ids)) != len(ids):
                err(f"{where}: duplicate id inside '{game}': {ids}")
            want = 1 if game == "thread" else (10 if legacy else 5)
            if len(ids) != want:
                (warn if legacy else err)(
                    f"{where}: '{game}' has {len(ids)} ids, expected {want}")
            for i in ids:
                item = by_id[game].get(i)
                if item is None:
                    err(f"{where}: '{game}' id '{i}' resolves to nothing")
                    continue
                if game in ("who", "what"):
                    img = ROOT / item.get("img", "")
                    if not item.get("img") or not img.is_file():
                        err(f"{where}: image missing for {game}/{i}: {item.get('img')}")
                if game != "thread":
                    nm = normalise(item.get("name", ""))
                    if nm in names and names[nm][0] != game:
                        og, oi = names[nm]
                        (warn if legacy else err)(
                            f"{where}: answer collision — '{nm}' is both "
                            f"{og}/{oi} and {game}/{i}")
                    names[nm] = (game, i)

    for w in warns:
        print(f"WARN  {w}")
    for e2 in errors:
        print(f"ERROR {e2}", file=sys.stderr)
    print(f"verify: {len(keys)} editions ({keys[0]}..{keys[-1]}, recipe change "
          f"at {manifest.get('recipeChangeEdition')}) — "
          f"{len(errors)} errors, {len(warns)} warnings")
    return 1 if errors else 0


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("freeze", help="freeze editions 0..today under the current "
                                  "client algorithm")
    p = sub.add_parser("propose", help="draft the next N unaired editions")
    p.add_argument("--days", type=int, default=14)
    p.add_argument("--out", default=None, metavar="PATH",
                   help="write the batch here instead of "
                        "data/editions.proposed.json (dry run: leaves the "
                        "live proposals and the manifest untouched)")
    sub.add_parser("review", help="re-render the review sheet from existing "
                                  "proposals (no content re-roll)")
    a = sub.add_parser("approve", help="promote proposed editions into the manifest")
    a.add_argument("--through", required=True, metavar="YYYY-MM-DD")
    v = sub.add_parser("verify", help="validate the live manifest (CI gate): "
                                      "ids resolve, images exist, no collisions")
    v.add_argument("--manifest", default=None,
                   help="alternate manifest path (CI broken-manifest test)")
    args = ap.parse_args()
    return {"freeze": cmd_freeze, "propose": cmd_propose,
            "review": cmd_review, "approve": cmd_approve,
            "verify": cmd_verify}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
