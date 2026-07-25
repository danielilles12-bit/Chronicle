# harvest_objects_v2.py -- Wikidata-class object harvest for Relic ('what')

## Why this exists

A 24-25 Jul 2026 audit found `tools/fame/universe_objects.json` (2219 rows,
built by `build_universe_objects.py`) is dominated by immovable architecture:
it was harvested from UNESCO World Heritage **site** lists and Wikipedia
"List of..." architecture articles (vital articles, largest mosques, tallest
statues, etc.). Worse, its `kind` vocabulary -- `site`, `building`,
`artefact`, `manuscript`, `painting`, `sculpture`, `monument` -- has no
bucket for an instrument, garment, tool, vehicle, machine, coin or weapon,
so even portable objects harvested elsewhere have nowhere sensible to go.

This script targets the missing register directly: **Wikidata SPARQL by
object class** (vehicle, ship, clothing, tool, weapon, coin, musical
instrument, jewellery, machine, furniture, archaeological find), filtered
hard for recognisability, plus the BBC/British Museum "A History of the
World in 100 Objects" list -- 100 objects explicitly chosen for a
general-but-curious radio audience, almost all portable, all photographed.

It does **not** touch `universe_objects.json`, `current_inventory.json` or
any `data/*.json` file, and is **not wired into** `build_universe_objects.py`.
It only produces `tools/fame/object_candidates_v2.json` for human review (or
a later session) to merge.

## Sources

### Single-root Wikidata classes (`SINGLE_ROOT_JOBS`)

Each queries `wdt:P31 wd:<QID>` (direct instance-of) or
`wdt:P31/wdt:P279* wd:<QID>` (transitive, for classes whose named instances
are typed via subclasses -- e.g. a "steam locomotive" is not directly
`instance of: ship`), filtered to items with an image (`wdt:P18`) **and** an
enwiki sitelink (`?article schema:about ?item ; schema:isPartOf
<https://en.wikipedia.org/>`). A `wikibase:sitelinks` floor is applied
inside the query itself for the larger classes (query speed + a first-pass
quality gate), then `ORDER BY DESC(?sitelinks) LIMIT n` caps the pull to the
most notable members.

| bucket | kind | QID | mode | floor | limit |
|---|---|---|---|---|---|
| ship | ship | Q11446 | transitive | 15 | 400 |
| painting | painting | Q3305213 | direct | 15 | 350 |
| sculpture | sculpture | Q860861 | transitive | 12 | 300 |
| tool | tool | Q39546 | transitive | 8 | 300 |
| archaeological_find | archaeological_find | Q220659 | transitive | 6 | 350 |
| musical_instrument | musical_instrument | Q34379 | transitive | -- | 400 |
| weapon | weapon | Q728 | transitive | -- | 300 |
| coin | coin | Q41207 | transitive | -- | 200 |
| machine | machine | Q11019 | transitive | 15 | 350 |
| furniture | furniture | Q14745 | transitive | 6 | 250 |

These transitive counts were verified live against the audit's own table
during calibration (ship 19,397; sculpture 6,433; tool 5,311; archaeological
artifact 1,391; musical instrument 488; weapon 253; coin 128 -- exact
matches). **`vehicle` and `item of clothing` did NOT reproduce** the
audit's headline numbers (see "Where this harvest disagrees with the
audit brief" below) -- both needed a different query shape, documented here
rather than silently forced to match.

### Curated union buckets (a single class query is wrong or times out)

- **`vehicle`**: a plain `wdt:P31/wdt:P279* wd:Q42889` ("vehicle") query
  **times out** on the public endpoint -- the branching factor under that
  root is too large for its ~60s budget. Named historical vehicles are
  almost always typed as instances of a specific *leaf* class instead (a
  "car model", not directly "a vehicle"), so `VEHICLE_ROOTS` unions 15 fast,
  individually-queried leaf classes: car model, car, aircraft model,
  aircraft, spacecraft, submarine, motorcycle, locomotive class, airship,
  hot air balloon, wagon, chariot, stagecoach, sled, tank.
