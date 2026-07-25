#!/usr/bin/env python3
"""
build_salience.py -- HISTORY-LOVER SALIENCE index for the Dead Famous
content pipeline.

Complementary to (never a replacement for) tools/fame/build_scores.py's
`fame` score. `fame` measures GENERAL-POPULATION popularity: it is
0.50*pageviews + 0.15*languages + 0.10*inlinks + 0.25*cross-language-family
consensus, and it is dominated by casual lookup traffic. That is the right
instrument for the easy tier and the wrong one for the hard tier: this
game's audience is history enthusiasts ("Rest Is History listeners"), who
recognise Belisarius, Stilicho, the Gracchi, Mithridates and Brunel far
better than raw pageviews imply.

`salience` estimates: *how well does a keen amateur historian know this?*

Usage
-----
    python3 build_salience.py                 # harvest (cached) + score
    python3 build_salience.py --offline       # local cache/metrics only
    python3 build_salience.py --out other.json
    python3 build_salience.py --probe-projects 400
        (discovery mode: enumerate the WikiProject names that actually
         appear across a sample of the universe, so the curated
         HISTORY_PROJECTS list below can be checked against reality.)

Signals
-------
S1 record_density   (local, free)  log-inlinks residual vs log-pageviews.
S2 depth            (1 API call/50) log-article-length residual vs pageviews.
S3 history_importance (1 API call/50) English Wikipedia PageAssessments:
                    per-WikiProject class + importance, restricted to
                    history-flavoured projects. Domain editors judging
                    historical significance, wholly independent of traffic.
S4 vital            (~40 API calls) Wikipedia vital-article level (1-5),
                    restricted to History/People/Arts/Philosophy topics.
S5 iot              (~40 API calls) BBC Radio 4 *In Our Time*: ~1,100
                    curated episodes, the closest public enumeration of
                    "what this exact audience finds interesting".

Everything is written to tools/fame/salience.json with each component kept
separate so the blend stays inspectable and arguable.

Python 3.9 stdlib only. READ-ONLY with respect to data/, js/, and every
existing tools/fame file. Writes only: tools/fame/salience.json and
tools/fame/raw/salience_*.json (HTTP cache).
"""

import argparse
import collections
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

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
RAW_DIR = SCRIPT_DIR / "raw"

# Same UA family as fetch_metrics.py / wputils.py so enwiki sees one client.
USER_AGENT = "DeadFamousIntake/1.0 (daniel.illes12@gmail.com)"
EN_API = "https://en.wikipedia.org/w/api.php"

RATE_PER_SEC = 8.0
MIN_INTERVAL = 1.0 / RATE_PER_SEC
MAX_RETRIES = 5
TIMEOUT_SECONDS = 60

GENERATED_ON = "2026-07-25"

_last_request = [0.0]
STATS = {"requests": 0, "cache_hits": 0, "retries": 0}


# ---------------------------------------------------------------------------
# HTTP: throttle + retry + on-disk cache under raw/salience_<sha1>.json
# ---------------------------------------------------------------------------

def _throttle():
    now = time.monotonic()
    wait = _last_request[0] + MIN_INTERVAL - now
    if wait > 0:
        time.sleep(wait)
    _last_request[0] = time.monotonic()


def _cache_path(url):
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return RAW_DIR / ("salience_" + h + ".json")


def fetch_json(url, offline=False):
    path = _cache_path(url)
    if path.exists():
        try:
            STATS["cache_hits"] += 1
            return json.loads(path.read_text(encoding="utf-8"))["body"]
        except (OSError, json.JSONDecodeError, KeyError):
            pass
    if offline:
        raise RuntimeError("offline mode and no cache entry for: " + url)

    backoff = 1.0
    for attempt in range(1, MAX_RETRIES + 1):
        _throttle()
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                body = json.loads(resp.read().decode("utf-8", errors="replace"))
            STATS["requests"] += 1
            RAW_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"url": url, "body": body}),
                            encoding="utf-8")
            return body
        except (urllib.error.HTTPError, urllib.error.URLError,
                TimeoutError, json.JSONDecodeError) as exc:
            code = getattr(exc, "code", None)
            retryable = code in (429, 500, 502, 503, 504) or code is None
            if attempt == MAX_RETRIES or not retryable:
                raise
            STATS["retries"] += 1
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
    raise RuntimeError("unreachable")


def api(params, offline=False):
    params = dict(params)
    params.setdefault("format", "json")
    params.setdefault("formatversion", "2")
    url = EN_API + "?" + urllib.parse.urlencode(params, safe="|")
    return fetch_json(url, offline=offline)


def api_continue(params, offline=False):
    """Yield successive API responses, following `continue` tokens."""
    params = dict(params)
    seen = 0
    while True:
        data = api(params, offline=offline)
        yield data
        cont = data.get("continue")
        if not cont:
            return
        seen += 1
        if seen > 400:                       # hard stop; nothing here is that big
            return
        params.update(cont)


# ---------------------------------------------------------------------------
# Stats helpers (percentile ranking matches build_scores.py's convention)
# ---------------------------------------------------------------------------

def average_rank_percentiles(values):
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
        avg = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return [(r - 1) / (n - 1) * 100.0 for r in ranks]


def ols_residuals(xs, ys):
    """Residuals of y on x via ordinary least squares. Returns list."""
    n = len(xs)
    if n < 3:
        return [0.0] * n
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 1e-12:
        return [0.0] * n
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    b = sxy / sxx
    a = my - b * mx
    return [ys[i] - (a + b * xs[i]) for i in range(n)]


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 1e-12 or syy <= 1e-12:
        return 0.0
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    return sxy / math.sqrt(sxx * syy)


def norm_name(s):
    s = (s or "").lower()
    s = s.replace("’", "'").replace("‘", "'")
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split()).strip()


# ---------------------------------------------------------------------------
# S3: which WikiProjects count as "history-flavoured"?
#
# Curated from a discovery pass over the live PageAssessments data for this
# universe (`--probe-projects`). Three buckets, because they are not equally
# good evidence that a HISTORY ENTHUSIAST would know the subject:
#
#   CORE     -- general history projects and the big period/era projects.
#               A Top/High here is the strongest single piece of evidence.
#   PERIOD   -- national, regional and thematic history projects, plus the
#               Biography work groups that behave like history projects.
#   WEAK     -- adjacent projects (science, art, religion) that carry real
#               historical signal but also rate plenty of modern subjects.
#
# Matching is on the project string returned by prop=pageassessments, which
# is "Project" or "Project/task force". We match on prefix-before-slash for
# CORE/PERIOD names, and separately allow explicit slash-paths.
# ---------------------------------------------------------------------------

