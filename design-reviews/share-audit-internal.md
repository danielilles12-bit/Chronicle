# Yesternerd share-link baseline audit (read-only)

Date of audit: 2026-08-05. Live edition tested: №37 (Wednesday). Mirror tested:
`https://yesternerd.pages.dev` (identical code + `data/` to `yesternerd.app`;
confirmed the OG image also resolves on `yesternerd.app`).

Files read: `js/sharecard.js`, `js/app.js` (`routeSharedPlay`,
`consumeShareLaunch`, `ensureGameData`, `boot`), `js/track.js`, `js/daily.js`
(`todayIndex`, `getEdition`, `dailyStatus`, `recordDailyCompletion`),
`js/mapgame.js` / `js/revealgame.js` / `js/connectionsgame.js`
(`startEdition`, `resumeFrom`, `showLockedResult`, `finishSession`/
`finishPuzzle`), `index.html` (OG/twitter meta), `tests/helpers.py`,
`tests/test_resilience.py`.

No repo file was modified. Screenshots and raw JSON live in this scratchpad
directory alongside this report.

---

## 1. Exact current share text, per game

All text comes from `js/sharecard.js`. `lines()` joins with `\n` and drops
the URL line if `shareUrl()` isn't passed one (it always is, here).
**Every builder hardcodes the domain `https://yesternerd.app/`** — sharing
from the `.pages.dev` mirror still points strangers at the real domain, not
back at the mirror.

### Face Value / Relic — `revealShareText(kind, issue, rounds, score)`
```
FACE VALUE №37 🖼️
🟩🟩🟩
300 pts · 5 scraps torn
https://yesternerd.app/?play=who&ref=share
```
(Relic swaps `FACE VALUE`/🖼️ for `RELIC`/🏺 and `play=who` for `play=what`.)
Row glyphs: 🟥 = wrong · 🟨 = correct but "laboured" (≥4 scraps torn, any
wrong guess, or MCQ-rescued) · 🟩 = correct and clean.

### Lifeline — `mapShareText(issue, rounds, score)`
```
LIFELINE №37 🗺️
✅✅✅✅⚰️
80 pts · 1 funeral
https://yesternerd.app/?play=map&ref=share
```
Row glyphs: ⚰️ = wrong · 🧭 = correct but hinted/MCQ-rescued · ✅ = clean.
The trailing line omits the "N hints"/"N funerals" clause entirely and reads
`"· a clean sweep"` if the round was hint-free and loss-free.

### Thread — `threadShareText(issue, d)`
```
THREAD №37 🧵
🟨🟨🟨🟨
🟩🟩🟩🟨
🟩🟩🟩🟩
🟦🟦🟦🟦
🟪🟪🟪🟪
1 slip — RENAISSANCE MEN had me.
https://yesternerd.app/?play=thread&ref=share
```
Human line: `"Flawless."` if perfect; `"{N} slip(s)[ — TITLE had me]."` if
solved with mistakes; `"{TITLE or 'The board'} beat me."` if lost.

### Full House — `fullHouseShareText(issue, scores, total, streak)`
```
YESTERNERD №37 — FULL HOUSE 🏛️
🖼️90 🗺️80 🏺70 🧵100 · 340 PTS
🔥 5-day streak
https://yesternerd.app/?ref=share
```
**No `?play=` param** — there's no single game to route to, so this is a
bare link (confirmed in `shareUrl()`: called with no argument). The streak
line is blank (not even an empty line — `lines()` filters falsy parts) if
streak ≤ 1.

### Obituary — `obituaryShareText(streak, fromIssue, toIssue)`
```
YESTERNERD ⚰️
My 12-day streak died.
RIP №25–№36. MEMENTO MORI.
https://yesternerd.app/?ref=share
```
Also a bare link.

