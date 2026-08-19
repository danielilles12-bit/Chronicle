// "Save it as an app" — the Add to Home Screen flow (Daniel's rulings, 5 Aug
// 2026; plan signed off the same day). This replaces the old corner tip, whose
// one instruction ("tap Share in the bar below") was wrong on every iPhone
// shipped this year.
//
// WHY IT IS BUILT LIKE THIS
// The install ask is the app's most important long-term conversion moment: an
// installed home-screen app is the difference between a habit and a tab. So
// the ask is a whole screen, not a corner box, and it TEACHES the exact dance
// on the browser the player is actually holding.
//
// THE BRANCHES (detection order matters — first match wins)
//   installed    display-mode: standalone / navigator.standalone. Show nothing,
//                ever. Fire install-confirmed once: the only honest success
//                signal we have.
//   webview      Instagram / Facebook / TikTok / other in-app browsers, by UA
//                token. Installing is IMPOSSIBLE in there, so these get the
//                escape page (Screen B) instead of the install page.
//   native       A captured beforeinstallprompt (Chrome/Samsung on Android):
//                the browser lets us open the real OS install dialog, so the
//                screen carries one giant button and NO instructions at all.
//   chrome-ios   Chrome on iPhone. Its own branch because of the trap Daniel
//                found: the ⋯ bottom-right leads somewhere wrong; the door is
//                the Share icon TOP-RIGHT, next to the address bar.
//   safari       iOS Safari (and any other plain WebKit shell): Share, then
//                the [+] Add to Home Screen row. Copy serves BOTH the bottom-
//                bar layout (Share visible) and iOS 26's Compact default
//                (Share behind •••) — no page can detect which one you have.
//   generic      Everything else. Hardcodes no menu label, because Chrome's
//                own docs disagree with each other about what it says.
//
// NO POINTING ARROWS (Daniel's ruling). A page cannot know where the browser
// put its own chrome, and an arrow at empty space is worse than no arrow. The
// teaching is done with DRAWN REPLICAS of the real buttons, rendered LARGER
// than the words around them, so the eye lands on the button first.
//
// THE TIMING (plan §4)
//   - a "completed game" is any finished daily, any of the four.
//   - Screen A: at the end of game 2. Declined → a quiet strip at the top of
//     Home ("Save Yesternerd as an app — Show me how ›"). Strip × → one last
//     Screen A the day a streak reaches 7, then silence forever.
//   - Screen B: at the end of game 1 in a webview (catch people before the
//     social app swallows them), at most twice.
//
// State lives in misc (device-local, never carried between devices by
// carry.js: a fresh browser has not been asked yet). Keys avoid the product
// name — locked decision #7.
import * as store from './storage.js';
import { track } from './track.js';

// Where the link points when we hand it to the clipboard. Absolute and
// hardcoded on purpose: the whole point of the escape page is to move the
// player OUT of the in-app browser, and location.origin inside one of those
// can carry an app's own proxy host.
const HOME_URL = 'https://yesternerd.app/';

const UA = navigator.userAgent || '';

// ---------------------------------------------------------------------------
// detection
// ---------------------------------------------------------------------------
// Standalone FIRST, before anything else: an installed app must never be
// pitched an install. navigator.standalone is iOS's own flag (Safari's
// display-mode media query lies in some iOS versions), the media query covers
// Android and desktop.
export function isStandalone() {
  return navigator.standalone === true
    || (window.matchMedia && matchMedia('(display-mode: standalone)').matches);
}

const isIOS = () => /iP(hone|ad|od)/.test(UA)
  || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

// In-app browsers, by the tokens the fact-check found reliable. Named apps get
// confident copy; everything else gets the generic variant, which never claims
// to know what the menu says.
function webviewApp() {
  if (/Instagram/i.test(UA)) return 'instagram';
  if (/FBAN|FBAV|FB_IAB|FB4A|FBIOS/i.test(UA)) return 'facebook';
  if (/musical_ly|Bytedance|TikTok/i.test(UA)) return 'tiktok';
  // Less certain shells (WhatsApp moved to Meta's own browser in Nov 2025 and
  // its token is shaky) — enough to know it IS a webview, never enough to name
  // it in the copy.
  if (/WhatsApp|Snapchat|\bLine\/|MicroMessenger|LinkedInApp|Pinterest|Twitter/i.test(UA)) return 'other';
  return null;
}

