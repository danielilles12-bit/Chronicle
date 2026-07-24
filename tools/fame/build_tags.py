#!/usr/bin/env python3
"""
build_tags.py -- builds tools/fame/tags.json, the shared tagging layer
(era / region / occupation_family / kind) for the Dead Famous content
pipeline. Covers universe_people.json (4,000), universe_objects.json
(2,219) and metrics_input_wave3.json (78 = 20 people + 58 objects).

Python 3.9 stdlib only. Read-only against data/, js/, existing scripts and
metrics_*.jsonl. Only writes tools/fame/tags.json and a new cache
directory tools/fame/cache/wikidata_tags/ (own cache, never touches the
image_probe/ or wikidata_death/ caches it reads from).

ERA BUCKETS: ancient (<500 CE), medieval (500-1449), early-modern
(1450-1799), nineteenth (1800-1899), twentieth (1900-1988),
contemporary (1989+).

People era: bucket by min(death_year, birth_year+40) when birth_year is
known, else death_year alone.
Objects era: bucket by Wikidata P571 (inception) year; fallback to the
existing coarse era_hint (universe_objects.json) or codex/02 era text
(wave3 objects); else null.

People region: Pantheon bplace_country (person_2025_update.csv.bz2,
matched by QID) mapped to a 10-value macroregion scheme finer than
regions.py's; wave3 people fall back to codex/01's region column (no
Pantheon row for wave3 titles).
Objects region: Wikidata P17 (country) -> label -> same macroregion
table; falls back to universe_objects.json's own (coarser) region field,
or codex/02's region column for wave3 objects.

Networking: batched wbgetentities (props=claims, 50/batch) against
wikidata.org, throttled to <=8 req/s, UA "DeadFamousIntake/1.0
(daniel.illes12@gmail.com)". Before fetching anything fresh, reuses:
  - cache/image_probe/state/qid_map.json for title->QID (objects+wave3;
    fully populated already, so this script makes zero title->QID calls).
  - cache/image_probe/raw/*.json for already-cached wbgetentities
    props=claims responses (probe_images.py runs concurrently and shares
    the same QID universe for large parts of it).
  - cache/wikidata_death/claims/<sha1(qid)>.json for a pre-computed P570
    death year (gap_report.py's cache; small, checked as a shortcut).
Anything still missing is fetched fresh and cached under
cache/wikidata_tags/claims/<sha1(qid)>.json so reruns are free.
"""
import bz2
import csv
import glob
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import regions as regions_mod

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "cache")
OWN_CACHE_DIR = os.path.join(CACHE_DIR, "wikidata_tags")
OWN_CLAIMS_DIR = os.path.join(OWN_CACHE_DIR, "claims")
OWN_LABELS_DIR = os.path.join(OWN_CACHE_DIR, "labels")
IMAGE_PROBE_RAW_DIR = os.path.join(CACHE_DIR, "image_probe", "raw")
IMAGE_PROBE_STATE_DIR = os.path.join(CACHE_DIR, "image_probe", "state")
WIKIDATA_DEATH_CLAIMS_DIR = os.path.join(CACHE_DIR, "wikidata_death", "claims")

UNIVERSE_PEOPLE_PATH = os.path.join(HERE, "universe_people.json")
UNIVERSE_OBJECTS_PATH = os.path.join(HERE, "universe_objects.json")
WAVE3_PATH = os.path.join(HERE, "metrics_input_wave3.json")
PANTHEON_BZ2 = os.path.join(HERE, "raw", "person_2025_update.csv.bz2")
CODEX_FIGURES_CSV = os.path.join(HERE, "codex", "01_dead_famous_figures.csv")
CODEX_OBJECTS_CSV = os.path.join(HERE, "codex", "02_dead_famous_objects.csv")
OUT_PATH = os.path.join(HERE, "tags.json")

UA = "DeadFamousIntake/1.0 (daniel.illes12@gmail.com)"
WD_API = "https://www.wikidata.org/w/api.php"
MIN_INTERVAL = 1.0 / 8.0  # <= 8 req/s
BATCH_SIZE = 50
_last_ts = [0.0]

STATS = {
    "requests": 0,
    "cache_hits_own": 0,
    "cache_hits_image_probe": 0,
    "cache_hits_wikidata_death": 0,
}


