# The attic

Retired code, kept for the record (P4.1, Session 6 — 2026-07-21). Nothing in
here runs, ships, or is tested. `git mv` preserved each file's history.

## Why these are here

- `tools/` — crossword-era tooling (`validate_puzzles`, `fill_grid`,
  `fill_partial`, `history_words`, `wordlist_ext`, `swap_fulls`). The
  crossword game was retired from the app; its data files are long gone.
- `out/` — generated crossword grids (`minis`, `midis`, `elevens`, `fulls`).
- `tests/` — the Chronicle-era Playwright suite. These failed on selectors
  that no longer exist (documented 2026-07-16: stale, not regressions) and
  are superseded by the Dead Famous suite in `tests/` (test_smoke_core,
  test_daily_flow, test_resilience). `audit_replay.py` also depended on a
  scratchpad file from a finished tuning session.

If something in here turns out to be needed, `git mv` it back out.
