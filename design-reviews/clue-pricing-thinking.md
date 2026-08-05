# Clue pricing — the thinking behind the two options
4 Aug 2026 · design only, nothing in the repo touched

---

## 1. What the economy actually is

Written out once, honestly, because the design problem is downstream of the fact
that this is genuinely fiddly:

**Face Value / Relic** — round opens at **100**. Your tears cost **−10** each
(the scrap the game opens is on the house). Wrong guess **−15**. Clue A
(Claim to fame / First letters) **−25**. Clue B (Lived / Era) **−15**.
3 Choices **−80**, and a correct pick pays whatever's left. A correct answer
never pays under **10**. Second-and-later correct in a row: **+10**.
Day score = round average.

**Lifeline** — same skeleton, no tears. Claim to fame **−15**. Initials **−25**.
Wrong guess −15, 3 Choices −80, floor 10, +10 streak.

**Thread** — a different economy entirely: 100, each wrong group −20, floor 20,
four wrong and it snaps. No clues, nothing to price.

Two things fall out of writing it down that change the design brief:

- **The same clue name has different prices in different games.** "Claim to
  fame" is −25 in Face Value and −15 in Lifeline. A player who memorises a
  tariff on the intro is *carrying a wrong number into the next game*. This
  alone means the intro cannot be where pricing is taught. Price has to live on
  the control. (Flagging it as a possible content fix too — see §6.)
- **Only one price is unattached to a button:** the tear. Everything else has a
  control to sit on. So the tear is the one price a screen has to state on its
  own — and today it's the one price that *disappears* after the first tear.

---

## 2. Why what's there today fails

### The intro paragraph (`INTRO_CONTENT.copy2`)

> "Each round is worth 100. Tears cost 10 pts, wrong guesses 15, clue slips
> 15–25. Stuck? Three choices costs 80 and pays what's left. Two right in a row
> earns +10. Your day's score is your round average."

Six numbers, four sentences, `--ch-text-muted` at 13px — the quietest type on
the page carrying the heaviest content. Five separate failures:

1. **Wrong moment.** It's a price list read before entering the shop. "Clue
   slips cost 15–25" is unparseable before you know what a clue slip *is* or
   what one looks like. There is nothing on screen for the numbers to attach to.
2. **Inverted hierarchy.** The type says "small print, skip me". The content
   says "this is the whole game". The type wins. Players skip it. (The
   screenshot proves it visually: it is the greyest block on an otherwise
   high-contrast poster.)
3. **Wrong form.** A price list set as continuous prose forces you to parse
   grammar to extract arithmetic. Worst of both — not scannable like a table,
   not memorable like a sentence.
4. **Arithmetic, not stakes.** "Three choices costs 80 and pays what's left" is
   exactly true and completely inert. Nothing makes you *feel* that 80 is
   almost everything.
5. **It's the wrong number in the next game** (see §1).

### The in-game controls

Real screenshot, Face Value mid-round: `WORTH: 65 PTS` above the board, and
three identical cream pills below — `CLAIM TO FAME −25 PTS` · `LIVED −15 PTS` ·
`3 CHOICES −80 PTS`.

1. **No hierarchy — the stakes are inverted.** The −80 rescue is the single
   biggest decision in the round and it is styled *identically* to the −15
   clue. Same size, same border, same red micro-price. The typography is flat
   where the consequences are 5× apart.
2. **Cause and effect are 400px apart.** You tap a button at the bottom of the
   screen; the number that changes is in a different colour band above the
   board. Nothing connects them — no motion, no shared container, no shared
   visual language.
3. **Prices with no denominator.** "−25 PTS" floats free. −25 of what? The
   denominator is in the WORTH line, which is far away and never says what it's
   made of. And the most frequent transaction in the game — the tear — loses
   its price entirely after the first one (the ` · each tear −10` suffix is
   dropped), so in steady state the thing you do most is unpriced.
4. **"−80 pts" asks the player to do subtraction they can't do.** From 65, −80
   doesn't leave −15, it leaves 10 (the floor). The one place a number is
   genuinely misleading.
5. **Spent state is noise.** A bought clue's button stays visible with its price
   greyed out, duplicating the yellow answer chip below it.

### Why the earlier "Prize Note" mock failed (worth being blunt — it was the
### recommendation last round)

