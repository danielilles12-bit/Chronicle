# History-lover salience

**What this is.** A second opinion about every person and object in the
Dead Famous pools, answering a different question from the existing fame
score.

- `fame` (in `fame_scores.json`, built by `build_scores.py`) answers:
  **how many people look this up?** It is 0.50 pageviews + 0.15 language
  count + 0.10 inbound links + 0.25 cross-language consensus.
- `salience` (in `salience.json`, built by `build_salience.py`) answers:
  **how well would someone who likes history know this?**

Neither replaces the other. Nothing in this work changes `fame`, touches
`data/`, or wires salience into selection. It is a recommendation.

Run it with `python3 build_salience.py` (Python 3.9 stdlib only, no
dependencies). It took ~80 seconds and ~250 API calls on first run; reruns
are free from the cache in `raw/`.

---

## Why a second score was needed

The stated audience bar is "Rest Is History listeners". That audience
recognises Belisarius, Baybars, Basil II and Brunel far better than raw
pageview counts imply, and cares much less than the general public about
Robin Williams or Grace Kelly. A score built mostly from pageviews will
therefore rank a *good* hard-day figure below a *bad* one, systematically.

The launch review saw the same defect from the player's side: hard days
felt like "academic syllabus knowledge rather than rewarding recognition".

The measured version of that claim: among the 442 scheduled rounds in the
30-day launch window, the lowest-fame items after Mihrimah Sultan are
Joseph Lister, Richard Francis Burton, Lise Meitner, Alexander Suvorov,
Emmy Noether, Themistocles, Mary Anning and José de San Martín. Fame puts
them at the bottom of the schedule. Salience puts every one of them in the
top third. Fame is not measuring the thing the hard tier needs.

---

## The five signals

### 1. `history_importance` — WikiProject importance ratings (weight 0.42)

The strongest instrument, as expected. English Wikipedia's `PageAssessments`
API returns, per article, every WikiProject that claims it plus a class and
an importance rating (Top / High / Mid / Low). These are domain editors
judging historical significance directly, with no traffic component at all.

Two things are computed from it:

- **Peak** — the best rating, weighted by how history-flavoured the project
  is. Three buckets: `core` (History, Middle Ages, Classical Greece and
  Rome, Crusades, Ancient Egypt, the royalty/military/politics Biography
  work groups…) at weight 1.0; `period` (national and regional projects)
  at 0.62; `weak` (Philosophy, Physics, Civil engineering, Visual arts…)
  at 0.40. A second opinion is averaged in at 26% weight, but only if it
  is itself Mid or better.
- **Breadth** — how many history projects claim the subject at Mid or
  better, saturating. This turned out to matter as much as the peak.
  Simon de Montfort is only "Mid" anywhere, but he is Mid in *nine* history
  projects at once. That is what "woven through the historical record"
  looks like. Kim Kardashian is in none.

Coverage is 97% of people and 91% of structures.

**Curation was done empirically, not from memory.** `--probe-projects`
enumerates every project name that actually appears across the universe;
the bucket lists were built from that output. Three findings only visible
that way:

- WikiProject **Military history deliberately abolished importance
  ratings**, so it contributes nothing. Military figures are reached
  instead through `Biography/military biography work group`.
- WikiProject **Biography's top level carries no importance value at all**
  — it delegates entirely to work groups, whose names are inconsistent
  (`military biography work group` vs `WikiProject Royalty and Nobility`).
  Guessing these names silently zeroes most soldiers and monarchs.
- **Arctic and Antarctica** look like geography projects but are the only
  home that rates polar explorers. Omitting them buried the entire heroic
  age — Amundsen scored 34 points below his fame until they were added.

### 2. `vital` — Wikipedia vital-article level (weight 0.14)

Wikipedia's own curated hierarchy of what an encyclopaedia must cover:
level 1 (3 articles) through level 5 (~50,000). Harvested by enumerating
the level-1..5 category members for History, People, Arts, Philosophy and
religion, and four other topics. 3,341 of our 6,444 titles are vital at
some level.

