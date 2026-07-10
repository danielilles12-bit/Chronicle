# Dead Famous — The Launch Plan
*Written overnight 2026-07-09 → 07-10. Nothing in here has been built or pushed — this is the proposal.*
*Companion pieces: **morning-board.html** (the interactive version of this plan — open it first), **launch-demos/share-card-lab.html** and **launch-demos/closer-than-you-think.html** (two working demos).*

---

## The one-paragraph verdict

The app is already good — distinctive look, four solid games, a proper daily engine, real personality. What it's missing is not another game or more polish: **it's missing its growth loop.** Wordle didn't spread because it was the best word game; it spread because the *result you pasted into the group chat* was spoiler-free, instantly recognisable, and a little smug. Dead Famous currently shares plain numbers, only after finishing all four games, with no link — and a pasted link unfurls as a blank nothing because the site has zero social meta tags. Fix the share loop, make the streak visible, set up the two one-way doors (domain, epoch) correctly, and you have a genuine shot. Everything below is ordered by how much it moves that needle.

## What I did tonight

- Played every game fresh at phone size (screenshots in the board), read every share/streak/daily line of code, weighed every asset.
- Ran three deep research passes: (1) what actually made daily games spread and retain, with sources; (2) how 12 comparable indie games got their traction, incl. Timeguessr, the closest comp; (3) the 2026 technical facts for PWA launches — iOS push, link unfurling, GitHub Pages custom domains, analytics.
- Built two working demos so you can feel the two biggest proposals instead of reading about them.
- Changed nothing in the app.

## The scorecard — where we stand against "hit criteria"

| Hit ingredient | Status |
|---|---|
| Distinct look nobody else has | ✅ Strongest asset. Nothing in the "-dle" space looks like this |
| Same puzzle for everyone daily (water-cooler effect) | ✅ Engine already does this properly |
| No sign-up, no ads, instant play | ✅ Qualifies for the best launch venues (r/InternetIsBeautiful bans sign-up products) |
| First puzzle winnable by a stranger | ✅ Monday recipe is easiest; launch on a Monday |
| Streak with forgiveness | ✅ Built (1-day grace)… ❌ but invisible until you finish all 4 games |
| **Shareable, recognisable, spoiler-free result** | ❌ **The gap.** Numbers-only, full-house-only, no link, no emoji identity |
| Links that unfurl beautifully in chats | ❌ Zero OG tags today — pasted links look dead |
| Fast first load for link-tap visitors | ⚠️ 2.3 MB cold load; can be roughly halved for ~an evening's work |
| Analytics to see if any of this works | ❌ None |
| A "wow" fact engine for TikTok-era sharing | ⚠️ That's the fifth-game proposal (demo attached) |

---

# ACT I — Build the growth engine (week 1) · the product work that matters most

### 1. Share 2.0 — the single highest-impact change ⭐ my top recommendation
Every game gets a share button on its own summary screen (not just the full house), each with its own one-glance emoji grammar:

- **Thread 🧵** — Connections-style colour grid of your guesses (already how people expect to brag)
- **Lifeline 🗺️** — `✅✅🧭✅⚰️✅✅🧭✅✅` (clean / needed a hint / gave up = funeral)
- **Face Value 🖼️ / Relic 🏺** — `🟩🟩🟨🟩🟥…` per round + "23 scraps torn"
- **Full house 🏛️** — the combined receipt + streak flame
- **The obituary gets a share button.** "My 41-day streak died. RIP Issues 12–53. MEMENTO MORI" is the funniest, most human share in the app and right now it's a dead end.

Format rules (from the research): one headline line, one emoji row that encodes the run without spoiling anything, one human brag/wound line, the domain on the last line. Wordle famously had no link — but Wordle was googleable in one word; every successful indie comp (Framed, Globle, Bandle) includes their short domain. We should too.
Plus: generated image receipt (the canvas card in the lab demo) offered via the iOS share sheet alongside the text, with copy-text fallback. **Open share-card-lab.html — this is all built as a working mock.**
*Effort: ~1 overnight + a review round. Depends on decision #2 (domain) for the URL line.*

