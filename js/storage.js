// localStorage wrapper. All app state lives under one key, with a rolling
// one-step backup (P2.3): every save first files the previous good
// serialisation under BACKUP_KEY, so one corrupted blob never wipes a player.
import { track } from './track.js';

const KEY = 'chronicle.v1';
const BACKUP_KEY = 'chronicle.v1.backup';
// 2 = the first stamped schema. A blob without schemaVersion is valid v1
// data with the same structure — it's stamped on load and carried on.
const SCHEMA_VERSION = 2;

// The most recent serialisation known to parse; becomes the backup on the
// next save. Seeded by the first successful load of the session.
let lastGoodSerial = null;
let recoveryTracked = false;   // one recovered/lost beacon per session
let saveToastShown = false;    // the "not saving" notice shows once

// Did the LAST loadAll fail to even read the key? Distinct from "nothing is
// stored": a throwing localStorage (Safari with site data blocked, a locked
// or corrupt WebKit storage database, a private-mode edge) makes loadAll
// return {} — which looks identical to a brand-new device. Every setter is
// read-modify-write, so without this flag the very next save would file that
// empty {} over a perfectly good blob and the player's whole history would be
// gone, with the backup never consulted again (the new blob parses fine, so
// the heal path below never triggers). Set on every load, read by saveAll.
let readFailed = false;

// null = nothing stored (fresh device); undefined = stored but unreadable.
function parseBlob(raw) {
  if (raw == null) return null;
  try {
    const d = JSON.parse(raw);
    return d && typeof d === 'object' && !Array.isArray(d) ? d : undefined;
  } catch (e) { return undefined; }
}

function loadAll() {
  let raw = null;
  try {
    raw = localStorage.getItem(KEY);
    readFailed = false;
  } catch (e) {
    readFailed = true;
    return {};
  }
  let d = parseBlob(raw);
  if (d === null) return {};           // fresh device: nothing saved yet
  if (d === undefined) {
    // Main blob corrupt: fall back to the backup copy, and heal main from it
    // so the very next save doesn't file the corrupt bytes as "previous good".
    let backupRaw = null;
    try { backupRaw = localStorage.getItem(BACKUP_KEY); } catch (e) { /* read-only storage */ }
    const b = parseBlob(backupRaw);
    if (b) {
      if (!recoveryTracked) { recoveryTracked = true; track('err-save-recovered'); }
      lastGoodSerial = backupRaw;
      try { localStorage.setItem(KEY, backupRaw); } catch (e) { /* heal when possible */ }
      d = b;
    } else {
      if (!recoveryTracked) { recoveryTracked = true; track('err-save-lost'); }
      return {};                       // both copies unreadable: start fresh
    }
  } else {
    lastGoodSerial = raw;
  }
  // Migration: a pre-P2.3 blob is valid v1 data — stamp it and continue
  // (persisted by the next save; no structural change needed).
  if (!d.schemaVersion) d.schemaVersion = SCHEMA_VERSION;
  return d;
}

function saveAll(d) {
  // Refuse to write on top of state we could not read (see `readFailed`).
  // Every setter calls loadAll() immediately before this, so the flag always
  // describes THIS operation: a transient failure costs one unsaved change
  // and the next interaction re-reads and carries on, instead of costing the
  // player everything they have ever played.
  if (readFailed) { showSaveFailureToast(); return; }
  d.schemaVersion = SCHEMA_VERSION;
  let next;
  try { next = JSON.stringify(d); } catch (e) { showSaveFailureToast(); return; }
  // Backup BEFORE overwriting main: if this write corrupts or half-lands,
  // the previous good state is one key away. Its own try/catch, because the
  // backup is a nicety and the main write is the point — when storage is at
  // quota the backup write is the one most likely to be refused (it is the
  // write that ADDS bytes; overwriting main usually does not), and sharing a
  // try block let a refused backup skip the main write entirely, turning a
  // near-full disk into "nothing this player does is ever saved again".
  try {
    if (lastGoodSerial) localStorage.setItem(BACKUP_KEY, lastGoodSerial);
  } catch (e) { /* no backup this round; the main write still matters */ }
  try {
    localStorage.setItem(KEY, next);
    lastGoodSerial = next;
  } catch (e) {
    // Storage full or private mode: play on without persistence, but say so
    // once — a silent non-save is how streaks quietly die.
    showSaveFailureToast();
  }
}

// One-time dismissible notice that saves aren't sticking (P2.3). Built here
// rather than index.html because storage is the only module that can know;
// styled by .df-save-toast in css/style.css.
function showSaveFailureToast() {
  if (saveToastShown) return;
  saveToastShown = true;
  track('err-save');
  if (!document.body) return;
  const toast = document.createElement('div');
  toast.className = 'df-save-toast';
  toast.setAttribute('role', 'status');
  const msg = document.createElement('span');
  msg.textContent = 'Your progress may not be saving on this device';
  const close = document.createElement('button');
  close.type = 'button';
  close.className = 'df-save-toast-close';
  close.setAttribute('aria-label', 'Dismiss');
  close.textContent = '×';
  close.addEventListener('click', () => toast.remove());
  toast.appendChild(msg);
  toast.appendChild(close);
  document.body.appendChild(toast);
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

// P5.1: every in-progress daily session's key, for app.js's boot-time
// abandoned-daily check — the one caller that needs to enumerate rather than
// address a single session it already knows the key for.
export function getDailySessionKeys() {
  return Object.keys(loadAll().dailySessions || {});
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

// Always hands back a ledger with all three branches present. A blob that
// half-survived a crashed write (or an older/foreign shape) would otherwise
// make recordDailyCompletion throw on `ledger.streaks[g] = ...` AFTER it had
// already built the new entry in memory but BEFORE store.setDailyLedger ran —
// so the finished daily would vanish and the game's summary screen would die
// with it. Cheap to normalise, and it can only ever add missing branches.
export function getDailyLedger() {
  const d = loadAll();
  const l = d[LEDGER_KEY];
  if (!l || typeof l !== 'object' || Array.isArray(l)) return emptyLedger();
  if (!l.entries || typeof l.entries !== 'object') l.entries = {};
  if (!l.streaks || typeof l.streaks !== 'object') l.streaks = {};
  if (!l.fullHouse || typeof l.fullHouse !== 'object') {
    l.fullHouse = { streak: 0, lastEdition: -Infinity };
  }
  return l;
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
