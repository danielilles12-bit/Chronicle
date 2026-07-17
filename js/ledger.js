// The Ledger — the app's stats page, styled as a press record book (never a
// "stats modal"). Every number here is DERIVED live from the daily ledger in
// localStorage; this module writes nothing. It reuses daily.js's streak
// primitives (isStreakValid + derivedStreak + GAMES) rather than reimplementing
// the streak walk, so a "current" streak reported here is the same number the
// masthead punch card shows for the same data.
import * as store from './storage.js';
import * as daily from './daily.js';

// Home order, the one fixed presentation order across the app.
const ROWS = [
  { key: 'thread', label: 'Thread' },
  { key: 'map', label: 'Lifeline' },
  { key: 'who', label: 'Face Value' },
  { key: 'what', label: 'Relic' },
];

// ---------- pure computation (no DOM) ----------

// The exact validity test recordDailyCompletion uses: an entry exists for
// (game, edition) AND it was filed inside the streak-valid window. Built from
// the same daily.isStreakValid so "valid" means the same thing everywhere.
function gameValidAt(entries, g) {
  return (e) => {
    const en = entries[g] && entries[g][e];
    return !!en && daily.isStreakValid(e, en.completedOn);
  };
}

// Longest run of consecutive integers present in a set — the "best ever"
// companion to derivedStreak's "current". Same notion of a link in the chain
// (a valid edition), so the two agree by construction.
function longestRun(validSet) {
  let best = 0;
  for (const n of validSet) {
    if (validSet.has(n - 1)) continue;        // not a run start
    let len = 1;
    while (validSet.has(n + len)) len++;
    if (len > best) best = len;
  }
  return best;
}

// Every edition index for which game g has a *valid* entry, as a Set.
function validSetFor(entries, g) {
  const valid = gameValidAt(entries, g);
  const set = new Set();
  Object.keys(entries[g] || {}).forEach((k) => { const e = +k; if (valid(e)) set.add(e); });
  return set;
}

// All the figures the page shows, computed once from the ledger.
export function computeLedger(ledger, today) {
  const entries = ledger.entries || {};

  // Editions with at least one entry of any kind = "issues filed".
  const anyEditions = new Set();
  ROWS.forEach(({ key }) => Object.keys(entries[key] || {}).forEach((k) => anyEditions.add(+k)));

  const played = (g) => Object.keys(entries[g] || {}).length;
  const has = (g, n) => !!(entries[g] && entries[g][n]);
  const won = (g, n) => { const e = entries[g] && entries[g][n]; return !!e && (e.score || 0) > 0; };

  // Full house = all four played that edition (matches app.js fullHouseDone).
  // Perfect issue = all four WON that edition (matches app.js allWon).
  let fullHouses = 0;
  let perfectIssues = 0;
  anyEditions.forEach((n) => {
    if (ROWS.every(({ key }) => has(key, n))) fullHouses++;
    if (ROWS.every(({ key }) => won(key, n))) perfectIssues++;
  });

  // Full-house streaks. Current = derivedStreak anchored at today over the
  // "all four valid" predicate — the same closure recordDailyCompletion feeds
  // into ledger.fullHouse. Best = longest consecutive run of full-house-valid
  // editions ever.
  const allValidAt = (e) => ROWS.every(({ key }) => gameValidAt(entries, key)(e));
  const fhCurrent = daily.derivedStreak(allValidAt, today).streak;
  const fhValidSet = new Set();
  anyEditions.forEach((n) => { if (allValidAt(n)) fhValidSet.add(n); });
  const fhBest = longestRun(fhValidSet);

  const games = ROWS.map(({ key, label }) => {
    const p = played(key);
    let wins = 0;
    let bestScore = 0;
    Object.values(entries[key] || {}).forEach((e) => {
      if ((e.score || 0) > 0) wins++;
      if ((e.score || 0) > bestScore) bestScore = e.score || 0;
    });
    const current = daily.derivedStreak(gameValidAt(entries, key), today).streak;
    const best = longestRun(validSetFor(entries, key));
    return {
      key, label,
      played: p,
      winRate: p ? Math.round((wins / p) * 100) : 0,
      current, best, bestScore,
    };
  });

  const firstEdition = anyEditions.size ? Math.min(...anyEditions) : null;

  return {
    issuesFiled: anyEditions.size,
    fullHouses, perfectIssues,
    fhCurrent, fhBest,
    firstEdition,
    games,
  };
}

