// "Face Value" / "Relic" — guess the famous face or artefact hidden under a
// 3x3 grid of paper scraps. The game opens one scrap on the house; tearing
// more is the player's choice and the player's cost: every player tear docks
// the round's worth, and wrong guesses dock more. No clock — curiosity is the
// only spender.
// Mirrors the Map of a Life session shape (persisted, resumable; round count
// comes from the edition — 3/day since edition 30, 5 before, free play 5).
import { DATA, $, show, back, goHome, refreshHomeStats, setReceiptStamp, maybeIntro, openIntroHelp, wireTurnThePage, wireEncore, teachWrongGuess, announce, testHooksEnabled, consumeShareLaunch, w800Url, loadImgFallback } from './app.js';
import * as store from './storage.js';
import { track, roundOutcome, durationBucket } from './track.js';
import { isMatch, registerPool } from './match.js';
import { confirmFirstGuess } from './guesswarn.js';
import * as daily from './daily.js';
import { revealShareText, shareResult, flashShareButton } from './sharecard.js';
import { attachPinchZoom } from './pinchzoom.js';
import * as sfx from './sfx.js';

const ROUNDS = 5;               // free-play run length (dailies take theirs from the edition)
const SCRAPS = 9;               // 3x3 cover grid
const TEAR_COST = 10;           // per player tear (the opening scrap is on the house)
const WRONG_PENALTY = 15;       // per wrong guess
const WORTH_START = 100;
const WORTH_FLOOR = 10;         // a correct answer never pays less than this
const CLUE_A_COST = 25;         // "Claim to fame" (who) / "First letters" (what)
const CLUE_B_COST = 15;         // "Lived" (who) / "Era" (what)
// The ultimate clue (Daniel, 28 Jul 2026; repriced as a COST 28 Jul evening):
// three choices instead of a dead-end give-up. Opening it docks the round's
// worth like any other clue slip — "−80 pts", same grammar as the rest —
// so an untouched round pays 20 on a correct pick and the "a correct answer
// never pays less than 10" floor still holds. It keeps a streak alive but
// never extends it (no ++, no bonus): a rescue, not a win. This also
// replaced the Reveal/I-give-up button: a wrong pick IS the reveal.
const MCQ_COST = 80;

// Card #10 (house-voice verdicts): the moment badge rotates through these
// deterministically by round index (S.i), never at random, so a reloaded/
// resumed round always shows the same word it showed before.
const CORRECT_VERDICTS = [
  'Dead right.', 'History remembers.', 'Straight to the record.',
  'Ink it.', 'On the record.', 'First take.',
];
const WRONG_VERDICTS = [
  'Misfiled.', 'The dead disagree.', 'The record says no.',
  'Citation needed.', 'Not them.',
];

let S = null;
let MODE = 'who';               // 'who' = portraits, 'what' = artefacts
let frameZoom = null;           // pinch-zoom handle for #rv-frame

function pool() {
  return DATA.reveal.filter((x) => (MODE === 'who' ? x.kind === 'portrait' : x.kind !== 'portrait'));
}

// ---------- clue slips (buyable hints) ----------
// WHO blurbs are reliably "Occupation (1638–1715) · credit": the occupation is
// everything before the first parenthetical; the years live inside it.
function clueOccupation(item) {
  let occ = (item.blurb || '').split('(')[0];   // drop "(years) · credit"
  occ = occ.split('·')[0];                      // and any bare "· credit" fragment
  return occ.trim().replace(/[·,\s]+$/, '').trim();
}
function clueYears(item) {
  // Explicit `years` field (curated, e.g. "1884–1972") wins over scraping the
  // blurb: some blurbs' first parenthetical is a role/tenure date (Truman's
  // presidency, not his lifespan), which made "Lived" show the wrong fact.
  if (item.years) return String(item.years).trim();
  const m = (item.blurb || '').match(/\(([^)]*\d[^)]*)\)/);   // first parens holding a digit
  return m ? m[1].trim() : null;
}