# ---------------------------------------------------------------------------
# Low-level networking: throttle, retry/backoff, own on-disk cache
# ---------------------------------------------------------------------------

def _throttle():
    now = time.monotonic()
    wait = MIN_INTERVAL - (now - _last_ts[0])
    if wait > 0:
        time.sleep(wait)
    _last_ts[0] = time.monotonic()


def _hash(key):
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def wd_get(params):
    qs = urllib.parse.urlencode(params, safe="|")
    url = f"{WD_API}?{qs}"
    backoff = 1.0
    last_exc = None
    for attempt in range(6):
        _throttle()
        STATS["requests"] += 1
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_exc = e
            if e.code not in (429, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError) as e:
            last_exc = e
        time.sleep(backoff)
        backoff = min(backoff * 2, 30)
    raise RuntimeError(f"wikidata request failed after retries: {last_exc}")


def _own_cache_read(dir_path, qid):
    p = os.path.join(dir_path, _hash(qid) + ".json")
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _own_cache_write(dir_path, qid, value):
    os.makedirs(dir_path, exist_ok=True)
    p = os.path.join(dir_path, _hash(qid) + ".json")
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False)
    os.replace(tmp, p)


def load_image_probe_claims_cache():
    """Scan cache/image_probe/raw/*.json once; merge any wbgetentities
    props=claims responses into a qid->claims dict. Read-only reuse of
    another concurrently-running job's cache."""
    merged = {}
    for fp in glob.glob(os.path.join(IMAGE_PROBE_RAW_DIR, "*.json")):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        body = d.get("body") if isinstance(d, dict) else None
        if not isinstance(body, dict):
            continue
        entities = body.get("entities")
        if not isinstance(entities, dict):
            continue
        for qid, ent in entities.items():
            if isinstance(ent, dict) and "claims" in ent and qid not in merged:
                merged[qid] = ent["claims"]
    return merged


def wikidata_death_shortcut(qid):
    """Direct hit against gap_report.py's cache/wikidata_death/claims/
    (keyed by sha1(qid), value {"death_year": int|None}). Returns
    (found, death_year_or_None)."""
    p = os.path.join(WIKIDATA_DEATH_CLAIMS_DIR, _hash(qid) + ".json")
    if not os.path.exists(p):
        return False, None
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False, None
    STATS["cache_hits_wikidata_death"] += 1
    return True, d.get("death_year")


def fetch_claims_for_qids(qids, image_probe_cache):
    """qid -> claims dict. Checks own cache, then the merged image_probe
    cache, then fetches fresh in batches of 50 (cached for next run)."""
    result = {}
    to_fetch = []
    seen = set()
    for q in qids:
        if q is None or q in seen:
            continue
        seen.add(q)
        cached = _own_cache_read(OWN_CLAIMS_DIR, q)
        if cached is not None:
            result[q] = cached
            STATS["cache_hits_own"] += 1
            continue
        if q in image_probe_cache:
            result[q] = image_probe_cache[q]
            STATS["cache_hits_image_probe"] += 1
            continue
        to_fetch.append(q)

    for i in range(0, len(to_fetch), BATCH_SIZE):
        batch = to_fetch[i:i + BATCH_SIZE]
        data = wd_get({
            "action": "wbgetentities", "ids": "|".join(batch),
            "props": "claims", "format": "json",
        })
        entities = data.get("entities") or {}
        for q in batch:
            ent = entities.get(q) or {}
            claims = ent.get("claims") or {}
            result[q] = claims
            _own_cache_write(OWN_CLAIMS_DIR, q, claims)
    return result


def fetch_labels_for_qids(qids):
    """qid -> English label, own-cached."""
    result = {}
    to_fetch = []
    seen = set()
    for q in qids:
        if q is None or q in seen:
            continue
        seen.add(q)
        cached = _own_cache_read(OWN_LABELS_DIR, q)
        if cached is not None:
            result[q] = cached.get("label")
            STATS["cache_hits_own"] += 1
        else:
            to_fetch.append(q)

    for i in range(0, len(to_fetch), BATCH_SIZE):
        batch = to_fetch[i:i + BATCH_SIZE]
        data = wd_get({
            "action": "wbgetentities", "ids": "|".join(batch),
            "props": "labels", "languages": "en", "format": "json",
        })
        entities = data.get("entities") or {}
        for q in batch:
            ent = entities.get(q) or {}
            label = (ent.get("labels") or {}).get("en", {}).get("value")
            result[q] = label
            _own_cache_write(OWN_LABELS_DIR, q, {"label": label})
    return result


