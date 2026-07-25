# Suitability signals (tools/fame/build_suitability.py)

## The problem this solves

One fame score (`tools/fame/build_scores.py`) is used to pick content for
three games with different needs: 0.50\*pageviews + 0.15\*languages +
0.10\*inlinks + 0.25\*cross-language consensus — all Wikipedia
*popularity*. Popularity says nothing about whether a specific item plays
*well* in the game it's placed in. A 22 Jul 2026 review found this
directly: famous subjects with unusable images played as unfairly hard,
and obscure subjects with giveaway clues played as hollow — "a famous
answer with a bad image is not easy."

This adds three read-only, game-specific **suitability** signals, computed
straight from the shipped content pools, alongside (never blended into)
the fame score. Run it any time after the pools or editions change:

```
python3 tools/fame/build_suitability.py
```

Reads `data/figures.json`, `data/reveal-who.json`, `data/reveal-what.json`,
`data/editions.json` (read-only). Writes `tools/fame/suitability.json`.
No network access, no dependencies beyond the Python 3.9 standard library,
runs in well under a second (1185 items).

## Output shape

`suitability.json` has two parallel views of the same data:

- `items`: flat dict keyed by content id. Each entry carries whichever of
  the three signals apply to that id — a person can be both a Lifeline
  figure (`data/figures.json`) and a Face Value portrait
  (`data/reveal-who.json`) under the *same id* (146 ids are — e.g.
  `napoleon`), so their record carries both `lifeline_journey` and
  `image_legibility`/`portrait_viability` blocks side by side.
- `signals.<name>`: the method, thresholds, corpus-wide distribution, and
  a `worst_offenders_scheduled` (or equivalent) list per signal, for
  reporting without re-deriving stats from 1185 item records.

Every score's `inputs` sub-object records the raw fields it was computed
from (never just the number) so a reviewer can check the score's reasoning
without re-running the script.

---

## Signal 1 — Lifeline journey

**One-sentence explanation:** a figure who was born and died in the same
place is a dull round on a map game no matter how famous they are, so we
score the great-circle distance between their birth and death points.

**Computation:** haversine distance (km) between `birth.{lat,lon}` and
`death.{lat,lon}` in `data/figures.json`. Pure geometry, no external data.

**Threshold — `dull_km = 50`:** the brief asked directly "how many figures
are under 50km apart" — the answer is **74 / 541 (13.7%)**, a natural
reading of "born and died in the same metro area." No distribution-shape
argument was needed for this one; it's a direct, literal reading of the
brief's own question, chosen over a fixed-percentile cut so the number
means something in kilometers to a non-engineer ("under 50km" is legible;
"bottom 14th percentile" is not).

**Distribution (541 figures):**

| percentile | km |
|---|---|
| p5 | 0.0 |
| p10 | 22.3 |
| p25 | 158.2 |
| p50 | 550.8 |
| p75 | 1,889.9 |
| p90 | 6,811.8 |
| p95 | 8,603.0 |
| p100 (max) | 16,765.3 (Robert Falcon Scott, England → Antarctica) |

Under 50km: 74. Under 100km: 106. Under 200km: 152.

**Data-quality guards (checked, none currently triggered):**
- `birth_at_0_0` / `death_at_0_0` — coordinates sitting on Null Island,
  almost always a missing-data placeholder rather than a real place.
