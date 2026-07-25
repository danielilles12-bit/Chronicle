# HARVEST_AUDIENCE.md — harvesting people from audience-matched sources

**Script:** `tools/fame/harvest_audience.py`
**Output:** `tools/fame/audience_candidates.json` (+ `tools/fame/raw/audience_<source>.json`)
**Run date of the figures below:** 2026-07-25
**Python:** 3.9, stdlib only. No dependencies, no Node.

---

## 1. Why this exists

`tools/fame/universe_people.json` — the pool every Face Value and Lifeline
round is ultimately drawn from — is built from **one** source, the MIT
Pantheon Historical Popularity Index, and is then cut off at
`TARGET_COUNT = 4000` in `build_universe.py`. That single number discards
51,819 of 55,819 eligible people.

The blindspot audit (`tools/out/content-blindspots-2026-07-25/`) measured
what falls out of the pool at that cut. Of 90 canon figures a history
enthusiast would place instantly, **46 were already in the source data and
were removed by the cut alone**. What survives is heavily skewed toward one
kind of person:

| occupation family (audit taxonomy) | in universe (n=4000) | share |
| --- | ---: | ---: |
| statesman | 1301 | 32.5% |
| scientist | 486 | 12.2% |
| religious | 474 | 11.9% |
| writer | 404 | 10.1% |
| … | | |
| **athlete** | **52** | **1.3%** |
| **explorer** | **48** | **1.2%** |
| **inventor-engineer** | **46** | **1.2%** |
| activist-reformer | 43 | 1.1% |

The launch review's substantive complaint was the same thing from the
player's side: the month played **narrow** — rulers, commanders, senior
clergy, war, formal religion, monumental architecture, and death as the
recurring payoff. Everyday life, work, science, medicine, sport,
exploration and culture were all thin.

Pantheon's HPI is a general-population traffic measure. Ranking by it and
cutting at 4000 concentrates precisely on the people everybody already
sees. So this harvester attacks the problem from the other end:

1. **Editorial sources, not traffic.** Inclusion in the Oxford DNB is a
   judgement by editors that a person matters to British history. That is
   a different, better signal for this game than "how many people googled
   them last year".
2. **Sampled across occupation families, not ranked globally.** The harvest
   budget per family is set from the audit's own numbers — starved families
   get a large quota and a sitelink floor near the ground, saturated ones
   get a small quota and a high floor. Variety is built in by
   construction, not filtered in afterwards.

**The audience bar** is Rest Is History listeners: curious, Anglophone,
well-read, not academic.

### What is deliberately *not* a selection axis

**Gender.** Product direction, 2026-07-25: no gender-filtered queries, no
targets, no quotas, no machinery — and never filter *against*. Gender is
*recorded* per candidate (the game needs the fact) and is used nowhere in
selection, ranking or tiering. Where two candidates are otherwise equal a
human can use it as a tie-break; the pipeline does not. A better mix falls
out of harvesting the starved families anyway, which is the point.

**Sitelink count.** It measures general-population fame — the exact bias
being corrected. It is used only as a **floor** against the genuinely
unknown, and as a tie-break *within* a single occupation stratum, where it
only ever compares like with like. It never ranks a cricketer against a
king.

---

## 2. Sources — what worked and what it yielded

All source counts were confirmed by live query on 2026-07-25.

| id | source | universe of the source (dead + image + enwiki) | how it is sampled |
| --- | --- | ---: | --- |
| `odnb` | Oxford Dictionary of National Biography, Wikidata **P1415** | **24,276** (of 63,041 items carrying an ODNB ID) | one stratum per occupation |
| `adb` | Australian Dictionary of Biography, **P1907** | **4,817** | pulled whole |
| `dib` | Dictionary of Irish Biography, **P6829** | **2,748** | pulled whole |
| `inourtime` | BBC Radio 4 *In Our Time* episode list | 1,108 wikitable rows | every row's subject resolved, humans kept |
| `occupations` | Worldwide Wikidata occupation families | — | one stratum per occupation, no nationality filter |
| `nzpacific` | Te Ara / DNZB **P2745** + NZ/Oceania nationality, birthplace and ethnic group | DNZB 2,115; NZ citizens 7,257; Pacific ethnic groups 179; small Pacific nations 600 | seven strata, all image-free |

