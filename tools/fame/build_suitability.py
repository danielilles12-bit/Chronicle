#!/usr/bin/env python3
"""
build_suitability.py -- per-game content-suitability scorer for Dead Famous.

WHY THIS EXISTS
----------------
build_scores.py (tools/fame/build_scores.py) produces ONE fame score per
title, blended 50% pageviews + 15% languages + 10% inlinks + 25% cross-
language consensus -- all Wikipedia POPULARITY signals. That score is used
today to pick content for THREE games with different needs, and popularity
alone can't tell you whether a specific item plays well in the game it's
been placed in. A 22 Jul 2026 review found this directly: famous subjects
with unusable images played as unfairly hard, and obscure subjects with
giveaway clues played as hollow -- "a famous answer with a bad image is not
easy."

This script adds three READ-ONLY, game-specific SUITABILITY signals,
computed straight from the shipped content pools, and writes them to
suitability.json alongside a distribution summary and a "worst offenders"
list per signal. It does not touch fame_scores.json and does not decide how
the two should be combined -- see SUITABILITY.md for that recommendation.

  Signal 1 -- LIFELINE JOURNEY (data/figures.json)
    Lifeline shows a birth point and a death point on a map. A figure who
    was born and died within the same city is a dull round no matter how
    famous they are; a dramatic geographic arc is inherently interesting.
    Scored as the great-circle (haversine) distance between birth and
    death coordinates.

  Signal 2 -- IMAGE LEGIBILITY (data/reveal-who.json, data/reveal-what.json)
    Face Value / Relic reveal a photo through a torn 3x3 grid; the free
    opening cell must show real evidence, not empty background. Scored
    from the item's own fx/fy/frac fields (how big the subject is in
    frame) combined with the app's own grid geometry (how far the chosen
    opening cell sits from the cell that actually holds the subject) --
    see the "why no pixel decoding" note below.

  Signal 3 -- FACE VALUE PORTRAIT VIABILITY (data/reveal-who.json)
    A painted or sculpted likeness of someone nobody has seen photographed
    is a much harder round than fame alone predicts. Flags (not scores)
    each portrait as photograph / painting / sculpture / graphic /
    non_photographic_unspecified / unknown, from source text plus an
    era check (was photography even possible when this person died?).

WHY NO PIXEL DECODING (stdlib-only constraint)
------------------------------------------------
This script is Python 3.9 STDLIB ONLY -- no Pillow, no numpy, no new
dependency of any kind, even though tools/audit_start_scraps.py (which
already replicates the app's tear geometry) happens to import Pillow. All
819 files under assets/img/ are JPEG-encoded pixel data (a handful are
PNG bytes saved with a .jpg extension -- see the "png_mislabelled_jpg"
data-quality note in SUITABILITY.md); the Python standard library has no
JPEG (or PNG) pixel decoder, only import + no way to inspect the DCT-coded
pixel grid without writing one from scratch, which is not a "cheap proxy."
So per the brief, this script falls back to metadata-only proxies for
image content:
  - the real fx/fy/frac authored focal-region fields (not a fallback --
    this is the primary Signal 2 input and needs no image decoding at all)
  - image WIDTH/HEIGHT/FORMAT, read via a ~30-line stdlib `struct` parser
    that walks JPEG SOF markers / the PNG IHDR chunk (no pixel decode --
    this only reads the header, exactly like `file` or `identify -format`
    would, and is what caught the mislabelled PNGs above)
  - whole-image bytes-per-megapixel as a weak, corpus-relative "how much
    visual detail does this WHOLE image have" hint (JPEG compresses smooth
    regions like sky/plain backdrops far more than detailed/textured
    ones) -- reported as a diagnostic only, explicitly NOT used in the
    Signal 2 risk score, because it is confounded by old b/w photography
    (which also compresses small) and by unrelated encoder/quality
    settings. See SUITABILITY.md.

USAGE
-----
    python3 tools/fame/build_suitability.py

Reads data/figures.json, data/reveal-who.json, data/reveal-what.json,
data/editions.json (all read-only). Writes tools/fame/suitability.json.
No network access. Runs in well under a second.
"""
import json
import math
import re
import struct
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT_PATH = Path(__file__).resolve().parent / "suitability.json"

GENERATED_ON = "2026-07-25"

# Lifeline rounds are read starting at edition 28 through the newest edition
# actually present in data/editions.json (the brief said "28-64"; if more
# editions have landed since, we still cover them rather than silently
# ignoring newly-scheduled content).
EDITION_RANGE_LO = 28


