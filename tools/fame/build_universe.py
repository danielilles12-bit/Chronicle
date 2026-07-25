#!/usr/bin/env python3
"""
Build tools/fame/universe_people.json — a candidate universe of the most
famous DEAD historical figures.

Source: Pantheon 2.0, 2025 update
  https://storage.googleapis.com/pantheon-public-data/person_2025_update.csv.bz2
Cached locally at tools/fame/raw/person_2025_update.csv.bz2

WHAT CHANGED (25 Jul 2026) AND WHY
==================================
This script used to sort 55,819 eligible dead people by Pantheon's
Historical Popularity Index (HPI) and keep the top 4,000. Everything below
rank 4,000 was discarded before any of this project's own judgement ran.

That single number was measured to be the largest content defect in the
pipeline. Of 90 figures a history enthusiast would name instantly, 46 were
already sitting in the source data on disk and were cut by the truncation
alone — Thomas Cromwell (Pantheon rank 6,434), Mary Anning (6,790),
Aethelflaed (7,518), Isambard Kingdom Brunel (8,797), Simon de Montfort
(10,325), Sacagawea (12,132), Samuel Pepys (16,016), Mary Seacole (36,014).
Not one of them was rejected on merit. Nobody ever saw them.

But raising the depth ON ITS OWN makes the pool worse, not better. Reaching
Pepys at rank 16,000 also drags in ~12,000 people nobody wants, and the
existing `fame` score cannot separate them: measured on an enthusiast-canon
list versus a list of internet curiosities (Bob Ross, Ted Bundy, Robert
Wadlow, Jeanne Calment...), fame rated the two groups within 0.74 points of
each other. Depth without a better ranking signal is just more noise.

So depth is paired here with a re-ranking signal. See SALIENCE.md: the
strongest instrument for "would a history lover know this?" is English
Wikipedia's WikiProject **importance ratings**, which are domain editors
judging historical significance with no traffic component at all. This
script reuses build_salience.py's curated project buckets and scoring
directly, so the curation lives in exactly one place.

THREE DOCUMENTED FAILURE MODES OF THAT SIGNAL, AND WHAT IS DONE ABOUT THEM
--------------------------------------------------------------------------
SALIENCE.md is explicit that the importance signal must NOT be applied
naively as a hard cut. Three defects, three structural answers:

1. COVERAGE HOLES. Whole categories carry no importance rating at all —
   explorers and travellers especially (Wilfred Thesiger scores 1.2 and
   John Hanning Speke 4.7; both are MISSING DATA, not obscurity). A hard
   floor would delete the heroic age of exploration.
   -> `confidence shrinkage`. The history signal is blended toward "no
      opinion" in proportion to how thin the evidence is: conf = n/(n+K)
      over the number of history projects that actually rated the subject.
      Unrated (n=0) means conf=0, which collapses the blend to pure HPI —
      the subject is neither promoted nor demoted. This is the same
      convention the rest of the codebase uses for missing signals (see
      compile_editions.item_signal: "a record with no match is a wildcard,
      never a rejection"). Speke, rated Low by exactly one project, moves
      only a third of the way toward that rating rather than being buried
      by one editor's opinion.

2. DOMAIN TILT. Measured over the current 4,000-person universe, median
   history_importance by domain is: politics 57.7, military 57.7,
   exploration 51.7, science 44.7, religion 43.9, arts 38.3, sports 38.3,
   business 38.3. A GLOBAL ranking on this signal would therefore pack the
   universe with even more statesmen and soldiers — the exact "history as
   rulers and wars" imbalance the launch review complained about, and which
   the widening is supposed to fix.
   -> the history score is percentile-ranked WITHIN DOMAIN. Thesiger is
      compared with other explorers, Bach with other composers. The domain
      mix of the admitted set therefore stays governed by HPI; the
      re-ranking only reshuffles people *inside* their own domain.

3. MODERN-POLITICAL LEAK. WikiProject Politics rates Kim Il-sung Top
   because he matters, not because a history podcast would cover him.
   -> within-domain percentiling dampens this (a Top rating is ordinary
      among politicians, exceptional among explorers), but it does NOT fix
      it, and nothing here pretends to. Admission to the candidate universe
      is not scheduling. The tone/composition cap in
      tools/compile_editions.py (`propose`) is the control that stops
      authoritarian subjects stacking up inside one issue.

COST ORDERING — THE REASON THIS IS SAFE TO WIDEN
================================================
Every signal used here is fetched in batches of 50 titles per HTTP call.
The genuinely expensive step is downstream: fetch_metrics.py spends THREE
uncached per-title calls (langlinks, pageviews, inlinks) on every row of
this file, at roughly 21 KB of on-disk cache each, and probe_images.py
spends more again. Measured: 150x more HTTP per admitted title than
anything in this script (3 calls/title versus 1 call/50 titles).

The cache figures are worth stating precisely, because "the cache is
already 843 MB" is usually quoted as an argument against widening and it
is not the metrics cache. Measured breakdown of cache.nosync:
image_probe 600 MB, pageviews 94 MB, languages 46 MB, inlinks 32 MB,
wikidata_tags 72 MB. Metrics proper is 172 MB across 8,094 titles. Image
probing is the 600 MB, it is a separate later stage, and nothing in this
file commits to running it.

So the pipeline is ordered cheapest-first, and this whole script is the
pre-filter that protects the expensive stage:

  stage                              cost per title      runs on
  ---------------------------------  ------------------  ---------------
  0 read Pantheon CSV, sort by HPI    0 calls (local)     55,819
  1 structural pre-filter             0 calls (local)     55,819 -> SCAN_DEPTH
  2 resolve enwiki titles             1 call / 50         SCAN_DEPTH
  3 WikiProject assessments           1 call / 50         survivors of 2
  4 blend, rank, cut                  0 calls (local)     -> TARGET_COUNT
  --------------------------------------------------------------------
  5 fetch_metrics.py (EXPENSIVE)      3 calls / 1         TARGET_COUNT only
  6 probe_images.py   (EXPENSIVE)     per-image           later still

Stages 2 and 3 are additionally run in WAVES down the HPI order, with a
provable stop rule (see `_wave_bound`): once the admitted cut score exceeds
the best score any not-yet-assessed candidate could possibly reach, the
remaining waves are skipped and never fetched at all. Widening the scan
from 4,000 to 16,000 therefore costs a few hundred batched calls, while the
per-title budget below the line is spent only on what survives.

Everything is resumable. Title resolution and assessments are both cached
on disk under raw/; re-running after an interruption refetches nothing.

Python 3.9, stdlib only.
"""
import argparse
import bz2
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RAW_DIR = os.path.join(HERE, "raw")
CSV_BZ2 = os.path.join(RAW_DIR, "person_2025_update.csv.bz2")
RESOLUTION_CACHE = os.path.join(RAW_DIR, "wiki_title_resolution_cache.json")
ASSESSMENT_CACHE = os.path.join(RAW_DIR, "universe_assessment_cache.json")
OUTPUT = os.path.join(HERE, "universe_people.json")