Real corroboration, but it drifts toward "important" rather than "beloved",
which is why it is a supporting weight rather than a driver.

### 3. `record_density` — inbound links vs pageviews (weight 0.13)

The free signal, computed entirely from data already collected. High
inbound-link count with modest pageviews is the signature of a figure woven
through the record but rarely looked up casually. Computed as the residual
of log(inlinks) regressed on log(pageviews), within class, then percentile
ranked.

**It works, but weakly** — correlation with fame is only 0.22, so it is
genuinely independent, but it is noisy. Navigation templates, year articles
and "list of" membership inflate inlinks for whole categories of subject
(every monarch is linked from every regnal-year article). Kept at a modest
weight because it is free and honest; not trusted on its own.

### 4. `article_depth` — article length vs pageviews (weight 0.09)

Same residual trick against article byte length: how much have people who
care bothered to write, relative to how many people visit? Belisarius has a
107 KB article on modest traffic.

Correlation with `record_density` is only 0.36, so the two are measuring
somewhat different things and both were kept — but this is the weakest
signal in the blend and the first one to drop if the model is ever
simplified.

### 5. Audience corpora — bounded bonus (+7 / +12 / +15 for 1 / 2 / 3 hits)

Public lists enumerating what this exact audience finds interesting.

- **BBC Radio 4 *In Our Time*** — 1,126 subjects parsed from
  "List of In Our Time programmes". Only the episode-title column is used;
  the contributors column is full of living historians and counting it
  would have been actively wrong.
- **BBC Radio 4 *Great Lives*** — 625 nominated subjects, one person per
  episode. This is the person-dense complement, because In Our Time is
  overwhelmingly about events, concepts and works. Same guard: the guest
  and presenter columns are excluded.
- **National "greatest countryman" polls** — 100 Greatest Britons and 19
  international spin-offs (Unsere Besten, De Grootste Nederlander,
  Le Plus Grand Français, El Gen Argentino…), reached via the
  "Greatest Britons spin-offs" hub. Mass-audience votes on historical
  standing, and the only corpus here that is not Anglocentric. Credit is
  restricted to person-class titles, because poll articles also link to
  broadcasters and countries.

736 of 6,444 titles hit at least one. Deliberately a **bounded bonus, not a
driver**: coverage is thin, so absence must never condemn a subject.

### 6. `general_fame_anchor` (weight 0.22)

A deliberate, modest amount of general fame is kept in the blend. A subject
with a genuinely zero public footprint is academic syllabus knowledge —
which is the exact failure the launch review named. Salience should reward
enthusiasm, not reward obscurity for its own sake.

Resulting correlation between fame and salience is **0.74**: strongly
related, as it must be (famous historical figures really are famous), but
with a quarter of the variance independent.

### Discarded

- **The Rest Is History episode catalogue.** The Wikipedia article is 6 KB
  and contains no episode list. Not machine-readable from any free source.
- **Wolfson History Prize / bestseller / Osprey / Great Courses catalogues.**
  No structured, freely accessible listing found; scraping publisher sites
  would add dependencies and fragility for a signal the three corpora above
  already approximate.
- **Revision counts and distinct-editor counts.** Would need a per-article
  API call for 6,444 articles and is heavily distorted by edit-warring on
  contested subjects.

---

## Evidence that the signal is real

### Divergence, both directions (the headline test)

Where salience and fame disagree most, restricted to shipped-pool items.

**High salience, low fame** — reads like a history-podcast running order:

> Temple of Hatshepsut, Al-Khwarizmi, Marquis de Lafayette, Willem Barentsz,
> Franz Joseph I, Sanchi Stupa, Tsar Nicholas II, Baybars, Kaiser Wilhelm II,
> Hürrem Sultan, José de San Martín, Louis Riel, Otto the Great,
> Christine de Pizan, John Franklin, Demosthenes, Itō Hirobumi,
> Godfrey of Bouillon, Olmec Colossal Head, Mary Kingsley, Yamagata Aritomo,
> Menelik II, Samuel Baker, Peter Abelard, Richard Francis Burton,
> Frederick Barbarossa, Arthur Evans, Robert Falcon Scott, Basil II,
> Alexander Suvorov

