# Letters to the Editor — the player-feedback invitation
**Design plan, 4 Aug 2026. Plan only — nothing in the app has been changed.**
Mocks: `feedback-mock-a.png` (Home plate) · `feedback-mock-b.png` (moment-screen
stamp) · `feedback-mock-c.png` (Home postbag card). Sources in
`scratchpad/site/feedback-mock-[a|b|c].html`.

---

## 1 · What's wrong with the current plan

The checklist says *"a menu item + a quiet line on the full-house screen"*. There
is no menu — the "menu" is the six-word grey footer at the bottom of Home. So the
current plan is: **two grey lines**. Grey lines get read by people who were already
looking for them, which for feedback is roughly nobody.

The fix isn't volume, it's **furniture**. A zine has a letters column. It is on the
same page every issue, nobody is startled by it, and it is unmistakably an
invitation rather than a support ticket. That's the model.

## 2 · The principle (so this doesn't drift later)

> **Feedback is furniture, not an interruption.**
> It lives permanently in places where the player has *stopped playing* —
> the foot of Home, the end-of-day screen, the record book. It never appears
> where a puzzle is happening, and it never has to be dismissed.

This keeps the loud/quiet law intact: play screens (`.view-game`) stay cream + ink
with one accent and gain nothing. Home is a lobby, not a play screen — it already
carries a magenta PLAY TODAY hero, so a bordered plate with a magenta tab is well
inside house style. The day-done screen is `.view-loud` and can take a red stamp.

## 3 · Recommended combination — ONE answer

Five surfaces. Together they are unmissable; individually not one of them
interrupts anything.

| # | Surface | What goes there | When |
|---|---|---|---|
| **1** | **Foot of Home**, above the footer | **The Letters plate** (Direction A) — magenta kicker tab, big display headline, one line of body, full-width ink button | From the player's **first ever finished daily**, then permanently |
| **2** | **Day-done moment screen** (`#view-daydone`), below the Share + Home buttons | **The Complaints Dept stamp card** (Direction B) — red rubber stamp, tappable block | Every time the screen shows — both the full-house face and the obituary face, with different copy |
| **3** | **Your Legacy foot**, above the Carry row | One `carry-open`-style row: kicker + bold line + arrow | Always (only engaged players get here) |
| **4** | **Home footer**, one word | `Write to us` inserted into the About · Sources · Privacy line | Always — the one door a day-one stranger can still find |
| **5** | **About page** | A proper paragraph + button + email address | Always |

**Why this shape:**

- **Where.** The foot of Home is where a player lands when they've finished the
  last game and scrolled back down — every row above it says "Done", so the plate is
  the only live thing on the screen. That's the moment they have an opinion and
  nothing else to do with it. The day-done screen catches them at peak goodwill
  (full house) *and* at peak honesty (the obituary, where the app is literally
  saying "you're history" — see §5 for why that one matters most).
- **When: always, not after N days.** Any "show it after 3 visits" gate would
  silence launch week, which is the *only* week the form really matters. The one
  gate worth having is the honest one: a person who has never finished a game has
  nothing to report, so the Home plate stays hidden until their first completed
  daily. One condition, one line of code, no timers, no counters, no nag state.
- **Why five and not one.** Each surface catches a different mood: the plate
  catches "I keep meaning to say", the stamp catches "that was great / that was
  brutal", the Legacy row catches the streak-obsessive, the footer catches the
  bug reporter, About catches the person who wants to know who's behind it.

**Explicitly kept separate:** the existing `Report a problem` mailto on each game
summary and on the image-credit panel. That's the **corrections** lane — its
subject line carries the content ID, which is what makes a wrong date findable and
fixable. Don't fold it into the form; you'd lose the ID and gain nothing.

## 4 · The copy (house voice — dry, print-shop, short)

**1 · Home plate**
> `LETTERS TO THE EDITOR` *(magenta kicker tab)*
> **TELL US WHERE IT HURTS.**
> Too hard, too easy, too obscure, plain broken — or a round you'd have framed.
> One reader, one desk, no committee.
> `[ WRITE TO THE EDITOR → ]`
> `TWO QUESTIONS · NO LOGIN · ONE MINUTE`

**2a · Day-done, full-house face**
> *(red stamp)* `TELL US WHERE IT HURTS` / `COMPLAINTS DEPT · DESK № 1`
> `THE EDITOR READS EVERY ONE →`

**2b · Day-done, obituary face** *(streak just died — dark background)*
> *(red stamp)* `ANY LAST WORDS?` / `COMPLAINTS DEPT · DESK № 1`
> `TELL THE EDITOR WHAT KILLED IT →`

