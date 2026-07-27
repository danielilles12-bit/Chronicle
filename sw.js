// Dead Famous service worker: slim shell precache, cache-first serving.
// Bump VERSION on EVERY deploy (and BUILD in js/app.js — keep them in sync):
// that byte-change is what makes phones install the new edition.
//
// Update flow (the "off the presses" plumbing):
//   app.js asks for an update check on every wake-up -> this file changes ->
//   new worker precaches the shell, skipWaiting+claim take over immediately ->
//   app.js sees controllerchange and shows the NEW EDITION bar -> the user's
//   pull-to-refresh (or a tap on the bar) reloads into the new version.
const VERSION = 'deadfamous-v138';

// Daily-content cache: survives version bumps so updating the app never
// re-downloads the whole archive, served stale-while-revalidate below.
const DATA_CACHE = 'df-data';

// Puzzle-image cache: Face Value / Relic photos, cache-first and version-bump
// proof (the files are immutable). app.js prefetches today's + tomorrow's
// editions into it on every online open, so a later offline open (the
// aeroplane case) still has playable rounds.
const IMG_CACHE = 'df-img';

// The shell: everything the app needs to boot and look right. Deliberately
// EXCLUDES data/*.json (they live in DATA_CACHE) so the install stays small —
// the old 2.3 MB all-or-nothing install was the main reason updates silently
// failed on flaky connections.
const ASSETS = [
  './',
  './index.html',
  './css/brand-tokens.css',
  './css/style.css',
  // P3.4: how-to-play is the one static content page worth precaching (it's
  // the natural "help" destination and is tiny); about/sources/corrections/
  // privacy/404 stay out to keep the install small — they cache themselves
  // on first visit via the generic fetch handler below.
  './how-to-play.html',
  './css/pages.css',
  './assets/fonts/archivo-black.woff2',
  './assets/fonts/archivo-regular.woff2',
  './assets/fonts/archivo-bold.woff2',
  './assets/fonts/space-mono-regular.woff2',
  './assets/fonts/space-mono-bold.woff2',
  './assets/brand/david-sticker.png',
  './assets/brand/game-icon-thread.png',
  './assets/brand/game-icon-lifeline.png',
  './assets/brand/game-icon-face-value.png',
  './assets/brand/game-icon-relic.png',
  './assets/brand/stamp-alea-iacta-fest.png',
  './assets/brand/ptr-queen.png',
  './assets/sfx/tear.mp3',
  './assets/sfx/correct.mp3',
  './assets/sfx/stamp.mp3',
  './assets/sfx/fanfare.mp3',
  './assets/sfx/toll.mp3',
  './js/app.js',
  './js/track.js',
  './js/sharecard.js',
  './js/storage.js',
  './js/match.js',
  './js/pinchzoom.js',
  './js/mapgame.js',
  './js/revealgame.js',
  './js/connectionsgame.js',
  './js/daily.js',
  './js/ledger.js',
  './js/sfx.js',
  './manifest.webmanifest',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/apple-touch-icon.png',
  './icons/favicon.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(VERSION).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== VERSION && k !== DATA_CACHE && k !== IMG_CACHE)
          .map((k) => caches.delete(k)),
      ))
      .then(() => self.clients.claim()),
  );
});

// P5.1: a failed cache write (quota exceeded, private-mode storage limits) is
// invisible from inside the worker — GoatCounter only runs on a page — so
// tell every open client once; app.js dedupes to one beacon per session.
function notifyImgCacheFail() {
  self.clients.matchAll().then((clients) => {
    clients.forEach((c) => c.postMessage({ type: 'df-img-cache-fail' }));
  });
}

// P5.3b: IMG_CACHE is otherwise unbounded — every edition ever opened adds
// its images and nothing ever leaves. Cap it at 300 entries (~a month of
// dailies at 10 images/day) by dropping the OLDEST puts once over.
// Cache.keys() returns entries in insertion order, so the first `excess`
// keys are exactly the ones to drop.
const IMG_CACHE_MAX = 300;
async function evictImgCache(cache) {
  const keys = await cache.keys();
  const excess = keys.length - IMG_CACHE_MAX;
  if (excess <= 0) return;
  await Promise.all(keys.slice(0, excess).map((k) => cache.delete(k)));
}

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (url.pathname.includes('/audit/')) return; // never cache dev tools (path-prefix agnostic: GH Pages serves under /Chronicle/)
  if (url.pathname.includes('/preview/')) return; // design prototypes live outside the app shell
  if (url.pathname.includes('/launch-demos/')) return; // proposal demos, not part of the app

  // Puzzle images: cache-first, immutable. First fetch (usually the app.js
  // prefetch) files the image into IMG_CACHE; every later request — including
  // offline ones — is served from it.
  if (url.pathname.includes('/assets/img/')) {
    e.respondWith(caches.open(IMG_CACHE).then(async (c) => {
      const hit = await c.match(req, { ignoreSearch: true });
      if (hit) return hit;
      const res = await fetch(req);
      if (res && res.ok) {
        await c.put(req, res.clone()).catch(notifyImgCacheFail);
        e.waitUntil(evictImgCache(c));
      }
      return res;
    }));
    return;
  }

  // Daily content (P5.3b): network-first with a 3s ceiling, falling back to
  // the last cached copy. A correction pushed to main now lands on the very
  // next online open instead of lagging one open behind; a slow or offline
  // connection still serves instantly from cache, and the network attempt is
  // kept alive via waitUntil so a late reply still refreshes the cache for
  // next time.
  if (url.pathname.includes('/data/')) {
    e.respondWith(caches.open(DATA_CACHE).then(async (c) => {
      const network = fetch(req).then((res) => {
        if (res && res.ok) c.put(req, res.clone());
        return res;
      }).catch(() => null);
      e.waitUntil(network);
      const timeout = new Promise((resolve) => setTimeout(resolve, 3000));
      const res = await Promise.race([network, timeout]);
      if (res) return res;
      const hit = await c.match(req, { ignoreSearch: true });
      return hit || network;
    }));
    return;
  }

  e.respondWith(
    caches.match(req, { ignoreSearch: true }).then((hit) => {
      if (hit) return hit;
      return fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(VERSION).then((c) => c.put(req, copy));
        return res;
      }).catch(() => {
        // Offline and this exact page was never cached: for a real page
        // navigation, the app shell is a better dead end than a browser
        // error screen. (P3.4: about/sources/corrections/privacy/404 are
        // real standalone pages now, not SPA routes — this fallback only
        // kicks in when the network is actually unreachable, not on every
        // cache miss, so a first-time online visit to any of them fetches
        // the real page instead of silently showing the app shell.)
        if (req.mode === 'navigate') return caches.match('./index.html');
      });
    }),
  );
});