**High fame, low salience** — reads like general celebrity and tourism:

> Blackbeard, Robin Williams, Percy Fawcett, Harper Lee, Park Güell,
> Quba Mosque, Amerigo Vespucci, The Thinker, Erich Maria Remarque,
> Anne of Cleves, Sally Ride, Meteora, Pablo Escobar, Boudhanath,
> Stari Most, Gustave Courbet, Alexei Navalny, Billy the Kid, Grace Kelly,
> Charles Bridge, Bruce Lee, Rialto Bridge, Kösem Sultan,
> Lorenzo de' Medici, Wat Arun, F. Scott Fitzgerald, Jim Morrison,
> Guy Fawkes, Elizabeth Taylor, Tupac Shakur

The object split is the cleanest result in the whole exercise. High
salience: Temple of Hatshepsut, Sanchi Stupa, Olmec Colossal Head,
Staffordshire Hoard, Gedi Ruins, Kerma Deffufa, Tara Brooch, Bust of
Nefertiti, Oseberg Ship, Lindisfarne Gospels, Gundestrup Cauldron — a
museum-and-archaeology list. Low salience: Park Güell, Quba Mosque,
Meteora, Boudhanath, Stari Most, Charles Bridge, Rialto Bridge, Wat Arun,
Hawa Mahal, Predjama Castle — a **tourist-postcard list**. Fame cannot
tell those two groups apart; salience separates them almost perfectly.

### Against the launch review's own verdicts

Taking the review's item-level judgements as labels — items it wanted
replaced for recognition reasons versus items it marked AIR, benchmark, or
specialist-but-fair:

| | mean fame | mean salience |
|---|---:|---:|
| Review negatives | 69.2 | 49.2 |
| Review positives | 83.8 | 85.3 |
| **Separation** | **+14.6** | **+36.1** |

Rank separation (AUC) on the same labels: **fame 0.594, salience 0.969.**
Excluding Mihrimah Sultan, whose score turns out to be a data bug (below):
**fame 0.458 — worse than a coin flip — salience 0.958.**

This is the central result, but the labelled set is small (16 positives,
3–4 negatives) and I selected which review verdicts counted as recognition
judgements. Treat it as corroboration of the divergence lists, not as an
independent experiment.

### Where it fails — reported honestly

**Mihrimah Sultan is a broken title mapping, not a fame outlier.** The pool
item points at a **531-byte disambiguation page**. Salience scored her 0.2
and fame scores her 13.9 because both were measuring an empty page. The real
article, "Mihrimah Sultan (daughter of Suleiman I)", is 23 KB. This is now
fixed — see "The disambiguation-page bug" below.

**Daigo Fukuryū Maru scores 79.7 — salience does not flag it, and should
not.** The review's objection was "great story, wrong game": low *visual*
answerability. Bhimbetka (90.7) is the same case. Salience measures
recognition, not whether a photograph is guessable. **It cannot substitute
for the image-crop audit**, and no weighting would make it do so.

**Day-level verdicts: a null result.** Comparing the review's six "best
complete-day candidates" against its eight "heaviest intervention" days,
across all 15 rounds each day: mean fame gap −0.2, mean salience gap −0.1.
Neither metric predicts the review's day verdicts, because those were
driven by Thread board structure and image crops. Salience is an
item-selection tool only.

**Modern political importance leaks in.** Kim Il-sung and Kim Jong-il sit
near the top of the high-salience list. WikiProject Politics rates them Top
because they matter, not because a history podcast would cover them.

**Popular-history subjects that Wikipedia rates "Mid" get demoted.** Anne of
Cleves (−44), Guy Fawkes (−33), Kösem Sultan (−35), Lorenzo de' Medici
(−34), Michel Ney (−32) and Blackbeard (−53) are all thoroughly
Rest-Is-History material, and the instrument marks them down. This is the
signal's deepest limitation: **WikiProject importance measures scholarly
significance, and popular-history appeal is only partly the same thing.**
Tudor wives, Vikings and the Gunpowder Plot are "Mid" to Wikipedia's
editors and headline material to this audience.

