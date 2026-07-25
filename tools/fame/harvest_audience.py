#!/usr/bin/env python3
"""
harvest_audience.py -- harvest people-content from AUDIENCE-MATCHED sources.

WHY THIS EXISTS
---------------
tools/fame/universe_people.json is built from a single source (the MIT
Pantheon Historical Popularity Index) and then truncated at TARGET_COUNT =
4000, which discards ~51,800 eligible people. The 2026-07-25 blindspot audit
(tools/out/content-blindspots-2026-07-25/) showed what that costs: the
universe is ~32% statesmen/politicians and thin on everyone who did
something other than rule, fight or preach -- 52 athletes, 48 explorers, 46
inventor-engineers in the whole 4000. The launch review's substantive
complaint matched: the month played NARROW -- rulers, commanders, senior
clergy, war, formal religion, monumental architecture, death as the
recurring payoff. Everyday life, work, science, medicine, sport,
exploration and culture were all thin.

Pantheon's HPI is a general-population traffic measure, so ranking by it
concentrates exactly on the people everyone already sees. This harvester
goes at the problem from the other end: sources that encode EDITORIAL
JUDGEMENT about historical significance, sampled deliberately ACROSS
occupation families rather than ranked globally by fame.

The audience bar is "Rest Is History podcast listeners": curious,
Anglophone, well-read, not academic.

SOURCES (all counts verified by live query on 2026-07-25)
---------------------------------------------------------
  odnb        Oxford DNB via Wikidata P1415. 63,041 items carry an ODNB ID;
              24,276 are dead + have an image (P18) + have an enwiki
              article. ODNB inclusion is an editorial judgement about
              British historical significance and it yields precisely the
              missing band (Pepys, Bazalgette, W. G. Grace). Sampled as
              per-OCCUPATION strata, not as a global top-N -- see
              "Occupation strata" below.
  adb         Australian Dictionary of Biography, P1907. 4,817 dead + image
              + enwiki.
  dib         Dictionary of Irish Biography, P6829. 2,748 dead + image +
              enwiki.
  inourtime   BBC Radio 4 "In Our Time". The Wikipedia article "List of In
              Our Time programmes" holds 1,108 wikitable rows (~484k chars
              of wikitext). Closest thing to a literal enumeration of what
              this audience finds interesting. Not categorised by subject,
              so every row's linked subject is resolved to a Wikidata item
              and only P31=Q5 (human) items are kept.
  occupations Global Wikidata occupation-family queries, no dictionary and
              no nationality filter. This is the direct fix for the 32%-
              statesmen skew AND it reaches outside the Anglophone
              dictionaries for region variety.
  nzpacific   New Zealand / Pacific -- the one verified SOURCE-LEVEL hole
              (Te Rauparaha, Tupaia, Eddie Mabo, Kupe and Hone Heke are
              absent from Pantheon entirely). The Te Ara / Dictionary of
              New Zealand Biography property was UNVERIFIED in the brief;
              it is P2745, confirmed live via wbsearchentities.

DELIBERATELY NOT A SELECTION AXIS
---------------------------------
Gender. Product direction (2026-07-25): do not run gender-filtered queries,
do not set targets, do not build machinery for it, and never filter
against. Gender is RECORDED per candidate because the game needs the fact,
and it is not used to select, rank or quota anybody. The optimisation
target is subject-matter variety.

Sitelink count is likewise NOT the ranking signal -- it measures
general-population fame, the exact bias being corrected. It is used only as
a FLOOR against the genuinely unknown, and the floor is set per occupation
family (low where the universe is starved, high where it is saturated).

USAGE
-----
    python3 tools/fame/harvest_audience.py                  # full run
    python3 tools/fame/harvest_audience.py --verify-only    # network check
    python3 tools/fame/harvest_audience.py --source odnb    # one source
    python3 tools/fame/harvest_audience.py --force          # ignore raw/
    python3 tools/fame/harvest_audience.py --limit-scale 0.25   # quick pass

Outputs:
    tools/fame/raw/audience_<source>.json   per-source selection results
    tools/fame/audience_candidates.json     merged, enriched, deduped

Both are re-runnable and resumable: every HTTP response is cached on disk
(tools/fame/cache/audience_sparql/, .../audience_wd/) and every source's
selection phase is skipped if its raw/ file already exists.

Python 3.9, stdlib only. See tools/fame/HARVEST_AUDIENCE.md for the full
write-up, the SPARQL queries and how this should feed build_universe.py.
"""

import argparse
import hashlib
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
RAW_DIR = HERE / "raw"
CACHE_DIR = HERE / "cache"
OUTPUT_PATH = HERE / "audience_candidates.json"

USER_AGENT = "DeadFamousIntake/1.0 (daniel.illes12@gmail.com)"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
WD_API = "https://www.wikidata.org/w/api.php"
EN_API = "https://en.wikipedia.org/w/api.php"

GENERATED_ON = "2026-07-25"

# WDQS aggregate queries are heavy server-side; throttle gently and lean on
# the disk cache for resumability (same policy as harvest_people_v2.py).
SPARQL_MIN_INTERVAL = 1.5
SPARQL_TIMEOUT = 180
SPARQL_MAX_RETRIES = 4

# The MediaWiki action APIs are cheap; fetch_metrics.py's 8 req/s ceiling.
API_MIN_INTERVAL = 1.0 / 8.0
API_TIMEOUT = 60
API_MAX_RETRIES = 5

BATCH_SIZE = 50

_last_sparql_ts = [0.0]
_last_api_ts = [0.0]

STATS = {"sparql": 0, "sparql_cached": 0, "api": 0, "api_cached": 0, "retries": 0}


# ---------------------------------------------------------------------------
# Region + era conventions.
#
# build_tags.py already owns the canonical 10-bucket macroregion table
# (Europe / Middle East & North Africa / Sub-Saharan Africa / North America
# / Latin America & Caribbean / East Asia / South Asia / Southeast Asia /
# Central Asia & Russia / Oceania) including ~100 historical-polity aliases
# ("Kingdom of England" -> Europe, "Ottoman Empire" -> MENA). Reuse it so
# this harvest's region breakdown is directly comparable with the audit's.
# It is imported READ-ONLY and defensively: another agent owns that file and
# may be editing it, so a broken import degrades to regions.py + the same
# documented remap rather than killing the run.
# ---------------------------------------------------------------------------

sys.path.insert(0, str(HERE))

_REGION_FN = None
_REGION_SOURCE = "unavailable"
try:
    import build_tags as _build_tags  # noqa: E402
    _REGION_FN = _build_tags.region_for_country_label
    _REGION_SOURCE = "build_tags.region_for_country_label"
except Exception as _e:  # pragma: no cover - fallback path
    try:
        import regions as _regions  # noqa: E402

        _FALLBACK_REMAP = {
            "Europe": "Europe", "Middle East": "Middle East & North Africa",
            "Central Asia": "Central Asia & Russia", "South Asia": "South Asia",
            "East Asia": "East Asia", "Southeast Asia": "Southeast Asia",
            "Africa": "Sub-Saharan Africa",
            "North America": "North America",
            "South America": "Latin America & Caribbean",
            "Oceania": "Oceania",
        }

        def _fallback_region(label):
            coarse = _regions.region_for_country(label)
            return _FALLBACK_REMAP.get(coarse) if coarse else None

        _REGION_FN = _fallback_region
        _REGION_SOURCE = f"regions.py fallback (build_tags import failed: {_e})"
    except Exception:  # pragma: no cover
        _REGION_FN = lambda label: None  # noqa: E731
        _REGION_SOURCE = "none"


def region_for_label(label):
    if not label:
        return None
    try:
        return _REGION_FN(label)
    except Exception:
        return None


def era_for_year(year):
    """Same buckets as build_tags.era_for_year (inlined -- 10 lines, not
    worth a second import dependency)."""
    if year is None:
        return None
    if year < 500:
        return "ancient"
    if year <= 1449:
        return "medieval"
    if year <= 1799:
        return "early-modern"
    if year <= 1899:
        return "nineteenth"
    if year <= 1988:
        return "twentieth"
    return "contemporary"


def era_for_person(birth_year, death_year):
    if birth_year is not None and death_year is not None:
        candidate = min(death_year, birth_year + 40)
    elif birth_year is not None:
        candidate = birth_year + 40
    else:
        candidate = death_year
    return era_for_year(candidate)


# ---------------------------------------------------------------------------
# HTTP layer: throttling, retry/backoff, on-disk cache.
# Mirrors fetch_metrics.py's http_get_json conventions -- successful and
# definitively-failed responses are cached; transient failures are not, so a
# re-run retries them.
# ---------------------------------------------------------------------------

def _cache_path(bucket, key):
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()
    d = CACHE_DIR / bucket
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{h}.json"


