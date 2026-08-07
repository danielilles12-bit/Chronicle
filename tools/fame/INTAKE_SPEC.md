# Intake spec — adding a Face Value / Relic item end-to-end

Scope: turning one row of `tools/fame/final_pools.json`'s `per_game.who.add` /
`per_game.what.add` into a real record in `data/reveal-who.json` /
`data/reveal-what.json`, plus its image file(s). Written so an agent with no
other context can do this ~267 times without re-deriving anything below.

This is content-pool intake only. It does **not** touch `data/editions.json`
or `data/editions.proposed.json` — those are populated later by
`tools/compile_editions.py propose`, from whatever is sitting in the reveal-*
pool by then. Adding a record here makes it *eligible*, nothing more.

---

## 0. The two files you write to

- `data/reveal-who.json` — Face Value, portraits. Every record has
  `"kind": "portrait"`.
- `data/reveal-what.json` — Relic, everything else (buildings, objects, art,
  manuscripts, ships...). Every record has **`"kind": "artefact"`** — literally
  that string, always, for all 239 current records. `js/app.js` concatenates
  both files into `DATA.reveal` and `js/revealgame.js` splits the pool back
  into who/what purely via `x.kind === 'portrait'` vs not. Do not copy
  `final_pools.json`'s finer `kind` values (`building`, `site`, `sculpture`,
  `manuscript`, `painting`, `monument`...) into the data file's `kind` field —
  those are internal fame-pipeline classification, not the game schema.

Both files are a flat JSON array, 1-space indent, `ensure_ascii=False`
(accented characters and apostrophes are written literally, not escaped),
trailing newline. `tools/derive_commons_urls.py` already round-trips them
with exactly this convention (`json.dumps(items, indent=1,
ensure_ascii=False)` + conditional trailing `\n`) — match it by hand if you're
editing directly, or use that script's `save_records` pattern.

---

## 1. Source of truth for what to add

`tools/fame/final_pools.json` → `per_game.who.add` (132 items) and
`per_game.what.add` (135 items) = **267 total** candidates. Each entry looks
like:

```json
{"name": "Michael Jackson", "wiki_title": "Michael Jackson", "fame": 99.92,
 "era": "twentieth", "region": "North America",
 "occupation_family": "performer", "image": "ok", "flags": [], "provenance": "add"}
```

`image` is `"ok"` or `"small"` (never `"none"` in either add list — see
digest below). Some entries carry a `flags` array (e.g.
`["sensitive-nazi"]`, `["sensitive-religious"]`) with `provenance:
"verdict-include"` — these were already reviewed and approved by the owner;
add them the same as anything else, no extra schema field required (see
Gotchas re: living-persons check, which nothing here automates).

**Image lookup**: `tools/fame/image_availability.json` → `items[wiki_title]`
is the actual source of truth for the Commons file:

```json
"Michael Jackson": {
  "qid": "Q2831", "has_image": true,
  "file": "Michael Jackson 1983 (3x4 cropped) (contrast).jpg",
  "license": "Public domain", "license_ok": true,
  "artist": "Matthew Rolston; Distributed by Epic Records",
  "min_dimension_px": 2291, "small": false
}
```