### The image receipt (owner has decided to DROP this — what depends on it)
`drawCard()` in `sharecard.js` (lines 95–213) renders a 1080×1350 PNG onto a
canvas: the `yesternerd-wordmark-primary-v2.png` masthead, the
`antinous-sticker.png` corner sticker, the game glyph + score in a "ticket"
box, up to 4 emoji rows (with Thread's solved-group glyph prefix logic,
lines 179–201), and a rotated stamp (`CARPET DIEM` etc.). It is **only**
reachable through `performShare()` (line 228) when
`navigator.share && navigator.canShare({files:[...]})` — i.e. iOS/Android
native share sheets that accept files. Desktop, and any share sheet that
doesn't accept files, never sees it; those paths fall straight to
text-only `navigator.share` or clipboard copy.
**What breaks/simplifies if it's dropped:** `drawCard`, `sticker()`,
`wordmark()`, `imgReady()`, and the `card` parameter threaded through
`shareResult()`/`performShare()` all become dead code — none of it is used
by anything else. The two lazy-loaded PNGs (`antinous-sticker.png`,
`yesternerd-wordmark-primary-v2.png`) become unreferenced by this file
(worth checking if they're used elsewhere before deleting). The `trackAs`
outcome logic (shared/copied/cancelled/failed) is independent of the image
and is unaffected — it fires off `performShare()`'s return value regardless
of whether a card was attempted. **Nothing in the OG-preview or `?play=`
routing path depends on the image receipt** — those are fully independent
systems (the OG image is a static file referenced from `index.html`'s
`<meta>` tags; the in-app receipt is a canvas rendered only on the sending
device, at share time, never uploaded anywhere).

---

## 2. URL shape

```
https://yesternerd.app/?play=<who|map|what|thread>&ref=share
https://yesternerd.app/?ref=share                              (fullhouse/obituary — no play=)
```

- `ref=share` is GoatCounter's default campaign param (shows under
  Campaigns); `track.js`'s `initTracking()` scrubs `ref`/`utm_*` from the
  URL bar **after** the pageview is counted, so it never bakes into an
  "Add to Home Screen" start URL.
- `play=<game>` is read once by `routeSharedPlay()` and **always scrubbed**
  after routing, valid or not (confirmed live: after landing, the
  address bar / `location.search` shows only `?ref=share`).
- **The issue number is never in the URL.** Recipients always land on
  *their own* `daily.todayIndex()` for that game — a deliberate Wordle-style
  choice (comment in `app.js` line 731) — but the share **text** does carry
  the sender's issue number (`№37` etc., baked in at share time). If a
  stranger opens the link on a later day, the text they were shown says one
  issue number and the game that actually opens is a different one. This is
  never reconciled or flagged anywhere in the UI.
- No signing, no expiry, plain validated params — by design (comment
  references "the discarded X1 card").

---

## 3. State-by-state: what a tapper lands on

