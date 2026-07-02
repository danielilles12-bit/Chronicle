# Chronicle — Content Audit (2026-07-02)

Scope: all four launch formats. Map of a Life (355 figures), Zoom In Who (76) + What (40) — visual audit of the actual zoom motion, Connections (25 puzzles) — NYT design principles, Chrono (40 sets).

Judging principles agreed with Daniel:
- **Map of a Life**: a puzzle is satisfying when fame × geographic story is high. Gold standard: Napoleon (Ajaccio → St Helena — both famously *his* points, with the irony that neither is mainland France). Weak: an only-somewhat-famous figure born and died in the same city (clue-poor, no journey).
- **Zoom In**: the opening crop must be low-clue (but not pure texture) and the zoom-out must deliver clues progressively — never start on the giveaway.
- **Connections**: NYT principles — every item fits exactly one group *as labeled*; labels are precise enough to exclude the other 12 items; deliberate red herrings; difficulty ladder yellow→purple; purple has a twist (wordplay/lateral), not just harder trivia.

---

## 1. Zoom In — visual audit of all 116 items

Method: re-rendered every item's opening (p=0), mid (p=0.4) and late (p=0.8) frames with the exact crop math from `revealgame.js`, reviewed all 116 by eye (contact sheets in scratchpad).

### Broken asset (fix immediately)
| item | problem |
|---|---|
| **guernica** | `assets/img/guernica.jpg` is the **wrong image entirely** — it shows a photo of a tree-lined road at sunset, not Picasso's painting. Every frame of the round, including the reveal, shows the wrong picture. Likely the downloader grabbed a photo of the town of Guernica. |

### Openings that start on the giveaway (violate the crop rule)
| item | what the opening shows |
|---|---|
| **einstein** | The tongue. The single most identifying feature of that photo fills the opening frame. |
| **karl-marx** | The huge white beard fills the frame — Marx's #1 identifier. |
| **ho-chi-minh** | Opens directly on his face (eye/nose/cheek); the wispy goatee arrives by mid. frac=0.42 clamps to 0.28 but fx/fy sit on the face. |
| **terracotta-warrior** | Wide hall photo — even at the tightest crop the opening already shows *ranks of soldiers in formation*, instantly identifiable. Needs a close-up image of a single warrior, not a tighter crop. |
| **easter-island-moai** | Opening shows a full moai head in profile against grass — unmistakable silhouette from frame one. |

### Borderline-fast openings (identifying attribute visible at open; acceptable but worth a nudge)
- **che-guevara** — beret star at open (Korda photo tell)
- **winston-churchill** — polka-dot bow tie at open
- **sitting-bull** — upright feather at open (narrows to a 2-figure pool with geronimo)
- **starry-night** — opens on the swirling moon, the most iconic corner; consider focal point on the village at bottom
- **birth-of-venus** — opens on the giant scallop shell edge
- **venus-de-milo** — opens centered on the arm stump, the statue's #1 tell
- **tut-mask** — gold/blue stripes at open; known trade-off, labeled easy, fine to keep

### Clue-starved windows (too little info for too long — the opposite failure)
| item | problem |
|---|---|
| **hammurabi-stele** | fx/fy point at blank black basalt. Opening, mid AND late are a featureless dark column; almost zero information until the reveal. Move focal point to the relief at the top (Hammurabi before Shamash) or the inscribed band. |
| **joan-of-arc** | In-play window is mostly red drapery throughout; face/armor arrive only at the very end. |
| **catherine-great** | Focal point tracks the silver gown; even the late frame is dress/arm — verify her face ever enters the in-play window (image is wide; the 0.9-crop may miss it). |
| **da-vinci-self** | Opening and mid are near-pure red-chalk hatching; ramp only kicks in late. Tolerable for a hard item, but consider nudging fx/fy toward the face. |

### Weak reveals (full image is a poor payoff)
- **mussolini** — full-length photo; face is tiny and dark at the reveal
- **jefferson-davis** — full-length standing photo; face illegible at the reveal
- (minor) **trotsky**, **lenin** — very dark/plain through mid; face arrives only at reveal. Acceptable.