CORE_PROJECTS = {
    # General and period history. A Top/High here is the strongest evidence
    # available that a history enthusiast would place the subject.
    "History", "History of Science", "European history", "Middle Ages",
    "Classical Greece and Rome", "Ancient Egypt", "Ancient Near East",
    "Archaeology", "Byzantine world", "Crusades", "Rome",
    "Roman and Byzantine emperors", "Mesoamerica", "Assyria", "Prehistory",
    "Ancient Germanic studies", "Jewish history", "Cold War",
    "Former countries", "British Empire", "Royalty and Nobility",
    "British Royalty", "English Royalty", "Ottoman Empire", "Soviet Union",
    "American Revolutionary War", "American Civil War", "United States History",
    "Military history", "Pritzker Military Library", "Historic sites",
    "World Heritage Sites", "Indigenous peoples of the Americas",
    "Indigenous peoples of North America", "Civil Rights Movement",
    "Numismatics", "Heraldry and vexillology", "Mongols",
    "Norse history and culture", "Anglo-Saxon Kingdoms", "Phoenicia",
    "Arctic", "Antarctica",
    # WikiProject Military history deliberately abolished importance
    # ratings, so it contributes nothing numeric -- kept here only so the
    # bucket audit reads honestly. Its military biographies are picked up
    # instead through Biography's military biography work group, below.
    # Arctic/Antarctica look like geography projects but are in practice
    # the only home that rates polar explorers (Amundsen, Shackleton,
    # Scott, Franklin) -- omitting them buried the entire heroic age.
}

PERIOD_PROJECTS = {
    # National, regional and thematic projects. Real evidence, but these
    # rate their own nationals generously, so they carry ~0.62 weight.
    "Politics", "International relations", "Women's History", "Anthropology",
    "Egypt", "Greece", "Italy", "France", "Germany", "Spain", "Portugal",
    "Russia", "Ukraine", "China", "Japan", "Korea", "India", "Pakistan",
    "Bangladesh", "Iran", "Iraq", "Syria", "Turkey", "Israel", "Judaism",
    "Arab world", "Afghanistan", "Central Asia", "Southeast Asia", "Asia",
    "East Asia", "Africa", "African diaspora", "South Africa", "Ethiopia",
    "Nigeria", "Mexico", "Peru", "Brazil", "Argentina", "Cuba", "Haiti",
    "Latin America", "South America", "Caribbean", "United States",
    "United States Constitution", "U.S. Congress", "Australia", "Canada",
    "New Zealand", "Ireland", "Scotland", "Wales", "England",
    "Politics of the United Kingdom", "United Kingdom", "Netherlands",
    "Belgium", "Sweden", "Norway", "Denmark", "Finland", "Nordic countries",
    "Poland", "Hungary", "Czech Republic", "Austria", "Switzerland",
    "Romania", "Greece", "Serbia", "Croatia", "Vietnam", "Indonesia",
    "Thailand", "Philippines", "Tambayan Philippines", "Ethnic groups",
    "Extinct and endangered languages", "Writing systems", "Latin",
    "Ships", "Maritime warfare", "Castles", "Cities",
    "National Register of Historic Places", "Museums", "Libraries",
    "Sicily", "Lithuania", "Bulgaria", "Palestine", "Albania", "Slovakia",
    "Greenland", "Iceland", "Armenia", "Georgia (country)", "Azerbaijan",
    "European Microstates",
    # Outlaws, plotters and notorious criminals are popular-history
    # staples (Guy Fawkes, Billy the Kid, Ned Kelly); this is their only
    # rating home and it belongs above the "weak" tier.
    "Crime and Criminal Biography",
}

WEAK_PROJECTS = {
    # Adjacent fields: genuinely historical for some subjects, but they also
    # rate a great deal of modern material, so ~0.30 weight.
    "Biography", "Philosophy", "Religion", "Christianity", "Catholicism",
    "Islam", "Hinduism", "Buddhism", "Saints", "Bible", "Theology",
    "Lutheranism", "Zoroastrianism", "Literature", "Books", "Poetry",
    "Novels", "Theatre", "Visual arts", "Architecture", "Sculpture",
    "Painting", "Photography", "Classical music", "Opera", "Composers",
    "Science", "Physics", "Chemistry", "Astronomy", "Mathematics",
    "Medicine", "Biology", "Technology", "Engineering", "Civil engineering",
    "Electrical engineering", "Trains", "Aviation", "Spaceflight",
    "Computing", "Law", "Economics", "Sociology", "Linguistics",
    "Geology", "Palaeontology", "Rocks and minerals", "Human rights",
    "Feminism", "Socialism", "Conservatism", "Anarchism", "Freemasonry",
    "Energy", "Journalism", "Education", "Business", "Death",
    "Science Fiction", "Children's literature", "Women writers",
    "Women in Religion", "Women scientists", "Psychology", "Physiology",
    "Geography", "Protected areas", "Gemology and Jewelry", "Cemeteries",
    "Smithsonian Institution", "British Library", "Atheism",
}

# WikiProject Biography's top level carries NO importance value at all --
# it delegates entirely to work groups -- so these matter a great deal.
# They are the main route by which military and political figures whose
# only other home is (deliberately unrated) WikiProject Military history
# get scored. Matched by keyword because the naming is inconsistent
# upstream ("military biography work group" vs "WikiProject Royalty and
# Nobility" vs "politics and government work group"); the exact strings
# were read off the live API, not guessed.
BIO_CORE_KEYWORDS = ("military", "politics and government", "royalty",
                     "peerage", "core biographies")
# Real work groups that are not history-flavoured. An arts/entertainment
# or science Top rating is weak evidence of *history-enthusiast*
# recognition -- the general-fame anchor already rewards those people.
BIO_WEAK_KEYWORDS = ("arts and entertainment", "science and academia",
                     "musician", "actors", "filmmaker", "writers and poets")
# Anything else under Biography (notably "sports and games work group")
# scores zero: a Top rating from WikiProject Baseball is no evidence at
# all about history-audience recognition.

IMPORTANCE_VALUE = {
    "Top": 100.0,
    "High": 72.0,
    "Mid": 40.0,
    "Low": 14.0,
    "Bottom": 6.0,
}
# "", "Unknown", "NA", "???" -> no opinion, not a zero. A project that has
# not assessed importance must not drag a subject down.

# Article-quality class is a weak secondary: FA/GA/A/B mean editors who
# care have invested real work, which correlates with enthusiast interest.
CLASS_VALUE = {
    "FA": 100.0, "FL": 100.0, "A": 88.0, "GA": 80.0, "B": 58.0,
    "C": 38.0, "Start": 18.0, "Stub": 4.0, "List": 30.0,
}


