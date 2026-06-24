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
// so "book" never matches "Cook".
function tolerance(len) {
  if (len <= 4) return 0;
  if (len <= 8) return 1;
  return 2;
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

export function isMatch(guess, figure) {
  const g = normalize(guess);
  if (g.length < 2) return false;
  const gKey = numeralKey(g);
  const gToks = tokens(g);
  const cands = [figure.name].concat(figure.variants || []);
  for (const raw of cands) {
    const c = normalize(raw);
    if (!c) continue;
    if (g === c) return true;
    if (numeralKey(c) !== gKey) continue; // regnal numbers must agree
    const tol = tolerance(c.length);
    if (tol > 0 && damerau(g, c, tol) <= tol) return true;
    if (covers(gToks, tokens(c))) return true;
  }
  return false;
}
