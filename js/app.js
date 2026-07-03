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
    tintStrong: 'color-mix(in srgb, var(--ch-burgundy) 10%, var(--ch-cream))',
    tintSoft: 'color-mix(in srgb, var(--ch-burgundy) 6%, var(--ch-cream))',
    launchDaily: startThreadDaily, launchPractice: startThreadPractice,
  },
  {
    key: 'map', label: 'Lifeline', tagline: 'Born here, died there. Name the figure.',
    glyph: 'assets/brand/svg/game-icon-lifeline-primary.svg',
    tintStrong: 'color-mix(in srgb, var(--ch-forest) 10%, var(--ch-cream))',
    tintSoft: 'color-mix(in srgb, var(--ch-forest) 6%, var(--ch-cream))',
    launchDaily: startMapDaily, launchPractice: startMapPractice,
  },
  {
    key: 'who', label: 'Face Value', tagline: 'A famous face, one sliver at a time.',
    glyph: 'assets/brand/svg/game-icon-face-value-primary.svg',
    tintStrong: 'color-mix(in srgb, var(--ch-gold) 12%, var(--ch-cream))',
    tintSoft: 'color-mix(in srgb, var(--ch-gold) 7%, var(--ch-cream))',
    launchDaily: (n) => startRevealDaily('who', n), launchPractice: (n) => startRevealPractice('who', n),
  },
  {
    key: 'what', label: 'Relic', tagline: 'A famous artefact, one sliver at a time.',
    glyph: 'assets/brand/svg/game-icon-relic-primary.svg',
    tintStrong: 'color-mix(in srgb, var(--ch-sage) 14%, var(--ch-cream))',
    tintSoft: 'color-mix(in srgb, var(--ch-sage) 8%, var(--ch-cream))',
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
    <section class="game-row" data-row="${g.key}">
      <div class="game-strip" data-strip="${g.key}"
           style="--row-tint-strong:${g.tintStrong};--row-tint-soft:${g.tintSoft}">
        <button class="hero-card" data-hero="${g.key}" aria-label="Play today's ${g.label}">
          <div class="hero-top">
            <div class="hero-text">
              <h2 class="hero-name">${g.label}</h2>
              <p class="hero-tagline">${g.tagline}</p>
            </div>
            <img class="hero-glyph" src="${g.glyph}" alt="" aria-hidden="true">
          </div>
          <div class="hero-bottom">
            <span class="hero-edition" data-edition></span>
            <span class="hero-status" data-status></span>
          </div>
        </button>
        <div class="day-cards" data-days></div>
      </div>
      <button class="row-archive" data-archive="${g.key}" aria-label="Open the Archive">
        <span>Archive</span>
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
  const today = daily.todayIndex();
  GAME_ROWS.forEach((g) => {
    const status = daily.dailyStatus(g.key, today);
    const entry = status === 'done' ? store.getDailyEntry(g.key, today) : null;
    const hero = $(`[data-hero="${g.key}"]`);
    hero.querySelector('[data-edition]').textContent = daily.editionLabel(today).replace('Edition #', 'EDITION #').toUpperCase();
    hero.querySelector('[data-status]').textContent = statusLabel(status, entry && entry.score);
    hero.classList.toggle('row-done', status === 'done');
    hero.classList.toggle('row-progress', status === 'in-progress');

    // Past (aired) editions only, newest first, capped at 7 — or fewer in the
    // first week of the app's life.
    const days = [];
    for (let n = today - 1; n >= 0 && days.length < MAX_DAY_CARDS; n--) days.push(n);
    const wrap = $(`[data-strip="${g.key}"] [data-days]`);
    wrap.innerHTML = days.map((n) => {
      const st = dayCardStatus(g.key, n);
      const dayEntry = st === 'done' ? store.getDailyEntry(g.key, n) : null;
      const label = st === 'done' ? `✓ ${dayEntry ? dayEntry.score : 0}` : '—';
      return `<button class="day-card${st === 'done' ? ' day-done' : ''}" data-day="${g.key}" data-n="${n}">
        <span class="day-weekday">${daily.weekdayName(n)}</span>
        <span class="day-status">${label}</span>
      </button>`;
    }).join('');
    wrap.querySelectorAll('[data-day]').forEach((btn) => {
      btn.addEventListener('click', () => g.launchPractice(+btn.dataset.n));
    });
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
  $('#dateline').textContent = new Date().toLocaleDateString('en-GB', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  });
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
      + 'Chronicle could not load its data. Please reload once you are online.</p>';
    return;
  }

  initPullToRefresh();
  initHome();
  initCrossword();
  initMapGame();
  initRevealGame();
  initConnectionsGame();
  initDaily();
  refreshHomeStats();
  refreshTodayStrip();

  // Deterministic hooks for the automated test-suite.
  window.__CHRONICLE_TEST__ = Object.assign(window.__CHRONICLE_TEST__ || {}, { data: DATA, store, isMatch, daily });

  if ('serviceWorker' in navigator && location.protocol.indexOf('http') === 0) {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  }
}

boot();
