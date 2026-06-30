// Boot, data loading, view router, home screen.
import * as store from './storage.js';
import { isMatch } from './match.js';
import { initCrossword, renderPuzzleList } from './crossword.js';
import { initMapGame, renderMapStart } from './mapgame.js';
import { initRevealGame, renderRevealStart } from './revealgame.js';
import { initChronoGame, renderChronoStart } from './chronogame.js';
import { initConnectionsGame, renderConnList } from './connectionsgame.js';

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
  if (id === 'view-home') refreshHomeStats();
  if (id === 'view-mapstart') renderMapStart();
  if (id === 'view-revealstart') renderRevealStart();
  if (id === 'view-chronostart') renderChronoStart();
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
  const rv = store.getReveal();
  if ($('#stat-reveal')) {
    $('#stat-reveal').textContent = rv.sessions
      ? `Best: ${rv.bestScore} pts · streak ${rv.bestStreak}`
      : (DATA.reveal ? `${DATA.reveal.length} to identify` : '');
  }
  const ch = store.getChrono();
  if ($('#stat-chrono')) {
    $('#stat-chrono').textContent = ch.sessions
      ? `Best: ${ch.bestScore} pts`
      : (DATA.chrono ? `${DATA.chrono.length} puzzles` : '');
  }
  const cs = store.getConnStats();
  if ($('#stat-conn')) {
    $('#stat-conn').textContent = cs.solved
      ? `${cs.solved} of ${DATA.connections ? DATA.connections.length : '?'} solved`
      : (DATA.connections ? `${DATA.connections.length} puzzles` : '');
  }
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
  $('#card-reveal').addEventListener('click', () => {
    renderRevealStart();
    show('view-revealstart');
  });
  $('#card-chrono').addEventListener('click', () => {
    renderChronoStart();
    show('view-chronostart');
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
    const [puzzles, figures, world, reveal, chrono, connections] = await Promise.all(
      ['data/puzzles.json', 'data/figures.json', 'data/worldmap.json', 'data/reveal.json',
       'data/chrono.json', 'data/connections.json'].map((u) =>
        fetch(u).then((r) => {
          if (!r.ok) throw new Error('failed to load ' + u);
          return r.json();
        })),
    );
    DATA.puzzles = puzzles;
    DATA.figures = figures;
    DATA.world = world;
    DATA.reveal = reveal;
    DATA.chrono = chrono;
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
  initChronoGame();
  initConnectionsGame();
  refreshHomeStats();

  // Deterministic hooks for the automated test-suite.
  window.__CHRONICLE_TEST__ = { data: DATA, store, isMatch };

  if ('serviceWorker' in navigator && location.protocol.indexOf('http') === 0) {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  }
}

boot();
