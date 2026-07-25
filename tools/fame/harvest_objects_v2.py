#!/usr/bin/env python3
"""
harvest_objects_v2.py -- Wikidata object-class + curated-canon harvest for
the Relic ('what') game's object pool.

WHY THIS EXISTS: an audit (24-25 Jul 2026) found the existing object
universe (tools/fame/universe_objects.json, 2219 rows) is 68% immovable
architecture (site/building/monument kinds), because it was harvested from
UNESCO World Heritage SITE lists and Wikipedia "List of..." architecture
articles. The `kind` vocabulary it uses (site, building, artefact,
manuscript, painting, sculpture, monument) has no bucket for an instrument,
garment, tool, vehicle, machine, coin or weapon -- so even portable objects
harvested elsewhere have nowhere sensible to go. This script targets the
missing register directly: Wikidata SPARQL by object CLASS (vehicle, ship,
clothing, tool, weapon, coin, musical instrument, jewellery, machine,
furniture, archaeological find), filtered hard for recognisability, plus
the BBC/British Museum "A History of the World in 100 Objects" list.

This script does NOT touch universe_objects.json, current_inventory.json or
any data/*.json file, and is not wired into build_universe_objects.py. It
only produces tools/fame/object_candidates_v2.json for human review (or a
later session) to merge. See HARVEST_OBJECTS_V2.md for the full writeup.

DESIGN (mirrors tools/fame/fetch_metrics.py's conventions -- this script
imports that module directly and reuses its http_get_json/_cache_path/
_throttle/retry-with-backoff machinery rather than reimplementing it):
  - Python 3.9 stdlib only (urllib.request, json, re, time, pathlib).
    fetch_metrics and regions (both existing, read-only reuse) are the only
    intra-repo imports.
  - Every request carries fetch_metrics.USER_AGENT.
  - Every raw HTTP response is cached under tools/fame/cache/<metric>/
    (cache/ is the existing gitignored symlink to cache.nosync/), keyed by
    a hash of the request URL/query -- via fetch_metrics's own
    _cache_path()/http_get_json(), so throttling, 429/5xx backoff, and
    "a killed-and-restarted run never re-fetches anything cached" are all
    inherited for free, using distinct metric namespaces
    (sparql_objects_v2, enwiki_objects_v2, commons_objects_v2) so nothing
    collides with fetch_metrics's own pageviews/languages/inlinks caches.
  - Network is verified with ONE cheap SPARQL query and ONE cheap enwiki
    API call before anything else runs; the script aborts loudly rather
    than producing fabricated output if either fails.
  - PRIVACY: every request is for public Wikidata/Wikipedia/Commons
    reference data (a QID, a class, a public article title). Nothing about
    this project (its own item ids, schedule, or content) is ever sent
    anywhere.

USAGE:
    cd "tools/fame"
    python3 harvest_objects_v2.py                 # full run, all sources
    python3 harvest_objects_v2.py --sources ship,painting,how100
    python3 harvest_objects_v2.py --refresh        # ignore cache, force re-fetch

OUTPUT:
    tools/fame/raw/objects_v2_sparql.json   -- every raw SPARQL binding row,
                                                by bucket (debug/resumability)
    tools/fame/raw/objects_v2_how100.json   -- raw parsed how100 table rows
    tools/fame/object_candidates_v2.json    -- final deduped, tagged,
                                                kind-mapped candidate list
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
from collections import Counter, OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fetch_metrics as fm            # noqa: E402  -- reuse http/cache/throttle
from regions import COUNTRY_REGION, region_for_country  # noqa: E402

RAW_DIR = HERE / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = HERE / "object_candidates_v2.json"

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
EN_API = "https://en.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

GENERATED_ON = "2026-07-25"


# ---------------------------------------------------------------------------
# HTTP helpers -- thin wrappers over fetch_metrics's cached http_get_json
# ---------------------------------------------------------------------------

def sparql_query(query, cache_key, timeout_note=None):
    url = SPARQL_ENDPOINT + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    cache_file = fm._cache_path("sparql_objects_v2", cache_key)
    result = fm.http_get_json(url, cache_file)
    return result


def enwiki_api(params, cache_key):
    qs = urllib.parse.urlencode(params)
    url = EN_API + "?" + qs
    cache_file = fm._cache_path("enwiki_objects_v2", cache_key)
    return fm.http_get_json(url, cache_file)


def commons_api(params, cache_key):
    qs = urllib.parse.urlencode(params)
    url = COMMONS_API + "?" + qs
    cache_file = fm._cache_path("commons_objects_v2", cache_key)
    return fm.http_get_json(url, cache_file)


def verify_network():
    print("== Network verification ==", file=sys.stderr)
    sparql_ok = False
    try:
        r = sparql_query(
            "SELECT ?item WHERE { ?item wdt:P31 wd:Q146 } LIMIT 1",
            "network_check_v2",
        )
        sparql_ok = bool(r.get("ok") and r.get("body"))
        print(f"  query.wikidata.org SPARQL: {'OK' if sparql_ok else 'FAIL ' + str(r)}",
              file=sys.stderr)
    except Exception as e:
        print(f"  query.wikidata.org SPARQL: FAIL {type(e).__name__}: {e}", file=sys.stderr)

    enwiki_ok = False
    try:
        r = enwiki_api(
            {"action": "query", "format": "json", "titles": "Rosetta Stone", "prop": "pageprops"},
            "network_check_v2",
        )
        enwiki_ok = bool(r.get("ok"))
        print(f"  en.wikipedia.org API: {'OK' if enwiki_ok else 'FAIL ' + str(r)}",
              file=sys.stderr)
    except Exception as e:
        print(f"  en.wikipedia.org API: FAIL {type(e).__name__}: {e}", file=sys.stderr)

    if not (sparql_ok and enwiki_ok):
        print("ABORT: network verification failed; refusing to fabricate output.",
              file=sys.stderr)
        sys.exit(1)
    return True


# ---------------------------------------------------------------------------
# Class registry: single-root jobs (direct P31, or transitive P31/P279*)
# ---------------------------------------------------------------------------
# floor = minimum wikibase:sitelinks required (a quality gate applied inside
# the SPARQL query itself, before ORDER BY/LIMIT, both for query speed on
# huge classes and as the "sitelink count as a floor" quality signal).

SINGLE_ROOT_JOBS = [
    # bucket_id,           kind,                  qid,        mode,          floor, limit
    ("ship",               "ship",                "Q11446",   "transitive",  15,    400),
    ("painting",           "painting",            "Q3305213", "direct",      15,    350),
    ("sculpture",          "sculpture",           "Q860861",  "transitive",  12,    300),
    ("tool",               "tool",                "Q39546",   "transitive",  8,     300),
    ("archaeological_find","archaeological_find", "Q220659",  "transitive",  6,     350),
    ("musical_instrument", "musical_instrument",  "Q34379",   "transitive",  None,  400),
    ("weapon",             "weapon",              "Q728",     "transitive",  None,  300),
    ("coin",               "coin",                "Q41207",   "transitive",  None,  200),
    ("machine",            "machine",             "Q11019",   "transitive",  15,    350),
    ("furniture",          "furniture",           "Q14745",   "transitive",  6,     250),
]

# clothing: Wikidata quirk noted in the brief (a plain P31/P279* wd:Q11460
# query badly undercounts named historical garments -- many are typed via
# headgear or other loosely-linked branches). Union of roots as the fix.
CLOTHING_ROOTS = [
    ("clothing",  "Q11460",     "transitive", 6, 300),
    ("headgear",  "Q1254933",   "transitive", 6, 250),
]

# vehicle: a plain P31/P279* wd:Q42889 query times out (branching factor is
# too large for the public endpoint's 60s budget). Curated union of the
# individually-fast leaf classes that actually carry named historical
# vehicles instead.
VEHICLE_ROOTS = [
    ("car model",        "Q3231690",   "direct", 12,   200),
    ("car",               "Q1420",      "direct", 8,    120),
    ("aircraft model",   "Q15056995",  "direct", 12,   200),
    ("aircraft",          "Q11436",     "direct", 10,   200),
    ("spacecraft",        "Q40218",     "direct", None, 120),
    ("submarine",         "Q2811",      "direct", 10,   150),
    ("motorcycle",        "Q34493",     "direct", None, 120),
    ("locomotive class",  "Q19832486",  "direct", 10,   200),
    ("airship",           "Q133585",    "direct", None, 60),
    ("hot air balloon",   "Q1551574",   "direct", None, 20),
    ("wagon",             "Q859281",    "direct", None, 20),
    ("chariot",           "Q203788",    "direct", None, 20),
    ("stagecoach",        "Q339249",    "direct", None, 20),
    ("sled",              "Q181388",    "direct", None, 20),
    ("tank",              "Q12876",     "direct", None, 20),
]

# jewellery: the modelling quirk flagged in the brief -- a plain instance-of
# query on wd:Q161380 ("jewellery") returns almost nothing because named
# jewellery pieces are typed as specific subclasses. Union of those
# subclasses instead (still small; supplemented by MUST_INCLUDE below).
JEWELLERY_ROOTS = [
    ("necklace", "Q189299",  "direct", None, 30),
    ("bracelet", "Q201664",  "direct", None, 30),
    ("brooch",   "Q499916",  "direct", None, 30),
    ("fibula",   "Q324926",  "direct", None, 30),
    ("tiara",    "Q749249",  "direct", None, 30),
    ("earring",  "Q168456",  "direct", None, 20),
    ("amulet",   "Q131557",  "direct", None, 40),
    ("diadem",   "Q746591",  "direct", None, 20),
]

# Named examples the audit called out as verified-absent from the universe.
# Fetched explicitly by title (via pageprops -> QID -> SPARQL VALUES) so the
# final report can say plainly whether each now has a real candidate row,
# independent of whether the class harvest above happened to net it too.
MUST_INCLUDE_TITLES = [
    "Spinning jenny", "Stephenson's Rocket", "Enigma machine", "Ford Model T",
    "The Ashes", "Stradivarius", "Sutton Hoo helmet", "Staffordshire Hoard",
    "Nebra sky disc", "Cyrus Cylinder", "Standard of Ur", "Lewis chessmen",
    "Vindolanda tablets", "Portland Vase", "Penny Black", "Mary Rose",
    "Vasa (ship)", "Wright Flyer", "Sputnik 1", "Antikythera mechanism",
]


def build_class_query(qid, mode, floor, limit):
    triple = (f"?item wdt:P31 wd:{qid} ." if mode == "direct"
              else f"?item wdt:P31/wdt:P279* wd:{qid} .")
    floor_filter = f"FILTER(?sitelinks >= {floor})" if floor else ""
    return f"""
    SELECT ?item ?itemLabel ?image ?sitelinks ?enwikiTitle ?inception
           ?countryLabel ?commonscat WHERE {{
      {triple}
      ?item wdt:P18 ?image .
      ?item wikibase:sitelinks ?sitelinks .
      {floor_filter}
      ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> ;
                schema:name ?enwikiTitle .
      OPTIONAL {{ ?item wdt:P571 ?inception . }}
      OPTIONAL {{ ?item wdt:P17 ?country . }}
      OPTIONAL {{ ?item wdt:P373 ?commonscat . }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    ORDER BY DESC(?sitelinks)
    LIMIT {limit}
    """


def qid_from_uri(uri):
    return uri.rsplit("/", 1)[-1]


def parse_bindings(body, bucket, kind, source_class_label):
    out = []
    for b in (body.get("results") or {}).get("bindings", []):
        if "item" not in b or "enwikiTitle" not in b:
            continue
        qid = qid_from_uri(b["item"]["value"])
        sitelinks_raw = b.get("sitelinks", {}).get("value")
        try:
            sitelinks = int(float(sitelinks_raw)) if sitelinks_raw is not None else None
        except ValueError:
            sitelinks = None
        out.append({
            "qid": qid,
            "label": b.get("itemLabel", {}).get("value"),
            "image_url": b.get("image", {}).get("value"),
            "sitelinks": sitelinks,
            "enwiki_title": b.get("enwikiTitle", {}).get("value"),
            "inception": b.get("inception", {}).get("value"),
            "country": b.get("countryLabel", {}).get("value"),
            "commonscat": b.get("commonscat", {}).get("value"),
            "bucket": bucket,
            "kind": kind,
            "source_class": source_class_label,
        })
    return out


def harvest_single_root_jobs(jobs, log):
    all_raw = []
    for bucket, kind, qid, mode, floor, limit in jobs:
        query = build_class_query(qid, mode, floor, limit)
        cache_key = f"{bucket}_{qid}_{mode}_{floor}_{limit}"
        result = sparql_query(query, cache_key)
        if not result.get("ok"):
            print(f"  [{bucket}] SPARQL FAILED: {result.get('error')}", file=sys.stderr)
            log[bucket] = {"status": "error", "error": result.get("error"), "raw_count": 0}
            continue
        rows = parse_bindings(result["body"], bucket, kind, bucket)
        all_raw.extend(rows)
        log[bucket] = {"status": "ok", "raw_count": len(rows), "qid": qid, "mode": mode,
                        "floor": floor, "limit": limit}
        print(f"  [{bucket}] {len(rows)} rows (qid={qid} mode={mode} floor={floor})",
              file=sys.stderr)
        time.sleep(0.3)
    return all_raw


def harvest_union_jobs(bucket, kind, roots, log):
    all_raw = []
    seen_qids = set()
    per_root_counts = {}
    for root_label, qid, mode, floor, limit in roots:
        query = build_class_query(qid, mode, floor, limit)
        cache_key = f"{bucket}_{root_label}_{qid}_{mode}_{floor}_{limit}"
        result = sparql_query(query, cache_key)
        if not result.get("ok"):
            print(f"  [{bucket}/{root_label}] SPARQL FAILED: {result.get('error')}",
                  file=sys.stderr)
            per_root_counts[root_label] = {"status": "error", "raw_count": 0}
            continue
        rows = parse_bindings(result["body"], bucket, kind, root_label)
        new_rows = [r for r in rows if r["qid"] not in seen_qids]
        for r in new_rows:
            seen_qids.add(r["qid"])
        all_raw.extend(new_rows)
        per_root_counts[root_label] = {"status": "ok", "raw_count": len(rows),
                                        "new_after_union": len(new_rows)}
        print(f"  [{bucket}/{root_label}] {len(rows)} rows, {len(new_rows)} new "
              f"(qid={qid})", file=sys.stderr)
        time.sleep(0.3)
    log[bucket] = {"status": "ok", "raw_count": len(all_raw), "per_root": per_root_counts}
    return all_raw


def fetch_items_by_qid(qids, bucket, kind, source_label, batch_size=120):
    """Bulk-enrich a known list of Wikidata QIDs (used for MUST_INCLUDE and
    for how100 rows once resolved to a QID)."""
    out = []
    qids = list(dict.fromkeys(qids))
    for i in range(0, len(qids), batch_size):
        batch = qids[i:i + batch_size]
        values = " ".join(f"wd:{q}" for q in batch)
        query = f"""
        SELECT ?item ?itemLabel ?image ?sitelinks ?enwikiTitle ?inception
               ?countryLabel ?commonscat WHERE {{
          VALUES ?item {{ {values} }}
          OPTIONAL {{ ?item wdt:P18 ?image . }}
          OPTIONAL {{ ?item wikibase:sitelinks ?sitelinks . }}
          OPTIONAL {{ ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> ;
                                schema:name ?enwikiTitle . }}
          OPTIONAL {{ ?item wdt:P571 ?inception . }}
          OPTIONAL {{ ?item wdt:P17 ?country . }}
          OPTIONAL {{ ?item wdt:P373 ?commonscat . }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        """
        cache_key = f"byqid_{bucket}_{i}_{'_'.join(batch[:3])}"
        result = sparql_query(query, cache_key)
        if not result.get("ok"):
            print(f"  [by-qid {bucket}] SPARQL FAILED: {result.get('error')}", file=sys.stderr)
            continue
        rows = parse_bindings(result["body"], bucket, kind, source_label)
        out.extend(rows)
        time.sleep(0.3)
    return out


# ---------------------------------------------------------------------------
# "A History of the World in 100 Objects" (BBC Radio 4 / British Museum)
# ---------------------------------------------------------------------------

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")
FILE_LINK_RE = re.compile(r"^\s*(File|Image):", re.IGNORECASE)
EXTLINK_RE = re.compile(r"\[https?://\S+\s+([^\]]+)\]")
REF_RE = re.compile(r"<ref[^>]*/?>.*?</ref>|<ref[^>]*/>", re.DOTALL | re.IGNORECASE)


def first_wikilink(text):
    for m in WIKILINK_RE.finditer(text):
        target = m.group(1).strip()
        if FILE_LINK_RE.match(target):
            continue
        display = m.group(2)
        display = display.strip() if display else target
        return target, display
    return None, None


def strip_wiki_markup(text):
    text = REF_RE.sub("", text)
    text = WIKILINK_RE.sub(lambda m: (m.group(2) or m.group(1)).strip(), text)
    text = EXTLINK_RE.sub(lambda m: m.group(1).strip(), text)
    text = re.sub(r"'{2,}", "", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\s+", " ", text).strip(" ,")
    return text


def fetch_how100_wikitext():
    result = enwiki_api({
        "action": "query", "format": "json", "prop": "revisions", "rvprop": "content",
        "rvslots": "main", "titles": "A History of the World in 100 Objects",
        "formatversion": "2",
    }, "how100_wikitext")
    if not result.get("ok"):
        return None
    pages = ((result.get("body") or {}).get("query") or {}).get("pages") or []
    if not pages or "missing" in pages[0]:
        return None
    revs = pages[0].get("revisions")
    if not revs:
        return None
    return revs[0]["slots"]["main"]["content"]


TABLE_BLOCK_RE = re.compile(r'\{\|\s*class="wikitable".*?\n(.*?)\n\|\}', re.DOTALL)


def parse_how100_rows(wikitext):
    for marker in ("==See also==", "==References==", "==External links=="):
        idx = wikitext.find(marker)
        if idx != -1:
            wikitext = wikitext[:idx]

    rows = []
    for block_match in TABLE_BLOCK_RE.finditer(wikitext):
        block = block_match.group(1)
        for line in block.split("\n"):
            line = line.strip()
            if not line.startswith("|") or line.startswith("|-") or line.startswith("|}") \
                    or line.startswith("!"):
                continue
            cells = [c.strip() for c in line[1:].split("||")]
            if len(cells) < 5:
                continue
            image_cell, number_cell, object_cell, origin_cell, date_cell = cells[:5]
            target, display = first_wikilink(object_cell)
            rows.append({
                "number": number_cell.strip(),
                "raw_object": object_cell,
                "name": strip_wiki_markup(display or object_cell) or strip_wiki_markup(object_cell),
                "wikilink_target": target,
                "origin": strip_wiki_markup(origin_cell),
                "date": strip_wiki_markup(date_cell),
            })
    return rows


def resolve_titles_to_qids(titles, batch_size=50):
    """Batch enwiki API: titles -> {canonical_title, qid, missing}."""
    out = {}
    titles = list(dict.fromkeys(t for t in titles if t))
    for i in range(0, len(titles), batch_size):
        batch = titles[i:i + batch_size]
        result = enwiki_api({
            "action": "query", "format": "json", "titles": "|".join(batch),
            "redirects": "1", "prop": "pageprops", "ppprop": "wikibase_item|disambiguation",
            "formatversion": "2",
        }, f"resolve_{i}_{hash(tuple(batch)) & 0xffffffff}")
        if not result.get("ok"):
            continue
        body = result.get("body") or {}
        query = body.get("query", {})
        norm_map = {n["from"]: n["to"] for n in query.get("normalized", [])}
        redir_map = {r["from"]: r["to"] for r in query.get("redirects", [])}
        pages_by_title = {p["title"]: p for p in query.get("pages", [])}
        for raw in batch:
            cur = raw
            if cur in norm_map:
                cur = norm_map[cur]
            if cur in redir_map:
                cur = redir_map[cur]
            page = pages_by_title.get(cur)
            if page is None or page.get("missing"):
                out[raw] = {"canonical_title": cur, "qid": None, "missing": True,
                            "is_disambig": False}
                continue
            pageprops = page.get("pageprops", {}) or {}
            out[raw] = {
                "canonical_title": page.get("title", cur),
                "qid": pageprops.get("wikibase_item"),
                "missing": False,
                "is_disambig": "disambiguation" in pageprops,
            }
        time.sleep(0.2)
    return out


# ---------------------------------------------------------------------------
# Quality filtering / kind refinement / recognition tagging
# ---------------------------------------------------------------------------

BAD_NAME_RE = re.compile(
    r"^(unidentified|unknown|untitled|fragment(?:s)? of an? unidentified|"
    r"object \d+|no\.\s*\d+|item \d+|catalogue|accession)\b", re.IGNORECASE)
PURE_NUMBER_RE = re.compile(r"^[\d\s.,\-–]+$")

DISAMBIG_HINT_RE = re.compile(r"\(disambiguation\)$", re.IGNORECASE)

GENERIC_BLOCKLIST = {
    "car", "aircraft", "ship", "vehicle", "clothing", "tool", "weapon",
    "coin", "furniture", "machine", "jewellery", "sculpture", "painting",
    "musical instrument", "submarine", "motorcycle", "spacecraft",
}


def is_low_quality_name(name):
    if not name:
        return True
    n = name.strip()
    if len(n) < 3:
        return True
    if PURE_NUMBER_RE.match(n):
        return True
    if BAD_NAME_RE.match(n):
        return True
    if DISAMBIG_HINT_RE.search(n):
        return True
    if n.lower() in GENERIC_BLOCKLIST:
        return True
    return False


# Extended `kind` refinement keywords -- used only for how100 rows (no
# SPARQL class hint) and as a light override where a class-harvested name
# obviously belongs to a more specific bucket than its source class implied.
KIND_KEYWORDS = OrderedDict([
    ("manuscript", ["codex", "manuscript", "gospel", "book of", "scroll", "papyrus",
                    "psalter", "chronicle", "folio", "tablet of", "tablets"]),
    ("coin", ["coin", "denarius", "shekel", "stater", "sovereign (coin)"]),
    ("jewellery", ["necklace", "bracelet", "brooch", "tiara", "earring", "amulet",
                   "diadem", "torc", "pendant", "crown of", "crown jewels"]),
    ("clothing", ["dress", "robe", "cloak", "uniform of", "tunic", "kimono", "armour of",
                  "vestment", "cope", "coronation robe", "sandal", "shoe", "boot",
                  "hat of", "helmet of", "slippers"]),
    ("weapon", ["sword", "dagger", "spear", "musket", "rifle", "cannon", "shield of",
                "armour", "armor", "bow of", "arrow"]),
    ("musical_instrument", ["violin", "stradivarius", "piano", "organ", "harp", "lyre",
                            "drum of", "trumpet", "guitar"]),
    ("tool", ["axe", "chisel", "hammer of", "plough", "loom", "spinning jenny",
              "printing press", "astrolabe", "sundial", "clock", "compass"]),
    ("machine", ["engine", "machine", "computer", "mechanism", "device", "apparatus"]),
    ("vehicle", ["locomotive", "car", "automobile", "aircraft", "airplane", "biplane",
                 "chariot", "wagon", "carriage", "balloon", "airship", "tank",
                 "spacecraft", "rocket", "capsule", "satellite", "flyer"]),
    ("ship", ["ship", "warship", "shipwreck", "vessel", "galleon", "frigate",
              "submarine"]),
    ("furniture", ["throne", "chair of", "desk of", "table of", "cabinet", "chest of"]),
    ("archaeological_find", ["hoard", "helmet", "disc", "cylinder", "standard of",
                             "mask of", "figurine", "urn", "amphora", "vase", "stele",
                             "stone of"]),
    ("sculpture", ["statue", "bust of", "sculpture", "colossus", "sphinx"]),
    ("painting", ["madonna", "portrait of", "the last supper"]),
])


def guess_kind_extended(name, default="artefact"):
    n = (name or "").lower()
    for kind, keys in KIND_KEYWORDS.items():
        if any(k in n for k in keys):
            return kind
    return default


ICONIC_TITLES = {
    t.lower() for t in [
        "Rosetta Stone", "Enigma machine", "Antikythera mechanism",
        "Sutton Hoo helmet", "Staffordshire Hoard", "Nebra sky disc",
        "Cyrus Cylinder", "Standard of Ur", "Lewis chessmen",
        "Vindolanda tablets", "Portland Vase", "Penny Black", "Mary Rose",
        "Vasa (ship)", "Vasa", "Wright Flyer", "Sputnik 1",
        "Stephenson's Rocket", "Spinning jenny", "Ford Model T",
        "The Ashes", "Stradivarius", "Bayeux Tapestry", "Domesday Book",
        "Magna Carta", "Liberty Bell", "Spirit of St. Louis",
        "Apollo 11", "Vostok 1", "Enola Gay", "Little Boy", "Fat Man",
        "Gutenberg Bible", "Jacquard loom", "Supermarine Spitfire",
        "Flying Scotsman (locomotive)", "Terracotta Army",
        "Shroud of Turin", "Dead Sea Scrolls", "Voynich manuscript",
        "Hope Diamond", "Coronation Chair", "Resolute desk",
        "Trevithick's steam locomotive", "Difference engine",
        "Rocket (locomotive)", "Titanic", "RMS Titanic", "Cutty Sark",
        "HMS Victory", "USS Constitution", "Old Ironsides",
        "Wright brothers", "Hindenburg", "Graf Zeppelin",
        "Amati", "Guarneri", "Stradivari",
    ]
}


def normalize_title(s):
    if not s:
        return ""
    s = s.strip().lower()
    s = re.sub(r"^the\s+", "", s)
    s = re.sub(r"\s*\([^)]*\)$", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tag_recognition(sitelinks, enwiki_title, from_how100):
    norm = normalize_title(enwiki_title)
    is_iconic = any(normalize_title(t) == norm for t in ICONIC_TITLES)
    sl = sitelinks or 0
    if is_iconic or sl >= 70 or (from_how100 and sl >= 40):
        return "household_name"
    if sl >= 15 or from_how100:
        return "enthusiast"
    return "specialist"


# ---------------------------------------------------------------------------
# Dedup against existing pools (read-only)
# ---------------------------------------------------------------------------

def load_known_titles():
    """
    Known-title set for dedup, keyed ONLY on fields that are authoritative
    identifiers for a specific real-world object -- wiki_title (the enwiki
    article title, unambiguous) and, for reveal-what.json which has no
    wiki_title, its curated name+variants (hand-picked aliases of THAT one
    object, not generic words).

    Deliberately does NOT match on universe_objects.json's free-text "name"
    or a Wikidata item's short itemLabel: both can be a single generic word
    (e.g. Wikidata Q150758 "Enigma machine" has itemLabel "Enigma", which
    would otherwise false-collide with an unrelated Connections tile also
    displayed as "Enigma", and with "The Enigma (diamond)"'s name "The
    Enigma"). wiki_title/variants are the only fields safe to match
    generically -- caught during this harvest's own smoke-testing.
    """
    known = set()
    universe_path = HERE / "universe_objects.json"
    if universe_path.exists():
        data = json.loads(universe_path.read_text(encoding="utf-8"))
        for o in data.get("objects", []):
            known.add(normalize_title(o.get("wiki_title")))

    inventory_path = HERE / "current_inventory.json"
    if inventory_path.exists():
        data = json.loads(inventory_path.read_text(encoding="utf-8"))
        for it in data.get("items", []):
            if it.get("game") != "what":
                continue
            if it.get("wiki_title"):
                known.add(normalize_title(it["wiki_title"]))

    reveal_what_path = HERE.parent.parent / "data" / "reveal-what.json"
    if reveal_what_path.exists():
        data = json.loads(reveal_what_path.read_text(encoding="utf-8"))
        for it in data:
            known.add(normalize_title(it.get("name")))
            for v in it.get("variants", []) or []:
                known.add(normalize_title(v))

    known.discard("")
    return known


# ---------------------------------------------------------------------------
# Image licence lookup (best-effort, via Commons API)
# ---------------------------------------------------------------------------

def commons_filename_from_url(image_url):
    if not image_url:
        return None
    tail = urllib.parse.unquote(image_url.rsplit("/", 1)[-1])
    return tail


def fetch_commons_licence(image_url):
    fname = commons_filename_from_url(image_url)
    if not fname:
        return None
    title = f"File:{fname}"
    result = commons_api({
        "action": "query", "format": "json", "titles": title,
        "prop": "imageinfo", "iiprop": "extmetadata|url",
        "formatversion": "2",
    }, f"licence_{fname}")
    if not result.get("ok"):
        return None
    pages = ((result.get("body") or {}).get("query") or {}).get("pages") or []
    if not pages or pages[0].get("missing"):
        return None
    ii = pages[0].get("imageinfo")
    if not ii:
        return None
    meta = ii[0].get("extmetadata", {}) or {}

    def _val(key):
        return (meta.get(key) or {}).get("value")

    licence = _val("LicenseShortName") or _val("License")
    return {
        "licence": licence,
        "artist": re.sub(r"<[^>]+>", "", _val("Artist") or "") or None,
        "credit": re.sub(r"<[^>]+>", "", _val("Credit") or "") or None,
        "commons_url": ii[0].get("descriptionurl"),
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

ALL_SOURCES = (
    [b for b, *_ in SINGLE_ROOT_JOBS]
    + ["clothing", "vehicle", "jewellery", "must_include", "how100"]
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default=",".join(ALL_SOURCES),
                         help="comma-separated subset of: " + ",".join(ALL_SOURCES))
    parser.add_argument("--skip-licence", action="store_true",
                         help="skip the per-candidate Commons licence lookup pass "
                              "(faster, but drops image_licence field)")
    parser.add_argument("--from-raw", action="store_true",
                         help="skip ALL network harvesting; reload raw rows from "
                              "tools/fame/raw/objects_v2_sparql.json (written by a "
                              "previous run) and re-run only the offline "
                              "filter/dedupe/tag/kind/region stages. Implies "
                              "--skip-licence (Commons lookups are a network call "
                              "too). Use this to reprocess a completed harvest "
                              "without re-hitting Wikidata/enwiki at all.")
    args = parser.parse_args()
    wanted = set(s.strip() for s in args.sources.split(",") if s.strip())

    log = {}
    raw_all = []
    must_include_rows = []

    if args.from_raw:
        args.skip_licence = True
        cache_path = RAW_DIR / "objects_v2_sparql.json"
        if not cache_path.exists():
            print(f"ABORT: --from-raw given but {cache_path} does not exist.",
                  file=sys.stderr)
            sys.exit(1)
        raw_all = json.loads(cache_path.read_text(encoding="utf-8"))
        print(f"== --from-raw: loaded {len(raw_all)} rows from {cache_path} "
              f"(no network calls made) ==", file=sys.stderr)
        by_bucket = Counter(r.get("bucket") for r in raw_all)
        for bucket, count in by_bucket.items():
            log[bucket] = {"status": "ok (from-raw)", "raw_count": count}
        must_include_rows = [r for r in raw_all if r.get("bucket") == "must_include"]
        wanted = set(by_bucket.keys())
        # jump straight to the merge/filter/dedupe/tag pipeline below
        _run_pipeline(raw_all, must_include_rows, log, wanted, args)
        return

    verify_network()

    print("\n== Single-root class harvests ==", file=sys.stderr)
    jobs = [j for j in SINGLE_ROOT_JOBS if j[0] in wanted]
    if jobs:
        raw_all.extend(harvest_single_root_jobs(jobs, log))

    if "clothing" in wanted:
        print("\n== clothing (union: clothing + headgear) ==", file=sys.stderr)
        raw_all.extend(harvest_union_jobs("clothing", "clothing", CLOTHING_ROOTS, log))

    if "vehicle" in wanted:
        print("\n== vehicle (curated leaf-class union) ==", file=sys.stderr)
        raw_all.extend(harvest_union_jobs("vehicle", "vehicle", VEHICLE_ROOTS, log))

    if "jewellery" in wanted:
        print("\n== jewellery (curated leaf-class union -- Wikidata quirk workaround) ==",
              file=sys.stderr)
        raw_all.extend(harvest_union_jobs("jewellery", "jewellery", JEWELLERY_ROOTS, log))

    if "must_include" in wanted:
        print("\n== must-include named examples (from the audit brief) ==", file=sys.stderr)
        resolved = resolve_titles_to_qids(MUST_INCLUDE_TITLES)
        qids = [info["qid"] for info in resolved.values() if info.get("qid")]
        missing_titles = [t for t, info in resolved.items() if not info.get("qid")]
        if missing_titles:
            print(f"  no Wikidata item found for: {missing_titles}", file=sys.stderr)
        must_include_rows = fetch_items_by_qid(qids, "must_include", None, "must_include")
        # kind for must-include rows: guess from name since there's no single
        # source class (they span vehicle/machine/tool/weapon/archaeological_find...)
        for r in must_include_rows:
            r["kind"] = guess_kind_extended(f"{r.get('label') or ''} {r.get('enwiki_title') or ''}".strip())
        log["must_include"] = {"status": "ok", "raw_count": len(must_include_rows),
                                "requested": len(MUST_INCLUDE_TITLES),
                                "missing": missing_titles}
        print(f"  {len(must_include_rows)}/{len(MUST_INCLUDE_TITLES)} resolved",
              file=sys.stderr)
        raw_all.extend(must_include_rows)

    how100_candidates = []
    if "how100" in wanted:
        print("\n== A History of the World in 100 Objects ==", file=sys.stderr)
        wikitext = fetch_how100_wikitext()
        if wikitext is None:
            print("  FAILED to fetch how100 article wikitext", file=sys.stderr)
            log["how100"] = {"status": "error", "raw_count": 0}
        else:
            rows = parse_how100_rows(wikitext)
            (RAW_DIR / "objects_v2_how100.json").write_text(
                json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
            titles_to_resolve = [r["wikilink_target"] or r["name"] for r in rows]
            resolved = resolve_titles_to_qids(titles_to_resolve)
            qids = []
            qid_to_row = {}
            unresolved = 0
            for r in rows:
                key = r["wikilink_target"] or r["name"]
                info = resolved.get(key)
                if info and info.get("qid") and not info.get("is_disambig"):
                    qids.append(info["qid"])
                    qid_to_row[info["qid"]] = r
                else:
                    unresolved += 1
            fetched = fetch_items_by_qid(qids, "how100", None, "how100")
            for r in fetched:
                src_row = qid_to_row.get(r["qid"], {})
                r["kind"] = guess_kind_extended(f"{r.get('label') or ''} {r.get('enwiki_title') or ''}".strip())
                r["how100_origin"] = src_row.get("origin")
                r["how100_date"] = src_row.get("date")
                r["how100_number"] = src_row.get("number")
            how100_candidates = fetched
            log["how100"] = {"status": "ok", "raw_rows": len(rows),
                              "resolved_to_qid": len(qids), "unresolved": unresolved,
                              "final_candidates": len(fetched)}
            print(f"  {len(rows)} table rows, {len(qids)} resolved to a Wikidata item, "
                  f"{unresolved} left unresolved", file=sys.stderr)
            raw_all.extend(fetched)

    _run_pipeline(raw_all, must_include_rows, log, wanted, args)


def _run_pipeline(raw_all, must_include_rows, log, wanted, args):
    """Everything downstream of raw row collection: merge/dedupe, quality
    filter, dedup-against-existing-pools, recognition tagging, kind
    refinement, region/era enrichment, final assembly + summary + write.
    Shared by the normal network-harvest path and --from-raw (offline
    reprocessing of an already-completed harvest's cached raw rows)."""
    if not args.from_raw:
        (RAW_DIR / "objects_v2_sparql.json").write_text(
            json.dumps(raw_all, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nTotal raw rows across all sources: {len(raw_all)}", file=sys.stderr)

    # -----------------------------------------------------------------
    # Merge/dedupe within this run (by QID; a candidate may have matched
    # more than one bucket/root -- keep the first, record all sources hit)
    # -----------------------------------------------------------------
    by_qid = OrderedDict()
    for row in raw_all:
        qid = row["qid"]
        if qid not in by_qid:
            by_qid[qid] = dict(row)
            by_qid[qid]["also_matched"] = []
            how100_flag = row.get("bucket") == "how100"
            by_qid[qid]["from_how100"] = how100_flag
        else:
            existing = by_qid[qid]
            src = row.get("source_class") or row.get("bucket")
            if src and src not in existing["also_matched"] and src != existing.get("source_class"):
                existing["also_matched"].append(src)
            if row.get("bucket") == "how100":
                existing["from_how100"] = True
            # prefer a real name/sitelinks if the first hit was missing one
            if not existing.get("label") and row.get("label"):
                existing["label"] = row["label"]
            if (existing.get("sitelinks") is None) and row.get("sitelinks") is not None:
                existing["sitelinks"] = row["sitelinks"]

    within_run_dedup_dropped = len(raw_all) - len(by_qid)
    print(f"Unique Wikidata items after within-run QID dedup: {len(by_qid)} "
          f"({within_run_dedup_dropped} duplicate bucket-hits collapsed)", file=sys.stderr)

    # -----------------------------------------------------------------
    # Quality filter
    # -----------------------------------------------------------------
    quality_dropped = 0
    survivors = []
    for qid, row in by_qid.items():
        name = row.get("label") or row.get("enwiki_title")
        if is_low_quality_name(name) or is_low_quality_name(row.get("enwiki_title")):
            quality_dropped += 1
            continue
        if not row.get("enwiki_title") or not row.get("image_url"):
            quality_dropped += 1
            continue
        survivors.append(row)
    print(f"After quality-name filter: {len(survivors)} "
          f"({quality_dropped} dropped: generic/catalogue/missing name or image)",
          file=sys.stderr)

    # -----------------------------------------------------------------
    # Dedup against existing pools (read-only)
    # -----------------------------------------------------------------
    known_titles = load_known_titles()
    print(f"Loaded {len(known_titles)} known normalized titles from "
          f"universe_objects.json / current_inventory.json / data/reveal-what.json",
          file=sys.stderr)

    new_candidates = []
    already_known = 0
    for row in survivors:
        # Match only on wiki_title (the authoritative enwiki article
        # identity) -- never on the Wikidata itemLabel, which can be a
        # generic short word (see load_known_titles docstring).
        norm = normalize_title(row.get("enwiki_title"))
        if norm in known_titles:
            already_known += 1
            continue
        new_candidates.append(row)
    print(f"After dedup against existing pools: {len(new_candidates)} genuinely new "
          f"({already_known} already known)", file=sys.stderr)

    # -----------------------------------------------------------------
    # Recognition tagging + specialist exclusion
    # -----------------------------------------------------------------
    tagged = []
    specialist_dropped = 0
    for row in new_candidates:
        tag = tag_recognition(row.get("sitelinks"), row.get("enwiki_title"),
                               row.get("from_how100", False))
        if tag == "specialist":
            specialist_dropped += 1
            continue
        row["recognition"] = tag
        tagged.append(row)
    print(f"After specialist exclusion: {len(tagged)} kept "
          f"({specialist_dropped} tagged specialist and dropped)", file=sys.stderr)

    # -----------------------------------------------------------------
    # Kind refinement pass (light override: a name matching a more specific
    # keyword than its source class implied gets bumped)
    # -----------------------------------------------------------------
    for row in tagged:
        name = f"{row.get('label') or ''} {row.get('enwiki_title') or ''}".strip()
        refined = guess_kind_extended(name, default=row.get("kind") or "artefact")
        # only override when the refined guess differs AND isn't the generic
        # fallback "artefact" stepping on a real class hint
        if refined != "artefact" or not row.get("kind"):
            row["kind"] = refined if row.get("kind") is None else row.get("kind")
        if row.get("kind") is None:
            row["kind"] = refined

    # -----------------------------------------------------------------
    # Region + era + licence enrichment
    # -----------------------------------------------------------------
    print("\n== Region + licence enrichment ==", file=sys.stderr)
    for i, row in enumerate(tagged, 1):
        country = row.get("country")
        row["region"] = region_for_country(country) if country else None
        row["culture_or_region"] = country
        row["date_era"] = row.get("inception") or row.get("how100_date")

        if not args.skip_licence:
            try:
                lic = fetch_commons_licence(row.get("image_url"))
            except Exception as e:
                lic = None
                print(f"  licence lookup error for qid={row['qid']}: {e}", file=sys.stderr)
            row["image_licence"] = (lic or {}).get("licence")
            row["image_artist"] = (lic or {}).get("artist")
            row["image_commons_url"] = (lic or {}).get("commons_url")
        if i % 200 == 0:
            print(f"  ...{i}/{len(tagged)} enriched", file=sys.stderr)

    # -----------------------------------------------------------------
    # Final record shape
    # -----------------------------------------------------------------
    final = []
    for row in tagged:
        final.append({
            "name": row.get("label") or row.get("enwiki_title"),
            "wiki_title": row.get("enwiki_title"),
            "wikidata_id": row.get("qid"),
            "kind": row.get("kind"),
            "date_era": row.get("date_era"),
            "culture_region": row.get("culture_or_region"),
            "region": row.get("region"),
            "image_url": row.get("image_url"),
            "image_licence": row.get("image_licence") if not args.skip_licence else None,
            "image_artist": row.get("image_artist") if not args.skip_licence else None,
            "image_commons_url": row.get("image_commons_url") if not args.skip_licence else None,
            "sitelinks": row.get("sitelinks"),
            "recognition": row.get("recognition"),
            "source_bucket": row.get("bucket"),
            "source_class": row.get("source_class"),
            "also_matched_classes": row.get("also_matched") or [],
            "from_how100": bool(row.get("from_how100")),
            "how100_number": row.get("how100_number"),
        })

    final.sort(key=lambda r: (-(r["sitelinks"] or 0), r["wiki_title"] or ""))

    # -----------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------
    per_kind = Counter(r["kind"] for r in final)
    per_recognition = Counter(r["recognition"] for r in final)
    per_bucket = Counter(r["source_bucket"] for r in final)

    summary = {
        "generatedOn": GENERATED_ON,
        "sources_run": sorted(wanted),
        "total_raw_rows": len(raw_all),
        "unique_after_within_run_dedup": len(by_qid),
        "after_quality_filter": len(survivors),
        "already_known_dropped": already_known,
        "specialist_dropped": specialist_dropped,
        "total_new_candidates": len(final),
        "per_kind": dict(per_kind),
        "per_recognition": dict(per_recognition),
        "per_source_bucket": dict(per_bucket),
        "job_log": log,
        "must_include_check": {
            t: any(normalize_title(c["wiki_title"]) == normalize_title(t) for c in final)
            or any(normalize_title(r.get("enwiki_title")) == normalize_title(t)
                   for r in must_include_rows)
            for t in MUST_INCLUDE_TITLES
        },
    }

    out = {
        "generatedOn": GENERATED_ON,
        "notes": [
            "Wikidata SPARQL by object class (wdt:P31 / wdt:P31/wdt:P279*), "
            "filtered to items with an image (P18) AND an enwiki sitelink, "
            "plus the BBC/British Museum 'A History of the World in 100 "
            "Objects' list. See tools/fame/HARVEST_OBJECTS_V2.md.",
            "Does not touch universe_objects.json, current_inventory.json or "
            "any data/*.json file -- for human review / a later merge pass "
            "into build_universe_objects.py only.",
            "'specialist'-tagged candidates were dropped entirely per spec; "
            "only household_name/enthusiast survive into this file.",
        ],
        "summary": summary,
        "candidates": final,
    }

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nWrote {OUT_PATH} ({len(final)} candidates)", file=sys.stderr)
    print(json.dumps(summary, indent=1), file=sys.stderr)


if __name__ == "__main__":
    main()