`file` is the bare Commons filename (no `File:` prefix). `license` is the
verbatim Commons `LicenseShortName` — use it as-is for the record's `license`
field (existing data already contains oddities like `"CC BY-SA 3.0 de"` and
`"FAL"` verbatim, so don't normalize it further). `small: true` means
`min_dimension_px < 800`; those are the `image: "small"` rows in
`final_pools.json` — still usable, just don't expect crisp detail on zoom.

---

## 2. Step-by-step recipe, one item

### 2.1 Pick an id

No slugify script exists in this repo — ids are hand-picked lowercase-hyphen
slugs, usually short and recognisable (`einstein`, `gandhi`, `napoleon`, not
`albert-einstein`/`mahatma-gandhi`/`napoleon-bonaparte`), with a
disambiguating prefix only when the bare slug would collide or be ambiguous
(`michelangelo-david` for the David statue, not bare `david`, which would be
confusable/collide with a King David record).

**Hard rule not enforced by the validator**: the id must be unique across
**both** files combined, not just within one. `data/reveal-who.json` and
`data/reveal-what.json` are concatenated at runtime into `DATA.reveal`, and
lookups do `DATA.reveal.find(x => x.id === id)` — a duplicate across files
means the second one is unreachable by id. `tools/validate_reveal.py` only
checks for duplicates *within* each file separately, so this is a silent
failure mode if you don't check by hand. As of today there are 297 who ids
and 239 what ids with zero overlap — verify your new id against the union of
both before committing it.

### 2.2 Download the image

```bash
python3 tools/fetch_commons.py fetch "File:<the file field from image_availability.json>" <your-id>
```

This calls the Commons API (`prop=imageinfo&iiurlwidth=1200`), downloads the
~1200px-wide thumbnail (or the full image if it's already narrower) to
`assets/img/<id>.jpg`, and prints a JSON stub:

```json
{"id": "<id>", "img": "assets/img/<id>.jpg", "license": "...",
 "attribution": "...", "source": "Wikimedia Commons: <filename>",
 "_bytes": 123456, "_size": "1200x1523"}
```

Use that `source` string verbatim — it's the exact `"Wikimedia Commons: "` +
filename format that `tools/audit_rights.py` and `tools/derive_commons_urls.py`
parse (`commons_filename()` only strips that literal prefix; anything else
is treated as "unverified"/un-parseable).

If you already trust `image_availability.json`'s `license`/`artist`, you can
skip the round-trip through `fetch_commons.py`'s printed stub and just build
the record fields directly — but still use `fetch_commons.py fetch` (or the
same URL shape) to actually get the bytes onto disk at `assets/img/<id>.jpg`.

### 2.3 Shrink the originals, then build the small-serving variant

```bash
python3 tools/build_image_variants.py --cap-originals   # first
python3 tools/build_image_variants.py                   # then
```

**Run `--cap-originals` after any batch, and run it FIRST.** It shrinks the
top-level originals in place to the same 1600px ceiling the variant uses,
keeping the filename, the real format, the colour mode and the embedded
colour profile — only the pixel dimensions change. Skipping it is not
cosmetic: the "Sharper pictures" commit (`e4748ec3`, 7 Aug 2026) pulled 97
files at full museum resolution, `assets/img/` reached 814 MB with three
files of 59, 59 and 29 MB, and **every Cloudflare deploy failed** because Pages
refuses any single file over 25 MiB. `tools/repo_checks.py` now fails CI
at 20 MB, so this cannot reach the host again — but the failure will be
yours to fix, and `--cap-originals` is the fix.

The second command is idempotent — it skips anything whose
`w800/<name>.webp` is already newer than its source. This is the "shrink"
tool from the v127 commit: longest edge capped at 1600px, WebP quality 78,
EXIF rotation baked in. Current corpus (7 Aug 2026): `assets/img/`
(originals) = 324 MB over 819 files (~405 KB avg); `assets/img/w800/` =
139 MB over 819 files (~174 KB avg).

Order matters: capping first means each variant is built from the master
rather than from an already re-compressed original.

**This step is easy to skip by accident and nothing will error if you do** —
`js/app.js`'s `loadImgFallback()` tries the w800 URL first and silently falls
back to the full original on a 404. The app still works without it, just
serves the full-size original every time, defeating the entire point of the
size-reduction pass. Always run this after adding images.

### 2.4 Choose the crop geometry (fx, fy, frac, start)

This is the one genuinely manual, per-image judgment call in the whole
pipeline — it requires looking at the actual downloaded photo.

- **`fx`, `fy`** (floats, 0.0–1.0 each): the normalized position of the
  image's "money shot" — the detail whose reveal is the payoff — under a
  *square, cover-fit* crop window. `paintCover()` in `js/revealgame.js` sets
  `background-position: fx*100% fy*100%` on a square frame; `moneyScrap()`
  maps `(fx, fy)` to one of the 3×3 grid cells (`col = min(2, floor(fx*3))`,
  same for row) — that cell is the one hiding the answer. Per
  `tools/QUALITY_RUBRIC.md`: never put the money shot in the opening
  (free) scrap, and difficulty = fame × fragment ambiguity, not raw crop
  size.
- **`start`** (optional int 0–8): overrides which scrap the game opens for
  free. Default is computed by `startScrap()` — farthest 3×3 cell from the
  money cell, corners checked first — but that default can land on empty
  sky/backdrop. `tools/audit_start_scraps.py <output-dir>` renders one audit
  card PNG per item (the full window + the candidate opening cell enlarged)
  for a reviewer to judge FAIR / TOO_EASY / UNFAIR / BROKEN;
  `tools/apply_start_scrap_audit.py <results-dir> <manifest.json>` bulk-applies
  verdicts as `start` overrides. For one-off additions it's fine to leave
  `start` unset and spot-check the rendered game once content is live;
  for a batch of ~267 it's worth running the audit tool.
- **`frac`** (float, 0.05–1.0): required by `tools/validate_reveal.py` (range
  check) but **not read anywhere in `js/`** — grepped across
  `js/*.js`; the only hits are the unrelated English word "fraction" in
  comments. It appears to be a leftover from a pre-tear-mechanic zoom system
  (see project memory: "tear mechanic replaces zoom"). Set it to something in
  the existing range players' worth (current corpus mostly sits 0.15–0.45,
  occasionally up to 0.9 for very wide/tall subjects like
  `sistine-ceiling`) so the file reads consistently, but its actual runtime
  effect today is none. See Open Questions.

### 2.5 Write the record

Full field list, in the order the existing data uses it (fields marked
*required* are checked by `tools/validate_reveal.py`; the rest are optional
but should be filled for consistency and for the Sources page):

| field | required? | notes |
|---|---|---|
| `id` | yes (dup-checked) | see 2.1 |
| `name` | yes | display name |
| `kind` | yes | `"portrait"` in reveal-who.json; `"artefact"` in reveal-what.json, always |
| `difficulty` | yes | `"easy"` \| `"medium"` \| `"hard"` — see §3 |
| `variants` | yes, non-empty | lowercase + trimmed (validator enforces this literally); see §4 for what the matcher already forgives so you don't have to enumerate typos |
| `blurb` | yes | load-bearing text — see §3.1, the clue system parses it |
| `img` | yes | `"assets/img/<id>.jpg"`, file must exist on disk |
| `fx`, `fy` | yes, 0–1 | see 2.4 |
| `frac` | yes, 0.05–1.0 | see 2.4 |
| `start` | no | see 2.4 |
| `license` | yes | verbatim Commons LicenseShortName |
| `attribution` | no (but always populated in practice) | legacy author field, `creditHTML()`'s fallback if `image_author` missing |
| `source` | yes | exactly `"Wikimedia Commons: <filename>"` |
| `image_source_url` | no | direct Commons file-page URL |
| `image_author` | no | preferred author field (see §5) |
| `image_license` | no | mirrors `license` under the new namespace |
| `image_license_url` | no | only present when the license actually has a legal-text URL (CC variants); omitted entirely for Public domain / "No restrictions" |
| `image_retrieved` | no | ISO date last verified against Commons |

**Filled example — a person** (real record, `data/reveal-who.json`):

```json
{
 "id": "tutankhamun",
 "name": "Tutankhamun",
 "kind": "portrait",
 "difficulty": "easy",
 "variants": [
  "tutankhamun", "tutankhamen", "tutankhaten", "king tut",
  "king tutankhamun", "tut", "pharaoh tutankhamun"
 ],
 "blurb": "Boy pharaoh of Egypt's 18th dynasty (c. 1341–1323 BC) · his tomb held over 100 walking sticks — scans confirm the boy king needed them",
 "img": "assets/img/tutankhamun.jpg",
 "fx": 0.5,
 "fy": 0.38,
 "frac": 0.45,
 "start": 6,
 "license": "Public domain",
 "attribution": "Roland Unger",
 "source": "Wikimedia Commons: CairoEgMuseumTaaMaskMostlyPhotographed.jpg",
 "image_source_url": "https://commons.wikimedia.org/wiki/File:CairoEgMuseumTaaMaskMostlyPhotographed.jpg",
 "image_author": "Roland Unger",
 "image_license": "Public domain",
 "image_retrieved": "2026-07-21"
}
```

**Filled example — an object** (real record, `data/reveal-what.json`):

```json
{
 "id": "colosseum",
 "name": "The Colosseum",
 "kind": "artefact",
 "difficulty": "easy",
 "variants": [
  "the colosseum", "colosseum", "coliseum", "the coliseum",
  "flavian amphitheatre", "amphitheatrum flavium", "colisseum"
 ],
 "blurb": "c. 70–80 AD · Arena flooded for staged sea battles at first; underground chambers to hoist gladiators came later",
 "img": "assets/img/colosseum.jpg",
 "fx": 0.73698224852071,
 "fy": 0.8777692485384793,
 "frac": 0.2123425200348275,
 "license": "CC BY-SA 2.0",
 "attribution": "Wikipedia user Diliff",
 "source": "Wikimedia Commons: Rome Colosseum exterior 2.jpg",
 "image_source_url": "https://commons.wikimedia.org/wiki/File:Rome_Colosseum_exterior_2.jpg",
 "image_author": "Nicholas Hartmann",
 "image_license": "CC BY-SA 4.0",
 "image_license_url": "https://creativecommons.org/licenses/by-sa/4.0",
 "image_retrieved": "2026-07-21"
}
```

Note the last example: `attribution` ("Wikipedia user Diliff") and
`image_author` ("Nicholas Hartmann") genuinely differ, and `license`
("CC BY-SA 2.0") differs from `image_license` ("CC BY-SA 4.0") — the legacy
fields were entered by hand originally, the `image_*` fields are the more
recent, Commons-verified re-derivation. Prefer getting `image_*` right (via
2.6 below); the legacy `license`/`attribution`/`source` fields only need to
be internally consistent with `image_*`, not necessarily hand-perfect.

**Where to insert it in the array**: `tools/QUALITY_RUBRIC.md` states "array
order IS the airing order" — `daily.js`/`compile_editions.py`'s cursors walk
each difficulty tier's array in file order, so position = curation
priority, best-first. New, not-yet-quality-ranked items should be appended
at the end of the file (lowest priority), not spliced into the middle —
don't jump a new unreviewed item ahead of curated content.

### 2.6 Populate the `image_*` fields (optional but recommended)

```bash
python3 tools/derive_commons_urls.py --online
```

Batch-verifies every record's `source` filename against the live Commons API
and — only when both the file resolves AND its license family matches the
stored `license` — writes `image_source_url` / `image_author` /
`image_license` / `image_license_url` / `image_retrieved`. Anything that
fails either check is left untouched and reported to
`tools/out/commons_report.csv`, nothing is guessed. Safe to run over the
whole file after a batch of additions — it only touches records that qualify
and is idempotent.

(`--online` hits the network for every unique filename in both files, in
batches of 50; drop `--online` for a dry pass that only prints counts.)

---

## 3. Tier (difficulty) assignment

No formula exists for this — `final_pools.json`'s `add` entries carry a raw
`fame` score (Wikipedia/Wikidata-derived) but **no tier**; only the `keep`
list's `current_tier` reflects a tier, inherited from already-aired content.
Fame alone is a weak signal: measured medians across the current pool are
`easy≈95, medium≈87-89, hard≈83-85` — overlapping enough that fame score by
itself will misclassify. Use `tools/QUALITY_RUBRIC.md`'s actual test:

> easy = instantly famous **image** (not just famous person — Rutherford is
> famous, his face is not); medium = famous subject, less-worn image; hard =
> earned recognition.

Current corpus balance for context (not a target, just what "even" looks
like today): who 297 = 79 easy / 139 medium / 79 hard; what 239 = 78 easy /
104 medium / 57 hard.

### 3.1 Blurb format is load-bearing, not just prose

`js/revealgame.js` **parses the blurb string at runtime** to generate two of
the four paid hint clues. Getting the shape wrong doesn't break validation,
but silently breaks/hides a clue in the live game.

- **Who** (`clueOccupation`/`clueYears`): blurb must read
  `"<occupation clause> (<years>) · <fact>"` — occupation is everything
  before the first `(`; years is the first parenthetical containing a digit.
  Real example: `"Boy pharaoh of Egypt's 18th dynasty (c. 1341–1323 BC) ·
  his tomb held..."`.
- **What** (`clueInitials`/`extractEra`): no occupation clause (initials
  clue derives from `name`, not `blurb`) — but `extractEra()` needs a
  datable phrase somewhere in the blurb: an N-th-century phrase, a
  BC/BCE/AD/CE-tagged year, or a plain 1000–2100 year (optionally with
  `c.`, a range, or a decade `s`). Real examples: `"c. 70–80 AD · Arena
  flooded..."`, `"Michelangelo, c. 1512 · a physician argued..."`. If the
  blurb is genuinely undatable, `extractEra` returns null and the Era clue
  button just hides — not fatal, but avoid it when a real date exists.

Neither `final_pools.json` nor `image_availability.json` nor
`universe_people.json`/`universe_objects.json` contain any blurb/fact text —
this is new prose you (or an LLM pass) must write per item, following
`tools/QUALITY_RUBRIC.md`'s bar: "one concrete, delightful fact beats
dates-and-titles," dates must be correct, museum/location must be current.

---

## 4. Alias mechanics — what `variants` needs to cover, and what it doesn't

The matcher (`js/match.js`, `isMatch()`/`normalize()`) is quite forgiving —
`variants` should cover *genuinely different name-forms*, not typos or
grammar variants, since those are handled automatically:

**Normalization applied to every guess and every name/variant before
comparing** (`normalize()`): lowercase → NFD-normalize and strip diacritics →
strip all characters outside `[a-z0-9\s]` (punctuation becomes a space) →
collapse whitespace → drop everything from a bare token `"by"` onward (so
`"The Last Supper by Leonardo"` reads as `"the last supper"`) → drop the
articles `the/a/an` → fold written/numeric ordinals 1st–16th and the words
`first`..`sixteenth` to roman numerals (`"Henry 8"` / `"Henry the Eighth"` /
`"Henry VIII"` all normalize identically).

**Automatically forgiven, no `variants` entry needed for these:**
- Case, accents, punctuation.
- One typo per word via Damerau-Levenshtein (transposition-aware), capped at
  1 edit, 0 for words ≤4 chars; plus a separate doubled-letter rule
  (`"Elliott"` ~ `"Eliot"`).
- Missing/extra leading title word (`queen/king/emperor/pope/saint/sir/...`
  — full list in `TITLES` in `js/match.js`) — `"queen mary"` matches
  `"Mary I"` and vice versa.
- Extra surrounding words, if the candidate is multi-token (`"covers"`
  rule) — `"Leonardo da Vinci The Last Supper"` matches `"The Last Supper"`.
- Containment of a whole registered variant phrase inside a longer guess,
  when the pool is registered (`registerPool('who', ...)` /
  `registerPool('what', ...)` — done once at init for the whole who/what
  pool) — `"the taj mahal india"` matches `taj-mahal`.
- A "distinctive core" token: any single word that appears in this item's
  `name` (not just its variants) and in no other item's name+variants across
  the same pool auto-matches, generously, UNLESS it's a generic noun (see
  below).
