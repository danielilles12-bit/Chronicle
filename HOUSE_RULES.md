# HOUSE RULES — Daniel's standing content rulings

Every ruling Daniel has made about content, distilled to be applied to ALL
future content — not just the batches he audited by hand. Each rule is
tagged **[ENGINE]** (a tool enforces it mechanically — the tool is named)
or **[JUDGMENT]** (whoever curates applies it; the review sheet is the
check). When a new audit produces a new ruling, it gets added HERE in the
same session — this file is why his feedback compounds instead of
evaporating.

Last updated: 9 Aug 2026 (the issue number stopped facing players — the date
replaces it everywhere; Encore deleted; every clue control quotes its true
cost; the rescue asks once per game before it fires; blurbs capitalised after
the middle dot; Home stopped narrating state and started drawing it — one
marker per puzzle).

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
- **[JUDGMENT]** Sheets and overlays (carry, confirm, the intro card) are not
  surfaces and do not get a chip — they get an explicit Close, above the
  fold, that returns to the surface underneath. Nothing that opens over a
  view may be dismissable only by tapping outside it.

## The Archive (Daniel, 7 Aug 2026)

Replaced the calendar "Morgue", the per-row Back-issues bar, the per-row
M–T–W–T–F–S–S week strip, and the old Encore. One word for the whole feature
in player-facing copy: **Archive**. "Back issues" and "the Morgue" are retired.

- **[ENGINE]** **The window is today plus the six editions before it, floored
  at the launch edition.** In `js/daily.js`: `ARCHIVE_FLOOR = 42`,
  `ARCHIVE_SPAN = 6`, `first = max(FLOOR, today − 6)`, `last = today − 1`,
  newest first, empty when `first > last`. Verified arithmetic: an edition
  airs on EPOCH + n days, and 2026-06-29 + 42 days = **Monday 10 August 2026**,
  launch day. Enforced and worked through five dated examples by
  `tests/test_archive_window.py`.
  Why six: content repeats on a 28–42 day gap, so a deeper archive would start
  showing material already scheduled to come back. Why a floor: editions 24–41
  aired before launch and are not launch quality — no player may reach one.
- **[ENGINE]** **The window is a hard access guard, not a drawing rule.**
  `daily.canPlayEdition(n)` is asked by the function that LAUNCHES a daily —
  `startRevealDaily`/`startMapDaily`/`startThreadDaily` and `app.js`'s
  `launchEdition` — not only by the code that decides which cards to render. A
  stale card tapped across a midnight rollover, a hand-typed edition, or a
  slow download that straddles midnight all fail closed and land on a
  repainted Home. This is the CLAUDE.md "no casual path to unaired content"
  rule made mechanical.
- **[JUDGMENT]** **Home is the only door.** Each game's row is one horizontal
  scroller: today's hero card, then the reachable past days to its right,
  newest first, each showing that game's result for that day. Tapping one goes
  straight into that game, that day — no calendar, no "which game?" picker.
  A past-day card reads weekday · date and then DRAWS its state in the same
  marks the hero card above it uses (see "One marker per puzzle" below) — it
  prints no status word at all. The words it used to print died in two steps:
  "Untouched" on 7 Aug 2026 (the same cold word on screen 24 times at once),
  then `N pts` and `Resume` on 9 Aug. Screen readers still get the whole state
  via the card's aria-label, where a silent card would be ambiguous rather
  than restful. The cards are 124px tall against the hero's ~173px: torn-off
  stubs, not cards that failed to fill.
- **[JUDGMENT]** **The Archive is regulars' furniture.** A newcomer (no
  completed daily) sees no day cards at all, the same call that already hides
  the punch card — their screen sells one game and nothing else.
- **[ENGINE]** **An archive play is a real daily.** It launches as the daily
  for that edition, writes a normal ledger entry, and shows up in the Ledger.
  It does NOT loosen streaks: `isStreakValid` still requires completion within
  two days of the air date, so a play from four days back records a score and
  revives nothing. That rule is untouched and must stay untouched
  (`tests/test_daily_flow.py: daily_lock_and_repair`).
- **[JUDGMENT]** Unscored "practice" loses its last player-facing route with
  the calendar, and that is intended — a past day being playable AND scored
  serves the same want better. The engines keep their practice support; only
  the routes are gone.
- **[JUDGMENT]** **A finished day opens its result, read-only, AND SHOWS THE
  SOLUTION.** The receipt says what you scored; the plates under it say what
  the answers were. Per game: Face Value and Relic show the fully uncovered
  image (in the same duotone the live reveal applies, because the credit line
  says "duotone") plus its blurb and the discreet ⓘ credit; Lifeline shows the
  map with both pins plus name, occupation and fact — `data/figures.json`
  carries no image for any of its 541 entries, so a portrait is impossible
  without a separate content-and-rights project; Thread shows the solved board
  in its four colours with its labels and title, and no fact line (boards
  carry none). The round list is rebuilt from `getEdition(game, n)` — the
  manifest is the record of what aired — never from the ledger entry.
