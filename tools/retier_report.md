# Difficulty re-tier — Dead Famous content pools

Generated 25 Jul 2026. Scope: the `difficulty` field of `data/reveal-who.json`,
`data/reveal-what.json` and `data/figures.json`. Nothing else was touched —
no other field, no other file, no manifest, no version bump.

## Why

The easy tier was not short of *content*, it was short of *labels*. Face Value
carried 106 items marked easy while 274 of its 426 items score fame ≥ 90; 67 of
the 121 marked hard also scored ≥ 90. Because almost every easy-labelled item
had already been scheduled, the compiler could not fill a Monday: editions 24–28
were published with **zero** easy Face Value and Relic rounds against a recipe
asking for up to four.

The arithmetic that makes it concrete. Under the 5-round recipe each game needs
14 easy / 13 medium / 8 hard rounds a week, so the 28-day repeat floor (locked
decision #5) needs at least 4 × that many *distinct* items per tier, and the
42-day target needs 6 ×. Measured at edition 65 (2026-09-02), the first
unscheduled day:

| pool | tier | eligible before | needed (28-day floor) | verdict |
|---|---|---|---|---|
| who | easy | 53 | 56 | **SHORT** |
| who | medium | 148 | 52 | ok |
| who | hard | 90 | 32 | ok |
| what | easy | 54 | 56 | **SHORT** |
| what | medium | 109 | 52 | ok |
| what | hard | 66 | 32 | ok |
| map | easy | 151 | 56 | ok |
| map | medium | 161 | 52 | ok |
| map | hard | 94 | 32 | ok |

Face Value easy and Relic easy were below the hard floor. That is not a content
shortage — it is a labelling defect.

## Which inputs I used, and which I did not

**Authoritative fame: `tools/fame/fame_scores.json`.** 8,094 titles, scored by
`build_scores.py`, percentile-ranked *within class* (person / artefact / structure /
artwork / other) so a famous statue is not compared against a famous emperor.

**Not used for scoring: `tools/fame/calibration_scores.json`.** It is a 30-item
calibration cohort scored by the older `score_fame.py` against *only those 30
items*, so its numbers live on a different scale (Napoleon 95.2, Tutankhamun 62.8
there, versus 99.6 and 93.5 in the real index). Useful as a scale sanity-check,
meaningless as a threshold source.

**`tools/fame/title_health.json`** — all 1,331 pool items resolve and all report
`ok`, so no item was excluded on status alone. But `ok` only proves *an article
exists and is long enough*, never that it is the **right** article; see the
wrong-resolution list below.

**`tools/fame/salience.json`** — used only as a *veto*, never as an axis. See the
blind-spot section: the salience blend is 42% WikiProject importance, which
systematically under-rates explorers and travellers, so it is not safe to demote on.

**`tools/fame/suitability.json`** — used as the difficulty corrector, exactly as
`tools/fame/SUITABILITY.md` §3 prescribes.

## The rule

> **Fame sets the band. Suitability only ever makes a round harder. The author's
> label stands wherever the measurement is ambiguous, and no label moves more than
> one tier.**

### 1. Fame band

Thresholds are the project's own, lifted from `tools/editions.config.json` — not
percentile cuts invented for this pass:

| band | test | constant |
|---|---|---|
| icon → `easy` | fame ≥ 90 | `icon_fame_threshold` |
| banker → `medium` | 75 ≤ fame < 90 | `banker_fame_threshold` |
| earned → `hard` | fame < 75 | — |

### 2. Hysteresis: a ±5 dead band at each threshold

An item is only moved *down* a tier when it is at least 5 points inside the next
band — an item authored easy at fame 87 keeps its label, one at 84 does not. This
is what stops the pass being a percentile cut: near a boundary the measurement is
not better evidence than the curator, and `QUALITY_RUBRIC.md`'s force-ranking
protocol adjudicates the clear bottom, not the marginal middle. It is what saved,
for example, Blackbeard (fame 85.5, easy) and Dian Fossey (71.3, medium).

### 3. Suitability corrector — one tier harder, never easier

`QUALITY_RUBRIC.md` is explicit that the tiers are about the **image**, not the
person: *"Fame of the image, not the person: Rutherford is famous, his face is
not — that's what difficulty tiers are for."* And `SUITABILITY.md` §3 gives the
correction verbatim: when `stylised_likeness` is true, *raise* the effective
difficulty by one tier from what fame alone would assign.

- **Face Value:** `portrait_viability.stylised_likeness` (a likeness that can only
  ever be a painting, bust or engraving) drops the band one tier. This is what
  puts Julius Caesar, Cleopatra and Genghis Khan at `medium` despite fame ≥ 98 —
  their faces are sculpture, not photography — and what moves Louis XIV, Martin
  Luther and Suleiman *out* of easy (`flag_easy_but_stylised`).

### 4. Promotion gates — a famous subject with a poor round is not easy

These block a promotion *into* easy. They never demote an item the author already
placed there, because the project's own audit says the fix in that direction is a
different one:

- **Face Value / Relic:** `image_legibility.flag_worst_offender` (crop risk ≥ 0.75)
  blocks promotion to easy. `SUITABILITY.md` is explicit that these need a re-crop
  or a curated `start` override, *"not a difficulty-label patch"* — so an already-easy
  worst offender (e.g. Al Capone, risk 0.82) keeps its label and is listed for a
  re-crop instead. This is why the Mona Lisa (fame 99.6, risk 0.80) was **not**
  promoted to easy.
- **Lifeline:** `lifeline_journey.dull` (birth→death < 50 km) blocks promotion to
  easy — a one-pin round gives the player less to work with than fame predicts. It
  does not demote: `QUALITY_RUBRIC.md` allows a flat journey *"for very famous
  figures"*, so Jesus (9 km), Julius Caesar (0 km) and Henry VIII (9 km) keep the
  easy labels their curator gave them.

### 5. One-tier cap

Where the evidence and the author disagree by two tiers, nothing moves. A
pageview-derived proxy is not strong enough to carry an item from `hard` to `easy`
in one step — the author who filed Warren Harding as hard probably knew his face
is not famous even though his article is busy. 77 items hit this cap and are
listed below as needing a human call.

### 6. Evidence gates — leave alone rather than guess

An item is untouched, and listed, when: title health is not `ok`; there is no
`fame_scores.json` entry; salience is `low_confidence`; the resolved article is
suspect; a Face Value portrait's medium is unknown; or a Lifeline figure has no
journey data. Three further conditions block *demotion only* (fame may be
understated, so a promotion would still be safe): a broken monthly pageview
series, salience exceeding fame by ≥ 25, or a resolved person-article with fewer
than 20 language versions.

### 7. The manifest constraint

Editions 0–64 are already compiled into `data/editions.json`. Relabelling an item
changes the difficulty mix of every edition it appears in, so each candidate move
was applied only if **no scheduled edition's distance from its declared recipe got
worse**. Moves that could not stand alone were applied in compensating groups
(a promotion and a demotion inside the same edition, or a 3-cycle), found by a
constraint-repair search. 167 of 466 candidate moves survived this test.

## Before / after

| pool | easy | medium | hard |
|---|---|---|---|
| Face Value **before** | 106 | 199 | 121 |
| Face Value **after** | **145** | 159 | 122 |
| Relic **before** | 107 | 160 | 97 |
| Relic **after** | **116** | 157 | 91 |
| Lifeline **before** | 204 | 212 | 125 |
| Lifeline **after** | **211** | 194 | 136 |

167 items moved: 70 into easy, 15 out of easy, 82 between medium and hard.

## Headroom against scheduling demand

Weekly demand per game under `NEW_RECIPE` is **14 easy / 13 medium / 8 hard**.
The 28-day repeat floor therefore needs ≥ **56 / 52 / 32** distinct eligible items;
the 42-day target needs a pool of ≥ **84 / 78 / 48**. `eligible` = not scheduled
within 28 editions of edition 65.

| pool | tier | pool before → after | eligible before → after | 28-day floor | 42-day pool target |
|---|---|---|---|---|---|
| who | easy | 106 → **145** | 53 → **92** | 56 ✅ | 84 ✅ |
| who | medium | 199 → **159** | 148 → **108** | 52 ✅ | 78 ✅ |
| who | hard | 121 → **122** | 90 → **91** | 32 ✅ | 48 ✅ |
| what | easy | 107 → **116** | 54 → **63** | 56 ✅ | 84 ✅ |
| what | medium | 160 → **157** | 109 → **106** | 52 ✅ | 78 ✅ |
| what | hard | 97 → **91** | 66 → **60** | 32 ✅ | 48 ✅ |
| map | easy | 204 → **211** | 151 → **158** | 56 ✅ | 84 ✅ |
| map | medium | 212 → **194** | 161 → **143** | 52 ✅ | 78 ✅ |
| map | hard | 125 → **136** | 94 → **105** | 32 ✅ | 48 ✅ |

**The bottleneck is relieved.** Face Value easy goes from 53 eligible (3 short of
the floor) to 92 — 36 spare. Relic easy goes from 54 (2 short) to 63 — 7 spare.
Every tier in every pool now clears the 28-day floor on eligibility and the
42-day target on pool size. No tier was emptied: the smallest is Relic hard at 91
items (floor 32, target 48).

Relic easy is the tight one, and the reason is structural rather than editorial:
only 29 Relic items are unscheduled anywhere in editions 0–64, so almost every
promotion needed a compensating demotion inside the same edition, and there were
only 12 of those available. 116 items is comfortably above the 84-item 42-day
target, so it is healthy in steady state — but it has the least slack and should
be the first pool the next content batch feeds.

## Items re-tiered (167)

### Face Value (`data/reveal-who.json`) — 96 moved

| id | old → new | fame | salience | reason |
|---|---|---|---|---|
| `louis-xiv` | easy → **medium** | 97.2 | 99.6 | fame 97.2 -> easy band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `martin-luther` | easy → **medium** | 96.9 | 98.5 | fame 96.9 -> easy band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `suleiman-magnificent` | easy → **medium** | 93.8 | 94.8 | fame 93.8 -> easy band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `dante-alighieri` | easy → **medium** | 93.6 | 95.7 | fame 93.6 -> easy band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `vlad-impaler` | easy → **medium** | 89.0 | 82.7 | fame 89.0 sits inside the +-5 dead band at 90 - the author's call stands; stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `julius-caesar` | hard → **medium** | 99.2 | 99.6 | fame 99.2 -> easy band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `cleopatra` | hard → **medium** | 98.5 | 95.7 | fame 98.5 -> easy band (icon >=90 / banker >=75); stylised likeness (sculpture, explicit_keyword) -> one tier harder |
| `genghis-khan` | hard → **medium** | 98.0 | 98.9 | fame 98.0 -> easy band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `aristotle` | hard → **medium** | 97.6 | 98.5 | fame 97.6 -> easy band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `catherine-great` | hard → **medium** | 97.0 | 99.6 | fame 97.0 -> easy band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `saint-paul` | hard → **medium** | 96.0 | 94.4 | fame 96.0 -> easy band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `george-iii` | hard → **medium** | 96.0 | 95.7 | fame 96.0 -> easy band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `abraham` | hard → **medium** | 95.7 | 89.5 | fame 95.7 -> easy band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `saint-peter` | hard → **medium** | 95.2 | 95.3 | fame 95.2 -> easy band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `ashoka-great` | hard → **medium** | 95.1 | 96.5 | fame 95.1 -> easy band (icon >=90 / banker >=75); stylised likeness (sculpture, explicit_keyword) -> one tier harder |
| `timur` | hard → **medium** | 93.0 | 95.3 | fame 93.0 -> easy band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `john-the-baptist` | hard → **medium** | 93.0 | 85.6 | fame 93.0 -> easy band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `adam-smith` | hard → **medium** | 92.5 | 91.6 | fame 92.5 -> easy band (icon >=90 / banker >=75); stylised likeness (graphic, explicit_keyword) -> one tier harder |
| `rumi` | hard → **medium** | 92.3 | 93.7 | fame 92.3 -> easy band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `cyrus-great` | hard → **medium** | 92.3 | 97.9 | fame 92.3 -> easy band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `philip-ii-spain` | hard → **medium** | 92.2 | 92.8 | fame 92.2 -> easy band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `henry-v` | hard → **medium** | 92.0 | 95.3 | fame 92.0 -> easy band (icon >=90 / banker >=75); stylised likeness (graphic, explicit_keyword) -> one tier harder |
| `hannibal` | hard → **medium** | 92.0 | 96.0 | fame 92.0 -> easy band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `arthur-schopenhauer` | hard → **medium** | 89.8 | 93.0 | fame 89.8 -> medium band (icon >=90 / banker >=75) |
| `jefferson-davis` | hard → **medium** | 88.0 | 89.4 | fame 88.0 -> medium band (icon >=90 / banker >=75) |
| `herman-melville` | hard → **medium** | 84.3 | 59.0 | fame 84.3 -> medium band (icon >=90 / banker >=75) |
| `henrik-ibsen` | hard → **medium** | 83.5 | 84.2 | fame 83.5 -> medium band (icon >=90 / banker >=75) |
| `cecil-rhodes` | hard → **medium** | 81.9 | 76.4 | fame 81.9 -> medium band (icon >=90 / banker >=75) |
| `fdr` | medium → **easy** | 99.5 | 99.6 | fame 99.5 -> easy band (icon >=90 / banker >=75) |
| `joseph-stalin` | medium → **easy** | 99.5 | 98.6 | fame 99.5 -> easy band (icon >=90 / banker >=75) |
| `john-lennon` | medium → **easy** | 98.8 | 94.5 | fame 98.8 -> easy band (icon >=90 / banker >=75) |
| `theodore-roosevelt` | medium → **easy** | 98.7 | 98.0 | fame 98.7 -> easy band (icon >=90 / banker >=75) |
| `eisenhower` | medium → **easy** | 98.4 | 99.6 | fame 98.4 -> easy band (icon >=90 / banker >=75) |
| `walt-disney` | medium → **easy** | 98.3 | 96.0 | fame 98.3 -> easy band (icon >=90 / banker >=75) |
| `frank-sinatra` | medium → **easy** | 97.9 | 94.8 | fame 97.9 -> easy band (icon >=90 / banker >=75) |
| `prince-philip` | medium → **easy** | 97.7 | 88.7 | fame 97.7 -> easy band (icon >=90 / banker >=75) |
| `george-harrison` | medium → **easy** | 97.3 | 75.5 | fame 97.3 -> easy band (icon >=90 / banker >=75) |
| `gaddafi` | medium → **easy** | 97.2 | 96.8 | fame 97.2 -> easy band (icon >=90 / banker >=75) |
| `tupac` | medium → **easy** | 97.1 | 65.5 | fame 97.1 -> easy band (icon >=90 / banker >=75) |
| `ulysses-grant` | medium → **easy** | 97.0 | 99.1 | fame 97.0 -> easy band (icon >=90 / banker >=75) |
| `darwin` | medium → **easy** | 97.0 | 99.6 | fame 97.0 -> easy band (icon >=90 / banker >=75) |
| `edward-viii` | medium → **easy** | 96.9 | 91.3 | fame 96.9 -> easy band (icon >=90 / banker >=75) |
| `oscar-wilde` | medium → **easy** | 96.7 | 94.1 | fame 96.7 -> easy band (icon >=90 / banker >=75) |
| `george-orwell` | medium → **easy** | 96.7 | 95.8 | fame 96.7 -> easy band (icon >=90 / banker >=75) |
| `khrushchev` | medium → **easy** | 96.0 | 99.0 | fame 96.0 -> easy band (icon >=90 / banker >=75) |
| `kissinger` | medium → **easy** | 96.0 | 82.6 | fame 96.0 -> easy band (icon >=90 / banker >=75) |
| `herbert-hoover` | medium → **easy** | 95.6 | 89.2 | fame 95.6 -> easy band (icon >=90 / banker >=75) |
| `grover-cleveland` | medium → **easy** | 95.2 | 90.5 | fame 95.2 -> easy band (icon >=90 / banker >=75) |
| `chiang-kai-shek` | medium → **easy** | 95.0 | 91.9 | fame 95.0 -> easy band (icon >=90 / banker >=75) |
| `calvin-coolidge` | medium → **easy** | 95.0 | 89.6 | fame 95.0 -> easy band (icon >=90 / banker >=75) |
| `henry-ford` | medium → **easy** | 94.9 | 86.6 | fame 94.9 -> easy band (icon >=90 / banker >=75) |
| `bismarck` | medium → **easy** | 94.7 | 99.6 | fame 94.7 -> easy band (icon >=90 / banker >=75) |
| `william-howard-taft` | medium → **easy** | 94.4 | 92.0 | fame 94.4 -> easy band (icon >=90 / banker >=75) |
| `isaac-asimov` | medium → **easy** | 94.0 | 77.3 | fame 94.0 -> easy band (icon >=90 / banker >=75) |
| `boris-yeltsin` | medium → **easy** | 93.9 | 92.7 | fame 93.9 -> easy band (icon >=90 / banker >=75) |
| `albert-camus` | medium → **easy** | 93.6 | 91.7 | fame 93.6 -> easy band (icon >=90 / banker >=75) |
| `frank-lloyd-wright` | medium → **easy** | 93.5 | 78.5 | fame 93.5 -> easy band (icon >=90 / banker >=75) |
| `kipling` | medium → **easy** | 93.4 | 98.0 | fame 93.4 -> easy band (icon >=90 / banker >=75) |
| `mohammad-reza-pahlavi` | medium → **easy** | 93.4 | 79.1 | fame 93.4 -> easy band (icon >=90 / banker >=75) |
| `idi-amin` | medium → **easy** | 93.2 | 80.8 | fame 93.2 -> easy band (icon >=90 / banker >=75) |
| `tchaikovsky` | medium → **easy** | 93.1 | 86.8 | fame 93.1 -> easy band (icon >=90 / banker >=75) |
| `senna` | medium → **easy** | 93.0 | 67.4 | fame 93.0 -> easy band (icon >=90 / banker >=75) |
| `shinzo-abe` | medium → **easy** | 92.9 | 93.1 | fame 92.9 -> easy band (icon >=90 / banker >=75) |
| `rfk` | medium → **easy** | 92.5 | 95.6 | fame 92.5 -> easy band (icon >=90 / banker >=75) |
| `deng-xiaoping` | medium → **easy** | 92.3 | 92.2 | fame 92.3 -> easy band (icon >=90 / banker >=75) |
| `ts-eliot` | medium → **easy** | 92.2 | 77.4 | fame 92.2 -> easy band (icon >=90 / banker >=75) |
| `joseph-smith` | medium → **easy** | 92.0 | 93.6 | fame 92.0 -> easy band (icon >=90 / banker >=75) |
| `pinochet` | medium → **easy** | 92.0 | 92.1 | fame 92.0 -> easy band (icon >=90 / banker >=75) |
| `steinbeck` | medium → **easy** | 91.3 | 69.7 | fame 91.3 -> easy band (icon >=90 / banker >=75) |
| `rockefeller` | medium → **easy** | 91.2 | 79.2 | fame 91.2 -> easy band (icon >=90 / banker >=75) |
| `arthur-miller` | medium → **easy** | 91.0 | 64.3 | fame 91.0 -> easy band (icon >=90 / banker >=75) |
| `walt-whitman` | medium → **easy** | 90.1 | 79.4 | fame 90.1 -> easy band (icon >=90 / banker >=75) |
| `ibn-sina` | medium → **hard** | 89.6 | 97.5 | fame 89.6 -> medium band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `justinian-i` | medium → **hard** | 88.9 | 96.4 | fame 88.9 -> medium band (icon >=90 / banker >=75); stylised likeness (painting, explicit_keyword) -> one tier harder |
| `franz-schubert` | medium → **hard** | 87.8 | 87.3 | fame 87.8 -> medium band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `horatio-nelson` | medium → **hard** | 87.6 | 95.7 | fame 87.6 -> medium band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `mary-wollstonecraft` | medium → **hard** | 86.4 | 91.3 | fame 86.4 -> medium band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `peter-paul-rubens` | medium → **hard** | 84.6 | 86.7 | fame 84.6 -> medium band (icon >=90 / banker >=75); stylised likeness (painting, explicit_keyword) -> one tier harder |
| `tokugawa-ieyasu` | medium → **hard** | 83.8 | 81.1 | fame 83.8 -> medium band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `hatshepsut` | medium → **hard** | 83.0 | 94.0 | fame 83.0 -> medium band (icon >=90 / banker >=75); stylised likeness (sculpture, explicit_keyword) -> one tier harder |
| `robert-burns` | medium → **hard** | 82.4 | 88.9 | fame 82.4 -> medium band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `shaka-zulu` | medium → **hard** | 78.0 | 76.8 | fame 78.0 -> medium band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `al-biruni` | medium → **hard** | 77.3 | 85.3 | fame 77.3 -> medium band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `friedrich-schiller` | medium → **hard** | 76.2 | 87.4 | fame 76.2 -> medium band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `montezuma-ii` | medium → **hard** | 73.0 | 71.9 | fame 73.0 sits inside the +-5 dead band at 75 - the author's call stands; stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `toussaint-louverture` | medium → **hard** | 72.6 | 81.6 | fame 72.6 sits inside the +-5 dead band at 75 - the author's call stands; stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `artemisia-gentileschi` | medium → **hard** | 71.7 | 49.6 | fame 71.7 sits inside the +-5 dead band at 75 - the author's call stands; stylised likeness (painting, explicit_keyword) -> one tier harder |
| `kosem-sultan` | medium → **hard** | 69.9 | 34.5 | fame 69.9 -> hard band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `ida-b-wells` | medium → **hard** | 69.0 | 83.6 | fame 69.0 -> hard band (icon >=90 / banker >=75) |
| `lise-meitner` | medium → **hard** | 65.4 | 81.9 | fame 65.4 -> hard band (icon >=90 / banker >=75) |
| `elizabeth-cady-stanton` | medium → **hard** | 62.9 | 77.7 | fame 62.9 -> hard band (icon >=90 / banker >=75) |
| `clara-barton` | medium → **hard** | 62.4 | 47.4 | fame 62.4 -> hard band (icon >=90 / banker >=75) |
| `chien-shiung-wu` | medium → **hard** | 56.1 | 69.1 | fame 56.1 -> hard band (icon >=90 / banker >=75) |
| `queen-nzinga` | medium → **hard** | 52.1 | 61.1 | fame 52.1 -> hard band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |
| `vera-rubin` | medium → **hard** | 50.4 | 47.0 | fame 50.4 -> hard band (icon >=90 / banker >=75) |
| `qutuz` | medium → **hard** | 39.1 | 23.6 | fame 39.1 -> hard band (icon >=90 / banker >=75); stylised likeness (non_photographic_unspecified, era_predates_photography) -> one tier harder |

### Relic (`data/reveal-what.json`) — 29 moved

| id | old → new | fame | salience | reason |
|---|---|---|---|---|
| `itsukushima-shrine` | easy → **medium** | 81.3 | 74.7 | fame 81.3 -> medium band (icon >=90 / banker >=75) |
| `rialto-bridge` | easy → **medium** | 75.2 | 39.5 | fame 75.2 -> medium band (icon >=90 / banker >=75) |
| `masada` | hard → **medium** | 89.7 | 77.8 | fame 89.7 -> medium band (icon >=90 / banker >=75) |
| `lanse-aux-meadows` | hard → **medium** | 88.7 | 91.3 | fame 88.7 -> medium band (icon >=90 / banker >=75) |
| `merv` | hard → **medium** | 87.9 | 83.3 | fame 87.9 -> medium band (icon >=90 / banker >=75) |
| `bhimbetka` | hard → **medium** | 87.8 | 90.7 | fame 87.8 -> medium band (icon >=90 / banker >=75) |
| `cyrene` | hard → **medium** | 86.9 | 85.9 | fame 86.9 -> medium band (icon >=90 / banker >=75) |
| `benin-bronzes` | hard → **medium** | 86.9 | 96.1 | fame 86.9 -> medium band (icon >=90 / banker >=75) |
| `ollantaytambo` | hard → **medium** | 86.3 | 80.4 | fame 86.3 -> medium band (icon >=90 / banker >=75) |
| `little-mermaid-statue` | hard → **medium** | 84.6 | 82.6 | fame 84.6 -> medium band (icon >=90 / banker >=75) |
| `daigo-fukuryu-maru` | hard → **medium** | 83.6 | 79.5 | fame 83.6 -> medium band (icon >=90 / banker >=75) |
| `stone-town-zanzibar-door` | hard → **medium** | 83.2 | 70.3 | fame 83.2 -> medium band (icon >=90 / banker >=75) |
| `tassili-rock-art` | hard → **medium** | 79.0 | 71.0 | fame 79.0 -> medium band (icon >=90 / banker >=75) |
| `forbidden-city` | medium → **easy** | 96.3 | 95.1 | fame 96.3 -> easy band (icon >=90 / banker >=75) |
| `british-museum` | medium → **easy** | 95.7 | 96.8 | fame 95.7 -> easy band (icon >=90 / banker >=75) |
| `lighthouse-alexandria` | medium → **easy** | 95.2 | 92.8 | fame 95.2 -> easy band (icon >=90 / banker >=75) |
| `holy-sepulchre` | medium → **easy** | 95.0 | 95.9 | fame 95.0 -> easy band (icon >=90 / banker >=75) |
| `colossus-rhodes` | medium → **easy** | 95.0 | 94.8 | fame 95.0 -> easy band (icon >=90 / banker >=75) |
| `red-fort` | medium → **easy** | 94.9 | 92.4 | fame 94.9 -> easy band (icon >=90 / banker >=75) |
| `voynich-manuscript` | medium → **easy** | 94.2 | 88.4 | fame 94.2 -> easy band (icon >=90 / banker >=75) |
| `hope-diamond` | medium → **easy** | 92.7 | 86.0 | fame 92.7 -> easy band (icon >=90 / banker >=75) |
| `gyeongbokgung` | medium → **easy** | 91.0 | 94.0 | fame 91.0 -> easy band (icon >=90 / banker >=75) |
| `amber-room` | medium → **easy** | 90.3 | 79.2 | fame 90.3 -> easy band (icon >=90 / banker >=75) |
| `amber-fort` | medium → **easy** | 90.0 | 84.3 | fame 90.0 -> easy band (icon >=90 / banker >=75) |
| `mildenhall-treasure` | medium → **hard** | 69.2 | 72.4 | fame 69.2 -> hard band (icon >=90 / banker >=75) |
| `alfred-jewel` | medium → **hard** | 68.9 | 77.9 | fame 68.9 -> hard band (icon >=90 / banker >=75) |
| `tara-brooch` | medium → **hard** | 68.9 | 84.5 | fame 68.9 -> hard band (icon >=90 / banker >=75) |
| `rila-monastery` | medium → **hard** | 68.6 | 60.7 | fame 68.6 -> hard band (icon >=90 / banker >=75) |
| `olmec-colossal-head` | medium → **hard** | 64.0 | 86.9 | fame 64.0 -> hard band (icon >=90 / banker >=75) |

### Lifeline (`data/figures.json`) — 42 moved

| id | old → new | fame | salience | reason |
|---|---|---|---|---|
| `yitzhak-rabin` | easy → **medium** | 84.4 | 91.7 | fame 84.4 -> medium band (icon >=90 / banker >=75) |
| `ovid` | easy → **medium** | 84.1 | 95.0 | fame 84.1 -> medium band (icon >=90 / banker >=75) |
| `miguel-de-cervantes` | easy → **medium** | 84.0 | 72.2 | fame 84.0 -> medium band (icon >=90 / banker >=75) |
| `sophocles` | easy → **medium** | 82.3 | 88.3 | fame 82.3 -> medium band (icon >=90 / banker >=75) |
| `toyotomi-hideyoshi` | easy → **medium** | 82.1 | 77.9 | fame 82.1 -> medium band (icon >=90 / banker >=75) |
| `boudica` | easy → **medium** | 80.9 | 86.3 | fame 80.9 -> medium band (icon >=90 / banker >=75) |
| `shaka-zulu` | easy → **medium** | 78.0 | 76.8 | fame 78.0 -> medium band (icon >=90 / banker >=75) |
| `leonidas-i` | easy → **medium** | 76.9 | 78.9 | fame 76.9 -> medium band (icon >=90 / banker >=75) |
| `benjamin-disraeli` | hard → **medium** | 87.0 | 96.4 | fame 87.0 -> medium band (icon >=90 / banker >=75) |
| `septimius-severus` | hard → **medium** | 85.8 | 87.8 | fame 85.8 -> medium band (icon >=90 / banker >=75) |
| `constantine-xi` | hard → **medium** | 76.6 | 82.5 | fame 76.6 -> medium band (icon >=90 / banker >=75) |
| `nader-shah` | hard → **medium** | 76.3 | 68.3 | fame 76.3 -> medium band (icon >=90 / banker >=75) |
| `bob-marley` | medium → **easy** | 97.5 | 80.1 | fame 97.5 -> easy band (icon >=90 / banker >=75) |
| `henry-kissinger` | medium → **easy** | 96.0 | 82.6 | fame 96.0 -> easy band (icon >=90 / banker >=75) |
| `james-i-england` | medium → **easy** | 94.8 | 95.9 | fame 94.8 -> easy band (icon >=90 / banker >=75) |
| `william-mckinley` | medium → **easy** | 94.7 | 90.7 | fame 94.7 -> easy band (icon >=90 / banker >=75) |
| `napoleon-iii` | medium → **easy** | 93.6 | 87.1 | fame 93.6 -> easy band (icon >=90 / banker >=75) |
| `haile-selassie` | medium → **easy** | 92.7 | 89.8 | fame 92.7 -> easy band (icon >=90 / banker >=75) |
| `josip-broz-tito` | medium → **easy** | 92.7 | 97.6 | fame 92.7 -> easy band (icon >=90 / banker >=75) |
| `ho-chi-minh` | medium → **easy** | 92.6 | 80.8 | fame 92.6 -> easy band (icon >=90 / banker >=75) |
| `tiberius` | medium → **easy** | 92.3 | 96.8 | fame 92.3 -> easy band (icon >=90 / banker >=75) |
| `philip-ii-spain` | medium → **easy** | 92.2 | 92.8 | fame 92.2 -> easy band (icon >=90 / banker >=75) |
| `william-iii` | medium → **easy** | 90.6 | 97.8 | fame 90.6 -> easy band (icon >=90 / banker >=75) |
| `henry-ii-england` | medium → **easy** | 90.5 | 96.4 | fame 90.5 -> easy band (icon >=90 / banker >=75) |
| `wernher-von-braun` | medium → **easy** | 90.2 | 83.0 | fame 90.2 -> easy band (icon >=90 / banker >=75) |
| `trajan` | medium → **easy** | 90.2 | 97.2 | fame 90.2 -> easy band (icon >=90 / banker >=75) |
| `alexander-ii-of-russia` | medium → **easy** | 90.0 | 74.6 | fame 90.0 -> easy band (icon >=90 / banker >=75) |
| `vercingetorix` | medium → **hard** | 69.3 | 74.6 | fame 69.3 -> hard band (icon >=90 / banker >=75) |
| `gustavus-adolphus` | medium → **hard** | 67.9 | 79.9 | fame 67.9 -> hard band (icon >=90 / banker >=75) |
| `georges-clemenceau` | medium → **hard** | 67.4 | 75.1 | fame 67.4 -> hard band (icon >=90 / banker >=75) |
| `themistocles` | medium → **hard** | 66.8 | 86.3 | fame 66.8 -> hard band (icon >=90 / banker >=75) |
| `jose-marti` | medium → **hard** | 66.6 | 76.2 | fame 66.6 -> hard band (icon >=90 / banker >=75) |
| `john-iii-sobieski` | medium → **hard** | 64.0 | 72.6 | fame 64.0 -> hard band (icon >=90 / banker >=75) |
| `michel-ney` | medium → **hard** | 62.9 | 32.0 | fame 62.9 -> hard band (icon >=90 / banker >=75) |
| `atahualpa` | medium → **hard** | 62.5 | 64.9 | fame 62.5 -> hard band (icon >=90 / banker >=75) |
| `afonso-de-albuquerque` | medium → **hard** | 60.2 | 75.6 | fame 60.2 -> hard band (icon >=90 / banker >=75) |
| `henry-the-navigator` | medium → **hard** | 59.9 | 67.8 | fame 59.9 -> hard band (icon >=90 / banker >=75) |
| `andreas-vesalius` | medium → **hard** | 57.9 | 67.5 | fame 57.9 -> hard band (icon >=90 / banker >=75) |
| `mikhail-kutuzov` | medium → **hard** | 57.2 | 74.9 | fame 57.2 -> hard band (icon >=90 / banker >=75) |
| `simon-de-montfort` | medium → **hard** | 56.5 | 55.2 | fame 56.5 -> hard band (icon >=90 / banker >=75) |
| `vasco-nunez-de-balboa` | medium → **hard** | 54.4 | 40.0 | fame 54.4 -> hard band (icon >=90 / banker >=75) |
| `francisco-vazquez-de-coronado` | medium → **hard** | 47.7 | 23.9 | fame 47.7 -> hard band (icon >=90 / banker >=75) |

## Items deliberately left alone

### A. Evidence too weak to act on (120)

**1. Suspected wrong Wikipedia article** (6)

| pool | id | tier kept | fame | salience | reason |
|---|---|---|---|---|---|
| Lifeline | `abd-el-kader` | hard | 25.1 | 1.2 | suspected wrong article: resolves to 'Abdul Qadir' (15 languages, 57k views) - not the Algerian emir |
| Relic | `sunflowers` | medium | 93.1 | 78.5 | resolved title 'Helianthus' shares no word with the item name - suspected wrong article |
| Relic | `sunflowers-munich` | medium | 93.1 | 78.5 | resolved title 'Helianthus' shares no word with the item name - suspected wrong article |
| Relic | `golden-pavilion` | medium | 80.0 | 77.7 | suspected wrong article: resolves to Mishima's novel 'The Temple of the Golden Pavilion', not Kinkaku-ji |
| Relic | `olympia-stadium` | medium | 70.8 | 75.4 | suspected wrong article: resolves to 'Detroit Olympia', a US ice-hockey arena |
| Relic | `great-buddha-kamakura` | medium | 70.2 | 71.8 | suspected wrong article: resolves to the temple 'Kotoku-in', not the statue |

**2. Two-tier disagreement — needs a human call** (77)

| pool | id | tier kept | fame | salience | reason |
|---|---|---|---|---|---|
| Lifeline | `catherine` | hard | 97.0 | 99.6 | two-tier disagreement (authored hard, evidence says easy, fame 97.0) - too large to settle from a popularity proxy |
| Lifeline | `william-the-conqueror` | hard | 95.5 | 95.4 | two-tier disagreement (authored hard, evidence says easy, fame 95.5) - too large to settle from a popularity proxy |
| Lifeline | `grace-kelly` | hard | 94.5 | 57.5 | two-tier disagreement (authored hard, evidence says easy, fame 94.5) - too large to settle from a popularity proxy |
| Lifeline | `saladin` | hard | 94.3 | 95.6 | two-tier disagreement (authored hard, evidence says easy, fame 94.3) - too large to settle from a popularity proxy |
| Lifeline | `cook` | hard | 93.9 | 98.8 | two-tier disagreement (authored hard, evidence says easy, fame 93.9) - too large to settle from a popularity proxy |
| Lifeline | `suleiman` | hard | 93.8 | 94.8 | two-tier disagreement (authored hard, evidence says easy, fame 93.8) - too large to settle from a popularity proxy |
| Lifeline | `harriet-tubman` | hard | 93.2 | 88.3 | two-tier disagreement (authored hard, evidence says easy, fame 93.2) - too large to settle from a popularity proxy |
| Lifeline | `tamerlane` | hard | 93.0 | 95.3 | two-tier disagreement (authored hard, evidence says easy, fame 93.0) - too large to settle from a popularity proxy |
| Lifeline | `augusto-pinochet` | hard | 92.0 | 92.1 | two-tier disagreement (authored hard, evidence says easy, fame 92.0) - too large to settle from a popularity proxy |
| Lifeline | `hannibal` | hard | 92.0 | 96.0 | two-tier disagreement (authored hard, evidence says easy, fame 92.0) - too large to settle from a popularity proxy |
| Lifeline | `george-i` | hard | 91.9 | 89.6 | two-tier disagreement (authored hard, evidence says easy, fame 91.9) - too large to settle from a popularity proxy |
| Lifeline | `bolivar` | hard | 91.8 | 99.6 | two-tier disagreement (authored hard, evidence says easy, fame 91.8) - too large to settle from a popularity proxy |
| Lifeline | `john-king-of-england` | hard | 91.0 | 94.6 | two-tier disagreement (authored hard, evidence says easy, fame 91.0) - too large to settle from a popularity proxy |
| Lifeline | `robert-mugabe` | hard | 90.4 | 86.5 | two-tier disagreement (authored hard, evidence says easy, fame 90.4) - too large to settle from a popularity proxy |
| Lifeline | `vascodagama` | hard | 90.2 | 85.3 | two-tier disagreement (authored hard, evidence says easy, fame 90.2) - too large to settle from a popularity proxy |
| Lifeline | `f-scott-fitzgerald` | hard | 90.2 | 56.2 | two-tier disagreement (authored hard, evidence says easy, fame 90.2) - too large to settle from a popularity proxy |
| Lifeline | `robert-falcon-scott` | easy | 73.1 | 93.6 | two-tier disagreement (authored easy, evidence says hard, fame 73.1) - too large to settle from a popularity proxy |
| Lifeline | `toussaint-louverture` | easy | 72.6 | 81.6 | two-tier disagreement (authored easy, evidence says hard, fame 72.6) - too large to settle from a popularity proxy |
| Lifeline | `yi-sun-sin` | easy | 62.6 | 52.2 | two-tier disagreement (authored easy, evidence says hard, fame 62.6) - too large to settle from a popularity proxy |
| Lifeline | `bartolomeu-dias` | easy | 61.5 | 40.3 | two-tier disagreement (authored easy, evidence says hard, fame 61.5) - too large to settle from a popularity proxy |
| Relic | `magna-carta` | hard | 99.5 | 100.0 | two-tier disagreement (authored hard, evidence says easy, fame 99.5) - too large to settle from a popularity proxy |
| Relic | `dead-sea-scrolls` | hard | 98.7 | 99.7 | two-tier disagreement (authored hard, evidence says easy, fame 98.7) - too large to settle from a popularity proxy |
| Relic | `shroud-of-turin` | hard | 97.4 | 88.1 | two-tier disagreement (authored hard, evidence says easy, fame 97.4) - too large to settle from a popularity proxy |
| Relic | `saturn-v` | hard | 97.0 | 94.2 | two-tier disagreement (authored hard, evidence says easy, fame 97.0) - too large to settle from a popularity proxy |
| Relic | `hammurabi-stele` | hard | 97.0 | 99.5 | two-tier disagreement (authored hard, evidence says easy, fame 97.0) - too large to settle from a popularity proxy |
| Relic | `domesday-book` | hard | 97.0 | 97.3 | two-tier disagreement (authored hard, evidence says easy, fame 97.0) - too large to settle from a popularity proxy |
| Relic | `antikythera-mechanism` | hard | 96.7 | 95.1 | two-tier disagreement (authored hard, evidence says easy, fame 96.7) - too large to settle from a popularity proxy |
| Relic | `gobekli-tepe` | hard | 96.6 | 98.1 | two-tier disagreement (authored hard, evidence says easy, fame 96.6) - too large to settle from a popularity proxy |
| Relic | `ajanta-caves` | hard | 96.3 | 97.7 | two-tier disagreement (authored hard, evidence says easy, fame 96.3) - too large to settle from a popularity proxy |
| Relic | `koh-i-noor` | hard | 95.6 | 87.3 | two-tier disagreement (authored hard, evidence says easy, fame 95.6) - too large to settle from a popularity proxy |
| Relic | `palmyra` | hard | 95.4 | 98.3 | two-tier disagreement (authored hard, evidence says easy, fame 95.4) - too large to settle from a popularity proxy |
| Relic | `ctesiphon` | hard | 93.8 | 96.4 | two-tier disagreement (authored hard, evidence says easy, fame 93.8) - too large to settle from a popularity proxy |
| Relic | `gutenberg-bible` | hard | 93.4 | 96.9 | two-tier disagreement (authored hard, evidence says easy, fame 93.4) - too large to settle from a popularity proxy |
| Relic | `laocoon` | hard | 93.2 | 94.5 | two-tier disagreement (authored hard, evidence says easy, fame 93.2) - too large to settle from a popularity proxy |
| Relic | `trajan-column` | hard | 93.1 | 97.7 | two-tier disagreement (authored hard, evidence says easy, fame 93.1) - too large to settle from a popularity proxy |
| Relic | `newgrange-entrance-stone` | hard | 92.5 | 93.7 | two-tier disagreement (authored hard, evidence says easy, fame 92.5) - too large to settle from a popularity proxy |
| Relic | `hampi` | hard | 92.0 | 89.0 | two-tier disagreement (authored hard, evidence says easy, fame 92.0) - too large to settle from a popularity proxy |
| Relic | `kannon` | hard | 91.5 | 94.4 | two-tier disagreement (authored hard, evidence says easy, fame 91.5) - too large to settle from a popularity proxy |
| Relic | `cyrus-cylinder` | hard | 91.4 | 97.0 | two-tier disagreement (authored hard, evidence says easy, fame 91.4) - too large to settle from a popularity proxy |
| Relic | `topkapi-palace` | hard | 91.3 | 82.7 | two-tier disagreement (authored hard, evidence says easy, fame 91.3) - too large to settle from a popularity proxy |
| Relic | `cullinan-diamond` | hard | 91.2 | 81.7 | two-tier disagreement (authored hard, evidence says easy, fame 91.2) - too large to settle from a popularity proxy |
| Relic | `mausoleum-halicarnassus` | hard | 91.2 | 71.8 | two-tier disagreement (authored hard, evidence says easy, fame 91.2) - too large to settle from a popularity proxy |
| Relic | `catalhoyuk` | hard | 90.9 | 90.0 | two-tier disagreement (authored hard, evidence says easy, fame 90.9) - too large to settle from a popularity proxy |
| Relic | `konark-sun-temple` | hard | 90.8 | 75.7 | two-tier disagreement (authored hard, evidence says easy, fame 90.8) - too large to settle from a popularity proxy |
| Relic | `moray` | hard | 90.5 | 90.3 | two-tier disagreement (authored hard, evidence says easy, fame 90.5) - too large to settle from a popularity proxy |
| Relic | `pergamon` | hard | 90.0 | 96.0 | two-tier disagreement (authored hard, evidence says easy, fame 90.0) - too large to settle from a popularity proxy |
| Face Value | `jimmy-carter` | hard | 99.4 | 97.4 | two-tier disagreement (authored hard, evidence says easy, fame 99.4) - too large to settle from a popularity proxy |
| Face Value | `george-hw-bush` | hard | 98.7 | 98.5 | two-tier disagreement (authored hard, evidence says easy, fame 98.7) - too large to settle from a popularity proxy |
| Face Value | `stephen-hawking` | hard | 97.9 | 85.8 | two-tier disagreement (authored hard, evidence says easy, fame 97.9) - too large to settle from a popularity proxy |
| Face Value | `tolkien` | hard | 97.8 | 81.7 | two-tier disagreement (authored hard, evidence says easy, fame 97.8) - too large to settle from a popularity proxy |
| Face Value | `freud` | hard | 97.7 | 98.4 | two-tier disagreement (authored hard, evidence says easy, fame 97.7) - too large to settle from a popularity proxy |
| Face Value | `ambedkar` | hard | 97.6 | 94.8 | two-tier disagreement (authored hard, evidence says easy, fame 97.6) - too large to settle from a popularity proxy |
| Face Value | `george-v` | hard | 97.4 | 93.3 | two-tier disagreement (authored hard, evidence says easy, fame 97.4) - too large to settle from a popularity proxy |
| Face Value | `woodrow-wilson` | hard | 96.8 | 94.2 | two-tier disagreement (authored hard, evidence says easy, fame 96.8) - too large to settle from a popularity proxy |
| Face Value | `agatha-christie` | hard | 96.5 | 78.6 | two-tier disagreement (authored hard, evidence says easy, fame 96.5) - too large to settle from a popularity proxy |
| Face Value | `franz-kafka` | hard | 96.1 | 92.9 | two-tier disagreement (authored hard, evidence says easy, fame 96.1) - too large to settle from a popularity proxy |
| Face Value | `hirohito` | hard | 95.8 | 93.4 | two-tier disagreement (authored hard, evidence says easy, fame 95.8) - too large to settle from a popularity proxy |
| Face Value | `kurt-cobain` | hard | 95.0 | 74.7 | two-tier disagreement (authored hard, evidence says easy, fame 95.0) - too large to settle from a popularity proxy |
| Face Value | `william-mckinley` | hard | 94.7 | 90.7 | two-tier disagreement (authored hard, evidence says easy, fame 94.7) - too large to settle from a popularity proxy |
| Face Value | `warren-harding` | hard | 94.6 | 90.2 | two-tier disagreement (authored hard, evidence says easy, fame 94.6) - too large to settle from a popularity proxy |
| Face Value | `andrew-johnson` | hard | 93.9 | 91.2 | two-tier disagreement (authored hard, evidence says easy, fame 93.9) - too large to settle from a popularity proxy |
| Face Value | `pol-pot` | hard | 93.8 | 84.7 | two-tier disagreement (authored hard, evidence says easy, fame 93.8) - too large to settle from a popularity proxy |
| Face Value | `ferdinand-marcos` | hard | 93.3 | 95.0 | two-tier disagreement (authored hard, evidence says easy, fame 93.3) - too large to settle from a popularity proxy |
| Face Value | `lovecraft` | hard | 93.2 | 82.5 | two-tier disagreement (authored hard, evidence says easy, fame 93.2) - too large to settle from a popularity proxy |
| Face Value | `james-garfield` | hard | 93.2 | 83.3 | two-tier disagreement (authored hard, evidence says easy, fame 93.2) - too large to settle from a popularity proxy |
| Face Value | `james-buchanan` | hard | 92.8 | 86.2 | two-tier disagreement (authored hard, evidence says easy, fame 92.8) - too large to settle from a popularity proxy |
| Face Value | `kurosawa` | hard | 92.5 | 78.5 | two-tier disagreement (authored hard, evidence says easy, fame 92.5) - too large to settle from a popularity proxy |
| Face Value | `benjamin-harrison` | hard | 92.3 | 90.8 | two-tier disagreement (authored hard, evidence says easy, fame 92.3) - too large to settle from a popularity proxy |
| Face Value | `robert-e-lee` | hard | 92.2 | 90.4 | two-tier disagreement (authored hard, evidence says easy, fame 92.2) - too large to settle from a popularity proxy |
| Face Value | `martin-van-buren` | hard | 92.1 | 87.5 | two-tier disagreement (authored hard, evidence says easy, fame 92.1) - too large to settle from a popularity proxy |
| Face Value | `herodotus` | hard | 90.8 | 98.2 | two-tier disagreement (authored hard, evidence says easy, fame 90.8) - too large to settle from a popularity proxy |
| Face Value | `raphael` | hard | 90.7 | 74.7 | two-tier disagreement (authored hard, evidence says easy, fame 90.7) - too large to settle from a popularity proxy |
| Face Value | `emily-dickinson` | hard | 90.5 | 88.4 | two-tier disagreement (authored hard, evidence says easy, fame 90.5) - too large to settle from a popularity proxy |
| Face Value | `ralph-waldo-emerson` | hard | 90.3 | 84.5 | two-tier disagreement (authored hard, evidence says easy, fame 90.3) - too large to settle from a popularity proxy |
| Face Value | `pocahontas` | easy | 84.0 | 77.0 | two-tier disagreement (authored easy, evidence says hard, fame 84.0) - too large to settle from a popularity proxy |
| Face Value | `wangari-maathai` | easy | 61.4 | 74.0 | two-tier disagreement (authored easy, evidence says hard, fame 61.4) - too large to settle from a popularity proxy |
| Face Value | `van-gogh-self` | easy | 28.5 | 22.8 | two-tier disagreement (authored easy, evidence says hard, fame 28.5) - too large to settle from a popularity proxy |

**3. Demotion blocked — the fame reading is suspect** (16)

| pool | id | tier kept | fame | salience | reason |
|---|---|---|---|---|---|
| Lifeline | `jose-de-san-martin` | medium | 68.0 | 96.8 | demotion blocked: salience 96.8 is 28.8 above fame 68.0 - the history-lover signal contradicts the popularity signal |
| Lifeline | `demosthenes` | medium | 67.2 | 92.2 | demotion blocked: salience 92.2 is 25.0 above fame 67.2 - the history-lover signal contradicts the popularity signal |
| Lifeline | `otto-the-great` | medium | 64.2 | 92.0 | demotion blocked: salience 92.0 is 27.8 above fame 64.2 - the history-lover signal contradicts the popularity signal |
| Lifeline | `franz-joseph` | medium | 59.7 | 93.8 | demotion blocked: salience 93.8 is 34.0 above fame 59.7 - the history-lover signal contradicts the popularity signal |
| Lifeline | `tsar-nicholas-ii` | easy | 57.9 | 89.7 | demotion blocked: monthly pageview series is broken (pv_stat 4343 vs 36091/mo implied by the 5-year total) - almost certainly a page move; fame is understated |
| Lifeline | `christine-de-pizan` | medium | 52.7 | 80.5 | demotion blocked: salience 80.5 is 27.8 above fame 52.7 - the history-lover signal contradicts the popularity signal |
| Lifeline | `roxelana` | easy | 50.4 | 81.2 | demotion blocked: salience 81.2 is 30.7 above fame 50.4 - the history-lover signal contradicts the popularity signal |
| Lifeline | `kim-il-sung` | medium | 50.3 | 92.3 | demotion blocked: monthly pageview series is broken (pv_stat 594 vs 47335/mo implied by the 5-year total) - almost certainly a page move; fame is understated |
| Relic | `nazca-lines` | medium | 54.7 | 61.1 | demotion blocked: monthly pageview series is broken (pv_stat 557 vs 9937/mo implied by the 5-year total) - almost certainly a page move; fame is understated |
| Relic | `sanchi-stupa` | medium | 54.0 | 87.2 | demotion blocked: salience 87.2 is 33.2 above fame 54.0 - the history-lover signal contradicts the popularity signal |
| Relic | `temple-of-hatshepsut` | medium | 48.9 | 91.4 | demotion blocked: monthly pageview series is broken (pv_stat 74 vs 3900/mo implied by the 5-year total) - almost certainly a page move; fame is understated |
| Face Value | `kaiser-wilhelm-ii` | medium | 67.3 | 98.0 | demotion blocked: monthly pageview series is broken (pv_stat 8974 vs 43966/mo implied by the 5-year total) - almost certainly a page move; fame is understated |
| Face Value | `nicholas-ii` | medium | 57.9 | 89.7 | demotion blocked: monthly pageview series is broken (pv_stat 4343 vs 36091/mo implied by the 5-year total) - almost certainly a page move; fame is understated |
| Face Value | `hurrem-sultan` | medium | 50.4 | 81.2 | demotion blocked: salience 81.2 is 30.7 above fame 50.4 - the history-lover signal contradicts the popularity signal |
| Face Value | `al-khwarizmi` | medium | 46.2 | 84.3 | demotion blocked: monthly pageview series is broken (pv_stat 1037 vs 13130/mo implied by the 5-year total) - almost certainly a page move; fame is understated |
| Face Value | `baybars` | medium | 45.6 | 77.2 | demotion blocked: salience 77.2 is 31.6 above fame 45.6 - the history-lover signal contradicts the popularity signal |

**4. Missing or unusable input data** (21)

| pool | id | tier kept | fame | salience | reason |
|---|---|---|---|---|---|
| Lifeline | `thomas-cochrane` | hard | — | 7.6 | no entry in fame_scores.json |
| Lifeline | `john-smith` | hard | — | 14.1 | no entry in fame_scores.json |
| Lifeline | `john-reed` | hard | — | 43.3 | no entry in fame_scores.json |
| Relic | `temple-poseidon` | easy | — | 47.3 | no entry in fame_scores.json |
| Relic | `st-stephens-vienna` | medium | — | 80.7 | no entry in fame_scores.json |
| Relic | `villa-of-mysteries` | hard | — | 39.3 | no entry in fame_scores.json |
| Face Value | `edgar-allan-poe` | medium | 97.0 | 87.0 | portrait medium unknown - image fame unjudgeable |
| Face Value | `andrew-jackson` | medium | 96.6 | 94.2 | portrait medium unknown - image fame unjudgeable |
| Face Value | `frederic-chopin` | hard | 94.2 | 84.3 | portrait medium unknown - image fame unjudgeable |
| Face Value | `john-quincy-adams` | medium | 94.1 | 90.7 | portrait medium unknown - image fame unjudgeable |
| Face Value | `william-henry-harrison` | hard | 93.5 | 83.4 | portrait medium unknown - image fame unjudgeable |
| Face Value | `mary-shelley` | medium | 92.6 | 76.5 | portrait medium unknown - image fame unjudgeable |
| Face Value | `zachary-taylor` | hard | 91.8 | 83.2 | portrait medium unknown - image fame unjudgeable |
| Face Value | `james-polk` | hard | 91.1 | 90.6 | portrait medium unknown - image fame unjudgeable |
| Face Value | `wellington` | hard | 89.8 | 99.6 | portrait medium unknown - image fame unjudgeable |
| Face Value | `ada-lovelace` | easy | 87.6 | 90.7 | portrait medium unknown - image fame unjudgeable |
| Face Value | `nikolai-gogol` | hard | 83.1 | 86.8 | portrait medium unknown - image fame unjudgeable |
| Face Value | `honore-de-balzac` | medium | 82.8 | 86.8 | portrait medium unknown - image fame unjudgeable |
| Face Value | `alexander-von-humboldt` | medium | 79.0 | 97.1 | portrait medium unknown - image fame unjudgeable |
| Face Value | `mary-anning` | medium | 66.6 | 73.3 | portrait medium unknown - image fame unjudgeable |
| Face Value | `mihrimah-sultan` | medium | — | 26.2 | no entry in fame_scores.json |

### B. Correct on the evidence, but blocked by the compiled manifest (299)

These items' labels disagree with the measurement, but changing them would push
at least one already-scheduled edition further from its declared recipe. They are
the price of not touching `data/editions.json`. Summary:

| pool | blocked move | count |
|---|---|---|
| Lifeline | easy → medium | 13 |
| Lifeline | hard → medium | 36 |
| Lifeline | medium → easy | 53 |
| Lifeline | medium → hard | 6 |
| Relic | easy → medium | 10 |
| Relic | hard → medium | 45 |
| Relic | medium → easy | 43 |
| Face Value | easy → medium | 19 |
| Face Value | hard → medium | 20 |
| Face Value | medium → easy | 39 |
| Face Value | medium → hard | 15 |

The 135 blocked promotions **into easy** are the ones that still cost headroom;
they are listed in full because a future recompile of the editions that block them
would free them:

| pool | id | current | fame | blocked by editions |
|---|---|---|---|---|
| Lifeline | `alexander` | medium | 99.4 | 2 |
| Lifeline | `mozart` | medium | 98.4 | 0 |
| Lifeline | `vangogh` | medium | 98.3 | 1, 61 |
| Lifeline | `judy-garland` | medium | 98.0 | 16 |
| Lifeline | `saddam-hussein` | medium | 97.9 | 5 |
| Lifeline | `osama-bin-laden` | medium | 97.8 | 3, 56 |
| Lifeline | `diana-princess-of-wales` | medium | 97.8 | 16, 45 |
| Lifeline | `gerald-ford` | medium | 97.7 | 4 |
| Lifeline | `marlon-brando` | medium | 97.4 | 12 |
| Lifeline | `elizabeth-taylor` | medium | 97.2 | 23, 55 |
| Lifeline | `curie` | medium | 97.1 | 1, 61 |
| Lifeline | `ulysses-s-grant` | medium | 97.0 | 11 |
| Lifeline | `darwin` | medium | 97.0 | 1 |
| Lifeline | `audrey-hepburn` | medium | 96.8 | 18, 55 |
| Lifeline | `joanofarc` | medium | 96.6 | 0, 60 |
| Lifeline | `andrew-jackson` | medium | 96.6 | 9 |
| Lifeline | `nikita-khrushchev` | medium | 96.0 | 5 |
| Lifeline | `akbar` | medium | 95.6 | 6 |
| Lifeline | `herbert-hoover` | medium | 95.6 | 11 |
| Lifeline | `saint-peter` | medium | 95.2 | 14 |
| Lifeline | `grover-cleveland` | medium | 95.2 | 19 |
| Lifeline | `constantine-the-great` | medium | 95.0 | 13 |
| Lifeline | `chiang-kai-shek` | medium | 95.0 | 54 |
| Lifeline | `william-howard-taft` | medium | 94.4 | 19 |
| Lifeline | `james-madison` | medium | 94.4 | 4 |
| Lifeline | `jim-morrison` | medium | 94.1 | 17 |
| Lifeline | `john-quincy-adams` | medium | 94.1 | 7 |
| Lifeline | `isaac-asimov` | medium | 94.0 | 10, 59 |
| Lifeline | `andrew-johnson` | medium | 93.9 | 21 |
| Lifeline | `boris-yeltsin` | medium | 93.9 | 10 |
| Lifeline | `annefrank` | medium | 93.7 | 2, 62 |
| Lifeline | `alexander-graham-bell` | medium | 93.3 | 10 |
| Lifeline | `charles-v-hre` | medium | 93.3 | 54 |
| Lifeline | `james-a-garfield` | medium | 93.2 | 19 |
| Lifeline | `maya-angelou` | medium | 93.0 | 20, 53 |
| Lifeline | `shinzo-abe` | medium | 92.9 | 9 |
| Lifeline | `james-buchanan` | medium | 92.8 | 22 |
| Lifeline | `hedy-lamarr` | medium | 92.5 | 31, 60 |
| Lifeline | `henry-vii` | medium | 92.5 | 27 |
| Lifeline | `cyrus-the-great` | medium | 92.3 | 18 |
| Lifeline | `t-s-eliot` | medium | 92.2 | 11, 60 |
| Lifeline | `nightingale` | medium | 92.1 | 2, 59 |
| Lifeline | `zachary-taylor` | medium | 91.8 | 22 |
| Lifeline | `claude-monet` | medium | 91.4 | 13 |
| Lifeline | `john-steinbeck` | medium | 91.3 | 17 |
| Lifeline | `james-k-polk` | medium | 91.1 | 22 |
| Lifeline | `adolf-eichmann` | medium | 90.8 | 25 |
| Lifeline | `mark-antony` | medium | 90.8 | 48 |
| Lifeline | `hernan-cortes` | medium | 90.7 | 5 |
| Lifeline | `yasser-arafat` | medium | 90.6 | 14 |
| Lifeline | `hadrian` | medium | 90.5 | 62 |
| Lifeline | `hugo-chavez` | medium | 90.2 | 3 |
| Lifeline | `catherine-of-aragon` | medium | 90.1 | 48 |
| Relic | `us-constitution` | medium | 99.2 | 34 |
| Relic | `rosetta-stone` | medium | 98.6 | 20, 49 |
| Relic | `berlin-wall` | medium | 98.6 | 34 |
| Relic | `world-trade-center` | medium | 98.3 | 46 |
| Relic | `great-pyramid-giza` | medium | 97.5 | 0, 28 |
| Relic | `angkor-wat` | medium | 97.5 | 2, 61 |
| Relic | `last-supper` | medium | 97.0 | 1, 60 |
| Relic | `little-boy` | medium | 96.9 | 64 |
| Relic | `windsor-castle` | medium | 96.3 | 9 |
| Relic | `carcassonne` | medium | 96.2 | 3 |
| Relic | `sagrada-familia` | medium | 96.1 | 6 |
| Relic | `hms-victory` | medium | 96.1 | 41 |
| Relic | `bayeux-tapestry` | medium | 96.0 | 3, 62 |
| Relic | `voyager-golden-record` | medium | 95.8 | 47 |
| Relic | `sistine-chapel` | medium | 95.6 | 47 |
| Relic | `uss-constitution` | medium | 95.6 | 48 |
| Relic | `mont-saint-michel` | medium | 95.4 | 6 |
| Relic | `pieta-michelangelo` | medium | 94.5 | 6, 35 |
| Relic | `book-of-kells` | medium | 94.3 | 11, 39 |
| Relic | `codex-sinaiticus` | medium | 94.0 | 24, 61 |
| Relic | `al-aqsa-mosque` | medium | 93.5 | 53 |
| Relic | `codex-gigas` | medium | 93.1 | 4, 38 |
| Relic | `hanging-gardens` | medium | 92.9 | 53 |
| Relic | `cologne-cathedral` | medium | 92.9 | 12 |
| Relic | `vasa-ship` | medium | 92.8 | 38 |
| Relic | `musee-dorsay` | medium | 92.6 | 54 |
| Relic | `borobudur` | medium | 92.2 | 11 |
| Relic | `bamiyan-buddhas` | medium | 92.0 | 54 |
| Relic | `maitreya-koryuji` | medium | 91.4 | 57 |
| Relic | `valley-of-kings` | medium | 91.2 | 55 |
| Relic | `chambord` | medium | 91.2 | 12 |
| Relic | `pamukkale` | medium | 91.1 | 1 |
| Relic | `cutty-sark` | medium | 91.1 | 56 |
| Relic | `school-of-athens` | medium | 90.9 | 20, 48 |
| Relic | `lewis-chessmen` | medium | 90.9 | 16, 45 |
| Relic | `qe2` | medium | 90.5 | 59 |
| Relic | `lascaux` | medium | 90.5 | 15 |
| Relic | `victoria-albert-museum` | medium | 90.5 | 55 |
| Relic | `bran-castle` | medium | 90.4 | 3, 63 |
| Relic | `blue-mosque` | medium | 90.4 | 11 |
| Relic | `cahokia` | medium | 90.2 | 57 |
| Relic | `girl-pearl-earring` | medium | 90.1 | 4, 46 |
| Relic | `sigiriya` | medium | 90.1 | 7 |
| Face Value | `pope-francis` | medium | 98.6 | 47 |
| Face Value | `karl-marx` | medium | 98.4 | 5 |
| Face Value | `nikola-tesla` | medium | 98.3 | 45 |
| Face Value | `robin-williams` | medium | 98.2 | 50 |
| Face Value | `lbj` | medium | 98.1 | 53 |
| Face Value | `george-vi` | medium | 98.0 | 55 |
| Face Value | `judy-garland` | medium | 98.0 | 51 |
| Face Value | `saddam-hussein` | medium | 97.9 | 61 |
| Face Value | `truman` | medium | 97.8 | 62 |
| Face Value | `gerald-ford` | medium | 97.7 | 64 |
| Face Value | `friedrich-nietzsche` | medium | 97.6 | 3 |
| Face Value | `johnny-cash` | medium | 97.6 | 53 |
| Face Value | `jawaharlal-nehru` | medium | 97.6 | 18 |
| Face Value | `thomas-edison` | medium | 97.5 | 46 |
| Face Value | `brando` | medium | 97.4 | 57 |
| Face Value | `marie-curie` | medium | 97.1 | 6, 38 |
| Face Value | `rabindranath-tagore` | medium | 97.0 | 21 |
| Face Value | `turing` | medium | 96.9 | 53 |
| Face Value | `stanley-kubrick` | medium | 96.8 | 54 |
| Face Value | `edward-vii` | medium | 96.7 | 57 |
| Face Value | `mark-twain` | medium | 96.4 | 0 |
| Face Value | `pope-benedict-xvi` | medium | 95.8 | 60 |
| Face Value | `ataturk` | medium | 95.7 | 12 |
| Face Value | `helen-keller` | medium | 95.7 | 34 |
| Face Value | `fyodor-dostoevsky` | medium | 95.3 | 3 |
| Face Value | `trotsky` | medium | 95.3 | 10 |
| Face Value | `selena` | medium | 95.0 | 55 |
| Face Value | `david-lynch` | medium | 93.9 | 60 |
| Face Value | `eleanor-roosevelt` | medium | 93.3 | 46 |
| Face Value | `harriet-tubman` | medium | 93.2 | 4 |
| Face Value | `richard-wagner` | medium | 93.1 | 22 |
| Face Value | `haile-selassie` | medium | 92.7 | 4 |
| Face Value | `ho-chi-minh` | medium | 92.6 | 4 |
| Face Value | `florence-nightingale` | medium | 92.1 | 2, 35 |
| Face Value | `richard-feynman` | medium | 92.1 | 64 |
| Face Value | `ayn-rand` | medium | 92.0 | 42 |
| Face Value | `hans-christian-andersen` | medium | 91.8 | 17 |
| Face Value | `claude-monet` | medium | 91.4 | 13 |
| Face Value | `anton-chekhov` | medium | 90.9 | 12 |

## Editions 24–28: the residual

Nine game-slots were already off-recipe before this pass, all in editions 24–28,
all in the same direction (too few easy rounds) — the visible symptom of the
defect. Re-labelling improved three of them and broke none:

| edition | date | game | recipe wants | before | after |
|---|---|---|---|---|---|
| №24 | 2026-07-23 | who | 2/2/1 | 0/4/1 | 1/2/2 |
| №24 | 2026-07-23 | what | 2/2/1 | 0/5/0 | 1/4/0 |
| №25 | 2026-07-24 | who | 1/3/1 | 0/4/1 | 1/2/2 |
| №25 | 2026-07-24 | what | 1/3/1 | 0/5/0 | 0/5/0 |
| №26 | 2026-07-25 | who | 1/2/2 | 0/3/2 | 0/3/2 |
| №26 | 2026-07-25 | what | 1/2/2 | 0/5/0 | 0/5/0 |
| №27 | 2026-07-26 | what | 0/2/3 | 0/5/0 | 0/4/1 |
| №28 | 2026-07-27 | who | 4/1/0 | 0/5/0 | 0/2/3 |
| №28 | 2026-07-27 | what | 4/1/0 | 0/5/0 | 1/4/0 |

The rest cannot be fixed by relabelling, because the items in those editions are
genuinely not easy. Edition 28 is a Monday asking for four easy Face Value rounds
and its five items are Elizabeth Cady Stanton, Schubert, Schiller, Verdi and Dian
Fossey — no measurement makes any of those a Monday face. **That is a content
selection problem in five specific editions, not a labelling one.** Editions 27
and 28 have not aired yet; now that the easy tier is properly stocked they could
be re-proposed and would compile clean. That needs `data/editions.json`, which is
outside this change's remit.

## Data-quality defects found in the fame pipeline

These are findings *about the inputs*, not changes. They are the reason several
obviously-famous items could not be re-tiered, and they are worth fixing at source.

### 1. Wrong-article resolutions that `title_health.json` reports as `ok`

`title_health.json` proves an article exists and is long enough. It does not prove
it is the right subject. Five confirmed mis-resolutions, each of which would have
driven a wrong label:

| pool | item | resolves to | consequence |
|---|---|---|---|
| Relic | `sunflowers-van-gogh` | **Helianthus** — the flower genus | fame 93.1 is the *plant's*; would have been promoted to easy |
| Relic | `olympia-stadium` | **Detroit Olympia** — a US ice-hockey arena | fame 70.8 is meaningless here |
| Relic | `golden-pavilion` | **The Temple of the Golden Pavilion** — Mishima's *novel* | fame 80.0 is the book's, not Kinkaku-ji's |
| Lifeline | `abd-el-kader` | **Abdul Qadir** — 15 languages, 57k views | the Algerian emir is not this article |
| Relic | `great-buddha-kamakura` | **Kōtoku-in** — the temple, not the statue | borderline; left alone to be safe |

All five were excluded from re-tiering. A name↔title token check across the whole
corpus flagged only these, so the resolution layer is broadly sound — but `ok` should
not be read as "verified".

### 2. Broken monthly pageview series (page moves)

`fame` is 50% `pv_pct`, a percentile of `pv_stat` — a trimmed monthly median. When
an article has been **renamed** inside the 5-year window, the new title's monthly
series is near-zero before the move, the trimmed median lands in that dead zone, and
fame collapses. Eleven pool items are affected; the tell is `pv_stat` falling below
30% of the monthly average implied by the 5-year total:

| pool | item | fame | salience | pv_stat / month | implied by 5-yr total |
|---|---|---|---|---|---|
| Lifeline | `william-adams` | 25.7 | 37.6 | 2 | 7479 |
| Face Value | `al-khwarizmi` | 46.2 | 84.3 | 1037 | 13130 |
| Lifeline | `kim-jong-il` | 47.2 | 80.2 | 375 | 47473 |
| Relic | `temple-of-hatshepsut` | 48.9 | 91.4 | 74 | 3900 |
| Lifeline | `kim-il-sung` | 50.3 | 92.3 | 594 | 47335 |
| Relic | `nazca-lines` | 54.7 | 61.1 | 557 | 9937 |
| Face Value | `nicholas-ii` | 57.9 | 89.7 | 4343 | 36091 |
| Lifeline | `tsar-nicholas-ii` | 57.9 | 89.7 | 4343 | 36091 |
| Face Value | `kaiser-wilhelm-ii` | 67.3 | 98.0 | 8974 | 43966 |
| Lifeline | `wilhelm-ii` | 67.3 | 98.0 | 8974 | 43966 |
| Face Value | `robert-oppenheimer` | 94.4 | 87.8 | 231048 | 792296 |

Nicholas II reads fame 57.9 on 2.2 million views; Kim Il-sung 50.3 on 2.8 million.
Both are wrong by a wide margin. None of these items was demoted. **Fixing this in
`build_scores.py` — by falling back to the 5-year mean when the trimmed median
disagrees with it by more than ~3× — would unlock a further round of correct
re-tiering.**

## The salience blind spot (explorers and travellers)

`salience.json` weights WikiProject importance at 0.42, and the WikiProject system
barely rates exploration — the salience build itself documents that Amundsen scored
34 points below his fame until the Arctic/Antarctica projects were added. The result
is a category-shaped hole: Wilfred Thesiger 1.2, Freya Stark 4.9, John Hanning Speke
4.7, Percy Fawcett 6.4. Those are not statements about audience recognition.

**Salience was therefore never used as a scoring axis in this pass** — only as a
one-way veto (`low_confidence`, and "salience far above fame" as a demotion block).
No item anywhere was demoted because its salience was low. The 36 explorer,
traveller, navigator and conquistador figures in the Lifeline pool, for the record:

| figure | occupation | fame | salience | old → new | moved? |
|---|---|---|---|---|---|
| Wilfred Thesiger | Explorer who twice crossed the Empty Quarter | 27.2 | 1.2 | hard → hard | no |
| John Hanning Speke | Explorer who claimed the Nile's source and d | 32.0 | 4.7 | hard → hard | no |
| Freya Stark | Travel writer who mapped remote corners of A | 26.9 | 4.9 | hard → hard | no |
| Percy Fawcett | Explorer who vanished hunting a lost city in | 58.4 | 6.4 | hard → hard | no |
| Francisco Vázquez de Coronado | Conquistador who crossed the southwest chasi | 47.7 | 23.9 | medium → hard | **yes** |
| Amerigo Vespucci | Explorer for whom America is named | 81.6 | 32.8 | medium → medium | no |
| William Adams | Navigator and samurai retainer | 25.7 | 37.6 | hard → hard | no |
| Vasco Núñez de Balboa | Conquistador who first saw the Pacific from  | 54.4 | 40.0 | medium → hard | **yes** |
| Bartolomeu Dias | Portuguese navigator who opened the sea road | 61.5 | 40.3 | easy → easy | no |
| Piri Reis | Ottoman admiral and cartographer | 48.4 | 41.3 | hard → hard | no |
| Samuel Baker | Victorian explorer who named Lake Albert | 24.6 | 46.5 | hard → hard | no |
| Mary Kingsley | Victorian woman who explored West Africa in  | 31.4 | 53.9 | hard → hard | no |
| Francisco Pizarro | Conquistador who destroyed the Inca Empire a | 77.3 | 58.8 | easy → easy | no |
| Matthew Henson | African American explorer at the front of th | 46.0 | 63.0 | hard → hard | no |
| Henry the Navigator | Portuguese prince and patron of exploration | 59.9 | 67.8 | medium → hard | **yes** |
| Jack London | Novelist and adventure writer | 87.5 | 69.6 | medium → medium | no |
| Leif Erikson | Norse explorer who reached America five cent | 83.2 | 73.5 | medium → medium | no |
| Francis Drake | English sea captain who circumnavigated the  | 89.8 | 77.8 | easy → easy | no |
| Ibn Battuta | Moroccan explorer and scholar | 87.0 | 78.0 | easy → easy | no |
| Fridtjof Nansen | Polar scientist who later ran relief for ref | 65.9 | 80.6 | hard → hard | no |
| Willem Barentsz | Dutch navigator and explorer | 47.7 | 81.8 | hard → hard | no |
| Robert Louis Stevenson | Novelist and travel writer | 89.2 | 83.1 | medium → medium | no |
| John Franklin | Naval officer whose Arctic expedition vanish | 58.3 | 83.9 | hard → hard | no |
| David Livingstone | Missionary-explorer of Africa's rivers and l | 79.8 | 86.6 | medium → medium | no |
| Richard Francis Burton | Explorer and linguist who translated forbidd | 64.9 | 86.6 | hard → hard | no |
| Zheng He | Eunuch and explorer | 82.2 | 87.4 | medium → medium | no |
| Yuri Gagarin | First human to travel into space | 90.6 | 88.9 | easy → easy | no |
| Hernán Cortés | Conquistador who conquered the Aztec Empire | 90.7 | 89.5 | medium → medium | no |
| Edmund Hillary | Mountaineer, first to summit Everest | 88.1 | 92.6 | hard → hard | no |
| Ferdinand Magellan | Led the first circumnavigation of the globe | 92.3 | 93.5 | easy → easy | no |
| Robert Falcon Scott | Royal Navy officer and polar explorer | 73.1 | 93.6 | easy → easy | no |
| Marco Polo | Venetian merchant and traveler | 93.8 | 95.0 | easy → easy | no |
| Christopher Columbus | Genoese explorer who crossed the Atlantic fo | 98.2 | 95.1 | easy → easy | no |
| Roald Amundsen | Polar explorer, first to reach the South Pol | 84.5 | 95.4 | easy → easy | no |
| Ernest Shackleton | Antarctic explorer who lost his ship and bro | 82.2 | 97.2 | medium → medium | no |
| James Cook | Royal Navy explorer who charted the Pacific | 93.9 | 98.8 | hard → hard | no |

**Only three of the 36 moved, all on fame, none on salience:**

| figure | fame | salience | move | is this the blind spot? |
|---|---|---|---|---|
| Francisco Vázquez de Coronado | 47.7 | 23.9 | medium → hard | no — both signals agree he is obscure |
| Vasco Núñez de Balboa | 54.4 | 40.0 | medium → hard | no — both signals agree |
| Henry the Navigator | 59.9 | 67.8 | medium → hard | **worth a second opinion** — salience 8 points above fame, and he is the patron of the whole Age of Discovery |

The four lowest-salience figures in the pool — Thesiger (1.2), Stark (4.9), Speke
(4.7), Fawcett (6.4) — were all already labelled `hard` and were left exactly
where they were; the rule never consulted their salience. Two more explorers were
*candidates* for demotion on fame and did not move: Pizarro (fame 77.3, easy) was
blocked by the manifest, and Bartolomeu Dias (61.5, easy) by the two-tier cap.
Both would be worth a human look before any future pass frees them.

*(Oppenheimer appears in that table for a different reason — the 2023 film spike,
not a page move. His fame of 94.4 is fine and he was not demoted, so the guard cost
nothing there.)*

## Same subject, different tier in two pools

228 subjects appear in more than one pool. 133 already carried different labels
before this pass; 137 do after — 26 newly split, 22 newly reconciled. **Divergence
is not automatically a bug**: `QUALITY_RUBRIC.md` scores Face Value on the image and
Lifeline on name recognition plus journey, so a recognisable face is genuinely not
the same round as a recognisable birth→death arc. 75 of the 137 splits are explained
by exactly that — a stylised-only likeness, a flat journey, or both.

Julius Caesar is the model case and is now **correct**: `medium` in Face Value (his
face is a marble bust) and `easy` in Lifeline (everyone knows the name). Same for
Cleopatra, Jesus and Genghis Khan.

The two the review flagged both turn out to be **fame-data casualties, not
judgement calls**, and both were left untouched in both pools:

| subject | Face Value | Lifeline | why it was left |
|---|---|---|---|
| Nicholas II | medium | easy | fame reads 57.9 on 2.2M views — broken pageview series (page move) |
| Roxelana / Hürrem Sultan | medium | easy | fame 50.4, salience 81.2 — a 31-point divergence; demotion blocked |

Both should be re-examined once `build_scores.py` handles renamed articles. On the
evidence available today the Lifeline `easy` looks generous for both and the Face
Value `medium` looks about right, but I am not willing to move either on a number I
can show is wrong.

Of the 26 newly-split subjects, 11 are the intended effect of the stylised-portrait
corrector (Dante, Louis XIV, Hatshepsut, Justinian, Montezuma II, Rubens, Tokugawa,
Catherine the Great, Timur, Hannibal, plus Cecil Rhodes on fame). The other 15 are
an artefact of the manifest constraint — the same person's promotion was legal in
one pool and blocked in the other (Khrushchev, Hoover, Cleveland, Chiang Kai-shek,
Taft, Asimov, Yeltsin, Abe, T. S. Eliot, Steinbeck, Grant, Darwin, Haile Selassie,
Ho Chi Minh, José Martí). Those will converge naturally as editions age out; none
of them is wrong, just unfinished.

## Needs a human call

1. **The 77 two-tier disagreements.** The biggest are household names the author
   filed as `hard`: Magna Carta (fame 99.5), Jimmy Carter (99.4), George H. W. Bush
   (98.7), Stephen Hawking (97.9), Tolkien (97.8), Sigmund Freud (97.7). Some of
   these are right as hard — Magna Carta photographs as a sheet of dense Latin, and
   the game is about the *image*. Others look like plain mislabels. One pass of
   human eyes over that table would probably free another 20–30 easy items.
2. **Editions 27 and 28 have not aired and still cannot meet their recipe.** They
   should be re-proposed against the corrected pools. That is a `data/editions.json`
   change, outside this remit.
3. **Relic easy has the least slack** (63 eligible against a floor of 56). It clears,
   but it is the pool to feed first.
4. **The already-easy worst-offender crops** — Al Capone (risk 0.82) and the others
   `SUITABILITY.md` lists — keep their easy labels and need a re-crop, not a relabel.
5. **Relaxing the manifest constraint on aired history.** Treating editions 0–19
   (aired, and past the trailing-7-day archive, so unreachable by any player) as
   unconstrained would apply 296 moves instead of 167 and lift Relic easy from 116
   to 128 items / 63 to 75 eligible. The cost is that 54 aired edition-slots would
   no longer match the recipe they were compiled under, and Relic hard would fall
   from 91 to 73. I did **not** do this — the current change clears every floor
   without it — but the option is real if Relic easy ever gets tight.

## Verification

```
python3 tools/validate_reveal.py         0 errors  (187 warnings, unchanged)
python3 tools/compile_editions.py verify 0 errors  (7 warnings, unchanged)
python3 tests/run_all.py --fast          reveal data PASS
                                         board data PASS
                                         image rights PASS
                                         manifest verify PASS
                                         schedule repetition PASS
```

167 lines changed across the three files, all of them a `difficulty` value. Byte
formatting preserved: 1-space indent, `ensure_ascii=False`, and `reveal-who.json`
still ends without a trailing newline while the other two keep theirs.

---

# Addendum — re-run over the corrected fame index (25 Jul 2026, later the same day)

The pass above rested on numbers that were wrong for 34 of the 1,331 pool items:
8 sat on the wrong Wikipedia subject and 26 sat on 23 renamed articles whose
pageview series had split in two. Both root causes were fixed in
`tools/fame/build_salience.py` (`TITLE_OVERRIDES`) and `tools/fame/build_scores.py`
(`RENAMED_FROM` + month-by-month series merging), but `fame_scores.json` itself had
not been rebuilt. This addendum rebuilds it and re-runs the identical rule.
**One label changed.**

## 1. The regeneration

```
cd tools/fame && python3 build_scores.py <out.json> \
    metrics_wave1.jsonl metrics_wave2.jsonl metrics_wave3.jsonl \
    ../out/wrongmap/metrics_fix.jsonl
```

8,096 scored records, 0 errors. The result is **byte-identical** to the corrected
index the previous agent left at `tools/out/wrongmap/fame_scores_fixed.json` — no
discrepancy of any kind.

- **The 26 renamed items all carry merged series.** All 23 renamed titles that back
  a pool item found their former title in the cache (`pv_merged_from` non-empty on
  every one; zero cache misses). Nicholas II 57.9 → **94.9**, Wilhelm II 67.3 →
  **94.3**, Kim Il-sung 50.2 → **93.7**, Kim Jong-il 47.2 → **91.8**, the mortuary
  temple of Hatshepsut 49.0 → **82.1**, the Nazca lines 54.7 → **86.6**,
  al-Khwarizmi 46.2 → **79.2**.
- **The 8 wrong-subject items now score their real subject.** Sunflowers → *Sunflowers
  (Van Gogh series)* 86.2 (not Helianthus's 93.1); Michelangelo's David → *David
  (Michelangelo)* 95.0 (not the biblical king's); the self-portrait → *Vincent van
  Gogh* 98.3 (not 28.5); the Golden Pavilion → *Kinkaku-ji* 80.0; the Great Buddha →
  *Kōtoku-in* 70.2; Olympia → *Stadium at Olympia* 74.9; Abd el-Kader → *Emir
  Abdelkader* 51.9. The last two needed metrics that did not exist in any wave file
  and came from `tools/out/wrongmap/metrics_fix.jsonl`.
- **Unaffected titles are unchanged.** Against the same index rebuilt with the rename
  merge switched off, no title outside `RENAMED_FROM` moves more than **0.23** points
  and the median move is **0.04** — pure percentile-rank churn from two titles
  entering the index. 0 titles move by more than half a point.

⚠️ `metrics_fix.jsonl` currently lives under `tools/out/`, which is gitignored. Until
it moves into `tools/fame/` (as `metrics_wave4.jsonl`, alongside the other wave
files), the index is **not reproducible from a fresh clone** — `abd-el-kader` and
`olympia-stadium` would silently fall back to "no fame entry". That is a one-line
housekeeping job for whoever next touches the fame tooling.

## 2. Method — the rule was re-implemented, not re-read

The rule in §"The rule" above was re-implemented from scratch and **validated against
this report before being trusted**: run against the author's labels and a rebuild of
the pre-fix index, it produces **466 candidate moves** (the same 466), reproduces
**167 of 167** applied moves with the identical target tier, and reproduces **119 of
120** of the deliberately-left-alone list. The single divergence is `van-gogh-self`,
and it is the expected one: the wrong-subject fix has already changed which article
that item points at.

Two clarifications the re-implementation had to settle, both fixed by matching this
report's own arithmetic:

- The promotion gate (worst-offender crop, dull journey) **caps a promotion at
  `medium`; it does not abolish it.** Only this reading yields exactly 466 candidates.
- The ±5 dead band protects the **standing** label — the author's, or the one this
  pass set. Without that, `walt-whitman` (promoted to easy at 90.1) would flip
  straight back to medium on a rank wobble to 89.98. A label may not oscillate on
  hundredths of a point.

## 3. What the corrected numbers actually changed

Nine verdicts changed. Only one survived every guard.

| item | old → new fame | rule's verdict | outcome |
|---|---|---|---|
| `who/baybars` | 45.6 → **56.9** | medium → **hard** | **APPLIED** |
| `who/nicholas-ii` | 57.9 → **94.9** | medium → easy | blocked by the manifest (edition 7) |
| `who/kaiser-wilhelm-ii` | 67.3 → **94.3** | medium → easy | blocked by the manifest (edition 19) |
| `map/mehmed-ii` | 88.2 → **91.7** | medium → easy | blocked by the manifest (edition 27) |
| `who/al-khwarizmi` | 46.2 → **79.2** | medium → hard | blocked by the manifest (edition 11) |
| `who/van-gogh-self` | 28.5 → **98.3** | easy → medium | blocked by the manifest (edition 7) |
| `map/scipio-africanus` | 75.01 → 74.95 | candidate withdrawn | no action |
| `map/william-wilberforce` | 70.04 → 69.98 | medium → hard | **declined — measurement noise** |
| `what/pergamon` | 90.02 → 89.99 | hard → medium | **declined — measurement noise** |

### The one change applied

**`who/baybars`: medium → hard.** The 25 Jul pass wanted to demote him and was
stopped by its own guard — salience 77.2 stood 31.6 points above a fame of 45.6, and
that gap is the signature of a broken measurement, not of an obscure subject. The
measurement is now sound (the *Baibars* → *Baybars* series is reassembled) and it
still says hard: fame 56.9, comfortably below the 75 threshold and nowhere near the
dead band, with a stylised likeness on top (no contemporary portrait of him exists).
The guard did its job — it deferred the call until the number could be trusted. He
appears in no compiled edition, so the manifest constraint is satisfied trivially.

### Declined: two band crossings that are pure noise

`william-wilberforce` (70.04 → 69.98) and `pergamon` (90.02 → 89.99) cross a
threshold by hundredths of a point. **Neither item's own data changed today** — not
one pageview, language or inbound link. Their fame moved only because two titles
entered the index and shifted every percentile rank by a rounding error. Acting on
that would contradict the reason the dead band exists, and it would be indefensible
to a reader who asked what had changed about Pergamon. Both are listed here so the
decision is on the record; if Daniel wants Pergamon at medium (salience 96.0 is the
highest in Relic's hard tier), it is a free move — it is in no scheduled edition.

## 4. The nine "warranted" promotions, checked one at a time

The handover listed 13 moves as warranted. Verified against the rule, **eight of them
fail a guard that exists for a good reason** and one is applied above:

| proposed | verdict | why |
|---|---|---|
| `map/kim-jong-il` hard → easy | **declined** | two tiers in one step (§5). Nothing moves; it joins the human-call list. |
| `map/wilhelm-ii` hard → easy | **declined** | same — two tiers. |
| `map/kim-il-sung` medium → easy | **declined** | born in Pyongyang, died in Pyongyang: an **8.7 km** Lifeline journey. `lifeline_journey.dull` blocks promotion to easy (§4) — a one-pin round gives the player less than his fame promises. |
| `map/otto-the-great` → hard | **declined** | fame 71.6 sits **inside the ±5 dead band** at 75 (§2). The author's medium stands. |
| `what/olympia-stadium` → hard | **declined** | fame 74.86 — 0.14 of a point inside the dead band. Independently, its new title has no WikiProject coverage, so salience is `low_confidence` (§6). Two reasons not to touch it. |
| `who/empress-theodora` → hard | **declined** | correct on the evidence, but it was already a candidate *before* today's corrections and is blocked by edition 15, exactly as the 299 others are. Nothing about it changed. |
| `what/blue-mosque` medium → easy | **declined** | likewise — already a candidate at fame 90.4, blocked by edition 11. |
| `map/frederick-barbarossa` hard → medium | **declined** | already a candidate at fame 75.6, blocked by edition 12. |
| `what/ellora-kailasa` hard → medium | **declined** | already a candidate at fame 84.0, blocked by editions 1 and 62. |
| `who/baybars` → hard | **applied** | see above. |

The last four are worth being precise about: they are *not* consequences of today's
data fix. Their corrected fame is higher, but their band was the same before and
after; they sat in the 299 "correct but blocked by the manifest" bucket yesterday and
they sit there today.

**A whole-pool sweep confirms it.** Re-derived over the corrected index the rule now
proposes 306 moves against the current labels (299 → 306). Tested one at a time
against every compiled edition, **exactly two are admissible**: `who/baybars` and
`what/pergamon`. Every other candidate sits in at least one edition that currently
matches its recipe **exactly**, so any relabel takes that slot from distance 0 to
distance 2. The 25 Jul constraint-repair search left nothing on the table.

**No edition was touched.** Five of the blocked moves are blocked only by aired
legacy editions (1, 7, 11, 12, 15, 19 — all past the trailing-7-day archive and
unreachable by any player), and one by edition 27, which airs tomorrow and was
re-proposed only hours ago. Rewriting an aired issue to unlock a label is a worse
trade than leaving the label; re-opening tomorrow's issue for a Lifeline promotion
into a tier that already has 158 eligible items buys nothing.

## 5. The dictator question — my answer

Four of the biggest corrections are 20th-century dictators, and on measured fame
Kim Il-sung (93.7), Kim Jong-il (91.8), Wilhelm II (94.3) and Nicholas II (94.9) now
argue for easy — that is, for Monday.

**On the measurement I think fame is right and the worry is misplaced; on the
composition I think the worry is real and the difficulty label is the wrong lever.**

The tier answers one question: *will a player recognise this?* Nicholas II at
`medium` was never a judgement about tone — it was an artifact of a page move in
February 2024 splitting his pageviews in two. The last Tsar is not a Tuesday face;
2.2 million readers say so. Refusing the correction would mean deliberately keeping a
number I can prove is wrong because I do not like where it points, which is how the
easy tier got starved in the first place.

But an easy Monday assembled from Kim Il-sung, Gaddafi and Pinochet is a different
product from one assembled from Sinatra and Senna, and that is a real risk **already
present**: the Face Value easy pool of 145 currently contains Hitler, Stalin, Mao,
Mussolini, Lenin, Pinochet, Idi Amin, Gaddafi, Khomeini, bin Laden, Escobar, Che and
the Shah — about **one item in ten**. Four easy faces drawn from a 92-item eligible
easy pool will produce a two-dictator Monday reasonably often, by luck alone.

The lever for that is the proposer, not the labels. `tools/editions.config.json`
already caps `max_occupation_per_round` at 1 and `max_same_era` at 3; what it lacks
is a tone cap. **My recommendation to Daniel: add a cap of at most one authoritarian
ruler / atrocity subject per issue (and never two in one game's round), Mon–Wed
especially.** That fixes the launch review's complaint — over-representation of
rulers, dark payoffs stacking — without lying about who is famous, and it is exactly
the mechanism that already fixed editions 27 and 28 by swapping in Sinatra, Harrison,
Senna and Camus. Note the CLAUDE.md rule concerns *living* politicians; none of these
figures is living, so nothing here breaches it.

As it happens the rule reached the same place on its own today: the two-tier cap stops
both Kims and Wilhelm II from reaching easy, the dull-journey gate stops Kim Il-sung,
and the manifest stops Nicholas II and Kaiser Wilhelm. **No dictator moved into a
Monday slot.** But that is luck, and it will not hold at the next recompile — which is
why the composition cap is worth having before, not after.

## 6. Counts, headroom, verification

| pool | easy | medium | hard | | eligible easy | medium | hard |
|---|---|---|---|---|---|---|---|
| Face Value before | 145 | 159 | 122 | | 92 | 108 | 91 |
| Face Value **after** | 145 | **158** | **123** | | **92** | **107** | **92** |
| Relic (unchanged) | 116 | 157 | 91 | | 63 | 106 | 60 |
| Lifeline (unchanged) | 211 | 194 | 136 | | 158 | 143 | 105 |

`eligible` = not scheduled in editions 38–64, the same window as the table above.
**The easy-tier headroom established by the 25 Jul pass is intact**: Face Value easy
92 eligible against a floor of 56, Relic easy 63 against 56. The only movement is one
Face Value item from medium to hard, and Face Value hard (123, floor 32) has ample
room.

```
python3 tools/validate_reveal.py          0 errors  (188 warnings)
python3 tools/validate_schedule.py        0 gating errors  (124 historical-only, unchanged)
python3 tools/compile_editions.py verify  0 errors  (7 warnings, unchanged)
python3 tests/run_all.py --fast           reveal data PASS / board data PASS /
                                          image rights PASS / manifest verify PASS /
                                          schedule repetition PASS
```

Every compiled edition still satisfies its difficulty recipe to exactly the same
degree as before: total distance across all 195 edition-slots is **20 before and 20
after**, and no individual slot got worse.

The 188th `validate_reveal` warning (up from 187) is not from this change: it is the
new title-health guard reporting that `olmec-colossal-head` has no Wikidata item
behind its article, so the subject check cannot run on it. That is an absence of
evidence, not a defect, and it was treated as such — the item keeps the label the
25 Jul pass gave it.

One file changed: `data/reveal-who.json`, one `difficulty` value. Byte formatting
preserved (1-space indent, `ensure_ascii=False`, still no trailing newline).

## 7. Needs Daniel's call

1. **Move `metrics_fix.jsonl` into `tools/fame/`** so the fame index rebuilds from a
   fresh clone. Small, but it is a reproducibility hole today.
2. **A tone cap in the proposer** (§5). This is the one I would actually act on.
3. **Five correct labels are hostage to aired history** — Nicholas II and Kaiser
   Wilhelm II to easy, al-Khwarizmi to hard, the Van Gogh self-portrait to medium,
   Mehmed II to easy. All are blocked by editions nobody can reach any more. The
   report's option 5 above (treating editions 0–19 as unconstrained) would free them
   and roughly 130 others. Not needed while every floor clears — worth taking the day
   Relic easy gets tight.
4. **Van Gogh's self-portrait is now formally a `medium` face** under the stylised-
   likeness corrector, alongside Louis XIV and Dante. It is arguably the most
   recognisable painted face alive, and the corrector may simply be wrong about it.
   Blocked by the manifest either way, so nothing turns on it today.