- Regnal numerals are guarded: `"Napoleon III"` will never match
  `"Napoleon"` (or vice versa) even though containment/fuzz would otherwise
  allow it.

**What you should actually put in `variants`:** the full name, common
short/nickname forms, alternate transliterations/spellings, "the X of Y"
epithets, and — the one thing the matcher can't infer — cases where the
distinctive-core word is a common noun. `js/match.js` maintains a hardcoded
`GENERIC_NOUNS` allowlist (castle, temple, rhino, gold, mask, statue, dome,
crown, sword, ...) so that e.g. `"golden rhino"` matches the one rhino item
but `"Mongolian Golden Rhino"` (naming a *different* rhino) correctly does
not. **See Gotchas below — this list needs upkeep for new items.**

---

## 5. Validation to run after adding

```bash
python3 tests/run_all.py --fast     # validators only, no browser, seconds
python3 tests/run_all.py            # + the full Playwright suite (needs `python3 -m playwright install`)
```

`--fast` runs, in order:
1. `python3 tools/validate_reveal.py` — schema/range checks on
   reveal-who/reveal-what/figures (duplicate id within-file, required
   fields present, `img` file exists on disk, `fx`/`fy`/`frac` in range,
   `difficulty` valid, `variants` non-empty and pre-lowercased, plus the
   optional trust-surface fields' shape if present).
2. `python3 tools/validate_boards.py` — Thread/chrono, unrelated to this
   batch.
3. `python3 tools/audit_rights.py` (offline mode — filename-hint license
   check only). **This never fails the suite regardless of content** —
   `audit_rights.py`'s `main()` never calls `sys.exit(1)`; MISMATCHes are
   printed to stdout/CSV, not enforced. "Image rights PASS" in CI output
   means the script ran without an exception, not that every license is
   verified correct. Run it with `--online` by hand if you want a real
   check: `python3 tools/audit_rights.py --online`.
4. `python3 tools/compile_editions.py verify` — only checks ids *already
   referenced inside `data/editions.json`*; new, not-yet-scheduled pool
   additions are invisible to it and cannot fail it.

The full (non-`--fast`) run adds the Playwright browser suite, including
`tests/match_harness.py`, which walks every item in every pool and asserts
`isMatch(name_or_variant, item, poolKey)` is true for itself — this is the
one check that would actually catch a badly-normalized or colliding
`variants` entry, so run the full suite (not just `--fast`) at least once
per batch, not just after every single item.

Optional, not part of `tests/run_all.py` but good practice after a batch:

```bash
python3 tools/build_sources_page.py   # regenerates sources.html's credit register from reveal-*.json
```

---

## 6. Digest — final_pools.json image availability

| pool | `image: "ok"` | `image: "small"` | `image: "none"` | total |
|---|---|---|---|---|
| who.add | 96 | 36 | 0 | 132 |
| what.add | 113 | 22 | 0 | 135 |

No candidate in either add list has `image: "none"` — everything proposed
for intake already has a usable Commons image, at minimum small/low-res.
(`"small"` = shortest dimension < 800px per `probe_images.py`'s
`SMALL_THRESHOLD_PX`.) 267 total additions (132 + 135), matching the
`stats` block in `final_pools.json` (`who.add: 132`, `what.add: 135`,
resulting pool sizes 400 / 350 against targets of the same).

---

## 7. Gotchas (surprising, worth knowing before you start)

1. **`kind` in the data file is not the same as `kind` in `final_pools.json`.**
   Always write `"artefact"` for reveal-what.json regardless of whether
   `final_pools.json` calls it `building`/`site`/`sculpture`/`manuscript`/etc.
2. **Ids must be unique across both files combined**, not just within one —
   the validator only checks per-file. Check the union yourself.
3. **`assets/img/<id>.jpg` isn't always really a JPEG.** `fetch_commons.py`
   always names the output `<id>.jpg` regardless of the actual bytes
   Commons served. At least 3 files in the current corpus
   (`confucius.jpg`, `sima-qian.jpg`, `sylvia-plath.jpg`) are genuine PNG
   data under a `.jpg` name. This is harmless — browsers and Pillow sniff
   real content, not the extension — but don't be alarmed by it, and don't
   "fix" it by renaming (nothing depends on the true format matching the
   extension).
4. **Skipping `build_image_variants.py` fails silently.** No error anywhere
   in the pipeline if you forget it — the client just falls back to full-size
   originals forever via the w800→404→original fallback in
   `loadImgFallback()`. Always run it after a batch of new images.
5. **`frac` is currently dead code.** Required by the validator (0.05–1.0),
   not read by any `js/` file. Fill it plausibly for consistency; don't
   spend real effort calibrating it. See Open Questions.
6. **`audit_rights.py`'s offline "image rights" CI step cannot fail.** It's
   pure reporting, not a gate — don't rely on a green run to mean your
   licenses are correct; run `--online` by hand if you want that checked.
7. **PD images never show a photographer credit in-app**, even when
   `image_author` is filled. `creditHTML()` in `js/revealgame.js` only
   prints the "Photo: `<author>` · ..." line when a `license_url` is also
   present (true of CC-licensed images, never of Public domain / "No
   restrictions"); Public-domain items collapse to a bare
   `"Public domain · Wikimedia Commons"` regardless of `image_author`.
   Still fill `image_author` anyway — `tools/build_sources_page.py`'s
   Sources-page register shows it unconditionally, independent of this
   in-app gating.
8. **`GENERIC_NOUNS` in `js/match.js` is a hardcoded allowlist that this
   batch will likely outgrow.** Several `final_pools.json` additions have a
   common noun as their most distinctive name token, and that noun isn't
   currently in the allowlist: `Space Shuttle` ("shuttle"), `The Little
   Mermaid (statue)` ("mermaid"), `The Kiss (Klimt)` ("kiss"), `Sunflowers
   (Van Gogh series)` ("sunflowers"), `The Motherland Calls` ("motherland"),
   `Colossus of Rhodes` ("colossus" — not currently in `GENERIC_NOUNS`,
   unlike `rhino`/`helmet`/`mask` which already are). Any word NOT in that
   set is instead treated as a permissive "proper-name anchor" by
   `containsDistinctiveCore()` — meaning a wrong-but-similar guess (e.g. a
   hypothetical other "Colossus") would be forgiven extra descriptive words
   it shouldn't be. This file is explicitly out of scope for a
   content-only intake pass (js/ changes require the owner's sign-off per
   this repo's separation of content vs. code), but flag it — the list may
   need new entries once these items are live, and `tests/match_harness.py`
   is the regression net that would catch it if a wrong-answer case is
   later added there.
9. **Living-persons / sensitivity policy has no automated check anywhere in
   `tools/fame/`.** Project memory records a "no living politicians" rule
   from the content-intake pipeline; nothing in `finalize_pools.py`,
   `propose_pools.py`, or `gap_report.py` encodes an is-alive filter. A
   manual scan of the 132 `who.add` names found no obviously-living person
   (all appear to be historical/deceased), and 3 are pre-flagged
   sensitive-but-approved (`sensitive-nazi`: Hitler; `sensitive-religious`:
   Jesus, Joseph Smith — all `provenance: "verdict-include"`, i.e.
   already owner-approved for inclusion). Still worth a final human glance
   before going live with all 267.
10. **`trust_schema.py`'s fields (`fact_sources`, `confidence`, `tags`,
    `reviewed_by`, `reviewed_on`) are fully optional and currently unused by
    every single existing record in both files** — don't feel obliged to
    populate them; they validate cleanly absent.

---

## 8. Open questions (do not guess — ask before assuming)

- **What was `frac` originally for, and is it truly safe to fill with an
  arbitrary in-range placeholder?** It matches a validator range check but
  has zero live consumers in `js/`. It may be inert dead weight (most
  likely, given the "tear mechanic replaces zoom" project history), or it
  may be read by some tool this investigation didn't surface (e.g. a
  design/audit HTML page under `audit/` — `audit/zoom-in-review.html`
  references "frac" but that's a standalone review tool, not part of the
  live app or the test suite). Confirm with the owner before treating it as
  fully cosmetic across 267 new records.
- **Should `GENERIC_NOUNS` in `js/match.js` be extended as part of this
  batch, or handled as a separate follow-up once live?** (See Gotcha 8.)
  This spec treats it as out of scope for a content-only pass but flags it
  because several incoming items are exactly the shape that historically
  triggered an owner-reported false-positive match bug.
- **Is there an intended target split of easy/medium/hard for this specific
  batch of 267**, or is per-item editorial judgment (per
  `tools/QUALITY_RUBRIC.md`) sufficient with no aggregate target? No
  target ratio is specified anywhere in `final_pools.json` or its
  generating scripts for the `add` lists (only `keep` entries carry a
  `current_tier`, inherited from prior aired history).
- **Should new items get inserted anywhere other than the end of each
  tier's implicit ordering** (e.g. interleaved by fame rank)? Nothing in
  `compile_editions.py` or `daily.js` requires ordering by anything other
  than "curated quality, best first" per `tools/QUALITY_RUBRIC.md` — this
  spec recommends simple append, but if the owner wants new content
  interleaved with existing mid-tier content rather than trailing behind
  all of it, that's a decision this investigation can't make unilaterally.
