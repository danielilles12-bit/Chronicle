#!/usr/bin/env python3
"""Build ~500 extra "Map of a Life" figures from Wikidata.

Pulls famous *deceased* humans that have a birthplace AND deathplace with
coordinates, birth/death years, an occupation and a cross-wiki "fame" score
(sitelink count). Cleans, de-duplicates against the hand-made figures already
in data/figures.json, assigns a difficulty tier from the fame score, and (with
--write) merges the new people in after the originals.

Run a sample first (no --write) to eyeball quality:
    python3 tools/build_figures.py --limit 60
Then generate for real:
    python3 tools/build_figures.py --write
"""
import argparse
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIGURES = os.path.join(ROOT, "data", "figures.json")

# QLever is a fast, independent full mirror of Wikidata — used here because the
# official query.wikidata.org service is in an outage and throttling to 1 req /
# 1000s. Same SPARQL, but no built-in prefixes, so we declare them ourselves.
ENDPOINT = "https://qlever.dev/api/wikidata"
UA = "ChronicleHistoryApp/1.0 (daniel.illes12@gmail.com)"

PREFIXES = """
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""

# Occupation labels that are too generic / unhelpful as a hint.
OCC_BAN = {
    "human", "aristocrat", "noble", "nobleman", "noblewoman", "person",
    "businessperson", "official", "civil servant", "researcher",
}

# SPARQL: one row per person, multi-valued bits collapsed with SAMPLE /
# GROUP_CONCAT so the result set stays one-line-per-human.
QUERY = """
SELECT ?item ?name ?byear ?dyear ?bplace ?bcountry ?dplace ?dcountry ?bc ?dc ?sl ?occs WHERE {
  {
    SELECT ?item (SAMPLE(?nm) AS ?name)
           (SAMPLE(?by) AS ?byear) (SAMPLE(?dy) AS ?dyear)
           (SAMPLE(?bpl) AS ?bplace) (SAMPLE(?bco) AS ?bcountry)
           (SAMPLE(?dpl) AS ?dplace) (SAMPLE(?dco) AS ?dcountry)
           (SAMPLE(?bcoord) AS ?bc) (SAMPLE(?dcoord) AS ?dc)
           (SAMPLE(?slv) AS ?sl)
           (GROUP_CONCAT(DISTINCT ?occL; separator="|") AS ?occs)
    WHERE {
      ?item wdt:P31 wd:Q5 ; wdt:P569 ?bd ; wdt:P570 ?dd ;
            wdt:P19 ?bp ; wdt:P20 ?dp ; wikibase:sitelinks ?slv .
      FILTER(?slv >= %(MINSL)d)
      ?bp wdt:P625 ?bcoord . ?dp wdt:P625 ?dcoord .
      ?item rdfs:label ?nm FILTER(LANG(?nm)="en") .
      ?bp rdfs:label ?bpl FILTER(LANG(?bpl)="en") .
      ?dp rdfs:label ?dpl FILTER(LANG(?dpl)="en") .
      OPTIONAL { ?bp wdt:P17 ?bcty. ?bcty rdfs:label ?bco FILTER(LANG(?bco)="en") }
      OPTIONAL { ?dp wdt:P17 ?dcty. ?dcty rdfs:label ?dco FILTER(LANG(?dco)="en") }
      OPTIONAL { ?item wdt:P106 ?occ. ?occ rdfs:label ?occL FILTER(LANG(?occL)="en") }
      BIND(YEAR(?bd) AS ?by) BIND(YEAR(?dd) AS ?dy)
    }
    GROUP BY ?item ORDER BY DESC(?sl) LIMIT %(LIMIT)d
  }
}
"""


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", s)).strip()


def fetch(min_sl, limit, tries=6):
    import time
    q = PREFIXES + (QUERY % {"MINSL": min_sl, "LIMIT": limit})
    req = urllib.request.Request(ENDPOINT, data=q.encode("utf-8"),
                                 headers={"User-Agent": UA,
                                          "Accept": "application/sparql-results+json",
                                          "Content-Type": "application/sparql-query"})
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)["results"]["bindings"]
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503) or attempt == tries:
                raise
            wait = min(int(e.headers.get("Retry-After") or 20), 60)
            print("  server busy (%d); waiting %ds then retrying (%d/%d)..."
                  % (e.code, wait, attempt, tries))
            time.sleep(wait + 1)


def parse_point(wkt):
    m = re.match(r"Point\(([-0-9.]+) ([-0-9.]+)\)", wkt or "", re.I)
    if not m:
        return None
    lon, lat = float(m.group(1)), float(m.group(2))
    return round(lat, 2), round(lon, 2)


def cell(row, key):
    return row[key]["value"] if key in row else ""


def slugify(name, used):
    base = re.sub(r"[^a-z0-9]+", "-", norm(name)).strip("-") or "figure"
    s = base
    n = 2
    while s in used:
        s = "%s-%d" % (base, n)
        n += 1
    used.add(s)
    return s


def occupation_phrase(occs):
    parts = [p.strip() for p in (occs or "").split("|") if p.strip()]
    parts = [p for p in parts if p.lower() not in OCC_BAN]
    if not parts:
        return None
    # prefer up to two, the shortest/most concrete first
    parts = sorted(dict.fromkeys(parts), key=len)[:2]
    phrase = " and ".join(parts)
    return phrase[0].upper() + phrase[1:]


ROMAN = re.compile(r"^[ivxlcdm]+$")


def variants_for(name):
    n = norm(name)
    out = {n}
    toks = n.split()
    if len(toks) >= 2 and not ROMAN.match(toks[-1]) and len(toks[-1]) >= 3:
        out.add(toks[-1])               # surname
    out.discard("")
    return sorted(out)


def build_entry(row, used_ids):
    name = cell(row, "name").strip()
    name = re.sub(r"\s*\(.*?\)\s*", "", name).strip()   # drop "(disambiguator)"
    try:
        by = int(cell(row, "byear"))
        dy = int(cell(row, "dyear"))
    except ValueError:
        return None
    if not name or len(name) < 2:
        return None
    if not (-3000 <= by <= 2025 and -3000 <= dy <= 2025):
        return None
    span = dy - by
    if span < 5 or span > 115:
        return None
    bcoord = parse_point(cell(row, "bc"))
    dcoord = parse_point(cell(row, "dc"))
    if not bcoord or not dcoord:
        return None
    occ = occupation_phrase(cell(row, "occs"))
    if not occ:
        return None

    def place(lbl, country):
        lbl = (lbl or "").strip()
        country = (country or "").strip()
        return "%s, %s" % (lbl, country) if country and country not in lbl else lbl

    return {
        "id": slugify(name, used_ids),
        "name": name,
        "variants": variants_for(name),
        "occupation": occ,
        "birth": {"year": by, "place": place(cell(row, "bplace"), cell(row, "bcountry")),
                  "lat": bcoord[0], "lon": bcoord[1]},
        "death": {"year": dy, "place": place(cell(row, "dplace"), cell(row, "dcountry")),
                  "lat": dcoord[0], "lon": dcoord[1]},
        "_sl": int(cell(row, "sl") or 0),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-sitelinks", type=int, default=80)
    ap.add_argument("--limit", type=int, default=1300)
    ap.add_argument("--target", type=int, default=500)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    existing = json.load(open(FIGURES))
    seen = set()
    for f in existing:
        seen.add(norm(f["name"]))
        for v in f.get("variants", []):
            seen.add(norm(v))
    used_ids = {f["id"] for f in existing}

    print("querying Wikidata (min sitelinks %d, limit %d)..." % (args.min_sitelinks, args.limit))
    rows = fetch(args.min_sitelinks, args.limit)
    print("  %d rows returned" % len(rows))

    cands = []
    for row in rows:
        e = build_entry(row, used_ids)
        if not e:
            continue
        nm = norm(e["name"])
        if nm in seen:
            continue
        seen.add(nm)
        cands.append(e)
    print("  %d clean, de-duplicated candidates" % len(cands))

    cands.sort(key=lambda e: e["_sl"], reverse=True)

    # Difficulty spread: easy = household names (top of the fame ranking),
    # hard = drawn from deeper (less famous) so the hard tier really bites.
    t = args.target
    n_easy, n_med = int(t * 0.35), int(t * 0.35)
    n_hard = t - n_easy - n_med
    easy = cands[:n_easy]
    med = cands[n_easy:n_easy + n_med]
    # step through the deeper pool for hard, so they're less famous but real
    deep = cands[n_easy + n_med:]
    if len(deep) > n_hard:
        step = len(deep) / float(n_hard)
        hard = [deep[int(i * step)] for i in range(n_hard)]
    else:
        hard = deep
    for e in easy:
        e["difficulty"] = "easy"
    for e in med:
        e["difficulty"] = "medium"
    for e in hard:
        e["difficulty"] = "hard"
    chosen = easy + med + hard

    print("\nDifficulty split: easy %d / medium %d / hard %d (total %d)"
          % (len(easy), len(med), len(hard), len(chosen)))
    for tier, lst in (("EASY", easy), ("MEDIUM", med), ("HARD", hard)):
        sample = ", ".join("%s (%d)" % (e["name"], e["_sl"]) for e in lst[:8])
        print("  %-7s sl-range %d..%d  e.g. %s"
              % (tier, lst[-1]["_sl"], lst[0]["_sl"], sample))

    if not args.write:
        print("\n(sample run — nothing written; pass --write to merge into figures.json)")
        return

    for e in chosen:
        e.pop("_sl", None)
    merged = existing + chosen
    with open(FIGURES, "w") as fh:
        json.dump(merged, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("\nWROTE %d figures (%d original + %d new) -> %s"
          % (len(merged), len(existing), len(chosen), FIGURES))


if __name__ == "__main__":
    main()