// The stashed beforeinstallprompt event. Captured at module load (below) so a
// prompt fired during boot is never missed.
let deferredPrompt = null;

export function branch() {
  if (isStandalone()) return 'installed';
  if (webviewApp()) return 'webview';
  if (deferredPrompt) return 'native';
  if (isIOS()) {
    if (/CriOS/.test(UA)) return 'chrome-ios';
    // Firefox/Edge/Opera on iOS cannot add to the home screen at all, so they
    // must not be taught Safari's dance. They fall through to the branch that
    // promises nothing specific.
    if (/FxiOS|EdgiOS|OPiOS/.test(UA)) return 'generic';
    return 'safari';
  }
  return 'generic';
}

// ---------------------------------------------------------------------------
// replica glyphs — drawn from Daniel's phone screenshots (5 Aug 07:20)
// ---------------------------------------------------------------------------
// Every one is ≥40px tall: the ruling is that the button is bigger than the
// words, because the player is hunting a shape, not reading a sentence.
const GLYPH = {
  // iOS Share: a box open at the top with an arrow rising out of it.
  share: `<svg class="install-glyph" width="32" height="42" viewBox="0 0 32 42" fill="none"
      stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"
      aria-hidden="true" focusable="false">
    <path d="M16 3.5V25"/><path d="M8.5 11 16 3.5 23.5 11"/>
    <path d="M10 15H3.5v23.5h25V15H22"/></svg>`,
  // Safari's "More" capsule (iOS 26's Compact layout hides Share behind it).
  dotsPill: `<svg class="install-glyph" width="58" height="40" viewBox="0 0 58 40"
      aria-hidden="true" focusable="false">
    <rect x="1.4" y="1.4" width="55.2" height="37.2" rx="18.6" fill="none"
      stroke="currentColor" stroke-width="2.6"/>
    <circle cx="17" cy="20" r="3.1" fill="currentColor"/>
    <circle cx="29" cy="20" r="3.1" fill="currentColor"/>
    <circle cx="41" cy="20" r="3.1" fill="currentColor"/></svg>`,
  // Instagram's ⋯ is a bare glyph in the corner, no button plate around it.
  dotsBare: `<svg class="install-glyph" width="46" height="40" viewBox="0 0 46 40"
      aria-hidden="true" focusable="false">
    <circle cx="8" cy="20" r="4" fill="currentColor"/>
    <circle cx="23" cy="20" r="4" fill="currentColor"/>
    <circle cx="38" cy="20" r="4" fill="currentColor"/></svg>`,
  // Chrome's ⋮ menu.
  dotsVert: `<svg class="install-glyph" width="24" height="42" viewBox="0 0 24 42"
      aria-hidden="true" focusable="false">
    <circle cx="12" cy="8" r="3.4" fill="currentColor"/>
    <circle cx="12" cy="21" r="3.4" fill="currentColor"/>
    <circle cx="12" cy="34" r="3.4" fill="currentColor"/></svg>`,
  // The share-sheet row's leading icon: a rounded box with a plus in it.
  plusBox: `<svg class="install-glyph install-glyph-row" width="40" height="40" viewBox="0 0 40 40"
      aria-hidden="true" focusable="false">
    <rect x="2" y="2" width="36" height="36" rx="9" fill="none" stroke="currentColor" stroke-width="2.6"/>
    <path d="M20 11.5v17M11.5 20h17" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/></svg>`,
  // "Open in external browser": a square with the arrow leaving it through the
  // top-right corner (Daniel's description, confirmed on his screenshot).
  external: `<svg class="install-glyph install-glyph-row" width="40" height="40" viewBox="0 0 40 40" fill="none"
      stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"
      aria-hidden="true" focusable="false">
    <path d="M23 7H10a3 3 0 0 0-3 3v20a3 3 0 0 0 3 3h20a3 3 0 0 0 3-3V17"/>
    <path d="M18.5 21.5 33 7"/><path d="M24 7h9v9"/></svg>`,
};

