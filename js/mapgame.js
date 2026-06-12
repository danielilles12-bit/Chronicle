// "Map of a Life": guess the historical figure from birth/death geography.
import { DATA, $, show, back, goHome, refreshHomeStats, appConfirm } from './app.js';
import * as store from './storage.js';
import { isMatch } from './match.js';

const MAP_W = 1000, MAP_H = 500;
let S = null;            // current session
let vb = [0, 0, MAP_W, MAP_H];   // current viewBox
let animId = null;

// ---------- seeded rng (deterministic sessions for tests via ?mapseed=N) ----------
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function makeRng() {
  const m = location.search.match(/[?&]mapseed=(\d+)/);
  return m ? mulberry32(+m[1]) : Math.random;
}

function shuffled(arr, rng) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// ---------- projection & viewBox ----------
function proj(lon, lat) {
  return [(lon + 180) / 360 * MAP_W, (90 - lat) / 180 * MAP_H];
}

function setVb(box) {
  vb = box;
  $('#map-svg').setAttribute('viewBox', box.map((v) => v.toFixed(2)).join(' '));
  scaleMarkers(box);
}

function targetBox(p1, p2) {
  const panel = $('#map-svg').getBoundingClientRect();
  const aspect = panel.width && panel.height ? panel.width / panel.height : 2;
  let x0 = Math.min(p1[0], p2[0]), x1 = Math.max(p1[0], p2[0]);
  let y0 = Math.min(p1[1], p2[1]), y1 = Math.max(p1[1], p2[1]);
  let w = Math.max((x1 - x0) * 1.9, 170);
  let h = Math.max((y1 - y0) * 1.9, 85);
  if (w / h > aspect) h = w / aspect; else w = h * aspect;
  if (w > MAP_W) { w = MAP_W; h = w / aspect; }
  if (h > MAP_H) { h = MAP_H; w = Math.min(MAP_W, h * aspect); }
  let cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  cx = Math.min(Math.max(cx, w / 2), MAP_W - w / 2);
  cy = Math.min(Math.max(cy, h / 2), MAP_H - h / 2);
  return [cx - w / 2, cy - h / 2, w, h];
}

function animateTo(box) {
  if (animId) cancelAnimationFrame(animId);
  const from = vb.slice();
  const t0 = performance.now();
  const dur = 850;
  const ease = (t) => 1 - Math.pow(1 - t, 3);
  function frame(now) {
    const t = Math.min(1, (now - t0) / dur);
    const k = ease(t);
    setVb(from.map((v, i) => v + (box[i] - v) * k));
    if (t < 1) animId = requestAnimationFrame(frame);
  }
  animId = requestAnimationFrame(frame);
}

// ---------- map rendering ----------
function renderWorld() {
  const svg = $('#map-svg');
  svg.setAttribute('viewBox', '0 0 1000 500');
  svg.innerHTML = `<rect x="-40" y="-40" width="1080" height="580" fill="#dce9f2"></rect>`
    + `<path class="map-land" d="${DATA.world.land}" fill-rule="evenodd"></path>`
    + `<g id="mk"></g>`;
}

function yearLabel(pt) {
  const y = pt.year < 0 ? `${-pt.year} BC` : String(pt.year);
  return pt.approx ? `c. ${y}` : y;
}

function drawMarkers(fig) {
  const b = proj(fig.birth.lon, fig.birth.lat);
  const d = proj(fig.death.lon, fig.death.lat);
  const g = $('#mk');
  g.innerHTML =
    `<circle class="mk-dot mk-birth" cx="${b[0]}" cy="${b[1]}" r="6"></circle>`
    + `<circle class="mk-ring mk-death-ring" cx="${d[0]}" cy="${d[1]}" r="9" fill="none" stroke="#b4422e"></circle>`
    + `<circle class="mk-dot mk-death" cx="${d[0]}" cy="${d[1]}" r="3.2"></circle>`
    + `<text class="mk-label" data-anchor="b" x="${b[0]}" y="${b[1]}">${yearLabel(fig.birth)}</text>`
    + `<text class="mk-label" data-anchor="d" x="${d[0]}" y="${d[1]}">${yearLabel(fig.death)}</text>`;
  return [b, d];
}