The *idea* was right and it survives into Option 1. The *rendering* was a
diagram pretending to be an object: four dashed red lines and four floating
yellow flags on one small note, flags overlapping each other and the note's own
type. Two fatal problems:

- **The encoding is undecodable.** A line at 80% across "means" −80; a line at
  10% "means" −10. Same visual, opposite readings, disambiguated only by the
  label — which means the picture teaches nothing the label wasn't already
  saying. It's a bar chart in a banknote costume, and a bar chart is more work
  to read than the sentence it replaced.
- **The in-game promise breaks the layout.** "After paying, the note simply IS
  smaller" means your score readout changes *size* as well as value. At 15 vs
  10 the difference becomes unreadable, and a shrinking element reflows
  everything under it every time you tear.

The Tariff table failed differently and for a reason worth respecting: it's the
clearest possible thing, and Daniel rejected it because a table is the least
in-world object in the app. That's a taste ruling, not a mistake — and it's
already served by the `how-to-play.html` page, which lists the full tariff today.

---

## 3. The principle both final options are built on

**Prices belong at the moment of temptation, not in a briefing. The intro's job
is stakes; the button's job is price; the help page's job is the tariff.**

Three layers, each carrying only what it can carry:

| layer | job | content |
|---|---|---|
| intro card | the promise | you start at 100; help costs some of it; a right answer never pays under 10 |
| in-game controls | the price | the actual number, on the actual control, sized to the actual stake |
| `?` / how-to-play | the tariff | every number, for anyone who wants it |

Two supporting rules:

- **The pot and the things that eat it belong in one eyeline.** Today they're
  separated by the whole board. That is the single biggest structural bug.
- **The −80 is a different species and must look like one.** It is not a clue,
  it's a rescue. Same-shaped pill is a category error.

---

## 4. Directions considered

