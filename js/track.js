// Privacy-friendly analytics (GoatCounter): no cookies, no consent banner,
// EU-hosted, free for non-commercial use. Dashboard:
// https://yesternerd.goatcounter.com (Daniel's account). Set CODE to ''
// to disable everything; count.js already skips localhost by itself.
const CODE = 'yesternerd';

// Call sites use the app's terse internal vocabulary (game keys: map = Lifeline,
// who = Face Value, what = Relic). DISPLAY translates them into the names the
// GoatCounter dashboard shows: a numbered funnel that reads top-to-bottom as a
// story — 1 arrived, 2 saw the games, 3 started, 4 finished, 5 full house,
// 6 shared, 7 installed, 9 something broke. Unmapped names pass through as-is.
const DISPLAY = {
  'open-browser': '1-visit-in-browser',
  'open-pwa': '1-visit-installed-app',
  'open-new': '1-visitor-first-time',
  'open-return': '1-visitor-returning',
  'rows-rendered': '2-saw-the-games',
  'rows-rendered-slow': '2-saw-the-games-slowly',
  'cta-tap': '3-tapped-play-today',
  'start-thread': '3-started-thread',
  'start-map': '3-started-lifeline',
  'start-who': '3-started-facevalue',
  'start-what': '3-started-relic',
  'finish-thread': '4-finished-thread',
  'finish-map': '4-finished-lifeline',
  'finish-who': '4-finished-facevalue',
  'finish-what': '4-finished-relic',
  'finish-day': '5-finished-all-four',
  // Encore (post-daily bonus runs — practice family, tracked for uptake).
  'encore-who': '3-started-encore-facevalue',
  'encore-map': '3-started-encore-lifeline',
  'encore-what': '3-started-encore-relic',
  // The daily manifest didn't cover an edition it should have (approve not
  // run, or editions.json failed to load) — the emergency fallback served
  // cursor arithmetic instead. The daily still existed; this is the alarm.
  'err-manifest-missing': '9-manifest-missing',
  // P2.2: one data file failed to download (once per file per session). The
  // other games stayed playable; the affected card showed a named retry.
  'err-data-figures': '9-data-figures-failed',
  'err-data-worldmap': '9-data-worldmap-failed',
  'err-data-reveal-who': '9-data-reveal-who-failed',
  'err-data-reveal-what': '9-data-reveal-what-failed',
  'err-data-connections': '9-data-connections-failed',
  'err-data-editions': '9-data-editions-failed',
  // P2.3: player-storage health. recovered = main blob was corrupt, the
  // backup copy saved the day; lost = both copies unreadable, fresh start;
  // err-save = writes are failing right now (quota/private mode), the
  // player was shown the one-time notice.
  'err-save-recovered': '9-save-recovered-from-backup',
  'err-save-lost': '9-save-lost-both-copies',
  'err-save': '9-save-failing',
  'share-thread': '6-shared-thread',
  'share-map': '6-shared-lifeline',
  'share-who': '6-shared-facevalue',
  'share-what': '6-shared-relic',
  'share-fullhouse': '6-shared-full-house',
  'share-obituary': '6-shared-obituary',
  // Clipboard fallback still delivered the text — success family, marked.
  'share-thread-copied': '6-shared-thread-copied',
  'share-map-copied': '6-shared-lifeline-copied',
  'share-who-copied': '6-shared-facevalue-copied',
  'share-what-copied': '6-shared-relic-copied',
  'share-fullhouse-copied': '6-shared-full-house-copied',
  'share-obituary-copied': '6-shared-obituary-copied',
  // Nothing left the phone — kept out of the 6-shared family entirely.
  'share-thread-cancelled': '6x-share-cancelled-thread',
  'share-map-cancelled': '6x-share-cancelled-lifeline',
  'share-who-cancelled': '6x-share-cancelled-facevalue',
  'share-what-cancelled': '6x-share-cancelled-relic',
  'share-fullhouse-cancelled': '6x-share-cancelled-full-house',
  'share-obituary-cancelled': '6x-share-cancelled-obituary',
  'share-thread-failed': '6x-share-failed-thread',
  'share-map-failed': '6x-share-failed-lifeline',
  'share-who-failed': '6x-share-failed-facevalue',
  'share-what-failed': '6x-share-failed-relic',
  'share-fullhouse-failed': '6x-share-failed-full-house',
  'share-obituary-failed': '6x-share-failed-obituary',
  // Carry (js/carry.js): moving a record between origins. Same family as
  // install — both are "this player is changing which jar their streak lives
  // in". carry-land counts arrivals on a carry link; -offer/-ok/-declined are
  // the confirm funnel; -repeat is a second import of a payload already here
  // (the idempotency guard doing its job, not an error); -bad is a code that
  // failed validation.
  'carry-export': '7-carry-code-made',
  'carry-copy-code': '7-carry-code-copied',
  'carry-copy-link': '7-carry-link-copied',
  'carry-land': '7-carry-link-opened',
  'carry-import-offer': '7-carry-offered',
  'carry-import-ok': '7-carry-arrived',
  'carry-import-declined': '7-carry-declined',
  'carry-import-repeat': '7-carry-already-here',
  'carry-import-bad': '9-carry-code-rejected',
  // "Save it as an app" (js/install.js). The funnel reads: which screen a
  // player was shown (one row per browser branch, so a branch that converts
  // nobody is visible rather than averaged away), what they tapped, and — the
  // only signal that is not self-reported — install-confirmed, fired on the
  // first launch that reports itself as an installed app.
  'install-shown-safari': '7-install-shown-ios-safari',
  'install-shown-chrome-ios': '7-install-shown-ios-chrome',
  'install-shown-native': '7-install-shown-android-native',
  'install-shown-generic': '7-install-shown-generic',
  'install-saved-claim': '7-install-saved-claim',
  'install-later': '7-install-later',
  'install-strip-tap': '7-install-strip-tapped',
  // Android's OS dialog answering for itself (the native branch only).
  'install-accepted': '7-install-android-accepted',
  'install-declined': '7-install-android-declined',
  'install-confirmed': '7-installed',
  // The escape page: in-app browsers cannot install anything, so the win here
  // is getting out into a real browser at all.
  'webview-shown-instagram': '7-webview-shown-instagram',
  'webview-shown-facebook': '7-webview-shown-facebook',
  'webview-shown-tiktok': '7-webview-shown-tiktok',
  'webview-shown-other': '7-webview-shown-other',
  'webview-copylink': '7-webview-link-copied',
  // Crash beacons arrive pre-named from app.js ('9-app-error-<script>' /
  // '9-app-rejection-<type>') and pass through the map untouched.
};

