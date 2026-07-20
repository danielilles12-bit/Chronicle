// Privacy-friendly analytics (GoatCounter): no cookies, no consent banner,
// EU-hosted, free for non-commercial use. Dashboard:
// https://deadfamous.goatcounter.com (Daniel's account). Set CODE to ''
// to disable everything; count.js already skips localhost by itself.
const CODE = 'deadfamous';

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
  'share-thread': '6-shared-thread',
  'share-map': '6-shared-lifeline',
  'share-who': '6-shared-facevalue',
  'share-what': '6-shared-relic',
  'share-fullhouse': '6-shared-full-house',
  'share-obituary': '6-shared-obituary',
  'install-tip-shown': '7-install-pitch-shown',
  'install-tip-tap': '7-install-pitch-tapped',
  'install-tip-dismiss': '7-install-pitch-dismissed',
  'install-accepted': '7-installed',
  'install-declined': '7-install-declined',
  // Crash beacons arrive pre-named from app.js ('9-app-error-<script>' /
  // '9-app-rejection-<type>') and pass through the map untouched.
};
let queued = [];

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
