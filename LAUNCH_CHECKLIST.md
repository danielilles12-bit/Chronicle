# LAUNCH_CHECKLIST.md — the 10 days to Monday 10 August

*Written Fri 31 Jul 2026 from Daniel's brain-dump + the July launch review. This is
the operative pre-launch document — work through it top to bottom, tick things off
in the same session they land, and add anything new here rather than in a fresh doc.*
*Supersedes LAUNCH_PLAN.md as the to-do list (that file stays as rationale/history).*

**Owner tags:** `[DANIEL]` = only Daniel can do it. `[SESSION]` = a Claude Code
session does it. `[BOTH]` = Daniel decides, session executes.

**Already shipped — do NOT redo, only re-brand where marked ®:**
Share 2.0 emoji grammars + canvas share card ®, OG/social meta kit + social-card.png ®,
GoatCounter analytics, update plumbing (v95), fame-index content repair,
Sessions A + C of the launch review, 27 Jul rulings, known-face retirements (v139).

---

## 0 · Decision gates — Daniel, needed by Sat 1 Aug evening

Everything below flows from these. One reply covers it: e.g.
**"G1 = Clues Ago, G2 = refresh only, G3 = defer, G4 = ok"**.

- [x] **G1a — Rename: YES** (Daniel, 31 Jul). Name itself still TBD — not
      necessarily Clues Ago. New candidates must be collision-checked against
      UK sources before committing (sessions can run these checks on request).
- [ ] **G1b — The name.** Deadline **Sun 2 Aug evening** for the 10 Aug launch;
      after that the tester week erodes and the cheap fallback is 17 Aug (also
      a Monday — marketing-only date, epoch untouched). **Buy the domains
      within the hour of deciding — candidate domains are unregistered and
      unprotected. Don't tease the name anywhere before they're bought.** [DANIEL]
      *Fixed constraint:* renaming after launch is impossible — installed
      iPhone PWAs cannot migrate domains.
      *Rename scope, verified 31 Jul:* name appears in ~15 live app files +
      `assets/brand/social-card.png` + GoatCounter code; localStorage keys are
      `chronicle.*` (name-free — streaks untouched by any rename); app icons
      are name-free art. Execution ≈ half a day once the name lands.
- [ ] **G2 — Visual direction.** Recommendation: NO full redesign (the look is
      the app's strongest asset per the July scorecard, and there's no time);
      YES to the targeted refresh list in §3. [DANIEL]
- [ ] **G3 — Leaderboard.** Recommendation: defer post-launch (needs a write
      backend we don't have; Cloudflare Worker + KV is the cheap path once
      hosting moves). Optional pre-launch substitute: challenge links
      ("DANIEL SCORED 315. OUTLIVE HIM." via URL params, no backend). [DANIEL]
- [ ] **G4 — Freeze date.** Editions 42–48 (launch week) content-frozen by
      Sat 8 Aug. [BOTH]

---

## 1 · Rename & rebrand *(execution blocks on G1b — but prep does NOT)*

**Prep now, no name needed:** [SESSION]
- [ ] Rename manifest: exact file/line list of every name occurrence in the
      live app (initial sweep done 31 Jul — ~15 files; excl. attic/docs/stale
      `.claude/worktrees` copy, which should be cleaned up)
- [ ] Social-card + masthead layout as a template with placeholder wordmark
- [ ] Redirect + cutover runbook written (old→new 301s, GoatCounter swap steps)
- [ ] Cloudflare account created so the cutover isn't blocked on it (account
      creation is Daniel's — sessions cannot create accounts) [DANIEL]

**Execution, the hour the name lands:**
- [ ] Buy new .app domain (+ .com if free) at Namecheap [DANIEL]
- [ ] String/asset sweep: `<title>`, meta description, OG/twitter tags, manifest
      name + short_name, share-text last line, About / Sources / How-to-play /
      privacy pages, 404, README, sitemap/robots [SESSION]
- [ ] Redesign `assets/brand/social-card.png` + masthead wordmark under new name
      (keep the pop-zine visual system — this is a rename, not a redesign) [SESSION]
- [ ] Domain + hosting move in one step: Cloudflare Pages (Session 8 spec),
      new domain live, deadfamous.app 301-redirects to it [SESSION]