# ---------------------------------------------------------------------------
# Wikidata claim value extraction
# ---------------------------------------------------------------------------

def wd_time_year(claims, prop):
    for claim in (claims.get(prop) or []):
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


def wd_item_id(claims, prop):
    for claim in (claims.get(prop) or []):
        try:
            return claim["mainsnak"]["datavalue"]["value"]["id"]
        except (KeyError, TypeError):
            continue
    return None


# ---------------------------------------------------------------------------
# Era bucketing
# ---------------------------------------------------------------------------

def era_for_year(year):
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


ERA_HINT_TO_BUCKET = {
    "ancient": "ancient",
    "classical": "ancient",
    "medieval": "medieval",
    "early-modern": "early-modern",
    # "modern" deliberately excluded -- too vague per task spec.
}


def era_from_codex_range(era_text):
    """Best-effort era bucket from a free-text codex era column (e.g.
    '20th century', '18th-19th centuries', 'Early modern', 'Renaissance').
    Used only as a fallback for wave3 objects when P571 is absent. Takes
    the EARLIEST century mentioned (closest to an object's inception)."""
    if not era_text:
        return None
    s = era_text.strip().lower()
    named = {
        "prehistoric": "ancient",
        "ancient": "ancient",
        "ancient to modern": "ancient",
        "ancient to early modern": "ancient",
        "medieval": "medieval",
        "medieval and renaissance": "medieval",
        "medieval to early modern": "medieval",
        "medieval and early modern": "medieval",
        "medieval to modern": "medieval",
        "renaissance": "early-modern",
        "renaissance and early modern": "early-modern",
        "early modern": "early-modern",
    }
    if s in named:
        return named[s]
    # ordinal-century forms, e.g. "20th century", "18th-19th centuries"
    import re
    nums = re.findall(r"(\d+)(?:st|nd|rd|th)", s)
    if nums:
        century = int(nums[0])
        # take the first (earliest) century in the range; a "20th century"
        # object was completed in [1901,2000] -- approximate with year 1901
        # for bucketing purposes (matches the century's own bucket in all
        # of our bucket boundaries except the ancient/medieval split, which
        # no century-form string can land on anyway).
        approx_year = (century - 1) * 100 + 1
        return era_for_year(approx_year)
    return None


# ---------------------------------------------------------------------------
# Macroregion tables
#
# Target set: Europe, East Asia, South Asia, Southeast Asia,
# Middle East & North Africa, Sub-Saharan Africa, North America,
# Latin America & Caribbean, Oceania, Central Asia & Russia.
#
# Derived from regions.py's COUNTRY_REGION (reused, not reinvented) via a
# systematic remap, with the specific overrides the groundwork specifies:
# Turkiye -> MENA, Georgia/Armenia/Azerbaijan/Mongolia/Afghanistan ->
# Central Asia & Russia, Greenland/Bermuda -> North America, Caribbean
# territories -> Latin America & Caribbean. Additionally (judgment calls,
# noted in the final report): Russia itself -> Central Asia & Russia (the
# bucket name pairs them); regions.py's undifferentiated "Africa" is split
# along the UN Northern-Africa list into MENA vs Sub-Saharan Africa;
# regions.py's "North America" bucket (which bundles in Mexico/Central
# America/Caribbean) is split so true North America is just
# US/Canada/Bermuda/Greenland and the rest move to Latin America &
# Caribbean; "South America" folds into Latin America & Caribbean.
# ---------------------------------------------------------------------------

OLD_BUCKET_DEFAULT = {
    "Europe": "Europe",
    "Middle East": "Middle East & North Africa",
    "Central Asia": "Central Asia & Russia",
    "South Asia": "South Asia",
    "East Asia": "East Asia",
    "Southeast Asia": "Southeast Asia",
    "Africa": "Sub-Saharan Africa",
    "North America": "Latin America & Caribbean",
    "South America": "Latin America & Caribbean",
    "Oceania": "Oceania",
}

