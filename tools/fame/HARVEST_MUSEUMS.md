# harvest_museums.py -- museum-object candidates for Relic ('what')

## Why this exists

`universe_objects.json` (built by `build_universe_objects.py`) is harvested
from UNESCO World Heritage *site* lists and Wikipedia vital-article lists,
so it's dominated by buildings, facades, monuments and ruins. A content
review flagged this as a top complaint: players want portable, domestic,
technological, artistic and working-life objects. Open-access museum
collections fix this directly -- their objects are portable by definition,
their photography is on plain backgrounds (which the tear-reveal mechanic
needs far more than a monument shot against sky), and they carry explicit
rights metadata (important given image licensing has already caused
problems in this project).

This script only produces `tools/fame/museum_candidates.json` for a human
(or a later session) to review. **It does not touch `universe_objects.json`
and is not wired into `build_universe_objects.py`.**

## Sources and their current status

| source | status | method | notes |
|---|---|---|---|
| Metropolitan Museum of Art Open Access API | working, no key | full crawl of `isHighlight=true & hasImages=true`, then kept only `isPublicDomain=true` | ~2100 highlight+image objects exist; this is the one source with an unambiguous CC0 rights signal at API scale |
| Smithsonian Open Access API | working, but rate-limited | curated seed-term search list (~60 terms), not a crawl | reachable via the public `DEMO_KEY` (no personal registration done by this script), but DEMO_KEY's token bucket is small (~10, refilling ~1/sec) -- a broad crawl isn't practical on it. A free personal api.data.gov key would lift this a lot; getting one requires a human to sign up, which this automation does not do. |
| Victoria & Albert Museum collections API | working, no key | curated seed-term search list (~30 terms) | API has no explicit "highlight" flag, so curated terms stand in for one |
| Science Museum Group collection API | working, no key, needs a browser-like User-Agent | curated seed-term search list (~30 terms) | the site's edge/WAF returns HTTP 403 for the default curl/urllib User-Agent; this script sends a browser-like one and that's sufficient |
| Rijksmuseum | **skipped** | -- | its API requires a personal registered key; the placeholder tried during exploration returned HTTP 410 Gone. Per the brief, sources needing a key we don't have are dropped rather than faked. |
| "A History of the World in 100 Objects" (BBC Radio 4 / British Museum) | working | parses the wikitext of the English Wikipedia article of that name | the route into British-Museum-curated, Anglophone-canon objects, since the British Museum's own collection API requires registration |

## How to re-run

```
cd "tools/fame"
python3 harvest_museums.py                              # all 5 sources
python3 harvest_museums.py --sources met                 # just one
python3 harvest_museums.py --sources vam,smg,how100       # a subset
```

The script first makes one cheap request to the Met API to confirm network
access, and stops immediately (exit code 1) if that fails, rather than
producing fabricated output.

Every raw HTTP response is cached on disk under
`tools/fame/cache/museums/<source>/<hash>.json` (the `cache/` symlink points
at the gitignored `cache.nosync/`). A killed-and-restarted run replays cache
hits instantly and only makes live requests for whatever it hadn't reached
yet -- there is no separate row-level checkpoint file because the harvest
logic itself is cheap once responses are cached. To force a source to
refetch, delete its subfolder under `cache/museums/`.

Per-source raw dumps land in `tools/fame/raw/museums_<source>.json` (that
whole directory is already gitignored). The final merged, deduped output is
`tools/fame/museum_candidates.json`.

Runtime: the Met source is by far the slowest (it fetches full object
detail for every highlight+image ID, ~2000+ requests at a polite ~6/s, plus
one or two Wikipedia-title-resolution requests per surviving candidate);
budget several minutes for it. The four curated-seed sources are quick
(dozens of search requests each).

## What the output looks like

`museum_candidates.json`:

```json
{
  "summary": {
    "total_raw_before_dedup": ...,
    "total_after_within_run_dedup": ...,
    "already_known_dropped": ...,
    "total_new_candidates": ...,
    "wiki_title_resolved": ...,
    "wiki_title_unresolved": ...,
    "per_source": {"met": N, "smithsonian": N, "vam": N, "smg": N, "how100": N},
    "per_kind": {...},
    "per_region": {...},
    "per_recognition": {"household_name": N, "enthusiast": N},
    "sources": {
      "met": {"status": "ok"|"error"|"skipped", "candidates": N, "note": "..."},
      ...
    },
    "http_stats": {...}
  },
  "candidates": [
    {
      "name": "...",
      "wiki_title": "..." | null,
      "wiki_resolution": "exact" | "wikilink-hint" | "search" | null,
      "source_museum": "...",
      "kind": "ceramic" | "arms_and_armour" | "clothing" | "jewellery" | ...,
      "date_era": "...",
      "region": "Europe" | "East Asia" | ... | null,
      "culture_or_place": "...",
      "image_url": "..." | null,
      "image_licence": "...",
      "museum_object_url": "...",
      "highlight": true|false,
      "recognition": "household_name" | "enthusiast",
      "raw_id": "met:547802" | "smithsonian:nmah_670130" | ...,
      "department": "..." | null
    }
  ]
}
```