### Property IDs verified this run

| property | meaning | status |
| --- | --- | --- |
| P1415 | Oxford DNB ID | confirmed, 63,041 items |
| P1907 | Australian Dictionary of Biography ID | confirmed |
| P6829 | Dictionary of Irish Biography ID | confirmed |
| **P2745** | **Dictionary of New Zealand Biography (Te Ara) ID** | **was UNVERIFIED in the brief — confirmed live via `wbsearchentities`** |
| P1816 | National Portrait Gallery (London) person ID | confirmed, 21,756 dead + image + enwiki — **not used this run**, held in reserve |
| P4823 | American National Biography ID | confirmed, 14,517 dead + image + enwiki — **not used this run**, held in reserve |

P1816 is the most interesting of the two unused ones: an NPG sitter is by
definition someone whose *portrait* was judged nationally significant,
which is a direct signal for Face Value. P4823 is the obvious next source
if North America needs deepening.

### Yields

See §7 for the numbers from the 2026-07-25 run.

---

## 3. How to re-run

```bash
# network check only (one cheap request to each endpoint)
python3 tools/fame/harvest_audience.py --verify-only

# full run (~1-1.5 h cold, minutes when the cache is warm)
python3 tools/fame/harvest_audience.py

# one source at a time
python3 tools/fame/harvest_audience.py --source odnb
python3 tools/fame/harvest_audience.py --source inourtime --source nzpacific

# quick pass: every stratum limit scaled down
python3 tools/fame/harvest_audience.py --limit-scale 0.25

# ignore existing raw/audience_*.json and re-select
python3 tools/fame/harvest_audience.py --force
```

**Resumability, at three levels:**

1. Every SPARQL response is cached on disk under
   `tools/fame/cache/audience_sparql/`, keyed by a hash of the exact query
   text (so LIMIT/OFFSET pages cache separately).
2. Every Wikidata entity and label is cached **per QID** under
   `tools/fame/cache/audience_wd_entity/` and `…_label/`, not per batch —
   so a re-run with a different candidate set reuses everything it already
   has.
3. Each source's selection phase writes `raw/audience_<source>.json` and is
   skipped entirely on a later run unless `--force`.

`tools/fame/cache/` is a gitignored symlink to `cache.nosync/`, and
`tools/fame/raw/` is gitignored, so none of this lands in the repo.

**Conventions reused from `tools/fame/fetch_metrics.py`:** the descriptive
`User-Agent` (both APIs return 403 to a bare request), the throttle, the
retry/backoff on 429/5xx, the "cache successes and definitive failures but
never transient ones" policy, and the never-crash-on-a-bad-row rule.
Throttles here are 1.5 s between SPARQL queries (WDQS aggregates are
expensive server-side) and 8 req/s for the MediaWiki action APIs.

---

## 4. The queries

### 4.1 Selection — deliberately lean

Selection and enrichment are **two phases**. A single query that also
pulled labels, coordinates and occupations for a 24k-row set times WDQS out
(measured: the bare `COUNT` over ODNB alone takes 16–55 s). So selection
returns three columns and nothing else, and enrichment happens over the
`wbgetentities` API, which is fast, batched 50 at a time and cached per QID.

```sparql
SELECT DISTINCT ?p ?sl ?a WHERE {
  # <-- per-stratum WHERE clause goes here, e.g.
  #     ?p wdt:P1415 ?dictid .
  #     ?p wdt:P106 wd:Q11900058 .        # explorer
  ?p wdt:P570 ?dod .                      # dead (excludes living people)
  ?p wdt:P18 ?img .                       # OPTIONAL LINE -- see below
  ?a schema:about ?p ; schema:isPartOf <https://en.wikipedia.org/> .
  ?p wikibase:sitelinks ?sl .
  FILTER(?sl >= {floor})
}
ORDER BY DESC(?sl)
LIMIT {limit}
```

Per-stratum WHERE clauses:

