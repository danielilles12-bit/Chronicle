"""
Merge every raw harvest into the final tools/fame/universe_objects.json.

Pipeline:
 1. Load raw/unesco_raw.json, raw/vital_raw.json, raw/lists_raw.json, and
    the manual_seed.SEED list.
 2. Canonicalize every raw wikilink title via the enwiki API (redirects
    resolved, batches of 50).
 3. Group by canonical title, merging from_lists / kind / region / era
    hints from every source that pointed at it.
 4. Enrich canonical titles with pageprops+categories to drop
    disambiguation pages and person articles.
 5. Apply a manual blocklist (countries, continents, generic non-object
    terms) and a light context-based country scan to fill in missing
    region for portable-object sources (paintings, ships, manuscripts...).
 6. Write the final JSON.
"""
import json
import os
import re
import sys
from collections import Counter

import wputils
from regions import COUNTRY_REGION, region_for_country
from kindguess import guess_kind
from manual_seed import SEED as MANUAL_SEED

HERE = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(HERE, "raw")
OUT_PATH = os.path.join(HERE, "universe_objects.json")

KIND_PRIORITY = ["painting", "manuscript", "sculpture", "artefact",
                  "monument", "building", "site"]

GENERIC_BLOCKLIST = {
    "museum", "movie theater", "cinema", "bible", "prayer book",
    "book of hours", "seven wonders of the ancient world",
    "new 7 wonders of the world", "new seven wonders of the world",
    "crown jewels of the united kingdom", "roman empire", "byzantine empire",
    "ottoman empire", "united nations", "world heritage site",
    "unesco", "list of world heritage sites", "castle", "cathedral",
    "mosque", "temple", "pagoda", "palace", "bridge", "tower",
    "lighthouse", "fortification", "fort", "pyramid", "obelisk",
    "sculpture", "statue", "painting", "monument", "shipwreck",
    "warship", "tomb", "necropolis", "acropolis", "gospel", "codex",
    "manuscript", "diamond", "crown", "throne", "the wall street journal",
    "the new york times", "reuters", "associated press", "christie's",
    "sotheby's", "national gallery", "national museum",
}

# continents / supranational regions that sometimes leak in as "rows"
PLACE_BLOCKLIST = {
    "africa", "asia", "europe", "north america", "south america",
    "oceania", "antarctica", "middle east", "central asia",
    "southeast asia", "south asia", "east asia", "soviet union",
    "european union", "united nations", "commonwealth of nations",
    "arab world",
}


def load_json(name):
    path = os.path.join(RAW_DIR, name)
    if not os.path.exists(path):
        print(f"WARNING: missing {path}", file=sys.stderr)
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def clean_display_name(name, canonical_title):
    if not name:
        return canonical_title
    n = name
    n = re.sub(r"''+", "", n)               # italics markup
    n = re.sub(r"<br\s*/?>", ", ", n, flags=re.IGNORECASE)  # line breaks
    n = re.sub(r"\{\{[^{}]*\}\}", "", n)     # stray templates
    n = re.sub(r"\s+", " ", n).strip(" ,")
    if not n:
        return canonical_title
    return n


def build_country_scanner():
    names = sorted(set(COUNTRY_REGION.keys()), key=len, reverse=True)
    escaped = [re.escape(n) for n in names]
    pattern = re.compile(r"\b(" + "|".join(escaped) + r")\b")
    return pattern


COUNTRY_SCAN_RE = build_country_scanner()


def scan_context_for_region(context):
    if not context:
        return None
    m = COUNTRY_SCAN_RE.search(context)
    if not m:
        return None
    return region_for_country(m.group(1))


