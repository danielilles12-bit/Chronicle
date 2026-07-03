// Forgiving answer matching: case/accent/punctuation-insensitive, tolerant of
// small typos (Damerau-Levenshtein), and of the ways people phrase a correct
// answer — written ordinals ("the First" = "I"), dropped articles, a
// volunteered artist ("… by Leonardo"), and extra words around the core name.

const ARTICLES = new Set(['the', 'a', 'an']);

// Written ordinals / small cardinals → roman numerals, so "Elizabeth the First",
// "Henry 8" and "Elizabeth I" all canonicalise to the same regnal form.
const NUMWORDS = {
  first: 'i', second: 'ii', third: 'iii', fourth: 'iv', fifth: 'v',
  sixth: 'vi', seventh: 'vii', eighth: 'viii', ninth: 'ix', tenth: 'x',
  eleventh: 'xi', twelfth: 'xii', thirteenth: 'xiii', fourteenth: 'xiv',
  fifteenth: 'xv', sixteenth: 'xvi',
};
const ROMAN_BY_NUM = ['', 'i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii',
  'ix', 'x', 'xi', 'xii', 'xiii', 'xiv', 'xv', 'xvi'];

function numToRoman(tok) {
  if (Object.prototype.hasOwnProperty.call(NUMWORDS, tok)) return NUMWORDS[tok];
  const m = /^(\d{1,2})(?:st|nd|rd|th)?$/.exec(tok); // "8", "1st", "14th"
  if (m) {
    const n = parseInt(m[1], 10);
    if (n >= 1 && n <= 16) return ROMAN_BY_NUM[n];
  }
  return tok;
}

// Lowercase, strip accents/punctuation, then canonicalise token-by-token:
// drop a trailing "… by <artist>" clause, drop articles, fold regnal numbers.
export function normalize(s) {
  const cleaned = String(s)
    .toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (!cleaned) return '';
  const out = [];
  for (const tok of cleaned.split(' ')) {
    if (tok === 'by') break;          // "The Last Supper by Leonardo" → "the last supper"
    if (ARTICLES.has(tok)) continue;  // articles never change the answer
    out.push(numToRoman(tok));
  }
  return out.join(' ');
}

// Edit distance with transpositions, early-exit above `max`.
export function damerau(a, b, max) {
  const al = a.length, bl = b.length;
  if (Math.abs(al - bl) > max) return max + 1;
  let prev2 = null;
  let prev = [];
  for (let j = 0; j <= bl; j++) prev[j] = j;
  for (let i = 1; i <= al; i++) {
    const cur = [i];
    let rowMin = i;
    for (let j = 1; j <= bl; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      let v = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
        v = Math.min(v, prev2[j - 2] + 1);
      }
      cur[j] = v;
      if (v < rowMin) rowMin = v;
    }
    if (rowMin > max) return max + 1;
    prev2 = prev;
    prev = cur;
  }
  return prev[bl];
}

// Tolerance scales with the target's length; very short names must be exact
// so "book" never matches "Cook". Capped at 1 everywhere — "one typo per
// word is fine; more isn't" (owner calibration). Multi-token strings are
// compared token-by-token (see stringsMatch/covers) so this cap applies
// per word, not to the whole phrase at once.
function tolerance(len) {
  if (len <= 4) return 0;
  return 1;
}

// Regnal numerals are tiny edit distances apart but name different people:
// "Napoleon III" must never fuzzy-match "Napoleon I".
const ROMANS = new Set(['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix',
  'x', 'xi', 'xii', 'xiii', 'xiv', 'xv', 'xvi']);

// All roman-numeral tokens anywhere in the name, in order. Fuzzy and subset
// matching are only allowed between strings whose numeral sequences are
// identical, so "Cleopatra I" can't ride the typo budget into "Cleopatra", nor
// "Alexander IV of Macedon" into "Alexander III of Macedon".
function numeralKey(s) {
  return s.split(' ').filter((t) => ROMANS.has(t)).join('-');
}

function tokens(s) { return s ? s.split(' ') : []; }

// A guess carrying a royal/honorific title should still match a variant that
// doesn't spell it out (or vice versa): "queen mary" ⇄ "mary i" / "bloody
// mary". Strip a single leading title token from a normalized string; only
// ever applied to build an extra candidate for matching, never in place of
// the untouched string, and only kept when the remainder is long enough to
// be meaningfully a name (>= 4 chars) so it can't turn "st paul" into the
// absurdly short, over-matchable "paul"-vs-anything via "st" alone, etc.
const TITLES = new Set([
  'queen', 'king', 'emperor', 'empress', 'tsar', 'tsarina', 'kaiser',
  'sultan', 'pharaoh', 'pope', 'saint', 'st', 'sir', 'lord', 'lady',
  'president', 'general', 'chancellor',
]);

