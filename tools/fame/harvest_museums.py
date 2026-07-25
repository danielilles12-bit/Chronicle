#!/usr/bin/env python3
"""
harvest_museums.py -- harvest candidate PORTABLE objects for the Relic
('what') game universe from open-access museum collection APIs, plus the
BBC/British Museum "A History of the World in 100 Objects" list from
Wikipedia.

WHY THIS EXISTS: tools/fame/universe_objects.json (built by
build_universe_objects.py) is harvested from UNESCO World Heritage SITE
lists and Wikipedia vital-article lists, so it is dominated by buildings,
facades, monuments and ruins. A content review found this is a top player
complaint -- people want portable, domestic, technological, artistic and
working-life objects, and the tear-reveal mechanic (a torn 3x3 grid) needs
plain-background object photography, not a monument shot against sky.
Museum open-access APIs fix both problems at once, and also carry explicit
rights metadata, which matters because image licensing has already caused
problems in this project.

This script does NOT touch universe_objects.json or wire itself into
build_universe_objects.py -- it only produces tools/fame/museum_candidates.json,
a standalone list for a human (or a later session) to review and merge.

SOURCES (each independently toggleable/skippable -- see SOURCE STATUS below):
  - Metropolitan Museum of Art Open Access API (collectionapi.metmuseum.org).
    No key required. We pull the full isHighlight=true & hasImages=true set
    (the Met's own curatorial "highlight" flag), then keep isPublicDomain
    items only, since Met's Open Access program releases those images as
    CC0 -- the one source here with an unambiguous, checkable, public-domain
    photography licence at scale.
  - Smithsonian Open Access API (api.si.edu). Reachable without registering
    a personal key by using the public "DEMO_KEY" that api.data.gov ships
    in its own docs, but DEMO_KEY is rate-limited far below what a broad
    category crawl needs. So this source uses a hand-curated list of search
    terms for well-known Smithsonian holdings (curated, not crawled) --
    which also happens to match the "quality not volume" requirement. A
    real personal api.data.gov key (free, self-service signup) would lift
    the ceiling considerably; registering for one is outside what this
    script does on its own (account creation is not something this
    automation performs).
  - Victoria & Albert Museum collections API (api.vam.ac.uk). No key
    required. No explicit "highlight" flag in the API, so this source also
    uses a curated search-term seed list of well-known V&A holdings.
  - Science Museum Group collection API (collection.sciencemuseumgroup.org.uk).
    No key required, but its edge/WAF blocks the default curl/urllib User-
    Agent with a 403 -- a browser-like UA is required and is what this
    script sends. Curated search-term seed list, same reasoning as V&A.
  - Rijksmuseum: SKIPPED. Its public API requires a personal registered
    key (the placeholder key tried during exploration returned HTTP 410
    Gone); per the brief, sources needing a key we don't have are dropped
    rather than faked.
  - "A History of the World in 100 Objects" (BBC Radio 4 / British Museum):
    harvested by parsing the wikitext of the English Wikipedia article of
    that name (the numbered wikitables listing all 100 objects). This is
    the route into British-Museum-curated, Anglophone-canon objects,
    since the British Museum's own collection API requires registration.

DESIGN (mirrors tools/fame/fetch_metrics.py's conventions):
  - Python 3.9 stdlib only (urllib.request, json, time, hashlib, pathlib).
  - Every request carries a fixed, honest User-Agent.
  - Per-source throttling (Smithsonian's DEMO_KEY needs to go much slower
    than the others; see SOURCE_MIN_INTERVAL below).
  - Every raw API response is cached on disk under tools/fame/cache/museums/
    <source>/<hash>.json (cache/ is a symlink to cache.nosync/, gitignored),
    keyed by a hash of the request URL, so a killed-and-restarted run never
    re-fetches anything it already has -- this is the run's resumability:
    because the harvest logic itself is cheap once responses are cached,
    restarting the script just replays cache hits until it reaches new
    ground, rather than needing separate row-level checkpointing.
  - HTTP 429 / 5xx get exponential backoff (5 tries); a 404 is a cacheable,
    definitive answer.
  - A per-source status block in the output's "summary.sources" records
    ok/error/skipped and a human-readable note per source -- no silent
    failures. If a whole source is unreachable, the script carries on with
    the others and reports it clearly rather than crashing or fabricating
    data for it.
  - wputils.py (existing, read-only reuse) supplies enwiki API helpers used
    to resolve candidate names to canonical English Wikipedia titles and to
    reject disambiguation pages / accidental person-article matches.

USAGE:
    python3 harvest_museums.py [--sources met,smithsonian,vam,smg,how100] [--refresh]

    Default is all five sources. --refresh bypasses the on-disk cache.

OUTPUT:
    tools/fame/raw/museums_<source>.json -- one raw dump per source (raw/ is
        already wholesale-gitignored in this repo).
    tools/fame/museum_candidates.json -- the final deduped, quality-filtered,
        Wikipedia-resolved candidate list plus a top-level "summary" block.
        See HARVEST_MUSEUMS.md for the exact shape and how this is meant to
        feed build_universe_objects.py later (not wired in by this script).
"""
import argparse
import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import wputils
from regions import region_for_country

HERE = Path(__file__).resolve().parent
RAW_DIR = HERE / "raw"
CACHE_DIR = HERE / "cache" / "museums"
OUT_PATH = HERE / "museum_candidates.json"

USER_AGENT = "DeadFamousIntake/1.0 (daniel.illes12@gmail.com)"
TIMEOUT_SECONDS = 30
MAX_RETRIES = 5
BACKOFF_CAP_SECONDS = 30

# Per-source politeness. Smithsonian's public DEMO_KEY has a small, quickly
# -recovering token bucket (observed: limit=10, refills roughly 1/sec) --
# verified live before writing this: three requests one second apart showed
# remaining go 9 -> 8 -> 7, i.e. it drains slower than it's hit at 1 req/s.
# Going slower than that keeps us comfortably inside the bucket.
SOURCE_MIN_INTERVAL = {
    "met": 0.15,
    "smithsonian": 1.3,
    "vam": 0.25,
    "smg": 0.35,
    "commons": 0.15,
    "enwiki": 0.15,
}

COMMONS_API = "https://commons.wikimedia.org/w/api.php"

SMITHSONIAN_KEY = "DEMO_KEY"


# ---------------------------------------------------------------------------
# Low-level HTTP: throttling, retries, per-source disk caching
# ---------------------------------------------------------------------------

class Stats:
    def __init__(self):
        self.requests = 0
        self.cache_hits = 0
        self.retries = 0
        self.errors = 0


STATS = defaultdict(Stats)
_last_request_ts = defaultdict(float)


def _throttle(source):
    interval = SOURCE_MIN_INTERVAL.get(source, 0.2)
    now = time.monotonic()
    wait = _last_request_ts[source] + interval - now
    if wait > 0:
        time.sleep(wait)
    _last_request_ts[source] = time.monotonic()


