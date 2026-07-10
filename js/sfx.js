// The sound layer: five one-shot effects, played via Web Audio.
// Strategy (agreed 10 Jul): sound marks STATE changes, not interactions —
// verdicts and rituals only, so the loud visual design keeps the lead. The
// one exception is the paper tear, the app's signature mechanic. Wrong
// guesses stay silent on purpose: the shake is the feedback, and a failure
// sound turns into nagging by the tenth miss.
import * as store from './storage.js';

const SRC = {
  tear: 'assets/sfx/tear.mp3',        // Face Value / Relic scrap tear
  correct: 'assets/sfx/correct.mp3',  // any round-level win, all games
  stamp: 'assets/sfx/stamp.mp3',      // session receipt (the Alea stamp)
  fanfare: 'assets/sfx/fanfare.mp3',  // "You made history." full house
  toll: 'assets/sfx/toll.mp3',        // "You're history." streak obituary
};

// Volume hierarchy: tear quietest, verdict middle, rituals loudest. Values
// also compensate for how hot each ElevenLabs take came out — toll peaks at
// -32 dBFS (the "distant, muffled" prompt taken literally), hence the large
// make-up gain; swap for a louder regeneration if it sounds hissy on-device.
const GAIN = { tear: 0.4, correct: 0.85, stamp: 1.0, fanfare: 1.0, toll: 12 };

let ctx = null;
const buffers = {};
let muted = !!store.getMisc().soundMuted;

export function initSfx() {
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return;
  ctx = new AC();
  Object.entries(SRC).forEach(([name, url]) => {
    fetch(url)
      .then((r) => (r.ok ? r.arrayBuffer() : Promise.reject(new Error(url))))
      // callback form: promise-based decodeAudioData is missing on older iOS
      .then((buf) => new Promise((res, rej) => ctx.decodeAudioData(buf, res, rej)))
      .then((decoded) => { buffers[name] = decoded; })
      .catch(() => {}); // a missing sound is never worth breaking the game
  });
  // Browsers gate playback behind a first user gesture; unlock on the first
  // one so later programmatic plays (e.g. Thread's delayed stamp) work too.
  const unlock = () => { if (ctx.state !== 'running') ctx.resume().catch(() => {}); };
  ['touchstart', 'pointerdown', 'keydown'].forEach((ev) =>
    document.addEventListener(ev, unlock, { once: true, passive: true }));
}

export function play(name) {
  if (muted || !ctx || !buffers[name]) return;
  // Also covers iOS's 'interrupted' state after a phone call / backgrounding.
  if (ctx.state !== 'running') ctx.resume().catch(() => {});
  const src = ctx.createBufferSource();
  src.buffer = buffers[name];
  // The tear fires many times a round from a single sample: vary the pitch a
  // touch so it reads as paper, not a soundboard button.
  if (name === 'tear') src.playbackRate.value = 0.92 + Math.random() * 0.16;
  const gain = ctx.createGain();
  gain.gain.value = GAIN[name] || 1;
  src.connect(gain).connect(ctx.destination);
  src.start();
}

export function isMuted() { return muted; }

export function setMuted(m) {
  muted = m;
  store.setMisc({ soundMuted: m });
}
