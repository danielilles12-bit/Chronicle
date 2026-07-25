#!/usr/bin/env python3
"""
harvest_people_v2.py -- harvest candidate historical PEOPLE from source
families the current fame pipeline (universe_people.json, built from the
MIT Pantheon Historical Popularity Index + Wikipedia list harvests) cannot
reach.

WHY THIS EXISTS
    Pantheon ranks people by cross-language Wikipedia presence, which
    systematically rewards "great man" historiography: rulers, commanders,
    statesmen, senior clerics, philosophers. A content review of the shipped
    Dead Famous launch month found it was only ~15% women and overwhelmingly
    elite/male/political, with non-European history represented mostly
    through rulers, conquerors and ruins. This script targets the specific
    pockets that fix that, using sources Pantheon structurally under-weighs:
    women found via OCCUPATION (not "notable women" lists), science/medicine
    beyond the canonical handful, sport & pop-culture halls of fame (which
    skew towards English-speaking recognition and are weak in other-language
    wikis, so a cross-language-presence metric underrates them), labour and
    social-reform figures, and Indigenous/Oceanian/non-European figures
    known for culture, science or exploration rather than conquest.

    It also DELIBERATELY re-surfaces obvious household names when a query
    happens to catch them: a separate audit found the shipped pool has
    almost no unused EASY, highly-recognisable people left, which is the
    binding constraint on the whole calendar. This script is not tuned to
    avoid famous people -- it is tuned to reach underrepresented POCKETS,
    and famous people found there are flagged, not discarded.

SOURCES (see build_query()/POCKETS below for exact QIDs)
    A. Wikidata SPARQL: women crossed with occupation classes (physician,
       scientist, engineer, aircraft pilot, writer, composer, athlete,
       activist, printer, midwife, astronomer, mathematician, photographer,
       archaeologist, epidemiologist, surgeon) -- i.e. women found through
       what they did, not through being women.
    B. Wikidata SPARQL: Nobel laureates (all 6 categories) + Fields Medal +
       Turing Award + Lasker-DeBakey Award (P166 award received); Fellows of
       the Royal Society (P2070, a direct identifier property); a broader
       (non-gender-restricted) epidemiologist/surgeon occupation cross.
    C. Wikidata SPARQL: sport/pop-culture halls of fame via direct
       identifier properties (Baseball, Pro Football, Basketball, Tennis,
       Golf, Rock & Roll HOFs), Olympic gold medallists (P166 award =
       Q15243387), Academy Award winners (P166 award, class Q19020).
    D. Wikidata SPARQL: trade unionists, abolitionists, suffragists, social
       reformers (P106 occupation, no gender filter -- this pocket is about
       class/labour representation, not gender).
    E. Indigenous/Oceanian/non-European culture & science:
       - Australian Dictionary of Biography (P1907, direct ID property)
       - Dictionary of New Zealand Biography / Te Ara (P2745)
       - Dictionary of Irish Biography (P6829)
       - Indigenous ethnic groups via P172 (Maori, Indigenous Australians,
         Native Hawaiians, Inuit, Native Americans in the US, First Nations
         in Canada)
       - Pacific Island nations via P27 citizenship (Fiji, PNG, Samoa,
         Tonga, Vanuatu, Solomon Islands, Kiribati, Marshall Islands,
         Micronesia, Palau, Kingdom of Hawaii, Cook Islands, French
         Polynesia, Niue)
       - Dictionary of African Biography has NO Wikidata identifier
         property (checked: wbsearchentities finds nothing). Per spec,
         falls back to Wikipedia CATEGORY TRAVERSAL (enwiki API) instead:
         a bounded BFS from continent-level occupation categories, through
         their "by nationality" subcategories, collecting page members,
         then enriching each title into a full person record via batched
         Wikidata lookups. This is also written as a general-purpose
         fallback usable for any future pocket with no structured source.

DESIGN NOTES (matches tools/fame/fetch_metrics.py's conventions)
    - Python 3.9 stdlib only.
    - Every HTTP request carries a fixed, descriptive User-Agent.
    - A global throttle caps request rate; SPARQL aggregate queries are
      slow server-side (10-25s each is normal), so the SPARQL throttle is
      gentler than the enwiki one.
    - Every raw HTTP response is cached on disk under tools/fame/cache/
      (SPARQL queries keyed by a hash of the full query text; this re-uses
      the *mechanism* wputils.py already has for enwiki calls, which caches
      under tools/fame/raw/ as that module was written to do -- read-only
      reuse, not modified here). A killed-and-restarted run never re-issues
      a query it already has an answer for.
    - Each pocket's raw harvest is also saved as its own resumable JSON file
      under tools/fame/raw/people_v2_<pocket>.json; if that file already
      exists, the pocket is skipped entirely on a re-run unless --force is
      given.
    - SPARQL query ordering matters a lot for WDQS performance: a query
      that joins a broad class (e.g. "citizenship of a country") after a
      cheap, selective VALUES/direct-property binding runs in ~2-20s;
      the same join attempted in the other order timed out (>40s) in
      testing. Every multi-value pocket here binds ?person via a VALUES
      clause or a direct identifier property FIRST.
    - A missing/slow source never crashes the run; the pocket's error is
      recorded and the run continues.

OUTPUT
    tools/fame/raw/people_v2_<pocket>.json  -- one file per pocket, the raw
        harvested rows for that pocket (kept for provenance/debugging).
    tools/fame/people_candidates.json -- the deduplicated, enriched,
        cross-checked-against-existing-content final candidate list.

USAGE
    python3 tools/fame/harvest_people_v2.py                  # full run
    python3 tools/fame/harvest_people_v2.py --verify-only     # network check only
    python3 tools/fame/harvest_people_v2.py --pocket women_physician
    python3 tools/fame/harvest_people_v2.py --force            # ignore existing raw/*.json

See tools/fame/HARVEST_PEOPLE_V2.md for the full write-up.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import wputils
from regions import region_for_country

HERE = Path(__file__).resolve().parent
CACHE_DIR = HERE / "cache"
RAW_DIR = HERE / "raw"
OUTPUT_PATH = HERE / "people_candidates.json"

USER_AGENT = "DeadFamousIntake/1.0 (daniel.illes12@gmail.com)"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

# WDQS aggregate queries are heavy server-side (10-25s typical); throttle
# gently client-side and lean on a long per-request timeout + disk cache
# for resumability rather than a tight retry loop.
SPARQL_MIN_INTERVAL = 2.0
SPARQL_TIMEOUT = 90
SPARQL_MAX_RETRIES = 4

_last_sparql_ts = [0.0]

RAW_DIR.mkdir(parents=True, exist_ok=True)
(CACHE_DIR / "people_v2_sparql").mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Network verification (run first, unconditionally)
# ---------------------------------------------------------------------------

def verify_network():
    """One cheap request to each endpoint this script depends on. Returns
    (sparql_ok, enwiki_ok, details_dict)."""
    details = {}

    sparql_ok = False
    try:
        q = (
            'SELECT ?p WHERE { ?p wdt:P31 wd:Q5 ; wdt:P106 wd:Q901 . } LIMIT 1'
        )
        url = SPARQL_ENDPOINT + "?" + urllib.parse.urlencode(
            {"query": q, "format": "json"})
        req = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT,
                          "Accept": "application/sparql-results+json"})
        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            status = resp.status
        elapsed = time.monotonic() - t0
        n = len(body.get("results", {}).get("bindings", []))
        sparql_ok = (status == 200 and n >= 1)
        details["sparql"] = f"HTTP {status}, {n} row(s), {elapsed:.1f}s"
    except Exception as e:
        details["sparql"] = f"FAILED: {type(e).__name__}: {e}"

    enwiki_ok = False
    try:
        t0 = time.monotonic()
        data = wputils.api_get(wputils.EN_API, {
            "action": "query", "titles": "Marie Curie", "prop": "pageprops",
        }, use_cache=False)
        elapsed = time.monotonic() - t0
        pages = data.get("query", {}).get("pages", {})
        enwiki_ok = len(pages) >= 1
        details["enwiki"] = f"{len(pages)} page(s), {elapsed:.1f}s"
    except Exception as e:
        details["enwiki"] = f"FAILED: {type(e).__name__}: {e}"

    return sparql_ok, enwiki_ok, details


# ---------------------------------------------------------------------------
# SPARQL HTTP layer: caching, throttling, retry+backoff (mirrors
# fetch_metrics.py's http_get_json shape, adapted for the SPARQL endpoint)
# ---------------------------------------------------------------------------

def _sparql_cache_path(query):
    h = hashlib.sha1(query.encode("utf-8")).hexdigest()
    return CACHE_DIR / "people_v2_sparql" / f"{h}.json"


def _throttle_sparql():
    now = time.monotonic()
    wait = _last_sparql_ts[0] + SPARQL_MIN_INTERVAL - now
    if wait > 0:
        time.sleep(wait)
    _last_sparql_ts[0] = time.monotonic()


def sparql_query(query):
    """
    Run a SPARQL query against WDQS with disk caching (keyed by the exact
    query text -- LIMIT/OFFSET included, so each page caches separately),
    throttling, and retry+backoff on 429/5xx/timeouts.

    Returns: {"ok": bool, "bindings": list, "error": str|None}
    """
    cache_file = _sparql_cache_path(query)
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            return cached
        except (OSError, json.JSONDecodeError):
            pass

    url = SPARQL_ENDPOINT + "?" + urllib.parse.urlencode(
        {"query": query, "format": "json"})
    last_error = None
    for attempt in range(1, SPARQL_MAX_RETRIES + 1):
        _throttle_sparql()
        req = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT,
                          "Accept": "application/sparql-results+json"})
        try:
            with urllib.request.urlopen(req, timeout=SPARQL_TIMEOUT) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            bindings = body.get("results", {}).get("bindings", [])
            result = {"ok": True, "bindings": bindings, "error": None}
            cache_file.write_text(json.dumps(result), encoding="utf-8")
            return result
        except urllib.error.HTTPError as e:
            last_error = f"http_{e.code}"
            if e.code == 429 or 500 <= e.code < 600:
                sleep_s = min(5 * attempt, 30)
                if attempt < SPARQL_MAX_RETRIES:
                    time.sleep(sleep_s)
                    continue
            result = {"ok": False, "bindings": [], "error": last_error}
            return result
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last_error = f"{type(e).__name__}:{e}"
            if attempt < SPARQL_MAX_RETRIES:
                time.sleep(min(5 * attempt, 30))
                continue
    return {"ok": False, "bindings": [], "error": last_error or "max_retries_exceeded"}


# ---------------------------------------------------------------------------
# The master per-person SELECT template.
#
# Uses GROUP BY ?person with SAMPLE()/GROUP_CONCAT() aggregates rather than
# the wikibase:label SERVICE, because the SERVICE does not compose cleanly
# with GROUP BY across several OPTIONAL joins -- direct rdfs:label with a
# language filter is the standard WDQS pattern for aggregate queries and was
# verified (see HARVEST_PEOPLE_V2.md) to return one clean row per person.
# ---------------------------------------------------------------------------

MASTER_TEMPLATE = """
SELECT ?person (SAMPLE(?personLabel) AS ?name) (SAMPLE(?article) AS ?enwikiArticle)
       (SAMPLE(?genderLabel) AS ?gender) (MAX(?sitelinks) AS ?sitelinkcount)
       (SAMPLE(?dob) AS ?dob) (SAMPLE(?dod) AS ?dod)
       (SAMPLE(?birthplaceLabel) AS ?birthplace) (SAMPLE(?bcoord) AS ?bcoord)
       (SAMPLE(?deathplaceLabel) AS ?deathplace) (SAMPLE(?dcoord) AS ?dcoord)
       (GROUP_CONCAT(DISTINCT ?occLabel; separator="|") AS ?occupations)
       (GROUP_CONCAT(DISTINCT ?citizenshipLabel; separator="|") AS ?citizenships)