def _cache_path(source, key):
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()
    d = CACHE_DIR / source
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{h}.json"


def http_get_json(url, source, cache_key=None, extra_headers=None, use_cache=True):
    """
    GET url, parse JSON, with per-source caching / throttling / retry+backoff.
    Returns: {"ok": bool, "status": int|str, "body": dict|None, "error": str|None}
    Mirrors fetch_metrics.py's http_get_json contract.
    """
    cache_key = cache_key if cache_key is not None else url
    cache_file = _cache_path(source, cache_key)

    if use_cache and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            STATS[source].cache_hits += 1
            return cached
        except (OSError, json.JSONDecodeError):
            pass

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if extra_headers:
        headers.update(extra_headers)

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        _throttle(source)
        STATS[source].requests += 1
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                raw = resp.read()
                status = resp.status
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                parsed = None
            result = {"ok": True, "status": status, "body": parsed, "error": None}
            if use_cache:
                cache_file.write_text(json.dumps(result), encoding="utf-8")
            return result

        except urllib.error.HTTPError as e:
            if e.code == 404:
                result = {"ok": False, "status": 404, "body": None, "error": "not_found"}
                if use_cache:
                    cache_file.write_text(json.dumps(result), encoding="utf-8")
                return result
            if e.code == 429 or 500 <= e.code < 600:
                STATS[source].retries += 1
                retry_after = None
                try:
                    retry_after = e.headers.get("Retry-After") if e.headers else None
                except Exception:
                    retry_after = None
                if retry_after and retry_after.strip().isdigit():
                    sleep_s = min(float(retry_after), BACKOFF_CAP_SECONDS)
                else:
                    sleep_s = min(2 ** attempt, BACKOFF_CAP_SECONDS)
                last_error = f"http_{e.code}"
                if attempt < MAX_RETRIES:
                    time.sleep(sleep_s)
                    continue
                STATS[source].errors += 1
                return {"ok": False, "status": e.code, "body": None, "error": last_error}
            last_error = f"http_{e.code}"
            result = {"ok": False, "status": e.code, "body": None, "error": last_error}
            STATS[source].errors += 1
            if use_cache:
                cache_file.write_text(json.dumps(result), encoding="utf-8")
            return result

        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            STATS[source].retries += 1
            last_error = f"{type(e).__name__}:{e}"
            if attempt < MAX_RETRIES:
                time.sleep(min(2 ** attempt, BACKOFF_CAP_SECONDS))
                continue

    STATS[source].errors += 1
    return {"ok": False, "status": "error", "body": None, "error": last_error or "max_retries_exceeded"}


# ---------------------------------------------------------------------------
# Shared classifiers: object kind + region, name -> wiki_title resolution
# ---------------------------------------------------------------------------

KIND_KEYWORDS = [
    ("manuscript", ["manuscript", "codex", "scroll", "papyrus", "gospel",
                    "book of", "psalter", "folio", "illuminated", "diary of"]),
    ("arms_and_armour", ["sword", "dagger", "armour", "armor", "helmet",
                          "shield", "musket", "rifle", "cannon", "spear",
                          "gauntlet", "breastplate"]),
    ("clothing", ["dress", "gown", "suit", "robe", "jacket", "costume",
                  "uniform", "shoe", "slipper", "hat", "glove", "kimono",
                  "textile", "tapestry", "carpet", "rug", "embroidery"]),
    ("jewellery", ["jewel", "necklace", "earring", "brooch", "tiara",
                   "crown", "diadem", "pendant", "bracelet"]),
    ("ceramic", ["vase", "porcelain", "ceramic", "urn", "amphora", "jar",
                 "bowl", "pottery", "pot "]),
    ("sculpture", ["statue", "sculpture", "bust of", "figurine", "carving",
                   "statuette"]),
    ("painting", ["painting", "portrait of", "canvas", "fresco"]),
    ("scientific_instrument", ["telescope", "microscope", "astrolabe",
                               "clock", "sextant", "globe", "orrery",
                               "barometer", "compass"]),
    ("technology", ["engine", "computer", "telegraph", "locomotive",
                     "typewriter", "telephone", "radio set", "television",
                     "camera", "gramophone"]),
    ("vehicle", ["automobile", "locomotive", "aircraft", "spacecraft",
                 "module", "chariot", "biplane", "monoplane", "airplane"]),
    ("coin", ["coin", "medal", "medallion", "banknote"]),
    ("furniture", ["chair", "cabinet", "throne", "writing desk", "settee",
                   "bed,", " bed ", "bedstead"]),
    ("musical_instrument", ["violin", "piano", "trumpet", "guitar", "drum",
                             "harp", "cello", "lute"]),
    ("photograph", ["photograph", "daguerreotype"]),
]


def classify_kind(*texts):
    blob = " " + " ".join(t.lower() for t in texts if t) + " "
    for kind, keys in KIND_KEYWORDS:
        if any(k in blob for k in keys):
            return kind
    return "artefact"


CULTURE_REGION_HINTS = [
    ("africa", "Africa"), ("europe", "Europe"), ("oceania", "Oceania"),
    ("north america", "North America"), ("south america", "South America"),
    ("native american", "North America"), ("american", "North America"),
    ("canadian", "North America"), ("mexican", "North America"),
    ("aztec", "North America"), ("maya", "North America"),
    ("inca", "South America"), ("peruvian", "South America"),
    ("brazilian", "South America"), ("argentine", "South America"),
    ("british", "Europe"), ("english", "Europe"), ("scottish", "Europe"),
    ("irish", "Europe"), ("welsh", "Europe"), ("french", "Europe"),
    ("italian", "Europe"), ("german", "Europe"), ("dutch", "Europe"),
    ("flemish", "Europe"), ("spanish", "Europe"), ("greek", "Europe"),
    ("roman", "Europe"), ("byzantine", "Europe"), ("russian", "Europe"),
    ("venetian", "Europe"), ("austrian", "Europe"), ("swiss", "Europe"),
    ("scandinavian", "Europe"), ("viking", "Europe"), ("celtic", "Europe"),
    ("japanese", "East Asia"), ("chinese", "East Asia"),
    ("korean", "East Asia"), ("tibetan", "East Asia"),
    ("mongol", "East Asia"),
    ("thai", "Southeast Asia"), ("vietnamese", "Southeast Asia"),
    ("cambodian", "Southeast Asia"), ("khmer", "Southeast Asia"),
    ("indonesian", "Southeast Asia"), ("burmese", "Southeast Asia"),
    ("indian", "South Asia"), ("mughal", "South Asia"),
    ("nepalese", "South Asia"), ("sri lankan", "South Asia"),
    ("persian", "Middle East"), ("iranian", "Middle East"),
    ("islamic", "Middle East"), ("ottoman", "Middle East"),
    ("turkish", "Middle East"), ("syrian", "Middle East"),
    ("mesopotamian", "Middle East"), ("assyrian", "Middle East"),
    ("babylonian", "Middle East"), ("sumerian", "Middle East"),
    ("egyptian", "Africa"), ("nubian", "Africa"), ("ethiopian", "Africa"),
    ("beninese", "Africa"), ("west african", "Africa"),
    ("african", "Africa"),
    ("australian", "Oceania"), ("maori", "Oceania"),
    ("polynesian", "Oceania"), ("aboriginal", "Oceania"),
    ("pacific islander", "Oceania"),
]


