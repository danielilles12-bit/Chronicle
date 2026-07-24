#!/usr/bin/env python3
"""
gap_report.py -- gap-analysis stage of the Dead Famous content pipeline.

Usage:
    python3 gap_report.py <scores.json> <out.json>

Reads a build_scores.py output (the CLI-supplied <scores.json>) plus four
fixed reference files that live alongside this script:
    current_inventory.json   -- the app's current who/what/map/thread-tile pools
    universe_people.json     -- birth_year/death_year/domain for candidate persons
    codex/01_dead_famous_figures.csv
    codex/02_dead_famous_objects.csv -- knowledge-picked comparison sets

...and writes a single JSON report with five sections:
    1. pool_health       -- every current who/what/map pool item joined with
                             its fame score, binned A-E within its own game.
    2. missing_bankers    -- high-fame candidates not yet in a pool.
    3. codex_vs_metrics  -- where the knowledge-picked codex CSVs and the
                             metrics-derived fame scores disagree.
    4. antiquity_check   -- the antiquity bench (death_year < 500, fame >= 50).
    5. summary            -- roll-up counts across all of the above.

Read-only with respect to data/, js/, cache/, fetch_metrics.py, build_scores.py
and any metrics_*.jsonl -- this script only reads the four reference files
above and the scores.json passed on the command line (plus a brand-new,
purely-additive cache/wikidata_death/ directory it creates for its own
death-year lookups -- see "Person enrichment" below). Python 3.9 stdlib only.

Person enrichment (domain + death_year fallback for codex-only people):
build_scores.py's "person" rows only carry a domain/death_year when the
title is also in universe_people.json. A meaningful slice of high-fame
people (mostly recent entertainers/athletes) are knowledge-picked into
codex/01_dead_famous_figures.csv but never made it into universe_people.json,
so without a fallback they silently default to policy_flag "needs_review"
instead of a real verdict. To close that gap this script:
  1. Falls back to codex/01's free-text "category" column (keyword-mapped
     to a domain) whenever universe_people.json has no domain for a title.
  2. For titles whose *domain* thereby resolves to "arts" or "sports" but
     which still have no death_year (i.e. not in universe_people.json at
     all), fetches the death year in one batched pass from Wikidata
     (enwiki title -> QID via action=query&prop=pageprops, then QID ->
     P570 via wbgetentities), 50 titles/QIDs per request, rate-limited to
     <=8 req/s, cached under cache/wikidata_death/ so reruns cost zero
     network calls. This is scoped tightly (arts/sports + missing
     death_year only) because that is the only combination where the
     death_year actually changes the policy_flag outcome.
"""

import csv
import hashlib
import json
import math
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
GENERATED_ON = "2026-07-22"

# Classes that build_scores.py treats as "man-made object" (as opposed to
# "person"). "other" is deliberately excluded from missing_bankers /
# codex_vs_metrics' object side -- it is the catch-all bucket for titles
# that matched none of the classification signals, not a real answer pool.
OBJECT_CLASSES = ("structure", "artwork", "artefact")

BIN_ORDER = ["A", "B", "C", "D", "E"]
BIN_FRACS = {"A": 0.15, "B": 0.25, "C": 0.30, "D": 0.20, "E": 0.10}

# Codex category (free-text, e.g. "actor and martial artist") -> domain,
# used only when universe_people.json has no domain for a title. Checked
# in this exact order, first keyword hit wins. "sports" is deliberately
# checked before "arts" (rather than in the coordinator's original prose
# order) so a combo category like "actor and martial artist" resolves to
# sports, not arts -- the simplification the coordinator asked for instead
# of a dedicated tie-break rule. Domains with no keyword bucket here
# (e.g. "military", "business") are intentionally not invented -- any
# category that matches nothing falls through to domain=None, i.e. still
# "needs_review", which is the correct conservative outcome for a mapping
# this script wasn't told how to make.
CATEGORY_DOMAIN_RULES = [
    ("sports", ("athlete", "martial artist")),
    ("arts", (
        "musician", "singer", "composer", "performer", "actor", "comedian",
        "dancer", "filmmaker", "artist", "photographer", "fashion designer",
        "writer",
    )),
    ("politics", ("statesman", "statesperson", "ruler", "dictator", "revolutionary", "political")),
    ("science", ("scientist", "inventor", "mathematician", "engineer", "computer scientist", "psychologist", "economist")),
    ("religion", ("religious",)),
    ("exploration", ("explorer", "aviator", "astronaut", "mountaineer")),
    ("other", ("crime figure",)),
]

