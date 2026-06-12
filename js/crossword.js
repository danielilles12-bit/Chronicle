// NYT-style crossword engine: selection, direction toggle, auto-advance,
// clue bar, clue list, check/reveal, timer, correct-only completion.
import { DATA, $, $$, show, back, appConfirm } from './app.js';
import * as store from './storage.js';

let G = null;          // current game
let timerInt = null;

const FORMAT_META = {
  mini: ['Mini', '5×5 — a quick one'],
  midi: ['Midi', '7×7 — a coffee break'],
  full: ['Full', 'The full-size grid'],
};

// ---------- list ----------
export function renderPuzzleList() {
  const root = $('#cwlist');
  root.innerHTML = '';
  for (const fmt of ['mini', 'midi', 'full']) {
    const puzzles = DATA.puzzles.filter((p) => p.format === fmt);
    if (!puzzles.length) continue;
    const h = document.createElement('h3');
    h.className = 'cw-group-title';
    h.textContent = FORMAT_META[fmt][0];
    const sub = document.createElement('p');
    sub.className = 'cw-group-sub';
    sub.textContent = FORMAT_META[fmt][1];
    root.append(h, sub);
    puzzles.forEach((p) => {
      const st = store.getPuzzle(p.id);
      const btn = document.createElement('button');
      btn.className = 'cwitem';
      btn.dataset.pid = p.id;
      const state = st && st.completed
        ? `<span class="cw-state done">✓ ${fmtTime(st.elapsed)}</span>`
        : (st && st.entries && st.entries.some((e) => e)
          ? '<span class="cw-state">In progress</span>'
          : '<span class="cw-state">—</span>');
      btn.innerHTML = `<span class="cw-size">${p.size}×${p.size}</span>`
        + `<span class="cw-name">${p.title}</span>${state}`;
      btn.addEventListener('click', () => openPuzzle(p));
      root.appendChild(btn);
    });
  }
}

// ---------- model ----------
function buildModel(p) {
  const n = p.size;
  const cells = [];
  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) {
      cells.push({ r, c, i: r * n + c, block: p.grid[r][c] === '#', sol: p.grid[r][c], num: null, slot: { across: null, down: null }, pos: { across: 0, down: 0 } });
    }
  }
  const at = (r, c) => cells[r * n + c];
  // derive numbering identically to the validator
  let num = 0;
  const slots = { across: [], down: [] };
  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) {
      const cell = at(r, c);
      if (cell.block) continue;
      const sa = (c === 0 || at(r, c - 1).block) && c + 1 < n && !at(r, c + 1).block;
      const sd = (r === 0 || at(r - 1, c).block) && r + 1 < n && !at(r + 1, c).block;
      if (sa || sd) { num++; cell.num = num; }
      if (sa) {
        const s = { num, dir: 'across', cells: [] };
        for (let cc = c; cc < n && !at(r, cc).block; cc++) s.cells.push(at(r, cc).i);
        slots.across.push(s);
      }
      if (sd) {
        const s = { num, dir: 'down', cells: [] };
        for (let rr = r; rr < n && !at(rr, c).block; rr++) s.cells.push(at(rr, c).i);
        slots.down.push(s);
      }
    }
  }
  // attach clue text and back-references
  for (const dir of ['across', 'down']) {
    for (const s of slots[dir]) {
      const cl = p.clues[dir].find((x) => x.num === s.num);
      s.clue = cl ? cl.clue : '';
      s.cells.forEach((i, k) => { cells[i].slot[dir] = s; cells[i].pos[dir] = k; });
    }
  }
  const all = slots.across.concat(slots.down);
  return { cells, slots, all, n };
}

// ---------- open / persist ----------
export function openPuzzle(p) {
  const m = buildModel(p);
  const saved = store.getPuzzle(p.id) || {};
  G = {
    p, ...m,
    entries: (saved.entries && saved.entries.length === m.cells.length)
      ? saved.entries.slice() : m.cells.map(() => ''),
    wrong: new Set(saved.wrong || []),
    revealed: new Set(saved.revealed || []),
    elapsed: saved.elapsed || 0,
    completed: !!saved.completed,
    sel: null, dir: 'across',
  };
  $('#cw-title').textContent = p.title;
  buildGridDOM();
  buildClueLists();
  show('view-cw');
  sizeGrid();             // after show: a hidden container has zero width
  selectSlot(G.slots.across[0], true);
  renderTimer();
  if (!G.completed) startTimer();
}

