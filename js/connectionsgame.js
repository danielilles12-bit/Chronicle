// Connections — group 16 history clues into four hidden categories
import { $, $$, show, back, goHome, refreshHomeStats, setReceiptStamp, maybeIntro, openIntroHelp, wireTurnThePage, announce, consumeShareLaunch } from './app.js';
import * as store from './storage.js';
import * as daily from './daily.js';
import { threadShareText, threadEmojiRows, shareResult, flashShareButton, shareUrl } from './sharecard.js';
import { track, durationBucket } from './track.js';
import * as sfx from './sfx.js';

const MAX_MISTAKES = 4;
const COLOUR_ORDER = ['yellow', 'green', 'blue', 'purple'];
// Card #12: colorblind print glyphs — zine ornaments, not an a11y mode toggle.
// Prefixed on every solved-group label, in-app and on the canvas receipt.
const GROUP_GLYPH = { yellow: '●', green: '▲', blue: '■', purple: '✦' };
let S = null;
let currentPuzzle = null;

// A solved group's label row, glyph-prefixed: "<glyph> ANCIENT ROME". The
// glyph is its own span so CSS can force ink colour + opacity regardless of
// the group's tinted background/text colour.
function groupLabelHTML(colour, label) {
  const glyph = GROUP_GLYPH[colour] || '';
  return `<span class="conn-glyph" aria-hidden="true">${glyph}</span>${label}`;
}

// ---------- scoring ----------
// NYT-Connections-style mistake penalty: mirrors the "floor + linear penalty"
// shape used in mapgame.js / revealgame.js (Math.max(floor, 100 - k*mistakes)).
// 0 mistakes = 100 pts, each mistake costs 20, floor is 20 pts if still solved.
// Running out of mistakes before finishing (game-over) scores 0.
function calcScore(solved, mistakes) {
  if (!solved) return 0;
  return Math.max(20, 100 - 20 * mistakes);
}

// ---------- injected styles (scoped to Connections; no css/*.css edits) ----------
function ensureConnScoreStyles() {
  if ($('#conn-score-styles')) return;
  const style = document.createElement('style');
  style.id = 'conn-score-styles';
  style.textContent = `
    .conn-score-live { font-size: 13px; font-weight: 700; color: var(--ink, #1a1a1a); margin-right: 8px; letter-spacing: .01em; }
    .conn-sum-score { text-align: center; font-size: 34px; font-weight: 800; margin-top: 6px; }
    .conn-sum-score small { display: block; font-size: 13px; font-weight: 600; opacity: .65; margin-top: 2px; }
  `;
  document.head.appendChild(style);
}

