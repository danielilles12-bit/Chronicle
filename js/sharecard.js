// Share 2.0 — the approved grammar: one headline, one spoiler-free emoji row
// that encodes the run, one human brag/wound line, then the link (once the
// domain exists). Every game keeps its own glyph so a group chat can tell
// games apart at a glance. Also draws the image receipt offered alongside
// the text on share sheets that accept files.
import { track } from './track.js';

// Full scheme on purpose: bare domains don't linkify in Discord/Slack.
// The canvas receipt strips the scheme for display.
// ?ref=share shows shared-link visits under the GoatCounter Campaigns panel
// ("ref" is in its default campaign params). track.js scrubs the param after
// the pageview is counted so it never bakes into an installed app's URL.
//
// P5.2: a per-game share additionally carries ?play=<game>, which app.js's
// boot router reads to open that game's TODAY daily directly — Wordle
// convention, the recipient plays their own today, never the sender's issue
// — instead of the generic home page (whose CTA only ever opens Face Value).
// fullhouse/obituary shares have no single game to route to, so they keep
// the bare link. Plain validated params on purpose — no signing, see the
// discarded X1 card in the audited plan.
// TEMPORARY until the domain move (see index.html note).
const BASE_URL = 'https://deadfamous.app/';
export function shareUrl(game) {
  return game ? `${BASE_URL}?play=${game}&ref=share` : `${BASE_URL}?ref=share`;
}

const THREAD_EMOJI = { yellow: '🟨', green: '🟩', blue: '🟦', purple: '🟪' };
// Card #12: colorblind print glyphs. The text emoji-grid share (above) stays
// pure colour squares — that's the Wordle-family convention, untouched here.
// The canvas image receipt below additionally prefixes a solved-group row
// (a guess where all four tiles matched, i.e. a homogeneous row) with its
// glyph, drawn as ink text so it survives regardless of hue perception.
const THREAD_GLYPH = { yellow: '●', green: '▲', blue: '■', purple: '✦' };
const EMOJI_TO_COLOUR = Object.fromEntries(Object.entries(THREAD_EMOJI).map(([c, e]) => [e, c]));

// Row builders are exported so the canvas receipt can reuse the exact same
// encoding the text uses — one grammar, two renderings.
export function threadEmojiRows(guesses) {
  return (guesses || []).map((g) => g.map((c) => THREAD_EMOJI[c] || '⬜').join(''));
}
export function mapEmojiRow(rounds) {
  // mcq = rescued via the three-choices clue: assisted, same glyph as hints.
  return rounds.map((r) => (!r.correct ? '⚰️' : (r.hints || r.mcq) ? '🧭' : '✅')).join('');
}
export function revealEmojiRow(rounds) {
  return rounds.map((r) => {
    if (!r.correct) return '🟥';
    return ((r.torn || 0) >= 4 || (r.wrongs || 0) > 0 || r.mcq) ? '🟨' : '🟩';
  }).join('');
}

function lines(url, ...parts) {
  return parts.concat(url ? [url] : []).filter(Boolean).join('\n');
}

// ---------- per-game share text ----------
export function threadShareText(issue, d) {
  const grid = threadEmojiRows(d.guesses).join('\n');
  const human = d.perfect ? 'Flawless.'
    : d.solved ? `${d.mistakes} slip${d.mistakes === 1 ? '' : 's'}${d.title ? ` — ${d.title.toUpperCase()} had me` : ''}.`
    : `${d.title ? d.title.toUpperCase() : 'The board'} beat me.`;
  return lines(shareUrl('thread'), `THREAD №${issue} 🧵`, grid, human);
}

export function mapShareText(issue, rounds, score) {
  const row = mapEmojiRow(rounds);
  const hints = rounds.filter((r) => r.correct && r.hints).length;
  const coffins = rounds.filter((r) => !r.correct).length;
  const bits = [];
  if (hints) bits.push(`${hints} hint${hints === 1 ? '' : 's'}`);
  if (coffins) bits.push(`${coffins} funeral${coffins === 1 ? '' : 's'}`);
  const human = `${score} pts${bits.length ? ' · ' + bits.join(', ') : ' · a clean sweep'}`;
  return lines(shareUrl('map'), `LIFELINE №${issue} 🗺️`, row, human);
}