def project_bucket(project):
    head, _, tail = project.partition("/")
    if head == "Biography" and tail:
        low = tail.lower()
        if any(k in low for k in BIO_CORE_KEYWORDS):
            return "core"
        if any(k in low for k in BIO_WEAK_KEYWORDS):
            return "weak"
        return None          # sports and games, and anything unrecognised
    if head in CORE_PROJECTS:
        return "core"
    if head in PERIOD_PROJECTS:
        return "period"
    if head in WEAK_PROJECTS:
        return "weak"
    return None


# "weak" was originally 0.30. Raised to 0.40 after seeing Isambard Kingdom
# Brunel -- Top-importance in Civil engineering, runner-up in 100 Greatest
# Britons, an In Our Time subject and a Great Lives subject -- score only
# 33/100 on history importance. The history of science, engineering and
# ideas is squarely inside this audience's interests, and 0.30 was
# punishing every figure whose only rating home is a discipline project.
BUCKET_WEIGHT = {"core": 1.0, "period": 0.62, "weak": 0.40}


def score_assessments(assessments):
    """assessments: {project: {"class":..., "importance":...}} -> dict of
    history_importance components. Returns (raw_score 0-100, detail)."""
    scored = []          # (bucket_weight, value, project, importance)
    best_class = 0.0
    breadth_weight = 0.0
    for project, rec in (assessments or {}).items():
        cls = (rec or {}).get("class") or ""
        best_class = max(best_class, CLASS_VALUE.get(cls, 0.0))
        if project == "Project-independent assessment":
            continue
        bucket = project_bucket(project)
        if bucket is None:
            continue
        imp = (rec or {}).get("importance") or ""
        val = IMPORTANCE_VALUE.get(imp)
        if val is None:
            continue
        scored.append((BUCKET_WEIGHT[bucket], val, project, imp))
        # BREADTH: how many history projects claim this subject at all, at
        # Mid or better. This is a genuinely separate fact from the peak
        # rating. Simon de Montfort is only "Mid" anywhere, but he is Mid
        # in nine history projects at once -- England, Middle Ages, France,
        # English Royalty, Crusades, military biography, politics, royalty,
        # peerage -- which is precisely what "woven through the historical
        # record" looks like. Kim Kardashian is in none.
        if imp in ("Top", "High", "Mid"):
            breadth_weight += BUCKET_WEIGHT[bucket]

    if not scored:
        return None, {
            "n_history_projects": 0, "best": None, "best_project": None,
            "breadth_weight": 0.0, "class_value": round(best_class, 1),
        }

    # Peak: weighted best-of-two, but the second opinion only counts if it
    # is itself a Mid-or-better rating. Otherwise a figure who happens to
    # carry one incidental Low banner from an unrelated project is punished
    # for it -- Ivan the Terrible is Top-importance to WikiProject Russia
    # and simply has not been assessed by anyone else, and averaging in a
    # stray Low was costing him ~9 points of history importance for a fact
    # about Wikipedia's banner coverage rather than about Ivan.
    scored.sort(key=lambda t: -(t[0] * t[1]))
    top = scored[0]
    peak = top[0] * top[1]
    seconds = [s for s in scored[1:] if s[3] in ("Top", "High", "Mid")]
    if seconds:
        peak = 0.74 * peak + 0.26 * (seconds[0][0] * seconds[0][1])

    # Breadth saturates: the 2nd and 3rd history home say a lot, the 9th
    # says little. 1 core home ~= 28, 3 ~= 63, 6 ~= 85.
    breadth = 100.0 * (1.0 - math.exp(-breadth_weight / 3.0))

    raw = min(100.0, 0.70 * peak + 0.38 * breadth)
    return raw, {
        "n_history_projects": len(scored),
        "best": top[3],
        "best_project": top[2],
        "breadth_weight": round(breadth_weight, 2),
        "class_value": round(best_class, 1),
    }


# ---------------------------------------------------------------------------
# S4: vital articles
# ---------------------------------------------------------------------------

VITAL_TOPICS = ["History", "People", "Arts", "Philosophy and religion",
                "Society and social sciences", "Geography", "Technology"]
VITAL_LEVEL_VALUE = {1: 100.0, 2: 100.0, 3: 92.0, 4: 70.0, 5: 40.0}


def harvest_vital(offline=False, verbose=True):
    """Returns {article_title: best (lowest) vital level}."""
    out = {}
    cats = []
    for lvl in (1, 2, 3, 4):
        cats.append((lvl, "Category:Wikipedia level-%d vital articles" % lvl))
        for topic in VITAL_TOPICS:
            cats.append((lvl, "Category:Wikipedia level-%d vital articles in %s"
                         % (lvl, topic)))
    for topic in ("History", "People", "Arts", "Philosophy and religion"):
        cats.append((5, "Category:Wikipedia level-5 vital articles in %s" % topic))

    for lvl, cat in cats:
        try:
            for page in api_continue({
                "action": "query", "list": "categorymembers",
                "cmtitle": cat, "cmlimit": "500", "cmnamespace": "1",
            }, offline=offline):
                for m in page.get("query", {}).get("categorymembers", []):
                    t = m.get("title", "")
                    if t.startswith("Talk:"):
                        t = t[5:]
                    if t and (t not in out or lvl < out[t]):
                        out[t] = lvl
        except Exception as exc:                       # noqa: BLE001
            if verbose:
                print("  vital: skipped %s (%s)" % (cat, exc), file=sys.stderr)
    if verbose:
        print("  vital: %d articles" % len(out), file=sys.stderr)
    return out


# ---------------------------------------------------------------------------
# S5: In Our Time
# ---------------------------------------------------------------------------

IOT_LIST_TITLE = "List of In Our Time programmes"
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")


def harvest_in_our_time(offline=False, verbose=True):
    """Parse the episode table. Returns (link_targets, plain_titles).

    Table columns are: 1 broadcast date, 2 episode title, 3 contributors.
    ONLY column 2 is used -- column 3 is full of living historians
    (Dawkins, Tom Holland, ...) which would be actively wrong to count.
    """
    data = api({"action": "query", "prop": "revisions", "rvprop": "content",
                "rvslots": "main", "titles": IOT_LIST_TITLE}, offline=offline)
    pages = data.get("query", {}).get("pages", [])
    if not pages or "missing" in pages[0]:
        if verbose:
            print("  IOT: list article not found", file=sys.stderr)
        return set(), set()
    wt = pages[0]["revisions"][0]["slots"]["main"]["content"]

    targets, plains = set(), set()
    in_table = False
    cell_idx = 0
    for line in wt.splitlines():
        s = line.strip()
        if s.startswith("{|"):
            in_table, cell_idx = True, 0
            continue
        if s.startswith("|}"):
            in_table = False
            continue
        if not in_table:
            continue
        if s.startswith("|-"):
            cell_idx = 0
            continue
        if s.startswith("!"):
            continue
        if s.startswith("|"):
            cell_idx += 1
            if cell_idx != 2:
                continue
            cell = s[1:].strip()
            for m in WIKILINK_RE.finditer(cell):
                tgt = m.group(1).strip()
                if tgt and ":" not in tgt.split("|")[0][:12]:
                    targets.add(tgt)
            plain = WIKILINK_RE.sub(lambda m: (m.group(2) or m.group(1)), cell)
            plain = re.sub(r"''+", "", plain)
            plain = re.sub(r"<[^>]+>", " ", plain)
            plain = re.sub(r"\{\{[^}]*\}\}", " ", plain)
            plain = re.sub(r"\[[^\]]*\]", " ", plain)
            if plain.strip():
                plains.add(plain.strip())
    if verbose:
        print("  IOT: %d linked subjects, %d episode titles"
              % (len(targets), len(plains)), file=sys.stderr)
    return targets, plains


