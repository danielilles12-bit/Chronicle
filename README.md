# Chronicle — History Games

Hi Daniel! This is your history games app. It's a **Progressive Web App (PWA)**:
a website that installs onto your iPhone's home screen and then behaves like a
real app — full screen, custom icon, and it works with no internet connection
after the first load.

## What's inside

**The Crossword** — history-themed crosswords in the style of NYT Games:
- 5 Minis (5×5), 3 Midis (7×7), 2 full-size grids
- Tap a square to select it; tap it again to switch between Across and Down
- The bar under the grid shows the current clue; arrows move between clues
- The ☰ button shows all clues; the ✓ button lets you check or reveal
  a square, a word, or the whole puzzle
- A timer runs while you solve; you get the celebration only when every
  square is correct
- Your progress is saved automatically, even if you close the app

**Map of a Life** — guess the historical figure from geography:
- A green dot marks where they were born (with the year); a red ring marks
  where they died (with the year)
- Type the name — spelling doesn't have to be perfect, and nicknames like
  "JFK" work
- Sessions are 10 rounds. Unaided correct answers score 100 points; hints
  cost 25 each, wrong guesses 10; "Reveal" ends a round with 0. Answer
  several in a row for a streak bonus.

## Known limitations and substitutions

- _This section is filled in at the end of the build — see the bottom of the
  file for the final word on what shipped._

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

You now have a "Chronicle" icon on your home screen. Open it from there —
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

## How it was tested

Every shipped crossword is checked by an automated validator (structure,
symmetry, interlock, no junk) and solved end-to-end by an automated browser
pretending to be an iPhone. The map game is played through complete sessions
with typos, hints, wrong answers and reveals, and the exact scores are
verified. The offline behaviour and the install manifest are also tested
automatically. Tests live in `tests/`, screenshots of every screen in
`screenshots/`, and an independent review log in `CRITIC_REPORT.md`.

Data sources: country outlines derived from Natural Earth (public domain);
crossword fill vocabulary assisted by the Crossword Nexus collaborative word
list; all historical facts written and double-checked for this app.