function stripTitle(s) {
  const toks = tokens(s);
  if (toks.length < 2 || !TITLES.has(toks[0])) return null;
  const rest = toks.slice(1).join(' ');
  if (rest.length < 4) return null;
  return rest;
}

// ---------- pool registration: containment + distinctive-core ----------
// Words too common/structural to ever anchor a match on their own — shared
// across many items' names ("of", "the") or genuinely ambiguous single
// tokens in Chronicle's corpus (regnal/lineage particles). Kept separate
// from ARTICLES (which normalize() strips outright) because these still
// need to exist as ordinary tokens for containment purposes; they're only
// excluded when building each item's "core" token set.
const CORE_STOPWORDS = new Set([
  'the', 'of', 'a', 'an', 'and', 'in', 'la', 'le', 'el', 'de', 'di',
  'von', 'van', 'der', 'den', 'da', 'du', 'al', 'ii', 'iii',
  'with', 'off', 'on', 'at', 'for', 'to', 'from', 'as',
  // Generic common nouns that describe rather than name — happen to be
  // pool-unique in Chronicle's current corpus (only "Girl with a Pearl
  // Earring" has "girl" in its name) but are not a real identifying name
  // component, so they must never anchor a distinctive-core match alone.
  'girl', 'boy', 'man', 'woman',
]);

// key -> { byId: Map<id, {variantSets: string[][], distinctive: Set<string>}>,
//          tokenOwners: Map<token, Set<id>> } — kept only for inspection/debug.
const POOLS = new Map();

// Split a normalized string into its tokens (helper name distinct from the
// single-string `tokens()` above since this only ever runs on already
// normalized text supplied by registerPool/isMatch).
function toTokenList(s) { return s ? s.split(' ').filter(Boolean) : []; }

// Register (or replace) a pool of items under `key` so isMatch(guess, item, key)
// can additionally accept containment and distinctive-core-token matches
// scoped to that pool. `items` must each have a stable `.id`, a `.name`, and
// an optional `.variants` array — the same shape mapgame/revealgame already
// pass into isMatch. Safe to call again (e.g. hot reload) — replaces the pool.
//
// Distinctive-core v2: a core token is only ever *eligible* to anchor a
// match if it comes from the item's NAME (e.g. "nazca" from "Nazca Lines").
// Tokens that only appear in a variant ("maid" from "the maid of orleans")
// never qualify, even if they'd otherwise be unique in the pool — variants
// are alternate full names a guesser might type in full, not a grab-bag of
// keywords. The pool-wide uniqueness check still scans every variant's
// tokens (not just names), so a name token colliding with some other item's
// variant token is correctly still treated as non-distinctive.
export function registerPool(key, items) {
  const byId = new Map();
  const tokenOwners = new Map(); // token -> Set<id> across the whole pool (names + variants)
  for (const item of items) {
    const variantStrs = [item.name].concat(item.variants || [])
      .map(normalize).filter(Boolean);
    const variantTokLists = variantStrs.map(toTokenList);
    const nameToks = toTokenList(normalize(item.name));
    const nameCoreTokens = new Set();
    for (const t of nameToks) {
      if (!CORE_STOPWORDS.has(t) && t.length > 0) nameCoreTokens.add(t);
    }
    const allTokens = new Set();
    for (const toks of variantTokLists) {
      for (const t of toks) {
        if (!CORE_STOPWORDS.has(t) && t.length > 0) allTokens.add(t);
      }
    }
    for (const t of allTokens) {
      if (!tokenOwners.has(t)) tokenOwners.set(t, new Set());
      tokenOwners.get(t).add(item.id);
    }
    byId.set(item.id, { variantStrs, variantTokLists, nameToks, nameCoreTokens });
  }
  // A name-core token is distinctive for an item iff no other item's
  // name+variant tokens include it anywhere in the pool.
  for (const [, entry] of byId) {
    entry.distinctive = new Set();
    for (const t of entry.nameCoreTokens) {
      const owners = tokenOwners.get(t);
      if (owners && owners.size === 1) entry.distinctive.add(t);
    }
  }
  POOLS.set(key, { byId, tokenOwners });
}

const MIN_GUESS_LEN = 4; // guard rail: rules 2-3 never auto-accept below this

// Regnal guard: a guess carrying a roman-numeral/ordinal token that isn't
// part of the matched variant itself names a *different* person than the
// one being matched — "Napoleon III" must never match "Napoleon" (via
// containment) even though "Napoleon" ⊆ "Napoleon III" as plain words.
// "Elizabeth I" must still match a variant that itself is "elizabeth i"
// (the numeral there belongs to the variant, not an "extra" guess token).
function hasExtraneousRegnal(guessToks, variantToks) {
  const variantHas = new Set(variantToks.filter((t) => ROMANS.has(t)));
  for (const t of guessToks) {
    if (ROMANS.has(t) && !variantHas.has(t)) return true;
  }
  return false;
}