GREAT_LIVES_TITLE = "Great Lives"


def harvest_great_lives(offline=False, verbose=True):
    """BBC Radio 4 *Great Lives*: ~1,300 episodes, each nominating ONE
    person. Table columns: 1 guest, 2 nominee, 3 presenter. Only column 2
    is the subject -- column 1 is the celebrity guest and column 3 the
    presenter, and counting either would be actively wrong.

    This is the person-dense complement to *In Our Time*, which is
    overwhelmingly about events, concepts and works rather than people.
    """
    data = api({"action": "query", "prop": "revisions", "rvprop": "content",
                "rvslots": "main", "titles": GREAT_LIVES_TITLE,
                "redirects": "1"}, offline=offline)
    pages = data.get("query", {}).get("pages", [])
    if not pages or "missing" in pages[0]:
        if verbose:
            print("  Great Lives: article not found", file=sys.stderr)
        return set()
    wt = pages[0]["revisions"][0]["slots"]["main"]["content"]

    out = set()
    in_table = False
    cell_idx = 0
    for line in wt.splitlines():
        s = line.strip()
        if s.startswith("{|"):
            in_table, cell_idx = True, 0
            continue
        if s.startswith("|}"):
            in_table = False
            continue
        if not in_table:
            continue
        if s.startswith("|-"):
            cell_idx = 0
            continue
        if s.startswith("!"):
            continue
        if not s.startswith("|"):
            continue
        cell = s[1:].strip()
        # rowspan'd presenter cells carry an attribute prefix; strip it so
        # the column index stays aligned with the visible table.
        if re.match(r'^\s*rowspan\s*=', cell, re.I):
            cell = cell.split("|", 1)[1] if "|" in cell else ""
        cell_idx += 1
        if cell_idx != 2:
            continue
        for m in WIKILINK_RE.finditer(cell):
            tgt = m.group(1).strip()
            if tgt and not tgt.startswith(("File:", "Image:", "Category:")):
                out.add(tgt)
    if verbose:
        print("  Great Lives: %d nominated subjects" % len(out), file=sys.stderr)
    return out


GREATEST_HUB = "Greatest Britons spin-offs"


def harvest_greatest_polls(offline=False, verbose=True):
    """National "greatest countryman" television polls -- the BBC's 100
    Greatest Britons and its ~40 international spin-offs (Unsere Besten,
    De Grootste Nederlander, Le Plus Grand Francais, El Gen Argentino...).

    These are mass-audience votes on historical standing, which is a
    different and useful thing from either pageviews or editor judgement,
    and unlike the two BBC radio corpora they are not Anglocentric.

    Returned links are raw wikilinks from the poll articles, so callers
    must restrict credit to person-class titles: poll articles also link
    to broadcasters, countries and occupations.
    """
    data = api({"action": "query", "prop": "revisions", "rvprop": "content",
                "rvslots": "main", "titles": GREATEST_HUB, "redirects": "1"},
               offline=offline)
    pages = data.get("query", {}).get("pages", [])
    if not pages or "missing" in pages[0]:
        if verbose:
            print("  greatest polls: hub not found", file=sys.stderr)
        return set(), []
    hub = pages[0]["revisions"][0]["slots"]["main"]["content"]

    poll_titles = set()
    for m in WIKILINK_RE.finditer(hub):
        tgt = m.group(1).strip()
        if re.search(r"(greatest|grootste|besten|gen argentino|grandes|"
                     r"velk|nej|suur|store|storste|mari rom|plus grand)",
                     tgt, re.I):
            poll_titles.add(tgt)
    poll_titles.add("100 Greatest Britons")

    names = set()
    used = []
    for pt in sorted(poll_titles):
        try:
            d = api({"action": "query", "prop": "revisions",
                     "rvprop": "content", "rvslots": "main", "titles": pt,
                     "redirects": "1"}, offline=offline)
            p = d.get("query", {}).get("pages", [])
            if not p or "missing" in p[0] or not p[0].get("revisions"):
                continue
            body = p[0]["revisions"][0]["slots"]["main"]["content"]
        except Exception:                                # noqa: BLE001
            continue
        before = len(names)
        for m in WIKILINK_RE.finditer(body):
            tgt = m.group(1).strip()
            if tgt and not tgt.startswith(("File:", "Image:", "Category:",
                                           "Template:", "wikt:")):
                names.add(tgt)
        used.append((pt, len(names) - before))
    if verbose:
        print("  greatest polls: %d poll articles, %d candidate links"
              % (len(used), len(names)), file=sys.stderr)
    return names, used


def canonicalize(titles, offline=False, verbose=True):
    """raw title -> canonical enwiki title (redirects followed)."""
    out = {}
    titles = [t for t in dict.fromkeys(titles) if t]
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        try:
            data = api({"action": "query", "titles": "|".join(batch),
                        "redirects": "1"}, offline=offline)
        except Exception:                                # noqa: BLE001
            continue
        q = data.get("query", {})
        norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
        redir = {r["from"]: r["to"] for r in q.get("redirects", [])}
        for raw in batch:
            cur = norm.get(raw, raw)
            cur = redir.get(cur, cur)
            out[raw] = cur
    if verbose:
        print("  canonicalised %d/%d titles" % (len(out), len(titles)),
              file=sys.stderr)
    return out


# ---------------------------------------------------------------------------
# S2/S3 harvest: pageassessments + article length, one batched call each 50
# ---------------------------------------------------------------------------

