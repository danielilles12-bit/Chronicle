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
  if (!DATA.puzzles) return;
  const solved = DATA.puzzles.filter((p) => {
    const s = store.getPuzzle(p.id);
    return s && s.completed;
  }).length;
  const total = DATA.puzzles.length;
  $('#stat-crossword').textContent = solved
    ? `${solved} of ${total} solved`
    : `${total} puzzle${total === 1 ? '' : 's'} waiting`;
  const m = store.getMap();
  $('#stat-map').textContent = m.sessions
    ? `Best: ${m.bestScore} pts · streak ${m.bestStreak}`
    : `${DATA.figures.length} lives to guess`;
  const whoCount = DATA.reveal ? DATA.reveal.filter((x) => x.kind === 'portrait').length : 0;
  const whatCount = DATA.reveal ? DATA.reveal.filter((x) => x.kind !== 'portrait').length : 0;
  const rvWho = store.getReveal('who');
  if ($('#stat-reveal-who')) {
    $('#stat-reveal-who').textContent = rvWho.sessions
      ? `Best: ${rvWho.bestScore} pts · streak ${rvWho.bestStreak}`
      : `${whoCount} faces to name`;
  }
  const rvWhat = store.getReveal('what');
  if ($('#stat-reveal-what')) {
    $('#stat-reveal-what').textContent = rvWhat.sessions
      ? `Best: ${rvWhat.bestScore} pts · streak ${rvWhat.bestStreak}`
      : `${whatCount} artefacts to name`;
  }
  const cs = store.getConnStats();
  if ($('#stat-conn')) {
    $('#stat-conn').textContent = cs.solved
      ? `${cs.solved} of ${DATA.connections ? DATA.connections.length : '?'} solved`
      : (DATA.connections ? `${DATA.connections.length} puzzles` : '');
  }
}

// ---------- Today strip ----------
// One row per game, in the fixed presentation order Thread, Lifeline,
// Face Value, Relic. `launchDaily`/`launchPractice` take the edition index.
const TODAY_GAMES = [
  { key: 'thread', label: 'Thread', launchDaily: startThreadDaily, launchPractice: startThreadPractice },
  { key: 'map', label: 'Lifeline', launchDaily: startMapDaily, launchPractice: startMapPractice },
  { key: 'who', label: 'Face Value', launchDaily: (n) => startRevealDaily('who', n), launchPractice: (n) => startRevealPractice('who', n) },
  { key: 'what', label: 'Relic', launchDaily: (n) => startRevealDaily('what', n), launchPractice: (n) => startRevealPractice('what', n) },
];

function statusLabel(status, score) {
  if (status === 'done') return `Done · ${score} pts`;
  if (status === 'in-progress') return 'In progress';
  return 'Not started';
}

export function refreshTodayStrip() {
  const strip = $('#today-strip');
  if (!strip || !DATA.figures) return; // boot not finished yet
  const n = daily.todayIndex();
  $('#today-label').textContent = daily.editionLabel(n);
  TODAY_GAMES.forEach((g) => {
    const tile = $(`#today-${g.key}`);
    if (!tile) return;
    const status = daily.dailyStatus(g.key, n);
    const entry = status === 'done' ? store.getDailyEntry(g.key, n) : null;
    tile.querySelector('.today-status').textContent = statusLabel(status, entry && entry.score);
    tile.classList.toggle('today-done', status === 'done');
    tile.classList.toggle('today-progress', status === 'in-progress');
  });
}

function initDaily() {
  TODAY_GAMES.forEach((g) => {
    const tile = $(`#today-${g.key}`);
    if (!tile) return;
    tile.addEventListener('click', () => g.launchDaily(daily.todayIndex()));
  });
  const archiveLink = $('#today-archive-link');
  if (archiveLink) {
    archiveLink.addEventListener('click', () => {
      renderArchive();
      show('view-archive');
    });
  }
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
  // Crosswords are retained but hidden from the app for now; the card carries
  // `hidden`. Guard so this is a no-op when the card isn't shown.
  const cwCard = $('#card-crossword');
  if (cwCard) {
    cwCard.addEventListener('click', () => {
      renderPuzzleList();
      show('view-cwlist');
    });
  }
  $('#card-map').addEventListener('click', () => {
    renderMapStart();
    show('view-mapstart');
  });
  $('#card-reveal-who').addEventListener('click', () => {
    renderRevealStart('who');
    show('view-revealstart');
  });
  $('#card-reveal-what').addEventListener('click', () => {
    renderRevealStart('what');
    show('view-revealstart');
  });
  $('#card-conn').addEventListener('click', () => {
    renderConnList();
    show('view-connlist');
  });
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

  initHome();
  initCrossword();
  initMapGame();
  initRevealGame();
  initConnectionsGame();
  initDaily();
  refreshHomeStats();
  refreshTodayStrip();

  // Deterministic hooks for the automated test-suite.
  window.__CHRONICLE_TEST__ = { data: DATA, store, isMatch, daily };

  if ('serviceWorker' in navigator && location.protocol.indexOf('http') === 0) {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  }
}

boot();
