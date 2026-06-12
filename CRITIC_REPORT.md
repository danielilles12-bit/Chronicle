# Critic report — round 3

## Verdict
HIGH: 1  MEDIUM: 1  LOW: 10

## Defects

### [HIGH] PAC clue gives the wrong year for the first PAC
- Where: data/puzzles.json — full-1 ("Second Terms"), 61-Across, answer PAC
- What: Clue says "Election-funding org. — the first was formed in 1944." The first PAC, the CIO-PAC, was formed in July 1943 (in response to the Smith–Connally Act of June 1943), to support FDR's 1944 campaign. The org was formed in 1943, not 1944.
- Why it matters: A factually wrong date in a clue is exactly what the spec forbids; the clue's whole hook is the date.

### [MEDIUM] EDY clue calls the candy maker an "ice-cream maker"
- Where: data/puzzles.json — full-1 ("Second Terms"), 42-Down, answer EDY
- What: Clue: "Joseph ___, ice-cream maker who teamed with Dreyer in 1928." In every standard account (incl. the brand's own history), Joseph Edy was the candy maker and William Dreyer the ice-cream maker; the pair founded Grand Ice Cream in Oakland in 1928. The 1928 date is right; the occupational descriptor is swapped onto the wrong partner.
- Why it matters: Misleading/sloppy wording — solvers who know the trivia know Edy as the candy man.

### [LOW] Full-1 title "Second Terms" is only half-earned
- Where: data/puzzles.json — full-1
- What: Of the two 15-letter spanners, GROVERCLEVELAND fits the title (non-consecutive second term) but EIGHTTRACKTAPES has nothing to do with it. The title implies a theme the grid doesn't deliver. (Full-2's "Old Europe" coheres: VERSAILLES + METTERNICH.)
- Why it matters: Un-NYT-like; a titled puzzle promises a theme.

### [LOW] Repeated fill across puzzles, including identical 1-Across in consecutive midis
- Where: data/puzzles.json — midi-1 and midi-2 both open with 1A NOT; HAN, EON, ARI, AMA, NIT and ERA each appear in two different puzzles
- What: Within-puzzle uniqueness holds (validator enforces it), but a 10-puzzle set re-using short fill — twice in the very same slot — is inelegant.
- Why it matters: Feels like constructor's autopilot to a regular solver.

### [LOW] TREXARM is a borderline entry with a loose clue
- Where: data/puzzles.json — full-1, 25-Across
- What: "Tiny-limbed pose named for a Cretaceous predator." "T. rex arms" is informal slang (sleep position/dance move); as a 7-letter crossword entry it's wobbly, and "pose" stretches it further. Facts in the clue (Cretaceous) are fine.
- Why it matters: Spec demands real words/names/phrases only; this one is defensible but at the edge.

### [LOW] ANAKIN clue leans on a name not used on screen until 1983
- Where: data/puzzles.json — full-2 ("Old Europe"), 72-Across
- What: "Skywalker whose screen saga began in 1977." The character (as Darth Vader) debuted in 1977, but the name "Anakin" wasn't spoken on screen until Return of the Jedi (1983). Defensible, but a pedant can object.
- Why it matters: Date-pinned clues invite date-pedantry.

### [LOW] Completion modal has a single exit
- Where: js/crossword.js / index.html — #cw-done
- What: After solving, the only action is "Back to puzzles"; the modal backdrop isn't dismissible, so you can't stay and admire the solved grid (you must re-open the puzzle from the list).
- Why it matters: NYT lets you close the congratulations and look at your grid.

### [LOW] Browser Back button is not wired to the in-app router
- Where: js/app.js (trail-based router, no History API)
- What: On desktop (and any browser context), pressing the browser's Back button exits the app instead of going back one view. Irrelevant in the installed iPhone PWA, the primary target.
- Why it matters: Mild dead-end feel on desktop, which the spec says must be acceptable.

### [LOW] Map session is lost if the app is killed mid-run
- Where: js/mapgame.js / js/storage.js
- What: Only bestScore/bestStreak/sessions persist. Crossword progress survives force-quit; a half-finished 10-round map session does not.
- Why it matters: Spec says scores/progress persist; sessions are short, but the asymmetry with crosswords is noticeable.