function scaleMarkers(box) {
  const g = $('#mk');
  if (!g || !g.firstChild) return;
  const w = box[2];
  const r = w * 0.016;
  const birth = g.querySelector('.mk-birth');
  const ring = g.querySelector('.mk-death-ring');
  const death = g.querySelector('.mk-death');
  birth.setAttribute('r', r);
  ring.setAttribute('r', r * 1.55);
  ring.setAttribute('stroke-width', r * 0.55);
  death.setAttribute('r', r * 0.55);
  const bx = +birth.getAttribute('cx'), by = +birth.getAttribute('cy');
  const dx = +death.getAttribute('cx'), dy = +death.getAttribute('cy');
  // keep the two year labels apart: the higher point labels upward,
  // the lower one downward (birth wins the tie)
  const samePlace = Math.hypot(bx - dx, by - dy) < r * 3;
  g.querySelectorAll('.mk-label').forEach((t) => {
    const isBirth = t.dataset.anchor === 'b';
    const cx = isBirth ? bx : dx;
    const cy = isBirth ? by : dy;
    const up = samePlace ? isBirth : (isBirth ? by <= dy : dy < by);
    t.setAttribute('font-size', (w * 0.034).toFixed(2));
    t.setAttribute('stroke-width', (w * 0.008).toFixed(2));
    const nearRightEdge = cx > box[0] + box[2] * 0.78;
    t.setAttribute('x', nearRightEdge ? cx - r * 2 : cx + r * 2);
    t.setAttribute('text-anchor', nearRightEdge ? 'end' : 'start');
    t.setAttribute('y', up ? cy - r * 1.6 : cy + r * 3.0);
  });
}

// ---------- session ----------
export function renderMapStart() {
  const m = store.getMap();
  $('#map-best').textContent = m.sessions
    ? `Your best: ${m.bestScore} pts · longest streak ${m.bestStreak}`
    : 'First session — good luck';
  const saved = store.getSession();
  $('#map-resume').hidden = !saved;
  if (saved) {
    $('#map-resume').textContent = `Resume — round ${saved.i + 1} of 10 (${saved.score} pts)`;
  }
}

function persistSession() {
  store.setSession({
    ids: S.rounds.map((f) => f.id),
    i: S.i, score: S.score, streak: S.streak, bestStreak: S.bestStreak,
    results: S.results.map((r) => ({
      id: r.fig.id, pts: r.pts, correct: r.correct, hints: r.hints, wrongs: r.wrongs,
    })),
  });
}

function resumeSession() {
  const saved = store.getSession();
  if (!saved) return;
  const byId = (id) => DATA.figures.find((f) => f.id === id);
  S = {
    rounds: saved.ids.map(byId),
    i: saved.i, score: saved.score, streak: saved.streak,
    bestStreak: saved.bestStreak,
    results: saved.results.map((r) => ({
      fig: byId(r.id), pts: r.pts, correct: r.correct, hints: r.hints, wrongs: r.wrongs,
    })),
  };
  renderWorld();
  setVb([0, 0, MAP_W, MAP_H]);
  show('view-map');
  startRound();
}

function startSession() {
  const rng = makeRng();
  const by = (d) => DATA.figures.filter((f) => f.difficulty === d);
  const picks = shuffled(by('easy'), rng).slice(0, 4)
    .concat(shuffled(by('medium'), rng).slice(0, 3))
    .concat(shuffled(by('hard'), rng).slice(0, 3));
  S = {
    rounds: shuffled(picks, rng),
    i: 0, score: 0, streak: 0, bestStreak: 0, results: [],
  };
  renderWorld();
  setVb([0, 0, MAP_W, MAP_H]);
  show('view-map');
  startRound();
}

