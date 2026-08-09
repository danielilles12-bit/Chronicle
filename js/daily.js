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

// The first edition the compiled manifest is responsible for — the same
// number as recipeChangeEdition in data/editions.json. It is written out here
// because the one moment it matters is the moment that file did NOT load, and
// a number read from a missing file is no number at all. If the manifest's
// own recipeChangeEdition ever moves, move this with it.
export const MANIFEST_ERA_START = 24;

// LEGACY recipe — rounds games (Lifeline, Face Value, Relic) at 10 rounds/day,
// [easy, medium, hard] counts per weekday (0=Mon...6=Sun), ordered E, M, H.
// Editions >= recipeChangeEdition come from the manifest (getEdition below):
// 5 rounds/day from edition 24, then 3 rounds/day (one easy, one medium, one
// hard — the 28 Jul 2026 recipe) from edition 30. The client never needs
// those counts — it renders however many ids the manifest carries — so this
// arithmetic serves only pre-manifest history and the approved-but-missing
// edition emergency, and its numbers must NEVER change.
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

// The LOCAL calendar day, expressed as a DST-free day number. Reading the
// date's local Y/M/D and re-stamping them as if UTC makes the difference
// between any two of these an exact multiple of 86400000 — a real local
// midnight timestamp is not, because a DST shift makes one local day 23 or
// 25 hours long. Using real timestamps, a player whose UTC offset is LARGER
// today than it was on EPOCH day (any southern-hemisphere summer, e.g.
// Sydney from October) lands one hour short of a whole day and Math.floor
// takes their edition index back a day — they'd be served yesterday's issue
// for months, and one edition would appear to repeat at the transition,
// which reads exactly like "my streak stopped counting".
function localMidnight(d) {
  return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate());
}

// Dev-only gate for the ?dailydate= override below: true only for local/
// offline serving (localhost, 127.0.0.1, an empty hostname, or a direct
// file:// open), never for the real deployed host. This is what makes the
// override safe to leave in shipped code — yesternerd.app's hostname can
// never match, so no query string on the production site can ever change
// which edition is shown, regardless of what a real player types in the URL.
function devHostAllowed() {
  if (typeof location === 'undefined') return false;
  const h = location.hostname;
  return h === 'localhost' || h === '127.0.0.1' || h === '' || location.protocol === 'file:';
}