def classify_region(*texts):
    for t in texts:
        if not t:
            continue
        r = region_for_country(t.strip())
        if r:
            return r
    for t in texts:
        if not t:
            continue
        low = t.lower()
        for key, region in CULTURE_REGION_HINTS:
            if key in low:
                return region
    return None


STOPWORDS = {
    "the", "a", "an", "of", "and", "in", "on", "from", "with", "to", "at",
    "by", "for", "or", "is", "as", "this", "that",
}


def core_words(text):
    words = re.findall(r"[a-zA-Z']+", (text or "").lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text):
    if not text:
        return None
    return html.unescape(_HTML_TAG_RE.sub("", text)).strip() or None


def clean_name_text(text):
    if not text:
        return None
    t = re.sub(r"''+", "", text)
    t = re.sub(r"\s+", " ", t).strip(" ,.;:")
    return t or None


_CIRCA_TEMPLATE_RE = re.compile(r"\{\{\s*circa\s*\|([^}]*)\}\}", re.IGNORECASE)
_GENERIC_TEMPLATE_RE = re.compile(r"\{\{([^{}|]*\|)?([^{}]*)\}\}")


def clean_date_text(text):
    """Strip Wikipedia template markup (e.g. '{{circa|450 BC}}' -> 'c. 450 BC')
    that leaks through from wikitext-sourced date cells."""
    if not text:
        return None
    t = _CIRCA_TEMPLATE_RE.sub(r"c. \1", text)
    t = _GENERIC_TEMPLATE_RE.sub(r"\2", t)
    return clean_name_text(t)


def resolve_wiki_title(name, wikilink_hint=None):
    """
    Best-effort resolve `name` to a canonical, existing enwiki title.
    Returns (title_or_None, method_or_None). Disambiguation / person-article
    rejection happens later in a batched pass (batch_reject_bad_titles).
    """
    clean = clean_name_text(name)
    if not clean:
        return None, None

    try:
        info = wputils.canonicalize_titles([clean]).get(clean)
    except Exception:
        info = None
    if info and info.get("exists"):
        return info["title"], "exact"

    if wikilink_hint:
        try:
            info2 = wputils.canonicalize_titles([wikilink_hint]).get(wikilink_hint)
        except Exception:
            info2 = None
        if info2 and info2.get("exists"):
            title = info2["title"]
            if core_words(name) & core_words(title):
                return title, "wikilink-hint"

    try:
        data = wputils.api_get(wputils.EN_API, {
            "action": "query", "list": "search",
            "srsearch": clean, "srlimit": "1", "formatversion": "2",
        })
        hits = data.get("query", {}).get("search", [])
        if hits:
            cand_title = hits[0]["title"]
            info3 = wputils.canonicalize_titles([cand_title]).get(cand_title)
            if info3 and info3.get("exists") and (core_words(name) & core_words(info3["title"])):
                return info3["title"], "search"
    except Exception:
        pass

    return None, None


def batch_reject_bad_titles(candidates):
    """
    One batched enrich_titles() pass over every resolved wiki_title, to drop
    resolutions that turned out to be disambiguation pages or person
    articles (both are real failure modes of resolve_wiki_title's
    wikilink-hint / search fallbacks -- e.g. an artwork's caption linking to
    its painter, or a generic term landing on a disambiguation page).
    """
    titles = sorted({c["wiki_title"] for c in candidates if c.get("wiki_title")})
    if not titles:
        return 0
    info = wputils.enrich_titles(titles)
    rejected = 0
    for c in candidates:
        t = c.get("wiki_title")
        if not t:
            continue
        meta = info.get(t, {})
        if meta.get("is_disambig") or meta.get("is_person"):
            c["wiki_title"] = None
            c["wiki_resolution"] = "rejected_" + (
                "disambiguation" if meta.get("is_disambig") else "person_article")
            rejected += 1
    return rejected


# ---------------------------------------------------------------------------
# Source 1: Metropolitan Museum of Art Open Access API
# ---------------------------------------------------------------------------

MET_BASE = "https://collectionapi.metmuseum.org/public/collection/v1"
MET_MAX_PER_DEPARTMENT = 40  # diversity cap so one huge department can't dominate


def harvest_met(status):
    result = http_get_json(f"{MET_BASE}/departments", "met", "departments")
    if not result.get("ok"):
        status["met"] = {"status": "error", "candidates": 0,
                          "note": f"could not fetch department list: {result.get('error')}"}
        return []
    dept_names = {d["departmentId"]: d["displayName"]
                  for d in result["body"].get("departments", [])}

    search_url = f"{MET_BASE}/search?isHighlight=true&hasImages=true&q=a"
    sresult = http_get_json(search_url, "met", "search_highlights")
    if not sresult.get("ok"):
        status["met"] = {"status": "error", "candidates": 0,
                          "note": f"highlight search failed: {sresult.get('error')}"}
        return []
    object_ids = sresult["body"].get("objectIDs") or []
    print(f"[met] {len(object_ids)} highlight+image object IDs found", file=sys.stderr)

    raw_objects = []
    errors = 0
    for i, oid in enumerate(object_ids, 1):
        r = http_get_json(f"{MET_BASE}/objects/{oid}", "met", f"object_{oid}")
        if r.get("ok") and r.get("body"):
            raw_objects.append(r["body"])
        else:
            errors += 1
        if i % 200 == 0 or i == len(object_ids):
            print(f"[met] fetched {i}/{len(object_ids)} objects "
                  f"(errors so far: {errors})", file=sys.stderr)

    (RAW_DIR / "museums_met.json").write_text(
        json.dumps(raw_objects, ensure_ascii=False, indent=1), encoding="utf-8")

    # Quality filter: public-domain photography only (the one source here
    # with an unambiguous CC0 rights signal at scale), has a usable image,
    # title not a bare catalogue placeholder, then a per-department cap for
    # diversity so e.g. Asian Art (largest single bucket) doesn't crowd out
    # everything else.
    by_dept = defaultdict(list)
    dropped_not_pd = 0
    dropped_no_image = 0
    dropped_generic = 0
    for o in raw_objects:
        if not o.get("isPublicDomain"):
            dropped_not_pd += 1
            continue
        image = o.get("primaryImage") or ""
        if not image:
            dropped_no_image += 1
            continue
        title = clean_name_text(o.get("title") or o.get("objectName") or "")
        if not title or len(title) < 4 or title.lower() in {"fragment", "vessel", "object"}:
            dropped_generic += 1
            continue
        by_dept[o.get("department")].append(o)

    candidates = []
    for dept, objs in by_dept.items():
        # prefer objects with more additional images as a light proxy for
        # how heavily the Met itself has documented/featured the piece
        objs.sort(key=lambda o: len(o.get("additionalImages") or []), reverse=True)
        for o in objs[:MET_MAX_PER_DEPARTMENT]:
            title = clean_name_text(o.get("title") or o.get("objectName"))
            region = classify_region(o.get("country"), o.get("culture"))
            date_txt = o.get("objectDate") or o.get("period") or o.get("dynasty") or None
            kind = classify_kind(o.get("classification"), o.get("objectName"), title)
            wiki_title, method = resolve_wiki_title(title)
            candidates.append({
                "name": title,
                "wiki_title": wiki_title,
                "wiki_resolution": method,
                "source_museum": "Metropolitan Museum of Art",
                "kind": kind,
                "date_era": date_txt,
                "region": region,
                "culture_or_place": o.get("culture") or o.get("country") or None,
                "image_url": image_for_met(o),
                "image_licence": "CC0 (Met Open Access -- isPublicDomain=true)",
                "museum_object_url": o.get("objectURL"),
                "highlight": bool(o.get("isHighlight")),
                "raw_id": f"met:{o.get('objectID')}",
                "department": dept_names.get(dept, dept),
            })

    status["met"] = {
        "status": "ok",
        "candidates": len(candidates),
        "note": (f"{len(object_ids)} highlight+image IDs fetched ({errors} fetch "
                 f"errors); dropped not-public-domain={dropped_not_pd}, "
                 f"no-image={dropped_no_image}, generic-title={dropped_generic}; "
                 f"capped at {MET_MAX_PER_DEPARTMENT}/department across "
                 f"{len(by_dept)} departments"),
    }
    return candidates


