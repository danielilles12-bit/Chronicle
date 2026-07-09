// Dead Famous service worker: precache everything, serve cache-first.
// Bump VERSION on every deploy to refresh clients.
const VERSION = 'deadfamous-v90';

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
  './js/app.js',
  './js/storage.js',
  './js/match.js',
  './js/crossword.js',
  './js/mapgame.js',
  './js/revealgame.js',
  './js/connectionsgame.js',
  './js/daily.js',
  './data/puzzles.json',
  './data/figures.json',
  './data/worldmap.json',
  './data/reveal.json',
  './data/reveal-who.json',
  './data/reveal-what.json',
  './data/connections.json',
  './manifest.webmanifest',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-maskable-512.png',
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
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
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