function testDateOverride() {
  if (!devHostAllowed()) return null;
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

// THE DATE IS THE NAME OF THE DAY (Daniel, 9 Aug 2026). The issue number
// used to head the masthead, every game card, every receipt, the letters
// stamp and every share — and playtesters simply did not know what "№ 71"
// meant. The edition index is still the app's internal spine; it just never
// faces a player any more. "9 Aug 2026" — day, short month, full year.
const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function editionDateLabel(n) {
  const d = editionDate(Math.max(0, n));
  // Two-digit year with a typographic apostrophe (Daniel, 9 Aug 2026):
  // "9 Aug 2026 // SUNDAY" wrapped to two lines on any phone narrower than
  // ~400px and left the "//" dangling at the end of line one. "9 Aug ’26"
  // holds one line down to 320px, and the year is the least useful part of a
  // daily game's dateline anyway. One format everywhere — masthead, receipts,
  // letters stamp, Ledger, day-done and every share — so no two surfaces
  // write the same day differently.
  const yy = String(d.getFullYear()).slice(-2);
  return `${d.getDate()} ${MONTH_NAMES[d.getMonth()]} \u2019${yy}`;
}

export function editionLabel(n) {
  return `${editionDateLabel(n)} · ${weekdayName(n)}`;
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

// ---------- manifest-driven selection (Session 3) ----------
// data/editions.json is the compiled manifest (tools/compile_editions.py):
// exact item ids per game per edition. Aired editions are frozen there
// forever, new ones arrive via propose/approve. When the manifest holds an
// edition it always wins — a frozen edition stays identical even if the pool
// files are later reordered. The cursor arithmetic below remains for two
// jobs: history (editions the manifest might not carry, n < recipeChangeEdition)
// and the emergency (an edition past the switch that was never approved).
//
// What it must NOT do is stand in for a manifest that never arrived: the
// arithmetic is the old ten-round recipe against the raw pools, so it would
// invent a different, unapproved issue — one that can hold items no edition
// has aired yet — and hand it out as today's, into the ledger, the streak and
// the share card. A lost file is a failure to report, not a schedule to
// improvise around; see manifestReady below.
let manifestMissTracked = false;

function manifestEdition(game, n) {
  const man = DATA.editions;
  const ed = man && man.editions && man.editions[n];
  const ids = ed && ed[game];
  if (!ids || !ids.length) return null;
  const byId = new Map(poolFor(game).map((x) => [x.id, x]));
  const items = ids.map((id) => byId.get(id)).filter(Boolean);
  return items.length ? items : null;   // ids that resolve to nothing = treat as missing
}

// Fired (once per session) when an edition that SHOULD be manifest-served is
// not: either the manifest file never loaded, or n is past the recipe switch
// and its edition was never approved. Legacy-era editions falling back to
// arithmetic are normal, not an emergency.
function trackManifestMiss(n) {
  const man = DATA.editions;
  if (man && n < man.recipeChangeEdition) return;
  if (manifestMissTracked) return;
  manifestMissTracked = true;
  track('err-manifest-missing');
}

// Can edition n be built at all right now? False in exactly one case: the
// manifest file is not loaded and n is one of the editions it owns. Launch
// paths ask this BEFORE opening a game, so a lost manifest surfaces as the
// same "couldn't load — tap to retry" any lost pool file already shows
// (ensureEdition in app.js) rather than as an empty or invented round list.
export function manifestReady(n) {
  return !!DATA.editions || n < MANIFEST_ERA_START;
}

// getEdition(game, n) -> ordered list of item objects for that edition.
// game: 'map' | 'who' | 'what' | 'thread'
// For 'thread' the return is a 1-element array [board] (kept as an array for
// a uniform call shape across games).
// Empty means "cannot be built" — never "here is a substitute".
export function getEdition(game, n) {
  const fromManifest = manifestEdition(game, n);
  if (fromManifest) return fromManifest;
  trackManifestMiss(n);
  // No manifest and no arithmetic licence: refuse rather than improvise.
  // Note this is only the MISSING-FILE case. A manifest that loaded but has
  // no entry for n is a curation gap, not a lost file, and keeps its existing
  // emergency fallback below.
  if (!manifestReady(n)) return [];
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

// ---------- the Archive window (Daniel, 7 Aug 2026) ----------
// Locked decision #4, tightened. What a player can reach at any moment is
// today's edition plus the SIX editions before it, with a hard floor at the
// launch edition. The calendar Morgue and its trailing-7 window are gone;
// these three functions are now the only definition of "reachable".
//
// Why six and not more: content repeats on a 28–42 day gap (locked decision
// #5), so a deeper archive would start showing material already scheduled to
// come back. Why a floor: editions 24–41 aired before launch day and are not
// launch quality — no player should ever be handed one.
//
// ARCHIVE_FLOOR is 42 because edition n airs on EPOCH + n days, and
// 2026-06-29 + 42 days = 2026-08-10, launch day (a Monday, like EPOCH).
// Verified against editionIndex/editionDate by tests/test_archive_window.py.
export const ARCHIVE_FLOOR = 42;
export const ARCHIVE_SPAN = 6;

// Oldest / newest reachable ARCHIVE edition for a given today. The window is
// empty (first > last) on launch day itself, which is exactly right: there is
// no back issue on the first day.
export function archiveFirst(today) {
  return Math.max(ARCHIVE_FLOOR, today - ARCHIVE_SPAN);
}
export function archiveLast(today) {
  return today - 1;
}

// The reachable archive editions, NEWEST FIRST — the order the day cards are
// laid out in on Home. Empty array when nothing is reachable.
export function archiveEditions(today) {
  const first = archiveFirst(today);
  const out = [];
  for (let n = archiveLast(today); n >= first; n--) out.push(n);
  return out;
}

// THE HARD ACCESS GUARD (spec §4). Every path that opens a daily asks this
// first — not just the ones that render a card. A stale card tapped after a
// midnight rollover, a hand-typed URL, or a double-tap mid-rollover must all
// fail closed, because a "yes" here on an edition past today would hand a
// player unaired content (CLAUDE.md: no casual path may reach it).
//
// Today is always playable, even before the floor (a QA date, or the days
// between the epoch and launch): the floor governs the ARCHIVE, never the
// issue of the day.
export function canPlayEdition(n, today) {
  const t = today == null ? todayIndex() : today;
  if (!Number.isInteger(n) || n < 0) return false;
  if (n === t) return true;
  return n >= archiveFirst(t) && n <= archiveLast(t);
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

// ---------- the SHOWED-UP streak (locked decision #2, displayed 7 Aug 2026) ----------
// Locked decision #2 says finishing any ONE of the four games keeps the run
// alive; all four is a full house — prestige, never the minimum. The ledger
// always honoured that in the data, but every surface on screen read the
// FULL-HOUSE number, so the faithful one-game-a-morning player was shown an
// empty week forever. These helpers are what the display reads now.
//
// Nothing about the RULES moved: isStreakValid (the two-day repair window) and
// derivedStreak are untouched, and the predicate below is simply
// "any one game counts" instead of "all four". Because streaks are DERIVED
// from the completion records rather than incremented, no migration is needed —
// an existing player's number becomes correct on their next load, and it will
// mostly go UP.

// Is this game's entry for edition e both present and inside the window?
function entryValidIn(entries, g) {
  return (e) => {
    const en = entries[g] && entries[g][e];
    return !!en && isStreakValid(e, en.completedOn);
  };
}

// The one predicate the whole display hangs off: did the player show up for
// edition e — any one of the four games, completed inside the window?
// Score is irrelevant: closing the issue counts even with losses (decision #2).
export function showedUpAt(e, ledgerEntries) {
  const entries = ledgerEntries || store.getDailyLedger().entries || {};
  return GAMES.some((g) => entryValidIn(entries, g)(e));
}

// All four, same window. The punch card's richer mark — the same punch, plus
// the gold token — so a full house reads as part of one continuous run rather
// than a separate achievement sitting alongside it.
export function fullHouseAt(e, ledgerEntries) {
  const entries = ledgerEntries || store.getDailyLedger().entries || {};
  return GAMES.every((g) => entryValidIn(entries, g)(e));
}

// The live showed-up streak: derivedStreak with the "any one game" predicate.
// Same walk, same anchor, same two-day reach — only the predicate is kinder.
export function showedUpStreak(today) {
  const t = today == null ? todayIndex() : today;
  const entries = store.getDailyLedger().entries || {};
  return derivedStreak((e) => showedUpAt(e, entries), t);
}

// The showed-up run as it STOOD, whether or not it is still alive. The
// obituary needs this: derivedStreak reports 0 the moment a run is beyond
// repair, which is exactly the moment the wake is held, so the wake would have
// nothing to bury. It used to read the frozen ledger.fullHouse cache instead;
// deriving it means it is right for players who never completed anything since
// this shipped, with no migration.
export function lastShowedUpRun(today) {
  const t = today == null ? todayIndex() : today;
  const entries = store.getDailyLedger().entries || {};
  const valid = (e) => showedUpAt(e, entries);
  let last = -Infinity;
  GAMES.forEach((g) => {
    Object.keys(entries[g] || {}).forEach((k) => {
      const e = +k;
      if (Number.isFinite(e) && e <= t && e > last && valid(e)) last = e;
    });
  });
  if (!Number.isFinite(last)) return { streak: 0, lastEdition: -Infinity };
  let n = 0;
  while (valid(last - n)) n++;
  return { streak: n, lastEdition: last };
}

// ---------- the repair window, made visible (7 Aug 2026) ----------
// isStreakValid has always let a missed Tuesday be healed by finishing it from
// the archive by Thursday. Nothing on screen ever said so, so a kind mechanic
// did no work at all. This finds the one day worth telling the player about,
// or null — and Home shows a quiet strip only when it returns something.
//
// All four conditions the strip needs live here, in one place:
//   1. an edition still inside the two-day window has NO completed game;
//   2. it is genuinely repairable — reachable through the Archive window, so
//      canPlayEdition would actually open it (the launch path's own guard);
//   3. there is a real run at stake (see `rescued` below);
//   4. it has not already been repaired — a completed game makes showedUpAt
//      true, and this returns null again by itself. No dismiss control, no
//      stored flag: it expires on its own.
//
// Oldest first, because the older gap is the one that expires tonight.
//
// `rescued` is the run the player would have AFTER repairing — simulated by
// running the existing derivedStreak over a predicate with that one day filled
// in. That, not the currently-visible number, is what is at stake: a gap two
// days back has already dragged the live streak down to 0 or 1, so gating on
// the live number would hide the strip in precisely the case it exists for.
export function repairOpportunity(today) {
  const t = today == null ? todayIndex() : today;
  const entries = store.getDailyLedger().entries || {};
  const valid = (e) => showedUpAt(e, entries);
  const current = derivedStreak(valid, t).streak;
  for (let e = t - 2; e <= t - 1; e++) {
    if (e < 0 || valid(e)) continue;                 // played already (or repaired)
    if (!canPlayEdition(e, t)) continue;             // outside the Archive window
    const rescued = derivedStreak((x) => (x === e ? true : valid(x)), t).streak;
    // A run worth saving, and saving it has to actually change something.
    if (rescued < 3 || rescued <= current) continue;
    return { edition: e, rescued, lastDay: e + 2 === t };
  }
  return null;
}

// Record a daily completion: one immutable entry per (game, edition), then
// recompute the showed-up, per-game and full-house streaks from the record. A
// streak is only truly dead once its first missed edition is past the repair
// window — the obituary check in app.js uses lastEdition <= today - 4
// accordingly.
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
  // The number the display reads. Cached alongside the other two so the stored
  // ledger describes itself; every SURFACE derives it live (showedUpStreak),
  // which is what makes this migration-free for players already on a run.
  const anyValid = (e) => GAMES.some((g) => gameValid(g)(e));
  ledger.showedUp = derivedStreak(anyValid, completedOn);

  store.setDailyLedger(ledger);
  track(`finish-${game}`);
  if (GAMES.every((g) => ledger.entries[g] && ledger.entries[g][editionIndex])) track('finish-day');
  trackRitualWeek(completedOn);
  return ledger;
}

// P5.1: "showed up" already governs streaks (locked decision #2 — any one
// game's daily counts, not all four); ritual-week reuses the same bar. Weeks
// are Math.floor(editionIndex / 7) rather than a real ISO-week string —
// EPOCH is itself a Monday, so this lines up exactly with real Mon-Sun
// calendar weeks, with none of a year-boundary string's edge cases. Fires
// once per week, the first time a device's distinct "showed up" editions
// that week reaches three.
function trackRitualWeek(completedOn) {
  const misc = store.getMisc();
  const week = Math.floor(completedOn / 7);
  const days = new Set(misc.ritualWeek === week ? (misc.ritualDays || []) : []);
  if (days.has(completedOn)) return;   // already counted (another game finished the same day)
  days.add(completedOn);
  const patch = { ritualWeek: week, ritualDays: [...days] };
  if (days.size >= 3 && misc.ritualFiredWeek !== week) {
    track('ritual-week');
    patch.ritualFiredWeek = week;
  }
  store.setMisc(patch);
}

// P5.1: derived from the ledger rather than stamped on first completion, so
// it's correct immediately for players who completed dailies before this
// shipped too — no migration step. Used by app.js's boot-time D1/D7/D30
// return check.
export function firstCompletedEdition() {
  const entries = store.getDailyLedger().entries || {};
  let min = null;
  GAMES.forEach((g) => {
    Object.values(entries[g] || {}).forEach((e) => {
      if (e && Number.isFinite(e.completedOn) && (min == null || e.completedOn < min)) min = e.completedOn;
    });
  });
  return min;
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

// P3.5: a "Report a problem" mailto, subject pre-filled so a fix can be
// traced back without any backend — no server, so email is the whole
// mechanism. contentId is a specific record id (the reveal credit panel) or
// null (a daily summary covering several items — the reporter names the one
// they mean in the email body).
export function reportProblemHref(contentId, editionIndex) {
  const issue = editionIndex != null ? editionIndex : '?';
  const subject = contentId
    ? `Yesternerd correction: ${contentId} (issue ${issue})`
    : `Yesternerd correction: issue ${issue}`;
  return `mailto:daniel.illes12@gmail.com?subject=${encodeURIComponent(subject)}`;
}

export { GAMES };
