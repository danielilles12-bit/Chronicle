# Dead Famous — scoring, image eligibility and daily assembly rules

## 1. Executive recommendation

Do not use a single Wikipedia score as both fame and difficulty.

Wikipedia pageviews, sitelinks and backlinks are three correlated measures of prominence inside the same knowledge ecosystem. They are useful for candidate discovery, but they do not answer the product's central question: **will an ordinary player identify this particular torn image?**

Use three layers:

1. A bulk-scriptable general-fame prior.
2. A visual-eligibility gate and visual-recognizability score.
3. A game-specific difficulty model and constrained daily scheduler.

## 2. Replacement formula

Put every component on a 0–100 scale.

```text
FAME =
  0.40 × evergreen_multilingual_pageviews
+ 0.20 × quality_adjusted_language_breadth
+ 0.10 × clean_mainspace_backlinks
+ 0.15 × cross_region_consensus
+ 0.15 × curated_prominence
```

For the two picture games:

```text
IMAGE_POOL_SCORE =
  visual_eligibility_gate
  × (0.70 × FAME + 0.25 × VISUAL_RECOGNIZABILITY + 0.05 × ANSWERABILITY)
```

`visual_eligibility_gate` is 0 or 1. Huge pageviews therefore cannot rescue an unsuitable visual subject.

For the map game:

```text
MAP_POOL_SCORE = 0.75 × FAME + 0.25 × GEO_DIAGNOSTICITY
```

Score separately within at least these entity classes:

- portrait people;
- map people;
- buildings and monuments;
- individual artworks;
- movable artefacts, vehicles and machines;
- archaeological sites.

Do not percentile-rank all entity classes together.

### Important mathematical correction

`percentile_rank(log1p(x))` is identical to `percentile_rank(x)` because the logarithm preserves ordering. Use either:

- percentile ranks without a logarithm; or
- winsorised z-scores of `log1p(x)` when differences in magnitude should matter.

## 3. Exact component definitions

### Evergreen multilingual pageviews

For each candidate, language and month:

1. Resolve the canonical title and all redirects.
2. Fetch user pageviews for all-access traffic.
3. Sum the canonical page and its redirects; do not allocate disambiguation-page traffic.
4. Normalise within the language edition, either by total project traffic or by candidate percentile for that month.
5. Exclude the latest 90 days.
6. Drop the candidate's two highest months in the five-year window.
7. Calculate `0.70 × median_month + 0.30 × 20th_percentile_month`.

Group languages into broad audiences so several closely related European Wikipedias do not overwhelm the result:

- English;
- Romance;
- Germanic;
- Slavic;
- Middle Eastern and North African;
- South Asian;
- East Asian;
- Southeast Asian.

For an English-language product, give English 35% of the multilingual pageview component and divide the remaining 65% among the other groups.

Flag `spike_driven = true` when `highest_month / median_month > 8`. In that case, cap the fame contribution at the pre-spike distribution.

### Quality-adjusted language breadth

- Count Wikipedia sitelinks only, not every Wikimedia sister project.
- Full credit for a language article at least 1,500 bytes long.
- Give 0.25 credit below 1,500 bytes.
- Give no credit to redirects, disambiguation pages or missing pages.
- Cap the contribution from each language family.
- Apply `log1p` before a magnitude-sensitive standardisation, or use a simple percentile without `log1p`.

### Clean mainspace backlinks

- Namespace 0 only.
- Linking pages must be non-redirects.
- Exclude disambiguation, list, year and date pages.
- Count unique linking pages rather than link occurrences.
- Winsorise at the 95th percentile.
- Keep the weight at 10%; backlink accumulation is strongly affected by article age and editorial structure.

### Cross-region consensus

For each of the eight language groups, record whether the candidate:

1. has a substantive article; and
2. falls above the 70th candidate-pageview percentile in that group.

The score is the percentage of groups passing both conditions. This distinguishes global familiarity from very large single-market prominence.

### Curated prominence

Use list membership as a capped prior:

- Wikipedia Vital Articles;
- UNESCO World Heritage and comparable structured heritage designations;
- a small number of other broad, independently curated global lists.

No single list may contribute more than one third of this component. UNESCO membership by itself must never make an obscure place an easy answer.

## 4. Failure modes and required guardrails

### Correlated Wikipedia signals

Pageviews, language editions and backlinks are not independent evidence. Reduce backlink weight, quality-adjust language count and add cross-region consensus rather than treating 60/20/20 as three different dimensions.

### Recent deaths, films, anniversaries and news

- Exclude the latest 90 days from core fame.
- Use trimmed monthly statistics rather than five-year totals.
- Store recent interest separately if editorial staff want topical choices.
- Never let recent interest determine the easy/medium/hard label.

