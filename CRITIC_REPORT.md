# Critic report — round 6 (final)

## Verdict
HIGH: 0  MEDIUM: 2  LOW: 8

## Defects

### [MEDIUM] A finished-but-unviewed session is permanently discarded if the player taps "Start a session" instead of "See your results"
- Where: js/mapgame.js — startSession() / renderMapStart(); view-mapstart button hierarchy in index.html
- What: The round-5 fix correctly surfaces a kill-after-final-round session as a "See your results (N pts)" button, and tapping it records the session (verified: suite + my probe). But that button is the *secondary* pill, below the primary "Start a session". If the player taps Start instead — plausible for someone returning days after an eviction — startSession() immediately persists a fresh session over the finished blob and the completed session is never counted: empirically reproduced (Chromium, mapseed=7): finish all 10 rounds for 1090 pts on screen → reload → map start shows "See your results (1090 pts)" → tap "Start a session" → store.getMap() is still {sessions: 0, bestScore: 0, bestStreak: 0}. A completed session containing what may be the player's best score evaporates with no record and no acknowledgement, even though the app had every byte needed to bank it before overwriting.
- Why it matters: Spec promises score persistence and a session summary; banking a *finished* session should not depend on which of two buttons the player taps.

### [MEDIUM] The shared confirm dialog survives navigation and sits orphaned over the wrong screen
- Where: js/app.js appConfirm() / #confirm-sheet (global, outside any .view); js/crossword.js viewchange handler hides cw-done/cw-sheet/cw-cluelist but not #confirm-sheet
- What: The round-5 fix clears the crossword's own overlays on viewchange, but the app-wide #confirm-sheet is exempt. Two reproduced paths: (1) Chromium desktop — open Mini 1 → ✓ → "Clear & restart" → confirm up → browser Back: the puzzle list renders with "Clear all your answers and restart this puzzle?" still floating over it; tapping "Clear it" then wipes a puzzle that is no longer on screen. (2) WebKit hardware keyboard — in a map round tap ‹ (quit) → confirm up → press Backspace (focus on body): view navigates to the map start screen with the quit dialog still open; tapping "Quit session" from there clears the session and dumps the player on Home. The round-5 Backspace guard was added only inside view-cw, so the exact overlay-open-Backspace niche round 5 flagged still fires everywhere else.
- Why it matters: An orphaned modal acting on off-screen state is broken, un-NYT-like UI on a one-press path (Back is a natural "dismiss the dialog" reflex), and its buttons mutate things the player can no longer see.

### [LOW] Mid-round resume restores hint chips but not wrong-guess chips, so carried −10 penalties are invisible
- Where: js/mapgame.js — persistSession() stores cur.wrongs as a count only; startRound() rebuilds hint chips but #map-guesses stays empty
- What: Take a hint, guess wrong twice, kill the app, resume: the chips for both hints reappear and the penalties are correctly kept (verified: resumed round paid 100−25−25−10 = +40 with one wrong guess carried), but the struck-through wrong-guess chips are gone, so a player who answers correctly sees a quieter payout than the visible state explains. Scoring integrity is now right (round-5 LOW fixed); what remains is a cosmetic accounting gap.
- Why it matters: The score deduction is honest but unexplained on the resumed screen.

### [LOW] "Start a session" silently overwrites a resumable mid-round session with no confirmation
- Where: js/mapgame.js — startSession() bound directly to #map-start
- What: With "Resume — round N of 10 (X pts)" showing, tapping "Start a session" discards the saved session without the in-app confirm that quitting from inside a round requires. The Resume button is always fresh now (render() re-runs renderMapStart, verified), so the player is informed — but one mistap deletes progress that the quit path guards with "Quit this session? The score so far will be lost."
- Why it matters: Inconsistent protection for the same destructive outcome.