// A replica row is a CUTOUT, not a control (19 Aug 2026, the Emma report —
// second player to tap the drawing and conclude the app was broken). A
// faithful copy of a tappable row invites the tap, so the copy now wears
// tape strips, a small caption and a tilt: scrapbook language, "this is a
// picture". And because people will tap it anyway, the tap answers — see
// wireScreen — instead of the silence that reads as breakage.
const cutout = (rowHTML) => `
  <div class="install-cutout">
    <span class="install-tape install-tape-l" aria-hidden="true"></span>
    <span class="install-tape install-tape-r" aria-hidden="true"></span>
    ${rowHTML}
    <span class="install-cutout-cap">what it looks like</span>
    <span class="install-cutout-note" hidden>Just a picture — find the real one on your browser’s own bar.</span>
  </div>`;

// A share-sheet row, drawn as the phone draws it: ICON LEFT, label right
// (Daniel's screenshots settled this — the stale iOS-13-era sources had it
// backwards).
const sheetRow = (glyph, label) =>
  cutout(`<div class="install-row">${glyph}<span>${label}</span></div>`);

// An in-app browser's menu row: iOS context menus put the label first and the
// icon on the trailing edge, which is how Instagram's own menu reads.
const menuRow = (label, glyph) =>
  cutout(`<div class="install-row install-row-menu"><span>${label}</span>${glyph}</div>`);

const step = (n, doHTML, extraHTML) => `
  <div class="install-step">
    <div class="install-num">${n}</div>
    <div class="install-step-body">
      <div class="install-do">${doHTML}</div>
      ${extraHTML || ''}
    </div>
  </div>`;

// ---------------------------------------------------------------------------
// the screens
// ---------------------------------------------------------------------------
// Every word below is Daniel's, verbatim from the signed-off plan. The lede is
// the LOCKED body copy: universal and vague-but-true about the risk, because
// the seven-day rule is Safari-only and a per-browser claim would be a lie
// somewhere.
const LEDE = 'Once you save it as an app, tomorrow’s games are one tap away. '
  + 'And a streak that lives in a browser can die in a browser — on your home '
  + 'screen, it’s safe for good.';
const HEADLINE = 'Save Yesternerd as an app on your home screen';

// Screen A, per branch: the steps between the promise and the buttons.
function stepsFor(kind) {
  if (kind === 'native') {
    // Android's happy path needs no lesson: one button opens the real OS
    // dialog. Browser name only where it is trivially detectable (the ruling).
    const chrome = /Chrome/.test(UA) && !/SamsungBrowser|EdgA|OPR/.test(UA);
    return `
      <div class="install-cta-wrap">
        <button type="button" class="install-cta" id="install-now">Save it now</button>
        <p class="install-note install-note-mid">${chrome ? 'Chrome' : 'Your browser'} will ask you to confirm.<br>
          Nothing to download, nothing to sign up for.</p>
      </div>`;
  }
  if (kind === 'chrome-ios') {
    return `
      ${step(1, `Tap Share ${GLYPH.share}`,
    `<p class="install-note">Top right, next to the address bar.
         <b>Not the ${GLYPH.dotsBare} at the bottom.</b></p>`)}
      ${step(2, 'Then pick this',
    `${sheetRow(GLYPH.plusBox, 'Add to Home Screen')}
       <p class="install-note install-note-step">Tap <b>View More</b> if you don’t see it,
         then <b>Add to Home Screen</b>.</p>`)}`;
  }
  if (kind === 'safari') {
    return `
      ${step(1, `Tap Share ${GLYPH.share}`,
    `<p class="install-note">It’s in the bar by the address.
         Can’t see it? It’s behind ${GLYPH.dotsPill}</p>`)}
      ${step(2, 'Then pick this',
    `${sheetRow(GLYPH.plusBox, 'Add to Home Screen')}
       <p class="install-note install-note-step">Tap <b>View More</b> if you don’t see it,
         then <b>Add to Home Screen</b>.</p>`)}`;
  }
  // generic: name no menu label — Chrome's own documentation disagrees with
  // itself, and since Chrome 138 the menu may sit at the bottom instead.
  return `
    ${step(1, `Tap the ${GLYPH.dotsVert} menu`, '<p class="install-note">It sits next to the address bar.</p>')}
    ${step(2, 'Then look for',
    `${menuRow('Install app', GLYPH.plusBox)}
     <p class="install-note">Or <b>Add to Home screen</b> — browsers word it differently.</p>`)}`;
}