def main():
    unesco_items = load_json("unesco_raw.json")
    vital_items = load_json("vital_raw.json")
    lists_items = load_json("lists_raw.json")

    for it in unesco_items:
        it["tag"] = "unesco"
        it["kind"] = None
        it["era_hint"] = None
    for it in vital_items:
        it["tag"] = f"vital-4:{it.get('vital_section', '')}"
        it["kind"] = None
        it["era_hint"] = None

    manual_items = []
    for name, kind, region, era in MANUAL_SEED:
        manual_items.append({
            "raw_title": name, "name": name, "tag": "curated-landmarks",
            "kind": kind, "region": region, "era_hint": era, "context": "",
        })

    all_raw = unesco_items + vital_items + lists_items + manual_items
    print(f"Total raw rows across all sources: {len(all_raw)}",
          file=sys.stderr)

    raw_titles = [it["raw_title"] for it in all_raw if it.get("raw_title")]
    print(f"Unique raw titles to canonicalize: {len(set(raw_titles))}",
          file=sys.stderr)
    canon_map = wputils.canonicalize_titles(raw_titles)

    # Group by canonical (existing) title
    groups = {}
    dropped_missing = 0
    for it in all_raw:
        raw_title = it.get("raw_title")
        if not raw_title:
            continue
        info = canon_map.get(raw_title)
        if not info or not info.get("exists"):
            dropped_missing += 1
            continue
        canonical = info["title"]
        groups.setdefault(canonical, []).append(it)

    print(f"Dropped (missing/no article): {dropped_missing}",
          file=sys.stderr)
    print(f"Unique canonical titles after redirect-merge: {len(groups)}",
          file=sys.stderr)

    # Enrich for disambiguation / person detection
    canonical_titles = list(groups.keys())
    enrich = wputils.enrich_titles(canonical_titles)

    dropped_disambig = 0
    dropped_person = 0
    dropped_blocklist = 0
    objects = []

    for canonical, items in groups.items():
        low = canonical.lower()
        info = enrich.get(canonical, {})
        if info.get("is_disambig"):
            dropped_disambig += 1
            continue
        if info.get("is_person"):
            dropped_person += 1
            continue
        if low in GENERIC_BLOCKLIST or low in PLACE_BLOCKLIST:
            dropped_blocklist += 1
            continue
        if low in {c.lower() for c in COUNTRY_REGION.keys()}:
            dropped_blocklist += 1
            continue

        tags = sorted(set(i["tag"] for i in items if i.get("tag")))

        # name: prefer a clean display name from any source, shortest
        # non-degenerate one
        candidates = [clean_display_name(i.get("name"), canonical)
                      for i in items]
        candidates = [c for c in candidates if c]
        name = min(candidates, key=len) if candidates else canonical

        # kind: majority vote among explicit hints, else guess
        kind_hints = [i.get("kind") for i in items if i.get("kind")]
        if kind_hints:
            counts = Counter(kind_hints)
            top = counts.most_common()
            best_count = top[0][1]
            tied = [k for k, c in top if c == best_count]
            if len(tied) == 1:
                kind = tied[0]
            else:
                kind = next((k for k in KIND_PRIORITY if k in tied),
                            tied[0])
        else:
            kind = guess_kind(name) or guess_kind(canonical)

        # region: majority vote among explicit hints
        region_hints = [i.get("region") for i in items if i.get("region")]
        region = None
        if region_hints:
            region = Counter(region_hints).most_common(1)[0][0]
        else:
            for i in items:
                region = scan_context_for_region(i.get("context", ""))
                if region:
                    break

        # era: first non-null hint
        era_hint = next((i.get("era_hint") for i in items
                          if i.get("era_hint")), None)

        objects.append({
            "name": name,
            "wiki_title": canonical,
            "kind": kind,
            "region": region,
            "era_hint": era_hint,
            "from_lists": tags,
        })

    print(f"Dropped disambiguation pages: {dropped_disambig}",
          file=sys.stderr)
    print(f"Dropped person articles: {dropped_person}", file=sys.stderr)
    print(f"Dropped blocklist (countries/generic terms): "
          f"{dropped_blocklist}", file=sys.stderr)
    print(f"FINAL object count: {len(objects)}", file=sys.stderr)

    objects.sort(key=lambda o: o["wiki_title"])

    out = {
        "generatedOn": "2026-07-22",
        "sources": [
            "Wikipedia: UNESCO World Heritage Site lists (per-country, "
            "cultural+mixed only, natural-only sites excluded)",
            "Wikipedia:Vital articles/Level 4/Arts (Specific structures, "
            "Cultural venues, Painting, Sculpture sections)",
            "Wikipedia: List of most expensive paintings",
            "Wikipedia: List of diamonds",
            "Wikipedia: List of Roman amphitheatres",
            "Wikipedia: List of illuminated manuscripts",
            "Wikipedia: List of museum ships",
            "Wikipedia: List of colossal sculptures in situ",
            "Wikipedia: List of tallest statues",
            "Wikipedia: List of Egyptian pyramids",
            "Wikipedia: List of the oldest mosques",
            "Wikipedia: List of largest mosques",
            "Wikipedia: List of largest art museums",
            "Wikipedia: List of most-visited museums",
            "Wikipedia: List of obelisks in Rome",
            "Hand-curated seed: Ancient/New 7 Wonders, named crown jewels, "
            "iconic modern landmarks and portable artefacts under-"
            "represented by the above lists (139 items, each verified to "
            "resolve to a real en.wikipedia.org article)",
        ],
        "objects": objects,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"Wrote {OUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