| source | WHERE clause |
| --- | --- |
| ODNB | `?p wdt:P1415 ?dictid . ?p wdt:P106 wd:<occ> .` (one per occupation) |
| ODNB catch-all | `?p wdt:P1415 ?dictid .` — floor 25, for entries whose occupations are outside the table |
| ADB / DIB | `?p wdt:P1907 ?dictid .` / `?p wdt:P6829 ?dictid .` — plus a second, image-free lane at floor 4 |
| occupations | `?p wdt:P106 wd:<occ> .` — no dictionary, no nationality |
| nzpacific/dnzb | `?p wdt:P2745 ?dnzb .` — taken whole |
| nzpacific/indigenous-australian | `VALUES ?eth { wd:Q170355 wd:Q726673 } { ?p wdt:P172 ?eth } UNION { ?p wdt:P27 wd:Q408 ; wdt:P172 ?eth }` |
| nzpacific/nz-citizen | `?p wdt:P27 wd:Q664 .` |
| nzpacific/born-in-nz | `?p wdt:P19 ?bp . ?bp wdt:P17 wd:Q664 .` |
| nzpacific/pacific-peoples | `VALUES ?eth { wd:Q6122670 wd:Q170355 wd:Q1283606 wd:Q37732 wd:Q726673 } ?p wdt:P172 ?eth .` |
| nzpacific/oceania-citizens | `VALUES ?c { …16 Oceania country QIDs… } ?p wdt:P27 ?c .` |
| nzpacific/born-in-oceania | `VALUES ?c { …same… } ?p wdt:P19 ?bp . ?bp wdt:P17 ?c .` |

**Why `ORDER BY DESC(?sl)` is not the bias it looks like.** The *stratum*
does the choosing — "ODNB, cricketers, above this floor". Sorting inside
one occupation only compares cricketers with cricketers. It never lets a
king outrank a cricketer, which is the failure mode of a global HPI
ranking.

**Living people** are excluded at the query level by requiring `P570`.
`is_living` and `is_living_politician` are still computed after enrichment
and re-checked, so nothing slips through silently.

**The image line is optional per stratum** (`require_image`, the 5th
element of a stratum tuple). Requiring a Wikidata portrait is a **Face
Value** constraint — Lifeline needs birth and death coordinates and no
portrait at all. Applying it everywhere silently deleted exactly the
pre-colonial figures the map game most needs: Tupaia, the Ra'iātean
navigator who sailed with Cook and died in Batavia, carries no P18 and was
missed entirely by the first run. Eddie Mabo carries no P18, no P19, no P27
and no P172 — his ADB entry is the only route to him in the whole of
Wikidata. So the NZ/Pacific source runs image-free throughout, and ADB and
DIB each get a second image-free lane alongside the main one. `has_image`
is recorded on every candidate either way.

### 4.2 The occupation histogram that set the budgets

The family budgets are not guesses. This query produced the live list of
which occupations ODNB actually contains, and how many of each — every
occupation QID in the script comes from its output, so their presence in
the data is proven rather than assumed:

```sparql
SELECT ?occ ?occLabel (COUNT(DISTINCT ?p) AS ?c) WHERE {
  ?p wdt:P1415 ?id ; wdt:P570 ?dod ; wdt:P18 ?img ; wdt:P106 ?occ .
  ?a schema:about ?p ; schema:isPartOf <https://en.wikipedia.org/> .
  ?occ rdfs:label ?occLabel . FILTER(LANG(?occLabel)="en")
} GROUP BY ?occ ?occLabel ORDER BY DESC(?c) LIMIT 150
```

Top of the result: politician 5731, writer 4198, painter 1443, poet 1303,
university teacher 1039, physician 1031, military personnel 1012. Deep in
the tail, and exactly what the game is short of: engineer 631, explorer
462, inventor 296, photographer 256, cricketer 234, archaeologist 232,
trade unionist 186, ornithologist 142, diarist 134, aircraft pilot 116,
printer 80, nurse 87, farmer 85, spy 78.

### 4.3 Sitelink counts for the In Our Time path

IOT candidates arrive via title→QID resolution, not via a selection query,
so they have no sitelink count yet. One VALUES query per 300 QIDs:

```sparql
SELECT ?p ?sl WHERE { VALUES ?p { wd:Q1 wd:Q2 … } ?p wikibase:sitelinks ?sl }
```

### 4.4 In Our Time parsing

`List of In Our Time programmes` is one Wikipedia article holding the whole
episode list — ~484,600 characters of wikitext, **1,108 wikitable rows**.
It is *not* categorised by subject, so the pipeline is:

1. `action=query&prop=revisions&rvslots=main` for the raw wikitext.
2. Split on `\n|-` (the wikitable row separator).
3. Split each row into columns on line-leading `|`. (Safe: the multi-line
   contributor templates inside the Contributors column use `*` bullets,
   never a line-leading `|`.)
4. Take the first `[[wikilink]]` in column 2 (the Title column) as the
   episode subject; fall back to the stripped plain text when a title is
   unlinked.
5. Resolve those subjects with `action=query&prop=pageprops&
   ppprop=wikibase_item&redirects=1`, 50 at a time.
6. Keep only items with `P31 = Q5` (human). Most IOT episodes are topics —
   "Delian League", "Seashell" — and they are dropped here.

### 4.5 Enrichment

`action=wbgetentities&props=claims|labels&languages=en`, 50 QIDs a call.
Claims kept: P31 (instance of), P21 (sex or gender), P106 (occupation),
P569/P570 (birth/death date), P19/P20 (birth/death place), P27
(citizenship), P172 (ethnic group), P18 (image), P39 (position held), and
on *place* items P625 (coordinates) and P17 (country).

Places are resolved in a second pass over the distinct place QIDs only —
places repeat heavily across people, so this is a fraction of the calls a
per-person lookup would need. `prop=pageimages` on enwiki gives the
independent second image check.

---

## 5. Output shape

`tools/fame/audience_candidates.json`:

```jsonc
{
  "generatedOn": "2026-07-25",
  "generator": "tools/fame/harvest_audience.py",
  "audience": "Rest Is History listeners — …",
  "optimisation_target": "subject-matter variety …",
  "network": { "wikidata_sparql": "OK — …", "enwiki_api": "OK — …" },
  "region_table": "build_tags.region_for_country_label",
  "limit_scale": 1.0,
  "sources":   { "<id>": { "description", "rows", "distinct_people", "errors" } },
  "dedupe_inputs": { "<path>": <rows read> },
  "summary":   { …see below… },
  "candidates": [ … ]
}
```

Each candidate:

| field | notes |
| --- | --- |
| `qid`, `name`, `wiki_title` | Wikidata id, English label, enwiki title |
| `gender` | **recorded, never selected on** |
| `occupations`, `occupation_qids` | all P106 values, English labels |
| `primary_family`, `families` | see §6 |
| `birth_year`, `death_year`, `era` | era buckets match `build_tags.py` |
| `is_living`, `is_living_politician` | both flagged; living people are dropped from the output |
| `died_recently` | died since `RECENT_DEATH_CUTOFF` (2016); held back from the shortlist, kept in the pool |
| `birth_place`, `birth_lat`, `birth_lon`, `birth_country` | **coordinates matter — Lifeline plots them** |
| `death_place`, `death_lat`, `death_lon`, `death_country` | |
| `citizenships`, `ethnic_groups`, `region` | region uses the audit's 10-bucket vocabulary |
| `sources`, `strata` | provenance: which source(s) and which stratum found them |
| `sitelinks` | floor/tie-break only |
| `has_wikidata_image`, `has_enwiki_image`, `has_image` | two independent checks |
| `journey_km`, `journey_class` | great-circle birth→death |
| `recognition_tier` | `household_name` / `enthusiast` (specialists are dropped) |
| `is_new`, `dup_match` | dedupe result and what it matched on |
| `priority_score` | transparent integer, sorting only |

`summary` carries the tallies: totals, new vs already-known, tier, family,
region, era, journey class, source combination, coordinate coverage, image
coverage, and what was excluded and why.

### Tiering

| tier | rule | why |
| --- | --- | --- |
| `household_name` | sitelinks ≥ 55, or an In Our Time subject with ≥ 30 | the scarce easy-Monday resource |
| `enthusiast` | any In Our Time subject; or sitelinks ≥ 10; or an editorial-dictionary entry with ≥ 4; or an editorial-dictionary entry with ≥ 3 in a starved family who died before 1975 | most of the harvest's real value — hard-weekend material |
| `specialist` | everything else | **dropped from the output** |

Editorial-dictionary membership is treated as evidence in its own right: a
figure ODNB judged worth an entry, carrying a handful of sitelinks, is an
enthusiast figure even though the general population has never heard of
them. That is the whole point of using ODNB instead of pageviews.

### Journey

