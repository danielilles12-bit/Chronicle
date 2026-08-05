// Boot, data loading, view router, home screen.
// BUILD is shown in the home footer; bump it together with sw.js VERSION on
// every deploy so what phones display always names what they are running.
const BUILD = 'v177';

// iOS (incl. iPadOS, which masquerades as MacIntel) gets the OS's own
// overscroll physics back — style.css keys native rubber-banding off this
// class, and initPullToRefresh rides it. Everywhere else stays solid-stop.
if (/iP(hone|ad|od)/.test(navigator.userAgent)
    || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)) {
  document.documentElement.classList.add('ios');
}

import * as store from './storage.js';
import { track, initTracking } from './track.js';
import { fullHouseShareText, obituaryShareText, shareResult, flashShareButton, shareUrl } from './sharecard.js';
import { isMatch } from './match.js';
import { initMapGame, renderMapStart, startMapDaily, startMapPractice } from './mapgame.js';
import { initRevealGame, renderRevealStart, startRevealDaily, startRevealPractice } from './revealgame.js';
import { initConnectionsGame, startThreadDaily, startThreadPractice } from './connectionsgame.js';
import * as daily from './daily.js';
import * as sfx from './sfx.js';
import { renderLedger } from './ledger.js';
import * as carry from './carry.js';
import { initInstall, isStandalone, qaActions as installQA, testHooks as installHooks } from './install.js';

export const DATA = { figures: null, world: null, reveal: null, connections: null, editions: null };
export const $ = (sel) => document.querySelector(sel);
export const $$ = (sel) => Array.from(document.querySelectorAll(sel));

// window.__CHRONICLE_TEST__ exposes answer data and game internals to the
// Python test-suite. Never ship it to players: every assignment site checks
// this gate — localhost (where the tests run) or an explicit ?test=1.
export function testHooksEnabled() {
  return location.hostname === 'localhost'
    || location.hostname === '127.0.0.1'
    || /[?&]test=1(&|$)/.test(location.search);
}

// ---------- router ----------
const trail = ['view-home'];

export function show(id) {
  if (trail[trail.length - 1] !== id) {
    trail.push(id);
    try { window.history.pushState({ depth: trail.length }, ''); } catch (e) { /* sandboxed contexts */ }
  }
  render();
}

// Desktop nicety: the browser Back button walks the in-app view trail.
// Depth-synced so the Forward button never navigates the app backwards.
try { window.history.replaceState({ depth: 1 }, ''); } catch (e) { /* sandboxed */ }
window.addEventListener('popstate', (e) => {
  const depth = (e.state && e.state.depth) || 1;
  let changed = false;
  while (trail.length > Math.max(1, depth)) {
    trail.pop();
    changed = true;
  }
  if (changed) render();
});

export function back() {
  if (trail.length <= 1) return;
  // pop via the History API when we own the current entry so the browser
  // and in-app trails stay in step; popstate does the actual render
  if (window.history.state && window.history.state.depth === trail.length) {
    window.history.back();
    return;
  }
  trail.pop();
  render();
}

export function goHome() {
  trail.length = 0;
  trail.push('view-home');
  // Re-stamp the entry we are standing on as depth 1, because the trail we
  // just emptied is what back() measures history against. Without this, the
  // entry still claims the depth it had before (say 3); the NEXT view pushes
  // depth 2 on top of it, so back()'s history.back() lands on a depth-3 entry,
  // the popstate handler pops nothing, and the ‹ chip does nothing on the
  // first tap. Found 5 Aug 2026 by tests/test_no_dead_ends.py — the sequence
  // "finish a daily › ‹ home › Your Legacy › ‹" reproduced it exactly.
  try { window.history.replaceState({ depth: 1 }, ''); } catch (e) { /* sandboxed */ }
  render();
}

function render() {
  const id = trail[trail.length - 1];
  $$('.view').forEach((v) => { v.hidden = v.id !== id; });
  // Rollover: revisiting Home re-evaluates today's edition, so a session left
  // open across local midnight picks up the new day's Today strip without
  // needing a live timer (see spec "Rollover").
  if (id === 'view-home') { refreshHomeStats(); refreshTodayStrip(); refreshIssueClosed(); }
  else stopIssueClosedCountdown();
  if (id === 'view-mapstart') renderMapStart();
  if (id === 'view-revealstart') renderRevealStart();
  if (id === 'view-archive') renderArchive();
  if (id === 'view-ledger') renderLedger();
  document.dispatchEvent(new CustomEvent('viewchange', { detail: id }));
}

// Receipt stamp: ALEA IACTA FEST celebrates any real score; a zero-point
// session gets DAMNATIO MEMORIAE instead (struck from the record) — a
// celebration stamp on a failed run read as mockery (owner call 2026-07-15).
export function setReceiptStamp(viewId, score) {
  const root = document.querySelector(`#${viewId} .df-receipt`);
  if (!root) return;
  const alea = root.querySelector('[data-stamp-alea]');
  const zero = root.querySelector('[data-stamp-zero]');
  if (alea) alea.hidden = score === 0;
  if (zero) zero.hidden = score !== 0;
}

// Styled in-app replacement for window.confirm().
export function appConfirm(message, yesLabel) {
  return new Promise((resolve) => {
    const sheet = $('#confirm-sheet');
    const yes = $('#confirm-yes');
    const no = $('#confirm-no');
    $('#confirm-msg').textContent = message;
    yes.textContent = yesLabel || 'Yes';
    const finish = (val) => {
      sheet.hidden = true;
      yes.removeEventListener('click', onYes);
      no.removeEventListener('click', onNo);
      resolve(val);
    };
    const onYes = () => finish(true);
    const onNo = () => finish(false);
    yes.addEventListener('click', onYes);
    no.addEventListener('click', onNo);
    sheet.hidden = false;
  });
}

// ---------- home ----------
export function refreshHomeStats() {
  // Stats (best score/streak) still live in storage and back the hero/day
  // cards' status lines; the old dedicated stat-line elements under each big
  // description card are gone with that layout, so there is nothing left to
  // paint here for now. A future stats screen reads the same storage getters.
}

// ---------- Game rows (hero + day-card strip + Archive bar) ----------
// One row per game, in the fixed presentation order Face Value, Lifeline,
// Relic, Thread — most instantly-graspable first, heaviest cold-open last
// (conversion call, 2026-07-20; keep in sync with GAMES in daily.js, which
// drives the same order for "turn the page"). `launchDaily`/`launchPractice`
// take the edition index.
// Per-row accent tints are Archive Codex versions of NYT's per-game colour
// coding (spec "Per-row accent tints"): a strong tint for the hero card, a
// slightly lighter one (lower mix %) for day cards + the Archive bar.
const GAME_ROWS = [
  // `time` is the expected-time whisper on the hero card (P1.4): muted and
  // small next to the issue number, same voice as the dateline whisper.
  {
    key: 'who', label: 'Face Value', tagline: 'A famous face, one scrap at a time.',
    glyph: 'assets/brand/game-icon-face-value.webp', time: '~3 min',
    tintStrong: 'var(--df-magenta)',
    tintSoft: 'color-mix(in srgb, var(--df-magenta) 12%, var(--ch-cream))',
    launchDaily: (n) => startRevealDaily('who', n), launchPractice: (n) => startRevealPractice('who', n),
  },
  {
    key: 'map', label: 'Lifeline', tagline: 'Born here, died there. Name the figure.',
    glyph: 'assets/brand/game-icon-lifeline.webp', time: '~3 min',
    tintStrong: 'var(--df-yellow)',
    tintSoft: 'color-mix(in srgb, var(--df-yellow) 18%, var(--ch-cream))',
    launchDaily: startMapDaily, launchPractice: startMapPractice,
  },
  {
    key: 'what', label: 'Relic', tagline: 'A famous artefact, one scrap at a time.',
    glyph: 'assets/brand/game-icon-relic.webp', time: '~3 min',
    tintStrong: 'var(--df-red)',
    tintSoft: 'color-mix(in srgb, var(--df-red) 10%, var(--ch-cream))',
    launchDaily: (n) => startRevealDaily('what', n), launchPractice: (n) => startRevealPractice('what', n),
  },
  {
    key: 'thread', label: 'Thread', tagline: 'Group 16 clues into four hidden categories.',
    glyph: 'assets/brand/game-icon-thread.webp', time: '~2 min',
    tintStrong: 'var(--df-cyan)',
    tintSoft: 'color-mix(in srgb, var(--df-cyan) 14%, var(--ch-cream))',
    launchDaily: startThreadDaily, launchPractice: startThreadPractice,
  },
];
// Kept for the Archive picker (practice-game buttons) and archive-row dots,
// which key off the same game list/order.
const TODAY_GAMES = GAME_ROWS;