// ---------- shared helpers ----------
function shuffleArray(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function ensureLiveScoreEl() {
  let el = $('#conn-score-live');
  if (!el) {
    el = document.createElement('span');
    el.id = 'conn-score-live';
    el.className = 'conn-score-live';
    const mistakesEl = $('#conn-mistakes');
    mistakesEl.parentNode.insertBefore(el, mistakesEl);
  }
  return el;
}

function updateLiveScore() {
  ensureLiveScoreEl().textContent = `${calcScore(true, S.mistakes)} pts`;
}

// Daily and practice attempts use the namespaced generic store so they never
// collide with each other.
function modeStore(key) {
  return {
    get: () => store.getDailySession(key),
    set: (s) => store.setDailySession(key, s),
    clear: () => store.clearDailySession(key),
  };
}

// ---------- daily / practice entry points ----------
// Thread daily/practice opens the edition's single board directly (no list).
function startEdition(mode, editionIndex) {
  // P5.2: consumed synchronously (no await between app.js setting it and
  // this read), so it's safe even though the intro overlay can defer begin()
  // behind a user tap — fromShare is closed over either way.
  const fromShare = mode === 'daily' && consumeShareLaunch('thread');
  if (mode === 'daily') {
    const entry = store.getDailyEntry('thread', editionIndex);
    if (entry) { showLockedResult(editionIndex, entry); return; }
  }
  const boards = daily.getEdition('thread', editionIndex);
  const puzzle = boards[0];
  if (!puzzle) return;               // no board available for this tier (shouldn't happen with real content)
  const key = mode === 'daily' ? daily.dailyKey('thread', editionIndex) : daily.practiceKey('thread', editionIndex);
  const st = modeStore(key);
  const progress = st.get();
  if (mode === 'daily' && progress) track('resume-thread');
  const begin = () => {
    ensureConnScoreStyles();
    currentPuzzle = puzzle;
    const tiles = [];
    puzzle.groups.forEach((group) => {
      group.items.forEach((item) => tiles.push({ item, colour: group.colour, label: group.label }));
    });
    S = {
      mode, dailyKey: key, store: st, editionIndex,
      puzzle,
      tiles: shuffleArray(tiles),
      selected: new Set(),
      found: new Set(progress ? progress.found : []),
      mistakes: progress ? progress.mistakes : 0,
      guesses: progress ? (progress.guesses || []) : [],
      startedAt: (progress && progress.startedAt) || Date.now(),
      fromShare,
      done: false,
    };
    $('#conn-puzzle-title').textContent = puzzle.title;
    renderConnGame();
    show('view-conn');
  };
  // First-run intro only on a genuinely fresh daily board (no saved progress).
  const fresh = !progress || (!(progress.found && progress.found.length) && !progress.mistakes);
  if (mode === 'daily' && fresh) maybeIntro('thread', editionIndex, begin);
  else begin();
}

export function startThreadDaily(editionIndex) { startEdition('daily', editionIndex); }
export function startThreadPractice(editionIndex) { startEdition('practice', editionIndex); }

function showLockedResult(editionIndex, entry) {
  const boards = daily.getEdition('thread', editionIndex);
  const puzzle = boards[0];
  currentPuzzle = puzzle;
  const detail = entry.detail || {};
  S = {
    mode: 'daily', dailyKey: daily.dailyKey('thread', editionIndex), store: modeStore(null),
    editionIndex, puzzle, done: true, locked: true,
    found: new Set(['yellow', 'green', 'blue', 'purple']),
    mistakes: detail.mistakes || 0,
  };
  $('#conn-sum-title').textContent = puzzle ? puzzle.title : 'Thread';
  renderThreadReceipt({
    editionIndex, mode: 'daily', title: puzzle ? puzzle.title : '',
    score: entry.score, solved: detail.solved, perfect: detail.perfect,
    mistakes: detail.mistakes || 0, found: null, guesses: detail.guesses || [],
  });
  const reveal = $('#conn-sum-groups');
  reveal.innerHTML = '';
  if (puzzle) {
    COLOUR_ORDER.forEach((colour) => {
      const group = puzzle.groups.find((g) => g.colour === colour);
      const div = document.createElement('div');
      div.className = `conn-group conn-group-${colour}`;
      div.innerHTML = `<div class="conn-group-label">${groupLabelHTML(colour, group.label)}</div>`
        + `<div class="conn-group-items">${group.items.join(', ')}</div>`;
      reveal.appendChild(div);
    });
  }
  show('view-connsum');
}

// Save the player's found groups + mistakes so far, so leaving mid-puzzle
// (header back arrow) doesn't lose progress. Mirrors the session-persistence
// pattern used by map/reveal in storage.js. No-op until the player has
// actually made some headway, so a puzzle opened-and-immediately-backed-out
// isn't misreported as "in progress". Daily/practice sessions still persist
// even at found.size===0 as long as a mistake's been made — same rule.
function persistProgress() {
  if (!currentPuzzle || !S) return;
  if (S.found.size === 0 && S.mistakes === 0) {
    S.store.clear();
    return;
  }
  S.store.set({
    found: [...S.found],
    mistakes: S.mistakes,
    guesses: S.guesses || [],
    startedAt: S.startedAt,
  });
}

function renderConnGame() {
  renderFound();
  renderGrid();
  updateMistakesDisplay();
  updateLiveScore();
  $('#conn-submit').disabled = S.selected.size !== 4;
  $('#conn-feedback').hidden = true;
}

function renderFound() {
  const found = $('#conn-found');
  found.innerHTML = '';
  COLOUR_ORDER.filter((c) => S.found.has(c)).forEach((colour) => {
    const group = S.puzzle.groups.find((g) => g.colour === colour);
    const div = document.createElement('div');
    div.className = `conn-group conn-group-${colour}`;
    div.innerHTML =
      `<div class="conn-group-label">${groupLabelHTML(colour, group.label)}</div>` +
      `<div class="conn-group-items">${group.items.join(', ')}</div>`;
    found.appendChild(div);
  });
}

// P2.4: tiles are real <button type="button">s — natively tabbable, Enter/
// Space toggles via click, aria-pressed carries the selection state. CSS
// (.conn-tile button reset in style.css) keeps them pixel-identical to the
// old divs.
function renderGrid() {
  const grid = $('#conn-grid');
  grid.innerHTML = '';
  const remaining = S.tiles.filter((t) => !S.found.has(t.colour));
  remaining.forEach((tile, i) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'conn-tile' + (S.selected.has(i) ? ' conn-selected' : '');
    btn.dataset.i = i;
    btn.setAttribute('aria-pressed', S.selected.has(i) ? 'true' : 'false');
    btn.textContent = tile.item;
    btn.addEventListener('click', () => onTapTile(i));
    grid.appendChild(btn);
  });
  fitConnTiles();
}