# ---------------------------------------------------------------------------
# Wikidata death-year fallback config
# ---------------------------------------------------------------------------

WIKIDATA_UA = "DeadFamousIntake/1.0 (daniel.illes12@gmail.com)"
WIKIDATA_MIN_INTERVAL = 1.0 / 8.0  # <= 8 req/s
WIKIDATA_BATCH_SIZE = 50
WIKIDATA_CACHE_DIR = SCRIPT_DIR / "cache" / "wikidata_death"
PAGEPROPS_CACHE_DIR = WIKIDATA_CACHE_DIR / "pageprops"
CLAIMS_CACHE_DIR = WIKIDATA_CACHE_DIR / "claims"

_last_wikidata_request_at = [0.0]


# ---------------------------------------------------------------------------
# Small stats helpers (no imports from build_scores.py / fetch_metrics.py --
# duplicated on purpose so this script has zero coupling to code that isn't
# allowed to be touched or that could carry network-capable side effects).
# ---------------------------------------------------------------------------

def percentile(sorted_vals, pct):
    """Linear-interpolation percentile (0-100) of an already-sorted list.
    Returns None for an empty list (callers must guard div-by-zero-shaped
    situations themselves; this never raises)."""
    n = len(sorted_vals)
    if n == 0:
        return None
    if n == 1:
        return float(sorted_vals[0])
    k = (pct / 100.0) * (n - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def bin_allocation(n):
    """Largest-remainder (Hamilton) apportionment of n items into the 5
    proposed_bin buckets at their target fractions (15/25/30/20/10%).
    Pure multiplication, no division -- safe for any n >= 0 including 0
    and 1, so per-game binning never risks a division error on a small or
    empty scored pool."""
    floors = {label: 0 for label in BIN_ORDER}
    if n <= 0:
        return floors
    raw = {label: BIN_FRACS[label] * n for label in BIN_ORDER}
    for label in BIN_ORDER:
        floors[label] = int(raw[label])
    remainder = n - sum(floors.values())
    order_by_remainder = sorted(
        BIN_ORDER, key=lambda l: (-(raw[l] - floors[l]), BIN_ORDER.index(l))
    )
    for i in range(remainder):
        floors[order_by_remainder[i]] += 1
    return floors


def assign_proposed_bins(rows_desc_by_fame):
    """rows_desc_by_fame: list of dicts, already sorted fame-descending,
    all with a non-null 'fame'. Mutates 'proposed_bin' in place."""
    counts = bin_allocation(len(rows_desc_by_fame))
    idx = 0
    for label in BIN_ORDER:
        for _ in range(counts[label]):
            rows_desc_by_fame[idx]["proposed_bin"] = label
            idx += 1


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_inventory(path):
    data = load_json(path)
    items = data.get("items", [])
    by_game = {}
    for it in items:
        by_game.setdefault(it.get("game"), []).append(it)
    return items, by_game


def load_people(path):
    data = load_json(path)
    by_title = {}
    for p in data.get("people", []):
        t = p.get("wiki_title")
        if t and t not in by_title:
            by_title[t] = p
    return by_title


def load_codex_csv(path):
    by_title = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            t = row.get("exact_english_wikipedia_article_title")
            if t and t not in by_title:
                by_title[t] = row
    return by_title


def pool_title_set(inv_by_game, game):
    return {it["wiki_title"] for it in inv_by_game.get(game, []) if it.get("wiki_title")}


def policy_flag_for_person(domain, death_year):
    """People-only policy flags. Never filters -- callers always keep the
    row, this only annotates it."""
    if domain is None:
        return "needs_review"
    if domain in ("arts", "sports") and isinstance(death_year, (int, float)) and death_year >= 2016:
        return "recent_entertainment"
    return None


def domain_from_codex_category(category_str):
    """Best-effort domain from codex/01's free-text 'category' column, per
    CATEGORY_DOMAIN_RULES. Returns None if nothing matches."""
    if not category_str:
        return None
    s = category_str.lower()
    for domain, keywords in CATEGORY_DOMAIN_RULES:
        for kw in keywords:
            if kw in s:
                return domain
    return None


def resolve_person_domain(title, people_by_title, codex_figures):
    """universe_people.json domain first; codex/01 category keyword-mapped
    as a fallback only when universe_people.json has none."""
    p = people_by_title.get(title)
    if p is not None and p.get("domain") is not None:
        return p["domain"]
    row = codex_figures.get(title)
    if row is not None:
        return domain_from_codex_category(row.get("category"))
    return None


# ---------------------------------------------------------------------------
# Wikidata death-year fallback -- stdlib urllib only, no imports from
# fetch_metrics.py (kept fully independent, same reasoning as the
# percentile()/cache duplication above).
# ---------------------------------------------------------------------------

def _hash_key(key):
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def _cache_read(dir_path, key):
    p = dir_path / f"{_hash_key(key)}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _cache_write(dir_path, key, value):
    dir_path.mkdir(parents=True, exist_ok=True)
    p = dir_path / f"{_hash_key(key)}.json"
    p.write_text(json.dumps(value), encoding="utf-8")


def _wikidata_get_json(url):
    """Rate-limited (<=8 req/s) GET returning (ok, data). ok=False on any
    network/parse failure -- callers must NOT cache a negative result when
    ok is False, so a transient failure doesn't get baked in forever."""
    now = time.monotonic()
    wait = WIKIDATA_MIN_INTERVAL - (now - _last_wikidata_request_at[0])
    if wait > 0:
        time.sleep(wait)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": WIKIDATA_UA})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
        return True, json.loads(body)
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError):
        return False, None
    finally:
        _last_wikidata_request_at[0] = time.monotonic()