**Assessment coverage is uneven.** 31 pool items (2.3%) carry no history
rating at all and fall back to a neutral ~46. Wilfred Thesiger has thirteen
project banners and still scores nothing, because none carry an importance
value.

**Of the six figures named in the original brief**, salience raises
Belisarius (+10), Brunel (+10), Mithridates (+2) and Simon de Montfort
(+0.4), and *lowers* Stilicho (−9). Stilicho is rated "Mid" by every project
that assesses him. On that one the instrument disagrees with the brief, and
I am reporting the disagreement rather than tuning it away.

**Anglophone tilt.** Two of the three corpora are BBC Radio 4. The national
polls partly offset this, but a Japanese or Persian figure has fewer routes
to a corpus hit than a British one.

---

## The disambiguation-page bug

**Root cause.** The live pool records in `data/reveal-who.json`,
`data/figures.json` and `data/reveal-what.json` carry **no `wiki_title`
field at all**. Every fame/salience tool therefore resolves an item from its
display *name*. When that name is a bare ambiguous string — "Seneca",
"Charles V", "Vasa", "Mihrimah Sultan" — the lookup lands on a
**disambiguation page**: a few hundred bytes of links, no pageviews, no
inbound links, no WikiProject assessments. The item then scores near zero on
every derived metric, and does so *confidently*, which is worse than
scoring blank.

**Scope.** A systematic check of all 1,331 pool items (via `pageprops`,
the authoritative disambiguation flag, not a byte-size guess) found **14
items resolving to a disambiguation page or a non-existent article** — more
than the ten first reported, because that first pass was a spot check.

| game | pool id | resolved to (wrong) | correct article |
|---|---|---|---|
| who | `charles-v-hre` | `Charles V` (743 B, disambig) | Charles V, Holy Roman Emperor |
| who | `empress-theodora` | `Theodora` (disambig) | Theodora (wife of Justinian I) |
| who | `mihrimah-sultan` | `Mihrimah Sultan` (531 B, disambig) | Mihrimah Sultan (daughter of Suleiman I) |
| map | `charles-v-hre` | `Charles V` (disambig) | Charles V, Holy Roman Emperor |
| map | `john-reed` | `John Reed` (disambig) | John Reed (journalist) |
| map | `john-smith` | `John Smith` (disambig) | John Smith (explorer) |
| map | `seneca` | `Seneca` (disambig) | Seneca the Younger |
| map | `thomas-cochrane` | `Thomas Cochrane` (1,136 B, disambig) | Thomas Cochrane, 10th Earl of Dundonald |
| map | `william-adams` | `William Adams` (disambig) | William Adams (samurai) |
| what | `hindenburg` | `Hindenburg` (disambig) | LZ 129 Hindenburg |
| what | `merv` | `Ancient Merv` (no such article) | Merv |
| what | `sacre-coeur` | `Sacré Cœur` (disambig) | Sacré-Cœur, Paris |
| what | `st-stephens-vienna` | `St. Stephen's Cathedral` (disambig) | St. Stephen's Cathedral, Vienna |
| what | `temple-poseidon` | `Temple of Poseidon` (457 B, disambig) | Temple of Poseidon, Sounion |

Six more (`cyrene`, `fram-ship`, `mikasa`, `vasa-ship`,
`world-trade-center`, `christ-the-redeemer`) have ambiguous names but were
already resolving correctly through `final_pools.json`; they are pinned
anyway so they cannot regress.

**A correction to the first report.** I originally wrote that eight
*scheduled* items had garbage fame scores. That over-claimed. The scheduler
(`compile_editions.py`) tries an item's `name` and then each of its
`variants`, so items carrying a good variant — "lz 129 hindenburg",
"fram (ship)", "japanese battleship mikasa" — resolve correctly despite the
ambiguous display name. **Only Mihrimah Sultan actually received a garbage
fame number** (13.86, from the disambiguation page, which is the one such
page that happens to exist in `fame_scores.json`). Seven other scheduled
items got *no* fame signal, which the scheduler treats as "no opinion" by
design and is harmless. The bug was real and worth fixing, but its blast
radius on the schedule was one item, not eight.