// Toggle selection classes/aria in place instead of rebuilding the grid, so
// keyboard focus stays where it is between taps.
function updateTileSelection() {
  for (const el of $$('#conn-grid .conn-tile')) {
    const sel = S.selected.has(+el.dataset.i);
    el.classList.toggle('conn-selected', sel);
    el.setAttribute('aria-pressed', sel ? 'true' : 'false');
  }
}

// After a submit resolves, focus can be stranded (the Submit button disables
// itself; a solved group's tiles vanish). Hand it to the first tile so a
// keyboard player keeps playing without hunting.
function restoreGridFocus() {
  const active = document.activeElement;
  if (active && active !== document.body && !active.disabled) return;
  const first = document.querySelector('#conn-grid .conn-tile');
  if (first) first.focus({ preventScroll: true });
}

// Shrink each tile's font until its whole-word text fits — no mid-word breaks.
// A long single word ("Constantinople") rides down to a smaller size on one
// line; a multi-word tile ("Saudi Arabia") wraps only at the space.
function fitConnTiles() {
  for (const el of $$('#conn-grid .conn-tile')) {
    let size = 13;
    el.style.fontSize = size + 'px';
    let guard = 0;
    while ((el.scrollHeight > el.clientHeight + 0.5 || el.scrollWidth > el.clientWidth + 0.5)
           && size > 7 && guard < 30) {
      size -= 0.5;
      el.style.fontSize = size + 'px';
      guard++;
    }
  }
}

function onTapTile(i) {
  if (S.done) return;
  if (S.selected.has(i)) {
    S.selected.delete(i);
  } else if (S.selected.size < 4) {
    S.selected.add(i);
  }
  $('#conn-submit').disabled = S.selected.size !== 4;
  updateTileSelection();
}

function updateMistakesDisplay() {
  const left = MAX_MISTAKES - S.mistakes;
  const el = $('#conn-mistakes');
  el.innerHTML = '';
  for (let i = 0; i < MAX_MISTAKES; i++) {
    const dot = document.createElement('span');
    dot.className = 'conn-dot' + (i < left ? ' conn-dot-on' : '');
    el.appendChild(dot);
  }
  updateLiveScore();
}