// Leading articles/particles skipped when abbreviating an artefact's name to
// initials ("The Colosseum" → "C.", "Hanging Gardens of Babylon" → "H. G. B.").
const REVEAL_ARTICLES = new Set([
  'the', 'of', 'a', 'an', 'and', 'la', 'le', 'el', 'al', 'de', 'del', 'della',
  'di', 'da', 'van', 'von', 'des', 'du', 'les',
]);
function clueInitials(name) {
  const parts = (name || '').split(/\s+/)
    .filter((w) => w && !REVEAL_ARTICLES.has(w.toLowerCase().replace(/[^a-z']/gi, '')));
  return parts.map((w) => (w[0] || '').toUpperCase() + '.').join(' ').trim();
}

// WHAT blurbs are freeform prose that USUALLY carries a date. Try, in order:
// (a) an N-th-century phrase, (b) a year tagged BC/BCE/AD/CE, (c) a plain
// modern year (1000–2100, with optional "c.", range, or decade "s"). Returns
// null when the blurb is genuinely undatable so the Era clue can be hidden.
function extractEra(item) {
  // Same curated override as clueYears: an explicit `years` field wins over
  // scraping the blurb (some blurbs lead with a restoration or rediscovery
  // date, which made "Era" show the wrong period).
  if (item.years) return String(item.years).trim();
  const blurb = item.blurb;
  if (!blurb) return null;
  let m = blurb.match(/\b\d{1,2}(?:st|nd|rd|th)[ -]centur(?:y|ies)(?:\s+(?:BC|BCE|AD|CE))?/i);
  if (m) return m[0].trim();
  m = blurb.match(/\b(?:AD|CE|BC|BCE)\s+\d{1,4}(?:\s*[–-]\s*\d{1,4})?\b|(?:c\.?\s*)?\b\d{1,4}(?:\s*[–-]\s*\d{1,4})?\s*(?:BC|BCE|AD|CE)\b/i);
  if (m) return m[0].trim();
  const re = /(?:c\.?\s*)?\b(\d{4})(?:s\b|\s*[–-]\s*\d{1,4}s?)?/g;   // fresh: no shared lastIndex
  let mm;
  while ((mm = re.exec(blurb))) {
    const y = parseInt(mm[1], 10);
    if (y >= 1000 && y <= 2100) return mm[0].trim();
  }
  return null;
}

// The two clue slips per MODE. Button A always has content; button B may be
// null (undatable Relic) → its button is hidden for that round.
function clueDefs() {
  const item = round();
  if (MODE === 'who') {
    return {
      a: { label: 'Claim to fame', cost: CLUE_A_COST, value: () => clueOccupation(item) },
      b: { label: 'Lived to/from', cost: CLUE_B_COST, value: () => clueYears(item) },
    };
  }
  return {
    a: { label: 'First letters', cost: CLUE_A_COST, value: () => clueInitials(item.name) },
    b: { label: 'Era', cost: CLUE_B_COST, value: () => extractEra(item) },
  };
}

// A bought clue REPLACES its own button, in the same slot (clue pricing,
// 5 Aug 2026): the yellow clue lands exactly where the control was, and the
// control goes away. No greyed-out button with a duplicate answer below it.
function revealClueInSlot(btn, text) {
  const chip = document.createElement('div');
  chip.className = 'hint-chip clue-slot';
  chip.textContent = text;
  btn.parentNode.insertBefore(chip, btn);
  btn.hidden = true;
  btn.disabled = true;
}
function clearClueSlots() {
  document.querySelectorAll('#rv-controls .clue-slot').forEach((el) => el.remove());
}

// One strikethrough guess chip (same shape as mapgame's) — used live on a
// wrong guess and again when a resumed round rebuilds its chips.
function addGuessChip(text) {
  const chip = document.createElement('span');
  chip.className = 'guess-chip';
  const guessText = document.createElement('span');
  guessText.textContent = text;
  chip.appendChild(guessText);
  const penalty = document.createElement('small');
  penalty.textContent = `-${WRONG_PENALTY}`;
  chip.appendChild(penalty);
  $('#rv-guesses').appendChild(chip);
}

// The rescue closes the shop (Daniel, 5 Aug 2026). Opening "3 choices" drops
// the round to its floor, so from that moment every other clue and every
// further tear costs exactly nothing — the deductions are swallowed. Leaving
// them live would (a) offer prices that cannot be charged, and (b) hand out a
// free full reveal, which turns a three-way gamble into a certainty: the whole
// picture (letters carved on an artefact included, readable at 4× zoom) for
// nought. So the rescue freezes the round where the player paid to leave it:
// clue slips and scraps lock, the torn view and its zoom stay, and the only
// move left is the choice.
function rescueOpen() {
  return !!(S && S.cur && S.cur.mcqOpts);
}

// A price is only true while the whole of it can actually come off. Once the
// floor would swallow part of it, "−25 pts" is a lie — so near the floor the
// control says what it LEAVES instead (clue pricing, 5 Aug 2026). Both halves
// come from worthNow(), never from hard-coded arithmetic.
function priceSpan(cost) {
  const w = worthNow();
  return w - cost < WORTH_FLOOR
    ? `<span class="leaves">· drops to ${Math.max(WORTH_FLOOR, w - cost)}</span>`
    : `<span class="cost">−${cost}</span>`;
}

// Relabel every still-live control for the round's CURRENT worth. Called from
// updateWorth, so a tear / clue / wrong guess repriced everything at once.
function refreshControlLabels() {
  if (!S || !S.cur) return;
  const frozen = rescueOpen();
  for (const [id, key] of [['#rv-clue-a', 'clueA'], ['#rv-clue-b', 'clueB']]) {
    const btn = $(id);
    if (!btn || btn.hidden || S.cur[key]) continue;
    // A frozen slip quotes nothing and is visibly out of service (the house
    // .pill:disabled treatment): a price on a control that can no longer
    // charge it is exactly the lie the pricing rule exists to stop.
    btn.innerHTML = frozen
      ? `<span>${btn.dataset.clueLabel}</span>`
      : `<span>${btn.dataset.clueLabel} ${priceSpan(+btn.dataset.clueCost)}</span>`;
    if (frozen) btn.disabled = true;
  }
  const mcq = $('#rv-mcq');
  // The rescue never quotes its nominal −80: on an untouched round it leaves
  // 20, after any spending it leaves 10, and that is the number that matters.
  if (mcq && !S.cur.mcqOpts) {
    mcq.innerHTML = `<span>3 choices <span class="leaves">· round worth ${Math.max(WORTH_FLOOR, worthNow() - MCQ_COST)}</span></span>`;
  }
}

// Label the two clue buttons for this round's MODE, re-enable them, and hide
// button B when its clue has no content (an undatable Relic).
function setupClues() {
  clearClueSlots();
  const defs = clueDefs();
  const btnA = $('#rv-clue-a');
  btnA.dataset.clueLabel = defs.a.label;
  btnA.dataset.clueCost = defs.a.cost;
  btnA.disabled = false;
  btnA.hidden = false;
  const btnB = $('#rv-clue-b');
  const bVal = defs.b.value();
  btnB.dataset.clueLabel = defs.b.label;
  btnB.dataset.clueCost = defs.b.cost;
  if (bVal == null || bVal === '') {
    btnB.hidden = true;
    btnB.disabled = true;
  } else {
    btnB.disabled = false;
    btnB.hidden = false;
  }
  refreshControlLabels();
}

function buyClue(which) {
  if (!S || !S.cur || !S.cur.open) return;
  if (rescueOpen()) return;   // the rescue closed the shop; the button is dead
  const key = which === 'a' ? 'clueA' : 'clueB';
  if (S.cur[key]) return;
  const def = clueDefs()[which];
  const value = def.value();
  if (value == null || value === '') return;
  S.cur[key] = true;
  S.cur.clueCost = (S.cur.clueCost || 0) + def.cost;
  revealClueInSlot($(which === 'a' ? '#rv-clue-a' : '#rv-clue-b'), `${def.label}: ${value}`);
  updateWorth();
  announce(`${def.label}: ${value}. Worth ${worthNow()} points.`);
  persist();   // P2.1: bought clues survive a quit/reopen
}

// ---------- rng (shared shape with mapgame) ----------
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function makeRng() {
  const p = new URLSearchParams(location.search).get('revealseed');
  return mulberry32(p ? parseInt(p, 10) : (Date.now() & 0xffffffff) ^ 0x9e3779b9);
}
function shuffled(arr, rng) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// ---------- image painting ----------
const dims = {};               // img path -> {w,h,src} | {failed:true}, cached after first load

// The frame shows a square window into the image, covered by scraps. The
// window is `cover`-fit and biased toward the item's focal point so the
// money shot is IN the frame — which scrap hides it is the difficulty.
function paintCover(item) {
  const frame = $('#rv-frame');
  frame.classList.remove('df-duotone');
  frame.style.backgroundColor = '#111';
  frame.style.backgroundSize = 'cover';
  frame.style.backgroundPosition = `${(item.fx * 100).toFixed(1)}% ${(item.fy * 100).toFixed(1)}%`;
  // P5.3a: dims[item.img].src (once resolved by ensureDims/prefetchRounds) is
  // whichever URL actually loaded, w800 or original; before that's known,
  // guess w800 optimistically — the ensureDims callback below repaints once
  // the real answer is in, correcting a wrong guess (e.g. a missing variant).
  const d = dims[item.img];
  frame.style.backgroundImage = `url("${(d && d.src) || w800Url(item.img)}")`;
}

// On reveal the frame drops the square scrap-grid shape and morphs to the
// image's real aspect (CSS transition on #rv-frame animates it). With an exact
// aspect there is no cropping, so `cover` shows the whole picture, no bars.
// Portrait images cap their HEIGHT (~44dvh) so tall pictures don't overrun the
// screen; landscape/square keep the guessing width. Missing dims (image
// failed) fall back to the old `contain` square.
function paintFull(item) {
  const frame = $('#rv-frame');
  frame.style.backgroundPosition = 'center';
  frame.style.backgroundRepeat = 'no-repeat';
  const d = dims[item.img];
  frame.style.backgroundImage = `url("${(d && d.src) || w800Url(item.img)}")`;
  if (d && d.w && d.h) {
    frame.style.aspectRatio = `${d.w} / ${d.h}`;
    frame.style.width = d.h > d.w
      ? `min(80vw, calc(44dvh * ${d.w} / ${d.h}))`
      : 'min(80vw, 40dvh)';
    frame.style.backgroundSize = 'cover';
  } else {
    frame.style.backgroundSize = 'contain';
  }
}

// P3.3: the discreet tap-to-expand photo credit. Only ever called after a
// round resolves (resolveRound) — never during guessing, so the credit can't
// leak an answer via image_author/whatever before the reveal. CC-licensed
// images show the full "Photo: author · licence · Wikimedia Commons" line
// with author and licence linked (image_source_url / image_license_url);
// anything without a licence URL (Public domain, or Commons' own "No
// restrictions" Flickr-Commons tag) has no attribution requirement, so it
// collapses to a plain "<licence> · Wikimedia Commons" — matching what the
// Commons record itself asserts, never a guessed "Public domain" label.
function creditHTML(item) {
  const author = item.image_author || item.attribution || '';
  const licenseLabel = item.image_license || item.license || '';
  const licenseUrl = item.image_license_url || '';
  const sourceUrl = item.image_source_url || '';
  if (!author && !licenseLabel) return '';

  const authorHTML = sourceUrl
    ? `<a href="${sourceUrl}" target="_blank" rel="noopener">${author}</a>` : author;
  const licenseHTML = licenseUrl
    ? `<a href="${licenseUrl}" target="_blank" rel="noopener">${licenseLabel}</a>` : licenseLabel;

  // Every reveal gets the same duotone CSS filter (df-duotone, applied a few
  // lines up in resolveRound) — true of every image at this exact moment
  // regardless of which record it is, so it's safe to state outright rather
  // than rely on a per-record modification note this session never backfills.
  // image_modifications (once populated) can add anything MORE specific
  // (e.g. a real crop) on top of it.
  let line;
  if (licenseUrl && author) {
    line = `Photo: ${authorHTML} · ${licenseHTML} · Wikimedia Commons · duotone`;
    if (item.image_modifications) line += `, ${item.image_modifications}`;
  } else {
    line = `${licenseHTML || 'Wikimedia Commons'} · Wikimedia Commons`;
  }
  const report = `<a class="rv-report-link" href="${daily.reportProblemHref(item.id, S.editionIndex)}">Report a problem</a>`;
  return line + report;
}

function showCredit(item) {
  const btn = $('#rv-credit-btn');
  const panel = $('#rv-credit-panel');
  const html = creditHTML(item);
  if (!html) { btn.hidden = true; panel.hidden = true; return; }
  panel.innerHTML = html;
  panel.hidden = true;
  btn.hidden = false;
  btn.setAttribute('aria-expanded', 'false');
}

function toggleCreditPanel() {
  const btn = $('#rv-credit-btn');
  const panel = $('#rv-credit-panel');
  const open = panel.hidden;
  panel.hidden = !open;
  btn.setAttribute('aria-expanded', String(open));
}

function ensureDims(item, cb) {
  const d = dims[item.img];
  if (d && !d.failed) { cb(); return; }
  // A failed load is remembered (so the round can show its honest offline
  // notice) but never treated as real dims — Retry clears it and reloads.
  loadImgFallback(item.img,
    (img, src) => { dims[item.img] = { w: img.naturalWidth, h: img.naturalHeight, src }; cb(); },
    () => { dims[item.img] = { failed: true }; cb(); });
}

// Honest offline state (owner report 2026-07-15, the aeroplane case): if the
// round's image never arrived, don't deal nine scraps over a blank void —
// cover the frame with a "not downloaded" notice and park the controls.
function setRoundOffline(off) {
  const el = $('#rv-offline');
  if (el) el.hidden = !off;
  if (!off) $('#rv-offline-retry').textContent = 'Retry';
  const cur = S && S.cur;
  const frozen = rescueOpen();   // coming back online must not re-open the shop
  $('#rv-input').disabled = off;
  $('#rv-guess-btn').disabled = off;
  $('#rv-clue-a').disabled = off || frozen || !!(cur && cur.clueA);
  $('#rv-clue-b').disabled = off || frozen || !!(cur && cur.clueB);
  $('#rv-mcq').disabled = off || !!(cur && cur.mcqOpts);
  $('#rv-scraps').style.visibility = off ? 'hidden' : '';
}

// ---------- scraps ----------
// The money scrap is the grid cell holding the focal point (fx/fy map to the
// frame under cover-fit positioning). The round OPENS with the scrap farthest
// from it already torn — the game's tear, on the house — and only scraps
// orthogonally touching an open scrap can be torn next, so the player plots a
// route toward the reveal. Every tear the PLAYER makes is paid.
function moneyScrap(item) {
  const c = Math.min(2, Math.floor(item.fx * 3));
  const r = Math.min(2, Math.floor(item.fy * 3));
  return r * 3 + c;
}
function startScrap(item) {
  const m = moneyScrap(item);
  // Curated override (start-scrap fairness audit, tools/audit_start_scraps.py):
  // the farthest-from-the-money-shot default can land on sky/backdrop; `start`
  // pins the opening scrap to a cell that actually shows part of the subject.
  // A curated start MAY be the money cell itself (owner ruling, 29 Jul 2026):
  // for obscure subjects, opening on the give-away is kinder than a fair-but-
  // hopeless tear path — "it's more satisfying to guess from the single scrap
  // already provided". The old `!== m` guard only protected against accident;
  // curation is not an accident.
  if (Number.isInteger(item.start) && item.start >= 0 && item.start <= 8) {
    return item.start;
  }
  const mr = Math.floor(m / 3), mc = m % 3;
  let best = 0, bd = -1;
  for (const i of [0, 2, 6, 8, 1, 3, 5, 7, 4]) {   // corners first, deterministic
    const d = Math.abs(Math.floor(i / 3) - mr) + Math.abs((i % 3) - mc);
    if (d > bd) { bd = d; best = i; }
  }
  return best;
}
function neighbors(i) {
  const r = Math.floor(i / 3), c = i % 3;
  const out = [];
  if (r > 0) out.push(i - 3);
  if (r < 2) out.push(i + 3);
  if (c > 0) out.push(i - 1);
  if (c < 2) out.push(i + 1);
  return out;
}
function refreshTearable() {
  if (!S || !S.cur) return;
  // Once the rescue is open no scrap is tearable at all: they lock in the same
  // dashed-out state an adjacency-blocked scrap already uses (see rescueOpen).
  const frozen = rescueOpen();
  const torn = new Set(S.cur.torn);
  const open = new Set();
  if (torn.size) {
    for (const t of torn) for (const n of neighbors(t)) if (!torn.has(n)) open.add(n);
  } else {
    for (let i = 0; i < SCRAPS; i++) open.add(i);   // opening tear: anywhere
  }
  document.querySelectorAll('#rv-scraps .df-scrap').forEach((el) => {
    const i = +el.dataset.i;
    const isTorn = torn.has(i);
    const isLocked = !isTorn && (frozen || !open.has(i));
    el.classList.toggle('tearable', !isTorn && !frozen && open.has(i));
    el.classList.toggle('locked', isLocked);
    // a11y: a locked scrap is a real disabled control, not just a dashed
    // border; an already-torn one (invisible — nothing left to tear) leaves
    // the DOM in place but drops out of the tab order.
    el.setAttribute('aria-disabled', String(isLocked));
    if (isTorn) el.setAttribute('tabindex', '-1');
    else el.removeAttribute('tabindex');
  });
}
function worthNow() {
  const cur = S && S.cur;
  if (!cur) return WORTH_START;
  const paidTears = Math.max(0, cur.torn.length - 1);   // the game-opened scrap is free; every player tear is paid
  const clueCost = cur.clueCost || 0;                   // bought clue slips
  return Math.max(WORTH_FLOOR, WORTH_START - TEAR_COST * paidTears - WRONG_PENALTY * cur.wrongs - clueCost);
}

// One label across all three guessing games (clue pricing, 5 Aug 2026):
// Relic's "INK" was a private joke that made the same number look like a
// different currency.
function updateWorth() {
  const el = $('#rv-worth');
  if (!el || !S || !S.cur) return;
  const w = worthNow();
  // The tear price stays up through ordinary play — it is the one cost the
  // player pays without pressing a control, so it has nowhere else to live.
  // Never say "free": the freebie is the scrap the GAME opened, not the
  // player's first tear (owner correction 2026-07-20). Near the floor the
  // nominal −10 stops being true, so it becomes the honest outcome instead.
  let suffix;
  if (w <= WORTH_FLOOR) suffix = ' · <span class="worth-note">minimum</span>';
  else if (rescueOpen()) suffix = '';   // no tears left to price (see rescueOpen)
  else if (w - TEAR_COST < WORTH_FLOOR) {
    suffix = ` · <span class="worth-note">next tear · drops to ${WORTH_FLOOR}</span>`;
  } else suffix = ` · each tear <span class="cost">−${TEAR_COST}</span>`;
  el.innerHTML = `WORTH: <b>${w} PTS</b>${suffix}`;
  flashWorth(el, w);
  refreshControlLabels();
}

// A half-second pale-gold stamp on the number when it actually moves — the
// cause-and-effect cue that replaces permanent hypothetical arithmetic.
// Reduced motion collapses the animation globally (style.css); the live
// region still speaks the new worth.
let lastWorthShown = null;
function flashWorth(el, w) {
  const b = el.querySelector('b');
  if (b && lastWorthShown != null && lastWorthShown !== w) b.classList.add('flash');
  lastWorthShown = w;
}

function buildScraps() {
  const wrap = $('#rv-scraps');
  wrap.innerHTML = '';
  wrap.hidden = false;
  for (let i = 0; i < SCRAPS; i++) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'df-scrap';
    b.dataset.i = i;
    b.setAttribute('aria-label', `Tear scrap ${i + 1}`);
    b.style.transform = `rotate(${((i * 7) % 5) - 2}deg)`;
    b.addEventListener('click', () => tearScrap(i));
    wrap.appendChild(b);
  }
}

// A blocked tap shakes its scrap instead of doing nothing — covers both an
// already-torn scrap (nothing left to tear) and an adjacency-locked one.
// Two more channels ride along, neither of which changes how anything looks
// at rest: (1) prefers-reduced-motion collapses the shake to ~.01s (see the
// global override in style.css) so those users get a held, non-animated
// outline flash instead, timed in JS so that same override can't crush it
// too; (2) a polite live-region announcement (app.js's shared #sr-live) for
// screen readers, who feel a shake even less than reduced-motion users do.
const DENY_REASON_TEXT = {
  torn: 'Already torn.',
  locked: 'Choose a scrap next to an open space.',
  frozen: 'Tearing is closed — pick one of the three.',
};
function denyTap(i, reason) {
  const el = $(`#rv-scraps [data-i="${i}"]`);
  if (el) {
    el.classList.remove('deny');
    void el.offsetWidth;   // restart the animation on repeat taps
    el.classList.add('deny');
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      el.classList.add('deny-static');
      clearTimeout(el._denyStaticTimer);
      el._denyStaticTimer = setTimeout(() => el.classList.remove('deny-static'), 450);
    }
  }
  announce(DENY_REASON_TEXT[reason] || DENY_REASON_TEXT.locked);
}

function tearScrap(i, force) {
  if (!S || !S.cur || !S.cur.open) return;
  const cur = S.cur;
  if (cur.torn.includes(i)) { denyTap(i, 'torn'); return; }
  // The rescue froze the picture where it stood: a further tear would cost
  // nothing, so it is not on offer (see rescueOpen).
  if (!force && rescueOpen()) { denyTap(i, 'frozen'); return; }
  // Adjacency rule: a scrap must touch an open one (force = the game's own
  // opening tear). A blocked tap shakes its head instead of silently doing
  // nothing.
  if (!force && cur.torn.length && !cur.torn.some((t) => neighbors(t).includes(i))) {
    denyTap(i, 'locked');
    return;
  }
  cur.torn.push(i);
  const el = $(`#rv-scraps [data-i="${i}"]`);
  if (el) el.classList.add('torn');
  // force = the round's opening scrap, torn by the game, not the player
  if (!force) sfx.play('tear');
  refreshTearable();
  updateWorth();
  if (!force) {
    announce(`Worth ${worthNow()} points.`);
    persist();   // P2.1: every paid tear is saved the moment it happens
  }
}

// ---------- session ----------
export function renderRevealStart(mode) {
  if (mode) MODE = mode;
  const title = $('#rv-start-title');
  if (title) title.textContent = MODE === 'who' ? 'Face Value' : 'Relic';
  const r = store.getReveal(MODE);
  $('#rv-best').textContent = r.sessions
    ? `Your best: ${r.bestScore} pts · longest streak ${r.bestStreak}`
    : 'First run — good luck';
  const saved = store.getRevealSession(MODE);
  const valid = saved && saved.ids && saved.results;
  $('#rv-resume').hidden = !valid;
  if (valid) {
    $('#rv-resume').textContent = saved.results.length >= saved.ids.length
      ? `See your results (${saved.score} pts)`
      : `Resume — round ${saved.results.length + 1} of ${saved.ids.length} (${saved.score} pts)`;
  }
}

function byId(id) { return DATA.reveal.find((x) => x.id === id); }

// Free sessions keep using store.getRevealSession/setRevealSession/
// clearRevealSession (per MODE) exactly as before. Daily and practice
// sessions use the namespaced generic store so they never collide with a
// free session or with each other.
function modeStore(sessMode, key) {
  if (sessMode === 'free') {
    return {
      get: () => store.getRevealSession(MODE),
      set: (s) => store.setRevealSession(MODE, s),
      clear: () => store.clearRevealSession(MODE),
    };
  }
  return {
    get: () => store.getDailySession(key),
    set: (s) => store.setDailySession(key, s),
    clear: () => store.clearDailySession(key),
  };
}

// Warm the browser/SW cache for the whole session so only round 1 can ever
// wait on the network. Sequential chain: never competes with the image the
// player is actually looking at.
function prefetchRounds() {
  if (!S || !S.rounds) return;
  const queue = S.rounds.slice(S.i);
  const next = () => {
    const item = queue.shift();
    if (!item || !S) return;
    if (dims[item.img]) { next(); return; }
    loadImgFallback(item.img,
      (img, src) => { dims[item.img] = { w: img.naturalWidth, h: img.naturalHeight, src }; next(); },
      () => next());
  };
  next();
}

// P2.1: the current round's spent state (torn scraps, wrong guesses, bought
// clues and their cost) rides along with every save, mirroring mapgame's
// persistSession/pendingCur pattern — so a resumed round is SCORE-IDENTICAL
// to never having left: same open scraps, same worth, same chips.
function persist() {
  S.store.set({
    ids: S.rounds.map((x) => x.id),
    score: S.score, streak: S.streak, bestStreak: S.bestStreak,
    editionIndex: S.editionIndex,
    startedAt: S.startedAt,
    cur: S.cur && S.cur.open
      ? {
          torn: S.cur.torn.slice(), wrongs: S.cur.wrongs,
          clueA: !!S.cur.clueA, clueB: !!S.cur.clueB, clueCost: S.cur.clueCost || 0,
          wrongGuesses: (S.cur.wrongGuesses || []).slice(),
          // Chip ORDER must survive a resume — reshuffling on reload would
          // let a player relaunch until the layout whispers the answer.
          mcqOpts: S.cur.mcqOpts ? S.cur.mcqOpts.slice() : null,
        }
      : null,
    results: S.results.map((r) => ({ id: r.item.id, pts: r.pts, correct: r.correct, mcq: !!r.mcq })),
  });
}

function pickRounds(rng) {
  const items = pool();
  const by = (d) => shuffled(items.filter((x) => x.difficulty === d), rng);
  const want = { easy: 2, medium: 2, hard: 1 };
  const picks = [];
  const pools = { easy: by('easy'), medium: by('medium'), hard: by('hard') };
  for (const d of ['easy', 'medium', 'hard']) picks.push(...pools[d].slice(0, want[d]));
  const used = new Set(picks.map((p) => p.id));
  const rest = shuffled(items.filter((p) => !used.has(p.id)), rng);
  const target = Math.min(ROUNDS, items.length);
  while (picks.length < target && rest.length) picks.push(rest.shift());
  return shuffled(picks, rng).slice(0, target);
}

function startSession() {
  const saved = store.getRevealSession(MODE);
  if (saved && saved.ids && saved.results && saved.results.length >= saved.ids.length) {
    resumeSession();             // a finished-but-unviewed session: bank it first
    return;
  }
  const rng = makeRng();
  S = {
    mode: 'free', dailyKey: null, store: modeStore('free', null),
    rounds: pickRounds(rng), i: 0, score: 0, streak: 0, bestStreak: 0, results: [],
  };
  show('view-reveal');
  startRound();
}

function resumeSession() {
  const saved = store.getRevealSession(MODE);
  if (!saved || !saved.ids || !saved.results) return;
  resumeFrom('free', null, saved);
}

// Shared resume path for free/daily/practice.
function resumeFrom(sessMode, key, saved, fromShare) {
  const st = modeStore(sessMode, key);
  if (saved.ids.some((id) => !byId(id)) || saved.results.some((r) => !byId(r.id))) {
    st.clear();
    if (sessMode === 'free') renderRevealStart();
    return;
  }
  const next = saved.results.length;
  S = {
    mode: sessMode, dailyKey: key, store: st, editionIndex: saved.editionIndex,
    rounds: saved.ids.map(byId),
    i: Math.min(next, saved.ids.length - 1),
    score: saved.score, streak: saved.streak, bestStreak: saved.bestStreak,
    results: saved.results.map((r) => ({ item: byId(r.id), pts: r.pts, correct: r.correct })),
    pendingCur: saved.cur || null,
    startedAt: saved.startedAt || Date.now(),
    fromShare: !!fromShare,
  };
  if (next >= saved.ids.length) { finishSession(); return; }
  show('view-reveal');
  startRound();
}

// ---------- daily / practice entry points ----------
// game key for the daily/practice namespace is 'who' or 'what' (MODE).
function startEdition(sessMode, editionIndex) {
  if (MODE !== 'who' && MODE !== 'what') return;
  const key = sessMode === 'daily' ? daily.dailyKey(MODE, editionIndex) : daily.practiceKey(MODE, editionIndex);
  // P5.2: consumed synchronously (no await between app.js setting it and
  // this read), so it's safe even though the intro overlay can defer begin()
  // behind a user tap — fromShare is closed over either way.
  const fromShare = sessMode === 'daily' && consumeShareLaunch(MODE);
  if (sessMode === 'daily') {
    const entry = store.getDailyEntry(MODE, editionIndex);
    if (entry) { showLockedResult(editionIndex, entry); return; }
  }
  const saved = store.getDailySession(key);
  if (saved && saved.ids && saved.results) {
    if (sessMode === 'daily') track(`resume-${MODE}`);
    resumeFrom(sessMode, key, saved, fromShare);
    return;
  }
  const mode = MODE;   // capture: MODE is stable while the intro overlay is up
  const begin = () => {
    const rounds = daily.getEdition(mode, editionIndex);
    S = {
      mode: sessMode, dailyKey: key, store: modeStore(sessMode, key), editionIndex,
      rounds, i: 0, score: 0, streak: 0, bestStreak: 0, results: [],
      startedAt: Date.now(), fromShare,
    };
    show('view-reveal');
    startRound();
  };
  // First-run intro before a fresh daily only (not resume/practice/locked).
  // Teach-by-doing (P1.5): Face Value skips the up-front rules card entirely —
  // a first-timer tears immediately, the worth line prices the tears in
  // context (see updateWorth — since 5 Aug 2026 that price stays up through
  // ordinary play, so `S.teach` no longer gates it), and the "?" opens the
  // full card on demand. Other games keep their intro. Routing unchanged.
  if (sessMode === 'daily' && mode === 'who') {
    const seenIntro = !!(store.getMisc().introSeen || {}).who;
    if (!seenIntro) {
      store.setMisc({ introSeen: Object.assign({}, store.getMisc().introSeen || {}, { who: true }) });
    }
    begin();
    if (S) S.teach = !seenIntro;
  } else if (sessMode === 'daily') {
    maybeIntro(mode, editionIndex, begin);
  } else {
    begin();
  }
}

// The access guard lives on the entry point itself, not only on the cards
// that call it (spec §4 / CLAUDE.md): a stale card tapped after a midnight
// rollover, or a hand-typed edition, must fail closed here too. app.js's
// launchEdition checks the same rule before it gets this far — this is the
// belt to that pair of braces, because THIS is the function that opens a
// daily, and nothing may open one without passing the window.
export function startRevealDaily(mode, editionIndex) {
  if (!daily.canPlayEdition(editionIndex)) { goHome(); return; }
  MODE = mode;
  startEdition('daily', editionIndex);
}
export function startRevealPractice(mode, editionIndex) { MODE = mode; startEdition('practice', editionIndex); }

// A locked (already-completed) daily: the summary view, read-only. The round
// list is rebuilt from the MANIFEST (daily.getEdition), not from the ledger
// entry — the manifest is the record of what actually aired, while the entry
// only carries what the player scored on it. Points are matched back onto the
// manifest's rounds by id.
function showLockedResult(editionIndex, entry) {
  const scored = new Map((entry.detail || []).map((r) => [r.id, r]));
  const aired = daily.getEdition(MODE, editionIndex);
  const results = aired.map((item) => {
    const r = scored.get(item.id) || {};
    return { item, pts: r.pts || 0, correct: !!r.correct, torn: r.torn || 0, wrongs: r.wrongs || 0 };
  });
  S = {
    mode: 'daily', dailyKey: daily.dailyKey(MODE, editionIndex), store: modeStore('daily', null),
    editionIndex, done: true, locked: true,
    score: entry.score,
    // Re-opening a finished daily is the ONLY place the solution recap shows.
    // A player who has just finished a live run watched every reveal happen;
    // repeating it under their receipt would be noise.
    showSolution: true,
    results: results.length ? results : (entry.detail || []).map((r) => ({
      item: byId(r.id) || { name: '(removed)', kind: MODE === 'who' ? 'portrait' : 'artefact' },
      pts: r.pts, correct: r.correct, torn: r.torn || 0, wrongs: r.wrongs || 0,
    })),
  };
  renderLockedSummary();
  show('view-revealsum');
}

function round() { return S.rounds[S.i]; }

function startRound() {
  const item = round();
  // P2.1: a mid-round save carries the round's spent state back in — same
  // torn scraps, same wrong guesses, same bought clues, so worthNow() lands
  // on exactly the number the player left behind.
  const carried = S.pendingCur;
  S.pendingCur = null;
  S.cur = carried
    ? {
        open: true, torn: (carried.torn || []).slice(), wrongs: carried.wrongs || 0,
        clueCost: carried.clueCost || 0, clueA: !!carried.clueA, clueB: !!carried.clueB,
        wrongGuesses: (carried.wrongGuesses || []).slice(),
        mcqOpts: carried.mcqOpts ? carried.mcqOpts.slice() : null,
      }
    : { open: true, torn: [], wrongs: 0, clueCost: 0, clueA: false, clueB: false, wrongGuesses: [], mcqOpts: null };
  lastWorthShown = null;   // a fresh round's first worth is not a "change"
  $('#rv-progress').textContent = `Round ${S.i + 1} of ${S.rounds.length}`;
  announce(`Round ${S.i + 1} of ${S.rounds.length}.`);
  $('#rv-score').textContent = `${S.score} pts`;
  $('#rv-prompt').hidden = false;
  $('#rv-prompt').textContent = item.kind === 'portrait'
    ? 'Who is this? Tear towards the answer.' : 'What is this? Tear towards the answer.';
  $('#rv-feedback').hidden = true;
  $('#rv-feedback').innerHTML = '';
  $('#rv-wrong-note').hidden = true;
  $('#rv-form').hidden = false;
  $('#rv-controls').hidden = false;
  $('#rv-mcq-chips').hidden = true;
  $('#rv-mcq-chips').innerHTML = '';
  $('#rv-mcq').disabled = false;
  $('#rv-guesses').innerHTML = '';
  $('#rv-input').value = '';
  $('#rv-input').disabled = false;
  $('#rv-guess-btn').disabled = false;
  $('#rv-next').hidden = true;
  $('#rv-badge').hidden = true;
  $('#rv-credit-btn').hidden = true;
  $('#rv-credit-panel').hidden = true;
  $('#rv-credit-panel').innerHTML = '';
  $('#rv-streak').hidden = S.streak < 2;
  if (S.streak >= 2) $('#rv-streak').textContent = `${S.streak} in a row`;
  setupClues();
  // Resumed round: put the bought-clue chips (values re-derive from the item)
  // and the wrong-guess chips back exactly as they were.
  const defs = clueDefs();
  if (S.cur.clueA) revealClueInSlot($('#rv-clue-a'), `${defs.a.label}: ${defs.a.value()}`);
  if (S.cur.clueB) revealClueInSlot($('#rv-clue-b'), `${defs.b.label}: ${defs.b.value()}`);
  if (S.cur.mcqOpts) renderMcq();   // resumed mid-choice: same three, same order
  (S.cur.wrongGuesses || []).forEach((g) => addGuessChip(g));
  // Back to the square scrap window (clears any inline aspect/width the last
  // reveal morphed the frame to).
  const frame = $('#rv-frame');
  frame.style.aspectRatio = '1 / 1';
  frame.style.width = '';
  if (frameZoom) frameZoom.reset();
  paintCover(item);
  buildScraps();
  if (S.cur.torn.length) {
    // Resumed round: the already-torn scraps (opening scrap included) go
    // straight back to open — no sounds, no re-charging.
    for (const t of S.cur.torn) {
      const el = $(`#rv-scraps [data-i="${t}"]`);
      if (el) el.classList.add('torn');
    }
    refreshTearable();
  } else {
    tearScrap(startScrap(item), true);   // the game's opening scrap, placed far from the money shot
  }
  updateWorth();
  setRoundOffline(false);
  ensureDims(item, () => {
    // Only flag the round still on screen (the load is async).
    if (!S || !S.cur || !S.cur.open || round() !== item) return;
    const d = dims[item.img];
    if (d && d.failed) setRoundOffline(true);
    else paintCover(item);   // repaint with the now-resolved src (w800 or fallback)
  });
  prefetchRounds();
  persist();
  if (testHooksEnabled()) {
    window.__CHRONICLE_TEST__ = Object.assign(window.__CHRONICLE_TEST__ || {}, {
      revealRound: { index: S.i, id: item.id, name: item.name, kind: item.kind },
      revealDebug: {
        tear: tearScrap,
        tornCount: () => (S && S.cur ? S.cur.torn.length : 0),
        worth: worthNow,
        // Back-compat shim for the old timed harness: progress p ≈ tearing
        // through the grid. p=0 → no tears, p=1 → all nine scraps torn.
        setProgress: (p) => { for (let k = 0; k < Math.round(p * SCRAPS); k++) tearScrap(k); },
        getP: () => (S && S.cur ? S.cur.torn.length / SCRAPS : null),
      },
    });
  }
}

// The renderer owns the reveal's terminal punctuation, not the data: append
// "." only when the blurb doesn't already end in its own terminal mark ("!"
// and "?" earn their keep — a blurb like "...her 1993 live album Selena
// Live!" must not lose that "!" to a blind appended "."). Data policy (see
// tools/validate_reveal.py) is the mirror image: blurbs must not end in a
// bare "." — this is the layer that supplies it.
const TERMINAL_PUNCT_RE = /[.!?…]['")’”\]]*$/;
function withTerminalPunct(text) {
  const t = (text || '').trim();
  return TERMINAL_PUNCT_RE.test(t) ? t : `${t}.`;
}

// ---------- the ultimate clue: three choices ----------
// The answer plus the item's two curated distractors (tools/build_mcq.py),
// shuffled once per round and frozen into the session so a reload can't
// re-deal. Items without an mcq field (shouldn't happen — build_mcq covers
// every pool) fall back to two same-kind names so the button never breaks.
function mcqOptionsFor(item) {
  let names = (item.mcq || []).slice(0, 2);
  if (names.length < 2) {
    const others = pool().filter((x) => x.id !== item.id && x.name !== item.name
      && x.kind === item.kind && x.difficulty === item.difficulty);
    while (names.length < 2 && others.length) {
      const pick = others.splice(Math.floor(Math.random() * others.length), 1)[0];
      if (!names.includes(pick.name)) names.push(pick.name);
    }
  }
  const opts = [item.name, ...names];
  for (let i = opts.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [opts[i], opts[j]] = [opts[j], opts[i]];
  }
  return opts;
}

function openMcq() {
  if (!S || !S.cur || !S.cur.open || S.cur.mcqOpts) return;
  S.cur.mcqOpts = mcqOptionsFor(round());
  S.cur.clueCost = (S.cur.clueCost || 0) + MCQ_COST;  // priced like a clue slip
  persist();
  if (S.mode === 'daily') track(`mcq-open-${MODE}`);
  renderMcq();
}

function renderMcq() {
  const item = round();
  const wrap = $('#rv-mcq-chips');
  wrap.innerHTML = '';
  S.cur.mcqOpts.forEach((name) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'pill mcq-opt';
    b.textContent = name;
    b.addEventListener('click', () => {
      if (!S || !S.cur || !S.cur.open) return;
      resolveRound(name === item.name, { mcq: true });
    });
    wrap.appendChild(b);
  });
  wrap.hidden = false;
  // Typing is over, and so is spending: the gamble replaces the keyboard AND
  // closes the clue slips and the scraps (see rescueOpen). refreshTearable
  // locks the picture; updateWorth → refreshControlLabels dims the slips and
  // strips the prices they can no longer charge.
  $('#rv-form').hidden = true;
  $('#rv-mcq').disabled = true;
  refreshTearable();
  updateWorth();   // the −80 is already in clueCost: the standard readout tells it straight
  announce(`Three choices: ${S.cur.mcqOpts.join(', ')}. Pick one for ${worthNow()} points.`
    + ' Tearing and clues are closed.');
}

function resolveRound(correct, opts) {
  const item = round();
  if (!S.cur.open) return;
  const fromMcq = !!(opts && opts.mcq);
  S.cur.open = false;
  const wrongs = S.cur.wrongs || 0;
  let pts = 0;
  let bonus = 0;
  if (correct) {
    // A multiple-choice pick pays what the round is still worth — the −80
    // was charged when the choices opened, so no cap is needed here — and
    // leaves the streak untouched (alive, but no ++ and no bonus).
    pts = worthNow();
    if (!fromMcq) {
      S.streak++;
      S.bestStreak = Math.max(S.bestStreak, S.streak);
      if (S.streak >= 2) bonus = 10;
    }
    sfx.play('correct');
  } else {
    S.streak = 0;
  }
  const total = pts + bonus;
  S.results.push({ item, pts: total, correct, torn: S.cur.torn.length, wrongs, mcq: fromMcq });
  if (S.mode === 'daily' && fromMcq) track(`mcq-${MODE}-${correct ? 'win' : 'loss'}`);
  S.score = daily.sessionScore(S.results);   // the 0–100 dial: capped round average
  if (S.mode === 'daily') {
    const hints = (S.cur.clueA ? 1 : 0) + (S.cur.clueB ? 1 : 0);
    track(`round-${MODE}-${roundOutcome(correct, hints, wrongs)}`);
  }
  persist();

  // The reveal: every scrap flies off, the full image shows with the house
  // duotone treatment, and the verdict badge lands on the frame's corner.
  $('#rv-scraps').querySelectorAll('.df-scrap').forEach((el) => el.classList.add('torn'));
  $('#rv-prompt').hidden = true;
  if (frameZoom) frameZoom.reset();   // the frame morphs aspect; start the reveal at 1x
  paintFull(item);
  $('#rv-frame').classList.add('df-duotone');
  const badge = $('#rv-badge');
  badge.className = `df-moment-badge${correct ? '' : ' bad'}`;
  const verdict = correct
    ? CORRECT_VERDICTS[S.i % CORRECT_VERDICTS.length]
    : WRONG_VERDICTS[S.i % WRONG_VERDICTS.length];
  badge.innerHTML = correct
    ? `<b>${verdict}</b><small>+${total} PTS</small>`
    : `<b>${verdict}</b><small>0 PTS</small>`;
  badge.hidden = false;
  $('#rv-worth').innerHTML = '';
  // P2.4: the verdict, spoken — correct answers and reveals alike.
  announce(correct
    ? `${verdict} ${item.name}. Plus ${total} points.`
    : `It was ${item.name}. 0 points.`);

  const fb = $('#rv-feedback');
  fb.className = correct ? 'good' : 'info';
  fb.innerHTML = correct
    ? `<b class="fig">${item.name}</b> — ${withTerminalPunct(item.blurb)} <span class="pts">+${total} pts</span>`
      + (bonus ? ` <small>(includes ${bonus} streak bonus)</small>` : '')
      + (fromMcq ? ' <small>(picked from three)</small>' : '')
    : `It was <b class="fig">${item.name}</b> — ${withTerminalPunct(item.blurb)} <span class="pts">0 pts</span>`;
  fb.hidden = false;
  showCredit(item);

  $('#rv-input').disabled = true;
  $('#rv-guess-btn').disabled = true;
  $('#rv-clue-a').disabled = true;
  $('#rv-clue-b').disabled = true;
  $('#rv-form').hidden = true;
  $('#rv-controls').hidden = true;
  $('#rv-mcq-chips').hidden = true;
  $('#rv-score').textContent = `${S.score} pts`;
  $('#rv-streak').hidden = S.streak < 2;
  if (S.streak >= 2) $('#rv-streak').textContent = `${S.streak} in a row`;
  const last = S.i === S.rounds.length - 1;
  $('#rv-next').textContent = last ? 'See results ›' : 'Next ›';
  $('#rv-next').hidden = false;
  $('#rv-next').scrollIntoView({ block: 'nearest' });
}

function renderLockedSummary() {
  const head = document.querySelector('#view-revealsum [data-receipt-head]');
  if (head) head.textContent = `Yesternerd · ${MODE === 'who' ? 'Face Value' : 'Relic'}`
    + (S.editionIndex != null ? ` · № ${S.editionIndex}` : '');
  $('#rv-sum-total').textContent = S.score;
  setReceiptStamp('view-revealsum', S.score);
  $('#rv-sum-report').href = daily.reportProblemHref(null, S.editionIndex);
  // Bands recalibrated 28 Jul 2026 for the 3-round daily: each round is now
  // a third of the day, so one miss lands near 70 (was ~86 under 5 rounds)
  // and the old 90/75/55/30 ladder read two bands harsher than the same
  // performance did before. Anchors: clean low-tear day ≥ 88; two-of-three
  // with decent play ≥ 60; heavy but real progress ≥ 35; one rescue ≥ 15.
  const remarks = [
    [88, 'A connoisseur of the ages.'],
    [60, 'A sharp eye for history.'],
    [35, 'A good eye — keep looking.'],
    [15, 'The details are coming into focus.'],
    [0, 'Every expert starts by squinting.'],
  ];
  $('#rv-sum-remark').innerHTML = remarks.find((x) => S.score >= x[0])[1];
  const ol = $('#rv-sum-rounds');
  ol.innerHTML = '';
  for (const r2 of S.results) {
    const li = document.createElement('li');
    li.innerHTML = `<span class="sum-name">${r2.item.name}<small>${r2.item.kind}</small></span>`
      + `<span class="sum-pts${r2.pts ? '' : ' zero'}">${r2.pts ? '+' + r2.pts : '0'}</span>`;
    ol.appendChild(li);
  }
  // Daily results are locked: no replay from the summary screen.
  // Share 2.0: dailies only (the issue number is the common reference).
  const isDaily = S.mode === 'daily' && S.editionIndex != null;
  S.share = isDaily ? {
    text: revealShareText(MODE, S.editionIndex, S.results, S.score),
    trackAs: `share-${MODE}`,
  } : null;
  const rvShare = $('#rv-sum-share');
  if (rvShare) rvShare.hidden = !S.share;
  wireTurnThePage('rv-sum-turn', S.editionIndex, isDaily);
  renderSolution();
  wireEncore('rv-sum-encore', MODE, isDaily);
  $('#rv-sum-again').hidden = !!S.locked;
}

// The solution recap under the receipt (Archive v2). One plate per round, in
// manifest order: the fully uncovered image — exactly the reveal the round
// ended on — plus the blurb that came with it, and the same discreet ⓘ credit
// affordance the live reveal carries (locked decision #8).
function renderSolution() {
  const wrap = $('#rv-sum-solution');
  if (!wrap) return;
  if (!S.showSolution || !S.results || !S.results.length) {
    wrap.hidden = true;
    wrap.innerHTML = '';
    return;
  }
  wrap.innerHTML = '<p class="sum-solution-head">The answers</p>'
    + S.results.map((r, i) => {
      const item = r.item || {};
      const credit = creditHTML(item);
      // w800 first, full original on error — the same ladder every other
      // image load in the app uses (app.js loadImgFallback), inlined here
      // because these are declarative <img> tags rather than JS loads.
      const img = item.img
        ? `<span class="sol-figure-wrap"><img class="sol-figure" src="${w800Url(item.img)}"
             alt="${item.name || ''}" loading="lazy"
             onerror="this.onerror=null;this.src='${item.img}'"></span>`
        : '';
      return `<article class="sol-round">
        <span class="sol-pts${r.pts ? '' : ' zero'}">${r.pts ? '+' + r.pts : '0 pts'}</span>
        ${img}
        <div class="sol-body">
          <h3 class="sol-name">${item.name || '(removed)'}</h3>
          ${item.blurb ? `<p class="sol-blurb">${item.blurb}</p>` : ''}
          ${credit ? `<button type="button" class="sol-credit-btn" data-credit="${i}"
              aria-label="Photo credit" aria-expanded="false">ⓘ</button>
            <div class="sol-credit-panel" id="sol-credit-${i}" hidden>${credit}</div>` : ''}
        </div>
      </article>`;
    }).join('');
  wrap.hidden = false;
  wrap.querySelectorAll('[data-credit]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const panel = $(`#sol-credit-${btn.dataset.credit}`);
      if (!panel) return;
      const open = panel.hidden;
      panel.hidden = !open;
      btn.setAttribute('aria-expanded', String(open));
    });
  });
}