NORTH_AFRICA_COUNTRIES = {
    "Algeria", "Egypt", "Libya", "Morocco", "Sudan", "Tunisia",
}

TRUE_NORTH_AMERICA = {"Canada", "United States", "United States of America"}

MOVE_TO_CENTRAL_ASIA_RUSSIA = {"Georgia", "Armenia", "Azerbaijan", "Russia"}


def build_country_to_macroregion():
    table = {}
    all_country_dicts = [regions_mod.COUNTRY_REGION]
    for d in all_country_dicts:
        for name, old_bucket in d.items():
            if name in NORTH_AFRICA_COUNTRIES:
                table[name] = "Middle East & North Africa"
            elif name in MOVE_TO_CENTRAL_ASIA_RUSSIA:
                table[name] = "Central Asia & Russia"
            elif old_bucket == "North America":
                table[name] = ("North America" if name in TRUE_NORTH_AMERICA
                                else "Latin America & Caribbean")
            else:
                table[name] = OLD_BUCKET_DEFAULT[old_bucket]
    # Names not present in regions.py at all, needed for our data.
    table["Greenland"] = "North America"
    table["Bermuda"] = "North America"
    table["Türkiye"] = "Middle East & North Africa"
    table["Myanmar (Burma)"] = "Southeast Asia"
    table["Hong Kong"] = "East Asia"
    table["Macau"] = "East Asia"
    table["Isle of Man"] = "Europe"
    table["Faroe Islands"] = "Europe"
    table["Kosovo"] = "Europe"
    table["Monaco"] = "Europe"
    table["Puerto Rico"] = "Latin America & Caribbean"
    table["U.S. Virgin Islands"] = "Latin America & Caribbean"
    table["Cabo Verde"] = "Sub-Saharan Africa"
    table["Cape Verde"] = "Sub-Saharan Africa"
    table["Réunion"] = "Sub-Saharan Africa"
    table["The Bahamas"] = "Latin America & Caribbean"
    table["Czech Republic"] = "Europe"
    table["Ivory Coast"] = "Sub-Saharan Africa"
    table["United States of America"] = "North America"
    table["Republic of Korea"] = "East Asia"
    table["Korea"] = "East Asia"
    table["Kingdom of the Netherlands"] = "Europe"
    table["Vatican City"] = "Europe"
    table["Holy See"] = "Europe"
    return table


COUNTRY_TO_MACROREGION = build_country_to_macroregion()

# Historical polities / former states / city fallbacks that show up as
# Wikidata P17/P131 values for older objects, hand-mapped to the finer
# macroregion scheme (not derived from regions.py's own aliases, since a
# handful of those need a different bucket here -- e.g. Aztec/Inca move
# from "North America"/"South America" into Latin America & Caribbean,
# Russian Empire/Soviet Union/Moscow move from Europe into Central Asia &
# Russia alongside modern Russia).
HISTORICAL_OR_CITY_ALIASES = {
    "British Empire": "Europe", "Kingdom of England": "Europe",
    "Kingdom of Great Britain": "Europe", "German Reich": "Europe",
    "Weimar Republic": "Europe", "Nazi Germany": "Europe",
    "East Germany": "Europe", "West Germany": "Europe",
    "Kingdom of Italy": "Europe", "Kingdom of France": "Europe",
    "Kingdom of Spain": "Europe", "Kingdom of Prussia": "Europe",
    "Austria-Hungary": "Europe", "Austrian Empire": "Europe",
    "Holy Roman Empire": "Europe", "Republic of Venice": "Europe",
    "Grand Duchy of Tuscany": "Europe", "Kingdom of Poland": "Europe",
    "Polish People's Republic": "Europe", "Czechoslovakia": "Europe",
    "Yugoslavia": "Europe", "Byzantine Empire": "Europe",
    "Russian Empire": "Central Asia & Russia",
    "Soviet Union": "Central Asia & Russia",
    "Ottoman Empire": "Middle East & North Africa",
    "Persian Empire": "Middle East & North Africa",
    "Achaemenid Empire": "Middle East & North Africa",
    "Sasanian Empire": "Middle East & North Africa",
    "Mamluk Sultanate": "Middle East & North Africa",
    "Ancient Egypt": "Middle East & North Africa",
    "People's Republic of China": "East Asia",
    "Republic of China": "East Asia", "Qing dynasty": "East Asia",
    "Ming dynasty": "East Asia", "Empire of Japan": "East Asia",
    "Joseon": "East Asia", "Khmer Empire": "Southeast Asia",
    "Dutch East Indies": "Southeast Asia",
    "British Raj": "South Asia", "Mughal Empire": "South Asia",
    "Federated States of Micronesia": "Oceania",
    "Confederate States of America": "North America",
    "New Spain": "Latin America & Caribbean",
    "New France": "North America",
    "Inca Empire": "Latin America & Caribbean",
    "Aztec Empire": "Latin America & Caribbean",
    "Kingdom of Kush": "Sub-Saharan Africa",
    "Aksumite Empire": "Sub-Saharan Africa",
    "New York City": "North America", "London": "Europe",
    "Paris": "Europe", "Beijing": "East Asia", "Tokyo": "East Asia",
    "Moscow": "Central Asia & Russia", "Rome": "Europe",
    "Cairo": "Middle East & North Africa",
    "Washington, D.C.": "North America",
}