Every candidate is deduped against `universe_objects.json`,
`current_inventory.json` (the `game=="what"` rows) and
`data/reveal-what.json` (matched on name *and* the `variants` list, since
that file has no `wiki_title` field) before it's included -- so this file
is meant to be **net-new** content, not a full re-harvest of everything.

### `kind` is a richer vocabulary than `universe_objects.json` uses

`build_universe_objects.py`'s existing `kind` enum is `{building, monument,
site, painting, sculpture, artefact, manuscript}` -- fine for
UNESCO-sourced architecture, too coarse for museum objects. This harvest
uses a wider vocabulary (`ceramic`, `clothing`, `jewellery`,
`arms_and_armour`, `scientific_instrument`, `technology`, `vehicle`, `coin`,
`furniture`, `musical_instrument`, `photograph`, plus the original set) so
the object-type signal isn't flattened to "artefact" for everything. A
later merge into `universe_objects.json` will need to either extend that
enum or map this richer one down to it -- that's a deliberate later
decision, not made here.

### `recognition` is a judgement call, not a score

The product brief for this harvest was corrected mid-task: general-
population popularity metrics (pageviews, sitelink counts) understate what
this app's actual audience already knows, because the stated content bar
for Dead Famous is "Rest Is History podcast listeners" -- a history-
enthusiast audience, not the general public. So every surviving candidate
carries a `recognition` tag instead of being filtered by traffic:

- `household_name` -- recognisable to almost anyone. The scarce easy-tier
  resource the game needs for its easiest days.
- `enthusiast` -- known to history lovers, not the general public. This is
  what most of this harvest actually is, by construction: Met's own
  curatorial "highlight" flag and the BBC/British Museum's curated canon
  mark *significance*, not mass fame.
- `specialist` (too obscure even for enthusiasts) is dropped outright
  before the file is written, rather than kept and flagged.

The tag comes from a small hand-reviewed override list (see
`RECOGNITION_OVERRIDES` in the script -- specific names actually seen in a
harvested run, judged individually) layered over a per-source default (see
`SOURCE_DEFAULT_RECOGNITION`). This is deliberately not a scoring model --
a separate effort in this project owns building an actual history-lover
salience score; this harvest just tags its own output with its best
judgement so that effort has something to work from. Expect to revisit the
override list by eye if this script is re-run against a materially
different candidate set (e.g. after widening the curated seed lists).

A related, always-applied quality filter: any candidate whose name is a
bare "sherds"/"fragment(s)" or similar (`JUNK_NAME_RE`) is dropped
regardless of source, per the original brief's instruction to reject
sherds, unnamed fragments and catalogue-number names.

## Feeding this into build_universe_objects.py (not done here)

This script deliberately stops at `museum_candidates.json`. Wiring it into
the real pipeline is a later decision, but the shape is meant to make that
easy:

1. `build_universe_objects.py` currently reads `raw/unesco_raw.json`,
   `raw/vital_raw.json`, `raw/lists_raw.json` and `manual_seed.SEED`, then
   canonicalizes titles, groups by canonical title, enriches for
   disambiguation/person detection, and writes `universe_objects.json`
   with `{name, wiki_title, kind, region, era_hint, from_lists}` per
   object.
2. `museum_candidates.json`'s candidates already carry a resolved
   `wiki_title` (where resolution succeeded) and a compatible-ish `region`
   (same region vocabulary as `regions.py`), so a future integration could
   treat this file as one more raw source: map its `kind` values down to
   the existing 7-value enum (or extend the enum -- see above), tag
   `from_lists` with something like `"museum-<source>"`, and run it
   through the same canonicalize/enrich/dedup pass `build_universe_objects.py`
   already does for its other sources.
3. The richer per-candidate fields this harvest adds that
   `universe_objects.json` doesn't currently have at all --
   `image_url`, `image_licence`, `museum_object_url`, `highlight`,
   `recognition`, `date_era`, `culture_or_place` -- are exactly the kind of
   thing that would let the Relic reveal screen show a real, rights-clear
   image and a tap-to-expand credit line (the existing credits convention
   per `data/reveal-what.json`'s `license`/`attribution`/`source`/
   `image_*` fields) without another round of manual sourcing. Whether to
   carry them through wholesale, and how to reconcile `image_licence`
   strings that are advisory ("verify per-item before use") rather than a
   clean SPDX-style value, is for whoever does that integration to decide.
