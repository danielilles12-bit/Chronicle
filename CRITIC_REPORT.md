# Critic report — round 1

## Verdict
HIGH: 1  MEDIUM: 4  LOW: 9

## Defects

### [HIGH] Hint chips from previous rounds persist for the rest of the session
- Where: `js/mapgame.js` (`startRound` vs. the `#hint-occ` / `#hint-ini` click handlers); visible in shipped screenshots `13-map-wrong-guess.png` and `14-map-revealed.png`
- What: Hint chips are inserted as siblings of `#map-guesses` (`$('#map-guesses').parentNode.insertBefore(chip, $('#map-guesses'))`), but `startRound()` only clears `#map-guesses` itself. Every hint chip therefore stays on screen for all subsequent rounds (and accumulates if more hints are used). The shipped screenshots prove it: in Round 2 (Nelson Mandela) the player is still shown "First European to reach India by sea" — Vasco da Gama's occupation hint from Round 1.
- Why it matters: The game actively displays the wrong figure's hint during play; a player who trusts it will answer with the previous figure. This is a functional defect reachable in any normal session that uses a hint.

### [MEDIUM] Birth/death year labels collide when the two points are close
- Where: `js/mapgame.js` `scaleMarkers`/`drawMarkers`; visible in `13-map-wrong-guess.png` and `14-map-revealed.png` (Mandela: "2013" overprints "1918", which is unreadable)
- What: Both labels are anchored a fixed offset right of their dots (birth above, death below) with no collision handling. For figures whose birth and death points are near each other but not identical (Mandela Mvezo/Johannesburg; similarly Mozart Salzburg/Vienna, Saladin Tikrit/Damascus at certain aspect ratios), the labels overlap and one year is illegible.
- Why it matters: The two years are the core puzzle information; when one is unreadable the round is materially harder for no reason and the screen looks broken.

### [MEDIUM] Factually sloppy clue: Plato and the five solids (Midi 3, 4-Down)
- Where: `data/puzzles.json`, `midi-3`, down 4: "Plato matched five of them to the elements" (SOLIDS)
- What: In the *Timaeus* Plato matched four solids to the four elements (tetrahedron–fire, cube–earth, octahedron–air, icosahedron–water); the dodecahedron he assigned to the cosmos/heavens, not to an element. "Matched five of them to the elements" overstates it.
- Why it matters: A history-themed crossword trades on precision; a pedantic solver will rightly object.

### [MEDIUM] Typo tolerance accepts the wrong monarch as correct
- Where: `js/match.js` (`tolerance` of 2 for candidates ≥ 9 chars) against `data/figures.json` variants
- What: Regnal numerals fall inside the edit-distance budget: "Napoleon III" matches variant "napoleon i" (distance 2), "Catherine I" matches "catherine ii" (distance 1), "Suleiman II" matches "suleiman i" (distance 1). A player who names a *different historical person* is scored correct.
- Why it matters: Forgiving matching is for typos, not for crediting answers that are factually a different figure.

### [MEDIUM] Spec deviation: a number of clues have no history angle at all
- Where: `data/puzzles.json` — e.g. OATBRAN ("High-fiber cereal component", midi-2), PRETTILY ("In a fetching way", full-2), IRONON, PROS, NAMELY, SEEM, OWNERS (midi-3), HIM, FLAP, HURT, AND (full-1), PUN, SPAT, STY, LALA, ITLL (full-2), GETONIT (midi-1), LET (mini-3)
- What: The Definition of Done says "all clues history-themed and factually accurate." Most fill is admirably history-slanted, but the entries above are plain dictionary/pop clues with no historical angle.
- Why it matters: It is a stated acceptance criterion; judged against the spec these clues miss it (NYT-realistic, but the spec is stricter than the NYT).

### [LOW] Back from the session summary leads to a dead round, and "See results" double-counts the session
- Where: `js/mapgame.js` (`finishSession`, router trail in `js/app.js`)
- What: From the summary, the top-left back chevron returns to the finished round-10 screen (everything disabled) where "See results ›" can be pressed again; `finishSession()` then increments `m.sessions` a second time.
- Why it matters: Dead-ended screen plus a quietly inflating stats counter.

### [LOW] Quitting a session mid-way has no confirmation
- Where: `#view-map` back button (aria-label "Quit session"), `index.html` / `js/app.js`
- What: One accidental tap on the chevron abandons a 10-round session silently; the in-progress score is lost with no "are you sure?".
- Why it matters: Easy destructive action; NYT Games confirm before discarding progress.

### [LOW] Native `window.confirm` dialogs break the visual register
- Where: `js/crossword.js` `doReveal('puzzle')` and `restart()`
- What: Reveal-puzzle and Clear & restart use the browser's system confirm dialog inside an otherwise carefully styled app (custom sheets exist and could host this).
- Why it matters: Jarring, un-NYT-like; on an installed PWA the system dialog looks foreign.