**Fix, in three layers.**

1. `TITLE_OVERRIDES` in `build_salience.py` — 20 `(game, id) -> title`
   pairs, every one verified live against the API (exists, not a
   disambiguation page, ≥ 1,500 bytes). This is the durable record, because
   `current_inventory.json` is gitignored and regenerated.
2. `current_inventory.json` — `wiki_title` filled in for the 13 affected
   items that exist in that 22 July snapshot. Mapping field only.
3. The resolver now **rejects** a disambiguation/missing/short article
   instead of silently scoring it, so a bad name-lookup produces an honest
   blank rather than a confident zero.

**Before / after.** Every item below now resolves to the right article:

| pool item | salience before | after |
|---|---:|---:|
| `map/charles-v-hre` | 45.8 | **97.8** |
| `who/charles-v-hre` | 45.8 | **97.8** |
| `map/seneca` | 45.8 | **93.5** |
| `what/merv` | 45.8 | **83.3** |
| `what/st-stephens-vienna` | 45.8 | **80.7** |
| `what/hindenburg` | 45.8 | **80.6** |
| `who/empress-theodora` | 45.8 | **69.2** |
| `what/sacre-coeur` | 45.8 | **61.5** |
| `what/temple-poseidon` | 45.8 | 47.3 |
| `map/john-reed` | 45.8 | 43.3 |
| `map/william-adams` | 45.8 | 37.6 |
| `who/mihrimah-sultan` | **0.2** | **26.2** |
| `map/john-smith` | 45.8 | 14.1 |
| `map/thomas-cochrane` | 45.8 | 7.6 |

**Do not act on the bottom of that table yet.** Six of the corrected titles
are absent from `fame_scores.json`, so they have no pageview or inlink data:
density and depth fall back to a neutral 50 and the fame anchor to 50, and
the whole score then rests on WikiProject ratings alone. Those items now
carry `"low_confidence": true`. Thomas Cochrane at 7.6 is the clearest
example of why this matters — a `Low` rating from one work group, on the man
who inspired both Hornblower and Aubrey. That is the scholarly-vs-popular
failure mode, not a verdict. **Run `fetch_metrics.py` then `build_scores.py`
over the six corrected titles before making any swap decision.**

### The permanent guard

`tools/validate_reveal.py` now fails the build on this class of bug. Because
the suite runs offline, the online check is factored out:

- `build_salience.py` writes **`tools/fame/title_health.json`** — small,
  committed, one row per pool item: resolved title, source, status
  (`ok` / `disambiguation` / `missing` / `too_short` / `unresolved`) and
  article size.
- `validate_reveal.py`'s `check_title_health()` **errors** on any status
  that is not `ok`, and **warns** on any pool item missing from the manifest
  (a newly added item whose title has never been verified). A missing
  manifest warns rather than fails, matching how the other fame-signal
  consumers degrade.

Verified by negative test: re-pointing Mihrimah at the disambiguation page
and deleting an item from the manifest produced exactly one ERROR and the
expected WARNs; restoring gave 0 errors. `python3 tests/run_all.py --fast`
is green (all five validators PASS).

---

## How to use fame and salience together

### The hypothesis was right, and the reason is better than expected

The working hypothesis — fame governs the easy tier, salience governs the
hard tier — is supported. But the numbers point at something more useful
than a split rule.

**The easy tier is not actually exhausted.** Its scarcity is a labelling
artefact:

| game | items labelled `easy` | items scoring fame ≥ 90 |
|---|---:|---:|
| Face Value (`who`) | 106 | **273** |
| Lifeline (`map`) | 204 | **245** |
| Relic (`what`) | 105 | **160** |

At the 5+5+5+1 recipe a game consumes about 13 easy rounds a week, so a
six-week rotation needs ~78 distinct easy items. Every game already has
two to three times that many household names — **66 of the 120 `who` items
currently labelled "hard" are at fame ≥ 90.** Household names are sitting
in the hard tier while the easy tier is described as empty.