### [LOW] Repeated short fill across the 10-puzzle set, including an identical 1-Across in consecutive midis
- Where: data/puzzles.json — midi-1 and midi-2 both open with 1A NOT; HAN (mini-1/mini-3), EON (mini-4/mini-5), ERA (midi-1/full-2), AMA, ARI, NIT (midi-2/full-2), ALL (midi-3/full-2)
- What: Within-puzzle uniqueness is validator-enforced and holds; these are cross-puzzle repeats, unchanged since round 4 and an acknowledged trade-off category.
- Why it matters: Reads as constructor autopilot in a curated 10-puzzle collection.

### [LOW] ANN and ANNA in the same grid
- Where: data/puzzles.json — full-2 "Old Europe", 23-Down ANN and 61-Down ANNA
- What: Both clues are factually sound (Cape Ann for Anne of Denmark; Leonowens in 1860s Siam), but ANN is wholly contained in ANNA; NYT construction avoids near-duplicate name roots in one grid. Unchanged since round 4; acknowledged category.
- Why it matters: Duplication-adjacent blemish in a marquee puzzle.

### [LOW] TREXARM remains a borderline entry
- Where: data/puzzles.json — full-1 "Across the Ages", 25-Across
- What: The clue wording was fixed this round ("a Cretaceous apex predator" — the awkward possessive is gone), but T-REX ARM as a standalone 7-letter entry is still informal slang at the edge of "real words/names/phrases only". Acknowledged category.
- Why it matters: Spec's vocabulary bar; defensible but wobbly.

### [LOW] A tail of generic glue clues is not history-themed
- Where: data/puzzles.json — e.g. full-1: YELP, OPT, EATS, REF, MCS, RINSE, HIREE; full-2: GRAN, EAT, TIC, EEK, MAW, GLANCE, AFFECT
- What: Two former members of this list were upgraded this round (ESTEEM now Roman-flavored, EXIT now "pursued by a bear"), but roughly a dozen short glue entries in the two fulls still carry plain dictionary clues against the spec's literal "all clues history-themed". Defensible under standard construction practice — nobody history-flavors EEK.
- Why it matters: Letter-of-spec gap; practical impact minimal.

### [LOW] Pinch zoom disabled app-wide
- Where: index.html viewport meta (user-scalable=no)
- What: Standard for app-like games and disclosed in the README as a deliberate trade-off, but a real accessibility limitation for low-vision users.
- Why it matters: Accessibility; mitigated by large type and disclosure.

### [LOW] Offline behaviour automated only on Chromium
- Where: tests/test_pwa.py output; README "Known limitations"
- What: WebKit's Playwright harness errors on offline reload ("WebKit encountered an internal error"), so the offline flow is hard-gated on Chromium only, WebKit best-effort. Disclosed; reconfirmed in this round's suite run.
- Why it matters: The target platform is iOS/WebKit; its offline guarantee rests on platform behaviour, not a green check.