// Rule 2: containment — does `variant` (as a whole word-sequence) appear
// inside `guessToks`, exact token match, no per-token fuzz? A variant that is
// entirely stopwords can never satisfy this on its own (guard rail). Blocked
// when the guess carries a regnal numeral the variant doesn't account for.
function containsPhrase(guessToks, variantToks) {
  if (!variantToks.length) return false;
  if (variantToks.every((t) => CORE_STOPWORDS.has(t))) return false;
  if (hasExtraneousRegnal(guessToks, variantToks)) return false;
  const n = variantToks.length;
  for (let i = 0; i + n <= guessToks.length; i++) {
    let ok = true;
    for (let j = 0; j < n; j++) {
      if (guessToks[i + j] !== variantToks[j]) { ok = false; break; }
    }
    if (ok) return true;
  }
  return false;
}

// Rule 3: distinctive-core — does any guess token match (exact, or damerau
// distance 1 for tokens >= 6 chars) a token that is distinctive for this item
// within its registered pool? Blocked when the guess carries a regnal
// numeral not part of the item's own name (e.g. "napoleon iii" must not
// ride the core-token "napoleon" into a match).
function containsDistinctiveCore(guessToks, distinctiveSet, nameToks) {
  if (!distinctiveSet || !distinctiveSet.size) return false;
  if (hasExtraneousRegnal(guessToks, nameToks || [])) return false;
  for (const gt of guessToks) {
    if (gt.length < MIN_GUESS_LEN) continue; // guard rail
    if (distinctiveSet.has(gt)) return true;
    if (gt.length >= 6) {
      for (const dt of distinctiveSet) {
        if (dt.length >= 6 && damerau(gt, dt, 1) <= 1) return true;
      }
    }
  }
  return false;
}

// Every core token of `cand` appears somewhere in `guess` (typo-tolerant), so a
// guess may carry extra words: "Queen Elizabeth the First" ⊇ "Elizabeth I",
// "Leonardo da Vinci The Last Supper" ⊇ "The Last Supper". Restricted to
// multi-token answers so a lone surname ("Washington") can't be smuggled in by
// padding the guess with other words.
function covers(guessToks, candToks) {
  if (candToks.length < 2) return false;
  const pool = guessToks.slice();
  for (const ct of candToks) {
    const tol = tolerance(ct.length);
    let hit = -1;
    for (let k = 0; k < pool.length; k++) {
      if (pool[k] === ct || (tol > 0 && damerau(pool[k], ct, tol) <= tol)) { hit = k; break; }
    }
    if (hit < 0) return false;
    pool.splice(hit, 1); // consume the matched guess token
  }
  return true;
}

// Per-token fuzzy equality: same word count, each pair either identical or
// one edit apart (capped, never two). "hagiya sofiya" ~ "hagia sofia" (one
// edit per word); "napolyeone" (single token, 2 edits from "napoleon") does
// not qualify — that's a whole-string case, handled separately below.
function tokenwiseFuzzyEqual(gToks, cToks) {
  if (gToks.length !== cToks.length) return false;
  for (let i = 0; i < gToks.length; i++) {
    const gt = gToks[i], ct = cToks[i];
    if (gt === ct) continue;
    const tol = tolerance(ct.length);
    if (tol > 0 && damerau(gt, ct, tol) <= tol) continue;
    return false;
  }
  return true;
}

// Exact / fuzzy / covers comparison between one guess string and one
// candidate string, both already normalized. Factored out so the
// title-stripping fallback in isMatch can rerun the same checks on
// de-titled strings without duplicating the logic.
function stringsMatch(g, c) {
  if (g === c) return true;
  if (numeralKey(c) !== numeralKey(g)) return false; // regnal numbers must agree
  const gToks = tokens(g), cToks = tokens(c);
  // Whole-string fuzz only for single-token strings (a lone word's typo
  // budget); multi-token strings compare per-word so the edit-distance cap
  // of 1 applies per word, not smeared across the whole phrase.
  if (gToks.length === 1 && cToks.length === 1) {
    const tol = tolerance(c.length);
    if (tol > 0 && damerau(g, c, tol) <= tol) return true;
  } else if (gToks.length === 1 && cToks.length > 1) {
    // A single-token guess against a multi-word candidate: still allow a
    // one-edit match against the space-removed candidate, so a dropped
    // space ("machupicchu" for "Machu Picchu") counts as the one typo it
    // is, without opening the door to bare-fragment guesses (still capped
    // at distance 1 on the whole joined string).
    const joined = cToks.join('');
    const tol = tolerance(joined.length);
    if (tol > 0 && damerau(g, joined, tol) <= tol) return true;
  } else if (tokenwiseFuzzyEqual(gToks, cToks)) {
    return true;
  }
  return covers(gToks, cToks);
}