USER_AGENT = "DeadFamousIntake/1.0 (daniel.illes12@gmail.com)"
GENERATED_ON = "2026-07-25"

# ---------------------------------------------------------------------------
# The two numbers this file exists to get right.
# ---------------------------------------------------------------------------
# How deep into Pantheon's HPI ordering we LOOK. Canon recovery was measured
# by depth: 8,000 -> 22% of the 90-name enthusiast canon, 12,000 -> 37%,
# 16,000 -> 54%, 24,000 -> 67%. 16,000 is the evidence-backed point: it is
# where the named misses actually live (Cromwell 6,434 ... Pepys 16,016), and
# going on to 24,000 buys 13 more points of canon for 50% more scanning while
# the band's signal-to-noise keeps falling (HPI 23.20 -> 22.11, i.e. the rows
# are already nearly indistinguishable from each other by the source's own
# measure).
#
# Set to 18,000 rather than exactly 16,000 for one honest reason: Samuel
# Pepys, the figure the whole exercise was named after, sits at rank 16,016
# and would fall SIXTEEN places outside a hard 16,000 cut. A boundary that
# excludes its own headline example is a boundary chosen badly. Scanning is
# batched at 50 titles per call, so the extra 2,000 costs about 80 HTTP calls
# and no per-title budget at all — the cheapest 2,000 candidates in the
# pipeline.
SCAN_DEPTH = 18000

# How many survive into universe_people.json — and therefore how many rows
# the EXPENSIVE downstream stage has to pay for. This is the real budget
# decision, and it turned out to matter more than the scan depth, because
# the re-rank can move a candidate a few thousand places but not eight
# thousand. Measured canon recovery against the same 46-name list:
#
#     admitted      canon recovered      marginal
#      8,000        14/46  (30%)
#     10,000        18/46  (39%)         +4 figures per 2,000 admitted
#     12,000        22/46  (48%)         +4 figures per 2,000 admitted
#     14,000        24/46  (52%)         +2 figures per 2,000 admitted
#
# 12,000 is the knee: it is the last step that still returns four recovered
# figures per 2,000 rows of downstream cost, and it lands on the 48-54% the
# depth study predicted. Below it the admission cut simply re-imposes the
# truncation this file exists to remove — at 8,000, Aethelflaed, Sacagawea,
# Tecumseh, Prince Rupert and Pepys are all scanned, all scored, and all
# thrown away again.
#
# The cost of that choice, measured rather than estimated (see the cost
# ordering above): people-titles 4,000 -> 12,000, so total metrics titles go
# ~8,094 -> ~16,100. The often-quoted "843 MB cache" is mostly image probing
# (600 MB); metrics proper is 172 MB across 8,094 titles, i.e. ~21 KB each,
# so this adds ~170 MB and ~24,000 batched-at-1 API calls. One-off, cached,
# resumable.
TARGET_COUNT = 12000

