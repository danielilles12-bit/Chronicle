# Yesternerd launch-day social kit

Ready-to-post PNGs for Daniel's personal Instagram and the Yesternerd account.
The layouts use the shipped Yesternerd wordmark, Antinous mascot, game icons,
fonts, colours and real home-screen capture.

## Recommended launch sequence

### Personal Story

Post `story/01` through `story/05` in order. On frame 5, add Instagram's
**Link** sticker for `https://yesternerd.app/` inside the deliberately empty
lower area. Add an `@yesternerdgame` mention to frame 1 or frame 5.

The five-frame sequence is intentionally personal first, product second:

1. I made a thing.
2. What it is.
3. How the daily format works.
4. Why I made it.
5. Direct invitation to play.

### Main feed / grid

Post `feed/01` through `feed/05` as one carousel, in order. Slide 1 also works
as a standalone launch post if a carousel feels too formal for the personal
account. The exports are 1080 × 1440 (3:4), Instagram's current full-height
portrait photo format.

### Reel

`reel-cover.png` is a cover only; it is not a finished video. It is exported
at 1080 × 1680, a high-resolution version of Instagram's recommended cover
ratio. Keep the wordmark and title centred when Instagram asks you to choose
the profile-grid crop.

## Recommended personal caption

I've made a thing. It's called **Yesternerd** — four little history games,
every day.

There's Face Value, Lifeline, Relic and Thread. A new set opens at midnight,
and everyone gets the same games. It's free, there's no sign-up, and it runs
in your browser.

Play today's set at **yesternerd.app**. If you try it, tell me what you think —
especially what you get stuck on.

## Short caption

I made a daily history game. Well, four of them. **Yesternerd** is live:
free, no sign-up, and about ten minutes a day. Play at **yesternerd.app**.

## Suggested alt text

Launch graphics for Yesternerd, a free browser-based daily history game. The
cream, black, yellow, cyan and magenta designs feature a marble bust wearing
square black glasses, the Yesternerd wordmark, four game icons and a screenshot
of the app. The carousel explains that Face Value, Lifeline, Relic and Thread
refresh every midnight and take about ten minutes to play.

## Export notes

- Stories: 1080 × 1920 (9:16).
- Reel cover: 1080 × 1680 (the recommended 1:1.55 cover ratio, rounded).
- Feed carousel: 1080 × 1440 (3:4).
- Story text and logos stay away from the top and bottom interface zones.
- Frame 5 leaves extra room at the bottom for Instagram's organic Link sticker.
- Source layout: `source/launch-assets.html`.
- Re-export command from the repository root:

  ```sh
  NODE_PATH=/Users/danielilles/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules \
    /Users/danielilles/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node \
    assets/social/launch-day/source/render.cjs
  ```

## Copy provenance

The factual claims and the “showing up, not grinding” line are adapted from
the app's current About and Press pages. This kit does not add launch metrics,
testimonials, rankings or other claims the product cannot yet support.
