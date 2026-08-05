# HOUSE RULES — Daniel's standing content rulings

Every ruling Daniel has made about content, distilled to be applied to ALL
future content — not just the batches he audited by hand. Each rule is
tagged **[ENGINE]** (a tool enforces it mechanically — the tool is named)
or **[JUDGMENT]** (whoever curates applies it; the review sheet is the
check). When a new audit produces a new ruling, it gets added HERE in the
same session — this file is why his feedback compounds instead of
evaporating.

Last updated: 5 Aug 2026 (navigation contract; install flow).

## Navigation (the way back)

- **[ENGINE]** **The navigation contract (Daniel, 5 Aug 2026):** every
  surface except Home carries exactly one always-visible way back, top-left,
  in the house ‹ chip language, reachable without scrolling. Moment screens
  comply via their centred Home CTA above the fold. Enforced by
  `tests/test_no_dead_ends.py`. Why it is a rule and not a habit: the app is
  deliberately hub-and-spoke (Home is the hub; no menus, no tab bar), so a
  screen without a chip is a trap, not a minor omission — two shipped that
  way inside a fortnight (the intro overlay, the reading pages) before this
  was written down. The test walks every view, the intro overlay in both its
  modes, the sheets, the moment screens, the reading pages and 404, and fails
  CI on any dead end.
- **[JUDGMENT]** Sheets and overlays (archive picker, carry, confirm) are not
  surfaces and do not get a chip — they get an explicit Close, above the
  fold, that returns to the surface underneath. Nothing that opens over a
  view may be dismissable only by tapping outside it.

## Save it as an app (the install flow)

Daniel's rulings, 5 Aug 2026, from the signed-off plan. Built in `js/install.js`;
`tests/test_install.py` is the check on all of it.

- **[JUDGMENT]** The promise is universal and vague-but-true: "a streak that
  lives in a browser can die in a browser". **No per-browser deletion claims** —
  the seven-day rule is Safari-only, and Chrome and Firefox delete nothing, so a
  named claim is a lie somewhere. The locked body copy is the whole argument.
- **[ENGINE]** **No pointing arrows at browser chrome.** A page cannot know
  where the browser put its own buttons (iOS 26's Compact layout hides Share
  behind •••; Chrome 138 can move its menu to the bottom), and an arrow at empty
  space is worse than no arrow. Teaching is done with **drawn replicas** of the
  real buttons instead.
- **[ENGINE]** **The replica outsizes the words.** Body copy is 15px; every
  replica glyph is ≥40px tall, so the eye lands on the shape it is hunting.
  Enforced by `test_install.py::screens_render`.
- **[JUDGMENT]** Instructions must match the verified flow on the browser in
  hand, and hardcode nothing undetectable: iOS share-sheet rows are **icon-left,
  label-right** (`[+] Add to Home Screen`, reached via **View More** and a
  scroll); Chrome-on-iPhone's door is **Share, top right** — with the explicit
  warning **"not the ⋯ at the bottom"**; Chrome on Android hardcodes no menu
  label at all.
- **[ENGINE]** Timing: the ask comes after **2 completed games** (any mix;
  a daily AND an Encore both count), never mid-round. Declined → one quiet strip
  at the top of Home; strip × → **one** final ask the day a streak reaches 7,
  then silence forever. An installed app is never asked anything.
- **[ENGINE]** In-app browsers (Instagram/Facebook/TikTok and friends) get the
  **escape page** after **1 completed game**, at most twice — installing is
  impossible in there and the record dies with the app. Instagram's menu label
  is **"Open in external browser"**, verbatim, verified on Daniel's phone; every
  other app keeps flexible phrasing. A guaranteed **COPY THE LINK** button is
  the fallback, because escaping a webview cannot be scripted in 2026.

## Scheduling (the day compiler)

- **[ENGINE]** 3 rounds per game per day, exactly one easy/medium/hard;
  Thread tier by weekday (Mon/Tue easy, Wed/Thu medium, Fri–Sun hard).
  `compile_editions.py` recipe.
- **[ENGINE]** The week gets harder INSIDE each tier (Monday = the tier's
  most famous end, Sunday = its deeper half, never its dregs). Weekday
  ramp in `compile_editions.py`.