## What was checked
- Ran `python3 tools/validate_puzzles.py` (5 mini / 3 midi / 2 full, ALL PUZZLES VALID) and re-read the validator source: it genuinely enforces structure, ≥3-letter runs, interlock (every white cell in an across AND a down), connectivity, ≥11 rotational symmetry, numbering/answer/position agreement, in-puzzle duplicate and clue-contains-answer bans.
- Ran the full suite `python3 tests/run_all.py`: all five steps PASS (validator; all 10 crosswords solved end-to-end on WebKit/iPhone; deterministic 10-round map session with exact scoring, numeral-guard, kill-before-Next resume AND the new kill-after-final-round assertions; manifest/icons/SW/Chromium-offline; 16 screenshots regenerated). Zero console errors except the disclosed WebKit-offline harness noise.
- Wrote and ran independent Playwright probes (Chromium desktop + WebKit iPhone) for the paths the suite skips. Verified FIXED from round 5: final-round interrupt now offers "See your results (1090 pts)", delivers the summary and records stats; mid-round interrupt with hints resumes the same figure with both chips rebuilt, hint buttons disabled and the full penalty applied (+40 on 2 hints + 1 wrong); browser Back during the celebration hides the modal and no stale "solved" modal appears over the next puzzle; Backspace/letters with check sheet, confirm sheet or completion modal open in the crossword neither navigate (WebKit) nor leak into the grid; reveal-all completion shows "Filled in!" with no confetti and a "✓ time · revealed" list badge; revealed squares locked against overtyping and backspace; quit-confirm Cancel/Yes flows; "Play again" lands on Round 1 and stays there on both engines despite the async history.back()+pushState sequence; browser Back mid-session now shows a fresh Resume button (render() re-runs renderMapStart). Zero console/page errors in every probe.
- Found the two MEDIUMs above by probing the recovery path's alternative button (Start instead of See-results) and the one overlay exempt from the viewchange cleanup (#confirm-sheet, both Back and WebKit-Backspace triggers).
- Re-audited every clue and answer in all 10 puzzles as the pedantic professor, deriving answers from the grids. Re-checked this round's three edits (TREXARM wording, ESTEEM/dignitas, EXIT "pursued by a bear" — the Winter's Tale direction is "Exit, pursued by a bear", so the clue is exact) and spot-re-verified the obscurest dated claims (Order 227, Les Baux 1821, Tetris 1984, Safeco 1923, Spindletop 1901, AMA 1847/Medicare, 1800 tie, Nye Committee, Plessis-Praslin praline, core-rope ROM, one-term Adamses, $15M Purchase, 218 BC, She 1887, RICO 1970, Stamp Act 1765, Rae/Franklin, Saudi 1932, ATF/Prohibition, Hee Haw 1969, Enya 1988, Blues and Greens, Schubert 1824, PAC 1943, Cleveland/Harrison, Chirac 1995–2007, Suleiman "Lawgiver", Rousseau 1762, Tut 1922, NATO 1949, Dred Scott, Edy/Dreyer 1928, More/Utopia, Ascot 1711, bra 1914, NES 1985, L 1892, Emu War 1932, Versailles 1919, Fiona Macleod/Shrek 2001, Elsie 1936, Nantes 1598, Esau, Fleischer, ream 480, NBA 1946, MTV 8/1/1981, Great Game, Kilmer/Holliday, Streeter/Women Marines, Cellini, laser 1960, Cape Ann/Anne of Denmark, Leonowens, Moe Berg, Pascal/Cleopatra's nose, Pindar, Uma/Parvati, Bikini 1946–58, ANAKIN first spoken in ROTJ 1983, Air Cav, WTA 1973, Rubin Carter, Ogden "Junction City", Victoria/William IV, Han placement, Salem 1692, Edo 1868, Roman Empire ~5M km²). No factually wrong clue found.
- Verified all 30 figures in data/figures.json: exact 10/10/10 difficulty split; every name/variant set, occupation line, birth/death year (incl. BC signs and approx flags) and place-name-vs-coordinate plausibility (Ajaccio/Longwood −15.95,−5.69; Mvezo; Sancellemoz/Passy; Bergen-Belsen 52.76,9.91; Pella/Babylon; Libyssa/Gebze; Szigetvár; Fort de Joux; Werowocomoco/Gravesend; Sines/Kochi; Marton/Kealakekua; Kesh/Otrar; Stettin/St Petersburg; Caracas/Santa Marta; and the rest) — no errors.
- Read all UX code (index.html, css/style.css, js/app.js, crossword.js, mapgame.js, match.js, storage.js, sw.js, manifest.webmanifest) against every spec item, including the new history-sync back(), session cur-state persistence, assisted flag plumbing and overlay resets.
- Inspected all 16 freshly regenerated screenshots: home/dateline correct for today, list states, mini/midi/full renders, clue list, check/reveal sheet, "Bravo!" modal, map start/round/hint/correct/wrong/revealed/summary (395 = 75+100+110+110 checks out), desktop layout — all clean, no placeholders or dead ends visible.
- Checked manifest (standalone, portrait, full icon set incl. maskable), PNG icon dimensions byte-level (32/180/192/512/512), and the service-worker precache list against the file tree (all runtime assets covered; assets/icon.svg is build-source only).
