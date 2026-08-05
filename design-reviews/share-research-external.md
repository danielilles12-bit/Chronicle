# Shared result links in daily-game / streak apps — external research

Research only, no repo files touched. Compiled 5 Aug 2026 via web search (WebFetch was blocked on
nytimes.com and help.nytimes.com domains — noted where it limited verification).

## Confidence key
- **High** — corroborated by 3+ independent sources, or an official product page/blog/help doc.
- **Medium** — corroborated by 2 sources, or 1 official source with no independent confirmation.
- **Low** — single secondary/marketing-blog source, or inferred rather than directly stated.

---

## Findings

**1. Wordle's daily-result share is text only — no link at all.**
Tapping Share copies plain text to the clipboard: `Wordle ### X/6` plus a 5-wide emoji grid
(🟩 correct spot, 🟨 wrong spot, ⬛/⬜ absent). Multiple independent how-to guides describe this
and none mention a URL being embedded in the copied text — one explicitly contrasts it with
sharing "an image file," confirming it's plain text/emoji, not a link or attachment.
Source: [How-To Geek](https://www.howtogeek.com/108120/how-to-share-your-wordle-score-without-spoilers/), [iPhone Life](https://www.iphonelife.com/content/how-to-share-wordle-results-iphone-or-ipad), [Gamer Journalist](https://gamerjournalist.com/why-wont-my-wordle-share-how-to-fix/).
Confidence: **Medium** (consistent secondary sources; I could not reach NYT's own help page —
help.nytimes.com and www.nytimes.com both refused WebFetch — so this isn't confirmed against a
primary document).

**2. Because there's no link, "where does the tap land" doesn't apply to Wordle's core share loop.**
This is itself a finding: the single biggest daily-game share mechanism in the world does not try
to convert the share into a click at all. It's pure social proof/bragging inside a chat or feed;
discovery of the game itself happens independently (search, bookmark, app icon, word of mouth).
Confidence: **Medium** — inferred from (1) directly, not a claim any source states outright.

**3. Wordle's canonical URL always shows "today," with no date parameter needed.**
The game lives at `nytimes.com/games/wordle` (also documented historically as
`.../wordle/index.html`); the games hub is the separate `nytimes.com/games`. Because the URL has
no per-day state, anyone who does navigate there — whether prompted by a share or not — always
lands on the current day's puzzle. There is no casual path to a specific past day's puzzle via
this URL.
Source: [Wikipedia: Wordle](https://en.wikipedia.org/wiki/Wordle), corroborated by multiple current news write-ups referencing `nytimes.com/games/wordle`.
Confidence: **Medium** (URL shape confirmed by several sources; I could not load the live page to
verify first-time-visitor vs. returning-player UI differences — flagged as unverified below).

**4. NYT's Nov 2025 "Create Your Own Wordle" feature *is* a real, deep-linked share — a different
feature from the daily-result share.**
Subscribers can author a custom puzzle (any 4–7 letter word from the official list) and get an
actual shareable URL: **`nytimes.com/games/create/wordle/[unique-code]`**. Anyone who taps that
link can play that specific puzzle without a subscription or account — the link deep-links into
exact content, not the daily puzzle or the hub. This is the one clear example in NYT's own
portfolio of a personalized, content-specific share link.
Source: [Variety](https://variety.com/2025/gaming/news/wordle-create-your-own-puzzle-nyt-games-1236571309/), [Forbes](https://www.forbes.com/sites/erikkain/2025/11/06/wordle-just-got-a-massive-update-and-its-really-fun/), [Yahoo Tech](https://tech.yahoo.com/puzzles/wordle/articles/nyt-games-subscribers-now-custom-180000910.html).
Confidence: **High** (three independent outlets report the same URL shape and no-subscription-needed detail).

**5. Wordle, Connections, Strands and the Mini Crossword are free daily with no paywall; the
*archive* is what's gated.**
All four are playable daily at no cost and without an account. The official Wordle Archive
(1,000+ past puzzles back to June 2021) requires an NYT Games or All Access subscription; the
independent, unofficial `wordlearchive.com` and similar sites replicate it for free.
Source: [Fast Company](https://www.fastcompany.com/91116731/wordle-archive-new-york-times-1000-puzzles-subscribers), [TechCrunch](https://techcrunch.com/2024/05/07/nyt-games-wordle-archive-access-1000-past-puzzles), [Kotaku](https://kotaku.com/wordle-archive-unlimited-puzzle-word-game-josh-wardle-f-1848481517).
Confidence: **High**.

**6. The emoji-grid format was invented by a *player*, not NYT/Wardle engineering — Wardle just
adopted it.**
Josh Wardle saw a New Zealand-based player (@irihapeta) manually typing colored-square grids to
share results and built a Share button that auto-generates the same spoiler-free format. His own
tweet crediting her is the primary source.
Source: [Josh Wardle's tweet](https://x.com/powerlanguish/status/1471493886031773707).
Confidence: **High** (primary-source tweet from the creator).

**7. Wordle's share drove the acquisition, by NYT's own account of the numbers.**
NYT reported the game brought "tens of millions" of new users to the paper after the share
feature made results ubiquitous on Twitter, WhatsApp and Slack.
Source: [TechCrunch, May 2022](https://techcrunch.com/2022/05/04/wordle-new-york-times-user-growth/embed/).
Confidence: **Medium-High** (single primary business-press source, widely re-reported).

**8. Duolingo's streak-share artifact is a full-screen, high-contrast, aspect-ratio-tuned
celebration screen aimed at screenshots, not a link.**
Reporting on Duolingo's internal growth work says they added temporary instrumentation to track
*screenshot events* (not personal data) to find which in-app moments users were already
screenshotting to share — streak milestones (100/365 days) were the strongest signal — then
designed a dedicated full-screen celebration UI sized for Twitter/Instagram, reportedly producing
a 5–10x increase in organic sharing.
Source: [Startup Spells](https://startupspells.com/p/duolingo-screenshot-tracking-viral-strategy).
Confidence: **Low-Medium** (single secondary/newsletter source; I could not find an official
Duolingo engineering/product post confirming the "5–10x" figure — treat that number as unverified).

**9. Duolingo's "Friend Streak" is entirely in-app — no external link or OG artifact.**
The official Duolingo blog post describes Friend Streaks as started via in-app invite between
mutual followers, viewed by tapping the streak flame in-app. There is no mention anywhere in the
post of an external share link, URL, or Open Graph preview — it isn't designed to be shared
outside the app at all.
Source: [Duolingo blog: Friend Streak](https://blog.duolingo.com/friend-streak/).
Confidence: **Medium** (official primary source, but it's evidence of absence — the post simply
never discusses external sharing, so I can't rule out a since-added feature).

**10. Strava supports two distinct share artifacts: a real URL to the activity page, and a
separate, purpose-built branded image for Instagram Stories.**
Strava's own help docs describe copying a link to an activity/route (which would rely on that
page's Open Graph tags to unfurl in chat apps), and separately describe the app generating a
pre-styled image (distance, pace, time, mini route map) specifically for posting to Instagram
Stories.
Source: [Strava Support: How to Get and Share Links](https://support.strava.com/hc/en-us/articles/4418607378189-How-to-Get-and-Share-Links-From-Strava), [Strava Support: Sharing Your Activities](https://support.strava.com/en-us/articles/15401840-sharing-your-strava-activities).
Confidence: **Medium-High** (official support docs, though they don't spell out the OG-tag
mechanics explicitly — that part is my inference from the general link-unfurl finding in #12).

**11. Instagram Stories and DMs are close to the only Instagram surfaces that render OG link
previews at all, and Stories effectively requires an attached image (via the Link Sticker) to
show anything.**
Multiple link-preview-tooling vendors describe this consistently: a bare link with only an
`og:image` meta tag will often show nothing in Stories unless the image is present and properly
sized (Instagram crops toward center, recommends designing for that). This is the concrete
mechanical reason products like Spotify Wrapped and Strava default to an *attached, exported
image* for Stories rather than trusting a link's OG card.
Source: [OpenGraphPlus](https://opengraphplus.com/consumers/instagram/issues/no-preview-showing), [Share Preview blog](https://share-preview.com/blog/instagram-link-preview).
Confidence: **Medium** (consistent across several SEO/marketing-tooling sites, but none are
Meta's own documentation, which I did not locate).

**12. Spotify Wrapped's share is primarily an exported image/video card, and independent bug
reports show its link-based OG previews have been unreliable across some chat apps.**
A Telegram-client GitHub issue documents Spotify share links (with query parameters) failing to
show OG metadata correctly in Telegram, while stripped links work — evidence that even a large,
well-resourced product has had inconsistent OG-unfurl behavior, reinforcing why Wrapped leans on
a rendered image as the primary shareable artifact rather than depending on link previews.
Source: [GitHub: Telegram-iOS issue #875](https://github.com/TelegramMessenger/Telegram-iOS/issues/875).
Confidence: **Low-Medium** (a bug report, not a design statement from Spotify; it shows the
*symptom* that motivates image-first sharing, not Spotify's stated rationale).

**13. Heardle's growth loop worked (Wordle's full "social machinery" — one puzzle/day, 6 guesses,
spoiler-free emoji grid) but Spotify never connected it to the core app, and it shut down 15
months after Spotify acquired it.**
Multiple outlets frame the lesson the same way: viral acquisition without integration into the
retention engine doesn't compound — Heardle drove tens of millions of monthly visits at its peak
but was never linked into the Spotify app itself before Spotify killed it in 2023.
Source: [TechCrunch](https://techcrunch.com/2023/04/14/spotify-is-shutting-down-heardle-the-wordle-like-music-guessing-game-it-bought-last-year), [9to5Mac](https://9to5mac.com/2023/04/14/heardle-spotify-shutting-down/), [Startup Spells](https://startupspells.com/p/spotify-acquisition-heardle-wordle-clone).
Confidence: **Medium-High** (consistent narrative across independent press + one deeper analysis piece).

**14. Build-time/static Open Graph image generation is a well-established, no-live-server pattern
(Satori/Resvg, `@vercel/og`), but it presupposes a build step (Node/React) that doesn't exist in
this codebase.**
The standard technique renders HTML/CSS to an SVG/PNG once at build time (e.g., via GitHub
Actions) and ships the image as a static asset — genuinely serverless and compatible with a
static host. But every implementation found runs on Node/JS tooling (Satori, Vercel OG, Astro
integrations); none of the sources describe a Python-only equivalent.
Source: [Vercel: OG Image Generation](https://vercel.com/blog/introducing-vercel-og-image-generation-fast-dynamic-social-card-images), [theportraitofageek.com](https://theportraitofageek.com/2026/generating-og-images-at-build-time/).
Confidence: **Medium** (the technique itself is well documented; the "no Python option" gap is
a negative finding — I did not find one, not proof one doesn't exist).

**15. No hard, publicly available data comparing "attach an image file" vs. "share a text+link"
conversion rates in mobile share sheets was found.**
Searches for engagement/conversion studies on this specific comparison returned only
implementation docs (Apple's `ShareLink`/`UIActivityViewController`) and generic marketing-blog
assertions, no rigorous published study.
Confidence: **N/A — flagged as unverifiable.** Treat any claim of "X% better" you encounter
elsewhere on this topic with skepticism; I could not substantiate one.

---

## Comparison table

| Product | What's actually shared | Contains a link? | Where a tap lands | Paywall/account gate on first play? |
|---|---|---|---|---|
| **Wordle** (daily result) | Text: `Wordle ### X/6` + emoji grid | No | N/A — no link in the share itself; independent navigation to `nytimes.com/games/wordle` always shows *today's* puzzle | No |
| **Wordle "Create Your Own"** (Nov 2025) | Real link | Yes — `nytimes.com/games/create/wordle/[code]` | That exact custom puzzle | Playing: no. Creating: yes (subscriber-only) |
| **NYT Connections** | Text: 4-color emoji grid (yellow/green/blue/purple), mistake pattern | No (same pattern as Wordle per secondary sources; unverified against a primary doc) | N/A | No |
| **Duolingo streak** | Full-screen celebration UI, screenshot-driven | No | N/A (screenshot, not link) | N/A |
| **Duolingo Friend Streak** | In-app status page | No external artifact documented | Stays inside the app | Requires mutual in-app follow |
| **Strava** | Either (a) a real activity URL, or (b) an exported branded image (stats + mini map) for IG Stories | (a) Yes (b) No | (a) That activity's page on strava.com/app | Public activities viewable without login; full detail may prompt signup |
| **Spotify Wrapped** | Primarily an exported image/video card; link sharing exists but has documented OG-reliability issues on some platforms | Both, but image is the primary artifact for Stories | Link version opens the Wrapped content in Spotify app/web | Requires a Spotify account to view your own Wrapped |
| **Heardle** (pre-shutdown) | Text: emoji grid, Wordle-style | Unverified | Unverified | Free, no account (per general reporting) |
| **Framed / Globle / Worldle / Costcodle / Duotrigordle** | Emoji-grid style results (per general "-dle" convention) | Unverified for each individually | Unverified | Generally free, no account |

Rows marked "unverified" reflect genuine gaps — general search did not surface a source detailed
enough to state the exact share text/link behavior with confidence for those specific games.

---

## What this implies for a tiny static PWA with no backend (Yesternerd)

- **The single biggest precedent (Wordle) proves you don't need a link at all to get value from
  sharing.** Its share is pure social proof/bragging — text + emoji, copied to clipboard, no URL.
  If Yesternerd's Web Share API / clipboard-copy share text is just a spoiler-free result summary
  with no link, that is not an under-built version of the "real" thing — it's the exact pattern
  that drove NYT's biggest acquisition wins. Zero infrastructure required.

- **But Yesternerd is not yet "Wordle-famous," so it's reasonable to deviate and include a plain
  link anyway.** Nobody types `nytimes.com/games/wordle` from memory either — but "just Google
  Wordle" works because the brand is now ubiquitous. Yesternerd doesn't have that yet, so a bare
  `yesternerd.app` (or a specific game path) in the share text is cheap, adds no infra, and closes
  the gap Wordle's fame otherwise papers over.

- **Wordle's "always today, no date param" URL design is directly reusable and already fits the
  CLAUDE.md rules.** Because the canonical URL has no per-day state, a tapped link can never
  expose future or already-spoiled content — it just shows whatever issue is live *right now* to
  whoever opens it. That is exactly the constraint CLAUDE.md already enforces ("no casual path...
  may reach unaired content"), so a share link that points at the app root, or at a specific game
  without a date/edition parameter, is inherently safe by construction — no extra guarding needed.

- **Personalized, per-result OG images are the kind of infrastructure investment even NYT doesn't
  bother with for its flagship game.** Every dynamic-OG-image pattern found (Vercel OG, Satori,
  Astro build-time generation) assumes a Node/JS build pipeline, which conflicts with CLAUDE.md's
  "no build step, no Node" rule. A single **static, per-game** OG image (one for Face Value, one
  for Lifeline, one for Relic, one for Thread — hand-made or generated once with a Python script
  and committed to `assets/`) captures most of the link-preview value NYT itself gets, at zero
  ongoing infra cost. Treat true per-result dynamic OG images as low priority / not worth building.

- **If a "shareable image" artifact is ever wanted (Strava/Wrapped style, for Instagram Stories
  specifically), it should be a client-side, canvas-generated image the user explicitly exports —
  not a server-rendered OG card.** This is because Instagram Stories/DM are essentially the only
  Instagram surfaces that render link previews at all, and Stories needs an attached image (via
  Link Sticker) to show anything reliably — a bare OG-tagged link is likely to underperform there
  regardless of how good the tags are. A canvas export is pure client-side JS, so it doesn't
  violate the no-backend/no-build rule.

- **Landing destination: go straight into the game, not a marketing page.** No product researched
  inserts an interstitial, paywall, or hub redirect before a first play — Wordle/Connections/
  Strands/Mini are free with zero gate, and the one deep-link example found (Create Your Own
  Wordle) drops the recipient directly onto the specific content, no login wall. This matches
  Yesternerd's existing hub-and-spoke nav contract: a shared link should land in the relevant
  Moment/game screen (which already carries its own way-back-to-Home chip), not a separate landing
  page.

- **The Heardle cautionary tale is about integration, not sharing mechanics.** Heardle's share loop
  demonstrably worked (tens of millions of monthly visits at peak) but Spotify never linked it back
  into its core app, and it was cut 15 months later. The lesson for Yesternerd isn't about link
  design — it's that a share mechanism only compounds if it's tied to something the owner will
  keep maintaining and cross-promoting, which is more of a roadmap/ownership question than a
  technical one.

- **Don't over-invest based on unverified "best practice."** No rigorous data was found comparing
  image-attachment vs. text+link conversion rates, and generic deep-linking marketing-blog stats
  (e.g. "64% increase in owned-media conversions") come from ad-tech vendors (Branch, Adapty)
  without methodology disclosed — treat those figures as vendor marketing, not evidence, and don't
  let them justify infrastructure Yesternerd's architecture doesn't support.

---

## Explicitly flagged as NOT verified (do not treat as established fact)

- Whether a first-time visitor to `nytimes.com/games/wordle` sees a different UI (e.g. an
  onboarding/how-to-play modal) than a returning player — plausible from a couple of low-detail
  mentions, but not confirmed against the live page (WebFetch was blocked on the nytimes.com
  domain in this environment, so the page could not be inspected directly).
- Whether NYT Connections' share text includes any link — assumed to follow Wordle's no-link
  pattern based on format similarity, but no source explicitly confirms the absence of a link.
  the way Wordle's does.
- Exact share-text/link behavior for Framed, Globle, Worldle, Costcodle, and Duotrigordle
  individually — general "-dle" convention (emoji grid, presumably no link) is well attested, but
  no source detailed each game's actual copied text.
- Duolingo's reported "5–10x increase in organic sharing" figure from the screenshot-tracking
  growth project — sourced from a single newsletter analysis (Startup Spells), not an official
  Duolingo publication.
- Whether Strava's or Spotify's link-share flows actually rely on standard Open Graph tags
  mechanically (vs. some proprietary unfurl service) — inferred from general link-preview
  mechanics, not stated by either company directly.
