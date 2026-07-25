#!/usr/bin/env python3
"""
build_scores.py -- refined, class-aware fame scorer for the Dead Famous
content pipeline (v2, replaces score_fame.py's flat 60/20/20 blend).

Usage:
    python3 build_scores.py <out.json> <metrics1.jsonl> [<metrics2.jsonl> ...]

To regenerate the live index exactly, run from this directory:
    python3 build_scores.py fame_scores.json \
        metrics_wave1.jsonl metrics_wave2.jsonl metrics_wave3.jsonl \
        metrics_fixups.jsonl
metrics_fixups.jsonl is small but NOT optional: it carries the two titles
(Emir Abdelkader, Stadium at Olympia) that only became reachable once their
wrong-subject mappings were corrected, and the wave files are gitignored
harvest output. Omit it and those two score as missing.

Input: one or more metrics .jsonl files, each a fetch_metrics.py output --
one JSON object per line with at least "name", "wiki_title",
"pageviews_5y", "languages", "inlinks", "error" (and optionally
"resolved_title" when the title redirected).

What it does:
    1. Loads + dedupes all rows across the given files by wiki_title (last
       file wins). Rows whose *final* value has a non-null "error" are
       pulled into a separate "errors" list and excluded from scoring.
    2. Classifies every remaining title into one of: person, structure,
       artwork, artefact, other -- by cross-referencing universe_people.json,
       universe_objects.json, current_inventory.json, and the two codex
       CSVs (all read from this same directory).
    3. Re-derives two richer per-title stats straight from fetch_metrics.py's
       raw cached API responses (cache/pageviews/, cache/languages/):
         - pv_stat: a trimmed, recency-excluding, spike-resistant read on
           monthly pageviews (falls back to pageviews_5y/60 if the cache
           entry is missing or unreadable). When the article was RENAMED
           inside the window the pageviews API splits its series across the
           old and new titles; RENAMED_FROM below lists every such pool
           article and the series are summed month-by-month before any
           statistic is taken. `pv_merged_from` on each output row records
           which former titles were folded in.
         - family_consensus: fraction (0-1) of 8 language families that
           have at least one Wikipedia edition of the article (falls back
           to a languages-count heuristic under the same condition).
    4. Percentile-ranks pv_stat / languages / inlinks *within each class*
       (percentiles are not comparable across classes -- a "famous" statue
       and a "famous" emperor are famous on different scales) and blends:
         fame = 0.50*pct(pv_stat) + 0.15*pct(languages) + 0.10*pct(inlinks)
                + 0.25*(family_consensus*100)
    5. Writes out.json: generatedOn, counts_per_class, the full scored
       list (sorted by class, then fame descending), and the errors list.

Python 3.9 stdlib only. Read-only with respect to fetch_metrics.py, its
cache, and everything under data/ or js/ -- this script only *reads*
fetch_metrics.py (to reuse its PAGEVIEWS_END constant so the "final 3
months" window can never silently drift out of sync) and the cache files
it produced.
"""

import csv
import hashlib
import json
import math
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_DIR = SCRIPT_DIR / "cache"

# fetch_metrics.py lives in this same directory, so `python3 build_scores.py`
# puts SCRIPT_DIR on sys.path[0] automatically and this import is safe --
# importing only runs module-level constant/class definitions, no I/O, no
# network calls (those only happen inside fetch_metrics.main()).
from fetch_metrics import PAGEVIEWS_END  # noqa: E402


GENERATED_ON = "2026-07-22"


# ---------------------------------------------------------------------------
# Cache-key derivation -- duplicated (not imported) from fetch_metrics.py's
# _title_to_underscored / _cache_path so this script never calls into any
# function there that could touch the network or write to the cache.
# ---------------------------------------------------------------------------

def _title_to_underscored(title):
    return title.strip().replace(" ", "_")


def _cache_path(metric, key):
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return CACHE_DIR / metric / f"{h}.json"


