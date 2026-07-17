// Dead Famous service worker: slim shell precache, cache-first serving.
// Bump VERSION on EVERY deploy (and BUILD in js/app.js — keep them in sync):
// that byte-change is what makes phones install the new edition.
//
// Update flow (the "off the presses" plumbing):
//   app.js asks for an update check on every wake-up -> this file changes ->
//   new worker precaches the shell, skipWaiting+claim take over immediately ->
//   app.js sees controllerchange and shows the NEW EDITION bar -> the user's
//   pull-to-refresh (or a tap on the bar) reloads into the new version.
const VERSION = 'deadfamous-v106';

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
      if (res && res.ok) c.put(req, res.clone());
      return res;
    }));
    return;
  }

  // Daily content: serve the cached copy instantly, refresh it in the
  // background. Content therefore lags one open at most, works offline after
  // the first online boot, and never gates a version update.
  if (url.pathname.includes('/data/')) {
    e.respondWith(caches.open(DATA_CACHE).then(async (c) => {
      const hit = await c.match(req, { ignoreSearch: true });
      const refresh = fetch(req).then((res) => {
        if (res && res.ok) c.put(req, res.clone());
        return res;
      });
      if (hit) {
        e.waitUntil(refresh.catch(() => {}));
        return hit;
      }
      return refresh;
    }));
    return;
  }

  e.respondWith(
    caches.match(req, { ignoreSearch: true }).then((hit) => {
      if (hit) return hit;
      if (req.mode === 'navigate') {
        return caches.match('./index.html').then((page) => page || fetch(req));
      }
      return fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(VERSION).then((c) => c.put(req, copy));
        return res;
      });
    }),
  );
});
