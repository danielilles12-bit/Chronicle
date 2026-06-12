# Critic report — round 2

## Verdict
HIGH: 0  MEDIUM: 1  LOW: 8

There are zero HIGH defects this round. All five round-1 functional complaints
(hint-chip leak, year-label collision, session double-count/dead-end, native
confirms, screenshot misrepresentations) are verified fixed in code, in tests
and in the regenerated screenshots.

## Defects

### [MEDIUM] Regnal-numeral guard is incomplete — some wrong monarchs still score as correct
- Where: `js/match.js` (`splitNumeral` / `isMatch`) against `data/figures.json`
- What: The round-1 fix only compares numerals when **both** the guess and the
  candidate end in one. Two holes remain, confirmed by replicating the
  algorithm exactly: (1) a guess with a trailing numeral fuzzy-matches a
  numeral-less variant — "Cleopatra I" (a real, different queen: Cleopatra I
  Syra, regent of Egypt c. 193–176 BC) matches the stored variant "cleopatra"
  at edit distance 2 and is scored correct for Cleopatra VII; (2) numerals not
  in last position bypass the guard entirely — "Alexander I of Macedon",
  "Alexander II of Macedon" and "Alexander IV of Macedon" (all real, different
  kings) are within distance ≤2 of the variant "alexander iii of macedon" and
  all score as correct. ("Napoleon II/III", "Catherine I", "Suleiman II" are
  genuinely fixed.)
- Why it matters: Round 1's principle stands — typo forgiveness must not
  credit a player who names a factually different historical person.

### [LOW] Repeated answers across the 10-puzzle set — worse than round 1 recorded
- Where: `data/puzzles.json`
- What: Nine answers now repeat across puzzles: AGO (midi-3, full-2),
  EON (mini-4, mini-5), FOR (mini-2, full-2), HAN (mini-1, mini-3),
  NOT (midi-1, midi-2), ODE (midi-2, full-2), ODIN (mini-4, full-1),
  OIL (midi-2, full-2), TIE (midi-3, full-1). Round 1 listed five of these;
  ODE, OIL, TIE and AGO were missed then and remain. No within-puzzle dupes
  (validator-confirmed).
- Why it matters: Noticeable déjà vu in a small curated pack a player will
  finish in a sitting or two; the round-1 note was not acted on.

### [LOW] FOR crosses FORD in the same starting square (and other substring containments)
- Where: `data/puzzles.json`, full-2 (1-Across FORD, 1-Down FOR share square
  (0,0)); also AND inside crossing ANDREWS and inside GRANDMA (full-1), LEN
  inside crossing BLEND (full-1), SET inside WELLSET (full-2)
- What: An answer that is a prefix of the entry it crosses, starting in the
  very same cell, is a construction wart NYT editors would not pass; the other
  containments are lesser versions of the same blemish.
- Why it matters: The product's stated bar is NYT-grade construction.

### [LOW] Revealed squares are not locked
- Where: `js/crossword.js` (`type()` does not check `G.revealed`)
- What: After "Reveal square/word/puzzle", the player can type over the
  revealed letter; the red "revealed" corner triangle stays on a now-wrong
  cell, producing a contradictory state (revealed mark + wrong letter, later
  also the red check slash). NYT locks revealed cells.
- Why it matters: Visual state lies about the cell; trivially reachable by
  tapping a revealed square and typing.

### [LOW] Physical keyboard still types into the grid while overlays are open
- Where: `js/crossword.js` global `keydown` handler (only checks
  `#view-cw.hidden`)
- What: With the check/reveal sheet, the clue list, or the styled confirm
  dialog open, letter keys, Backspace, Tab and arrows still mutate the grid
  underneath (desktop/hardware-keyboard scenario).
- Why it matters: Input leaking under a modal is classic un-QA'd behaviour;
  a stray keystroke during "Reveal the entire puzzle?" edits the puzzle.

### [LOW] Inconsistent leniency on lone first names in the map game
- Where: `data/figures.json` variants + `js/match.js` tolerance
- What: "Alexander", "Suleiman", "Victoria", "Cleopatra", "Napoleon",
  "Hannibal", "Toussaint" are all accepted bare, but "Catherine" (for
  Catherine the Great) is rejected — no bare variant and "catherine" is
  distance 3 from "catherine ii". "Antoinette" is likewise rejected for
  Marie Antoinette. A player who is right but terse loses the round.
- Why it matters: The forgiveness rules feel arbitrary exactly where the spec
  promises forgiving matching with stored variants.