### English-world and large-wiki bias

- Normalise inside each language edition.
- Aggregate language families rather than raw editions.
- Keep English below 40% of the multilingual component.
- Apply regional representation in pool selection and scheduling, not by falsely inflating difficulty scores.

### Bot-created or minimal sitelinks

- Require a minimum page length for full credit.
- Exclude redirects and non-Wikipedia projects.
- Cap individual language families.

### Disambiguation and redirect traffic

- Exclude pages with the disambiguation page property.
- Never award an entity traffic from a same-name disambiguation page.
- Resolve and sum true redirects because redirect views are not automatically attributed to the target.
- Store a `name_collision` flag for common ambiguous names.

### Backlink inflation

- Namespace 0 and non-redirect sources only.
- Remove list/year/date/disambiguation sources.
- Winsorise extreme counts.
- If feasible from dumps, remove links injected solely through navigation templates.

### Tourism, schoolwork, controversy and curiosity

These are valid evidence that people encounter a subject, but not proof of visual recognition. Multilingual persistence helps; the visual gate must make the final decision.

### Article age

Record article age diagnostically. Flag:

- young pages with very high views but few stable signals;
- old pages with many accumulated links but low persistent views.

Do not mechanically reward or punish age.

### Concept granularity and duplicates

Choose one canonical QID and build a relationship graph using `part of`, `has part`, `instance of`, `creator`, `architect`, `depicts` and `named after`. Do not allow parent/child duplicates such as a site and its best-known building to be scheduled as independent answers close together.

### Percentile instability

Freeze and version a reference universe. Recalculate on a published schedule rather than silently moving every difficulty boundary when new candidates arrive.

### Wikipedia coverage bias

Use quotas to ensure breadth of region, gender, era and domain. Do not relabel low-recognition subjects as easy merely to meet those quotas.

## 5. Visual eligibility and recognizability

### Person-image hard gate for weekdays

A candidate must satisfy all of the following:

1. A selected Commons/Wikidata image exists.
2. The shortest image dimension is at least 800 pixels.
3. A detector finds exactly one dominant face.
4. The face occupies 12–60% of the frame.
5. Estimated yaw is below 30° and pitch below 25°.
6. Eyes, nose and mouth are not materially obscured.
7. It is not a group portrait, cartoon or image containing the answer text.
8. At least two useful images depict the same person, or the canonical image is used by at least five Wikipedia editions.
9. At least 60% of the top ten usable images fall in one face-embedding cluster.
10. The image does not collide with another candidate above a starting cosine-similarity threshold of 0.88.

Store a manual `likeness_status`:

- `photograph`;
- `life_portrait`;
- `contemporary_sculpture`;
- `posthumous`;
- `invented`;
- `uncertain`.

Weekdays allow only the first three. Sundays may use a conventional ancient likeness only when that likeness is itself famous and materially specific, such as the Nefertiti Bust or Tutankhamun's mask.

### Object-image hard gate

1. A canonical image or dominant image cluster exists.
2. Shortest image dimension is at least 1,000 pixels.
3. At least three useful views exist unless it is a flat artwork.
4. At least 60% of candidate images depict the same physical work or stable design.
5. Recognition does not depend primarily on captions, flags, plaques or skyline text.
6. The nearest non-identical candidate is below the visual-collision threshold.
7. A building has a stable façade or silhouette in at least half of its top images.
8. A painting is a specific work or visually consistent named series.
9. The answer is not an umbrella class whose members look substantially different.
10. It is not a replica or reconstruction unless that replica is itself the famous subject.

Reject generic manuscripts, coins, crowns, swords, palaces, temples, bridges, ships and vehicle classes unless the named candidate has a genuinely distinctive form.

### Automated torn-image test

Generate 20 masks at each visibility level:

```text
18%, 32%, 50%, 72%, 100%
```

Reject or demote when:

- fewer than 18 of 20 final pre-answer masks expose a useful part of the subject;
- more than 8 of 20 first-stage masks expose answer text;
- embedding retrieval fails to return the correct candidate in the top five for more than half the 50%-visible masks;
- the answer is identifiable only from text, a flag or a watermark.

### Small manual recognition screen

Apply this only to the top approximately 600 candidates:

- Show the untorn image for three seconds to five people from at least three world regions.
- Weekday inclusion requires three of five to identify the answer.
- Sunday inclusion requires two of five.
- Store `context_dependent` when recognition comes from clothing, setting or props rather than the face or object itself.
- In production, separately ask `Did you recognise it at reveal?` and `Had you heard of it?`

## 6. Difficulty bins

Use predicted untorn-image recognition:

- A: at least 80%;
- B: 65–79%;
- C: 45–64%;
- D: 25–44%;
- E: below 25%.

Before player data exists, initialise from game-specific pool-score percentiles:

- A: top 15%;
- B: next 25%;
- C: next 30%;
- D: next 20%;
- E: bottom 10%.

Apply these independently to each five-answer game:

| Day | Required bins |
|---|---|
| Monday | A A A B C |
| Tuesday | A A B B C |
| Wednesday | A A B C C |
| Thursday | A B B C D |
| Friday | A B C C D |
| Saturday | A B C D D |
| Sunday | A B C D E |

Never begin a sequence with D or E. Put an A in position 1 or 2 and the hardest answer in position 4 or 5.

## 7. Daily assembly constraints

### Inside each five-answer game

- At least 3 macroregions.
- At most 2 answers from one macroregion.
- At least 3 era buckets.
- At most 2 answers from one era bucket.
- At most 2 answers from one broad domain.
- At most 1 answer from the same narrow occupation or object subtype.
- At most 2 answers associated with one modern country.
- At most 1 highly sensitive answer.
- No pair with visual cosine similarity above 0.88.
- No two answers sharing a surname, dynasty, creator or building complex.

Across the two person games:

- At least 1 woman in each game.
- At least 3 women across the 10 people.
- At most 4 political or military leaders.
- At least 2 arts/culture figures.
- At least 2 science/exploration/technology figures.

### Across the 15 answers from the three five-answer games

- At least 5 macroregions.
- At least 6 answers outside Europe and North America.
- No macroregion contributes more than 5.
- No modern country contributes more than 3.
- At least 2 pre-1500 subjects.
- At least 3 from 1500–1799.
- At least 4 from 1800–1945.
- At least 3 post-1945.
- At most 2 sensitive answers.
- Block direct creator/work, architect/building, depicts/person, part-of and named-after relationships between games.
- Do not repeat an answer in Connections on the same day.
- Exact-answer cooldown: 365 days.
- Same narrow subject or dynasty cooldown: 30 days.
- Same Connections relationship cooldown: 14 days.

Use a constraint solver rather than greedily selecting the highest-scoring unused answers.

## 8. Map-game rules

Calculate `geo_competitor_count`: the number of other eligible famous people born within 300 km of the birth pin and dying within 300 km of the death pin.

- Easy geography: 0–2 competitors.
- Medium: 3–8.
- Hard: 9–20.
- Sunday-only: more than 20.

Additional hard constraints:

- At most one birth/death pair under 100 km on weekdays.
- At least two of five pairs span over 1,000 km.
- At least two of five cross a modern national border.
- Reject locations with coordinate uncertainty over 50 km.
- Do not schedule two effectively identical pin pairs within 90 days.
- Famous person does not automatically mean easy map clue; use the separate map formula.

## 9. Connections rules

- Exactly one valid four-group partition under an exact-cover check.
- Zero unintended alternative groups of four.
- Two or three deliberate false triples.
- Every tile belongs to at most two plausible decoy relationships.
- Monday–Friday: at least 12 of 16 tiles are familiarity A/B and at most 2 are D/E.
- Sunday: at least 10 are A/B and at most 4 are D/E.
- Include one easy, one easy-medium, one hard-medium and one hard relationship.
- At most one wordplay or orthographic group.
- If a relationship is specialist, all four members must be A/B.
- If a group contains two D/E members, the relationship must be common and literal.
- Reveal labels must exclude all twelve non-members.
- Reject unbounded categories such as `associated with war`, `important rulers` or `things in museums`.

## 10. Recommended stored fields

Alongside QID, title and score components, store:

```text
entity_class
macroregion
country_or_countries
era_bucket
broad_domain
narrow_domain
gender
sensitivity_level
canonical_image
image_cluster_id
likeness_status
context_dependent
visual_collision_group
spike_driven
name_collision
geo_competitor_count
difficulty_prior_portrait
difficulty_prior_object
difficulty_prior_map
last_scheduled_date
related_qids
```

## 11. Wikimedia implementation references

- Pageview concepts and redirect behaviour: https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/concepts/page-views.html
- Pageview API reference: https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html
- Wikidata sitelinks: https://www.wikidata.org/wiki/Help:Sitelinks/en
- MediaWiki backlinks API: https://www.mediawiki.org/wiki/API:Backlinks
- MediaWiki language-links API: https://www.mediawiki.org/wiki/API:Langlinks
- MediaWiki image metadata API: https://www.mediawiki.org/wiki/API:Imageinfo/en
- Commons structured `depicts` data: https://commons.wikimedia.org/wiki/Commons:Depicts/en