def fetch_qids_for_titles(titles):
    """enwiki title -> Wikidata QID via action=query&prop=pageprops, in
    batches of 50, cached per-title. Returns (qid_by_title, stats)."""
    qid_by_title = {}
    to_fetch = []
    cache_hits = 0
    for t in titles:
        cached = _cache_read(PAGEPROPS_CACHE_DIR, t)
        if cached is not None:
            qid_by_title[t] = cached.get("qid")
            cache_hits += 1
        else:
            to_fetch.append(t)

    requests_made = 0
    for i in range(0, len(to_fetch), WIKIDATA_BATCH_SIZE):
        batch = to_fetch[i:i + WIKIDATA_BATCH_SIZE]
        params = urllib.parse.urlencode({
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "pageprops",
            "ppprop": "wikibase_item",
            "redirects": "1",
            "titles": "|".join(batch),
        })
        url = f"https://en.wikipedia.org/w/api.php?{params}"
        ok, data = _wikidata_get_json(url)
        requests_made += 1
        if not ok:
            # Transient failure -- leave unresolved for this run, don't
            # cache, so a rerun retries these titles instead of the
            # failure being remembered as "no QID" forever.
            for t in batch:
                qid_by_title.setdefault(t, None)
            continue

        by_resolved_title = {}
        for page in (data.get("query") or {}).get("pages") or []:
            pt = page.get("title")
            qid = (page.get("pageprops") or {}).get("wikibase_item")
            if pt:
                by_resolved_title[pt] = qid
        redirect_map = {}
        for r in (data.get("query") or {}).get("redirects") or []:
            if r.get("from") and r.get("to"):
                redirect_map[r["from"]] = r["to"]

        for t in batch:
            resolved = redirect_map.get(t, t)
            qid = by_resolved_title.get(resolved)
            _cache_write(PAGEPROPS_CACHE_DIR, t, {"qid": qid})
            qid_by_title[t] = qid

    return qid_by_title, {"pageprops_cache_hits": cache_hits, "pageprops_requests": requests_made}


