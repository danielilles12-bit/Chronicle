// POST /api/score — the field comparison's one endpoint (Cloudflare Pages
// Function; the plan is design-reviews/leaderboard-plan.md, approved 5 Aug
// 2026). Plain JS on purpose: no TypeScript, no build step, no npm imports —
// the same git push that deploys the site deploys this file, and nothing new
// is ever needed on the owner's machine.
//
// Contract with the client (js/percentile.js):
//   in:  {edition, game, score, token}
//   out: {below, total}            (~30 bytes — well under the 100-byte cap)
// `below` counts scores STRICTLY below yours — ties are never "beaten"
// (statistical-honesty ruling in the plan); `total` includes you.
//
// Storage (D1, binding name **DB**) is aggregate-only — the legal
// load-bearing wall of the whole feature. Two tables, created once in the
// Cloudflare dashboard:
//
//   CREATE TABLE tally (
//     edition INTEGER NOT NULL,
//     game    TEXT    NOT NULL,
//     score   INTEGER NOT NULL,
//     count   INTEGER NOT NULL DEFAULT 0,
//     PRIMARY KEY (edition, game, score)
//   );
//   CREATE TABLE seen (
//     edition INTEGER NOT NULL,
//     game    TEXT    NOT NULL,
//     token   TEXT    NOT NULL,
//     PRIMARY KEY (edition, game, token)
//   );
//
// No rows per person, no IP addresses, no user agents, no per-person
// timestamps — `tally` is literally "three people scored 84 on edition 42's
// Relic". `seen` holds only the day's dedup tokens (client-generated random
// UUIDs with no meaning, fresh every edition) and is swept lazily below, so
// nothing here can link one day's player to another's.
//
// Abuse posture: validation + dedup here, plus a Cloudflare rate-limiting
// rule configured in the dashboard (not in code). Residual risk accepted:
// with no leaderboard to win, a forged score buys one silly percentile.

const GAMES = ['who', 'map', 'what', 'thread'];

// Edition sanity check ONLY — never keying. Editions are defined by the
// PLAYER's local calendar date (js/daily.js, epoch 2026-06-29, the Wordle
// convention); the server clock is used solely to reject absurd numbers.
// ±2 days of slack covers every timezone on Earth with room to spare.
const EPOCH_UTC = Date.UTC(2026, 5, 29); // 2026-06-29 (month is 0-based)
const EDITION_SLACK = 2;

function plausibleEdition(n) {
  const serverDay = Math.floor((Date.now() - EPOCH_UTC) / 86400000);
  return Number.isInteger(n) && n >= 0
    && n >= serverDay - EDITION_SLACK && n <= serverDay + EDITION_SLACK;
}

function reject() {
  return new Response(null, { status: 400 });
}

export async function onRequestPost({ request, env }) {
  // Require a JSON content-type. The app always sends one; without this
  // check a cross-origin POST is a CORS "simple request" that skips the
  // browser's preflight, letting any web page write into the tally.
  const ct = request.headers.get('content-type') || '';
  if (ct.indexOf('application/json') === -1) return reject();
  let body;
  try {
    body = await request.json();
  } catch (e) {
    return reject();
  }
  if (!body || typeof body !== 'object') return reject();

  const { edition, game, score, token } = body;
  if (!plausibleEdition(edition)) return reject();
  if (GAMES.indexOf(game) === -1) return reject();
  if (!Number.isInteger(score) || score < 0 || score > 100) return reject();
  if (typeof token !== 'string' || !/^[0-9a-fA-F-]{8,64}$/.test(token)) return reject();

  try {
    const db = env.DB;
    // Dedup on (edition, game, token): only a token's FIRST post for a game
    // counts. INSERT OR IGNORE + changes tells us atomically whether this is
    // a first post, so a re-render of the results screen never double-counts.
    const ins = await db.prepare(
      'INSERT OR IGNORE INTO seen (edition, game, token) VALUES (?1, ?2, ?3)')
      .bind(edition, game, token).run();
    if (ins.meta.changes > 0) {
      await db.prepare(
        'INSERT INTO tally (edition, game, score, count) VALUES (?1, ?2, ?3, 1) '
        + 'ON CONFLICT (edition, game, score) DO UPDATE SET count = count + 1')
        .bind(edition, game, score).run();
      // Lazy sweep (the plan's no-cron cleanup): any counted write clears
      // dedup tokens older than yesterday. Usually a no-op costing nothing;
      // the aggregate tally rows are kept — they identify nobody and they're
      // the product. The floor is derived from the SERVER clock, never the
      // request: a client claiming edition serverDay+2 (which validation
      // allows as clock slack) must not be able to delete TODAY's dedup rows
      // and reopen double-counting — found in preview testing, 5 Aug 2026.
      const serverDay = Math.floor((Date.now() - EPOCH_UTC) / 86400000);
      await db.prepare('DELETE FROM seen WHERE edition < ?1')
        .bind(serverDay - 1).run();
    }
    const row = await db.prepare(
      'SELECT COALESCE(SUM(CASE WHEN score < ?3 THEN count END), 0) AS below, '
      + 'COALESCE(SUM(count), 0) AS total '
      + 'FROM tally WHERE edition = ?1 AND game = ?2')
      .bind(edition, game, score).first();
    return new Response(JSON.stringify({ below: row.below, total: row.total }), {
      headers: {
        'content-type': 'application/json',
        'cache-control': 'no-store',
      },
    });
  } catch (e) {
    // A dark database and a dark service must look identical from the app:
    // the client renders nothing for any non-200. No detail leaves here.
    return new Response(null, { status: 500 });
  }
}