Lifeline plots birth→death on a map, and a suitability analysis found fame
explains only **1.3%** of journey variance — so journey has to be selected
for explicitly or it does not happen. `journey_km` is the great-circle
distance; `journey_class` buckets it as `stayed-put` (<25 km), `local`
(<100), `regional` (<500), `long` (<2000), `epic` (≥2000) or `unknown` (a
missing coordinate at either end). A candidate without coordinates is much
less useful and `priority_score` reflects that.

---

## 6. Occupation families and the budgets

`FAMILY_POLICY` in the script maps each family to
`(odnb_limit, odnb_floor, global_limit, global_floor)`. `global_limit = 0`
means "do not run this family as a worldwide query" — the dictionaries
already supply more than enough.

| family | ODNB limit/floor | global limit/floor | rationale |
| --- | --- | --- | --- |
| ruling_politics | 35 / 12 | — | 32.5% of the universe already |
| military | 30 / 10 | — | the launch month's dominant theme |
| religion | 30 / 10 | — | 474 in the universe, nearly all senior clergy |
| letters | 55 / 5 | 60 / 40 | middling |
| scholarship | 70 / 4 | 80 / 30 | middling |
| arts_culture | 85 / 3 | 90 / 28 | middling |
| science_nature | 130 / 2 | 140 / 20 | starved |
| medicine | 150 / 2 | 150 / 15 | starved |
| engineering_invention | 160 / 2 | 160 / 15 | 46 in the universe |
| exploration_travel | 200 / 1 | 200 / 12 | 48 in the universe |
| sport | 180 / 1 | 200 / 15 | 52 in the universe |
| work_trade_everyday | 150 / 1 | 150 / 15 | "everyday life and work" |
| reform_activism | 150 / 1 | 150 / 12 | 43 in the universe |

`OCCUPATION_OVERRIDE` adjusts individual occupations where the family
default is wrong — archaeologists, photographers, dancers, comedians and
designers are boosted out of their middling families; `writer` (a 4,198-row
catch-all) and `university teacher` (pure noise) are cut back; explorers
and travellers are taken essentially in full.

**Diarists are filed under `work_trade_everyday`, not `letters`** — a
diarist *is* the everyday-life record (Pepys, Evelyn, Kilvert), which is
exactly the register the launch month was missing.

**`primary_family`** uses **Wikidata's own P106 order** — the first listed
occupation is the honest answer nearly always. The single override: if the
first occupation is in a saturated family (politician / soldier / cleric)
and a starved one appears later, the starved one wins — "politician + civil
engineer" really is an engineering round, and "prime minister who played
first-class cricket" really is a sport round. `families` keeps the full set.

An earlier version preferred whichever family was most starved, full stop.
That filed Bing Crosby as an athlete and Dean Martin as a boxer. Do not
reintroduce it.

### The output cap — three dimensions, none of them global

The tiered pool (18,631) is far larger than anyone can review, but
trimming it with a single global cut is precisely the mistake
`TARGET_COUNT = 4000` makes: **a global cut is a fame cut**. So the
shortlist is capped on three axes and never on overall rank.

1. **Family** (`FAMILY_OUTPUT_CAP`): 240 for each starved family, 200 for
   middling, 60 for saturated. No family can be trimmed out of existence.
2. **Era** (`ERA_SHARE`): within each family, 30% pre-modern / 35%
   nineteenth / 35% modern, with spill-over when a bucket genuinely cannot
   fill (sport has only 37 pre-1800 figures in the pool, and is not padded
   with people who do not exist). Without this the shortlist came out 68%
   twentieth-century.
3. **Region** (`REGION_MAX_SHARE` 30%, Oceania 8%): applied greedily as
   families are filled, starved families first so they get first pick of
   the scarce regions. A family is never left short to satisfy it — the
   region cap yields last.

**Recency** (`RECENT_DEATH_CUTOFF = 2016`) holds back anyone who died in
the last decade. A game called Dead Famous should not open on someone who
died last spring: it reads as news rather than history, obituary framing is
a different register from the house dark wit, and a just-dead politician is
barely different from a living one. 1,357 candidates sit behind this line,
including several 2025–26 deaths that the first run put straight into the
top of the shortlist. It is one constant to change.

---

## 7. Results of the 2026-07-25 run