| # | Scenario | What actually happens | Live-verified? |
|---|---|---|---|
| a | **Brand-new visitor, no localStorage** | `routeSharedPlay()` fires `land-share-<game>`, awaits `ensureGameData`, then `start-from-share-<game>` and `g.launchDaily(today)`. **Face Value only** skips its first-run intro card by design (5 Aug decision) and drops the stranger straight into Round 1 of the tear mechanic. **Lifeline, Relic, Thread** all show the first-run `#intro-card` overlay first — Home is rendered underneath it (confirmed: `visible_view` reports `view-home` while `intro-card` is showing), so there's a brief Home flash before the explainer, and the real game view doesn't paint until the stranger taps "Play №37 ›". | **Yes**, all 4 games, screenshots below |
| b | **Returning player, already played that game today** | `consumeShareLaunch` still fires (module flag cleared correctly), but because `store.getDailyEntry(game, today)` exists, `startEdition` calls `showLockedResult()` instead of starting a game — the stranger's own tap on *their own* share link shows *their own* locked summary from earlier today (score, breakdown, Turn-the-page / Share / Encore / Home). **`start-from-share-<game>` still fires even though no game actually started** — the funnel event can't distinguish "began playing" from "hit the already-done wall." No `answer-from-share-<game>` ever fires for this path (nothing to answer). | **Yes**, all 4 games (seeded via `recordDailyCompletion`, the real write path) |
| c | **Returning player, mid-round in that game** | `startEdition` finds a saved session (`store.getDailySession`) and calls `resumeFrom(mode, key, saved, fromShare)` — the player resumes exactly where they left off (same torn scraps / mistakes / guesses), `resume-<game>` fires, and `fromShare` rides along so the **next answer they submit** fires `answer-from-share-<game>`. No visual acknowledgement that this was a share-link open specifically (looks identical to a normal resume) — nothing in the UI says "you were mid-round, welcome back via a shared link." | **No — code-read only.** No screenshot taken (not required by scope) and, more importantly, **`tests/test_resilience.py`'s `share_landing()` is the only automated test of `?play=` at all, and it only covers a single game (Thread) in the fresh-visitor state** — this resume-from-share path has zero automated coverage across all 4 games. |
| d | **Arriving after that game's daily is "complete"** | Ambiguous in isolation — two real readings, both checked: (1) *same-day, already finished* → identical to row (b) above (confirmed). (2) *days later, edition rolled over* → `getEdition()` always resolves via the manifest or its pool-arithmetic fallback (`js/daily.js` line 220+); there is no "ran out of content" failure mode for routing purposes — the stranger simply gets **today's** fresh Lifeline/Thread/etc., not the sender's. The share **text** they were shown, however, still says the sender's old issue number (see URL-shape note above) — so "arriving after the daily referenced in the text is gone" reads to the stranger as an unexplained number mismatch, not an error. | **Partially** — (1) is the same live-tested case as (b); (2)'s no-failure-mode claim is a code read of `getEdition`'s fallback logic, not separately live-tested against a real rolled-over date. |
| e | **`?play=` for a game whose data fails to load** | `ensureGameData(game, null)` is called with `statusEl = null` — so even on failure there is **no visible status update anywhere** (the "couldn't load — tap to retry" text only ever gets set on a *card-tap* retry, which passes a real `statusEl`). `land-share-<game>` still fires, `err-data-<file>` fires, but **`start-from-share-<game>` never fires** and the game never opens. The stranger is left looking at an entirely normal-looking Home page with **zero indication anything was even attempted** — the tapped game's hero card just says "Play ›" like any other day. | **Yes** — live-simulated by aborting `data/figures.json` + `data/worldmap.json` for a `?play=map` landing; confirmed exactly this. Screenshot: `sharelink-map-datafail.png`. |

---

## 4. OG / link-preview findings

Live-fetched from both `yesternerd.pages.dev` and `yesternerd.app` (identical):

```html
<title>Yesternerd — Four Daily History Games</title>
<meta name="description" content="Four little history games a day: Face Value, Lifeline, Relic and Thread. New games at midnight — same games as everyone else. Free, no sign-up.">
<link rel="canonical" href="https://yesternerd.app/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Yesternerd">
<meta property="og:title" content="Yesternerd — Four Daily History Games">
<meta property="og:description" content="Four little history games a day. New games at midnight — same games as everyone else. Free, no sign-up.">
<meta property="og:url" content="https://yesternerd.app/">
<meta property="og:image" content="https://yesternerd.app/assets/brand/social-card.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Yesternerd — four daily history games. A marble bust of Antinous wearing chunky black nerd glasses beside the Yesternerd wordmark.">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Yesternerd — Four Daily History Games">
<meta name="twitter:description" content="Four little history games a day. New games at midnight — same games as everyone else. Free, no sign-up.">
<meta name="twitter:image" content="https://yesternerd.app/assets/brand/social-card.png">
```

- **Image loads fine**: HTTP 200, `image/png`, confirmed **1200×630** (matches
  the declared `og:image:width`/`height` exactly) on both hosts.
- **Visual**: cream-and-black left panel with the YESTERNERD wordmark + "FOUR
  DAILY HISTORY GAMES" + a `yesternerd.app` chip; right panel is the
  marble Antinous bust in the square CMYK glasses on a yellow ground. Same
  asset the sticker/masthead use elsewhere — on-brand, legible at thumbnail
  size, no text-in-image legibility risk.
