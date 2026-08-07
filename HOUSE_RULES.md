# HOUSE RULES — Daniel's standing content rulings

Every ruling Daniel has made about content, distilled to be applied to ALL
future content — not just the batches he audited by hand. Each rule is
tagged **[ENGINE]** (a tool enforces it mechanically — the tool is named)
or **[JUDGMENT]** (whoever curates applies it; the review sheet is the
check). When a new audit produces a new ruling, it gets added HERE in the
same session — this file is why his feedback compounds instead of
evaporating.

Last updated: 5 Aug 2026 (navigation contract; install flow; the rescue
closes the shop; the letters page).

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

## The letters page (player feedback)

Daniel's rulings, 5 Aug 2026 (design-reviews/install-flow-rulings.md
"FEEDBACK PLATE", overriding the 4 Aug feedback-plan wherever they differ).
Built in `js/feedback.js`; `tests/test_feedback.py` is the check.

- **[JUDGMENT]** **Feedback is furniture, not an interruption.** It lives
  only where the player has stopped playing — the foot of Home, the day-done
  screen, the foot of Your Legacy, the footer, About. Never on a play
  screen, never a modal/toast/badge, and nothing ever has to be dismissed.
- **[ENGINE]** **One honest gate, nothing else:** the Home plate stays
  hidden until the player's FIRST ever finished daily, then shows forever.
  No time or visit counters (they would mute launch week), no nag state, no
  suppression after writing (with no backend, "already wrote" would be a
  guess). `test_feedback.py::plate_hidden_until_first_daily`.
- **[JUDGMENT]** The approved plate (mock D): letters-column masthead rule
  (thick over thin), magenta LETTERS TO THE EDITOR kicker, headline **"Got
  opinions? Write in."**, and a **CYAN Antinous definitive stamp** —
  perforated edges, denomination = the LIVE issue number, circular postmark
  carrying the ACTUAL current date + YESTERNERD. British definitive-stamp
  language; **no envelope, no US iconography**. The earlier red "Complaints
  Dept" plate direction is dead for Home.
- **[ENGINE]** **"Tell us where it hurts" belongs to the win-screen rubber
  stamp only** (the day-done Complaints Dept card; the obituary face asks
  "Any last words?" instead). It must not appear on the Home plate.
  `test_feedback.py::plate_links_and_stamp` /
  `::daydone_card_both_faces`.
- **[ENGINE]** **What travels with a letter:** the Google Form link
  pre-fills ONE field — app version + coarse device family (e.g.
  "v182 · iPhone"), URL-encoded. No scores, no answers, no identifiers.
  Offline, every surface swaps to the mailto fallback (subject = build +
  surface, body = the same device line) and says so. GoatCounter records
  the TAP only (6f family; the mailto tap is counted apart so form-tap
  numbers stay honest).
- **[JUDGMENT]** **The corrections lane stays separate:** the per-round
  "Report a problem" mailto keeps carrying the content ID — never fold it
  into the form, or a wrong date stops being findable.

## Clue pricing (what a round is worth, and what it costs)

Daniel's rulings, 5 Aug 2026, from the restrained direction in
`design-reviews/clue-pricing-2026-08-05/`. Built in `js/revealgame.js` and
`js/mapgame.js`; `tests/test_smoke_core.py::clue_prices_are_true` is the check.

- **[ENGINE]** **No control may quote a price the floor would swallow.** A
  correct answer never pays under 10, so "−25" stops being true near the
  bottom. Every price is derived from `worthNow()` at paint time and flips to
  the honest outcome — `· LEAVES 10` — the moment the whole deduction can no
  longer come off. The three-choices rescue never quotes its nominal −80 at
  all: it always says what it LEAVES (20 on an untouched round, 10 after any
  spending). This is why the old "3 CHOICES −80" had to go — on a 65-point
  round it was simply a false number.
- **[ENGINE]** **One price, in one place, once.** The tear price lives on the
  worth line (it is the only cost paid without pressing a control); every
  other price lives on the control that charges it. At the floor the worth
  line reads `WORTH: 10 PTS · MINIMUM`.
- **[JUDGMENT]** **Prices are RED** (Daniel, 5 Aug 2026, overruling a proposal
  to make ordinary prices black): the red minus is what says "this is a cost".
  Outcomes — `LEAVES 10`, `MINIMUM` — are not prices and stay ink.
- **[JUDGMENT]** **The wrong-guess price rides on the Guess button**: "IF
  WRONG −15 PTS", Daniel's wording, with the "if". It is the one cost a player
  can incur without any warning at all.
- **[ENGINE]** **A bought clue replaces its own control, in the same slot.**
  Never a greyed-out button plus a duplicate yellow answer somewhere below it.