### [LOW] A handful of clues still have no history angle; one is sloppily worded
- Where: `data/puzzles.json` — AGO "In the past" (full-2), WAS "'Is,' once"
  (mini-2), TRIBECA "Manhattan district, short for 'Triangle Below Canal'"
  (full-2), GETONIT "'Hop to it, soldier!'" (midi-1, fig-leaf only); plus HIM
  "Any king, grammatically" (full-1) — the property is pronominal/referential,
  not grammatical case of kingship; the wording is loose.
- Why it matters: "All clues history-themed" is a stated acceptance criterion;
  round 1's rewrites covered most but not all (note: AGO is clued historically
  in midi-3 yet generically in full-2).

### [LOW] Pinch-zoom remains disabled app-wide
- Where: `index.html` viewport meta (`user-scalable=no`)
- What: Unchanged from round 1; now at least documented as a deliberate
  trade-off in README. Reading-heavy screens (clue list, summary) still cannot
  be zoomed (WCAG 1.4.4).
- Why it matters: Accessibility cost is acknowledged but not mitigated (e.g.
  no larger-text option).

### [LOW] Housekeeping: dead CSS and a stray build artifact
- Where: `css/style.css` lines 136–137 (`.cell.flash` / `@keyframes cellflash`
  referenced nowhere in JS or HTML); untracked `tools/out/fulls.json` in the
  working tree while sibling outputs (`minis/midis/elevens.json`) are committed
- What: Unused animation rule shipped to clients; inconsistent repo state.
- Why it matters: Cosmetic, but the spec says zero placeholders/dead ends —
  dead code is the same smell.

## What was checked
- Ran `python3 tools/validate_puzzles.py` myself: 5 mini / 3 midi / 2 full,
  ALL PUZZLES VALID (structure, ≥3-letter runs, interlock, connectivity,
  rotational symmetry on the 11×11s, numbering/answer/position agreement, no
  within-puzzle duplicate answers, no clue containing its own answer).
- Ran the full suite `python3 tests/run_all.py` myself: validator, crosswords
  (all 10 solved end-to-end in WebKit/iPhone with toggle, check/reveal,
  wrong-fill toast, persistence-across-reload assertions), map game (full
  deterministic 10-round session with exact score math, hint-chip leak
  regression test, regnal-numeral assertions), PWA (manifest/icons/iOS meta,
  Chromium SW + full offline flow hard-gated; WebKit harness quirk tolerated
  and documented in README), screenshots — all PASS, console/page errors
  asserted empty on the gated paths.
- Audited every clue and answer in all 10 puzzles against the grids (answers
  re-derived from grid strings) and for factual accuracy, including all 20
  round-1 rewrites (Pascal/Cleopatra's nose, oat-bran craze, Old Guard
  "grumblers", Platonic-solids rewrite, Khrushchev shoe-banging, Lewis AND
  Clark, "over by Christmas" 1914, Gibson Girl, madrigal la-la, Woden/
  Wednesday, etc.). Spot checks beyond round 1: Roman Empire ~5M km², Notre-
  Dame 1804 single emperor crowned, NAS chartered 1863 under Lincoln, PTA 1897
  National Congress of Mothers, Tweety 1942, MSG 1908, L.L.Bean 1912. No
  factual errors found.
- Audited all 30 figures in `data/figures.json` (count, 10/10/10 difficulty
  split, names, variants, years, places, coordinate plausibility for every
  birth/death place, occupation texts). Verified the contested Vasco da Gama
  "c. 1469" via web search (Subrahmanyam's authoritative biography argues
  1469; Wikipedia/Britannica concur it is a defensible dating) — accepted.
- Re-implemented `js/match.js` (normalize, Damerau-Levenshtein, tolerance,
  numeral guard) in Python and brute-forced cross-figure confusions plus 17
  wrong-monarch probes — source of the MEDIUM finding above; also verified
  the round-1 cases (Napoleon III, Catherine I, Suleiman II) are fixed.
- Read all shipped code (`index.html`, `css/style.css`, `js/app.js`,
  `js/crossword.js`, `js/mapgame.js`, `js/match.js`, `js/storage.js`,
  `sw.js`, `manifest.webmanifest`) against every Definition-of-Done item;
  traced router trails for dead ends (summary back-chevron now goes Home;
  `S.done` guard prevents session double-count; quit now confirms via the
  styled in-app sheet).
- Inspected all 16 screenshots: hint chips no longer leak across rounds
  (13/14), Mandela's 1918/2013 labels no longer collide, completion shows a
  real solve time (1:01), desktop home no longer shows the iOS install tip;
  checked icon files are real PNGs at 192/512/512-maskable/180 (apple-touch).
- Verified README records the 15×15→11×11 substitution, the full scoring
  rules (floor and streak bonus), the WebKit offline-test caveat and the
  pinch-zoom trade-off, as required.