**Network: both endpoints verified OK before anything ran.** Wikidata SPARQL
(`query.wikidata.org`) HTTP 200; enwiki action API HTTP 200. Zero query
errors across all 331 strata. Both APIs 403 a bare request — the
descriptive `User-Agent` is what makes them answer.

### Selection yield

| source | rows selected | distinct people | errors |
| --- | ---: | ---: | ---: |
| odnb | 12,261 | 6,847 | 0 |
| occupations | 13,878 | 8,789 | 0 |
| nzpacific | 5,437 | 4,385 | 0 |
| adb | 3,100 | 2,547 | 0 |
| dib | 2,600 | 2,068 | 0 |
| inourtime | 1,035 | 1,031 | 0 |
| **merged** | **38,311** | **22,450** | **0** |

### Funnel

| stage | n |
| --- | ---: |
| distinct people selected | 22,450 |
| less non-human items (In Our Time topics) | −772 |
| less `specialist` tier | −3,801 |
| less living | −21 |
| **tiered pool** (`raw/audience_pool.json`) | **18,631** |
| less died since 2016 | −1,357 |
| **shortlist** (`audience_candidates.json`) after per-family/era/region caps | **2,520** |

**2,460 of the 2,520 (97.6%) are genuinely new** — not present in
`universe_people.json`, `current_inventory.json`, `data/figures.json` or
`data/reveal-who.json` by QID, wiki title or name. Across the whole tiered
pool, 16,000+ are new. The 60 non-new entries are figures the harvest
re-surfaced from a different angle and that the caps kept.

**Tier:** 1,993 enthusiast / 527 household_name.

**Source attribution of the shortlist** (a candidate can carry several):
worldwide occupation queries 1,721 · ODNB 692 · ADB 241 · DIB 160 ·
NZ/Pacific 91 · DNZB 72 · In Our Time 33.

### Subject-matter variety — the actual point

| family | universe (audit taxonomy) | shortlist |
| --- | ---: | ---: |
| statesmen / ruling | **1,301 (32.5%)** | 60 (2.4%) |
| military | 127 (3.2%) | 60 (2.4%) |
| religion | 474 (11.9%) | 60 (2.4%) |
| **athletes / sport** | **52 (1.3%)** | **240 (9.5%)** |
| **explorers / travel** | **48 (1.2%)** | **240 (9.5%)** |
| **inventor-engineers** | **46 (1.2%)** | **240 (9.5%)** |
| **activist-reformers** | **43 (1.1%)** | **240 (9.5%)** |
| medicine | (inside "scientist", 486) | 240 (9.5%) |
| science & nature | (same 486) | 240 (9.5%) |
| **work, trade & everyday life** | business 29 (0.7%) | **240 (9.5%)** |
| arts & culture | 248 artists + 192 performers | 200 (7.9%) |
| scholarship | 199 philosophers + others | 200 (7.9%) |
| letters | 404 writers (10.1%) | 200 (7.9%) |

Counting only people whose *first-listed* occupation puts them there:
athletes 52 → 240, explorers 48 → 186, inventor-engineers 46 → 240.

### Era

37.3% twentieth · 34.6% nineteenth · 21.3% early-modern · 2.8% medieval ·
2.1% ancient · 1.9% contemporary. **63% died before 1900.** The raw
harvest came out 68% twentieth-century before the era stratification was
added — Wikidata simply records more about modern people, so every quality
signal (coordinates, images, long journeys) quietly rewards recency.

### Region — same 10-bucket vocabulary as the audit

| region | universe | shortlist |
| --- | ---: | ---: |
| Europe | **65.18%** | 31.41% |
| North America | 8.59% | 32.20% |
| Oceania | **0.15%** | 11.02% |
| Central Asia & Russia | 4.73% | 10.65% |
| Middle East & North Africa | 13.61% | 3.58% |
| South Asia | 1.83% | 3.41% |
| Latin America & Caribbean | 1.34% | 3.08% |
| East Asia | 3.37% | 2.38% |
| Sub-Saharan Africa | **0.67%** | 1.89% |
| Southeast Asia | 0.51% | 0.37% |

The tiered pool underneath is 62% European — the dictionaries are
Anglophone — so this is the cap doing its job, not the harvest being
lopsided. Sub-Saharan Africa is the weakest result: 1.89% is nearly triple
the universe's 0.67% but still thin, and unlike Oceania it has no
equivalent editorial dictionary wired in. That is the clearest next job.

