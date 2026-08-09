// "Map of a Life": guess the historical figure from birth/death geography.
import { DATA, $, show, back, goHome, refreshHomeStats, setReceiptStamp, maybeIntro, openIntroHelp, wireTurnThePage, wireEncore, teachWrongGuess, announce, testHooksEnabled, consumeShareLaunch } from './app.js';
import * as store from './storage.js';
import { track, roundOutcome, durationBucket } from './track.js';
import { isMatch, registerPool } from './match.js';
import { confirmFirstGuess } from './guesswarn.js';
import * as daily from './daily.js';
import { mapShareText, shareResult, flashShareButton } from './sharecard.js';
import * as sfx from './sfx.js';

const MAP_W = 1000, MAP_H = 500;
// The world background rect (see renderWorld) bleeds 40 units past the land
// data on every side as a "sea" margin. targetBox is allowed to use that
// margin when centring on a marker near the map's edge (e.g. an Arctic
// death site) instead of hard-clamping the viewBox flush to 0/MAP_W/MAP_H,
// which left zero headroom for the marker ring and its year label.
const MAP_BLEED = 40;
let S = null;            // current session
let vb = [0, 0, MAP_W, MAP_H];   // current viewBox
let animId = null;

// ---------- round economy (mirrors Face Value/Relic's worthNow shape) ----------
const WORTH_START = 100;
const HINT_OCC_COST = 15; // "Claim to fame" — the lighter slip (matches the reveal games' 15/25 ladder)
const HINT_INI_COST = 25; // "Initials" — near-decisive with the dates already on the map
const WRONG_COST = 15;    // per wrong guess (aligned with Face Value/Relic)
const WORTH_FLOOR = 10;   // a correct answer never pays less than this; giving up pays 0
const MCQ_COST = 80;      // the three-choices rescue, priced like a clue slip; see revealgame.js

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
  // Reserve headroom for the year labels, which sit above/below their dot
  // (see scaleMarkers' anchor flip) and scale with the box's own width
  // (marker radius = w*0.016, label font-size = w*0.034). Baking a fixed
  // fraction of w into the height here — before the aspect fit below —
  // keeps both labels comfortably inside the box at any zoom level, instead
  // of only the marker dots themselves.
  h += 0.14 * w;
  if (w / h > aspect) h = w / aspect; else w = h * aspect;
  const maxW = MAP_W + 2 * MAP_BLEED, maxH = MAP_H + 2 * MAP_BLEED;
  if (w > maxW) { w = maxW; h = w / aspect; }
  if (h > maxH) { h = maxH; w = Math.min(maxW, h * aspect); }
  let cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  // Clamp into the bleed margin, not just the strict map bounds, so a
  // marker near the pole (or the antimeridian) isn't forced flush against
  // the viewBox edge with no room left for its ring/label.
  cx = Math.min(Math.max(cx, w / 2 - MAP_BLEED), MAP_W - w / 2 + MAP_BLEED);
  cy = Math.min(Math.max(cy, h / 2 - MAP_BLEED), MAP_H - h / 2 + MAP_BLEED);
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

// ---------- pinch / pan / double-tap / wheel zoom ----------
// Gestures drive the SVG viewBox directly: vectors re-render crisp at any
// zoom and setVb re-scales the markers every frame. One finger pans, two
// pinch, double-tap zooms in (and back out to the round's framing), a mouse
// wheel zooms about the cursor. Owner report 2026-07-15: "can't zoom".
const MIN_VB_W = 30;

function clampBox(box) {
  // A zero-size layout (backgrounded tab, mid-rotation) makes the gesture
  // maths divide by zero; never let a non-finite box poison the viewBox.
  if (!box.every(Number.isFinite)) return vb.slice();
  let [x, y, w, h] = box;
  const maxW = MAP_W + 2 * MAP_BLEED, maxH = MAP_H + 2 * MAP_BLEED;
  if (w > maxW) { h *= maxW / w; w = maxW; }
  if (h > maxH) { w *= maxH / h; h = maxH; }
  if (w < MIN_VB_W) { h *= MIN_VB_W / w; w = MIN_VB_W; }
  let cx = x + w / 2, cy = y + h / 2;
  cx = Math.min(Math.max(cx, w / 2 - MAP_BLEED), MAP_W - w / 2 + MAP_BLEED);
  cy = Math.min(Math.max(cy, h / 2 - MAP_BLEED), MAP_H - h / 2 + MAP_BLEED);
  return [cx - w / 2, cy - h / 2, w, h];
}