function screenAHTML(kind) {
  return `
    <div class="install-head">
      <div class="install-head-top">
        <span class="install-kicker">${kind === 'native' ? 'One tap' : 'One-time setup'}</span>
        <!-- The icon they are about to get, drawn as iOS draws icons: rounded
             squircle, soft drop shadow, NO zine ink border — the screen's whole
             argument is "this becomes an app" (Daniel, 5 Aug 2026). -->
        <img class="install-appicon" src="icons/icon-512.png" alt="" aria-hidden="true">
      </div>
      <img class="install-wordmark" src="assets/brand/yesternerd-wordmark-primary-v2.png" alt="Yesternerd">
      <h2 class="install-headline" id="install-headline">${HEADLINE}</h2>
      <p class="install-lede">${LEDE}</p>
    </div>
    <div class="install-steps">${stepsFor(kind)}</div>
    <div class="install-foot">
      ${kind === 'native' ? '' : '<button type="button" class="pill primary big" id="install-saved">I’ve saved it ›</button>'}
      <button type="button" class="install-later" id="install-later">Maybe later</button>
    </div>`;
}

// Screen B — the escape page. Named apps get their own name in the headline;
// anything less certain says "this in-app browser" and claims nothing else.
const APP_NAMES = { instagram: 'Instagram', facebook: 'Facebook', tiktok: 'TikTok' };

function screenBHTML(app) {
  const name = APP_NAMES[app];
  const headline = name ? `${name} can’t keep apps.` : 'This in-app browser can’t keep apps.';
  const inside = name ? `${name}’s browser` : 'this in-app browser';
  // Only Instagram's menu is verified word for word (Daniel's screenshot), so
  // only Instagram gets a verbatim label and a corner named with confidence.
  const where = app === 'instagram' ? 'It’s at the top right of this screen.'
    : 'It’s in the corner of this screen.';
  const pick = app === 'instagram'
    ? `${menuRow('Open in external browser', GLYPH.external)}`
    : `${menuRow('Open in browser', GLYPH.external)}
       <p class="install-note">The wording varies — it may say <b>Open in Safari</b> or <b>Open in Chrome</b>.</p>`;
  return `
    <div class="install-head">
      <div class="install-head-top">
        <span class="install-kicker install-kicker-warn">Wrong browser</span>
      </div>
      <h2 class="install-headline" id="install-headline">${headline}</h2>
      <p class="install-lede">You just played inside ${inside} — it can’t save Yesternerd to
        your home screen, and it won’t protect your streak. One tap fixes that.</p>
    </div>
    <div class="install-steps">
      ${step(1, `Tap ${GLYPH.dotsBare}`, `<p class="install-note">${where}</p>`)}
      ${step(2, 'Then pick this', pick)}
    </div>
    <div class="install-foot">
      <p class="install-or"><span>or</span></p>
      <button type="button" class="pill primary big" id="install-copy">Copy the link</button>
      <p class="install-note install-note-mid">then paste it in Safari or Chrome.</p>
      <input type="text" id="install-url" class="install-url" readonly hidden value="${HOME_URL}"
        aria-label="Yesternerd’s web address">
    </div>`;
}

