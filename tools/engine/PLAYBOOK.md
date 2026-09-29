# Yesternerd content engine — the playbook

This is the one document an unattended content run needs. It is written for
a Claude session that starts with **no memory of this project** (for
example the weekly cloud routine) and for the auditor sub-agents it runs
(`.claude/agents/`). It condenses what the owner, Daniel, taught the content
by hand between the 10 Aug 2026 launch and late September 2026: every flag,
swap and comment on his nightly review boards. The full ledger of his rulings
is `HOUSE_RULES.md`, and this file does not replace it. When they seem to
disagree, HOUSE_RULES wins.

**Standing mandate (Daniel, 29 Sep 2026).** The app runs unattended. Daniel
no longer reviews content day to day and may not open his laptop for months.
The engine must keep publishing good content by itself, learning mainly from
his curated period (10 Aug – mid Sep; for Thread, 17 Aug – late Sep). The
easy/medium/hard mix is a guide, not a law: break it for the right content.

---

## 0. The shape of a day (what is being filled)

Each edition (one calendar day, edition n = 29 Jun 2026 + n days) holds:

- **Face Value** (`who`, pool `data/reveal-who.json`): 3 portraits. The
  player tears scraps off a 3x3 grid to name the person. One scrap starts
  open; a player can only tear scraps **touching** what is already open.
- **Lifeline** (`map`, pool `data/figures.json`): 3 people, shown only as a
  birth pin and a death pin (with years) on a world map.
- **Relic** (`what`, pool `data/reveal-what.json`): 3 artefacts, artworks or
  landmarks, torn like Face Value.
- **Thread** (`thread`, pool `data/connections.json`): one 16-tile,
  4-group board, NYT-Connections style. Tier by weekday: Mon/Tue easy,
  Wed/Thu medium, Fri–Sun hard.
- Every rounds game has a **3-choice rescue** (answer plus two distractors),
  curated in `tools/fame/mcq_overrides.json`.

Default recipe: one easy, one medium, one hard per rounds game. Deviations
are fine when the better content needs it (HOUSE_RULES, 12 Aug ruling).

The audience: **Western (UK/US) adults who like popular history.** Think
listeners of The Rest Is History, or people who wander into the British
Museum for fun. Easy is not dumbed down. Hard is not academic.

---

## 1. Face Value: what Daniel accepts and rejects

**The first question is always "would this audience name this person from
the FULL picture?"** Name fame is not enough: the *likeness* must be famous.

- Struck for unknown likenesses, even though the names are famous: Rubens,
  Titian (twice), Monet, Voltaire, Philip II of Spain, Buddha, Artemisia
  Gentileschi (twice), Jane Austen ("no one knows what she looked like"),
  Aristotle, Kösem Sultan, Charles V.
- Loved: faces from banknotes, coins, textbooks and film. Presidents,
  dictators, monarchs with a state portrait, Einstein/Darwin/Tesla-class
  scientists, pop icons (Marilyn, Elvis, MJ, Hendrix, Bob Marley). Also the
  iconic single images: Che, Kim Il-sung's state portrait, Nefertiti's bust.
- **A random Swedish king whose portrait nobody has seen is not content**,
  even if people may have heard the name.
- Entertainers are fine as easy anchors, but never most of a day. No living
  politicians.

**The picture:** use the iconic likeness (the Wikipedia infobox or banknote
image). Reject the image, not just the opener, when:

- **it's too dark**: Jefferson, Rembrandt and Kafka were each "basically a
  black square on a phone";
- **it's mostly black garment or plain backdrop** (Rubens, Van Buren): the
  round then has only two states, nothing or the answer;
- **it's a bad photo** (Cobain: "absolutely terrible photo"), blurry, or
  shows other people (Theodora had to be cropped to her alone).