WHERE {{
{where_clause}
  ?person wdt:P31 wd:Q5 .
  ?article schema:about ?person ; schema:isPartOf <https://en.wikipedia.org/> .
  ?person wikibase:sitelinks ?sitelinks .
  FILTER(?sitelinks >= {min_sitelinks})
  ?person rdfs:label ?personLabel . FILTER(LANG(?personLabel) = "en")
  OPTIONAL {{ ?person wdt:P21 ?gender0 . ?gender0 rdfs:label ?genderLabel .
             FILTER(LANG(?genderLabel) = "en") }}
  OPTIONAL {{ ?person wdt:P569 ?dob }}
  OPTIONAL {{ ?person wdt:P570 ?dod }}
  OPTIONAL {{ ?person wdt:P19 ?birthplace0 . ?birthplace0 rdfs:label ?birthplaceLabel .
             FILTER(LANG(?birthplaceLabel) = "en")
             OPTIONAL {{ ?birthplace0 wdt:P625 ?bcoord }} }}
  OPTIONAL {{ ?person wdt:P20 ?deathplace0 . ?deathplace0 rdfs:label ?deathplaceLabel .
             FILTER(LANG(?deathplaceLabel) = "en")
             OPTIONAL {{ ?deathplace0 wdt:P625 ?dcoord }} }}
  OPTIONAL {{ ?person wdt:P106 ?occ . ?occ rdfs:label ?occLabel .
             FILTER(LANG(?occLabel) = "en") }}
  OPTIONAL {{ ?person wdt:P27 ?citizenship0 . ?citizenship0 rdfs:label ?citizenshipLabel .
             FILTER(LANG(?citizenshipLabel) = "en") }}
}}
GROUP BY ?person
ORDER BY DESC(BOUND(?dod)) DESC(MAX(?sitelinks))
LIMIT {limit}
OFFSET {offset}
"""
# Ordering note: DESC(BOUND(?dod)) first means people WITH a recorded death
# date are ranked ahead of living people at the same LIMIT cutoff. Living
# people are still captured (is_living=True, never silently dropped) but
# don't crowd dead historical figures out of a small LIMIT page -- this
# mattered a lot in practice: "Fellow of the Royal Society" ordered by raw
# sitelinks alone surfaces living royals/celebrities (Elon Musk, Charles
# III, Tim Berners-Lee) ahead of the actual historical scientists.


def build_query(where_clause, min_sitelinks, limit, offset):
    return MASTER_TEMPLATE.format(
        where_clause=where_clause, min_sitelinks=min_sitelinks,
        limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

POINT_RE = re.compile(r"Point\(([\-0-9.]+)\s+([\-0-9.]+)\)")
YEAR_RE = re.compile(r"^([+-]?\d+)-\d{2}-\d{2}T")


def parse_point(wkt):
    if not wkt:
        return None, None
    m = POINT_RE.match(wkt)
    if not m:
        return None, None
    lon, lat = float(m.group(1)), float(m.group(2))
    return lat, lon


def parse_year(iso):
    if not iso:
        return None
    m = YEAR_RE.match(iso)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def qid_from_uri(uri):
    if not uri:
        return None
    return uri.rsplit("/", 1)[-1]


def title_from_article_url(url):
    if not url:
        return None
    tail = url.rsplit("/", 1)[-1]
    return urllib.parse.unquote(tail).replace("_", " ")


def recognisability_hint(sitelinks):
    if sitelinks is None:
        return "unknown"
    if sitelinks >= 60:
        return "easy"
    if sitelinks >= 15:
        return "medium"
    return "niche"


def row_to_candidate(b, pocket_tag):
    """Convert one SPARQL result row (already GROUP BY ?person, so one row
    per person) into a normalized candidate dict."""
    qid = qid_from_uri(b.get("person", {}).get("value"))
    name = b.get("name", {}).get("value")
    wiki_title = title_from_article_url(b.get("enwikiArticle", {}).get("value"))
    gender = b.get("gender", {}).get("value")
    sitelinks = b.get("sitelinkcount", {}).get("value")
    sitelinks = int(float(sitelinks)) if sitelinks is not None else None
    dob = b.get("dob", {}).get("value")
    dod = b.get("dod", {}).get("value")
    birth_place = b.get("birthplace", {}).get("value")
    bcoord = b.get("bcoord", {}).get("value")
    death_place = b.get("deathplace", {}).get("value")
    dcoord = b.get("dcoord", {}).get("value")
    occupations_raw = b.get("occupations", {}).get("value") or ""
    citizenships_raw = b.get("citizenships", {}).get("value") or ""
    occupations = sorted(set(x for x in occupations_raw.split("|") if x))
    citizenships = sorted(set(x for x in citizenships_raw.split("|") if x))

    birth_lat, birth_lon = parse_point(bcoord)
    death_lat, death_lon = parse_point(dcoord)

    region = None
    for c in citizenships:
        region = region_for_country(c)
        if region:
            break

    has_dod = bool(dod)
    return {
        "qid": qid,
        "name": name,
        "wiki_title": wiki_title,
        "gender": gender,
        "occupations": occupations,
        "birth_year": parse_year(dob),
        "death_year": parse_year(dod),
        "has_death_date": has_dod,
        "is_living": not has_dod,
        "birth_place": birth_place,
        "birth_lat": birth_lat,
        "birth_lon": birth_lon,
        "death_place": death_place,
        "death_lat": death_lat,
        "death_lon": death_lon,
        "citizenships": citizenships,
        "region": region,
        "sitelinks": sitelinks,
        "recognisability_hint": recognisability_hint(sitelinks),
        "has_image": None,  # filled in later, only for surviving candidates
        "pockets": [pocket_tag],
        "sources": ["wikidata_sparql"],
    }


# ---------------------------------------------------------------------------
# Pocket runner (SPARQL-based pockets)
# ---------------------------------------------------------------------------

def run_sparql_pocket(pocket_id, where_clause, min_sitelinks, limit, max_pages=1):
    """Run one SPARQL-based pocket, paging while a page is full and under
    max_pages. Returns (candidates_list, error_or_None)."""
    candidates = []
    for page in range(max_pages):
        offset = page * limit
        query = build_query(where_clause, min_sitelinks, limit, offset)
        result = sparql_query(query)
        if not result["ok"]:
            return candidates, result["error"]
        rows = result["bindings"]
        for b in rows:
            candidates.append(row_to_candidate(b, pocket_id))
        print(f"    page {page}: {len(rows)} rows (offset {offset})", file=sys.stderr)
        if len(rows) < limit:
            break
    return candidates, None


# ---------------------------------------------------------------------------
# Pocket definitions
# ---------------------------------------------------------------------------
# Occupation QIDs verified live via wbsearchentities (type=item) on
# 2026-07-25 -- each resolved to the expected canonical occupation class as
# the #1 hit; see HARVEST_PEOPLE_V2.md for the verification transcript.
WOMEN_OCCUPATIONS = {
    "physician": "Q39631",
    "surgeon": "Q774306",
    "scientist": "Q901",
    "engineer": "Q81096",
    "aircraft_pilot": "Q2095549",
    "writer": "Q36180",
    "composer": "Q36834",
    "athlete": "Q2066131",
    "activist": "Q15253558",
    "printer": "Q175151",
    "midwife": "Q185196",
    "astronomer": "Q11063",
    "mathematician": "Q170790",
    "photographer": "Q33231",
    "archaeologist": "Q3621491",
    "epidemiologist": "Q12765408",
}
FEMALE_QID = "Q6581072"

SCIENCE_AWARD_QIDS = [
    "Q38104",   # Nobel Prize in Physics
    "Q44585",   # Nobel Prize in Chemistry
    "Q80061",   # Nobel Prize in Physiology or Medicine
    "Q37922",   # Nobel Prize in Literature
    "Q35637",   # Nobel Peace Prize
    "Q47170",   # Prize in Economic Sciences in Memory of Alfred Nobel
    "Q28835",   # Fields Medal
    "Q185667",  # Turing Award
    "Q136696",  # Lasker-DeBakey Clinical Medical Research Award
]

HOF_PROPERTIES = ["P4164", "P6930", "P3646", "P3363", "P4461", "P3162"]
# National Baseball HOF, Pro Football HOF, Naismith Basketball HOF,
# Tennis HOF, World Golf HOF, Rock and Roll HOF -- direct ID properties.

OLYMPIC_GOLD_QID = "Q15243387"
ACADEMY_AWARDS_CLASS_QID = "Q19020"

LABOUR_REFORM_OCCUPATIONS = {
    "trade_unionist": "Q15627169",
    "abolitionist": "Q12526417",
    "suffragist": "Q27532437",
    "social_reformer": "Q16611574",
}

INDIGENOUS_ETHNIC_GROUPS = {
    "maori": "Q6122670",
    "indigenous_australian": "Q170355",
    "native_hawaiian": "Q1283606",
    "inuit": "Q189975",
    "native_american_us": "Q49297",
    "first_nations_canada": "Q392316",
}

OCEANIA_COUNTRY_QIDS = [
    "Q712",     # Fiji
    "Q691",     # Papua New Guinea
    "Q683",     # Samoa
    "Q678",     # Tonga
    "Q686",     # Vanuatu
    "Q685",     # Solomon Islands
    "Q710",     # Kiribati
    "Q709",     # Marshall Islands
    "Q702",     # Federated States of Micronesia
    "Q695",     # Palau
    "Q156418",  # Kingdom of Hawaii (historical)
    "Q26988",   # Cook Islands
    "Q30971",   # French Polynesia
    "Q34020",   # Niue
]


def values_clause(var, qids):
    return "VALUES " + var + " { " + " ".join(f"wd:{q}" for q in qids) + " }"


def get_pockets():
    """Returns an ordered list of (pocket_id, where_clause, min_sitelinks,
    limit, max_pages, description)."""
    pockets = []

    # A. Women by occupation (not "famous women" lists).
    for occ_name, occ_qid in WOMEN_OCCUPATIONS.items():
        pocket_id = f"women_{occ_name}"
        where = (
            f"  ?person wdt:P106 wd:{occ_qid} .\n"
            f"  ?person wdt:P21 wd:{FEMALE_QID} .\n"
        )
        pockets.append((pocket_id, where, 4, 80, 1,
                         f"Women (P21={FEMALE_QID}) with occupation {occ_name} ({occ_qid})"))

    # B. Science / medicine / public health beyond the canonical handful.
    where = values_clause("?award", SCIENCE_AWARD_QIDS) + "\n  ?person wdt:P166 ?award .\n"
    pockets.append(("science_major_awards", where, 3, 150, 1,
                     "Nobel (all 6 categories) + Fields + Turing + Lasker laureates"))

    where = "  ?person wdt:P2070 ?frsid .\n"
    pockets.append(("royal_society_fellows", where, 8, 100, 1,
                     "Fellows of the Royal Society (P2070 direct ID property)"))

    where = values_clause("?occ", ["Q12765408", "Q774306"]) + "\n  ?person wdt:P106 ?occ .\n"
    pockets.append(("epidemiologists_surgeons_broad", where, 10, 60, 1,
                     "Epidemiologists/surgeons by occupation, no gender filter"))

    # C. Sport & popular culture.
    hof_union = " UNION ".join(
        f"{{ ?person wdt:{p} ?hofid{i} }}" for i, p in enumerate(HOF_PROPERTIES))
    where = "  " + hof_union + " .\n"
    pockets.append(("sport_halls_of_fame", where, 6, 150, 1,
                     "Baseball/Football/Basketball/Tennis/Golf/Rock&Roll Hall of Fame IDs"))

    where = f"  ?person wdt:P166 wd:{OLYMPIC_GOLD_QID} .\n"
    pockets.append(("olympic_gold_medallists", where, 8, 120, 1,
                     "Olympic gold medal (P166 award received = Q15243387)"))

    where = (f"  ?person wdt:P166 ?award .\n"
             f"  ?award wdt:P31/wdt:P279* wd:{ACADEMY_AWARDS_CLASS_QID} .\n")
    pockets.append(("academy_award_winners", where, 9, 120, 1,
                     "Academy Award winners (award class Q19020)"))

    # D. Labour, work, social reform (no gender filter -- this pocket is
    # about class representation).
    where = values_clause("?occ", list(LABOUR_REFORM_OCCUPATIONS.values())) + \
        "\n  ?person wdt:P106 ?occ .\n"
    pockets.append(("labour_social_reform", where, 5, 150, 1,
                     "Trade unionists / abolitionists / suffragists / social reformers"))

    # E. Indigenous / Oceanian / non-European culture & science.
    where = "  ?person wdt:P1907 ?adbid .\n"
    pockets.append(("australian_dictionary_of_biography", where, 3, 150, 1,
                     "Australian Dictionary of Biography ID (P1907)"))

    where = "  ?person wdt:P2745 ?teid .\n"
    pockets.append(("te_ara_nz_biography", where, 3, 120, 1,
                     "Dictionary of New Zealand Biography / Te Ara ID (P2745)"))

    where = "  ?person wdt:P6829 ?dibid .\n"
    pockets.append(("dictionary_irish_biography", where, 3, 120, 1,
                     "Dictionary of Irish Biography ID (P6829)"))

    where = values_clause("?eth", list(INDIGENOUS_ETHNIC_GROUPS.values())) + \
        "\n  ?person wdt:P172 ?eth .\n"
    pockets.append(("indigenous_ethnic_groups", where, 3, 150, 2,
                     "Maori / Indigenous Australian / Native Hawaiian / Inuit / "
                     "Native American (US) / First Nations (Canada) via P172"))

    where = values_clause("?country", OCEANIA_COUNTRY_QIDS) + \
        "\n  ?person wdt:P27 ?country .\n"
    pockets.append(("oceania_pacific_islands", where, 3, 120, 1,
                     "Pacific Island nation citizenship (P27), beyond AU/NZ"))

    return pockets


# ---------------------------------------------------------------------------
# Pocket E6: Dictionary of African Biography has no Wikidata ID property
# (verified: wbsearchentities type=property found nothing for "Dictionary
# of African Biography"). Fallback per spec: Wikipedia category traversal.
# ---------------------------------------------------------------------------

AFRICAN_SEED_CATEGORIES = [
    "Category:African writers",
    "Category:African physicians",
    "Category:African activists",
    "Category:African educators",
    "Category:African explorers",
    "Category:African archaeologists",
    "Category:African women scientists",
    "Category:African composers",
    "Category:African musicians",
]

CATEGORY_SKIP_SUBSTRINGS = [
    "stub", "template", "wikipedia", "list of", "lists of", "user ",
    "portal", "redirect", "establishment", "disestablishment", "works by",
    "novels by", "songs by", "films", "albums", "discography", "awards",
    "fiction", "mailing list", "islands", "rivers", "mountains",
    "buildings", "diaspora", "expatriates", "emigrants",
]


def is_skippable_category(title):
    lname = title.lower()
    return any(s in lname for s in CATEGORY_SKIP_SUBSTRINGS)


def enwiki_category_members(category_title, cmtype, limit=300):
    """list=categorymembers, paged via cmcontinue. cmtype: 'page' or
    'subcat'. Read-only reuse of wputils.api_get (which does its own
    caching/throttling/retry under tools/fame/raw/, per its existing
    design)."""
    out = []
    cont = None
    while len(out) < limit:
        params = {
            "action": "query", "list": "categorymembers",
            "cmtitle": category_title, "cmtype": cmtype,
            "cmlimit": min(500, limit - len(out)), "formatversion": "2",
        }
        if cmtype == "page":
            params["cmnamespace"] = 0
        if cont:
            params["cmcontinue"] = cont
        try:
            data = wputils.api_get(wputils.EN_API, params)
        except Exception as e:
            print(f"    category fetch error on {category_title}: {e}", file=sys.stderr)
            break
        members = data.get("query", {}).get("categorymembers", [])
        out.extend(m["title"] for m in members)
        cont = data.get("continue", {}).get("cmcontinue")
        if not cont:
            break
    return out[:limit]


def harvest_category_bfs(seed_categories, max_depth=2, max_subcats_per_level=30,
                          max_pages_total=400):
    """Bounded BFS from seed categories, descending through subcategories
    (skipping administrative/non-biographical ones) and collecting page
    (article) members at every level visited. General-purpose fallback for
    any pocket with no structured Wikidata source."""
    seen_cats = set()
    pages = set()
    frontier = [(c, 0) for c in seed_categories]
    while frontier and len(pages) < max_pages_total:
        cat, depth = frontier.pop(0)
        if cat in seen_cats:
            continue
        seen_cats.add(cat)
        pms = enwiki_category_members(cat, "page", limit=300)
        for p in pms:
            pages.add(p)
        print(f"    [{depth}] {cat}: {len(pms)} pages "
              f"(total pages so far: {len(pages)})", file=sys.stderr)
        if depth < max_depth and len(pages) < max_pages_total:
            subs = enwiki_category_members(cat, "subcat", limit=max_subcats_per_level)
            for s in subs:
                if s not in seen_cats and not is_skippable_category(s):
                    frontier.append((s, depth + 1))
    return list(pages)[:max_pages_total]


def batched(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def resolve_titles_to_qids(titles):
    """title -> qid, following redirects/normalization, batched 50 at a
    time. Mirrors the pattern in enrich_region_wikidata.py / build_universe.py."""
    result = {}
    for batch in batched(list(dict.fromkeys(titles)), 50):
        data = wputils.api_get(wputils.EN_API, {
            "action": "query", "titles": "|".join(batch), "redirects": "1",
            "prop": "pageprops", "ppprop": "wikibase_item", "formatversion": "2",
        })
        query = data.get("query", {})
        norm_map = {n["from"]: n["to"] for n in query.get("normalized", [])}
        redir_map = {r["from"]: r["to"] for r in query.get("redirects", [])}
        pages_by_title = {p["title"]: p for p in query.get("pages", [])}
        for raw in batch:
            cur = norm_map.get(raw, raw)
            cur = redir_map.get(cur, cur)
            page = pages_by_title.get(cur)
            if page and not page.get("missing"):
                qid = page.get("pageprops", {}).get("wikibase_item")
                if qid:
                    result[raw] = qid
    return result


def wd_get_entities(qids, props="claims|labels|sitelinks", languages="en"):
    """Batched wbgetentities, 50 QIDs per call. Returns qid -> entity dict."""
    result = {}
    for batch in batched(list(dict.fromkeys(qids)), 50):
        params = {
            "action": "wbgetentities", "ids": "|".join(batch),
            "props": props, "format": "json",
        }
        if languages:
            params["languages"] = languages
        data = wputils.api_get(wputils.WD_API, params)
        result.update(data.get("entities", {}))
    return result


def claim_ids(entity, prop):
    out = []
    for c in entity.get("claims", {}).get(prop, []):
        try:
            out.append(c["mainsnak"]["datavalue"]["value"]["id"])
        except (KeyError, TypeError):
            continue
    return out


def claim_time(entity, prop):
    for c in entity.get("claims", {}).get(prop, []):
        try:
            return c["mainsnak"]["datavalue"]["value"].get("time")
        except (KeyError, TypeError):
            continue
    return None


def claim_coord(entity, prop):
    for c in entity.get("claims", {}).get(prop, []):
        try:
            v = c["mainsnak"]["datavalue"]["value"]
            return v.get("latitude"), v.get("longitude")
        except (KeyError, TypeError):
            continue
    return None, None


def entity_label(entity, lang="en"):
    try:
        return entity.get("labels", {}).get(lang, {}).get("value")
    except AttributeError:
        return None


def entity_sitelink_count(entity):
    sl = entity.get("sitelinks")
    return len(sl) if isinstance(sl, dict) else None


def entity_enwiki_title(entity):
    sl = entity.get("sitelinks", {}) or {}
    enwiki = sl.get("enwiki")
    return enwiki.get("title") if enwiki else None


def enrich_titles_to_candidates(titles, pocket_id, source_tag):
    """
    General-purpose fallback enrichment: given a list of raw (possibly
    noisy -- not everything need be a person) enwiki page titles, resolve
    each to a Wikidata QID (following redirects), keep only humans
    (P31=Q5), and build full candidate dicts via a second batched lookup
    for occupation/gender/citizenship/birthplace/deathplace labels+coords.
    Shared by the category-BFS pocket (Dictionary of African Biography
    substitute) and the "In Our Time" episode-list pocket -- any future
    title-list-shaped source (no direct Wikidata property) can reuse this
    too.
    """
    if not titles:
        return [], "no_titles"

    title_to_qid = resolve_titles_to_qids(titles)
    print(f"    resolved {len(title_to_qid)}/{len(titles)} titles to Wikidata QIDs",
          file=sys.stderr)
    if not title_to_qid:
        return [], "no_qids_resolved"

    person_entities = wd_get_entities(list(title_to_qid.values()))

    # Filter to humans (P31 = Q5) and collect referenced QIDs (occupation,
    # gender, citizenship, birthplace, deathplace) for a second label pass.
    humans = {}
    ref_qids = set()
    for qid, ent in person_entities.items():
        if "Q5" not in claim_ids(ent, "P31"):
            continue
        humans[qid] = ent
        ref_qids.update(claim_ids(ent, "P106"))
        ref_qids.update(claim_ids(ent, "P21"))
        ref_qids.update(claim_ids(ent, "P27"))
        ref_qids.update(claim_ids(ent, "P19"))
        ref_qids.update(claim_ids(ent, "P20"))
    print(f"    {len(humans)}/{len(person_entities)} resolved QIDs are humans (P31=Q5)",
          file=sys.stderr)

    ref_entities = wd_get_entities(list(ref_qids), props="claims|labels")

    candidates = []
    title_by_qid = {v: k for k, v in title_to_qid.items()}
    for qid, ent in humans.items():
        occ_qids = claim_ids(ent, "P106")
        gender_qids = claim_ids(ent, "P21")
        citizenship_qids = claim_ids(ent, "P27")
        birthplace_qids = claim_ids(ent, "P19")
        deathplace_qids = claim_ids(ent, "P20")

        occupations = sorted(set(
            entity_label(ref_entities.get(q, {})) for q in occ_qids
            if entity_label(ref_entities.get(q, {}))))
        gender = None
        for g in gender_qids:
            gender = entity_label(ref_entities.get(g, {}))
            if gender:
                break
        citizenships = sorted(set(
            entity_label(ref_entities.get(q, {})) for q in citizenship_qids
            if entity_label(ref_entities.get(q, {}))))

        birth_place = birth_lat = birth_lon = None
        for bp in birthplace_qids:
            bp_ent = ref_entities.get(bp, {})
            birth_place = entity_label(bp_ent)
            birth_lat, birth_lon = claim_coord(bp_ent, "P625")
            if birth_place:
                break
        death_place = death_lat = death_lon = None
        for dp in deathplace_qids:
            dp_ent = ref_entities.get(dp, {})
            death_place = entity_label(dp_ent)
            death_lat, death_lon = claim_coord(dp_ent, "P625")
            if death_place:
                break

        dob = claim_time(ent, "P569")
        dod = claim_time(ent, "P570")
        sitelinks = entity_sitelink_count(ent)
        enwiki_title = entity_enwiki_title(ent) or title_by_qid.get(qid)
        region = None
        for c in citizenships:
            region = region_for_country(c)
            if region:
                break

        has_dod = bool(dod)
        candidates.append({
            "qid": qid,
            "name": entity_label(ent) or enwiki_title,
            "wiki_title": enwiki_title,
            "gender": gender,
            "occupations": occupations,
            "birth_year": parse_year(dob),
            "death_year": parse_year(dod),
            "has_death_date": has_dod,
            "is_living": not has_dod,
            "birth_place": birth_place,
            "birth_lat": birth_lat,
            "birth_lon": birth_lon,
            "death_place": death_place,
            "death_lat": death_lat,
            "death_lon": death_lon,
            "citizenships": citizenships,
            "region": region,
            "sitelinks": sitelinks,
            "recognisability_hint": recognisability_hint(sitelinks),
            "has_image": None,
            "pockets": [pocket_id],
            "sources": [source_tag],
        })
    return candidates, None


def run_category_fallback_pocket(pocket_id, seed_categories):
    """The African Biography substitute: BFS category harvest, then the
    shared title -> full-candidate enrichment."""
    titles = harvest_category_bfs(seed_categories)
    print(f"    category BFS collected {len(titles)} candidate page titles",
          file=sys.stderr)
    return enrich_titles_to_candidates(titles, pocket_id, "enwiki_category_bfs")


# ---------------------------------------------------------------------------
# Pocket F: "Enthusiast canon" -- figures who recur in popular history
# writing/podcasts/documentaries but whose general-population Wikipedia
# metrics (sitelinks, pageviews) are unremarkable, so they are invisible to
# every occupation/award/identifier-property pocket above. Per product
# guidance: sitelink count is a floor against the genuinely unknown, not a
# ranking signal -- a Rest Is History listener knows Belisarius or Simon de
# Montfort perfectly well even though neither would clear a "household name"
# bar. BBC Radio 4's "In Our Time" (~1000 episodes since 1998, list published
# as a single Wikipedia article) is close to a direct enumeration of what
# this audience finds interesting, so it is harvested as its own source.
# ---------------------------------------------------------------------------

IN_OUR_TIME_LIST_PAGE = "List of In Our Time programmes"


def _split_wikitable_row_into_columns(row_chunk):
    """
    Split one wikitable row's raw wikitext into its '|'-delimited columns.
    Column boundaries are lines that start with a single '|' (or '!' for
    header cells); everything after is a continuation of the current
    column's content (this is safe here because the multi-line
    {{indented plainlist| ...}} template inside the Contributors column
    uses '*' for its own bullet lines, never a line-leading '|').
    """
    columns = []
    current = None  # None (not just empty) so junk before the first '|'
                    # cell -- e.g. a leading blank line right after the
                    # '|-' row separator -- is discarded, not counted as
                    # a phantom column 0.
    for line in row_chunk.splitlines():
        if line.startswith("|") and not line.startswith("|-") and not line.startswith("||"):
            if current is not None:
                columns.append("\n".join(current))
            current = [line[1:].strip()]
        elif line.startswith("!"):
            if current is not None:
                columns.append("\n".join(current))
            current = [line[1:].strip()]
        else:
            if current is not None:
                current.append(line)
    if current is not None:
        columns.append("\n".join(current))
    return columns


TITLE_CELL_ITALIC_RE = re.compile(r"''+")


def _extract_episode_subject(title_cell):
    """
    From the Title column of one In Our Time episode row, return a best-
    guess subject string to resolve against enwiki: the target of the
    first wikilink if the cell has one (covers direct person/topic links
    like '[[Alexander the Great]]' or '[[Hans Holbein the Younger|Holbein]]
    at the Tudor Court'), else the cell's plain text with wiki markup
    stripped (covers unlinked titles).
    """
    if not title_cell:
        return None
    links = wputils.extract_wikilinks(title_cell)
    if links:
        return links[0][0].strip()
    plain = TITLE_CELL_ITALIC_RE.sub("", title_cell)
    plain = re.sub(r"\{\{[^{}]*\}\}", "", plain)
    plain = re.sub(r"<[^>]+>", "", plain)
    plain = plain.strip(" '\"")
    return plain or None


def harvest_in_our_time_subjects():
    """Fetch the episode-list article, split into wikitable rows, pull one
    subject-title guess per row. Returns a deduped list of subject titles."""
    wt = wputils.get_wikitext(IN_OUR_TIME_LIST_PAGE)
    if not wt:
        return []
    rows = re.split(r"\n\|-", wt)
    subjects = []
    for row in rows:
        if "Broadcast date" in row or len(row.strip()) < 10:
            continue
        cols = _split_wikitable_row_into_columns(row)
        if len(cols) < 2:
            continue
        subject = _extract_episode_subject(cols[1])
        if subject and not subject.lower().startswith(("http://", "https://")):
            subjects.append(subject)
    return list(dict.fromkeys(subjects))


def run_in_our_time_pocket(pocket_id):
    subjects = harvest_in_our_time_subjects()
    print(f"    parsed {len(subjects)} candidate episode-subject titles from "
          f"'{IN_OUR_TIME_LIST_PAGE}'", file=sys.stderr)
    return enrich_titles_to_candidates(subjects, pocket_id, "in_our_time_episode_list")


# ---------------------------------------------------------------------------
# Dedupe against existing project data (read-only)
# ---------------------------------------------------------------------------

REPO_ROOT = HERE.parent.parent


def _norm(s):
    if not s:
        return None
    s = s.strip().lower().replace("_", " ")
    s = re.sub(r"\s+", " ", s)
    return s or None


def load_existing_identifiers():
    """Read-only load of universe_people.json, current_inventory.json,
    data/figures.json, data/reveal-who.json. Returns (title_set, name_set,
    qid_set, per_file_counts)."""
    titles, names, qids = set(), set(), set()
    counts = {}

    def add(t=None, n=None, q=None):
        if t:
            titles.add(_norm(t))
        if n:
            names.add(_norm(n))
        if q:
            qids.add(q)

    path = HERE / "universe_people.json"
    if path.exists():
        d = json.loads(path.read_text(encoding="utf-8"))
        people = d.get("people", [])
        for p in people:
            add(t=p.get("wiki_title"), n=p.get("name"), q=p.get("qid"))
        counts["universe_people.json"] = len(people)

    path = HERE / "current_inventory.json"
    if path.exists():
        d = json.loads(path.read_text(encoding="utf-8"))
        items = d.get("items", [])
        for it in items:
            add(t=it.get("wiki_title"), n=it.get("display_name"))
        counts["current_inventory.json"] = len(items)

    path = REPO_ROOT / "data" / "figures.json"
    if path.exists():
        items = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(items, dict):
            items = items.get("figures", [])
        for it in items:
            add(n=it.get("name"))
        counts["data/figures.json"] = len(items)

    path = REPO_ROOT / "data" / "reveal-who.json"
    if path.exists():
        items = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(items, dict):
            items = items.get("items", [])
        for it in items:
            add(n=it.get("name"))
        counts["data/reveal-who.json"] = len(items)

    return titles, names, qids, counts


def mark_new(candidates, titles, names, qids):
    for c in candidates:
        matched = None
        if c.get("qid") and c["qid"] in qids:
            matched = f"qid={c['qid']}"
        elif _norm(c.get("wiki_title")) and _norm(c["wiki_title"]) in titles:
            matched = f"wiki_title={c['wiki_title']}"
        elif _norm(c.get("name")) and _norm(c["name"]) in names:
            matched = f"name={c['name']}"
        c["is_new"] = matched is None
        c["dup_match"] = matched


# ---------------------------------------------------------------------------
# Image existence check (batched pageimages, only for surviving candidates)
# ---------------------------------------------------------------------------

def annotate_has_image(candidates):
    titles = [c["wiki_title"] for c in candidates if c.get("wiki_title")]
    has_image_by_title = {}
    for batch in batched(list(dict.fromkeys(titles)), 50):
        try:
            data = wputils.api_get(wputils.EN_API, {
                "action": "query", "titles": "|".join(batch),
                "prop": "pageimages", "piprop": "name", "formatversion": "2",
            })
        except Exception as e:
            print(f"    pageimages batch error: {e}", file=sys.stderr)
            continue
        for p in data.get("query", {}).get("pages", []):
            has_image_by_title[p.get("title")] = bool(p.get("pageimage"))
    for c in candidates:
        t = c.get("wiki_title")
        c["has_image"] = has_image_by_title.get(t, False) if t else False


# ---------------------------------------------------------------------------
# Recognisability tiering.
#
# Product guidance (relayed mid-run): general-population metrics (sitelinks,
# pageviews) measure fame to EVERYONE, but this app's audience is history
# enthusiasts who recognise far more than the general public does. Sitelink
# count stays as a floor against the genuinely unknown, but is NOT the
# ranking signal -- three tags instead: "household_name" (recognisable to
# almost anyone -- the scarce easy-tier resource), "enthusiast" (known to
# history lovers, not the general public -- most of this harvest's real
# value), "specialist" (too obscure even for enthusiasts -- excluded from
# the final output). This is deliberately a simple heuristic tag, not a
# scoring model -- a separate agent owns tools/fame/build_salience.py.
# ---------------------------------------------------------------------------

ENTHUSIAST_OCCUPATION_HINTS = {
    "general", "military personnel", "military officer", "military commander",
    "monarch", "king", "queen", "emperor", "empress", "pharaoh", "consul",
    "statesman", "philosopher", "historian", "theologian", "explorer",
    "admiral", "nobleman", "noblewoman", "diplomat", "chronicler", "crusader",
    "warlord", "regent", "viceroy", "condottiero",
}


def recognition_tier(c):
    sitelinks = c.get("sitelinks") or 0
    pockets = c.get("pockets", [])
    if sitelinks >= 60:
        return "household_name"
    if "in_our_time_canon" in pockets:
        # Direct signal from a curated history-enthusiast source -- trust
        # it over the raw metric.
        return "enthusiast"
    if sitelinks >= 6:
        return "enthusiast"
    occ_lower = {o.lower() for o in c.get("occupations", [])}
    death_year = c.get("death_year")
    if (occ_lower & ENTHUSIAST_OCCUPATION_HINTS and death_year is not None
            and death_year < 1900 and sitelinks >= 3):
        # A pre-modern general/monarch/statesman with only modest sitelinks
        # is still exactly Rest Is History's bread and butter (Belisarius,
        # Stilicho, Mithridates...) -- don't let a low general-population
        # metric bury them.
        return "enthusiast"
    return "specialist"


def annotate_recognition_tier(candidates):
    for c in candidates:
        c["recognition_tier"] = recognition_tier(c)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def merge_candidates(all_by_qid, new_candidates):
    for c in new_candidates:
        qid = c.get("qid")
        if not qid:
            continue
        if qid in all_by_qid:
            existing = all_by_qid[qid]
            existing["pockets"] = sorted(set(existing["pockets"] + c["pockets"]))
            existing["occupations"] = sorted(set(existing["occupations"] + c["occupations"]))
            existing["citizenships"] = sorted(set(existing["citizenships"] + c["citizenships"]))
            existing["sources"] = sorted(set(existing["sources"] + c["sources"]))
            # prefer the richer/non-null values already present; fill gaps
            for field in ("birth_place", "birth_lat", "birth_lon",
                          "death_place", "death_lat", "death_lon",
                          "region", "gender", "birth_year", "death_year"):
                if existing.get(field) in (None, "") and c.get(field) not in (None, ""):
                    existing[field] = c[field]
            if (c.get("sitelinks") or 0) > (existing.get("sitelinks") or 0):
                existing["sitelinks"] = c["sitelinks"]
                existing["recognisability_hint"] = c["recognisability_hint"]
        else:
            all_by_qid[qid] = c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--force", action="store_true",
                     help="ignore existing raw/people_v2_<pocket>.json files")
    ap.add_argument("--pocket", default=None,
                     help="run only this pocket id (debug/resume)")
    ap.add_argument("--skip-african-fallback", action="store_true",
                     help="skip the slower category-BFS pocket")
    ap.add_argument("--skip-in-our-time", action="store_true",
                     help="skip the In Our Time enthusiast-canon pocket")
    args = ap.parse_args()

    print("=== Network verification ===", file=sys.stderr)
    sparql_ok, enwiki_ok, details = verify_network()
    print(f"  Wikidata SPARQL endpoint: {'OK' if sparql_ok else 'FAILED'} -- {details.get('sparql')}",
          file=sys.stderr)
    print(f"  enwiki action API:       {'OK' if enwiki_ok else 'FAILED'} -- {details.get('enwiki')}",
          file=sys.stderr)
    if args.verify_only:
        return
    if not (sparql_ok and enwiki_ok):
        print("Network verification failed -- stopping (no fabricated output).",
              file=sys.stderr)
        sys.exit(1)

    all_by_qid = {}
    pocket_errors = {}
    pocket_counts = {}

    all_pocket_ids = {p[0] for p in get_pockets()} | {
        "african_biography_fallback", "in_our_time_canon"}
    if args.pocket and args.pocket not in all_pocket_ids:
        print(f"Unknown pocket id: {args.pocket}", file=sys.stderr)
        sys.exit(1)

    pockets = get_pockets()
    if args.pocket:
        pockets = [p for p in pockets if p[0] == args.pocket]

    for pocket_id, where_clause, min_sitelinks, limit, max_pages, desc in pockets:
        raw_path = RAW_DIR / f"people_v2_{pocket_id}.json"
        if raw_path.exists() and not args.force:
            print(f"[{pocket_id}] using existing {raw_path.name} (--force to re-run)",
                  file=sys.stderr)
            cands = json.loads(raw_path.read_text(encoding="utf-8"))
        else:
            print(f"[{pocket_id}] {desc}", file=sys.stderr)
            cands, err = run_sparql_pocket(pocket_id, where_clause, min_sitelinks,
                                            limit, max_pages)
            if err:
                pocket_errors[pocket_id] = err
                print(f"    ERROR: {err}", file=sys.stderr)
            raw_path.write_text(json.dumps(cands, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
        pocket_counts[pocket_id] = len(cands)
        print(f"    -> {len(cands)} candidates", file=sys.stderr)
        merge_candidates(all_by_qid, cands)

    fallback_pockets = []
    if not args.skip_african_fallback:
        fallback_pockets.append((
            "african_biography_fallback",
            lambda pid: run_category_fallback_pocket(pid, AFRICAN_SEED_CATEGORIES),
            "Dictionary of African Biography has no Wikidata ID property -- "
            "falling back to Wikipedia category traversal"))
    if not args.skip_in_our_time:
        fallback_pockets.append((
            "in_our_time_canon",
            run_in_our_time_pocket,
            "Enthusiast canon: BBC Radio 4 'In Our Time' episode-subject list "
            "(~1000 episodes) -- history-enthusiast recognisability, not "
            "general-population fame"))
    if args.pocket:
        fallback_pockets = [p for p in fallback_pockets if p[0] == args.pocket]

    for pocket_id, runner, desc in fallback_pockets:
        raw_path = RAW_DIR / f"people_v2_{pocket_id}.json"
        if raw_path.exists() and not args.force:
            print(f"[{pocket_id}] using existing {raw_path.name} (--force to re-run)",
                  file=sys.stderr)
            cands = json.loads(raw_path.read_text(encoding="utf-8"))
        else:
            print(f"[{pocket_id}] {desc}", file=sys.stderr)
            cands, err = runner(pocket_id)
            if err:
                pocket_errors[pocket_id] = err
                print(f"    ERROR: {err}", file=sys.stderr)
            raw_path.write_text(json.dumps(cands, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
        pocket_counts[pocket_id] = len(cands)
        print(f"    -> {len(cands)} candidates", file=sys.stderr)
        merge_candidates(all_by_qid, cands)

    candidates = list(all_by_qid.values())
    print(f"\n=== Total unique candidates across all pockets: {len(candidates)} ===",
          file=sys.stderr)

    print("Checking image availability (batched pageimages)...", file=sys.stderr)
    annotate_has_image(candidates)

    print("Dedupe against existing project data...", file=sys.stderr)
    titles, names, qids, existing_counts = load_existing_identifiers()
    for f, n in existing_counts.items():
        print(f"  loaded {n} entries from {f}", file=sys.stderr)
    mark_new(candidates, titles, names, qids)
    new_count = sum(1 for c in candidates if c["is_new"])
    print(f"  {new_count}/{len(candidates)} candidates are genuinely new", file=sys.stderr)

    print("Tagging recognisability tier (household_name / enthusiast / specialist)...",
          file=sys.stderr)
    annotate_recognition_tier(candidates)
    tier_counts_all = {}
    for c in candidates:
        tier_counts_all[c["recognition_tier"]] = tier_counts_all.get(c["recognition_tier"], 0) + 1
    print(f"  before exclusion: {tier_counts_all}", file=sys.stderr)

    specialist_dropped = [c for c in candidates if c["recognition_tier"] == "specialist"]
    candidates = [c for c in candidates if c["recognition_tier"] != "specialist"]
    print(f"  dropped {len(specialist_dropped)} 'specialist' (too obscure even for "
          f"enthusiasts) candidates; {len(candidates)} remain", file=sys.stderr)

    tier_rank = {"household_name": 0, "enthusiast": 1}
    candidates.sort(key=lambda c: (not c["is_new"], tier_rank.get(c["recognition_tier"], 2),
                                    -(c.get("sitelinks") or 0)))
    new_count = sum(1 for c in candidates if c["is_new"])

    output = {
        "generatedOn": time.strftime("%Y-%m-%d"),
        "source": "harvest_people_v2.py -- Wikidata SPARQL occupation/award/"
                   "identifier-property crosses + enwiki category-BFS fallback "
                   "(Dictionary of African Biography substitute) + BBC 'In Our "
                   "Time' episode-list enthusiast-canon pocket; see "
                   "HARVEST_PEOPLE_V2.md",
        "pocket_counts": pocket_counts,
        "pocket_errors": pocket_errors,
        "total_candidates": len(candidates),
        "new_candidates": new_count,
        "specialist_tier_dropped": len(specialist_dropped),
        "recognition_tier_counts": {
            t: sum(1 for c in candidates if c["recognition_tier"] == t)
            for t in ("household_name", "enthusiast")
        },
        "candidates": candidates,
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    print(f"\nWrote {OUTPUT_PATH} ({len(candidates)} candidates, {new_count} new, "
          f"{len(specialist_dropped)} specialist-tier dropped)", file=sys.stderr)


if __name__ == "__main__":
    main()