def _read_cache(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(path, payload):
    try:
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass


def _throttle(slot, interval):
    now = time.monotonic()
    wait = slot[0] + interval - now
    if wait > 0:
        time.sleep(wait)
    slot[0] = time.monotonic()


def sparql_query(query):
    """Run a SPARQL query against WDQS. Returns {"ok", "bindings", "error"}.
    Cached by exact query text, so LIMIT/OFFSET pages cache separately."""
    cache_file = _cache_path("audience_sparql", query)
    cached = _read_cache(cache_file)
    if cached is not None:
        STATS["sparql_cached"] += 1
        return cached

    url = SPARQL_ENDPOINT + "?" + urllib.parse.urlencode(
        {"query": query, "format": "json"})
    last_error = None
    for attempt in range(1, SPARQL_MAX_RETRIES + 1):
        _throttle(_last_sparql_ts, SPARQL_MIN_INTERVAL)
        STATS["sparql"] += 1
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/sparql-results+json"})
        try:
            with urllib.request.urlopen(req, timeout=SPARQL_TIMEOUT) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            result = {"ok": True,
                      "bindings": body.get("results", {}).get("bindings", []),
                      "error": None}
            _write_cache(cache_file, result)
            return result
        except urllib.error.HTTPError as e:
            last_error = f"http_{e.code}"
            if e.code == 429 or 500 <= e.code < 600:
                STATS["retries"] += 1
                if attempt < SPARQL_MAX_RETRIES:
                    time.sleep(min(5 * attempt, 30))
                    continue
            return {"ok": False, "bindings": [], "error": last_error}
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            STATS["retries"] += 1
            last_error = f"{type(e).__name__}:{e}"
            if attempt < SPARQL_MAX_RETRIES:
                time.sleep(min(5 * attempt, 30))
                continue
    return {"ok": False, "bindings": [], "error": last_error or "max_retries_exceeded"}


def api_get(base, params, cache_bucket):
    """GET a MediaWiki action API endpoint, with cache/throttle/retry."""
    params = dict(params)
    params.setdefault("format", "json")
    qs = urllib.parse.urlencode(params)
    cache_file = _cache_path(cache_bucket, base + "?" + qs)
    cached = _read_cache(cache_file)
    if cached is not None:
        STATS["api_cached"] += 1
        return cached

    url = base + "?" + qs
    last_error = None
    for attempt in range(1, API_MAX_RETRIES + 1):
        _throttle(_last_api_ts, API_MIN_INTERVAL)
        STATS["api"] += 1
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            _write_cache(cache_file, body)
            return body
        except urllib.error.HTTPError as e:
            last_error = f"http_{e.code}"
            if e.code == 429 or 500 <= e.code < 600:
                STATS["retries"] += 1
                if attempt < API_MAX_RETRIES:
                    time.sleep(min(2 ** attempt, 30))
                    continue
            return {"error": last_error}
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            STATS["retries"] += 1
            last_error = f"{type(e).__name__}:{e}"
            if attempt < API_MAX_RETRIES:
                time.sleep(min(2 ** attempt, 30))
                continue
    return {"error": last_error or "max_retries_exceeded"}


# ---------------------------------------------------------------------------
# Network verification -- one cheap request to each endpoint, run first and
# unconditionally. Both APIs 403 a bare request; the descriptive User-Agent
# above is what makes them answer.
# ---------------------------------------------------------------------------

def verify_network():
    details = {}

    t0 = time.monotonic()
    r = sparql_query("SELECT ?p WHERE { ?p wdt:P1415 ?id } LIMIT 1")
    ok_sparql = r["ok"] and len(r["bindings"]) >= 1
    details["wikidata_sparql"] = (
        f"{'OK' if ok_sparql else 'FAILED'} -- {len(r['bindings'])} row(s), "
        f"{time.monotonic() - t0:.1f}s"
        + (f", error={r['error']}" if r.get("error") else ""))

    t0 = time.monotonic()
    body = api_get(EN_API, {"action": "query", "titles": "Samuel Pepys",
                            "prop": "pageprops", "formatversion": "2"},
                   "audience_wd")
    pages = (body.get("query") or {}).get("pages") or []
    ok_enwiki = bool(pages) and not body.get("error")
    details["enwiki_api"] = (
        f"{'OK' if ok_enwiki else 'FAILED'} -- {len(pages)} page(s), "
        f"{time.monotonic() - t0:.1f}s"
        + (f", error={body.get('error')}" if body.get("error") else ""))

    return ok_sparql, ok_enwiki, details


# ---------------------------------------------------------------------------
# Occupation families.
#
# Every QID below was verified live on 2026-07-25: the ODNB ones came out of
# a live occupation histogram over the ODNB set (so their presence in the
# data is proven, not assumed), the rest were resolved with
# wbsearchentities and checked to be the canonical occupation class.
#
# The FAMILY is the lever. The audit measured which families the universe
# is saturated with and which it is starved of, and the harvest budget per
# family is set accordingly -- suppressed families get a small limit and a
# high sitelink floor, starved families get a large limit and a floor near
# the ground. This is what makes the harvest broad by construction instead
# of a fame ranking with a diversity garnish.
# ---------------------------------------------------------------------------

# family -> (odnb_limit, odnb_floor, global_limit, global_floor)
# global_limit 0 = do not run this family as a worldwide query (already
# saturated in the universe; the dictionaries alone are plenty).
FAMILY_POLICY = {
    # --- SATURATED in the current universe: harvest thinly, high floor ---
    "ruling_politics":       (35,  12,   0,  0),   # 1301/4000 = 32.5% today
    "military":              (30,  10,   0,  0),   # war was the launch month's theme
    "religion":              (30,  10,   0,  0),   # 474/4000, all senior clergy
    # --- MIDDLING ---
    "letters":               (55,   5,  60, 40),
    "scholarship":           (70,   4,  80, 30),
    "arts_culture":          (85,   3,  90, 28),
    # --- STARVED: this is the point of the exercise ---
    "science_nature":        (130,  2, 140, 20),
    "medicine":              (150,  2, 150, 15),
    "engineering_invention": (160,  2, 160, 15),   # 46/4000 inventor-engineers
    "exploration_travel":    (200,  1, 200, 12),   # 48/4000 explorers
    "sport":                 (180,  1, 200, 15),   # 52/4000 athletes
    "work_trade_everyday":   (150,  1, 150, 15),   # "everyday life and work"
    "reform_activism":       (150,  1, 150, 12),   # 43/4000
}

STARVED_FAMILIES = {
    "science_nature", "medicine", "engineering_invention",
    "exploration_travel", "sport", "work_trade_everyday", "reform_activism",
}
SUPPRESSED_FAMILIES = {"ruling_politics", "military", "religion"}

# occupation QID -> (english label, family). Ordered roughly by family.
OCCUPATIONS = {
    # ruling / politics / law
    "Q82955": ("politician", "ruling_politics"),
    "Q193391": ("diplomat", "ruling_politics"),
    "Q16533": ("judge", "ruling_politics"),
    "Q808967": ("barrister", "ruling_politics"),
    "Q40348": ("lawyer", "ruling_politics"),
    "Q185351": ("jurist", "ruling_politics"),
    "Q2478141": ("aristocrat", "ruling_politics"),
    "Q116": ("monarch", "ruling_politics"),
    "Q132050": ("governor", "ruling_politics"),
    "Q17765219": ("colonial administrator", "ruling_politics"),
    "Q212238": ("civil servant", "ruling_politics"),
    # military
    "Q47064": ("military personnel", "military"),
    "Q189290": ("military officer", "military"),
    "Q10669499": ("naval officer", "military"),
    "Q4991371": ("soldier", "military"),
    "Q132851": ("admiral", "military"),
    "Q1402561": ("military leader", "military"),
    # religion
    "Q3409375": ("Anglican priest", "religion"),
    "Q1234713": ("theologian", "religion"),
    "Q250867": ("Catholic priest", "religion"),
    "Q29182": ("bishop", "religion"),
    "Q611644": ("Catholic bishop", "religion"),
    "Q1423891": ("Christian minister", "religion"),
    "Q2259532": ("ecclesiastic", "religion"),
    "Q42603": ("priest", "religion"),
    "Q432386": ("preacher", "religion"),
    "Q49476": ("archbishop", "religion"),
    "Q219477": ("missionary", "religion"),
    # letters
    "Q36180": ("writer", "letters"),
    "Q49757": ("poet", "letters"),
    "Q6625963": ("novelist", "letters"),
    "Q214917": ("playwright", "letters"),
    "Q1930187": ("journalist", "letters"),
    "Q333634": ("translator", "letters"),
    "Q864380": ("biographer", "letters"),
    "Q1607826": ("editor", "letters"),
    "Q11774202": ("essayist", "letters"),
    "Q4853732": ("children's writer", "letters"),
    "Q4263842": ("literary critic", "letters"),
    "Q28389": ("screenwriter", "letters"),
    "Q18844224": ("science fiction writer", "letters"),
    "Q14972848": ("lexicographer", "letters"),
    # NOTE: diarists are filed under work_trade_everyday, not letters --
    # a diarist IS the everyday-life record (Pepys, Evelyn, Kilvert).
    # scholarship
    "Q201788": ("historian", "scholarship"),
    "Q4964182": ("philosopher", "scholarship"),
    "Q14467526": ("linguist", "scholarship"),
    "Q1792450": ("art historian", "scholarship"),
    "Q2468727": ("classical scholar", "scholarship"),
    "Q5697103": ("antiquarian", "scholarship"),
    "Q1731155": ("orientalist", "scholarship"),
    "Q188094": ("economist", "scholarship"),
    "Q2306091": ("sociologist", "scholarship"),
    "Q182436": ("librarian", "scholarship"),
    "Q13418253": ("philologist", "scholarship"),
    "Q37226": ("teacher", "scholarship"),
    "Q1231865": ("pedagogue", "scholarship"),
    "Q14915627": ("musicologist", "scholarship"),
    # archaeology + anthropology sit in scholarship but are STARVED, so
    # they get their own boosted entries via OCCUPATION_LIMIT_OVERRIDE.
    "Q3621491": ("archaeologist", "scholarship"),
    "Q4773904": ("anthropologist", "scholarship"),
    # arts & culture
    "Q1028181": ("painter", "arts_culture"),
    "Q33231": ("photographer", "arts_culture"),
    "Q36834": ("composer", "arts_culture"),
    "Q177220": ("singer", "arts_culture"),
    "Q639669": ("musician", "arts_culture"),
    "Q33999": ("actor", "arts_culture"),
    "Q2259451": ("stage actor", "arts_culture"),
    "Q1281618": ("sculptor", "arts_culture"),
    "Q644687": ("illustrator", "arts_culture"),
    "Q5716684": ("dancer", "arts_culture"),
    "Q158852": ("conductor", "arts_culture"),
    "Q2865819": ("opera singer", "arts_culture"),
    "Q486748": ("pianist", "arts_culture"),
    "Q245068": ("comedian", "arts_culture"),
    "Q2526255": ("film director", "arts_culture"),
    "Q5322166": ("designer", "arts_culture"),
    "Q329439": ("engraver", "arts_culture"),
    "Q11569986": ("printmaker", "arts_culture"),
    "Q753110": ("songwriter", "arts_culture"),
    "Q765778": ("organist", "arts_culture"),
    "Q1776724": ("theatre manager", "arts_culture"),
    # science & nature
    "Q2374149": ("botanist", "science_nature"),
    "Q593644": ("chemist", "science_nature"),
    "Q169470": ("physicist", "science_nature"),
    "Q11063": ("astronomer", "science_nature"),
    "Q18805": ("naturalist", "science_nature"),
    "Q520549": ("geologist", "science_nature"),
    "Q350979": ("zoologist", "science_nature"),
    "Q3055126": ("entomologist", "science_nature"),
    "Q1225716": ("ornithologist", "science_nature"),
    "Q170790": ("mathematician", "science_nature"),
    "Q864503": ("biologist", "science_nature"),
    "Q2732142": ("statistician", "science_nature"),
    "Q901": ("scientist", "science_nature"),
    "Q98544732": ("scientific collector", "science_nature"),
    "Q2083925": ("botanical collector", "science_nature"),
    "Q901402": ("geographer", "science_nature"),
    # medicine
    "Q39631": ("physician", "medicine"),
    "Q774306": ("surgeon", "medicine"),
    "Q186360": ("nurse", "medicine"),
    "Q10872101": ("anatomist", "medicine"),
    "Q2055046": ("physiologist", "medicine"),
    "Q185196": ("midwife", "medicine"),
    "Q12765408": ("epidemiologist", "medicine"),
    "Q105186": ("pharmacist", "medicine"),
    # engineering & invention
    "Q81096": ("engineer", "engineering_invention"),
    "Q13582652": ("civil engineer", "engineering_invention"),
    "Q205375": ("inventor", "engineering_invention"),
    "Q42973": ("architect", "engineering_invention"),
    "Q1734662": ("cartographer", "engineering_invention"),
    "Q6606110": ("industrialist", "engineering_invention"),
    "Q2106711": ("shipbuilder", "engineering_invention"),
    # exploration & travel
    "Q11900058": ("explorer", "exploration_travel"),
    "Q12356615": ("traveler", "exploration_travel"),
    "Q2095549": ("aircraft pilot", "exploration_travel"),
    "Q9149093": ("mountaineer", "exploration_travel"),
    "Q11631": ("astronaut", "exploration_travel"),
    "Q45199": ("sailor", "exploration_travel"),
    "Q254651": ("navigator", "exploration_travel"),
    # sport
    "Q12299841": ("cricketer", "sport"),
    "Q937857": ("association football player", "sport"),
    "Q2066131": ("athlete", "sport"),
    "Q11338576": ("boxer", "sport"),
    "Q10833314": ("tennis player", "sport"),
    "Q10873124": ("chess player", "sport"),
    "Q2309784": ("sport cyclist", "sport"),
    "Q10349745": ("racing automobile driver", "sport"),
    "Q10843402": ("swimmer", "sport"),
    "Q14089670": ("rugby union player", "sport"),
    "Q846750": ("jockey", "sport"),
    "Q11513337": ("athletics competitor", "sport"),
    "Q10871364": ("baseball player", "sport"),
    "Q3665646": ("basketball player", "sport"),
    # work, trade & everyday life
    "Q43845": ("businessperson", "work_trade_everyday"),
    "Q215536": ("merchant", "work_trade_everyday"),
    "Q806798": ("banker", "work_trade_everyday"),
    "Q131524": ("entrepreneur", "work_trade_everyday"),
    "Q131512": ("farmer", "work_trade_everyday"),
    "Q175151": ("printer", "work_trade_everyday"),
    "Q998550": ("bookseller", "work_trade_everyday"),
    "Q2516866": ("publisher", "work_trade_everyday"),
    "Q10732476": ("art collector", "work_trade_everyday"),
    "Q9352089": ("spy", "work_trade_everyday"),
    "Q18939491": ("diarist", "work_trade_everyday"),
    "Q3499072": ("chef", "work_trade_everyday"),
    "Q156839": ("cook", "work_trade_everyday"),
    "Q1639825": ("blacksmith", "work_trade_everyday"),
    "Q437512": ("weaver", "work_trade_everyday"),
    "Q820037": ("miner", "work_trade_everyday"),
    "Q23754015": ("textile manufacturer", "work_trade_everyday"),
    "Q3427922": ("restaurateur", "work_trade_everyday"),
    # reform & activism
    "Q15627169": ("trade unionist", "reform_activism"),
    "Q322170": ("suffragette", "reform_activism"),
    "Q27532437": ("suffragist", "reform_activism"),
    "Q12526417": ("abolitionist", "reform_activism"),
    "Q15253558": ("activist", "reform_activism"),
    "Q16611574": ("social reformer", "reform_activism"),
    "Q12362622": ("philanthropist", "reform_activism"),
}

# Per-occupation overrides where the family default is the wrong call.
# (odnb_limit, odnb_floor, global_limit, global_floor); None = keep family.
OCCUPATION_OVERRIDE = {
    # Starved specialisms that happen to sit in a middling family.
    "Q3621491": (200, 1, 200, 14),   # archaeologist
    "Q4773904": (180, 1, 160, 16),   # anthropologist
    "Q33231": (200, 1, 180, 20),     # photographer -- documents everyday life
    "Q5716684": (150, 1, 140, 18),   # dancer
    "Q245068": (130, 2, 120, 20),    # comedian
    "Q5322166": (130, 2, 120, 20),   # designer
    "Q18939491": (200, 1, 120, 8),   # diarist -- the everyday-life record
    # Saturated even inside a middling family.
    "Q36180": (45, 8, 40, 55),       # "writer" is a catch-all, 4198 in ODNB
    "Q1622272": (0, 0, 0, 0),        # university teacher -- pure noise
    # Missionaries travel further than anyone; keep more than the religion
    # default even though the family is suppressed.
    "Q219477": (90, 2, 60, 18),
    # Explorers/travellers: take essentially everything ODNB has.
    "Q11900058": (300, 1, 250, 10),
    "Q12356615": (200, 1, 150, 10),
}


def limits_for(occ_qid, scope):
    """scope: 'odnb' or 'global'. Returns (limit, floor)."""
    label, family = OCCUPATIONS[occ_qid]
    ov = OCCUPATION_OVERRIDE.get(occ_qid)
    if ov is not None:
        ol, of, gl, gf = ov
    else:
        ol, of, gl, gf = FAMILY_POLICY[family]
    return (ol, of) if scope == "odnb" else (gl, gf)


def primary_family(occ_qids, occ_labels):
    """A person usually carries several occupations. Pick the one that says
    what a ROUND about them would actually be about.

    Wikidata lists P106 roughly main-occupation-first, so the first mapped
    occupation is the honest answer nearly all the time. An earlier version
    of this preferred whichever family was most starved, which produced
    nonsense at exactly the moment it mattered: Bing Crosby filed as an
    ATHLETE because he once owned a piece of a baseball team, Michael
    Crichton as a basketball player, Dean Martin as a boxer. That would
    have inflated the very numbers this harvest exists to report.

    The one deliberate override is the original intent: if the first
    occupation is in a saturated family (politician / soldier / cleric) and
    a starved one appears later, take the starved one -- 'politician + civil
    engineer' really is an engineering round, not another statesman."""
    fams = []
    for q in occ_qids:                      # ORDER MATTERS -- do not sort
        entry = OCCUPATIONS.get(q)
        if entry:
            fams.append(entry[1])
    if not fams:
        # Fall back to a label-text match for occupations outside the table.
        text = " ".join(l.lower() for l in occ_labels)
        for q, (lab, fam) in OCCUPATIONS.items():
            if lab in text:
                fams.append(fam)
    if not fams:
        return None, []
    first = fams[0]
    if first in SUPPRESSED_FAMILIES:
        for f in fams:
            if f in STARVED_FAMILIES:
                return f, sorted(set(fams))
    return first, sorted(set(fams))


# ---------------------------------------------------------------------------
# SELECTION PHASE -- lean SPARQL.
#
# Two-phase by design. A single query that also pulls labels, coordinates
# and occupations for a 24k-row set times WDQS out (measured: the bare COUNT
# over ODNB alone takes 16-55s). So selection stays lean -- person, sitelink
# count, enwiki article -- and enrichment happens over the wbgetentities
# API, which is fast, batched 50-at-a-time and cached per QID.
#
# ORDER BY DESC(?sitelinks) inside a stratum is a TIE-BREAK, not the
# selection principle: the stratum itself (this occupation, in this
# editorial dictionary, above this floor) is what does the choosing. Within
# "ODNB cricketers" or "ODNB engineers" a sitelink sort is harmless -- it is
# only comparing like with like. It never compares a cricketer to a king.
# ---------------------------------------------------------------------------

SELECT_TEMPLATE = """
SELECT DISTINCT ?p ?sl ?a WHERE {{
{where}
  ?p wdt:P570 ?dod .
{image_clause}  ?a schema:about ?p ; schema:isPartOf <https://en.wikipedia.org/> .
  ?p wikibase:sitelinks ?sl .
  FILTER(?sl >= {floor})
}}
ORDER BY DESC(?sl)
LIMIT {limit}
"""

# Requiring a Wikidata image (P18) is a FACE VALUE requirement -- that game
# tears scraps off a portrait. LIFELINE needs birth and death coordinates
# and no portrait at all. Requiring P18 everywhere therefore silently drops
# exactly the pre-colonial figures the map game most needs: Tupaia (the
# Ra'iatean navigator who sailed with Cook and died in Batavia) and Eddie
# Mabo both carry no P18 and were missed by the first run because of it.
# So the New Zealand / Pacific source -- the deliberate hole-filler, and
# small enough that the extra volume costs nothing -- runs without the
# image requirement. has_image is recorded per candidate either way, so
# Face Value can filter on it downstream.
IMAGE_CLAUSE = "  ?p wdt:P18 ?img .\n"

# Living people are excluded at the query level by requiring P570 (date of
# death). The project excludes living people outright and living
# politicians emphatically; is_living is still recorded per candidate and
# re-checked after enrichment, so nothing slips through silently.


def run_selection(where, floor, limit, require_image=True):
    q = SELECT_TEMPLATE.format(
        where=where, floor=floor, limit=limit,
        image_clause=IMAGE_CLAUSE if require_image else "")
    r = sparql_query(q)
    if not r["ok"]:
        return [], r["error"], q
    out = []
    for b in r["bindings"]:
        qid = b["p"]["value"].rsplit("/", 1)[-1]
        title = urllib.parse.unquote(
            b["a"]["value"].rsplit("/", 1)[-1]).replace("_", " ")
        try:
            sl = int(float(b["sl"]["value"]))
        except (KeyError, ValueError, TypeError):
            sl = None
        out.append({"qid": qid, "wiki_title": title, "sitelinks": sl})
    return out, None, q


def dictionary_strata(source_id, prop, scale):
    """ODNB-shaped source: one stratum per occupation."""
    strata = []
    for occ_qid in OCCUPATIONS:
        limit, floor = limits_for(occ_qid, "odnb")
        if limit <= 0:
            continue
        limit = max(10, int(limit * scale))
        label = OCCUPATIONS[occ_qid][0]
        where = (f"  ?p wdt:{prop} ?dictid .\n"
                 f"  ?p wdt:P106 wd:{occ_qid} .\n")
        strata.append((f"{source_id}:{label}", where, floor, limit))
    # Catch-all: strong ODNB entries whose occupations are outside the
    # table entirely (there is a long tail of them).
    strata.append((f"{source_id}:any-occupation",
                   f"  ?p wdt:{prop} ?dictid .\n", 25, max(50, int(400 * scale))))
    return strata


def whole_source_strata(source_id, prop, floor, limit, scale):
    """ADB/DIB-shaped source: small enough to pull whole, then let the
    family caps apply in post rather than in the query.

    A second, image-free stratum runs alongside the main one. Requiring a
    portrait is a Face Value constraint, and applying it to a whole
    editorial dictionary quietly deletes people the dictionary itself
    judged significant -- Eddie Mabo carries an ADB entry and no P18, no
    P19, no P27 and no P172, so the image requirement was the only thing
    standing between him and the harvest. The main stratum still leads with
    portrait-bearing entries; this one is the lane for the rest."""
    return [
        (f"{source_id}:all", f"  ?p wdt:{prop} ?dictid .\n",
         floor, max(100, int(limit * scale))),
        (f"{source_id}:no-image", f"  ?p wdt:{prop} ?dictid .\n",
         4, max(100, int(600 * scale)), False),
    ]


def global_occupation_strata(scale):
    """No dictionary, no nationality: worldwide by occupation. This is the
    direct answer to '32% statesmen', and because it is not filtered to the
    Anglophone dictionaries it is also the main lever on region variety."""
    strata = []
    for occ_qid in OCCUPATIONS:
        limit, floor = limits_for(occ_qid, "global")
        if limit <= 0:
            continue
        limit = max(10, int(limit * scale))
        label = OCCUPATIONS[occ_qid][0]
        strata.append((f"occupations:{label}",
                       f"  ?p wdt:P106 wd:{occ_qid} .\n", floor, limit))
    return strata


# New Zealand / Pacific. Te Rauparaha, Tupaia, Kupe, Hone Heke and Eddie
# Mabo are absent from Pantheon entirely, so this is a source-level hole,
# not a ranking artefact. P2745 (Dictionary of New Zealand Biography, the
# Te Ara property) was UNVERIFIED in the brief -- confirmed live on
# 2026-07-25 via wbsearchentities. Nationality queries are kept as the
# documented fallback because pre-colonial figures often carry no P27 at
# all: they are reached by ethnic group (P172) and birthplace-country
# instead.
# NOTE: Australia (Q408) and New Zealand (Q664) are deliberately NOT in
# this list. Both have dedicated coverage already -- Australia through the
# ADB source, New Zealand through its own strata below -- and including
# them here floods a sitelink-ordered stratum with Australians, pushing the
# actual Pacific islanders (and figures like Eddie Mabo) off the end.
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
PACIFIC_ETHNIC_QIDS = [
    "Q6122670",  # Māori
    "Q170355",   # Aboriginal Australians
    "Q1283606",  # Native Hawaiians
    "Q37732",    # Polynesians
    "Q726673",   # Torres Strait Islanders
]


def nz_pacific_strata(scale):
    def sc(n):
        return max(25, int(n * scale))
    # Every stratum here runs with require_image=False (the 5th element):
    # this is the hole-filling source, and a missing portrait must not cost
    # us a Lifeline figure. See IMAGE_CLAUSE above.
    strata = [
        # Stratum sizes are set against live counts (dead + enwiki, floor 2,
        # no image requirement): DNZB 2,115 / NZ citizens 7,257 / Pacific
        # ethnic groups 179 / small Pacific nations 600. The two small ones
        # are taken in full -- there is no reason to sample a pocket of 179
        # when the universe holds six Oceanians in total.
        # 1. The editorial source: Te Ara / DNZB (P2745), verified.
        ("nzpacific:dnzb", "  ?p wdt:P2745 ?dnzb .\n", 1, sc(3000), False),
        # 2. Nationality fallback.
        ("nzpacific:nz-citizen", "  ?p wdt:P27 wd:Q664 .\n", 2, sc(700), False),
        # 3. Born in New Zealand -- catches people with no/other P27.
        ("nzpacific:born-in-nz",
         "  ?p wdt:P19 ?bp . ?bp wdt:P17 wd:Q664 .\n", 2, sc(400), False),
        # 4. Ethnic group -- the route to pre-colonial figures. Taken whole.
        ("nzpacific:pacific-peoples",
         "  VALUES ?eth { " + " ".join(f"wd:{q}" for q in PACIFIC_ETHNIC_QIDS)
         + " }\n  ?p wdt:P172 ?eth .\n", 1, sc(300), False),
        # 5. Small Pacific nations by citizenship. Taken whole.
        ("nzpacific:oceania-citizens",
         "  VALUES ?c { " + " ".join(f"wd:{q}" for q in OCEANIA_COUNTRY_QIDS)
         + " }\n  ?p wdt:P27 ?c .\n", 2, sc(650), False),
        # 6. Born anywhere in the small Pacific nations.
        ("nzpacific:born-in-oceania",
         "  VALUES ?c { " + " ".join(f"wd:{q}" for q in OCEANIA_COUNTRY_QIDS)
         + " }\n  ?p wdt:P19 ?bp . ?bp wdt:P17 ?c .\n", 2, sc(400), False),
        # 7. Indigenous Australians reached through the ADB property as
        #    well, since P172 coverage on Wikidata is patchy.
        ("nzpacific:indigenous-australian",
         "  VALUES ?eth { wd:Q170355 wd:Q726673 }\n"
         "  { ?p wdt:P172 ?eth } UNION { ?p wdt:P27 wd:Q408 ; wdt:P172 ?eth }\n",
         1, sc(200), False),
    ]
    return strata


# ---------------------------------------------------------------------------
# In Our Time.
#
# 1,108 wikitable rows in one article. Each row's Title column is a
# wikilink; the link target is the episode subject. Most subjects are
# topics ("Delian League", "Seashell"), some are people -- so every subject
# is resolved to a Wikidata item and only P31=Q5 survives.
# ---------------------------------------------------------------------------

IN_OUR_TIME_PAGE = "List of In Our Time programmes"
WIKILINK_RE = re.compile(r"\[\[([^\]\|]+)(?:\|([^\]]*))?\]\]")


def get_wikitext(title):
    body = api_get(EN_API, {
        "action": "query", "prop": "revisions", "rvprop": "content",
        "rvslots": "main", "titles": title, "formatversion": "2",
    }, "audience_wd")
    try:
        return body["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]
    except (KeyError, IndexError, TypeError):
        return None


def _row_columns(chunk):
    """Split one wikitable row's wikitext into its '|'-delimited columns.
    Column boundaries are lines starting with a single '|' (or '!');
    everything else continues the current column (safe here -- the
    multi-line contributor templates use '*' bullets, never a line-leading
    '|')."""
    out, cur = [], None
    for line in chunk.splitlines():
        if line.startswith("|") and not line.startswith("|-") and not line.startswith("||"):
            if cur is not None:
                out.append("\n".join(cur))
            cur = [line[1:].strip()]
        elif line.startswith("!"):
            if cur is not None:
                out.append("\n".join(cur))
            cur = [line[1:].strip()]
        elif cur is not None:
            cur.append(line)
    if cur is not None:
        out.append("\n".join(cur))
    return out


def in_our_time_subjects():
    wt = get_wikitext(IN_OUR_TIME_PAGE)
    if not wt:
        return [], 0
    rows = re.split(r"\n\|-", wt)
    subjects = []
    for row in rows:
        if "Broadcast date" in row or len(row.strip()) < 10:
            continue
        cols = _row_columns(row)
        if len(cols) < 2:
            continue
        cell = cols[1]
        m = WIKILINK_RE.search(cell)
        if m:
            subj = m.group(1).strip()
        else:
            plain = re.sub(r"''+", "", cell)
            plain = re.sub(r"\{\{[^{}]*\}\}", "", plain)
            plain = re.sub(r"<[^>]+>", "", plain).strip(" '\"")
            subj = plain or None
        if subj and not subj.lower().startswith(("http://", "https://")) \
                and "#" not in subj and subj.lower() != "title":
            subjects.append(subj)
    return list(dict.fromkeys(subjects)), len(rows)


def batched(seq, n):
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def resolve_titles_to_qids(titles):
    """enwiki title -> (qid, canonical title), following redirects."""
    out = {}
    for batch in batched(dict.fromkeys(titles), BATCH_SIZE):
        body = api_get(EN_API, {
            "action": "query", "titles": "|".join(batch), "redirects": "1",
            "prop": "pageprops", "ppprop": "wikibase_item",
            "formatversion": "2",
        }, "audience_wd")
        q = body.get("query", {})
        norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
        redir = {r["from"]: r["to"] for r in q.get("redirects", [])}
        pages = {p["title"]: p for p in q.get("pages", [])}
        for raw in batch:
            cur = redir.get(norm.get(raw, raw), norm.get(raw, raw))
            page = pages.get(cur)
            if page and not page.get("missing"):
                qid = (page.get("pageprops") or {}).get("wikibase_item")
                if qid:
                    out[raw] = (qid, page["title"])
    return out


def sitelinks_for_qids(qids):
    """Sitelink counts for QIDs that did not come from a selection query
    (the In Our Time path). One SPARQL VALUES query per 300 QIDs."""
    out = {}
    for batch in batched(qids, 300):
        vals = " ".join(f"wd:{q}" for q in batch)
        q = ("SELECT ?p ?sl WHERE { VALUES ?p { " + vals +
             " } ?p wikibase:sitelinks ?sl }")
        r = sparql_query(q)
        if not r["ok"]:
            continue
        for b in r["bindings"]:
            qid = b["p"]["value"].rsplit("/", 1)[-1]
            try:
                out[qid] = int(float(b["sl"]["value"]))
            except (KeyError, ValueError, TypeError):
                pass
    return out


# ---------------------------------------------------------------------------
# ENRICHMENT -- wbgetentities, batched 50, cached per QID.
#
# Only the claims this project needs are kept, and they are cached per QID
# (not per batch) so a re-run with a different candidate set reuses
# everything it already has.
# ---------------------------------------------------------------------------

WANTED_CLAIMS = {
    "P31": "instance_of", "P21": "gender", "P106": "occupation",
    "P569": "birth_date", "P570": "death_date", "P19": "birth_place",
    "P20": "death_place", "P27": "citizenship", "P172": "ethnic_group",
    "P18": "image", "P625": "coord", "P17": "country",
    "P39": "position_held",
}


def _claim_values(entity, prop):
    """Return the datavalues of prop, ignoring deprecated/no-value ones."""
    out = []
    for c in entity.get("claims", {}).get(prop, []):
        if c.get("rank") == "deprecated":
            continue
        snak = c.get("mainsnak", {})
        if snak.get("snaktype") != "value":
            continue
        out.append(snak.get("datavalue", {}).get("value"))
    return out


def _slim(entity):
    """Keep only the fields we need, so the per-QID cache stays small."""
    slim = {"label": (entity.get("labels", {}).get("en") or {}).get("value")}
    for prop in WANTED_CLAIMS:
        vals = _claim_values(entity, prop)
        if not vals:
            continue
        if prop in ("P569", "P570"):
            slim[prop] = [v.get("time") for v in vals if isinstance(v, dict)]
        elif prop == "P625":
            slim[prop] = [(v.get("latitude"), v.get("longitude"))
                          for v in vals if isinstance(v, dict)]
        elif prop == "P18":
            slim[prop] = [v for v in vals if isinstance(v, str)][:1]
        else:
            slim[prop] = [v.get("id") for v in vals
                          if isinstance(v, dict) and v.get("id")]
    return slim


def fetch_entities(qids, progress_label=""):
    """qid -> slim entity dict. Per-QID disk cache."""
    result = {}
    todo = []
    for qid in dict.fromkeys(qids):
        cached = _read_cache(_cache_path("audience_wd_entity", qid))
        if cached is not None:
            result[qid] = cached
            STATS["api_cached"] += 1
        else:
            todo.append(qid)
    if todo:
        print(f"    {progress_label}: {len(result)} cached, "
              f"{len(todo)} to fetch", file=sys.stderr)
    for i, batch in enumerate(batched(todo, BATCH_SIZE)):
        body = api_get(WD_API, {
            "action": "wbgetentities", "ids": "|".join(batch),
            "props": "claims|labels", "languages": "en",
        }, "audience_wd_batch")
        entities = body.get("entities", {}) or {}
        for qid in batch:
            ent = entities.get(qid)
            slim = _slim(ent) if ent else {"label": None}
            _write_cache(_cache_path("audience_wd_entity", qid), slim)
            result[qid] = slim
        if (i + 1) % 10 == 0:
            print(f"      {progress_label} batch {i + 1}/"
                  f"{(len(todo) + BATCH_SIZE - 1) // BATCH_SIZE}",
                  file=sys.stderr)
    return result


def fetch_labels(qids):
    """qid -> english label, for occupation/gender/country/ethnic items."""
    out = {}
    todo = []
    for qid in dict.fromkeys(q for q in qids if q):
        cached = _read_cache(_cache_path("audience_wd_label", qid))
        if cached is not None:
            out[qid] = cached.get("label")
            STATS["api_cached"] += 1
        else:
            todo.append(qid)
    for batch in batched(todo, BATCH_SIZE):
        body = api_get(WD_API, {
            "action": "wbgetentities", "ids": "|".join(batch),
            "props": "labels", "languages": "en",
        }, "audience_wd_batch")
        entities = body.get("entities", {}) or {}
        for qid in batch:
            lab = None
            ent = entities.get(qid)
            if ent:
                lab = (ent.get("labels", {}).get("en") or {}).get("value")
            _write_cache(_cache_path("audience_wd_label", qid), {"label": lab})
            out[qid] = lab
    return out


def enwiki_images(titles):
    """title -> bool, via prop=pageimages. The dictionary queries already
    require a Wikidata image (P18); this is the second, independent check
    that the enwiki article actually leads with a picture, which is what
    Face Value needs."""
    out = {}
    for batch in batched([t for t in titles if t], BATCH_SIZE):
        body = api_get(EN_API, {
            "action": "query", "titles": "|".join(batch),
            "prop": "pageimages", "piprop": "name", "formatversion": "2",
        }, "audience_wd")
        q = body.get("query", {})
        norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
        for p in q.get("pages", []):
            out[p.get("title")] = bool(p.get("pageimage"))
        for raw in batch:
            if raw not in out and norm.get(raw) in out:
                out[raw] = out[norm[raw]]
    return out


YEAR_RE = re.compile(r"^([+-]?\d+)-\d{2}-\d{2}T")


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


def haversine_km(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2 +
         math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return round(2 * r * math.asin(math.sqrt(a)), 1)


def journey_class(km):
    """Lifeline plots birth -> death on a map. A figure who was born and
    died in the same place is a dull round; the suitability analysis found
    fame explains only 1.3% of journey variance, so journey has to be
    selected for explicitly."""
    if km is None:
        return "unknown"
    if km < 25:
        return "stayed-put"
    if km < 100:
        return "local"
    if km < 500:
        return "regional"
    if km < 2000:
        return "long"
    return "epic"


# ---------------------------------------------------------------------------
# Recognition tiering.
#
# The game needs BOTH ends: easy Mondays need household names, hard weekends
# need enthusiast figures. Specialists -- too obscure even for a Rest Is
# History listener -- are dropped.
#
# The tier is NOT a fame ranking. Editorial-dictionary membership is treated
# as evidence in its own right: a figure ODNB judged worth an entry, with a
# handful of sitelinks, is an enthusiast figure even though the general
# population has never heard of them. That is the whole point.
# ---------------------------------------------------------------------------

EDITORIAL_SOURCES = {"odnb", "adb", "dib", "dnzb", "in_our_time"}

# Deaths within this many years of the run are held back from the
# shortlist. A game called Dead Famous should not open on someone who died
# last spring: it reads as news rather than history, the obituary framing
# is a different (and more sensitive) register than the house dark wit, and
# a just-dead politician is barely different from a living one -- which the
# project excludes outright. They stay in raw/audience_pool.json with a
# died_recently flag, so this is one constant to change, not a re-harvest.
RECENT_DEATH_CUTOFF = 2016


def recognition_tier(c):
    sl = c.get("sitelinks") or 0
    srcs = set(c.get("sources", []))
    editorial = bool(srcs & EDITORIAL_SOURCES)
    iot = "in_our_time" in srcs
    death = c.get("death_year")
    fam = c.get("primary_family")

    if sl >= 55:
        return "household_name"
    if iot and sl >= 30:
        return "household_name"
    if iot:
        return "enthusiast"
    if sl >= 10:
        return "enthusiast"
    if editorial and sl >= 4:
        return "enthusiast"
    if (editorial and sl >= 3 and fam in STARVED_FAMILIES
            and death is not None and death < 1975):
        return "enthusiast"
    return "specialist"


# ---------------------------------------------------------------------------
# Final shortlist cap.
#
# The tiered pool comes out far larger than a human can review. Trimming it
# with a single global cut is exactly the mistake build_universe.py's
# TARGET_COUNT = 4000 makes -- a global cut is a fame cut, and a fame cut is
# what produced 32% statesmen and 52 athletes. So the cap is applied PER
# FAMILY, with the same budget logic as the harvest itself: a starved family
# keeps four times what a saturated one does, and no family can be trimmed
# out of existence.
#
# The full tiered pool is still written to raw/audience_pool.json, so
# widening any family later is a re-read, not a re-harvest.
# ---------------------------------------------------------------------------

FAMILY_OUTPUT_CAP = {
    # saturated -- a token presence only
    "ruling_politics": 60, "military": 60, "religion": 60,
    # middling
    "letters": 200, "scholarship": 200, "arts_culture": 200,
    # starved -- the point of the exercise
    "science_nature": 240, "medicine": 240, "engineering_invention": 240,
    "exploration_travel": 240, "sport": 240, "work_trade_everyday": 240,
    "reform_activism": 240,
}
UNKNOWN_FAMILY_CAP = 60

# Each family's cap is stratified by era as well. Without this the
# shortlist comes out ~68% twentieth-century: Wikidata simply records more
# about modern people (coordinates, images, long emigration journeys), so
# every "quality" signal quietly rewards recency. A game called Dead Famous
# cannot be two-thirds twentieth century. Buckets that cannot fill spill
# into the others, so a genuinely modern family (sport) is not padded with
# people who do not exist.
ERA_BUCKETS = {
    "pre_modern": ("ancient", "medieval", "early-modern"),
    "nineteenth": ("nineteenth",),
    "modern": ("twentieth", "contemporary"),
}
ERA_SHARE = {"pre_modern": 0.30, "nineteenth": 0.35, "modern": 0.35}


# A third cap, on region. The audit's complaint was Europe at 65% and
# Oceania at 0.15%, and the raw harvest over-corrects: New Zealand and the
# Pacific get a source of their own (they are a genuine source-level hole)
# and would otherwise take ~14% of the shortlist, more than Europe deserves
# to lose. No region may exceed REGION_MAX_SHARE of the shortlist, and
# Oceania -- a hole being filled, not a main course -- gets a tighter one.
# The rest of the Pacific depth stays in raw/audience_pool.json.
REGION_MAX_SHARE = 0.30
REGION_SPECIAL_SHARE = {"Oceania": 0.08}

# Families are filled in this order so the starved ones get first pick of
# the scarce regions.
FAMILY_FILL_ORDER = [
    "exploration_travel", "sport", "medicine", "engineering_invention",
    "science_nature", "work_trade_everyday", "reform_activism",
    "arts_culture", "scholarship", "letters",
    "ruling_politics", "military", "religion",
]


def _era_bucket(era):
    for name, members in ERA_BUCKETS.items():
        if era in members:
            return name
    return "modern"


def apply_family_caps(pool):
    """Per-family, per-era cap over the tiered pool. Within a bucket, order
    by priority_score (which already rewards new + journey + image + starved
    family + non-European) and only then by sitelinks."""
    def order(rows):
        rows.sort(key=lambda c: (-c["priority_score"],
                                 -(c.get("sitelinks") or 0),
                                 c.get("name") or ""))
        return rows

    by_family = {}
    for c in pool:
        by_family.setdefault(c.get("primary_family"), []).append(c)

    total_cap = sum(FAMILY_OUTPUT_CAP.get(f, UNKNOWN_FAMILY_CAP)
                    for f in by_family)
    region_quota, region_used = {}, {}

    def region_ok(c, enforce=True):
        r = c.get("region")
        if not r or not enforce:
            return True
        if r not in region_quota:
            share = REGION_SPECIAL_SHARE.get(r, REGION_MAX_SHARE)
            region_quota[r] = int(round(total_cap * share))
        return region_used.get(r, 0) < region_quota[r]

    def take(c):
        r = c.get("region")
        if r:
            region_used[r] = region_used.get(r, 0) + 1

    def fill(candidates, want, chosen_qids, enforce=True):
        got = []
        for c in candidates:
            if len(got) >= want:
                break
            if c["qid"] in chosen_qids or not region_ok(c, enforce):
                continue
            got.append(c)
            chosen_qids.add(c["qid"])
            take(c)
        return got

    ordered_families = ([f for f in FAMILY_FILL_ORDER if f in by_family]
                        + [f for f in by_family if f not in FAMILY_FILL_ORDER])

    out = []
    for fam in ordered_families:
        rows = order(by_family[fam])
        cap = FAMILY_OUTPUT_CAP.get(fam, UNKNOWN_FAMILY_CAP)
        by_era = {}
        for c in rows:
            by_era.setdefault(_era_bucket(c.get("era")), []).append(c)
        for lst in by_era.values():
            order(lst)

        chosen, taken = set(), []
        for bucket, share in ERA_SHARE.items():
            want = int(round(cap * share))
            taken.extend(fill(by_era.get(bucket, []), want, chosen))
        # Spill: a bucket that could not fill (or was blocked by a region
        # quota) borrows from the rest of the family, still quota-aware.
        if len(taken) < cap:
            taken.extend(fill(rows, cap - len(taken), chosen))
        # Last resort: rather than leave a family short, ignore the region
        # quota. Keeping every family present matters more than the cap.
        if len(taken) < cap:
            taken.extend(fill(rows, cap - len(taken), chosen, enforce=False))
        out.extend(taken)

    return order(out)


def priority_score(c):
    """Transparent integer, for sorting the output only -- not a model.
    Rewards exactly what the audit said the game is short of."""
    s = 0
    if c.get("is_new"):
        s += 4
    if c.get("primary_family") in STARVED_FAMILIES:
        s += 3
    if c.get("journey_class") in ("regional", "long", "epic"):
        s += 3
    elif c.get("journey_class") == "local":
        s += 1
    if c.get("has_image"):
        s += 2
    if c.get("birth_lat") is not None and c.get("death_lat") is not None:
        s += 2
    if c.get("region") and c["region"] != "Europe":
        s += 1
    if c.get("recognition_tier") == "household_name":
        s += 1
    if c.get("primary_family") in SUPPRESSED_FAMILIES:
        s -= 2
    return s


# ---------------------------------------------------------------------------
# Dedupe against existing project data (READ-ONLY).
# ---------------------------------------------------------------------------

def _norm(s):
    if not s:
        return None
    s = s.strip().lower().replace("_", " ")
    return re.sub(r"\s+", " ", s) or None


def load_existing_identifiers():
    titles, names, qids, counts = set(), set(), set(), {}

    def add(t=None, n=None, q=None):
        if t:
            titles.add(_norm(t))
        if n:
            names.add(_norm(n))
        if q:
            qids.add(q)

    p = HERE / "universe_people.json"
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        people = d.get("people", []) if isinstance(d, dict) else d
        for x in people:
            add(t=x.get("wiki_title"), n=x.get("name"), q=x.get("qid"))
        counts["tools/fame/universe_people.json"] = len(people)

    p = HERE / "current_inventory.json"
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        items = d.get("items", []) if isinstance(d, dict) else d
        for x in items:
            add(t=x.get("wiki_title"), n=x.get("display_name"))
        counts["tools/fame/current_inventory.json"] = len(items)

    p = REPO_ROOT / "data" / "figures.json"
    if p.exists():
        items = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(items, dict):
            items = items.get("figures", [])
        for x in items:
            add(n=x.get("name"))
        counts["data/figures.json"] = len(items)

    p = REPO_ROOT / "data" / "reveal-who.json"
    if p.exists():
        items = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(items, dict):
            items = items.get("items", [])
        for x in items:
            add(n=x.get("name"))
        counts["data/reveal-who.json"] = len(items)

    return titles, names, qids, counts


def mark_new(candidates, titles, names, qids):
    for c in candidates:
        matched = None
        if c.get("qid") and c["qid"] in qids:
            matched = f"qid={c['qid']}"
        elif _norm(c.get("wiki_title")) in titles:
            matched = f"wiki_title={c['wiki_title']}"
        elif _norm(c.get("name")) in names:
            matched = f"name={c['name']}"
        c["is_new"] = matched is None
        c["dup_match"] = matched


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def get_sources(scale):
    """source_id -> (description, [strata]). A stratum is
    (stratum_id, where_clause, sitelink_floor, limit)."""
    return {
        "odnb": ("Oxford Dictionary of National Biography (Wikidata P1415); "
                 "24,276 dead + image + enwiki. One stratum per occupation.",
                 dictionary_strata("odnb", "P1415", scale)),
        "adb": ("Australian Dictionary of Biography (P1907); 4,817 dead + "
                "image + enwiki. Pulled whole.",
                whole_source_strata("adb", "P1907", 2, 2500, scale)),
        "dib": ("Dictionary of Irish Biography (P6829); 2,748 dead + image "
                "+ enwiki. Pulled whole.",
                whole_source_strata("dib", "P6829", 2, 2000, scale)),
        "nzpacific": ("New Zealand / Pacific: Te Ara-DNZB (P2745, verified "
                      "live) plus nationality, birthplace and ethnic-group "
                      "fallbacks for pre-colonial figures.",
                      nz_pacific_strata(scale)),
        "occupations": ("Worldwide Wikidata occupation families, no "
                        "dictionary or nationality filter -- the direct fix "
                        "for the 32%-statesmen skew.",
                        global_occupation_strata(scale)),
        "inourtime": ("BBC Radio 4 'In Our Time' episode list (1,108 rows) "
                      "-- resolved to Wikidata, humans only.", None),
    }


SOURCE_TAG = {
    "odnb": "odnb", "adb": "adb", "dib": "dib",
    "inourtime": "in_our_time", "occupations": "wikidata_occupation",
    "nzpacific": "nzpacific",
}


def run_source(source_id, desc, strata, scale, force):
    """Selection phase for one source. Writes raw/audience_<id>.json."""
    raw_path = RAW_DIR / f"audience_{source_id}.json"
    if raw_path.exists() and not force:
        d = json.loads(raw_path.read_text(encoding="utf-8"))
        print(f"  [{source_id}] reusing {raw_path.name} "
              f"({len(d.get('rows', []))} rows)", file=sys.stderr)
        return d

    print(f"  [{source_id}] {desc}", file=sys.stderr)
    rows, errors, queries = [], {}, {}

    if source_id == "inourtime":
        subjects, n_rows = in_our_time_subjects()
        print(f"    parsed {n_rows} wikitable rows -> {len(subjects)} "
              f"distinct episode subjects", file=sys.stderr)
        resolved = resolve_titles_to_qids(subjects)
        print(f"    resolved {len(resolved)} subjects to Wikidata items",
              file=sys.stderr)
        for raw_title, (qid, canon) in resolved.items():
            rows.append({"qid": qid, "wiki_title": canon, "sitelinks": None,
                         "stratum": "inourtime:episode-subject",
                         "episode_title": raw_title})
        queries["inourtime"] = (
            f"enwiki action=query&prop=revisions of '{IN_OUR_TIME_PAGE}', "
            "wikitable rows split on '|-', first wikilink of column 2 taken "
            "as the subject, then action=query&prop=pageprops "
            "(ppprop=wikibase_item, redirects=1) in batches of 50.")
    else:
        for st in strata:
            stratum_id, where, floor, limit = st[:4]
            require_image = st[4] if len(st) > 4 else True
            got, err, q = run_selection(where, floor, limit, require_image)
            queries[stratum_id] = q.strip()
            if err:
                errors[stratum_id] = err
                print(f"    {stratum_id}: ERROR {err}", file=sys.stderr)
                continue
            for r in got:
                r["stratum"] = stratum_id
            rows.extend(got)
            print(f"    {stratum_id}: {len(got)} rows "
                  f"(floor={floor}, limit={limit}"
                  f"{'' if require_image else ', no image required'})",
                  file=sys.stderr)

    payload = {
        "source": source_id, "description": desc,
        "generatedOn": GENERATED_ON, "limit_scale": scale,
        "n_rows": len(rows), "n_distinct": len({r["qid"] for r in rows}),
        "errors": errors, "queries": queries, "rows": rows,
    }
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"    -> {len(rows)} rows, {payload['n_distinct']} distinct people "
          f"-> {raw_path.name}", file=sys.stderr)
    return payload


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

HUMAN_QID = "Q5"
FEMALE_QID, MALE_QID = "Q6581072", "Q6581097"

# Position-held classes that make someone a politician for the purposes of
# the "no living politicians" rule. Only consulted when the person is
# actually living, which after the P570 filter is a handful of In Our Time
# subjects.
POLITICS_OCC_QIDS = {q for q, (_, f) in OCCUPATIONS.items()
                     if f == "ruling_politics"}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--verify-only", action="store_true",
                    help="run the network check and exit")
    ap.add_argument("--source", action="append", default=None,
                    help="run only this source (repeatable)")
    ap.add_argument("--force", action="store_true",
                    help="ignore existing raw/audience_*.json")
    ap.add_argument("--limit-scale", type=float, default=1.0,
                    help="scale every stratum limit (0.25 = quick pass)")
    args = ap.parse_args()

    t_start = time.monotonic()

    print("Verifying network access...", file=sys.stderr)
    ok_sparql, ok_enwiki, net = verify_network()
    for k, v in net.items():
        print(f"  {k}: {v}", file=sys.stderr)
    print(f"  region table: {_REGION_SOURCE}", file=sys.stderr)
    if args.verify_only:
        return 0 if (ok_sparql and ok_enwiki) else 1
    if not (ok_sparql and ok_enwiki):
        print("Network verification FAILED -- aborting.", file=sys.stderr)
        return 1

    sources = get_sources(args.limit_scale)
    wanted = args.source or list(sources)

    # ---- selection -------------------------------------------------------
    print("\nSELECTION", file=sys.stderr)
    raws = {}
    for sid in wanted:
        if sid not in sources:
            print(f"  unknown source {sid!r}; known: {list(sources)}",
                  file=sys.stderr)
            return 1
        desc, strata = sources[sid]
        raws[sid] = run_source(sid, desc, strata, args.limit_scale, args.force)

    # ---- merge -----------------------------------------------------------
    by_qid = {}
    for sid, payload in raws.items():
        tag = SOURCE_TAG[sid]
        for r in payload["rows"]:
            qid = r["qid"]
            c = by_qid.setdefault(qid, {
                "qid": qid, "wiki_title": r.get("wiki_title"),
                "sitelinks": r.get("sitelinks"), "sources": [], "strata": [],
            })
            if tag not in c["sources"]:
                c["sources"].append(tag)
            if r.get("stratum") and r["stratum"] not in c["strata"]:
                c["strata"].append(r["stratum"])
            if c.get("sitelinks") is None and r.get("sitelinks") is not None:
                c["sitelinks"] = r["sitelinks"]
            if not c.get("wiki_title"):
                c["wiki_title"] = r.get("wiki_title")
            if r.get("episode_title"):
                c["in_our_time_episode"] = r["episode_title"]
    # A DNZB entry is an editorial dictionary entry in its own right.
    for c in by_qid.values():
        if any(s.startswith("nzpacific:dnzb") for s in c["strata"]):
            if "dnzb" not in c["sources"]:
                c["sources"].append("dnzb")
    print(f"\nMERGED: {len(by_qid)} distinct people across "
          f"{len(raws)} source(s)", file=sys.stderr)

    # ---- enrichment ------------------------------------------------------
    print("\nENRICHMENT", file=sys.stderr)
    entities = fetch_entities(list(by_qid), "people")

    # Drop non-humans (In Our Time is full of topics) before anything else.
    non_human = [q for q, e in entities.items()
                 if HUMAN_QID not in (e.get("P31") or [])]
    for q in non_human:
        by_qid.pop(q, None)
    print(f"    dropped {len(non_human)} non-human items (In Our Time "
          f"topics etc.); {len(by_qid)} people remain", file=sys.stderr)

    # Sitelinks for anything that arrived without them.
    missing_sl = [q for q, c in by_qid.items() if c.get("sitelinks") is None]
    if missing_sl:
        print(f"    fetching sitelink counts for {len(missing_sl)} people",
              file=sys.stderr)
        got = sitelinks_for_qids(missing_sl)
        for q, sl in got.items():
            if q in by_qid:
                by_qid[q]["sitelinks"] = sl

    # Places -> label, coordinates, country.
    place_qids = set()
    for q, c in by_qid.items():
        e = entities.get(q, {})
        for prop in ("P19", "P20"):
            place_qids.update(e.get(prop) or [])
    print(f"    resolving {len(place_qids)} distinct birth/death places",
          file=sys.stderr)
    places = fetch_entities(sorted(place_qids), "places")

    # Labels for occupations / genders / citizenships / place countries /
    # ethnic groups.
    label_qids = set()
    for q, c in by_qid.items():
        e = entities.get(q, {})
        for prop in ("P21", "P106", "P27", "P172"):
            label_qids.update(e.get(prop) or [])
    for pe in places.values():
        label_qids.update(pe.get("P17") or [])
    print(f"    resolving {len(label_qids)} distinct labels", file=sys.stderr)
    labels = fetch_labels(sorted(label_qids))
    for q, pe in places.items():
        if pe.get("label"):
            labels.setdefault(q, pe["label"])

    def place_info(pqid):
        pe = places.get(pqid) or {}
        lat = lon = None
        coords = pe.get("P625") or []
        if coords:
            lat, lon = coords[0]
        country_qids = pe.get("P17") or []
        country = labels.get(country_qids[0]) if country_qids else None
        return pe.get("label"), lat, lon, country

    # Enwiki lead-image check.
    print(f"    checking enwiki lead images for {len(by_qid)} articles",
          file=sys.stderr)
    imgs = enwiki_images([c.get("wiki_title") for c in by_qid.values()])

    # ---- derive ----------------------------------------------------------
    candidates = []
    for qid, c in by_qid.items():
        e = entities.get(qid, {})
        occ_qids = e.get("P106") or []
        occ_labels = [labels.get(o) for o in occ_qids if labels.get(o)]
        gender_qids = e.get("P21") or []
        gender = labels.get(gender_qids[0]) if gender_qids else None
        citizenships = [labels.get(x) for x in (e.get("P27") or [])
                        if labels.get(x)]
        ethnic = [labels.get(x) for x in (e.get("P172") or []) if labels.get(x)]

        birth_year = parse_year((e.get("P569") or [None])[0])
        death_year = parse_year((e.get("P570") or [None])[0])
        is_living = not bool(e.get("P570"))

        bq = (e.get("P19") or [None])[0]
        dq = (e.get("P20") or [None])[0]
        b_label, b_lat, b_lon, b_country = place_info(bq) if bq else (None,) * 4
        d_label, d_lat, d_lon, d_country = place_info(dq) if dq else (None,) * 4

        region = None
        for cand in citizenships + [b_country, d_country]:
            region = region_for_label(cand)
            if region:
                break
        if not region:
            for cand in ethnic:
                region = region_for_label(cand)
                if region:
                    break

        fam, fams = primary_family(occ_qids, occ_labels)
        km = haversine_km(b_lat, b_lon, d_lat, d_lon)
        title = c.get("wiki_title")

        rec = {
            "qid": qid,
            "name": e.get("label") or title,
            "wiki_title": title,
            "gender": gender,
            "occupations": sorted(set(occ_labels)),
            "occupation_qids": occ_qids,
            "primary_family": fam,
            "families": fams,
            "birth_year": birth_year,
            "death_year": death_year,
            "era": era_for_person(birth_year, death_year),
            "is_living": is_living,
            "is_living_politician": bool(
                is_living and (set(occ_qids) & POLITICS_OCC_QIDS
                               or e.get("P39"))),
            "birth_place": b_label, "birth_lat": b_lat, "birth_lon": b_lon,
            "birth_country": b_country,
            "death_place": d_label, "death_lat": d_lat, "death_lon": d_lon,
            "death_country": d_country,
            "citizenships": citizenships,
            "ethnic_groups": ethnic,
            "region": region,
            "sources": sorted(c["sources"]),
            "strata": sorted(c["strata"]),
            "sitelinks": c.get("sitelinks"),
            "has_wikidata_image": bool(e.get("P18")),
            "has_enwiki_image": bool(imgs.get(title)),
            "journey_km": km,
            "journey_class": journey_class(km),
        }
        rec["has_image"] = rec["has_wikidata_image"] or rec["has_enwiki_image"]
        if c.get("in_our_time_episode"):
            rec["in_our_time_episode"] = c["in_our_time_episode"]
        candidates.append(rec)

    # ---- dedupe, tier, filter -------------------------------------------
    print("\nDEDUPE / TIERING", file=sys.stderr)
    titles, names, qids_seen, counts = load_existing_identifiers()
    for k, v in counts.items():
        print(f"    read {k}: {v} rows", file=sys.stderr)
    mark_new(candidates, titles, names, qids_seen)

    for c in candidates:
        c["recognition_tier"] = recognition_tier(c)

    n_before = len(candidates)
    living = [c for c in candidates if c["is_living"]]
    living_politicians = [c for c in candidates if c["is_living_politician"]]
    specialists = [c for c in candidates if c["recognition_tier"] == "specialist"]

    for c in candidates:
        dy = c.get("death_year")
        c["died_recently"] = dy is not None and dy >= RECENT_DEATH_CUTOFF

    pool = [c for c in candidates
            if c["recognition_tier"] != "specialist" and not c["is_living"]]
    for c in pool:
        c["priority_score"] = priority_score(c)
    pool.sort(key=lambda c: (-c["priority_score"],
                             -(c.get("sitelinks") or 0),
                             c.get("name") or ""))

    print(f"    {n_before} enriched -> dropped {len(specialists)} specialist, "
          f"{len(living)} living ({len(living_politicians)} living "
          f"politicians) -> {len(pool)} in the tiered pool", file=sys.stderr)

    # Full tiered pool goes to raw/ so a later widening is a re-read, not a
    # re-harvest; the reviewable shortlist goes to the output file.
    pool_path = RAW_DIR / "audience_pool.json"
    pool_path.write_text(json.dumps(
        {"generatedOn": GENERATED_ON, "n": len(pool),
         "note": "full tiered pool before the per-family output cap",
         "candidates": pool}, ensure_ascii=False), encoding="utf-8")

    recent = [c for c in pool if c["died_recently"]]
    kept = apply_family_caps([c for c in pool if not c["died_recently"]])
    print(f"    held back {len(recent)} who died since {RECENT_DEATH_CUTOFF}; "
          f"per-family output cap: {len(pool)} -> {len(kept)} "
          f"(full pool kept in raw/audience_pool.json)", file=sys.stderr)

    # ---- summary ---------------------------------------------------------
    def tally(key_fn, rows):
        out = {}
        for r in rows:
            k = key_fn(r)
            out[k if k is not None else "(unknown)"] = \
                out.get(k if k is not None else "(unknown)", 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))

    summary = {
        "total_candidates": len(kept),
        "tiered_pool_before_cap": len(pool),
        "pool_file": "tools/fame/raw/audience_pool.json",
        "pool_family_breakdown": tally(lambda c: c["primary_family"], pool),
        "pool_new": sum(1 for c in pool if c["is_new"]),
        "new_vs_existing": {
            "new": sum(1 for c in kept if c["is_new"]),
            "already_known": sum(1 for c in kept if not c["is_new"]),
        },
        "recognition_tier": tally(lambda c: c["recognition_tier"], kept),
        "primary_family": tally(lambda c: c["primary_family"], kept),
        "region": tally(lambda c: c["region"], kept),
        "era": tally(lambda c: c["era"], kept),
        "journey_class": tally(lambda c: c["journey_class"], kept),
        "by_source": tally(lambda c: "+".join(c["sources"]), kept),
        "coordinates": {
            "both_endpoints": sum(1 for c in kept if c["journey_km"] is not None),
            "birth_only": sum(1 for c in kept
                              if c["birth_lat"] is not None and c["death_lat"] is None),
            "neither": sum(1 for c in kept
                           if c["birth_lat"] is None and c["death_lat"] is None),
            "real_journey_100km_plus": sum(
                1 for c in kept if (c["journey_km"] or 0) >= 100),
        },
        "images": {
            "wikidata_p18": sum(1 for c in kept if c["has_wikidata_image"]),
            "enwiki_lead": sum(1 for c in kept if c["has_enwiki_image"]),
            "either": sum(1 for c in kept if c["has_image"]),
        },
        "excluded": {
            "died_since_%d" % RECENT_DEATH_CUTOFF: len(recent),
            "specialist_tier": len(specialists),
            "living": len(living),
            "living_politicians": len(living_politicians),
            "non_human_items": len(non_human),
        },
        # Recorded, deliberately not an optimisation target (see module
        # docstring): gender is never used to select, rank or quota.
        "gender_recorded_not_targeted": tally(lambda c: c["gender"], kept),
    }

    payload = {
        "generatedOn": GENERATED_ON,
        "generator": "tools/fame/harvest_audience.py",
        "audience": "Rest Is History listeners -- curious, Anglophone, "
                    "well-read, not academic",
        "optimisation_target": "subject-matter variety (the launch review's "
                               "complaint was a narrow month: rulers, "
                               "commanders, clergy, war, religion, death). "
                               "Gender is recorded, never selected on.",
        "network": net,
        "region_table": _REGION_SOURCE,
        "limit_scale": args.limit_scale,
        "sources": {sid: {"description": raws[sid]["description"],
                          "rows": raws[sid]["n_rows"],
                          "distinct_people": raws[sid]["n_distinct"],
                          "errors": raws[sid]["errors"]}
                    for sid in raws},
        "dedupe_inputs": counts,
        "summary": summary,
        "candidates": kept,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                           encoding="utf-8")

    print(f"\nWROTE {OUTPUT_PATH.relative_to(REPO_ROOT)}: {len(kept)} candidates "
          f"({summary['new_vs_existing']['new']} new)", file=sys.stderr)
    print(f"  tiers: {summary['recognition_tier']}", file=sys.stderr)
    print(f"  families: {summary['primary_family']}", file=sys.stderr)
    print(f"  HTTP: sparql={STATS['sparql']} (cached {STATS['sparql_cached']}) "
          f"api={STATS['api']} (cached {STATS['api_cached']}) "
          f"retries={STATS['retries']} elapsed={time.monotonic() - t_start:.0f}s",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
