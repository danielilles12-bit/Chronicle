// "Zoom In" — guess the famous artefact or portrait from a cropped fragment
// that widens with every wrong guess. Mirrors the Map of a Life session shape
// (10 rounds, persisted, resumable) so the two games behave consistently.
import { DATA, $, show, back, goHome, appConfirm, refreshHomeStats } from './app.js';
import * as store from './storage.js';
import { isMatch } from './match.js';

const MAXSTAGE = 4;            // 0 = tightest crop … 4 = almost the whole image
const ROUNDS = 10;

let S = null;

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

// ---------- image cropping ----------
const dims = {};               // img path -> {w,h}, cached after first load

function fracAt(item, stage) {
  return item.frac + (0.85 - item.frac) * (stage / MAXSTAGE);
}

function paintCrop(item, stage) {
  const frame = $('#rv-frame');
  const wh = dims[item.img];
  frame.style.backgroundImage = `url("${item.img}")`;
  frame.style.backgroundColor = '#111';
  if (!wh) return;                                  // re-painted on load
  const { w: W, h: H } = wh;
  const side = fracAt(item, stage) * Math.min(W, H);
  const D = frame.getBoundingClientRect().width || 320;
  const scale = D / side;
  const cx = Math.max(side / 2, Math.min(W - side / 2, item.fx * W));
  const cy = Math.max(side / 2, Math.min(H - side / 2, item.fy * H));
  frame.style.backgroundSize = `${(W * scale).toFixed(1)}px ${(H * scale).toFixed(1)}px`;
  frame.style.backgroundPosition =
    `${(-(cx * scale - D / 2)).toFixed(1)}px ${(-(cy * scale - D / 2)).toFixed(1)}px`;
}

function paintFull(item) {
  const frame = $('#rv-frame');
  frame.style.backgroundImage = `url("${item.img}")`;
  frame.style.backgroundSize = 'contain';
  frame.style.backgroundPosition = 'center';
}

function showCrop(item, stage) {
  if (dims[item.img]) { paintCrop(item, stage); return; }
  const img = new Image();
  img.onload = () => {
    dims[item.img] = { w: img.naturalWidth, h: img.naturalHeight };
    if (S && S.cur && S.cur.open && round() === item) paintCrop(item, stage);
  };
  img.src = item.img;
  paintCrop(item, stage);       // sets bg now; positions once dims are known
}

// ---------- session ----------
export function renderRevealStart() {
  const r = store.getReveal();
  $('#rv-best').textContent = r.sessions
    ? `Your best: ${r.bestScore} pts · longest streak ${r.bestStreak}`
    : 'First session — good luck';
  const saved = store.getRevealSession();
  const valid = saved && saved.ids && saved.results;
  $('#rv-resume').hidden = !valid;
  if (valid) {
    $('#rv-resume').textContent = saved.results.length >= saved.ids.length
      ? `See your results (${saved.score} pts)`
      : `Resume — round ${saved.results.length + 1} of ${saved.ids.length} (${saved.score} pts)`;
  }
}

function byId(id) { return DATA.reveal.find((x) => x.id === id); }

function persist() {
  store.setRevealSession({
    ids: S.rounds.map((x) => x.id),
    score: S.score, streak: S.streak, bestStreak: S.bestStreak,
    cur: S.cur && S.cur.open ? { stage: S.cur.stage } : null,
    results: S.results.map((r) => ({ id: r.item.id, pts: r.pts, correct: r.correct, stage: r.stage })),
  });
}

function pickRounds(rng) {
  const items = DATA.reveal;
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
  const saved = store.getRevealSession();
  if (saved && saved.ids && saved.results && saved.results.length >= saved.ids.length) {
    resumeSession();             // a finished-but-unviewed session: bank it first
    return;
  }
  const rng = makeRng();
  S = { rounds: pickRounds(rng), i: 0, score: 0, streak: 0, bestStreak: 0, results: [] };
  show('view-reveal');
  startRound();
}

function resumeSession() {
  const saved = store.getRevealSession();
  if (!saved || !saved.ids || !saved.results) return;
  if (saved.ids.some((id) => !byId(id)) || saved.results.some((r) => !byId(r.id))) {
    store.clearRevealSession();
    renderRevealStart();
    return;
  }
  const next = saved.results.length;
  S = {
    rounds: saved.ids.map(byId),
    i: Math.min(next, saved.ids.length - 1),
    score: saved.score, streak: saved.streak, bestStreak: saved.bestStreak,
    results: saved.results.map((r) => ({ item: byId(r.id), pts: r.pts, correct: r.correct, stage: r.stage })),
    pendingCur: saved.cur || null,
  };
  if (next >= saved.ids.length) { finishSession(); return; }
  show('view-reveal');
  startRound();
}

