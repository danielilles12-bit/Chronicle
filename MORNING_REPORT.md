# Morning report — overnight content quality audit

**2026-07-09 · deployed as sw v86, commit 9ce1833 · everything below is live**

## TL;DR

30+ agents blind-playtested every Thread board and fact-checked all four
games overnight. The verdict on your content: **conceptually strong, with
craft-level flaws that were all fixable in one night.** Zero boards were
beyond saving except one; the fixes are live. The best content now airs
first in every game. Total spend: one hiccup (the session limit paused us
1am–6:30am), otherwise as planned — Sonnet did the grunt work, I did the
judging.

## The big finds (my favourites)

1. **The Golden Stool wasn't the Golden Stool.** Our Relic item claimed
   the sacred Asante stool sits in the British Museum. The real Sika Dwa
   Kofi has never been captured or photographed — it's guarded in Kumasi;
   our photo showed some other stool. Cut. (This is the exact "confidently
   wrong" trust-killer the audit was designed to catch.)
2. **Tower Bridge accepted "London Bridge" as a correct answer** — the
   most famous bridge mix-up in the world, being actively taught to
   players. Removed; the blurb now makes the mix-up the joke.
3. **21 BC-era figures had years off by one** (Cicero died 43 BC, we said
   42) — a Wikidata astronomical-year import bug, hand-corrected against
   standard scholarship. Plus "TutanKhamun" was typo'd in his own name.
4. **Kim Jong-il's paid map hint was "Film actor and politician."**
   263 occupation/place hints fixed across Lifeline (7 US presidents were
   listed by their pre-White-House day jobs; Mother Teresa was a "Nun and
   musician").
5. **"Hold the fort" isn't anyone's last words** (Sherman signal message,
   1864; he died in bed in 1891) and **Alexandroupoli is named after the
   wrong Alexander** (a 20th-century Greek king). Both swapped.

## Thread: what blind playtesting proved

Agents solved the 16 tiles cold, then compared against your answer key —
so "this board is ambiguous" means *a real solver actually went wrong
there*, not an opinion.

- **57 boards repaired**: ~14 title leaks (titles that named a tile or
  label — "The Sun King" board had "Sun King" as a tile), ~15 genuinely
  ambiguous tiles (each fixed with the exact swap the playtest suggested),
  ~10 factual label overclaims (the Maqdala Crown was never returned;
  Ypres was fought over three times, not twice), the rest label-wit work.
- **1 cut**: conn-096, pure "sort the gods by pantheon" with zero
  misdirection. Pool is now 179 boards.
- **The craft pattern to know for future boards**: your tile-level traps
  are genuinely excellent (playtesters kept praising specific ones — the
  Chamberlain trap, the Tutankhamun trap, Waterloo-as-era-ender). The
  weaknesses were always: title leaks, "Wikipedia category" labels, and
  easy boards that sort into four islands. That's all in the rubric now.

## Face Value & Relic

- **36 fact corrections** (Tut's mask moved to the Grand Egyptian Museum
  in Oct 2025; the Roman Forum blurb was off by 700 years; Mozart's
  portraitist was misnamed; Palmyra's arch is presented pre-2015 no more).
- **64 blurb upgrades** — every one carries a concrete delight fact I
  personally verified (Tikal was the Star Wars rebel base; Celsus is
  buried under his own library; the Lewis Chessmen inspired wizard's
  chess). Blurbs whose proposed facts I couldn't vouch for were NOT
  applied.
- **75 answer variants added, each proven necessary**: I built a harness
  that runs every proposed variant through the app's real matcher first —
  117 of 192 proposals already matched (your matcher is more forgiving
  than the agents assumed) and were rejected as bloat.
- **91 difficulty retiers**, adjudicated by rendering every candidate's
  actual opening crop into contact sheets (fame × fragment ambiguity, per
  your calibration rule). Kept medium where the crop deliberately
  withholds (Angkor Wat's opens on black corrugated stone; Windsor's on
  trees), promoted the unmistakable (Beethoven's scowl, the floating
  torii, Starry Night's swirls).

## Schedule front-load

Array order = airing order in daily.js, so each tier is now sorted best-
first: a new player's first weeks are the certified best content in all
four games. **Recommendation: reset EPOCH in js/daily.js to your launch
date when you launch** — that gives every real player the golden first
month. (Pre-launch, breaking past editions is harmless; verified the app
boots and serves editions cleanly on the new order.)

## Needs your eyes (in priority order)

1. **Five image swaps** I didn't risk overnight: Anne Boleyn (sitter
   disputed — swap to the "B necklace" portrait), the Alexander bust and
   Caesar bust (museums themselves hedge the IDs — blurbs now own the
   uncertainty as a fun fact, but better images exist), Herculaneum
   Frescoes (a category, not a thing — weak reveal), Churchill (archive
   credit, and there are better-known photos).
2. **Six Thread boards flagged "redesign, not repair"** (conn-009, 010,
   012, 067, 105, 117): structurally sound but they play as sorting
   chores. They now rank last in their tiers, so no rush.
3. **Easy-tier scarcity in Face Value**: honest retiering shrank easy to
   62 portraits; the daily recipe burns 28/week, so easy faces repeat
   roughly monthly. Next content batch should be ~20 instantly-famous
   faces. (Same applies mildly to Relic easy: 78.)
4. **Bayeux Tapestry** is on loan to the British Museum Sept 2026–Jul
   2027 — blurb notes the tour, but you may want to time its airing.
5. **The Playwright test suite is stale** — it references the pre-redesign
   home screen (`#card-map`) and fails at HEAD, before any of tonight's
   changes. Worth a repair session.
6. Housekeeping list in the workbook: two greedy variants ("the queen",
   "the tower") that make the matcher over-generous when those items are
   up; a couple of untraceable source citations; Robert Burns' "lost
   portrait authenticated 2023" blurb claim needs verifying before use.

---

# The freebie: art direction critique ("is it overdone?")

Reviewed at phone size, as a player would see it.

**You have two directions in that folder, and the answer differs:**

**house-v2 (light auction-catalogue) — NOT overdone. Commit to it.**
The lot numbers, hairline rules, and red wax accent read instantly at
390px; the hierarchy is genuinely NYT-games-grade. Crucially, the wink
lives in the *copy* ("SEALED · 6:41", "Tomorrow it returns to the
vaults") — the cheapest, most durable place for personality. The state
chips (VIEWING OPEN / UNVIEWED / ROUND 4 OF 10) do theme and function in
one element. That's "grand, with a wink" executed correctly.

Three real critiques of it: the "D" wax seal floats ambiguously (button
or badge?); the red small-caps labels sit near the legibility floor on a
phone; and the hero photo spoils today's Relic answer before you've
played — the "SEALED" state needs to actually veil the image.

**soane-home (dark gilded gallery) — this is the overdone one.** Gold
frame inside gold frame; the three game cards shrink to postage stamps at
contrast levels that will punish cheap screens. It's a beautiful poster
and a heavy tool. But don't delete it — it's the app's evening dress.
Use it as the wax-seal win-ritual backdrop, where three seconds of
opulence is exactly right.

**curators-room-board** — a mood board, not a screen. Keep as reference;
don't ship AI-generated texture into the product. Your Commons imagery IS
the art programme and it's better than anything generated.

**brand-playbook** — right instinct, needs a components page (topbar,
pill, sheet, tile, chip) more than more prose. Acid test: could the
Thread play screen be built from it without new decisions?

**Recommended order:** commit house-v2 as the shell → apply to Home +
full Thread loop → salvage soane for the win ritual → fix the hero-
spoiler state → testers.
