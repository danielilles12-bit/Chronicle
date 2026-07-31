// Carry — moving a player's record from one origin to another.
//
// WHY THIS EXISTS. localStorage is per-ORIGIN, and this app's only persistence
// is localStorage. Three ordinary situations therefore look, to a player, like
// their streak was deleted:
//   1. the site moves to a new domain (installed iOS apps cannot follow);
//   2. they played in Safari, then installed the app to the home screen —
//      the installed app is a separate storage jar on some platforms;
//   3. they were reading inside Instagram's or WhatsApp's in-app browser,
//      which is its own throwaway jar, and want out into a real browser.
// One tool covers all three: EXPORT the record to a link or a short code,
// IMPORT it on the other side, MERGING rather than overwriting.
//
// DESIGN RULES this file obeys:
//   - Nothing is ever eval'd, and no untrusted key is ever spread into
//     storage. An incoming payload is walked against an explicit whitelist
//     and REBUILT from scratch; anything unrecognised is dropped silently.
//   - The merge never loses. Entries are unioned; a streak can only rise,
//     because it is recomputed by daily.js's own derivedStreak over a
//     SUPERSET of the entries that were already here.
//   - Importing the same payload twice does nothing the second time, and the
//     merge itself is idempotent anyway (union + max).
//   - No app name and no domain are baked in. The one line that changes on
//     moving day is DESTINATION, below.
import * as store from './storage.js';
import * as daily from './daily.js';
import { track } from './track.js';

// ---------------------------------------------------------------------------
// Configuration — the ONE line to change when the house moves
// ---------------------------------------------------------------------------
// Where carry LINKS should point: a base URL — scheme + host, plus a sub-path
// only if the app is not served from the root — with no trailing slash. ''
// means "wherever this copy of the app is served from", which is what you want
// for the Safari -> installed-app and in-app-browser cases.
//
// On moving day: set this to the NEW address and deploy that build to the OLD
// one. Links minted by the old site then land on the new site. The new site
// keeps '' — its own links are for its own players' second devices.
//
//   const DESTINATION = 'https://the-new-name.app';
const DESTINATION = '';

// The fragment the importer looks for. Emitted as 'carry'; 'df-carry' is
// accepted too so links minted by any earlier build keep working. Neither
// carries the product name — a rename must not strand a link already sitting
// in somebody's Notes app.
const FRAGMENT_KEY = 'carry';
const FRAGMENT_ALIASES = [FRAGMENT_KEY, 'df-carry'];

// Payload schema. Bump only for an incompatible change; the importer refuses
// anything it does not recognise rather than guessing.
const SCHEMA = 1;

// Round-by-round `detail` is only ever read again to re-draw a recent day's
// summary and share card, and the archive only reaches back seven aired days.
// Carrying it for every edition ever played is what makes a payload enormous,
// so it travels for the most recent editions only. Older entries keep their
// score and date — which is everything streaks and the Ledger need.
const DETAIL_WINDOW = 14;

// A URL longer than this is treated as "won't survive the journey". 8k is the
// smallest ceiling still in the wild (old proxies, some Android intents);
// Chrome and Safari both take far more. Past it the UI leads with the code.
const MAX_URL = 8000;

// Payload bombs: hard ceilings, enforced during validation.
const LIMITS = {
  payload: 400000,      // characters of encoded payload accepted at all
  json: 4000000,        // characters of decoded JSON accepted at all
  entriesPerGame: 4000, // ~11 years of dailies
  editionIndex: 100000,
  detailRounds: 32,
  guessRows: 24,
  guessCols: 12,
  stringLen: 120,
  arrayLen: 4000,
  carriedIn: 12,        // remembered import fingerprints
};

const GAMES = daily.GAMES;                 // ['who','map','what','thread']
const GAME_LABEL = { who: 'Face Value', map: 'Lifeline', what: 'Relic', thread: 'Thread' };

// Standalone localStorage keys — the handful of flags that live OUTSIDE the
// main blob (set by app.js and privacy.html). Everything else in the app is
// inside the blob and travels with it.
//   skipgc          — the analytics opt-out (GoatCounter's own flag)
//   df.celebrated   — highest edition whose "you made history" screen was shown
//   df.mourned      — highest edition whose obituary screen was shown
// The df.* names are pre-existing keys, read as-is; nothing new is minted.
const FLAG_SPEC = {
  skipgc: 'optout',
  'df.celebrated': 'maxnum',
  'df.mourned': 'maxnum',
};

let destinationOverride = null;   // test hook only, see testHooks()
let pending = null;               // an incoming payload captured this boot
let sheetWired = false;

// ---------------------------------------------------------------------------
// small helpers
// ---------------------------------------------------------------------------
const $ = (sel) => document.querySelector(sel);
const isObj = (v) => !!v && typeof v === 'object' && !Array.isArray(v);
const BAD_KEY = /^(__proto__|constructor|prototype)$/;

function num(v, max) {
  if (typeof v !== 'number' || !Number.isFinite(v)) return null;
  if (max !== undefined && Math.abs(v) > max) return null;
  return v;
}

function str(v) {
  return typeof v === 'string' && v.length <= LIMITS.stringLen ? v : null;
}

function bool(v) {
  return typeof v === 'boolean' ? v : null;
}

