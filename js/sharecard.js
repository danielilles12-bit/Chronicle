// Share 3.0 — the stranger-first grammar (Daniel, 21 Aug 2026): one plain
// sentence a friend who has never seen the game can act on (name the game,
// name the app, give the score), the emoji row as a bare fingerprint of the
// run, the dare, the link. No date in the text (the challenge landing card
// names the puzzle's day), no streak line, no jargon detail lines. Survived
// two GPT critique rounds; see HOUSE_RULES "Sharing".
//
// TEXT AND EMOJI ONLY (Daniel, 7 Aug 2026). A share is written results +
// emoji + the link — never a generated image. The canvas "receipt card" that
// used to ride along as a PNG file attachment is gone; no share path may ever
// attach a file again. See HOUSE_RULES.md "Sharing".
import { track } from './track.js';
import * as daily from './daily.js';

// A share names the DAY, not the issue number (Daniel, 9 Aug 2026): the
// callers still pass an edition index, and this is the one place it turns
// into words a recipient can read.
const day = (issue) => daily.editionDateLabel(issue);

// Full scheme on purpose: bare domains don't linkify in Discord/Slack.
// ?ref=share shows shared-link visits under the GoatCounter Campaigns panel
// ("ref" is in its default campaign params). track.js scrubs the param after
// the pageview is counted so it never bakes into an installed app's URL.
//
// The Challenge Rally (Daniel, 19 Aug 2026): a share is a dare, not a
// receipt. Every share link now also carries e=<edition> and s=<score>, so
// the recipient opens the exact puzzle they were challenged to — app.js's
// boot router clamps e to the recipient's own reachable window (never the
// future, never past the archive) and greets them with the score to beat.
// A per-game share carries ?play=<game>; the full-house share names no game
// (e+s alone = a whole-day challenge, landed as a Home strip). The obituary
// keeps the bare link — a wake is not a duel. Plain validated params on
// purpose — no signing, see the discarded X1 card in the audited plan.
const BASE_URL = 'https://yesternerd.app/';
// Build 2 (19 Aug 2026): a per-game share links its landing page —
// /play/<player-facing-slug> — whose static og: tags give chat apps that
// game's own preview card (crawlers never run JS, so ?play= alone always
// showed the generic card). The page bounces humans into the app with
// every param preserved; old ?play= links keep working forever.
const GAME_PATH = { who: 'face-value', map: 'lifeline', what: 'relic', thread: 'thread' };
export function shareUrl(game, ch) {
  const p = new URLSearchParams();
  if (ch && Number.isInteger(ch.e) && ch.e >= 0) p.set('e', String(ch.e));
  if (ch && Number.isInteger(ch.s) && ch.s >= 0) p.set('s', String(ch.s));
  p.set('ref', 'share');
  const base = game ? `${BASE_URL}play/${GAME_PATH[game]}` : BASE_URL;
  return `${base}?${p.toString()}`;
}

const THREAD_EMOJI = { yellow: '🟨', green: '🟩', blue: '🟦', purple: '🟪' };

// The result grid. This IS the shareable thing — pure colour squares, the
// Wordle-family convention. Exported so any surface can render the same
// encoding the share text uses.
export function threadEmojiRows(guesses) {
  return (guesses || []).map((g) => g.map((c) => THREAD_EMOJI[c] || '⬜').join(''));
}
export function mapEmojiRow(rounds) {
  // mcq = rescued via the three-choices clue: assisted, same glyph as hints.
  return rounds.map((r) => (!r.correct ? '⚰️' : (r.hints || r.mcq) ? '🧭' : '✅')).join('');
}
export function revealEmojiRow(rounds) {
  return rounds.map((r) => {
    if (!r.correct) return '🟥';
    return ((r.torn || 0) >= 4 || (r.wrongs || 0) > 0 || r.mcq) ? '🟨' : '🟩';
  }).join('');
}

function lines(url, ...parts) {
  return parts.concat(url ? [url] : []).filter(Boolean).join('\n');
}