function attachMapGestures() {
  const svg = $('#map-svg');
  if (!svg || svg.dataset.gestures) return;
  svg.dataset.gestures = '1';
  svg.style.touchAction = 'none';
  const pointers = new Map();
  let pinch0 = null;    // pinch-start: distance, box, map point under midpoint
  let pan0 = null;      // drag-start: client point + box
  let lastTap = null;

  const toMap = (cx, cy, box) => {
    const r = svg.getBoundingClientRect();
    return [box[0] + (cx - r.left) / r.width * box[2],
            box[1] + (cy - r.top) / r.height * box[3]];
  };
  const homeBox = () => (S && S.homeBox) || [0, 0, MAP_W, MAP_H];

  svg.addEventListener('pointerdown', (e) => {
    if (animId) cancelAnimationFrame(animId);   // a touch takes the wheel
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinch0 = {
        d: Math.hypot(a.x - b.x, a.y - b.y) || 1,
        vb: vb.slice(),
        mapPt: toMap((a.x + b.x) / 2, (a.y + b.y) / 2, vb),
      };
      pan0 = null;
    } else if (pointers.size === 1) {
      pan0 = { x: e.clientX, y: e.clientY, vb: vb.slice(), moved: false };
    }
  });

  svg.addEventListener('pointermove', (e) => {
    const p = pointers.get(e.pointerId);
    if (!p) return;
    p.x = e.clientX; p.y = e.clientY;
    if (pointers.size === 2 && pinch0) {
      const [a, b] = [...pointers.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y) || 1;
      const w = Math.max(MIN_VB_W, Math.min(MAP_W + 2 * MAP_BLEED, pinch0.vb[2] * (pinch0.d / d)));
      const h = w * pinch0.vb[3] / pinch0.vb[2];
      // keep the map point that started under the fingers under them still
      const r = svg.getBoundingClientRect();
      const fx = ((a.x + b.x) / 2 - r.left) / r.width;
      const fy = ((a.y + b.y) / 2 - r.top) / r.height;
      setVb(clampBox([pinch0.mapPt[0] - fx * w, pinch0.mapPt[1] - fy * h, w, h]));
    } else if (pointers.size === 1 && pan0) {
      const r = svg.getBoundingClientRect();
      const dx = (e.clientX - pan0.x) / r.width * pan0.vb[2];
      const dy = (e.clientY - pan0.y) / r.height * pan0.vb[3];
      if (Math.abs(e.clientX - pan0.x) + Math.abs(e.clientY - pan0.y) > 6) pan0.moved = true;
      setVb(clampBox([pan0.vb[0] - dx, pan0.vb[1] - dy, pan0.vb[2], pan0.vb[3]]));
    }
  });

  function end(e) {
    const wasTap = e.type === 'pointerup' && pan0 && !pan0.moved && pointers.size === 1;
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinch0 = null;
    if (pointers.size === 0) pan0 = null;
    if (!wasTap) return;
    const now = performance.now();
    if (lastTap && now - lastTap.t < 350
        && Math.hypot(e.clientX - lastTap.x, e.clientY - lastTap.y) < 30) {
      lastTap = null;
      const home = homeBox();
      if (vb[2] < home[2] * 0.9) {
        animateTo(home);                          // already in close: back out
      } else {
        const [mx, my] = toMap(e.clientX, e.clientY, vb);
        const w = Math.max(MIN_VB_W, vb[2] / 2.5);
        const h = w * vb[3] / vb[2];
        animateTo(clampBox([mx - w / 2, my - h / 2, w, h]));
      }
    } else {
      lastTap = { t: now, x: e.clientX, y: e.clientY };
    }
  }
  svg.addEventListener('pointerup', end);
  svg.addEventListener('pointercancel', end);

  svg.addEventListener('wheel', (e) => {
    e.preventDefault();
    if (animId) cancelAnimationFrame(animId);
    const k = e.deltaY > 0 ? 1.15 : 1 / 1.15;
    const w = Math.max(MIN_VB_W, Math.min(MAP_W + 2 * MAP_BLEED, vb[2] * k));
    const h = w * vb[3] / vb[2];
    const [mx, my] = toMap(e.clientX, e.clientY, vb);
    const r = svg.getBoundingClientRect();
    const fx = (e.clientX - r.left) / r.width;
    const fy = (e.clientY - r.top) / r.height;
    setVb(clampBox([mx - fx * w, my - fy * h, w, h]));
  }, { passive: false });
}

// ---------- map rendering ----------
function renderWorld() {
  const svg = $('#map-svg');
  svg.setAttribute('viewBox', '0 0 1000 500');
  svg.innerHTML = `<rect x="-40" y="-40" width="1080" height="580" fill="var(--ch-cream)"></rect>`
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
  // stash the projected positions; scaleMarkers re-reads them every frame
  // when re-scaling radii and re-laying-out the year labels.
  g.dataset.bx = b[0]; g.dataset.by = b[1];
  g.dataset.dx = d[0]; g.dataset.dy = d[1];
  g.innerHTML =
    `<circle class="mk-dot mk-birth" cx="${b[0]}" cy="${b[1]}" r="6"></circle>`
    + `<circle class="mk-ring mk-death-ring" cx="${d[0]}" cy="${d[1]}" r="9" fill="none" stroke="var(--ch-map-origin)"></circle>`
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

  // Markers always sit at their TRUE projected positions. (They used to be
  // pushed apart to a zoom-scaled minimum gap when close together, but that
  // displacement depended on the viewBox width — with free pinch-zoom the
  // pins visibly crawled across the map as the gap recomputed. A same-city
  // pair still reads: the death ring draws around the birth dot, the year
  // labels split up/down below, and the player can now zoom in to resolve.)
  const bx = +g.dataset.bx, by = +g.dataset.by;
  const dx = +g.dataset.dx, dy = +g.dataset.dy;
  birth.setAttribute('cx', bx); birth.setAttribute('cy', by);
  ring.setAttribute('cx', dx); ring.setAttribute('cy', dy);
  death.setAttribute('cx', dx); death.setAttribute('cy', dy);

  // keep the two year labels apart: whichever marker is higher labels
  // upward, the lower one downward (birth wins the tie) — so the labels
  // never cross, even when birth and death share a city.
  g.querySelectorAll('.mk-label').forEach((t) => {
    const isBirth = t.dataset.anchor === 'b';
    const cx = isBirth ? bx : dx;
    const cy = isBirth ? by : dy;
    const up = isBirth ? by <= dy : dy < by;
    t.setAttribute('font-size', (w * 0.034).toFixed(2));
    t.setAttribute('stroke-width', (w * 0.008).toFixed(2));
    const nearRightEdge = cx > box[0] + box[2] * 0.78;
    t.setAttribute('x', nearRightEdge ? cx - r * 2 : cx + r * 2);
    t.setAttribute('text-anchor', nearRightEdge ? 'end' : 'start');
    t.setAttribute('y', up ? cy - r * 1.6 : cy + r * 3.0);
  });
}