function persist() {
  store.setPuzzle(G.p.id, {
    entries: G.entries,
    wrong: [...G.wrong],
    revealed: [...G.revealed],
    elapsed: G.elapsed,
    completed: G.completed,
  });
}

// ---------- DOM ----------
function buildGridDOM() {
  const grid = $('#cw-grid');
  grid.style.setProperty('--n', G.n);
  grid.innerHTML = '';
  for (const cell of G.cells) {
    const d = document.createElement('div');
    d.className = 'cell' + (cell.block ? ' block' : '');
    d.dataset.i = cell.i;
    if (!cell.block) {
      d.innerHTML = (cell.num ? `<span class="num">${cell.num}</span>` : '')
        + '<span class="letter"></span>';
    }
    grid.appendChild(d);
  }
}

function sizeGrid() {
  if (!G) return;
  const head = 56, cluebar = 50, kb = 178, pad = 26;
  const avail = window.innerHeight - head - cluebar - kb - pad;
  const side = Math.min($('#cw-grid-wrap').clientWidth - 8, avail, 560);
  const grid = $('#cw-grid');
  grid.style.setProperty('--gridside', side + 'px');
  grid.style.setProperty('--cell', (side / G.n) + 'px');
}

function buildClueLists() {
  for (const dir of ['across', 'down']) {
    const ol = $('#cw-cluelist-' + dir);
    ol.innerHTML = '';
    for (const s of G.slots[dir]) {
      const li = document.createElement('li');
      li.dataset.dir = dir;
      li.dataset.num = s.num;
      li.innerHTML = `<span class="cl-num">${s.num}</span><span>${s.clue}</span>`;
      li.addEventListener('click', () => {
        selectSlot(s, true);
        $('#cw-cluelist').hidden = true;
      });
      ol.appendChild(li);
    }
  }
}

// ---------- selection ----------
function curSlot() { return G.cells[G.sel].slot[G.dir]; }

function selectCell(i, dir) {
  if (G.cells[i].block) return;
  if (dir) G.dir = dir;
  G.sel = i;
  paint();
}

function selectSlot(s, firstEmpty) {
  G.dir = s.dir;
  let target = s.cells[0];
  if (firstEmpty) {
    const empty = s.cells.find((i) => !G.entries[i]);
    if (empty !== undefined) target = empty;
  }
  G.sel = target;
  paint();
}

function paint() {
  const slot = curSlot();
  $$('#cw-grid .cell').forEach((el) => {
    const i = +el.dataset.i;
    const cell = G.cells[i];
    if (cell.block) return;
    el.classList.toggle('sel', i === G.sel);
    el.classList.toggle('word', i !== G.sel && slot.cells.includes(i));
    el.classList.toggle('wrong', G.wrong.has(i));
    el.classList.toggle('revealed', G.revealed.has(i));
    el.querySelector('.letter').textContent = G.entries[i] || '';
  });
  $('#cw-clue-label').textContent = `${slot.num} ${slot.dir === 'across' ? 'Across' : 'Down'}`;
  $('#cw-clue-text').textContent = slot.clue;
  window.__CHRONICLE_TEST__ = Object.assign(window.__CHRONICLE_TEST__ || {}, {
    cw: {
      id: G.p.id, sel: G.sel, dir: G.dir, completed: G.completed,
      entries: G.entries.slice(), sol: G.cells.map((c) => c.sol),
    },
  });
  // clue list states
  $$('#cw-cluelist li').forEach((li) => {
    const s = G.slots[li.dataset.dir].find((x) => x.num === +li.dataset.num);
    li.classList.toggle('done', s.cells.every((i) => G.entries[i]));
    li.classList.toggle('current', s === slot);
  });
}

// ---------- input ----------
function type(ch) {
  if (!G || G.completed) return;
  const i = G.sel;
  G.entries[i] = ch;
  G.wrong.delete(i);
  advanceAfterFill();
  persist();
  checkCompletion();
  paint();
}

function advanceAfterFill() {
  const slot = curSlot();
  const k = G.cells[G.sel].pos[G.dir];
  for (let j = k + 1; j < slot.cells.length; j++) {
    if (!G.entries[slot.cells[j]]) { G.sel = slot.cells[j]; return; }
  }
  for (let j = 0; j < k; j++) {
    if (!G.entries[slot.cells[j]]) { G.sel = slot.cells[j]; return; }
  }
  // word complete -> next clue with an empty cell
  nextClue(true);
}