// ---------- per-game share text ----------
// Stranger-first grammar (Daniel, 21 Aug 2026; scores still read over their
// maximum per the 19 Aug ruling — "64/100", never "64 pts"). Losses share
// exactly the same way — a 0/100 to beat is the most beatable dare in the
// paper. "I just played" and not "I've been playing": always true, even for
// a first-timer's very first share.
const GAME_TITLE = { who: 'Face Value', map: 'Lifeline', what: 'Relic', thread: 'Thread' };
const DARE = 'Think you can beat me?';
const opener = (game, score) =>
  `I just played ${GAME_TITLE[game]}, one of Yesternerd's daily history games, and got ${score}/100.`;

export function threadShareText(issue, d) {
  const grid = threadEmojiRows(d.guesses).join('\n');
  const score = d.score || 0;
  return lines(shareUrl('thread', { e: issue, s: score }),
    opener('thread', score), grid, DARE);
}

export function mapShareText(issue, rounds, score) {
  return lines(shareUrl('map', { e: issue, s: score }),
    opener('map', score), mapEmojiRow(rounds), DARE);
}

export function revealShareText(kind, issue, rounds, score) {
  return lines(shareUrl(kind, { e: issue, s: score }),
    opener(kind, score), revealEmojiRow(rounds), DARE);
}

// The streak stays home (21 Aug 2026): it read as sender vanity to a
// stranger, and the four scores already prove the day was played. Callers
// still pass it; it is deliberately unread.
export function fullHouseShareText(issue, scores, total) {
  const row = `🖼️${scores.who} 🗺️${scores.map} 🏺${scores.what} 🧵${scores.thread}`;
  return lines(shareUrl(null, { e: issue, s: total }),
    `I just played all four of Yesternerd's daily history games and got ${total}/400.`,
    row, 'Think you can beat my total?');
}

// The receipt's verdict when a challenged player finishes the exact thing
// they were dared on. One writer so every surface speaks identically; the
// day-done screen passes max=400 for a full-house dare.
export function challengeVerdictLine(theirs, yours, max) {
  const m = max || 100;
  if (yours > theirs) return `Their ${theirs}/${m} · your ${yours}/${m}. Beaten.`;
  if (yours === theirs) return `Their ${theirs}/${m} · your ${yours}/${m}. Dead heat.`;
  return `Their ${theirs}/${m} stands. You: ${yours}/${m}.`;
}

export function obituaryShareText(streak, fromIssue, toIssue) {
  return lines(shareUrl(), 'YESTERNERD ⚰️',
    `My ${streak}-day streak died.`,
    `RIP ${day(fromIssue)}–${day(toIssue)}. MEMENTO MORI.`);
}

// ---------- the share flow ----------
// Text is the only unit: it pastes everywhere, it survives every app, and it
// is what a group chat actually reads. Never a file — see the ruling at the
// top of this file. Cancelling the sheet is respected silently; no sheet at
// all falls back to the clipboard.
export async function shareResult({ text, trackAs }) {
  const outcome = await performShare(text);
  // Count what actually happened, not the button tap: only 'shared' fires the
  // success event; copied/cancelled/failed each get their own suffixed event
  // so abandoned share sheets never inflate the share numbers.
  if (trackAs) track(outcome === 'shared' ? trackAs : `${trackAs}-${outcome}`);
  return outcome;
}

async function performShare(text) {
  try {
    if (navigator.share) { await navigator.share({ text }); return 'shared'; }
  } catch (e) {
    if (e && e.name === 'AbortError') return 'cancelled';
  }
  try { await navigator.clipboard.writeText(text); return 'copied'; } catch (e) { /* sandboxed */ }
  return 'failed';
}

// Uniform button feedback for the copied/failed fallbacks.
export function flashShareButton(btn, outcome, idleLabel) {
  if (outcome === 'copied') btn.textContent = 'Copied — paste it anywhere';
  else if (outcome === 'failed') btn.textContent = 'Sharing unavailable here';
  else return;
  setTimeout(() => { btn.textContent = idleLabel; }, 1800);
}