// ---------------------------------------------------------------------------
// showing and dismissing
// ---------------------------------------------------------------------------
const $ = (sel) => document.querySelector(sel);
let openKind = null;        // which screen is on screen right now (null = none)
let openReason = null;      // 'offer' | 'strip' | 'final' | 'qa'

function screenEl() { return $('#install-screen'); }

function paint(html, kind, reason) {
  const ov = screenEl();
  if (!ov) return false;
  const body = $('#install-body');
  if (!body) return false;
  body.innerHTML = html;
  ov.hidden = false;
  // The overlay can be opened from the bottom of a long summary; the way back
  // must be "reachable without scrolling" (the navigation contract), so the
  // screen always opens at its own top.
  ov.scrollTop = 0;
  openKind = kind;
  openReason = reason;
  wireScreen();
  const back = $('#install-back');
  if (back) back.focus({ preventScroll: true });
  return true;
}

function closeScreen() {
  const ov = screenEl();
  if (ov) ov.hidden = true;
  openKind = null;
  openReason = null;
}

// A dismissal that is not "I've saved it": both the ‹ chip and "Maybe later"
// mean the same thing to the state machine — this player said no for now.
function decline() {
  if (openReason === 'qa') { closeScreen(); return; }
  // Closing an escape screen the player opened from the Home banner is not
  // an install "maybe later" — they were never asked to install anything, so
  // it earns no strip and no install-later beacon. Just back to Home.
  if (openReason === 'banner') { closeScreen(); return; }
  track('install-later');
  // Earn the strip only on the first ask. After the strip has been killed with
  // its ×, nothing may bring it back — the final streak-7 offer is the last
  // word (plan §4).
  if (!store.getMisc().installStripGone) store.setMisc({ installLater: true });
  closeScreen();
  refreshStrip();
}

function claimSaved() {
  track('install-saved-claim');
  // Believed, but not trusted: the real confirmation is the first launch that
  // reports display-mode standalone (install-confirmed). Either way this
  // device stops being asked.
  store.setMisc({ installSaved: true, installLater: false });
  closeScreen();
  refreshStrip();
}

async function copyLink() {
  const btn = $('#install-copy');
  const field = $('#install-url');
  let ok = false;
  try {
    await navigator.clipboard.writeText(HOME_URL);
    ok = true;
  } catch (e) {
    // No clipboard permission (in-app browsers often withhold it): show the
    // address so a long-press → Copy still gets them out. Same fallback shape
    // as the carry tool.
    if (field) {
      field.hidden = false;
      field.focus();
      field.select();
    }
  }
  if (btn) {
    const was = btn.textContent;
    btn.textContent = ok ? 'Copied' : 'Select it and copy';
    setTimeout(() => { btn.textContent = was; }, 1800);
  }
  if (ok) track('webview-copylink');
}

function nativeInstall() {
  const ev = deferredPrompt;
  if (!ev) { closeScreen(); return; }   // QA preview, or a prompt already spent
  deferredPrompt = null;
  const p = ev.prompt();
  if (p && p.catch) p.catch(() => {});
  Promise.resolve(ev.userChoice).then((c) => {
    if (c && c.outcome === 'accepted') {
      track('install-accepted');
      store.setMisc({ installSaved: true, installLater: false });
      closeScreen();
      refreshStrip();
    } else {
      track('install-declined');
    }
  }).catch(() => {});
}

// One beacon per session however many times the drawing gets prodded — the
// question the dashboard answers is "does this confusion exist", not "how
// hard did one person try".
let replicaTapTracked = false;