Everything else (≈95 of 116) ramps well: opens on fabric/texture/prop, delivers a strong middle clue (medal cluster, pose, instrument), face or object identity lands late. The recalibration commit did its job for the portraits; the failures above are focal-point/asset issues, not the zoom engine.

---

## 2. Connections — NYT-principles audit of all 25 puzzles

(The 2026-06-30 audit covered facts and applied 8 fixes; this pass is design-only.)

### The systemic issue: catch-all labels
NYT labels are precise enough that, post-solve, every item *obviously* belongs to exactly one group. Several puzzles use catch-all labels that genuinely include other groups' items:

| puzzle | violation | suggested fix |
|---|---|---|
| **conn-018** Scientific Firsts | Worst offender. Purple "Namesakes of scientific units" — but yellow's **Newton** (newton) and **Faraday** (farad) also have units named after them; and Volta/Ampère/Ohm are also "Physicists" (yellow's label). Mutual contamination both ways. | Yellow → "20th-century physicists": Einstein, Bohr, **Feynman, Hawking** (drop Newton, Faraday). Purple relabel "Namesakes of electrical units" (volt/amp/ohm/watt — all electrical). |
| **conn-004** Died in Exile | **Kaiser Wilhelm II** (green) was deposed in 1918 — he fits purple "Deposed monarchs of 1917-1922" *exactly* as labeled. | Swap Wilhelm II → **Napoleon III** (deposed 1870, died in exile in England 1873) in green. |
| **conn-024** The Twentieth Century | Purple's "**Bloody Sunday**" is underspecified — a US player reads it as Selma 1965, which collides with blue's "Selma" (civil rights). | Rename item "Bloody Sunday 1905" (spark of the 1905 Russian Revolution) — also makes purple's theme cleaner. |
| **conn-002** Last Stands | Yellow "Famous battles" is a catch-all — **Waterloo** is also Napoleon's most famous defeat (blue's label). Solvable by elimination, but the label doesn't exclude. | Sharpen yellow, e.g. "Battles that became bywords for defeat" (Waterloo, Stalingrad, Hastings, Gettysburg all work). |
| **conn-013** Left-Handed Legends | Blue "Conquerors and generals" — but yellow's Napoleon, Caesar and Alexander are all conquerors/generals too (3 double-fits). The whole puzzle hinges on obscure lefty trivia to peel them apart. | Relabel blue with an excluder, e.g. "Conquerors who never saw Europe's Atlantic coast"… simplest robust fix: blue → "Conquerors of the medieval world" (Genghis, Saladin, Charlemagne, + swap Hannibal → Tamerlane… but Tamerlane is used in conn-025) — flag for rework rather than a quick patch. |
| **conn-015** Seven Seas | Yellow "Famous explorers" — Amundsen/Scott/Shackleton (green) are famous explorers too. | Yellow → "Explorers of the Age of Sail" or "Explorers before 1800" (Columbus, Magellan, da Gama, Cook all qualify; all polar names are 1900s). |
| **conn-016** Walls and Borders | Yellow "Famous walls" contains **Berlin Wall** (fits green "Cold War divisions") and **Hadrian's Wall** (fits blue "Roman frontier defences"). Two of four yellow items fit other labels exactly. | Arguably the intended gimmick (yellow steals the icons), but as-labeled it breaks the one-solution rule twice. Consider green → "Cold War divisions *other than walls*"-style sharpening, or embrace it and sharpen yellow to "Walls tourists visit today". |
| **conn-007** Wartime Inventions | **Microwave oven** (green "Cold War spinoffs") is a civilian use of WWII radar tech — fits purple's label squarely; and it's not really Cold War. | Swap microwave → "Nuclear power" or "Weather satellites"; or relabel purple to "WWII-or-earlier military tech in your home". |
| **conn-019** Dictators | **Bokassa** (purple, self-proclaimed emperor) is also a 20th-century dictator (yellow's label). Soft — resolves by elimination. | Optional: yellow → "European + Mao axis…" — or leave; low priority. |

### Other design notes
- **conn-017** Code Names: "Gold" appears twice on one board (D-Day beach + "Gold (Berlin Tunnel)"), and the parenthetical telegraphs its group. Also "Bletchley Park" is a place, not a project codename. Swap the Berlin Tunnel item → "Ivy Bells" or "Mongoose"; swap Bletchley Park → "Tube Alloys" (British bomb project — also a lovely trap with yellow).
- **conn-022**: the same two disasters appear twice in different framings (Burning of Rome / "Nero and the fire"; Chicago Fire / "Mrs O'Leary's cow"). It's actually an elegant green-vs-purple structure — keep, but know NYT wouldn't repeat a referent on one board.
- **conn-005**: Caravaggio labeled an "Italian Renaissance painter" — he's Baroque. Swap → Tintoretto or Veronese. (Michelangelo-as-painter double-fit is a classic intended red herring — keep.)
- **conn-020**: "Gettysburg Address" under "Founding American documents" (1863 ≠ founding) — relabel "Revered American texts". Tordesillas as a "peace treaty" is stretchy (no war ended) — it also already appears as a line in conn-016.
- **conn-008**: "Off with his head" is an order given *about* someone, not words spoken by the condemned — weakest item in an otherwise fun puzzle.

### Flat puzzles (no trap, no twist — pure sorting)
**conn-009, conn-010, conn-012** are four parallel taxonomies ("rulers of X" × 4). Fair as easy days, but no red herrings and no purple twist. Fine to keep; new content should not add more of these.

### The exemplars (what new puzzles should look like)
- **conn-023** Words From the Past — all-etymology, genuinely NYT-purple in spirit. Best in set.
- **conn-006** Capital Changes — blue/purple mirror (city ↔ its former name) is delicious.
- **conn-004** Died in Exile — "Napoleon's life told in four places" is a great category shape.
- **conn-014** Gone Too Soon — ages-at-death adjacency creates real tension.

---

## 3. Chrono — 40 sets (agent audit + web fact-check)

**Verdicts: 12 great / 22 fine / 6 weak.**
Great: chrono-002, 003, 005, 006, 016, 020, 022, 027, 029, 030, 037, 039.

### Weak sets
| set | problem |
|---|---|
| chrono-012 | Sistine ceiling (1512) vs Mona Lisa (1517) — 5-year coin flip, no narrative to reason it out |
| chrono-014 | Civil War battles at 1-year spacing — coin flips unless you've memorized battle order; relabel hard or respace |
| chrono-023 | Brandenburg Concertos / Ring cycle dates are specialist classical-music knowledge |
| chrono-028 | Marathon (-490) vs Thermopylae (-480) — 10-year coin flip; general audience doesn't know which invasion came first |
| chrono-032 | "Caesar dictator for life" and "Caesar assassinated" both dated -44 with no month field — **unresolvable tie**, must fix (dictator ~Feb, Ides = March) |
| chrono-036 | Brunelleschi dome competition / Cosimo's return — niche Renaissance knowledge; also Donatello's David date (1440) is genuinely disputed by art historians |

### Fact flags (from a web-checked pass over all contested years)
- chrono-032: add month data or reword one Caesar item (see above) — **the one real bug**.
- chrono-009/028: "Alexander conquers Persia -331" is shorthand (Gaugamela 331, Darius died 330) — fine, but don't pair it with another -331/-330 item.
- chrono-021: "Gunpowder weapons in China, 1000" — defensible round number, loosest date in the pool.
- chrono-029: "Greece wins independence 1830" — one convention among several (1821 war start, 1832 recognition); keep but don't pair with 1820s items.
- chrono-036: Donatello's David "1440" — contested (1430s–1460s proposals).
- "Napoleon escapes Elba, March 1815" phrasing: he *sailed* Feb 26, *landed* March 1 — if the label says "escapes", Feb is more defensible; keep "returns to France" phrasing.
- Cuban Missile Crisis: Oct 14 1962 is the U-2 *flight*; discovery (photo analysis) is Oct 15, Kennedy told Oct 16 — phrase the item as "U-2 photographs missile sites".
- Hot-air balloon 1783: animals flew Sept 19, humans Nov 21 — two different flights; don't imply one.
- Everything else checked clean (Colosseum 80, Hagia Sophia 537, Zheng He 1405, Tenochtitlan 1325, Baghdad 762, Maxim 1884, Crécy 1346, Westphalia 1648, Puyi 1912, etc.)

### Difficulty relabels
- chrono-014 medium → hard · chrono-017 medium → easy · chrono-023 medium → hard

### Pool gaps (for new content)
- Heavy Western/US skew; no set anchored in Sub-Saharan Africa, South Asia or Latin America on its own terms
- Post-1990 nearly absent (no 9/11, internet era, 2008 crisis)
- Science/tech is "great man physics" only — no medicine, climate, industry
- All hard sets are Western political/military crises

---

## 4. Map of a Life — 355 figures

### Batch 1 (177 figures): A=39 · B=104 · C=34
Cut candidates dominated by one failure mode: famous-name-but-tiny-distance (Dickens, Jefferson, Adam Smith, Rembrandt, Raphael, Cicero, Aquinas… all <200km, no story). Full lists in the appendix below.

A-tier patterns worth cloning (also the content directions):
- **Exile deaths**: Napoleon, Trotsky, Marie Antoinette (Vienna→Paris), Dante (Florence→Ravenna), Chopin (heart returned to Poland), Ovid (Rome→Black Sea)
- **Explorers dying on the frontier**: Cook (Yorkshire→Hawaii), Magellan (→Philippines), da Gama (→Kochi), Amundsen (lost in the Arctic)
- **Immigrant/refugee arcs**: Einstein (Ulm→Princeton), Tesla (→NY hotel room), Freddie Mercury (Zanzibar→London), Chaplin (London→Hollywood→Switzerland)
- **The map IS the history**: Muhammad (Mecca→Medina = the Hijra), Jesus (Bethlehem→Jerusalem), Anne Frank (Frankfurt→Bergen-Belsen), Atatürk (born in Thessaloniki — Greece!)

### Data flags (batch 1 + fact-check agent)
- **theodosius-i**: birthplace "Italica" is very likely a **mix-up with Trajan/Hadrian** — should be Cauca (Coca), Spain. Fix.
- **cyrus-the-great**: death "Syr Darya, Tajikistan" — battle site is conventionally placed in modern Kazakhstan/Uzbekistan. Fix country.
- **confucius**: death place "Si River" — he died in Qufu by tradition; the 51km distance is an artifact. Fix.
- **pontius-pilate**: all four fields (birth −10/Italy, death 39/Judea) are legendary/unattested — strongest cut-for-data candidate in the set.
- False-precision birth years on genuinely unknown dates: **saint-peter (0)**, **nefertiti (−1369/−1329)**, **boudica (30)**, **spartacus (−103)**. Either cut or accept as convention; Boudica's "Britain→Britain" is also uninformative geography.
- Acceptable conventions (leave): Seneca "Rome", Constantine "Nicomedia", Attila "Pannonia", Eleanor 1122/Poitiers, Vlad "Bucharest", Nebuchadnezzar −634.

### Batch 2 (178 figures): A=67 · B=72 · C=39

**Combined: A=106 · B=176 · C=73.** Cutting all 73 C-tier figures lands the roster at **282** — inside the 250–300 target.

Batch 2 A-tier highlights (more patterns to clone): executions at famous places (Anne Boleyn → Tower, Louis XVI → guillotine, Nicholas II → Yekaterinburg, Robespierre guillotined in the Paris he terrorized), conquistador ironies (Pizarro assassinated in the Lima he founded, Atahualpa), crusader kings dying on campaign (Richard I at Châlus, Louis IX at Tunis, Barbarossa drowned in Turkey), and modern arcs (Grace Kelly Philadelphia→Monaco, Navalny → Arctic penal colony, Chiang Kai-shek → Taipei).

Batch 2 C-tier is dominated by two blocks:
- **Nine minor US presidents** (Garfield, Cleveland, Taft, Van Buren, A. Johnson, Buchanan, Polk, Taylor, Tyler) — no geography story, crowd out better American figures
- **"Italy to Italy" Roman emperors/generals** (Vespasian, Diocletian, Sulla, Galba, Cato, Scipio, Theodosius)

**Borderline cuts flagged for Daniel's judgment** (the agent cut these for obscurity, but they're arguably famous enough to keep as hard items): Zheng He, Justinian, Alfred the Great, Maria Theresa, Pericles, Emperor Meiji, Lorenzo de' Medici, Franz Joseph. Note most of them are also same-city birth/death, which is what really sinks them per the agreed principle.