function submitGuess() {
  if (S.selected.size !== 4 || S.done) return;
  if (S.fromShare) { S.fromShare = false; track('answer-from-share-thread'); }
  const remaining = S.tiles.filter((t) => !S.found.has(t.colour));
  const selectedTiles = [...S.selected].map((i) => remaining[i]);
  const colours = selectedTiles.map((t) => t.colour);
  // The guess log is the share grid (Share 2.0): one row of four colours per
  // submitted guess, right or wrong, in play order.
  if (!S.guesses) S.guesses = [];
  S.guesses.push(colours.slice());
  const allSame = colours.every((c) => c === colours[0]);

  const fb = $('#conn-feedback');

  if (allSame) {
    S.found.add(colours[0]);
    S.selected = new Set();
    fb.hidden = true;
    sfx.play('correct');
    const group = S.puzzle.groups.find((g) => g.colour === colours[0]);

    if (S.found.size === S.puzzle.groups.length) {
      // all found
      S.done = true;
      announce(`Correct — ${group.label}. All four groups found.`);
      setTimeout(() => finishPuzzle(), 400);
    } else {
      announce(`Correct — ${group.label}. ${S.found.size} of 4 groups found.`);
      persistProgress();
      renderConnGame();
      // P2.4: the solved group's tiles just left the grid — hand focus to
      // the next tile so keyboard play continues seamlessly.
      restoreGridFocus();
    }
  } else {
    // Check if one away
    const colourCounts = {};
    colours.forEach((c) => { colourCounts[c] = (colourCounts[c] || 0) + 1; });
    const oneAway = Object.values(colourCounts).some((n) => n === 3);

    S.mistakes++;
    S.selected = new Set();
    updateMistakesDisplay();

    fb.className = 'conn-feedback conn-wrong';
    fb.textContent = oneAway ? 'One thread loose.' : 'Knot quite.';
    fb.hidden = false;
    // P1.5/P2.4: wrong guesses are announced politely, with the guesses left
    // (Thread's visible feedback line already carries the explicit text).
    const left = MAX_MISTAKES - S.mistakes;
    announce((oneAway ? 'Wrong group — one away.' : 'Wrong group.')
      + (left > 0 ? ` ${left} guess${left === 1 ? '' : 'es'} left.` : ''));

    // shake the grid
    const grid = $('#conn-grid');
    grid.classList.remove('conn-shake');
    void grid.offsetWidth;
    grid.classList.add('conn-shake');

    updateTileSelection();
    $('#conn-submit').disabled = true;

    if (S.mistakes >= MAX_MISTAKES) {
      S.done = true;
      setTimeout(() => finishPuzzle(), 600);
    } else {
      persistProgress();
      // P2.4: Submit just disabled itself under the keyboard — hand focus
      // back to the grid.
      restoreGridFocus();
    }
  }
}

function finishPuzzle() {
  const perfect = S.found.size === S.puzzle.groups.length && S.mistakes === 0;
  const solved = S.found.size === S.puzzle.groups.length;
  const score = calcScore(solved, S.mistakes);
  sfx.play('stamp');

  if (S.mode === 'daily') {
    daily.recordDailyCompletion('thread', S.editionIndex, {
      score,
      detail: { solved, perfect, mistakes: S.mistakes, guesses: S.guesses || [] },
    });
    const outcome = !solved ? 'lost' : (S.mistakes === 0 ? 'clean' : 'fought');
    track(`round-thread-${outcome}`);
    track(`dur-thread-${durationBucket(Date.now() - (S.startedAt || Date.now()))}`);
    S.locked = true;
  }
  // practice mode: no ledger, no puzzle-list record, no stats — replayable.
  // Session dropped LAST, once the result is safely recorded (see the same
  // note in revealgame.js finishSession).
  S.store.clear();
  refreshHomeStats();

  // summary
  $('#conn-sum-title').textContent = S.puzzle.title;
  renderThreadReceipt({
    editionIndex: S.editionIndex, mode: S.mode, title: S.puzzle.title,
    score, solved, perfect, mistakes: S.mistakes, found: S.found.size,
    guesses: S.guesses || [],
  });

  const reveal = $('#conn-sum-groups');
  reveal.innerHTML = '';
  COLOUR_ORDER.forEach((colour) => {
    const group = S.puzzle.groups.find((g) => g.colour === colour);
    const div = document.createElement('div');
    div.className = `conn-group conn-group-${colour}`;
    div.innerHTML =
      `<div class="conn-group-label">${groupLabelHTML(colour, group.label)}</div>` +
      `<div class="conn-group-items">${group.items.join(', ')}</div>`;
    reveal.appendChild(div);
  });

  // P2.4: the game's verdict, spoken.
  announce(solved
    ? `Board solved. ${score} points.`
    : 'The thread snapped. 0 points.');
  show('view-connsum');
}