function statusLabel(status, score) {
  if (status === 'done') return `Done · ${score} pts`;
  if (status === 'in-progress') return 'In progress';
  return 'Play ›';   // an invitation, not a status report (conversion audit 2026-07-20)
}

// Build the static shell for all four rows once. Called on boot; content
// (edition label, status, day-card weekdays) is filled in by
// refreshGameRows(), which also runs every time Home is revisited so a
// rollover past local midnight or a completed daily is picked up live.
function renderGameRows() {
  const root = $('#home-rows');
  if (!root || root.dataset.built) return;
  root.innerHTML = GAME_ROWS.map((g) => `
    <section class="game-row" data-row="${g.key}"
             style="--row-tint-strong:${g.tintStrong};--row-tint-soft:${g.tintSoft}">
      <button class="hero-card" data-hero="${g.key}" aria-label="Play today's ${g.label}">
        <div class="hero-top">
          <div class="hero-text">
            <h2 class="hero-name">${g.label}</h2>
            <p class="hero-tagline">${g.tagline}</p>
          </div>
          <img class="hero-glyph" src="${g.glyph}" alt="">
        </div>
        <div class="hero-bottom">
          <span class="hero-edition" data-edition></span>
          <span class="hero-status" data-status></span>
        </div>
      </button>
      <div class="df-week" data-week aria-hidden="true"></div>
      <button class="row-archive" data-archive="${g.key}" aria-label="Open back issues">
        <span>Back issues</span>
        <svg class="row-archive-glyph" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6 H20 V19 A1 1 0 0 1 19 20 H5 A1 1 0 0 1 4 19 Z" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M2.5 6 H21.5 L20 3 H4 Z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M9.5 10.5 H14.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
      </button>
    </section>
  `).join('');
  root.dataset.built = '1';
  // The funnel's missing middle: fires when the four cards actually paint.
  // open-* minus this = visitors who never saw the landing (loading bleed);
  // this minus start-* = visitors who saw it and didn't bite (persuasion bleed).
  track('rows-rendered');
  // Cards no longer wait on data, so a slow paint means slow HTML/JS delivery.
  if (performance.now() > 2500) track('rows-rendered-slow');

  GAME_ROWS.forEach((g) => {
    $(`[data-hero="${g.key}"]`).addEventListener('click', () => {
      track(`start-${g.key}`);
      launchWhenReady(g);
    });
    $(`[data-archive="${g.key}"]`).addEventListener('click', async () => {
      if (!await ensureGameData(g.key, $(`[data-row="${g.key}"] [data-status]`))) return;
      renderArchive();
      show('view-archive');
    });
  });
}

// Launch a game from Home, waiting out the background data download if the
// player outran it. The card's own status line doubles as the loading state,
// and gates only on the files THIS game needs (P2.2).
async function launchWhenReady(g) {
  const statusEl = document.querySelector(`[data-hero="${g.key}"] [data-status]`);
  if (!await ensureGameData(g.key, statusEl)) return;
  g.launchDaily(daily.todayIndex());
}

// Weekday comes from the edition index (not the raw device date) so it
// honours the ?dailydate= QA override the same way the issue number does.
function datelineHTML(n) {
  const safe = Math.max(0, n);
  return `№ ${safe} // ${daily.weekdayName(safe)}`;
}

// 'done' | 'in-progress' | 'not-started' for a past (aired) edition, for the
// day cards. v1 note (spec "Cautions"): this reads the daily ledger only —
// practice completions leave no persistent record in any game engine
// (mapgame.js/revealgame.js/connectionsgame.js all no-op storage on practice
// finish "no ledger, no trace"), so a day card cannot distinguish "played in
// practice" from "not played" today. Showing daily results only, as the spec
// allows for v1.
function dayCardStatus(gameKey, editionIndex) {
  return daily.dailyStatus(gameKey, editionIndex);
}

// The masthead punch card (approved streak look, the "combo"): this week as
// seven die-punched ticket squares — a hole is that day's full house — plus
// the running count while the streak is alive. "Alive" includes runs still
// inside the 48h repair window, matching derivedStreak's anchor in daily.js.
function renderPunchCard() {
  const el = $('#punch-card');
  if (!el) return;
  const today = daily.todayIndex();
  if (today < 0) { el.hidden = true; return; }
  const monday = today - daily.weekday(today);
  const letters = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];
  const chips = letters.map((ch, i) => {
    const day = monday + i;
    const done = day <= today && day >= 0 && fullHouseDone(day);
    const cls = ['punch-day', done ? 'punched' : '', day === today ? 'today' : '', day > today ? 'future' : '']
      .filter(Boolean).join(' ');
    return `<span class="${cls}">${done ? '<i></i>' : ch}</span>`;
  }).join('');
  const fh = store.getDailyLedger().fullHouse || { streak: 0, lastEdition: -Infinity };
  const alive = Number.isFinite(fh.lastEdition) && fh.lastEdition >= today - 3 && fh.streak > 0;
  el.innerHTML = chips + (alive ? `<span class="punch-count">№ ${fh.streak} running</span>` : '');
  el.hidden = false;
}

const MAX_DAY_CARDS = 7;

export function refreshGameRows() {
  if (!$('#home-rows')) return;
  renderGameRows();
  applyStrangerMode();
  const today = Math.max(0, daily.todayIndex());
  $('#dateline').innerHTML = datelineHTML(today);
  renderPunchCard();
  GAME_ROWS.forEach((g) => {
    const status = daily.dailyStatus(g.key, today);
    const entry = status === 'done' ? store.getDailyEntry(g.key, today) : null;
    const hero = $(`[data-hero="${g.key}"]`);
    hero.querySelector('[data-edition]').innerHTML =
      `№ ${Math.max(0, today)}<span class="hero-time"> · ${g.time}</span>`;
    hero.querySelector('[data-status]').textContent = statusLabel(status, entry && entry.score);
    hero.classList.toggle('row-done', status === 'done');
    hero.classList.toggle('row-progress', status === 'in-progress');

    // This week's M-S strip: filled square = that day's daily completed.
    const weekEl = $(`[data-row="${g.key}"] [data-week]`);
    if (weekEl) {
      const monday = today - daily.weekday(today);
      weekEl.innerHTML = ['M','T','W','T','F','S','S'].map((ch, i) => {
        const n = monday + i;
        const cls = [];
        if (n === today) cls.push('today');
        if (n <= today && daily.dailyStatus(g.key, n) === 'done') cls.push('done');
        return `<span class="${cls.join(' ')}">${ch}</span>`;
      }).join('');
    }

  });
}

// Back-compat name used by boot()/render(); the Today-strip concept is gone,
// replaced by the per-row hero + day cards, but the refresh still happens on
// every Home visit for the same rollover reason (see render()).
export function refreshTodayStrip() { refreshGameRows(); }

// ---------- Turn the page (Change A: an ending for every day) ----------
// The next of today's four dailies (home order: Face Value, Lifeline, Relic,
// Thread == daily.GAMES) with no ledger entry yet, or null once all four are
// played (won OR lost). "Played" is derived straight from the ledger — no new
// storage shape.
function nextUnplayedDaily(n) {
  return daily.GAMES.find((g) => !store.getDailyEntry(g, n)) || null;
}

function launchDailyByKey(key, n) {
  const g = GAME_ROWS.find((x) => x.key === key);
  if (g) g.launchDaily(n);
}

