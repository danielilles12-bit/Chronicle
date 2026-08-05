// The field line — "Your 84 beat about 7 in 10 of today's players." — the
// whole client side of the anonymous score comparison (plan:
// design-reviews/leaderboard-plan.md, approved 5 Aug 2026). One optional
// line on each game's daily results screen; no names, no rankings, no new
// screen, no login.
//
// Iron rule (the plan's launch-safety guarantee): the app must be
// byte-identical in behaviour when the service is absent. Offline, timeout,
// non-200, kill switch off, opt-out — every one of them renders nothing,
// logs nothing user-visible, and never blocks, delays or alters play,
// scoring, streaks, Carry, sharing or navigation. One POST, one timeout,
// never a retry.
import * as daily from './daily.js';
import { track } from './track.js';
import { PERCENTILE_ON } from './app.js';

// ---------- the wording bands (Daniel's ruling, 5 Aug 2026) ----------
// These three numbers ARE the ruling — change one line here to move a band;
// nothing else encodes them.
export const FIELD_MIN = 10;         // fewer than this many players: render
                                     // NOTHING — no line, no placeholder, no
                                     // layout shift (the under-10 silence rule)
export const FIELD_APPROX_MIN = 20;  // FIELD_MIN up to here: the honest
                                     // small-field line ("You're among the
                                     // first N players…"), no percentage
export const FIELD_PERCENT_MIN = 50; // FIELD_APPROX_MIN up to here: approximate
                                     // words ("about 7 in 10"); from here on:
                                     // a percentage rounded to the nearest 5

const ENDPOINT = '/api/score';
const TIMEOUT_MS = 4000;  // one attempt; an answer slower than this isn't worth the wait

// Standalone localStorage keys, deliberately OUTSIDE the storage.js blob:
// the dedup token must never travel with a Carry export (no cross-device,
// no cross-day identity — the plan's hardest privacy line), and privacy.html
// — a plain page with no modules — needs the opt-out flag reachable without
// parsing the blob. Same pattern as GoatCounter's 'skipgc'.
const OPTOUT_KEY = 'skipcompare'; // 't' = the player turned comparison off
const TOKEN_KEY = 'fieldtoken';   // {n: edition, t: token} — overwritten next edition

// "Compare my scores anonymously" — default ON (Daniel, 5 Aug 2026:
// disclosure on privacy.html instead of a consent prompt). Off means no POST
// at all, never "POST but hide".
export function isCompareOn() {
  try { return localStorage.getItem(OPTOUT_KEY) !== 't'; } catch (e) { return false; }
}

export function setCompareOn(on) {
  try { localStorage.setItem(OPTOUT_KEY, on ? 'f' : 't'); } catch (e) { /* private mode */ }
  track(on ? 'percentile-on' : 'percentile-off');
}

// A fresh random token per edition, used only so the same finish isn't
// counted twice that day (the server dedups on it). It means nothing, is
// shared by all four games of one edition, and writing the next edition's
// token destroys it — so it can never link Monday's player to Tuesday's.
function newToken() {
  try {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  } catch (e) { /* fall through */ }
  let t = '';
  for (let i = 0; i < 32; i++) t += Math.floor(Math.random() * 16).toString(16);
  return t;
}

function editionToken(edition) {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(TOKEN_KEY)); } catch (e) { /* absent/corrupt */ }
  if (saved && saved.n === edition && typeof saved.t === 'string') return saved.t;
  const t = newToken();
  try { localStorage.setItem(TOKEN_KEY, JSON.stringify({ n: edition, t })); } catch (e) { /* private mode */ }
  return t;
}

// The line itself, or null for silence. Ties are never "beaten": `below`
// counts scores strictly under yours (server-side); `total` includes you.
// Both banded numbers get words at their extremes instead of a broken or
// brutal figure — "about 0 in 10" and "about 10 in 10" read like misprints,
// "beat 0%" is needlessly cruel, and "beat 100%" claims more than happened.
export function wording(score, below, total) {
  if (!Number.isFinite(below) || !Number.isFinite(total)) return null;
  if (total < FIELD_MIN) return null;                 // the under-10 silence rule
  const b = Math.max(0, Math.min(total - 1, below));
  if (total < FIELD_APPROX_MIN) {
    return `You’re among the first ${total} players of today’s issue.`;
  }
  if (total < FIELD_PERCENT_MIN) {
    const tenths = Math.round((b / total) * 10);
    if (tenths <= 0) return `Your ${score} joins the back of today’s field.`;
    if (tenths >= 10) return `Your ${score} beat nearly all of today’s players.`;
    return `Your ${score} beat about ${tenths} in 10 of today’s players.`;
  }
  const pct = Math.round((b / total) * 20) * 5;       // nearest 5
  // Same treatment at this band's extremes (Daniel, 5 Aug 2026). "beat 0%" is
  // brutal, and "beat 100%" is a rounding artefact — you never beat yourself,
  // so 199/200 rounds to a number that claims more than happened.
  if (pct <= 0) return `Your ${score} joins the back of today’s field.`;
  if (pct >= 100) return `Your ${score} beat nearly all of today’s players.`;
  return `Your ${score} beat ${pct}% of today’s players.`;
}

// One POST, one timeout, no retries. Every failure mode returns null and is
// swallowed here — the caller renders nothing and the game never knows.
async function post(game, edition, score) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(ENDPOINT, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ edition, game, score, token: editionToken(edition) }),
      signal: ctrl.signal,
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (!data || !Number.isFinite(data.below) || !Number.isFinite(data.total)) return null;
    return data;
  } catch (e) {
    return null;   // offline, timeout, DNS, service dark — all identical: nothing
  } finally {
    clearTimeout(timer);
  }
}

// The one entry point, called by each game's summary render (mapgame.js /
// revealgame.js / connectionsgame.js). Always starts by resetting the
// element, so a practice or Encore summary can never show a stale line from
// an earlier daily. Fire-and-forget: the summary paints immediately and the
// line joins it only if an answer arrives.
//
// Dailies only, TODAY only: practice and Encore never post (isDaily is false
// for both), and neither does a repair-window completion or a locked reopen
// of a past day — the line says "today's players", so only today's edition
// may ever produce it.
export function renderFieldLine(elId, game, editionIndex, score, isDaily) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.hidden = true;
  el.textContent = '';
  if (!isDaily || !PERCENTILE_ON || !isCompareOn()) return;
  if (editionIndex == null || editionIndex !== daily.todayIndex()) return;
  const s = Math.round(score || 0);
  if (!(s >= 0 && s <= 100)) return;
  post(game, editionIndex, s).then((r) => {
    if (!r) return;
    const text = wording(s, r.below, r.total);
    if (!text) return;
    el.textContent = text;
    el.hidden = false;
    track('percentile-shown');
  }).catch(() => { /* never surfaces */ });
}
