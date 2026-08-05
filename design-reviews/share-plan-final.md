# Sharing — FINAL plan (after research + GPT critique)
5 Aug 2026. Supersedes share-plan-draft.md.

## What changed after the critique
The draft proposed four per-game landing pages and stranger-vs-returning
routing. **Both are cut.** GPT's objections were checked against the code and
held. The remaining plan is roughly one evening, not three, and most of the
freed time should go to launch QA and seeding.

## DO — in this order

### 1. Drop the image card  (owner's decision, unchanged)
Remove drawCard + the file-share path from js/sharecard.js; keep text + link.
Rationale: the emoji grid is the receipt; the attachment adds a step, 173KB,
and an untrusted blank placeholder in the iOS sheet.
**Honest tradeoff to state:** Instagram Stories effectively needs an image to
show anything. We are not optimising for Stories at launch; if that channel
matters later, the card can return as an explicit "save image" action rather
than an automatic attachment.

### 2. Fix the silent failure  (the only player-facing bug here)
If a shared link's game data fails to load, the visitor currently lands on an
ordinary Home page with no indication anything was attempted. Show an explicit
message + retry. Never leave a tapped link looking like a no-op.

### 3. Fix the instrumentation — honestly, not ambitiously
Verified problems:
- `land-share-<game>` fires for ANY valid `?play=` URL, with or without
  `ref=share`. Either require the campaign param or rename it to a generic
  deep-link arrival.
- `start-from-share-<game>` fires before the engine decides fresh / resumed /
  already-played. Rename to `share-routed-<game>` (what it actually means) or
  drop it.
- `answer-from-share-<game>` ALREADY EXISTS and fires on the first real answer.
  **This is the activation signal — the draft was wrong to claim we cannot
  measure sharing.** Keep it; it is the honest denominator-mate for arrivals.
- Do NOT introduce `share-blocked`: it would merge "already played" (success),
  "data failed" (reliability) and "no data" (deployment) into one useless
  bucket. Leave load failures in the existing `err-data-*` family.
- Check GoatCounter campaign params: `ref` is a source, not a campaign;
  `utm_campaign=share&utm_source=<game>` is the documented shape. Verify one
  real phone visit lands correctly in the live dashboard BEFORE changing more.

### 4. Keep ONE routing rule for everybody
- Unplayed → open/resume that game (existing behaviour, the warm-referral
  intent).
- Already played → their own result screen, which already offers "Turn the
  page ›" to the next unplayed game. **Verified: not a dead end.**
- Load failure → explicit error + retry (item 2).
No stranger/returning branch: "no localStorage" does not mean "new person" —
in-app browsers, cleared storage and device switches all look new, and the
branch would discard a warm referral's intent.

### 5. Modest test coverage
Per engine family (Lifeline / Face Value+Relic / Thread), not a 24-cell matrix:
all four games fresh; one representative already-played and one mid-round
resume; invalid param once; load-failure/retry per loader path.
Fix `seed_completion()`'s Thread shape only while in those tests.

## DON'T — and why
- **Per-game landing pages.** "A tiny static file that boots the app" hides
  real work: app.js expects the full application shell, so it means four
  drifting copies, or a redirect hop, or a refactor — plus no-JS fallback,
  canonical/noindex, service-worker behaviour, preview-cache invalidation,
  old-domain redirect preservation, and new route tests. And the generic
  preview ("Four Daily History Games") explains an unknown product BETTER
  than a Relic-specific card would.
- **Dynamic per-result previews.** Correct blocker is no-backend/no-runtime
  generation (not "needs Node" — that was imprecise).
- **Signed links, accounts, any backend.** Already-settled rules.

## Acknowledged, not solved
- A result shared near midnight can say №42 while the recipient opens №43.
- Social previews cache aggressively; a corrected image may not propagate.
- Share-sheet completion ≠ delivered ≠ clicked. Our numbers are directional.

## Corrected research claims
- Wordle's emoji sharing drove virality **while it was still unknown** (Wardle
  interview) — it did not merely coast on fame. This SUPPORTS the owner's
  hypothesis that sharing can grow an unknown product; it just doesn't
  support building landing pages before there's evidence previews suppress taps.
- "NYT URLs have no date param" was overstated; today-only remains our simpler
  choice on its own merits (and unaired content is a validation rule anyway).

## Where the freed evenings should go
301 redirects · real-device share/unfurl/tap journey (iPhone Safari, installed
PWA, WhatsApp, one in-app browser) · verify GoatCounter live · content freeze +
regression · outreach seeding. Sharing cannot create the first audience.