### 2. Make pasted links unfurl properly — OG/social meta kit
Static `og:` + `twitter:` tags in index.html + one designed 1200×630 social card image (pop-zine masthead style) + correct `theme-color`. Verified against how iMessage/WhatsApp/Discord/Slack/X actually read tags in 2026 (details in board). Without this, every link anyone pastes anywhere looks broken. *Effort: small — an hour or two including the card design.*

### 3. Analytics — GoatCounter
Free, no cookies, no consent banner needed, one script tag, supports custom events. Events: page view, game started/finished (per game), share tapped, install-nudge tapped. Without this the launch is blind — we won't know which games retain, where people drop, or whether shares convert. *Effort: small.*

### 4. Performance diet
2.3 MB → target under ~1.2 MB cold load: quantize the 582 KB stamp PNG (→ ~150 KB), re-crush the icon PNGs, subset the five font files (pyftsubset, fits your no-Node setup), lazy-load the reveal-game JSONs. Every launch-day visitor arrives cold via a link tap. *Effort: ~half an evening.*

# ACT II — Deepen the ritual (week 2)

### 5. Put the streak on the masthead
A small flame chip next to the dateline: `🔥 5`. Tapping it shows a mini streak calendar. Duolingo's own data: reaching a 7-day streak makes users 3.6× likelier to continue; celebration weighted toward days 2/3/5/7 (a little stamp animation on the celebration screen at those milestones). The mechanic already exists — this is pure surfacing. *Effort: ~1 evening.*

### 6. Thirty-second orientation for strangers
No tutorial (research is clear: dailies that teach-by-playing win). Just one dismissible line under the masthead on first visit: *"Four little history games. New issue at midnight. Same issue as everyone else."* — plus the countdown moved somewhere a non-finisher can see it. *Effort: small.*

### 7. Install nudge with a real reason
After first game completed (the peak-delight moment): "Add to Home Screen — it keeps your streak safe." That last part is literally true: Safari wipes site data after 7 days of not visiting for non-installed sites; installed apps are exempt. The current tip exists but fires without a moment or a reason. *Effort: small.*

### 8. Open-items cleanup (from the last build)
Thread's daily summary → proper receipt like the others; per-game intro cards; "first tear free" hint copy pass; **candlelit theme decision** — it's fully built in CSS but nothing ever turns it on. Cheapest charming option: auto-switch after local sunset ("the museum dims after dark"), with a manual toggle in the corner. Or cut it for launch. *Effort: ~1 evening for the lot.*

### 9. (Stretch) Challenge links
"Beat 315" — share URL carries `?beat=315&issue=12`; the friend's device shows a little "DANIEL SCORED 315. OUTLIVE HIM." banner. No backend needed. Strong second loop after broadcast sharing. *Effort: ~1 evening. Fine to park.*

# ACT III — Launch operations (week 3)