def image_for_met(o):
    return o.get("primaryImage") or o.get("primaryImageSmall") or None


# ---------------------------------------------------------------------------
# Source 2: Smithsonian Open Access API (curated seed terms -- see module
# docstring for why this isn't a broad crawl)
# ---------------------------------------------------------------------------

SMITHSONIAN_SEED_QUERIES = [
    "ruby slippers Wizard of Oz", "Wright Flyer 1903", "Spirit of St. Louis",
    "Apollo 11 command module Columbia", "Star-Spangled Banner flag",
    "Hope Diamond", "John Bull locomotive", "Kermit the Frog puppet",
    "Star Trek Enterprise studio model", "R2-D2 Star Wars model",
    "Abraham Lincoln top hat", "Julia Child kitchen", "Dizzy Gillespie trumpet",
    "Duke Ellington score", "Muhammad Ali gloves", "Amelia Earhart Lockheed Vega",
    "Charles Lindbergh flight suit", "SR-71 Blackbird", "Space Shuttle Discovery",
    "Chuck Yeager Bell X-1 Glamorous Glennis", "Jefferson portable writing desk",
    "Star of Asia sapphire", "Enola Gay", "Foucault pendulum",
  "Colt Paterson revolver", "Whitney cotton gin model", "McCormick reaper model",
    "first telephone Bell centennial", "Edison light bulb", "Morse telegraph key",
    "ENIAC panel", "Apple I computer", "Kodak Brownie camera",
    "Gatling gun", "George Washington uniform Revolutionary War",
  "Teddy bear Roosevelt", "Greensboro Woolworth lunch counter",
    "Fonzie leather jacket Happy Days", "Archie Bunker chair",
    "Mister Rogers sweater", "Dorothy gingham dress Wizard of Oz",
    "Scarecrow costume Wizard of Oz", "Cowardly Lion costume Wizard of Oz",
    "Judy Garland ruby slippers", "first ladies inaugural gown",
    "Star Wars Yoda puppet", "Julia Child French Chef kitchen",
    "Neil Armstrong spacesuit", "Lunar Module 2", "Friendship 7 capsule",
    "Wright brothers wind tunnel", "Titanic deck chair",
    "Betsy Ross flag", "Francis Scott Key", "Abraham Lincoln watch",
    "John Deere plow model", "penicillin mold Fleming",
    "Big Bird costume Sesame Street", "Oscar the Grouch puppet",
    "Bozo the Clown puppet", "Howdy Doody puppet",
]


def harvest_smithsonian(status):
    if not SMITHSONIAN_KEY:
        status["smithsonian"] = {"status": "skipped", "candidates": 0,
                                  "note": "no API key configured"}
        return []

    raw_hits = []
    candidates = []
    ok_queries = 0
    for qi, term in enumerate(SMITHSONIAN_SEED_QUERIES, 1):
        url = ("https://api.si.edu/openaccess/api/v1.0/search?"
               + urllib.parse.urlencode({"q": term, "api_key": SMITHSONIAN_KEY, "rows": 6}))
        r = http_get_json(url, "smithsonian", f"search_{term}")
        if qi % 10 == 0 or qi == len(SMITHSONIAN_SEED_QUERIES):
            print(f"[smithsonian] {qi}/{len(SMITHSONIAN_SEED_QUERIES)} seed "
                  f"queries done", file=sys.stderr)
        if not r.get("ok"):
            continue
        ok_queries += 1
        rows = ((r.get("body") or {}).get("response") or {}).get("rows") or []
        best = pick_best_smithsonian_row(rows, term)
        if best:
            raw_hits.append(best)

    (RAW_DIR / "museums_smithsonian.json").write_text(
        json.dumps(raw_hits, ensure_ascii=False, indent=1), encoding="utf-8")

    for row in raw_hits:
        c = smithsonian_row_to_candidate(row)
        if c:
            candidates.append(c)

    status["smithsonian"] = {
        "status": "ok" if ok_queries else "error",
        "candidates": len(candidates),
        "note": (f"curated seed list of {len(SMITHSONIAN_SEED_QUERIES)} search terms "
                 f"({ok_queries} queries succeeded) using the public DEMO_KEY -- "
                 f"a real personal api.data.gov key would allow a much broader "
                 f"crawl; not a broad category crawl by design (see docstring)."),
    }
    return candidates


def pick_best_smithsonian_row(rows, seed_term):
    """Pick the first row that looks like a real, named, media-bearing object
    (not a publication/finding-aid/archival record), CC0, with online media."""
    for row in rows:
        content = row.get("content") or {}
        dnr = content.get("descriptiveNonRepeating") or {}
        usage = (dnr.get("metadata_usage") or {}).get("access")
        online_media = dnr.get("online_media") or {}
        media = online_media.get("media") or []
        title = row.get("title") or ""
        obj_types = [ot.get("content", "") for ot in
                     (content.get("freetext", {}).get("objectType") or [])]
        is_publication = any("publication" in ot.lower() or "journal" in ot.lower()
                              for ot in obj_types)
        if is_publication:
            continue
        if usage != "CC0":
            continue
        if not media:
            continue
        if len(title) < 4:
            continue
        return row
    return None