// Wire a daily summary's forward button: "Turn the page ›" to the next unplayed
// game, or "Close the issue ›" (→ Home, where the ending shows) once all four
// are played. Hidden for practice/free and any non-today edition, so archive/
// practice flows never surface it. Idempotent (.onclick) — called on every
// summary render.
export function wireTurnThePage(btnId, editionIndex, isDaily) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  const today = daily.todayIndex();
  if (!isDaily || editionIndex !== today) { btn.hidden = true; btn.onclick = null; return; }
  const next = nextUnplayedDaily(today);
  btn.textContent = next ? 'Turn the page ›' : 'Call it a day ›';
  btn.hidden = false;
  btn.onclick = () => { if (next) launchDailyByKey(next, today); else goHome(); };
}

// ---------- First-run intro cards (Change B) ----------
// One shared overlay, per-game content. Reuses each game's start-screen title +
// economy copy, tightened (Thread never had a start screen, so its copy is new).
// Shown once per game before its first daily (misc.introSeen), re-openable any
// time via the topbar "?" as a dismissable overlay that leaves game state alone.
// v164: each entry also carries its poster art, the kicker plate's words and
// the game's accent (the same colour its home-card edge uses in GAME_ROWS).
// accentInk is the text colour that sits on that accent: ink everywhere it
// clears 4.5:1 (magenta on white is only 3.0:1), cream on the print red.
const INTRO_CONTENT = {
  thread: {
    art: 'assets/intro/intro-thread.webp',
    kicker: 'Thread',            // "Thread · thread" would be a stutter, so one word
    accent: 'var(--df-cyan)',
    accentInk: 'var(--ch-ink)',
    title: 'Find the four threads.',
    copy: 'Sixteen clues hide four secret groups of four. Tap the four you think belong together, then submit.',
    copy2: 'A solved board scores 100; each wrong group costs 20, down to a floor of 20. Four wrong guesses and the thread snaps.',
  },
  map: {
    art: 'assets/intro/intro-map.webp',
    kicker: 'Lifeline · Map',
    accent: 'var(--df-yellow)',
    accentInk: 'var(--ch-ink)',
    title: 'Two dots, one life.',
    copy: 'Each round shows where a figure was born and where they died, with the years. Type their name — spelling needn’t be perfect.',
    copy2: 'Each round starts at 100 points. Clues and wrong guesses lower what a correct answer is worth, never below 10.',
  },
  who: {
    art: 'assets/intro/intro-who.webp',
    kicker: 'Face Value · Who',
    accent: 'var(--df-magenta)',
    accentInk: 'var(--ch-ink)',
    title: 'Tear towards it.',
    copy: 'A famous face hides under nine scraps — one is already open. You can only tear scraps touching what’s open, so plot your route.',
    copy2: 'Each round starts at 100 points. Tears, clues and wrong guesses lower what a correct answer is worth, never below 10.',
  },
  what: {
    art: 'assets/intro/intro-what.webp',
    kicker: 'Relic · What',
    accent: 'var(--df-red)',
    accentInk: 'var(--ch-text-inverse)',
    title: 'Tear towards it.',
    copy: 'A famous artefact hides under nine scraps — one is already open. You can only tear scraps touching what’s open, so plot your route.',
    copy2: 'Each round starts at 100 points. Tears, clues and wrong guesses lower what a correct answer is worth, never below 10.',
  },
};

function fillIntro(gameKey) {
  const c = INTRO_CONTENT[gameKey];
  if (!c) return false;
  const art = $('#intro-art-img');
  if (art && !art.src.endsWith(c.art)) art.src = c.art;
  const kicker = $('#intro-kicker');
  if (kicker) kicker.textContent = c.kicker;
  const sheet = $('#intro-sheet');
  if (sheet) {
    sheet.style.setProperty('--intro-accent', c.accent);
    sheet.style.setProperty('--intro-accent-ink', c.accentInk);
  }
  $('#intro-title').textContent = c.title;
  $('#intro-copy').textContent = c.copy;
  $('#intro-copy2').textContent = c.copy2;
  return true;
}

function closeIntro() {
  const ov = $('#intro-card');
  if (ov) { ov.hidden = true; ov.onclick = null; }
}

// First-run gate: show the intro once before a game's first daily, then run
// begin(). Practice/free never call this, so they never see it.
export function maybeIntro(gameKey, n, begin) {
  const seen = (store.getMisc().introSeen || {})[gameKey];
  if (seen || !fillIntro(gameKey)) { begin(); return; }
  const ov = $('#intro-card');
  const btn = $('#intro-play');
  btn.textContent = `Play № ${n} ›`;
  btn.onclick = () => {
    const cur = store.getMisc().introSeen || {};
    store.setMisc({ introSeen: Object.assign({}, cur, { [gameKey]: true }) });
    closeIntro();
    begin();
  };
  ov.onclick = null;             // first run: no tap-outside — the ✕ is the door
  // The way out (4 Aug 2026): back to Home WITHOUT marking the intro seen,
  // so the next tap on the game gets the card again.
  $('#intro-back').onclick = () => closeIntro();
  ov.hidden = false;
}

// Topbar "?": reopen the same card as a dismissable overlay. No game state is
// touched — the round underneath is exactly as it was left.
export function openIntroHelp(gameKey) {
  if (!fillIntro(gameKey)) return;
  const ov = $('#intro-card');
  const btn = $('#intro-play');
  btn.textContent = 'Got it ›';
  btn.onclick = closeIntro;
  ov.onclick = (e) => { if (e.target === ov) closeIntro(); };  // tap-outside dismiss
  $('#intro-back').onclick = closeIntro;
  ov.hidden = false;
}

function initDaily() {
  initArchive();
  // Escape closes the intro in either mode; in first-run mode this is the
  // same "back to Home, intro stays unseen" path as the ✕.
  document.addEventListener('keydown', (e) => {
    const ov = $('#intro-card');
    if (e.key === 'Escape' && ov && !ov.hidden) closeIntro();
  });
}

// ---------- screen-reader announcements (P1.5 + P2.4) ----------
// One polite live region for game feedback (#sr-live in index.html, visually
// hidden — announcements never change how anything looks). Carries, across
// all four games: worth changes, wrong/correct verdicts, Thread one-away,
// round starts and game completion.
export function announce(text) {
  const el = $('#sr-live');
  if (!el) return;
  el.textContent = '';               // clear first so a repeated message re-announces
  setTimeout(() => { el.textContent = text; }, 30);
}

// First wrong guess anywhere (P1.5): the strikethrough guess chip alone is
// too subtle the first time it ever happens — surface the explicit line once,
// in context, then let the chip carry it (the live region still announces
// every wrong guess for screen readers). `srText`, when given, is a fuller
// spoken-only variant (e.g. with the new worth) — the visible one-shot note
// always shows `text` unchanged.
export function teachWrongGuess(noteId, text, srText) {
  announce((srText || text).replace('−', 'minus '));
  if (store.getMisc().wrongTaught) return;
  store.setMisc({ wrongTaught: true });
  const el = document.getElementById(noteId);
  if (el) { el.textContent = text; el.hidden = false; }
}

// ---------- Archive / Practice ----------
// The Morgue is a CALENDAR (owner call 2026-07-15): month grids, newest month
// first, one tappable cell per aired edition. Replaces the old flat
// "Fri / Issue № N" list (and the weekday filter chips a calendar makes
// redundant — the weekday IS the column).
function initArchive() {
  const filterRow = $('#archive-filters');
  if (filterRow) filterRow.hidden = true; // chips retired; calendar columns carry the weekday
  const picker = $('#archive-picker');
  if (picker) {
    picker.querySelectorAll('[data-practice-game]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const g = TODAY_GAMES.find((x) => x.key === btn.dataset.practiceGame);
        const n = +picker.dataset.editionIndex;
        if (!g) return;
        // P2.2: a practice launch gates on ITS game's files (the picker can
        // launch any game, whatever row opened the archive). The button
        // carries the loading/failure state, then gets its label back.
        const label = btn.textContent;
        if (!await ensureGameData(g.key, btn)) {
          setTimeout(() => { btn.textContent = label; }, 1800);
          return;
        }
        btn.textContent = label;
        picker.hidden = true;
        // The repair window (streak rule, Daniel's kinder call 2026-07-10):
        // an edition still completable-for-streak (within 2 days of airing,
        // daily.isStreakValid) and not yet in the ledger launches as the
        // DAILY — this is the only path that can heal a missed day. Anything
        // older, or already completed, is practice as before.
        const today = daily.todayIndex();
        const repairable = daily.isStreakValid(n, today) && !store.getDailyEntry(g.key, n);
        if (repairable) g.launchDaily(n);
        else g.launchPractice(n);
      });
    });
    const closeBtn = $('#archive-picker-close');
    if (closeBtn) closeBtn.addEventListener('click', () => { picker.hidden = true; });
  }
}

