# The Yesternerd Leaderboard — a plan for Daniel to approve

*Written 5 Aug 2026. Planning only — nothing in the repo has been touched.
You decided to build a leaderboard; this document finds the version worth
building and is honest about what it costs. Launch is Monday 10 Aug; content
freezes Saturday 8 Aug; there are roughly four working evenings left.*

---

## The one-paragraph version

Build the **percentile board**: after you finish a daily, the app tells you
"your 84 beat 71% of today's players" — no names, no rankings, no login.
It is the only leaderboard that is kind at launch (it never shows an empty
room), nearly cheat-proof by construction, and almost weightless legally
(it stores no names, no emails, nothing anyone typed). Ship it the **week
after launch**, not before — the four remaining evenings are already spoken
for, and a percentile board is at its most boring in week one anyway, when
there are few scores to compare against. Friend groups ("play against your
group chat") are the right **version 2**, a few weeks later, once we can see
whether the WhatsApp groups actually want it. The native feedback form
should **ride the same plumbing — but second**: launch with the Google Form
as planned, then move feedback in-house when the leaderboard machinery
exists, because at that point it costs half an evening.

---

## 1 · What kind of leaderboard is actually right here

First, the ground truth this decision sits on:

- **Everyone plays the same four games each day**, so "how did I do against
  everyone else *today*" is a natural, honest question. That is the question
  a leaderboard should answer.
- **The app's emotional register is gentle.** It celebrates showing up,
  treats a full house as prestige rather than a minimum, and holds a funeral
  for a dead streak. A leaderboard that makes Tuesday feel like an exam
  would be a self-inflicted wound.
- **At launch there will be very few players.** Dozens, maybe low hundreds
  on a good day. Any board that shows a *list* also shows how short the
  list is.
- **Every score is computed by the player's own browser**, so every reported
  score is, technically, a claim. (More in section 2.)

Against that, the candidates:

### Rejected: a global daily top-N (a public list of the day's best scores)

This is what "leaderboard" usually means, and it is wrong for this app three
separate ways. First, the **empty-room problem**: a top-10 with 12 players
on it announces "this game has 12 players" to every visitor — the one thing
a launch-week product must never say out loud. Second, it creates the
**strongest cheating incentive** of any design: a public podium with your
name on it is exactly the thing a bored teenager forges a score for, and
one forged 400 at the top poisons the whole board for everyone honest.
Third, **names are user content**: the moment strangers can publish text
(a nickname) where other strangers see it, you own a moderation problem and
a bigger privacy problem. All cost, and the prize is a podium that makes
the middle of the pack feel worse, in an app whose whole voice says
"showing up counts".

### Rejected: a streak leaderboard

Streaks are the app's sacred object — and that is exactly why they must not
be ranked. A global streak table makes every newcomer permanently behind
(the leaders' number only grows), converts a missed Tuesday from "a wound
the app mourns with you" into "you fell 400 places", and a forged streak is
both the easiest thing to fake and the most poisonous. This would monetise
the app's emotional currency and debase it in the same move.

### Rejected (for v1): friend groups via a shareable code

A private board for your group chat — someone creates a group, gets a code,
friends join with it, everyone sees each other's daily scores. This is
genuinely good for *this* app: the growth plan runs through WhatsApp groups,
friendly rivalry inside a known circle is the gentle kind, and cheating
inside a friend group is self-policing (you know who Dave is). But it is
the **biggest build** on the list — creating/joining/listing groups,
nicknames, a whole new screen (which, per the navigation contract, needs
its way-back chip and its dead-end test), profanity filtering, and a
delete-my-name path. It is the right **version 2**, built after launch,
when the feedback form can tell us whether the group chats actually want it.

### Rejected as the answer (but cheap garnish): challenge links

"DANIEL SCORED 315 — OUTLIVE HIM", carried in the share link, no server at
all. Already half-planned as G3's substitute. It is fun and costs about
half an evening, but it is not a leaderboard — it is a taunt with a
hyperlink. Worth doing as launch-week seasoning *if* an evening frees up;
it neither replaces nor blocks anything below.

### RECOMMENDED: the percentile board

After you finish a game's daily, one extra line appears on the summary you
already see:

> **TODAY'S FIELD** — your 84 beat 71% of today's Face Value players.

And on the full-house screen, one more:

> Your 312-point day beat 66% of everyone who finished all four.

Why this one wins, point by point:

- **It never shows an empty room.** There is no list, so there is no short
  list. Below a minimum crowd (say 20 scores for that game that day) it
  shows a graceful line instead — "Standings open once enough of today's
  scores are in" — and the app looks forward-leaning rather than deserted.
- **It is gentle by construction.** "You beat 71%" is private, personal,
  and comparative without being a ranking. Nobody is 47th. Nobody's name
  is above yours. The bottom of the field is never named or shown.
- **Cheating barely pays.** No name appears anywhere, so a forged score
  wins nothing visible; and one fake number among hundreds barely moves a
  percentage. The design removes the *incentive* rather than fighting the
  *method* — which is the only fight we can win (section 2).
- **It is almost weightless legally.** Nothing anyone typed is stored — no
  names, no free text — so there is no moderation surface and the privacy
  story stays one paragraph long (section 4).
- **It is the smallest real build.** One server endpoint, one database
  table, one strip of copy on screens that already exist. No new screen, so
  the navigation contract isn't even touched.
- **It answers the daily-ritual question exactly.** Same puzzle, same day,
  how did I do against the field — then it lets go of you. Tomorrow is a
  fresh board.

One honest limitation to accept: because everyone's "today" follows their
own clock (a New Zealand player's Tuesday starts 12 hours before a UK one),
early finishers compare against a smaller field. The copy says "today's
players *so far*" and the minimum-crowd rule hides the thinnest hours.
This is exactly how Wordle-family games behave and nobody minds.

---

## 2 · The cheating question, honestly

The browser computes the score, so the browser can lie. That was true of
share cards (the repo's own ruling on "signed share links" called
client-side signing security theatre and settled on treating scores as
*friendly claims*), and adding a server does not change the physics: a
determined person can always send us a made-up number. What a server
changes is that we can now **refuse the implausible and ignore the
repetitive**, which is all a game with no prizes needs.

How bad is it for the recommended design? **Barely.** A forged score on a
percentile board has no audience — there's no name, no podium, no prize —
and its effect is diluted across the whole field. The realistic damage is
statistical (someone scripting a thousand fake 100s to skew the curve), and
that is cheap to blunt:

- **Cap and shape checks** (a score is 0–100 per game; a submission carries
  its per-round breakdown and the parts must add up; anything else is
  discarded server-side).
- **One score per device token per game per day** (the database simply
  refuses a second row — first write wins, same as the ledger).
- **Same-day only** (the board only accepts a score for today's edition
  while that edition is current; archive and repair-window completions
  don't submit — the board is about *today's* field).
- **A light rate limit** (Cloudflare can throttle an address hammering the
  endpoint; this is a checkbox, not a build).

And that is where it should stop. No signed clients, no fingerprinting, no
anti-cheat arms race — those cost real evenings, annoy honest players, and
defend a prize that doesn't exist. **For this product's tone, a cheat who
quietly tells himself he beat 99% of players has already received his full
punishment.** If v2's friend groups arrive, cheating becomes social rather
than technical — Dave's suspicious 400 is Dave's group's problem, and they
know where he lives.

---

## 3 · Identity without accounts

The percentile board needs almost no identity at all — that's part of why
it's the right v1.

- **What the server needs:** a way to tell "the same phone submitting
  twice" from "two phones". The app mints a **random token** — a meaningless
  string of letters and numbers, invented on the device, tied to nothing
  (not your name, not your email, not your phone) — stores it inside the
  same saved blob as your streaks, and sends it with each score. That's the
  entire identity system in v1. No nickname exists anywhere.
- **Clearing storage / switching phones:** the app already has the **Carry
  tool** (`js/carry.js`), which packs your whole record into a link or code
  and merges it on the other side — built for the domain move and the
  Safari-to-installed-app hop. The token rides along by adding it to
  Carry's approved-luggage list (a small, well-understood change). So a
  player who carries their record keeps one identity; a player who wipes
  their storage without carrying gets a fresh token — and loses nothing,
  because v1 keeps no history worth losing (yesterday's field is gone
  anyway).
- **The trade-off, plainly:** a wiped device *could* submit a second score
  for the same day under its new token. On a percentile board this is a
  rounding error, and we accept it. The alternative — real accounts — is on
  the explicitly-discarded list and stays there.
- **v2 (groups) adds a chosen nickname**, stored on the device and shown
  only inside groups you joined. It travels via Carry like everything else.
  That's the moment identity gets heavier (moderation, deletion rights),
  which is exactly why it's deferred.

One principle to write into the code and the docs: **localStorage remains
the only home of a player's record.** The server holds a day or two of
anonymous scores for arithmetic, then bins them. The board is a postcard
the app sends, not a place your data lives. Nothing about streaks, the
ledger, or the epoch changes; "accounts/cloud sync" stays discarded.

---

## 4 · Privacy and legal (UK)

What v1 stores, in full: *edition number, four scores, a random token, a
timestamp.* No name, no email, no message, no location, no IP address kept.
Still, three things need doing properly:

1. **The privacy page must be rewritten the day this ships.** It currently
   promises scores "are never sent anywhere" — which becomes untrue the
   moment a score is submitted. New copy (draft): *"If you choose to
   compare your score with today's players, the app sends that day's
   score and a random token — a meaningless ID invented by your device,
   linked to nothing about you — to our server, which keeps it for up to
   30 days and keeps only anonymous daily totals after that. Say no and
   nothing is ever sent; everything else about the app works identically."*
2. **Make it opt-in, once.** The first time a summary screen could show
   the field, ask in-line: "Compare with today's players? [Count me in] /
   [No thanks]" — remembered forever, changeable from the privacy page like
   the analytics toggle. This keeps consent clean under UK GDPR (the UK's
   data-protection law), keeps the "no cookies" claim true (the token lives
   in the same local storage as everything else), and suits the house
   manners anyway.
3. **Retention as a promise:** raw score rows deleted after 30 days by a
   scheduled cleanup; only per-day aggregate numbers (how many played, the
   median) kept long-term. Cheap to build, and it keeps the honest sentence
   "we couldn't identify you from our data if we tried" true.

Because a random device token arguably counts as "personal data" in the
law's pedantic reading, one 10-minute homework item for you: the ICO (the
UK data-protection regulator) has a self-assessment tool for whether a
data-processing operation owes their small annual fee (~£40/year tier).
Most hobby-scale, no-tracking projects come out exempt or at the bottom
tier; worth checking once, not worth a solicitor.

**Nicknames are deliberately absent from v1** — they are user content, and
user content brings profanity filtering, a report path, and right-to-erasure
handling. All of that arrives only with v2 groups, where the audience is
"people who share a group code", the stakes are lower, and we can build the
blocklist + "email to remove a name" path calmly.

---

## 5 · The build, in stages

A necessary honesty first: this is **the app's first server-side code**,
and CLAUDE.md's architecture rules say "no backend". The amendment to
approve alongside this plan: *the app remains a static PWA that works
fully offline and stores everything locally; one small optional server
program may exist for community features; the app must behave perfectly
when that server is down or unreachable.* The tests will enforce that last
clause — every board strip must render (as silence or a gentle fallback
line) with the server unplugged.

**The machinery, in plain words.** The site now lives on Cloudflare Pages.
Cloudflare lets a site include a **Worker** — a small program that runs on
Cloudflare's computers, not the player's — and a **D1 database** (a simple
spreadsheet-like store the Worker can read and write). Both sit inside the
free tier at ludicrous headroom (the free daily allowance is roughly a
hundred thousand score submissions; a huge launch day might use one
percent of it). Crucially, Pages picks the Worker code up from a folder in
the same repo on the same `git push` — **no build step on the Mac, no
Node, no new deploy ritual**. One-time setup (~15 minutes of guided
clicking in the Cloudflare dashboard) creates the database and connects it.
D1 is preferred over the simpler "KV" store because percentiles need
counting and KV can garble simultaneous writes; D1 counts correctly.

### Stage 1 — the percentile board (v1). **2–3 evenings.**

- *Evening 1:* the Worker — one endpoint that accepts a validated score
  (caps, breakdown check, one-per-token-per-day, today-only) and answers
  "what beats what percentage" for each game; the database table; the
  30-day cleanup job.
- *Evening 2:* the client — the opt-in ask, the TODAY'S FIELD strip on the
  four summary screens and the full-house screen, the minimum-crowd
  fallback copy, the token in Carry's luggage list, the privacy-page
  rewrite and its toggle.
- *Evening 3:* tests (strip renders with server unplugged; opt-out sends
  nothing; no dead ends introduced — none expected, since no new screen
  exists), QA on the phone, BUILD+VERSION bump, ship.

### Stage 2 — friend groups (v2). **3–4 evenings, weeks later, gated on demand.**

Create a group → get a 6-character code → friends join → a private board
screen (with its ‹ chip and its dead-end test) shows the group's daily
scores and streak-flavoured bragging *inside the circle only*. Adds
nicknames (with a profanity blocklist and an email-to-remove path), group
tables in the same database, and the first real moderation surface. Build
it only if launch-month feedback or the group chats ask for it.

### Not in any stage

Global top-N, streak rankings, prizes, accounts, cloud sync of the record,
anti-cheat machinery beyond section 2's checks, push notifications about
your rank. Some are discarded product decisions; the rest are the anxious
versions of this feature.

---

## 6 · Launch-timing recommendation — plainly

**Do not ship this before launch. Build it the week after (target the week
of 17 Aug), and say nothing about it on launch day.**

The unsoftened reasons:

1. **The four evenings are already owed.** The checklist still contains the
   QA forcing switch and screen-state sweep, the visual refresh, the
   feedback entry points, Session D replays with human testers, the freeze,
   and the launch runbook. Every one of those touches launch day directly;
   the leaderboard does not. Spending two of four evenings on a brand-new
   backend means arriving at Monday with the known list unfinished.
2. **First-ever server code deserves an unhurried week, not a deadline
   sprint.** The one thing that must not happen on 10 Aug is a half-tested
   Worker misbehaving inside the first impression. The current app's
   superpower is that nothing about it can fall over; keep that superpower
   for launch day.
3. **The board is at its worst in week one anyway.** With small early
   crowds, the minimum-crowd rule would hide the percentile for most
   players most of the day — so shipping early buys almost nothing a
   player would actually see.
4. **The cost of waiting is only this:** launch-week scores never appear on
   a board (they're still scored, shared, and streaked exactly as now),
   and week-2 players get a pleasant surprise instead of a launch bullet
   point. A "new: see how you rank against the day's players" update in
   week 2 is also, usefully, a reason to message everyone again.

The risk of my recommendation, stated against myself: if launch goes
unexpectedly big, week one generates comparison appetite we can't feed for
a few days, and a rushed competitor of a feature ships into week 2 anyway.
I accept that risk; the mitigations are that the build is small, the design
above is already decided, and the challenge-link garnish can carry the
social load in the meantime for half an evening if wanted.

---

## 7 · Should the feedback form ride along?

**Yes — but second, and the launch plan doesn't change.** Launch with the
Google Form exactly as the checklist says: it costs zero build time, has a
comfortable reading view and notifications, and launch week is the wrong
moment to invent feedback infrastructure.

Then, when the leaderboard Worker exists, a native form becomes almost
free — one more endpoint, one more table, roughly **half an evening plus a
private reading page** (a secret-link page only you know, listing recent
feedback; grander admin tooling is not warranted). It is genuinely better
for this audience: no Google login smell, on-brand ink-and-cream, and the
build number and device details attach themselves automatically, which is
the half of every bug report people forget. It also stores user-typed text,
so the privacy page gains one sentence ("feedback you send us is stored so
we can read it — include an email only if you want a reply").

Fold it into the v1 leaderboard build as its final half-evening, or the
session after. Keep the Google Form as fallback until the native one has
survived a fortnight.

---

## What I'd do if it were my call

Spend the four remaining evenings exactly where the checklist already
points them, and launch on 10 Aug with no leaderboard and no mention of
one. The week of 17 Aug, build v1 precisely as in Stage 1 — percentiles,
opt-in, no names, 30-day retention — and ship it with the privacy rewrite
in the same deploy, announced as the week-2 update to every group chat
that got the launch message. Fold the native feedback form into that same
build's tail. Then wait: build friend groups only when a real person asks
for them, and never build the global top-N or the streak table — not
because they're hard, but because they're the anxious versions of this app.

---

## Questions only Daniel can answer

1. **The name and the line.** "TODAY'S FIELD — your 84 beat 71% of it" is
   a placeholder. What's the house wording? (This is a taste call, and it's
   most of what players will ever see of this feature.)
2. **Per-game, day-total, or both?** The plan says both (per-game lines on
   each summary, day-total on the full house). Trim to taste.
3. **The minimum crowd.** Percentile hides below N scores — is 20 right?
   Lower shows the field sooner; higher protects the empty room longer.
4. **Opt-in wording.** Happy with a one-time in-line "Count me in / No
   thanks"? (Auto-submitting without asking would be simpler but breaks
   the privacy posture I've assumed throughout.)
5. **The architecture amendment.** Formal yes/no: one small optional
   server program is now allowed, app must work fully without it. This
   goes into CLAUDE.md only with your explicit blessing.
6. **The ICO fee check** (~10 minutes on the regulator's self-assessment
   tool, possibly ~£40/year). Do you want a session to prepare the answers
   for you to click through?
7. **Challenge links as launch garnish** — want the half-evening version
   ("OUTLIVE HIM") in launch week, or keep the powder dry?
8. **Groups gate.** What would convince you v2 is wanted — a feedback-form
   mention count, a group chat asking, or your own itch?
