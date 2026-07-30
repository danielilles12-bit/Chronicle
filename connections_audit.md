# Connections — Content Audit

> **Applied 2026-06-30** — all 8 factual fixes made to `data/connections.json` (JSON re-validated, 25 puzzles intact):
> 1. conn-002 green → label "Greek battles against Persia" (Thermopylae was a defeat)
> 2. conn-002 blue → Borodino replaced with **Berezina**
> 3. conn-008 purple → label "Reputed dying quips" (drops "writers"; Bogart/Picasso weren't)
> 4. conn-008 yellow → "I have not yet begun to fight" replaced with **"This is no time to make new enemies"** (Voltaire)
> 5. conn-013 purple → label "Polymaths" (Newton/Franklin aren't Renaissance)
> 6. conn-014 yellow → label "Died in their early 30s"
> 7. conn-014 purple → label "Died at 40", now **Poe / Glenn Miller / John Lennon / Franz Kafka** (all died at exactly 40)
> 8. conn-025 blue → **Hannibal replaced with Odoacer**, label now "Barbarian conquerors". Hannibal (sophisticated general of Carthage, a settled superpower) didn't fit the outsider-destroyer theme; Odoacer (Germanic, deposed the last Western Roman emperor in 476) does. He's barbarian rather than strictly steppe-nomad, hence the precise label. Hannibal still appears in conn-013 ("Conquerors and generals"), where he fits.
>
> Bonus tidy: conn-014 blue → "Assassinated leaders" (dropped "young"; Lincoln/JFK/Caesar weren't young). Design-risk items in section B left as-is (judgment calls).



Audit of all 25 puzzles in `data/connections.json`. Each puzzle = 4 groups × 4 items.
Two lenses: **design** (is each item unambiguously in one group? is the puzzle solvable and fair?) and **facts** (is every claim true?).

Verdict up top: **18 of 25 puzzles are clean.** 7 puzzles have issues; of those, **8 are genuine factual errors** worth fixing, and a handful are softer design/ambiguity risks.

---

## A. Factual errors (recommend fixing)

| # | Puzzle | Group | Problem | Suggested fix |
|---|--------|-------|---------|---------------|
| 1 | conn-002 Last Stands | green "Ancient Greek **victories** over Persia" | **Thermopylae was a defeat**, not a victory (the 300 Spartans were wiped out). Marathon/Salamis/Plataea were wins. | Relabel green → **"Greek battles against Persia"** (keeps Thermopylae, which fits the "Last Stands" title perfectly). |
| 2 | conn-002 Last Stands | blue "Napoleon's defeats" | **Borodino is normally scored a French *victory*** (the French held the field; the Russians withdrew). The other three (Leipzig, Trafalgar, Aspern) are real defeats. | Swap **Borodino → Berezina** (the catastrophic 1812 retreat crossing — an unambiguous French disaster). Alt: *Vitoria*. |
| 3 | conn-008 Final Words | purple "Reputed dying quips of **writers**" | **Bogart was an actor, Picasso a painter** — neither was a writer. Only Wilde and Ibsen were writers. | Relabel purple → **"Reputed dying quips"** (drops "writers"; all four then fit). |
| 4 | conn-008 Final Words | yellow "Said to have been last words" | **"I have not yet begun to fight"** is John Paul Jones's *battle cry*, not anyone's last words. | Replace with a real reputed last line, e.g. **"This is no time to make new enemies"** (Voltaire) or **"Friends applaud, the comedy is over"** (Beethoven). |
| 5 | conn-013 Left-Handed Legends | purple "**Renaissance** polymaths" | **Newton (1640s–1720s) and Franklin (1700s) are not Renaissance figures.** | Relabel purple → **"Polymaths"** (or "Scientists & polymaths"). |
| 6 | conn-014 Gone Too Soon | yellow "Died at **33**" | **Bruce Lee died at 32; Alexander the Great is normally cited at 32** too. Only Eva Perón (33) and Jesus (~33) fit exactly. | Relabel yellow → **"Died in their early 30s"** (covers all four accurately). |
| 7 | conn-014 Gone Too Soon | purple "Died at **39**" | **Three of four ages are wrong.** Poe died at **40**, Glenn Miller at **40**, Lou Gehrig at **37**. Only MLK was 39. | Rebuild as a verified set — see note below. |
| 8 | conn-025 Legends and Leaders | blue "**Nomadic** conquerors" | **Hannibal was Carthaginian** (a settled Mediterranean power), not a steppe nomad like Attila/Genghis/Tamerlane. | Swap **Hannibal → Kublai Khan** (most recognisable) or **Babur**. |

### Note on conn-014 purple ("Died at 39")
Cleanest accurate rebuild, keeping the assassination flavour: **MLK (39), Malcolm X (39), Stonewall Jackson (39), Dietrich Bonhoeffer (39)** — all verified.
Or keep it lighter on obscurity: relabel to **"Died at 40"** and use **Edgar Allan Poe, Glenn Miller, John Lennon, + one more verified 40**. Either works; needs an editorial pick.

---

## B. Design / ambiguity risks (optional — judgment calls, not errors)

- **conn-006 Capital Changes** — blue lists *current* renamed names (Istanbul, St Petersburg, Mumbai, Ho Chi Minh City) and purple lists the *older* names of **the same four cities** (Byzantium, Petrograd, Bombay, Saigon). Clever, but genuinely hard/ambiguous — a player has to intuit "current vs earlier." Keep only if you want a hard puzzle.
- **conn-016 Walls and Borders** — **Hadrian's Wall** sits in yellow ("famous walls") but is *also* a Roman frontier defence (blue, alongside the Antonine Wall). A knowledgeable player could justifiably place it in blue. Exploitable overlap.
- **conn-018 Scientific Firsts** — **Faraday** (farad), **Newton** (newton) and **Marie Curie** (curie) all have SI/scientific units named after them, yet they're in the physicists / women-Nobel groups while Volta/Ampère/Ohm/Watt are the "unit namesakes." Classic misdirection, but a sharp player could swap them. Acceptable if intentional.
- **conn-008 Final Words** — beyond the two errors above, it's the loosest puzzle overall: "Off with his head" (a command, not spoken *by* the condemned) and "Hold the fort" (a signal, not last words) are weak fits. Worth a broader polish someday.
- **conn-014 blue** — label "Assassinated **young** leaders" but JFK (46), Lincoln (56) and Caesar (55) weren't young. Minor: drop "young."

### Smaller factual softness (low priority)
- conn-002 yellow vs blue: **Waterloo** (in yellow "famous battles") is also Napoleon's most famous defeat — intentional misdirection, fine.
- conn-007 yellow "Born in WWII": **radar** was developed in the mid-1930s (pre-war); **microwave oven** (1945) is borderline. Loose but defensible.
- conn-019 purple: **Maximilian of Mexico** was installed by France, not strictly "self-proclaimed."
- conn-022 purple: "Marie Antoinette's cake" isn't a disaster, and "Typhoid Mary" was a genuine carrier — the "blamed wrongly" framing is a stretch for two of four. Clever meta-group; keep if you like it.

---

## C. Clean puzzles (no changes needed)

conn-001, 003, 004, 005, 009, 010, 011, 012, 015, 017, 018*, 020, 021, 023, 024 — solid.
(*018 clean factually; see the unit-namesake overlap note above.)

conn-005's "Sculptors of a David" (Michelangelo / Donatello / Bernini / Verrocchio — all four really did carve a David) and conn-023 ("Words From the Past") are standouts.

---

*Ages and battle outcomes above are textbook-level facts (birth/death years, Thermopylae, Borodino). Flagged with high confidence; happy to cite sources for any specific one.*

---

# Thread board audit — 30 Jul 2026 (launch-window pass)

Trigger: Daniel's 30-day launch audit — "some boards aren't logical enough, some
categories are disputable; study NYT Connections and audit all the boards."

## What actually makes a NYT Connections board fun (from studying the archive)

Sampled real NYT boards (July 2026 back through 2025 via the public answer
archives). Five patterns carry the whole game:

1. **The phantom category.** The best grids plant 5–6 tiles that *suggest* a
   group that doesn't exist (EMPIRE the apple + OTTOMAN the palindrome tease a
   nonexistent "empires" group). The solve is realising the obvious grouping
   is the wrong one.
2. **Polysemy is the engine.** Tiles earn their place by having two readings
   (HORSE: gymnastics apparatus *and* zodiac animal). A tile with one meaning
   is filler.
3. **Mixed category archetypes.** A board is rarely four taxonomies. The
   canonical mix: one synonym/definition set, one family-membership set, one
   attribute or fill-in-the-blank set ("On the ___"), one structural-wordplay
   set (hidden words, anagrams, palindromic starts).
4. **Uniform tile surface.** Every tile looks the same *kind* of thing, so
   grammar can't sort the grid — only knowledge can. Tiles never repeat a
   word from their own label.
5. **Difficulty is ambiguity, not obscurity.** Purple is hard because the
   *connection* is hidden, not because the tiles are unheard of. An obscure
   tile is allowed only when the other three members make it solvable by
   elimination.

**Translations that work for a history game:** names that are also words/ships/
places (Bismarck, Victoria, Churchill); "Battle of ___ / ___ the Great /
Operation ___" fill-ins; hidden structures (Roman forts in -chester names,
gods in weekday names, Roman numerals in words); dates as the hidden axis
("all happened in 1917"); nickname/epithet traps (The Black Prince is *not* a
king). Enforced mechanically now: `tools/validate_boards.py` WARNs on
self-labeling groups (≥3 tiles repeating a label word, or all four tiles
sharing a token).

## Verdicts on the 30 staged boards (editions 42–71)

**Rebuilt or replaced:**
- ed42: NEW `conn-181` "The Long Way Home" — Odyssey board for launch day
  (movie moment). Siren is the trap: reads as a peril, sits in the
  words-the-epics-left group. `conn-067` back to stock, unburnt.
- `conn-162` Conquest of the Air (ed44): was sortable by tile type alone
  (people/craft/parts). Now two people-groups with phantom-first traps
  (Earhart and Gagarin both read as "firsts", both sit in "never came back"),
  and a "Flying ___" purple (Scotsman/Dutchman/Finn/Squad). Bonus: the old
  Spirit of St. Louis tile collided with the ed54 answer — gone.
- `conn-065` The People's Game (ed49): "Argentina 1978" and "Ping-Pong
  Diplomacy" tiles self-labelled. Now 16 bare sports; Marathon (reads
  ancient-Olympic, is place-named), Rugby (reads Victorian, is place-named)
  and Lacrosse (reads Victorian, is pre-Columbian) are the traps.