// ---------- session ----------
// Free sessions keep using store.getSession/setSession/clearSession exactly
// as before. Daily and practice sessions use the namespaced generic store
// (js/storage.js getDailySession family) so they never collide with a free
// session or with each other; MODE_STORE picks the right get/set/clear for
// the session currently in play.
function modeStore(mode, key) {
  if (mode === 'free') return { get: store.getSession, set: store.setSession, clear: store.clearSession };
  return {
    get: () => store.getDailySession(key),
    set: (s) => store.setDailySession(key, s),
    clear: () => store.clearDailySession(key),
  };
}

export function renderMapStart() {
  const m = store.getMap();
  $('#map-best').textContent = m.sessions
    ? `Your best: ${m.bestScore} pts · longest streak ${m.bestStreak}`
    : 'First run — good luck';
  const saved = store.getSession();
  const valid = saved && saved.ids && saved.results;
  $('#map-resume').hidden = !valid;
  if (valid) {
    $('#map-resume').textContent = saved.results.length >= saved.ids.length
      ? `See your results (${saved.score} pts)`
      : `Resume — round ${saved.results.length + 1} of ${saved.ids.length} (${saved.score} pts)`;
  }
}

function persistSession() {
  S.store.set({
    ids: S.rounds.map((f) => f.id),
    i: S.i, score: S.score, streak: S.streak, bestStreak: S.bestStreak,
    editionIndex: S.editionIndex,
    startedAt: S.startedAt,
    cur: S.cur && S.cur.open
      ? {
          hints: S.cur.hints, wrongs: S.cur.wrongs, occUsed: !!S.cur.occUsed, iniUsed: !!S.cur.iniUsed,
          wrongGuesses: (S.cur.wrongGuesses || []).slice(),
          hintCost: S.cur.hintCost || 0,
          mcqOpts: S.cur.mcqOpts ? S.cur.mcqOpts.slice() : null,
        }
      : null,
    results: S.results.map((r) => ({
      id: r.fig.id, pts: r.pts, correct: r.correct, hints: r.hints, wrongs: r.wrongs, mcq: !!r.mcq,
    })),
  });
}

// ---------- worth readout + guess chips (mirrors Face Value/Relic's df-worth
// and cost-stamped guess-chip treatment; no matching element in index.html
// for Lifeline, so it's created and inserted once here) ----------
function ensureWorthEl() {
  let el = $('#map-worth');
  if (!el) {
    el = document.createElement('p');
    el.id = 'map-worth';
    el.className = 'df-worth';
    const question = $('#map-question');
    question.parentNode.insertBefore(el, question);
  }
  return el;
}

function worthNow() {
  const cur = S && S.cur;
  if (!cur) return WORTH_START;
  // Rounds persisted before the per-hint pricing carried only a hint COUNT;
  // price those at the old flat 25.
  const hintCost = cur.hintCost != null ? cur.hintCost : 25 * cur.hints;
  return Math.max(WORTH_FLOOR, WORTH_START - hintCost - WRONG_COST * cur.wrongs);
}

function updateWorth() {
  const el = ensureWorthEl();
  if (!S || !S.cur) { el.innerHTML = ''; return; }
  const w = worthNow();
  // Lifeline has no tears, so the only suffix it ever needs is the floor
  // (clue pricing, 5 Aug 2026): once the round is worth 10 the listed prices
  // stop being real deductions, and the line says so.
  el.innerHTML = `WORTH: <b>${w} PTS</b>`
    + (w <= WORTH_FLOOR ? ' · <span class="worth-note">minimum</span>' : '');
  const b = el.querySelector('b');
  if (b && lastWorthShown != null && lastWorthShown !== w) b.classList.add('flash');
  lastWorthShown = w;
  refreshControlLabels();
}

let lastWorthShown = null;   // reset per round; drives the worth flash

// The rescue closes the shop (Daniel, 5 Aug 2026) — same ruling as Face
// Value/Relic, see the longer note in revealgame.js. Opening "3 choices"
// drops the round to its floor, so every remaining clue would cost nothing;
// offering one at a price it cannot charge is a lie, so the slips lock.
// (Lifeline has no scraps, so the clue slips are the whole of it.)
function rescueOpen() {
  return !!(S && S.cur && S.cur.mcqOpts);
}

// A price is only true while the whole of it can come off; near the floor the
// control says what it LEAVES instead. Same rule as Face Value/Relic, same
// source of truth: worthNow().
function priceSpan(cost) {
  const w = worthNow();
  return w - cost < WORTH_FLOOR
    ? `<span class="leaves">· drops to ${Math.max(WORTH_FLOOR, w - cost)}</span>`
    : `<span class="cost">−${cost}</span>`;
}

