# Critic report — round 5

## Verdict
HIGH: 1  MEDIUM: 1  LOW: 10

## Defects

### [HIGH] Interrupting the session after answering the FINAL round silently discards the whole session
- Where: js/mapgame.js — renderMapStart() / resumeSession() / finishSession()
- What: The round-4 fix makes resume derive the next round from `results.length`, which works for rounds 1–9 (verified). But when the app is killed/evicted after the 10th round resolves and before "See results ›" is tapped, the saved blob has `results.length === ids.length`, so renderMapStart() deems it non-resumable (Resume hidden) and resumeSession() would clear it. finishSession() never runs, so no summary is shown, `sessions` is never incremented and the best score is never recorded. Empirically reproduced (Playwright, mapseed=7): answered all 10 rounds for 1090 pts on screen → reload → map start says "First session — good luck", Resume hidden, `map` stats null, while an orphaned 10-result session blob sits in localStorage until the next "Start a session" overwrites it. On iOS, switching apps at the final feedback screen — the natural "I'm done" moment — routinely evicts the PWA page, so this is the same kill-before-"Next" window round 4 flagged, still broken for the last round, now as silent data loss instead of double-counting.
- Why it matters: A completed 10-round session — potentially the player's best score — vanishes without acknowledgement; the spec promises score persistence and a session summary.

### [MEDIUM] Navigating away during the celebration leaves a stale "solved" modal over the next puzzle
- Where: js/crossword.js — openPuzzle() never resets #cw-done (nor #cw-sheet / #cw-cluelist); index.html #cw-done lives inside #view-cw
- What: The completion modal is only hidden by its own two buttons. If the player leaves view-cw while it is open — a plain browser Back on desktop (any engine), or Backspace in WebKit (see LOW below) — the modal's `hidden` stays false. Opening any other puzzle then shows the old celebration over the fresh grid. Empirically reproduced (Chromium desktop): solve Mini 2 → modal up → browser Back → open Mini 1 → "Bravo! Mini 2 solved in 0:00." sits over the unsolved Mini 1 grid. It is dismissable ("Admire the grid"), but a celebration appears over a grid that is not fully correct, naming the wrong puzzle.
- Why it matters: Misleading celebration on the wrong puzzle violates "celebration ONLY when the grid is fully correct" on a path any desktop player can hit with one Back press.

### [LOW] Mid-round resume forgets hints and wrong-guess penalties already incurred
- Where: js/mapgame.js — persistSession() saves no S.cur state; startRound() resets it on resume
- What: Take both hints (occupation + initials shown), kill the app, resume: the same figure is presented with zero hint chips and zero penalty, and answering scores the full 100 (reproduced: 2 chips → reload → resume → same figure → "+100 pts"). An app-kill is a free hint-refund; deliberate players can use it to cheat their own best score.
- Why it matters: Scoring-integrity leak on the resume path; only self-cheating, hence LOW.

### [LOW] Unhandled keys are not preventDefault-ed while overlays are open — WebKit Backspace navigates the app back
- Where: js/crossword.js keydown handler — the overlay guard (`if (!$('#cw-sheet').hidden || ...) return;`) returns before preventDefault
- What: With the check/reveal sheet, clue list, confirm or completion modal open, Backspace falls through to the browser default. In WebKit (Playwright WebKit reproduces; affects hardware-keyboard iPad/Safari setups) that is history-back: the app yanks the player out of the puzzle view mid-solve, and is one of the two triggers for the stale-modal defect above. Chromium is unaffected.
- Why it matters: Hardware-keyboard niche, but it dumps a solver out of an in-progress puzzle from a habitual keypress.

### [LOW] Reveal-all earns the identical celebration and "✓ time" badge as an honest solve
- Where: js/crossword.js — doReveal('puzzle') → checkCompletion(); renderPuzzleList() done badge
- What: Revealing the entire puzzle triggers the full "Bravo!" + confetti and marks the list entry "✓ 0:00" exactly like a genuine solve. The letter of the spec ("celebration only when fully correct") is met, but NYT distinguishes assisted/revealed completions (no gold star, different copy).
- Why it matters: Un-NYT-like; cheapens the completion state the rest of the design treats as earned.