def region_for_country_label(label):
    if not label:
        return None
    label = label.strip()
    if label in COUNTRY_TO_MACROREGION:
        return COUNTRY_TO_MACROREGION[label]
    if label in HISTORICAL_OR_CITY_ALIASES:
        return HISTORICAL_OR_CITY_ALIASES[label]
    if label.lower().startswith("the "):
        stripped = label[4:]
        if stripped in COUNTRY_TO_MACROREGION:
            return COUNTRY_TO_MACROREGION[stripped]
        if stripped in HISTORICAL_OR_CITY_ALIASES:
            return HISTORICAL_OR_CITY_ALIASES[stripped]
    return None


# codex/01 & codex/02 free-text "region" columns, exact strings observed
# among the wave3 rows -> macroregion. Compound "X and Y" strings are
# resolved by primary/birthplace-or-origin judgment (documented per row
# in the final report), not a blind first-token split.
CODEX_PEOPLE_REGION_TO_MACRO = {
    "East Asia": "East Asia",
    "North America": "North America",
    "North America and Latin America": "North America",   # Selena, Texas-born
    "Oceania and North America": "Oceania",                # Heath Ledger, Australian-born
    "South Asia": "South Asia",
    "Sub-Saharan Africa": "Sub-Saharan Africa",
}

CODEX_OBJECT_REGION_TO_MACRO = {
    "East Asia": "East Asia",
    "Europe": "Europe",
    "Europe and North Asia": "Europe",           # Church of the Savior on Blood, St Petersburg
    "Latin America and Caribbean": "Latin America & Caribbean",
    "Middle East and North Africa": "Middle East & North Africa",
    "North America": "North America",
    "North America and Europe": "North America",  # Whistler's Mother, American-born artist
    "North America and space": "North America",   # Voyager Golden Record, launched from the US
    "South Asia": "South Asia",
    "Southeast Asia": "Southeast Asia",
}


# ---------------------------------------------------------------------------
# Occupation -> occupation_family (Pantheon "occupation" column, the 71
# distinct values actually present among our 4,000-person universe).
# Target families: ruler, statesman, military, religious, philosopher,
# writer, artist, composer, performer, scientist, inventor-engineer,
# explorer, activist-reformer, athlete, business, other.
# ---------------------------------------------------------------------------

