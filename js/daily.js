// Chronicle Daily engine — pure functions of the calendar date and the data
// files. No RNG, no storage reads for selection: the same (game, edition)
// pair always yields the same items, forever (mod pool growth via append).
//
// "Edition n" is the nth calendar day since EPOCH (a Monday). Every player
// on Earth gets the same edition on the same local date (Wordle convention).
import { DATA } from './app.js';
import * as store from './storage.js';
import { track } from './track.js';

// ---------- config ----------
export const EPOCH = new Date(2026, 5, 29); // 2026-06-29, a Monday (local, month is 0-based)
// Only a week of future editions is previewable in the archive — the unaired
// run must not be browsable in production ("same issue as everyone else").
// For QA browsing of the full run, use a local server with this raised.
export const ARCHIVE_PREVIEW_EDITIONS = 7;

// Rounds games (Lifeline, Face Value, Relic): 10 rounds/day, [easy, medium, hard]
// counts per weekday (0=Mon...6=Sun). Ordered within an edition: E, then M, then H.
export const RECIPE = [
  [7, 2, 1], // Mon
  [6, 3, 1], // Tue
  [5, 3, 2], // Wed
  [4, 4, 2], // Thu
  [3, 4, 3], // Fri
  [2, 4, 4], // Sat
  [1, 4, 5], // Sun
];
const TIERS = ['easy', 'medium', 'hard'];

// Thread: 1 board/day, tier by weekday.
export const THREAD_TIER = ['easy', 'easy', 'medium', 'medium', 'hard', 'hard', 'hard'];

const WEEKDAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

const MS_PER_DAY = 86400000;

// ---------- clock ----------
// Injectable "today" for testing/curation: ?dailydate=YYYY-MM-DD overrides
// the device clock. Always resolved against the device's LOCAL date.
function localMidnight(d) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

