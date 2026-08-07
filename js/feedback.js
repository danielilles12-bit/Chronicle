// Letters to the Editor — the player-feedback invitation.
// Approved by Daniel 5 Aug 2026 (design-reviews/install-flow-rulings.md,
// "FEEDBACK PLATE"); the thinking is design-reviews/feedback-plan.md.
//
// The principle: feedback is furniture, not an interruption. It lives where
// the player has STOPPED playing — the foot of Home, the day-done screen,
// the record book, the footer — never on a play screen, and nothing here
// ever has to be dismissed.
//
// Four surfaces wired here (About has its own inline copy of the link):
//   - #letters-plate  the standing letters column at the foot of Home,
//                     hidden until the player's first ever finished daily —
//                     the ONE condition in the whole feature; no timers, no
//                     counters, no nag state, and it never hides again.
//   - #dd-letters     the Complaints Dept stamp card on the day-done screen,
//                     copy per face (celebration vs obituary).
//   - #legacy-write   the coupon row at the foot of Your Legacy.
//   - #foot-write     the one word in the Home footer.
//
// What travels with a letter: the app version and a coarse device family
// (e.g. "v182 · iPhone"), pre-filled into the form's version field so a bug
// report can actually be traced to a build. Nothing else — no scores, no
// answers, no identifiers. GoatCounter records the TAP only; it can never
// see whether the form was submitted.
import { track } from './track.js';
import * as store from './storage.js';
import * as daily from './daily.js';

// The live Google Form (Daniel's account). The one entry id is the form's
// "App version" field — change the form and this pair must change together.
const FORM_URL = 'https://docs.google.com/forms/d/e/1FAIpQLScsbY9qiaomY00CABsQqPXztvjqvTy_hO4jIa9WorckJdcOUQ/viewform';
const ENTRY_VERSION = 'entry.2050964733';
const EDITOR_EMAIL = 'daniel.illes12@gmail.com';

let build = '';   // set by initFeedback — js/app.js owns the BUILD constant

// Coarse device family only — enough to reproduce a layout bug, never enough
// to identify anyone. Order matters: iPadOS masquerades as MacIntel (same
// check as app.js), and CrOS says "Linux" too.
function deviceHint() {
  const ua = navigator.userAgent || '';
  if (/iPhone|iPod/.test(ua)) return 'iPhone';
  if (/iPad/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)) return 'iPad';
  if (/Android/.test(ua)) return 'Android';
  if (/CrOS/.test(ua)) return 'Chromebook';
  if (/Mac/.test(ua)) return 'Mac';
  if (/Windows/.test(ua)) return 'Windows';
  if (/Linux/.test(ua)) return 'Linux';
  return 'Other';
}

function versionLine() {
  return `${build} · ${deviceHint()}`;
}

export function feedbackUrl() {
  return `${FORM_URL}?usp=pp_url&${ENTRY_VERSION}=${encodeURIComponent(versionLine())}`;
}

// The offline fallback: the form needs a network, the app doesn't. Subject
// carries build + surface, body seeds the same device line the form gets.
function mailtoUrl(where) {
  const subject = `Yesternerd letter (${build} · ${where})`;
  return `mailto:${EDITOR_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(versionLine())}`;
}

const offline = () => navigator.onLine === false;

// Same reading of the ledger as app.js's stranger gate: "has this player
// ever finished a daily" — any game, any edition. (Kept as its own three
// lines rather than imported: app.js imports this module, not the reverse.)
function hasAnyDailyCompletion() {
  const entries = store.getDailyLedger().entries || {};
  return daily.GAMES.some((g) => entries[g] && Object.keys(entries[g]).length > 0);
}

// One wiring shape for every surface: href decided by connectivity (form
// online, mailto offline — an <a> so the installed PWA opens the form in its
// in-app browser and the player can swipe straight back). `whereFn` is read
// at tap time because the day-done card's surface depends on which face the
// screen is wearing.
function wireSurface(el, whereFn, onPaint) {
  if (!el) return;
  const paint = () => {
    if (offline()) {
      el.href = mailtoUrl(whereFn());
      el.removeAttribute('target');
      el.removeAttribute('rel');
    } else {
      el.href = feedbackUrl();
      el.setAttribute('target', '_blank');
      el.setAttribute('rel', 'noopener');
    }
    if (onPaint) onPaint(offline());
  };
  el.addEventListener('click', () => {
    track(offline() ? 'feedback-mailto' : `feedback-${whereFn()}`);
  });
  window.addEventListener('online', paint);
  window.addEventListener('offline', paint);
  paint();
}

// The plate's cyan definitive stamp is franked live: denomination = today's
// issue number, postmark = the actual current date. Repainted on every Home
// visit so a session left open across midnight keeps the stamp honest.
function paintPlate() {
  const plate = document.getElementById('letters-plate');
  if (!plate) return;
  plate.hidden = !hasAnyDailyCompletion();
  const no = document.getElementById('lt-stamp-no');
  if (no) no.textContent = `№ ${Math.max(0, daily.todayIndex())}`;
  const pm = document.getElementById('lt-postmark-date');
  if (pm) pm.textContent = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
}

// The day-done stamp card, one per face. "Tell us where it hurts" is
// reserved for THIS stamp (Daniel, 5 Aug 2026) — it must not appear on the
// Home plate.
const DD_COPY = {
  fullhouse: { head: 'Tell us where it hurts', line: 'The editor reads every one →' },
  obituary: { head: 'Any last words?', line: 'Tell the editor what killed it →' },
};

function ddFace() {
  const v = document.getElementById('view-daydone');
  return v && v.classList.contains('obituary') ? 'obituary' : 'fullhouse';
}

function paintDayDone() {
  const c = DD_COPY[ddFace()];
  const head = document.getElementById('dd-letters-head');
  const line = document.getElementById('dd-letters-line');
  if (head) head.textContent = c.head;
  if (line) line.textContent = c.line;
}

export function initFeedback(appBuild) {
  build = appBuild;

  const plateBtn = document.getElementById('lt-btn');
  wireSurface(plateBtn, () => 'home', (off) => {
    plateBtn.textContent = off ? 'Email the editor →' : 'Write to the editor →';
    const note = document.getElementById('lt-offline');
    if (note) note.hidden = !off;
  });
  wireSurface(document.getElementById('dd-letters'), ddFace);
  wireSurface(document.getElementById('legacy-write'), () => 'legacy');
  wireSurface(document.getElementById('foot-write'), () => 'footer');

  paintPlate();
  paintDayDone();
  document.addEventListener('viewchange', (e) => {
    if (e.detail === 'view-home') paintPlate();
    if (e.detail === 'view-daydone') paintDayDone();
  });
}