def _extract_p570_year(claims):
    for claim in (claims.get("P570") or []):
        try:
            time_str = claim["mainsnak"]["datavalue"]["value"]["time"]
        except (KeyError, TypeError):
            continue
        if not time_str:
            continue
        sign = -1 if time_str.startswith("-") else 1
        digits = time_str[1:].split("-")[0]
        try:
            return sign * int(digits)
        except ValueError:
            continue
    return None


def fetch_death_years_for_qids(qids):
    """QID -> death year via wbgetentities props=claims (P570 = date of
    death), in batches of 50, cached per-QID. Returns (year_by_qid, stats)."""
    death_year_by_qid = {}
    to_fetch = []
    cache_hits = 0
    for q in qids:
        cached = _cache_read(CLAIMS_CACHE_DIR, q)
        if cached is not None:
            death_year_by_qid[q] = cached.get("death_year")
            cache_hits += 1
        else:
            to_fetch.append(q)

    requests_made = 0
    for i in range(0, len(to_fetch), WIKIDATA_BATCH_SIZE):
        batch = to_fetch[i:i + WIKIDATA_BATCH_SIZE]
        params = urllib.parse.urlencode({
            "action": "wbgetentities",
            "format": "json",
            "props": "claims",
            "ids": "|".join(batch),
        })
        url = f"https://www.wikidata.org/w/api.php?{params}"
        ok, data = _wikidata_get_json(url)
        requests_made += 1
        if not ok:
            for q in batch:
                death_year_by_qid.setdefault(q, None)
            continue

        entities = data.get("entities") or {}
        for q in batch:
            ent = entities.get(q) or {}
            dy = _extract_p570_year(ent.get("claims") or {})
            _cache_write(CLAIMS_CACHE_DIR, q, {"death_year": dy})
            death_year_by_qid[q] = dy

    return death_year_by_qid, {"claims_cache_hits": cache_hits, "claims_requests": requests_made}


def fetch_wikidata_death_years(titles):
    """titles -> {title: death_year_or_None}, plus request-count stats."""
    titles = sorted(set(titles))
    if not titles:
        return {}, {
            "titles_needing_lookup": 0, "qids_resolved": 0, "death_years_found": 0,
            "pageprops_cache_hits": 0, "pageprops_requests": 0,
            "claims_cache_hits": 0, "claims_requests": 0,
        }
    qid_by_title, pp_stats = fetch_qids_for_titles(titles)
    qids = sorted({q for q in qid_by_title.values() if q})
    death_year_by_qid, claims_stats = fetch_death_years_for_qids(qids)

    result = {}
    found = 0
    for t in titles:
        q = qid_by_title.get(t)
        dy = death_year_by_qid.get(q) if q else None
        result[t] = dy
        if dy is not None:
            found += 1

    stats = {"titles_needing_lookup": len(titles), "qids_resolved": len(qids), "death_years_found": found}
    stats.update(pp_stats)
    stats.update(claims_stats)
    return result, stats


