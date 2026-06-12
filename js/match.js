// Forgiving answer matching: case/accent/punctuation-insensitive,
// tolerant of small typos (Damerau-Levenshtein), per-figure variants.

export function normalize(s) {
  return String(s)
    .toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

// Edit distance with transpositions, early-exit above `max`.
export function damerau(a, b, max) {
  const al = a.length, bl = b.length;
  if (Math.abs(al - bl) > max) return max + 1;
  const INF = max + 1;
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

function splitNumeral(s) {
  const parts = s.split(' ');
  const last = parts[parts.length - 1];
  if (parts.length > 1 && ROMANS.has(last)) {
    return [parts.slice(0, -1).join(' '), last];
  }
  return [s, ''];
}

export function isMatch(guess, figure) {
  const g = normalize(guess);
  if (g.length < 2) return false;
  const gNum = splitNumeral(g)[1];
  const cands = [figure.name].concat(figure.variants || []);
  for (const raw of cands) {
    const c = normalize(raw);
    if (!c) continue;
    if (g === c) return true;
    const cNum = splitNumeral(c)[1];
    if (gNum && cNum && gNum !== cNum) continue;
    const tol = tolerance(c.length);
    if (tol > 0 && damerau(g, c, tol) <= tol) return true;
  }
  return false;
}