def harvest_page_facts(titles, offline=False, verbose=True):
    """{title: {"length": int|None, "assessments": {...}, "redirect_of": ...}}"""
    out = {}
    titles = [t for t in dict.fromkeys(titles) if t]
    total = (len(titles) + 49) // 50
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        if verbose and (i // 50) % 20 == 0:
            print("  page facts: batch %d/%d" % (i // 50 + 1, total),
                  file=sys.stderr)
        try:
            first = True
            merged = {}
            for data in api_continue({
                "action": "query", "titles": "|".join(batch),
                "prop": "info|pageassessments", "palimit": "max",
                "pasubprojects": "1", "redirects": "1",
            }, offline=offline):
                q = data.get("query", {})
                if first:
                    for r in q.get("redirects", []):
                        merged.setdefault("_redir", {})[r["from"]] = r["to"]
                    for n in q.get("normalized", []):
                        merged.setdefault("_norm", {})[n["from"]] = n["to"]
                    first = False
                for p in q.get("pages", []):
                    t = p.get("title")
                    if not t:
                        continue
                    rec = merged.setdefault(t, {"length": None,
                                                "assessments": {},
                                                "missing": "missing" in p})
                    if p.get("length") is not None:
                        rec["length"] = p.get("length")
                    for proj, val in (p.get("pageassessments") or {}).items():
                        rec["assessments"][proj] = val
        except Exception as exc:                          # noqa: BLE001
            if verbose:
                print("  page facts: batch failed (%s)" % exc, file=sys.stderr)
            continue

        norm = merged.pop("_norm", {})
        redir = merged.pop("_redir", {})
        for raw in batch:
            cur = norm.get(raw, raw)
            cur = redir.get(cur, cur)
            rec = merged.get(cur)
            if rec is None:
                continue
            out[raw] = {"length": rec["length"],
                        "assessments": rec["assessments"],
                        "resolved": cur,
                        "missing": rec["missing"]}
    if verbose:
        print("  page facts: %d/%d resolved" % (len(out), len(titles)),
              file=sys.stderr)
    return out


# ---------------------------------------------------------------------------
# Item universe
# ---------------------------------------------------------------------------

POOL_FILES = [("who", "data/reveal-who.json"),
              ("map", "data/figures.json"),
              ("what", "data/reveal-what.json")]

# ---------------------------------------------------------------------------
# Title overrides -- (game, id) -> canonical enwiki title.
#
# The live pool records in data/*.json carry NO wiki_title field at all, so
# every downstream tool has to resolve an item from its display *name*. When
# that name is a bare ambiguous string ("Seneca", "Charles V", "Vasa") the
# lookup lands on a DISAMBIGUATION page: a few hundred bytes of links, with
# no pageviews, no inbound links and no WikiProject assessments. The item
# then scores near zero on any metric derived from it.
#
# That is what produced the launch review's headline claim that Mihrimah
# Sultan sat at the 13.9th fame percentile: her item resolved to a 531-byte
# disambiguation stub, not to her 23 KB biography.
#
# Every title below was verified live against the enwiki API: it exists, it
# is not a disambiguation page, and it is over 1,500 bytes. This dict is the
# durable record -- current_inventory.json is gitignored and regenerated, so
# a fix applied only there does not survive.
# ---------------------------------------------------------------------------
TITLE_OVERRIDES = {
    ("who", "charles-v-hre"): "Charles V, Holy Roman Emperor",
    ("who", "empress-theodora"): "Theodora (wife of Justinian I)",
    ("who", "mihrimah-sultan"): "Mihrimah Sultan (daughter of Suleiman I)",
    ("map", "charles-v-hre"): "Charles V, Holy Roman Emperor",
    ("map", "john-reed"): "John Reed (journalist)",
    ("map", "john-smith"): "John Smith (explorer)",
    ("map", "seneca"): "Seneca the Younger",
    ("map", "thomas-cochrane"): "Thomas Cochrane, 10th Earl of Dundonald",
    ("map", "william-adams"): "William Adams (samurai)",
    ("what", "christ-the-redeemer"): "Christ the Redeemer (statue)",
    ("what", "cyrene"): "Cyrene, Libya",
    ("what", "fram-ship"): "Fram (ship)",
    ("what", "hindenburg"): "LZ 129 Hindenburg",
    ("what", "merv"): "Merv",
    ("what", "mikasa"): "Japanese battleship Mikasa",
    ("what", "sacre-coeur"): "Sacré-Cœur, Paris",
    ("what", "st-stephens-vienna"): "St. Stephen's Cathedral, Vienna",
    ("what", "temple-poseidon"): "Temple of Poseidon, Sounion",
    ("what", "vasa-ship"): "Vasa (ship)",
    ("what", "world-trade-center"): "World Trade Center (1973–2001)",
}

# An article shorter than this is either a disambiguation page that has not
# been tagged as one, a redirect stub, or a placeholder -- in every case it
# carries no usable signal.
MIN_ARTICLE_BYTES = 1500


def check_titles(titles, offline=False, verbose=True):
    """{title: {"resolved", "missing", "disambiguation", "length", "status"}}

    `status` is one of ok / disambiguation / missing / too_short. This is the
    check that build_item_universe applies to every resolved title and that
    title_health.json exposes to the offline validator.
    """
    out = {}
    titles = [t for t in dict.fromkeys(titles) if t]
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        try:
            for data in api_continue({
                "action": "query", "titles": "|".join(batch),
                "prop": "info|pageprops", "ppprop": "disambiguation",
                "redirects": "1",
            }, offline=offline):
                q = data.get("query", {})
                norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
                redir = {r["from"]: r["to"] for r in q.get("redirects", [])}
                pages = {p["title"]: p for p in q.get("pages", [])}
                for raw in batch:
                    cur = redir.get(norm.get(raw, raw), norm.get(raw, raw))
                    p = pages.get(cur)
                    if p is None:
                        continue
                    missing = "missing" in p
                    disambig = "disambiguation" in (p.get("pageprops") or {})
                    length = p.get("length")
                    if missing:
                        status = "missing"
                    elif disambig:
                        status = "disambiguation"
                    elif (length or 0) < MIN_ARTICLE_BYTES:
                        status = "too_short"
                    else:
                        status = "ok"
                    out[raw] = {"resolved": cur, "missing": missing,
                                "disambiguation": disambig, "length": length,
                                "status": status}
        except Exception as exc:                          # noqa: BLE001
            if verbose:
                print("  title check: batch failed (%s)" % exc, file=sys.stderr)
    return out


def build_item_universe(offline=False, verbose=True):
    """Returns (items, extra_titles).

    items: list of {id, game, name, difficulty, wiki_title, title_source}
    extra_titles: universe_people / universe_objects titles not in a pool.
    """
    inv_by_game = collections.defaultdict(dict)
    inv_path = SCRIPT_DIR / "current_inventory.json"
    if inv_path.exists():
        for it in json.loads(inv_path.read_text(encoding="utf-8"))["items"]:
            if it.get("wiki_title"):
                inv_by_game[it["game"]][it["id"]] = it["wiki_title"]

    name_to_title = {}
    fp_path = SCRIPT_DIR / "final_pools.json"
    if fp_path.exists():
        fp = json.loads(fp_path.read_text(encoding="utf-8"))
        for game, buckets in fp.get("per_game", {}).items():
            for bucket in ("keep", "add"):
                for e in buckets.get(bucket, []) or []:
                    if e.get("name") and e.get("wiki_title"):
                        name_to_title.setdefault(norm_name(e["name"]),
                                                 e["wiki_title"])

    items, unresolved = [], []
    for game, rel in POOL_FILES:
        path = REPO_ROOT / rel
        for e in json.loads(path.read_text(encoding="utf-8")):
            title = TITLE_OVERRIDES.get((game, e["id"]))
            src = "override" if title else None
            if not title:
                title = inv_by_game[game].get(e["id"])
                src = "inventory" if title else None
            if not title:
                title = name_to_title.get(norm_name(e.get("name", "")))
                src = "final_pools" if title else None
            rec = {"id": e["id"], "game": game, "name": e.get("name"),
                   "difficulty": e.get("difficulty"),
                   "wiki_title": title, "title_source": src,
                   "title_status": None}
            items.append(rec)
            if not title:
                unresolved.append(rec)

    if unresolved:
        if verbose:
            print("  resolving %d pool items by name via enwiki"
                  % len(unresolved), file=sys.stderr)
        try:
            resolved = canonicalize([r["name"] for r in unresolved],
                                    offline=offline, verbose=False)
        except Exception:                                # noqa: BLE001
            resolved = {}
        for r in unresolved:
            t = resolved.get(r["name"])
            if t:
                r["wiki_title"] = t
                r["title_source"] = "name-lookup"

    # Health-check every resolved title. A name-lookup that landed on a
    # disambiguation page is WORSE than no title at all: it yields a
    # confident-looking near-zero score instead of an honest blank. Drop
    # those back to unresolved rather than scoring the wrong page.
    health = check_titles([r["wiki_title"] for r in items if r["wiki_title"]],
                          offline=offline, verbose=verbose)
    dropped = 0
    for r in items:
        h = health.get(r["wiki_title"] or "")
        if not h:
            continue
        r["title_status"] = h["status"]
        r["title_length"] = h["length"]
        if h["status"] != "ok":
            dropped += 1
            if r["title_source"] == "name-lookup":
                r["wiki_title"] = None
                r["title_source"] = None
    if verbose and dropped:
        print("  %d pool items resolved to a disambiguation/missing/short "
              "article (see title_health.json)" % dropped, file=sys.stderr)

    extra = set()
    for fname, key in (("universe_people.json", "people"),
                       ("universe_objects.json", "objects")):
        p = SCRIPT_DIR / fname
        if not p.exists():
            continue
        for e in json.loads(p.read_text(encoding="utf-8")).get(key, []):
            if e.get("wiki_title"):
                extra.add(e["wiki_title"])

    pool_titles = {r["wiki_title"] for r in items if r["wiki_title"]}
    return items, sorted(extra - pool_titles)


def load_fame():
    p = SCRIPT_DIR / "fame_scores.json"
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {s["wiki_title"]: s for s in data.get("scores", [])}


# ---------------------------------------------------------------------------
# Discovery mode
# ---------------------------------------------------------------------------

def probe_projects(n, offline=False):
    items, extra = build_item_universe(offline=offline)
    titles = [r["wiki_title"] for r in items if r["wiki_title"]][:n]
    facts = harvest_page_facts(titles, offline=offline)
    counter = collections.Counter()
    rated = collections.Counter()
    for rec in facts.values():
        for proj, val in (rec["assessments"] or {}).items():
            counter[proj] += 1
            if (val or {}).get("importance") in IMPORTANCE_VALUE:
                rated[proj] += 1
    print("%-58s %6s %6s %s" % ("PROJECT", "seen", "rated", "bucket"))
    for proj, c in counter.most_common(220):
        print("%-58s %6d %6d %s"
              % (proj[:58], c, rated[proj], project_bucket(proj) or "-"))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(SCRIPT_DIR / "salience.json"))
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--probe-projects", type=int, default=0)
    ap.add_argument("--skip-universe", action="store_true",
                    help="score only shipped-pool items (faster)")
    args = ap.parse_args()

    if args.probe_projects:
        probe_projects(args.probe_projects, offline=args.offline)
        return

    print("[1/6] building item universe", file=sys.stderr)
    items, extra_titles = build_item_universe(offline=args.offline)
    pool_titles = sorted({r["wiki_title"] for r in items if r["wiki_title"]})
    all_titles = pool_titles if args.skip_universe else \
        sorted(set(pool_titles) | set(extra_titles))
    print("  %d pool items, %d pool titles, %d titles to score"
          % (len(items), len(pool_titles), len(all_titles)), file=sys.stderr)

    print("[2/6] fame_scores.json", file=sys.stderr)
    fame = load_fame()

    print("[3/6] pageassessments + article length", file=sys.stderr)
    facts = harvest_page_facts(all_titles, offline=args.offline)

    print("[4/6] vital articles", file=sys.stderr)
    vital = harvest_vital(offline=args.offline)

    print("[5/6] audience corpora", file=sys.stderr)
    iot_targets, iot_plains = harvest_in_our_time(offline=args.offline)
    gl_targets = harvest_great_lives(offline=args.offline)
    poll_targets, polls_used = harvest_greatest_polls(offline=args.offline)

    canon = canonicalize(sorted(iot_targets | gl_targets | poll_targets),
                         offline=args.offline)
    iot_titles = set(iot_targets) | {canon[t] for t in iot_targets if t in canon}
    gl_titles = set(gl_targets) | {canon[t] for t in gl_targets if t in canon}
    poll_titles_set = set(poll_targets) | \
        {canon[t] for t in poll_targets if t in canon}
    iot_norm = ({norm_name(t) for t in iot_titles}
                | {norm_name(t) for t in iot_plains})
    iot_norm.discard("")
    gl_norm = {norm_name(t) for t in gl_titles}
    gl_norm.discard("")

    print("[6/6] scoring", file=sys.stderr)

    # A title with no fame_scores record has no class either, and the
    # fallback "other" bucket holds only a dozen titles -- percentile
    # ranking inside it is noise (one such item came out at 100.0 and
    # another at 25.0 purely because of bucket size). The game a pool item
    # belongs to tells us the class directly: who/map are people, what is
    # an object, and "artefact" is build_scores.py's catch-all object class.
    class_hint = {}
    for it in items:
        if it["wiki_title"]:
            class_hint.setdefault(it["wiki_title"],
                                  "artefact" if it["game"] == "what" else "person")

    # ---- per-title raw signal assembly ----
    rows = []
    for title in all_titles:
        f = fame.get(title) or {}
        fct = facts.get(title) or {}
        cls = f.get("class") or class_hint.get(title) or "other"
        pv = f.get("pv_stat")
        inl = f.get("inlinks")
        length = fct.get("length")
        assessments = fct.get("assessments") or {}
        hist_raw, hist_detail = score_assessments(assessments)
        vlevel = vital.get(title) or vital.get(fct.get("resolved") or "")
        n = norm_name(title)
        resolved = fct.get("resolved")
        iot_hit = (title in iot_titles) or (resolved in iot_titles) \
            or (n in iot_norm)
        gl_hit = (title in gl_titles) or (resolved in gl_titles) \
            or (n in gl_norm)
        # Poll articles link to broadcasters, countries and occupations as
        # well as to the ranked people, so this credit is restricted to
        # person-class titles.
        poll_hit = cls == "person" and (
            title in poll_titles_set or resolved in poll_titles_set)
        rows.append({
            "wiki_title": title,
            "class": cls,
            "fame": f.get("fame"),
            "pv_stat": pv,
            "inlinks": inl,
            "languages": f.get("languages"),
            "length": length,
            "hist_raw": hist_raw,
            "hist_detail": hist_detail,
            "vital_level": vlevel,
            "iot": bool(iot_hit),
            "great_lives": bool(gl_hit),
            "greatest_poll": bool(poll_hit),
            "corpus_hits": int(bool(iot_hit)) + int(bool(gl_hit))
                           + int(bool(poll_hit)),
            "missing_article": bool(fct.get("missing")),
        })

    # ---- S1 record_density + S2 depth: residuals, computed within class ----
    by_class = collections.defaultdict(list)
    for r in rows:
        by_class[r["class"]].append(r)

    for cls, group in by_class.items():
        idx_d = [i for i, r in enumerate(group)
                 if isinstance(r["pv_stat"], (int, float))
                 and isinstance(r["inlinks"], (int, float))]
        if len(idx_d) >= 3:
            xs = [math.log1p(max(0.0, group[i]["pv_stat"])) for i in idx_d]
            ys = [math.log1p(max(0, group[i]["inlinks"])) for i in idx_d]
            res = ols_residuals(xs, ys)
            for k, i in enumerate(idx_d):
                group[i]["density_resid"] = res[k]

        idx_l = [i for i, r in enumerate(group)
                 if isinstance(r["pv_stat"], (int, float))
                 and isinstance(r["length"], (int, float)) and r["length"] > 0]
        if len(idx_l) >= 3:
            xs = [math.log1p(max(0.0, group[i]["pv_stat"])) for i in idx_l]
            ys = [math.log(group[i]["length"]) for i in idx_l]
            res = ols_residuals(xs, ys)
            for k, i in enumerate(idx_l):
                group[i]["depth_resid"] = res[k]

    # ---- percentile-rank each component within class ----
    def rank_into(group, src, dst, default=0.0):
        vals = [g.get(src) if isinstance(g.get(src), (int, float)) else None
                for g in group]
        present = [i for i, v in enumerate(vals) if v is not None]
        if not present:
            for g in group:
                g[dst] = default
            return
        pcts = average_rank_percentiles([vals[i] for i in present])
        for g in group:
            g[dst] = default
        for k, i in enumerate(present):
            group[i][dst] = pcts[k]

    for cls, group in by_class.items():
        rank_into(group, "density_resid", "density_pct", 50.0)
        rank_into(group, "depth_resid", "depth_pct", 50.0)

    # ---- blend ----
    #
    # Weights are argued in SALIENCE.md. The short version:
    #  * history_importance is the only signal that is a direct expert
    #    judgement of historical significance -> largest weight.
    #  * The audience corpora (In Our Time, Great Lives, national
    #    "greatest countryman" polls) are the only signals drawn from this
    #    exact audience, but they are binary and cover a few thousand
    #    subjects -> a bounded bonus, not a driver, so absence never
    #    condemns. Presence in two or three is markedly better evidence
    #    than presence in one, so the bonus is stepped rather than flat.
    #  * vital level is general encyclopaedic canon: real corroboration,
    #    but it drifts toward "important" rather than "beloved".
    #  * density/depth are traffic-independent footprint measures. They are
    #    cheap and honest but noisy (navboxes, year-article spam), so they
    #    share a modest weight.
    #  * A general-fame anchor is kept deliberately small but non-zero: a
    #    subject with NO public footprint at all is academic syllabus
    #    knowledge, which is the exact failure the launch review named.
    W_HIST, W_VITAL, W_DENSITY, W_DEPTH, W_FAME = 0.42, 0.14, 0.13, 0.09, 0.22
    CORPUS_BONUS = {0: 0.0, 1: 7.0, 2: 12.0, 3: 15.0}

    for cls, group in by_class.items():
        for g in group:
            hist = g["hist_raw"]
            hist_used = hist if hist is not None else \
                min(55.0, 0.55 * (g["hist_detail"] or {}).get("class_value", 0.0))
            vital_used = VITAL_LEVEL_VALUE.get(g["vital_level"], 0.0)
            fame_used = g["fame"] if isinstance(g["fame"], (int, float)) else 50.0
            core = (W_HIST * hist_used
                    + W_VITAL * vital_used
                    + W_DENSITY * g["density_pct"]
                    + W_DEPTH * g["depth_pct"]
                    + W_FAME * fame_used)
            core += CORPUS_BONUS.get(g["corpus_hits"], 15.0)
            g["salience_raw"] = max(0.0, min(100.0, core))
        rank_into(group, "salience_raw", "salience", 0.0)

    # ---- assemble output ----
    by_title = {r["wiki_title"]: r for r in rows}
    out_titles = []
    for r in rows:
        d = r.get("hist_detail") or {}
        out_titles.append({
            "wiki_title": r["wiki_title"],
            "class": r["class"],
            "salience": round(r["salience"], 2),
            "salience_raw": round(r["salience_raw"], 2),
            "fame": r["fame"],
            "divergence": (round(r["salience"] - r["fame"], 2)
                           if isinstance(r["fame"], (int, float)) else None),
            # A title absent from fame_scores.json has no pageview or inlink
            # data, so density/depth fall back to a neutral 50 and the fame
            # anchor to 50 too: the whole score then rests on WikiProject
            # ratings alone. Such a score is a hint, never grounds for a
            # scheduling decision -- run fetch_metrics.py + build_scores.py
            # over the title first.
            "low_confidence": not isinstance(r["pv_stat"], (int, float)),
            "components": {
                "history_importance": (round(r["hist_raw"], 1)
                                       if r["hist_raw"] is not None else None),
                "history_best_rating": d.get("best"),
                "history_best_project": d.get("best_project"),
                "history_projects_rating_it": d.get("n_history_projects", 0),
                "history_breadth_weight": d.get("breadth_weight", 0.0),
                "article_class_value": d.get("class_value"),
                "vital_level": r["vital_level"],
                "in_our_time": r["iot"],
                "great_lives": r["great_lives"],
                "greatest_poll": r["greatest_poll"],
                "corpus_hits": r["corpus_hits"],
                "record_density_pct": round(r["density_pct"], 2),
                "article_depth_pct": round(r["depth_pct"], 2),
            },
            "inputs": {
                "pv_stat": r["pv_stat"],
                "inlinks": r["inlinks"],
                "languages": r["languages"],
                "article_length": r["length"],
            },
        })
    out_titles.sort(key=lambda x: (x["class"], -x["salience"]))

    out_items = []
    for it in items:
        t = it["wiki_title"]
        r = by_title.get(t)
        out_items.append({
            "id": it["id"], "game": it["game"], "name": it["name"],
            "difficulty": it["difficulty"], "wiki_title": t,
            "title_source": it["title_source"],
            "title_status": it.get("title_status"),
            "salience": round(r["salience"], 2) if r else None,
            "low_confidence": bool(r) and not isinstance(r["pv_stat"], (int, float)),
            "fame": (r or {}).get("fame"),
            "divergence": (round(r["salience"] - r["fame"], 2)
                           if r and isinstance(r["fame"], (int, float))
                           else None),
            "in_our_time": (r or {}).get("iot"),
            "great_lives": (r or {}).get("great_lives"),
            "greatest_poll": (r or {}).get("greatest_poll"),
            "history_importance": (round(r["hist_raw"], 1)
                                   if r and r["hist_raw"] is not None else None),
            "history_best_rating": ((r or {}).get("hist_detail") or {}).get("best"),
            "vital_level": (r or {}).get("vital_level"),
        })

    # correlation diagnostics (reported, not used, so the blend stays honest)
    pairs = [(r["fame"], r["salience"]) for r in rows
             if isinstance(r["fame"], (int, float))]
    diag = {
        "pearson_fame_vs_salience": round(
            pearson([p[0] for p in pairs], [p[1] for p in pairs]), 4),
    }
    for a, b in (("density_pct", "depth_pct"), ("density_pct", "fame"),
                 ("depth_pct", "fame")):
        vs = [(r[a], r[b]) for r in rows
              if isinstance(r.get(a), (int, float))
              and isinstance(r.get(b), (int, float))]
        diag["pearson_%s_vs_%s" % (a, b)] = round(
            pearson([v[0] for v in vs], [v[1] for v in vs]), 4)
    hs = [(r["hist_raw"], r["fame"]) for r in rows
          if r["hist_raw"] is not None and isinstance(r["fame"], (int, float))]
    diag["pearson_history_importance_vs_fame"] = round(
        pearson([h[0] for h in hs], [h[1] for h in hs]), 4)
    diag["titles_with_history_importance"] = sum(
        1 for r in rows if r["hist_raw"] is not None)
    diag["titles_in_our_time"] = sum(1 for r in rows if r["iot"])
    diag["titles_great_lives"] = sum(1 for r in rows if r["great_lives"])
    diag["titles_greatest_poll"] = sum(1 for r in rows if r["greatest_poll"])
    diag["titles_any_corpus"] = sum(1 for r in rows if r["corpus_hits"])
    diag["titles_vital"] = sum(1 for r in rows if r["vital_level"])
    diag["greatest_poll_articles_used"] = len(polls_used)

    output = {
        "generatedOn": GENERATED_ON,
        "what_this_is": (
            "History-lover salience: an estimate of how well a keen amateur "
            "historian knows a subject. Complementary to fame_scores.json's "
            "`fame`, which measures general-population popularity. "
            "Never a replacement. See SALIENCE.md."
        ),
        "weights": {
            "history_importance": W_HIST, "vital": W_VITAL,
            "record_density": W_DENSITY, "article_depth": W_DEPTH,
            "general_fame_anchor": W_FAME,
            "audience_corpus_bonus_by_hits": CORPUS_BONUS,
        },
        "diagnostics": diag,
        "counts": {
            "pool_items": len(out_items),
            "pool_items_with_title": sum(1 for i in out_items if i["wiki_title"]),
            "titles_scored": len(out_titles),
        },
        "items": out_items,
        "titles": out_titles,
    }
    Path(args.out).write_text(json.dumps(output, indent=1, ensure_ascii=False),
                              encoding="utf-8")

    # ---- title_health.json: the committed, offline-checkable guard ----
    #
    # salience.json is large and gitignored, so it cannot be what the test
    # suite checks. This file is small, committed, and is the artefact
    # tools/validate_reveal.py reads: it records, for every pool item, which
    # enwiki article the item resolves to and whether that article is real.
    # Regenerate it whenever the pools change.
    health_rows = []
    for it in items:
        health_rows.append({
            "game": it["game"], "id": it["id"], "name": it["name"],
            "wiki_title": it["wiki_title"],
            "title_source": it["title_source"],
            "status": it.get("title_status") or "unresolved",
            "article_bytes": it.get("title_length"),
        })
    health_rows.sort(key=lambda r: (r["game"], r["id"]))
    bad = [r for r in health_rows if r["status"] != "ok"]
    health_path = SCRIPT_DIR / "title_health.json"
    health_path.write_text(json.dumps({
        "generatedOn": GENERATED_ON,
        "what_this_is": (
            "Which English Wikipedia article each Dead Famous pool item "
            "resolves to, and whether that article is real. Pool records in "
            "data/*.json carry no wiki_title, so items are resolved by "
            "display name; a bare ambiguous name lands on a disambiguation "
            "page and scores near zero on every fame/salience metric. "
            "tools/validate_reveal.py fails the build on any status that is "
            "not 'ok'. Regenerate with: python3 tools/fame/build_salience.py"
        ),
        "min_article_bytes": MIN_ARTICLE_BYTES,
        "counts": {
            "items": len(health_rows),
            "ok": len(health_rows) - len(bad),
            "not_ok": len(bad),
        },
        "items": health_rows,
    }, indent=1, ensure_ascii=False), encoding="utf-8")

    print("Wrote %s (%d titles, %d items). HTTP: %d requests, %d cache hits."
          % (args.out, len(out_titles), len(out_items),
             STATS["requests"], STATS["cache_hits"]), file=sys.stderr)
    print("Wrote %s (%d ok, %d not ok)."
          % (health_path, len(health_rows) - len(bad), len(bad)),
          file=sys.stderr)


if __name__ == "__main__":
    main()
