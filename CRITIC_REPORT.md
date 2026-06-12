# Critic report — round 4

## Verdict
HIGH: 1  MEDIUM: 1  LOW: 8

## Defects

### [HIGH] Resuming a map session mid-round replays an already-scored round and double-counts it
- Where: js/mapgame.js — resumeSession() / persistSession() / startRound()
- What: persistSession() saves the round index `i` when a round starts and again when it resolves, but `i` is only advanced when the player taps "Next". If the app is killed/reloaded in the window between answering and tapping "Next" (a natural moment to switch apps on iOS, where the PWA page is routinely evicted), the saved state has the resolved round still at index `i` with its result already in `results` and its points already in `score`. resumeSession() blindly restarts round `i`: the same figure is presented again — with its name just shown in the feedback the player saw — and answering it again pushes a duplicate result and adds points a second time. Empirically reproduced (Playwright, mapseed=42): answer round 1 correctly (100 pts) → reload → "Resume — round 1 of 10 (100 pts)" → same figure (darwin) replayed with input enabled → score 210 pts, saved results length 2 at i=0. The replay even collects a +10 "streak" bonus for consecutively answering the same round, and the session would end with 11 results in a "10-round" summary and an inflated, persisted best score.
- Why it matters: Broken functionality in a shipped feature — corrupted scoring, a free already-revealed answer, and a permanently inflated best score. The test suite only covers resume-after-Next (tests/test_mapgame.py), so this path is untested.