OCCUPATION_TO_FAMILY = {
    # -- given decisions --
    "POLITICIAN": "statesman",
    "NOBLEMAN": "ruler",
    "ASTRONAUT": "explorer",
    "COMPANION": "other",
    "MAFIOSO": "other",
    "PIRATE": "other",
    "EXTREMIST": "other",
    "ECONOMIST": "scientist",
    "PHYSICIAN": "scientist",
    "PILOT": "other",
    # -- remaining 61 values, mapped here --
    "RELIGIOUS FIGURE": "religious",
    "WRITER": "writer",
    "PHILOSOPHER": "philosopher",
    "PAINTER": "artist",
    "PHYSICIST": "scientist",
    "MILITARY PERSONNEL": "military",
    "COMPOSER": "composer",
    "ACTOR": "performer",
    "CHEMIST": "scientist",
    "MATHEMATICIAN": "scientist",
    "SOCIAL ACTIVIST": "activist-reformer",
    "INVENTOR": "inventor-engineer",
    "SINGER": "performer",
    "EXPLORER": "explorer",
    "BIOLOGIST": "scientist",
    "MUSICIAN": "performer",
    "HISTORIAN": "writer",
    "FILM DIRECTOR": "artist",
    "ASTRONOMER": "scientist",
    "BUSINESSPERSON": "business",
    "ARCHITECT": "artist",
    "PSYCHOLOGIST": "scientist",
    "SOCCER PLAYER": "athlete",
    "SCULPTOR": "artist",
    "LINGUIST": "scientist",
    "DIPLOMAT": "statesman",
    "OCCULTIST": "other",
    "CELEBRITY": "other",
    "ARTIST": "artist",
    "ENGINEER": "inventor-engineer",
    "CHESS PLAYER": "athlete",
    "GEOGRAPHER": "scientist",
    "LAWYER": "other",
    "FASHION DESIGNER": "artist",
    "DESIGNER": "artist",
    "SOCIOLOGIST": "scientist",
    "DANCER": "performer",
    "PUBLIC WORKER": "other",
    "RACING DRIVER": "athlete",
    "ARCHAEOLOGIST": "scientist",
    "COMIC ARTIST": "artist",
    "JOURNALIST": "writer",
    "ATHLETE": "athlete",
    "MARTIAL ARTS": "athlete",
    "CONDUCTOR": "performer",
    "BOXER": "athlete",
    "INSPIRATION": "other",
    "COMPUTER SCIENTIST": "scientist",
    "ANTHROPOLOGIST": "scientist",
    "GEOLOGIST": "scientist",
    "PHOTOGRAPHER": "artist",
    "JUDGE": "statesman",
    "MOUNTAINEER": "explorer",
    "COACH": "athlete",
    "PRODUCER": "artist",
    "COMEDIAN": "performer",
    "MAGICIAN": "performer",
    "AMERICAN FOOTBALL PLAYER": "athlete",
    "POLITICAL SCIENTIST": "scientist",
    "CRICKETER": "athlete",
    "SWIMMER": "athlete",
}

# codex/01 "category" column for the 20 wave3 people -- compound strings
# resolved by primary (first-listed) role.
CODEX_PEOPLE_CATEGORY_TO_FAMILY = {
    "photographer": "artist",
    "actor and writer": "performer",
    "musician": "performer",
    "religious leader and activist": "religious",
    "musician and activist": "performer",
    "actor and dancer": "performer",
    "artist": "artist",
    "actor": "performer",
    "athlete": "athlete",
    "religious founder and writer": "religious",
    "singer": "performer",
    "actor and comedian": "performer",
    "singer and activist": "performer",
}