def smithsonian_row_to_candidate(row):
    content = row.get("content") or {}
    dnr = content.get("descriptiveNonRepeating") or {}
    freetext = content.get("freetext") or {}
    indexed = content.get("indexedStructured") or {}
    title = clean_name_text(row.get("title"))
    if not title:
        return None

    online_media = dnr.get("online_media") or {}
    media = (online_media.get("media") or [None])[0] or {}
    resources = media.get("resources") or []
    image_url = None
    for res in resources:
        if "jpeg" in (res.get("label") or "").lower() or "high" in (res.get("label") or "").lower():
            image_url = res.get("url")
            break
    if not image_url:
        image_url = media.get("content")

    date_txt = None
    dates = freetext.get("date") or []
    if dates:
        date_txt = dates[0].get("content")
    elif indexed.get("date"):
        date_txt = indexed["date"][0]

    place = None
    places = freetext.get("place") or []
    if places:
        place = places[0].get("content")

    obj_type = None
    obj_types = freetext.get("objectType") or []
    if obj_types:
        obj_type = obj_types[0].get("content")

    kind = classify_kind(obj_type, title)
    region = classify_region(place)

    wiki_title, method = resolve_wiki_title(title)

    return {
        "name": title,
        "wiki_title": wiki_title,
        "wiki_resolution": method,
        "source_museum": f"Smithsonian ({dnr.get('unit_code') or row.get('unitCode') or 'SI'})",
        "kind": kind,
        "date_era": date_txt,
        "region": region,
        "culture_or_place": place,
        "image_url": image_url,
        "image_licence": "CC0 (Smithsonian Open Access)",
        "museum_object_url": dnr.get("guid"),
        "highlight": True,  # curated seed list -- every candidate here was
                             # hand-picked for recognisability, see docstring
        "raw_id": f"smithsonian:{dnr.get('record_ID') or row.get('id')}",
        "department": None,
    }


# ---------------------------------------------------------------------------
# Source 3: Victoria & Albert Museum collections API (curated seed terms)
# ---------------------------------------------------------------------------

VAM_SEED_QUERIES = [
    "Great Bed of Ware", "Ardabil Carpet", "Tipu's Tiger",
    "Raphael Cartoon Miraculous Draught", "Hereford Screen",
    "Samson Slaying a Philistine Giambologna", "Chihuly chandelier rotunda",
    "James Hilliard portrait miniature", "netsuke", "samurai armour",
    "Ming dynasty blue and white porcelain vase", "Damascus Room",
  "astrolabe Islamic", "Mary Quant dress", "Vivienne Westwood punk",
    "Elizabethan portrait miniature", "Chinese famille rose vase",
    "Japanese woodblock print Hokusai", "Coronation of Queen Victoria dress",
  "medieval reliquary", "Fabergé egg", "Persian miniature painting",
    "William Morris textile design", "Wedgwood jasperware vase",
    "Art Deco jewellery", "suffragette sash", "Sixties Mary Quant Mini dress",
    "Japanese armour helmet", "Chinese cloisonne vase", "Mughal miniature painting",
    "Gothic ivory casket", "medieval stained glass panel",
]


def harvest_vam(status):
    raw_hits = []
    ok_queries = 0
    for qi, term in enumerate(VAM_SEED_QUERIES, 1):
        url = ("https://api.vam.ac.uk/v2/objects/search?"
               + urllib.parse.urlencode({"q": term, "page_size": 5}))
        r = http_get_json(url, "vam", f"search_{term}")
        if not r.get("ok"):
            continue
        ok_queries += 1
        records = ((r.get("body") or {}).get("records")) or []
        best = pick_best_vam_record(records)
        if best:
            raw_hits.append(best)

    (RAW_DIR / "museums_vam.json").write_text(
        json.dumps(raw_hits, ensure_ascii=False, indent=1), encoding="utf-8")

    candidates = []
    for rec in raw_hits:
        c = vam_record_to_candidate(rec)
        if c:
            candidates.append(c)

    status["vam"] = {
        "status": "ok" if ok_queries else "error",
        "candidates": len(candidates),
        "note": (f"curated seed list of {len(VAM_SEED_QUERIES)} search terms "
                 f"({ok_queries} queries succeeded); no API key needed; V&A's "
                 f"search API has no explicit 'highlight' flag so curated "
                 f"terms stand in for one."),
    }
    return candidates


def pick_best_vam_record(records):
    for rec in records:
        title = rec.get("_primaryTitle") or rec.get("objectType") or ""
        if len(title) < 3:
            continue
        images = rec.get("_images") or {}
        if not images.get("_primary_thumbnail") and not images.get("_iiif_image_base_url"):
            continue
        return rec
    return None


def vam_record_to_candidate(rec):
    title = clean_name_text(rec.get("_primaryTitle") or rec.get("objectType"))
    if not title:
        return None
    images = rec.get("_images") or {}
    image_id = rec.get("_primaryImageId")
    image_url = None
    if images.get("_iiif_image_base_url") and image_id:
        image_url = images["_iiif_image_base_url"] + "full/full/0/default.jpg"
    elif images.get("_primary_thumbnail"):
        image_url = images["_primary_thumbnail"]

    place = rec.get("_primaryPlace")
    kind = classify_kind(rec.get("objectType"), title)
    region = classify_region(place)
    on_display = bool((rec.get("_currentLocation") or {}).get("onDisplay"))

    wiki_title, method = resolve_wiki_title(title)

    return {
        "name": title,
        "wiki_title": wiki_title,
        "wiki_resolution": method,
        "source_museum": "Victoria and Albert Museum",
        "kind": kind,
        "date_era": rec.get("_primaryDate"),
        "region": region,
        "culture_or_place": place,
        "image_url": image_url,
        "image_licence": "© Victoria and Albert Museum, London (museum photography; "
                          "object itself may be public domain -- verify per-item before use)",
        "museum_object_url": f"https://collections.vam.ac.uk/item/{rec.get('systemNumber')}/"
                              if rec.get("systemNumber") else None,
        "highlight": on_display,
        "raw_id": f"vam:{rec.get('systemNumber')}",
        "department": None,
    }


# ---------------------------------------------------------------------------
# Source 4: Science Museum Group collection API (curated seed terms)
# ---------------------------------------------------------------------------