function wireScreen() {
  const saved = $('#install-saved');
  if (saved) saved.addEventListener('click', claimSaved);
  const later = $('#install-later');
  if (later) later.addEventListener('click', decline);
  const copy = $('#install-copy');
  if (copy) copy.addEventListener('click', copyLink);
  const now = $('#install-now');
  if (now) now.addEventListener('click', nativeInstall);
  // The mistaken tap becomes the lesson: wobble the drawing, say what it is.
  // No arrow, no position claim — a page cannot know where the browser put
  // its buttons (the same ruling that banned pointing at chrome).
  const answerTap = (el, noteHome) => {
    el.classList.remove('install-cutout-shake');
    void el.getBoundingClientRect();   // reflow, so the animation restarts on
    el.classList.add('install-cutout-shake');   // every tap (SVGs included —
    // they have no offsetWidth, the usual trick's HTMLElement-only property)
    let note = noteHome.querySelector('.install-cutout-note');
    if (!note) {
      note = document.createElement('span');
      note.className = 'install-cutout-note';
      noteHome.appendChild(note);
    }
    note.textContent = 'Just a picture — find the real one on your browser’s own bar.';
    note.hidden = false;
    if (!replicaTapTracked) {
      replicaTapTracked = true;
      track('install-replica-tap');
    }
  };
  document.querySelectorAll('#install-body .install-cutout').forEach((c) => {
    c.addEventListener('click', () => answerTap(c, c));
  });
  // The bare glyphs too (the share icon in step 1, the ••• in its small
  // print): drawn at button size, they invite the same tap. Their note lands
  // at the end of the step that contains them.
  document.querySelectorAll('#install-body .install-glyph').forEach((g) => {
    if (g.closest('.install-cutout')) return;   // the cutout already answers
    g.addEventListener('click', () => {
      answerTap(g, g.closest('.install-step-body') || g.parentElement);
    });
  });
}

// A forced preview (reason 'qa') paints the screen and nothing else: it must
// not count itself into the funnel or spend the player's one real ask —
// Daniel checks these screens on his own phone, on the live site.
function showScreenA(kind, reason) {
  if (!paint(screenAHTML(kind), kind, reason)) return;
  if (reason === 'qa') return;
  track(`install-shown-${kind}`);
  store.setMisc({ installAsked: true });
}

function showScreenB(app, reason) {
  if (!paint(screenBHTML(app), `webview-${app}`, reason)) return;
  // 'banner' is the player OPENING the escape themselves (the Home warning
  // strip): their tap is already counted (webview-note-tap), and a door they
  // chose to walk through must not spend the auto-offer's twice-per-device
  // cap — that cap exists to limit interruptions, and this was no
  // interruption.
  if (reason === 'qa' || reason === 'banner') return;
  track(`webview-shown-${app}`);
  const misc = store.getMisc();
  store.setMisc({ installEscapes: (misc.installEscapes || 0) + 1 });
}

// ---------------------------------------------------------------------------
// the strip on Home (what a "maybe later" leaves behind)
// ---------------------------------------------------------------------------
export function refreshStrip() {
  const strip = $('#install-tip');
  if (!strip) return;
  const misc = store.getMisc();
  const show = !!misc.installLater && !misc.installStripGone && !misc.installSaved
    && !isStandalone() && branch() !== 'webview';
  strip.hidden = !show;
}

function initStrip() {
  const strip = $('#install-tip');
  if (!strip) return;
  const cta = $('#install-tip-btn');
  if (cta) {
    cta.addEventListener('click', () => {
      track('install-strip-tap');
      const b = branch();
      showScreenA(b === 'installed' || b === 'webview' ? 'generic' : b, 'strip');
    });
  }
  const close = $('#install-tip-close');
  if (close) {
    close.addEventListener('click', () => {
      // The × is final for the strip. One last Screen A is still owed, the day
      // a streak reaches 7 — and after that, silence.
      store.setMisc({ installStripGone: true, installLater: false });
      strip.hidden = true;
    });
  }
}