### 10. ⚠️ The domain — a one-way door that must be decided FIRST
Technical finding of the night: **installed iPhone PWAs cannot migrate to a new domain.** iOS has no mechanism for it (Chrome's new migration API explicitly excludes cross-site moves), and once a custom domain is set, GitHub Pages force-redirects the old github.io URL. Translation: whatever URL we launch under is the URL forever — and anyone who installs under `danielilles12-bit.github.io/Chronicle/` is stranded there. **Decide the domain this week, wire it up (I have the exact GitHub steps), re-install on your phone, and only then launch.** Cost: ~$10–20/year. Candidates to react to: `deadfamous.app`, `deadfamous.games`, `deadfamous.day`, `playdeadfamous.com`. This also unblocks the share-text URL line (#1) and the OG tags (#2).

### 11. Launch-day checklist (I'll script what's scriptable)
- Set `EPOCH` to launch day — **a Monday** (easiest recipe day = winnable first puzzle for every stranger; the schedule is already front-loaded easy early-week)
- `ARCHIVE_PREVIEW_EDITIONS`: Infinity → ~7
- Wipe test ledgers / fresh QA sweep on a clean profile; cross-browser pass (iOS Safari, Android Chrome, desktop); Lighthouse ≥ 90
- Content spot-check of Issues №1–7 (the ones everyone will actually see)
- sw.js VERSION bump ritual continues every push

### 12. The seeding plan (you execute; the product supports it)
Ranked by evidence from the comp research — the pattern across Bandle/Immaculate Grid/Globle is *one influential share, topic-matched community, founder present daily*:
1. **DM 3–5 mid-tier history TikTok/YouTube creators** (10K–500K followers) with the play link — this exact thing was the accidental inflection point for two comps; we do it on purpose
2. **Topic-matched subreddits, never tech ones** (Globle's creator: r/geography worked, r/webdev = zero): r/WebGames, r/InternetIsBeautiful (no-signup rule = we qualify), history subs matched to strong content days
3. **Show HN** (`Show HN: Dead Famous – daily history games…`), be present in comments all morning
4. **Email hey.gg** (a podcast/blog whose entire beat is interviewing daily-game creators) and **Kottke.org** (has covered new dailies ~monthly) — warm targets, not cold pitches
5. **Long-shot, zero-cost:** a short charming note to Goalhanger (The Rest is History) — the audience is 12M downloads/month and it's the exact taste match
6. Submit to the "-dle directory" sites (listdle, dles.gg, etc.) — 20 minutes, compounding SEO
7. A tiny `/press.html` one-pager (screenshots, blurb, your contact) so pitches look pro

# THE BIG BET (pick one, or neither)

### A. "Closer Than You Think" as game five ⭐ my recommendation — **play the demo first**
The proximity game from your own backlog, prototyped tonight: *Cleopatra — closer to the Great Pyramid or the Moon landing?* Eight rounds, timeline-bar reveal, 🤯 share grammar, "History fooled me 3 times."
Why I think it's the launch headline: every single round is a self-contained wow fact — i.e. **native TikTok/group-chat ammunition** (the seeding plan's creators need exactly this); the 🤯 emoji row is the most distinctive share grammar in the whole app; and it's the only game a total stranger can play with zero knowledge and still enjoy losing.
Cost if approved: ~2–3 overnight builds (game + wiring into rows/engine/sw) + a content sprint (~90 verified rounds = 3 months of dailies) + fact-check pass per our pipeline. Fits before launch if we start this week.

### B. The Permanent Exhibition (the collection)
Every solved figure/relic becomes a card in your own museum wing; completion meters per category. The strongest *retention* idea on the list and very on-brand — but big (new views, data model, save format). My take: **post-launch update №1**, not launch — it also gives week-2 players a reason to return when press traffic fades.

### C. Neither — polish only
Legitimate. Acts I–III alone are a coherent launch.

# What I deliberately did NOT plan

- **Monetization** — the research is unambiguous: bolting ads/paywalls onto a young daily game kills the exact promise that makes it spread. Park until traction. (A Ko-fi tip link is harmless if you ever want one.)
- **Push notifications** — iOS supports web push for installed PWAs now, but it needs a push server (GitHub Pages has none) and only reaches installed users anyway. Post-launch project.
- **App Store wrapper** — the PWA *is* the distribution advantage (instant play from a link). Revisit only if the game earns it.
- **Round-count changes** (10→5 rounds for Face Value/Relic to shorten sessions and double content runway) — real trade-offs both ways, touches the cursor math, needs your call with analytics data, not a pre-launch gamble. Flagged as a decision, not a recommendation.

# The 7 decisions I need from you

1. **Share 2.0** — approve the grammar in the lab (or mark up what to change)?
2. **Domain** — which name? (This unblocks #1, #2, and the whole timeline.)
3. **Big bet** — A (Closer Than You Think, pre-launch), B (Exhibition, post-launch), or C (neither)?
4. **Launch Monday** — which one? (~3 weeks out suggested; EPOCH follows it.)
5. **Candlelit** — wire to sunset, or cut for launch?
6. **The stray files** — ~15 design-exploration files sit untracked in the folder (this plan, the boards, old logo reviews). Next "push" they go public. Gitignore them, or don't care?
7. **Streak forgiveness upgrade** — happy with the current 1-day grace, or add a Duolingo-style "streak repair" (do yesterday's missed games from the archive within 48h to heal it)? Small build, big churn saver, slightly dilutes streak purity.

Reply in the morning with e.g. **"approve 1, 2=deadfamous.app, 3=A, 4=Aug 3, 5=sunset, 6=gitignore, 7=keep"** — or open morning-board.html, tap through, and paste what it generates. I'll turn approvals into a build schedule.