export function revealShareText(kind, issue, rounds, score) {
  const name = kind === 'who' ? 'FACE VALUE' : 'RELIC';
  const glyph = kind === 'who' ? '🖼️' : '🏺';
  const row = revealEmojiRow(rounds);
  const scraps = rounds.reduce((s, r) => s + (r.torn || 0), 0);
  return lines(shareUrl(kind), `${name} №${issue} ${glyph}`, row, `${score} pts · ${scraps} scraps torn`);
}

export function fullHouseShareText(issue, scores, total, streak) {
  const row = `🖼️${scores.who} 🗺️${scores.map} 🏺${scores.what} 🧵${scores.thread} · ${total} PTS`;
  const flame = streak > 1 ? `🔥 ${streak}-day streak` : '';
  return lines(shareUrl(), `YESTERNERD №${issue} — FULL HOUSE 🏛️`, row, flame);
}

export function obituaryShareText(streak, fromIssue, toIssue) {
  return lines(shareUrl(), 'YESTERNERD ⚰️',
    `My ${streak}-day streak died.`,
    `RIP №${fromIssue}–№${toIssue}. MEMENTO MORI.`);
}

// ---------- the image receipt ----------
let stickerImg = null;
function sticker() {
  if (!stickerImg) {
    stickerImg = new Image();
    stickerImg.src = 'assets/brand/antinous-sticker.png';
  }
  return stickerImg;
}

