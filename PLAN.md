# PLAN — Chronicle: History Games PWA

Overnight autonomous build. Mission: a polished, mobile-first history games app
(NYT-Games-style crosswords + "Map of a Life") as an installable, fully offline
PWA. Done = all automated tests green AND 3 consecutive clean critic reviews
(hard cap: 6 critic rounds, agreed with Daniel for cost control).

## Architecture

- **Static, no build step.** Plain HTML/CSS/JS (ES modules). Deployable to any
  static host; run locally with `python3 -m http.server`.
- **Single-page app.** `index.html` owns all views; JS swaps them:
  `home`, `crossword-list`, `crossword-play`, `map-game`, `map-summary`.
  SPA keeps the PWA standalone experience seamless (no page reloads).
- **Modules** (`js/`):
  - `app.js` — boot, view router, service-worker registration, home screen
  - `crossword.js` — grid engine + NYT-style interactions
  - `mapgame.js` — Map of a Life engine
  - `match.js` — forgiving answer matching (normalize + Damerau-Levenshtein)
  - `storage.js` — localStorage wrapper (`chronicle.*` keys)
- **Data** (`data/`): `puzzles.json`, `figures.json`, `worldmap.json`
  (equirectangular SVG path data baked in at build time — zero runtime network).
- **Tooling** (`tools/`, Python): puzzle validator, grid filler, icon
  rasterizer, map asset builder. Machine constraint: no Node.js — all tooling
  and tests run on Python 3.9 (`python3 -m playwright`).

## Data formats

### Crossword (`data/puzzles.json`)
```json
{
  "id": "mini-1", "format": "mini", "size": 5, "title": "…",
  "grid": ["CAESR", "#AREA", "…"],
  "clues": { "across": [{ "num": 1, "row": 0, "col": 0, "answer": "CAESR",
                           "clue": "…" }], "down": [ … ] }
}
```
`#` = block. `grid` holds the solution letters. Clue entries carry their own
answer + position so the validator can cross-check grid vs. clue list.
Numbering follows standard crossword rules (derived and verified, not trusted).

### Figure (`data/figures.json`)
```json
{
  "id": "napoleon", "name": "Napoleon Bonaparte",
  "variants": ["napoleon", "bonaparte", "napoleon i"],
  "difficulty": "easy", "occupation": "French emperor and military commander",
  "birth": { "year": 1769, "place": "Ajaccio, Corsica", "lat": 41.92, "lon": 8.74 },
  "death": { "year": 1821, "place": "Longwood, Saint Helena", "lat": -15.95, "lon": -5.69 }
}
```
Place names stored beside coordinates so the critic can audit them.

## Content inventory

- **Crosswords:** 5 minis (5×5), 3 midis (7×7), 2 fulls (15×15, rotational
  symmetry). All clues history-themed and factually accurate; marquee entries
  are history names/terms, ordinary fill words get history-angle clues.
  Spec-sanctioned fallback if two valid 15×15s prove infeasible after sustained
  effort: 15×15 + 11×11, or two 11×11s — recorded in README.
- **Figures:** 30 (10 easy / 10 medium / 10 hard), ancient → modern, European
  bias with global mix. Session = 10 rounds sampled across difficulties.

## Game rules implemented

- **Crossword UX:** tap to select, tap again to toggle across/down; current-clue
  bar with prev/next; auto-advance within word and to next clue; full clue list
  view; check square/word/puzzle; reveal square/word/puzzle; running timer
  (pauses when hidden); celebration only when grid is 100% correct; progress
  persists per puzzle.
- **Map of a Life:** green circle = birthplace + birth year, red = death place
  + death year, on an inline SVG world map with auto-zoom to fit both points.
  Matching: case/accent-insensitive, punctuation-tolerant, 1 typo allowed for
  names ≤ 8 chars / 2 for longer, per-figure variants list. Hints: occupation
  (−25), initials (−25 more); reveal = 0. Base 100/round; streak bonus +10 per
  consecutive correct (from 2nd). Summary screen with per-round breakdown.
  Scores/streak history persist.

## Validation (non-negotiable)

`tools/validate_puzzles.py` checks every puzzle: rectangular grid, legal chars,
no answers < 3 letters, every white cell in both an across and a down answer
(full interlock), single connected component, 180° rotational symmetry for
15×15 (and 11×11 fallback) grids, clue list ↔ grid consistency (positions,
numbering, answers), no duplicate answers within a puzzle, all clues non-empty.
Exit non-zero on any failure. Run in CI-style before every critic round.

## Test strategy (Playwright for Python, WebKit = iPhone Safari engine)

`tests/` run against `python3 -m http.server` on a local port:
1. **Crossword completion** — for every shipped puzzle, solve end-to-end via
   real key events at iPhone 13 viewport (390×844); assert celebration state,
   timer ran, persistence works. Also exercise direction toggle, check, reveal.
2. **Map game sessions** — full 10-round sessions: correct answers, answers
   with deliberate typos and accent stripping, variant names, both hints,
   reveal, wrong answers; assert scoring math and summary screen exactly.
3. **PWA/offline** — manifest fields + icons resolve; SW registers; after first
   load, go offline (`context.set_offline`) and reload: app fully works.
   Run on WebKit and cross-checked on Chromium.
4. **Console hygiene** — collect console errors/page errors across all flows;
   assert zero.
5. **Screenshots** — every screen captured to `/screenshots`.

## Critic protocol

Fresh subagent per round (no build context), two personas: (a) pedantic history
professor fact-checking every clue/answer/date/place/figure; (b) ruthless QA +
NYT Games designer auditing UX against the spec. Writes `CRITIC_REPORT.md`
(defects with high/medium/low severity). All high+medium get fixed, tests
re-run, repeat. Stop: 3 consecutive zero-high/medium rounds, or round 6.

## Milestones (commit at each)

1. Plan + repo scaffold ✛ 2. App shell + design system ✛ 3. PWA plumbing +
icons ✛ 4. World map asset ✛ 5. Figures dataset ✛ 6. Map game ✛ 7. Crossword
engine ✛ 8. Validator + filler ✛ 9. All puzzles valid ✛ 10. Tests green ✛
11. Critic rounds ✛ 12. README + handoff.

## Risks & fallbacks

- **15×15 fill quality** — backtracking filler + curated wordlist; fallback
  sizes per spec, documented.
- **WebKit service-worker quirks under Playwright** — offline behavior also
  verified on Chromium; manual Safari note in README if needed.
- **Map GeoJSON fetch fails** — embed simplified hand-built outline instead
  (lower fidelity, still offline-correct).
- **Cost/usage cap overnight** — work is committed at every checkpoint; the
  loop resumes losslessly.