# ---------------------------------------------------------------------------
# Small JSON helpers
# ---------------------------------------------------------------------------

def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Signal 1 -- Lifeline journey (haversine birth->death distance)
# ---------------------------------------------------------------------------

EARTH_RADIUS_KM = 6371.0088
HALF_CIRCUMFERENCE_KM = math.pi * EARTH_RADIUS_KM  # ~20015km: max possible

# Evidence for these two cutoffs is in SUITABILITY.md; summarised here:
#  - DULL_KM=50: the brief asked directly "how many figures are under 50km
#    apart" -- 74/541 (13.7%) are, and it's a natural "same metro area"
#    reading of "born and died in the same place."
#  - a distance can never legitimately exceed HALF_CIRCUMFERENCE_KM; this
#    dataset has no such case today but the check stays in as a guard.
DULL_KM = 50.0


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def percentile(sorted_vals, pct):
    n = len(sorted_vals)
    if n == 0:
        return None
    if n == 1:
        return float(sorted_vals[0])
    k = (pct / 100.0) * (n - 1)
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def build_lifeline_journey(figures, editions_doc):
    items = {}
    kms = []
    errors = []
    for f in figures:
        fid = f["id"]
        b, d = f.get("birth") or {}, f.get("death") or {}
        blat, blon, dlat, dlon = b.get("lat"), b.get("lon"), d.get("lat"), d.get("lon")

        flags = []
        if None in (blat, blon, dlat, dlon):
            errors.append({"id": fid, "error": "missing birth/death coordinates"})
            continue
        for lat, lon, which in ((blat, blon, "birth"), (dlat, dlon, "death")):
            if lat == 0 and lon == 0:
                flags.append(f"{which}_at_0_0")
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                flags.append(f"{which}_coord_out_of_range")

        km = haversine_km(blat, blon, dlat, dlon)
        if km > HALF_CIRCUMFERENCE_KM + 1:  # +1: float slack
            flags.append("impossible_distance")

        # Soft, non-blocking sanity check: a large journey recorded for a
        # figure who died before ~500 BC is unusual (though not impossible
        # -- imperial campaigns, exile and religious pilgrimage all predate
        # 500 BC). None of the 541 figures trip this today; it's a guard
        # for future data entry, not a claim about existing records.
        by = b.get("year")
        if isinstance(by, (int, float)) and by < -500 and km > 3000:
            flags.append("large_journey_for_ancient_era_check_by_hand")

        kms.append(km)
        items[fid] = {
            "name": f.get("name"),
            "inputs": {
                "birth": {"year": b.get("year"), "place": b.get("place"), "lat": blat, "lon": blon},
                "death": {"year": d.get("year"), "place": d.get("place"), "lat": dlat, "lon": dlon},
            },
            "journey_km": round(km, 1),
            "dull": km < DULL_KM,
            "flags": flags,
        }

    kms_sorted = sorted(kms)
    n = len(kms_sorted)
    for fid, rec in items.items():
        rec["journey_percentile"] = round(
            100.0 * sum(1 for v in kms_sorted if v <= rec["journey_km"]) / n, 1
        ) if n else None

    distribution = {
        "n": n,
        "under_50km": sum(1 for v in kms_sorted if v < 50),
        "under_100km": sum(1 for v in kms_sorted if v < 100),
        "under_200km": sum(1 for v in kms_sorted if v < 200),
        "percentiles_km": {
            str(p): round(percentile(kms_sorted, p), 1) for p in (5, 10, 25, 50, 75, 90, 95, 100)
        } if n else {},
        "max_possible_km": round(HALF_CIRCUMFERENCE_KM, 1),
    }

    # Scheduled Lifeline rounds, editions EDITION_RANGE_LO..newest.
    eds = editions_doc.get("editions") or {}
    ed_indices = sorted(int(k) for k in eds.keys())
    hi = max(ed_indices) if ed_indices else EDITION_RANGE_LO
    scheduled = []
    for i in range(EDITION_RANGE_LO, hi + 1):
        ed = eds.get(str(i))
        if not ed:
            continue
        for fid in ed.get("map") or []:
            rec = items.get(fid)
            scheduled.append({
                "id": fid,
                "edition": i,
                "date": ed.get("date"),
                "journey_km": rec["journey_km"] if rec else None,
                "dull": rec["dull"] if rec else None,
            })

    scheduled_valid = [s for s in scheduled if s["journey_km"] is not None]
    scheduled_dull = [s for s in scheduled_valid if s["dull"]]
    worst = sorted(scheduled_valid, key=lambda s: s["journey_km"])[:20]

    return {
        "signal": "lifeline_journey",
        "source": "data/figures.json",
        "method": "haversine great-circle distance (km) between birth and death coordinates; "
                  "one sentence: a figure who died where they were born is a dull round, however "
                  "famous, so shorter journeys score as duller.",
        "thresholds": {"dull_km": DULL_KM},
        "items": items,
        "distribution": distribution,
        "scheduled_editions": {"lo": EDITION_RANGE_LO, "hi": hi},
        "scheduled_rounds_total": len(scheduled),
        "scheduled_rounds_dull": len(scheduled_dull),
        "worst_offenders_scheduled": worst,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Signal 2 -- Image legibility
#
# money_scrap/start_scrap below are COPIED (not imported -- imports would
# force a Pillow dependency at module load time; see the module docstring)
# verbatim in logic from tools/audit_start_scraps.py, which is the app's
# own reference implementation of js/revealgame.js's tear geometry. Do not
# edit tools/audit_start_scraps.py; if its geometry ever changes, re-copy
# these three functions from it.
# ---------------------------------------------------------------------------

def money_scrap(fx, fy):
    c = min(2, int(fx * 3))
    r = min(2, int(fy * 3))
    return r * 3 + c


def start_scrap(fx, fy, override=None):
    m = money_scrap(fx, fy)
    if isinstance(override, int) and 0 <= override <= 8 and override != m:
        return override
    mr, mc = divmod(m, 3)
    best, bd = 0, -1
    for i in [0, 2, 6, 8, 1, 3, 5, 7, 4]:  # corners first, deterministic
        d = abs(i // 3 - mr) + abs(i % 3 - mc)
        if d > bd:
            bd, best = d, i
    return best


def grid_distance(cell_a, cell_b):
    ar, ac = divmod(cell_a, 3)
    br, bc = divmod(cell_b, 3)
    return abs(ar - br) + abs(ac - bc)


# ---- stdlib-only image header reader (dimensions + byte size; NO pixel decode) ----

_SOF_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def read_image_header(path):
    """Returns (width, height, byte_size, format) using only stdlib `struct`
    to walk JPEG SOF markers or the PNG IHDR chunk -- header parsing only,
    no pixel/DCT decoding. Returns None if the file isn't a JPEG or PNG."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    size = len(data)
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        if len(data) >= 24 and data[12:16] == b"IHDR":
            w, h = struct.unpack(">II", data[16:24])
            return w, h, size, "png"
        return None
    if data[:2] == b"\xff\xd8":
        i, n = 2, len(data)
        while i < n - 1:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            if marker == 0xD9:
                break
            if i + 4 > n:
                break
            seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker in _SOF_MARKERS:
                h = struct.unpack(">H", data[i + 5:i + 7])[0]
                w = struct.unpack(">H", data[i + 7:i + 9])[0]
                return w, h, size, "jpg"
            i += 2 + seg_len
        return None
    return None


# Evidence for RISK_FLAG_CUTOFF: see SUITABILITY.md -- the risk-score
# histogram over all 790 who+what items has a near-empty bucket at
# 0.70-0.75 (1 item) separating a long shoulder (up to ~0.65) from a
# distinct worst tier (0.75-0.85, 20 items). 0.75 sits in that gap.
RISK_FLAG_CUTOFF = 0.75


def build_image_legibility(who_items, what_items, editions_doc):
    items = {}
    risks = []
    png_mislabelled = []

    def process(pool_items, pool_name):
        for it in pool_items:
            iid = it["id"]
            fx, fy, frac = it["fx"], it["fy"], it["frac"]
            money = money_scrap(fx, fy)
            override = it.get("start")
            start = start_scrap(fx, fy, override)
            is_override = isinstance(override, int) and 0 <= override <= 8 and override != money
            dist = grid_distance(start, money)
            # Risk: small subject-to-frame ratio (frac) combined with an
            # opening cell placed far (in grid steps, 2-4) from the cell
            # that actually holds the subject. One sentence: risk is high
            # when the subject is small in the photo AND the free peek is
            # about as far from it as this 3x3 grid can put it.
            risk = (1.0 - frac) * (dist / 4.0)
            risks.append(risk)

            img_path = ROOT / it["img"]
            header = read_image_header(img_path)
            diagnostics = {"img": it["img"]}
            if header:
                w, h, nbytes, fmt = header
                diagnostics.update({
                    "width": w, "height": h, "format": fmt,
                    "bytes_per_megapixel": round(nbytes / max(1, w * h) * 1_000_000, 0),
                })
                if fmt == "png":
                    png_mislabelled.append(iid)
            else:
                diagnostics["error"] = "could not read image header"

            items[iid] = {
                "name": it.get("name"),
                "pool": pool_name,
                "kind": it.get("kind"),
                "difficulty": it.get("difficulty"),
                "inputs": {"fx": fx, "fy": fy, "frac": frac},
                "money_cell": money,
                "start_cell": start,
                "start_is_curated_override": is_override,
                "grid_distance_start_to_money": dist,
                "risk_score": round(risk, 4),
                "flag_worst_offender": risk >= RISK_FLAG_CUTOFF,
                "image_diagnostics_metadata_only": diagnostics,
            }

    process(who_items, "who")
    process(what_items, "what")

    risks_sorted = sorted(risks)
    n = len(risks_sorted)
    distribution = {
        "n": n,
        "percentiles_risk": {
            str(p): round(percentile(risks_sorted, p), 4) for p in (10, 25, 50, 75, 90, 95, 99, 100)
        } if n else {},
        "flagged_worst_offenders_total": sum(1 for r in risks if r >= RISK_FLAG_CUTOFF),
    }

    eds = editions_doc.get("editions") or {}
    ed_indices = sorted(int(k) for k in eds.keys())
    hi = max(ed_indices) if ed_indices else EDITION_RANGE_LO
    scheduled = []
    for i in range(EDITION_RANGE_LO, hi + 1):
        ed = eds.get(str(i))
        if not ed:
            continue
        for key in ("who", "what"):
            for iid in ed.get(key) or []:
                rec = items.get(iid)
                scheduled.append({
                    "id": iid, "pool": key, "edition": i, "date": ed.get("date"),
                    "risk_score": rec["risk_score"] if rec else None,
                    "frac": rec["inputs"]["frac"] if rec else None,
                    "grid_distance": rec["grid_distance_start_to_money"] if rec else None,
                })

    scheduled_valid = [s for s in scheduled if s["risk_score"] is not None]
    worst = sorted(scheduled_valid, key=lambda s: -s["risk_score"])[:25]

    return {
        "signal": "image_legibility",
        "source": "data/reveal-who.json, data/reveal-what.json",
        "method": "risk = (1 - frac) * (grid_distance(start_cell, money_cell) / 4); one sentence: "
                  "risk is high when the subject is a small part of the photo and the free opening "
                  "view is placed as far from it as the 3x3 grid allows.",
        "thresholds": {"risk_flag_cutoff": RISK_FLAG_CUTOFF},
        "note_on_pixel_decoding": "no per-cell pixel stats (luminance/edge density) are computed -- "
                                   "Python 3.9 stdlib cannot decode JPEG pixel data; see module "
                                   "docstring and SUITABILITY.md. image_diagnostics_metadata_only "
                                   "carries header-only stats (dimensions, bytes/megapixel) as a "
                                   "weak, whole-image, corpus-relative diagnostic -- NOT part of "
                                   "risk_score.",
        "data_quality_png_mislabelled_as_jpg": sorted(png_mislabelled),
        "items": items,
        "distribution": distribution,
        "scheduled_editions": {"lo": EDITION_RANGE_LO, "hi": hi},
        "scheduled_rounds_total": len(scheduled),
        "worst_offenders_scheduled": worst,
    }


# ---------------------------------------------------------------------------
# Signal 3 -- Face Value portrait viability (photograph vs stylised likeness)
# ---------------------------------------------------------------------------

_PHOTO_KW = re.compile(
    r"photograph\w*|\bphoto\b|daguerreotype|tintype|ambrotype|collodion|wire photo|press photo",
    re.I)
_SCULPT_KW = re.compile(r"\bbust\b|\bstatue\w*|\bsculpture\w*|\bmarble\b|\bbronze\b|\brelief\b", re.I)
_PAINT_KW = re.compile(
    r"\bpainting\w*|portrait by|self-portrait|\bfresco\w*|\bmosaic\w*|oil on canvas", re.I)
_GRAPHIC_KW = re.compile(
    r"\bengrav\w*|\bwoodcut\w*|\betching\w*|\blithograph\w*|\bdrawing\w*|\bsketch\w*|"
    r"\billustration\w*|\bminiature\w*|\bprint\b|\bmanuscript\w*|\bcoin\w*|\bstamp\w*|"
    r"\bmedal\w*|\btapestry\b|\bicon\b", re.I)
# Small, manually-curated (not exhaustive) list of 19th-century pioneer
# photographers -- only added because it resolves a real, checked case
# (Robert Howlett's famous 1857 photograph of Brunel) that would otherwise
# fall into the 1839-1860 "uncertain" bucket below. See SUITABILITY.md.
_PIONEER_PHOTOGRAPHERS_KW = re.compile(
    r"howlett|mathew b(?:enjamin)?\.? brady|alexander gardner|julia margaret cameron|"
    r"f[eé]lix nadar|\bnadar\b|philip haas|antoine claudet|roger fenton|francis frith|"
    r"john jabez edwin mayall|southworth|hawes|disd[eé]ri", re.I)

_FIRST_PARENS = re.compile(r"\(([^)]{2,60})\)")
_CENTURY = re.compile(r"(\d{1,2})(?:st|nd|rd|th)\s+century", re.I)
_NUMYEAR = re.compile(r"\d{1,4}")

# 1839: public announcement of the daguerreotype process -- practical
# photography did not exist before this date, full stop.
# 1860: by the wet-plate/collodion era, photography had spread widely
# enough in the US/Europe that a surviving photograph is the norm for a
# notable public figure who died after this point, not the exception.
# Between the two: genuinely ambiguous without more information, so this
# script reports "unknown" rather than guessing.
PHOTOGRAPHY_INVENTED_YEAR = 1839
PHOTOGRAPHY_COMMON_YEAR = 1860


def approx_reference_year(blurb):
    """Best-effort life/death year parsed from the blurb's leading
    "(1889-1977)" / "(c. 1341-1323 BC)" / "(c. 5th century BC)" style
    parenthetical. Returns None if nothing parseable is found. Not used
    for anything requiring precision -- only to bucket against the two
    photography-era thresholds above."""
    m = _FIRST_PARENS.search(blurb or "")
    if not m:
        return None
    grp = m.group(1)
    is_bc = bool(re.search(r"\bBCE?\b", grp))
    cm = _CENTURY.search(grp)
    if cm:
        c = int(cm.group(1))
        return -(c * 100) if is_bc else (c - 1) * 100 + 50
    nums = _NUMYEAR.findall(grp)
    if not nums:
        return None
    last = int(nums[-1])
    return -last if is_bc else last


def classify_portrait_medium(item):
    text = " ".join(str(item.get(f, "")) for f in ("attribution", "source", "image_author"))
    if _PHOTO_KW.search(text):
        return "photograph", "explicit_keyword", None
    if _SCULPT_KW.search(text):
        return "sculpture", "explicit_keyword", None
    if _PAINT_KW.search(text):
        return "painting", "explicit_keyword", None
    if _GRAPHIC_KW.search(text):
        return "graphic", "explicit_keyword", None
    if _PIONEER_PHOTOGRAPHERS_KW.search(text):
        return "photograph", "named_pioneer_photographer", None

    ref_year = approx_reference_year(item.get("blurb"))
    if ref_year is None:
        return "unknown", "unparseable_blurb_year", ref_year
    if ref_year < PHOTOGRAPHY_INVENTED_YEAR:
        return "non_photographic_unspecified", "era_predates_photography", ref_year
    if ref_year < PHOTOGRAPHY_COMMON_YEAR:
        return "unknown", "era_ambiguous_1839_1860", ref_year
    return "photograph", "era_after_photography_common", ref_year


def build_portrait_viability(who_items):
    items = {}
    medium_counts = Counter()
    for it in who_items:
        medium, confidence, ref_year = classify_portrait_medium(it)
        stylised = medium in (
            "painting", "sculpture", "graphic", "non_photographic_unspecified")
        medium_counts[medium] += 1
        items[it["id"]] = {
            "name": it.get("name"),
            "difficulty": it.get("difficulty"),
            "inputs": {
                "attribution": it.get("attribution"),
                "source": it.get("source"),
                "image_author": it.get("image_author"),
                "blurb_reference_year_parsed": ref_year,
            },
            "medium": medium,
            "confidence": confidence,
            "stylised_likeness": stylised if medium != "unknown" else None,
            "flag_easy_but_stylised": (it.get("difficulty") == "easy" and stylised),
        }

    total = len(who_items)
    photographic = medium_counts["photograph"]
    stylised_total = (medium_counts["painting"] + medium_counts["sculpture"]
                       + medium_counts["graphic"] + medium_counts["non_photographic_unspecified"])
    unknown_total = medium_counts["unknown"]

    easy_but_stylised = sorted(
        (iid for iid, r in items.items() if r["flag_easy_but_stylised"]),
        key=lambda iid: items[iid]["name"] or iid,
    )

    return {
        "signal": "portrait_viability",
        "source": "data/reveal-who.json",
        "method": "medium classified from attribution/source keywords, falling back to an "
                  "era check against when photography existed (1839) and became common (1860) "
                  "parsed from the blurb's life-dates; one sentence: a portrait can only be a "
                  "genuine photograph if its subject was still alive after photography existed.",
        "thresholds": {
            "photography_invented_year": PHOTOGRAPHY_INVENTED_YEAR,
            "photography_common_year": PHOTOGRAPHY_COMMON_YEAR,
        },
        "items": items,
        "summary": {
            "total": total,
            "by_medium": dict(medium_counts),
            "photograph_fraction": round(photographic / total, 3) if total else None,
            "stylised_fraction": round(stylised_total / total, 3) if total else None,
            "unknown_fraction": round(unknown_total / total, 3) if total else None,
        },
        "worst_offenders_easy_but_stylised": easy_but_stylised,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    figures = load("figures.json")
    who_items = load("reveal-who.json")
    what_items = load("reveal-what.json")
    editions_doc = load("editions.json")

    lifeline = build_lifeline_journey(figures, editions_doc)
    legibility = build_image_legibility(who_items, what_items, editions_doc)
    viability = build_portrait_viability(who_items)

    # Flat items index keyed by id, merging whichever signals apply to that
    # id (the same real-world figure can appear in figures.json AND
    # reveal-who.json under the same id, e.g. "napoleon" -- 146 ids do).
    all_ids = set(lifeline["items"]) | set(legibility["items"]) | set(viability["items"])
    merged = {}
    for iid in sorted(all_ids):
        entry = {}
        if iid in lifeline["items"]:
            entry["lifeline_journey"] = lifeline["items"][iid]
        if iid in legibility["items"]:
            entry["image_legibility"] = legibility["items"][iid]
        if iid in viability["items"]:
            entry["portrait_viability"] = viability["items"][iid]
        merged[iid] = entry

    output = {
        "generatedOn": GENERATED_ON,
        "generator": "tools/fame/build_suitability.py",
        "inputs": {
            "figures": "data/figures.json",
            "reveal_who": "data/reveal-who.json",
            "reveal_what": "data/reveal-what.json",
            "editions": "data/editions.json",
        },
        "counts": {
            "figures": len(figures), "reveal_who": len(who_items), "reveal_what": len(what_items),
            "unique_ids": len(all_ids),
        },
        "items": merged,
        "signals": {
            "lifeline_journey": {k: v for k, v in lifeline.items() if k != "items"},
            "image_legibility": {k: v for k, v in legibility.items() if k != "items"},
            "portrait_viability": {k: v for k, v in viability.items() if k != "items"},
        },
    }

    OUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {len(merged)} merged items -> {OUT_PATH}", file=sys.stderr)
    print(f"  lifeline_journey : {lifeline['distribution']['n']} figures, "
          f"{lifeline['distribution']['under_50km']} under 50km, "
          f"{lifeline['scheduled_rounds_dull']}/{lifeline['scheduled_rounds_total']} "
          f"scheduled rounds (ed {EDITION_RANGE_LO}-{lifeline['scheduled_editions']['hi']}) dull",
          file=sys.stderr)
    print(f"  image_legibility : {legibility['distribution']['n']} items, "
          f"{legibility['distribution']['flagged_worst_offenders_total']} flagged worst offenders, "
          f"{len(legibility['data_quality_png_mislabelled_as_jpg'])} PNGs mislabelled .jpg",
          file=sys.stderr)
    print(f"  portrait_viability: {viability['summary']['photograph_fraction']:.0%} photograph, "
          f"{viability['summary']['stylised_fraction']:.0%} stylised, "
          f"{len(viability['worst_offenders_easy_but_stylised'])} easy-but-stylised",
          file=sys.stderr)


if __name__ == "__main__":
    main()
