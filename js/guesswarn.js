// First-guess warning (Daniel, 5 Aug 2026).
//
// The wrong-guess price used to sit inside the Guess button ("if wrong −15
// pts"), which crowded the one control the player most needs to read. It now
// arrives once, as a question, at the only moment it matters: the first time
// someone submits a typed guess in a given game.
//
// Per-GAME, not per-player: Relic asks even if Face Value already did. A
// player who learned the rule in one game is still meeting a new game's first
// round, and the two games price the same mistake differently over time.
// Lifeline is included for the same reason — it is the third typed-answer
// game and its Guess button lost the same hint.
//
// State lives in misc.guessWarned = { who: true, ... }; a game that has asked
// never asks again on that device. Practice and encore rounds count too —
// the warning is about the rule, not the stakes.
import * as store from './storage.js';

const el = (id) => document.getElementById(id);

function seen() {
  return (store.getMisc().guessWarned) || {};
}

function markSeen(game) {
  const cur = seen();
  store.setMisc({ guessWarned: Object.assign({}, cur, { [game]: true }) });
}

function close() {
  const sheet = el('guess-warn');
  if (sheet) sheet.hidden = true;
}

// Ask, if this game has never asked. Returns true when the caller should go
// ahead and submit immediately (already warned, or storage unavailable);
// false when the sheet has taken over — `proceed` runs if they confirm.
export function confirmFirstGuess(game, cost, proceed) {
  let already = true;
  try { already = !!seen()[game]; } catch (e) { already = true; }
  const sheet = el('guess-warn');
  if (already || !sheet) return true;

  el('guess-warn-copy').textContent =
    `Are you sure? A wrong guess costs ${cost} points. A right one costs nothing.`;

  const go = el('guess-warn-go');
  const back = el('guess-warn-back');
  const finish = (confirmed) => {
    go.onclick = null; back.onclick = null; sheet.onclick = null;
    document.removeEventListener('keydown', onKey);
    close();
    markSeen(game);          // asked once, whatever they chose
    if (confirmed) proceed();
  };
  function onKey(e) { if (e.key === 'Escape') finish(false); }

  go.onclick = () => finish(true);
  back.onclick = () => finish(false);
  sheet.onclick = (e) => { if (e.target === sheet) finish(false); };
  document.addEventListener('keydown', onKey);

  sheet.hidden = false;
  go.focus();
  return false;
}

// Deterministic hook for the Python suite (same gating as everywhere else).
export function testHooks() {
  return { seen, markSeen };
}
