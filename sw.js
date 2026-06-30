// Chronicle service worker: precache everything, serve cache-first.
// Bump VERSION on every deploy to refresh clients.
const VERSION = 'chronicle-v9';

const ASSETS = [
  './',
  './index.html',
  './css/style.css',
  './js/app.js',
  './js/storage.js',
  './js/match.js',
  './js/crossword.js',
  './js/mapgame.js',
  './js/revealgame.js',
  './js/chronogame.js',
  './js/connectionsgame.js',
  './data/puzzles.json',
  './data/figures.json',
  './data/worldmap.json',
  './data/reveal.json',
  './data/chrono.json',
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
  if (url.pathname.startsWith('/audit/')) return; // never cache dev tools
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