// ---------------------------------------------------------------------------
// the webview warning banner on Home (11 Aug 2026)
// ---------------------------------------------------------------------------
// ~16% of launch traffic arrived inside Instagram's built-in browser, where
// the record is disposable and installing is impossible — and only 8 of 74
// such sessions found the escape page's exit on their own. So inside a
// detected in-app browser (webviewApp() above — the one detector) the state
// is said out loud at the top of Home: one line, one door. The door opens
// the SAME escape screen the end-of-game offer uses (showScreenB), so the
// teach lives in exactly one place; on iOS a page cannot open Safari itself,
// which is why the door leads to instructions rather than attempting it.
// The × snoozes the banner for SEVEN DAYS rather than forever: a warning
// that can never return quietly rots into wallpaper, and unlike the install
// strip (whose × is final by ruling) this strip guards against real, ongoing
// harm — but it must also never become a daily nag, hence the week.
const WEBVIEW_NOTE_SNOOZE_MS = 7 * 24 * 60 * 60 * 1000;
let noteApp = null;           // which app the visible banner is naming
let noteShownTracked = false; // the shown beacon fires once per session

function paintWebviewNote(app) {
  const line = $('#webview-note-line');
  if (!line) return;
  noteApp = app;
  const name = APP_NAMES[app];
  // Named where detection is confident (the ruling: browser-name dynamism is
  // fine where trivially detectable); the generic line claims nothing.
  // "CAN die", not "will": the locked streak-risk wording is universal and
  // vague-but-true, and per-browser deletion claims are banned.
  line.textContent = name
    ? `You’re in ${name}’s browser — streaks can die in here.`
    : 'You’re in an in-app browser — streaks can die in here.';
}

function refreshWebviewNote() {
  const note = $('#webview-note');
  if (!note) return;
  // branch() puts 'installed' before 'webview', so a standalone app is never
  // warned — same precedence as everything else in this file.
  if (branch() !== 'webview') { note.hidden = true; return; }
  const at = store.getMisc().webviewNoteSnoozedAt;
  if (typeof at === 'number') {
    const since = Date.now() - at;
    // A snooze stamped in the future (a device clock that moved) does not
    // count: fail open, towards the warning.
    if (since >= 0 && since < WEBVIEW_NOTE_SNOOZE_MS) { note.hidden = true; return; }
  }
  paintWebviewNote(webviewApp());
  note.hidden = false;
  if (!noteShownTracked) { noteShownTracked = true; track('webview-note-shown'); }
}

function initWebviewNote() {
  const cta = $('#webview-note-btn');
  if (cta) {
    cta.addEventListener('click', () => {
      track('webview-note-tap');
      showScreenB(noteApp || webviewApp() || 'other', 'banner');
    });
  }
  const close = $('#webview-note-close');
  if (close) {
    close.addEventListener('click', () => {
      track('webview-note-dismiss');
      store.setMisc({ webviewNoteSnoozedAt: Date.now() });
      const note = $('#webview-note');
      if (note) note.hidden = true;
    });
  }
}

// ---------------------------------------------------------------------------
// the timing state machine
// ---------------------------------------------------------------------------
// The longest streak this device holds, across the four games, the full house
// and — since the display switched to it — the showed-up run, which is the
// number the player is actually looking at when this offer says "protect your
// streak". Read straight off the ledger rather than through daily.js, which
// imports app.js — this module stays free of that cycle. The cached showedUp
// field is written by the same recordDailyCompletion that gates this offer, so
// it is always fresh by the time this is asked.
function bestStreak() {
  const l = store.getDailyLedger();
  let best = Math.max((l.fullHouse && l.fullHouse.streak) || 0,
                      (l.showedUp && l.showedUp.streak) || 0);
  Object.keys(l.streaks || {}).forEach((g) => {
    const s = (l.streaks[g] && l.streaks[g].streak) || 0;
    if (s > best) best = s;
  });
  return best;
}

// Long enough for the receipt to stamp, short enough to still read as part of
// the same moment.
const OFFER_DELAY = 650;