// Owner-calibrated permanent rejections: guesses that are plausible-looking
// but name a different, specific, real thing, so no amount of fuzz/core
// logic should ever be allowed to wave them through. Checked first, as a
// straight normalized-string equality (not fuzzy) — exported so data/test
// code can inspect it. Keyed by the *item id* the rejection applies to.
export const REJECTED_GUESSES = {
  parthenon: ['pantheon'],
  stonehenge: ['stonehedge'],
};

// A guess with >= 2 non-stopword tokens counts as "multi-token" for the
// purposes of the containment/distinctive-core carve-out (rule 1). A guess
// like "the wall" (1 meaningful token) doesn't qualify just because it has
// two words.
function meaningfulTokenCount(toks) {
  let n = 0;
  for (const t of toks) if (!CORE_STOPWORDS.has(t)) n++;
  return n;
}

// `poolKey` is optional; when omitted (or not registered via registerPool)
// behaviour is exactly as before — rules 2/3 below are additive acceptance
// paths that only ever add matches, never remove existing ones.
export function isMatch(guess, figure, poolKey) {
  const g = normalize(guess);
  if (g.length < 2) return false;

  // Reject overrides: a normalized guess that exactly equals a known
  // near-miss for THIS item is rejected outright, before any fuzz runs.
  const rejected = REJECTED_GUESSES[figure.id];
  if (rejected && rejected.some((r) => normalize(r) === g)) return false;

  const pool = poolKey && POOLS.get(poolKey);

  const gNoTitle = stripTitle(g);
  const cands = [figure.name].concat(figure.variants || []);
  const guessToksAll = toTokenList(g);
  const singleToken = meaningfulTokenCount(guessToksAll) < 2;

  for (const raw of cands) {
    const c = normalize(raw);
    if (!c) continue;
    if (stringsMatch(g, c)) return true;
    // Title/honorific-insensitive fallback: strip a leading "queen"/"king"/…
    // from whichever side(s) have one, then compare again. Covers "queen
    // mary" vs "mary i" as well as a guess without a title against a variant
    // that happens to carry one. Stripping the title off the CANDIDATE is
    // skipped for single-token guesses: it would manufacture a bare-fragment
    // comparison ("mary" vs "queen mary" stripped to "mary") that rule 1
    // never allows a lone-word guess to win on — "mary" alone must not
    // match "Mary, Queen of Scots" just because one of her variants happens
    // to start with a title.
    const cNoTitle = stripTitle(c);
    if (gNoTitle && stringsMatch(gNoTitle, c)) return true;
    if (cNoTitle && !singleToken && stringsMatch(g, cNoTitle)) return true;
    if (gNoTitle && cNoTitle && stringsMatch(gNoTitle, cNoTitle)) return true;
  }

  // Rule 1 guard: a guess with fewer than 2 meaningful tokens can only ever
  // match via the variant list above (exact, or one edit) — it never gets
  // the containment/distinctive-core carve-outs below. Otherwise a bare
  // fragment ("nazca", "tut", "wall", "pyramid") could ride a single shared
  // or distinctive word into an accept despite naming no one in full.
  if (singleToken) return false;

  // Guard rail: guesses under MIN_GUESS_LEN normalized characters never
  // auto-accept via containment/distinctive-core (rules 2-3) — they can
  // still have matched a short variant exactly above (e.g. "cid").
  if (g.length < MIN_GUESS_LEN) return false;

  // Collision guard: if the normalized guess is exactly some OTHER pool
  // item's name/variant, it names that other thing, not this one — block
  // the containment/distinctive-core carve-outs below regardless of how
  // fuzzy/containing the guess might otherwise look against the current
  // item. Scoped to here (not the direct variant-list match above) so two
  // items that legitimately share an exact nickname/variant string (e.g.
  // two "Queen Mary"s) can still both be matched by their own shared name.
  if (pool) {
    for (const [otherId, otherEntry] of pool.byId) {
      if (otherId === figure.id) continue;
      if (otherEntry.variantStrs.includes(g)) return false;
    }
  }
  const guessToks = guessToksAll;

  // Rule 2: containment — any accepted variant, as a whole word sequence,
  // found inside the (longer) guess.
  for (const raw of cands) {
    const c = normalize(raw);
    if (!c) continue;
    if (containsPhrase(guessToks, toTokenList(c))) return true;
  }

  // Rule 3: distinctive-core — a guess containing a core token that is
  // unique to this item within its registered pool (eligible tokens come
  // from the item's NAME only — see registerPool).
  if (pool) {
    const entry = pool.byId.get(figure.id);
    if (entry && containsDistinctiveCore(guessToks, entry.distinctive, entry.nameToks)) {
      return true;
    }
  }

  return false;
}