### [LOW] Dynamic label-halo scaling is silently overridden by CSS
- Where: js/mapgame.js scaleMarkers() vs css/style.css `.mk-label { stroke-width: 3 }`
- What: scaleMarkers sets `stroke-width` as an SVG presentation attribute on each zoom frame, but the CSS class rule outranks presentation attributes, so the halo is always 3 user-units — the per-zoom computation is dead code, and the white halo is relatively thicker at deep zooms than intended. Shipped screenshots still look fine.
- Why it matters: Dead code masking an intended visual behaviour; could bite a future tweak.

### [LOW] Pinch zoom disabled app-wide
- Where: index.html viewport meta (`user-scalable=no`)
- What: Standard for app-like games, and the README discloses it as a deliberate accessibility trade-off, but it remains a real accessibility limitation (no zoom for low-vision users).
- Why it matters: Accessibility; mitigated by large type and disclosure.

### [LOW] Offline behaviour automated only on Chromium
- Where: tests/test_pwa.py; README "Known limitations"
- What: WebKit's Playwright harness errors on offline reload ("WebKit encountered an internal error"), so the full offline flow is hard-gated on Chromium only; WebKit is best-effort. Disclosed in README and test output.
- Why it matters: The target platform is iOS/WebKit; the offline guarantee there rests on PWA platform behaviour, not on a green automated check.

## What was checked
- Ran `python3 tools/validate_puzzles.py` myself: 5 mini / 3 midi / 2 full, ALL PUZZLES VALID (structure, ≥3-letter runs, full interlock, connectivity, 15×15 rotational symmetry, numbering/answer/position agreement, no in-puzzle duplicate answers, no clue containing its own answer).
- Ran the full suite `python3 tests/run_all.py`: validator, crosswords (all 10 solved end-to-end in WebKit/iPhone viewport incl. direction toggle, check/reveal, wrong-fill toast, persistence across reload), map game (deterministic 10-round session with exact-score assertions, hint-chip checks, regnal-numeral matching guards, best-score persistence), PWA/offline (manifest, icons, SW, Chromium offline flow), screenshots — all five steps PASS, zero console errors asserted by the harness.
- Read every clue/answer in data/puzzles.json (all fresh 15×15 clues plus all mini/midi clues) as the pedantic professor; manually cross-checked grid letters against both 15-letter spanners (GROVERCLEVELAND, EIGHTTRACKTAPES) and full-2's marquee entries (VERSAILLES, METTERNICH, STREETER, MAVERICK); WebSearch-verified the claims I wasn't certain of: first-PAC date (wrong — CIO-PAC, 1943), Edy/Dreyer roles (misleading), Safeco 1923 founding (accurate per the company's own corporate history), Ruth Cheney Streeter (accurate). Dozens of other dated claims (Bauxite/Les Baux 1821, Tetris 1984, RICO 1970, WTA 1973, MTV 1981, Ascot 1711, bra patent 1914, NES 1985, Chicago L 1892, Emu War 1932, Edict of Nantes 1598, 1800 electoral tie, Notre-Dame 1804, Bikini 1946–58, Schubert Octet 1824, Nye Committee, Order No. 227, Hannibal 218 BC, Louisiana Purchase $15M, etc.) checked — no further errors found.
- Verified all 30 figures in data/figures.json: names, variants, difficulty spread (10/10/10), birth/death years (incl. BC handling and "approx" flags), place names, occupation texts, and coordinate plausibility against the stated places (e.g. Mvezo, Sancellemoz/Passy, Fort de Joux, Libyssa/Gebze, Otrar, Kealakekua Bay, Werowocomoco, Szigetvár) — no errors found.
- Read all UX code (index.html, css/style.css, js/app.js, crossword.js, mapgame.js, match.js, storage.js, sw.js, manifest.webmanifest) against every spec item: standalone manifest + full icon set incl. apple-touch-icon, SW precache list complete, NYT crossword conventions (tap/toggle, clue bar, auto-advance, clue list, check/reveal square-word-puzzle, timer, celebration only on a fully correct grid), map scoring math (max(10, 100−25·hints−10·wrongs), +10 streak from the 2nd consecutive, reveal = 0), forgiving matching (accent/case/punctuation-insensitive, length-scaled Damerau-Levenshtein, roman-numeral guard), localStorage persistence.
- Inspected all 16 screenshots in screenshots/ for layout, typography, marker/label legibility, zoom framing, scoring consistency (summary 395 = 75+100+110+110 checks out, streak bonuses correct) and desktop rendering.
- Checked icons (real rendered PNG set incl. maskable + apple-touch-icon) and README claims against the code and test output.
