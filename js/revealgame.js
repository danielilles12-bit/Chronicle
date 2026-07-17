// "Face Value" / "Relic" — guess the famous face or artefact hidden under a
// 3x3 grid of paper scraps. Tearing scraps off is the player's choice and the
// player's cost: the first tear is free, each further tear docks the round's
// worth, and wrong guesses dock more. No clock — curiosity is the only spender.
// Mirrors the Map of a Life session shape (10 rounds, persisted, resumable).
import { DATA, $, show, back, goHome, refreshHomeStats, setReceiptStamp, maybeIntro, openIntroHelp, wireTurnThePage } from './app.js';
import * as store from './storage.js';
import { isMatch, registerPool } from './match.js';
import * as daily from './daily.js';
import { revealShareText, revealEmojiRow, shareResult, flashShareButton } from './sharecard.js';
import { attachPinchZoom } from './pinchzoom.js';
import * as sfx from './sfx.js';

const ROUNDS = 10;
const SCRAPS = 9;               // 3x3 cover grid
const TEAR_COST = 10;           // per scrap after the first (first tear is free)
const WRONG_PENALTY = 15;       // per wrong guess
const WORTH_START = 100;
const WORTH_FLOOR = 10;         // a correct answer never pays less than this
const CLUE_A_COST = 25;         // "Claim to fame" (who) / "First letters" (what)
const CLUE_B_COST = 15;         // "Lived" (who) / "Era" (what)

let S = null;
let MODE = 'who';               // 'who' = portraits, 'what' = artefacts
let frameZoom = null;           // pinch-zoom handle for #rv-frame

function pool() {
  return DATA.reveal.filter((x) => (MODE === 'who' ? x.kind === 'portrait' : x.kind !== 'portrait'));
}

// ---------- clue slips (buyable hints) ----------
// WHO blurbs are reliably "Occupation (1638–1715) · credit": the occupation is
// everything before the first parenthetical; the years live inside it.
function clueOccupation(item) {
  let occ = (item.blurb || '').split('(')[0];   // drop "(years) · credit"
  occ = occ.split('·')[0];                      // and any bare "· credit" fragment
  return occ.trim().replace(/[·,\s]+$/, '').trim();
}
function clueYears(item) {
  const m = (item.blurb || '').match(/\(([^)]*\d[^)]*)\)/);   // first parens holding a digit
  return m ? m[1].trim() : null;
}