function backspace() {
  if (!G || G.completed) return;
  const i = G.sel;
  if (G.entries[i]) {
    G.entries[i] = '';
    G.wrong.delete(i);
  } else {
    const slot = curSlot();
    const k = G.cells[i].pos[G.dir];
    if (k > 0) {
      G.sel = slot.cells[k - 1];
    } else {
      prevClue(false);
      const s2 = curSlot();
      G.sel = s2.cells[s2.cells.length - 1];
    }
    G.entries[G.sel] = '';
    G.wrong.delete(G.sel);
  }
  persist();
  paint();
}

function clueIndex() { return G.all.indexOf(curSlot()); }

function nextClue(onlyWithEmpty) {
  const start = clueIndex();
  for (let step = 1; step <= G.all.length; step++) {
    const s = G.all[(start + step) % G.all.length];
    if (!onlyWithEmpty || s.cells.some((i) => !G.entries[i])) { selectSlot(s, true); return; }
  }
  paint();
}

function prevClue(firstEmpty) {
  const start = clueIndex();
  const s = G.all[(start - 1 + G.all.length) % G.all.length];
  selectSlot(s, firstEmpty);
}

function toggleDir() {
  G.dir = G.dir === 'across' ? 'down' : 'across';
  paint();
}

// ---------- check / reveal ----------
function scopeCells(scope) {
  if (scope === 'square') return [G.sel];
  if (scope === 'word') return curSlot().cells.slice();
  return G.cells.filter((c) => !c.block).map((c) => c.i);
}

function doCheck(scope) {
  for (const i of scopeCells(scope)) {
    if (G.entries[i] && G.entries[i] !== G.cells[i].sol) G.wrong.add(i);
  }
  persist();
  paint();
}

function doReveal(scope) {
  const go = () => {
    for (const i of scopeCells(scope)) {
      if (G.entries[i] !== G.cells[i].sol) {
        G.entries[i] = G.cells[i].sol;
        G.revealed.add(i);
        G.wrong.delete(i);
      }
    }
    persist();
    checkCompletion();
    paint();
  };
  if (scope === 'puzzle') {
    appConfirm('Reveal the entire puzzle?', 'Reveal it').then((ok) => { if (ok) go(); });
  } else {
    go();
  }
}

function restart() {
  appConfirm('Clear all your answers and restart this puzzle?', 'Clear it').then((ok) => {
    if (!ok) return;
    G.entries = G.cells.map(() => '');
    G.wrong.clear();
    G.revealed.clear();
    G.elapsed = 0;
    G.completed = false;
    persist();
    renderTimer();
    startTimer();
    selectSlot(G.slots.across[0], true);
  });
}

// ---------- completion ----------
function checkCompletion() {
  const whites = G.cells.filter((c) => !c.block);
  if (!whites.every((c) => G.entries[c.i])) return;
  if (whites.every((c) => G.entries[c.i] === c.sol)) {
    if (G.completed) return;
    G.completed = true;
    stopTimer();
    persist();
    $('#cw-done-title').textContent = ['Splendid!', 'Bravo!', 'History made!'][Math.floor(Math.random() * 3)];
    $('#cw-done-sub').textContent = `${G.p.title} solved in ${fmtTime(G.elapsed)}.`;
    $('#cw-done').hidden = false;
    confetti();
  } else {
    const t = $('#cw-toast');
    t.hidden = false;
    clearTimeout(t._to);
    t._to = setTimeout(() => { t.hidden = true; }, 2200);
  }
}

function confetti() {
  const root = $('#confetti');
  root.innerHTML = '';
  const colors = ['#ffda00', '#a7d8ff', '#4a7c43', '#b4422e', '#9a7b2d'];
  for (let k = 0; k < 44; k++) {
    const d = document.createElement('div');
    d.className = 'confetto';
    d.style.left = Math.random() * 100 + '%';
    d.style.background = colors[k % colors.length];
    d.style.animationDelay = (Math.random() * 0.5) + 's';
    d.style.animationDuration = (1.1 + Math.random()) + 's';
    root.appendChild(d);
  }
  setTimeout(() => { root.innerHTML = ''; }, 2600);
}

// ---------- timer ----------
function startTimer() {
  stopTimer();
  timerInt = setInterval(() => {
    if (document.hidden || $('#view-cw').hidden) return;
    G.elapsed++;
    renderTimer();
    if (G.elapsed % 5 === 0) persist();
  }, 1000);
}

function stopTimer() {
  if (timerInt) clearInterval(timerInt);
  timerInt = null;
}