function refreshControlLabels() {
  if (!S || !S.cur) return;
  // A frozen slip quotes nothing and goes visibly out of service (the house
  // .pill:disabled treatment) — it can no longer charge what it says.
  const frozen = rescueOpen();
  const occ = $('#hint-occ');
  if (occ && !S.cur.occUsed) {
    occ.innerHTML = frozen ? '<span>Claim to fame</span>'
      : `<span>Claim to fame ${priceSpan(HINT_OCC_COST)}</span>`;
    if (frozen) occ.disabled = true;
  }
  const ini = $('#hint-ini');
  if (ini && !S.cur.iniUsed) {
    ini.innerHTML = frozen ? '<span>Initials</span>'
      : `<span>Initials ${priceSpan(HINT_INI_COST)}</span>`;
    if (frozen) ini.disabled = true;
  }
  const mcq = $('#map-mcq');
  if (mcq && !S.cur.mcqOpts) {
    mcq.innerHTML = `<span>3 choices <span class="leaves">· round worth ${Math.max(WORTH_FLOOR, worthNow() - MCQ_COST)}</span></span>`;
  }
}

function addGuessChip(text) {
  const chip = document.createElement('span');
  chip.className = 'guess-chip';
  const guessText = document.createElement('span');
  guessText.textContent = text;
  chip.appendChild(guessText);
  const penalty = document.createElement('small');
  penalty.textContent = `-${WRONG_COST}`;
  chip.appendChild(penalty);
  $('#map-guesses').appendChild(chip);
}

function resumeSession() {
  const saved = store.getSession();
  if (!saved || !saved.ids || !saved.results) return;
  resumeFrom('free', null, saved);
}

// Shared resume path for free/daily/practice: `saved` is the persisted
// session shape (ids/i/score/streak/bestStreak/results/cur/editionIndex).
function resumeFrom(mode, key, saved, fromShare) {
  const byId = (id) => DATA.figures.find((f) => f.id === id);
  // The round to play is always the first one without a stored result —
  // a session saved mid-round (answered, "Next" untapped) must NOT replay
  // the already-scored round.
  const next = saved.results.length;
  const st = modeStore(mode, key);
  if (saved.ids.some((id) => !byId(id)) || saved.results.some((r) => !byId(r.id))) {
    st.clear();
    if (mode === 'free') renderMapStart();
    return;
  }
  S = {
    mode, dailyKey: key, store: st, editionIndex: saved.editionIndex,
    rounds: saved.ids.map(byId),
    i: Math.min(next, saved.ids.length - 1),
    score: saved.score, streak: saved.streak,
    bestStreak: saved.bestStreak,
    results: saved.results.map((r) => ({
      fig: byId(r.id), pts: r.pts, correct: r.correct, hints: r.hints, wrongs: r.wrongs,
    })),
    pendingCur: saved.cur || null,
    startedAt: saved.startedAt || Date.now(),
    fromShare: !!fromShare,
  };
  if (next >= saved.ids.length) {
    // every round already answered when the app died: go straight to results
    finishSession();
    return;
  }
  renderWorld();
  setVb([0, 0, MAP_W, MAP_H]);
  show('view-map');
  startRound();
}

function startSession() {
  const rng = makeRng();
  const by = (d) => DATA.figures.filter((f) => f.difficulty === d);
  const picks = shuffled(by('easy'), rng).slice(0, 2)
    .concat(shuffled(by('medium'), rng).slice(0, 2))
    .concat(shuffled(by('hard'), rng).slice(0, 1));
  S = {
    mode: 'free', dailyKey: null, store: modeStore('free', null),
    rounds: shuffled(picks, rng),
    i: 0, score: 0, streak: 0, bestStreak: 0, results: [],
  };
  renderWorld();
  setVb([0, 0, MAP_W, MAP_H]);
  show('view-map');
  startRound();
}

// ---------- daily / practice entry points ----------
// Daily: 10 figures = getEdition('map', n) in exact order (no shuffle). A
// completed daily is locked — reopening shows the results summary instead of
// replaying. Practice: same edition list, but replayable and never touches
// the ledger (separate `chronicle.practice.*` storage key).
function startEdition(mode, editionIndex) {
  const key = mode === 'daily' ? daily.dailyKey('map', editionIndex) : daily.practiceKey('map', editionIndex);
  // P5.2: consumed synchronously (no await between app.js setting it and
  // this read), so it's safe even though the intro overlay can defer begin()
  // behind a user tap — fromShare is closed over either way.
  const fromShare = mode === 'daily' && consumeShareLaunch('map');
  if (mode === 'daily') {
    const entry = store.getDailyEntry('map', editionIndex);
    if (entry) { showLockedResult(editionIndex, entry); return; }
  }
  const saved = store.getDailySession(key);
  if (saved && saved.ids && saved.results) {
    if (mode === 'daily') track('resume-map');
    resumeFrom(mode, key, saved, fromShare);
    return;
  }
  const begin = () => {
    const rounds = daily.getEdition('map', editionIndex);
    S = {
      mode, dailyKey: key, store: modeStore(mode, key), editionIndex,
      rounds, i: 0, score: 0, streak: 0, bestStreak: 0, results: [],
      startedAt: Date.now(), fromShare,
    };
    renderWorld();
    setVb([0, 0, MAP_W, MAP_H]);
    show('view-map');
    startRound();
  };
  // First-run intro before a fresh daily only (not resume/practice/locked).
  if (mode === 'daily') maybeIntro('map', editionIndex, begin);
  else begin();
}

// The access guard lives on the entry point itself — see the twin comment in
// revealgame.js startRevealDaily. Nothing may open a daily without passing
// the archive window first.
export function startMapDaily(editionIndex) {
  if (!daily.canPlayEdition(editionIndex)) { goHome(); return; }
  startEdition('daily', editionIndex);
}
export function startMapPractice(editionIndex) { startEdition('practice', editionIndex); }