# Attrition buffer: some rows have no enwiki article or collide on title.
# Measured over the 18,871 candidates actually scanned: 7 missing articles
# and 2 duplicate titles, i.e. 0.05%. 2% is ample headroom.
BUFFER_FACTOR = 1.02

BATCH_SIZE = 50
MIN_REQUEST_GAP = 0.15  # ~6-7 req/s, under the 8 req/s ceiling

# --- the blend ------------------------------------------------------------
# Half how famous you are, half how much a history lover would care. HPI is
# a real cross-language measurement of public footprint and the thing that
# makes a portrait guessable at all, so it never stops mattering; but in the
# tail of a 18,000-row scan it is nearly flat (HPI 24.31 at rank 10,000 vs
# 23.20 at 16,000), so letting it dominate there would mean deciding on a
# variable that has stopped varying.
#
# Chosen by sweep, not by taste. Across w_hpi = 0.55 -> 0.35, canon recovery
# rises 23 -> 26 of 46 and canon-vs-curiosity AUC rises 0.831 -> 0.867, with
# no measurable harm to the six figures SALIENCE.md names as the signal's
# documented victims (Anne of Cleves, Guy Fawkes, Kosem Sultan, Lorenzo de'
# Medici, Michel Ney, Blackbeard all stay inside the admitted set at every
# weight, worst case Michel Ney drifting 4,271 -> 5,158). 0.50 is taken
# rather than pushing further because:
#   * it is the point where Samuel Pepys, the named boundary case, is
#     admitted (rank 11,613 of 12,000), and where the internet-curiosity
#     control list finally has NOBODY in the top 1,000;
#   * beyond it the gains come from leaning harder on a signal whose
#     failure modes (modern-political leak, popular-history demotion) this
#     file can dampen but not measure, and SALIENCE.md's own validated
#     blend gives WikiProject importance 0.42 alongside a general-fame
#     anchor. Going past 50/50 would be extrapolating past the evidence.
W_HPI = 0.50
W_SALIENCE = 0.50

# Confidence shrinkage constant. conf = n/(n+K) over the number of history
# projects carrying an importance rating: 1 project -> 0.33, 2 -> 0.50,
# 3 -> 0.60, 6 -> 0.75, 9 -> 0.82. K=2 is deliberately gentle; the failure
# being guarded against (one stray Low rating burying a real figure) is much
# more costly here than a slow climb toward a well-evidenced rating.
SHRINK_K = 2.0

# Audience corpora (In Our Time / Great Lives / national "greatest
# countryman" polls), harvested by build_salience.py. Same stepped, BOUNDED
# bonus it uses: coverage is thin and Anglocentric, so presence is evidence
# but absence must never condemn. These corpora are three HTTP calls in
# total regardless of how many people we score, so they are free at scale —
# and they are the only signal that reaches the figures WikiProject
# importance ratings miss entirely.
CORPUS_BONUS = {0: 0.0, 1: 7.0, 2: 12.0, 3: 15.0}

# Stage 2/3 wave size. Small enough that the stop rule can bite, large
# enough that the per-wave overhead is irrelevant.
WAVE_SIZE = 4000