- **[ENGINE]** Repeats: hard floor 42 days, target 60, per SUBJECT across
  all games. (30 Jul research: one-viewing picture recognition survives
  weeks — Shepard 1967, Standing 1973 — and a solved round is retrieval
  practice on top; 42 keeps repeats out of "oh, this again", 60 lands in
  pleasantly-half-forgotten. Every tier pool holds 97+ items so this
  cannot starve a tier.) `repeat_floor_days`/`repeat_target_days`.
- **[ENGINE]** Launch blindfold: editions before launch_edition (42)
  constrain nothing.
- **[ENGINE]** Adjacent-day nets: no candidate whose name/variants/tiles
  overlap yesterday's or tomorrow's answers.
- **[ENGINE]** Tone: at most 1 dark-tone subject per issue (curated tag
  list in editions.config.json is the place to disagree).
- **[ENGINE]** Rulers/statesmen/commanders may fill up to ~2/3 of an
  issue's human slots (0.67; owner 30 Jul: "up to six out of ten is fine
  — those are the people history buffs know"). ANY OTHER occupation
  family may appear at most ONCE per issue: two rulers read as classic
  history, two philosophers read as a theme issue nobody asked for.
  `max_power_share_per_issue` / `max_nonpower_family_per_issue`.
- **[ENGINE]** Western-first (owner 30 Jul: "an app for Westerners first
  and foremost — those are the people I'll be marketing to"): the
  Western-recognisability bias applies to EVERY slot including hard and
  Sunday. Per-item waiver: fame ≥ icon threshold pays no penalty, so
  Genghis Khan and Angkor Wat still anchor hard days. Deep non-Western
  cuts are for curated moments, not weekly slots.
- **[JUDGMENT]** Variety beats gender-balance: optimise subject-matter
  spread (era, region, occupation, object kind); never cast to a quota.
  But the launch pattern holds: a woman's face early in any showcase
  window reads right — day 1 got Ada Lovelace by name.
- **[JUDGMENT]** Rolling kind variety: not two of the same relic KIND
  close together ("too many temples lately", "too many diamonds", two
  ships back-to-back). No mechanical check yet — the tags are too coarse
  (TODO below); catch it on the review sheet.

## The 3-choice clue (the "ultimate clue")

- **[ENGINE]** The trio never names a same/adjacent-day answer; no two
  rounds on one day share an option. `build_mcq.py` + `--check` in CI.
- **[ENGINE]** Era, gender and photograph-vs-painting must match; fame
  similar-or-higher than the answer.
- **[ENGINE]** Holistic gates (owner 30 Jul: "is it incredibly easy to
  guess which one is right? Then it fails — those 20 points should feel
  earned"): a face or journey from one part of the world never gets two
  options from another ("don't give an Asian man Leonardo and a U.S.
  president"), and an object never gets options from a different physical
  class ("a pendant never gets the Sphinx"). Region/kind buckets in
  `build_mcq.py`; relaxations are logged and surface in
  `tools/out/mcq-trio-report.md` (run with `--report`).
- **[ENGINE]** Curated picks live ONLY in `tools/fame/mcq_overrides.json`
  — they beat the generator, survive every re-run, and are validated
  against the schedule. Never hand-edit `mcq` fields in data files.
- **[JUDGMENT]** After any schedule change, skim the trio report's
  flagged rows. Known trap: region tags follow birthplace, so Tolkien
  reads "African" (Bloemfontein) and Mercury "African" (Zanzibar) —
  famous misfits get overrides.

## Thread boards

- **[JUDGMENT]** Build to the NYT grammar — full rubric + per-board
  verdicts in `connections_audit.md`: phantom categories, polysemy,
  uniform tile surfaces, binary membership, one structural-twist group,
  difficulty from ambiguity not obscurity. Fake-fives (a tile that fits
  two labels but resolves uniquely by elimination) are the mechanic, not
  a bug.
- **[ENGINE]** Self-labeling groups (tiles repeating a label word — "First
  Crusade" under a Crusades label) are flagged by `validate_boards.py`.
- **[JUDGMENT]** Category claims must be undisputable. Weird is fine if
  binary ("years ending 89"); vibes are not ("denounced as a menace").
- **[JUDGMENT]** Every new board gets a Fable-tier review before it's
  schedulable (intake pipeline), and external-critic suggestions must be
  checked against the SCHEDULE before adoption (a proposed tile can
  collide with a nearby answer).

## Face Value / Relic rounds

- **[JUDGMENT]** Tier by LIKENESS recognisability, not name fame — Ada
  Lovelace is a famous name with a hard face. Fame ≠ face recognition.
  (TODO below: recognisability score.)
- **[JUDGMENT]** The opening scrap must be fair for the tier: easy rounds
  open near the money shot, hard rounds may not — but never a scrap of
  irrelevant background ("random buildings"). New items run
  `tools/audit_start_scraps.py` before first staging; explicit `start`
  overrides are the owner's word and survive image swaps only if re-aimed.
- **[JUDGMENT]** The image IS the puzzle: the subject must dominate the
  frame (crop to the person if the source shows a crowd), no blur, the
  iconic view over the clever one. Rights recorded via
  `tools/fetch_commons.py` + `audit_rights.py`, w800 rebuild after swaps.
- **[ENGINE]** The dual-licence Commons trap (31 Jul 2026 audit): Commons
  files often carry one licence for the THING (public domain statue) and
  another for the PHOTOGRAPH (CC BY/BY-SA). The API's `LicenseShortName`
  collapses the pair to the PD half — never trust it; read the file page's
  own licence templates. `tools/validate_reveal.py` now ERRORs on any
  CC BY/BY-SA record missing `image_license_url` or an author, because the
  in-app ⓘ drops the photographer's name without both. This shipped 16
  broken credits before it was caught.
- **[JUDGMENT]** Subject copyright is separate from photo licence: an
  in-copyright statue or building (France/Russia/Denmark-class, no
  commercial freedom of panorama) cannot be a reveal subject when the work
  is the chief motif — no Commons licence can clear it, and OUR crop can
  destroy a de-minimis defence the original framing had (Centre Pompidou,
  31 Jul). Commons `NoFoP-*` tags catch some; only looking at the picture
  catches the rest. Retired under this rule: little-mermaid-statue,
  centre-pompidou, motherland-calls, louvre (all `reserve: true`).
- **[JUDGMENT]** Name-on-artefact caps the tier at easy: mid-round zoom is
  4×, so painted/carved lettering that spells the answer (or an accepted
  variant) is readable once its scrap tears. A label you can find by
  playing is a fine EASY mechanic and a broken MEDIUM (Cutty Sark's bow,
  31 Jul — held out of ed 45 for this; retier before staging her).

## Casting and tone

- **[JUDGMENT]** Audience bar: Rest-is-History listeners. Easy ≠ dumbed
  down, hard ≠ academic. No living politicians as answers. Entertainment
  faces are fine as easy anchors (Mercury, Pelé, MJ) but never the
  majority of a day.
- **[JUDGMENT]** Blurbs and facts: dark wit welcome, claims must hold to
  a pedant's reading ("coined" vs "made famous"; Josephus predicted
  VESPASIAN would be emperor, not himself). When a critic softens a label,
  keep the voice, fix the claim.

- **[ENGINE]** Moratorium list (Daniel, 5 Aug 2026): **Adolf Hitler and
  Osama bin Laden are out of rotation until further notice** — too sensitive
  for the launch window. Mechanism: `"reserve": true` on their entries in
  `data/figures.json` (both) and `data/reveal-who.json` (bin Laden) — the
  compiler excludes reserved items from every future proposal and Encore
  skips them at runtime; aired editions (2, 3, 37) stay frozen history and
  age out of the archive on schedule. Not deleted — lifting the moratorium
  is deleting two `reserve` flags. Judgment note: their names may still
  appear as MCQ wrong-answer options in other figures' puzzles — flagged to
  Daniel 5 Aug, default is to leave those.

## Standing TODO (rails not yet built)

1. Recognisability score for Face Value tiers, seeded from the ~90 tier
   verdicts in the 30 Jul audit; proposer uses it instead of raw fame for
   who-tier placement; outliers surface for the owner instead of staging
   silently.
2. Finer object kinds (temple/castle/diamond/ship…) so rolling kind
   variety can be machine-checked.
3. Per-item `start_audited` date so the intake gate on opening scraps can
   be mechanical instead of a checklist item.
