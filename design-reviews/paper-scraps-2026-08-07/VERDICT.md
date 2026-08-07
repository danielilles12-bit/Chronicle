# The paper scraps — four candidates, photographed from the real game

**Mockup only. Nothing here is on a shipping branch, no BUILD or VERSION was
bumped, and `css/style.css` is untouched.** Branch `mockup/paper-scraps`.

## The complaint, restated

The tear board covers the picture with nine squares. Today every one of them
is the same paper gradient with the word YESTERNERD stamped in the middle. On
a phone that reads as branded wrapping paper, or as nine game tiles — not as
one sheet of paper torn apart. It is the app's signature mechanic (six of the
ten daily rounds, plus the Home hero), so it is worth getting right.

The north star is `new intro images/Codex Image 4 Aug 2026, 16_56_48.png`.
What it does that we don't: ragged torn edges, a lifted curling corner,
magenta paper underside between and beneath the pieces, halftone texture,
hard ink shadows, and **no watermark anywhere**.

## What these pictures are

Not paintings of an idea. Every image in `renders/` is Chromium's own output
of the actual game: a real Face Value and a real Relic board, real adjacency,
the real `tearable` / `locked` / `deny` states, the real tear transition. The
only thing injected is a stylesheet. The harness is `tools/mockup_scraps.py`.

Two subjects, both `reserve: true` in the live pools so no mockup can leak an
unaired answer: **van-gogh-self** (Face Value) and **olmec-colossal-head**
(Relic). Same subject across all four candidates so the comparison is fair.

Board size is the real one: `#rv-frame` is `min(80vw, 40dvh)`, which on an
installed iPhone-13-sized app is **312 CSS px**, rendered at device pixel
ratio 3 and resampled to 312px ("phone size") and 624px ("2x").

---

## Verdict in one line

**Ship candidate 1 now. Ship candidate 2 with it if it survives one look on a
real phone. Candidate 3 is a genuine post-launch project, not a tweak — and
it has one accessibility collision that has to be solved before it could ever
go near a release.**

---

## 0 — Current

`renders/0-current_*`

Nine identical squares, nine identical watermarks. The dashed `tearable`
border is doing all the work of telling you what the board is for; everything
else is repeat pattern.

## 1 — The cheap 80%   ← **ship this**

`renders/1-cheap-80_*` · `css/candidate-1-cheap-80.css` ·
`patches/candidate-1-cheap-80.diff`

Three moves, all pure CSS, no new assets, ~55 lines:

1. **One printer's mark instead of nine watermarks.** The house name survives
   once, small, in the bottom-right corner of scrap 8, where a plate mark
   lives on a real sheet. About a ninth of the ink; the brand impression
   stays.
2. **Nine sheets, not one mould.** Each scrap gets its own paper shade
   (inside a five-value band — same ream, different sheets), its own grain
   angle, its own halftone-dot offset, and its own extra fraction of a degree
   of rotation on top of the one the game already sets. The tell-tale
   −2/0/2/−1/1 repeat stops being visible.
3. **Nine pieces lying on each other.** A 1.5px hard ink shadow per scrap
   plus a reversed paint order, so each piece sits *on* the ones down and to
   its right. Same hard-shadow language as the house's cards. A 3% over-scale
   goes with it, which also closes the slivers of photograph the existing
   rotations were opening along the seams.