function finishSession() {
  if (S.done) { renderLockedSummary(); show('view-revealsum'); return; }
  S.done = true;
  sfx.play('stamp');

  if (S.mode === 'free') {
    const r = store.getReveal(MODE);
    r.sessions = (r.sessions || 0) + 1;
    r.bestScore = Math.max(r.bestScore || 0, S.score);
    r.bestStreak = Math.max(r.bestStreak || 0, S.bestStreak);
    store.setReveal(MODE, r);
  } else if (S.mode === 'daily') {
    daily.recordDailyCompletion(MODE, S.editionIndex, {
      score: S.score,
      // torn/wrongs feed the Share 2.0 emoji row (🟩 clean, 🟨 laboured, 🟥 lost)
      detail: S.results.map((r3) => ({ id: r3.item.id, pts: r3.pts, correct: r3.correct, torn: r3.torn, wrongs: r3.wrongs })),
    });
    track(`dur-${MODE}-${durationBucket(Date.now() - (S.startedAt || Date.now()))}`);
    S.locked = true;
  }
  // practice mode: no ledger, no best-score update — replayable, no trace.
  // The in-progress session is dropped LAST, once the result is safely on the
  // record. Clearing first meant that anything throwing on the way to the
  // ledger took the played session down with it: nothing to resume, nothing
  // recorded, a finished daily simply gone.
  S.store.clear();
  refreshHomeStats();

  renderLockedSummary();
  announce(`Run complete. Final score ${S.score} points.`);
  if (testHooksEnabled()) {
    window.__CHRONICLE_TEST__ = Object.assign(window.__CHRONICLE_TEST__ || {}, {
      revealSession: { score: S.score, results: S.results.map((r3) => ({ id: r3.item.id, pts: r3.pts, correct: r3.correct })) },
    });
  }
  show('view-revealsum');
  // "A game finished" for the install flow (js/install.js listens): a daily —
  // free play does not count. Encore is itself a daily now (Archive v2), so it
  // arrives here through the same branch. Announced rather than called so this
  // file keeps no dependency on the install flow at all.
  if (S.mode === 'daily') {
    document.dispatchEvent(new CustomEvent('gamefinished',
      { detail: { game: MODE, daily: true } }));
  }
}

