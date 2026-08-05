# The Percentile Board — build plan v2 (FINAL, approved to build)
5 Aug 2026 · supersedes v1 · v1's GPT critique incorporated · Daniel's rulings baked in

**Status: APPROVED TO BUILD NOW (Daniel, 5 Aug 2026).** Daniel overrode the
"wait until 17 Aug" recommendation. The launch-safety guardrails that motivated
waiting are preserved differently: the service is strictly optional, the app
must work perfectly with it down, and a one-line kill switch exists. Launch-day
risk stays near zero because the feature *failing* is indistinguishable from
the feature not existing.

## What it is (one sentence)
After finishing a game's daily, the results screen gains one line —
**"Your 84 beat about 7 in 10 of today's players."** — no names, no rankings,
no new screen, no login.

## Daniel's rulings (locked)
1. **Build now**, not post-launch.
2. **No consent prompt.** Participation is default-on for everyone who
   completes a daily. Transparency instead of permission-asking: an honest
   privacy-page rewrite + a quiet settings toggle to opt out. (Legality rests
   on the storage design below being genuinely anonymous — that design is
   therefore NOT optional.)
3. Percentile shape, not a top-N list (v1 decision, unchanged).

## Decisions from the GPT critique (all accepted unless noted)
- **No permanent device identity.** A fresh random token per edition, used
  only to prevent accidental double-counting that day, never stored beyond a
  short window, never able to link Monday's player to Tuesday's. NOT carried
  by carry.js. (This replaces v1's persistent token — conceded in full.)
- **Not "cheat-proof"** — say "low-incentive, reasonably abuse-resistant."
  With no podium, a forged score wins nothing.
- **Per-game comparison is v1**, on each game's own results screen — one UI
  element, one place. (GPT preferred the four-game total; its own caveat
  applies: most players don't finish all four — the analytics prove it — so
  total-only would show most players nothing. Full-house comparison can join
  later if traffic supports it.)
- **Statistical honesty:**
  - Ties: count only scores strictly below yours; phrase is "beat" / "scored
    higher than".
  - Field < 20: no percentage at all — show the honest small-field line:
    "You're among the first N players of today's issue." (zine-voiced, and
    hides the empty room)
  - Field 20–49: approximate words — "about 7 in 10".
  - Field ≥ 50: percentage rounded to the nearest 5.
  - Everything keyed by EDITION NUMBER, never the server's calendar date
    (midnight differs across the world; the app already defines editions by
    the player's local date).
- **Storage is aggregate-only** (the legal load-bearing wall):
  - Table `tally(edition, game, score, count)` — literally "three people
    scored 84 on edition 42's Relic." No rows per person. Nothing to subject-
    access, nothing to breach.
  - Table `seen(edition, game, token)` — the day's dedup tokens only; purged
    lazily (see below). Tokens are random client-generated UUIDs with no
    meaning.
  - No IP addresses, user agents, or timestamps-per-person written by us.
    Cloudflare processes request metadata in transit as any host does — the
    privacy page says so plainly instead of pretending otherwise.
- **No scheduled jobs.** Cleanup is lazy: the first write that arrives for
  edition N deletes `seen` rows for editions < N−1. Same effect as a cron,
  zero extra infrastructure. (Kills v1's "scheduled cleanup" hand-wave.)
- **Native feedback form: separate project, not this one.** Google Form
  remains the launch answer. (Conceded — a safe text-accepting endpoint is a
  different animal from an integer tally.)

## Architecture (respects "no Node on the Mac" absolutely)
- **Cloudflare Pages Functions** in this same repo: a `functions/api/score.js`
  file (plain JS module — no TypeScript, no build step). Cloudflare picks it
  up automatically on the same push that deploys the site. No wrangler, no
  Node, nothing new on Daniel's machine.
- **D1 database** (Cloudflare's small SQL store), created once in the
  dashboard and bound to the Pages project (one-time clicking, ~5 minutes,
  driven via Chrome like the cutover was).
- **Testing without local tooling:** push the work to a NON-production branch
  — Cloudflare builds a preview URL with the function live against a test
  binding. Real end-to-end testing, still zero Node locally. This IS the
  spike GPT demanded: prove one endpoint + one table on a preview branch
  before writing the client line. Budget half an evening; if the spike fights
  back, stop and reassess rather than pushing through.
- **One endpoint:** `POST /api/score` with `{edition, game, score, token}`.
  Server: validate (score 0–100 integer, game in the four, edition within
  plausible range), dedup on (edition, game, token), increment the tally,
  return `{below, total}`. The client computes and words the line. Response
  under 100 bytes. GET endpoints: none needed.
- **Abuse posture:** input validation + dedup + Cloudflare's free-tier rate
  limiting rule. Accepted residual risk: a determined person can inflate the
  tally; with no leaderboard to win, the blast radius is one silly percentile.
- **Kill switch:** a single const in js/app.js (`PERCENTILE_ON`). Off = the
  app never calls the endpoint and the line never renders. Ship ON, flip OFF
  in one commit if launch week says so.

## Client behaviour
- On daily completion (not practice, not encore): if the toggle is on, POST
  and render the one line on the results screen using the wording tiers
  above. Any failure (offline, timeout, non-200, service dark): render
  nothing, log nothing user-visible, never retry aggressively. The game's own
  flow must be byte-identical whether the service exists or not.
- Settings: "Compare my scores anonymously" — default ON, in the existing
  sound/settings area of Home's footer. Off = no POST at all (not "POST but
  hide").
- Analytics: one GoatCounter event when the line renders (`percentile-shown`)
  and one for opt-out toggles. Nothing else.

## The paperwork (do IN THIS ORDER inside the build)
1. **privacy.html rewrite ships in the same deploy as the first POST** — it
   currently promises scores "are never sent anywhere," which becomes false
   the moment this ships. New text: what is sent (edition, game, score, a
   meaningless random token), what is kept (anonymous tallies), what is never
   kept (anything identifying, anything cross-day), the toggle, and honest
   words about Cloudflare processing requests in transit.
2. **CLAUDE.md amendment** (GPT's wording, adjusted for Daniel's default-on
   ruling): "The core app remains static, offline-capable and local-first.
   One optional comparison service may receive only the current edition's
   completed score and an edition-specific random token. Participation is
   default-on with a clear privacy-page disclosure and a settings opt-out
   (Daniel, 5 Aug 2026). The service stores no cross-day player identity and
   no user-written content; its failure must never affect play, scoring,
   streaks, Carry, sharing or navigation."
3. **HOUSE_RULES entry** recording the ruling and its date.
4. **Daniel, 10 minutes:** the UK ICO registration-fee self-assessment
   (ico.org.uk → "Do I need to pay the fee?"). Likely answerable either way
   for anonymous tallies; do the check, keep the receipt of the answer.

## Tests (extend the 14-suite gate)
- Client: with the endpoint stubbed — line renders correctly at each wording
  tier; renders NOTHING on failure/timeout/toggle-off; practice and encore
  never POST; the results screen passes the no-dead-ends contract unchanged.
- Server: a small python script hitting the preview-branch URL — validation
  rejects junk, dedup holds, tally increments, lazy sweep fires. (Manual/CI
  curl-level, not Playwright.)
- The existing suite must stay green untouched.

## Build order for the session that does this
0. Model-plan approval from Daniel first (standing rule).
1. Spike: D1 + binding (Chrome-driven dashboard clicks) → `functions/api/
   score.js` minimal → preview branch → curl proof. STOP here if it fights.
2. Harden the endpoint (validation, dedup, sweep, rate limit).
3. Client line + wording tiers + toggle + kill switch.
4. privacy.html + CLAUDE.md + HOUSE_RULES, same commit as the client.
5. Tests; full suite; bump BUILD+VERSION together; deploy; verify live with
   a real POST from a phone.
6. Update this document's status line and the launch board.

## Explicitly rejected (keep it rejected)
Top-N/global rankings; streak leaderboards; names or any identity; accounts;
consent dialogs (Daniel's ruling — disclosure instead); permanent tokens;
tokens in Carry; cron/scheduled Workers; TypeScript/build steps; storing
anything a person typed; per-result dynamic previews; "nearly cheat-proof"
as a claim.