| # | direction | verdict |
|---|---|---|
| D1 | **The Tariff** — dot-leader price table on the intro | Clearest thing possible; already rejected as "least in-world", and it's still six rows to read before round 1. **Cut** — but it's exactly right as the `how-to-play` reference, which already exists. |
| D2 | **The Receipt** — teach by one worked example round | Charming, on-brand (the summary screen already IS a receipt), but it teaches a *story*, not a *price* — you still can't tell what this button costs. Also spends the receipt idiom before the payoff screen does. **Cut.** |
| D3 | **The Informants** — Registrar / Biographer / Fixer, bribe-priced | The funniest and the most Yesternerd. But it renames three things players already know, adds a vocabulary tax to every round, and breaks across games (Lifeline's clues are different people). **Cut as structure, keep as flavour copy** — "the fixer's price" is a great line inside whichever option wins. |
| D4 | **The Prize Note with tear-lines** (last round's recommendation) | Right metaphor, undecodable rendering, layout-breaking in play — see §2. **Cut as drawn; its core survives as Option 1.** |
| D5 | **Bite bars** — a bar on each chip filled to its share of the pot | Solves the hierarchy problem honestly and cheaply. But it imports a second visual language (progress bars) into a zine that has no bars anywhere, and it's ambiguous whether full = good or bad. **Cut — but fold the proportionality into size and weight instead, which Option 2 does.** |
| D6 | **Hold-to-preview ("the haggle")** — press a clue, the worth line rehearses the price before you commit | Genuinely good, and I want it eventually. But it's invisible until discovered, so it can't be the primary teaching device; and a long-press on a control that also fires on tap is a mis-tap generator on mobile. **Deferred — an enhancement to whichever option wins, not an answer.** |
| D7 | **No prices at all** — show only the current worth, let purchases just move the number | Beautiful, honest, fewest digits on screen. But it makes every purchase a blind trust exercise and turns the −80 into a trap. **Cut** — though the aspiration (fewer floating numbers) is right, and both finalists reduce the count of *unattached* numbers from 4 to 1. |
| **F1** | **THE HUNDRED** — the pot as a printed note with a running tab, moved down to sit with the buttons | **WON.** Organises everything around *what you still have*; fixes the eyeline bug; generalises to all four games including Thread. |
| **F2** | **PRICED TO SELL** — every purchasable wears a stuck-on price tag, sized to its stake; the intro shows the same tags | **WON.** Organises everything around *what things cost*; the intro becomes a picture of the buttons you're about to meet; ships in an evening with near-zero risk. |

### Why these two, and why exactly two

They are the two honest answers to the same question, and they differ on the
axis that actually matters: **F1 leads with what you have; F2 leads with what
things cost.** F1 is the bigger idea and the bigger build (a new component with
live state, and it moves the worth readout). F2 is the surgical fix (a restyle
of controls that already exist, plus reusing that markup on the intro). They are
also combinable later — F2's tags would sit happily on F1's screen — so this
isn't a fork you can't walk back.

F2 is deliberately *not* "the cheap version of F1". It's the earlier "price
tags" sketch taken seriously: last round it was a sticker glued onto a pill and
nothing else. Here the tag becomes the organising unit, size maps to stake, the
tear price stops vanishing, the bought state gets a `PAID` stamp instead of a
grey-out, and — the actual idea — **the intro shows the real controls rather
than describing them.**

---

## 5. The two options in detail

### OPTION 1 — THE HUNDRED

*One object carries the economy: a printed hundred-point note.*

**Intro.** The grey tariff paragraph is deleted outright. In its place, the note
at full width, mint condition, plus one sentence in ink (not muted grey):

> Every scrap you tear and every clue you buy is paid out of it. Guess right and
> you keep what's left — never less than 10.

Note face carries banknote boilerplate in mono micro — `PAYS THE BEARER ON
DEMAND` / **100** / `POINTS · EVERY ROUND, EVERY GAME` — corner denominations,
ink border, hard shadow, the game's accent on the band. Under it, one small
mono row: `TERMS OVERLEAF ▸` — a tap-to-expand that reveals the full tariff for
anyone who wants it, and which is what the mid-game `?` re-open lands on.
Zero tariff numbers on the intro by default. **Intro numbers: 100 and 10.**

**In-game.** The `WORTH: … · EACH TEAR −10` line above the board is deleted.
The note moves down into `.map-main` and sits directly above the clue buttons,
so the pot and the things that eat it are finally in one eyeline:

- left cell: the live number, big, with `PTS STILL YOURS` under it
- right cell: the running tab in mono with dot leaders and red minuses —
  `TEARS ×2 ····· −20`, `LIVED ········ −15`. Nothing spent yet? The tab shows
  the house tariff instead: `EACH TEAR ···· −10`, so the tear price never
  disappears.
- the note stays a fixed size; only the number and the tab change. (Explicitly
  fixing the earlier mock's shrinking-note problem.)

Then the two clue buttons, then 3 Choices on its own full-width red-ruled plate.
Loud/quiet law: in play the note is cream + ink with red minuses only — the
accent stays off the play screen; the mint note on the intro (a moment screen)
carries the game colour.

**Why it's the strongest answer:** it's the only structure where the display and
the game's own gesture are the same idea — a round is a hundred points of paper
and everything you do tears a piece off. It fixes the eyeline bug rather than
decorating around it. And it's the only one that generalises to **Thread**,
which has no clues to price but does have a 100 that wrong groups eat 20 at a
time.

**Costs and risks:** a new component with live state in two game files; the
worth readout moves (muscle memory for existing players); the tab needs a rule
for what happens after ~4 different spend types (answer: tears collapse to
`TEARS ×n`, so the ceiling is 4 rows and in practice it's 2–3).

### OPTION 2 — PRICED TO SELL

*The tag is the unit. Everything you can buy wears one; the intro shows the
same tags.*

**Intro.** The grey paragraph is replaced by a card headed `WHAT HELP COSTS`
containing **the three real controls at real size** — the exact buttons the
player is about to meet, tags and all — under a stamped sub-head
`AND THE THINGS YOU DON'T BUY:` with two small ticket stubs, `EVERY TEAR −10`
and `EVERY WRONG GUESS −15`. One closing line in ink:

> Each round opens at 100. Guess right and you keep what's left — never less
> than 10.

The point is not that it lists prices. It's that the player has *already seen
these exact objects* before the first round, so the numbers become recognisable
rather than memorable. Tags sit at small rotations like real stickers — a
market-stall card, not a table: no rows, no alignment grid, no dot leaders.

**In-game.** Nothing moves. Four changes, all local:

1. The price leaves the button's text flow and becomes a **stuck-on tag** —
   punched hole, slight rotation, ink border, small hard shadow — overhanging
   the top-right corner. Fixes the `CLAIM TO FAME −25 PTS` run-on and gives the
   price object-ness.
2. **3 Choices becomes a different species**: full width, red-ruled, red tag,
   with a mono sub-line `PAYS WHATEVER'S LEFT — NEVER UNDER 10`.
3. The WORTH readout becomes a tag too, so the whole screen speaks one
   language — `THIS ROUND · 65 PTS LEFT` — with `EVERY TEAR −10` as a small
   tag beside it that **stays for the whole round** instead of vanishing after
   the first tear.
4. A bought clue's tag takes a red `PAID` stamp and the button goes quiet —
   the price stops being live noise.

**Why it's a real contender, not a consolation prize:** it makes the intro
honest work (a preview, not a briefing) at a fraction of the build, changes no
layout and no state, and gets the hierarchy fix — the −80 stops looking like the
−15 — which is the most damaging of the current bugs. It ships in one evening.

**Costs and risks:** it doesn't fix the eyeline problem (the worth readout still
lives above the board), it has nothing to say for Thread, and it's five tags on
one intro card — the busiest of the finalists if the rotations aren't
disciplined.

---

## 6. Two things worth deciding either way

**A. Show what 3 Choices would actually pay.** Today the button says `−80 PTS`,
and from a worth of 65 that reads as −15 when the real answer is 10 (the floor).
`worthNow()` is known at all times, so the button can carry the outcome live:
`3 CHOICES · −80 · YOU'D WIN 20`. This keeps Daniel's 28 Jul ruling intact — it
is still *priced as a cost*, same grammar as the other slips — and just adds the
number the player was being asked to compute. **This is the single highest-value
change in either option and it's one line of code.** Both mocks show it.

**B. "Claim to fame" costs −25 in Face Value and −15 in Lifeline.** Same name,
different price, and both games sit on the same home screen. Whatever wins here,
this trains a wrong instinct. Two clean fixes: align the prices, or rename one
(Lifeline's cheap slip could be "Trade" or "Line of work"). Content call, not a
design call — flagging it, not deciding it.

---

## 7. What the mocks show (390×844, real fonts, real CSS, real numbers)

All four are built on top of the app's actual `brand-tokens.css` + `style.css`,
inside the real `.intro-overlay` / `.view-game` markup, using real clue names,
real prices and a real round image. Source files live in the site copy as
`cp-opt1-intro.html`, `cp-opt1-game.html`, `cp-opt2-intro.html`,
`cp-opt2-game.html`.

- **`clue-pricing-option-1-intro.png`** — the mint note in place of the grey
  paragraph. Two numbers on the whole screen: 100 and 10.
- **`clue-pricing-option-1-game.png`** — mid-round Face Value at 65 points:
  two tears and a Lived slip already spent. The note sits between the guess box
  and the buttons; the tab shows where the 35 went; the tear price is still on
  screen; `LIVED` is stamped `PAID`; 3 Choices is red-ruled and says what it
  would actually pay.
- **`clue-pricing-option-2-intro.png`** — the stall card: the three real
  controls at real size, plus two stubs for the things you don't buy.
- **`clue-pricing-option-2-game.png`** — the same three controls in play, tags
  and all, with the worth readout left exactly where it lives today and now
  speaking tag.

**One honest trade-off visible in the shots:** Option 2's card is ~120px taller
than Option 1's note, so it takes that height off the intro poster (art drops
from 42vh to 36vh). Option 1's intro keeps more of the artwork. There's
precedent either way — `style.css` already shrinks the poster to 33vh on short
screens — but it's a real cost and Daniel should see it in the two images
side by side.

Two mock-only deviations, both noted so nothing is mistaken for a proposal:
the scrap watermark is set to `YESTERNERD` (the repo's `.df-scrap::after` still
prints the old brand name — a separate stale string, not part of this work), and
the mocks are static, so the `TERMS OVERLEAF` row is shown closed.

## 8. What I'd do

**Option 1 is the better design; Option 2 is the better bet if the launch window
is tight.** If both fit, they aren't exclusive: build Option 2's tags and the
3-Choices outcome line now (an evening, no risk, fixes the worst bug), and hold
the note for the first post-launch content-quiet week, when moving the worth
readout can be done carefully and rolled out to Thread at the same time.