// A locked (already-completed) daily: the summary view, read-only. Rounds are
// rebuilt from the MANIFEST (daily.getEdition) rather than from the ledger
// entry — see the twin comment in revealgame.js showLockedResult.
function showLockedResult(editionIndex, entry) {
  const byId = (id) => (DATA.figures || []).find((f) => f.id === id);
  const scored = new Map((entry.detail || []).map((r) => [r.id, r]));
  const aired = daily.getEdition('map', editionIndex);
  const results = aired.map((fig) => {
    const r = scored.get(fig.id) || {};
    return { fig, pts: r.pts || 0, correct: !!r.correct, hints: r.hints || 0 };
  });
  S = {
    mode: 'daily', dailyKey: daily.dailyKey('map', editionIndex), store: modeStore('daily', null),
    editionIndex, done: true, locked: true,
    score: entry.score,
    showSolution: true,
    results: results.length ? results : (entry.detail || []).map((r) => ({
      fig: byId(r.id) || { name: '(removed)', birth: {}, death: {} },
      pts: r.pts, correct: r.correct, hints: r.hints || 0,
    })),
  };
  renderLockedSummary();
  show('view-mapsum');
}

function round() { return S.rounds[S.i]; }

function startRound() {
  const fig = round();
  const carried = S.pendingCur;
  S.pendingCur = null;
  S.cur = carried
    ? {
        hints: carried.hints, wrongs: carried.wrongs, occUsed: carried.occUsed, iniUsed: carried.iniUsed,
        hintCost: carried.hintCost != null ? carried.hintCost : 25 * (carried.hints || 0),
        wrongGuesses: carried.wrongGuesses || [], open: true,
        mcqOpts: carried.mcqOpts ? carried.mcqOpts.slice() : null,
      }
    : { hints: 0, hintCost: 0, wrongs: 0, occUsed: false, iniUsed: false, wrongGuesses: [], open: true, mcqOpts: null };
  $('#map-progress').textContent = `Round ${S.i + 1} of ${S.rounds.length}`;
  announce(`Round ${S.i + 1} of ${S.rounds.length}.`);
  $('#map-score').textContent = `${S.score} pts`;
  $('#map-feedback').hidden = true;
  $('#map-feedback').innerHTML = '';
  $('#map-wrong-note').hidden = true;
  $('#map-form').hidden = false;
  $('#map-hints').hidden = false;
  clearClueSlots();
  $('#map-guesses').innerHTML = '';
  $('#map-input').value = '';
  $('#map-input').disabled = false;
  $('#map-guess-btn').disabled = false;
  $('#hint-occ').disabled = false;
  $('#hint-occ').hidden = false;
  $('#hint-ini').disabled = false;
  $('#hint-ini').hidden = false;
  $('#map-mcq').disabled = false;
  $('#map-mcq-chips').hidden = true;
  $('#map-mcq-chips').innerHTML = '';
  lastWorthShown = null;   // a fresh round's first worth is not a "change"
  // a resumed mid-round keeps its hints/wrong guesses (and their cost):
  // rebuild the chips and the worth readout from the carried-over state.
  if (S.cur.occUsed) revealClueInSlot($('#hint-occ'), fig.occupation);
  if (S.cur.iniUsed) revealClueInSlot($('#hint-ini'), `Initials: ${initials(fig.name)}`);
  S.cur.wrongGuesses.forEach((g) => addGuessChip(g));
  if (S.cur.mcqOpts) renderMcq();   // resumed mid-choice: same three, same order
  updateWorth();
  $('#map-next').hidden = true;
  $('#map-streak').hidden = S.streak < 2;
  if (S.streak >= 2) $('#map-streak').textContent = `${S.streak} in a row`;

  setVb([0, 0, MAP_W, MAP_H]);
  const [b, d] = drawMarkers(fig);
  scaleMarkers([0, 0, MAP_W, MAP_H]);
  S.homeBox = targetBox(b, d);   // double-tap zooms back out to this framing
  animateTo(S.homeBox);

  persistSession();
  if (testHooksEnabled()) {
    window.__CHRONICLE_TEST__ = Object.assign(window.__CHRONICLE_TEST__ || {}, {
      mapRound: { index: S.i, id: fig.id, name: fig.name },
    });
  }
}

// A bought clue REPLACES its own button, in the same slot (clue pricing,
// 5 Aug 2026) — no greyed control plus a duplicate answer below it.
function revealClueInSlot(btn, text) {
  const chip = document.createElement('div');
  chip.className = 'hint-chip clue-slot';
  chip.textContent = text;
  btn.parentNode.insertBefore(chip, btn);
  btn.hidden = true;
  btn.disabled = true;
}
function clearClueSlots() {
  document.querySelectorAll('#map-hints .clue-slot').forEach((el) => el.remove());
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

// ---------- the ultimate clue: three choices (mirrors revealgame.js) ----------
function mcqOptionsFor(fig) {
  let names = (fig.mcq || []).slice(0, 2);
  if (names.length < 2) {
    const others = (DATA.figures || []).filter((x) => x.id !== fig.id
      && x.name !== fig.name && x.difficulty === fig.difficulty);
    while (names.length < 2 && others.length) {
      const pick = others.splice(Math.floor(Math.random() * others.length), 1)[0];
      if (!names.includes(pick.name)) names.push(pick.name);
    }
  }
  const opts = [fig.name, ...names];
  for (let i = opts.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [opts[i], opts[j]] = [opts[j], opts[i]];
  }
  return opts;
}

function openMcq() {
  if (!S || !S.cur || !S.cur.open || S.cur.mcqOpts) return;
  S.cur.mcqOpts = mcqOptionsFor(round());
  S.cur.hintCost = (S.cur.hintCost || 0) + MCQ_COST;  // priced like a clue slip
  persistSession();
  if (S.mode === 'daily') track('mcq-open-map');
  renderMcq();
}

function renderMcq() {
  const fig = round();
  const wrap = $('#map-mcq-chips');
  wrap.innerHTML = '';
  S.cur.mcqOpts.forEach((name) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'pill mcq-opt';
    b.textContent = name;
    b.addEventListener('click', () => {
      if (!S || !S.cur || !S.cur.open) return;
      resolveRound(name === fig.name, { mcq: true });
    });
    wrap.appendChild(b);
  });
  wrap.hidden = false;
  // Typing is over, and so is spending: updateWorth → refreshControlLabels
  // dims the two clue slips and strips the prices they can no longer charge.
  $('#map-form').hidden = true;
  $('#map-mcq').disabled = true;
  updateWorth();   // the −80 is already in hintCost: the standard readout tells it straight
  announce(`Three choices: ${S.cur.mcqOpts.join(', ')}. Pick one for ${worthNow()} points.`
    + ' Clues are closed.');
}