- **`clothing`**: the brief's own table already flags a Wikidata modelling
  quirk for jewellery; the same problem hits clothing. `wdt:P31/wdt:P279*
  wd:Q11460` ("clothing") measures only ~2,223 items with image+enwiki, far
  below the audit's 9,549 -- and even a broad union with headgear, footwear,
  military uniform, robe and costume roots only reaches ~2,829. Named
  garments are evidently scattered across even more disconnected subclasses
  than that; this harvest ships what the clean, defensible query reaches
  (clothing + headgear union) and documents the shortfall rather than
  padding the number.
- **`jewellery`**: exactly the quirk the brief calls out -- a plain
  instance-of query on "jewellery" (Q161380) returns almost nothing because
  named pieces are typed as specific subclasses (necklace, bracelet,
  brooch, fibula, tiara, earring, amulet, diadem). `JEWELLERY_ROOTS` unions
  those eight directly; the yield is still small (jewellery is a niche
  Wikidata category even after the fix) and is topped up by well-known named
  pieces surfaced through `MUST_INCLUDE_TITLES` and `how100`.

### `MUST_INCLUDE_TITLES` -- the audit's own worked examples

The brief named ~20 specific objects as proof the gap is real (spinning
jenny, Stephenson's Rocket, Enigma machine, Ford Model T, the Ashes urn, a
Stradivarius, Sutton Hoo helmet, Staffordshire Hoard, Nebra sky disc, Cyrus
Cylinder, Standard of Ur, Lewis chessmen, Vindolanda tablets, Portland Vase,
Penny Black, Mary Rose, Vasa, Wright Flyer, Sputnik 1, Antikythera
mechanism). Each is fetched explicitly by title (enwiki pageprops -> Wikidata
QID -> bulk SPARQL `VALUES` lookup) so the report can say plainly, per
title, whether it now has a real candidate row -- independent of whether the
class harvest above happened to net it too. **Important finding**: about
half of these were already sitting in `universe_objects.json` (via
`manual_seed.py`'s "curated-landmarks" list, generically tagged
`kind: "artefact"`) or even already **live** in the shipped
`data/reveal-what.json`. See "Where this harvest disagrees with the audit
brief" below -- this doesn't mean the harvest was pointless, it means the
"absent" framing was partly wrong even as the underlying kind-vocabulary
problem is real.

### `how100` -- A History of the World in 100 Objects

Parses the wikitext of the English Wikipedia article of that name (the
numbered wikitables per era), extracts each row's first non-`File:`
wikilink as the candidate object, resolves it to a Wikidata item via enwiki
pageprops, then bulk-fetches image/sitelinks/etc via the same `VALUES`
SPARQL path used for `MUST_INCLUDE_TITLES`. A number of rows have no
wikilinked object at all (e.g. "Stone (basalt) chopping tool" -- generic,
correctly left unresolved rather than guessed).

## Quality filtering

1. **Name filter** (`is_low_quality_name`): rejects pure numbers, catalogue/
   accession-style names ("Object 4", "Unidentified..."), disambiguation
   pages, and a short blocklist of generic class-name leakage (e.g. a stray
   row whose "name" is literally "vehicle" or "sculpture").
2. **Completeness filter**: drops anything missing an enwiki title or an
   image URL outright (both are required fields downstream).
3. **Dedup against existing pools** (read-only; never edits these files):
   `universe_objects.json` (`wiki_title`, all 2219 rows), `current_inventory.json`
   (`wiki_title` of `game == "what"` rows only), `data/reveal-what.json`
   (`name` + every `variants` entry, since that file carries no
   `wiki_title`). **Matching is deliberately restricted to these
   authoritative title/alias fields** -- an earlier version of this script
   also matched on `universe_objects.json`'s free-text `name` and on the
   Wikidata item's short `itemLabel`, and that produced a real false
   positive during testing: Wikidata's label for "Enigma machine" (Q150758)
   is just "Enigma", which collided with an unrelated Connections
   thread-tile literally titled "Enigma" and with "The Enigma (diamond)".
   Both were removed as dedup keys; only `wiki_title`-class fields survive.