### Additional data flags (batch 2)
- **hammurabi**: birth −1810 doesn't match standard reign chronology (c. 1792–1750 BC reign); birth year actually unknown.
- (Repeats of the fact-check agent's flags: cyrus death country, theodosius birthplace, saint-peter/nefertiti/boudica/spartacus false precision, pontius-pilate legendary death.)

### Full cut-candidate list (73)
Batch 1: galileo-galilei, johann-sebastian-bach, winston-churchill, hans-christian-andersen, miguel-de-cervantes, charles-dickens, archimedes, niccolo-machiavelli, thomas-jefferson, adam-smith, neil-armstrong, sophocles, thomas-aquinas, cicero, yuri-gagarin, rembrandt, stephen-hawking, jimmy-carter, henry-ford, qin-shi-huang, harry-s-truman, agatha-christie, raphael, theodore-roosevelt, elizabeth-i-of-england, john-maynard-keynes, louis-xiv-of-france, lyndon-b-johnson, james-madison, hernan-cortes, john-quincy-adams, diego-velazquez, andrew-jackson, kim-il-sung, silvio-berlusconi
Batch 2: herbert-hoover, montesquieu, john-milton, zheng-he, epicurus, sappho, james-a-garfield, grover-cleveland, william-howard-taft, martin-van-buren, tacitus, andrew-johnson, james-buchanan, james-k-polk, zachary-taylor, john-tyler, cato-the-elder, harper-lee, alfred-the-great, alexander-iii-of-russia, josephus, theodosius-i, galba, otto-the-great, vespasian, theodoric-the-great, justinian-i, clovis-i, charles-martel, jan-hus, bernardo-ohiggins, maria-theresa, franz-joseph, lorenzo-de-medici, emperor-meiji, scipio-africanus, pericles, darius-i, sulla

⚠️ Batch 1's list includes some very famous names cut for "no geography story" (Churchill, Elizabeth I, Louis XIV, Jefferson, Galileo, Bach…). Per the Napoleon principle these are honest cuts — the two map points teach nothing — but they're also the app's most recognizable names. Alternative to cutting: keep the super-famous ones as easy filler (a player who nails "London-ish → London-ish, 1874–1965, occupation: statesman" still gets a dopamine hit from *Churchill*). Recommend: cut the obscure C's outright (~50), keep ~20 famous-but-flat ones, decision per name in the review tool.

---

## 5. Rename candidates

| current | candidates |
|---|---|
| Map of a Life | **Lifeline** · Two Pins · Cradle & Grave · Span |
| Zoom In: Who | **Face Value** · Close-Up · In Person |
| Zoom In: What | **The Big Picture** · Detail · Masterpiece |
| Chrono | **Out of Order** · First Things First · Turn of Events |
| Connections | **Throughline** (Daniel's) · Common Thread · Ties That Bind |

Note: the game actually zooms *out* — "Zoom In" is a misnomer; any rename fixes that for free.
