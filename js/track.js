// Privacy-friendly analytics (GoatCounter): no cookies, no consent banner,
// EU-hosted, free for non-commercial use. Dashboard:
// https://deadfamous.goatcounter.com (Daniel's account). Set CODE to ''
// to disable everything; count.js already skips localhost by itself.
const CODE = 'deadfamous';

// Event names kept short and stable — they become paths in the GoatCounter
// dashboard: start-thread, finish-map, share-fullhouse, install-tip-shown…
let queued = [];

export function track(event) {
  if (!CODE) return;
  const gc = window.goatcounter;
  if (gc && gc.count) {
    try { gc.count({ path: event, event: true }); } catch (e) { /* never break the game */ }
  } else {
    queued.push(event);
  }
}

export function initTracking() {
  if (!CODE || location.protocol.indexOf('http') !== 0) return;
  window.goatcounter = window.goatcounter || {};
  const s = document.createElement('script');
  s.async = true;
  s.dataset.goatcounter = `https://${CODE}.goatcounter.com/count`;
  s.src = 'https://gc.zgo.at/count.js';
  s.addEventListener('load', () => {
    const q = queued; queued = [];
    q.forEach(track);
  });
  document.head.appendChild(s);
}