def build_person_enrichment(scores, people_by_title, codex_figures):
    """One pass over every scored 'person' title producing
    {title: {"domain", "birth_year", "death_year", "death_year_source"}}.

    domain: universe_people.json first, else codex/01 category fallback.
    death_year: universe_people.json first (source "universe"); for
    titles that still lack one AND whose resolved domain is "arts" or
    "sports" (the only case where it changes policy_flag), a batched
    Wikidata lookup fills it in (source "wikidata"). Everyone else keeps
    death_year=None, death_year_source=None -- untouched, since a missing
    death_year for a non-arts/sports (or already-flagged-needs_review)
    person can't change any policy_flag outcome.

    Returns (enrichment, wikidata_stats).
    """
    enrichment = {}
    wikidata_candidates = set()

    for s in scores:
        if s.get("class") != "person":
            continue
        title = s.get("wiki_title")
        if not title or title in enrichment:
            continue
        p = people_by_title.get(title)
        domain = resolve_person_domain(title, people_by_title, codex_figures)
        birth_year = p.get("birth_year") if p else None
        death_year = p.get("death_year") if p else None
        death_year_source = "universe" if (p is not None and death_year is not None) else None

        enrichment[title] = {
            "domain": domain,
            "birth_year": birth_year,
            "death_year": death_year,
            "death_year_source": death_year_source,
        }

        if death_year is None and domain in ("arts", "sports"):
            wikidata_candidates.add(title)

    wikidata_years, wikidata_stats = fetch_wikidata_death_years(wikidata_candidates)
    for title, dy in wikidata_years.items():
        if dy is not None:
            enrichment[title]["death_year"] = dy
            enrichment[title]["death_year_source"] = "wikidata"

    return enrichment, wikidata_stats


# ---------------------------------------------------------------------------
# Section 1: pool_health
# ---------------------------------------------------------------------------

def build_pool_health(inv_by_game, scores, scores_by_title):
    # 40th percentile of fame, per class, across the FULL scored universe
    # (not just pool items) -- used for the dead_weight_count stat.
    class_fame = {}
    for s in scores:
        if s.get("fame") is not None:
            class_fame.setdefault(s["class"], []).append(s["fame"])
    class_p40 = {cls: percentile(sorted(vals), 40) for cls, vals in class_fame.items()}

    result = {}
    for game in ("who", "what", "map"):
        rows = []
        for it in inv_by_game.get(game, []):
            title = it.get("wiki_title")
            s = scores_by_title.get(title) if title else None
            fame = s["fame"] if s else None
            cls = s["class"] if s else None
            rows.append({
                "id": it.get("id"),
                "display_name": it.get("display_name"),
                "wiki_title": title,
                "current_tier": it.get("tier"),
                "fame": fame,
                "class": cls,
                "aired_count": len(it.get("aired_in") or []),
                "proposed_bin": None,
            })

        # Scored items first (fame descending); unscored items trail, order
        # among themselves is irrelevant so a stable sort is fine.
        rows.sort(key=lambda r: (r["fame"] is None, -(r["fame"] if r["fame"] is not None else 0.0)))

        scored_rows = [r for r in rows if r["fame"] is not None]
        assign_proposed_bins(scored_rows)

        dead_weight_count = 0
        for r in scored_rows:
            thresh = class_p40.get(r["class"])
            if thresh is not None and r["fame"] < thresh:
                dead_weight_count += 1

        median_fame_by_tier = {}
        for tier in ("easy", "medium", "hard"):
            vals = [r["fame"] for r in rows if r["current_tier"] == tier and r["fame"] is not None]
            median_fame_by_tier[tier] = statistics.median(vals) if vals else None

        result[game] = {
            "items": rows,
            "summary": {
                "pool_size": len(rows),
                "scored_count": len(scored_rows),
                "unscored_count": len(rows) - len(scored_rows),
                "below_fame_30_count": sum(1 for r in scored_rows if r["fame"] < 30),
                "dead_weight_count": dead_weight_count,
                "median_fame_by_tier": median_fame_by_tier,
            },
        }
    return result


# ---------------------------------------------------------------------------
# Section 2: missing_bankers
# ---------------------------------------------------------------------------