function round() { return S.rounds[S.i]; }

function startRound() {
  const fig = round();
  S.cur = { hints: 0, wrongs: 0, open: true };
  $('#map-progress').textContent = `Round ${S.i + 1} of 10`;
  $('#map-score').textContent = `${S.score} pts`;
  $('#map-feedback').hidden = true;
  $('#map-feedback').innerHTML = '';
  $('#map-hint-chips').innerHTML = '';
  $('#map-guesses').innerHTML = '';
  $('#map-input').value = '';
  $('#map-input').disabled = false;
  $('#map-guess-btn').disabled = false;
  $('#hint-occ').disabled = false;
  $('#hint-ini').disabled = false;
  $('#map-reveal').disabled = false;
  $('#map-next').hidden = true;
  $('#map-streak').hidden = S.streak < 2;
  if (S.streak >= 2) $('#map-streak').textContent = `${S.streak} in a row`;

  setVb([0, 0, MAP_W, MAP_H]);
  const [b, d] = drawMarkers(fig);
  scaleMarkers([0, 0, MAP_W, MAP_H]);
  animateTo(targetBox(b, d));

  persistSession();
  window.__CHRONICLE_TEST__ = Object.assign(window.__CHRONICLE_TEST__ || {}, {
    mapRound: { index: S.i, id: fig.id, name: fig.name },
  });
}

const NAME_PARTICLES = new Set(['of', 'the', 'van', 'von', 'da', 'de', 'la', 'le', 'di']);

function initials(name) {
  const parts = name.split(/\s+/).filter((w) => w && !NAME_PARTICLES.has(w.toLowerCase()));
  return parts.map((w) => w[0].toUpperCase() + '.').join(' ');
}

function figureBio(fig) {
  return `born ${fig.birth.place}, ${yearLabel(fig.birth)}; `
    + `died ${fig.death.place}, ${yearLabel(fig.death)}`;
}

function resolveRound(correct) {
  const fig = round();
  S.cur.open = false;
  let pts = 0;
  let bonus = 0;
  if (correct) {
    pts = Math.max(10, 100 - 25 * S.cur.hints - 10 * S.cur.wrongs);
    S.streak++;
    S.bestStreak = Math.max(S.bestStreak, S.streak);
    if (S.streak >= 2) bonus = 10;
  } else {
    S.streak = 0;
  }
  const total = pts + bonus;
  S.score += total;
  S.results.push({ fig, pts: total, correct, hints: S.cur.hints, wrongs: S.cur.wrongs });
  persistSession();

  const fb = $('#map-feedback');
  fb.className = correct ? 'good' : 'info';
  fb.innerHTML = (correct
    ? `<b class="fig">${fig.name}</b> — ${figureBio(fig)}. `
      + `<span class="pts">+${total} pts</span>`
      + (bonus ? ` <small>(includes ${bonus} streak bonus)</small>` : '')
    : `It was <b class="fig">${fig.name}</b> — ${figureBio(fig)}. <span class="pts">0 pts</span>`);
  fb.hidden = false;

  $('#map-input').disabled = true;
  $('#map-guess-btn').disabled = true;
  $('#hint-occ').disabled = true;
  $('#hint-ini').disabled = true;
  $('#map-reveal').disabled = true;
  $('#map-score').textContent = `${S.score} pts`;
  $('#map-streak').hidden = S.streak < 2;
  if (S.streak >= 2) $('#map-streak').textContent = `${S.streak} in a row`;
  const last = S.i === S.rounds.length - 1;
  $('#map-next').textContent = last ? 'See results ›' : 'Next round ›';
  $('#map-next').hidden = false;
}