- `conn-011` Spoils of Empire (ed52): the Marco Polo "said to bring back"
  group wasn't binary (Daniel: he was 'said to bring back' silk too). Replaced
  with commodity money; Cacao beans traps against Chocolate.
- `conn-087` Dates in Disguise (ed53): events now *named* as events (Battle of
  Hastings, Storming of the Bastille), "1917 outside Russia" → "1917" (no tile
  was Russian), and the battle-words now spread across three groups so you
  must date them, not pattern-match them.
- `conn-070` Household Names (ed56): "Patented by a woman" (unknowable) →
  "Everyday things named after a person" (Sandwich/Cardigan/Wellington/
  Mackintosh), which mirror-traps the trade-surnames group.
- `conn-075` Mind How You Go (ed57): "Denounced as a menace to the young"
  (disputable) → Victorian seaside resorts; Boater added to the hats as the
  seaside trap.
- `conn-048` To the Ends of the Earth (ed60): sea-ice jargon (Growler, Bergy
  Bit) → polar phenomena everyone knows (Aurora, Midnight Sun, Polar Night,
  Permafrost).
- ed63: `conn-078` Unfinished Business pulled (self-labeling Edwards +
  numbered Crusades — "too easy, not satisfying"). Rebuilt in stock as a
  medium: unfinished works / heirs who never took the throne (Black Prince
  and Old Pretender trap against the kings' nicknames group) / old coins /
  royal nicknames. `conn-108` Curtain Up (retiered easy, per Daniel "should
  be on an easier day") airs here instead — Monday.
- ed69: needed a hard board → `conn-117` Gods of Many Lands: uniform god
  tiles, three Norse gods split across three groups, weekday-gods purple.
  (`conn-037` was considered and rejected: its Abu Simbel tile would air two
  days before Abu Simbel is an answer.)
- `conn-014` Brute Force (ed61): "A cockerel" → "Rooster" (uniform surface).
  Stays genuinely hard; it airs a Saturday, which is where hard belongs.

**Audited, left standing (with reasons):** conn-044 (1889 purple is exactly
the NYT year-twist; facts check out — Nintendo founded 1889), conn-035,
conn-040 (born-1809 purple; Lincoln tile 4 days after Lincoln airs is a known
WARN, threads don't spoil answers), conn-102 (Odysseus/Achilles sit in the
Trojan group while reading as epic heroes — proper trap structure), conn-004,
conn-077 (Castle/Bishop/Knight chess purple is a textbook phantom group),
conn-061, conn-137, conn-151, conn-055, conn-018 (unit-namesake misdirection
is intentional, June audit agreed), conn-154 (Code of Hammurabi tile vs the
Hammurabi kings group is a legit same-board trap), conn-074, conn-050,
conn-093, conn-058 (Taj Mahal traps against the Mughals group), conn-062,
conn-073, conn-079, conn-108 (nationality-sortable, but Daniel accepted it as
easy-day material and it now airs a Monday).

**Known debt:** the deep-hard taxonomy boards (conn-058, conn-062, conn-130
etc.) are quiz-like rather than trap-like — fine on hard days, but the next
batch of boards should be built phantom-first. The stock-wide sweep beyond
the staged 30 has only had the mechanical screen (self-labeling validator),
not a full editorial pass.