**Cost:** about an hour, including the corner-mark placement (the −14deg
swings the line's tail downward, and the frame clips, so the mark sits a
line-and-a-half up from the paper's edge). 41 lines of actual CSS, zero new
files, +2.6 KB gzipped.

**Risk:** near nil. It is the same box model, the same states, the same
transition.

**One thing it changes on purpose:** today a `locked` scrap is signalled by a
dimmer watermark. With eight watermarks gone, that whisper had nowhere to
live, so `locked` now paints a 5%-ink veil over its paper instead. The dashed
`tearable` border — the loud half of the pair, and the half anyone actually
reads — is untouched.

## 2 — One printed sheet   ← **ship with 1 if it survives a real phone**

`renders/2-printed-sheet_*` · `css/candidate-2-printed-sheet.css` ·
`patches/candidate-2-printed-sheet.diff`

Candidate 1 makes nine different sheets. This makes them one sheet again. A
single very faint composition is printed across the whole cover and the nine
scraps each carry a different fragment: a masthead cropped by the sheet edge
over the top row, a double newspaper rule under it, a column rule, a patch of
halftone residue bottom-left, registration crosshairs at two corners, CMYK
bars in the right-hand margin. Scraps 3, 4, 7 and 8 carry a hairline or
nothing.

**Print furniture only** — no facts, no dates, no illustrations, no words
that could be read as a clue. The only lettering is the house name at a size
that crops it to letterforms, which is what a masthead is.

Because the pieces rotate independently, the composition does *not* line up
across the seams. That is the point: it is a sheet that was torn and whose
pieces then shifted.

**Mechanism:** one 300x300 SVG, inlined as a data URI (so the patch has no
file dependency), drawn on `::before` at `background-size: 300% 300%` with a
`background-position` per grid index. One asset, nine crops, no JS.

**Cost:** ~half a day, most of it dialling the strength down — the first pass
was three times too loud and read as a graphic instead of as a ghost.
+2.0 KB gzipped on top of candidate 1.

**Risks, honestly:**
- **It is easy to overdo.** There is one knob (`--sheet-strength`); below
  ~0.6 it disappears on a phone, above ~1.4 it becomes a pattern. The value
  shipped here is 1.0 and it wants one look on Daniel's actual phone in
  daylight before it is trusted.
- **The masthead is set in Georgia**, a system serif, because an SVG used as
  a background image cannot reach the app's own webfont. It renders slightly
  differently on Android. Converting those letterforms to paths is half an
  hour and also shrinks the file.
- Nothing about the mechanic changes: same box, same states, same tap
  targets.

## 3 — The stretch

`renders/3-stretch_*` · `css/candidate-3-stretch.css` ·
`patches/candidate-3-stretch.diff`

Ragged torn edges, magenta paper underside showing between the pieces, hard
ink shadows, one lifted curling corner on the centre scrap.

### The move that makes it safe

The obvious way to do this — clip each scrap to a ragged silhouette — leaks
the game. A bite in a scrap's edge opens a sliver of the **photograph** along
every seam, on every scrap, before the player has torn anything: nine free
clues. The first pass of this did exactly that.

So the layers are turned inside out:

> the **button** becomes the magenta underside sheet, and it always covers
> its whole grid cell; the cream **paper** moves onto `::before`, and that is
> what gets clipped.

A bite in the paper can then only ever expose magenta. It also buys back two
things the naive version loses: **hit testing stays rectangular** (a
pseudo-element's `clip-path` does not affect it) and the `:active`
press-darkening keeps working (the ragged element's filter is on `::before`,
not on the button).

### The honest bill

**Work:** two full days minimum, and that is with the mechanism already
found. This mockup took four rebuilds to get here.

**What it costs structurally:**
- The paper has to be **rebuilt on `::before`**, so every background
  candidates 1 and 2 put on the button gets restacked per grid index — nine
  more rules. One shared surface, three owners.
- `::after` ends up doing three unrelated jobs across the board: the
  locked-state dimming `style.css` already hangs on it, the printer's mark on
  scrap 8, and the lifted corner on scrap 4 — each needing an escape hatch
  from the other two.
- The nine silhouettes are **generated static data**, 68 points each. No
  designer can open them; re-rolling them means re-running a script.
- The lifted corner is **hand-placed on one grid index**. It does not know
  whether that scrap has been torn, and a second one is a second hand-built
  shape.
- +6.1 KB gzipped, and nine extra composited layers.

**What it risks:**
1. **The reduced-motion deny outline collides with the magenta.** `--ch-gold`
   is `#D6008F` — a magenta. Compare the bottom row of either contact sheet:
   in current / 1 / 2 the held outline on the blocked scrap is unmistakable;
   in 3 it nearly vanishes into the magenta rim. This is the accessibility
   fallback for players who have motion reduced, and it would have to be
   re-coloured before this could ship. **Blocking issue.**
2. **Hot magenta against a full-colour photograph.** The north star is a
   *duotone* illustration; the live game shows colour photographs. Once a
   neighbour is torn, the magenta rim borders the picture directly, and there
   is no way in CSS to drop it only on the sides that face an opening. It
   reads well on the Relic (a grey basalt head on blue) and busier on the Van
   Gogh. Worth Daniel's eye at phone size before anyone commits.
3. **The dashed `tearable` border now sits on the magenta rim**, not on the
   torn paper edge — deliberate (a dashed line following a tear reads as
   damage, not as an invitation), but it is a judgement call, not a fact.
4. `clip-path` still clips a focus ring. `.df-scrap` has no keyboard focus
   style today so nothing breaks — but the day one is added, it has to go on
   the button, never on the paper.

### What was measured, not guessed

- **Tap targets.** Every board point was probed at 1 CSS pixel resolution
  (93,636 samples) and compared with today's. Candidates 1, 2 and 3 give
  **identical** results: 3.5% of points change owner, all of them within
  ~2px of a seam, all to an adjacent scrap. The whole 3.5% comes from
  candidate 1's 3% over-scale — **candidate 3's ragged edges add exactly
  zero**, which is the design working. The worst-affected scrap loses 472 of
  ~10,500 px² (4.5%) and is still a ~100x100px target.
- **Every state still reads.** In all four candidates, at the round's opening
  the game reports `torn=[0] tearable=[1,3] locked=[2,4,5,6,7,8]`, and after
  four more legal tears `torn=[0,1,3,4,5]`. Identical across candidates: the
  stylesheets do not touch adjacency, scoring, saves or announcements. The
  `deny` shake and the reduced-motion held outline are both photographed
  (rows 3 and 4 of each contact sheet), and both read in 0, 1 and 2. See
  risk 1 for candidate 3.
- **Speed.** Tearing all nine scraps with the CPU throttled 4x, style-recalc
  time was 29–102 ms across candidates and runs — the run-to-run spread on
  the *unmodified* app (36 / 102 / 42 ms) is wider than the gap between
  candidates. **No candidate shows a measurable slowdown on this harness.**
  That is a desktop measurement, not a field one; treat it as "no red flag",
  not as proof.

---

## Safe now vs post-launch

| | verdict |
|---|---|
| Killing the nine repeated watermarks | **safe now** — one line, all upside |
| Per-scrap paper, grain, dots, rotation | **safe now** |
| Hard ink shadow + reversed paint order | **safe now** |
| The faint printed sheet | **safe now, after one look on a real phone** |
| Ragged edges, magenta underside, lifted corner | **post-launch**, and only after the gold/magenta collision is solved |

---

## Every path

**The review page** (private artifact, everything below laid out to look at,
tap any board for the detailed view):
https://claude.ai/code/artifact/a222ab85-512e-4478-be79-ea1b2a383d70

**Contact sheets (start here)** — current vs 1 vs 2 vs 3, four states each:
- `design-reviews/paper-scraps-2026-08-07/renders/_contact-sheet_who.png` (Face Value)
- `design-reviews/paper-scraps-2026-08-07/renders/_contact-sheet_what.png` (Relic)

**Individual renders** (`design-reviews/paper-scraps-2026-08-07/renders/`),
68 files named
`<candidate>_<who|what>_<open|mid|deny-shake|deny-held>_<1x-phone-size|2x>.webp`,
plus `<candidate>_who_phone.webp` — the whole screen, for context. (WEBP at
q95: the same pictures losslessly are 24 MB for a review that gets looked at
once.)

**The CSS, one file per candidate** (cumulative: 2 is the delta on 1, 3 on 2):
- `design-reviews/paper-scraps-2026-08-07/css/candidate-1-cheap-80.css`
- `design-reviews/paper-scraps-2026-08-07/css/candidate-2-printed-sheet.css`
- `design-reviews/paper-scraps-2026-08-07/css/candidate-3-stretch.css`

**Applyable patches** — each one applies on its own to a clean
`css/style.css` (`git apply`, all three verified):
- `design-reviews/paper-scraps-2026-08-07/patches/candidate-1-cheap-80.diff`
- `design-reviews/paper-scraps-2026-08-07/patches/candidate-2-printed-sheet.diff`
- `design-reviews/paper-scraps-2026-08-07/patches/candidate-3-stretch.diff`

**The harness:** `tools/mockup_scraps.py` — `python3 tools/mockup_scraps.py`
re-shoots everything; `--only 1 3` re-shoots those candidates.