function finishSession() {
  if (S.done) {
    show('view-mapsum');
    return;
  }
  S.done = true;
  store.clearSession();
  const m = store.getMap();
  m.sessions = (m.sessions || 0) + 1;
  m.bestScore = Math.max(m.bestScore || 0, S.score);
  m.bestStreak = Math.max(m.bestStreak || 0, S.bestStreak);
  store.setMap(m);
  refreshHomeStats();

  $('#sum-total').textContent = S.score;
  const remarks = [
    [850, 'A chronicler for the ages.'],
    [650, 'The archives salute you.'],
    [450, 'A solid grasp of the past.'],
    [250, 'History rhymes — keep listening.'],
    [0, 'Every historian starts somewhere.'],
  ];
  $('#sum-remark').textContent = remarks.find((r) => S.score >= r[0])[1];
  const ol = $('#sum-rounds');
  ol.innerHTML = '';
  for (const r of S.results) {
    const li = document.createElement('li');
    li.innerHTML = `<span class="sum-name">${r.fig.name}`
      + `<small>${yearLabel(r.fig.birth)} – ${yearLabel(r.fig.death)}`
      + (r.hints ? ` · ${r.hints} hint${r.hints > 1 ? 's' : ''}` : '') + '</small></span>'
      + `<span class="sum-pts${r.pts ? '' : ' zero'}">${r.pts ? '+' + r.pts : '0'}</span>`;
    ol.appendChild(li);
  }
  window.__CHRONICLE_TEST__ = Object.assign(window.__CHRONICLE_TEST__ || {}, {
    mapSession: { score: S.score, results: S.results.map((r) => ({ id: r.fig.id, pts: r.pts, correct: r.correct })) },
  });
  show('view-mapsum');
}

// ---------- init ----------
export function initMapGame() {
  $('#map-start').addEventListener('click', startSession);

  $('#map-form').addEventListener('submit', (e) => {
    e.preventDefault();
    if (!S || !S.cur.open) return;
    const guess = $('#map-input').value.trim();
    if (!guess) return;
    if (isMatch(guess, round())) {
      resolveRound(true);
    } else {
      S.cur.wrongs++;
      const chip = document.createElement('span');
      chip.className = 'guess-chip';
      chip.textContent = guess;
      $('#map-guesses').appendChild(chip);
      const inp = $('#map-input');
      inp.value = '';
      inp.classList.remove('shake');
      void inp.offsetWidth;       // restart the animation
      inp.classList.add('shake');
      inp.focus();
    }
  });

  $('#hint-occ').addEventListener('click', () => {
    if (!S || !S.cur.open) return;
    S.cur.hints++;
    $('#hint-occ').disabled = true;
    const chip = document.createElement('div');
    chip.className = 'hint-chip';
    chip.textContent = round().occupation;
    $('#map-hint-chips').appendChild(chip);
  });

  $('#hint-ini').addEventListener('click', () => {
    if (!S || !S.cur.open) return;
    S.cur.hints++;
    $('#hint-ini').disabled = true;
    const chip = document.createElement('div');
    chip.className = 'hint-chip';
    chip.textContent = `Initials: ${initials(round().name)}`;
    $('#map-hint-chips').appendChild(chip);
  });

  $('#map-reveal').addEventListener('click', () => {
    if (!S || !S.cur.open) return;
    resolveRound(false);
  });

  $('#map-next').addEventListener('click', () => {
    if (S.i === S.rounds.length - 1) { finishSession(); return; }
    S.i++;
    startRound();
  });

  $('#map-quit').addEventListener('click', () => {
    if (S && !S.done) {
      appConfirm('Quit this session? The score so far will be lost.', 'Quit session')
        .then((ok) => {
          if (ok) {
            store.clearSession();
            renderMapStart();
            back();
          }
        });
    } else {
      back();
    }
  });

  $('#map-resume').addEventListener('click', resumeSession);

  $('#sum-back').addEventListener('click', goHome);
  $('#sum-again').addEventListener('click', () => {
    back();              // drop the summary from the view trail
    startSession();
  });
  $('#sum-home').addEventListener('click', goHome);
}
