// Boot, data loading, view router, home screen.
// BUILD is shown in the home footer; bump it together with sw.js VERSION on
// every deploy so what phones display always names what they are running.
const BUILD = 'v115';

// iOS (incl. iPadOS, which masquerades as MacIntel) gets the OS's own
// overscroll physics back — style.css keys native rubber-banding off this
// class, and initPullToRefresh rides it. Everywhere else stays solid-stop.
if (/iP(hone|ad|od)/.test(navigator.userAgent)
    || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)) {
  document.documentElement.classList.add('ios');
}

import * as store from './storage.js';
import { track, initTracking } from './track.js';
import { fullHouseShareText, obituaryShareText, shareResult, flashShareButton } from './sharecard.js';
import { isMatch } from './match.js';
import { initMapGame, renderMapStart, startMapDaily, startMapPractice } from './mapgame.js';
import { initRevealGame, renderRevealStart, startRevealDaily, startRevealPractice } from './revealgame.js';
import { initConnectionsGame, startThreadDaily, startThreadPractice } from './connectionsgame.js';
import * as daily from './daily.js';
import * as sfx from './sfx.js';
import { renderLedger } from './ledger.js';

export const DATA = { figures: null, world: null, reveal: null, connections: null };
export const $ = (sel) => document.querySelector(sel);
export const $$ = (sel) => Array.from(document.querySelectorAll(sel));

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
// One row per game, in the fixed presentation order Thread, Lifeline,
// Face Value, Relic. `launchDaily`/`launchPractice` take the edition index.
// Per-row accent tints are Archive Codex versions of NYT's per-game colour
// coding (spec "Per-row accent tints"): a strong tint for the hero card, a
// slightly lighter one (lower mix %) for day cards + the Archive bar.
const GAME_ROWS = [
  {
    key: 'thread', label: 'Thread', tagline: 'Group 16 clues into four hidden categories.',
    glyph: 'assets/brand/game-icon-thread.png',
    tintStrong: 'var(--df-cyan)',
    tintSoft: 'color-mix(in srgb, var(--df-cyan) 14%, var(--ch-cream))',
    launchDaily: startThreadDaily, launchPractice: startThreadPractice,
  },
  {
    key: 'map', label: 'Lifeline', tagline: 'Born here, died there. Name the figure.',
    glyph: 'assets/brand/game-icon-lifeline.png',
    tintStrong: 'var(--df-yellow)',
    tintSoft: 'color-mix(in srgb, var(--df-yellow) 18%, var(--ch-cream))',
    launchDaily: startMapDaily, launchPractice: startMapPractice,
  },
  {
    key: 'who', label: 'Face Value', tagline: 'A famous face, one scrap at a time.',
    glyph: 'assets/brand/game-icon-face-value.png',
    tintStrong: 'var(--df-magenta)',
    tintSoft: 'color-mix(in srgb, var(--df-magenta) 12%, var(--ch-cream))',
    launchDaily: (n) => startRevealDaily('who', n), launchPractice: (n) => startRevealPractice('who', n),
  },
  {
    key: 'what', label: 'Relic', tagline: 'A famous artefact, one scrap at a time.',
    glyph: 'assets/brand/game-icon-relic.png',
    tintStrong: 'var(--df-red)',
    tintSoft: 'color-mix(in srgb, var(--df-red) 10%, var(--ch-cream))',
    launchDaily: (n) => startRevealDaily('what', n), launchPractice: (n) => startRevealPractice('what', n),
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

  GAME_ROWS.forEach((g) => {
    $(`[data-hero="${g.key}"]`).addEventListener('click', () => {
      track(`start-${g.key}`);
      launchWhenReady(g);
    });
    $(`[data-archive="${g.key}"]`).addEventListener('click', async () => {
      if (!await ensureData($(`[data-row="${g.key}"] [data-status]`))) return;
      renderArchive();
      show('view-archive');
    });
  });
}

// Launch a game from Home, waiting out the background data download if the
// player outran it. The card's own status line doubles as the loading state.
async function launchWhenReady(g) {
  const statusEl = document.querySelector(`[data-hero="${g.key}"] [data-status]`);
  if (!await ensureData(statusEl)) return;
  g.launchDaily(daily.todayIndex());
}

async function ensureData(statusEl) {
  if (dataLoaded) return true;
  const slow = setTimeout(() => {
    if (statusEl) statusEl.textContent = 'spinning up the presses…';
  }, 150);
  const ok = await loadData();
  clearTimeout(slow);
  if (!ok && statusEl) statusEl.textContent = 'offline — tap to retry';
  return ok;
}

// Card #6 (difficulty whisper): the dateline gains a muted, lowercase,
// em-dash-separated whisper naming today's edition's spot on the Mon->Sun
// difficulty ladder (daily.weekdayWhisper). Weekday comes from the edition
// index (not the raw device date) so it honours the ?dailydate= QA override
// the same way the issue number already does.
function datelineHTML(n) {
  const safe = Math.max(0, n);
  return `Issue № ${safe} // ${daily.weekdayName(safe)} `
    + `<span class="dateline-whisper">— ${daily.weekdayWhisper(safe)}</span>`;
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
    hero.querySelector('[data-edition]').textContent = `ISSUE № ${Math.max(0, today)}`;
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
// The next of today's four dailies (home order: Thread, Lifeline, Face Value,
// Relic == daily.GAMES) with no ledger entry yet, or null once all four are
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
  btn.textContent = next ? 'Turn the page ›' : 'Close the issue ›';
  btn.hidden = false;
  btn.onclick = () => { if (next) launchDailyByKey(next, today); else goHome(); };
}

// ---------- First-run intro cards (Change B) ----------
// One shared overlay, per-game content. Reuses each game's start-screen title +
// economy copy, tightened (Thread never had a start screen, so its copy is new).
// Shown once per game before its first daily (misc.introSeen), re-openable any
// time via the topbar "?" as a dismissable overlay that leaves game state alone.
const INTRO_CONTENT = {
  thread: {
    glyph: 'assets/brand/game-icon-thread.png',
    title: 'Find the four threads.',
    copy: 'Sixteen clues hide four secret groups of four. Tap the four you think belong together, then submit.',
    copy2: 'A solved board scores 100; each wrong group costs 20, down to a floor of 20. Four wrong guesses and the thread snaps.',
  },
  map: {
    glyph: 'assets/brand/game-icon-lifeline.png',
    title: 'Ten lives, twenty dots.',
    copy: 'Each round shows where a figure was born and where they died, with the years. Type their name — spelling needn’t be perfect.',
    copy2: '100 points for an unaided answer (a correct one always pays at least 10). Clue slips cost 15–25, wrong guesses 15, revealing scores zero. Each correct answer from the second in a row earns +10. Your issue score is your round average.',
  },
  who: {
    glyph: 'assets/brand/game-icon-face-value.png',
    title: 'Tear towards it.',
    copy: 'A famous face hides under nine scraps — one is already open. You can only tear scraps touching what’s open, so plot your route.',
    copy2: 'Each round is worth 100. Tears cost 10, wrong guesses 15, and clue slips 15–25. Two right in a row earns +10. Your issue score is your round average.',
  },
  what: {
    glyph: 'assets/brand/game-icon-relic.png',
    title: 'Tear towards it.',
    copy: 'A famous artefact hides under nine scraps — one is already open. You can only tear scraps touching what’s open, so plot your route.',
    copy2: 'Each round is worth 100. Tears cost 10, wrong guesses 15, and clue slips 15–25. Two right in a row earns +10. Your issue score is your round average.',
  },
};

function fillIntro(gameKey) {
  const c = INTRO_CONTENT[gameKey];
  if (!c) return false;
  $('#intro-glyph').src = c.glyph;
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
  ov.onclick = null;             // first run: only the button proceeds
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
  ov.hidden = false;
}

function initDaily() {
  initArchive();
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
      btn.addEventListener('click', () => {
        const g = TODAY_GAMES.find((x) => x.key === btn.dataset.practiceGame);
        const n = +picker.dataset.editionIndex;
        picker.hidden = true;
        if (g) g.launchPractice(n);
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

// One month's grid, Monday-first. `today`/`last` are edition indices; cells
// outside [0, last] render as dead numbers, today is marked but not tappable
// (its edition lives on the front page), future-but-previewable editions are
// tappable at reduced weight (pre-launch QA browsing).
function renderMonth(monthStart, today, last) {
  const sec = document.createElement('section');
  sec.className = 'cal-month';
  const title = monthStart.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });
  const dows = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
    .map((d) => `<span class="cal-dow">${d}</span>`).join('');
  const lead = (monthStart.getDay() + 6) % 7;
  const daysInMonth = new Date(monthStart.getFullYear(), monthStart.getMonth() + 1, 0).getDate();
  let cells = '';
  for (let i = 0; i < lead; i++) cells += '<span class="cal-cell blank"></span>';
  for (let d = 1; d <= daysInMonth; d++) {
    const n = daily.editionIndex(new Date(monthStart.getFullYear(), monthStart.getMonth(), d));
    if (n < 0 || n > last) {
      cells += `<span class="cal-cell dead">${d}</span>`;
    } else if (n === today) {
      cells += `<span class="cal-cell today" aria-label="Issue № ${n} — today, on the front page">`
        + `<b>${d}</b><span class="cal-dots">${calDots(n)}</span></span>`;
    } else {
      cells += `<button type="button" class="cal-cell${n > today ? ' future' : ''}" data-edition="${n}"`
        + ` aria-label="Issue № ${n} · ${daily.weekdayName(n)}">`
        + `<b>${d}</b><span class="cal-dots">${calDots(n)}</span></button>`;
    }
  }
  sec.innerHTML = `<h3 class="cal-title">${title}</h3><div class="cal-grid">${dows}${cells}</div>`;
  sec.querySelectorAll('[data-edition]').forEach((b) => {
    b.addEventListener('click', () => openArchiveEdition(+b.dataset.edition));
  });
  return sec;
}

function renderArchive() {
  const main = $('#archive-list');
  if (!main || !DATA.figures) return;
  main.innerHTML = '';
  const today = daily.todayIndex();
  // Visibility rule (spec): n < today (aired) OR n <= today + preview. Pre-
  // launch ARCHIVE_PREVIEW_EDITIONS is Infinity ("everything visible"); cap
  // the render window at a generous but finite lookahead so the calendar
  // stays finite even with an Infinity config.
  const last = today + (Number.isFinite(daily.ARCHIVE_PREVIEW_EDITIONS) ? daily.ARCHIVE_PREVIEW_EDITIONS : 180);
  const firstMonth = daily.editionDate(0);
  const stop = new Date(firstMonth.getFullYear(), firstMonth.getMonth(), 1);
  const lastDate = daily.editionDate(Math.max(0, last));
  let cursor = new Date(lastDate.getFullYear(), lastDate.getMonth(), 1);
  while (cursor >= stop) {
    main.appendChild(renderMonth(cursor, today, last));
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

  $('#install-tip-close').addEventListener('click', () => {
    $('#install-tip').hidden = true;
    store.setMisc({ installTipDismissed: true });
    track('install-tip-dismiss');
  });
  // Chromium fires beforeinstallprompt when the app is installable; stow the
  // event (preventDefault also mutes Chrome's own mini-infobar) and pitch at
  // OUR moment — after the first finished daily, like the iOS tip.
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredInstall = e;
    maybeShowInstallTip();
  });
  window.addEventListener('appinstalled', () => {
    track('install-accepted');
    const tip = $('#install-tip');
    if (tip) tip.hidden = true;
  });
  $('#install-btn').addEventListener('click', () => {
    const ev = deferredInstall;
    if (!ev) return;
    deferredInstall = null;
    track('install-tip-tap');
    ev.prompt();
    ev.userChoice.then((c) => {
      if (!c || c.outcome !== 'accepted') track('install-declined');
      $('#install-tip').hidden = true;
    }).catch(() => {});
  });

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
  document.addEventListener('viewchange', (e) => {
    if (e.detail === 'view-home') maybeShowInstallTip();
  });
  maybeShowInstallTip();
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

// The install pitch waits for the first finished daily — the moment a streak
// exists to protect. "Keeps your streak safe" is literal: Safari wipes a
// non-installed site's storage after 7 idle days; installed apps are exempt.
// iOS gets illustrated steps (Apple offers no install API); Chromium gets a
// real one-tap Install button via the stashed beforeinstallprompt event.
let deferredInstall = null;

const isStandalone = () => navigator.standalone === true
  || (window.matchMedia && matchMedia('(display-mode: standalone)').matches);

function maybeShowInstallTip() {
  const tip = $('#install-tip');
  if (!tip || !tip.hidden) return;
  if (!hasAnyDailyCompletion()) return;
  const misc = store.getMisc();
  if (isStandalone() || misc.installTipDismissed || misc.iosTipDismissed) return;
  const isIOS = /iP(hone|ad|od)/.test(navigator.userAgent);
  if (isIOS) {
    $('#install-steps').hidden = false;
  } else if (deferredInstall) {
    $('#install-btn').hidden = false;
  } else {
    return; // no install path on this browser (e.g. desktop Safari/Firefox)
  }
  tip.hidden = false;
  track('install-tip-shown');
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

  window.__CHRONICLE_TEST__ = Object.assign(window.__CHRONICLE_TEST__ || {}, {
    ptr: {
      isArmed: () => armed,
      isPulling: () => pulling,
    },
  });
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
  return `Next issue drops in<b>${h}:${m}:${sec}</b>`;
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
  $('#ic-verdict').textContent = `Issue № ${n}, filed. Some got away.`;
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
  $('#dd-issue').textContent = `Issue № ${n}`;
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
  $('#dd-issue').textContent = `Issue № ${daily.todayIndex()}`;
  $('#dd-title').textContent = "You're history.";
  $('#dd-score-label').textContent = 'Your streak ended at';
  $('#dd-total').textContent = `${streak} days`;
  $('#dd-streak-label').textContent = 'Rest in peace';
  $('#dd-streak').textContent = `Issues ${Math.max(0, lastEdition - streak + 1)}–${lastEdition}`;
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
// Memoised loader for the five content files. A failed attempt clears the
// memo so the next tap retries; success registers the match pools and wires
// the game modules exactly once — no launch path can outrun this, because
// every one of them awaits ensureData() first.
let dataLoaded = false;
let dataPromise = null;
function loadData() {
  if (dataLoaded) return Promise.resolve(true);
  if (dataPromise) return dataPromise;
  dataPromise = Promise.all(
    ['data/figures.json', 'data/worldmap.json', 'data/reveal-who.json',
     'data/reveal-what.json', 'data/connections.json'].map((u) =>
      fetch(u).then((r) => {
        if (!r.ok) throw new Error('failed to load ' + u);
        return r.json();
      })),
  ).then(([figures, world, revealWho, revealWhat, connections]) => {
    DATA.figures = figures;
    DATA.world = world;
    // reveal-who.json (portraits) + reveal-what.json (artefacts) are the
    // current, actively-curated content files; DATA.reveal is their union,
    // filtered by `kind` downstream (revealgame.js) exactly as before.
    DATA.reveal = revealWho.concat(revealWhat);
    DATA.connections = connections;
    dataLoaded = true;
    initMapGame();
    initRevealGame();
    initConnectionsGame();
    setTimeout(prefetchDailyImages, 1200); // after first paint settles
    return true;
  }).catch(() => {
    dataPromise = null;
    return false;
  });
  return dataPromise;
}

async function boot() {
  initTracking();
  // The opening funnel, one event per boot: installed-app vs browser tab,
  // first-ever visit vs a return. These four paths are the denominators for
  // every start/finish/share rate on the dashboard.
  track(isStandalone() ? 'open-pwa' : 'open-browser');
  if (store.getMisc().seenBefore) track('open-return');
  else { track('open-new'); store.setMisc({ seenBefore: true }); }
  daily.normalizeLedgerScales();
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
  // run behind it; only a tap into a game ever waits on them (ensureData).
  loadData();

  initPullToRefresh();
  initHome();
  initDaily();
  initDayDone();
  refreshHomeStats();
  refreshTodayStrip();
  if (!maybeMourn()) maybeCelebrate();
  // Boot renders Home without going through render() (the view is visible by
  // default), so paint the edition-closed strip here too — unless a moment
  // screen (mourn/celebrate) already navigated away.
  if (trail[trail.length - 1] === 'view-home') refreshIssueClosed();

  // Deterministic hooks for the automated test-suite.
  window.__CHRONICLE_TEST__ = Object.assign(window.__CHRONICLE_TEST__ || {}, { data: DATA, store, isMatch, daily });

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

// Warm today's + tomorrow's Face Value / Relic images so the dailies stay
// playable offline (the aeroplane rule, owner report 2026-07-15): each
// request routes through the service worker, which files the bytes into the
// version-bump-proof df-img cache. Sequential so it never competes with an
// image the player is actually looking at; tomorrow's edition rides along as
// a buffer for a day spent entirely offline.
function prefetchDailyImages() {
  const today = daily.todayIndex();
  if (today < 0) return;
  const urls = [];
  const seen = new Set();
  for (const n of [today, today + 1]) {
    for (const game of ['who', 'what']) {
      for (const item of daily.getEdition(game, n)) {
        if (item.img && !seen.has(item.img)) { seen.add(item.img); urls.push(item.img); }
      }
    }
  }
  const next = () => {
    const u = urls.shift();
    if (!u) return;
    const img = new Image();
    img.onload = next;
    img.onerror = next;
    img.src = u;
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
    ? '🗞️ New edition off the presses — <b>pull down to refresh</b>'
    : '🗞️ New edition off the presses — <b>tap to refresh</b>';
  bar.addEventListener('click', () => location.reload());
  document.body.appendChild(bar);
}

boot();
