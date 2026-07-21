# Dead Famous — Daily History Games

Hi Daniel! This is your history games app (live at **deadfamous.app**). It's a
**Progressive Web App (PWA)**: a website that installs onto your iPhone's home
screen and then behaves like a real app — full screen, custom icon, and it
works with no internet connection after the first load.

## What's inside

Four daily games, one issue per day — the same puzzles for every player on the
same calendar day, everywhere:

**Face Value** — a famous face hides under nine paper scraps; one is already
open. Tear scraps (each tear costs points) and type the name. 5 rounds a day.

**Lifeline** — a world map shows where a historical figure was born (green
dot) and died (red ring), with the years. Type the name — spelling doesn't
have to be perfect, and nicknames like "JFK" work. 5 rounds a day.

**Relic** — like Face Value, but a famous artefact, building or artwork hides
under the scraps. 5 rounds a day.

**Thread** — sixteen clues hide four secret groups of four (in the style of
NYT Connections). One board a day; four wrong guesses and the thread snaps.

**Scoring** — every round is worth 100 points. Tears, clue slips and wrong
guesses each cost some of it; a day's score for a game is the round average,
so every game reads on the same 0–100 dial. Mondays are gentlest and the
difficulty climbs through the week to a Sunday stinker.

**The daily rhythm:**
- The day's puzzles come from a pre-compiled schedule
  (`data/editions.json`, built and approved via `tools/compile_editions.py`).
- Finishing a daily locks it — reopening shows your result, not a replay.
- Completing any one game's daily keeps that game's streak alive; completing
  all four is the celebrated **full house**. A missed day can be repaired
  from the archive within two days.
- **Encore** — after a finished daily, "Encore: 5 more ›" offers a bonus run
  drawn only from puzzles that have already aired. Replayable, never affects
  scores or streaks.
- **Back Issues (The Morgue)** — the trailing 7 aired days, replayable in
  Practice mode (no effect on streaks or the record). Older issues retire.
- **Your Legacy** — the stats page: days played, full houses, streaks and
  bests, reached from the masthead punch card or the home footer.

## Put it on the web, free (one-time, ~10 minutes)

The app is plain files — any free static host works. Easiest path, click by
click, with GitHub Pages:

1. Go to **github.com** and sign in (create the free account if you don't
   have one).
2. Click the **+** in the top-right corner → **New repository**.
3. Name it `chronicle`, leave everything else as it is, click
   **Create repository**.
4. On the next page click **uploading an existing file** (it's a link in the
   "Quick setup" box).
5. On your Mac, open the folder `Desktop/History quiz app` in Finder.
   Press **Cmd+A** to select everything, then drag it all into the upload
   area in your browser. (If the browser complains about hidden files like
   `.git`, just don't include them — selecting all visible files is fine.)
6. Click the green **Commit changes** button and wait for the upload.
7. In the repository, click **Settings** (top bar) → **Pages** (left menu).
8. Under "Branch", choose **main** and click **Save**.
9. Wait ~2 minutes, refresh the page, and GitHub shows your address:
   `https://YOURNAME.github.io/chronicle/`. Open it on your phone — done.

## Add it to your iPhone home screen

1. Open the address above in **Safari** on your iPhone.
2. Tap the **Share** button (the square with the arrow pointing up, middle of
   the bottom bar).
3. Scroll down and tap **Add to Home Screen**.
4. Tap **Add** (top right).

You now have a "Dead Famous" icon on your home screen. Open it from there —
no Safari bars, just the app. After that first visit it works on the plane,
in the basement, anywhere: everything is stored on the phone.

## For the curious: running it locally

In Terminal:

```
cd "$HOME/Desktop/History quiz app"
python3 -m http.server 8000
```

…then open `http://localhost:8000` in a browser. (Opening `index.html`
directly by double-click won't work fully — PWAs need to be served.)

`?dailydate=YYYY-MM-DD` on the URL previews any date's edition (QA only).

## How it's checked

Content going into the schedule passes scripted validators
(`tools/validate_*.py`) and the edition compiler's own collision, repeat-gap
and rights checks; each proposed week gets a human review sheet
(`tools/out/review-*.html`) before approval. The old crossword-era automated
browser suite in `tests/` is retired and a fresh end-to-end suite for the four
live games is planned — until then, changes are verified by hand in the
browser.

Data sources: country outlines derived from Natural Earth (public domain);
portrait and artefact images from Wikimedia Commons with per-image licences
recorded in the data files; all historical facts written and double-checked
for this app.