- **Nothing in these tags varies by game or by `?play=`/`ref=` params.**
  `og:url` is hardcoded to the bare domain — a `?play=map` link and a bare
  homepage link produce **identical** iMessage/WhatsApp/Discord preview
  cards: same generic title, same generic description, same generic
  four-games-in-one image. There is no per-game title ("Lifeline №37"), no
  score, no hint of what the sender actually played or achieved. For a
  redesign built around per-result sharing, this is the single biggest gap
  between what the share **text** promises (a specific game, a specific
  score, a specific emoji grid) and what the link **preview card** shows
  (a generic four-in-one house ad) — the two are currently unrelated
  systems that happen to travel together in the same message.

---

## 5. Share-funnel event inventory (from `js/track.js`)

Every event below is real and already firing in production; nothing here
needs new instrumentation to *observe* — only to segment further per-game
or per-state if the redesign wants that granularity.

**Landing / start / mid-round (per game: `map`,`who`,`what`,`thread`):**
- `land-share-<game>` → dashboard `1-land-share-<name>` — fires the instant
  a valid `?play=` param is seen, before data even loads.
- `start-from-share-<game>` → `3-start-from-share-<name>` — fires once that
  game's data is ready, **regardless of whether a fresh game actually
  started, a locked summary was shown instead (state b), or a mid-round
  session was resumed (state c)**. This is the biggest instrumentation gap:
  today it cannot distinguish "genuinely began a new round from a share"
  from "the link just showed them a screen."
- `answer-from-share-<game>` → `3-answer-from-share-<name>` — fires on the
  first guess/submit **only** for a genuinely-fresh or genuinely-resumed
  session (never fires for the locked-summary state b, since there's
  nothing to answer).