def _load_cache_json(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _final_n_months(window_end, n=3):
    """Set of 'YYYYMM' strings for the last n calendar months of the
    fetch window, derived from fetch_metrics.py's PAGEVIEWS_END
    (format YYYYMMDDHH) so this can't drift out of sync by hand."""
    year = int(window_end[0:4])
    month = int(window_end[4:6])
    months = set()
    y, m = year, month
    for _ in range(n):
        months.add(f"{y:04d}{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return months


WINDOW_FINAL_3_MONTHS = _final_n_months(PAGEVIEWS_END, 3)


# ---------------------------------------------------------------------------
# Renamed articles -- former enwiki titles whose pageviews belong to the same
# subject (25 Jul 2026)
#
# The Wikimedia pageviews API is keyed by the *title as requested*, not by the
# page. When an article is moved inside the 5-year window the series splits in
# two: the new title reads near-zero before the move, the old title near-zero
# after it, and neither is the article's real traffic. pv_stat is a trimmed
# monthly MEDIAN, so the half of the window that sits in the dead zone drags
# the median straight into it and fame collapses. Nicholas II read fame 57.9
# on 2.2 million views; Kim Il-sung 50.3 on 2.8 million.
#
# The fix is to reassemble the series: sum the two (or more) titles month by
# month before computing any statistic. Every pair below was confirmed against
# the enwiki move log (action=query&list=logevents&letype=move) -- the move is
# a real page move to this exact target, dated inside 2020-07..2025-06 -- and
# the former title's monthly series was fetched into the same cache directory
# fetch_metrics.py writes, so this stays a pure cache read.
#
# Summing includes the residual traffic the old title still draws as a
# redirect. That is deliberate: a reader who arrives via the old name is a
# reader of this article, and the point of the statistic is audience size.
#
# A former title with no cache entry is skipped, not fatal -- the merge just
# degrades to whatever it can reach, exactly like the rest of this file.
# Regenerate the cache entries with fetch_metrics.py if this list grows.
# ---------------------------------------------------------------------------
RENAMED_FROM = {
    "Al-Khwarizmi": ["Muhammad ibn Musa al-Khwarizmi"],       # 2023-08-07
    "Amber Fort": ["Amer Fort"],                              # 2021-09-10
    "Baybars": ["Baibars"],                                   # 2022-09-27
    "Blue Mosque, Istanbul": ["Sultan Ahmed Mosque"],         # 2022-01-06
    "Boudha Stupa": ["Boudhanath"],                           # 2024-10-04
    "Cnut": ["Cnut the Great"],                               # 2022-01-09
    "Frederick Barbarossa": ["Frederick I, Holy Roman Emperor"],   # 2022-09-04
    "Gustavus Adolphus": ["Gustavus Adolphus of Sweden"],     # 2021-06-17
    "Kailasa Temple, Ellora": ["Kailasa temple, Ellora",
                               "Kailasatempel"],              # 2020-08-29 / 2021-09-18
    "Kim Il Sung": ["Kim Il-sung"],                           # 2023-04-16
    "Kim Jong Il": ["Kim Jong-il"],                           # 2023-04-16
    "Mehmed II": ["Mehmed the Conqueror"],                    # moved back and forth 2022-2025
    "Mithridates VI Eupator": ["Mithridates VI"],             # 2021-01-19
    "Mortuary temple of Hatshepsut": ["Mortuary Temple of Hatshepsut"],  # 2023-06-11
    "Nazca lines": ["Nazca Lines"],                           # 2024-04-15
    "Nebra sky disc": ["Nebra sky disk"],                     # 2021-10-26
    "Nicholas II": ["Nicholas II of Russia"],                 # 2024-02-19
    "Otto the Great": ["Otto I, Holy Roman Emperor"],         # 2022-04-23
    "The Buddha": ["Gautama Buddha"],                         # 2022-10-20
    "Theodora (wife of Justinian I)": ["Theodora (6th century)"],   # 2021-01-24
    "Wangarĩ Maathai": ["Wangari Maathai"],                   # 2024-04-08
    "Wilhelm II": ["Wilhelm II, German Emperor"],             # 2023-11-04
    "William Adams (samurai)": ["William Adams (pilot)"],     # 2024-06-12
}


# ---------------------------------------------------------------------------
# Language families
# ---------------------------------------------------------------------------

LANGUAGE_FAMILIES = {
    "Romance": {"fr", "es", "it", "pt", "ro", "ca", "gl"},
    "Germanic": {"de", "nl", "sv", "da", "no", "nb", "nn", "is", "af"},
    "Slavic": {"ru", "pl", "uk", "cs", "sk", "bg", "sr", "hr", "sl", "be", "mk"},
    "MiddleEast": {"ar", "fa", "he", "tr", "az", "ku", "ckb"},
    "SouthAsian": {"hi", "bn", "ur", "ta", "te", "ml", "mr", "pa", "gu", "kn", "si", "ne"},
    "EastAsian": {"zh", "ja", "ko"},
    "SoutheastAsian": {"vi", "th", "id", "ms", "tl", "jv", "my", "km", "lo"},
}
# English ("en") is its own family and is counted automatically below --
# 1 (English) + up to 7 others = 8 families total, matching the spec.


# ---------------------------------------------------------------------------
# Object-kind -> class keyword mapping
# ---------------------------------------------------------------------------

# Checked in this order: ARTWORK first, then STRUCTURE, then default to
# ARTEFACT (the catch-all "anything else object-like"). This order was
# picked by hand-checking the actual compound categories present in
# codex/02_dead_famous_objects.csv (e.g. "architecture and artwork" ->
# structure via "architecture"; "sculpture and monument" -> artwork via
# "sculpture") and it resolves every one of them sensibly.
STRUCTURE_KEYWORDS = [
    "building", "monument", "site", "architecture", "bridge", "tower",
    "infrastructure", "fortification", "religious structure", "archaeological site",
]
ARTWORK_KEYWORDS = ["painting", "sculpture", "print", "textile", "land art", "cave art"]
ARTEFACT_KEYWORDS = [
    "artefact", "manuscript", "ship", "aircraft", "vehicle", "locomotive",
    "spacecraft", "rocket", "weapon", "computer", "sign",
]


def classify_object_kind(kind_str):
    s = (kind_str or "").lower()
    for kw in ARTWORK_KEYWORDS:
        if kw in s:
            return "artwork"
    for kw in STRUCTURE_KEYWORDS:
        if kw in s:
            return "structure"
    return "artefact"  # explicit artefact keywords, or "anything else object-like"


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------

def percentile(sorted_vals, pct):
    """Linear-interpolation percentile (0-100) of an already-sorted list."""
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    if n == 1:
        return float(sorted_vals[0])
    k = (pct / 100.0) * (n - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def average_rank_percentiles(values):
    """0-100 percentile rank per value, average-rank method for ties
    (identical to score_fame.py's version, kept for continuity)."""
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [100.0]
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return [(r - 1) / (n - 1) * 100.0 for r in ranks]


def _num_or_zero(value):
    return value if isinstance(value, (int, float)) else 0


# ---------------------------------------------------------------------------
# Per-title refined metrics, read straight from fetch_metrics.py's cache
# ---------------------------------------------------------------------------

def _monthly_series(title):
    """[(timestamp, views)] straight out of the cache, or None."""
    cached = _load_cache_json(_cache_path("pageviews", _title_to_underscored(title)))
    if not isinstance(cached, dict):
        return None, None
    body = cached.get("body")
    if cached.get("ok") and isinstance(body, dict) and isinstance(body.get("items"), list):
        series = []
        for it in body["items"]:
            ts, views = it.get("timestamp"), it.get("views")
            if ts is None or views is None:
                continue
            series.append((ts, views))
        return series, cached
    return None, cached


def merged_monthly_series(title):
    """Monthly series for `title`, summed month-by-month with the series of
    every title it was renamed FROM (see RENAMED_FROM). Returns
    (series, merged_titles) where series is [(timestamp, views)] sorted by
    timestamp, or (None, []) when the canonical title has no usable cache."""
    base, _ = _monthly_series(title)
    if base is None:
        return None, []
    totals = {}
    for ts, v in base:
        totals[ts] = totals.get(ts, 0) + v
    merged = []
    for former in RENAMED_FROM.get(title, []):
        extra, _ = _monthly_series(former)
        if not extra:
            continue
        merged.append(former)
        for ts, v in extra:
            totals[ts] = totals.get(ts, 0) + v
    return sorted(totals.items()), merged


def compute_pv_stat(record):
    """Returns (pv_stat, pv_fallback, spike_driven, merged_titles)."""
    wiki_title = record.get("wiki_title")
    resolved = record.get("resolved_title") or wiki_title
    underscored = _title_to_underscored(resolved)
    cached = _load_cache_json(_cache_path("pageviews", underscored))

    pageviews_5y = record.get("pageviews_5y")
    fallback_stat = (pageviews_5y / 60.0) if isinstance(pageviews_5y, (int, float)) else 0.0

    if not isinstance(cached, dict):
        return fallback_stat, True, False, []

    body = cached.get("body")
    if cached.get("ok") and isinstance(body, dict) and isinstance(body.get("items"), list):
        series, merged_titles = merged_monthly_series(resolved)
        series = series or []

        kept = [v for ts, v in series if ts[:6] not in WINDOW_FINAL_3_MONTHS]
        kept_sorted = sorted(kept)

        if kept_sorted:
            highest_month = kept_sorted[-1]
            median_month = percentile(kept_sorted, 50)
        else:
            highest_month = 0
            median_month = 0
        spike = (highest_month / max(1, median_month)) > 8

        # Drop the 2 highest remaining months. If there's too little data to
        # safely drop 2 (<=2 points), keep everything rather than zeroing
        # out an otherwise legitimate low-traffic title -- the spec doesn't
        # cover this edge case, and it only bites very sparse cache entries.
        if len(kept_sorted) > 2:
            trimmed = kept_sorted[:-2]
        else:
            trimmed = kept_sorted

        if trimmed:
            pv_stat = 0.7 * percentile(trimmed, 50) + 0.3 * percentile(trimmed, 20)
        else:
            pv_stat = 0.0
        return pv_stat, False, spike, merged_titles

    if cached.get("ok") is False:
        # A definitive, cached negative result (typically 404 not_found) --
        # this is real evidence of zero pageviews, not a data-quality gap,
        # so it does NOT count as a fallback.
        return 0.0, False, False, []

    # Unexpected/malformed shape.
    return fallback_stat, True, False, []


def compute_family_consensus(record):
    """Returns (family_consensus, fam_fallback)."""
    wiki_title = record.get("wiki_title")
    cached = _load_cache_json(_cache_path("languages", wiki_title))

    languages_count = record.get("languages")
    fallback_val = min(1.0, languages_count / 40.0) if isinstance(languages_count, (int, float)) else 0.0

    if not isinstance(cached, dict) or not cached.get("ok"):
        return fallback_val, True

    body = cached.get("body") or {}
    pages = ((body.get("query") or {}).get("pages")) or {}
    page = next(iter(pages.values()), None)
    if page is None or "missing" in page:
        return fallback_val, True

    # A page with zero interwiki links legitimately omits the "langlinks"
    # key entirely (confirmed against the cache) rather than including an
    # empty list -- treat that the same as an empty list, not a cache miss.
    codes = {ll.get("lang") for ll in (page.get("langlinks") or [])}

    families_present = 1  # English, automatic (this is the enwiki article)
    for fam_codes in LANGUAGE_FAMILIES.values():
        if codes & fam_codes:
            families_present += 1
    return families_present / 8.0, False


# ---------------------------------------------------------------------------
# Reference-data loading (for classification + "sources" provenance)
# ---------------------------------------------------------------------------

def load_universe_people(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    by_title = {}
    for p in data.get("people", []):
        t = p.get("wiki_title")
        if t and t not in by_title:
            by_title[t] = p
    return by_title


def load_universe_objects(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    by_title = {}
    for o in data.get("objects", []):
        t = o.get("wiki_title")
        if t and t not in by_title:
            by_title[t] = o
    return by_title


def load_inventory_games(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    by_title = {}
    for it in data.get("items", []):
        t = it.get("wiki_title")
        g = it.get("game")
        if not t or not g:
            continue
        by_title.setdefault(t, set()).add(g)
    return by_title


def load_codex_csv(path):
    by_title = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            t = row.get("exact_english_wikipedia_article_title")
            if t and t not in by_title:
                by_title[t] = row
    return by_title


# ---------------------------------------------------------------------------
# Metrics loading (dedupe by wiki_title, last file wins)
# ---------------------------------------------------------------------------

def load_metrics(paths):
    by_title = {}
    order = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                title = rec.get("wiki_title")
                if not title:
                    continue
                if title not in by_title:
                    order.append(title)
                by_title[title] = rec  # last wins

    good, errors = [], []
    for title in order:
        rec = by_title[title]
        if rec.get("error"):
            errors.append(rec)
        else:
            good.append(rec)
    return good, errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 3:
        print(
            "Usage: python3 build_scores.py <out.json> <metrics1.jsonl> [<metrics2.jsonl> ...]",
            file=sys.stderr,
        )
        sys.exit(1)

    out_path = Path(sys.argv[1])
    metrics_paths = [Path(p) for p in sys.argv[2:]]

    good_records, error_records = load_metrics(metrics_paths)

    people_by_title = load_universe_people(SCRIPT_DIR / "universe_people.json")
    objects_by_title = load_universe_objects(SCRIPT_DIR / "universe_objects.json")
    inventory_games_by_title = load_inventory_games(SCRIPT_DIR / "current_inventory.json")
    codex_figures_by_title = load_codex_csv(SCRIPT_DIR / "codex" / "01_dead_famous_figures.csv")
    codex_objects_by_title = load_codex_csv(SCRIPT_DIR / "codex" / "02_dead_famous_objects.csv")

    prepared = []
    for rec in good_records:
        title = rec["wiki_title"]

        in_people = title in people_by_title
        in_codex_fig = title in codex_figures_by_title
        in_objects = title in objects_by_title
        in_codex_obj = title in codex_objects_by_title
        inv_games = sorted(inventory_games_by_title.get(title, set()))

        if in_people or in_codex_fig or "who" in inv_games or "map" in inv_games:
            cls = "person"
            object_kind = None
        elif in_objects or in_codex_obj or "what" in inv_games:
            if in_objects:
                kind_str = objects_by_title[title].get("kind")
            elif in_codex_obj:
                kind_str = codex_objects_by_title[title].get("category")
            else:
                kind_str = None  # only signal was inventory game "what"
            cls = classify_object_kind(kind_str)
            object_kind = kind_str
        else:
            cls = "other"
            object_kind = None

        pv_stat, pv_fallback, spike_driven, merged_titles = compute_pv_stat(rec)
        family_consensus, fam_fallback = compute_family_consensus(rec)

        universe_rank = None
        if in_people:
            pr = people_by_title[title].get("proxy_rank")
            universe_rank = pr if isinstance(pr, int) else None

        prepared.append({
            "wiki_title": title,
            "name": rec.get("name") or title,
            "class": cls,
            "pv_stat": pv_stat,
            "pv_fallback": pv_fallback,
            "spike_driven": spike_driven,
            "pv_merged_from": merged_titles,
            "family_consensus": family_consensus,
            "fam_fallback": fam_fallback,
            "pageviews_5y": rec.get("pageviews_5y"),
            "languages": rec.get("languages"),
            "inlinks": rec.get("inlinks"),
            "sources": {
                "in_universe_people": in_people,
                "universe_rank": universe_rank,
                "in_universe_objects": in_objects,
                "object_kind": object_kind,
                "in_codex_figures": in_codex_fig,
                "in_codex_objects": in_codex_obj,
                "inventory_games": inv_games,
            },
        })

    by_class = {}
    for p in prepared:
        by_class.setdefault(p["class"], []).append(p)

    scores = []
    counts_per_class = {}
    for cls, items in by_class.items():
        counts_per_class[cls] = len(items)

        pv_vals = [it["pv_stat"] for it in items]
        lang_vals = [_num_or_zero(it["languages"]) for it in items]
        inlink_vals = [_num_or_zero(it["inlinks"]) for it in items]

        pv_pcts = average_rank_percentiles(pv_vals)
        lang_pcts = average_rank_percentiles(lang_vals)
        inlink_pcts = average_rank_percentiles(inlink_vals)

        for i, it in enumerate(items):
            pv_pct, lang_pct, inlink_pct = pv_pcts[i], lang_pcts[i], inlink_pcts[i]
            fame = (
                0.50 * pv_pct
                + 0.15 * lang_pct
                + 0.10 * inlink_pct
                + 0.25 * (it["family_consensus"] * 100)
            )
            scores.append({
                "wiki_title": it["wiki_title"],
                "name": it["name"],
                "class": cls,
                "fame": round(fame, 2),
                "pv_pct": round(pv_pct, 2),
                "lang_pct": round(lang_pct, 2),
                "inlink_pct": round(inlink_pct, 2),
                "family_consensus": round(it["family_consensus"], 4),
                "spike_driven": it["spike_driven"],
                "pv_stat": round(it["pv_stat"], 2),
                "pv_merged_from": it["pv_merged_from"],
                "pageviews_5y": it["pageviews_5y"],
                "languages": it["languages"],
                "inlinks": it["inlinks"],
                "pv_fallback": it["pv_fallback"],
                "fam_fallback": it["fam_fallback"],
                "sources": it["sources"],
            })

    scores.sort(key=lambda x: (x["class"], -x["fame"]))

    output = {
        "generatedOn": GENERATED_ON,
        "counts_per_class": dict(sorted(counts_per_class.items())),
        "scores": scores,
        "errors": error_records,
    }

    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"Wrote {len(scores)} scored records ({len(error_records)} errors) to {out_path}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