// ---------- init ----------
export function initRevealGame() {
  // Two separate pools — 'who' (portraits) / 'what' (artefacts) — so a
  // distinctive core token is only unique relative to items the player could
  // actually be shown in that mode, not the whole reveal corpus.
  registerPool('who', DATA.reveal.filter((x) => x.kind === 'portrait'));
  registerPool('what', DATA.reveal.filter((x) => x.kind !== 'portrait'));

  // Pinch/double-tap zoom on the frame: revealed slivers are inspectable
  // mid-round (image and scrap grid scale together, so the torn windows stay
  // truthful) and the final reveal is zoomable too. The wrap clips while
  // zoomed so the scaled frame never rides over the guess form.
  frameZoom = attachPinchZoom($('#rv-frame'), {
    maxScale: 4,
    onZoomChange: (z) => $('#rv-frame-wrap').classList.toggle('pz-active', z > 1),
  });

  $('#rv-start').addEventListener('click', startSession);
  $('#rv-resume').addEventListener('click', resumeSession);
  $('#rv-help').addEventListener('click', () => openIntroHelp(MODE));
  $('#rv-credit-btn').addEventListener('click', toggleCreditPanel);

  $('#rv-form').addEventListener('submit', (e) => {
    e.preventDefault();
    if (!S || !S.cur || !S.cur.open) return;
    const guess = $('#rv-input').value.trim();
    if (!guess) return;
    // First guess in this game, ever: ask once before spending anything.
    if (!confirmFirstGuess(MODE, WRONG_PENALTY, () => $('#rv-form')
        .dispatchEvent(new Event('submit', { cancelable: true })))) return;
    if (S.fromShare) { S.fromShare = false; track(`answer-from-share-${MODE}`); }
    if (isMatch(guess, round(), MODE)) {
      resolveRound(true);
    } else {
      // A wrong guess docks the round's worth (see worthNow) — guessing blind
      // is a real gamble, not a free spin.
      S.cur.wrongs = (S.cur.wrongs || 0) + 1;
      S.cur.wrongGuesses = S.cur.wrongGuesses || [];
      S.cur.wrongGuesses.push(guess);
      persist();   // P2.1: wrong guesses (and their cost) survive a quit/reopen
      addGuessChip(guess);
      updateWorth();
      // P1.5: announce every wrong guess politely; show the explicit line
      // once — the first wrong guess anywhere (teachWrongGuess one-shots it).
      const wrongText = MODE === 'who' ? `Not them — −${WRONG_PENALTY}` : `Not that — −${WRONG_PENALTY}`;
      teachWrongGuess('rv-wrong-note', wrongText,
        `${wrongText}. Worth ${worthNow()} points.`);
      const inp = $('#rv-input');
      inp.value = '';
      inp.classList.remove('shake');
      void inp.offsetWidth;
      inp.classList.add('shake');
      inp.focus();
    }
  });

  $('#rv-clue-a').addEventListener('click', () => buyClue('a'));
  $('#rv-clue-b').addEventListener('click', () => buyClue('b'));
  $('#rv-mcq').addEventListener('click', openMcq);

  $('#rv-offline-retry').addEventListener('click', () => {
    if (!S || !S.cur || !S.cur.open) return;
    const item = round();
    const btn = $('#rv-offline-retry');
    btn.disabled = true;
    delete dims[item.img];
    ensureDims(item, () => {
      btn.disabled = false;
      if (!S || !S.cur || !S.cur.open || round() !== item) return;
      const d = dims[item.img];
      if (d && !d.failed) {
        paintCover(item);
        setRoundOffline(false);
      } else {
        btn.textContent = 'Still offline — retry';
      }
    });
  });

  $('#rv-next').addEventListener('click', () => {
    if (S.i === S.rounds.length - 1) { finishSession(); return; }
    S.i++;
    startRound();
  });

  $('#rv-quit').addEventListener('click', () => {
    // Header back arrow: leave the session, same as every other game's back
    // button — it must not discard progress. The session is persisted
    // continuously (persist runs after every tear/clue/guess/round — P2.1),
    // so just make sure the current state is saved, then go. Reopening
    // resumes exactly here: same scraps, same clues, same worth.
    if (S && !S.done) persist();
    S = null;
    back();
  });

  const rvShareBtn = $('#rv-sum-share');
  if (rvShareBtn) {
    rvShareBtn.addEventListener('click', async () => {
      if (!S || !S.share) return;
      const out = await shareResult(S.share);
      flashShareButton(rvShareBtn, out, 'Share the tear-up');
    });
  }
  $('#rv-sum-back').addEventListener('click', goHome);
  $('#rv-sum-again').addEventListener('click', () => { back(); startSession(); });
  $('#rv-sum-home').addEventListener('click', goHome);
}