4. **Recognition tagging + specialist exclusion** (`tag_recognition`):
   - `household_name`: `wikibase:sitelinks >= 70`, OR on the hardcoded
     `ICONIC_TITLES` allowlist (~50 titles), OR from `how100` with
     `sitelinks >= 40`.
   - `enthusiast`: `sitelinks >= 15`, or anything from `how100` regardless
     of sitelinks (the BBC/British Museum curation is itself a recognition
     signal for "known to history lovers").
   - `specialist`: everything else -- **dropped from the output file
     entirely**, per spec ("specialist... exclude"). The summary block
     still records how many were dropped for transparency.
5. **`kind` refinement**: a keyword pass (`guess_kind_extended`) that can
   promote a class-harvested item to a more specific kind than its source
   class implied, and is the only kind-assignment path for `how100` /
   `must_include` rows (which have no single source class). Falls back to
   `artefact` -- matching the existing convention that the shipped data
   file's `kind` field is a flat `"artefact"` for everything non-portrait
   anyway (see `INTAKE_SPEC.md` section 0).

## Proposed extended `kind` vocabulary

For **selection and balance during content curation only** -- per
`INTAKE_SPEC.md`, the shipped `data/reveal-what.json` schema keeps a flat
`"kind": "artefact"` for every non-portrait record regardless of this
finer classification, and `js/revealgame.js` only ever branches on
`kind === 'portrait'` vs not. Nothing here should be copied into that file's
`kind` field.

| kind | covers | rationale |
|---|---|---|
| `vehicle` | cars, aircraft, spacecraft, locomotives, submarines, motorcycles, airships, wagons, chariots | zero representation before this harvest; visually and thematically distinct from "ship" |
| `ship` | boats, warships, wrecks | kept distinct from `vehicle` -- large, separate Wikidata population (19,397), and a recognisable genre of its own (Mary Rose, Vasa, Titanic) |
| `clothing` | garments, headgear, footwear, uniforms, vestments | zero representation before this harvest; texture-rich, tears legibly |
| `tool` | hand tools, instruments of measurement/craft (astrolabes, looms, presses) | zero representation before this harvest |
| `weapon` | swords, firearms, armour, shields | zero representation before this harvest |
| `coin` | individual named/historic coins and coin types | zero representation before this harvest |
| `musical_instrument` | violins, pianos, drums, named individual instruments | zero representation before this harvest -- explicitly called out (a Stradivarius) |
| `jewellery` | necklaces, crowns, tiaras, brooches, amulets | zero representation before this harvest; small population but high recognisability per item |
| `machine` | engines, computers, mechanisms, apparatus (Enigma, Antikythera mechanism, Difference Engine) | zero representation before this harvest; distinct from `tool` (powered/mechanical vs hand-operated) |
| `furniture` | thrones, historic chairs/desks | zero representation before this harvest; small population, high recognisability (Coronation Chair, Resolute desk) |
| `archaeological_find` | hoards, excavated grave-goods, steles (Sutton Hoo, Staffordshire Hoard, Nebra disc, Standard of Ur) | splits genuinely spectacular excavated objects out of the `artefact` catch-all, where they'd otherwise be indistinguishable from a random museum piece |
| `painting`, `sculpture`, `manuscript`, `monument`, `building`, `site`, `artefact` | unchanged from the existing vocabulary | kept as-is; this harvest only adds new buckets, it doesn't touch the existing ones |

## Where this harvest disagrees with the audit brief

Two things worth flagging plainly rather than quietly reconciling:

1. **`vehicle` and `item of clothing` counts don't reproduce.** The brief's
   table states vehicle = 32,360 and item of clothing = 9,549 (both "with
   image + enwiki"). Live verification during calibration found: a plain
   `P31/P279*` query for "vehicle" (Q42889) times out entirely on the public
   endpoint; the 15-leaf-class curated union this script uses instead reaches
   roughly 16,000 pre-quality-filter. For clothing, `P31/P279*` on Q11460
   ("clothing") measures only 2,223, and even a six-root union (clothing +
   headgear + footwear + military uniform + robe + costume) only reaches
   2,829. It's plausible the brief's numbers came from a broader or
   differently-shaped query (a per-country/per-era union, or counting via a
   different property path) -- but this script did not attempt to
   force-match a number it couldn't independently reproduce, since that would
   risk quietly padding the wrong quality bar. All other classes in the
   table (ship, painting, sculpture, tool, archaeological artifact, musical
   instrument, weapon, coin) matched the audit's figures exactly during
   calibration.
2. **Several of the brief's "verified absent" named examples are not, in
   fact, absent.** Sutton Hoo helmet, Nebra sky disc, Cyrus Cylinder,
   Standard of Ur, Lewis chessmen, Portland Vase, Mary Rose, Vasa, and
   Antikythera mechanism are already in `universe_objects.json` (added by
   `manual_seed.py`'s "curated-landmarks" list) -- and Sutton Hoo helmet,
   Staffordshire Hoard, Nebra sky disc, Cyrus Cylinder, Standard of Ur,
   Lewis chessmen, Portland Vase, Mary Rose, Vasa and Wright Flyer are
   already **live** in the shipped `data/reveal-what.json` today. The real
   gap these prove isn't non-existence -- it's that they're all flattened
   to generic `kind: "artefact"`/`"artefact"`, indistinguishable from every
   other object, which is exactly what the extended `kind` vocabulary above
   fixes. Genuinely new from that named list: Ford Model T, Penny Black,
   The Ashes, Stephenson's Rocket, Stradivarius, Spinning jenny, Enigma
   machine, Vindolanda tablets, Sputnik 1.

## How to re-run

```
cd "tools/fame"
python3 harvest_objects_v2.py                              # everything, live network
python3 harvest_objects_v2.py --sources ship,painting        # a subset, live network
python3 harvest_objects_v2.py --skip-licence                 # live network, no Commons licence pass
python3 harvest_objects_v2.py --from-raw                     # OFFLINE: reprocess an already-
                                                               # completed harvest's raw dump,
                                                               # zero network calls, ~1 second
```

Valid `--sources` values: every `SINGLE_ROOT_JOBS` bucket id (`ship`,
`painting`, `sculpture`, `tool`, `archaeological_find`,
`musical_instrument`, `weapon`, `coin`, `machine`, `furniture`), plus
`clothing`, `vehicle`, `jewellery`, `must_include`, `how100`.

The script verifies network access (one SPARQL query, one enwiki API call)
before anything else and aborts loudly if either fails, rather than writing
fabricated output. (`--from-raw` skips this too -- it makes no network
calls of any kind.)

Every raw HTTP response (SPARQL, enwiki, Commons) is cached under
`tools/fame/cache/<sparql|enwiki|commons>_objects_v2/<hash>.json` via
`fetch_metrics.py`'s own `http_get_json`/`_cache_path` (imported directly,
not reimplemented) -- so throttling, 429/5xx exponential backoff, and
resumability (a killed-and-restarted run replays cache hits instantly and
only makes live requests for whatever it hadn't reached yet) are all
inherited. To force a full re-fetch, delete the relevant
`tools/fame/cache/*_objects_v2/` subfolder(s) (the shared `cache/` symlink
also holds fetch_metrics's own unrelated caches -- don't delete the whole
directory).

**`--from-raw`**: every raw SPARQL/enwiki binding this script ever collects
gets written to `tools/fame/raw/objects_v2_sparql.json` (one flat array,
tagged with `bucket`) the moment the network harvest finishes -- *before*
the merge/filter/dedupe/tag/kind/region pipeline runs. `--from-raw` reloads
that file and replays only the offline pipeline stages against it, with
zero network calls (so it also implies `--skip-licence` -- Commons lookups
are a network call too). This is how the delivered `object_candidates_v2.json`
in this repo was actually produced: the live network harvest completed and
wrote a complete 5,043-row raw dump, but the subsequent per-candidate
Commons licence-enrichment pass (a nice-to-have, not required for a
candidate list) was still in progress when time ran out, and re-running the
whole harvest from scratch to redo it would have re-spent ~20+ minutes of
already-cached network time for no new information. `--from-raw` reprocesses
the existing raw dump in under a second instead. Use it any time you want to
retune the quality filter, the recognition thresholds, the kind keywords, or
the variety trim (see below) without re-hitting Wikidata/enwiki at all.

## Licence enrichment: NOT included in this delivery

`fetch_commons_licence()` (a per-candidate Commons API call for
`LicenseShortName`/`Artist`/`Credit`) exists in the script and works (verified
in isolation during development), but the per-candidate pass over ~2,200
candidates was still running when this harvest needed to ship, and was
dropped rather than waited out further. **Every candidate in
`object_candidates_v2.json` has `image_licence`, `image_artist` and
`image_commons_url` set to `null`.** This is a deliberate scope cut, not a
bug: the existing intake pipeline (`INTAKE_SPEC.md`) already re-checks
image rights per item before anything reaches `data/reveal-what.json`, so
licence data here would have been re-verified at merge time regardless. To
add it later, run `python3 harvest_objects_v2.py --from-raw` after removing
the `args.skip_licence = True` line the `--from-raw` path forces (or just
run the full live harvest again with neither `--skip-licence` nor
`--from-raw`, accepting the ~15-20 minute licence-lookup pass at the end).

## Variety trim (product-owner steer, 25 Jul 2026)

The raw pipeline output was 2,210 candidates -- slightly over the 800-2,000
target. Per explicit direction received mid-harvest ("prioritise VARIETY OF
SUBJECT MATTER... favour categories the pool completely lacks... if you
have to trim the list, trim architecture first"), the trim was applied
**only** to the four kinds that already had some prior representation in
the existing universe per the audit table (ship: 225 existing, painting:
108, sculpture: 95, and vehicle as the largest/least-scarce new bucket) --
raising their effective sitelinks floor from 15 to 22. Every
zero-representation category this harvest exists to fill --
`clothing`, `tool`, `weapon`, `coin`, `musical_instrument`, `jewellery`,
`furniture`, `machine`, `archaeological_find` -- was left completely
untouched.

| kind | dropped |
|---|---|
| ship | 88 |
| vehicle | 85 |
| painting | 73 |
| sculpture | 2 |

After the trim: 1,962 candidates. **This was not the final number** -- a
manual audit pass (below) found real data-quality bugs and cut it further to
**1,772**.

## Manual cleanup pass -- real bugs the automated filter missed

Spot-checking the trimmed 1,962-candidate set by eye (sorting each `kind`'s
top items by `sitelinks` and reading them) surfaced systemic problems the
automated `is_low_quality_name`/specialist-exclusion filters did not catch.
These were fixed by a targeted post-process (not yet folded back into
`main()` -- see "Follow-ups" below), dropping **190 more candidates**:

| reason | count | what it was |
|---|---|---|
| `observatory_in_clothing` | 116 | **The single biggest bug.** A Wikidata subclass-chain quirk (a dome-shaped roof apparently mis-modelled as a kind of headgear) meant `wdt:P31/wdt:P279* wd:Q1254933` ("headgear") pulled in well over a hundred real, physical, ground-based astronomical **observatory buildings** -- Griffith Observatory, Mount Wilson, Paris Observatory, Arecibo, and dozens more -- tagged `kind: "clothing"`. This was pure architecture leaking into a bucket that's supposed to be the opposite of architecture. Every `clothing`-kind candidate whose title contained "Observatory" was dropped (zero false-positive risk -- no real garment is named "Observatory"). Genuine space-based telescopes (Hubble, JWST, Chandra, Kepler, Herschel Space Observatory) were untouched -- they were correctly harvested under `machine`/`tool`, not `clothing`, and are real single-object satellites, not buildings. |
| `how100_misresolved_wikilink` | 32 | A real parser bug in `parse_how100_rows`/`first_wikilink()`: many how100 table cells read "**[[Type]] of/from [[Specific name]]**" (e.g. `[[Mummy]] of [[Hornedjitef]]`, `[[Hokusai]]'s ''[[The Great Wave off Kanagawa]]''`), and grabbing the *first* wikilink picks the generic type, culture, dynasty, deity, material or person mentioned first rather than the actual named object. Caught 32 rows resolving to things like "Sudan", "Shiva", "Maya civilization", "Ming dynasty", "Ulugh Beg" (a person), "Lysimachus" (a person), "David Hockney" (a living artist -- would also have failed the project's own living-persons policy), "bronze"/"jade"/"basalt" (materials), "Victorian era" (a period), and "Gilgamesh flood myth" (a story, not a physical tablet). Dropped by `how100_number`, not by title text, to avoid any unicode-transcription risk. **Not re-parsed/fixed at the source** -- see Follow-ups. |
| `non_physical_or_generic_or_building` | 36 | Two distinct sub-problems caught by one hand-built blocklist: (a) non-physical items that happened to be `instance of` a harvested class in Wikidata -- software/apps (Tetris, Google Drive, Ableton Live, Ardour, LMMS, Duolingo, 15.ai) and one mythical object (Holy Grail, which has no verifiable physical referent); (b) extremely generic modern mass-produced-item articles with no distinct story -- exactly what the original brief says to reject (Computer, Computer keyboard, Computer monitor, Microwave oven, Television set, Belt (clothing), Chain, Envelope, Sensor, Tire) -- plus a handful of ground buildings/towers that leaked into `machine`/`tool`/`sculpture`/`archaeological_find` via similar ontology quirks to the observatory one (Ostankino Tower, Canton Tower, Oriental Pearl Tower, Milad Tower, Baku TV Tower, Sky Tower, Basilica Cistern, Vera C. Rubin Observatory (ground-based, unlike its space-telescope cousins), Juche Tower, Tower of the Winds, Kröller-Müller Museum, Louisiana Museum of Modern Art, Spasskaya Tower, Powder Tower Prague, Dura-Europos synagogue/church, Amundsen-Scott South Pole Station). |
| `org_or_building_qid_blocklist` | 3 | Knights Templar, Knights Hospitaller, Teutonic Order -- medieval military-religious *organizations*, not garments, despite landing in the `clothing` class harvest (their Wikidata "image" is a coat-of-arms/cross emblem, not a wearable object). |
| `list_article` | 1 | "List of names on the Eiffel Tower" -- a Wikipedia list article, not an object; `is_low_quality_name` should reject any `^List of` title and didn't (a genuine gap in the automated filter, worth fixing at the source -- see Follow-ups). |
| `institution_or_metonym_not_object` | 2 | "Filmfare Awards" (an awards franchise/ceremony, not the physical trophy) and "Sublime Porte" (a metonym for the Ottman government, not a physical object). |

Verified NOT false-positives during this audit (kept despite superficially
matching one of the above patterns): "The Church at Auvers" / "The Abbey in
the Oakwood" / "Madonna in the Church" (paintings *of* a building are not
architecture leaking in -- the object is the painting), "Kakiemon elephants
(British Museum)" (parenthetical museum attribution, not a building match),
"Nag Hammadi library" (the found manuscript codices, not a library
building), and every generic-but-legitimate archaeological/tool *type*
article (Hand axe, Clovis point, Tobacco pipe, Bronze mirror, Mortar and
pestle, Astrolabe) -- these have one real representative photographed
specimen and a genuine story, unlike the "modern mass-produced item with no
story" category above.

**Final: 1,772 candidates.** See `summary.manual_cleanup` in
`object_candidates_v2.json` for the exact rationale and per-reason counts,
machine-readable.

### Follow-ups NOT done here (time-boxed; flag for a future session)

- **Fix `first_wikilink()` to prefer the last non-generic wikilink**, or add
  a small stoplist of generic-type first-words (mummy, statue, bronze,
  miniature of...), so how100 rows resolve to the specific object rather
  than its type/culture/material modifier at the source, instead of being
  caught and dropped downstream.
- **Add `^List of` to `is_low_quality_name`** -- a one-line fix; only one
  instance surfaced in this run's data but it's a real gap.
- **Re-audit the `headgear` root (Q1254933) for other subclass-chain
  quirks** beyond observatories -- this run only checked for the pattern it
  already knew to look for (a keyword scan for "Observatory" specifically);
  a full manual read of the remaining 181 `clothing` candidates was not
  done given time constraints.
- **The manual cleanup steps above are currently one-off post-process
  scripts run against `object_candidates_v2.json` directly, not part of
  `harvest_objects_v2.py`'s `main()`/`_run_pipeline()`.** A future session
  should fold the blocklists and the `^List of`/observatory/how100-number
  rules into `_run_pipeline()` itself so a fresh `--from-raw` run reproduces
  the cleaned 1,772, not the pre-cleanup 2,210.

To redo the variety trim differently, edit the `TRIM_KINDS`/`TRIM_FLOOR`
constants in the standalone trim step and re-run against the `--from-raw`
output, then re-apply (or better, first fold in) the manual cleanup rules
above.

## Output shape

`tools/fame/object_candidates_v2.json` (real entry from the delivered file):

```json
{
 "generatedOn": "2026-07-25",
 "notes": [ "..." ],
 "summary": { "total_raw_rows": 5043, "per_kind": {...}, "per_recognition": {...},
              "job_log": {...}, "variety_trim": {...},
              "must_include_check": {"Sputnik 1": true, ...} },
 "candidates": [
   {
    "name": "Sputnik 1",
    "wiki_title": "Sputnik 1",
    "wikidata_id": "Q80811",
    "kind": "machine",
    "date_era": null,
    "culture_region": null,
    "region": null,
    "image_url": "http://commons.wikimedia.org/wiki/Special:FilePath/Sputnik%201%20satellite%20model.png",
    "image_licence": null,
    "image_artist": null,
    "image_commons_url": null,
    "sitelinks": 91,
    "recognition": "household_name",
    "source_bucket": "machine",
    "source_class": "machine",
    "also_matched_classes": ["must_include"],
    "from_how100": false,
    "how100_number": null
   }
 ]
}
```

`image_licence`/`image_artist`/`image_commons_url` are `null` for every
candidate in this delivery -- see "Licence enrichment: NOT included in this
delivery" above. `also_matched_classes` shows Sputnik 1 was independently
found by both the `machine` SPARQL class harvest and the `must_include`
named-example check -- cross-validation that the class harvest is working,
not a data quality issue.

`sources_run`/`per_source_bucket`/`job_log`/`variety_trim` are all in
`summary` so a partial run (`--sources ...`) or a re-trimmed run is
self-documenting.

## How this should feed `build_universe_objects.py` (NOT wired in)

This script deliberately stops at `object_candidates_v2.json`. A future
merge session should, at minimum:

1. Human-review the `household_name` tier first (it's the smaller, safer
   set) -- spot-check `image_url`s actually render and `date_era`/
   `culture_region` read sensibly, the same review step every other harvest
   in this pipeline (`museum_candidates.json`, `people_candidates.json`)
   gets before merging.
2. Re-run the existing dedup against whatever `universe_objects.json` and
   `current_inventory.json` look like *at merge time* (both are live files
   that keep changing -- this harvest's dedup snapshot is only as fresh as
   25 Jul 2026).
3. Feed the survivors into `build_universe_objects.py`'s existing
   canonicalize -> enrich -> disambiguation/person-drop pipeline (its
   `canonicalize_titles`/`enrich_titles` in `wputils.py` already do exactly
   this for every other source) rather than trusting this script's
   Wikidata-side resolution as final -- Wikidata and enwiki occasionally
   disagree on canonical titles.
4. Decide whether the extended `kind` values above get merged as-is into
   `universe_objects.json`'s `kind` field (currently `site`/`building`/
   `artefact`/`manuscript`/`painting`/`sculpture`/`monument` only) or get
   collapsed back to `artefact` at that stage -- this script does not make
   that call, since it changes the schema every other harvester in this
   directory writes to.
5. Run `fetch_metrics.py` over the merged additions before they reach fame
   scoring, same as every other new-object batch.
