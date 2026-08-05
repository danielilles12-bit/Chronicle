# The Copy Review — plan v2 (in context, triaged)
5 Aug 2026 · supersedes the flat 194-string sheet (rejected: too many items,
no context) · plan only — no copy is rewritten here

**Status: PROPOSED.** Daniel reads this, answers the three questions at the
bottom, and the build session runs without him.

## What it is (one sentence)
Daniel reviews only the ~30 highest-stakes lines, each shown as a screenshot
of its real screen in its real state; everything else is swept by a model
against HOUSE_RULES and only violations come back to him.

## The triage principle — what earns Daniel's eyes
Stakes, not location. A line reaches the must-read tier only if it is one of:
1. **First minute** — what a stranger meets in their first 60 seconds
   (stranger hero, the four intro overlays, round prompts, 404).
2. **An ask** — anything requesting an action: the five share texts, the
   carry flow, Encore, Report a problem.
3. **A wound** — anything a losing player reads: wrong-answer verdicts, the
   low end of the remark ladders, "The thread snapped.", the damnatio stamp,
   "Some got away.", failure/error copy.
4. **A claim** — anything factual or legal: privacy.html, "Works offline",
   "Free, no sign-up" (in every link preview), press/about/corrections.
Everything else — button labels, table headers, placeholders, chrome — is a
cheaper lane. Already-ruled copy never comes back (see Settled, below).

## The tiers (from a fresh inventory, ~190 recurring strings)
- **Tier 1 — Daniel reads, in context: ~30 decisions (~60 strings).**
  8 first-minute + 8 asks + 8 wounds + 6 claims. Pools count as ONE decision:
  the five wrong-verdicts ("Misfiled.", "The dead disagree.", …) are one
  screenshot with the other four listed beneath it — one yes/no on the set.
- **Tier 2 — spot-check: ~60 strings.** Positive verdicts, ledger empty
  states, archive/Morgue labels, carry success statuses, countdowns,
  how-to-play body. Model-screened first; Daniel sees only what gets flagged
  (expect ≤10 lines). The rest waits for a post-launch skim.
- **Tier 3 — swept only: ~100 strings.** Guess / Submit / Shuffle / Close /
  Play again, stat labels, placeholders, aria-labels, meta boilerplate.
  Never shown to Daniel unless the sweep finds a violation.

## Settled — excluded even where it appears in a screenshot
Rulings already made are not re-asked: the install flow's six screens, the
field-line bands, every clue price / worth line / "LEAVES 10", the
first-guess warning wording, the intro overlays' scoring sentence ("teaches
the model, not the tariff"), "To Tear You The Truth", and the moment screens
(You Made History / the obituary). Where a settled line shares a screenshot
with a line under review, the annotation marks it "settled — not under
review". (The old start screens still quoting "Three choices costs 80" are
unreachable dead views — excluded, flagged separately for cleanup.)

## The in-context method — the contact sheet
The Playwright harness already does everything needed: `tests/helpers.py`
boots the app on an iPhone-13 viewport, pins the date, forces states
(fresh profile = stranger; `seed_completion` builds any ledger; the play
helpers reach any summary, won or lost), and Playwright screenshots any
screen. So: a small Python script — helpers.py as-is, no new harness
features — walks the Tier-1 surfaces in their right states and writes ONE
static page: `design-reviews/copy-review-2026-08-06/sheet.html`.
- Screenshots in reading order, grouped by stakes (first minute → asks →
  wounds → claims), each numbered.
- Under each: the line(s) under review, highlighted, with pool variants
  listed as text; settled lines greyed out.
- Share texts appear as the literal text block a friend would receive.
- **Verdicts are default-keep.** No tap-tooling: Daniel replies in chat with
  only the numbers he wants changed ("7 — too cruel", "13 keep the RIP").
  Silence on a number is approval. One message, done.
- Optional, not required: `?qa=1` on his phone already summons every gated
  screen live if a screenshot ever isn't enough to judge feel.

Why this beats alternatives: a live click-through costs Daniel 3× the time
and misses forced states; a tap-verdict widget is tooling for its own sake
when a numbered reply already works (it's how the launch board syncs).

## The cheap lane — the model sweep
One pass over ALL ~190 strings (Tiers 1–3), same forced-ranking pattern as
the content intake pipeline: rank worst-first against HOUSE_RULES' standing
copy rules — house voice (zine, dark wit, never corporate), claims that hold
to a pedant's reading, no price the floor would swallow, no bare extremes,
no per-browser deletion claims — plus internal consistency (WORTH
everywhere, game names never drifting). Output: the bottom ≤10 with a
one-line reason each, appended to the contact sheet as "flagged". No
approvals requested; violations only. Copy already guarded by engine tests
(field-line wording, clue prices, install replicas) is listed as
machine-checked, not re-read.

## Sequencing and Daniel's time budget
1. **6 Aug (session, Daniel: 0 min):** build the contact sheet, run the
   sweep, publish the sheet as an artifact page he can open on his phone.
2. **7 Aug (Daniel: 25–30 min, one sitting):** read the sheet — ~30
   numbered decisions plus ≤10 flagged lines — reply with the change list.
3. **7–8 Aug (session, Daniel: ~5 min):** apply the changes, add any new
   rulings to HOUSE_RULES, run the suite, bump BUILD+VERSION, deploy; he
   skims a plain-language summary of what changed.
4. **Post-launch, no deadline:** the Tier-2 skim (~10 min). Privacy does
   NOT slide — it is a claim, so it is Tier 1. About + press do not slide
   either: Daniel chose the FULL pre-launch read (5 Aug, overriding the
   claims-only default) — both pages go on the sheet in full, which makes
   his sitting ~45 min rather than 30.

## Explicitly out of scope
- No copy is rewritten in this plan; rewrites happen only after step 2,
  only on lines Daniel names.
- No new tooling beyond what helpers.py already supports; no verdict
  widgets, no CMS, no string extraction framework.
- No relitigating anything in the Settled list, and no fifth look at
  surfaces the engine tests already pin word-for-word.
- No visual changes of any kind.

## Three decisions — ANSWERED (Daniel, 5 Aug 2026)
1. **Default-keep: YES.** Silence on a numbered item is approval; Daniel
   writes only about lines he wants changed.
2. **The obituary share: ON THE SHEET.** It travels to friends' phones;
   it gets its own numbered decision.
3. **About + press: FULL pre-launch read**, overriding the claims-only
   default. Both pages go on the sheet whole; sitting grows to ~45 min.