function renderTimer() {
  $('#cw-timer').textContent = fmtTime(G.elapsed);
}

function fmtTime(s) {
  return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
}

// ---------- keyboard ----------
function buildKeyboard() {
  const rows = ['QWERTYUIOP', 'ASDFGHJKL', 'ZXCVBNM⌫'];
  const root = $('#cw-keyboard');
  root.innerHTML = '';
  for (const row of rows) {
    const r = document.createElement('div');
    r.className = 'kb-row';
    for (const ch of row) {
      const k = document.createElement('button');
      k.className = 'kb-key' + (ch === '⌫' ? ' wide' : '');
      k.textContent = ch;
      k.addEventListener('click', () => (ch === '⌫' ? backspace() : type(ch)));
      r.appendChild(k);
    }
    root.appendChild(r);
  }
}

// ---------- init ----------
export function initCrossword() {
  buildKeyboard();

  $('#cw-grid').addEventListener('click', (e) => {
    const el = e.target.closest('.cell');
    if (!el || !G) return;
    const i = +el.dataset.i;
    if (G.cells[i].block) return;
    if (i === G.sel) toggleDir();
    else selectCell(i);
  });

  $('#cw-prev').addEventListener('click', () => prevClue(true));
  $('#cw-next').addEventListener('click', () => nextClue(false));
  $('#cw-clue-current').addEventListener('click', toggleDir);

  $('#cw-menu-btn').addEventListener('click', () => { $('#cw-sheet').hidden = false; });
  $('#cw-cluelist-btn').addEventListener('click', () => { $('#cw-cluelist').hidden = false; });
  $$('[data-close-sheet]').forEach((b) => b.addEventListener('click', () => {
    b.closest('.sheet').hidden = true;
  }));
  $$('.sheet').forEach((sh) => sh.addEventListener('click', (e) => {
    if (e.target === sh) sh.hidden = true;
  }));

  $$('#cw-sheet [data-check]').forEach((b) => b.addEventListener('click', () => {
    doCheck(b.dataset.check);
    $('#cw-sheet').hidden = true;
  }));
  $$('#cw-sheet [data-reveal]').forEach((b) => b.addEventListener('click', () => {
    $('#cw-sheet').hidden = true;
    doReveal(b.dataset.reveal);
  }));
  $('#cw-restart').addEventListener('click', () => {
    $('#cw-sheet').hidden = true;
    restart();
  });

  $$('#cw-cluelist .tab').forEach((t) => t.addEventListener('click', () => {
    $$('#cw-cluelist .tab').forEach((x) => x.classList.toggle('active', x === t));
    $('#cw-cluelist-across').hidden = t.dataset.tab !== 'across';
    $('#cw-cluelist-down').hidden = t.dataset.tab !== 'down';
  }));

  $('#cw-done-back').addEventListener('click', () => {
    $('#cw-done').hidden = true;
    renderPuzzleList();
    back();
  });

  window.addEventListener('resize', sizeGrid);
  document.addEventListener('visibilitychange', () => {
    // timer self-gates on document.hidden; nothing else needed
  });
  document.addEventListener('viewchange', (e) => {
    if (e.detail !== 'view-cw') stopTimer();
    else if (G && !G.completed && !timerInt) startTimer();
  });

  window.addEventListener('keydown', (e) => {
    if ($('#view-cw').hidden || !G) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (/^[a-zA-Z]$/.test(e.key)) { type(e.key.toUpperCase()); e.preventDefault(); }
    else if (e.key === 'Backspace') { backspace(); e.preventDefault(); }
    else if (e.key === 'Enter' || e.key === 'Tab') { e.shiftKey ? prevClue(true) : nextClue(false); e.preventDefault(); }
    else if (e.key.startsWith('Arrow')) {
      e.preventDefault();
      const horiz = e.key === 'ArrowLeft' || e.key === 'ArrowRight';
      const want = horiz ? 'across' : 'down';
      if (G.dir !== want) { G.dir = want; paint(); return; }
      const d = (e.key === 'ArrowRight' || e.key === 'ArrowDown') ? 1 : -1;
      const { r, c } = G.cells[G.sel];
      let rr = r, cc = c;
      while (true) {
        rr += horiz ? 0 : d; cc += horiz ? d : 0;
        if (rr < 0 || cc < 0 || rr >= G.n || cc >= G.n) return;
        const cand = G.cells[rr * G.n + cc];
        if (!cand.block) { selectCell(cand.i); return; }
      }
    }
  });
}