- `resume-<game>` → `3-resume-<name>` — fires whenever any daily is resumed
  (share-originated or not; doesn't distinguish the two).

**Share button outcomes (per surface: `thread`,`map`,`who`,`what`,`fullhouse`,`obituary`):**
- `share-<surface>` → `6-shared-<name>` — only on a *completed* native share
  (`navigator.share` resolved, no AbortError).
- `share-<surface>-copied` → `6-shared-<name>-copied` — clipboard fallback,
  counted as a success family (text still left the device).
- `share-<surface>-cancelled` → `6x-share-cancelled-<name>` — kept OUT of
  the 6-shared family entirely.
- `share-<surface>-failed` → `6x-share-failed-<name>` — sandboxed / no
  clipboard permission, kept out of 6-shared too.

**Nothing currently measures:**
- Which OG-preview a recipient actually saw before tapping (not measurable —
  no beacon fires until the page itself loads).
- Conversion from "saw the preview card" to "tapped the link" (WhatsApp/
  iMessage/Discord don't expose this to the site).
- Per-game breakdown of the image-receipt vs text-only share path (the
  `trackAs` event doesn't distinguish which branch of `performShare()` was
  taken — useful to know before ripping the image out, but recoverable from
  `navigator.canShare` capability alone if ever needed).
- Whether a `land-share-<game>` visitor was state (a)/(b)/(c)/(e) above —
  see the `start-from-share` gap noted above; the ledger/session state
  needed to tell them apart already exists client-side at that moment, it's
  just not being read into the event name.

---

## 6. Blunt list: what's confusing or broken for a stranger today

1. **A stranger arriving after the daily rolls over gets silently served
   a different puzzle than the one referenced in the text they were sent** —
   the share text says `№37`, the game that opens says `№41` (or whatever
   today is), with no acknowledgement of the mismatch anywhere. Intentional
   by design (Wordle convention: always play your own today), but it is a
   genuine point of confusion nobody has verified against a real user.
2. **A failed data load on a share link fails completely silently.** No
   error, no retry affordance, no "something went wrong" — the stranger
   just sees an ordinary-looking Home page and the specific game they were
   sent still says "Play ›" as if nothing happened. `land-share-<game>`
   and `err-data-<file>` both fire server-side, so Daniel *can* see this in
   analytics, but the stranger themselves gets zero signal. Verified live.
3. **The `start-from-share-<game>` event overclaims.** It fires identically
   whether the recipient (a) actually started a brand-new round, (b) just
   saw their own already-done summary, or (c) resumed a stale mid-round
   session — so today's dashboard cannot answer "how many share-link taps
   actually became new gameplay" without further segmentation.
4. **One static OG image/title/description for every link, regardless of
   `?play=` or game.** A Lifeline score-340 share and the bare homepage
   link render an *identical* preview card in iMessage/WhatsApp/Discord —
   all the per-game personality lives in the share **text**, none of it in
   the **preview card**, which is the first (and sometimes only, if the
   recipient doesn't open the text) thing a stranger sees.
5. **Inconsistent first-run experience by game.** Face Value skips its
   how-to-play intro entirely on a stranger's first daily; Lifeline, Relic
   and Thread all interpose a full-screen explainer + "Play №N ›" button
   before the actual game paints, with a Home flash underneath it. A
   stranger tapping two different game-shares from the same friend gets two
   different landing rhythms.
6. **The share domain is hardcoded to `yesternerd.app`**, so any testing or
   sharing done from the `.pages.dev` mirror still sends people to the real
   production domain — fine in practice (mirror and prod serve identical
   `data/`), but worth knowing if the mirror is ever used to demo an
   unreleased change.
7. **Automated test coverage for the whole `?play=` funnel is thin**: only
   `tests/test_resilience.py`'s `share_landing()` exercises it, and only for
   Thread, and only for the fresh-visitor + invalid-param states. The
   already-done (b), mid-round-resume (c), and data-failure (e) states have
   no automated coverage for *any* game — everything reported here for
   those states came from a fresh live/headless pass done for this audit,
   not from the existing suite.
8. **Seeding gotcha worth flagging to whoever writes new tests for this**:
   `tests/helpers.py`'s `seed_completion(page, game, n, score=80, detail=None)`
   defaults `detail` to `[]`. That's the right empty shape for Map/Face
   Value/Relic (`detail` is an array there) but the **wrong** shape for
   Thread, whose real `detail` is an **object**
   (`{solved, perfect, mistakes, guesses}`). Seeding Thread with the
   default produces a locked summary that says "GAME OVER — THE THREAD
   SNAPPED" while still showing the seeded score front and centre — this
   audit hit it firsthand (`sharelink-thread-returning.png` had to be
   redone with a realistic detail object). `tests/test_carry.py` line 202
   already calls `seed_completion` for Thread without a `detail` override,
   inside a loop over all 4 games — it currently doesn't matter there
   because that test never renders the Thread locked-summary screen, but
   it's a live footgun for the next person who does.

---

## Screenshots (this scratchpad directory)

| File | Shows |
|---|---|
| `sharelink-who-stranger.png` | Fresh visitor, Face Value share link → straight into Round 1 (no intro) |
| `sharelink-who-returning.png` | Already-completed-today, Face Value share link → locked summary "THE RECORD STANDS." |
| `sharelink-map-stranger.png` | Fresh visitor, Lifeline share link → Home underneath, "TWO DOTS, ONE LIFE" intro overlay, "PLAY №37 ›" |
| `sharelink-map-returning.png` | Already-completed-today, Lifeline share link → locked summary |
| `sharelink-map-datafail.png` | `?play=map` with `figures.json`/`worldmap.json` blocked → plain Home, no error shown anywhere |
| `sharelink-what-stranger.png` | Fresh visitor, Relic share link → Home underneath, "TEAR TOWARDS IT" intro overlay |
| `sharelink-what-returning.png` | Already-completed-today, Relic share link → locked summary |
| `sharelink-thread-stranger.png` | Fresh visitor, Thread share link → Home underneath, "FIND THE FOUR THREADS" intro overlay |
| `sharelink-thread-returning.png` | Already-completed-today, Thread share link → locked summary (re-seeded with a realistic `detail` object — see finding #8) |

Raw machine-readable results (visible view id, GoatCounter events captured
locally, console errors, seeded ledger entries) for every run above:
`share-audit-live-results.json` in this same directory. All GoatCounter
network calls were blocked during testing (host-level route abort on
`zgo.at`/`goatcounter.com`) so none of this polluted Daniel's real dashboard.
