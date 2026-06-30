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

export function getReveal() {
  const d = loadAll();
  return d.reveal || { bestScore: 0, bestStreak: 0, sessions: 0 };
}

export function setReveal(r) {
  const d = loadAll();
  d.reveal = r;
  saveAll(d);
}

export function getRevealSession() {
  return loadAll().revealSession || null;
}

export function setRevealSession(s) {
  const d = loadAll();
  d.revealSession = s;
  saveAll(d);
}

export function clearRevealSession() {
  const d = loadAll();
  delete d.revealSession;
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