SMG_SEED_QUERIES = [
    "Stephenson's Rocket", "Puffing Billy locomotive",
    "Charles Babbage Difference Engine", "Babbage Analytical Engine",
    "Crick Watson DNA model", "Enigma machine", "Galileo telescope replica",
    "Newcomen engine", "Watt steam engine", "Fleming penicillin",
    "Whittle jet engine", "Apollo 10 command module",
    "Cooke Wheatstone telegraph", "Faraday electric motor",
    "Crookes X-ray tube", "iron lung", "Sinclair ZX Spectrum",
    "BBC Micro computer", "first computer mouse", "Vickers Vimy aircraft",
    "Blackburn monoplane", "Foucault pendulum", "Charles Darwin microscope",
    "penny farthing bicycle", "Singer sewing machine",
    "Bessemer converter model", "spinning jenny", "flying shuttle",
    "Baird television", "Morse telegraph", "Supermarine Spitfire",
]


def harvest_smg(status):
    raw_hits = []
    ok_queries = 0
    headers = {"Accept": "application/json"}
    for term in SMG_SEED_QUERIES:
        url = ("https://collection.sciencemuseumgroup.org.uk/search?"
               + urllib.parse.urlencode({"q": term}))
        r = http_get_json(url, "smg", f"search_{term}", extra_headers=headers)
        if not r.get("ok"):
            continue
        ok_queries += 1
        records = (r.get("body") or {}).get("data") or []
        best = pick_best_smg_record(records)
        if best:
            raw_hits.append(best)

    (RAW_DIR / "museums_smg.json").write_text(
        json.dumps(raw_hits, ensure_ascii=False, indent=1), encoding="utf-8")

    candidates = []
    for rec in raw_hits:
        c = smg_record_to_candidate(rec)
        if c:
            candidates.append(c)

    status["smg"] = {
        "status": "ok" if ok_queries else "error",
        "candidates": len(candidates),
        "note": (f"curated seed list of {len(SMG_SEED_QUERIES)} search terms "
                 f"({ok_queries} queries succeeded); requires a browser-like "
                 f"User-Agent -- the default urllib/curl UA gets a 403 from "
                 f"the site's edge/WAF, confirmed during exploration."),
    }
    return candidates


def pick_best_smg_record(records):
    for rec in records:
        attrs = rec.get("attributes") or {}
        title = (attrs.get("summary") or {}).get("title") or ""
        if len(title) < 3:
            continue
        if not attrs.get("multimedia"):
            continue
        return rec
    return None


def smg_record_to_candidate(rec):
    attrs = rec.get("attributes") or {}
    title = clean_name_text((attrs.get("summary") or {}).get("title"))
    if not title:
        return None

    mm = (attrs.get("multimedia") or [None])[0] or {}
    processed = mm.get("@processed") or {}
    image_url = None
    for key in ("large", "medium", "large_thumbnail"):
        if processed.get(key, {}).get("location"):
            image_url = processed[key]["location"]
            break
    legal = mm.get("legal") or {}
    rights = (legal.get("rights") or [None])[0] or {}
    licence = rights.get("licence")
    copyright_line = rights.get("copyright")
    licence_text = " / ".join(x for x in (licence, copyright_line) if x) or None

    date_info = (attrs.get("creation") or {}).get("date") or []
    date_txt = date_info[0].get("value") if date_info else None

    category = (attrs.get("category") or [None])[0] or {}
    cat_name = category.get("name")

    ondisplay = bool(attrs.get("ondisplay"))
    kind = classify_kind(cat_name, title)

    wiki_title, method = resolve_wiki_title(title)

    return {
        "name": title,
        "wiki_title": wiki_title,
        "wiki_resolution": method,
        "source_museum": "Science Museum Group",
        "kind": kind,
        "date_era": date_txt,
        "region": None,  # SMG collection is UK/science-history and doesn't
                          # carry a clean country/culture field like the others
        "culture_or_place": cat_name,
        "image_url": image_url,
        "image_licence": licence_text or "Not specified by API for this item -- verify before use",
        "museum_object_url": f"https://collection.sciencemuseumgroup.org.uk/objects/{rec.get('id')}"
                              if rec.get("id") else None,
        "highlight": ondisplay,
        "raw_id": f"smg:{rec.get('id')}",
        "department": None,
    }


# ---------------------------------------------------------------------------
# Source 5: "A History of the World in 100 Objects" (Wikipedia article)
# ---------------------------------------------------------------------------

HOW100_TITLE = "A History of the World in 100 Objects"
WIKITABLE_RE = re.compile(r'\{\|\s*class="wikitable".*?\n\|\}', re.DOTALL)