# ---------------------------------------------------------------------------
# Occupation -> coarse domain mapping (covers all 101 occupation values
# observed among dead rows in the 2025 Pantheon dataset; unseen values fall
# back to "other").
# ---------------------------------------------------------------------------
OCCUPATION_TO_DOMAIN = {
    # military
    "MILITARY PERSONNEL": "military",
    "PIRATE": "military",
    # politics (incl. nobility, law, diplomacy, court society, activism)
    "POLITICIAN": "politics",
    "NOBLEMAN": "politics",
    "DIPLOMAT": "politics",
    "JUDGE": "politics",
    "LAWYER": "politics",
    "POLITICAL SCIENTIST": "politics",
    "EXTREMIST": "politics",
    "PUBLIC WORKER": "politics",
    "SOCIAL ACTIVIST": "politics",
    "COMPANION": "politics",  # royal consorts/companions; mixed bag but mostly court society
    "MAFIOSO": "politics",
    # arts (incl. entertainment, media, design)
    "WRITER": "arts",
    "ACTOR": "arts",
    "PAINTER": "arts",
    "COMPOSER": "arts",
    "MUSICIAN": "arts",
    "SINGER": "arts",
    "FILM DIRECTOR": "arts",
    "SCULPTOR": "arts",
    "ARTIST": "arts",
    "COMIC ARTIST": "arts",
    "DANCER": "arts",
    "CONDUCTOR": "arts",
    "PHOTOGRAPHER": "arts",
    "DESIGNER": "arts",
    "FASHION DESIGNER": "arts",
    "PRODUCER": "arts",
    "CRITIC": "arts",
    "MAGICIAN": "arts",
    "GAME DESIGNER": "arts",
    "PRESENTER": "arts",
    "COMEDIAN": "arts",
    "JOURNALIST": "arts",
    "MODEL": "arts",
    "CELEBRITY": "arts",
    "CHEF": "arts",
    "PORNOGRAPHIC ACTOR": "arts",
    "YOUTUBER": "arts",
    # science (incl. academia, medicine, tech, social science)
    "BIOLOGIST": "science",
    "MATHEMATICIAN": "science",
    "PHYSICIST": "science",
    "ASTRONOMER": "science",
    "CHEMIST": "science",
    "PHYSICIAN": "science",
    "PSYCHOLOGIST": "science",
    "ANTHROPOLOGIST": "science",
    "ARCHAEOLOGIST": "science",
    "COMPUTER SCIENTIST": "science",
    "ECONOMIST": "science",
    "ENGINEER": "science",
    "GEOGRAPHER": "science",
    "GEOLOGIST": "science",
    "HISTORIAN": "science",
    "INVENTOR": "science",
    "LINGUIST": "science",
    "SOCIOLOGIST": "science",
    "STATISTICIAN": "science",
    "PHILOSOPHER": "science",
    "INSPIRATION": "other",
    # religion
    "RELIGIOUS FIGURE": "religion",
    "OCCULTIST": "religion",
    # exploration
    "EXPLORER": "exploration",
    "ASTRONAUT": "exploration",
    "MOUNTAINEER": "exploration",
    "PILOT": "exploration",
    # business
    "BUSINESSPERSON": "business",
    # sports
    "ATHLETE": "sports",
    "SOCCER PLAYER": "sports",
    "AMERICAN FOOTBALL PLAYER": "sports",
    "BADMINTON PLAYER": "sports",
    "BASEBALL PLAYER": "sports",
    "BASKETBALL PLAYER": "sports",
    "BOXER": "sports",
    "BULLFIGHTER": "sports",
    "CHESS PLAYER": "sports",
    "COACH": "sports",
    "CRICKETER": "sports",
    "CYCLIST": "sports",
    "FENCER": "sports",
    "GO PLAYER": "sports",
    "GOLFER": "sports",
    "GYMNAST": "sports",
    "HANDBALL PLAYER": "sports",
    "HOCKEY PLAYER": "sports",
    "MARTIAL ARTS": "sports",
    "POKER PLAYER": "sports",
    "RACING DRIVER": "sports",
    "REFEREE": "sports",
    "RUGBY PLAYER": "sports",
    "SKATER": "sports",
    "SKIER": "sports",
    "SNOOKER": "sports",
    "SWIMMER": "sports",
    "TABLE TENNIS PLAYER": "sports",
    "TENNIS PLAYER": "sports",
    "VOLLEYBALL PLAYER": "sports",
    "WRESTLER": "sports",
    "": "other",
}


def domain_for(occupation):
    return OCCUPATION_TO_DOMAIN.get((occupation or "").strip(), "other")