- [ ] **Early-user data handoff:** page on the old origin that packs
      localStorage into a link fragment; importer on the new origin. Streaks are
      sacred (locked decision №3) — this is how we honour it across origins.
      Bonus: the same mechanism doubles as a Safari → installed-app transfer
      tool (see §2, streak investigation). [SESSION]
- [ ] Personal note to the handful of early users with their handoff link [DANIEL]
- [ ] New GoatCounter site code; keep old one recording redirects [SESSION]
- [ ] Re-verify link unfurls (iMessage, WhatsApp, Discord, X) on new domain [BOTH]
- [ ] Daniel reinstalls on his phone from the new domain [DANIEL]

## 2 · Screens & state correctness *(the "some screens never show up on my phone" item)*

- [ ] **Screen-state inventory:** enumerate every gated/one-shot screen —
      first-visit orientation, install nudge, per-game intro cards, streak
      obituary, milestone celebrations, full-house, update bar, encore offer,
      MCQ rescue, archive edge states, candlelit (if on) [SESSION]
- [ ] **QA forcing switch** (e.g. `?qa=1` debug menu) that can summon any of the
      above on demand — this is how Daniel finally *sees* new-user-only screens
      on his own phone, and how every future session retests them [SESSION]
- [ ] Fix what the sweep finds broken [SESSION]
- [ ] **Streak/persistence investigation** — Daniel reports it may not be
      working. Three most likely culprits, in order:
      1. iOS keeps *separate* storage for Safari vs an installed home-screen
         app — play in one, the other knows nothing about it;
      2. Safari wipes site data after 7 days of not visiting (installed apps
         are exempt);
      3. Instagram/WhatsApp/LinkedIn in-app browsers are a third, throwaway
         storage.
      Reproduce, then fix messaging/handoff accordingly. Add Playwright
      day-rollover tests: streak increments, 1-day grace, obituary. [SESSION]
- [ ] **Device matrix:** iPhone 13 (physical if borrowable; else iOS Simulator
      Safari from this Mac), Android Chrome (borrow one — install flow differs
      completely from iOS), desktop [BOTH]
- [ ] **In-app browser pass** (IG / WhatsApp / LinkedIn webviews — this is where
      launch traffic actually lands): detect webview → gentle "open in your real
      browser" nudge, since webviews can't install and don't keep data [SESSION]
- [ ] Update-delivery check: push a trivial bump, confirm Daniel's installed
      phone receives it via the pull-to-refresh bar [BOTH]

## 3 · Targeted visual refresh *(blocks on G2; timebox: two evenings)*

- [ ] Install prompt redesigned — currently the worst screen; give it the zine
      treatment + the true hook: "it keeps your streak safe" [SESSION]
- [ ] Per-game intro cards — full-bleed art, logos at proper scale, stop wasting
      the screen [SESSION]
- [ ] Double-edge/shade ruling: mock both flat and double-edged boxes on one
      screen, Daniel picks in 30 seconds [BOTH]
- [ ] One consistency pass over moment/celebration screens [SESSION]

## 4 · Feedback flow *(new build — nothing exists today)*

- [ ] Google Form: 2 fields (what happened / what should happen), no login [DANIEL]
- [ ] Entry points: a menu item + a quiet line on the full-house screen, opening
      the form with build number + device auto-appended; mailto fallback;
      GoatCounter event on tap [SESSION]
- [ ] Launch-week habit: check the form every morning, triage into this file [DANIEL]

## 5 · Content close-out (Sessions B + D from the July review)

**Session B's 300-start audit: SUPERSEDED 31 Jul** — Daniel's sheet-based 30-day
approval covered it: build_launch_audit.py renders the true opening scrap of
every round (curated overrides honoured — the tool dishonesty bug was fixed
before his audit), and his nominated swaps were applied in commit 56acc517.
What survives is the legal layer taste-approval can't cover:

- [x] **Rights hygiene — DONE 31 Jul** (Opus deep audit, all 48 launch-window
      images verified against Commons wikitext + pixel provenance; report in
      tools/out/rights-check-2026-07-31/). Shipped: 16 credit records fixed
      (dual-licence Commons trap — photographs mis-stored as "Public domain");
      4 items retired on subject copyright (`little-mermaid-statue`,
      `centre-pompidou`, `motherland-calls`, `louvre` — all reserve:true);
      slots recast per Daniel: ed 38 → Space Shuttle, ed 41 → Vasa,
      ed 45 → Hoover Dam (Cutty Sark held out: name readable on her bow at
      zoom = broken medium); schedule-aware MCQ distractors regenerated;
      new validate_reveal.py gate (CC BY ⇒ licence URL + author);
      3 new HOUSE_RULES entries.
- [ ] Rights follow-ups, NOT launch-blocking: retier `cutty-sark` to easy
      before staging; `daria-i-noor` + `john-the-baptist` need real
      photographer credits before staging (stored "authors" are the artists);
      `lenin` is GFDL-only (awkward licence — swap image when convenient);
      `sacagawea` provenance unverifiable (Commons source gone); full
      790-image verification backlog [post-launch]
- [ ] Pool intake debt — NOT launch-blocking (nothing staged in the window):
      Cleopatra asp-painting swap, Mihrimah + remaining unrescuables, 20 retired
      figures' Lifeline map entries [post-launch]
- [ ] **Session D:** targeted replay of 3 / 16 / 23 / 30 Aug boards; human-tester
      round (Daniel recruits — status?); fix fallout [BOTH]
- [ ] Freeze editions 42–48; full suite green; fresh-profile QA sweep;
      Lighthouse ≥ 90 [SESSION]

## 6 · GTM — Daniel executes, product supports

- [ ] Outreach lists: WhatsApp groups (highest conversion — do these first),
      IG close friends/stories, LinkedIn; personal message templates, not
      broadcast blasts [DANIEL]
- [ ] Creator DM list: 3–5 mid-tier history TikTok/YouTube creators
      (10K–500K) [DANIEL]
- [ ] `press.html` one-pager: screenshots, blurb, contact — so DMs look pro [SESSION]
- [ ] Week-1 seeding (from the researched plan): topic-matched subreddits
      (r/WebGames, r/InternetIsBeautiful — we qualify, no signup), Show HN,
      hey.gg + Kottke emails, the Goalhanger long-shot note, -dle directory
      submissions [DANIEL]
- [ ] **Raw creative capture:** screen-record real gameplay after the rebrand —
      feeds launch posts now and paid ads later [DANIEL]
- [ ] Launch-day runbook: what posts when, GoatCounter watch, hotfix ritual
      (BUILD+VERSION bump, ~5 min deploy lag) [SESSION drafts, DANIEL runs]

---

## Day-by-day

| When | What |
|---|---|
| **Fri 31 Jul – Sun 2 Aug** | Name-independent work runs NOW: §2 QA switch + streak investigation, Session B, §1 rename prep, §4 feedback flow, §3 mocks · Daniel: name call by Sun evening → domains bought same hour → rename execution |
| **Mon 3 – Wed 5 Aug** | Rename/move DONE early (testers must install on the final domain) · §2 correctness + streak investigation + device passes |
| **Wed 5 – Fri 7 Aug** | §3 refresh · §4 feedback flow · Session D replays + human testers |
| **Sat 8 – Sun 9 Aug** | Freeze + full QA + Lighthouse · §6 GTM prep + runbook |
| **Mon 10 Aug** | Launch: WhatsApp waves morning, IG midday, LinkedIn afternoon; present all day; hotfix loop live |

## Explicitly deferred — post-launch backlog, do not build now

- **Paid social + creatives** — playbook when ready: 9:16 vertical, 15–30 s,
  hook in first 2 s ("Only 4% get this Cleopatra one right"), gameplay
  screen-recording, end-card with name + "free, no signup". Made in CapCut or
  Canva from the §6 raw captures; run via Meta Ads Manager (needs IG
  professional account + FB page); test at £5–10/day, 2–3 variants. Gate:
  organic retention data first.
- **Leaderboard** — only if the feedback form shows demand; Cloudflare
  Worker + KV opt-in daily board (initials + score, once per day) fits the
  no-login architecture.
- Monetisation · Permanent Exhibition · push notifications · vague-clue sweep ·
  10→5 round-count decision · remaining ~109 image rights.
