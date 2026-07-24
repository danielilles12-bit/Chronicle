#!/usr/bin/env python3
"""
Build tools/fame/universe_people.json — a candidate universe of the most
famous DEAD historical figures, ranked by the MIT Pantheon Historical
Popularity Index (HPI).

Source: Pantheon 2.0, 2025 update
  https://storage.googleapis.com/pantheon-public-data/person_2025_update.csv.bz2
Cached locally at tools/fame/raw/person_2025_update.csv.bz2

Python 3.9, stdlib only.
"""
import bz2
import csv
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(HERE, "raw")
CSV_BZ2 = os.path.join(RAW_DIR, "person_2025_update.csv.bz2")
RESOLUTION_CACHE = os.path.join(RAW_DIR, "wiki_title_resolution_cache.json")
OUTPUT = os.path.join(HERE, "universe_people.json")

USER_AGENT = "DeadFamousIntake/1.0 (daniel.illes12@gmail.com)"
GENERATED_ON = "2026-07-22"
TARGET_COUNT = 4000
CANDIDATE_BUFFER = 4700  # pull extra rows to absorb resolution attrition
BATCH_SIZE = 50
MIN_REQUEST_GAP = 0.15  # ~6-7 req/s, under the 8 req/s ceiling

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
# Step 1: load candidates from the cached Pantheon CSV
# ---------------------------------------------------------------------------
def load_candidates():
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

    return deduped[:CANDIDATE_BUFFER]


# ---------------------------------------------------------------------------
# Step 2: resolve slugs to canonical current en.wikipedia article titles,
# following redirects, via the enwiki API in batches of 50.
# ---------------------------------------------------------------------------
def load_cache():
    if os.path.exists(RESOLUTION_CACHE):
        with open(RESOLUTION_CACHE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(RESOLUTION_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


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


def resolve_all(candidates):
    cache = load_cache()
    to_fetch = [c["slug"] for c in candidates if c["slug"] not in cache]

    for i in range(0, len(to_fetch), BATCH_SIZE):
        batch = to_fetch[i:i + BATCH_SIZE]
        resolved = resolve_batch(batch)
        cache.update(resolved)
        time.sleep(MIN_REQUEST_GAP)
        if (i // BATCH_SIZE) % 10 == 0:
            print(f"  resolved {min(i + BATCH_SIZE, len(to_fetch))}/{len(to_fetch)} new titles...")

    save_cache(cache)
    return cache


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Loading candidates from cached Pantheon CSV...")
    candidates = load_candidates()
    print(f"  {len(candidates)} dead-person candidates with QID+slug, sorted by HPI")

    print("Resolving en.wikipedia titles (following redirects)...")
    cache = resolve_all(candidates)

    people = []
    dropped_missing = 0
    dropped_dup_title = 0
    seen_titles = set()
    for c in candidates:
        if len(people) >= TARGET_COUNT:
            break
        title = cache.get(c["slug"])
        if not title:
            dropped_missing += 1
            continue
        if title in seen_titles:
            dropped_dup_title += 1
            continue
        seen_titles.add(title)
        people.append({
            "name": c["name"],
            "wiki_title": title,
            "qid": c["wd_id"],
            "birth_year": c["birth_year"],
            "death_year": c["death_year"],
            "domain": domain_for(c["occupation"]),
            "proxy_rank": len(people) + 1,
        })

    print(f"  kept {len(people)} people; dropped {dropped_missing} with no enwiki article, "
          f"{dropped_dup_title} duplicate-title collisions")

    out = {
        "generatedOn": GENERATED_ON,
        "source": ("MIT Pantheon 2.0 (2025 update), person_2025_update.csv.bz2, "
                   "https://pantheon.world/data/datasets — filtered to alive==FALSE "
                   "with a known death year, ranked by hpi_raw (Historical Popularity "
                   "Index), en.wikipedia titles canonicalized via action=query&redirects=1"),
        "people": people,
    }
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Wrote {OUTPUT} ({len(people)} people)")


if __name__ == "__main__":
    main()