function calDots(n) {
  return TODAY_GAMES.map((g) => {
    const status = daily.dailyStatus(g.key, n);
    const dot = status === 'done' ? 'done' : status === 'in-progress' ? 'progress' : '';
    return `<span class="archive-dot ${dot}" title="${g.label}"></span>`;
  }).join('');
}

// One month's grid, Monday-first. `today`/`first`/`last` are edition indices;
// only [first, last] (the trailing aired window) renders as tappable cells.
// Today is marked but not tappable (its edition lives on the front page);
// everything else — older aired days included — renders as dead numbers.
function renderMonth(monthStart, today, first, last) {
  const sec = document.createElement('section');
  sec.className = 'cal-month';
  const title = monthStart.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });
  const dows = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
    .map((d) => `<span class="cal-dow">${d}</span>`).join('');
  const lead = (monthStart.getDay() + 6) % 7;
  const daysInMonth = new Date(monthStart.getFullYear(), monthStart.getMonth() + 1, 0).getDate();
  let cells = '';
  for (let d = 1; d <= daysInMonth; d++) {
    const n = daily.editionIndex(new Date(monthStart.getFullYear(), monthStart.getMonth(), d));
    if (n === today) {
      cells += `<span class="cal-cell today" aria-label="№ ${n} — today">`
        + `<b>${d}</b><span class="cal-dots">${calDots(n)}</span></span>`;
    } else if (n >= first && n <= last) {
      cells += `<button type="button" class="cal-cell" data-edition="${n}"`
        + ` aria-label="№ ${n} · ${daily.weekdayName(n)}">`
        + `<b>${d}</b><span class="cal-dots">${calDots(n)}</span></button>`;
    } else {
      cells += `<span class="cal-cell dead">${d}</span>`;
    }
  }
  for (let i = 0; i < lead; i++) cells = '<span class="cal-cell blank"></span>' + cells;
  sec.innerHTML = `<h3 class="cal-title">${title}</h3><div class="cal-grid">${dows}${cells}</div>`;
  sec.querySelectorAll('[data-edition]').forEach((b) => {
    b.addEventListener('click', () => openArchiveEdition(+b.dataset.edition));
  });
  return sec;
}

function renderArchive() {
  const main = $('#archive-list');
  // The calendar itself needs no content files (dates + the ledger only), so
  // it renders whatever the data situation — per-game gating happens on the
  // practice buttons instead (P2.2).
  if (!main) return;
  main.innerHTML = '';
  const today = daily.todayIndex();
  // The Morgue holds the trailing 7 aired days ONLY (locked decision #4):
  // older editions go dark, which frees their content for rescheduling later
  // without feeling stale. No future previews of any kind — the unaired run
  // must never be browsable (QA uses ?dailydate= instead).
  const first = Math.max(0, today - 7);
  const last = today - 1;
  const newest = daily.editionDate(Math.max(0, today));
  const oldest = daily.editionDate(Math.max(0, Math.min(first, today)));
  const stop = new Date(oldest.getFullYear(), oldest.getMonth(), 1);
  let cursor = new Date(newest.getFullYear(), newest.getMonth(), 1);
  while (cursor >= stop) {
    main.appendChild(renderMonth(cursor, today, first, last));
    cursor = new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1);
  }
}

function openArchiveEdition(editionIndex) {
  const picker = $('#archive-picker');
  if (!picker) return;
  picker.dataset.editionIndex = editionIndex;
  $('#archive-picker-title').textContent = daily.editionLabel(editionIndex);
  picker.hidden = false;
}

function initHome() {
  $('#dateline').innerHTML = datelineHTML(daily.todayIndex());
  // The other three games' free-play "Start a run" views
  // (view-mapstart/view-revealstart) are untouched, but Home no longer links
  // to them directly — free play is reached via Archive → practice (spec
  // "Removals/moves"), so they're hidden routes.
  $$('[data-back]').forEach((b) => b.addEventListener('click', back));

  // The stranger's door (conversion Phase 2): one primary CTA straight into
  // Face Value — the most instantly-graspable first touch. cta-tap measures
  // the door itself; the standard start-who keeps the game funnel comparable.
  const ctaBtn = $('#stranger-play');
  if (ctaBtn) {
    ctaBtn.addEventListener('click', () => {
      track('cta-tap');
      track('start-who');
      launchWhenReady(GAME_ROWS.find((g) => g.key === 'who'));
    });
  }

  // The Ledger (stats) has two doors: tapping the masthead punch card, and the
  // text link in the home footer. Both just route to the view; ledger.js paints
  // it fresh on every visit (render() calls renderLedger).
  const openLedger = () => show('view-ledger');
  const punch = $('#punch-card');
  if (punch) {
    punch.addEventListener('click', openLedger);
    punch.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openLedger(); }
    });
  }
  const ledgerLink = $('#ledger-link');
  if (ledgerLink) ledgerLink.addEventListener('click', openLedger);

  // Sound on/off lives in the home footer — the app has no settings screen.
  const soundBtn = $('#sound-toggle');
  if (soundBtn) {
    const paint = () => { soundBtn.textContent = sfx.isMuted() ? 'Sound off' : 'Sound on'; };
    paint();
    soundBtn.addEventListener('click', () => {
      sfx.setMuted(!sfx.isMuted());
      paint();
      if (!sfx.isMuted()) sfx.play('stamp'); // audible proof it's back on
    });
  }
}

function hasAnyDailyCompletion() {
  const entries = store.getDailyLedger().entries || {};
  return daily.GAMES.some((g) => entries[g] && Object.keys(entries[g]).length > 0);
}

// The stranger's landing (conversion Phase 2): until the first finished
// daily, Home is one headline and one door — week strips, archive bars and
// the punch card are regulars' furniture and stay hidden (see .is-stranger
// rules in style.css). Everything unlocks at the same moment the install
// pitch arrives: the first completed daily.
function applyStrangerMode() {
  const stranger = !hasAnyDailyCompletion();
  document.body.classList.toggle('is-stranger', stranger);
  const hero = $('#stranger-hero');
  if (hero) hero.hidden = !stranger;
}

// The whole "save it as an app" flow — detection, timing, the six screens and
// the strip on Home — lives in js/install.js. app.js only boots it (initInstall
// in boot()) and lends it the QA panel's buttons below; isStandalone is
// imported from there so there is exactly one definition of "installed".

// ---------- QA forcing switch ----------
// ?qa=1 once, then it sticks (misc.qaMode) until switched off from the panel.
// Not host-gated on purpose — see the header of js/qa.js for why that is safe.
function maybeInitQA() {
  const asked = /[?&]qa=1(?:&|$)/.test(location.search);
  if (!asked && !store.getMisc().qaMode) return;
  if (asked && !store.getMisc().qaMode) store.setMisc({ qaMode: true });
  import('./qa.js').then(({ initQA }) => {
    const n = daily.todayIndex();
    // installQA carries the install flow's own forcing actions (the Home strip
    // plus all six install/escape screens) — see js/install.js.
    initQA(Object.assign({}, installQA, {
      introWho: () => openIntroHelp('who'),
      introMap: () => openIntroHelp('map'),
      introWhat: () => openIntroHelp('what'),
      introThread: () => openIntroHelp('thread'),
      // A dead run: last played five editions ago, well past the obituary
      // threshold (lastEdition + 4).
      obituary: () => showObituary(12, Math.max(0, n - 5)),
      celebration: () => showCelebration(n),
      newEdition: () => showNewEditionBar(),
      issueClosed: () => {
        const strip = $('#issue-closed');
        if (!strip) return;
        $('#ic-verdict').textContent = `№ ${n}, done. Some got away.`;
        strip.hidden = false;
        strip.scrollIntoView({ block: 'center' });
      },
    }), store);
  }).catch((e) => console.warn('QA panel unavailable', e));
}