### [LOW] Stated scoring rules omit the floor and the bonus size
- Where: `index.html` map start screen copy / README vs. `js/mapgame.js` `resolveRound`
- What: Copy says hints cost 25 and wrong guesses 10 (implying a correct answer could approach 0), but the code floors any correct answer at 10 points (`Math.max(10, …)`), and the streak bonus is a flat +10 from 2-in-a-row — neither is stated.
- Why it matters: Score shown can contradict the arithmetic the rules imply (e.g. 2 hints + 5 wrong guesses still pays 10).

### [LOW] Initials hint includes particles and epithets
- Where: `js/mapgame.js` `initials()`
- What: "Joan of Arc" → "J. O. A.", "Catherine the Great" → "C. T. G.", "Alexander the Great" → "A. T. G.", "Vincent van Gogh" → "V. V. G.". Initialising "of"/"the" is noise, not signal.
- Why it matters: A paid-for hint (−25) should be crisp; "T. G." is not an initial of a name.

### [LOW] Two shipped screenshots misrepresent real states
- Where: `screenshots/16-desktop-home.png`, `screenshots/06-crossword-complete.png`
- What: The "desktop" shot shows the iOS-Safari "Add to Home Screen" tip (the capture used an iPhone UA at desktop size — real desktops never see it); the completion shot reads "Mini 1 solved in 0:00." because the test auto-solved in under a second.
- Why it matters: The screenshot set is the visual record of the product; these two show states a user cannot reach.

### [LOW] Pinch-zoom disabled
- Where: `index.html` viewport meta (`user-scalable=no`)
- What: Zoom is blocked app-wide, including the reading-heavy clue list and summary screens.
- Why it matters: Accessibility (WCAG 1.4.4); common in games but still a trade-off worth recording.

### [LOW] Cleopatra "Last pharaoh of Ptolemaic Egypt" is loose
- Where: `data/figures.json`, `cleopatra` occupation
- What: Strictly, her son Caesarion (Ptolemy XV) was nominal pharaoh for roughly two weeks after her suicide; careful sources say "last *active* ruler of the Ptolemaic Kingdom."
- Why it matters: Pedantic-professor territory, but this is exactly the persona the product invites.

### [LOW] Repeated answers across the 10-puzzle set
- Where: `data/puzzles.json` — HAN (mini-1, mini-3), NOT (midi-1, midi-2), ODIN (mini-4, full-1), FOR (mini-2, full-2), EON (mini-4, mini-5)
- What: No puzzle repeats an answer internally (validator-checked), but the same short entries recur across a set a player will likely finish in one or two sittings; ODIN even gets the same one-eyed-god angle twice.
- Why it matters: Noticeable déjà vu in a small, curated pack.

## What was checked
- Every clue/answer in `data/puzzles.json` (all 10 puzzles): grid/clue consistency re-derived by hand for all five minis, three midis and both 11×11s (rotational symmetry confirmed cell-by-cell); every factual claim in every clue audited. Spot-verified by web search where not certain: Simon Fraser last beheading 1747 ([Wikipedia](https://en.wikipedia.org/wiki/Simon_Fraser,_11th_Lord_Lovat)), Safeco founded 1923 in Seattle ([Wikipedia](https://en.wikipedia.org/wiki/Safeco)), bauxite identified at Les Baux 1821 ([EARTH Magazine](https://www.earthmagazine.org/article/march-23-1821-bauxite-discovered/)), Ogden "Junction City" ([USU exhibit](https://exhibits.usu.edu/exhibits/show/transcontinentalrailroad/utahafterthegoldenspike/impacts/ogden)). No factual errors found in the puzzles beyond the Plato wording above.
- All 30 figures in `data/figures.json`: names, variants, birth/death years, places, occupations, and coordinate plausibility against each named place (all coordinates check out; difficulty split is exactly 10/10/10; 30 figures as specced).
- `python3 tools/validate_puzzles.py` run directly: ALL PUZZLES VALID (5 mini, 3 midi, 2 full). The 11×11 substitution for 15×15 is documented in README as the build instructions allowed.
- Full suite `python3 tests/run_all.py` run: validator, crosswords, map game, pwa/offline, screenshots — all PASS, including console-error assertions.
- All 16 screenshots inspected (this is how the HIGH and the label-collision defects were found).
- Code read in full: `index.html`, `css/style.css`, `js/app.js`, `js/crossword.js`, `js/mapgame.js`, `js/match.js`, `js/storage.js`, `sw.js`, `manifest.webmanifest`, `tools/validate_puzzles.py`. Crossword UX verified against the spec list (tap-to-select, direction toggle, clue bar, auto-advance, full clue list, check/reveal at all three scopes, timer, correct-only celebration — all present). Manifest standalone + full icon set verified (apple-touch-icon is 180×180); service worker precaches all app assets.
