// Chrono — put five historical events in the correct chronological order
import { DATA, $, show, back, goHome, refreshHomeStats } from './app.js';
import * as store from './storage.js';

const ROUNDS = 5;
const ORDINALS = ['1st', '2nd', '3rd', '4th', '5th'];
let S = null;

// ---------- rng ----------
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function shuffled(arr, rng) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// ---------- start screen ----------
export function renderChronoStart() {
  const s = store.getChrono();
  $('#ch-best').textContent = s.sessions
    ? `Your best: ${s.bestScore} pts`
    : `${DATA.chrono.length} puzzles to sort`;
  const saved = store.getChronoSession();
  const valid = saved && saved.ids && saved.results;
  $('#ch-resume').hidden = !valid;
  if (valid) {
    $('#ch-resume').textContent = saved.results.length >= saved.ids.length
      ? `See your results (${saved.score} pts)`
      : `Resume — round ${saved.results.length + 1} of ${saved.ids.length} (${saved.score} pts)`;
  }
}

// ---------- round selection ----------
function pickRounds(rng) {
  const all = DATA.chrono;
  const by = (d) => shuffled(all.filter((x) => x.difficulty === d), rng);
  const easy = by('easy').slice(0, 2);
  const medium = by('medium').slice(0, 2);
  const hard = by('hard').slice(0, 1);
  const picks = shuffled([...easy, ...medium, ...hard], rng).slice(0, ROUNDS);
  // pad if not enough variety
  if (picks.length < ROUNDS) {
    const used = new Set(picks.map((p) => p.id));
    const rest = shuffled(all.filter((p) => !used.has(p.id)), rng);
    while (picks.length < ROUNDS && rest.length) picks.push(rest.shift());
  }
  return picks;
}

// ---------- scoring ----------
function sortedIndices(puzzle) {
  return puzzle.items
    .map((item, i) => ({ i, year: item.year }))
    .sort((a, b) => a.year - b.year)
    .map((x) => x.i);
}

function countCorrect(order, puzzle) {
  const correct = sortedIndices(puzzle);
  return order.filter((idx, pos) => idx === correct[pos]).length;
}

function ptsForCorrect(c) {
  return [0, 10, 25, 50, 75, 100][c] || 0;
}

// ---------- persist ----------
function persist() {
  store.setChronoSession({
    ids: S.rounds.map((r) => r.id),
    score: S.score,
    results: S.results.map((r) => ({ id: r.puzzle.id, pts: r.pts, correct: r.correct })),
  });
}

// ---------- render round ----------
function renderRound() {
  const puzzle = S.rounds[S.i];
  const rng = mulberry32((Date.now() & 0xffffffff) ^ S.i);
  // S.order[pos] = item index from puzzle.items currently in that position
  S.order = shuffled([0, 1, 2, 3, 4], rng);
  S.selected = null;

  $('#ch-progress').textContent = `Round ${S.i + 1} of ${ROUNDS}`;
  $('#ch-score').textContent = `${S.score} pts`;
  $('#ch-puzzle-title').textContent = puzzle.title;

  const list = $('#ch-list');
  list.innerHTML = '';
  list.className = 'ch-list';
  rebuildList(puzzle, list);

  $('#ch-result').hidden = true;
  $('#ch-result').innerHTML = '';
  $('#ch-submit').hidden = false;
  $('#ch-next').hidden = true;

  show('view-chrono');
}

function rebuildList(puzzle, list) {
  list = list || $('#ch-list');
  list.innerHTML = '';
  S.order.forEach((itemIdx, pos) => {
    const item = puzzle.items[itemIdx];
    const div = document.createElement('div');
    div.className = 'ch-item' + (S.selected === pos ? ' ch-selected' : '');
    div.dataset.pos = pos;
    div.innerHTML =
      `<span class="ch-pos-label">${ORDINALS[pos]}</span>` +
      `<span class="ch-label">${item.label}</span>`;
    div.addEventListener('click', () => onTapItem(pos));
    list.appendChild(div);
  });
}

function onTapItem(pos) {
  if ($('#ch-submit').hidden) return; // round already resolved
  if (S.selected === null) {
    S.selected = pos;
  } else if (S.selected === pos) {
    S.selected = null;
  } else {
    // swap
    const a = S.selected, b = pos;
    [S.order[a], S.order[b]] = [S.order[b], S.order[a]];
    S.selected = null;
  }
  rebuildList(S.rounds[S.i]);
}