// ---------- flourish (one data-driven line, house voice) ----------
// FLAGGED FOR VOICE REVIEW. Picks the desk (game) with the highest single-issue
// score; falls back to a consolation line when nothing has scored yet.
function flourishLine(data) {
  const scored = data.games.filter((g) => g.bestScore > 0);
  if (!scored.length) {
    return 'Every issue filed is a day the record remembers.';
  }
  let top = scored[0];
  scored.forEach((g) => { if (g.bestScore > top.bestScore) top = g; }); // home order breaks ties
  return `Best byline to date: your ${top.label} desk — ${top.bestScore} in a single issue.`;
}

// ---------- rendering ----------
const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));

function tallyBlock(label, value) {
  return `<div class="ledger-tally"><b>${value}</b><span>${label}</span></div>`;
}

function gameRow(g, empty) {
  const cell = (v) => (empty ? '<td>·</td>' : `<td>${v}</td>`);
  return `<tr>
    <th scope="row">${esc(g.label)}</th>
    ${cell(g.played)}
    ${cell(g.winRate + '%')}
    ${cell(g.current)}
    ${cell(g.best)}
    ${cell(g.bestScore)}
  </tr>`;
}

export function renderLedger() {
  const root = document.getElementById('ledger-body');
  if (!root) return;
  const ledger = store.getDailyLedger();
  const today = Math.max(0, daily.todayIndex());
  const d = computeLedger(ledger, today);
  const empty = d.issuesFiled === 0;

  // Masthead subtitle: an inviting kicker when empty, otherwise the record's
  // opening date. FLAGGED FOR VOICE REVIEW.
  const since = empty
    ? 'History starts at midnight.'
    : `Keeping the record since Issue № ${d.firstEdition}.`;

  const tallies = `
    <div class="ledger-tallies">
      ${tallyBlock('Issues filed', empty ? '—' : d.issuesFiled)}
      ${tallyBlock('Full houses', empty ? '—' : d.fullHouses)}
      ${tallyBlock('Perfect issues', empty ? '—' : d.perfectIssues)}
    </div>`;

  const streaks = `
    <div class="ledger-streaks">
      <div class="ledger-streak"><span>Full-house streak</span><b>${empty ? '—' : d.fhCurrent}</b></div>
      <div class="ledger-streak"><span>Longest ever</span><b>${empty ? '—' : d.fhBest}</b></div>
    </div>`;

  const rows = d.games.map((g) => gameRow(g, empty)).join('');
  const table = `
    <table class="ledger-table">
      <thead>
        <tr>
          <th scope="col" class="ledger-desk">Desk</th>
          <th scope="col">Played</th>
          <th scope="col">Win%</th>
          <th scope="col">Cur.</th>
          <th scope="col">Best</th>
          <th scope="col">High</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
    <p class="ledger-legend">Cur. = current streak · Best = longest run · High = top issue</p>`;

  // The earned stamp: books have their fates. Shown only once a perfect issue
  // exists, and it is the page's single red accent. FLAGGED FOR VOICE REVIEW
  // (Latin: "Habent sua fata libelli" — books have their fates).
  const stamp = (!empty && d.perfectIssues > 0)
    ? `<div class="df-stamp ledger-stamp" aria-label="${d.perfectIssues} perfect issue${d.perfectIssues === 1 ? '' : 's'}">
         Habent sua fata<small>${d.perfectIssues} perfect issue${d.perfectIssues === 1 ? '' : 's'}</small>
       </div>`
    : '';

  const body = empty
    ? `<p class="ledger-empty-line">No issues filed yet.</p>
       <p class="ledger-empty-sub">Play today's four and your record opens here.</p>`
    : `<p class="ledger-flourish">${esc(flourishLine(d))}</p>`;

  root.innerHTML = `
    <div class="ledger-sheet${empty ? ' is-empty' : ''}">
      <div class="ledger-masthead">
        <span class="ledger-kicker">The record</span>
        <h3 class="ledger-title">The Ledger</h3>
        <span class="ledger-since">${esc(since)}</span>
      </div>
      ${tallies}
      ${streaks}
      ${table}
      ${body}
      ${stamp}
    </div>`;
}
