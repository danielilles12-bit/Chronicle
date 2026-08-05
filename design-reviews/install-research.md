# "Add to Home Screen" — research + redesign brief
Yesternerd · 4 Aug 2026 · research for Daniel's morning review

---

## 0. What we ship today (the thing being rejected)

**Where it lives:** `index.html` lines 120–130 (`#install-tip`), `css/style.css`
lines 243–258, `js/app.js` lines 637–755 (`maybeShowInstallTip`,
`forceInstallTip`, `beforeinstallprompt` handler).

**What it does now:** after the first finished daily, a small strip appears at
the bottom of Home, under the four game rows. On iPhone it shows the pitch
sentence *plus* two illustrated steps *plus* two hand-drawn glyphs *plus* an ×
— four things competing inside a 14px box. On Android it shows the same
sentence plus a one-tap **Install** button.

**Why Daniel's "too busy, too confusing" is objectively right — five faults:**

1. **Four ideas in one small box.** Headline, reason, step 1, step 2, close ×.
   Nothing is bigger than anything else, so nothing is first.
2. **The glyphs are tiny** (13×17px) and sit *inside* running text, so the
   thing the user must actually hunt for on their phone is the smallest,
   least-visible element on the screen.
3. **It's at the bottom of a scrolling page.** It appears below four game
   rows — often below the fold, i.e. it interrupts nothing and is seen by
   nobody, or it is seen at the exact moment the user is leaving.
4. **The instruction is now WRONG on current iPhones.** It says "Tap Share in
   the bar below". iOS 26's default *Compact* Safari toolbar has no Share
   button — it's hidden behind the **⋯** menu (see finding 4). A user who
   looks "in the bar below" and finds nothing concludes the app is broken.
5. **It shows in Instagram/WhatsApp browsers, where the steps cannot work.**
   The check is `/iP(hone|ad|od)/` on the user-agent, which is *true* inside
   the Instagram in-app browser — but there is no "Add to Home Screen" in
   that share sheet. We are teaching a dance the user cannot do (finding 5).

Also: `#install-tip` has `border-radius: 12px` — the only rounded box in a
design system whose token file says in capitals *"the zine is SQUARE"*
(`--ch-radius-card: 0px`). It doesn't just read busy, it reads foreign.

---

## 1. Findings from the field (8)