// Called at the end of every finished daily (the three game engines dispatch
// 'gamefinished'). Nothing here ever fires mid-round.
function onGameFinished() {
  const misc = store.getMisc();
  const games = (misc.installGames || 0) + 1;
  store.setMisc({ installGames: games });
  if (isStandalone() || openKind) return;

  const b = branch();
  if (b === 'webview') {
    // Catch them before the social app closes and takes the record with it:
    // after ONE game, and at most twice in total.
    if (games >= 1 && (misc.installEscapes || 0) < 2) {
      // A short beat so the summary's stamp lands first — this is a moment,
      // not an interruption.
      setTimeout(() => { if (!openKind) showScreenB(webviewApp(), 'offer'); }, OFFER_DELAY);
    }
    return;
  }
  if (misc.installSaved) return;
  if (!misc.installAsked) {
    if (games < 2) return;             // one game is not yet a habit to protect
    setTimeout(() => { if (!openKind) showScreenA(b, 'offer'); }, OFFER_DELAY);
    return;
  }
  // The last word: the strip has been killed, but a 7-day streak is exactly
  // the record worth protecting. One offer, once, ever.
  if (misc.installStripGone && !misc.installFinal && bestStreak() >= 7) {
    store.setMisc({ installFinal: true });
    setTimeout(() => { if (!openKind) showScreenA(b, 'final'); }, OFFER_DELAY);
  }
}

// ---------------------------------------------------------------------------
// wiring
// ---------------------------------------------------------------------------
// Captured at module load, not in initInstall: Chromium can fire this before
// boot() finishes, and a missed event costs the whole native branch.
window.addEventListener('beforeinstallprompt', (e) => {
  // preventDefault also mutes Chrome's own mini-infobar, so the ask happens at
  // OUR moment (after two games) rather than on arrival.
  e.preventDefault();
  deferredPrompt = e;
});
window.addEventListener('appinstalled', () => {
  store.setMisc({ installSaved: true, installLater: false });
  if (openKind) closeScreen();
  refreshStrip();
});

export function initInstall() {
  initStrip();
  refreshStrip();
  initWebviewNote();
  refreshWebviewNote();

  // The one honest success signal: the first launch that reports itself as an
  // installed app. Fired once per device, ever.
  if (isStandalone() && !store.getMisc().installConfirmed) {
    store.setMisc({ installConfirmed: true });
    track('install-confirmed');
  }

  document.addEventListener('gamefinished', onGameFinished);
  document.addEventListener('viewchange', (e) => {
    if (e.detail === 'view-home') { refreshStrip(); refreshWebviewNote(); }
  });
  const back = $('#install-back');
  if (back) back.addEventListener('click', decline);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && openKind) decline();
  });
}

// ---------------------------------------------------------------------------
// QA forcing (?qa=1) — see js/qa.js
// ---------------------------------------------------------------------------
// Every branch has to be summonable on a real phone AND headlessly, because
// most of them can never be reached on the device you happen to be holding.
// Forcing bypasses every gate (including standalone) — it only paints a
// screen, it changes no state and reveals no content.
export const qaActions = {
  installTip: () => {
    const strip = document.querySelector('#install-tip');
    if (!strip) return;
    strip.hidden = false;
    strip.scrollIntoView({ block: 'center' });
  },
  installSafari: () => showScreenA('safari', 'qa'),
  installChromeIOS: () => showScreenA('chrome-ios', 'qa'),
  installNative: () => showScreenA('native', 'qa'),
  installGeneric: () => showScreenA('generic', 'qa'),
  webviewInstagram: () => showScreenB('instagram', 'qa'),
  webviewGeneric: () => showScreenB('other', 'qa'),
  webviewNote: () => {
    const note = document.querySelector('#webview-note');
    if (!note) return;
    // The named variant — the one nine in ten real webview players see. Only
    // paints; the shown beacon and the snooze state stay untouched, same as
    // every other forcing here.
    paintWebviewNote('instagram');
    note.hidden = false;
    note.scrollIntoView({ block: 'center' });
  },
};

// Test-only view of the machine (app.js gates this behind testHooksEnabled).
// `force` is the same set of actions the QA panel wires up, so the Python
// suite can photograph and assert on every branch without the panel's own
// furniture sitting over the screen it is trying to look at.
export const testHooks = () => ({
  branch,
  isStandalone,
  open: () => openKind,
  state: () => store.getMisc(),
  force: qaActions,
});