function resolveRound(correct, opts) {
  const fig = round();
  const fromMcq = !!(opts && opts.mcq);
  S.cur.open = false;
  let pts = 0;
  let bonus = 0;
  if (correct) {
    pts = worthNow();   // MCQ's −80 was charged at open; the floor still pays ≥10
    if (!fromMcq) {
      S.streak++;
      S.bestStreak = Math.max(S.bestStreak, S.streak);
      if (S.streak >= 2) bonus = 10;
    }
    sfx.play('correct');
  } else {
    S.streak = 0;
  }
  const total = pts + bonus;
  S.results.push({ fig, pts: total, correct, hints: S.cur.hints, wrongs: S.cur.wrongs, mcq: fromMcq });
  if (S.mode === 'daily' && fromMcq) track(`mcq-map-${correct ? 'win' : 'loss'}`);
  S.score = daily.sessionScore(S.results);   // the 0–100 dial: capped round average
  if (S.mode === 'daily') track(`round-map-${roundOutcome(correct, S.cur.hints, S.cur.wrongs)}`);
  persistSession();

  const fb = $('#map-feedback');
  fb.className = correct ? 'good' : 'info';
  fb.innerHTML = (correct
    ? `<b class="fig">${fig.name}</b> — ${figureBio(fig)}. `
      + `<span class="pts">+${total} pts</span>`
      + (bonus ? ` <small>(includes ${bonus} streak bonus)</small>` : '')
      + (fromMcq ? ' <small>(picked from three)</small>' : '')
    : `It was <b class="fig">${fig.name}</b> — ${figureBio(fig)}. <span class="pts">0 pts</span>`)
    // Lifeline reveal line: a fun-fact reward, styled like Face Value's
    // blurb-as-reward text. figures.json doesn't carry `fact` on every entry
    // yet (content grind lands separately) — no-ops invisibly until it does.
    + (fig.fact ? `<span class="fig-fact">${fig.fact}</span>` : '');
  fb.hidden = false;
  // P2.4: the verdict, spoken — correct answers and reveals alike.
  announce(correct
    ? `Correct — ${fig.name}. Plus ${total} points.`
    : `It was ${fig.name}. 0 points.`);

  $('#map-input').disabled = true;
  $('#map-guess-btn').disabled = true;
  $('#hint-occ').disabled = true;
  $('#hint-ini').disabled = true;
  $('#map-mcq').disabled = true;
  $('#map-mcq-chips').hidden = true;
  $('#map-form').hidden = true;     // resolved: clear the dead controls so
  $('#map-hints').hidden = true;    // the Next button is always in view
  const worthEl = $('#map-worth');
  if (worthEl) worthEl.innerHTML = '';   // the round is settled — worth already paid out above
  $('#map-score').textContent = `${S.score} pts`;
  $('#map-streak').hidden = S.streak < 2;
  if (S.streak >= 2) $('#map-streak').textContent = `${S.streak} in a row`;
  const last = S.i === S.rounds.length - 1;
  $('#map-next').textContent = last ? 'See results ›' : 'Next round ›';
  $('#map-next').hidden = false;
  $('#map-next').scrollIntoView({ block: 'nearest' });
}

function renderLockedSummary() {
  const head = document.querySelector('#view-mapsum [data-receipt-head]');
  if (head) head.textContent = 'Yesternerd · Lifeline'
    + (S.editionIndex != null ? ` · № ${S.editionIndex}` : '');
  $('#sum-total').textContent = S.score;
  setReceiptStamp('view-mapsum', S.score);
  $('#sum-report').href = daily.reportProblemHref(null, S.editionIndex);
  // Bands recalibrated 28 Jul 2026 for the 3-round daily — see the twin
  // comment in revealgame.js renderLockedSummary.
  const remarks = [
    [88, 'Immortalised.'],
    [60, 'A household name.'],
    [35, 'Fifteen minutes of fame.'],
    [15, 'Getting warm.'],
    [0, 'A footnote.'],
  ];
  $('#sum-remark').innerHTML = remarks.find((r) => S.score >= r[0])[1];
  const ol = $('#sum-rounds');
  ol.innerHTML = '';
  for (const r of S.results) {
    const li = document.createElement('li');
    li.innerHTML = `<span class="sum-name">${r.fig.name}`
      + (r.fig.birth && r.fig.birth.year !== undefined
        ? `<small>${yearLabel(r.fig.birth)} – ${yearLabel(r.fig.death)}`
          + (r.hints ? ` · ${r.hints} hint${r.hints > 1 ? 's' : ''}` : '') + '</small>'
        : '') + '</span>'
      + `<span class="sum-pts${r.pts ? '' : ' zero'}">${r.pts ? '+' + r.pts : '0'}</span>`;
    ol.appendChild(li);
  }
  // Daily results are locked: replace the "Play again" action with a plain
  // Home button so a completed daily can't be replayed from its own summary.
  // Share 2.0: dailies only (the issue number is the common reference).
  const isDaily = S.mode === 'daily' && S.editionIndex != null;
  S.share = isDaily ? {
    text: mapShareText(S.editionIndex, S.results, S.score),
    trackAs: 'share-map',
  } : null;
  const sumShare = $('#sum-share');
  if (sumShare) sumShare.hidden = !S.share;
  wireTurnThePage('sum-turn', S.editionIndex, isDaily);
  renderSolution();
  wireEncore('sum-encore', 'map', isDaily);
  $('#sum-again').hidden = !!S.locked;
}