function testDateOverride() {
  const m = (typeof location !== 'undefined' ? location.search : '').match(/[?&]dailydate=(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  return new Date(+m[1], +m[2] - 1, +m[3]);
}

export function todayDate() {
  return testDateOverride() || new Date();
}

export function editionIndex(date) {
  return Math.floor((localMidnight(date) - localMidnight(EPOCH)) / MS_PER_DAY);
}

// Inverse of editionIndex: the local calendar date edition n airs on.
export function editionDate(n) {
  return new Date(EPOCH.getFullYear(), EPOCH.getMonth(), EPOCH.getDate() + n);
}

export function todayIndex() {
  return editionIndex(todayDate());
}

export function weekday(n) {
  // JS % can return negative for n < 0; editions before EPOCH aren't a real
  // case here, but keep this correct regardless.
  return ((n % 7) + 7) % 7;
}

export function weekdayName(n) {
  return WEEKDAY_NAMES[weekday(n)];
}

export function editionLabel(n) {
  return `№ ${n} · ${weekdayName(n)}`;
}

// ---------- difficulty whisper (Card #6) ----------
// Mon (gentlest) -> Sun (hardest), keyed by weekday() (0=Mon..6=Sun). Mirrors
// the RECIPE's Mon->Sun climb without being tied to any one game's numbers —
// it's a single site-wide flavour line, not a stat.
const WHISPER_LADDER = [
  'a kind one.',     // Mon
  'warming up.',     // Tue
  'fair game.',      // Wed
  'stiffening.',     // Thu
  'a proper test.',  // Fri
  'hard going.',     // Sat
  'a stinker.',      // Sun
];

export function weekdayWhisper(n) {
  return WHISPER_LADDER[weekday(n)];
}

// Weekend-only receipt nod: null Mon-Fri (the whisper stays a whisper — see
// brief card #6). Sat/Sun editions get one extra meta-line on their receipts.
export function weekendReceiptMeta(n) {
  const wd = weekday(n);
  if (wd === 5) return `Saturday — ${WHISPER_LADDER[5]}`;
  if (wd === 6) return `Sunday — ${WHISPER_LADDER[6]}`;
  return null;
}

// ---------- cursor arithmetic ----------
const WEEKLY_TOTAL = TIERS.map((_, i) => RECIPE.reduce((s, r) => s + r[i], 0)); // [28, 24, 18]
const THREAD_WEEKLY = { easy: 0, medium: 0, hard: 0 };
THREAD_TIER.forEach((t) => { THREAD_WEEKLY[t]++; });

// Total items of `tier` consumed by editions 0..n-1, for a rounds-game.
function roundsCursor(tier, n) {
  const ti = TIERS.indexOf(tier);
  if (n <= 0) return 0;
  const weeks = Math.floor(n / 7);
  const rem = n % 7;
  let total = weeks * WEEKLY_TOTAL[ti];
  for (let k = 0; k < rem; k++) total += RECIPE[weekday(k)][ti]; // editions 0..rem-1 (weekday cycle repeats every 7)
  return total;
}

// Total Thread boards of `tier` consumed by editions 0..n-1.
function threadCursor(tier, n) {
  if (n <= 0) return 0;
  const weeks = Math.floor(n / 7);
  const rem = n % 7;
  let total = weeks * THREAD_WEEKLY[tier];
  for (let k = 0; k < rem; k++) if (THREAD_TIER[weekday(k)] === tier) total++;
  return total;
}

// ---------- pool selection (deterministic, no shuffle) ----------
// Take `count` items starting at `start` (mod pool.length), wrapping.
// Never returns duplicates from a pool at least as large as `count`.
function takeWrapped(pool, start, count) {
  const len = pool.length;
  if (len === 0 || count <= 0) return [];
  const n = Math.min(count, len);
  const out = [];
  for (let i = 0; i < n; i++) out.push(pool[(start + i) % len]);
  return out;
}

// Pick `count` items of `tier` from `poolByTier`'s primary pool only (no
// backfill yet). The cursor/wrap index is always taken against the tier's
// full canonical pool, so it stays in sync across editions regardless of
// what any other tier does — this is the piece that must never be filtered
// by cross-tier usage.
function pickTierPrimary(poolByTier, tier, count, cursorFor) {
  const pool = poolByTier[tier] || [];
  const start = cursorFor(tier);
  return takeWrapped(pool, start, count);
}

// Backfill tier's shortfall from the adjacent tier (medium backfills
// easy/hard; easy backfills medium), skipping any id already handed out
// anywhere else in this edition — including ids the lender tier itself
// already legitimately used for its own quota. Backfill has no cursor of
// its own (it's an overflow path for tiny pools); it just walks the lender
// pool in array order.
function backfillTier(poolByTier, tier, shortfall, usedGlobal) {
  const backfillTier_ = tier === 'hard' ? 'medium' : tier === 'easy' ? 'medium' : 'easy';
  const backfillPool = (poolByTier[backfillTier_] || []).filter((x) => !usedGlobal.has(x.id));
  return backfillPool.slice(0, shortfall);
}

function byTier(items) {
  const out = { easy: [], medium: [], hard: [] };
  for (const it of items) if (out[it.difficulty]) out[it.difficulty].push(it);
  return out;
}

function poolFor(game) {
  if (game === 'map') return DATA.figures || [];
  if (game === 'who') return (DATA.reveal || []).filter((x) => x.kind === 'portrait');
  if (game === 'what') return (DATA.reveal || []).filter((x) => x.kind !== 'portrait');
  if (game === 'thread') return DATA.connections || [];
  return [];
}

// getEdition(game, n) -> ordered list of item objects for that edition.
// game: 'map' | 'who' | 'what' | 'thread'
// For 'thread' the return is a 1-element array [board] (kept as an array for
// a uniform call shape across games).
export function getEdition(game, n) {
  const items = poolFor(game);
  if (game === 'thread') {
    const tier = THREAD_TIER[weekday(n)];
    const pool = items.filter((x) => x.difficulty === tier);
    if (!pool.length) return [];
    const cursor = threadCursor(tier, n);
    return takeWrapped(pool, cursor % pool.length, 1);
  }
  const poolByTier = byTier(items);
  const counts = RECIPE[weekday(n)];
  const cursorFor = (t) => {
    const len = (poolByTier[t] || []).length;
    return len ? roundsCursor(t, n) % len : 0;
  };

  // Pass 1: every tier's primary selection, all against untouched canonical
  // pools (so cursors never depend on what another tier did this edition).
  const byTierPicks = {};
  const usedGlobal = new Set();
  TIERS.forEach((tier, i) => {
    const count = counts[i];
    const picks = count > 0 ? pickTierPrimary(poolByTier, tier, count, cursorFor) : [];
    byTierPicks[tier] = picks;
    picks.forEach((p) => usedGlobal.add(p.id));
  });

  // Pass 2: backfill any tier that came up short, now that every tier's
  // legitimate primary usage (including the lender's own) is known.
  TIERS.forEach((tier, i) => {
    const count = counts[i];
    if (count <= 0) return;
    const shortfall = count - byTierPicks[tier].length;
    if (shortfall > 0) {
      const extra = backfillTier(poolByTier, tier, shortfall, usedGlobal);
      extra.forEach((p) => usedGlobal.add(p.id));
      byTierPicks[tier] = byTierPicks[tier].concat(extra);
    }
  });

  const out = [];
  TIERS.forEach((tier) => out.push(...byTierPicks[tier]));
  return out;
}

export function editionThreadTier(n) {
  return THREAD_TIER[weekday(n)];
}

export function editionRecipe(n) {
  return RECIPE[weekday(n)];
}

// ---------- ledger ----------
// One compact record per (game, editionIndex) plus per-game and full-house
// streaks. Storage access lives in storage.js; daily.js only computes what
// goes into it so the streak rule is defined in one place and unit-testable
// without the DOM/localStorage.
// Order = home presentation order AND "turn the page" flow order (keep in
// sync with GAME_ROWS in app.js): Face Value, Lifeline, Relic, Thread.
const GAMES = ['who', 'map', 'what', 'thread'];

// Streak-valid rule ("the press window", Daniel's kinder call 2026-07-10):
// a completion counts toward streaks if it happened within TWO days of the
// air date — on the day, the day after, or the day after that. Day two is
// the REPAIR window: a missed Tuesday no longer kills the run, as long as
// Tuesday's issue is completed from the archive by Thursday. Later archive
// completions still write the entry (tile shows Done) but never count.
export function isStreakValid(airDate, completedOnEditionIndex) {
  return completedOnEditionIndex <= airDate + 2;
}

// Streaks are DERIVED from the entry record, never incremented: find the
// most recent edition that still counts (today, or one still inside the
// repair window), then walk backwards over consecutive valid editions.
// Order-independent by construction — healing a hole from the archive fixes
// the count no matter what order entries were written in.
export function derivedStreak(validAt, today) {
  let anchor = -1;
  for (let e = today; e >= today - 2; e--) {
    if (validAt(e)) { anchor = e; break; }
  }
  if (anchor < 0) return { streak: 0, lastEdition: -Infinity };
  let n = 0;
  while (validAt(anchor - n)) n++;
  return { streak: n, lastEdition: anchor };
}

// Record a daily completion: one immutable entry per (game, edition), then
// recompute the per-game and full-house streaks from the record. A streak is
// only truly dead once its first missed edition is past the repair window —
// the obituary check in app.js uses lastEdition <= today - 4 accordingly.
export function recordDailyCompletion(game, editionIndex, detail) {
  const ledger = store.getDailyLedger();
  const completedOn = todayIndex();
  if (!ledger.entries[game]) ledger.entries[game] = {};
  // Already recorded (e.g. re-entering a locked, completed daily): no-op,
  // never overwrite the original completedOn/score.
  if (ledger.entries[game][editionIndex]) return ledger;

  ledger.entries[game][editionIndex] = { completedOn, ...detail };

  const gameValid = (g) => (e) => {
    const en = ledger.entries[g] && ledger.entries[g][e];
    return !!en && isStreakValid(e, en.completedOn);
  };
  GAMES.forEach((g) => { ledger.streaks[g] = derivedStreak(gameValid(g), completedOn); });
  const allValid = (e) => GAMES.every((g) => gameValid(g)(e));
  ledger.fullHouse = derivedStreak(allValid, completedOn);

  store.setDailyLedger(ledger);
  track(`finish-${game}`);
  if (GAMES.every((g) => ledger.entries[g] && ledger.entries[g][editionIndex])) track('finish-day');
  return ledger;
}

// One session's score on the 0–100 dial: the average round worth, capped so
// streak bonuses lift weak rounds without pushing a day past a perfect 100.
// Robust to any round count — 5, 7 or 10 rounds all read on the same dial.
export function sessionScore(results) {
  if (!results || !results.length) return 0;
  const sum = results.reduce((a, r) => a + (r.pts || 0), 0);
  return Math.min(100, Math.round(sum / results.length));
}

// One-time migration (v113 scoring rebase): older rounds-game entries stored
// the SUM of ten rounds (up to ~1090); rebased entries store the capped round
// average. Rescale old entries so the Ledger and day totals read on one dial.
export function normalizeLedgerScales() {
  const ledger = store.getDailyLedger();
  let changed = false;
  for (const g of ['map', 'who', 'what']) {
    const entries = ledger.entries[g] || {};
    for (const k of Object.keys(entries)) {
      const en = entries[k];
      if (en && en.score > 100) {
        en.score = en.detail && en.detail.length
          ? sessionScore(en.detail)
          : Math.min(100, Math.round(en.score / 10));
        changed = true;
      }
    }
  }
  if (changed) store.setDailyLedger(ledger);
}

// Tiny per-game session-key + status helpers shared by every game's daily
// wiring, so mapgame.js/revealgame.js/connectionsgame.js don't each reinvent
// the naming scheme.
export function dailyKey(game, editionIndex) {
  return `chronicle.daily.${game}.${editionIndex}`;
}
export function practiceKey(game, editionIndex) {
  return `chronicle.practice.${game}.${editionIndex}`;
}

// 'done' | 'in-progress' | 'not-started', for the Today strip tiles.
export function dailyStatus(game, editionIndex) {
  const entry = store.getDailyEntry(game, editionIndex);
  if (entry) return 'done';
  const session = store.getDailySession(dailyKey(game, editionIndex));
  return session ? 'in-progress' : 'not-started';
}

export { GAMES };
