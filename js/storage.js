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

// ---------- Chronicle Daily ----------
// A generic namespaced-session store used by every game's daily AND practice
// modes (js/daily.js picks the items; each game engine just needs somewhere
// to persist an in-progress attempt keyed by a string it controls, e.g.
// `chronicle.daily.map.42` or `chronicle.practice.who.17`). This mirrors the
// existing per-game session shapes (mapSession, revealSession_*) but
// namespaced so a daily/practice run never collides with a free session.
export function getDailySession(key) {
  const d = loadAll();
  return (d.dailySessions && d.dailySessions[key]) || null;
}
export function setDailySession(key, state) {
  const d = loadAll();
  if (!d.dailySessions) d.dailySessions = {};
  d.dailySessions[key] = state;
  saveAll(d);
}
export function clearDailySession(key) {
  const d = loadAll();
  if (d.dailySessions) delete d.dailySessions[key];
  saveAll(d);
}

// The ledger: one completion record per (game, editionIndex), plus per-game
// streaks and the cross-game "full house" streak. Kept as one small object
// so daily.js's pure streak math (nextStreak) can read/write it in one place.
const LEDGER_KEY = 'dailyLedger';
const emptyLedger = () => ({
  entries: {},   // entries[game][editionIndex] = { score, completedOn, detail }
  streaks: {},   // streaks[game] = { streak, lastEdition }
  fullHouse: { streak: 0, lastEdition: -Infinity },
});

export function getDailyLedger() {
  const d = loadAll();
  return d[LEDGER_KEY] || emptyLedger();
}

export function setDailyLedger(ledger) {
  const d = loadAll();
  d[LEDGER_KEY] = ledger;
  saveAll(d);
}

export function getDailyEntry(game, editionIndex) {
  const l = getDailyLedger();
  return (l.entries[game] && l.entries[game][editionIndex]) || null;
}
