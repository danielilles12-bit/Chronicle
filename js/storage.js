// localStorage wrapper. All app state lives under one key.
const KEY = 'chronicle.v1';

function loadAll() {
  try { return JSON.parse(localStorage.getItem(KEY)) || {}; }
  catch (e) { return {}; }
}

function saveAll(d) {
  try { localStorage.setItem(KEY, JSON.stringify(d)); }
  catch (e) { /* storage full or private mode: play on without persistence */ }
}

export function getPuzzle(id) {
  const d = loadAll();
  return (d.puzzles && d.puzzles[id]) || null;
}

export function setPuzzle(id, state) {
  const d = loadAll();
  if (!d.puzzles) d.puzzles = {};
  d.puzzles[id] = state;
  saveAll(d);
}

export function getMap() {
  const d = loadAll();
  return d.map || { bestScore: 0, bestStreak: 0, sessions: 0 };
}

export function setMap(m) {
  const d = loadAll();
  d.map = m;
  saveAll(d);
}

export function getSession() {
  return loadAll().mapSession || null;
}

export function setSession(s) {
  const d = loadAll();
  d.mapSession = s;
  saveAll(d);
}

export function clearSession() {
  const d = loadAll();
  delete d.mapSession;
  saveAll(d);
}

// Zoom In keeps separate best-scores and in-progress sessions per mode
// ('who' = portraits, 'what' = artefacts), since they are now two games.
export function getReveal(mode = 'who') {
  const d = loadAll();
  return d['reveal_' + mode] || { bestScore: 0, bestStreak: 0, sessions: 0 };
}

export function setReveal(mode, r) {
  const d = loadAll();
  d['reveal_' + mode] = r;
  saveAll(d);
}

export function getRevealSession(mode = 'who') {
  return loadAll()['revealSession_' + mode] || null;
}

export function setRevealSession(mode, s) {
  const d = loadAll();
  d['revealSession_' + mode] = s;
  saveAll(d);
}

export function clearRevealSession(mode = 'who') {
  const d = loadAll();
  delete d['revealSession_' + mode];
  saveAll(d);
}

export function getMisc() {
  return loadAll().misc || {};
}

export function setMisc(patch) {
  const d = loadAll();
  d.misc = Object.assign(d.misc || {}, patch);
  saveAll(d);
}

export function getChrono() {
  const d = loadAll();
  return d.chrono || { bestScore: 0, sessions: 0 };
}
export function setChrono(c) { const d = loadAll(); d.chrono = c; saveAll(d); }
export function getChronoSession() { return loadAll().chronoSession || null; }
export function setChronoSession(s) { const d = loadAll(); d.chronoSession = s; saveAll(d); }
export function clearChronoSession() { const d = loadAll(); delete d.chronoSession; saveAll(d); }

export function getConn(id) {
  const d = loadAll();
  return (d.conns && d.conns[id]) || null;
}
export function setConn(id, state) {
  const d = loadAll();
  if (!d.conns) d.conns = {};
  d.conns[id] = state;
  saveAll(d);
}
export function getConnStats() {
  return loadAll().connStats || { solved: 0 };
}
export function setConnStats(s) { const d = loadAll(); d.connStats = s; saveAll(d); }