// ---------- the solution recap (Archive v2) ----------
// figures.json carries NO image for any of its 541 entries (verified 7 Aug
// 2026: id, name, occupation, birth, death, fact, mcq, variants, difficulty),
// so a portrait here is impossible without a separate content-and-rights
// project. The map IS this game's picture, so the recap shows exactly that:
// the two pins revealed, framed on the pair, with the name, the occupation
// and the fact underneath.

// A standalone framing box for one figure, independent of the live #map-svg
// (which is not on screen while the summary is). Fixed 2:1, matching the
// .sol-map aspect ratio in style.css.
function soloBox(p1, p2) {
  const aspect = 2;
  const x0 = Math.min(p1[0], p2[0]), x1 = Math.max(p1[0], p2[0]);
  const y0 = Math.min(p1[1], p2[1]), y1 = Math.max(p1[1], p2[1]);
  let w = Math.max((x1 - x0) * 2.2, 220);
  let h = Math.max((y1 - y0) * 2.2, 110);
  h += 0.14 * w;
  if (w / h > aspect) h = w / aspect; else w = h * aspect;
  const maxW = MAP_W + 2 * MAP_BLEED, maxH = MAP_H + 2 * MAP_BLEED;
  if (w > maxW) { w = maxW; h = w / aspect; }
  if (h > maxH) { h = maxH; w = Math.min(maxW, h * aspect); }
  let cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  cx = Math.min(Math.max(cx, w / 2 - MAP_BLEED), MAP_W - w / 2 + MAP_BLEED);
  cy = Math.min(Math.max(cy, h / 2 - MAP_BLEED), MAP_H - h / 2 + MAP_BLEED);
  return [cx - w / 2, cy - h / 2, w, h];
}

// One static SVG per round: same land path, same projection, same marker
// language (filled dot = birth, ring = death) as the live board, sized off
// the box rather than re-scaled every frame.
function miniMapSVG(fig) {
  if (!DATA.world || !fig || !fig.birth || fig.birth.lon == null) return '';
  const b = proj(fig.birth.lon, fig.birth.lat);
  const d = proj(fig.death.lon, fig.death.lat);
  const box = soloBox(b, d);
  const w = box[2];
  const r = w * 0.016;
  const up = b[1] <= d[1];
  const label = (pt, x, y, above) =>
    `<text class="mk-label" x="${(x + r * 2).toFixed(1)}" y="${(above ? y - r * 1.6 : y + r * 3.0).toFixed(1)}"`
    + ` font-size="${(w * 0.034).toFixed(2)}" stroke-width="${(w * 0.008).toFixed(2)}"`
    + ` text-anchor="start">${yearLabel(pt)}</text>`;
  return `<svg class="sol-map" viewBox="${box.map((v) => v.toFixed(2)).join(' ')}"
      role="img" aria-label="Born ${fig.birth.place}, died ${fig.death.place}">
    <rect x="-40" y="-40" width="1080" height="580" fill="var(--ch-cream)"></rect>
    <path class="map-land" d="${DATA.world.land}" fill-rule="evenodd"></path>
    <circle class="mk-dot mk-birth" cx="${b[0]}" cy="${b[1]}" r="${r.toFixed(2)}"></circle>
    <circle class="mk-ring mk-death-ring" cx="${d[0]}" cy="${d[1]}" r="${(r * 1.55).toFixed(2)}"
            fill="none" stroke="var(--ch-map-origin)" stroke-width="${(r * 0.55).toFixed(2)}"></circle>
    <circle class="mk-dot mk-death" cx="${d[0]}" cy="${d[1]}" r="${(r * 0.55).toFixed(2)}"></circle>
    ${label(fig.birth, b[0], b[1], up)}
    ${label(fig.death, d[0], d[1], !up)}
  </svg>`;
}

function renderSolution() {
  const wrap = $('#sum-solution');
  if (!wrap) return;
  if (!S.showSolution || !S.results || !S.results.length) {
    wrap.hidden = true;
    wrap.innerHTML = '';
    return;
  }
  wrap.innerHTML = '<p class="sum-solution-head">The answers</p>'
    + S.results.map((r) => {
      const fig = r.fig || {};
      return `<article class="sol-round">
        <span class="sol-pts${r.pts ? '' : ' zero'}">${r.pts ? '+' + r.pts : '0 pts'}</span>
        ${miniMapSVG(fig)}
        <div class="sol-body">
          <h3 class="sol-name">${fig.name || '(removed)'}</h3>
          ${fig.occupation ? `<p class="sol-meta">${fig.occupation}</p>` : ''}
          ${fig.fact ? `<p class="sol-blurb">${fig.fact}</p>` : ''}
        </div>
      </article>`;
    }).join('');
  wrap.hidden = false;
}