- **[ENGINE]** **The rescue closes the shop** (Daniel, 5 Aug 2026 — the exploit
  found during the clue-pricing work). Opening "3 choices" drops the round to
  its 10-point floor, so from that moment every other clue and (in Face
  Value/Relic) every further tear costs exactly nothing. So buying the rescue
  LOCKS them: the remaining clue slips go out of service in the house
  `.pill:disabled` treatment and stop quoting prices they can no longer charge,
  and the scraps lock in the same dashed-out state an adjacency-blocked scrap
  already uses. The picture freezes exactly where the player paid to leave it —
  everything torn stays torn and stays zoomable, so the player can still LOOK
  while choosing; they just cannot buy more looking. Two reasons, not one:
  offering a price that cannot be charged is the same lie the rest of this
  section exists to stop, AND a free full reveal would turn a three-way gamble
  into a certainty (a name carved on an artefact is readable at the mid-round
  4× zoom — see the name-on-artefact rule below), which contradicts "those 20
  points should feel earned". Nothing about scoring changed: an honest player's
  round pays exactly what it paid before. Checked by
  `tests/test_smoke_core.py::rescue_closes_reveal` and `::rescue_closes_map`.
- **[JUDGMENT]** **The introduction teaches the model, not the tariff.** One
  sentence — "Each round starts at 100 points. Tears, clues and wrong guesses
  lower what a correct answer is worth, never below 10." (Lifeline drops
  "Tears".) Individual prices, the rescue, streak bonuses and the round-average
  belong where they become relevant, or on `how-to-play.html`. Do not let the
  intro drift back into a price list.
- **[JUDGMENT]** **One label across all three guessing games: WORTH.** Relic's
  "INK" made the same number look like a different currency.
- **[JUDGMENT]** Explicitly NOT built, and not to be revived: scoring panels,
  numbered rules, split answer-value/next-tear cards, permanent right/wrong
  hypotheticals, ledgers, receipts, price tags, PAID stamps, purchase
  confirmations, red warning borders on the rescue.

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

- **[ENGINE]** The shop-window face (6 Aug 2026): **Frida Kahlo is out of
  rotation.** Her portrait is the demo board on the stranger's Home
  (`assets/brand/demo-facevalue.webp`), so it is on permanent public
  display — and a face we advertise must never also be a live puzzle.
  Mechanism: `"reserve": true` on her entry in `data/reveal-who.json`.
  She aired in editions 2 and 22 and was staged nowhere in 39–71, so this
  cost the schedule nothing. If the hero ever shows someone else, move the
  flag with the picture (regenerate via `python3 tools/make_demo_shot.py`).
  **Gotcha, learned the hard way:** the live pools the app AND the compiler
  read are `data/reveal-who.json` / `data/reveal-what.json`.
  `data/reveal.json` is the pre-split file from before "Zoom In split" and
  is read by nothing but the workshop review page — a `reserve` flag set
  there does nothing at all, silently, and the compiler will happily
  schedule the item anyway.

- **[JUDGMENT]** Marketing does not edit the pool's pictures (7 Aug 2026).
  The Home hero crops a quarter of one board out of one photograph, so it
  runs out of pixels long before a full-board round does. The fix is a
  SECOND copy, for the hero only: `tools/demo-source/frida-kahlo-commons.jpg`
  (1197x1795, the same public-domain Guillermo Kahlo print of 16 Oct 1932,
  Commons `File:Frida Kahlo, by Guillermo Kahlo.jpg`, retrieved 7 Aug 2026;
  same framing as the round's copy to within JPEG noise). It lives under
  `tools/`, which `_redirects` 404s, and `tools/make_demo_shot.py` serves it
  to the board at render time. **The round's own `assets/img/frida-kahlo.jpg`
  is left alone** — content curation owns the pool's images, and a hero
  re-shoot must never be the reason one of them changes underneath a round.
  Same rule for any future hero subject: new demo source beside that one, not
  a replacement in `assets/img/`.

- **[JUDGMENT]** The advertised face has to be nameable (Daniel, 7 Aug 2026).
  Shown three openings side by side he took **the brows meeting, with both
  eyes in the square** (`brow-join-wide` in `tools/make_demo_shot.py`) over a
  single brow-and-eye. The test is not "is this a face" but "can a newcomer
  name her from this" — so the opening scrap must land on whatever is
  singular about the person, not merely on a well-exposed piece of them. The
  two rejected framings stay in the tool's COMPOSITIONS dict as the record of
  the comparison; neither ships again without a fresh decision.

## Standing TODO (rails not yet built)

1. Recognisability score for Face Value tiers, seeded from the ~90 tier
   verdicts in the 30 Jul audit; proposer uses it instead of raw fame for
   who-tier placement; outliers surface for the owner instead of staging
   silently.
2. Finer object kinds (temple/castle/diamond/ship…) so rolling kind
   variety can be machine-checked.
3. Per-item `start_audited` date so the intake gate on opening scraps can
   be mechanical instead of a checklist item.
