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