function flagGet(k) {
  try { return localStorage.getItem(k); } catch (e) { return null; }
}

function flagSet(k, v) {
  try { localStorage.setItem(k, v); } catch (e) { /* private mode: play on */ }
}

// ---------------------------------------------------------------------------
// wire format
// ---------------------------------------------------------------------------
// A payload is four dot-separated fields, all URL-safe, so the same string
// works as a fragment, as a copy-code, and as something a person can read out:
//
//   <schema>.<encoding>.<checksum>.<data>
//     schema    decimal integer (SCHEMA)
//     encoding  'd' = deflate, 'j' = plain JSON
//     checksum  8 hex chars, FNV-1a 32 over the UTF-8 JSON *before* encoding
//     data      base64url (no padding) of the deflated or raw JSON bytes
//
// The checksum is integrity, not authenticity: it catches a truncated paste,
// a mangled link or a flipped character. It is deliberately NOT a signature —
// a player can already edit their own localStorage, so there is nothing here
// worth forging that they could not simply type in themselves.
function fnv1a(bytes) {
  let h = 0x811c9dc5;
  for (let i = 0; i < bytes.length; i++) {
    h ^= bytes[i];
    h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
  }
  return ('0000000' + h.toString(16)).slice(-8);
}

function b64url(bytes) {
  let s = '';
  const CHUNK = 0x8000;   // apply() has an argument-count ceiling
  for (let i = 0; i < bytes.length; i += CHUNK) {
    s += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
  }
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function unb64url(s) {
  const b = s.replace(/-/g, '+').replace(/_/g, '/');
  const bin = atob(b + '==='.slice(0, (4 - (b.length % 4)) % 4));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function pipe(bytes, stream) {
  const w = stream.writable.getWriter();
  // write() and close() return promises that REJECT when the stream errors —
  // which is exactly what a damaged code does to DecompressionStream. Left
  // bare they become unhandled rejections, and app.js's global crash hook
  // would file a mangled paste as an application error. Swallow them here;
  // the real failure surfaces on the read side below, where it is handled.
  // Not awaited: the writer only settles once the reader drains, so awaiting
  // before reading would deadlock on anything bigger than the buffer.
  w.write(bytes).catch(() => {});
  w.close().catch(() => {});
  return new Uint8Array(await new Response(stream.readable).arrayBuffer());
}

async function deflate(bytes) {
  if (typeof CompressionStream === 'undefined') return null;
  try { return await pipe(bytes, new CompressionStream('deflate')); } catch (e) { return null; }
}

async function inflate(bytes) {
  if (typeof DecompressionStream === 'undefined') return null;
  try { return await pipe(bytes, new DecompressionStream('deflate')); } catch (e) { return null; }
}

export async function encode(body) {
  const json = JSON.stringify(body);
  const raw = new TextEncoder().encode(json);
  const sum = fnv1a(raw);
  const squeezed = await deflate(raw);
  // Compression is only worth it if it actually won — a tiny record can come
  // out bigger with a zlib header on it.
  const useD = squeezed && squeezed.length < raw.length;
  return `${SCHEMA}.${useD ? 'd' : 'j'}.${sum}.${b64url(useD ? squeezed : raw)}`;
}

// Returns { ok:true, body } or { ok:false, reason } — never throws, because
// every failure here is something a human did to a link, not a bug.
export async function decode(payload) {
  const s = String(payload || '').trim();
  if (!s) return { ok: false, reason: 'empty' };
  if (s.length > LIMITS.payload) return { ok: false, reason: 'too-big' };
  const m = /^(\d+)\.([dj])\.([0-9a-f]{8})\.([A-Za-z0-9\-_]+)$/.exec(s);
  if (!m) return { ok: false, reason: 'not-a-code' };
  if (+m[1] !== SCHEMA) return { ok: false, reason: 'wrong-version' };
  let bytes;
  try { bytes = unb64url(m[4]); } catch (e) { return { ok: false, reason: 'damaged' }; }
  if (m[2] === 'd') {
    bytes = await inflate(bytes);
    if (!bytes) {
      return { ok: false, reason: typeof DecompressionStream === 'undefined' ? 'no-unzip' : 'damaged' };
    }
  }
  if (fnv1a(bytes) !== m[3]) return { ok: false, reason: 'damaged' };
  let json;
  try { json = new TextDecoder().decode(bytes); } catch (e) { return { ok: false, reason: 'damaged' }; }
  if (json.length > LIMITS.json) return { ok: false, reason: 'too-big' };
  let body;
  try { body = JSON.parse(json); } catch (e) { return { ok: false, reason: 'damaged' }; }
  if (!isObj(body) || body.v !== SCHEMA) return { ok: false, reason: 'wrong-version' };
  return { ok: true, body, sum: m[3] };
}

// ---------------------------------------------------------------------------
// what travels, and in what shape
// ---------------------------------------------------------------------------
// The only misc keys that cross. Anything not named here is left behind — a
// deliberately short list, since misc is the app's junk drawer and most of it
// is device-local noise.
const MISC_SPEC = {
  seenBefore: 'bool',
  soundMuted: 'bool',
  wrongTaught: 'bool',
  installTipDismissed: 'bool',
  introSeen: 'gamebools',
  abandonSeen: 'strings',
  retFired: 'strings',
  ritualWeek: 'number',
  ritualDays: 'numbers',
  ritualFiredWeek: 'number',
  carriedIn: 'strings',
};

const STATS_FIELDS = ['bestScore', 'bestStreak', 'sessions'];

// ---------------------------------------------------------------------------
// building a payload (export side)
// ---------------------------------------------------------------------------
// Deliberately NOT carried:
//   mapSession / revealSession_* / dailySessions — half-finished rounds. Low
//     value, and a resumed session belongs to the device it started on.
//   puzzles — a dead free-play store nothing reads any more.
//   misc.lastError — a crash breadcrumb about the OLD device; meaningless here.
//   dailyLedger.streaks / .fullHouse — caches. Recomputed from entries on
//     arrival, which is the only way they can be trusted.
export function buildState() {
  const blob = store.readAll();
  const ledger = isObj(blob.dailyLedger) ? blob.dailyLedger : {};
  const entries = isObj(ledger.entries) ? ledger.entries : {};

  // The newest edition anywhere in the record anchors the detail window, so
  // trimming never depends on the device's clock being right.
  let newest = -Infinity;
  GAMES.forEach((g) => {
    Object.keys(entries[g] || {}).forEach((k) => { if (+k > newest) newest = +k; });
  });
  const detailFrom = newest - DETAIL_WINDOW;

  const outEntries = {};
  GAMES.forEach((g) => {
    const src = entries[g];
    if (!isObj(src)) return;
    const keep = {};
    Object.keys(src).forEach((k) => {
      const e = src[k];
      if (!isObj(e) || BAD_KEY.test(k) || !/^-?\d+$/.test(k)) return;
      const slim = { completedOn: e.completedOn };
      if (e.score !== undefined) slim.score = e.score;
      if (e.detail !== undefined && +k > detailFrom) slim.detail = e.detail;
      keep[k] = slim;
    });
    if (Object.keys(keep).length) outEntries[g] = keep;
  });

  const state = { dailyLedger: { entries: outEntries } };
  if (Number.isFinite(blob.schemaVersion)) state.schemaVersion = blob.schemaVersion;
  ['map', 'reveal_who', 'reveal_what'].forEach((k) => {
    if (isObj(blob[k])) state[k] = blob[k];
  });
  const misc = isObj(blob.misc) ? blob.misc : null;
  if (misc) {
    const m = {};
    Object.keys(MISC_SPEC).forEach((k) => { if (misc[k] !== undefined) m[k] = misc[k]; });
    if (Object.keys(m).length) state.misc = m;
  }

  const flags = {};
  Object.keys(FLAG_SPEC).forEach((k) => {
    const v = flagGet(k);
    if (v !== null) flags[k] = v;
  });

  const body = { v: SCHEMA, at: Date.now(), state };
  if (Object.keys(flags).length) body.flags = flags;
  return body;
}

// ---------------------------------------------------------------------------
// validating a payload (import side)
// ---------------------------------------------------------------------------
// Every value that reaches storage passes through here. The output object is
// built literal-by-literal from checked primitives; the input object is never
// assigned, spread or merged wholesale.
function cleanRounds(arr) {
  if (arr.length > LIMITS.detailRounds) return null;
  const out = [];
  for (const r of arr) {
    if (!isObj(r)) return null;
    const o = {};
    if (r.id !== undefined) { const v = str(r.id); if (v === null) return null; o.id = v; }
    ['pts', 'torn', 'wrongs', 'hints'].forEach((k) => {
      if (r[k] !== undefined) { const v = num(r[k], 100000); if (v !== null) o[k] = v; }
    });
    if (r.correct !== undefined) { const v = bool(r.correct); if (v !== null) o.correct = v; }
    out.push(o);
  }
  return out;
}

function cleanThreadDetail(d) {
  const o = {};
  ['solved', 'perfect'].forEach((k) => {
    if (d[k] !== undefined) { const v = bool(d[k]); if (v !== null) o[k] = v; }
  });
  if (d.mistakes !== undefined) { const v = num(d.mistakes, 1000); if (v !== null) o.mistakes = v; }
  if (d.guesses !== undefined) {
    if (!Array.isArray(d.guesses) || d.guesses.length > LIMITS.guessRows) return null;
    const rows = [];
    for (const row of d.guesses) {
      if (!Array.isArray(row) || row.length > LIMITS.guessCols) return null;
      const cells = [];
      for (const c of row) { const v = str(c); if (v === null) return null; cells.push(v); }
      rows.push(cells);
    }
    o.guesses = rows;
  }
  return o;
}

// Returns the cleaned detail, or undefined for "drop it". A malformed detail
// is never a reason to reject a whole record — the score and date are what
// matter, so the detail is simply left behind.
function cleanDetail(d) {
  if (d === undefined || d === null) return undefined;
  if (Array.isArray(d)) return cleanRounds(d) || undefined;
  if (isObj(d)) return cleanThreadDetail(d) || undefined;
  return undefined;
}

function cleanEntry(raw) {
  if (!isObj(raw)) return null;
  const completedOn = num(raw.completedOn, LIMITS.editionIndex);
  if (completedOn === null) return null;
  const out = { completedOn };
  const score = num(raw.score, 100000);
  if (score !== null) out.score = score;
  const detail = cleanDetail(raw.detail);
  if (detail !== undefined) out.detail = detail;
  return out;
}

function cleanMisc(raw) {
  const out = {};
  Object.keys(MISC_SPEC).forEach((k) => {
    const v = raw[k];
    if (v === undefined) return;
    const kind = MISC_SPEC[k];
    if (kind === 'bool') { const b = bool(v); if (b !== null) out[k] = b; return; }
    if (kind === 'number') { const n = num(v, LIMITS.editionIndex); if (n !== null) out[k] = n; return; }
    if (kind === 'gamebools') {
      if (!isObj(v)) return;
      const m = {};
      GAMES.forEach((g) => { if (bool(v[g]) === true) m[g] = true; });
      if (Object.keys(m).length) out[k] = m;
      return;
    }
    if (kind === 'strings' || kind === 'numbers') {
      if (!Array.isArray(v) || v.length > LIMITS.arrayLen) return;
      const list = [];
      for (const item of v) {
        const c = kind === 'strings' ? str(item) : num(item, LIMITS.editionIndex);
        if (c === null) return;              // one bad element voids the list
        list.push(c);
      }
      out[k] = list;
    }
  });
  return out;
}

function cleanStats(raw) {
  if (!isObj(raw)) return null;
  const out = {};
  STATS_FIELDS.forEach((k) => { const n = num(raw[k], 1000000); if (n !== null) out[k] = n; });
  return Object.keys(out).length ? out : null;
}

// Throws a plain Error with a short reason on anything structurally wrong.
export function validate(body) {
  if (!isObj(body) || body.v !== SCHEMA) throw new Error('wrong-version');
  const state = body.state;
  if (!isObj(state)) throw new Error('damaged');

  const ledger = state.dailyLedger;
  const rawEntries = isObj(ledger) && isObj(ledger.entries) ? ledger.entries : {};
  const entries = {};
  let count = 0;
  for (const g of GAMES) {
    const src = rawEntries[g];
    if (!isObj(src)) continue;
    const keys = Object.keys(src);
    if (keys.length > LIMITS.entriesPerGame) throw new Error('too-big');
    const kept = {};
    for (const k of keys) {
      if (BAD_KEY.test(k) || !/^-?\d+$/.test(k)) continue;
      const n = +k;
      if (!Number.isFinite(n) || Math.abs(n) > LIMITS.editionIndex) continue;
      const e = cleanEntry(src[k]);
      if (!e) continue;
      kept[String(n)] = e;
      count++;
    }
    if (Object.keys(kept).length) entries[g] = kept;
  }

  const clean = { dailyLedger: { entries } };
  const sv = num(state.schemaVersion, 1000);
  if (sv !== null) clean.schemaVersion = sv;
  ['map', 'reveal_who', 'reveal_what'].forEach((k) => {
    const s = cleanStats(state[k]);
    if (s) clean[k] = s;
  });
  if (isObj(state.misc)) {
    const m = cleanMisc(state.misc);
    if (Object.keys(m).length) clean.misc = m;
  }

  const flags = {};
  if (isObj(body.flags)) {
    Object.keys(FLAG_SPEC).forEach((k) => {
      const v = body.flags[k];
      if (typeof v === 'string' && v.length <= 24) flags[k] = v;
    });
  }

  // A payload with literally nothing in it is a mistake, not a move.
  if (!count && !clean.misc && !Object.keys(flags).length
      && !clean.map && !clean.reveal_who && !clean.reveal_what) {
    throw new Error('nothing-in-it');
  }
  return { state: clean, flags, at: num(body.at, 1e15) };
}

// ---------------------------------------------------------------------------
// merge
// ---------------------------------------------------------------------------
// The whole point: arriving data is ADDED to what is already here. The only
// question a merge ever asks is "which of these two is the better record?",
// and the answer never subtracts.
//
// Entry conflict (same game, same edition, two versions):
//   1. a streak-VALID completion beats an invalid one — streaks come first;
//   2. then the higher score;
//   3. then the one that still has its round detail;
//   4. then the earlier completion date;
//   5. then whatever is already on this device.
function richerEntry(edition, mine, theirs) {
  if (!mine) return theirs;
  if (!theirs) return mine;
  const vMine = daily.isStreakValid(edition, mine.completedOn);
  const vTheirs = daily.isStreakValid(edition, theirs.completedOn);
  if (vMine !== vTheirs) return vMine ? mine : theirs;
  const sMine = mine.score || 0;
  const sTheirs = theirs.score || 0;
  if (sMine !== sTheirs) return sMine > sTheirs ? mine : theirs;
  const dMine = mine.detail !== undefined;
  const dTheirs = theirs.detail !== undefined;
  if (dMine !== dTheirs) return dMine ? mine : theirs;
  if (mine.completedOn !== theirs.completedOn) {
    return mine.completedOn < theirs.completedOn ? mine : theirs;
  }
  return mine;
}

function mergeStats(mine, theirs) {
  if (!theirs) return mine;
  const out = Object.assign({}, mine || {});
  // max, not sum: the two jars are usually the SAME human on the same phone
  // (Safari and the installed app), so adding their session counts together
  // would invent history that never happened.
  STATS_FIELDS.forEach((k) => {
    const a = num(out[k], 1000000) || 0;
    const b = num(theirs[k], 1000000) || 0;
    if (a || b) out[k] = Math.max(a, b);
  });
  return out;
}

function mergeMisc(mine, theirs) {
  const out = Object.assign({}, mine || {});
  if (!theirs) return out;
  // Plain one-way latches: once true, always true. Never un-see a thing.
  ['seenBefore', 'wrongTaught', 'installTipDismissed'].forEach((k) => {
    if (theirs[k] === true) out[k] = true;
  });
  // Sound is a preference OF THIS DEVICE (headphones in, meeting on). The
  // device you are standing in front of wins; the arriving value only fills
  // a gap.
  if (theirs.soundMuted !== undefined && out.soundMuted === undefined) {
    out.soundMuted = theirs.soundMuted;
  }
  if (isObj(theirs.introSeen)) {
    const seen = Object.assign({}, isObj(out.introSeen) ? out.introSeen : {});
    GAMES.forEach((g) => { if (theirs.introSeen[g] === true) seen[g] = true; });
    out.introSeen = seen;
  }
  // Union the "already fired, don't fire again" sets, so a move cannot make
  // the app re-nag about things it long ago said.
  ['abandonSeen', 'retFired'].forEach((k) => {
    if (!Array.isArray(theirs[k])) return;
    const set = new Set(Array.isArray(out[k]) ? out[k] : []);
    theirs[k].forEach((v) => set.add(v));
    out[k] = [...set];
  });
  // Ritual week: the later week wins outright; the same week unions its days.
  const myWeek = num(out.ritualWeek, LIMITS.editionIndex);
  const theirWeek = num(theirs.ritualWeek, LIMITS.editionIndex);
  if (theirWeek !== null && (myWeek === null || theirWeek > myWeek)) {
    out.ritualWeek = theirWeek;
    out.ritualDays = Array.isArray(theirs.ritualDays) ? [...theirs.ritualDays] : [];
  } else if (theirWeek !== null && theirWeek === myWeek && Array.isArray(theirs.ritualDays)) {
    const set = new Set(Array.isArray(out.ritualDays) ? out.ritualDays : []);
    theirs.ritualDays.forEach((d) => set.add(d));
    out.ritualDays = [...set];
  }
  const myFired = num(out.ritualFiredWeek, LIMITS.editionIndex);
  const theirFired = num(theirs.ritualFiredWeek, LIMITS.editionIndex);
  if (theirFired !== null) out.ritualFiredWeek = Math.max(myFired === null ? -Infinity : myFired, theirFired);
  if (Array.isArray(theirs.carriedIn)) {
    const set = new Set(Array.isArray(out.carriedIn) ? out.carriedIn : []);
    theirs.carriedIn.forEach((v) => set.add(v));
    out.carriedIn = [...set].slice(-LIMITS.carriedIn);
  }
  return out;
}

function mergeFlags(theirs) {
  const changes = [];
  Object.keys(theirs || {}).forEach((k) => {
    const kind = FLAG_SPEC[k];
    const mine = flagGet(k);
    if (kind === 'optout') {
      // Privacy latches ON. If either jar said "off the record", it stays off.
      if (theirs[k] === 't' && mine !== 't') changes.push([k, 't']);
      return;
    }
    if (kind === 'maxnum') {
      const a = parseInt(mine, 10);
      const b = parseInt(theirs[k], 10);
      if (!Number.isFinite(b)) return;
      if (!Number.isFinite(a) || b > a) changes.push([k, String(b)]);
    }
  });
  return changes;
}

// Recompute the cached streak fields from the merged entries, exactly the way
// daily.js does when a daily is completed. This is what makes "never lower a
// streak" true by construction rather than by promise: the merged entry set is
// a superset of what was here, derivedStreak is monotonic in that set, so the
// number it returns can only be the same or bigger.
function recomputeStreaks(ledger, today) {
  const entries = ledger.entries || {};
  const validAt = (g) => (e) => {
    const en = entries[g] && entries[g][e];
    return !!en && daily.isStreakValid(e, en.completedOn);
  };
  ledger.streaks = ledger.streaks || {};
  GAMES.forEach((g) => { ledger.streaks[g] = daily.derivedStreak(validAt(g), today); });
  ledger.fullHouse = daily.derivedStreak((e) => GAMES.every((g) => validAt(g)(e)), today);
  return ledger;
}

// Applies a validated payload. Returns a report of what actually landed.
export function applyCarry(clean, sum) {
  const blob = store.readAll();
  const before = summarise(blob);

  const ledger = isObj(blob.dailyLedger) ? blob.dailyLedger : { entries: {}, streaks: {}, fullHouse: { streak: 0, lastEdition: -Infinity } };
  if (!isObj(ledger.entries)) ledger.entries = {};
  let added = 0;
  let improved = 0;
  const theirEntries = clean.state.dailyLedger.entries;
  GAMES.forEach((g) => {
    const src = theirEntries[g];
    if (!src) return;
    if (!isObj(ledger.entries[g])) ledger.entries[g] = {};
    Object.keys(src).forEach((k) => {
      const edition = +k;
      const mine = ledger.entries[g][k];
      const winner = richerEntry(edition, mine, src[k]);
      if (!mine) { added++; ledger.entries[g][k] = winner; return; }
      if (winner !== mine) { improved++; ledger.entries[g][k] = winner; }
    });
  });
  recomputeStreaks(ledger, Math.max(0, daily.todayIndex()));
  blob.dailyLedger = ledger;

  ['map', 'reveal_who', 'reveal_what'].forEach((k) => {
    const merged = mergeStats(blob[k], clean.state[k]);
    if (merged) blob[k] = merged;
  });

  const misc = mergeMisc(blob.misc, clean.state.misc);
  const seen = new Set(Array.isArray(misc.carriedIn) ? misc.carriedIn : []);
  if (sum) seen.add(sum);
  misc.carriedIn = [...seen].slice(-LIMITS.carriedIn);
  blob.misc = misc;

  if (Number.isFinite(clean.state.schemaVersion)) {
    blob.schemaVersion = Math.max(blob.schemaVersion || 0, clean.state.schemaVersion);
  }

  // One write for the whole record — storage.js files the previous good copy
  // as the backup first, so an interruption here costs nothing.
  store.writeAll(blob);
  mergeFlags(clean.flags).forEach(([k, v]) => flagSet(k, v));

  const after = summarise(store.readAll());
  return { added, improved, before, after };
}

export function alreadyCarried(sum) {
  const misc = store.readAll().misc;
  return !!(isObj(misc) && Array.isArray(misc.carriedIn) && misc.carriedIn.indexOf(sum) !== -1);
}

// ---------------------------------------------------------------------------
// describing a record in plain words
// ---------------------------------------------------------------------------
// Works on either shape (a live blob or a payload's state), because both carry
// dailyLedger.entries and that is all this needs.
export function summarise(source) {
  const entries = (isObj(source) && isObj(source.dailyLedger) && isObj(source.dailyLedger.entries))
    ? source.dailyLedger.entries : {};
  const today = Math.max(0, daily.todayIndex());
  const validAt = (g) => (e) => {
    const en = entries[g] && entries[g][e];
    return !!en && daily.isStreakValid(e, en.completedOn);
  };
  const editions = new Set();
  GAMES.forEach((g) => Object.keys(entries[g] || {}).forEach((k) => editions.add(+k)));
  const full = daily.derivedStreak((e) => GAMES.every((g) => validAt(g)(e)), today).streak;
  let best = 0;
  let bestGame = null;
  GAMES.forEach((g) => {
    const s = daily.derivedStreak(validAt(g), today).streak;
    if (s > best) { best = s; bestGame = g; }
  });
  const streak = full > 0 ? full : best;
  const label = full > 0 ? 'full-house streak' : (bestGame ? `${GAME_LABEL[bestGame]} streak` : 'streak');
  return { issues: editions.size, streak, streakLabel: label };
}

// One optional manifest line naming the preferences in the crate. Only ever
// mentions settings a player deliberately changed — the silent one-time
// "already seen this" flags travel too, but nobody needs a bullet about them.
function settingsLine(state) {
  const words = [];
  const misc = isObj(state) && isObj(state.misc) ? state.misc : {};
  const flags = isObj(state) && isObj(state.flags) ? state.flags : {};
  if (misc.soundMuted === true) words.push('sound off');
  if (flags.skipgc === 't') words.push('off the record');
  return words.length ? `Settings: ${words.join(', ')}` : null;
}

// "41-day full-house streak + 12 issues" — the one line the confirm leads on.
function headline(sum) {
  const bits = [];
  if (sum.streak > 0) bits.push(`${sum.streak}-day ${sum.streakLabel}`);
  bits.push(`${sum.issues} issue${sum.issues === 1 ? '' : 's'}`);
  return bits.join(' + ');
}

// ---------------------------------------------------------------------------
// links and codes
// ---------------------------------------------------------------------------
function destinationBase() {
  const set = destinationOverride || DESTINATION;
  if (set) return set.replace(/\/+$/, '');
  // Same origin (the Safari -> installed-app and in-app-browser cases): keep
  // the DIRECTORY the app is actually served from, not the bare origin — a
  // project-style Pages deployment lives under a sub-path, and a link to the
  // domain root would land nowhere.
  return location.origin + location.pathname.replace(/\/[^/]*$/, '');
}

export function linkFor(payload) {
  // The app's front door, never a deep link: a path from the old host may not
  // exist on the new one, and the point of arriving is to be let in.
  return `${destinationBase()}/#${FRAGMENT_KEY}=${payload}`;
}

// ---------------------------------------------------------------------------
// boot hooks
// ---------------------------------------------------------------------------
// Called FIRST in boot(), before analytics or any other reader of the URL:
// grabs the fragment and scrubs it in the same breath. replaceState (not
// pushState) means the entry with the payload on it is gone from session
// history too, so Back cannot resurrect it and a reload cannot re-trigger it.
export function captureIncoming() {
  let hash = '';
  try { hash = location.hash || ''; } catch (e) { return false; }
  if (!hash) return false;
  const body = hash.replace(/^#/, '');
  let found = null;
  for (const key of FRAGMENT_ALIASES) {
    if (body.indexOf(key + '=') === 0) { found = body.slice(key.length + 1); break; }
  }
  if (!found) return false;
  pending = decodeURIComponent(found);
  try {
    history.replaceState(history.state, '', location.pathname + location.search);
  } catch (e) { /* sandboxed contexts: the URL stays ugly, the import still runs */ }
  return true;
}

// Called at the end of boot(), once there is an app to show a sheet over.
export async function offerIncoming() {
  if (!pending) return false;
  track('carry-land');
  return openImport(pending);
}

// ---------------------------------------------------------------------------
// the sheet
// ---------------------------------------------------------------------------
const COPY = {
  exportLede: 'Your record lives in this browser and nowhere else — no account, '
    + 'no cloud, nothing of yours on a server. To move it, take it with you.',
  // Link first when a link will survive the trip; the code is the fallback
  // AND the only thing that works into an installed home-screen app, so it
  // gets its own sentence either way.
  linkFirst: 'Send yourself the link — message, note, email — and open it in the '
    + 'browser you want the record to land in. Moving to the installed app '
    + 'instead? Use the code: tapping a link opens your browser, not the app.',
  codeFirst: 'Your record is a big one, so use the code — some apps quietly clip '
    + 'very long links. Copy it, open the browser or app you are moving to, '
    + 'come back to this sheet and paste it into the box below.',
};

const REASONS = {
  'not-a-code': 'That doesn’t look like a carry code. Copy the whole thing — it’s one long unbroken line.',
  damaged: 'That code arrived damaged — something clipped it on the way. Copy it again, all of it.',
  'wrong-version': 'That code was made by a different version of the app. Make a fresh one on the old device.',
  'no-unzip': 'This browser is too old to unpack that code. Try a different browser on this device.',
  'too-big': 'That code is far too big to be one of ours.',
  'nothing-in-it': 'That code is empty — there was nothing on the record to carry.',
  empty: 'Nothing pasted yet.',
};

function el(id) { return document.getElementById(id); }

function setStatus(text, kind) {
  const s = el('carry-status');
  if (!s) return;
  s.textContent = text || '';
  s.hidden = !text;
  s.className = 'carry-status' + (kind ? ' is-' + kind : '');
}

function showPanel(which) {
  ['carry-export-panel', 'carry-import-panel'].forEach((id) => {
    const n = el(id);
    if (n) n.hidden = id !== 'carry-' + which + '-panel';
  });
}

// "Not now" already IS the way out of a confirm, so the sheet's generic Close
// button stands down while a decision is on the table — two buttons that do
// the same thing next to each other is how people end up not trusting either.
function showConfirm(on) {
  const row = el('carry-confirm-row');
  const close = el('carry-close');
  if (row) row.hidden = !on;
  if (close) close.hidden = !!on;
}

function manifestHTML(lines) {
  return lines.map((l) => `<li>${l.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]))}</li>`).join('');
}

function openSheet() {
  const sheet = el('carry-sheet');
  if (sheet) sheet.hidden = false;
}

export function closeSheet() {
  const sheet = el('carry-sheet');
  if (sheet) sheet.hidden = true;
  setStatus('');
}

async function copyText(text, btn, label) {
  let ok = false;
  try {
    await navigator.clipboard.writeText(text);
    ok = true;
  } catch (e) {
    // No clipboard permission (or an in-app browser that withholds it): fall
    // back to selecting the field so a long-press → Copy still works.
    const field = el('carry-payload');
    if (field) { field.focus(); field.select(); }
  }
  if (btn) {
    const was = btn.textContent;
    btn.textContent = ok ? 'Copied' : 'Select it and copy';
    setTimeout(() => { btn.textContent = was; }, 1800);
  }
  if (ok) track(`carry-copy-${label}`);
  return ok;
}

let exported = null;   // { payload, link, tooLong } for the open sheet

async function openExport() {
  openSheet();
  showPanel('export');
  setStatus('');
  el('carry-title').textContent = 'Moving house';
  el('carry-lede').textContent = COPY.exportLede;
  el('carry-manifest').innerHTML = '<li>packing…</li>';
  const body = buildState();
  const sum = summarise(body.state);
  const lines = [];
  if (sum.streak > 0) lines.push(`${sum.streak}-day ${sum.streakLabel}`);
  lines.push(`${sum.issues} issue${sum.issues === 1 ? '' : 's'} on the record`);
  const settings = settingsLine({ misc: body.state.misc, flags: body.flags });
  if (settings) lines.push(settings);
  el('carry-manifest').innerHTML = manifestHTML(lines);

  const payload = await encode(body);
  const link = linkFor(payload);
  exported = { payload, link, tooLong: link.length > MAX_URL };
  el('carry-payload').value = payload;
  el('carry-link-btn').hidden = exported.tooLong;
  el('carry-help').textContent = exported.tooLong ? COPY.codeFirst : COPY.linkFirst;
  track('carry-export');
}

async function openImport(payload) {
  const res = await decode(payload);
  if (!res.ok) {
    openSheet();
    showPanel('import');
    el('carry-title').textContent = 'That didn’t travel well';
    el('carry-lede').textContent = REASONS[res.reason] || REASONS.damaged;
    el('carry-manifest').innerHTML = '';
    showConfirm(false);
    setStatus('');
    track('carry-import-bad');
    return false;
  }
  if (alreadyCarried(res.sum)) {
    openSheet();
    showPanel('import');
    el('carry-title').textContent = 'Already here';
    el('carry-lede').textContent = 'This record was carried over already — nothing left to do. Your streak is safe.';
    el('carry-manifest').innerHTML = '';
    showConfirm(false);
    setStatus('');
    pending = null;
    track('carry-import-repeat');
    return false;
  }
  let clean;
  try {
    clean = validate(res.body);
  } catch (e) {
    openSheet();
    showPanel('import');
    el('carry-title').textContent = 'That didn’t travel well';
    el('carry-lede').textContent = REASONS[e.message] || REASONS.damaged;
    el('carry-manifest').innerHTML = '';
    showConfirm(false);
    setStatus('');
    track('carry-import-bad');
    return false;
  }

  const theirs = summarise(clean.state);
  const mine = summarise(store.readAll());
  openSheet();
  showPanel('import');
  el('carry-title').textContent = 'Something arrived';
  el('carry-lede').textContent = `Carry ${headline(theirs)} over to this device?`;
  const lines = [];
  if (theirs.streak > 0) lines.push(`${theirs.streak}-day ${theirs.streakLabel}`);
  lines.push(`${theirs.issues} issue${theirs.issues === 1 ? '' : 's'} on the record`);
  const settings = settingsLine({ misc: clean.state.misc, flags: clean.flags });
  if (settings) lines.push(settings);
  lines.push(mine.issues
    ? `Merged with what’s already here (${mine.issues} issue${mine.issues === 1 ? '' : 's'}) — nothing is deleted, the better record wins.`
    : 'Nothing on this device yet, so this becomes the record.');
  el('carry-manifest').innerHTML = manifestHTML(lines);
  showConfirm(true);
  el('carry-yes').onclick = () => {
    const report = applyCarry(clean, res.sum);
    pending = null;
    showConfirm(false);
    el('carry-title').textContent = 'Carried over';
    el('carry-lede').textContent = report.added || report.improved
      ? 'Done. Your record travelled.'
      : 'Everything on that code was already here — nothing to add.';
    el('carry-manifest').innerHTML = manifestHTML([
      `${report.after.issues} issue${report.after.issues === 1 ? '' : 's'} on the record`,
      report.after.streak > 0
        ? `${report.after.streak}-day ${report.after.streakLabel}`
        : 'Streak starts again today',
      // Counts of rows added mean nothing to anybody. What a player wants to
      // know is that this did not cost them anything.
      report.improved
        ? `${report.improved} day${report.improved === 1 ? '' : 's'} upgraded to the better result — nothing overwritten`
        : 'Nothing was overwritten.',
    ]);
    track('carry-import-ok');
    refreshApp();
  };
  el('carry-no').onclick = () => { closeSheet(); track('carry-import-declined'); };
  track('carry-import-offer');
  return true;
}

// Repaint anything showing a number that just changed. Kept as a soft
// dependency (a CustomEvent) so carry.js never imports app.js — that would be
// a cycle, since app.js imports this.
function refreshApp() {
  document.dispatchEvent(new CustomEvent('carrydone'));
}

function wireSheet() {
  if (sheetWired) return;
  const sheet = el('carry-sheet');
  if (!sheet) return;
  sheetWired = true;
  el('carry-close').addEventListener('click', closeSheet);
  sheet.addEventListener('click', (e) => { if (e.target === sheet) closeSheet(); });
  el('carry-copy-btn').addEventListener('click', () => {
    if (exported) copyText(exported.payload, el('carry-copy-btn'), 'code');
  });
  el('carry-link-btn').addEventListener('click', () => {
    if (exported) copyText(exported.link, el('carry-link-btn'), 'link');
  });
  el('carry-payload').addEventListener('focus', (e) => e.target.select());
  el('carry-paste-btn').addEventListener('click', async () => {
    const raw = el('carry-paste').value.trim();
    if (!raw) { setStatus(REASONS.empty, 'bad'); return; }
    // A pasted LINK is a pasted code with a URL wrapped round it — unwrap it
    // rather than telling somebody they pasted the wrong thing.
    const m = /[#&](?:carry|df-carry)=([A-Za-z0-9.\-_%]+)/.exec(raw);
    setStatus('Unpacking…');
    const ok = await openImport(m ? decodeURIComponent(m[1]) : raw);
    if (ok) el('carry-paste').value = '';
  });
}

export function initCarry() {
  wireSheet();
  const open = el('carry-open');
  if (open) {
    open.addEventListener('click', () => {
      // A payload that arrived this boot and was waved away is still in hand:
      // offer it again rather than making them re-open the link.
      if (pending) { openImport(pending); return; }
      openExport();
    });
  }
}

// Deterministic hooks for the Python suite (gated by the caller, exactly like
// window.__CHRONICLE_TEST__ everywhere else).
export function testHooks() {
  return {
    encode,
    decode,
    validate,
    buildState,
    summarise,
    linkFor,
    applyCarry,
    alreadyCarried,
    maxUrl: MAX_URL,
    setDestination: (o) => { destinationOverride = o; },
    exportNow: async () => {
      const payload = await encode(buildState());
      return { payload, link: linkFor(payload) };
    },
  };
}