**3 · Your Legacy foot** *(same component as "Moving house?")*
> `SOMETHING TO SAY?`
> **Write to the editor →**

**4 · Home footer**
> Works offline · Your Legacy · Sound on · v169
> About · **Write to us** · Sources · Privacy

**5 · About page**
> **The letters page**
> One person makes this and one person reads the replies. If a round was wrong,
> too obscure, or quietly brilliant, that's worth knowing. Two questions, no login,
> and your app version comes along so a bug can actually be found.
> `[ WRITE TO THE EDITOR → ]` · or email daniel.illes12@gmail.com

**Offline state** (the form needs a network; the app doesn't)
> Button becomes `EMAIL THE EDITOR →`, footnote becomes
> `YOU'RE OFFLINE — THIS OPENS YOUR MAIL APP`.

*Voice note:* "Tell us where it hurts" is the load-bearing line — it gives
permission to complain, which is the feedback you actually need, and it sits
naturally beside "Some got away", "Nothing in here ever dies" and "You're history".
It works on a happy screen (a happy person's gripe is the most useful kind) and it
is the same sentence in all three places, which is what makes it furniture.

## 5 · Three visual directions

### A — LETTERS TO THE EDITOR plate → `feedback-mock-a.png`
Typographic. Cream plate, 2.5px ink border, hard shadow, a magenta kicker tab
punched over the top-left edge (the same device as the "We've moved" strip), a
31px Archivo Black headline, one line of body, a full-width ink button, and a
dashed tear-off rule above the fine print. Reads as the zine's standing letters
column. Uses only components already in `style.css` — cheapest to build, and the
headline does the persuading.

### B — COMPLAINTS DEPT stamp → `feedback-mock-b.png`
The moment-screen slot, shown on the magenta full-house screen. A cream
`loud-block` carrying a red double-ruled rubber stamp rotated −4.5° — exactly the
`MEMENTO MORI` / `CARPET DIEM` / `DAMNATIO MEMORIAE` language, but this one is
tappable. Additive rather than an alternative: it pairs with A or C.
*Watch:* the full-house screen already carries the small CARPET DIEM stamp, so on
that screen there are briefly two red stamps. They're far apart and different
sizes, and it reads as a print page rather than a repeat — but if it bothers you,
hide CARPET DIEM whenever the letters stamp shows.

### C — THE POSTBAG reply card → `feedback-mock-c.png`
Object, not layout. A franked reply card: CMYK airmail chevrons around the border,
a ruled `TO: THE EDITOR / YESTERNERD · DESK № 1` address block, and a `№1 REPLY
PAID` postmark reusing the milestone-postmark circle from the celebration screen.
The most charming of the three and the most obviously *an invitation to write*.
Costs about 25 extra lines of CSS and one new idea in the system (airmail stripes).

### Which one
**A for launch, C as the upgrade.** A is comparable-or-better at the actual job —
the headline is three times the size and states the ask in five words, where C
spends its top third on decoration before the reader learns what it's for. A also
introduces nothing new to the design system, which matters with six days to go.
C is the better object and worth revisiting after launch week, when there's time
to check the chevrons don't turn to mush on a low-DPI Android screen.
**B ships alongside whichever wins** — it's a different surface, not a competitor.

## 6 · What NOT to do

- **No modal, sheet, toast, or interstitial. Ever.** Nothing the player has to
  dismiss. This app has never once blocked the road and shouldn't start over a
  feedback form.
- **Nothing on a play screen.** Not in the game topbar, not after a wrong guess,
  not between rounds, not on the intro cards. The loud/quiet law, and the intro
  cards are the teaching moment — don't put a second CTA in the funnel.
- **No "How are we doing? 🙂😐🙁" row.** Off-voice, and three emoji taps give you
  a number you can't act on. You need sentences.
- **No time or count gate** ("after 3 days", "after 5 visits"). It would mute
  exactly the week the form exists for.
- **No red dot / badge / pip** on the invitation. That's notification grammar for
  something the player owes you. They don't owe you anything.
- **No suppression after they write.** With no backend you cannot know whether
  anyone submitted, so any "they've already done it" logic would be guessing, and
  a wrong guess silences your only channel. Nothing hides.
- **Don't require a name or an email address** in the form. A contact field halves
  responses and you've promised no accounts.
- **Don't retire the `Report a problem` mailto** — see §3.
- **Don't put it in the install tip or the pull-to-refresh queen.** Both are
  tuned; leave them alone.
- **Don't date the copy** ("in the first fortnight…"). This is a static app with a
  service worker; dated copy goes stale on someone's phone and stays there.

## 7 · How it gets built (one evening, ~2–3 hours)

**Daniel's 10 minutes first — the form**
1. New Google Form, three questions:
   1. *What happened?* — paragraph, required
   2. *What should have happened?* — paragraph, optional
   3. *Technical bits (already filled in — please ignore)* — short answer, optional
2. Settings: **Collect email addresses OFF**, **Limit to 1 response OFF** (both
   force a Google login).
3. ⋮ menu → **Get pre-filled link** → type `TEST` in question 3 → **Get link** →
   Copy. Paste that whole URL into the build session. It contains the
   `entry.123456789` id, which is the only thing the code needs.

**Files touched**
- `js/feedback.js` *(new, ~50 lines)* — `FORM_URL`, the one `entry.` id,
  `deviceLine()`, `feedbackUrl(where)`, `openFeedback(where)`, `mountFeedback()`.
- `index.html` — three markup blocks (Home plate, day-done stamp card, Legacy
  row) + one footer word.
- `css/style.css` — one commented block, `/* ---------- Letters ---------- */`,
  ~30 lines; copy them straight out of `feedback-mock-a.html` / `-b.html`.
- `js/app.js` — import, call `mountFeedback()`, show/hide the plate, swap the
  day-done stamp copy in `showCelebration` / `showObituary`, bump `BUILD`.
- `js/track.js` — six new `DISPLAY` entries.
- `about.html`, `privacy.html` (see below), `sw.js` `VERSION`, one test spec.

**URL shape**
```
https://docs.google.com/forms/d/e/<FORM_ID>/viewform?usp=pp_url
  &entry.123456789=v169 · home · iPhone · installed · 390x844 · en-GB
```
Opened with `target="_blank" rel="noopener"` so an installed PWA shows it in the
in-app browser and the player can swipe back to the game with their session intact.
Cross-origin, so `sw.js` never sees it — nothing to add to the cache list.

**Visibility rule (the only condition in the whole feature)**
```js
// Home plate: hidden until the player has ever finished a daily.
const seen = daily.GAMES.some(g => Object.keys(ledger.entries[g] || {}).length);
```

**Fallback**
`navigator.onLine === false` → the button's `href` becomes the mailto (subject
pre-filled with build + surface, body seeded with the device line) and the label
and footnote swap to the offline copy in §4. About always offers the email address
regardless.

**Analytics** — add to `track.js`'s `DISPLAY` map, using the existing
"digit + letter = sibling family kept out of the plain digit's sum" convention
(`4x`, `6x`), so these never pollute the share numbers:
```
6f-feedback-tapped-home        6f-feedback-tapped-fullhouse
6f-feedback-tapped-obituary    6f-feedback-tapped-legacy
6f-feedback-tapped-footer      6f-feedback-tapped-mailto
```
**Read these honestly:** GoatCounter records the *tap*, never the submission.
Taps ÷ submissions is your form's drop-off rate, and it will not be 1:1.

**One privacy line is required** — `privacy.html` currently promises no backend
and no data leaving the phone. Add, in its voice:
> *If you write to the editor, the form is hosted by Google, and the link carries
> your app version and a one-line device description so a bug can be reproduced.
> Nothing else goes with it, and nothing is sent unless you tap.*

**Tests** (three assertions, `tests/`)
1. Fresh storage → the Home plate is hidden.
2. One seeded ledger entry → the plate is visible and its target URL contains the
   current `BUILD`.
3. The day-done stamp card is a real `<button>` with an accessible name.

**Ship** — bump `BUILD` in `js/app.js` **and** `VERSION` in `sw.js` together, run
the suite, tick §4 of `LAUNCH_CHECKLIST.md`.

## 8 · Reserve — only if the form is quiet after a week

In priority order, cheapest first:

1. **The edition-closed strip** (`#issue-closed`, the "№ 42, done. Some got away."
   consolation on Home). The highest-signal surface in the app for *"the
   difficulty is wrong"* — but the strip is already a verdict, a score and a
   countdown, and a fourth element makes losing feel like a complaints queue.
   Held back on purpose. One muted line if you go: *"Something got away that
   shouldn't have? Tell the editor →"*
2. **A third question in the form** — *"Which game?"* as four radio buttons. Costs
   the player two seconds and saves Daniel a lot of guessing at triage.
3. **Promote the Home plate above the game rows** on days when all four dailies are
   already done. More code, more risk; only if scroll depth is genuinely the
   blocker.

Do **not** reach for a modal at any point in that ladder.