### [LOW] Browser-Back mid-session leaves the map start screen stale (no Resume button)
- Where: js/app.js popstate → render() (only refreshHomeStats for home); js/mapgame.js renderMapStart() only runs from the home-card click and quit/clear paths
- What: Pressing browser Back during a round lands on "Map of a Life" start with a resumable session saved but the Resume button hidden (reproduced on Chromium). Tapping "Start a session" then silently overwrites the saved session. Related residue: in-app ‹ pops the view trail without popping history, so one browser-Back press afterwards is a visible no-op (depth-sync prevents anything worse — Forward no longer mis-navigates; verified).
- Why it matters: Stale UI on a desktop-only navigation path; the installed-PWA primary target has no Back button.

### [LOW] Repeated short fill across the 10-puzzle set, including an identical 1-Across in consecutive midis
- Where: data/puzzles.json — midi-1 and midi-2 both open with 1A NOT; HAN (mini-1/mini-3), EON (mini-4/mini-5), ERA (midi-1/full-2), AMA, ARI, NIT (midi-2/full-2)
- What: Within-puzzle uniqueness holds (validator-enforced); the repeats are across puzzles, with NOT in the very same slot of consecutive midis. Acknowledged trade-off category, unchanged since round 4.
- Why it matters: Reads as constructor autopilot in a curated 10-puzzle collection.

### [LOW] ANN and ANNA in the same grid
- Where: data/puzzles.json — full-2 "Old Europe", 23-Down ANN and 61-Down ANNA
- What: Both clues are factually fine (Cape Ann named for Anne of Denmark; Leonowens in 1860s Siam), but ANN is wholly contained in ANNA; NYT construction avoids near-duplicates of the same name root in one grid. Unchanged since round 4.
- Why it matters: Duplication-adjacent blemish in a marquee puzzle.

### [LOW] TREXARM remains a borderline entry
- Where: data/puzzles.json — full-1 "Across the Ages", 25-Across ("Notoriously stubby limb on the Cretaceous' apex predator")
- What: Factually fine, but T-REX ARM as a standalone 7-letter entry is informal slang at the edge of "real words/names/phrases only"; the "Cretaceous'" possessive is also awkward styling.
- Why it matters: Spec's vocabulary bar; defensible but wobbly.

### [LOW] A tail of generic glue clues is not history-themed
- Where: data/puzzles.json — e.g. full-1: YELP, OPT, EXIT, ESTEEM, MCS, RINSE, EATS, REF, HIREE; full-2: GRAN, EAT, TIC, EEK, MAW, GLANCE, AFFECT
- What: The spec's letter says "all clues history-themed". The minis/midis and the vast majority of the fulls are flavored (often cleverly), but roughly 15 short glue entries in the two fulls carry plain dictionary clues. Defensible under a standard construction reading — nobody history-flavors EEK — but it is a literal spec deviation.
- Why it matters: Letter-of-spec gap; practical impact minimal.

### [LOW] Pinch zoom disabled app-wide
- Where: index.html viewport meta (user-scalable=no)
- What: Standard for app-like games and disclosed in the README as a deliberate trade-off, but a real accessibility limitation for low-vision users.
- Why it matters: Accessibility; mitigated by large type and disclosure.

### [LOW] Offline behaviour automated only on Chromium
- Where: tests/test_pwa.py output; README "Known limitations"
- What: WebKit's Playwright harness errors on offline reload ("WebKit encountered an internal error"), so the offline flow is hard-gated on Chromium only, WebKit best-effort. Disclosed; reconfirmed in this round's run.
- Why it matters: The target platform is iOS/WebKit; its offline guarantee rests on platform behaviour, not a green check.