// Leading articles/particles skipped when abbreviating an artefact's name to
// initials ("The Colosseum" → "C.", "Hanging Gardens of Babylon" → "H. G. B.").
const REVEAL_ARTICLES = new Set([
  'the', 'of', 'a', 'an', 'and', 'la', 'le', 'el', 'al', 'de', 'del', 'della',
  'di', 'da', 'van', 'von', 'des', 'du', 'les',
]);
function clueInitials(name) {
  const parts = (name || '').split(/\s+/)
    .filter((w) => w && !REVEAL_ARTICLES.has(w.toLowerCase().replace(/[^a-z']/gi, '')));
  return parts.map((w) => (w[0] || '').toUpperCase() + '.').join(' ').trim();
}

// WHAT blurbs are freeform prose that USUALLY carries a date. Try, in order:
// (a) an N-th-century phrase, (b) a year tagged BC/BCE/AD/CE, (c) a plain
// modern year (1000–2100, with optional "c.", range, or decade "s"). Returns
// null when the blurb is genuinely undatable so the Era clue can be hidden.
function extractEra(blurb) {
  if (!blurb) return null;
  let m = blurb.match(/\b\d{1,2}(?:st|nd|rd|th)[ -]centur(?:y|ies)(?:\s+(?:BC|BCE|AD|CE))?/i);
  if (m) return m[0].trim();
  m = blurb.match(/\b(?:AD|CE|BC|BCE)\s+\d{1,4}(?:\s*[–-]\s*\d{1,4})?\b|(?:c\.?\s*)?\b\d{1,4}(?:\s*[–-]\s*\d{1,4})?\s*(?:BC|BCE|AD|CE)\b/i);
  if (m) return m[0].trim();
  const re = /(?:c\.?\s*)?\b(\d{4})(?:s\b|\s*[–-]\s*\d{1,4}s?)?/g;   // fresh: no shared lastIndex
  let mm;
  while ((mm = re.exec(blurb))) {
    const y = parseInt(mm[1], 10);
    if (y >= 1000 && y <= 2100) return mm[0].trim();
  }
  return null;
}

// The two clue slips per MODE. Button A always has content; button B may be
// null (undatable Relic) → its button is hidden for that round.
function clueDefs() {
  const item = round();
  if (MODE === 'who') {
    return {
      a: { label: 'Claim to fame', cost: CLUE_A_COST, value: () => clueOccupation(item) },
      b: { label: 'Lived', cost: CLUE_B_COST, value: () => clueYears(item) },
    };
  }
  return {
    a: { label: 'First letters', cost: CLUE_A_COST, value: () => clueInitials(item.name) },
    b: { label: 'Era', cost: CLUE_B_COST, value: () => extractEra(item.blurb) },
  };
}

function addHintChip(text) {
  const chip = document.createElement('div');
  chip.className = 'hint-chip';
  chip.textContent = text;
  $('#rv-hint-chips').appendChild(chip);
}

// Label the two clue buttons for this round's MODE, re-enable them, and hide
// button B when its clue has no content (an undatable Relic).
function setupClues() {
  $('#rv-hint-chips').innerHTML = '';
  const defs = clueDefs();
  const btnA = $('#rv-clue-a');
  btnA.innerHTML = `${defs.a.label} <span class="cost">−${defs.a.cost}</span>`;
  btnA.disabled = false;
  btnA.hidden = false;
  const btnB = $('#rv-clue-b');
  const bVal = defs.b.value();
  if (bVal == null || bVal === '') {
    btnB.hidden = true;
    btnB.disabled = true;
  } else {
    btnB.innerHTML = `${defs.b.label} <span class="cost">−${defs.b.cost}</span>`;
    btnB.disabled = false;
    btnB.hidden = false;
  }
}

function buyClue(which) {
  if (!S || !S.cur || !S.cur.open) return;
  const key = which === 'a' ? 'clueA' : 'clueB';
  if (S.cur[key]) return;
  const def = clueDefs()[which];
  const value = def.value();
  if (value == null || value === '') return;
  S.cur[key] = true;
  S.cur.clueCost = (S.cur.clueCost || 0) + def.cost;
  $(which === 'a' ? '#rv-clue-a' : '#rv-clue-b').disabled = true;
  addHintChip(`${def.label}: ${value}`);
  updateWorth();
}

// ---------- rng (shared shape with mapgame) ----------
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function makeRng() {
  const p = new URLSearchParams(location.search).get('revealseed');
  return mulberry32(p ? parseInt(p, 10) : (Date.now() & 0xffffffff) ^ 0x9e3779b9);
}
function shuffled(arr, rng) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// ---------- image painting ----------
const dims = {};               // img path -> {w,h}, cached after first load

// The frame shows a square window into the image, covered by scraps. The
// window is `cover`-fit and biased toward the item's focal point so the
// money shot is IN the frame — which scrap hides it is the difficulty.
function paintCover(item) {
  const frame = $('#rv-frame');
  frame.classList.remove('df-duotone');
  frame.style.backgroundImage = `url("${item.img}")`;
  frame.style.backgroundColor = '#111';
  frame.style.backgroundSize = 'cover';
  frame.style.backgroundPosition = `${(item.fx * 100).toFixed(1)}% ${(item.fy * 100).toFixed(1)}%`;
}

// On reveal the frame drops the square scrap-grid shape and morphs to the
// image's real aspect (CSS transition on #rv-frame animates it). With an exact
// aspect there is no cropping, so `cover` shows the whole picture, no bars.
// Portrait images cap their HEIGHT (~44dvh) so tall pictures don't overrun the
// screen; landscape/square keep the guessing width. Missing dims (image
// failed) fall back to the old `contain` square.
function paintFull(item) {
  const frame = $('#rv-frame');
  frame.style.backgroundImage = `url("${item.img}")`;
  frame.style.backgroundPosition = 'center';
  frame.style.backgroundRepeat = 'no-repeat';
  const d = dims[item.img];
  if (d && d.w && d.h) {
    frame.style.aspectRatio = `${d.w} / ${d.h}`;
    frame.style.width = d.h > d.w
      ? `min(80vw, calc(44dvh * ${d.w} / ${d.h}))`
      : 'min(80vw, 40dvh)';
    frame.style.backgroundSize = 'cover';
  } else {
    frame.style.backgroundSize = 'contain';
  }
}

function ensureDims(item, cb) {
  const d = dims[item.img];
  if (d && !d.failed) { cb(); return; }
  const img = new Image();
  img.onload = () => { dims[item.img] = { w: img.naturalWidth, h: img.naturalHeight }; cb(); };
  // A failed load is remembered (so the round can show its honest offline
  // notice) but never treated as real dims — Retry clears it and reloads.
  img.onerror = () => { dims[item.img] = { failed: true }; cb(); };
  img.src = item.img;
}

// Honest offline state (owner report 2026-07-15, the aeroplane case): if the
// round's image never arrived, don't deal nine scraps over a blank void —
// cover the frame with a "not downloaded" notice and park the controls.
function setRoundOffline(off) {
  const el = $('#rv-offline');
  if (el) el.hidden = !off;
  if (!off) $('#rv-offline-retry').textContent = 'Retry';
  const cur = S && S.cur;
  $('#rv-input').disabled = off;
  $('#rv-guess-btn').disabled = off;
  $('#rv-reveal').disabled = off;
  $('#rv-clue-a').disabled = off || !!(cur && cur.clueA);
  $('#rv-clue-b').disabled = off || !!(cur && cur.clueB);
  $('#rv-scraps').style.visibility = off ? 'hidden' : '';
}

// ---------- scraps ----------
// The money scrap is the grid cell holding the focal point (fx/fy map to the
// frame under cover-fit positioning). The round OPENS with the scrap farthest
// from it already torn — free — and only scraps orthogonally touching an open
// scrap can be torn next, so the player plots a route toward the reveal.
function moneyScrap(item) {
  const c = Math.min(2, Math.floor(item.fx * 3));
  const r = Math.min(2, Math.floor(item.fy * 3));
  return r * 3 + c;
}
function startScrap(item) {
  const m = moneyScrap(item);
  // Curated override (start-scrap fairness audit, tools/audit_start_scraps.py):
  // the farthest-from-the-money-shot default can land on sky/backdrop; `start`
  // pins the opening scrap to a cell that actually shows part of the subject.
  if (Number.isInteger(item.start) && item.start >= 0 && item.start <= 8
      && item.start !== m) {
    return item.start;
  }
  const mr = Math.floor(m / 3), mc = m % 3;
  let best = 0, bd = -1;
  for (const i of [0, 2, 6, 8, 1, 3, 5, 7, 4]) {   // corners first, deterministic
    const d = Math.abs(Math.floor(i / 3) - mr) + Math.abs((i % 3) - mc);
    if (d > bd) { bd = d; best = i; }
  }
  return best;
}
function neighbors(i) {
  const r = Math.floor(i / 3), c = i % 3;
  const out = [];
  if (r > 0) out.push(i - 3);
  if (r < 2) out.push(i + 3);
  if (c > 0) out.push(i - 1);
  if (c < 2) out.push(i + 1);
  return out;
}
function refreshTearable() {
  if (!S || !S.cur) return;
  const torn = new Set(S.cur.torn);
  const open = new Set();
  for (const t of torn) for (const n of neighbors(t)) if (!torn.has(n)) open.add(n);
  document.querySelectorAll('#rv-scraps .df-scrap').forEach((el) => {
    const i = +el.dataset.i;
    if (torn.has(i)) return;
    el.classList.toggle('tearable', open.has(i));
    el.classList.toggle('locked', !open.has(i));
  });
}
function worthNow() {
  const cur = S && S.cur;
  if (!cur) return WORTH_START;
  const paidTears = Math.max(0, cur.torn.length - 1);   // first tear is free
  const clueCost = cur.clueCost || 0;                   // bought clue slips
  return Math.max(WORTH_FLOOR, WORTH_START - TEAR_COST * paidTears - WRONG_PENALTY * cur.wrongs - clueCost);
}

function updateWorth() {
  const el = $('#rv-worth');
  if (!el || !S || !S.cur) return;
  const label = MODE === 'what' ? 'INK' : 'WORTH';
  // The round opens with one scrap already torn on the house (that's the
  // "first tear free" in worthNow's ledger) — say so, then price the rest.
  // Once the player has torn one themselves the economy is learnt: hush.
  const hint = S.cur.torn.length <= 1 ? ' · first scrap free · next −10 each' : '';
  el.innerHTML = `${label}: <b>${worthNow()} PTS</b>${hint}`;
}

function buildScraps() {
  const wrap = $('#rv-scraps');
  wrap.innerHTML = '';
  wrap.hidden = false;
  for (let i = 0; i < SCRAPS; i++) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'df-scrap';
    b.dataset.i = i;
    b.setAttribute('aria-label', `Tear scrap ${i + 1}`);
    b.style.transform = `rotate(${((i * 7) % 5) - 2}deg)`;
    b.addEventListener('click', () => tearScrap(i));
    wrap.appendChild(b);
  }
}

function tearScrap(i, force) {
  if (!S || !S.cur || !S.cur.open) return;
  const cur = S.cur;
  if (cur.torn.includes(i)) return;
  // Adjacency rule: a scrap must touch an already-open scrap (the free
  // starting scrap is torn with force=true).
  if (!force && !cur.torn.some((t) => neighbors(t).includes(i))) return;
  cur.torn.push(i);
  const el = $(`#rv-scraps [data-i="${i}"]`);
  if (el) el.classList.add('torn');
  // force = the round's free opening scrap, torn by the game, not the player
  if (!force) sfx.play('tear');
  refreshTearable();
  updateWorth();
}

// ---------- session ----------
export function renderRevealStart(mode) {
  if (mode) MODE = mode;
  const title = $('#rv-start-title');
  if (title) title.textContent = MODE === 'who' ? 'Face Value' : 'Relic';
  const r = store.getReveal(MODE);
  $('#rv-best').textContent = r.sessions
    ? `Your best: ${r.bestScore} pts · longest streak ${r.bestStreak}`
    : 'First session — good luck';
  const saved = store.getRevealSession(MODE);
  const valid = saved && saved.ids && saved.results;
  $('#rv-resume').hidden = !valid;
  if (valid) {
    $('#rv-resume').textContent = saved.results.length >= saved.ids.length
      ? `See your results (${saved.score} pts)`
      : `Resume — round ${saved.results.length + 1} of ${saved.ids.length} (${saved.score} pts)`;
  }
}

function byId(id) { return DATA.reveal.find((x) => x.id === id); }

// Free sessions keep using store.getRevealSession/setRevealSession/
// clearRevealSession (per MODE) exactly as before. Daily and practice
// sessions use the namespaced generic store so they never collide with a
// free session or with each other.
function modeStore(sessMode, key) {
  if (sessMode === 'free') {
    return {
      get: () => store.getRevealSession(MODE),
      set: (s) => store.setRevealSession(MODE, s),
      clear: () => store.clearRevealSession(MODE),
    };
  }
  return {
    get: () => store.getDailySession(key),
    set: (s) => store.setDailySession(key, s),
    clear: () => store.clearDailySession(key),
  };
}

// Warm the browser/SW cache for the whole session so only round 1 can ever
// wait on the network. Sequential chain: never competes with the image the
// player is actually looking at.
function prefetchRounds() {
  if (!S || !S.rounds) return;
  const queue = S.rounds.slice(S.i);
  const next = () => {
    const item = queue.shift();
    if (!item || !S) return;
    if (dims[item.img]) { next(); return; }
    const img = new Image();
    img.onload = () => { dims[item.img] = { w: img.naturalWidth, h: img.naturalHeight }; next(); };
    img.onerror = () => next();
    img.src = item.img;
  };
  next();
}

// Only completed rounds are persisted; resuming restarts the current round
// with its scraps back in place (and its worth reset) — same convention as
// the old timed rounds, where the clock restarted fresh.
function persist() {
  S.store.set({
    ids: S.rounds.map((x) => x.id),
    score: S.score, streak: S.streak, bestStreak: S.bestStreak,
    editionIndex: S.editionIndex,
    results: S.results.map((r) => ({ id: r.item.id, pts: r.pts, correct: r.correct })),
  });
}

function pickRounds(rng) {
  const items = pool();
  const by = (d) => shuffled(items.filter((x) => x.difficulty === d), rng);
  const want = { easy: 4, medium: 3, hard: 3 };
  const picks = [];
  const pools = { easy: by('easy'), medium: by('medium'), hard: by('hard') };
  for (const d of ['easy', 'medium', 'hard']) picks.push(...pools[d].slice(0, want[d]));
  const used = new Set(picks.map((p) => p.id));
  const rest = shuffled(items.filter((p) => !used.has(p.id)), rng);
  const target = Math.min(ROUNDS, items.length);
  while (picks.length < target && rest.length) picks.push(rest.shift());
  return shuffled(picks, rng).slice(0, target);
}

function startSession() {
  const saved = store.getRevealSession(MODE);
  if (saved && saved.ids && saved.results && saved.results.length >= saved.ids.length) {
    resumeSession();             // a finished-but-unviewed session: bank it first
    return;
  }
  const rng = makeRng();
  S = {
    mode: 'free', dailyKey: null, store: modeStore('free', null),
    rounds: pickRounds(rng), i: 0, score: 0, streak: 0, bestStreak: 0, results: [],
  };
  show('view-reveal');
  startRound();
}

function resumeSession() {
  const saved = store.getRevealSession(MODE);
  if (!saved || !saved.ids || !saved.results) return;
  resumeFrom('free', null, saved);
}

// Shared resume path for free/daily/practice.
function resumeFrom(sessMode, key, saved) {
  const st = modeStore(sessMode, key);
  if (saved.ids.some((id) => !byId(id)) || saved.results.some((r) => !byId(r.id))) {
    st.clear();
    if (sessMode === 'free') renderRevealStart();
    return;
  }
  const next = saved.results.length;
  S = {
    mode: sessMode, dailyKey: key, store: st, editionIndex: saved.editionIndex,
    rounds: saved.ids.map(byId),
    i: Math.min(next, saved.ids.length - 1),
    score: saved.score, streak: saved.streak, bestStreak: saved.bestStreak,
    results: saved.results.map((r) => ({ item: byId(r.id), pts: r.pts, correct: r.correct })),
  };
  if (next >= saved.ids.length) { finishSession(); return; }
  show('view-reveal');
  startRound();
}

// ---------- daily / practice entry points ----------
// game key for the daily/practice namespace is 'who' or 'what' (MODE).
function startEdition(sessMode, editionIndex) {
  if (MODE !== 'who' && MODE !== 'what') return;
  const key = sessMode === 'daily' ? daily.dailyKey(MODE, editionIndex) : daily.practiceKey(MODE, editionIndex);
  if (sessMode === 'daily') {
    const entry = store.getDailyEntry(MODE, editionIndex);
    if (entry) { showLockedResult(editionIndex, entry); return; }
  }
  const saved = store.getDailySession(key);
  if (saved && saved.ids && saved.results) {
    resumeFrom(sessMode, key, saved);
    return;
  }
  const mode = MODE;   // capture: MODE is stable while the intro overlay is up
  const begin = () => {
    const rounds = daily.getEdition(mode, editionIndex);
    S = {
      mode: sessMode, dailyKey: key, store: modeStore(sessMode, key), editionIndex,
      rounds, i: 0, score: 0, streak: 0, bestStreak: 0, results: [],
    };
    show('view-reveal');
    startRound();
  };
  // First-run intro before a fresh daily only (not resume/practice/locked).
  if (sessMode === 'daily') maybeIntro(mode, editionIndex, begin);
  else begin();
}

export function startRevealDaily(mode, editionIndex) { MODE = mode; startEdition('daily', editionIndex); }
export function startRevealPractice(mode, editionIndex) { MODE = mode; startEdition('practice', editionIndex); }

function showLockedResult(editionIndex, entry) {
  S = {
    mode: 'daily', dailyKey: daily.dailyKey(MODE, editionIndex), store: modeStore('daily', null),
    editionIndex, done: true, locked: true,
    score: entry.score,
    results: (entry.detail || []).map((r) => ({
      item: byId(r.id) || { name: '(removed)', kind: MODE === 'who' ? 'portrait' : 'artefact' },
      pts: r.pts, correct: r.correct, torn: r.torn || 0, wrongs: r.wrongs || 0,
    })),
  };
  renderLockedSummary();
  show('view-revealsum');
}

function round() { return S.rounds[S.i]; }

function startRound() {
  const item = round();
  S.cur = { open: true, torn: [], wrongs: 0, clueCost: 0, clueA: false, clueB: false };
  $('#rv-progress').textContent = `Round ${S.i + 1} of ${S.rounds.length}`;
  $('#rv-score').textContent = `${S.score} pts`;
  $('#rv-prompt').hidden = false;
  $('#rv-prompt').textContent = item.kind === 'portrait'
    ? 'Who is this? Tear towards the answer.' : 'What is this? Tear towards the answer.';
  $('#rv-feedback').hidden = true;
  $('#rv-feedback').innerHTML = '';
  $('#rv-form').hidden = false;
  $('#rv-controls').hidden = false;
  $('#rv-guesses').innerHTML = '';
  $('#rv-input').value = '';
  $('#rv-input').disabled = false;
  $('#rv-guess-btn').disabled = false;
  $('#rv-next').hidden = true;
  $('#rv-badge').hidden = true;
  $('#rv-streak').hidden = S.streak < 2;
  if (S.streak >= 2) $('#rv-streak').textContent = `${S.streak} in a row`;
  setupClues();
  // Back to the square scrap window (clears any inline aspect/width the last
  // reveal morphed the frame to).
  const frame = $('#rv-frame');
  frame.style.aspectRatio = '1 / 1';
  frame.style.width = '';
  if (frameZoom) frameZoom.reset();
  paintCover(item);
  buildScraps();
  tearScrap(startScrap(item), true);   // the free opening scrap, placed far from the money shot
  updateWorth();
  setRoundOffline(false);
  ensureDims(item, () => {
    // Only flag the round still on screen (the load is async).
    if (!S || !S.cur || !S.cur.open || round() !== item) return;
    const d = dims[item.img];
    if (d && d.failed) setRoundOffline(true);
  });
  prefetchRounds();
  persist();
  window.__CHRONICLE_TEST__ = Object.assign(window.__CHRONICLE_TEST__ || {}, {
    revealRound: { index: S.i, id: item.id, name: item.name, kind: item.kind },
    revealDebug: {
      tear: tearScrap,
      tornCount: () => (S && S.cur ? S.cur.torn.length : 0),
      worth: worthNow,
      // Back-compat shim for the old timed harness: progress p ≈ tearing
      // through the grid. p=0 → no tears, p=1 → all nine scraps torn.
      setProgress: (p) => { for (let k = 0; k < Math.round(p * SCRAPS); k++) tearScrap(k); },
      getP: () => (S && S.cur ? S.cur.torn.length / SCRAPS : null),
    },
  });
}

function resolveRound(correct) {
  const item = round();
  if (!S.cur.open) return;
  S.cur.open = false;
  const wrongs = S.cur.wrongs || 0;
  let pts = 0;
  let bonus = 0;
  if (correct) {
    pts = worthNow();
    S.streak++;
    S.bestStreak = Math.max(S.bestStreak, S.streak);
    if (S.streak >= 2) bonus = 10;
    sfx.play('correct');
  } else {
    S.streak = 0;
  }
  const total = pts + bonus;
  S.score += total;
  S.results.push({ item, pts: total, correct, torn: S.cur.torn.length, wrongs });
  persist();

  // The reveal: every scrap flies off, the full image shows with the house
  // duotone treatment, and the verdict badge lands on the frame's corner.
  $('#rv-scraps').querySelectorAll('.df-scrap').forEach((el) => el.classList.add('torn'));
  $('#rv-prompt').hidden = true;
  if (frameZoom) frameZoom.reset();   // the frame morphs aspect; start the reveal at 1x
  paintFull(item);
  $('#rv-frame').classList.add('df-duotone');
  const badge = $('#rv-badge');
  badge.className = `df-moment-badge${correct ? '' : ' bad'}`;
  badge.innerHTML = correct
    ? `<b>Correct!</b><small>+${total} PTS</small>`
    : `<b>Not this time</b><small>0 PTS</small>`;
  badge.hidden = false;
  $('#rv-worth').innerHTML = '';

  const credit = item.license && item.license !== 'Public domain'
    ? ` <small class="rv-credit">${item.license}</small>` : '';
  const fb = $('#rv-feedback');
  fb.className = correct ? 'good' : 'info';
  fb.innerHTML = (correct
    ? `<b class="fig">${item.name}</b> — ${item.blurb}. <span class="pts">+${total} pts</span>`
      + (bonus ? ` <small>(includes ${bonus} streak bonus)</small>` : '')
    : `It was <b class="fig">${item.name}</b> — ${item.blurb}. <span class="pts">0 pts</span>`)
    + credit;
  fb.hidden = false;

  $('#rv-input').disabled = true;
  $('#rv-guess-btn').disabled = true;
  $('#rv-clue-a').disabled = true;
  $('#rv-clue-b').disabled = true;
  $('#rv-form').hidden = true;
  $('#rv-controls').hidden = true;
  $('#rv-score').textContent = `${S.score} pts`;
  $('#rv-streak').hidden = S.streak < 2;
  if (S.streak >= 2) $('#rv-streak').textContent = `${S.streak} in a row`;
  const last = S.i === S.rounds.length - 1;
  $('#rv-next').textContent = last ? 'See results ›' : 'Next ›';
  $('#rv-next').hidden = false;
  $('#rv-next').scrollIntoView({ block: 'nearest' });
}

function renderLockedSummary() {
  const head = document.querySelector('#view-revealsum [data-receipt-head]');
  if (head) head.textContent = `Dead Famous · ${MODE === 'who' ? 'Face Value' : 'Relic'}`
    + (S.editionIndex != null ? ` · Issue № ${S.editionIndex}` : '');
  $('#rv-sum-total').textContent = S.score;
  setReceiptStamp('view-revealsum', S.score);
  const remarks = [
    [850, 'A connoisseur of the ages.'],
    [650, 'A sharp eye for history.'],
    [450, 'A good eye — keep looking.'],
    [250, 'The details are coming into focus.'],
    [0, 'Every expert starts by squinting.'],
  ];
  $('#rv-sum-remark').textContent = remarks.find((x) => S.score >= x[0])[1];
  const ol = $('#rv-sum-rounds');
  ol.innerHTML = '';
  for (const r2 of S.results) {
    const li = document.createElement('li');
    li.innerHTML = `<span class="sum-name">${r2.item.name}<small>${r2.item.kind}</small></span>`
      + `<span class="sum-pts${r2.pts ? '' : ' zero'}">${r2.pts ? '+' + r2.pts : '0'}</span>`;
    ol.appendChild(li);
  }
  // Daily results are locked: no replay from the summary screen.
  // Share 2.0: dailies only (the issue number is the common reference).
  const isDaily = S.mode === 'daily' && S.editionIndex != null;
  S.share = isDaily ? {
    text: revealShareText(MODE, S.editionIndex, S.results, S.score),
    card: {
      game: MODE === 'who' ? 'FACE VALUE' : 'RELIC',
      glyph: MODE === 'who' ? '🖼️' : '🏺',
      score: S.score, sub: `ISSUE № ${S.editionIndex}`,
      rows: [revealEmojiRow(S.results.slice(0, 5)), revealEmojiRow(S.results.slice(5))].filter(Boolean),
    },
    trackAs: `share-${MODE}`,
  } : null;
  const rvShare = $('#rv-sum-share');
  if (rvShare) rvShare.hidden = !S.share;
  wireTurnThePage('rv-sum-turn', S.editionIndex, isDaily);
  $('#rv-sum-again').hidden = !!S.locked;
}

function finishSession() {
  if (S.done) { renderLockedSummary(); show('view-revealsum'); return; }
  S.done = true;
  S.store.clear();
  sfx.play('stamp');

  if (S.mode === 'free') {
    const r = store.getReveal(MODE);
    r.sessions = (r.sessions || 0) + 1;
    r.bestScore = Math.max(r.bestScore || 0, S.score);
    r.bestStreak = Math.max(r.bestStreak || 0, S.bestStreak);
    store.setReveal(MODE, r);
  } else if (S.mode === 'daily') {
    daily.recordDailyCompletion(MODE, S.editionIndex, {
      score: S.score,
      // torn/wrongs feed the Share 2.0 emoji row (🟩 clean, 🟨 laboured, 🟥 lost)
      detail: S.results.map((r3) => ({ id: r3.item.id, pts: r3.pts, correct: r3.correct, torn: r3.torn, wrongs: r3.wrongs })),
    });
    S.locked = true;
  }
  // practice mode: no ledger, no best-score update — replayable, no trace.
  refreshHomeStats();

  renderLockedSummary();
  window.__CHRONICLE_TEST__ = Object.assign(window.__CHRONICLE_TEST__ || {}, {
    revealSession: { score: S.score, results: S.results.map((r3) => ({ id: r3.item.id, pts: r3.pts, correct: r3.correct })) },
  });
  show('view-revealsum');
}

// ---------- init ----------
export function initRevealGame() {
  // Two separate pools — 'who' (portraits) / 'what' (artefacts) — so a
  // distinctive core token is only unique relative to items the player could
  // actually be shown in that mode, not the whole reveal corpus.
  registerPool('who', DATA.reveal.filter((x) => x.kind === 'portrait'));
  registerPool('what', DATA.reveal.filter((x) => x.kind !== 'portrait'));

  // Pinch/double-tap zoom on the frame: revealed slivers are inspectable
  // mid-round (image and scrap grid scale together, so the torn windows stay
  // truthful) and the final reveal is zoomable too. The wrap clips while
  // zoomed so the scaled frame never rides over the guess form.
  frameZoom = attachPinchZoom($('#rv-frame'), {
    maxScale: 4,
    onZoomChange: (z) => $('#rv-frame-wrap').classList.toggle('pz-active', z > 1),
  });

  $('#rv-start').addEventListener('click', startSession);
  $('#rv-resume').addEventListener('click', resumeSession);
  $('#rv-help').addEventListener('click', () => openIntroHelp(MODE));

  $('#rv-form').addEventListener('submit', (e) => {
    e.preventDefault();
    if (!S || !S.cur || !S.cur.open) return;
    const guess = $('#rv-input').value.trim();
    if (!guess) return;
    if (isMatch(guess, round(), MODE)) {
      resolveRound(true);
    } else {
      // A wrong guess docks the round's worth (see worthNow) — guessing blind
      // is a real gamble, not a free spin.
      S.cur.wrongs = (S.cur.wrongs || 0) + 1;
      const chip = document.createElement('span');
      chip.className = 'guess-chip';
      const guessText = document.createElement('span');
      guessText.textContent = guess;
      chip.appendChild(guessText);
      const penalty = document.createElement('small');
      penalty.textContent = `-${WRONG_PENALTY}`;
      chip.appendChild(penalty);
      $('#rv-guesses').appendChild(chip);
      updateWorth();
      const inp = $('#rv-input');
      inp.value = '';
      inp.classList.remove('shake');
      void inp.offsetWidth;
      inp.classList.add('shake');
      inp.focus();
    }
  });

  $('#rv-clue-a').addEventListener('click', () => buyClue('a'));
  $('#rv-clue-b').addEventListener('click', () => buyClue('b'));

  $('#rv-offline-retry').addEventListener('click', () => {
    if (!S || !S.cur || !S.cur.open) return;
    const item = round();
    const btn = $('#rv-offline-retry');
    btn.disabled = true;
    delete dims[item.img];
    ensureDims(item, () => {
      btn.disabled = false;
      if (!S || !S.cur || !S.cur.open || round() !== item) return;
      const d = dims[item.img];
      if (d && !d.failed) {
        paintCover(item);
        setRoundOffline(false);
      } else {
        btn.textContent = 'Still offline — retry';
      }
    });
  });

  $('#rv-reveal').addEventListener('click', () => {
    if (!S || !S.cur || !S.cur.open) return;
    resolveRound(false);
  });

  $('#rv-next').addEventListener('click', () => {
    if (S.i === S.rounds.length - 1) { finishSession(); return; }
    S.i++;
    startRound();
  });

  $('#rv-quit').addEventListener('click', () => {
    // Header back arrow: leave the session, same as every other game's back
    // button — it must not discard progress. persist() already runs at the
    // start of every round (so completed rounds + score are captured); make
    // sure that's saved, then go. Reopening resumes at this round (fresh
    // scraps — same convention as any mid-round refresh, see resumeFrom).
    if (S && !S.done) persist();
    S = null;
    back();
  });

  const rvShareBtn = $('#rv-sum-share');
  if (rvShareBtn) {
    rvShareBtn.addEventListener('click', async () => {
      if (!S || !S.share) return;
      const out = await shareResult(S.share);
      flashShareButton(rvShareBtn, out, 'Share the tear-up');
    });
  }
  $('#rv-sum-back').addEventListener('click', goHome);
  $('#rv-sum-again').addEventListener('click', () => { back(); startSession(); });
  $('#rv-sum-home').addEventListener('click', goHome);
}