**The tear (Daniel's words, 6 Sep and 29 Sep):** pick a starting tear that
contains at least a little bit of a clue for the absolute nerdiest players
AND allows a satisfying path of tears toward the face.

- The **opening scrap must show part of the subject**: clothes, collar,
  regalia, a hand, hair, a hat, a sabre hilt. Never blank background, sky
  or a studio wall. The nerdiest historian should be able to name them
  from scrap one.
- Daniel's most frequent opener was **the scrap directly under the face**
  (bottom-middle, `start: 7`): collar, lapels, orders or medals. Next came
  a mid-row side cell showing a shoulder or hair edge (`3`/`5`), and
  occasionally a top corner catching hair or a crown.
- Only open **on the face itself** (the money cell) for genuinely hard,
  obscure-looking subjects. That is allowed and sometimes kind.
- **The graded tear path:** the cells touching the opener should add
  evidence step by step (uniform, orders, beard, then face). George V is
  the model: aiguillettes, then the Garter star, then the beard, then the
  face.

---

## 2. Relic: what Daniel accepts and rejects

- **Recognisable things.** Struck as unknown: Ajanta Caves ("never heard of
  it"), Kaaba ("never heard of this thing"), Longmen Grottoes, Lahore Fort,
  Elephanta. Struck as "reads as generic ancient ruins": Persepolis. Struck
  for having no self-identifying view: Port Royal, Terracotta Army.
- **"When someone hears Relic they think Tutankhamun's mask, not a museum."**
  Every day should carry at least one true relic (an object, painting or
  document). Never two buildings unless their eras are wildly different;
  ideally at most one building. At most one painting a day.
- Museum BUILDINGS (the Met, the Prado, the Natural History Museum…) are
  benched from autopilot. Daniel's own British Museum Great Court pick is
  the one exception. Modern towers other than the famous New York trio
  and the Eiffel Tower are benched too.
- Cutty Sark and Sydney Opera House were early "no, swap for a relic"
  cases. Modern buildings are allowed but are the weakest kind of Relic.
- **Iconic image:** the postcard view. Wide, low monuments want an aerial
  view (Windsor, Newgrange). Temples want the famous facade (Angkor's
  five-tower reflection, Abu Simbel from the front). Mount Nemrut wants one
  colossal head, face-on.
- **Tear path matters as much as fame:** the Amber Room was struck for an
  unsatisfying tear-by-tear reveal. Nazca Lines was loved because its early
  scraps are baffling desert lines until the hummingbird lands.
- Opener: a part of THE thing (carving, masonry, pigment, rigging), never a
  neighbouring building, sky or grass.
- Rolling variety: no two ships, two diamonds, two temples or two crowns
  within a few days. After the White House, not the Capitol.
- A name painted on the object caps it at easy (it becomes readable once
  torn).

---

## 3. Lifeline: what Daniel accepts and rejects

- **Heard-of people only.** Struck as "nobody's heard of him/her":
  Maimonides (three times), Themistocles, Tycho Brahe, Alcibiades, T. S.
  Eliot, Chandragupta Maurya, Kwame Nkrumah, Sun Yat-sen, Empress Matilda
  (twice), William III, Rudolf. Saint Peter was struck because his birth
  and death places are tradition, not record. Any pin that is legend
  fails.
- **Judged as a map:** prefer journeys that tell a story, born on one
  continent and died on another (Pelé swapped for Bruce Lee: San
  Francisco to Hong Kong). Two pins in one country is a boring puzzle.
- Variety within a day: not three Britons of one era (Cook was swapped for
  "someone ancient or relatively modern, non-British"). Mix eras and
  regions.
- Western-first, but famous non-Westerners are welcome (Genghis Khan, Bruce
  Lee, Gandhi).

---

## 4. The 3-choice rescue (distractors), all games

**Rule (Daniel, 6 and 14 Sep): every distractor must be a deliberate,
plausible distraction, so the choice feels earned.** If the answer is a
clay tablet, the other two are clay tablets or close kin (Code of
Hammurabi, Cyrus Cylinder). They are never the International Space
Station.

- **Relic:** same physical kind first. Ship ↔ ships (Vasa ↔ Mary Rose /
  Mary Celeste), jewel ↔ jewels (Hope Diamond ↔ Koh-i-Noor / Imperial
  State Crown), painting ↔ same school, era and genre (Arnolfini ↔ The
  Ambassadors / The Moneylender and His Wife; Mona Lisa ↔ Virgin of the
  Rocks / Madonna of the Carnation), cathedral ↔ cathedrals (Sagrada ↔
  Milan / Cologne), wall ↔ walls (Berlin Wall ↔ Korean DMZ / Western
  Wall). After kind, match era and region.
- **Face Value:** same era, region, gender and role, and photo against
  photo or painting against painting. Yeltsin ↔ Brezhnev / Khrushchev;
  Jackie Kennedy ↔ Nancy Reagan / Lady Bird Johnson; Castro ↔ Pinochet /
  Che; Catherine the Great ↔ Marie Antoinette / Maria Theresa; Michael
  Jackson ↔ Hendrix / George Michael; Wellington ↔ Nelson / Zachary Taylor.
- **Lifeline:** same era, region and role, and people whose two pins could
  plausibly be those pins. For a man born and dying in 14th-century India,
  don't offer a random European king.
- **Fame ladder:** kind (famous) distractors for an obscure answer; cruel
  near-neighbours for a famous one. Saladin got Genghis Khan and Ptolemy I,
  "kind as Saladin isn't as well known". The Mona Lisa got two other
  Leonardos.
- A distractor must never be a same-day or adjacent-day answer, and no two
  rounds on one day may share an option. `build_mcq.py --check` enforces
  this.
- Distractor names must be real, correctly spelled and unambiguous.

---

## 5. Thread: what makes a board Daniel keeps

Study `tools/engine/thread_exemplars.md`: every board aired 17 Aug – 27 Sep,
most after his edits. The ones he wrote himself or loved ("Love!" on Higher
Powers) are the target: Stable Relations, Ruling the Waves, Hard to
Swallow, Olympus Inc., Location Location Location, Alphabet Soup,
First-Name Basis, Classical Education, The Colour Supplement, Read the
Small Print, Theatre of Operations, Family Business, Chapter Headings, Know
Your Place, Higher Powers, Out of Order, Change Here.

**Solvability target:** about 55% of players should solve it. That was
Daniel's own number on 13 Aug. Hard boards are hard through ambiguity
between FAMOUS things, never through obscurity.

**Grammar (full rubric in `connections_audit.md`):**

1. **Every tile is a household word.** "I've heard of it" is the bar even on
   hard boards. Struck: Beaufort, Mohs and Scoville scales; Bunsen and
   Erlenmeyer; knots other than Windsor; Europe and Eagles as bands; the
   Gulf of Tonkin, Aden and Finland; the Sea of Galilee.
2. **At least one fake-five / polysemous tile, even on easy boards.**
   Waterloo, Delta, Polo, Jersey, Windsor, the Beatles' John/Paul/George
   against kings. Easy boards with "zero traps or fun or delight" get
   rejected (Grand Tour).
3. **Not sortable by surface.** If all four tiles in a group are the only
   countries on the board, or all start with "Doctor", or all look like
   Greek words, the group sorts itself ("Name Dropping", "Roman Holiday":
   "too easy, can just sort by type of word"). Either mix the surfaces or
   make the label's fact the only way in (conn-004's "Found refuge from
   persecution in London": Marx, Freud, Lenin, de Gaulle).
4. **Binary, pedant-proof labels.** "Lost cities" (was Troy ever lost?)
   and "famous documents" are too vague. Tighten until membership is
   checkable ("Classic whiskey cocktails", not "Classic cocktails").
   Daniel's rule: explicit beats elegant.
5. **The title has a wink and never pre-solves a group.** "War Horse"
   would have handed over two fill-in words, so it became "Stable
   Relations".
6. **One structural-twist group** (fill-in-the-blank, hidden word, ___ Age,
   numbered Famous Fourths). Mix category archetypes on every board.
7. **No dated or controversial hooks** (Gulf of Mexico, living politicians).

**The history notch (Daniel, 22 Sep and 29 Sep 2026).** Recent boards drifted
light on history: High Society (cards), Animal Farm, Cover Story (hats),
Happy Hour (cocktails). He flagged Cross Purposes as "insufficiently
historical". **Every board must have at least TWO groups whose connection is
a historical fact** (a people, event, reign, war, empire, invention,
document or historical figure), and a third group should lean historical
where possible. One pop-culture or wordplay group is welcome as the fun
contrast (TMNT against Greek philosophers, the Beatles against kings, AI
models against Greek gods). Two are the limit. The best boards smuggle
history into an everyday surface: Hard to Swallow (foods by their
historical origin), Theatre of Operations (WWII codenames hiding among
board games and Shakespeare).

**Novelty:** Daniel wants new kinds of connections, not variations of the
same four. He is an antiquity and Rome nerd, but don't over-serve Greece and
Rome. Rotate eras and regions across the week.

**Dedup:** no tile that already appears on 3+ existing boards, and no
category that repeats an existing board's category (check the whole of
`data/connections.json`, not just recent boards). Constantinople is in four
boards already. `tools/engine/thread_dedup.py` reports collisions.

---

## 6. Scheduling rules the engine must keep (all enforced by tools)

- Repeat floor: 42 days per subject across all games, target 60.
- One dark-tone subject per issue. Rulers, statesmen and soldiers may fill up
  to 2/3 of human slots; any other occupation family appears at most once a
  day.
- At least one woman across Face Value + Lifeline each day (compiler
  enforces it using `tools/fame/mcq_gender.json`).
- At most two PLACES per Relic day, so every day carries a true object
  (compiler enforces it; `tools/engine/relic_objects.json` lists the
  objects. Add any new object relic there, or it counts as a place).
- Same-day and adjacent-day nets: no tile, name or distractor spoiling
  another round.
- Aired editions are frozen history. Never edit an edition whose date is
  today or earlier. Every edition from tomorrow on may be changed.

---

## 7. How the unattended run works (`tools/engine/autopilot.py`)

1. **Buffer check.** The manifest should always hold at least 8 weeks of
   future editions. If it already does, the run ends with "nothing to do".
   That is the normal case.
2. **Thread stock.** Count unaired, vetted boards. If there are fewer than
   the days to fill, the run writes new boards: `thread-writer` sub-agent →
   `thread-critic` sub-agent → `thread_dedup.py` → `validate_boards.py`.
   Only boards that pass the critic go into `data/connections.json` with
   `"engine": {"vetted": true}`.
3. **Compile.** `python3 tools/compile_editions.py propose --days N
   --vetted-only` drafts the new days from vetted pool items only. The
   verdicts live in `tools/engine/vetting.json`.
4. **Audit the draft.** Run the `picture-auditor` on every Face Value and
   Relic round in the draft (sheets from `render_audit_sheets.py
   --editions`), and the `distractor-auditor` on every trio (report from
   `tools/engine/trio_report.py`). Apply their fixes: `start` values in
   the data files, trio pins in `tools/fame/mcq_overrides.json`. Swap out
   anything they fail.
5. **Gate.** Merge-validate, approve, rebuild MCQs, run `repo_checks.py` and
   the validators. Bump BUILD in `js/app.js` and VERSION in `sw.js`
   together. Commit and push to the branch `claude/content-engine`. CI
   runs the full browser suite on that commit and, only if it passes,
   fast-forwards `main` and `release`. Cloudflare then deploys. **If any gate fails,
   push nothing.** The 8-week buffer absorbs a failed week.

**Things an unattended run must never do:** fetch or replace images (new
pictures need a human eye); edit aired editions; delete pool items (bench
with `"engine": {"vetted": false}` instead); change app code; touch
`reserve` flags (those are Daniel's rulings); push if a check is red.

---

## 8. Vetting file (`tools/engine/vetting.json`)

```json
{"who": {"<id>": {"ok": true, "start": 7, "note": "..."}},
 "what": {...}, "map": {...}, "thread": {"conn-240": {"ok": true}}}
```

`ok: false` benches an item from autopilot only. It remains in the pool,
already-aired editions keep working, and a human can still schedule it.
The picture auditor's `start` suggestions are applied to the data files;
the copy here is the record. Items missing from the file count as unvetted
and are skipped by `--vetted-only`.
