# Dead Famous — model handoff

This folder is a self-contained handoff for another model reviewing or extending the content system for **Dead Famous**, a daily popular-history quiz app.

## Product brief

Dead Famous has four games per day:

1. Identify a dead famous person from a progressively revealed torn portrait.
2. Identify a famous man-made object, building, monument, artwork or artefact from a progressively revealed torn image.
3. Identify a historical figure from their birth and death locations on a map.
4. Solve a 16-tile Connections-style history grouping puzzle.

The audience is the curious global general public: roughly the audience for popular history podcasts, not specialists or academics. A normal weekday should feel winnable. At reveal, a typical player should recognise approximately three of the five answers in each five-answer game. Sundays may be harder.

## Non-negotiable data constraint

Core ranking signals for approximately 7,000 candidates must be fetchable programmatically in bulk from free Wikimedia-family APIs or dumps. Suitable examples include Wikipedia pageviews, Wikidata sitelinks, MediaWiki backlinks, Commons image metadata, Wikipedia Vital Articles membership and structured heritage-list membership. Do not propose Google Trends or signals requiring manual research for all 7,000 candidates.

A one-time visual-quality audit of the final few hundred candidates is acceptable and recommended. It is not a substitute for bulk candidate discovery.

## Files

- `01_dead_famous_figures.csv`: 300 knowledge-selected dead figures intended as a visual-recognition comparison set.
- `02_dead_famous_objects.csv`: 200 knowledge-selected man-made objects, places and artworks intended as a visual-recognition comparison set.
- `03_scoring_visual_daily_rules.md`: the recommended ranking formula, failure-mode corrections, visual gates and exact daily scheduling constraints.

The CSV selections were made from general knowledge rather than by applying fame metrics. Their English Wikipedia titles were then batch-resolved against Wikipedia's API. The API validation affected titles only, not membership or ranking.

## How another model should use this handoff

1. Treat the two CSVs as comparison sets, not unquestionable ground truth.
2. Compare them with the metric-derived ranking to find false positives, false negatives and regional/category gaps.
3. Keep **fame**, **visual recognizability**, **answerability** and **game difficulty** as separate concepts.
4. Preserve the bulk-scriptable constraint when suggesting new signals.
5. Be especially sceptical of famous names with unauthentic likenesses, generic photographs, pageview spikes or English-only prominence.

## Small data caveats

- Orville Wright and Wilbur Wright both resolve to the canonical English article `Wright brothers`.
- A few entries intentionally use the canonical article title rather than the most familiar answer label, for example `Titanic`, `Kremlin`, `Blue Mosque, Istanbul` and `Macintosh 128K`.
- Regional labels describe broad cultural/geographic association and are designed for scheduling, not claims about modern nationality.