// P5.1: round outcome / duration / resume / abandon / share-funnel families
// are a game x bucket cross-product (56 entries) — generated rather than
// hand-typed so a mistyped bucket name can't silently create an uncounted
// event. Numbering extends the story above: 1 = arrived (a share landing is
// a specific flavour of arriving), 3 = started/still playing (resume, and
// the share funnel's start/answer steps, are both "mid-session" signals),
// 4 = how a round or the whole daily resolved, 4x = a daily rollover left
// UNresolved — kept out of the "4" family entirely, exactly like
// 6x-share-cancelled is kept out of 6-shared above — and 8 = the player
// came back days or weeks later (the one gap left in the single-digit
// scheme, reserved for retention).
const GAME_DISPLAY_NAME = { map: 'lifeline', who: 'facevalue', what: 'relic', thread: 'thread' };
Object.keys(GAME_DISPLAY_NAME).forEach((g) => {
  const name = GAME_DISPLAY_NAME[g];
  // Thread has no hint mechanic — see roundOutcome/finishPuzzle's own
  // clean/fought/lost (mistake-count based, not hints-based) logic.
  const outcomes = g === 'thread' ? ['clean', 'fought', 'lost'] : ['clean', 'hinted', 'fought', 'lost'];
  outcomes.forEach((o) => { DISPLAY[`round-${g}-${o}`] = `4-round-${name}-${o}`; });
  ['u2', 'u5', 'o5'].forEach((b) => { DISPLAY[`dur-${g}-${b}`] = `4-dur-${name}-${b}`; });
  if (g !== 'thread') {   // the three-choices clue lives in the rounds games only
    DISPLAY[`mcq-open-${g}`] = `4-mcq-open-${name}`;
    DISPLAY[`mcq-${g}-win`] = `4-mcq-${name}-win`;
    DISPLAY[`mcq-${g}-loss`] = `4-mcq-${name}-loss`;
  }
  DISPLAY[`resume-${g}`] = `3-resume-${name}`;
  DISPLAY[`abandon-${g}`] = `4x-abandoned-${name}`;
  DISPLAY[`land-share-${g}`] = `1-land-share-${name}`;
  DISPLAY[`start-from-share-${g}`] = `3-start-from-share-${name}`;
  DISPLAY[`answer-from-share-${g}`] = `3-answer-from-share-${name}`;
});
DISPLAY['ret-d1'] = '8-return-d1';
DISPLAY['ret-d7'] = '8-return-d7';
DISPLAY['ret-d30'] = '8-return-d30';
DISPLAY['ritual-week'] = '8-ritual-week';
// P2.2's file-load family covers data/*.json; this is the one other place a
// player's device can silently fail to persist something useful (the image
// cache, when storage is full or private-mode limits kick in) — sw.js can't
// call track() itself (no window.goatcounter inside a service worker), so it
// posts a message and app.js relays it here, once per session.
DISPLAY['err-img-cache'] = '9-img-cache-failed';