// ---------- P5.2: share deep links ----------
// A ?play=<game> link (thread|map|who|what) routes straight into that
// game's TODAY daily instead of the generic home page, whose CTA only ever
// opens Face Value. Recipients play their OWN today (Wordle convention), so
// any issue number a sender's link might carry is purely informational and
// is never read here — only the game key matters.
//
// shareLaunchGame is set the instant routeSharedPlay calls g.launchDaily and
// consumed synchronously by that game's startEdition (mapgame.js/
// revealgame.js/connectionsgame.js), which flags its own session so the
// first answer submitted can fire answer-from-share-<game>. No async gap
// between the two calls, so a single module variable is safe — at most one
// game ever launches this way per boot.
let shareLaunchGame = null;
export function consumeShareLaunch(gameKey) {
  if (shareLaunchGame !== gameKey) return false;
  shareLaunchGame = null;
  return true;
}

async function routeSharedPlay() {
  const params = new URLSearchParams(location.search);
  const game = params.get('play');
  const valid = ['thread', 'map', 'who', 'what'].indexOf(game) !== -1;
  if (valid) {
    track(`land-share-${game}`);
    const g = GAME_ROWS.find((x) => x.key === game);
    if (g && await ensureGameData(game, null)) {
      shareLaunchGame = game;
      track(`start-from-share-${game}`);
      g.launchDaily(daily.todayIndex());
    }
  }
  // Scrub after routing (track.js does the same for ref/utm): an installed
  // "Add to Home Screen" must never bake a share route into the app's
  // permanent start URL, or every later open would re-route as a share.
  if (params.has('play')) {
    params.delete('play');
    const qs = params.toString();
    history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
  }
}

// ---------- P5.1: abandoned dailies + return milestones ----------
// A daily session still open when local midnight passed it by is
// "abandoned" — checked once per boot, fired once per (game, edition) the
// first boot that notices and never again. finishSession always clears its
// own session key on completion, so any leftover session for an edition
// that's no longer today really was left mid-round, not a stale-but-done one.
function checkAbandonedDailies() {
  const today = daily.todayIndex();
  const misc = store.getMisc();
  const seen = new Set(misc.abandonSeen || []);
  let changed = false;
  store.getDailySessionKeys().forEach((key) => {
    const m = /^chronicle\.daily\.(map|who|what|thread)\.(-?\d+)$/.exec(key);
    if (!m || seen.has(key)) return;
    const game = m[1];
    const n = +m[2];
    if (n >= today) return;
    seen.add(key);
    changed = true;
    if (!store.getDailyEntry(game, n)) track(`abandon-${game}`);
  });
  if (changed) store.setMisc({ abandonSeen: [...seen] });
}

// Return one-shots: a device that skips day 1 and resurfaces on day 9 fires
// ret-d1 and ret-d7 together on that one boot; ret-d30 only once 30+
// editions have actually passed since the first-ever completed daily. Local
// edition-index arithmetic only — never a wall-clock timestamp or anything
// that could compare across devices.
const RETURN_THRESHOLDS = [['ret-d1', 1], ['ret-d7', 7], ['ret-d30', 30]];
function checkReturnMilestones() {
  const first = daily.firstCompletedEdition();
  if (first == null) return;
  const daysSince = daily.todayIndex() - first;
  const misc = store.getMisc();
  const fired = new Set(misc.retFired || []);
  let changed = false;
  RETURN_THRESHOLDS.forEach(([evt, days]) => {
    if (daysSince >= days && !fired.has(evt)) { track(evt); fired.add(evt); changed = true; }
  });
  if (changed) store.setMisc({ retFired: [...fired] });
}

// ---------- boot ----------

// The queen pull, riding native physics (iOS only). The overscroll bounce
// itself is the OS's own rubber band — style.css re-enables it via the
// html.ios override — so flicks and slow drags both bounce exactly like every
// other app on the phone; we add nothing to the page's motion. The
// fixed-position badge just tracks the finger, arms past the threshold, and a
// release past it reloads (which boots any freshly installed edition — see
// sw.js). Everywhere else (Android Chrome's built-in pull-to-refresh would
// fight the gesture; desktop has no rubber band) the page keeps a plain solid
// stop and updates arrive via the tappable NEW EDITION bar instead.
function initPullToRefresh() {
  const home = $('#view-home');
  const badge = $('#ptr-badge');
  const face = badge ? badge.querySelector('.ptr-badge-face') : null;
  if (!home || !badge || !face) return;
  if (!document.documentElement.classList.contains('ios')) return;
  const ARM = 70, MAX = 150, DAMP = 0.55;
  const BADGE = 76;                  // keep in sync with #ptr-badge in style.css
  let y0 = null, x0 = null, pulling = false, pull = 0, armed = false;
  let topOK = false;

  // `overflow-x: hidden` on body promotes it to its own scroll container in
  // some engines (window.scrollY stays 0 and body.scrollTop moves), while
  // iOS Safari scrolls the viewport — so read both. During the native top
  // rubber band this reads negative, which the <= 0 gates below rely on.
  const scrollTop = () =>
    (document.scrollingElement || document.documentElement).scrollTop + document.body.scrollTop;

  // Badge top edge: emerges from behind the screen edge fast enough to reach
  // the centre of the strip the native bounce opens, exactly at the arm
  // threshold, then stays centred in it. Releases only settle below ARM,
  // where the first branch is active — which is what the ptr-badge-settle
  // keyframes mirror.
  const badgeY = (p) => Math.min(1.04 * p - BADGE, 0.5 * p - BADGE / 2);

  const settle = () => {
    badge.style.setProperty('--pull', `${pull.toFixed(1)}px`);
    badge.style.translate = '';
    badge.classList.remove('ptr-armed');
    badge.classList.add('ptr-settle');
    setTimeout(() => {
      badge.classList.remove('ptr-settle');
      badge.hidden = true;
      face.style.rotate = ''; face.style.scale = '';
    }, 700);
    pulling = false; armed = false; pull = 0;
  };

  document.addEventListener('touchstart', (e) => {
    if (home.hidden || e.touches.length !== 1) { y0 = null; return; }
    y0 = e.touches[0].clientY; x0 = e.touches[0].clientX;
    topOK = scrollTop() <= 0;
    pulling = false; armed = false; pull = 0;
  }, { passive: true });

  document.addEventListener('touchmove', (e) => {
    if (y0 == null || home.hidden) return;
    const dy = e.touches[0].clientY - y0;
    const dx = e.touches[0].clientX - x0;
    if (!pulling && Math.abs(dx) > Math.abs(dy)) { y0 = null; return; }  // horizontal strip swipe
    if (!pulling) {
      if (dy > 0 && topOK && scrollTop() <= 0) pulling = true;
      else return;
    }
    if (dy <= 0 || scrollTop() > 0) { if (pull) settle(); return; }
    pull = Math.min(MAX, dy * DAMP);
    armed = pull >= ARM;
    badge.hidden = false;
    badge.classList.remove('ptr-settle');
    badge.style.translate = `0 ${badgeY(pull).toFixed(1)}px`;
    badge.classList.toggle('ptr-armed', armed);
    if (!armed) {
      // Below the arm threshold the badge tracks the pull directly
      // (rotation proportional to distance, scale ramping in across the
      // pull). Past the threshold the ptr-armed CSS animation takes over
      // rotate/scale — the standalone `rotate`/`scale` properties compose
      // independently of these inline styles instead of clobbering them
      // the way animating `transform` itself would.
      face.style.rotate = `${(pull * 2.6).toFixed(1)}deg`;
      face.style.scale = Math.min(1, 0.55 + (pull / ARM) * 0.45).toFixed(2);
    }
  }, { passive: true });

  document.addEventListener('touchend', () => {
    if (y0 == null) return;
    y0 = null;
    if (!pulling) return;
    if (armed) {
      badge.classList.remove('ptr-armed');
      badge.classList.add('ptr-go');
      setTimeout(() => location.reload(), 700);
      return;                       // the badge spins in place while the page springs back
    }
    settle();
  }, { passive: true });

  if (testHooksEnabled()) {
    window.__CHRONICLE_TEST__ = Object.assign(window.__CHRONICLE_TEST__ || {}, {
      ptr: {
        isArmed: () => armed,
        isPulling: () => pulling,
      },
    });
  }
}