function finishSession() {
  if (S.done) {
    renderLockedSummary();
    show('view-mapsum');
    return;
  }
  S.done = true;
  sfx.play('stamp');

  if (S.mode === 'free') {
    const m = store.getMap();
    m.sessions = (m.sessions || 0) + 1;
    m.bestScore = Math.max(m.bestScore || 0, S.score);
    m.bestStreak = Math.max(m.bestStreak || 0, S.bestStreak);
    store.setMap(m);
  } else if (S.mode === 'daily') {
    daily.recordDailyCompletion('map', S.editionIndex, {
      score: S.score,
      detail: S.results.map((r) => ({ id: r.fig.id, pts: r.pts, correct: r.correct, hints: r.hints })),
    });
    track(`dur-map-${durationBucket(Date.now() - (S.startedAt || Date.now()))}`);
    S.locked = true;
  }
  // practice mode: no ledger, no best-score update — replayable, no trace.
  // Session dropped LAST, once the result is safely recorded (see the same
  // note in revealgame.js finishSession).
  S.store.clear();
  refreshHomeStats();

  renderLockedSummary();
  announce(`Run complete. Final score ${S.score} points.`);
  if (testHooksEnabled()) {
    window.__CHRONICLE_TEST__ = Object.assign(window.__CHRONICLE_TEST__ || {}, {
      mapSession: { score: S.score, results: S.results.map((r) => ({ id: r.fig.id, pts: r.pts, correct: r.correct })) },
    });
  }
  show('view-mapsum');
  // "A game finished" for the install flow — see the same note in
  // revealgame.js: dailies count (Encore is one now), free play does not.
  if (S.mode === 'daily') {
    document.dispatchEvent(new CustomEvent('gamefinished',
      { detail: { game: 'map', daily: true } }));
  }
}

// ---------- init ----------
export function initMapGame() {
  registerPool('map', DATA.figures);
  attachMapGestures();
  $('#map-start').addEventListener('click', startSession);
  $('#map-help').addEventListener('click', () => openIntroHelp('map'));

  $('#map-form').addEventListener('submit', (e) => {
    e.preventDefault();
    if (!S || !S.cur.open) return;
    const guess = $('#map-input').value.trim();
    if (!guess) return;
    if (!confirmFirstGuess('map', WRONG_COST, () => $('#map-form')
        .dispatchEvent(new Event('submit', { cancelable: true })))) return;
    if (S.fromShare) { S.fromShare = false; track('answer-from-share-map'); }
    if (isMatch(guess, round(), 'map')) {
      resolveRound(true);
    } else {
      S.cur.wrongs++;
      S.cur.wrongGuesses = S.cur.wrongGuesses || [];
      S.cur.wrongGuesses.push(guess);
      persistSession();
      addGuessChip(guess);
      updateWorth();
      // P1.5: announce every wrong guess politely; the explicit line shows
      // once — the first wrong guess anywhere (teachWrongGuess one-shots it).
      teachWrongGuess('map-wrong-note', `Not them — −${WRONG_COST}`,
        `Not them — −${WRONG_COST}. Worth ${worthNow()} points.`);
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
    if (rescueOpen()) return;   // the rescue closed the shop; the button is dead
    S.cur.hints++;
    S.cur.hintCost = (S.cur.hintCost || 0) + HINT_OCC_COST;
    S.cur.occUsed = true;
    revealClueInSlot($('#hint-occ'), round().occupation);
    persistSession();
    updateWorth();
    announce(`Claim to fame: ${round().occupation}. Worth ${worthNow()} points.`);
  });

  $('#hint-ini').addEventListener('click', () => {
    if (!S || !S.cur.open) return;
    if (rescueOpen()) return;   // the rescue closed the shop; the button is dead
    S.cur.hints++;
    S.cur.hintCost = (S.cur.hintCost || 0) + HINT_INI_COST;
    S.cur.iniUsed = true;
    revealClueInSlot($('#hint-ini'), `Initials: ${initials(round().name)}`);
    persistSession();
    updateWorth();
    announce(`Initials: ${initials(round().name)}. Worth ${worthNow()} points.`);
  });

  $('#map-mcq').addEventListener('click', openMcq);

  $('#map-next').addEventListener('click', () => {
    if (S.i === S.rounds.length - 1) { finishSession(); return; }
    S.i++;
    startRound();
  });

  $('#map-quit').addEventListener('click', () => {
    // Header back arrow: leave the session, same as every other game's back
    // button — it must not discard progress. The session is already persisted
    // continuously (persistSession runs after every hint/guess/round), so
    // just make sure the current state is saved, then go — reopening resumes
    // exactly here (see resumeFrom/renderMapStart).
    if (S && !S.done) persistSession();
    S = null;
    back();
  });

  $('#map-resume').addEventListener('click', resumeSession);

  $('#sum-back').addEventListener('click', goHome);
  $('#sum-again').addEventListener('click', () => {
    back();              // drop the summary from the view trail
    startSession();
  });
  $('#sum-home').addEventListener('click', goHome);
  const sumShareBtn = $('#sum-share');
  if (sumShareBtn) {
    sumShareBtn.addEventListener('click', async () => {
      if (!S || !S.share) return;
      const out = await shareResult(S.share);
      flashShareButton(sumShareBtn, out, 'Share the run');
    });
  }
}