let queued = [];

// P5.1: round outcome bucket, shared by mapgame.js/revealgame.js (Thread
// computes its own — mistake-count based, no hint mechanic). Priority: a
// wrong guess before the correct answer always reads as "fought", even if a
// clue was also bought — "hinted" is reserved for a clean run helped only by
// a clue, never a struggled one.
export function roundOutcome(correct, hints, wrongs) {
  if (!correct) return 'lost';
  if (wrongs > 0) return 'fought';
  if (hints > 0) return 'hinted';
  return 'clean';
}

// P5.1: duration bucket for a completed daily, from a session-start
// timestamp kept in that game's session blob (see mapgame.js/revealgame.js/
// connectionsgame.js persist functions).
export function durationBucket(ms) {
  if (ms < 120000) return 'u2';
  if (ms < 300000) return 'u5';
  return 'o5';
}

export function track(event) {
  if (!CODE) return;
  const gc = window.goatcounter;
  if (gc && gc.count) {
    try { gc.count({ path: DISPLAY[event] || event, event: true }); } catch (e) { /* never break the game */ }
  } else {
    queued.push(event);
  }
}

export function initTracking() {
  if (!CODE || location.protocol.indexOf('http') !== 0) return;
  // /index.html and / are the same page: canonicalise before count.js reads
  // the URL, so the dashboard shows one row (and Add to Home Screen bakes in
  // the clean path).
  if (location.pathname.slice(-11) === '/index.html') {
    history.replaceState(null, '', location.pathname.slice(0, -10) + location.search + location.hash);
  }
  window.goatcounter = window.goatcounter || {};
  const s = document.createElement('script');
  s.async = true;
  s.dataset.goatcounter = `https://${CODE}.goatcounter.com/count`;
  s.src = 'https://gc.zgo.at/count.js';
  s.addEventListener('load', () => {
    const q = queued; queued = [];
    q.forEach(track);
    // count.js has counted the pageview (campaign intact) by the time its
    // load event fires. Now scrub ref/utm params so iOS "Add to Home Screen"
    // never bakes a campaign into the installed app's start URL — every
    // later open would re-count as a shared-link visit.
    if (/[?&](ref|utm_[a-z]+)=/.test(location.search)) {
      const p = new URLSearchParams(location.search);
      [...p.keys()].filter((k) => k === 'ref' || k.indexOf('utm_') === 0).forEach((k) => p.delete(k));
      const qs = p.toString();
      history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
    }
  });
  document.head.appendChild(s);
}