// ---------- You Made History / You're History ----------
// Celebration when all four dailies are done; obituary when a streak dies.
// One-shot flags live in localStorage so neither screen nags twice.
let ddCountdownTimer = null;

function flagGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
function flagSet(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } }

function fullHouseDone(n) {
  const ledger = store.getDailyLedger();
  return daily.GAMES.every((g) => ledger.entries[g] && ledger.entries[g][n]);
}
// A "win" is any daily that scored above zero; scoring nothing (giving up every
// round, or losing the Thread board) is a loss. The full-house celebration is
// the reward for winning all four — a day finished with a loss gets the quiet
// edition-closed strip instead (Change A). The ledger/streak/punch-card
// semantics stay completion-based (fullHouseDone), untouched.
function allWon(n) {
  const ledger = store.getDailyLedger();
  return daily.GAMES.every((g) => {
    const e = ledger.entries[g] && ledger.entries[g][n];
    return !!e && (e.score || 0) > 0;
  });
}
function dayTotal(n) {
  const ledger = store.getDailyLedger();
  return daily.GAMES.reduce((sum, g) => {
    const e = ledger.entries[g] && ledger.entries[g][n];
    return sum + ((e && e.score) || 0);
  }, 0);
}
// What the day-done share button sends: set by showCelebration (full-house
// receipt) or showObituary (the wake) so one button serves both moments.
let dayDoneShare = null;

function fullHouseShare(n) {
  const ledger = store.getDailyLedger();
  const scores = {};
  daily.GAMES.forEach((g) => {
    const e = ledger.entries[g] && ledger.entries[g][n];
    scores[g] = (e && e.score) || 0;
  });
  const streak = (ledger.fullHouse && ledger.fullHouse.streak) || 1;
  const total = dayTotal(n);
  return {
    text: fullHouseShareText(n, scores, total, streak),
    card: {
      game: 'FULL HOUSE', glyph: '🏛️', score: total, sub: `ISSUE № ${n}`,
      rows: [`🧵 ${scores.thread}   🗺️ ${scores.map}`, `🖼️ ${scores.who}   🏺 ${scores.what}`]
        .concat(streak > 1 ? [`🔥 ${streak}-day streak`] : []),
      url: shareUrl(),
    },
    trackAs: 'share-fullhouse',
    idle: "Share today's receipt",
  };
}

// Shared "time to local midnight" readout, reused by the full-house
// celebration and the edition-closed strip (Change A).
function countdownText() {
  const now = new Date();
  const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const ms = midnight - now;
  const h = String(Math.floor(ms / 3600000)).padStart(2, '0');
  const m = String(Math.floor((ms % 3600000) / 60000)).padStart(2, '0');
  const sec = String(Math.floor((ms % 60000) / 1000)).padStart(2, '0');
  return `New games in<b>${h}:${m}:${sec}</b>`;
}

function startCountdown() {
  const el = $('#dd-countdown');
  if (!el) return;
  el.hidden = false;
  const tick = () => { el.innerHTML = countdownText(); };
  tick();
  clearInterval(ddCountdownTimer);
  ddCountdownTimer = setInterval(tick, 1000);
}

// The edition-closed strip: a quiet Home banner shown once all four of today's
// dailies are played but at least one was lost (an all-won day gets You Made
// History instead). Its live countdown ticks only while Home is on screen —
// render() stops it on every non-Home view.
let icCountdownTimer = null;
function stopIssueClosedCountdown() { clearInterval(icCountdownTimer); icCountdownTimer = null; }

function refreshIssueClosed() {
  const strip = $('#issue-closed');
  if (!strip) return;
  const n = daily.todayIndex();
  if (!(n >= 0 && fullHouseDone(n) && !allWon(n))) { strip.hidden = true; stopIssueClosedCountdown(); return; }
  $('#ic-verdict').textContent = `№ ${n}, done. Some got away.`;
  $('#ic-score').textContent = dayTotal(n);
  strip.hidden = false;
  const tick = () => { $('#ic-countdown').innerHTML = countdownText(); };
  tick();
  clearInterval(icCountdownTimer);
  icCountdownTimer = setInterval(tick, 1000);
}

function showCelebration(n) {
  flagSet('df.celebrated', String(n));
  sfx.play('fanfare');
  const v = $('#view-daydone');
  v.classList.remove('obituary');
  $('#dd-issue').textContent = `№ ${n}`;
  $('#dd-title').textContent = 'You made history.';
  $('#dd-score-label').textContent = "Today's total";
  $('#dd-total').textContent = dayTotal(n);
  const ledger = store.getDailyLedger();
  const streak = (ledger.fullHouse && ledger.fullHouse.streak) || 1;
  $('#dd-streak-label').textContent = 'Streak';
  $('#dd-streak').textContent = `${streak} day${streak === 1 ? '' : 's'}`;
  $('#dd-stamp').hidden = true;
  $('#dd-carpet').hidden = false;
  // Milestone postmarks (streak look "combo"): front-loaded early — the
  // research says days 2/3/5/7 are where celebration moves retention most.
  const MILESTONES = [2, 3, 5, 7, 10, 25, 50, 100];
  const milestone = MILESTONES.includes(streak);
  $('#dd-milestone').hidden = !milestone;
  if (milestone) $('#dd-milestone-n').textContent = `№${streak}`;
  dayDoneShare = fullHouseShare(n);
  $('#dd-share').textContent = dayDoneShare.idle;
  $('#dd-share').hidden = false;
  startCountdown();
  show('view-daydone');
}

function showObituary(streak, lastEdition) {
  flagSet('df.mourned', String(lastEdition));
  sfx.play('toll');
  const v = $('#view-daydone');
  v.classList.add('obituary');
  $('#dd-issue').textContent = `№ ${daily.todayIndex()}`;
  $('#dd-title').textContent = "You're history.";
  $('#dd-score-label').textContent = 'Your streak ended at';
  $('#dd-total').textContent = `${streak} days`;
  $('#dd-streak-label').textContent = 'Rest in peace';
  $('#dd-streak').textContent = `Days ${Math.max(0, lastEdition - streak + 1)}–${lastEdition}`;
  $('#dd-stamp').hidden = false;
  $('#dd-carpet').hidden = true;
  $('#dd-milestone').hidden = true;
  // The obituary is the most human share in the app — dark humour travels.
  dayDoneShare = {
    text: obituaryShareText(streak, Math.max(0, lastEdition - streak + 1), lastEdition),
    card: {
      game: 'IN MEMORIAM', glyph: '⚰️', score: streak, unit: 'DAYS',
      sub: `ISSUES №${Math.max(0, lastEdition - streak + 1)}–№${lastEdition}`,
      rows: [], stamp: 'MEMENTO MORI',
      url: shareUrl(),
    },
    trackAs: 'share-obituary',
    idle: 'Share the obituary',
  };
  $('#dd-share').textContent = dayDoneShare.idle;
  $('#dd-share').hidden = false;
  $('#dd-countdown').hidden = true;
  show('view-daydone');
}