### [MEDIUM] "Next round" button is below the fold after a round resolves
- Where: index.html / css/style.css (#map-next at the bottom of .map-main); visible in screenshots/12-map-correct.png and 14-map-revealed.png
- What: On the target 390×844 viewport, once the feedback box appears (plus any hint chip or wrong-guess chip), the primary "Next round ›" action is pushed fully off-screen (12-map-correct.png: not visible at all; 14-map-revealed.png: top sliver visible). There is no scroll affordance; the input and buttons above it are all disabled at that moment, so the screen reads as a dead end until the player discovers they can scroll the lower panel.
- Why it matters: The single action that moves the game forward is hidden at the exact moment the player needs it, on the primary device, in the project's own canonical screenshots — well below the NYT bar the spec sets.

### [LOW] Browser history and in-app trail desynchronise
- Where: js/app.js — show()/back()/popstate handler
- What: show() pushes a history state, but the in-app ‹ back button pops only the internal trail, leaving the pushed history entry behind; and the popstate handler pops the trail on any popstate, so pressing the browser's Forward button also navigates the app backwards. The common Back-button case works; the bookkeeping around it is loose.
- Why it matters: Mildly odd navigation on desktop browsers; invisible in the installed PWA, the primary target.

### [LOW] Repeated short fill across the 10-puzzle set, including an identical 1-Across in consecutive midis
- Where: data/puzzles.json — midi-1 and midi-2 both open with 1A NOT; HAN (mini-1/mini-3), EON (mini-4/mini-5), ERA (midi-1/full-2), AMA, ARI and NIT (midi-2/full-2) each appear in two puzzles
- What: Within-puzzle uniqueness holds (validator-enforced), but a small set re-using the same short answers — twice in the very same slot — reads as constructor autopilot.
- Why it matters: Inelegant for a curated 10-puzzle collection; a regular solver will notice.

### [LOW] ANN and ANNA in the same grid
- Where: data/puzzles.json — full-2 ("Old Europe"), 23-Down ANN and 61-Down ANNA
- What: Both clues are factually fine (Cape Ann is named for Anne of Denmark; Anna Leonowens was in Siam in the 1860s), but ANN is wholly contained in ANNA; NYT-style construction avoids near-duplicate entries of the same name root in one puzzle.
- Why it matters: Duplication-adjacent blemish in the marquee puzzle.

### [LOW] TREXARM remains a borderline entry
- Where: data/puzzles.json — full-1 ("Across the Ages"), 25-Across
- What: The reclued "Notoriously stubby limb on the Cretaceous' apex predator" is factually fine and better than round 3's "pose" wording, but T-REX ARM as a standalone 7-letter entry is still informal slang at the edge of "real words/names/phrases only".
- Why it matters: Spec's vocabulary bar; defensible but wobbly.

### [LOW] EGO clued as a "Freudian coinage"
- Where: data/puzzles.json — full-1, 64-Across
- What: Freud wrote "das Ich"; "ego" is the Latin his English translators chose, and the word long predates Freud. As shorthand for "the psychoanalytic sense originates with Freud" the clue is defensible under a standard reading, but "coinage" overstates it.
- Why it matters: Date/attribution-pinned clues invite exactly this pedantry; "Freudian concept" would be airtight.

### [LOW] resumeSession() trusts the saved blob completely
- Where: js/mapgame.js — resumeSession()
- What: Saved figure ids are looked up with `DATA.figures.find(...)` and used unchecked; if a stored session references an id that no longer exists (e.g. after a future figures.json edit ships via SW update), `round()` returns undefined and startRound() throws, leaving a blank map view. No length/shape validation either.
- Why it matters: Latent crash on the upgrade path; trivial to guard.

### [LOW] Pinch zoom disabled app-wide
- Where: index.html viewport meta (user-scalable=no)
- What: Standard for app-like games and disclosed in the README as a deliberate trade-off, but it remains a real accessibility limitation for low-vision users.
- Why it matters: Accessibility; mitigated by large type and disclosure.

### [LOW] Offline behaviour automated only on Chromium
- Where: tests/test_pwa.py; README "Known limitations"
- What: WebKit's Playwright harness errors on offline reload, so the full offline flow is hard-gated on Chromium only, WebKit best-effort. Disclosed in README and test output.
- Why it matters: The target platform is iOS/WebKit; the offline guarantee there rests on PWA platform behaviour, not a green automated check.

## What was checked
- Ran `python3 tools/validate_puzzles.py` myself: 5 mini / 3 midi / 2 full, ALL PUZZLES VALID (structure, ≥3-letter runs, interlock, connectivity, 15×15 rotational symmetry, numbering/answer/position agreement, no in-puzzle duplicate answers, no clue containing its own answer). Read the validator's source to confirm it checks what it claims.
- Ran the full suite `python3 tests/run_all.py`: all five steps PASS (validator; all 10 crosswords solved end-to-end in WebKit/iPhone viewport with direction-toggle, check/reveal, wrong-fill toast and persistence assertions; deterministic 10-round map session with exact score math, hint-chip and regnal-numeral matching guards, best-score persistence, resume-after-Next; manifest/icons/SW/Chromium-offline; all 16 screenshots regenerated). Console/page errors asserted zero by the harness.
- Wrote and ran my own Playwright probe for the resume path the suite does not cover (reload after resolving, before "Next") — this is what surfaced the HIGH defect, with exact numbers (100 → 210 pts, duplicate result at i=0).
- Re-read every clue/answer in data/puzzles.json as the pedantic professor. Round-3 defects verified fixed: PAC clue now says 1943 (CIO-PAC, correct), EDY now "candy maker who partnered with ice-cream man Dreyer in 1928" (roles now correct), full-1 retitled "Across the Ages" (no false theme promise), ANAKIN reclued to "first named on screen in 1983" (correct — Return of the Jedi). Hand-verified both 15-letter spanners letter-by-letter against the grid (GROVERCLEVELAND col 2, EIGHTTRACKTAPES col 12). Spot-verified the dated/factual claims across all 10 puzzles (Les Baux 1821, Tetris 1984, Safeco 1923, Spindletop 1901, AMA 1847, Nye Committee, 1800 electoral tie, Notre-Dame 1804, Bikini 1946–58, Hannibal 218 BC, $15M Louisiana Purchase, Stamp Act 1765, RICO 1970, Saudi unification 1932, Hee Haw 1969, Schubert Octet 1824, Ascot 1711, bra patent 1914, NES 1985, Chicago L 1892, NATO 1949, Tut 1922, Rousseau 1762, Haggard 1887, Suleiman "Kanuni", John Rae, Cape Ann/Anne of Denmark, Streeter/Women Marines, Emu War 1932, Versailles 1919, Edict of Nantes 1598, Fiona Macleod 1890s + Shrek 2001, Elsie 1936, NBA 1946, MTV 1981, WTA 1973, Leonowens 1860s, Maverick, Moran, Mae West, CSI 2000, laser 1960, Marie Curie/"radioactivity", Moe Berg, Ogden "Junction City", Victoria/William IV, Plessis-Praslin, core-rope ROM, Pindar, Uma/Parvati, Pan/panic) — no factual errors found this round.
- Verified all 30 figures in data/figures.json: 10/10/10 difficulty split, unique ids, names/variants, birth/death years (incl. BC and approx flags), place names and coordinate plausibility (Ajaccio, Longwood, Mvezo, Sancellemoz/Passy, Fort de Joux, Libyssa/Gebze, Otrar, Kealakekua Bay, Werowocomoco, Szigetvár, Stettin/Szczecin, Santa Marta, Kochi, Downe) — no errors found.
- Read all UX code (index.html, css/style.css, js/app.js, crossword.js, mapgame.js, match.js, storage.js, sw.js, manifest.webmanifest) against every spec item; confirmed round-3 fixes ("Admire the grid" second exit, History-API Back, map session resume button, .mk-label stroke-width no longer clobbered by CSS).
- Inspected all 16 screenshots for layout, typography, marker/label legibility, zoom framing and scoring consistency (summary 395 = 75+0+100+110+110 checks out; solved state, check/reveal sheet, clue list, full 15×15 render all look right) — which is also where the below-the-fold "Next round" problem shows.
- Checked icons (real PNGs: 32/180/192/512/maskable-512) and manifest/SW precache list completeness against the file tree.