# codex/02 "category" column for the 58 wave3 objects, mapped onto
# universe_objects.json's controlled "kind" vocabulary (site, building,
# artefact, manuscript, painting, sculpture, monument).
CODEX_OBJECT_CATEGORY_TO_KIND = {
    "architecture": "building",
    "monument": "monument",
    "sculpture": "sculpture",
    "painting": "painting",
    "painting series": "painting",
    "print": "painting",
    "vehicle": "artefact",
    "aircraft": "artefact",
    "ship": "artefact",
    "weapon": "artefact",
    "spacecraft": "artefact",
    "computer": "artefact",
    "rocket": "artefact",
    "tower": "building",
    "tower and clock": "building",
    "bridge": "building",
    "fortification": "building",
    "infrastructure": "building",
    "infrastructure and monument": "monument",
    "textile artwork": "artefact",
    "land art": "site",
    "cave art": "site",
    "landscape architecture": "site",
    "religious structure": "building",
    "locomotive": "artefact",
    "airship": "artefact",
    "archaeological site": "site",
    "sculpture and archaeological site": "site",
    "sculpture and monument": "monument",
    "sign": "artefact",
    "architecture and artwork": "building",
}


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_pantheon_by_qid(qids_needed):
    by_qid = {}
    with bz2.open(PANTHEON_BZ2, "rt", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            q = row.get("wd_id")
            if q in qids_needed:
                by_qid[q] = row
    return by_qid


def load_codex_csv(path):
    by_title = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            t = row.get("exact_english_wikipedia_article_title")
            if t and t not in by_title:
                by_title[t] = row
    return by_title


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    print("Loading inputs...", file=sys.stderr)
    people_data = load_json(UNIVERSE_PEOPLE_PATH)
    universe_people = people_data["people"]
    objects_data = load_json(UNIVERSE_OBJECTS_PATH)
    universe_objects = objects_data["objects"]
    wave3 = load_json(WAVE3_PATH)
    codex_figures = load_codex_csv(CODEX_FIGURES_CSV)
    codex_objects = load_codex_csv(CODEX_OBJECTS_CSV)
    qid_map = load_json(os.path.join(IMAGE_PROBE_STATE_DIR, "qid_map.json"))

    wave3_titles = {w["wiki_title"] for w in wave3}
    wave3_people_rows = [w for w in wave3 if w["wiki_title"] in codex_figures]
    wave3_object_rows = [w for w in wave3 if w["wiki_title"] in codex_objects]
    print(f"wave3: {len(wave3_people_rows)} people, {len(wave3_object_rows)} "
          f"objects (of {len(wave3)} total)", file=sys.stderr)

    people_out = {}
    objects_out = {}

    # -----------------------------------------------------------------
    # PEOPLE: universe_people.json (4,000) via Pantheon
    # -----------------------------------------------------------------
    qids_needed = {p["qid"] for p in universe_people}
    print(f"Loading Pantheon CSV, matching {len(qids_needed)} QIDs...",
          file=sys.stderr)
    pantheon_by_qid = load_pantheon_by_qid(qids_needed)
    print(f"Pantheon matches: {len(pantheon_by_qid)}/{len(qids_needed)}",
          file=sys.stderr)

    unmapped_occupations = set()
    for p in universe_people:
        title = p["wiki_title"]
        birth_year = p.get("birth_year")
        death_year = p.get("death_year")
        era = era_for_person(birth_year, death_year)

        prow = pantheon_by_qid.get(p["qid"])
        region = None
        occupation_family = None
        if prow is not None:
            country = (prow.get("bplace_country") or "").strip()
            region = region_for_country_label(country) if country else None
            occ = (prow.get("occupation") or "").strip()
            if occ:
                occupation_family = OCCUPATION_TO_FAMILY.get(occ)
                if occupation_family is None:
                    unmapped_occupations.add(occ)
                    occupation_family = "other"

        people_out[title] = {
            "era": era,
            "region": region,
            "occupation_family": occupation_family,
            "death_year": death_year,
        }

    if unmapped_occupations:
        print(f"WARNING: unmapped Pantheon occupations (defaulted to "
              f"'other'): {sorted(unmapped_occupations)}", file=sys.stderr)

    # -----------------------------------------------------------------
    # OBJECTS: universe_objects.json (2,219) via Wikidata P571/P17
    # -----------------------------------------------------------------
    print("Loading image_probe raw cache for claims reuse...", file=sys.stderr)
    image_probe_claims = load_image_probe_claims_cache()
    print(f"image_probe cache covers {len(image_probe_claims)} QIDs so far",
          file=sys.stderr)

    def qid_for_title(title):
        entry = qid_map.get(title)
        return entry.get("qid") if entry else None

    all_object_rows = list(universe_objects) + [
        {
            "name": w["name"], "wiki_title": w["wiki_title"],
            "kind": None, "region": None, "era_hint": None,
            "_wave3": True,
        }
        for w in wave3_object_rows
    ]

    object_qids = {}
    for row in all_object_rows:
        q = qid_for_title(row["wiki_title"])
        object_qids[row["wiki_title"]] = q

    print(f"Fetching/reusing claims for {len(all_object_rows)} objects...",
          file=sys.stderr)
    obj_claims = fetch_claims_for_qids(
        [q for q in object_qids.values() if q], image_probe_claims)

    # collect P17 target QIDs needing an English label
    country_qids_needed = set()
    for title, q in object_qids.items():
        claims = obj_claims.get(q, {}) if q else {}
        loc_qid = wd_item_id(claims, "P17")
        if loc_qid:
            country_qids_needed.add(loc_qid)
    print(f"Resolving labels for {len(country_qids_needed)} P17 location "
          f"QIDs...", file=sys.stderr)
    country_labels = fetch_labels_for_qids(country_qids_needed)

    for row in all_object_rows:
        title = row["wiki_title"]
        is_wave3 = row.get("_wave3", False)
        q = object_qids.get(title)
        claims = obj_claims.get(q, {}) if q else {}

        inception_year = wd_time_year(claims, "P571")
        era = era_for_year(inception_year)
        if era is None:
            if is_wave3:
                codex_row = codex_objects.get(title)
                era = era_from_codex_range(codex_row.get("era")) if codex_row else None
            else:
                era = ERA_HINT_TO_BUCKET.get(row.get("era_hint"))

        loc_qid = wd_item_id(claims, "P17")
        region = region_for_country_label(country_labels.get(loc_qid)) if loc_qid else None
        if region is None:
            if is_wave3:
                codex_row = codex_objects.get(title)
                codex_region = codex_row.get("region") if codex_row else None
                region = CODEX_OBJECT_REGION_TO_MACRO.get(codex_region)
            else:
                region = row.get("region")  # existing coarser region, verbatim

        if is_wave3:
            codex_row = codex_objects.get(title)
            codex_cat = (codex_row.get("category") if codex_row else None)
            kind = CODEX_OBJECT_CATEGORY_TO_KIND.get(codex_cat)
        else:
            kind = row.get("kind")

        objects_out[title] = {"era": era, "region": region, "kind": kind}

    # -----------------------------------------------------------------
    # PEOPLE: wave3 (20) -- death_year via P570, occupation_family from
    # codex/01 category, region from codex/01 region.
    # -----------------------------------------------------------------
    print(f"Resolving death years for {len(wave3_people_rows)} wave3 "
          f"people...", file=sys.stderr)
    wave3_qids = {w["wiki_title"]: qid_for_title(w["wiki_title"])
                  for w in wave3_people_rows}

    need_network_claims = []
    death_year_by_title = {}
    for title, q in wave3_qids.items():
        if q is None:
            death_year_by_title[title] = None
            continue
        found, dy = wikidata_death_shortcut(q)
        if found:
            death_year_by_title[title] = dy
        else:
            need_network_claims.append(q)

    if need_network_claims:
        extra_claims = fetch_claims_for_qids(need_network_claims, image_probe_claims)
        for title, q in wave3_qids.items():
            if title in death_year_by_title:
                continue
            claims = extra_claims.get(q, {}) if q else {}
            death_year_by_title[title] = wd_time_year(claims, "P570")

    for w in wave3_people_rows:
        title = w["wiki_title"]
        death_year = death_year_by_title.get(title)
        era = era_for_person(None, death_year)

        codex_row = codex_figures.get(title)
        occupation_family = None
        region = None
        if codex_row is not None:
            occupation_family = CODEX_PEOPLE_CATEGORY_TO_FAMILY.get(codex_row.get("category"))
            region = CODEX_PEOPLE_REGION_TO_MACRO.get(codex_row.get("region"))

        people_out[title] = {
            "era": era,
            "region": region,
            "occupation_family": occupation_family,
            "death_year": death_year,
        }

    # -----------------------------------------------------------------
    # Coverage + write
    # -----------------------------------------------------------------
    def coverage(rows, fields):
        out = {}
        for field in fields:
            filled = sum(1 for r in rows.values() if r.get(field) is not None)
            out[field] = {"filled": filled, "null": len(rows) - filled}
        return out

    coverage_out = {
        "people": coverage(people_out, ["era", "region", "occupation_family", "death_year"]),
        "objects": coverage(objects_out, ["era", "region", "kind"]),
        "people_total": len(people_out),
        "objects_total": len(objects_out),
    }

    output = {
        "generatedOn": "2026-07-23",
        "people": people_out,
        "objects": objects_out,
        "coverage": coverage_out,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=1, sort_keys=True)

    print(f"\nWrote {OUT_PATH}", file=sys.stderr)
    print(json.dumps(coverage_out, indent=2), file=sys.stderr)
    print(f"Wikidata requests: {STATS['requests']}, own-cache hits: "
          f"{STATS['cache_hits_own']}, image_probe reuses: "
          f"{STATS['cache_hits_image_probe']}, wikidata_death reuses: "
          f"{STATS['cache_hits_wikidata_death']}", file=sys.stderr)


if __name__ == "__main__":
    main()