function round() { return S.rounds[S.i]; }

function startRound() {
  const item = round();
  const carried = S.pendingCur;
  S.pendingCur = null;
  S.cur = { stage: carried ? carried.stage : 0, open: true };
  $('#rv-progress').textContent = `Round ${S.i + 1} of ${S.rounds.length}`;
  $('#rv-score').textContent = `${S.score} pts`;
  $('#rv-prompt').textContent = item.kind === 'portrait' ? 'Who is this?' : 'What is this?';
  $('#rv-feedback').hidden = true;
  $('#rv-feedback').innerHTML = '';
  $('#rv-form').hidden = false;
  $('#rv-controls').hidden = false;
  $('#rv-guesses').innerHTML = '';
  $('#rv-input').value = '';
  $('#rv-input').disabled = false;
  $('#rv-guess-btn').disabled = false;
  $('#rv-next').hidden = true;
  $('#rv-streak').hidden = S.streak < 2;
  if (S.streak >= 2) $('#rv-streak').textContent = `${S.streak} in a row`;
  updateMoreButton();
  showCrop(item, S.cur.stage);
  persist();
  window.__CHRONICLE_TEST__ = Object.assign(window.__CHRONICLE_TEST__ || {}, {
    revealRound: { index: S.i, id: item.id, name: item.name, kind: item.kind },
  });
}

function updateMoreButton() {
  const atFull = S.cur.stage >= MAXSTAGE;
  $('#rv-more').disabled = atFull;
  $('#rv-more').textContent = atFull ? 'Fully revealed' : 'Show more';
}

function advance() {
  if (S.cur.stage < MAXSTAGE) S.cur.stage++;
  paintCrop(round(), S.cur.stage);
  updateMoreButton();
  persist();
}

function resolveRound(correct) {
  const item = round();
  S.cur.open = false;
  let pts = 0;
  let bonus = 0;
  if (correct) {
    pts = Math.max(20, 100 - 20 * S.cur.stage);
    S.streak++;
    S.bestStreak = Math.max(S.bestStreak, S.streak);
    if (S.streak >= 2) bonus = 10;
  } else {
    S.streak = 0;
  }
  const total = pts + bonus;
  S.score += total;
  S.results.push({ item, pts: total, correct, stage: S.cur.stage });
  persist();

  paintFull(item);
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

function finishSession() {
  if (S.done) { show('view-revealsum'); return; }
  S.done = true;
  store.clearRevealSession();
  const r = store.getReveal();
  r.sessions = (r.sessions || 0) + 1;
  r.bestScore = Math.max(r.bestScore || 0, S.score);
  r.bestStreak = Math.max(r.bestStreak || 0, S.bestStreak);
  store.setReveal(r);
  refreshHomeStats();

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
  window.__CHRONICLE_TEST__ = Object.assign(window.__CHRONICLE_TEST__ || {}, {
    revealSession: { score: S.score, results: S.results.map((r3) => ({ id: r3.item.id, pts: r3.pts, correct: r3.correct })) },
  });
  show('view-revealsum');
}

// ---------- init ----------
export function initRevealGame() {
  $('#rv-start').addEventListener('click', startSession);
  $('#rv-resume').addEventListener('click', resumeSession);

  $('#rv-form').addEventListener('submit', (e) => {
    e.preventDefault();
    if (!S || !S.cur.open) return;
    const guess = $('#rv-input').value.trim();
    if (!guess) return;
    if (isMatch(guess, round())) {
      resolveRound(true);
    } else {
      const chip = document.createElement('span');
      chip.className = 'guess-chip';
      chip.textContent = guess;
      $('#rv-guesses').appendChild(chip);
      const inp = $('#rv-input');
      inp.value = '';
      inp.classList.remove('shake');
      void inp.offsetWidth;
      inp.classList.add('shake');
      inp.focus();
      advance();          // a wrong guess widens the frame (the penalty)
    }
  });

  $('#rv-more').addEventListener('click', () => {
    if (!S || !S.cur.open || S.cur.stage >= MAXSTAGE) return;
    advance();
  });

  $('#rv-reveal').addEventListener('click', () => {
    if (!S || !S.cur.open) return;
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
        .then((ok) => { if (ok) { store.clearRevealSession(); renderRevealStart(); back(); } });
    } else {
      back();
    }
  });

  $('#rv-sum-back').addEventListener('click', goHome);
  $('#rv-sum-again').addEventListener('click', () => { back(); startSession(); });
  $('#rv-sum-home').addEventListener('click', goHome);
}
