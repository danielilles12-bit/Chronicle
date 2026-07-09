// "Face Value" / "Relic" — guess the famous face or artefact hidden under a
// 3x3 grid of paper scraps. Tearing scraps off is the player's choice and the
// player's cost: the first tear is free, each further tear docks the round's
// worth, and wrong guesses dock more. No clock — curiosity is the only spender.
// Mirrors the Map of a Life session shape (10 rounds, persisted, resumable).
import { DATA, $, show, back, goHome, appConfirm, refreshHomeStats } from './app.js';
import * as store from './storage.js';
import { isMatch, registerPool } from './match.js';
import * as daily from './daily.js';

const ROUNDS = 10;
const SCRAPS = 9;               // 3x3 cover grid
const TEAR_COST = 10;           // per scrap after the first (first tear is free)
const WRONG_PENALTY = 15;       // per wrong guess
const WORTH_START = 100;
const WORTH_FLOOR = 10;         // a correct answer never pays less than this

let S = null;
let MODE = 'who';               // 'who' = portraits, 'what' = artefacts

function pool() {
  return DATA.reveal.filter((x) => (MODE === 'who' ? x.kind === 'portrait' : x.kind !== 'portrait'));
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

function paintFull(item) {
  const frame = $('#rv-frame');
  frame.style.backgroundImage = `url("${item.img}")`;
  frame.style.backgroundSize = 'contain';
  frame.style.backgroundPosition = 'center';
  frame.style.backgroundRepeat = 'no-repeat';
}

function ensureDims(item, cb) {
  if (dims[item.img]) { cb(); return; }
  const img = new Image();
  img.onload = () => { dims[item.img] = { w: img.naturalWidth, h: img.naturalHeight }; cb(); };
  img.onerror = () => { dims[item.img] = { w: 1000, h: 1000 }; cb(); };
  img.src = item.img;
}

// ---------- scraps ----------
function worthNow() {
  const cur = S && S.cur;
  if (!cur) return WORTH_START;
  const paidTears = Math.max(0, cur.torn.length - 1);   // first tear is free
  return Math.max(WORTH_FLOOR, WORTH_START - TEAR_COST * paidTears - WRONG_PENALTY * cur.wrongs);
}

function updateWorth() {
  const el = $('#rv-worth');
  if (!el || !S || !S.cur) return;
  const label = MODE === 'what' ? 'INK' : 'WORTH';
  const torn = S.cur.torn.length;
  const hint = torn === 0 ? ' · first tear free' : '';
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

function tearScrap(i) {
  if (!S || !S.cur || !S.cur.open) return;
  const cur = S.cur;
  if (cur.torn.includes(i)) return;
  cur.torn.push(i);
  const el = $(`#rv-scraps [data-i="${i}"]`);
  if (el) el.classList.add('torn');
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
  const rounds = daily.getEdition(MODE, editionIndex);
  S = {
    mode: sessMode, dailyKey: key, store: modeStore(sessMode, key), editionIndex,
    rounds, i: 0, score: 0, streak: 0, bestStreak: 0, results: [],
  };
  show('view-reveal');
  startRound();
}

export function startRevealDaily(mode, editionIndex) { MODE = mode; startEdition('daily', editionIndex); }
export function startRevealPractice(mode, editionIndex) { MODE = mode; startEdition('practice', editionIndex); }

function showLockedResult(editionIndex, entry) {
  S = {
    mode: 'daily', dailyKey: daily.dailyKey(MODE, editionIndex), store: modeStore('daily', null),
    editionIndex, done: true, locked: true,
    score: entry.score,
    results: (entry.detail || []).map((r) => ({
      item: byId(r.id) || { name: '(removed)', kind: MODE === 'who' ? 'portrait' : 'artefact' }, pts: r.pts, correct: r.correct,
    })),
  };
  renderLockedSummary();
  show('view-revealsum');
}

function round() { return S.rounds[S.i]; }

function startRound() {
  const item = round();
  S.cur = { open: true, torn: [], wrongs: 0 };
  $('#rv-progress').textContent = `Round ${S.i + 1} of ${S.rounds.length}`;
  $('#rv-score').textContent = `${S.score} pts`;
  $('#rv-prompt').textContent = item.kind === 'portrait'
    ? 'Who is this? Tear a scrap to peek.' : 'What is this? Tear a scrap to peek.';
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
  paintCover(item);
  buildScraps();
  updateWorth();
  ensureDims(item, () => {});
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
  $('#rv-sum-again').hidden = !!S.locked;
}

function finishSession() {
  if (S.done) { renderLockedSummary(); show('view-revealsum'); return; }
  S.done = true;
  S.store.clear();

  if (S.mode === 'free') {
    const r = store.getReveal(MODE);
    r.sessions = (r.sessions || 0) + 1;
    r.bestScore = Math.max(r.bestScore || 0, S.score);
    r.bestStreak = Math.max(r.bestStreak || 0, S.bestStreak);
    store.setReveal(MODE, r);
  } else if (S.mode === 'daily') {
    daily.recordDailyCompletion(MODE, S.editionIndex, {
      score: S.score,
      detail: S.results.map((r3) => ({ id: r3.item.id, pts: r3.pts, correct: r3.correct })),
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
  $('#rv-start').addEventListener('click', startSession);
  $('#rv-resume').addEventListener('click', resumeSession);

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
    if (S && !S.done) {
      appConfirm('Quit this session? The score so far will be lost.', 'Quit session')
        .then((ok) => {
          if (ok) {
            S.store.clear();
            if (S.mode === 'free') renderRevealStart();
            back();
          }
        });
    } else {
      back();
    }
  });

  $('#rv-sum-back').addEventListener('click', goHome);
  $('#rv-sum-again').addEventListener('click', () => { back(); startSession(); });
  $('#rv-sum-home').addEventListener('click', goHome);
}