- `impossible_distance` — a distance exceeding the physical maximum
  (half Earth's circumference, ~20,015 km); this can only happen from a
  coordinate bug.
- `large_journey_for_ancient_era_check_by_hand` — a >3,000km journey
  recorded for someone who died before 500 BC. This is a **soft**,
  non-blocking flag, not a claim of error: several real figures (Cyrus the
  Great, Alexander the Great, Trajan, Saint Peter) legitimately travelled
  thousands of km in antiquity via empire, exile or conquest, and none of
  the 541 figures actually trip this check today. It's a guard for future
  data entry, kept in and documented rather than silently added, per the
  brief's instruction not to invent thresholds quietly.

**Scheduled rounds, editions 28–64 (185 Lifeline rounds):** 12 are dull
(<50km). The 10 dullest currently scheduled:

| id | edition | date | journey_km |
|---|---|---|---|
| maria-theresa | 39 | 2026-08-07 | 0.0 |
| johannes-gutenberg | 47 | 2026-08-15 | 0.0 |
| hatshepsut | 53 | 2026-08-21 | 0.0 |
| marco-polo | 56 | 2026-08-24 | 0.0 |
| cleopatra | 56 | 2026-08-24 | 0.0 |
| ashoka | 57 | 2026-08-25 | 0.0 |
| harper-lee | 61 | 2026-08-29 | 0.0 |
| thomas-more | 43 | 2026-08-11 | 1.4 |
| david-king | 63 | 2026-08-31 | 9.1 |
| elizabeth-i-of-england | 45 | 2026-08-13 | 20.9 |

(Full list of 20 in `signals.lifeline_journey.worst_offenders_scheduled`.)

---

## Signal 2 — Image legibility

**One-sentence explanation:** risk is high when the subject is a small
part of the photo *and* the free opening scrap the app hands the player
is placed as far from the subject as the 3×3 grid allows.

**Why not real pixel stats.** The brief asks for per-cell luminance/edge
density. This script is Python 3.9 **stdlib only** — no Pillow, no numpy,
even though `tools/audit_start_scraps.py` (read for its geometry, not
modified) already depends on Pillow for its own purpose (rendering review
PNGs). All 819 files under `assets/img/` are JPEG-encoded pixel data (see
data-quality note below); the standard library has **no JPEG or PNG pixel
decoder**, only enough to parse file headers. Writing a DCT/Huffman JPEG
decoder from scratch would not be a "cheap proxy" — so per the brief's own
fallback instruction, this script does not compute per-cell pixel
statistics, and says so plainly rather than quietly skipping it.

**What it computes instead:**
1. **`money_scrap`/`start_scrap`/grid distance** — copied verbatim (not
   imported, so this script never needs Pillow) from
   `tools/audit_start_scraps.py`, which is the project's own reference
   implementation of `js/revealgame.js`'s tear geometry. If that geometry
   ever changes, re-copy the three functions; do not let them drift.
2. **`frac`** — the item's own authored subject-to-frame ratio, already in
   `data/reveal-who.json`/`reveal-what.json`. This needs no image
   decoding at all; it's the single strongest signal available.
3. **`risk = (1 - frac) * (grid_distance(start_cell, money_cell) / 4)`.**
   `start_scrap` *always* maximizes grid distance from the money cell
   (max 4 for a corner money-cell, 3 for an edge, 2 for dead-center) unless
   a curator already overrode it — so this factor rewards items whose
   money cell is central (opening cell stays close, so a small subject can
   still be nearby) and penalizes items whose money cell is a corner *and*
   whose subject is small (opening cell is the opposite corner, about as
   far as this grid can put it).
4. **Image header metadata (diagnostic only, not in `risk_score`):** width,
   height, format and bytes-per-megapixel, read via a ~30-line stdlib
   `struct` parser that walks JPEG SOF markers / the PNG IHDR chunk — this
   reads the header only, no pixel decode, exactly like `file` would.
   Bytes-per-megapixel is reported as a weak, whole-image,
   corpus-relative "how much visual detail does this image have" hint
   (JPEG compresses smooth regions — sky, plain backdrops — into fewer
   bytes than detailed/textured ones) but it is **not** used in
   `risk_score`, because it's confounded by old black-and-white
   photography (which also compresses small for unrelated reasons — the
   lowest bytes/MP images in the corpus are 1920s-30s portrait
   photographs, not empty backgrounds) and by encoder/quality settings
   that have nothing to do with content.

I considered an explicit geometric overlap model (treat the subject as a
box of area `frac` centered on `(fx,fy)` and intersect it with the opening
cell's rectangle) and rejected it after testing: it produces false zeros
for large, off-center subjects (e.g. Henry VIII, `frac=0.53`, money cell
near the top edge) purely from rectangle-clipping arithmetic, not because
the opening cell is actually bad. The simpler multiplicative risk above
avoids fabricating undconfirmed geometry and is more honest about being a
heuristic, not a measurement.

**Threshold — `risk_flag_cutoff = 0.75`:** chosen from the shape of the
risk histogram over all 790 who+what items (bucket width 0.05):

```
0.60-0.65: 123   0.70-0.75: 1   <- near-empty gap
0.65-0.70: 12    0.75-0.80: 9
                 0.80-0.85: 6
                 0.85-0.90: 4
```

There's a near-empty bucket at 0.70–0.75 (just 1 item) separating a long
shoulder (up to ~0.65, the bulk of the corpus) from a distinct worst tier
(0.75–0.85, 19 items). 0.75 sits in that gap — a natural break, not an
arbitrary round number.

**Distribution (790 items, both pools):**

| percentile | risk |
|---|---|
| p10 | 0.325 |
| p25 | 0.38 |
| p50 | 0.42 |
| p75 | 0.5625 |
| p90 | 0.6375 |
| p95 | 0.6446 |
| p99 | 0.8 |
| p100 (max) | 0.85 |

19 items flagged (risk ≥ 0.75) across the full pool.

**Data quality found:** 10 files under `assets/img/` are **PNG-encoded but
saved with a `.jpg` extension** (caught by the header parser reading a PNG
signature where a JPEG one was expected): `brando`, `confucius`,
`cyrus-great`, `imperial-regalia-japan`, `koh-i-noor`,
`lighthouse-alexandria`, `mikasa`, `saddam-hussein`, `sima-qian`,
`sylvia-plath`. Harmless for display (browsers/`<img>` sniff content, not
extension) but worth knowing about if anything else ever assumes `.jpg`
means JPEG bytes.

**Worst opening cells among the 370 scheduled image rounds, editions
28–64** (185 who + 185 what; the brief's "~300" undercounts because
editions 29–64 landed after that estimate was written — see git history):

| id | pool | edition | date | risk | frac | grid dist |
|---|---|---|---|---|---|---|
| joseph-haydn | who | 36 | 2026-08-04 | 0.85 | 0.15 | 4 |
| mary-anning | who | 36 | 2026-08-04 | 0.85 | 0.15 | 4 |
| prague-castle | what | 57 | 2026-08-25 | 0.84 | 0.16 | 4 |
| temple-artemis | what | 33 | 2026-08-01 | 0.82 | 0.18 | 4 |
| mona-lisa | what | 28 | 2026-07-27 | 0.80 | 0.20 | 4 |
| sima-qian | who | 39 | 2026-08-07 | 0.80 | 0.20 | 4 |
| sunday-grande-jatte | what | 43 | 2026-08-11 | 0.80 | 0.20 | 4 |
| winston-churchill | who | 47 | 2026-08-15 | 0.7955 | 0.204 | 4 |
| aztec-sun-stone | what | 62 | 2026-08-30 | 0.7868 | 0.213 | 4 |
| hoover-dam | what | 52 | 2026-08-20 | 0.75 | 0.25 | 4 |

(Full list of 25 in `signals.image_legibility.worst_offenders_scheduled`.)
Note `mona-lisa`, `winston-churchill` and `sunday-grande-jatte` land here
*because* they're famous enough that curators zoomed out to fit a small,
precise focal point (`frac` 0.20–0.21) rather than filling the frame —
exactly the "famous answer, bad image" failure mode from the brief.

---

## Signal 3 — Face Value portrait viability

**One-sentence explanation:** a portrait can only be a genuine photograph
if its subject was still alive after photography existed, so a painted or
sculpted likeness of someone who predates the camera plays much harder
than their fame score alone would suggest.

**Computation:** for each of the 426 `data/reveal-who.json` portraits,
scan `attribution` / `source` / `image_author` for medium keywords
(word-boundary regexes, case-insensitive):

- **photograph**: photo(graph)\*, daguerreotype, tintype, ambrotype,
  collodion, "wire/press photo"
- **sculpture**: bust, statue, sculpture, marble, bronze, relief
- **painting**: painting, "portrait by", self-portrait, fresco, mosaic,
  oil on canvas
- **graphic**: engraving, woodcut, etching, lithograph, drawing, sketch,
  illustration, miniature, print, manuscript, coin, stamp, medal,
  tapestry, icon

If nothing matches, fall back to a small (~15 name), manually-curated list
of 19th-century pioneer photographers (Mathew Brady, Alexander Gardner,
Julia Margaret Cameron, Nadar, Robert Howlett, …) — added because it
resolves one confirmed real case (Robert Howlett's famous 1857 photograph
of Brunel, which otherwise falls in the ambiguous era band below) and is
disclosed here rather than silently baked in.

If *still* nothing matches, parse the blurb's leading "(1889–1977)" /
"(c. 1341–1323 BC)" / "(c. 5th century BC)" life-dates (a consistent
pattern across all 426 blurbs — regex resolved all of them) and bucket
against two era thresholds:

- **`< 1839` → `non_photographic_unspecified`, high confidence.** 1839 is
  the public announcement of the daguerreotype process — practical
  photography did not exist before this date, full stop. We know the
  portrait *isn't* a photo; we just don't know which stylised type
  (painting vs. bust vs. coin vs. engraving) without a keyword hit, so
  it's left unspecified rather than guessed.
- **`1839`–`1860` → `unknown`, genuinely ambiguous.** By the wet-plate/
  collodion era (~1860) a surviving photograph is the norm for a notable
  public figure, but in the 21-year gap right after photography's
  invention it could plausibly be either — reported as `unknown` rather
  than guessed. Only 14/426 (3.3%) land here.
- **`≥ 1860` → `photograph`, era-inferred.** Statistically the default for
  a post-1860 public figure on Wikimedia Commons, absent a keyword saying
  otherwise.

**Result (426 portraits):**

| medium | count | fraction |
|---|---|---|
| photograph | 258 | 60.6% |
| non_photographic_unspecified | 127 | 29.8% |
| painting | 17 | 4.0% |
| unknown | 14 | 3.3% |
| graphic | 6 | 1.4% |
| sculpture | 4 | 0.9% |

**Photograph: 60.6% · stylised (painting+sculpture+graphic+unspecified):
36.2% · unknown: 3.3%.**

**Flag, not a verdict:** `flag_easy_but_stylised` = `difficulty == "easy"
AND stylised_likeness`. 20 portraits currently marked "easy" (presumably
by fame) have no possible photograph:

`alexander-great, benjamin-franklin, dante-alighieri, gautama-buddha,
george-washington, henry-viii, isaac-newton, jane-austen, kublai-khan,
louis-xiv, beethoven, marcus-aurelius, martin-luther, napoleon, pocahontas,
saladin, suleiman-magnificent, van-gogh-self, vlad-impaler, mozart`

This is the exact "famous answer with a bad image is not easy" pattern the
brief described — high fame drove an "easy" difficulty label, but the only
available likeness is a painting/bust/coin, which plays harder than the
label promises regardless of how famous the sitter is.

**Known limitation:** this is a text/era heuristic over Wikimedia Commons
metadata, not a real classification of the image content — a mislabeled
or missing attribution field will misclassify silently. Treat `unknown`
and `non_photographic_unspecified` as "needs a human glance," not "solved."

---

## Recommendation: combining fame and suitability (not implemented here)

**Do not blend these into one number.** Fame answers "would a lot of
people recognise this name"; suitability answers "will this specific round
play fairly in this specific game." Collapsing them into a single score
would hide exactly the failure mode this whole exercise exists to catch —
a famous/bad-image item would still average out to a middling score and
get picked anyway.

Recommended use, per game, when selecting future content:

1. **Rank by fame first**, as today — it's still the right proxy for "is
   this worth including at all" and for setting the target difficulty
   label.
2. **Use suitability as a gate + a difficulty corrector, not a ranking
   input:**
   - **Lifeline:** treat `dull` (journey < 50km) as a soft penalty, not a
     hard exclude — a dull journey can still be scheduled on an easier day
     where the *name* carries the round, but avoid stacking multiple dull
     journeys in the same week, and don't schedule a dull journey as the
     week's hardest round.
   - **Face Value / Relic:** treat `flag_worst_offender` (risk ≥ 0.75) as
     a hard pre-publication check — these need either a curated `start`
     override (the mechanism already exists in the data and in
     `tools/audit_start_scraps.py`) or a re-cropped `fx/fy/frac`, not a
     difficulty-label patch, before they're scheduled again.
   - **Face Value specifically:** when `stylised_likeness` is true,
     *raise* the effective difficulty by one tier from what fame alone
     would assign (an "easy" stylised portrait should play as "medium";
     a "medium" one as "hard") rather than excluding the item — these are
     often exactly the household names (Napoleon, Henry VIII, Mozart)
     worth keeping, just not on an "easy" day.
3. **Re-run suitability whenever the pools or `data/editions.json`
   change** — it's read-only and sub-second, so there's no reason for it
   to go stale the way a one-off manual review would.
4. Keep the two scores **visibly separate** in whatever review tooling
   consumes them (e.g. two columns, not one weighted average), so a human
   curator can see *why* an item is flagged, not just *that* it is.
