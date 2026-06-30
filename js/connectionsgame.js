// Connections — group 16 history clues into four hidden categories
import { DATA, $, $$, show, back, goHome, refreshHomeStats } from './app.js';
import * as store from './storage.js';

const MAX_MISTAKES = 4;
const COLOUR_ORDER = ['yellow', 'green', 'blue', 'purple'];
let S = null;
let currentPuzzle = null;

// ---------- puzzle list ----------
export function renderConnList() {
  const main = $('#conn-list-main');
  main.innerHTML = '';
  DATA.connections.forEach((puzzle) => {
    const saved = store.getConn(puzzle.id);
    const btn = document.createElement('button');
    btn.className = 'cwitem';
    const status = saved ? (saved.perfect ? '✓ Perfect' : `✓ Solved`) : '';
    const statusClass = saved ? 'cw-state done' : 'cw-state';
    btn.innerHTML =
      `<span class="cw-size">${puzzle.groups.length}×4</span>` +
      `<span class="cw-name">${puzzle.title}</span>` +
      `<span class="${statusClass}">${status}</span>`;
    btn.addEventListener('click', () => startPuzzle(puzzle));
    main.appendChild(btn);
  });
}

// ---------- start a puzzle ----------
function shuffleArray(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function startPuzzle(puzzle) {
  currentPuzzle = puzzle;
  // Build flat tile list from all groups
  const tiles = [];
  puzzle.groups.forEach((group) => {
    group.items.forEach((item) => {
      tiles.push({ item, colour: group.colour, label: group.label });
    });
  });

  S = {
    puzzle,
    tiles: shuffleArray(tiles),
    selected: new Set(),
    found: new Set(),       // set of colour strings already solved
    mistakes: 0,
    done: false,
  };

  $('#conn-puzzle-title').textContent = puzzle.title;
  renderConnGame();
  show('view-conn');
}

function renderConnGame() {
  renderFound();
  renderGrid();
  updateMistakesDisplay();
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
      `<div class="conn-group-label">${group.label}</div>` +
      `<div class="conn-group-items">${group.items.join(', ')}</div>`;
    found.appendChild(div);
  });
}

function renderGrid() {
  const grid = $('#conn-grid');
  grid.innerHTML = '';
  const remaining = S.tiles.filter((t) => !S.found.has(t.colour));
  remaining.forEach((tile, i) => {
    const div = document.createElement('div');
    div.className = 'conn-tile' + (S.selected.has(i) ? ' conn-selected' : '');
    div.textContent = tile.item;
    div.addEventListener('click', () => onTapTile(i));
    grid.appendChild(div);
  });
}

function onTapTile(i) {
  if (S.done) return;
  if (S.selected.has(i)) {
    S.selected.delete(i);
  } else if (S.selected.size < 4) {
    S.selected.add(i);
  }
  $('#conn-submit').disabled = S.selected.size !== 4;
  renderGrid();
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
}

function submitGuess() {
  if (S.selected.size !== 4 || S.done) return;
  const remaining = S.tiles.filter((t) => !S.found.has(t.colour));
  const selectedTiles = [...S.selected].map((i) => remaining[i]);
  const colours = selectedTiles.map((t) => t.colour);
  const allSame = colours.every((c) => c === colours[0]);

  const fb = $('#conn-feedback');

  if (allSame) {
    S.found.add(colours[0]);
    S.selected = new Set();
    fb.hidden = true;

    if (S.found.size === S.puzzle.groups.length) {
      // all found
      S.done = true;
      setTimeout(() => finishPuzzle(), 400);
    } else {
      renderConnGame();
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
    fb.textContent = oneAway ? 'One away!' : 'Not quite — try again';
    fb.hidden = false;

    // shake the grid
    const grid = $('#conn-grid');
    grid.classList.remove('conn-shake');
    void grid.offsetWidth;
    grid.classList.add('conn-shake');

    renderGrid();
    $('#conn-submit').disabled = true;

    if (S.mistakes >= MAX_MISTAKES) {
      S.done = true;
      setTimeout(() => finishPuzzle(), 600);
    }
  }
}

function finishPuzzle() {
  const perfect = S.found.size === S.puzzle.groups.length && S.mistakes === 0;
  const solved = S.found.size === S.puzzle.groups.length;
  store.setConn(currentPuzzle.id, { solved, perfect, mistakes: S.mistakes });
  const stats = store.getConnStats();
  if (solved) stats.solved = (stats.solved || 0) + 1;
  store.setConnStats(stats);
  refreshHomeStats();

  // summary
  $('#conn-sum-title').textContent = S.puzzle.title;
  const msg = perfect ? 'Perfect — no mistakes!' :
    solved ? `Solved with ${S.mistakes} mistake${S.mistakes === 1 ? '' : 's'}` :
    `${S.found.size} of 4 groups found`;
  $('#conn-sum-msg').textContent = msg;

  const reveal = $('#conn-sum-groups');
  reveal.innerHTML = '';
  COLOUR_ORDER.forEach((colour) => {
    const group = S.puzzle.groups.find((g) => g.colour === colour);
    const div = document.createElement('div');
    div.className = `conn-group conn-group-${colour}`;
    div.innerHTML =
      `<div class="conn-group-label">${group.label}</div>` +
      `<div class="conn-group-items">${group.items.join(', ')}</div>`;
    reveal.appendChild(div);
  });

  show('view-connsum');
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
  $('#conn-shuffle').addEventListener('click', shuffleTiles);
  $('#conn-deselect').addEventListener('click', () => {
    S.selected = new Set();
    $('#conn-submit').disabled = true;
    renderGrid();
  });
  $('#conn-submit').addEventListener('click', submitGuess);
  $('#conn-quit').addEventListener('click', () => {
    S = null;
    back();
  });
  $('#conn-sum-back').addEventListener('click', () => {
    renderConnList();
    back();
  });
  $('#conn-sum-list').addEventListener('click', () => {
    renderConnList();
    show('view-connlist');
  });
}