function maybeCelebrate() {
  const n = daily.todayIndex();
  // You Made History is the reward for winning all four (Change A). A day
  // finished with a loss falls through to the edition-closed strip on Home.
  if (allWon(n) && flagGet('df.celebrated') !== String(n)) showCelebration(n);
}
function maybeMourn() {
  const ledger = store.getDailyLedger();
  const fh = ledger.fullHouse || { streak: 0, lastEdition: -Infinity };
  const today = daily.todayIndex();
  // Dead means beyond repair: the first missed edition (lastEdition + 1) can
  // be healed until (lastEdition + 1) + 2, so the wake happens the day after.
  if (fh.streak >= 3 && Number.isFinite(fh.lastEdition) && fh.lastEdition <= today - 4
      && flagGet('df.mourned') !== String(fh.lastEdition)) {
    showObituary(fh.streak, fh.lastEdition);
    return true;
  }
  return false;
}

function initDayDone() {
  $('#dd-close').addEventListener('click', goHome);
  $('#dd-home').addEventListener('click', goHome);
  $('#dd-share').addEventListener('click', async () => {
    if (!dayDoneShare) return;
    const btn = $('#dd-share');
    const out = await shareResult(dayDoneShare);
    flashShareButton(btn, out, dayDoneShare.idle);
  });
  document.addEventListener('viewchange', (e) => {
    if (e.detail === 'view-home') maybeCelebrate();
    if (e.detail !== 'view-daydone') clearInterval(ddCountdownTimer);
  });
}

// ---------- data ----------
// Independent per-file loading (P2.2): each game's launch gates only on the
// files IT needs, so one broken file can no longer take all four games down.
// A file that loaded once stays good in memory for the whole session; across
// restarts the service worker's stale-while-revalidate (sw.js DATA_CACHE)
// serves the last good copy. editions.json (the daily manifest) is attempted
// with every gate but its failure never blocks anything — getEdition falls
// back to the legacy arithmetic (Session 3) and fires err-manifest-missing.
const DATA_FILES = {
  figures: 'data/figures.json',
  world: 'data/worldmap.json',
  revealWho: 'data/reveal-who.json',
  revealWhat: 'data/reveal-what.json',
  connections: 'data/connections.json',
  editions: 'data/editions.json',
};
const GAME_NEEDS = {
  map: ['figures', 'world'],
  who: ['revealWho', 'revealWhat'],
  what: ['revealWho', 'revealWhat'],
  thread: ['connections'],
};
const fileData = {};        // key -> parsed JSON, kept once loaded (last-good)
const filePromises = {};    // key -> in-flight fetch; cleared on failure so a tap retries
const fileErrTracked = {};  // one 'err-data-<basename>' beacon per file per session

function loadFile(key) {
  if (fileData[key] !== undefined) return Promise.resolve(true);
  if (filePromises[key]) return filePromises[key];
  filePromises[key] = fetch(DATA_FILES[key])
    .then((r) => {
      if (!r.ok) throw new Error('failed to load ' + DATA_FILES[key]);
      return r.json();
    })
    .then((json) => {
      fileData[key] = json;
      wireLoadedGames();
      return true;
    })
    .catch(() => {
      filePromises[key] = null;
      if (!fileErrTracked[key]) {
        fileErrTracked[key] = true;
        track('err-data-' + DATA_FILES[key].split('/').pop().replace('.json', ''));
      }
      return false;
    });
  return filePromises[key];
}

// As each game's file set completes, publish it into DATA and wire that
// game's module exactly once — no launch path can outrun this, because every
// one of them awaits ensureGameData() first.
const wiredGames = {};
function wireLoadedGames() {
  if (!wiredGames.map && fileData.figures !== undefined && fileData.world !== undefined) {
    wiredGames.map = true;
    DATA.figures = fileData.figures;
    DATA.world = fileData.world;
    initMapGame();
  }
  if (!wiredGames.reveal && fileData.revealWho !== undefined && fileData.revealWhat !== undefined) {
    wiredGames.reveal = true;
    // reveal-who.json (portraits) + reveal-what.json (artefacts) are the
    // current, actively-curated content files; DATA.reveal is their union,
    // filtered by `kind` downstream (revealgame.js) exactly as before.
    DATA.reveal = fileData.revealWho.concat(fileData.revealWhat);
    initRevealGame();
  }
  if (!wiredGames.thread && fileData.connections !== undefined) {
    wiredGames.thread = true;
    DATA.connections = fileData.connections;
    initConnectionsGame();
  }
  if (fileData.editions !== undefined) DATA.editions = fileData.editions;
}

// Boot-time warm-up: start every download in parallel, then prefetch today's
// images once the reveal pools AND the manifest attempt have settled (the
// manifest names which items today's edition actually holds).
function loadAllData() {
  const editionsAttempt = loadFile('editions');
  Object.keys(DATA_FILES).forEach((k) => { if (k !== 'editions') loadFile(k); });
  Promise.all([loadFile('revealWho'), loadFile('revealWhat'), editionsAttempt])
    .then(([who, what]) => {
      if (who && what) setTimeout(prefetchDailyImages, 1200); // after first paint settles
    });
}

// Gate a launch on one game's files. `statusEl` (the tapped card's status
// line) doubles as the loading state; a failure names itself there and the
// same tap retries. The editions manifest is awaited too — so a fast first
// tap can't race it and serve fallback arithmetic — but its result never
// blocks: the Session 3 fallback covers it.
async function ensureGameData(gameKey, statusEl) {
  const needs = GAME_NEEDS[gameKey] || [];
  if (needs.every((k) => fileData[k] !== undefined) && fileData.editions !== undefined) return true;
  const slow = setTimeout(() => {
    if (statusEl) statusEl.textContent = 'spinning up the presses…';
  }, 150);
  const results = await Promise.all(needs.map(loadFile));
  await loadFile('editions');
  clearTimeout(slow);
  const ok = results.every(Boolean);
  if (!ok && statusEl) statusEl.textContent = 'couldn’t load — tap to retry';
  return ok;
}

// The farewell strip (cutover, 4 Aug 2026). Hostname-gated so only the OLD
// house ever shows it: both domains serve the same code from `release`, and
// installed deadfamous PWAs freeze on this build once the 301s land — the
// strip and its carry button are the last thing they'll ever show.
function initMovingNote() {
  const note = document.getElementById('moving-note');
  if (!note || !/(^|\.)deadfamous\./.test(location.hostname)) return;
  note.hidden = false;
  const btn = document.getElementById('moving-carry-btn');
  if (btn) btn.addEventListener('click', () => { carry.openExport(); track('moving-note-carry'); });
}

