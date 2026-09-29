# Weekly content run: instructions for the unattended cloud session

You are running unattended in the cloud, on a fresh checkout of the
Yesternerd repo. Nobody will answer questions. Daniel (the owner) is not
technical and is not watching; he may not look at this for months. Your job
is to keep the app's daily-content schedule topped up with GOOD content,
and to never break the live app.

Read `tools/engine/PLAYBOOK.md` in full before doing anything. It is the
owner's taste and the rules. `HOUSE_RULES.md` is the full ledger of his
rulings; consult it when unsure.

## 0. Setup

```bash
pip install Pillow playwright==1.56.0   # matches the cloud's preinstalled chromium
git config user.name "Yesternerd content engine"
git config user.email "content-engine@yesternerd.app"
git fetch origin
```

Do not run `playwright install`: the cloud sandbox cannot download
browsers, but it ships chromium in `/opt/pw-browsers`, which is the build
Playwright 1.56 expects (CI on GitHub uses 1.60 and downloads its own).
With 1.56 the full suite runs here (21/21 on 29 Sep 2026). If the browser
tests still cannot start, carry on: CI's full browser suite gates
`claude/content-engine` before anything goes live, and the fast validators
below still gate you. The sandbox cannot reach Wikimedia, which is why
this routine never touches images.

Work on a fresh branch from the latest main: `git checkout -B engine origin/main`.

**Did last week's run make it live?** You publish by pushing to the branch
`claude/content-engine`. CI runs the full suite on it, and only when that
passes does it fast-forward `main` and `release` (the live site). If
`git log origin/main..origin/claude/content-engine --oneline` shows
commits, last week's push did NOT go live. Either CI failed, or `main`
moved first and the fast-forward was refused. Check out that branch
(`git checkout -B engine origin/claude/content-engine`), rebase it onto
`origin/main`, run `python3 tests/run_all.py`, and fix any data problem
it names (a bad id, a clashing answer, a missing variant). Then carry on
from step 1 on top of it. If you cannot make it pass in a few steps, go
back to `git checkout -B engine origin/main` and start clean. The
buffer means one lost week costs nothing.

## 1. Is there anything to do?

```bash
python3 tools/engine/autopilot.py status
```

If `days_to_fill` is 0, stop now: print the status and end the run. Do not
commit. This is the normal outcome most weeks.

## 2. Thread boards (only if `thread_boards_to_write` > 0)

Write about 30% more boards than needed, split by the tiers in
`thread_needed`.

1. Spawn **thread-writer** sub-agents (definition in
   `.claude/agents/thread-writer.md`, model Opus), at most 12 boards each.
   Tell each writer to write its output file in small batches as it goes:
   one writer crashed at 17 boards by running out of output length.
   Give each one a different historical territory (ancient / medieval /
   early-modern / 19th c. / 20th c. / cross-era) and an output path under
   `tools/out/engine-audit/thread/`.
2. Spawn **thread-critic** sub-agents (`.claude/agents/thread-critic.md`,
   Opus) on the drafts. Keep only `pass` and `fix` boards (using the
   critic's corrected version).
3. Run `python3 tools/engine/thread_dedup.py` over the survivors together,
   and drop any board with a REJECT tile or a near-duplicate category.
4. Append the survivors to `data/connections.json`: ids continue from the
   highest `conn-NNN`, save it with `tools/engine/jsonio.py` (`save()`
   keeps each file's own indent — they differ, and the wrong one makes a
   20,000-line diff). Add `"<id>": {"ok": true}` under `"thread"` in
   `tools/engine/vetting.json`. Run `python3 tools/validate_boards.py` (0
   errors).

## 3. Draft the new days

```bash
python3 tools/engine/autopilot.py stage
python3 tools/engine/autopilot.py tidy-thread   # held boards + no board twice
python3 tools/engine/autopilot.py merged
```

If `stage` fails with a Shortage, the vetted pool is too thin for the repeat
floor. Retry with fewer days (`stage --days N`). A partial top-up beats none.

## 4. Audit the draft

Let A–B be the new edition numbers (the keys in
`data/editions.proposed.json`).

1. **Pictures:**
   `python3 tools/engine/render_audit_sheets.py tools/out/engine-audit/run --editions A-B --manifest tools/out/engine-audit/merged.json`
   Then spawn one **picture-auditor** sub-agent
   (`.claude/agents/picture-auditor.md`, Sonnet) on those sheets. The pool
   was pre-vetted, so failures should be rare. For any item it fails, set
   `"ok": false` in `tools/engine/vetting.json`, delete
   `data/editions.proposed.json` and go back to step 3 (at most twice).
   Apply any recommended `start` change to that item in
   `data/reveal-who.json` / `data/reveal-what.json` (save via
   `tools/engine/jsonio.py`).
2. **Distractors:**
   `python3 tools/engine/trio_report.py A-B --manifest tools/out/engine-audit/merged.json > tools/out/engine-audit/trios.txt`
   Spawn one **distractor-auditor** sub-agent
   (`.claude/agents/distractor-auditor.md`, Sonnet). Write every `replace`
   verdict (and every `keep`, so the trio is pinned) into
   `tools/fame/mcq_overrides.json` under the right game (save via `tools/engine/jsonio.py`). Pins
   there are the ONLY place trios are curated; never hand-edit `mcq` fields.

## 5. Gate, then ship

```bash
python3 tools/engine/autopilot.py gate      # approves + rebuilds clues + validators
python3 tests/run_all.py                    # full suite, if chromium installed
```

- If `gate` fails at `build_mcq.py` with "override names a same/adjacent-day
  answer" or "curated overrides share the option", replace ONLY the named
  option in `tools/fame/mcq_overrides.json` with another same-kind
  distractor (PLAYBOOK section 4), then re-run `gate`. It reports one clash
  at a time, so loop. Two relics of the same kind on one day (two bridges,
  two crowns) also show up here. Swap one of them in
  `data/editions.json` for a vetted relic at least 42 days from any other
  airing.
- If `gate` fails anywhere else, fix what it names if it is clearly a data slip.
  Otherwise stop without committing anything.
- If the full suite fails on something you changed, fix it or stop.

Then:

```bash
python3 tools/engine/autopilot.py bump
git add -A data tools/fame/mcq_overrides.json tools/engine/vetting.json js/app.js sw.js
git commit -m "Content engine: editions A-B staged unattended (vNNN)"
git push --force origin HEAD:refs/heads/claude/content-engine
```

Force-pushing is allowed ONLY on `claude/content-engine`, which belongs to
this routine. CI (`promote-engine` in `.github/workflows/ci.yml`) tests
that exact commit, then fast-forwards `main` and `release`. The site
updates about 10 minutes later.

Never add `data/editions.proposed.json` or anything under `tools/out/`.
Both are gitignored because they hold unaired answers, and CI fails if they
are tracked.

## 6. Report

End with a short plain-English summary for Daniel (no jargon): which dates
were filled, how many new Thread boards were written, anything benched, and
anything that went wrong. If you stopped early, say exactly why.

## Never

- Never edit an edition dated today or earlier.
- Never fetch, crop or replace images. New pictures need a human.
- Never change app code (`js/`, `css/`, `index.html`) except the BUILD and
  VERSION bump.
- Never touch `reserve` flags. They are the owner's rulings.
- Never push if a gate is red. The schedule is kept 8+ weeks ahead, so
  skipping a week is always safe.
- Never push to `main` or `release` directly, and never force-push any
  branch other than `claude/content-engine`. CI owns `main` and `release`
  for this routine.