## What was checked
- Ran `python3 tools/validate_puzzles.py` (5 mini / 3 midi / 2 full, ALL PUZZLES VALID) and read the validator source to confirm it actually enforces structure, ≥3-letter runs, interlock, connectivity, 15×15 rotational symmetry, numbering/answer/position agreement, in-puzzle duplicate bans and clue-contains-answer bans.
- Ran the full suite `python3 tests/run_all.py`: all five steps PASS (validator; all 10 crosswords solved end-to-end on WebKit/iPhone; deterministic 10-round map session with exact scoring, numeral-guard and resume-after-resolve assertions; manifest/icons/SW/Chromium-offline; 16 screenshots regenerated). Confirmed the suite now covers the round-4 HIGH (kill-before-Next resume for non-final rounds).
- Wrote and ran independent Playwright probes for paths the suite skips: final-round interrupt (found the HIGH — 1090-pt session discarded), mid-round interrupt after hints (hint-penalty refund), revealed-cell lock (typing over a revealed square leaves it intact and advances; overlay-open typing leaks nothing into the grid through check sheet, clue list, or confirm sheet), reveal-all → completion modal, browser Back during the celebration (found the MEDIUM stale modal), Backspace-with-overlay-open (WebKit navigates back; Chromium fine), browser Back/Forward depth sync after in-app back (no mis-navigation), quit-confirm Cancel/Yes flows. Zero console/page errors in every probe.
- Re-audited every clue and answer in all 10 puzzles as the pedantic professor, deriving answers from the grids myself. Spot-verified the dated/factual claims (Order 227, Les Baux 1821, Tetris 1984, Safeco 1923, Notre-Dame 1804, Spindletop 1901, AMA 1847/Medicare-1960s, 1800 electoral tie, Nye Committee, Plessis-Praslin praline, core-rope ROM, one-term Adamses, Louisiana Purchase $15M, Hannibal 218 BC, She 1887, RICO 1970, Stamp Act 1765, John Rae/Franklin, Saudi 1932, ATF/Prohibition, Hee Haw 1969, Enya 1988, Blues and Greens, von Braun, Schubert Octet 1824, PAC 1943, Grover Cleveland/Harrison, Chirac 1995–2007, 8-track fade, Suleiman "Lawgiver", Rousseau 1762, Tut 1922, NATO 1949, Dred Scott, Edy/Dreyer 1928, More/Utopia, Ascot 1711, posh folk etymology hedge, bra patent 1914, NES 1985, L 1892, Emu War 1932, Versailles 1919, Fiona Macleod/Shrek, Elsie 1936, Edict of Nantes 1598, Esau's lentils, Ari Fleischer, ream 480, imperial exams, NBA 1946, MTV 8/1/1981, Great Game, Val Kilmer/Holliday, Revere, Metternich, Ani "1,001 churches", WTA 1973, Anakin-named-1983, Air Cav, Streeter/Women Marines, Cellini, Rosa Parks, laser 1960, Felix, Cape Ann/Anne of Denmark, llamas, Deighton, Maverick, Mae West 1920s, Miller/Crucible, Moran, Leonowens 1860s, Marie Curie "radioactivity", Ogden "Junction City", Victoria/William IV niece, Moe Berg, Pascal/Cleopatra's nose, Pan/panic, Pindar, Uma/Parvati, Bikini 1946–58, Opium Wars, Han dynasty placement, Salem 1692, Edo/1868, Roman Empire ~5M km²) — no factually wrong clue found. EGO now "Freudian concept" (round-4 fix confirmed).
- Verified all 30 figures in data/figures.json: 10/10/10 difficulty split, names/variants/initials behaviour, birth/death years (incl. BC and approx flags) and place-name-vs-coordinate plausibility for every figure (Ajaccio/Longwood, Alexandria, Genoa/Valladolid, Ulm/Princeton, Vinci/Amboise, Brookline/Dallas, Kensington/Osborne, Mvezo/Johannesburg, Porbandar/New Delhi, Salzburg/Vienna, Domrémy/Rouen, Warsaw/Sancellemoz, Shrewsbury/Downe, Zundert/Auvers, Trier/London, Frankfurt/Bergen-Belsen, Vienna/Place de la Révolution, Pella/Babylon, Florence/London, Carthage/Libyssa, Tikrit/Damascus, Trabzon/Szigetvár, Cap-Français/Fort de Joux, Werowocomoco/Gravesend, Sines/Kochi, Marton/Kealakekua, Kesh/Otrar, Stettin/St Petersburg, Caracas/Santa Marta) — no errors.
- Read all UX code (index.html, css/style.css, js/app.js, crossword.js, mapgame.js, match.js, storage.js, sw.js, manifest.webmanifest) against every spec item; confirmed both round-4 fixes (resume derives from results.length for rounds 1–9; resolved rounds hide the dead form/hints and Next is in view).
- Inspected all 16 freshly regenerated screenshots: "Next round ›" now fully visible in 12 and 14 (round-4 MEDIUM fixed), marker/label legibility, auto-zoom framing (Portugal+India, South Africa), summary math (395 = 75+100+110+110), solved/check/clue-list/15×15 renders, desktop layout — all clean.
- Checked manifest (standalone, portrait, full icon set incl. maskable), real PNG icons (32/180/192/512/maskable-512), service-worker precache list against the file tree, and zero console errors across every probe and the harness runs.