async function boot() {
  // FIRST, before anything else reads or rewrites the URL: a carry link puts
  // the player's whole record in the fragment, and both initTracking and
  // routeSharedPlay call replaceState with location.hash carried along. Grab
  // it and scrub it here, and neither of them can ever see it (or bake it into
  // an "Add to Home Screen" start URL). The offer itself waits until the end
  // of boot, when there is an app to show it over.
  carry.captureIncoming();
  initTracking();
  // A crash in the wild is otherwise invisible (a broken deploy on one iOS
  // version, say). One anonymous event per session; the event name carries
  // only a bounded discriminator (script basename / rejection type — never
  // messages, which can hold URLs). Full detail is kept on the affected
  // device only (misc.lastError) so a reproducible report can be read there.
  let errTracked = false;
  const trackErr = (kind, tag, detail) => {
    try {
      store.setMisc({ lastError: { kind, detail: String(detail).slice(0, 300), at: Date.now(), build: BUILD } });
    } catch (e2) { /* never break on the way down */ }
    if (errTracked) return;
    errTracked = true;
    track(`9-app-${kind}${tag ? '-' + tag : ''}`);
  };
  window.addEventListener('error', (e) => {
    const src = String(e.filename || '').split('/').pop().split('?')[0]
      .toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 20);
    trackErr('error', src || 'unknown', `${e.message} @ ${e.filename}:${e.lineno}`);
  });
  window.addEventListener('unhandledrejection', (e) => {
    const nm = (e.reason && e.reason.name ? String(e.reason.name) : 'unknown')
      .toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 20);
    trackErr('rejection', nm, e.reason && (e.reason.stack || e.reason.message) || e.reason);
  });
  // The opening funnel, one event per boot: installed-app vs browser tab,
  // first-ever visit vs a return. These four paths are the denominators for
  // every start/finish/share rate on the dashboard.
  track(isStandalone() ? 'open-pwa' : 'open-browser');
  if (store.getMisc().seenBefore) track('open-return');
  else { track('open-new'); store.setMisc({ seenBefore: true }); }
  daily.normalizeLedgerScales();
  checkAbandonedDailies();
  checkReturnMilestones();
  // Free-play bests recorded before the rebase were 10-round sums; rescale
  // them onto the same 0–100 dial (approximate: sum/rounds).
  const mapStats = store.getMap();
  if (mapStats.bestScore > 100) {
    mapStats.bestScore = Math.min(100, Math.round(mapStats.bestScore / 10));
    store.setMap(mapStats);
  }
  for (const m of ['who', 'what']) {
    const r = store.getReveal(m);
    if (r.bestScore > 100) {
      r.bestScore = Math.min(100, Math.round(r.bestScore / 10));
      store.setReveal(m, r);
    }
  }
  sfx.initSfx(); // before the data fetch so sound decoding overlaps it

  // Conversion Phase 1: the landing is static markup + localStorage, so it
  // paints before a single data byte arrives. The downloads start here and
  // run behind it; only a tap into a game ever waits on the files that game
  // needs (ensureGameData).
  loadAllData();
  routeSharedPlay();

  initPullToRefresh();
  initHome();
  initDaily();
  initDayDone();
  carry.initCarry();
  initInstall();
  initMovingNote();
  refreshHomeStats();
  refreshTodayStrip();
  if (!maybeMourn()) maybeCelebrate();
  // Boot renders Home without going through render() (the view is visible by
  // default), so paint the edition-closed strip here too — unless a moment
  // screen (mourn/celebrate) already navigated away.
  if (trail[trail.length - 1] === 'view-home') refreshIssueClosed();

  maybeInitQA();

  // A record that just arrived from another device changes every number on
  // screen. carry.js announces rather than imports app.js (that would be a
  // cycle), so the repaint is wired here.
  document.addEventListener('carrydone', () => {
    daily.normalizeLedgerScales();
    refreshHomeStats();
    refreshTodayStrip();
    renderLedger();
  });
  // The offer goes last: decoding is async, and the sheet should open over a
  // painted app rather than a blank one.
  carry.offerIncoming();

  // Deterministic hooks for the automated test-suite.
  // nav exists for tests/test_no_dead_ends.py: it walks EVERY view in
  // index.html — including view-mapstart/view-revealstart, which no UI route
  // reaches today — and asserts each one's way back. Router only: it switches
  // views, exactly as a tap would, and can neither load nor reveal content.
  if (testHooksEnabled()) {
    window.__CHRONICLE_TEST__ = Object.assign(window.__CHRONICLE_TEST__ || {},
      { data: DATA, store, isMatch, daily, carry: carry.testHooks(),
        install: installHooks(),
        nav: { show, back, goHome, trail: () => trail.slice() } });
  }

  const buildTag = $('#build-tag');
  if (buildTag) {
    buildTag.textContent = BUILD;
    // Owner's kill switch: five quick taps on the version number toggle
    // GoatCounter's own localStorage opt-out ('skipgc' — the same flag
    // #toggle-goatcounter sets). Exists because the installed app has no
    // address bar, so the hash route can't reach it there.
    let taps = 0, tapTimer = null;
    buildTag.addEventListener('click', () => {
      taps++;
      clearTimeout(tapTimer);
      tapTimer = setTimeout(() => { taps = 0; }, 1200);
      if (taps < 5) return;
      taps = 0;
      const off = localStorage.getItem('skipgc') !== 't';
      localStorage.setItem('skipgc', off ? 't' : 'f');
      buildTag.textContent = off ? 'off the record' : 'back on the record';
      setTimeout(() => { buildTag.textContent = BUILD; }, 2000);
    });
  }

  if ('serviceWorker' in navigator && location.protocol.indexOf('http') === 0) {
    // P5.1: the image cache lives inside the service worker, which has no
    // window.goatcounter of its own — a failed cache write posts a message
    // here instead. One beacon per session, same shape as every other
    // err-* dedupe in this file.
    let imgCacheErrTracked = false;
    navigator.serviceWorker.addEventListener('message', (e) => {
      if (e.data && e.data.type === 'df-img-cache-fail' && !imgCacheErrTracked) {
        imgCacheErrTracked = true;
        track('err-img-cache');
      }
    });
    navigator.serviceWorker.register('sw.js').then((reg) => {
      // iOS only re-checks sw.js on a cold launch — resuming from the app
      // switcher is not a navigation — so ask for an update check on every
      // wake-up ourselves. This is what makes deploys actually reach phones.
      const check = () => { reg.update().catch(() => {}); };
      document.addEventListener('visibilitychange', () => {
        if (!document.hidden) check();
      });
      check();
      // No controller at registration time = very first visit, already on the
      // newest version. Otherwise any controllerchange means a fresh worker
      // (skipWaiting+claim in sw.js) has the new edition ready: invite the
      // customary gesture — the next reload boots it.
      if (navigator.serviceWorker.controller) {
        navigator.serviceWorker.addEventListener('controllerchange', showNewEditionBar);
      }
    }).catch(() => {});
  }
}

// P5.3a: assets/img/w800/<name>.webp is a pre-generated copy of every source
// image (tools/build_image_variants.py) — longest edge 800px, same aspect
// ratio, a fraction of the bytes. Every image load below tries it first and
// falls back to the full original on any error (missing variant, a
// generation miss) — a plain onerror swap, no feature detection needed
// (WebP support is universal in 2026).
export function w800Url(path) {
  const slash = path.lastIndexOf('/');
  const name = path.slice(slash + 1).replace(/\.[a-zA-Z0-9]+$/, '.webp');
  return `${path.slice(0, slash + 1)}w800/${name}`;
}

// Loads `path` via its w800 variant, swapping to the full original if that
// 404s or fails to decode. onload(img, resolvedSrc) fires with whichever
// Image actually loaded; onerror fires only if BOTH attempts fail.
export function loadImgFallback(path, onload, onerror) {
  const img = new Image();
  img.onload = () => onload(img, w800Url(path));
  img.onerror = () => {
    const orig = new Image();
    orig.onload = () => onload(orig, path);
    orig.onerror = onerror;
    orig.src = path;
  };
  img.src = w800Url(path);
}

// Warm today's Face Value / Relic images so the dailies stay playable offline
// (the aeroplane rule, owner report 2026-07-15): each request routes through
// the service worker, which files the bytes into the version-bump-proof
// df-img cache. Sequential so it never competes with an image the player is
// actually looking at. Installed apps (standalone) also warm tomorrow's
// edition as a buffer for a day spent entirely offline — browser tabs don't,
// since the daily shrank to 5+5 files and casual visitors shouldn't pay for
// a tomorrow they may never open (P5.3, brought forward).
function prefetchDailyImages() {
  const today = daily.todayIndex();
  if (today < 0) return;
  const urls = [];
  const seen = new Set();
  for (const n of (isStandalone() ? [today, today + 1] : [today])) {
    for (const game of ['who', 'what']) {
      for (const item of daily.getEdition(game, n)) {
        if (item.img && !seen.has(item.img)) { seen.add(item.img); urls.push(item.img); }
      }
    }
  }
  const next = () => {
    const u = urls.shift();
    if (!u) return;
    loadImgFallback(u, next, next);
  };
  next();
}

// The "off the presses" bar: appears once a new version has installed and
// taken over underneath the running page. Pull-to-refresh (or tapping the
// bar, for desktop and mid-game views where the pull is unavailable) reloads
// into it.
function showNewEditionBar() {
  if ($('#new-edition')) return;
  const bar = document.createElement('button');
  bar.id = 'new-edition';
  bar.type = 'button';
  bar.innerHTML = document.documentElement.classList.contains('ios')
    ? '✨ New version ready — <b>pull down to refresh</b>'
    : '✨ New version ready — <b>tap to refresh</b>';
  bar.addEventListener('click', () => location.reload());
  document.body.appendChild(bar);
}

boot();