// spec: { game, glyph, score, rows: ['🟩🟨…', …], sub, stamp, url } → PNG blob.
async function drawCard(spec) {
  try { if (document.fonts && document.fonts.ready) await document.fonts.ready; } catch (e) { /* draw anyway */ }
  const W = 1080, H = 1350;
  const cv = document.createElement('canvas');
  cv.width = W; cv.height = H;
  const x = cv.getContext('2d');
  x.fillStyle = '#F2EFE6'; x.fillRect(0, 0, W, H);
  x.fillStyle = 'rgba(11,11,11,.09)';
  for (let px = 20; px < W; px += 38) for (let py = 20; py < H; py += 38) {
    x.beginPath(); x.arc(px, py, 2.6, 0, 7); x.fill();
  }
  x.fillStyle = '#0B0B0B'; x.textBaseline = 'top';
  x.font = '400 118px "DF Slab","Arial Black",sans-serif';
  x.fillText('DEAD', 64, 74);
  x.fillText('FAMOUS', 64, 188);
  x.font = '700 34px "DF Mono",monospace';
  x.fillText(spec.sub, 66, 330);
  x.fillRect(64, 396, W - 128, 8);
  const st = sticker();
  if (st.complete && st.naturalWidth) {
    x.save(); x.translate(W - 200, 168); x.rotate(0.10);
    const sw = 240, sh = sw * st.naturalHeight / st.naturalWidth;
    x.drawImage(st, -sw / 2, -sh / 2, sw, sh); x.restore();
  }
  const cy = 470;
  x.fillStyle = '#0B0B0B'; x.fillRect(94, cy + 10, W - 168, 620);
  x.fillStyle = '#FFF'; x.fillRect(84, cy, W - 168, 620);
  x.strokeStyle = '#0B0B0B'; x.lineWidth = 6; x.strokeRect(84, cy, W - 168, 620);
  x.fillStyle = '#0B0B0B'; x.textAlign = 'center';
  x.font = '700 30px "DF Mono",monospace';
  x.fillText(`${spec.glyph}  ${spec.game}`, W / 2, cy + 40);
  x.setLineDash([16, 12]); x.beginPath(); x.moveTo(130, cy + 110); x.lineTo(W - 130, cy + 110); x.stroke(); x.setLineDash([]);
  x.font = '400 200px "DF Slab","Arial Black",sans-serif';
  x.fillText(String(spec.score), W / 2, cy + 150);
  x.font = '700 26px "DF Mono",monospace'; x.fillStyle = '#6B675C';
  x.fillText(spec.unit || 'POINTS', W / 2, cy + 372);
  x.fillStyle = '#0B0B0B';
  x.textAlign = 'center';
  x.font = '48px -apple-system,"Segoe UI Emoji",sans-serif';
  // Card #12: a Thread row where all four tiles matched (colours[0] repeated
  // 4x in the emoji string) is a solved group. Prefix it with the group's
  // ink-coloured glyph, drawn as text sized like the card's other label-scale
  // text (30px, matching spec.sub above) — the emoji squares themselves are
  // left untouched, exactly as the plain-text share grid stays pure colour.
  (spec.rows || []).slice(0, 4).forEach((row, i) => {
    const y = cy + 430 + i * 62;
    if (spec.game === 'THREAD') {
      const chars = Array.from(row);
      const colour = chars.length && chars.every((c) => c === chars[0]) ? EMOJI_TO_COLOUR[chars[0]] : null;
      const glyph = colour ? THREAD_GLYPH[colour] : null;
      if (glyph) {
        const rowWidth = x.measureText(row).width;
        x.save();
        x.font = '700 30px "DF Mono",monospace';
        x.fillStyle = 'rgba(11,11,11,.8)';
        x.textAlign = 'right';
        x.fillText(glyph, W / 2 - rowWidth / 2 - 16, y + 9);
        x.restore();
      }
    }
    x.fillText(row, W / 2, y);
  });
  x.save(); x.translate(W / 2, 1210); x.rotate(-0.06);
  x.strokeStyle = '#E02020'; x.lineWidth = 6; x.strokeRect(-250, -44, 500, 88);
  x.fillStyle = '#E02020'; x.font = '700 40px "DF Mono",monospace';
  x.fillText(spec.stamp || 'CARPET DIEM', 0, -20);
  x.restore();
  if (spec.url) {
    x.fillStyle = '#0B0B0B'; x.font = '700 28px "DF Mono",monospace';
    x.fillText(spec.url.replace(/^https?:\/\//, ''), W / 2, 1286);
  }
  x.textAlign = 'left';
  return new Promise((res) => cv.toBlob(res, 'image/png'));
}

// ---------- the share flow ----------
// Text is the primary unit (it pastes everywhere); the image receipt rides
// along on share sheets that accept files (iOS 15+). Cancelling the sheet is
// respected silently; no sheet at all falls back to the clipboard.
export async function shareResult({ text, card, trackAs }) {
  const outcome = await performShare(text, card);
  // Count what actually happened, not the button tap: only 'shared' fires the
  // success event; copied/cancelled/failed each get their own suffixed event
  // so abandoned share sheets never inflate the share numbers.
  if (trackAs) track(outcome === 'shared' ? trackAs : `${trackAs}-${outcome}`);
  return outcome;
}

async function performShare(text, card) {
  if (card && navigator.share && navigator.canShare) {
    try {
      const blob = await drawCard(card);
      if (blob) {
        const file = new File([blob], 'yesternerd-receipt.png', { type: 'image/png' });
        if (navigator.canShare({ files: [file] })) {
          await navigator.share({ files: [file], text });
          return 'shared';
        }
      }
    } catch (e) {
      if (e && e.name === 'AbortError') return 'cancelled';
      // fall through to text-only
    }
  }
  try {
    if (navigator.share) { await navigator.share({ text }); return 'shared'; }
  } catch (e) {
    if (e && e.name === 'AbortError') return 'cancelled';
  }
  try { await navigator.clipboard.writeText(text); return 'copied'; } catch (e) { /* sandboxed */ }
  return 'failed';
}

// Uniform button feedback for the copied/failed fallbacks.
export function flashShareButton(btn, outcome, idleLabel) {
  if (outcome === 'copied') btn.textContent = 'Copied — paste it anywhere';
  else if (outcome === 'failed') btn.textContent = 'Sharing unavailable here';
  else return;
  setTimeout(() => { btn.textContent = idleLabel; }, 1800);
}