def build_missing_bankers(scores, inv_by_game, enrichment):
    who_titles = pool_title_set(inv_by_game, "who")
    map_titles = pool_title_set(inv_by_game, "map")
    what_titles = pool_title_set(inv_by_game, "what")

    who_list, map_list, what_list = [], [], []

    for s in scores:
        fame = s.get("fame")
        if fame is None:
            continue
        title = s["wiki_title"]
        cls = s["class"]

        if cls == "person":
            e = enrichment.get(title) or {}
            domain = e.get("domain")
            birth_year = e.get("birth_year")
            death_year = e.get("death_year")
            flag = policy_flag_for_person(domain, death_year)

            if fame >= 70 and title not in who_titles:
                who_list.append({
                    "name": s["name"], "wiki_title": title, "class": cls,
                    "fame": fame, "domain": domain, "death_year": death_year,
                    "policy_flag": flag,
                })
            if fame >= 60 and title not in map_titles:
                map_list.append({
                    "name": s["name"], "wiki_title": title, "class": cls,
                    "fame": fame, "domain": domain,
                    "birth_year": birth_year, "death_year": death_year,
                    "policy_flag": flag,
                })
        elif cls in OBJECT_CLASSES:
            if fame >= 60 and title not in what_titles:
                what_list.append({
                    "name": s["name"], "wiki_title": title, "class": cls,
                    "fame": fame,
                    "object_kind": (s.get("sources") or {}).get("object_kind"),
                    "death_year": None,
                    "policy_flag": None,
                })

    who_list.sort(key=lambda r: -r["fame"])
    map_list.sort(key=lambda r: -r["fame"])
    what_list.sort(key=lambda r: -r["fame"])
    return {"who": who_list, "map": map_list, "what": what_list}


# ---------------------------------------------------------------------------
# Section 3: codex_vs_metrics
# ---------------------------------------------------------------------------

def build_codex_vs_metrics(scores, scores_by_title, codex_figures, codex_objects, enrichment):
    weak = []
    for title, row in codex_figures.items():
        s = scores_by_title.get(title)
        if s and s.get("fame") is not None and s["fame"] < 50:
            weak.append({
                "name": s["name"], "wiki_title": title, "class": s["class"],
                "fame": s["fame"], "codex_source": "figures",
                "codex_category": row.get("category"),
                "codex_region": row.get("region"),
                "codex_era": row.get("era"),
            })
    for title, row in codex_objects.items():
        s = scores_by_title.get(title)
        if s and s.get("fame") is not None and s["fame"] < 50:
            weak.append({
                "name": s["name"], "wiki_title": title, "class": s["class"],
                "fame": s["fame"], "codex_source": "objects",
                "codex_category": row.get("category"),
                "codex_region": row.get("region"),
                "codex_era": row.get("era"),
            })
    weak.sort(key=lambda r: r["fame"])  # weakest (most surprising) first

    persons_missing_all = [
        s for s in scores
        if s["class"] == "person" and s.get("fame") is not None and s["wiki_title"] not in codex_figures
    ]
    persons_missing_all.sort(key=lambda r: -r["fame"])
    persons_missing = []
    for s in persons_missing_all[:20]:
        e = enrichment.get(s["wiki_title"]) or {}
        persons_missing.append({
            "name": s["name"], "wiki_title": s["wiki_title"], "class": s["class"],
            "fame": s["fame"], "domain": e.get("domain"),
        })

    objects_missing_all = [
        s for s in scores
        if s["class"] in OBJECT_CLASSES and s.get("fame") is not None and s["wiki_title"] not in codex_objects
    ]
    objects_missing_all.sort(key=lambda r: -r["fame"])
    objects_missing = []
    for s in objects_missing_all[:20]:
        objects_missing.append({
            "name": s["name"], "wiki_title": s["wiki_title"], "class": s["class"],
            "fame": s["fame"], "object_kind": (s.get("sources") or {}).get("object_kind"),
        })

    return {
        "codex_items_scoring_below_50": weak,
        "highest_fame_persons_missing_from_codex": persons_missing,
        "highest_fame_objects_missing_from_codex": objects_missing,
    }


# ---------------------------------------------------------------------------
# Section 4: antiquity_check
# ---------------------------------------------------------------------------

def build_antiquity_check(scores, enrichment, who_titles):
    rows = []
    for s in scores:
        if s["class"] != "person" or s.get("fame") is None or s["fame"] < 50:
            continue
        e = enrichment.get(s["wiki_title"])
        if not e:
            continue  # can't confirm death_year without an enrichment record
        dy = e.get("death_year")
        if dy is None or dy >= 500:
            continue
        rows.append({
            "name": s["name"], "wiki_title": s["wiki_title"], "fame": s["fame"],
            "birth_year": e.get("birth_year"), "death_year": dy,
            "domain": e.get("domain"),
            "in_who_pool": s["wiki_title"] in who_titles,
        })
    rows.sort(key=lambda r: -r["fame"])
    return rows