// The Thread receipt (head/rows/total/remark), shared by the live finish and
// the locked archive view so the two renderings can't drift. `found` is null
// when the per-group count wasn't recorded (locked entries store only
// solved/perfect/mistakes).
function renderThreadReceipt({ editionIndex, mode, title, score, solved, perfect, mistakes, found, guesses }) {
  // Share 2.0: dailies are shareable (issue number = the common reference);
  // practice/free runs are not — nothing to compare against.
  const isDaily = mode === 'daily' && editionIndex != null;
  S.share = isDaily ? {
    text: threadShareText(editionIndex, { guesses, solved, perfect, mistakes, title }),
    card: {
      game: 'THREAD', glyph: '🧵', score, sub: `ISSUE № ${editionIndex}`,
      rows: threadEmojiRows(guesses),
      url: shareUrl('thread'),
    },
    trackAs: 'share-thread',
  } : null;
  const shareBtn = $('#conn-sum-share');
  if (shareBtn) shareBtn.hidden = !S.share;
  wireTurnThePage('conn-sum-turn', editionIndex, isDaily);
  const head = $('#conn-receipt-head');
  if (head) {
    head.textContent = 'Dead Famous · Thread'
      + (mode === 'daily' && editionIndex != null ? ` · № ${editionIndex}` : '');
  }
  const rows = $('#conn-sum-rows');
  rows.innerHTML = '';
  const add = (name, sub, pts, zero) => {
    const li = document.createElement('li');
    li.innerHTML = `<span class="sum-name">${name}${sub ? `<small>${sub}</small>` : ''}</span>`
      + `<span class="sum-pts${zero ? ' zero' : ''}">${pts}</span>`;
    rows.appendChild(li);
  };
  if (solved) {
    add('Board solved', title, '+100', false);
    if (mistakes) add(`Mistake${mistakes === 1 ? '' : 's'} × ${mistakes}`, '', `−${mistakes * 20}`, true);
    const floor = score - (100 - mistakes * 20);
    if (floor) add('House floor', 'nobody leaves empty-handed', `+${floor}`, false);
  } else {
    add(found != null ? `${found} of 4 groups found` : 'Game over', title, '0', true);
  }
  $('#conn-sum-total').textContent = score;
  setReceiptStamp('view-connsum', score);
  $('#conn-sum-report').href = daily.reportProblemHref(null, editionIndex);
  const msg = perfect ? 'Not a thread out of place.'
    : solved ? (mistakes >= 3 ? 'By a thread.' : 'Frayed, but intact.')
    : 'The thread snapped.';
  $('#conn-sum-msg').innerHTML = msg;
}

function shuffleTiles() {
  const remaining = S.tiles.filter((t) => !S.found.has(t.colour));
  const shuffled = shuffleArray(remaining);
  const found = S.tiles.filter((t) => S.found.has(t.colour));
  S.tiles = [...found, ...shuffled];
  S.selected = new Set();
  renderGrid();
  $('#conn-submit').disabled = true;
}

// ---------- init ----------
export function initConnectionsGame() {
  ensureConnScoreStyles();
  // Re-fit tile fonts when the board first becomes visible and on rot/resize
  // (the grid is rendered while its view is still hidden, so sizes read as 0).
  document.addEventListener('viewchange', (e) => {
    if (e.detail === 'view-conn') fitConnTiles();
  });
  let rzTimer;
  window.addEventListener('resize', () => {
    clearTimeout(rzTimer);
    rzTimer = setTimeout(() => {
      if ($('#conn-grid') && $('#conn-grid').children.length) fitConnTiles();
    }, 120);
  });
  $('#conn-shuffle').addEventListener('click', shuffleTiles);
  $('#conn-deselect').addEventListener('click', () => {
    S.selected = new Set();
    $('#conn-submit').disabled = true;
    updateTileSelection();
  });
  $('#conn-submit').addEventListener('click', submitGuess);
  $('#conn-help').addEventListener('click', () => openIntroHelp('thread'));
  const connShare = $('#conn-sum-share');
  if (connShare) {
    connShare.addEventListener('click', async () => {
      if (!S || !S.share) return;
      const out = await shareResult(S.share);
      flashShareButton(connShare, out, 'Share the thread');
    });
  }
  $('#conn-quit').addEventListener('click', () => {
    // Header back arrow: leave the puzzle, same as every other game's back
    // button — it must not just undo a selection. Save progress first so
    // reopening the puzzle resumes where it left off.
    if (S && !S.done) persistProgress();
    S = null;
    back();
  });
  // Leaving a finished board goes HOME (owner call 2026-07-15) — back() would
  // land on the spent board itself, a dead end. Same convention as the other
  // three games' summary back buttons (sum-back / rv-sum-back → goHome).
  $('#conn-sum-back').addEventListener('click', () => {
    goHome();
  });
}