- **[ENGINE]** **Encore is gone** (Daniel, 9 Aug 2026 — reverses CLAUDE.md
  locked decision #6, which had itself rewritten the feature on 7 Aug). A
  finished daily's summary offered "Encore: Sunday ›", another day of the SAME
  game. The behaviour worth encouraging is the opposite one: *"move on to the
  next puzzle of the day."* Anyone who wants more of one game reaches it from
  that game's row on Home — which is what the Archive is for. A summary now
  ends with **Play the next puzzle** (or **Call it a day** once all four are
  played), **Share**, and **Home**, and nothing else. `encoreEdition`,
  `startEncore`, `wireEncore`, the three buttons and the four `encore-*`
  analytics events are all deleted, not hidden.
- **[ENGINE]** **One marker per puzzle** (Daniel, 9 Aug 2026 — REPLACES the
  7 Aug rule "'Resume today's puzzle', not 'In progress'", and the day cards'
  `N pts` / `Resume` with it). Home stopped saying where you are and started
  showing it. Three status sentences in two different dialects — `Done · 33
  pts` and `Resume today's puzzle` on the big cards, `N pts` and `Resume` on
  the stubs directly beneath them — were shouting over the game names they sat
  under, and the two sizes of card did not even agree with each other. One
  drawn language now, identical at both sizes, ink only, always secondary to
  the name and the one-liner:
  **●** a puzzle finished · **◐** the puzzle you are inside · **○** not
  started · **›** there is still play to do · **✓ 33 PTS** finished, and what
  it paid. A chevron never appears on a finished card; a finished card never
  greys out, and still opens its own read-only result. **The chevron sits
  beside the marks, not at the far end of the row** (Daniel, 9 Aug 2026):
  parking it right looked deliberate on a three-round game and left Thread's
  single ◐ stranded 105px from its own arrow. The state reads as one cluster
  at any count, on the big cards and the stubs alike.
  **THE COUNTING RULE, which is the whole point:** one marker per ACTUAL
  puzzle. Face Value, Lifeline and Relic run three rounds a day and show
  three. **Thread is ONE puzzle and shows ONE.** Its four groups and its four
  allowed mistakes are the inside of that puzzle; four markers on Home would
  be a false promise about how much is left, so `found`, `mistakes`, groups
  and guesses are deliberately never read by the card. Marks come from the
  REAL saved session and nothing is inferred.
  Written state survives in exactly two places: the card's aria-label, which
  carries the whole thing in words because every shape is `aria-hidden`
  ("Face Value, in progress, two of three rounds completed, resume"); and the
  transient load/error line ("spinning up the presses…", "couldn't load — tap
  to retry"), which is the one thing a card is still allowed to say out loud.
  **BOTH HOMES, one language** (Daniel, 9 Aug 2026, the same day): the
  newcomer's three compact cards were held out of this for one release, and
  that left the app with two dialects and a player crossing between them the
  moment they finished their first daily. They now draw the same marks one
  size down, and "Resume today's puzzle" — the last status sentence anywhere
  on Home — is gone with them. A newcomer can only ever reach two of the
  three states, because finishing a daily is what ends stranger mode.
  `tests/test_home_card_states.py` and
  `tests/test_stranger_home.py::in_progress_draws_on_a_newcomers_card` are the
  checks; the gold and forest state tints went with the sentences they
  used to tint, and `row-progress`/`row-done`/`day-done` survive only as
  hooks for the day stub's left-edge tint.
- **[ENGINE]** **The marks must fit inside the picture's height.** The hero
  card's bottom row exists inside the 136px the illustration already occupies
  (12px row, 4px gap, against Face Value's ~17px of headroom), because a
  taller card is a card its own art no longer fills. Guarded from three
  directions: `tests/test_stranger_home.py::home_card_status_and_icons`,
  `tests/test_archive_window.py::day_card_shape`, and
  `tests/test_home_card_states.py::archive_shape_survives`. Anything new on
  that row has to buy its space from that budget, not from the card's height.
- **[ENGINE]** **A card may never eat a word of its own description**, and the
  narrowest phone is where it tries to. The tagline cap went from three lines
  to FOUR on 9 Aug 2026 (`.game-row.has-days .hero-tagline`, `max-height:
  5.6em`): the longer Relic and Thread lines Daniel wrote that morning wrapped
  to a fourth line at 375px and lost "landmark." and "connection." to the old
  cap — invisible at the 390px every other test measured, and it would have
  shipped. Four lines still fit the picture's height budget above. The check
  is `tests/test_stranger_home.py::taglines_survive_the_narrowest_phone`,
  which runs at 375 AND 390 and asserts nothing is clipped and the words never
  stand taller than the art. New copy that needs a fifth line needs shorter
  copy, not a taller card.

## The masthead (Daniel, 9 Aug 2026)

- **[JUDGMENT]** **The newcomer gets a nameplate slogan.** Under the wordmark,
  above the dateline: *"Four daily history games. Same set for everyone."* —
  one line telling someone arriving cold what the whole thing IS, in the
  newspaper's own place for it. Shown ONLY in stranger mode: a returning
  player knows what the app is and does not need telling every morning.
  Each sentence is one unbreakable unit, so a narrow phone breaks the line
  between them rather than mid-clause.
- **[ENGINE]** **Everything in the masthead starts on one margin.** The
  wordmark PNG carries 75px of transparent gutter down its left edge (3.85% of
  its width), so the visible Y used to land 6–10px right of the slogan and the
  dateline stacked under it — a wobble, not a margin. `.masthead-wordmark`
  pulls it back by exactly that fraction of whatever width the clamp resolves
  to, so it holds at every screen size. If the wordmark is ever re-exported,
  re-measure the gutter: `tests/test_stranger_home.py::
  the_masthead_stacks_on_one_margin` reads it straight off the asset and fails
  if the CSS no longer matches.

## The date, not the issue number (Daniel, 9 Aug 2026)

- **[ENGINE]** **Nothing a player reads says "№ 71" any more.** Daniel watched
  friends play and none of them knew what the issue number meant. `№` is gone
  from the masthead (now `9 AUG ’26 // SUNDAY`), the four Home cards, the
  first-run Play button, all three game receipts, the letters stamp, the
  Ledger's "in the making since" line, the day-done screen and every share
  headline (`FACE VALUE 9 Aug 2026 🖼️`). The edition index is still the app's
  internal spine — it just never faces a player. One helper does the words:
  `daily.editionDateLabel(n)` — **"9 Aug ’26", a two-digit year with a
  typographic apostrophe** (Daniel, same day, after seeing the full year wrap
  the masthead onto two lines with the "//" left dangling at the end of line
  one). One format on every surface, so no two write the same day differently.
  The masthead can still wrap on the narrowest phones or the longest weekdays;
  `// WEDNESDAY` is bound together (`.dateline-day`) so when it does, the
  slashes go with the day they introduce and the break reads as designed.
- **[ENGINE]** **No `№` faces a player anywhere now.** The last one was the
  streak milestone postmark, which read "№2 / days running" — and it was also
  the last place the app called a streak anything other than an "N-day
  streak". Both went the same day (Daniel: *"I prefer the 2-day streak
  wording"*): the stamp reads **2 / DAY STREAK**, matching the punch card, the
  streak-rescue line and every share. The only `№` left in the codebase is a
  joke inside the letters stamp's address — "Complaints Dept · Desk № 1" —
  which is a desk, not an issue.
- **[JUDGMENT]** **The Home cards carry no bottom line of WORDS.** It held the
  issue number and a "~3 min" estimate; both went that morning, and the row
  with them. A bottom row came back the same day to hold the state marks and
  nothing else (see "One marker per puzzle" above) — no issue number, no time
  estimate, no date, ever again. A card is its name, its one line, its
  picture, and how far you have got.

## Sharing (what a share actually is)

Daniel's ruling, 7 Aug 2026. It had been agreed verbally before and was never
written down here — which is exactly why the app drifted back to shipping a
picture. Written down now. Built in `js/sharecard.js`;
`tests/test_share_text_only.py` is the check on all of it.

- **[ENGINE]** **A share is text and emoji only, ending in the link.** Written
  results + the emoji result rows + `https://yesternerd.app/…`. **No generated
  image, ever.** The canvas "receipt card" (a 1080×1350 PNG with wordmark,
  Antinous sticker, big score and stamp) was deleted on 7 Aug 2026 along with
  its brand-image preloading and all file/blob plumbing.
- **[ENGINE]** **No share path may attach a file.** `navigator.share` is only
  ever called with `{ text }` — never `{ files }`, and `navigator.canShare` is
  not consulted at all. Enforced by `tests/test_share_text_only.py`, which
  covers all four games plus the full-house and obituary screens.
- **[ENGINE]** **The clipboard fallback stays.** Where the Web Share API is
  missing, the same text is copied and the button says
  **"Copied — paste it anywhere"** (failure says "Sharing unavailable here").
- **[ENGINE]** **The emoji result rows are the point** and are untouched —
  Thread's colour grid, Lifeline's ✅/🧭/⚰️ row, Face Value / Relic's 🟩/🟨/🟥
  row. Pure colour squares in the shared text, Wordle-family convention; the
  in-app colourblind glyphs stay in-app.
- **[ENGINE]** **Every share ends with the link, and the link carries the
  dare** (Challenge Rally, 19 Aug 2026): a per-game share links its landing
  page — `/play/<face-value|lifeline|relic|thread>?e=<edition>&s=<score>`
  `&ref=share` — whose static og: tags give chat apps that game's own
  preview card (Build 2; the four GPT cards, used as delivered). The page
  bounces humans into the app with params preserved; old `?play=` links
  keep working. The recipient opens the exact challenged day while it is
  reachable — `e` is clamped through `daily.canPlayEdition`, so an expired
  day bridges honestly to today and a sender past their own midnight can
  never unlock unaired content. A full-house share names no game (`e`+`s`
  alone) and lands as the taunt strip on Home ("Someone thinks they're
  smarter than you…" — Daniel's line); an exact-day dare is remembered all
  day (`misc.dayChallenge`, sittings apart) and the celebration answers it
  with the /400 verdict and "Send your score back ›". Params are plain
  and validated, never trusted (no signing — the discarded X1 card stays
  discarded).
- **[ENGINE]** **Challenge-first framing everywhere** (19 Aug 2026): buttons
  say **"Challenge a friend"** (working copy); a summary reached from a
  challenge link says **"Send your score back ›"**, shows the verdict line
  (their score · your score) and counts as `sendback`, not `share`. Scores
  read over their maximum — `87/100`, full house `N/400` — in strips,
  stamps, verdicts and share text alike ("87 to beat" sounded like 87
  people). In-game surfaces built earlier (worth line, Home card states)
  keep their `pts` wording until the copy pass rules on them.
- **[ENGINE]** **The stranger-first share text (Daniel, 21 Aug 2026).** Most
  recipients have never seen the game, so every share opens with one plain
  sentence they can act on — it names the game, names Yesternerd, and gives
  the score: *"I just played Relic, one of Yesternerd's daily history games,
  and got 64/100."* (full house: *"I just played all four of Yesternerd's
  daily history games and got 269/400."*). Then the emoji row bare, then the
  dare (**"Think you can beat me?"** / **"Think you can beat my total?"**),
  then the link. Ruled OUT of the text, deliberately: the **date** (the
  recipient can't use it before tapping; the challenge landing stamp now
  names the puzzle's day instead — it used to say "today" even for an older
  day's link, fixed same session), the **streak** (sender vanity to a
  stranger; the four scores already prove the day was played), and every
  jargon detail line ("7 scraps torn", "1 hint, 1 funeral", Thread's
  category confession). "I just played", never "I've been playing" — always
  true, even on a first share. The all-caps headline is gone; the old
  headline grammar ("RELIC 20 Aug ’26 🏺") was Wordle-convention insider
  text and is what people cancelled on. Survived two GPT critique rounds.
  Emoji rows, text-only, link-last, scores-over-maximum all unchanged.
  `tests/test_share_text_only.py` enforces the new shape.
- **[JUDGMENT]** The 7 Aug picture removal changed no wording; the 19 Aug
  challenge revision changed ONLY the wording above (score format + the
  dare line); the 21 Aug stranger-first rewrite changed ONLY the words
  around the machinery — the emoji rows and text-only rule are untouched.
  `tests/test_share_text_only.py` + `tests/test_challenge_links.py` are the
  checks.

## Full house means played, not won (Daniel, 19 Aug 2026)

Ruled during the sharing review; shipped with the Challenge Rally (v225).

- **[JUDGMENT]** A **full house is finishing all four of the day's games,
  win or lose.** Losing a puzzle must not change the day-end experience in
  ANY way: same celebration, same share, same copy. The quiet "done. Some
  got away." strip retires when this ships. (This restores locked decision
  #2's letter — "closing the issue is celebrated even with losses" — which
  the all-wins gate on the celebration had narrowed.)
- **[JUDGMENT]** Share framing is **challenge-first everywhere**, full house
  included — no separate "receipt" tier for the day-level share. Working
  button copy **"Challenge a friend"**; final wording at the screenshot
  copy pass.

## Link-preview cards (Daniel, 19 Aug 2026)

- **[JUDGMENT]** The four per-game link-preview images are the GPT set
  delivered 19 Aug (Face Value / Lifeline / Relic / Thread), used **exactly
  as delivered**. Concerns about recognisable answers on the cards
  (Einstein on Face Value, Tutankhamun's stripes on Relic) and Thread's
  pictogram board were raised and overruled — the same imagery already
  fronts the first-run intros. Settled; do not re-raise.

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

- **[ENGINE]** **Every control quotes what it would really take** (Daniel,
  9 Aug 2026, REPLACING the 5 Aug "say what it LEAVES" rule). A correct
  answer never pays under 10, so a nominal "−25" stops being true near the
  bottom — but the fix is a smaller true number, not different words. Each
  control shows `worthNow()` minus what the round would be worth after it,
  floor included: a 25-point clue on a 20-point round says `−10`, and on a
  round already at the floor it says `· FREE`, because it is. The three-
  choices rescue obeys the same rule (`−80` untouched, `−65` after a 25-point
  clue), which is what Daniel asked for: *"flipping the logic between clues is
  odd… it's confusing."* The tear price on the worth line follows too.
  Nothing anywhere says `LEAVES` or `DROPS TO` any more.
- **[ENGINE]** **One price, in one place, once.** The tear price lives on the
  worth line (it is the only cost paid without pressing a control); every
  other price lives on the control that charges it. At the floor the worth
  line reads `WORTH: 10 PTS · MINIMUM`.
- **[JUDGMENT]** **Prices are RED** (Daniel, 5 Aug 2026, overruling a proposal
  to make ordinary prices black): the red minus is what says "this is a cost".
  What is not a price — `FREE`, `MINIMUM` — is not red, and stays ink.
- **[ENGINE]** **The rescue asks before it fires** (Daniel, 9 Aug 2026). "3
  choices" is the priciest button in the app and the only one that closes the
  round's other work, and a first-timer could press it knowing neither. It now
  asks once per game, off the same machine as the first-guess warning
  (`js/guesswarn.js` `askOnce`, `misc.rescueWarned`), quoting the same true
  cost the button does.
- **[JUDGMENT]** **The wrong-guess price rides on the Guess button**: "IF
  WRONG −15 PTS", Daniel's wording, with the "if". It is the one cost a player
  can incur without any warning at all.
- **[JUDGMENT]** **Rescue distractors scale AGAINST the answer's fame**
  (Daniel, 11 Aug 2026, edition-44 review). For a lesser-known answer, the
  distractors are KIND — famous names the player can rule out (Saladin:
  Baibars/Nur ad-Din → Genghis Khan/Ptolemy I Soter; three unknowns is no
  rescue at all). For a very famous answer they are CRUEL — near neighbours
  that keep the 20 points earned (Mona Lisa: The Scream → Virgin of the
  Rocks/Madonna of the Carnation, all Leonardo). A distractor must also never
  be a same-day or adjacent-day ANSWER (Lewis Chessmen carried "Bayeux
  Tapestry" the day after it aired — anyone who played could eliminate it).
- **[JUDGMENT]** **Relic images are museum-grade** (Daniel, 11 Aug 2026):
  crisp, well-lit, subject on a clean background — "no blurry figurines".
  When a round's image is a fuzzy snapshot, replace the image, don't excuse
  it (Lewis Chessmen: lone warder snapshot → NMS king-and-queen shot).
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

## Answer matching (what counts as a right answer)

- **[ENGINE] Lenient on spelling, never on identity (Daniel, 18 Aug 2026).**
  Player reports agreed with by the owner: scoring was "far too strict on
  spelling". `js/match.js` now allows **two typos on long words** (8+
  letters — one on 5–7, exact under that) and accepts **phonetic
  sound-alikes** ("Ghandi" = Gandhi, "Karl Marks" = Marx, "Kruschev" =
  Khrushchev, "Tutenkamen" = Tutankhamun) via a fold that collapses doubled
  letters and merges x/ks, ph/f, silent h, c/k, z/s, y/i — plus vowels on
  6+ letter words. The counterweight, added the same day: a lone word
  within typo range of a **different** pool item's one-word name is never
  credited ("Davis" at King David, "Colossus" at the Colosseum, "Aristotle"
  at Plato, "Carnac" at Karnak) — this also retired some pre-existing
  false accepts. Both directions were audited against all three pools
  before shipping and are pinned by `tests/match_harness.py` (SPELLING
  LENIENCY block). Loosen or tighten only with a new ruling.
- **[ENGINE] Leniency extended to short names (Daniel, 20 Aug 2026).**
  Ruling from the ed-53 review ("the ONLY user emails I receive are people
  getting annoyed about spelling mistakes not being accepted"): the
  phonetic fold's minimum word length dropped from 4 to 3 letters, so
  "Jon" reaches "John" (the fold keeps a word's first letter, so a
  3-letter word can only ever equal a near-identical name). Verified by
  re-running the full match-harness cross-item sweep (149k comparisons,
  0 false accepts). Same session: every answer airing the next day gets a
  misspelling battery before deploy ("hungarian parlament", "chatrapati
  shivaji", "pocohontas"-class guesses) — gaps are fixed with variants
  ("wojtyla", "hungary parliament"), not by loosening the engine further.

## Scheduling (the day compiler)

- **[ENGINE]** 3 rounds per game per day, exactly one easy/medium/hard;
  Thread tier by weekday (Mon/Tue easy, Wed/Thu medium, Fri–Sun hard).
  `compile_editions.py` recipe.
- **[JUDGMENT]** **The tier recipe is a default Daniel may overrule on any
  specific day (Daniel, 11 Aug 2026).** The compiler keeps producing
  one-easy/one-medium/one-hard, and that stays the rule for anything
  auto-staged; but when Daniel names a swap on a given issue during daily
  review, the recipe yields for that issue only and does not need
  relitigating. First use: edition 44 (12 Aug 2026), where Relic runs
  Statue of Liberty (easy) + Mona Lisa (medium) + Lewis Chessmen (medium)
  with no hard round. Do not "fix" a past issue back to the recipe.
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
- **[JUDGMENT]** A group must not be solvable by surface type alone
  (Daniel, 15 Aug 2026, on conn-004's "Writers banished by the state":
  if the four tiles are the board's only writers, a player groups them
  as "the writers" without ever learning the banishment — "you didn't
  really actually get the category"). Either the surface must be mixed
  (another tile of that type sits in a different group) or the label's
  fact must be the only way in. The fix that session: the writers group
  became "Found refuge from persecution in London" (Marx, Freud, Lenin,
  de Gaulle) — Daniel wanted "political persecution", trimmed to
  "persecution" because the Nazis persecuted Freud as a Jew, not for
  politics, and labels must hold to a pedant's reading —
  four unmistakable names whose surfaces (economist, doctor,
  revolutionary, general) share nothing, so the London fact IS the
  category.
- **[JUDGMENT]** Category claims must be undisputable. Weird is fine if
  binary ("years ending 89"); vibes are not ("denounced as a menace").
- **[JUDGMENT]** Every new board gets a Fable-tier review before it's
  schedulable (intake pipeline), and external-critic suggestions must be
  checked against the SCHEDULE before adoption (a proposed tile can
  collide with a nearby answer).
- **[ENGINE]** The owner may waive a specific same-day/adjacent-day
  linked-subject collision (Daniel, 13 Aug 2026: Louis XIV as №46's Face
  Value answer AND a Thread tile the same day — "i don't care he shows up
  2x today"). The waiver lives in `WAIVED_COLLISIONS` in
  `tools/validate_schedule.py`, keyed to the exact edition pair and
  subject, with a dated ruling comment; the finding downgrades to a
  visible WARN instead of gating CI. A tile that merely NAMES a same-day
  answer spoils nothing by itself — the test is whether it helps SOLVE the
  other round (it must not reveal a portrait, a map journey or a relic).
  Each waiver is one-day-one-subject; new cases need their own ruling.
- **[JUDGMENT]** Board titles display DURING play (`#conn-puzzle-title`)
  and in the share text — so a title must never name a hidden completion
  word or otherwise pre-solve a group (16 Aug 2026: "War Horse" would
  have handed players two of conn-184's four fill-in words; Daniel
  renamed it "Stable Relations"). Check the title against the mechanic
  before staging any missing-word or wordplay board.
- **[JUDGMENT]** conn-065 "The People's Game" reserved (Daniel, 16 Aug
  2026, ed 49 review: "let's swap completely, i don't like this board").
  No autopsy was given; the recorded suspicion is that all sixteen tiles
  are sports, so the board plays as sports trivia sorted by region/era —
  one flat surface, no polysemy, no structural twist. Mechanism:
  `reserve: true` on `conn-065` in `data/connections.json`. Un-reserve
  only after a rework passes the NYT-grammar rubric.
- **[JUDGMENT]** conn-137 "True Colours" reserved (Daniel, 21 Aug 2026,
  ed 54 review: "no, will supply a new one"). No autopsy was given; the
  recorded suspicion is that the board's own title announces the trick
  and three of its four groups are colour-sorted the same way, so the
  twist tiles ("Blackshirts" against "The Black Prince", "Redshirts"
  against "Erik the Red") read as traps rather than as a mechanic.
  Mechanism: `reserve: true` on `conn-137` in `data/connections.json`.
  Edition 54 was refilled with conn-023 "Words From the Past" (hard,
  no linked-subject collision) as a standing safety net — Daniel's own
  replacement board supersedes it if it lands before the day airs.
- **[JUDGMENT]** conn-190 "Alphabet Soup" is Daniel's own board, dictated
  whole at the ed 55 review (22 Aug 2026) to replace conn-151 "Keep Your
  Distance": everyday words born as acronyms (RADAR/LASER/SCUBA/SONAR),
  present-day international organisations (NATO/UNESCO/UNICEF/OECD),
  20th-century secret police (GESTAPO/STASI/KGB/KEMPEITAI), Americans
  known by their initials (JFK/FDR/LBJ/MLK). He asked for a title and
  took "Alphabet Soup"; titles naming "initials" or "acronym" were
  rejected because they pre-solve a group. conn-151 was NOT reserved —
  he asked for a replacement, not an autopsy, so it stays schedulable.
  Standing note this board sets: a board whose whole surface is one
  uniform type (all-caps letter strings) is fine PROVIDED the groups cut
  across that surface — here the fake-five is NATO, which reads as an
  acronym-word and resolves only by elimination.

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
- **[JUDGMENT]** Image rights: free-licensed only — do not purchase
  licences to clear a subject (Daniel, 7 Aug 2026).
- **[JUDGMENT]** Lighthouse of Alexandria retired from rotation (Daniel,
  7 Aug 2026: "it is just a lighthouse") — no surviving structure and no
  photograph exists, only a Victorian reconstruction drawing, and the
  drawing alone can't carry a subject nobody could pick out unaided.
  Standing test for the next reconstruction-only artefact: a reconstruction
  is acceptable only when the SUBJECT itself is famous enough to be named
  from it — the Statue of Zeus at Olympia and the Colossus of Rhodes stay
  in rotation on that basis, Lighthouse doesn't. Mechanism: `reserve: true`
  on `lighthouse-alexandria` in `data/reveal-what.json`; not deleted.
- **[JUDGMENT]** Terracotta Army reserved (Daniel, 15 Aug 2026, ed 48
  review): no available photo tears fairly — a close-up of one warrior
  reads as "a statue", any wide pit shot is the answer from the first
  scrap, and the only quiet scrap (bare pit floor) "offers no clues and
  therefore doesn't feel fair". Un-reserve only with an image where at
  least two opening scraps are informative WITHOUT reading instantly as
  the army. Mechanism: `reserve: true` on `terracotta-warrior` in
  `data/reveal-what.json`; image, credits and pinned MCQ stay current.
- **[JUDGMENT]** `frac` in `data/reveal-who.json` / `data/reveal-what.json`
  is inert — confirmed 7 Aug 2026 that no runtime code reads it. Leave it
  where it exists rather than stripping it; don't treat it as a lever.
- **[JUDGMENT]** Persepolis reserved (Daniel, 16 Aug 2026, ed 49 review:
  "persepolis has too many angles, it just reads: ancient ruins").
  Standing test this ruling adds: a site with no single canonical view —
  where every available photo could be any ruin of its era — can't carry
  a Relic round, however famous the name. Un-reserve only with one
  genuinely iconic, self-identifying image. Mechanism: `reserve: true`
  on `persepolis` in `data/reveal-what.json`; image, credits and MCQ
  stay current.
- **[JUDGMENT]** Pompeii's flagship relic is the Priapus fresco of the
  House of the Vettii (Daniel, 16 Aug 2026, replacing Villa of the
  Mysteries on ed 49: "if we do pompeii, i want to do the wall painting
  with the man with the giant penis he is holding w a chain"). The bawdy
  pick over the scholarly one is deliberate — dark wit, tears
  brilliantly, unforgettable reveal. `villa-of-mysteries` stays in the
  pool (not reserved), but when a day wants Pompeii, Priapus goes first.
  NOTE the chain detail is Daniel's shorthand, not the picture: the god
  weighs his member against a bag of gold on a balance scale.
- **[JUDGMENT]** **The graded tear path** (Daniel, 22 Aug 2026, ed 55
  review, on Martin Van Buren: "no matter where you put the opening
  scrap, the next scrap basically has to reveal the face of the guy. If
  you start in one of the corners, it's not really fair because it's
  literally just an innocuous suit"). A reveal image must offer MIDDLE
  ground — scraps that are neither the answer nor nothing. A dark studio
  portrait where the frame is face + plain suit + backdrop fails even
  when the opener is legal, because the round has only two states. Prefer
  images whose periphery carries real evidence: regalia, orders, uniform,
  tools, setting, carved surface. The swap that session was George V —
  aiguillettes, then the Garter star, then the beard, then the face.
  Mechanism: `reserve: true` on `martin-van-buren` in
  `data/reveal-who.json` (the person is not retired — un-reserve with a
  portrait that has an informative middle, e.g. a seated painted one).
- **[JUDGMENT]** Port Royal reserved (Daniel, 22 Aug 2026, ed 55 review:
  "a very unsatisfying image. Either find a much better image of this
  thing, or just swap for something else entirely"). The only free-licensed
  photographs are snapshot-grade views of Fort Charles — one has a modern
  visitor and a pushchair in frame — and the city itself is under water,
  so no photograph can show the thing the blurb is about. Falls under the
  Persepolis test: no single canonical, self-identifying view. Mechanism:
  `reserve: true` on `port-royal` in `data/reveal-what.json`; un-reserve
  only with a museum-grade image that reads as Port Royal and not as any
  Caribbean fort.

## Casting and tone

- **[JUDGMENT]** Audience bar: Rest-is-History listeners. Easy ≠ dumbed
  down, hard ≠ academic. No living politicians as answers. Entertainment
  faces are fine as easy anchors (Mercury, Pelé, MJ) but never the
  majority of a day.
- **[JUDGMENT]** A Lifeline pick is judged as a MAP, not a name (Daniel,
  16 Aug 2026, swapping Pelé off ed 49: "swap for someone with a more
  interesting life story (i.e. pins further apart)"). Two pins in the
  same country is a boring puzzle whoever the person is; prefer journeys
  that tell a story — born one continent, died another (the swap that
  session: Bruce Lee, San Francisco → Hong Kong). Not a hard floor
  beyond the existing `min_lifeline_km`; a short journey can still air
  when the figure earns it, but the review sheet should ask "is the map
  itself interesting?" before "is the name famous?".
- **[JUDGMENT]** Blurbs and facts: dark wit welcome, claims must hold to
  a pedant's reading ("coined" vs "made famous"; Josephus predicted
  VESPASIAN would be emperor, not himself). When a critic softens a label,
  keep the voice, fix the claim.
- **[ENGINE]** Blurb shape (Daniel, 9 Aug 2026): a blurb is
  "Who/what they were (years) · the second half", and **the second half
  starts with a CAPITAL** — on the verdict line it reads as its own
  sentence, and the old lowercase start looked like a mistake. The whole
  pool (669 blurbs across Face Value and Relic) was swept that day.
  `tools/validate_reveal.py` now ERRORs on a lowercase letter after the
  "·"; a clause opening on a digit or a quote is left alone. The blurb
  still carries no closing full stop — the app appends that itself.
- **[JUDGMENT]** Every issue must carry at least one woman across Face
  Value + Lifeline combined (Daniel, 7 Aug 2026). New standing rule — still
  to be enforced in the compiler; until then it's a check on the review
  sheet, same as the other judgment rules.
- **[JUDGMENT]** Occupation-family duplicates within an issue are
  advisory, not blocking (Daniel, 6 Aug 2026: Mother Teresa/Malcolm X and
  Josephus/Dickinson on the same day are fine together). Flag them for a
  second look; don't hold content back over the overlap alone.

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

- **[JUDGMENT] The one-easy-one-medium-one-hard rule bends when the owner says so
  (Daniel, 7 Aug 2026).** Edition 51 (19 Aug) carries two medium Lifeline rounds and
  no hard one, because swapping Chandragupta Maurya for Maya Angelou was worth more
  than the tier symmetry. Daniel's words: *"rules are rules only until I say otherwise
  and make an exception."* Do not "repair" this day: the imbalance is deliberate and
  signed off. Flag future breaches as before, but treat an explicit owner exception as
  the end of the argument, not a bug to be re-raised next audit.

- **[JUDGMENT] Re-affirmed and hardened (Daniel, 12 Aug 2026) — stop asking.** On the
  edition 45 review Daniel asked for Ho Chi Minh in place of Ferdinand Marcos. Ho Chi
  Minh is tagged `medium` and the slot was the `hard` one, so the day now runs
  two-medium / no-hard. A question was put to him anyway, which was wrong twice over:
  the 7 Aug ruling above already covered it, and it had not been read first. His
  words: *"The rules are only the rules as long as I make them the rules… What I say
  goes, basically."* Standing instruction, all games, all days:
  **a named owner swap is executed as given.** Do not cite the tier recipe back at
  him, do not offer alternatives that "fit" instead, do not re-tier the item in
  `reveal-*.json` / `figures.json` to make the day look tidy, and do not log it as a
  deviation. Nothing in tests or CI checks the mix, so the hand-pick always ships
  clean. Read this file BEFORE reviewing content — it exists so settled arguments
  stay settled.