So the two scores do not merely fill different tiers. They identify a
**trade you can execute today**, in both directions:

- **39 pool items are general celebrity** (fame ≥ 90, salience < 75) —
  Robin Williams, Elizabeth Taylor, Tupac Shakur, Stanley Kubrick, Audrey
  Hepburn, Bruce Lee, John Wayne, Paul Newman, Stan Lee, The Starry Night.
  **23 of them are currently tagged medium or hard.** They are perfect
  Monday material and poor Friday material. Moving them down relieves the
  binding constraint.
- **13 pool items are enthusiast gold** (salience ≥ 90, fame < 75) —
  Kaiser Wilhelm II, José de San Martín, Franz Joseph I, Xuanzang, Robert
  Falcon Scott, Staffordshire Hoard, Basil II, Demosthenes, Otto the Great,
  Temple of Hatshepsut, Gedi Ruins. **12 are tagged medium or below.**
  Moving them up makes hard days rewarding.

### The rule I would ship

Stop treating `difficulty` as a hand-authored label and derive it:

| Tier | Gate | Supply vs the ~78–90 needed per game |
|---|---|---|
| **Easy** (Mon–Tue) | `fame ≥ 90`. **Ignore salience.** | who 273 / map 245 / what 160 |
| **Medium** (Wed–Thu) | `fame ≥ 75` **and** `salience ≥ 70` | who 337 / map 389 / what 294 |
| **Hard** (Fri–Sun) | `salience ≥ 75`, **no fame floor** | who 346 / map 415 / what 287 |

Plus two guards that apply to every tier:

1. **Never schedule an item with `salience < 45`.** 47 pool items fail
   this, 26 of them currently tagged hard. That set contains the genuine
   "obscure and unfair" cases the review complained about — and it is a
   *smaller and better-targeted* set than the low-fame tail, which sweeps
   up Lise Meitner and Themistocles.
2. **Never schedule an item whose `wiki_title` is missing, unresolved, or a
   disambiguation page.** `salience.json` carries `title_source` on every
   item so these are one filter away.

In plain English, for the calendar:

> **Monday wants people everyone has heard of. Friday wants people history
> lovers have heard of. They are different lists, and you currently have
> plenty of both — they are just filed under the wrong labels.**
>
> Use the fame score to pick Monday and Tuesday: household names, no
> further test. Use the salience score to pick Friday, Saturday and Sunday:
> it will happily give you Basil II and Demosthenes, and it will keep out
> the genuinely unfair ones. Midweek, require both.
>
> One safety rule for every day: if salience is under 45, do not schedule
> it at all, whatever the fame score says.

### What salience must not be used for

- It is not an image-answerability check. Keep the crop audit.
- It is not a Thread board check. The day-level test was a null result.
- It should not gate the easy tier. Adding a salience floor to easy would
  shrink the one supply that is genuinely constrained, for no benefit —
  Monday does not need historical resonance, it needs recognition.
- It is a proxy, like fame. Both are project-authored estimates, not
  audience research. The launch review's caveat applies unchanged.

---

## Files

| File | Role |
|---|---|
| `build_salience.py` | The whole pipeline. Stdlib only. `--offline` scores from cache with no network; `--probe-projects N` re-runs the WikiProject discovery audit. |
| `salience.json` | Output. `items` (1,331 pool entries keyed by id+game) and `titles` (6,444 scored articles), each carrying every component signal alongside the blend so the inputs stay inspectable. |
| `title_health.json` | Committed manifest of which Wikipedia article each pool item resolves to, and whether it is real. Read by `tools/validate_reveal.py`. Regenerate whenever the pools change. |
| `raw/salience_*.json` | HTTP cache, gitignored. Delete to force a refetch. |

Also modified, for the disambiguation fix only: `current_inventory.json`
(13 `wiki_title` fields) and `tools/validate_reveal.py` (the new
`check_title_health` guard). `fame_scores.json`, `build_scores.py` and
everything under `data/` remain untouched.