# ---------------------------------------------------------------------------
# Stage 0: load candidates from the cached Pantheon CSV (free, local)
# ---------------------------------------------------------------------------
def load_candidates(scan_depth):
    """Every eligible dead person, HPI-sorted and deduped, truncated to the
    scan depth plus an attrition buffer. Returns (rows, n_eligible)."""
    if not os.path.exists(CSV_BZ2):
        raise SystemExit(f"missing cached dataset: {CSV_BZ2}")

    rows = []
    with bz2.open(CSV_BZ2, "rt", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r.get("alive") != "FALSE":
                continue
            deathyear = (r.get("deathyear") or "").strip()
            if not deathyear:
                continue
            slug = (r.get("slug") or "").strip()
            wd_id = (r.get("wd_id") or "").strip()
            if not slug or not wd_id:
                continue
            hpi_raw = r.get("hpi_raw")
            try:
                hpi_raw_f = float(hpi_raw)
            except (TypeError, ValueError):
                continue
            try:
                death_year_i = int(float(deathyear))
            except ValueError:
                continue
            birthyear = (r.get("birthyear") or "").strip()
            birth_year_i = None
            if birthyear:
                try:
                    birth_year_i = int(float(birthyear))
                except ValueError:
                    birth_year_i = None
            rows.append({
                "wd_id": wd_id,
                "slug": slug,
                "name": r.get("name") or slug.replace("_", " "),
                "occupation": r.get("occupation") or "",
                "hpi_raw": hpi_raw_f,
                "hpi": r.get("hpi"),
                "birth_year": birth_year_i,
                "death_year": death_year_i,
                "birth_country": (r.get("bplace_country") or "").strip() or None,
                "is_group": (r.get("is_group") or "").strip().upper() == "TRUE",
            })

    rows.sort(key=lambda r: r["hpi_raw"], reverse=True)

    # de-dupe by wikidata QID, keep first (highest hpi) occurrence
    seen = set()
    deduped = []
    for r in rows:
        if r["wd_id"] in seen:
            continue
        seen.add(r["wd_id"])
        deduped.append(r)

    n_eligible = len(deduped)

    # Stage 1, structural pre-filter (free, local). Deliberately narrow:
    # `is_group` rows are bands/dynasties/crews rather than a person, and a
    # person-portrait game cannot use them. Everything else is left for the
    # ranked cut to judge, because no other cheap structural rule was found
    # that removes a meaningful share of the widened band without also
    # removing figures the games legitimately want (measured: is_group is 0
    # of the top 16,000 today, so this is a correctness guard rather than a
    # volume saving — the volume reduction comes from the ranked cut).
    kept = []
    dropped_group = 0
    for i, r in enumerate(deduped):
        r["pantheon_rank"] = i + 1
        if r["is_group"]:
            dropped_group += 1
            continue
        kept.append(r)

    limit = int(scan_depth * BUFFER_FACTOR)
    return kept[:limit], n_eligible, dropped_group


# ---------------------------------------------------------------------------
# Stage 2: resolve slugs to canonical current en.wikipedia article titles,
# following redirects, via the enwiki API in batches of 50 (1 call / 50).
# ---------------------------------------------------------------------------
def load_json_file(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return default
    return default


def save_json_file(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


def fetch_json(url, max_retries=6):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    delay = 1.0
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 429 or 500 <= e.code < 600:
                time.sleep(delay)
                delay = min(delay * 2, 30)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(delay)
            delay = min(delay * 2, 30)
            continue
    raise RuntimeError(f"failed to fetch after {max_retries} attempts: {url}")


def resolve_batch(slugs):
    """Return dict slug -> resolved canonical title, or None if missing."""
    titles_param = "|".join(slugs)
    qs = urllib.parse.urlencode({
        "action": "query",
        "titles": titles_param,
        "redirects": "1",
        "format": "json",
        "formatversion": "2",
    })
    url = f"https://en.wikipedia.org/w/api.php?{qs}"
    data = fetch_json(url)
    query = data.get("query", {})

    normalized = {n["from"]: n["to"] for n in query.get("normalized", [])}
    redirects = {r["from"]: r["to"] for r in query.get("redirects", [])}
    pages = {p.get("title"): p for p in query.get("pages", [])}

    result = {}
    for slug in slugs:
        t = slug.replace("_", " ")
        t = normalized.get(t, t)
        # follow redirect chain (bounded)
        for _ in range(6):
            nxt = redirects.get(t)
            if nxt is None or nxt == t:
                break
            t = nxt
        page = pages.get(t)
        if page is None or page.get("missing"):
            result[slug] = None
        else:
            result[slug] = page.get("title")
    return result


def resolve_wave(candidates, cache, offline=False):
    """Resolve titles for one wave. Cached on disk, so an interrupted run
    refetches nothing."""
    to_fetch = [c["slug"] for c in candidates if c["slug"] not in cache]
    if offline:
        if to_fetch:
            print(f"  [offline] {len(to_fetch)} slugs have no cached title; "
                  f"they will be dropped")
        return cache
    for i in range(0, len(to_fetch), BATCH_SIZE):
        batch = to_fetch[i:i + BATCH_SIZE]
        cache.update(resolve_batch(batch))
        time.sleep(MIN_REQUEST_GAP)
        if (i // BATCH_SIZE) % 20 == 0:
            print(f"    titles {min(i + BATCH_SIZE, len(to_fetch))}/{len(to_fetch)}...")
            save_json_file(RESOLUTION_CACHE, cache)
    save_json_file(RESOLUTION_CACHE, cache)
    return cache


# ---------------------------------------------------------------------------
# Stage 3: WikiProject importance assessments (1 call / 50).
#
# The curated project buckets, the peak/breadth scoring and the HTTP cache
# all live in build_salience.py and are reused rather than copied: SALIENCE.md
# records that those bucket lists were built empirically from a live probe
# (WikiProject Military history abolished importance ratings; Biography
# delegates to inconsistently-named work groups; Arctic/Antarctica are the
# only home that rates polar explorers), and duplicating them here would
# guarantee the two copies drift apart.
# ---------------------------------------------------------------------------
def load_salience_module():
    try:
        import build_salience  # noqa: WPS433 (same directory, stdlib-only)
        for fn in ("harvest_page_facts", "score_assessments",
                   "harvest_in_our_time", "harvest_great_lives",
                   "harvest_greatest_polls", "norm_name"):
            if not hasattr(build_salience, fn):
                raise AttributeError(fn)
        return build_salience
    except Exception as e:  # noqa: BLE001 — degrade, never crash the build
        print(f"build_universe: WARNING — could not use build_salience.py "
              f"({e!r}). Falling back to PURE HPI ORDER, which is the old "
              f"broken behaviour at a wider depth. Fix the import before "
              f"trusting this output.", file=sys.stderr)
        return None


def assess_wave(titles, bs, cache, offline=False):
    """titles -> {title: {"hist": float|None, "n": int, "class": float}}.
    Incrementally cached on disk; safe to interrupt and re-run."""
    todo = [t for t in titles if t and t not in cache]
    if not todo:
        return cache
    for i in range(0, len(todo), 200):
        chunk = todo[i:i + 200]
        facts = bs.harvest_page_facts(chunk, offline=offline, verbose=False)
        for t in chunk:
            rec = facts.get(t)
            if rec is None:
                # No answer from the API for this title. Record the miss so a
                # rerun does not hammer it again; scored as "no opinion".
                cache[t] = {"hist": None, "n": 0, "class": 0.0}
                continue
            raw, detail = bs.score_assessments(rec.get("assessments"))
            cache[t] = {
                "hist": None if raw is None else round(raw, 3),
                "n": detail.get("n_history_projects", 0),
                "class": detail.get("class_value", 0.0),
            }
        save_json_file(ASSESSMENT_CACHE, cache)
        print(f"    assessments {min(i + 200, len(todo))}/{len(todo)}...")
    return cache


# ---------------------------------------------------------------------------
# Stage 4: blend, rank, cut (free, local)
# ---------------------------------------------------------------------------
def percentiles(values):
    """Average-rank percentile, 0-100, ties averaged. Matches the convention
    in build_scores.py / build_salience.py."""
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [100.0]
    order = sorted(range(n), key=lambda i: values[i])
    out = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0
        pct = 100.0 * avg_rank / (n - 1)
        for k in range(i, j + 1):
            out[order[k]] = pct
        i = j + 1
    return out


def _wave_bound(best_unassessed_hpi_pct):
    """Upper bound on the admit_score any not-yet-assessed candidate could
    reach: perfect history percentile plus the maximum corpus bonus. If the
    current cut score already exceeds this, no later wave can change the
    admitted set and the remaining fetches are provably unnecessary."""
    return (W_HPI * best_unassessed_hpi_pct + W_SALIENCE * 100.0
            + max(CORPUS_BONUS.values()))


def build(args):
    scan_depth = args.scan_depth
    target = args.target

    print("[0/4] Pantheon CSV (local, 0 calls)")
    candidates, n_eligible, dropped_group = load_candidates(scan_depth)
    print(f"  {n_eligible} eligible dead people in the source")
    print(f"  scanning the top {scan_depth} by HPI "
          f"(pulled {len(candidates)} rows incl. attrition buffer; "
          f"{dropped_group} is_group rows dropped by the structural pre-filter)")

    bs = load_salience_module()

    # HPI percentile is computed over the WHOLE scanned band, so it is a
    # stable property of a candidate and does not shift as waves are added.
    hpi_pct_by_slug = {}
    hpis = [c["hpi_raw"] for c in candidates]
    for c, p in zip(candidates, percentiles(hpis)):
        hpi_pct_by_slug[c["slug"]] = p

    # --- audience corpora: 3 HTTP calls total, size-independent -----------
    iot_titles, iot_plain, gl_titles, poll_titles = set(), set(), set(), set()
    if bs is not None:
        try:
            iot_targets, iot_plains = bs.harvest_in_our_time(
                offline=args.offline, verbose=False)
            iot_titles, iot_plain = set(iot_targets), set(iot_plains)
            gl_titles = set(bs.harvest_great_lives(
                offline=args.offline, verbose=False))
            poll_targets, _ = bs.harvest_greatest_polls(
                offline=args.offline, verbose=False)
            poll_titles = set(poll_targets)
            print(f"  audience corpora: In Our Time {len(iot_titles)}, "
                  f"Great Lives {len(gl_titles)}, greatest-polls {len(poll_titles)}")
        except Exception as e:  # noqa: BLE001
            print(f"  WARNING — audience corpora unavailable ({e!r}); the "
                  f"bounded corpus bonus is disabled for this run",
                  file=sys.stderr)

    iot_norm = {bs.norm_name(t) for t in (iot_titles | iot_plain)} if bs else set()
    gl_norm = {bs.norm_name(t) for t in gl_titles} if bs else set()

    def corpus_hits(title, name):
        if bs is None:
            return 0
        n = bs.norm_name(name or title)
        nt = bs.norm_name(title)
        hits = 0
        if title in iot_titles or title in iot_plain or n in iot_norm or nt in iot_norm:
            hits += 1
        if title in gl_titles or n in gl_norm or nt in gl_norm:
            hits += 1
        if title in poll_titles:
            hits += 1
        return hits

    # --- stages 2+3, in waves down the HPI order --------------------------
    res_cache = load_json_file(RESOLUTION_CACHE, {})
    asr_cache = load_json_file(ASSESSMENT_CACHE, {})

    scored = []          # admitted-candidate records, built up wave by wave
    seen_titles = set()
    dropped_missing = dropped_dup = 0
    waves_run = 0
    stopped_early_at = None

    pos = 0
    while pos < len(candidates):
        wave = candidates[pos:pos + args.wave_size]
        waves_run += 1
        print(f"[2/4] wave {waves_run}: resolving {len(wave)} enwiki titles "
              f"(1 call / {BATCH_SIZE})")
        res_cache = resolve_wave(wave, res_cache, offline=args.offline)

        wave_titles = []
        wave_rows = []
        for c in wave:
            title = res_cache.get(c["slug"])
            if not title:
                dropped_missing += 1
                continue
            if title in seen_titles:
                dropped_dup += 1
                continue
            seen_titles.add(title)
            wave_titles.append(title)
            wave_rows.append((c, title))

        print(f"[3/4] wave {waves_run}: WikiProject assessments for "
              f"{len(wave_titles)} titles (1 call / {BATCH_SIZE})")
        if bs is not None:
            asr_cache = assess_wave(wave_titles, bs, asr_cache,
                                    offline=args.offline)

        for c, title in wave_rows:
            a = asr_cache.get(title) or {"hist": None, "n": 0, "class": 0.0}
            scored.append({
                "cand": c,
                "title": title,
                "hpi_pct": hpi_pct_by_slug[c["slug"]],
                "hist_raw": a.get("hist"),
                "n_projects": a.get("n", 0) or 0,
                "class_value": a.get("class", 0.0),
                "corpus_hits": corpus_hits(title, c["name"]),
            })

        pos += len(wave)

        # --- the stop rule ------------------------------------------------
        # Score what we have; if the cut is already above the best a later
        # wave could reach, the rest is provably unnecessary.
        if len(scored) >= target and pos < len(candidates):
            rank_and_score(scored)
            cut = sorted((s["admit_score"] for s in scored),
                         reverse=True)[target - 1]
            best_next = hpi_pct_by_slug[candidates[pos]["slug"]]
            bound = _wave_bound(best_next)
            if cut > bound:
                stopped_early_at = pos
                print(f"  stop rule fired: cut score {cut:.2f} exceeds the "
                      f"best possible score {bound:.2f} of anything below "
                      f"Pantheon rank {candidates[pos]['pantheon_rank']} — "
                      f"skipping {len(candidates) - pos} candidates unfetched")
                break
            print(f"  stop rule not met (cut {cut:.2f} <= bound {bound:.2f}); "
                  f"continuing")

    print("[4/4] blend, rank, cut (local, 0 calls)")
    rank_and_score(scored)
    scored.sort(key=lambda s: (-s["admit_score"], s["cand"]["pantheon_rank"]))
    admitted = scored[:target]

    people = []
    for i, s in enumerate(admitted):
        c = s["cand"]
        people.append({
            "name": c["name"],
            "wiki_title": s["title"],
            "qid": c["wd_id"],
            "birth_year": c["birth_year"],
            "death_year": c["death_year"],
            "domain": domain_for(c["occupation"]),
            "occupation": c["occupation"],
            "birth_country": c["birth_country"],
            "proxy_rank": i + 1,
            "pantheon_rank": c["pantheon_rank"],
            # every input kept alongside the blend so the ranking stays
            # inspectable, per the house convention in salience.json
            "admit_score": round(s["admit_score"], 2),
            "hpi_pct": round(s["hpi_pct"], 2),
            "history_importance": s["hist_raw"],
            "history_projects": s["n_projects"],
            "salience_pct": round(s["salience_pct"], 2),
            "corpus_hits": s["corpus_hits"],
        })

    stats = {
        "eligible_in_source": n_eligible,
        "scan_depth": scan_depth,
        "target_count": target,
        "admitted": len(people),
        "waves_run": waves_run,
        "stopped_early_after": stopped_early_at,
        "candidates_scored": len(scored),
        "dropped_no_enwiki_article": dropped_missing,
        "dropped_duplicate_title": dropped_dup,
        "dropped_is_group": dropped_group,
        "with_history_rating": sum(1 for s in scored if s["hist_raw"] is not None),
        "with_corpus_hit": sum(1 for s in scored if s["corpus_hits"]),
    }
    return people, stats


def rank_and_score(scored):
    """Within-domain percentile of the history signal, shrunk toward the
    candidate's own HPI percentile by evidence count, then blended."""
    by_domain = {}
    for s in scored:
        d = domain_for(s["cand"]["occupation"])
        s["_domain"] = d
        by_domain.setdefault(d, []).append(s)

    for d, group in by_domain.items():
        rated = [s for s in group if s["hist_raw"] is not None]
        if len(rated) >= 5:
            pcts = percentiles([s["hist_raw"] for s in rated])
            for s, p in zip(rated, pcts):
                s["_hist_pct"] = p
        else:
            # Too few rated members of this domain to percentile meaningfully;
            # treat the whole domain as "no opinion" rather than inventing an
            # ordering out of three data points.
            for s in group:
                s["_hist_pct"] = None
        for s in group:
            s.setdefault("_hist_pct", None)
            if s["hist_raw"] is None:
                s["_hist_pct"] = None

    for s in scored:
        hist_pct = s.get("_hist_pct")
        n = s["n_projects"]
        if hist_pct is None or n <= 0:
            # No opinion: the history signal neither promotes nor demotes.
            s["salience_pct"] = s["hpi_pct"]
        else:
            conf = n / (n + SHRINK_K)
            s["salience_pct"] = conf * hist_pct + (1.0 - conf) * s["hpi_pct"]
        s["admit_score"] = (W_HPI * s["hpi_pct"]
                            + W_SALIENCE * s["salience_pct"]
                            + CORPUS_BONUS.get(s["corpus_hits"], 15.0))


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scan-depth", type=int, default=SCAN_DEPTH,
                    help="how deep into Pantheon's HPI order to look")
    ap.add_argument("--target", type=int, default=TARGET_COUNT,
                    help="how many people survive into the output")
    ap.add_argument("--wave-size", type=int, default=WAVE_SIZE,
                    help="candidates fetched per wave (see the stop rule)")
    ap.add_argument("--out", default=OUTPUT,
                    help="output path (default: universe_people.json). Use a "
                         "scratch path to evaluate a change without "
                         "disturbing the live pipeline.")
    ap.add_argument("--offline", action="store_true",
                    help="score from the on-disk caches only; make no HTTP "
                         "calls. Uncached candidates are dropped.")
    args = ap.parse_args()

    people, stats = build(args)

    out = {
        "generatedOn": GENERATED_ON,
        "source": ("MIT Pantheon 2.0 (2025 update), person_2025_update.csv.bz2, "
                   "https://pantheon.world/data/datasets — filtered to alive==FALSE "
                   "with a known death year, en.wikipedia titles canonicalized via "
                   "action=query&redirects=1, then re-ranked by "
                   f"{W_HPI:g} x HPI-percentile + {W_SALIENCE:g} x "
                   "history-salience-percentile "
                   "(English Wikipedia WikiProject importance ratings, percentiled "
                   "WITHIN DOMAIN and shrunk toward no-opinion by how many projects "
                   "actually rated the subject) plus a bounded audience-corpus bonus. "
                   "See the module docstring and tools/fame/SALIENCE.md."),
        "ranking": {
            "w_hpi": W_HPI,
            "w_salience": W_SALIENCE,
            "shrink_k": SHRINK_K,
            "corpus_bonus": CORPUS_BONUS,
            "scan_depth": args.scan_depth,
            "target_count": args.target,
        },
        "stats": stats,
        "people": people,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {args.out} ({len(people)} people)")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