### F1 — Never on arrival; always after a finished thing
Google's own pattern catalogue puts install promotion *after* a conversion
event (checkout, sign-up, completed order), and says of banners: "Wait until
the user has demonstrated interest… If the user dismisses your banner, don't
show it again unless the user triggers a conversion event." Nielsen Norman's
work on interstitials lands in the same place: a promotion shown *after* a
user finishes something ("finishing a chapter… completing a game level")
"interrupts a natural pause rather than blocking access, and this format is
much less intrusive and tends to convert better." Google's own A/B write-ups
report installs up **~30%+** when the prompt waits for real engagement.
→ *Yesternerd already gets this right: we wait for the first finished daily.
Keep that. It is the one thing not to change.*
Sources: [web.dev — Patterns for promoting PWA installation](https://web.dev/articles/promote-install),
[NN/g mobile interstitial research (summarised)](https://www.nngroup.com/reports/topic/mobile-and-tablet-design/),
[Evaluating and A/B testing PWA features](https://medium.com/@martin.schierle/evaluating-and-a-b-testing-pwa-features-3a8ffaf3e964)

### F2 — On iPhone, the instruction screen *is* the product
Safari has no install API and Apple has repeatedly declined to add one
(open developer-forum request, 2025). "Since every install is a manual Add to
Home Screen, **the instruction UX is your conversion surface**." Android
removes the friction for you; iOS makes you teach the gesture. So the iOS
screen deserves the design effort, not a footnote strip.
Sources: [PWA on iOS: install guide & limits (2026)](https://deepclick.com/resources/blog/progressive-web-apps-on-ios/),
[Apple developer forums — request for beforeinstallprompt in Safari](https://developer.apple.com/forums/thread/807603)

### F3 — The established iOS pattern is a *two-line, two-step card* — nothing more
The most-copied component in the ecosystem (`react-ios-pwa-prompt`, ~5 forks
and ports, plus every Vue/Svelte clone) shows exactly: title "Add to Home
Screen", one line of why, then **"1) Press the 'Share' button"** and
**"2) Press 'Add to Home Screen'"**, each with the real iOS glyph, and an app
icon. Two steps, two glyphs, one reason. Its defaults are instructive:
**first shown on visit 2** (never visit 1), **1s delay**, shown across **2
visits**, then it stops.
Its own README states the reason it exists: *"'Add to Home Screen' is tucked
away in the Share menu, and most users never find it."*
Sources: [react-ios-pwa-prompt](https://github.com/chrisdancee/react-ios-pwa-prompt),
[npm react-ios-pwa-prompt](https://www.npmjs.com/package/react-ios-pwa-prompt)

### F4 — ⚠️ NEW (iOS 26): the Share button is no longer in the bottom bar by default
iOS 26's redesigned Safari defaults to the **Compact** toolbar, which drops
the Share icon. The path is now **⋯ → Share → Add to Home Screen** — three
taps, and the first one is a button we have never mentioned. The
"Add to Home Screen" label is unchanged, and the dialog now carries an
**"Open as Web App"** toggle (on by default). Older iPhones / users who
switched back to the full toolbar still have Share in the bottom bar.
→ *Any redesign must cover both layouts without doubling the word count, and
must NOT point a fixed arrow at a location that may be empty.*
Sources: [MacRumors — iOS 26: add web app to Home Screen](https://www.macrumors.com/how-to/save-safari-bookmark-web-app-iphone-home-screen/),
[iDownloadBlog — iOS 26 Safari home-screen web apps](https://www.idownloadblog.com/2025/06/17/apple-ios-26-safari-web-apps-home-screen-bookmarks/),
[Glide community — iOS 26 Add to Home Screen workflow change](https://community.glideapps.com/t/ios-26-add-to-home-screen-workflow-change/84599)

### F5 — Inside Instagram/Facebook/TikTok browsers, installing is impossible — say so
Firtman's PWA guidance is explicit: *"If you are rendering an installation
banner or installation hint dialog… check if you are within a WebView because
the user won't be able to follow your steps. Hide that information or invite
the user to open the URL in the default browser."* On Android these WebViews
often have no service worker at all, so the site behaves like a
non-installable browser. Detection is a known, solved problem (the `inapp-spy`
library is the reference implementation; the signature check is small enough
to reimplement in ~15 lines with no dependency).
→ *This matters commercially: launch traffic from an Instagram or WhatsApp
link lands in exactly this browser.*
Sources: [firt.dev — 9 amazing PWA secrets](https://firt.dev/pwa-secrets/),
[inapp-spy](https://github.com/shalanah/inapp-spy),
[How to detect and escape in-app browsers](https://jhrun.com/2025/11/escape-in-app-browser-programmatically-introducing-a-zero-dependency-javascript-library/)

### F6 — Keep the promotion *out of the journey*, and remember the "no"
Every reputable source repeats three rules: keep promotions outside the flow
of the user journey; always allow dismissal; **remember the dismissal**.
Google's snackbar guidance even times it: show for **4–7 seconds**, and only
after "strong interest signals". Nobody recommends a permanent strip.
→ *Yesternerd remembers dismissal (`installTipDismissed`) but then never asks
again, ever. That's over-correcting: the trade is a single, well-earned
re-ask at a bigger moment (see timing recommendation below).*
Source: [web.dev — Patterns for promoting PWA installation](https://web.dev/articles/promote-install)

### F7 — On Android, use the native prompt — but note we're leaving the good dialog on the table
Chrome fires `beforeinstallprompt` only once the user has tapped the page and
spent **≥30 seconds** on it, so by our trigger (a finished daily) it has
always fired. Stashing it and calling `prompt()` from our own button is the
recommended pattern, and we already do it correctly. **However:** Chrome
shows a much richer install sheet — app screenshots and description — if the
manifest carries at least one `screenshots` entry (320–3840px, consistent
aspect ratio, `form_factor: "narrow"` for phones). `manifest.webmanifest`
currently has **no screenshots**, so Android users get the plain one-line
dialog instead of a mini App-Store listing.
Sources: [Chrome — Richer PWA installation UI](https://developer.chrome.com/blog/richer-pwa-installation),
[web.dev — Richer install UI pattern](https://web.dev/patterns/web-apps/richer-install-ui),
[web.dev — install criteria](https://web.dev/articles/install-criteria)

### F8 — "It keeps your streak safe" is not marketing — it is literally true, and citable
Since iOS 13.4/Safari 13.1, WebKit deletes all script-writable storage
(localStorage, IndexedDB, service-worker registrations) for a site after
**7 days of browser use without interaction** with that site. Home-screen web
apps are **exempt** — the installed app runs its own process with its own
counter, so the tally never accumulates. Yesternerd's entire record (streaks,
ledger, punch card) is localStorage. So: *not installed = a fortnight's
holiday can wipe your streak; installed = it can't.*
Sources: [Search Engine Land — what Safari's 7-day cap means for PWA developers](https://searchengineland.com/what-safaris-7-day-cap-on-script-writeable-storage-means-for-pwa-developers-332519),
[The Register — Apple on web app storage](https://www.theregister.com/2020/03/26/apple_relax_were_not_totally/)

---

## 2. The seven design principles I extracted

1. **One glance = one idea.** The idea is *"two taps and your streak is
   safe."* Everything that isn't that either goes small or goes away.
2. **The glyphs must be the biggest thing on the screen**, not the smallest.
   The user is being sent on a hunt; give them a picture of the quarry.
3. **Show them what they'll see, not what to do.** Draw the actual share-sheet
   row ("⊞ Add to Home Screen") so the destination is recognised, not read.
4. **Never point at a fixed screen location.** iOS 26 moved the Share button,
   and users can move the address bar to the top. Name the button, show its
   icon, and give a one-line fallback for the ⋯ menu.
5. **Right moment beats right words.** After a finished daily, at the natural
   pause — never on arrival, never mid-game.
6. **One "no" is respected; one re-ask is earned.** Dismiss = gone. Re-offer
   only at a moment that makes the pitch true (a 3-day streak).
7. **Never teach a dance the user can't do.** If we're inside Instagram's
   browser, the honest screen is a different screen.

---

## 3. The three directions mocked

All three use only cream/ink + one accent, square corners, hard shadows.
Screenshots are 390×844 (iPhone 14/15/16 logical size).

| | Direction | What it is | Verdict |
|---|---|---|---|
| **A** | **THE PASS** | Full-screen page after the daily. Huge headline, two giant numbered step plates, a drawn share-sheet row, "Not now" at the bottom. | **Recommended** |
| **B** | **THE STRIP** | Home stays as it is; one quiet ink-bordered line: "Keep your streak safe" + **Show me how ›**. Tapping opens A. | Recommended as A's *doorway* for the re-ask |
| **C** | **THE POINTER** | Small card pinned above the Safari toolbar with a big ink arrow pointing at the Share button. | **Rejected — see F4** |

**Why A wins:** it is the only one where the two glyphs can be big enough to
actually recognise, and the design system already has a precedent Daniel
signed off on this week — the v164 intro card, which "reads as a PAGE, not a
popup" and uses the ‹ back chip. The install teach is the same species of
screen: a one-time, one-idea, full-bleed poster.

**Why C is rejected** despite being the prettiest: an arrow pointing at a
button that isn't there (iOS 26 Compact toolbar, or address-bar-at-top) is
worse than no arrow at all — it actively teaches the wrong thing, and we
cannot detect which toolbar the user has.

---

## 4. Recommended timing (localStorage only, no backend)

| When | What happens |
|---|---|
| First finished daily | Nothing. They've just met us. *(change from today)* |
| **Second day they finish a daily** (i.e. a streak of 2 exists) | **THE PASS** opens once, full screen, right after the day's receipt. "Not now" closes it. |
| After a "Not now" | Home shows **THE STRIP** — one quiet line, no steps, dismissible with ×. |
| After the × | Silence. |
| **One earned re-ask:** the day their streak hits 7 | THE PASS opens one final time: "Seven days. Don't lose it." Then never again. |
| Already installed / desktop / no install path | Nothing, ever. |

Storage: `installPitchSeen` (count), `installPitchDismissed` (bool),
`installStripDismissed` (bool). Three booleans, no backend, no accounts.

**Why streak-2 instead of the first finish:** the hook is "it keeps your
streak safe", and on day one there is no streak to protect — the sentence is
a promise, not a fact. On day two it is a fact, and the user has proven they
came back, which is exactly the "strong interest signal" F1/F6 ask for.

---

## 5. The one thing Daniel still has to decide (webview wording)

If someone arrives from an Instagram, Facebook, WhatsApp or TikTok link, they
are inside that app's browser. Installing is **impossible** there (F5), so
they get a different screen: "open this in your real browser first."

**The open question is the wording, and it's a brand-voice call, not a
technical one:**

- **Option 1 — name the app:** *"You're in Instagram's browser. Tap ⋯ → Open
  in Safari."* — clearer, more helpful, and we can detect which app with
  reasonable confidence. Risk: naming other companies in our UI, and being
  wrong about which app if detection slips.
- **Option 2 — stay generic:** *"You're in an app's built-in browser. Open
  this page in Safari or Chrome to add it to your Home Screen."* — never
  wrong, never awkward, slightly vaguer for a non-technical user.

Mocked as `install-mock-webview.png` in Option 1 wording, with the Option 2
sentence printed underneath it for comparison. **Not built either way until
Daniel picks.**

---

## 6. Files (all in the scratchpad — no repo file was touched)

**Daniel's morning review page (visual, plain-language, phone-friendly):**
https://claude.ai/code/artifact/02da500a-6839-43e3-b924-502af26d9542

| File | What it shows |
|---|---|
| `install-current-ios.png` | **Before** — today's strip, live, at the bottom of Home |
| `install-mock-a.png` | Direction A, iPhone (**recommended**) |
| `install-mock-a-android.png` | Direction A, Android — native prompt, one button |
| `install-mock-b.png` | Direction B, the quiet strip, on the real Home |
| `install-mock-c.png` | Direction C, the pointer (rejected, stamped) |
| `install-mock-webview.png` | The Instagram-browser state (**open decision**) |
| `site/install-mock-*.html` | The mocks themselves (repo CSS + fonts, relative paths) |
| `installshots.py` | Regenerates every screenshot at 390×844 @2x |
| `install-review.html` | The review page above, self-contained |

Run `python3 serve.py` (serves `site/` on :8080), then `python3 installshots.py`.

## 7. Two follow-ups worth logging (not part of this redesign)

- **Add `screenshots` to `manifest.webmanifest`** (F7) — turns Android's plain
  install dialog into a mini App-Store listing with pictures of the games.
  Cheap: three PNGs and six lines of JSON.
- **The Safari-forgets-you problem is real for non-installers** (F8). If
  install conversion stays low, the "carry your record" flow (`js/carry.js`)
  is the safety net, and may deserve a mention on the strip.