### Lifeline suitability

- **2,449 of 2,520 (97.2%)** have coordinates at **both** ends.
- **2,384 (94.6%)** have a real journey of 100 km or more.
- Median journey **841 km**, against **549 km** for the shipped figures.
- Only 45 (1.8%) stayed put; 866 (34.4%) are "epic" (≥2,000 km).

### Face Value suitability

2,513 have a Wikidata image (P18), 2,447 an enwiki lead image, **2,519 of
2,520 have at least one**.

### Verification against the brief's named examples

The figures the brief named as proof of the source-level hole are all now
reachable: **Tupaia** (Ra'iātea → Batavia, epic journey — was missed on the
first pass because he has no P18, which is what prompted the image-free
lane), **Eddie Mabo** (no image, no birthplace, no citizenship and no
ethnic group on Wikidata — reachable *only* through his ADB entry),
**Te Rauparaha**, **Hōne Heke**, **Te Kooti**, **Āpirana Ngata**,
**Truganini**. **Kupe** is correctly absent: he has no recorded death date,
so he cannot anchor a Lifeline round. **Pepys**, **Wolsey** and
**Bazalgette** were all found by ODNB and correctly marked `is_new: false`
— they are already in the universe. **W. G. Grace** is new and shortlisted.

### Two bugs worth recording

1. **`primary_family` originally preferred the starved family.** That filed
   Bing Crosby as an *athlete* (he part-owned a baseball team), Michael
   Crichton as a basketball player and Dean Martin as a boxer — inflating
   the very numbers this harvest exists to report. Fixed to use Wikidata's
   own occupation order, with a single deliberate override (see §6).
2. **The image requirement was silently deleting pre-colonial figures.**
   Requiring P18 is a *Face Value* constraint; Lifeline needs coordinates,
   not a portrait. Fixed with image-free lanes on the dictionaries and the
   whole NZ/Pacific source.

---

## 8. How this should feed `build_universe.py`

**Not wired in — another agent owns `build_universe.py`.** This is the
recommendation.

The bug is not that Pantheon is a bad source; it is that Pantheon is the
*only* source and `TARGET_COUNT = 4000` is a **global fame rank**. Two
changes, in order of value:

1. **Make the universe a union of sources, not one ranked list.**
   `universe_people.json` should be Pantheon *plus* `audience_candidates.json`,
   with a `sources` array per person. Provenance is already carried on
   every candidate here (`sources`, `strata`), so a merge can keep it.
   Match on `qid` first, then normalised `wiki_title`, then normalised
   `name` — the same three-step used by `load_existing_identifiers()` in
   this script.

2. **Replace the global cut with per-family floors.** A single
   `TARGET_COUNT` cuts by fame, which is what produced 32% statesmen and 52
   athletes. If a cut is needed at all, it should be applied *per occupation
   family* with its own target, so trimming the pool cannot silently delete
   an entire subject area. The family taxonomy and budgets in §6 are
   reusable as-is.

Practical notes for whoever does the wiring:

- **Do not re-rank the merged pool by sitelinks or HPI.** That would undo
  the entire exercise. Use `recognition_tier` for the easy/hard split and
  `priority_score` (or your own blend of family, journey and image) for
  ordering within a tier.
- **Candidates are pre-filtered but not pre-approved.** Living people and
  `specialist`-tier figures are already dropped. Everything surviving still
  goes through the normal intake gates (`INTAKE_SPEC.md`) — fact/joy
  review, image rights, crop suitability. Nothing here has been fact-checked
  beyond what Wikidata asserts.
- **`is_living_politician` is belt-and-braces.** The `P570` requirement
  already excludes living people at the query level; the flag exists so the
  rule is visible and auditable rather than implicit.
- **Coordinates are the gating field for Lifeline.** `journey_km is null`
  means one endpoint has no coordinates — usable for Face Value, not for
  Lifeline.
- **Re-running is cheap.** The caches make a repeat run minutes rather than
  an hour, so widening a family budget and re-running is a normal edit, not
  a big job.
- **Two verified sources are held in reserve**: NPG London (P1816, 21,756)
  and American National Biography (P4823, 14,517). Add them the same way if
  the pool needs more portraits or more North America.
