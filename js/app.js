// Boot, data loading, view router, home screen.
import * as store from './storage.js';
import { isMatch } from './match.js';
import { initCrossword, renderPuzzleList } from './crossword.js';
import { initMapGame, renderMapStart, startMapDaily, startMapPractice } from './mapgame.js';
import { initRevealGame, renderRevealStart, startRevealDaily, startRevealPractice } from './revealgame.js';
import { initConnectionsGame, renderConnList, startThreadDaily, startThreadPractice } from './connectionsgame.js';
import * as daily from './daily.js';

export const DATA = { puzzles: null, figures: null, world: null, reveal: null, chrono: null, connections: null };
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
  if (id === 'view-home') { refreshHomeStats(); refreshTodayStrip(); }
  if (id === 'view-mapstart') renderMapStart();
  if (id === 'view-revealstart') renderRevealStart();
  if (id === 'view-archive') renderArchive();
  document.dispatchEvent(new CustomEvent('viewchange', { detail: id }));
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
    glyph: 'assets/brand/svg/game-icon-thread-primary.svg',
    tintStrong: 'var(--df-cyan)',
    tintSoft: 'color-mix(in srgb, var(--df-cyan) 14%, var(--ch-cream))',
    launchDaily: startThreadDaily, launchPractice: startThreadPractice,
  },
  {
    key: 'map', label: 'Lifeline', tagline: 'Born here, died there. Name the figure.',
    glyph: 'assets/brand/svg/game-icon-lifeline-primary.svg',
    tintStrong: 'var(--df-yellow)',
    tintSoft: 'color-mix(in srgb, var(--df-yellow) 18%, var(--ch-cream))',
    launchDaily: startMapDaily, launchPractice: startMapPractice,
  },
  {
    key: 'who', label: 'Face Value', tagline: 'A famous face, one scrap at a time.',
    glyph: 'assets/brand/svg/game-icon-face-value-primary.svg',
    tintStrong: 'var(--df-magenta)',
    tintSoft: 'color-mix(in srgb, var(--df-magenta) 12%, var(--ch-cream))',
    launchDaily: (n) => startRevealDaily('who', n), launchPractice: (n) => startRevealPractice('who', n),
  },
  {
    key: 'what', label: 'Relic', tagline: 'A famous artefact, one scrap at a time.',
    glyph: 'assets/brand/svg/game-icon-relic-primary.svg',
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
  return 'Not started';
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

  GAME_ROWS.forEach((g) => {
    $(`[data-hero="${g.key}"]`).addEventListener('click', () => g.launchDaily(daily.todayIndex()));
    $(`[data-archive="${g.key}"]`).addEventListener('click', () => {
      renderArchive();
      show('view-archive');
    });
  });
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

const MAX_DAY_CARDS = 7;

export function refreshGameRows() {
  if (!$('#home-rows') || !DATA.figures) return; // boot not finished yet
  renderGameRows();
  const today = Math.max(0, daily.todayIndex());
  const wd = new Date().toLocaleDateString('en-GB', { weekday: 'long' });
  $('#dateline').textContent = `Issue № ${today} // ${wd}`;
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

function initDaily() {
  initArchive();
}

// ---------- Archive / Practice ----------
const WEEKDAY_CHIPS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
let archiveFilter = null; // null = all weekdays, else 0-6

function initArchive() {
  const filterRow = $('#archive-filters');
  if (!filterRow) return;
  filterRow.innerHTML = '';
  const allBtn = document.createElement('button');
  allBtn.className = 'pill small archive-chip active';
  allBtn.textContent = 'All';
  allBtn.addEventListener('click', () => { archiveFilter = null; renderArchive(); });
  filterRow.appendChild(allBtn);
  WEEKDAY_CHIPS.forEach((label, i) => {
    const btn = document.createElement('button');
    btn.className = 'pill small archive-chip';
    btn.textContent = label;
    btn.addEventListener('click', () => { archiveFilter = i; renderArchive(); });
    filterRow.appendChild(btn);
  });
  $$('[data-back]').forEach(() => {}); // no-op: back button already wired globally
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

function renderArchive() {
  const main = $('#archive-list');
  if (!main || !DATA.figures) return;
  main.innerHTML = '';
  $$('#archive-filters .archive-chip').forEach((btn, i) => {
    // i===0 is the "All" chip; weekday chips follow at i-1 === weekday index
    const isActive = i === 0 ? archiveFilter === null : (i - 1) === archiveFilter;
    btn.classList.toggle('active', isActive);
  });
  const today = daily.todayIndex();
  // Visibility rule (spec): n < today (aired) OR n <= today + preview. Pre-
  // launch ARCHIVE_PREVIEW_EDITIONS is Infinity ("everything visible"); cap
  // the render window at a generous but finite lookahead so the list stays
  // finite even with an Infinity config.
  const last = today + (Number.isFinite(daily.ARCHIVE_PREVIEW_EDITIONS) ? daily.ARCHIVE_PREVIEW_EDITIONS : 180);
  const rows = [];
  for (let n = last; n >= 0; n--) {
    if (n === today) continue; // today's edition lives in the Today strip, not duplicated here until tomorrow
    if (archiveFilter !== null && daily.weekday(n) !== archiveFilter) continue;
    rows.push(n);
  }
  rows.forEach((n) => {
    const row = document.createElement('button');
    row.className = 'cwitem archive-row';
    const marks = TODAY_GAMES.map((g) => {
      const status = daily.dailyStatus(g.key, n);
      const dot = status === 'done' ? 'done' : status === 'in-progress' ? 'progress' : '';
      return `<span class="archive-dot archive-dot-${g.key} ${dot}" title="${g.label}"></span>`;
    }).join('');
    row.innerHTML =
      `<span class="cw-size">${daily.weekdayName(n).slice(0, 3)}</span>` +
      `<span class="cw-name">Edition #${n}</span>` +
      `<span class="archive-marks">${marks}</span>`;
    row.addEventListener('click', () => openArchiveEdition(n));
    main.appendChild(row);
  });
  if (!rows.length) {
    main.innerHTML = '<p class="start-copy small" style="text-align:center;margin-top:24px">No editions match this filter.</p>';
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
  const wd = new Date().toLocaleDateString('en-GB', { weekday: 'long' });
  $('#dateline').textContent = `Issue № ${Math.max(0, daily.todayIndex())} // ${wd}`;
  // Crosswords are retained but hidden from the app for now, same as before
  // this rebuild; the card carries `hidden`. Guard so this is a no-op when
  // the card isn't shown. The other three games' free-play "Start a session"
  // views (view-mapstart/view-revealstart) get the same treatment as part of
  // this redesign: their views and logic are untouched, but Home no longer
  // links to them directly — free play is reached via Archive → practice
  // (spec "Removals/moves"), so they're hidden routes like the crossword.
  const cwCard = $('#card-crossword');
  if (cwCard) {
    cwCard.addEventListener('click', () => {
      renderPuzzleList();
      show('view-cwlist');
    });
  }
  $$('[data-back]').forEach((b) => b.addEventListener('click', back));

  const isIOS = /iP(hone|ad|od)/.test(navigator.userAgent);
  const standalone = navigator.standalone === true
    || (window.matchMedia && matchMedia('(display-mode: standalone)').matches);
  if (isIOS && !standalone && !store.getMisc().iosTipDismissed) {
    $('#ios-tip').hidden = false;
    $('#ios-tip-close').addEventListener('click', () => {
      $('#ios-tip').hidden = true;
      store.setMisc({ iosTipDismissed: true });
    });
  }
}

// ---------- boot ----------

// Pull-to-refresh with a damped, springy pull — home view only. Pulling past
// the arm threshold and releasing reloads the app (which also picks up any
// freshly deployed version via the service worker's update check).
function initPullToRefresh() {
  const home = $('#view-home');
  const pill = $('#ptr-pill');
  if (!home || !pill) return;
  const ARM = 64, MAX = 130, DAMP = 0.45;
  let y0 = null, x0 = null, pulling = false, armed = false;

  const settle = () => {
    home.style.transition = 'transform .32s cubic-bezier(.2,.8,.3,1.25)';
    home.style.transform = '';
    setTimeout(() => { home.style.transition = ''; pill.hidden = true; }, 340);
  };

  document.addEventListener('touchstart', (e) => {
    if (home.hidden || window.scrollY > 0 || e.touches.length !== 1) { y0 = null; return; }
    y0 = e.touches[0].clientY; x0 = e.touches[0].clientX;
    pulling = false; armed = false;
  }, { passive: true });

  document.addEventListener('touchmove', (e) => {
    if (y0 == null || home.hidden) return;
    const dy = e.touches[0].clientY - y0;
    const dx = e.touches[0].clientX - x0;
    if (!pulling && Math.abs(dx) > Math.abs(dy)) { y0 = null; return; }  // horizontal strip swipe
    if (dy <= 0 || window.scrollY > 0) {
      if (pulling) { pulling = false; armed = false; settle(); }
      return;
    }
    pulling = true;
    const pull = Math.min(MAX, dy * DAMP);
    home.style.transition = '';
    home.style.transform = `translateY(${pull.toFixed(1)}px)`;
    armed = pull >= ARM;
    pill.textContent = armed ? 'Release to refresh' : 'Pull to refresh';
    pill.hidden = false;
  }, { passive: true });

  document.addEventListener('touchend', () => {
    if (y0 == null) return;
    y0 = null;
    if (!pulling) return;
    if (armed) {
      pill.textContent = 'Refreshing\u2026';
      setTimeout(() => location.reload(), 160);
      return;                       // keep the pulled position until reload
    }
    settle();
  }, { passive: true });

  window.__CHRONICLE_TEST__ = Object.assign(window.__CHRONICLE_TEST__ || {}, {
    ptr: { isArmed: () => armed, isPulling: () => pulling },
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
function dayTotal(n) {
  const ledger = store.getDailyLedger();
  return daily.GAMES.reduce((sum, g) => {
    const e = ledger.entries[g] && ledger.entries[g][n];
    return sum + ((e && e.score) || 0);
  }, 0);
}
function shareText(n) {
  const ledger = store.getDailyLedger();
  const names = { thread: 'THREAD', map: 'LIFELINE', who: 'FACE VALUE', what: 'RELIC' };
  const lines = daily.GAMES.map((g) => {
    const e = ledger.entries[g] && ledger.entries[g][n];
    return `${names[g]} ${e ? e.score : 0}`;
  });
  const streak = (ledger.fullHouse && ledger.fullHouse.streak) || 1;
  return `DEAD FAMOUS · ISSUE № ${n}\n${lines.join(' · ')}\nTOTAL: ${dayTotal(n)} · STREAK: ${streak}`;
}

function startCountdown() {
  const el = $('#dd-countdown');
  if (!el) return;
  el.hidden = false;
  const tick = () => {
    const now = new Date();
    const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
    const ms = midnight - now;
    const h = String(Math.floor(ms / 3600000)).padStart(2, '0');
    const m = String(Math.floor((ms % 3600000) / 60000)).padStart(2, '0');
    const sec = String(Math.floor((ms % 60000) / 1000)).padStart(2, '0');
    el.innerHTML = `Next issue drops in<b>${h}:${m}:${sec}</b>`;
  };
  tick();
  clearInterval(ddCountdownTimer);
  ddCountdownTimer = setInterval(tick, 1000);
}

function showCelebration(n) {
  flagSet('df.celebrated', String(n));
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
  $('#dd-share').hidden = false;
  startCountdown();
  show('view-daydone');
}

function showObituary(streak, lastEdition) {
  flagSet('df.mourned', String(lastEdition));
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
  $('#dd-share').hidden = true;
  $('#dd-countdown').hidden = true;
  show('view-daydone');
}

function maybeCelebrate() {
  const n = daily.todayIndex();
  if (fullHouseDone(n) && flagGet('df.celebrated') !== String(n)) showCelebration(n);
}
function maybeMourn() {
  const ledger = store.getDailyLedger();
  const fh = ledger.fullHouse || { streak: 0, lastEdition: -Infinity };
  const today = daily.todayIndex();
  if (fh.streak >= 3 && Number.isFinite(fh.lastEdition) && fh.lastEdition <= today - 2
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
    const text = shareText(daily.todayIndex());
    const btn = $('#dd-share');
    try {
      if (navigator.share) { await navigator.share({ text }); return; }
      await navigator.clipboard.writeText(text);
      btn.textContent = 'Copied!';
      setTimeout(() => { btn.textContent = "Share today's receipt"; }, 1600);
    } catch (e) { /* user cancelled */ }
  });
  document.addEventListener('viewchange', (e) => {
    if (e.detail === 'view-home') maybeCelebrate();
    if (e.detail !== 'view-daydone') clearInterval(ddCountdownTimer);
  });
}

async function boot() {
  try {
    const [puzzles, figures, world, revealWho, revealWhat, connections] = await Promise.all(
      ['data/puzzles.json', 'data/figures.json', 'data/worldmap.json', 'data/reveal-who.json',
       'data/reveal-what.json', 'data/connections.json'].map((u) =>
        fetch(u).then((r) => {
          if (!r.ok) throw new Error('failed to load ' + u);
          return r.json();
        })),
    );
    DATA.puzzles = puzzles;
    DATA.figures = figures;
    DATA.world = world;
    // reveal-who.json (portraits) + reveal-what.json (artefacts) are the
    // current, actively-curated content files; DATA.reveal is their union,
    // filtered by `kind` downstream (revealgame.js) exactly as before.
    DATA.reveal = revealWho.concat(revealWhat);
    DATA.connections = connections;
  } catch (e) {
    document.body.innerHTML = '<p style="padding:40px;text-align:center">'
      + 'Dead Famous could not load its data. Please reload once you are online.</p>';
    return;
  }

  initPullToRefresh();
  initHome();
  initCrossword();
  initMapGame();
  initRevealGame();
  initConnectionsGame();
  initDaily();
  initDayDone();
  refreshHomeStats();
  refreshTodayStrip();
  if (!maybeMourn()) maybeCelebrate();

  // Deterministic hooks for the automated test-suite.
  window.__CHRONICLE_TEST__ = Object.assign(window.__CHRONICLE_TEST__ || {}, { data: DATA, store, isMatch, daily });

  if ('serviceWorker' in navigator && location.protocol.indexOf('http') === 0) {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  }
}

boot();
