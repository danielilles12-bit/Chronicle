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
// never asks again on that device. Free-play rounds count too — the warning
// is about the rule, not the stakes.
//
// THE SECOND WARNING (Daniel, 9 Aug 2026). "3 choices" is the most expensive
// button in the app and the only one that ends the round's work, and a first-
// timer had no way of knowing either before pressing it. It now asks the same
// way, once per game, off its own storage key.
import * as store from './storage.js';

const el = (id) => document.getElementById(id);

function seen(key) {
  return (store.getMisc()[key]) || {};
}

function markSeen(key, game) {
  const cur = seen(key);
  store.setMisc({ [key]: Object.assign({}, cur, { [game]: true }) });
}

function close(id) {
  const sheet = el(id);
  if (sheet) sheet.hidden = true;
}

// Both warnings are the same machine: a sheet with a go button, a back button,
// Escape and tap-outside both meaning "no", and the asking recorded whatever
// the player chose. `fill` writes the sheet's own words before it opens.
function askOnce({ sheetId, storeKey, game, fill, proceed }) {
  let already = true;
  try { already = !!seen(storeKey)[game]; } catch (e) { already = true; }
  const sheet = el(sheetId);
  if (already || !sheet) return true;

  fill();

  const go = el(sheetId + '-go');
  const back = el(sheetId + '-back');
  const finish = (confirmed) => {
    go.onclick = null; back.onclick = null; sheet.onclick = null;
    document.removeEventListener('keydown', onKey);
    close(sheetId);
    markSeen(storeKey, game);      // asked once, whatever they chose
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

// The way out of either sheet is phrased in the game's own verb: the two
// tearing games send you back to the scraps, Lifeline back to the two pins.
const backWord = (game) => (game === 'map' ? 'Keep looking' : 'Keep tearing');

// Ask, if this game has never asked. Returns true when the caller should go
// ahead and submit immediately (already warned, or storage unavailable);
// false when the sheet has taken over — `proceed` runs if they confirm.
export function confirmFirstGuess(game, cost, proceed) {
  return askOnce({
    sheetId: 'guess-warn',
    storeKey: 'guessWarned',
    game,
    proceed,
    fill: () => {
      el('guess-warn-copy').textContent =
        `Are you sure? A wrong guess costs ${cost} points.`;
      el('guess-warn-back').textContent = backWord(game);
    },
  });
}

// The same contract for the "3 choices" rescue: `cost` is what it will
// ACTUALLY take from this round right now (the caller works that out against
// the floor, exactly as the button's own label does), so the sheet and the
// button can never quote different numbers.
export function confirmFirstRescue(game, cost, proceed) {
  return askOnce({
    sheetId: 'mcq-warn',
    storeKey: 'rescueWarned',
    game,
    proceed,
    fill: () => {
      const shuts = game === 'map'
        ? 'no more clues'
        : 'no more tearing, no more clues';
      el('mcq-warn-copy').textContent =
        `Three choices costs ${cost} points and closes the round — ${shuts}. `
        + `A right pick still pays what's left.`;
      el('mcq-warn-back').textContent = backWord(game);
    },
  });
}

// Deterministic hook for the Python suite (same gating as everywhere else).
export function testHooks() {
  return { seen, markSeen };
}