// ---------- submit ----------
function submitRound() {
  const puzzle = S.rounds[S.i];
  const correct = countCorrect(S.order, puzzle);
  const pts = ptsForCorrect(correct);
  S.score += pts;
  S.results.push({ puzzle, order: S.order.slice(), correct, pts });
  persist();

  // rebuild list with result classes and year badges
  const list = $('#ch-list');
  list.innerHTML = '';
  const correctOrder = sortedIndices(puzzle);
  S.order.forEach((itemIdx, pos) => {
    const item = puzzle.items[itemIdx];
    const isCorrect = itemIdx === correctOrder[pos];
    const div = document.createElement('div');
    div.className = 'ch-item ch-result-item' + (isCorrect ? ' ch-correct' : ' ch-wrong');
    div.innerHTML =
      `<span class="ch-pos-label">${ORDINALS[pos]}</span>` +
      `<span class="ch-label">${item.label}</span>` +
      `<span class="ch-year">${item.year < 0 ? Math.abs(item.year) + ' BC' : item.year}</span>` +
      `<span class="ch-check">${isCorrect ? '✓' : '✗'}</span>`;
    list.appendChild(div);
  });

  // show how many correct + pts earned
  const result = $('#ch-result');
  result.hidden = false;
  const perfect = correct === 5;
  result.className = 'ch-result' + (perfect ? ' ch-perfect' : correct >= 3 ? ' ch-good' : '');
  result.innerHTML = perfect
    ? `<b>Perfect!</b> All five in order · <span class="ch-pts">+${pts} pts</span>`
    : `<b>${correct} of 5 correct</b> · <span class="ch-pts">+${pts} pts</span>`;

  $('#ch-score').textContent = `${S.score} pts`;
  $('#ch-submit').hidden = true;
  const last = S.i === ROUNDS - 1;
  $('#ch-next').textContent = last ? 'See results ›' : 'Next ›';
  $('#ch-next').hidden = false;
}

// ---------- session ----------
function startSession() {
  const rng = mulberry32((Date.now() & 0xffffffff) ^ 0xabcd1234);
  S = { rounds: pickRounds(rng), i: 0, score: 0, results: [] };
  persist();
  renderRound();
}

function resumeSession() {
  const saved = store.getChronoSession();
  if (!saved || !saved.ids) return;
  const byId = (id) => DATA.chrono.find((x) => x.id === id);
  if (saved.ids.some((id) => !byId(id))) { store.clearChronoSession(); renderChronoStart(); return; }
  if (saved.results.length >= saved.ids.length) {
    finishSession(saved.score, saved.results.map((r) => ({ puzzle: byId(r.id), pts: r.pts, correct: r.correct })));
    return;
  }
  S = {
    rounds: saved.ids.map(byId),
    i: saved.results.length,
    score: saved.score,
    results: saved.results.map((r) => ({ puzzle: byId(r.id), pts: r.pts, correct: r.correct })),
  };
  renderRound();
}

function finishSession(score, results) {
  score = score != null ? score : S.score;
  results = results || S.results;
  store.clearChronoSession();
  const stats = store.getChrono();
  stats.sessions = (stats.sessions || 0) + 1;
  stats.bestScore = Math.max(stats.bestScore || 0, score);
  store.setChrono(stats);
  refreshHomeStats();

  $('#ch-sum-total').textContent = score;
  const remarks = [
    [450, 'A master of the timeline.'],
    [350, 'History flows through you.'],
    [250, 'A solid grasp of the ages.'],
    [150, 'The timeline is coming into focus.'],
    [0, 'History is a work in progress.'],
  ];
  $('#ch-sum-remark').textContent = remarks.find((x) => score >= x[0])[1];

  const ol = $('#ch-sum-rounds');
  ol.innerHTML = '';
  results.forEach((r) => {
    const li = document.createElement('li');
    li.innerHTML =
      `<span class="sum-name">${r.puzzle.title}<small>${r.correct}/5 correct</small></span>` +
      `<span class="sum-pts${r.pts ? '' : ' zero'}">${r.pts ? '+' + r.pts : '0'}</span>`;
    ol.appendChild(li);
  });
  show('view-chronosum');
}

// ---------- init ----------
export function initChronoGame() {
  $('#ch-start').addEventListener('click', startSession);
  $('#ch-resume').addEventListener('click', resumeSession);

  $('#ch-submit').addEventListener('click', submitRound);

  $('#ch-next').addEventListener('click', () => {
    if (S.i === ROUNDS - 1) { finishSession(); return; }
    S.i++;
    renderRound();
  });

  $('#ch-quit').addEventListener('click', () => {
    store.clearChronoSession();
    renderChronoStart();
    back();
  });

  $('#ch-sum-back').addEventListener('click', goHome);
  $('#ch-sum-again').addEventListener('click', () => { back(); startSession(); });
  $('#ch-sum-home').addEventListener('click', goHome);
}