# ---------------------------------------------------------------------------
# Section 5: summary
# ---------------------------------------------------------------------------

def build_summary(pool_health, missing_bankers, codex_vs_metrics, antiquity_check, inv_by_game):
    current_pool_sizes = {g: len(inv_by_game.get(g, [])) for g in ("who", "what", "map")}
    fame_below_30 = {g: pool_health[g]["summary"]["below_fame_30_count"] for g in ("who", "what", "map")}

    def upgradable(game):
        return {
            "missing_bankers_count": len(missing_bankers[game]),
            "current_pool_size": current_pool_sizes[game],
        }

    return {
        "section_counts": {
            "pool_health": {g: pool_health[g]["summary"]["pool_size"] for g in ("who", "what", "map")},
            "missing_bankers": {g: len(missing_bankers[g]) for g in ("who", "map", "what")},
            "codex_vs_metrics": {k: len(v) for k, v in codex_vs_metrics.items()},
            "antiquity_check": len(antiquity_check),
        },
        "current_pool_sizes": current_pool_sizes,
        "fame_below_30_count": {"total": sum(fame_below_30.values()), **fame_below_30},
        "who_pool_upgradable": upgradable("who"),
        "what_pool_upgradable": upgradable("what"),
        "map_pool_upgradable": upgradable("map"),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 gap_report.py <scores.json> <out.json>", file=sys.stderr)
        sys.exit(1)

    scores_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    scores_data = load_json(scores_path)
    scores = scores_data.get("scores", [])
    scores_by_title = {}
    for s in scores:
        t = s.get("wiki_title")
        if t:
            scores_by_title[t] = s

    inv_items, inv_by_game = load_inventory(SCRIPT_DIR / "current_inventory.json")
    people_by_title = load_people(SCRIPT_DIR / "universe_people.json")
    codex_figures = load_codex_csv(SCRIPT_DIR / "codex" / "01_dead_famous_figures.csv")
    codex_objects = load_codex_csv(SCRIPT_DIR / "codex" / "02_dead_famous_objects.csv")

    enrichment, wikidata_stats = build_person_enrichment(scores, people_by_title, codex_figures)
    print(
        "Wikidata death-year pass: "
        f"{wikidata_stats['titles_needing_lookup']} titles needed a lookup "
        f"({wikidata_stats['pageprops_requests']} pageprops request(s), "
        f"{wikidata_stats['pageprops_cache_hits']} pageprops cache hit(s), "
        f"{wikidata_stats['claims_requests']} claims request(s), "
        f"{wikidata_stats['claims_cache_hits']} claims cache hit(s)) -> "
        f"{wikidata_stats['qids_resolved']} QIDs resolved, "
        f"{wikidata_stats['death_years_found']} death years found",
        file=sys.stderr,
    )

    pool_health = build_pool_health(inv_by_game, scores, scores_by_title)
    missing_bankers = build_missing_bankers(scores, inv_by_game, enrichment)
    codex_vs_metrics = build_codex_vs_metrics(
        scores, scores_by_title, codex_figures, codex_objects, enrichment
    )
    who_titles = pool_title_set(inv_by_game, "who")
    antiquity_check = build_antiquity_check(scores, enrichment, who_titles)
    summary = build_summary(pool_health, missing_bankers, codex_vs_metrics, antiquity_check, inv_by_game)

    output = {
        "generatedOn": GENERATED_ON,
        "source_scores_file": str(scores_path),
        "pool_health": pool_health,
        "missing_bankers": missing_bankers,
        "codex_vs_metrics": codex_vs_metrics,
        "antiquity_check": antiquity_check,
        "summary": summary,
        "meta": {
            "wikidata_death_year_pass": wikidata_stats,
        },
    }

    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote gap report to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