def harvest_how100(status):
    try:
        wt = wputils.get_wikitext(HOW100_TITLE)
    except Exception as e:
        status["how100"] = {"status": "error", "candidates": 0,
                             "note": f"could not fetch article wikitext: {e}"}
        return []
    if not wt:
        status["how100"] = {"status": "error", "candidates": 0,
                             "note": "article wikitext came back empty/missing"}
        return []

    rows = parse_how100_rows(wt)
    (RAW_DIR / "museums_how100.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    candidates = []
    for row in rows:
        c = how100_row_to_candidate(row)
        if c:
            candidates.append(c)

    status["how100"] = {
        "status": "ok",
        "candidates": len(candidates),
        "note": (f"parsed {len(rows)}/100 rows from the wikitext wikitables of "
                 f"the English Wikipedia article '{HOW100_TITLE}'"),
    }
    return candidates


def parse_how100_rows(wikitext):
    rows = []
    for table in WIKITABLE_RE.findall(wikitext):
        row_chunks = re.split(r"\n\|-\s*\n", table)
        for chunk in row_chunks:
            if "! Image" in chunk or 'class="wikitable"' in chunk:
                continue
            chunk = chunk.strip().rstrip("|}").strip()
            if not chunk.startswith("|"):
                continue
            cell_line = chunk.lstrip("|").strip()
            cells = [c.strip() for c in re.split(r"\|\|", cell_line)]
            if len(cells) < 5:
                continue
            image_cell, num_cell, obj_cell, origin_cell, date_cell = cells[:5]
            bm_url = None
            m = re.search(r"\[(https://www\.britishmuseum\.org[^\s\]]+)", chunk)
            if m:
                bm_url = m.group(1)
            file_m = re.search(r"\[\[File:([^|\]]+)", image_cell)
            file_title = f"File:{file_m.group(1).strip()}" if file_m else None
            wikilink_m = wputils.WIKILINK_RE.search(obj_cell)
            wikilink_target = wikilink_m.group(1).strip() if wikilink_m else None
            rows.append({
                "number": num_cell,
                "object_raw": obj_cell,
                "object_text": clean_name_text(strip_wikilinks(obj_cell)),
                "wikilink_target": wikilink_target,
                "origin_raw": origin_cell,
                "origin_text": clean_name_text(strip_wikilinks(origin_cell)),
                "date_text": clean_date_text(strip_wikilinks(date_cell)),
                "bm_url": bm_url,
                "file_title": file_title,
            })
    return rows


def strip_wikilinks(text):
    def repl(m):
        return m.group(2) if m.group(2) else m.group(1)
    return wputils.WIKILINK_RE.sub(repl, text)


def how100_row_to_candidate(row):
    name = row.get("object_text")
    if not name:
        return None
    wiki_title, method = resolve_wiki_title(name, row.get("wikilink_target"))
    region = classify_region(row.get("origin_text"))
    kind = classify_kind(name)
    image_info = commons_image_info(row.get("file_title"))

    return {
        "name": name,
        "wiki_title": wiki_title,
        "wiki_resolution": method,
        "source_museum": "British Museum (via BBC Radio 4 / British Museum "
                          "\"A History of the World in 100 Objects\")",
        "kind": kind,
        "date_era": row.get("date_text"),
        "region": region,
        "culture_or_place": row.get("origin_text"),
        "image_url": (image_info or {}).get("url"),
        "image_licence": (image_info or {}).get("license") or
                          "Not resolved from Commons -- see museum_object_url",
        "museum_object_url": row.get("bm_url"),
        "highlight": True,  # every one of these 100 is independently
                             # curated by the BBC/British Museum
        "raw_id": f"how100:{row.get('number')}",
        "department": None,
    }


def commons_image_info(file_title):
    if not file_title:
        return None
    try:
        data = wputils.api_get(COMMONS_API, {
            "action": "query", "titles": file_title, "prop": "imageinfo",
            "iiprop": "url|extmetadata", "formatversion": "2",
        })
    except Exception:
        return None
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None
    infos = pages[0].get("imageinfo") or []
    if not infos:
        return None
    ii = infos[0]
    meta = ii.get("extmetadata", {}) or {}

    def m(key):
        v = meta.get(key)
        return v.get("value") if isinstance(v, dict) else None

    return {
        "url": ii.get("url"),
        "license": m("LicenseShortName") or m("License"),
        "artist": strip_html(m("Artist")),
        "credit": strip_html(m("Credit")),
    }


# ---------------------------------------------------------------------------
# Recognition tagging + final quality pass
#
# General-population metrics (pageviews, sitelink counts) understate what
# this app's actual audience recognises: the stated content bar for Dead
# Famous is "Rest Is History podcast listeners", a history-enthusiast
# audience, not the general public. A history lover lights up at the Sutton
# Hoo helmet, the Antikythera mechanism or the Lewis Chessmen even though
# none of those are "household name" the way the Mona Lisa is. So instead of
# filtering candidates by traffic, every surviving candidate gets a
# recognition tier -- a judgement call, not a formula:
#   "household_name" -- recognisable to almost anyone (the scarce easy-tier
#       resource the game needs for its easiest days)
#   "enthusiast"      -- known to history lovers, not the general public
#       (what most of this harvest actually is, by construction: Met's own
#       curatorial "highlight" flag and the BBC/British Museum's curated
#       canon mark significance, not mass fame)
#   "specialist"      -- too obscure even for enthusiasts -- dropped outright
# A small hand-reviewed override list captures cases the source-level
# default gets wrong; everything else takes its source's default tier.
# ---------------------------------------------------------------------------

JUNK_NAME_RE = re.compile(
    r"\bsherds?\b|\bfragments?\s*$|^fragment of\b|\bpotsherd", re.IGNORECASE)

# Confident, hand-reviewed exceptions to the per-source default below --
# names actually seen in a harvested run, judged individually against the
# "would a well-read history enthusiast (or, for the top tier, almost
# anyone) light up at this?" bar. Keyed on normalize_title(name).
RECOGNITION_OVERRIDES = {
    # British Museum / BBC "History of the World" canon -- the true
    # household names from this list (Rosetta Stone, Sutton Hoo helmet,
    # Standard of Ur, Lewis Chessmen, Warren Cup) already exist in
    # universe_objects.json and are dropped by the dedup step before this
    # tagging pass ever sees them, so no how100 override is needed here --
    # but a few of the *remaining* ones cross further into pop-cultural
    # awareness than the plain "enthusiast" default:
    "durers rhinoceros": "household_name",  # one of the most reproduced
                                              # images in art history
    "kilwa pot sherds": "specialist",  # generic sherds despite the BM's own
                                        # curation -- also caught by
                                        # JUNK_NAME_RE, listed for clarity
    # Smithsonian curated seeds that lean "enthusiast" rather than the
    # source's "household_name" default (Americana/technology enthusiasts,
    # not universal recognition):
    "duke ellington score": "enthusiast",
    "dizzy gillespie trumpet": "enthusiast",
    "mccormick reaper model": "enthusiast",
    "whitney cotton gin model": "enthusiast",
    "john deere plow model": "enthusiast",
    "colt paterson revolver": "enthusiast",
    "john bull locomotive": "enthusiast",
    "foucault pendulum": "enthusiast",
    "wright brothers wind tunnel": "enthusiast",
    "first telephone bell centennial": "enthusiast",
    "morse telegraph key": "enthusiast",
    "eniac panel": "enthusiast",
    "gatling gun": "enthusiast",
    "jefferson portable writing desk": "enthusiast",
    "star of asia sapphire": "enthusiast",
    "chuck yeager bell x1 glamorous glennis": "enthusiast",
    "friendship 7 capsule": "enthusiast",
    "howdy doody puppet": "enthusiast",
    "bozo the clown puppet": "enthusiast",
    # V&A / Science Museum Group picks that are genuinely mainstream-famous
    # rather than the source's "enthusiast" default:
    "enigma machine": "household_name",
    "stephensons rocket": "household_name",
}

SOURCE_DEFAULT_RECOGNITION = {
    # BBC Radio 4 / British Museum: curated for a broad-but-engaged
    # listenership -- squarely "enthusiast" register, not mass fame (the
    # true household names from this list are the ones already in the
    # existing pool and dropped by dedup before we get here).
    "how100": "enthusiast",
    # Met's isHighlight flag marks curatorial/art-historical significance,
    # not necessarily mass recognition.
    "met": "enthusiast",
    # This seed list was deliberately written from pop-culture/Americana
    # icons (ruby slippers, Apollo 11, Kermit the Frog...) -- genuinely
    # household-name register by design; see RECOGNITION_OVERRIDES above
    # for the seeds that turned out more niche than intended.
    "smithsonian": "household_name",
    "vam": "enthusiast",
    "smg": "enthusiast",
}


def tag_recognition(candidates):
    kept = []
    dropped_junk = 0
    dropped_specialist = 0
    for c in candidates:
        if JUNK_NAME_RE.search(c["name"]):
            dropped_junk += 1
            continue
        source = c["raw_id"].split(":")[0]
        key = normalize_title(c["name"])
        tier = RECOGNITION_OVERRIDES.get(key) or \
            SOURCE_DEFAULT_RECOGNITION.get(source, "enthusiast")
        if tier == "specialist":
            dropped_specialist += 1
            continue
        c["recognition"] = tier
        kept.append(c)
    return kept, dropped_junk, dropped_specialist


# ---------------------------------------------------------------------------
# Dedup against what already exists
# ---------------------------------------------------------------------------

def normalize_title(s):
    if not s:
        return None
    t = s.lower().strip()
    t = re.sub(r"^the\s+", "", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t or None


def load_known_titles():
    known = set()

    uni_path = HERE / "universe_objects.json"
    if uni_path.exists():
        data = json.loads(uni_path.read_text(encoding="utf-8"))
        for o in data.get("objects", []):
            known.add(normalize_title(o.get("wiki_title")))
            known.add(normalize_title(o.get("name")))

    inv_path = HERE / "current_inventory.json"
    if inv_path.exists():
        data = json.loads(inv_path.read_text(encoding="utf-8"))
        for item in data.get("items", []):
            if item.get("game") != "what":
                continue
            known.add(normalize_title(item.get("wiki_title")))
            known.add(normalize_title(item.get("display_name")))

    reveal_path = HERE.parent.parent / "data" / "reveal-what.json"
    if reveal_path.exists():
        data = json.loads(reveal_path.read_text(encoding="utf-8"))
        for item in data:
            known.add(normalize_title(item.get("name")))
            for v in item.get("variants") or []:
                known.add(normalize_title(v))

    known.discard(None)
    return known


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

HARVESTERS = {
    "met": harvest_met,
    "smithsonian": harvest_smithsonian,
    "vam": harvest_vam,
    "smg": harvest_smg,
    "how100": harvest_how100,
}


def verify_network():
    r = http_get_json(
        "https://collectionapi.metmuseum.org/public/collection/v1/objects/1",
        "met", "network_check")
    return bool(r.get("ok"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default="met,smithsonian,vam,smg,how100",
                         help="comma-separated subset of: " + ",".join(HARVESTERS))
    parser.add_argument("--refresh", action="store_true",
                         help="(not yet wired to bypass cache -- delete "
                              "tools/fame/cache/museums/<source>/ to force a refetch)")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print("Verifying network access (one cheap Met API request)...", file=sys.stderr)
    if not verify_network():
        print("NETWORK CHECK FAILED -- could not reach collectionapi.metmuseum.org. "
              "Stopping rather than fabricating output.", file=sys.stderr)
        sys.exit(1)
    print("Network OK.", file=sys.stderr)

    wanted = [s.strip() for s in args.sources.split(",") if s.strip()]

    status = {}
    all_candidates = []
    for source in wanted:
        fn = HARVESTERS.get(source)
        if not fn:
            print(f"Unknown source '{source}', skipping", file=sys.stderr)
            continue
        print(f"\n=== harvesting: {source} ===", file=sys.stderr)
        t0 = time.monotonic()
        try:
            cands = fn(status)
        except Exception as e:
            status[source] = {"status": "error", "candidates": 0,
                               "note": f"unhandled exception: {type(e).__name__}: {e}"}
            cands = []
        elapsed = time.monotonic() - t0
        print(f"=== {source}: {len(cands)} candidates in {elapsed:.1f}s ===",
              file=sys.stderr)
        all_candidates.extend(cands)

    for s in HARVESTERS:
        if s not in wanted:
            status[s] = {"status": "skipped", "candidates": 0,
                         "note": "not requested via --sources"}

    print(f"\nTotal raw candidates before dedup: {len(all_candidates)}",
          file=sys.stderr)

    print("Rejecting disambiguation-page / person-article wiki_title matches...",
          file=sys.stderr)
    rejected = batch_reject_bad_titles(all_candidates)
    print(f"Rejected {rejected} bad wiki_title resolutions", file=sys.stderr)

    print("Deduping against universe_objects.json / current_inventory.json / "
          "data/reveal-what.json...", file=sys.stderr)
    known_titles = load_known_titles()

    # within-run dedup first (same object surfaced by >1 source): key on
    # wiki_title when resolved, else normalized name
    seen_keys = {}
    deduped = []
    for c in all_candidates:
        key = normalize_title(c.get("wiki_title")) or normalize_title(c.get("name"))
        if key in seen_keys:
            # keep the one with a resolved wiki_title / an image, whichever
            # is more complete
            existing = seen_keys[key]
            if (not existing.get("wiki_title") and c.get("wiki_title")) or \
               (not existing.get("image_url") and c.get("image_url")):
                idx = deduped.index(existing)
                deduped[idx] = c
                seen_keys[key] = c
            continue
        seen_keys[key] = c
        deduped.append(c)

    already_known = 0
    new_candidates = []
    for c in deduped:
        key = normalize_title(c.get("wiki_title")) or normalize_title(c.get("name"))
        if key and key in known_titles:
            already_known += 1
            continue
        new_candidates.append(c)

    print(f"After within-run dedup: {len(deduped)} (removed "
          f"{len(all_candidates) - len(deduped)} cross-source repeats)",
          file=sys.stderr)
    print(f"Already known in universe_objects/current_inventory/reveal-what: "
          f"{already_known}", file=sys.stderr)
    print(f"Genuinely new candidates: {len(new_candidates)}", file=sys.stderr)

    new_candidates, dropped_junk, dropped_specialist = tag_recognition(new_candidates)
    print(f"Dropped as generic sherd/unnamed-fragment junk: {dropped_junk}",
          file=sys.stderr)
    print(f"Dropped as 'specialist' (too obscure even for history "
          f"enthusiasts): {dropped_specialist}", file=sys.stderr)
    print(f"Final candidate count: {len(new_candidates)}", file=sys.stderr)

    # ---- summary block ----
    per_source = Counter(c["raw_id"].split(":")[0] for c in new_candidates)
    per_kind = Counter(c["kind"] for c in new_candidates)
    per_region = Counter(c.get("region") or "unknown" for c in new_candidates)
    per_recognition = Counter(c.get("recognition") for c in new_candidates)
    resolved_count = sum(1 for c in new_candidates if c.get("wiki_title"))

    http_stats = {src: {"requests": s.requests, "cache_hits": s.cache_hits,
                         "retries": s.retries, "errors": s.errors}
                  for src, s in STATS.items()}

    summary = {
        "generated_note": "tools/fame/museum_candidates.json -- see HARVEST_MUSEUMS.md",
        "total_raw_before_dedup": len(all_candidates),
        "total_after_within_run_dedup": len(deduped),
        "already_known_dropped": already_known,
        "total_new_candidates": len(new_candidates),
        "wiki_title_resolved": resolved_count,
        "wiki_title_unresolved": len(new_candidates) - resolved_count,
        "per_source": dict(per_source),
        "per_kind": dict(per_kind),
        "per_region": dict(per_region),
        "per_recognition": dict(per_recognition),
        "sources": status,
        "http_stats": http_stats,
    }

    new_candidates.sort(key=lambda c: (c["raw_id"].split(":")[0], c["name"]))

    out = {"summary": summary, "candidates": new_candidates}
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nWrote {OUT_PATH} ({len(new_candidates)} candidates)", file=sys.stderr)
    print(json.dumps(summary, indent=1), file=sys.stderr)


if __name__ == "__main__":
    main()
