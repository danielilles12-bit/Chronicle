#!/usr/bin/env python3
"""Sharing is text and emoji only (Daniel, 7 Aug 2026).

The app used to draw a 1080x1350 PNG "receipt card" on a canvas and attach it
as a FILE to the native share sheet. That is gone. This suite is the rail that
keeps it gone: it installs a spy Web Share API and proves that every share
surface in the app -- all four games plus the full-house celebration and the
streak obituary -- hands the OS a payload whose ONLY key is `text`, never
touches navigator.canShare, and never constructs a canvas, a Blob or a File.

It also checks the thing the picture was hiding: the shared text itself still
carries its headline, its emoji result rows (aligned, one glyph per round) and
the yesternerd.app link as its last line.

See HOUSE_RULES.md "Sharing (what a share actually is)".
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
import helpers as H  # noqa: E402

N = H.latest_edition()
DATE = H.edition_date(N)
DAY = H.edition_day_label(N)   # shares name the day, not the issue (9 Aug 2026)
LINK = "https://yesternerd.app/"

# A share sheet that always exists and always succeeds, wired to a recorder.
# Also traps every ingredient the deleted image path needed, so a future
# reintroduction fails here even if it never reaches navigator.share.
SPY = r"""
window.__shareSpy = { calls: [], canShare: 0, files: 0, blobs: 0, canvases: 0 };
(function () {
  var S = window.__shareSpy;
  Object.defineProperty(navigator, 'share', {
    configurable: true,
    value: function (d) {
      S.calls.push({
        keys: Object.keys(d || {}).sort(),
        text: (d && d.text) || null,
        hasFiles: !!(d && d.files),
      });
      return Promise.resolve();
    },
  });
  Object.defineProperty(navigator, 'canShare', {
    configurable: true,
    value: function () { S.canShare++; return true; },
  });
  var OrigFile = window.File;
  window.File = function () {
    S.files++;
    return new (Function.prototype.bind.apply(
      OrigFile, [null].concat(Array.prototype.slice.call(arguments))))();
  };
  var toBlob = HTMLCanvasElement.prototype.toBlob;
  HTMLCanvasElement.prototype.toBlob = function () {
    S.blobs++;
    return toBlob.apply(this, arguments);
  };
  var create = document.createElement.bind(document);
  document.createElement = function (tag) {
    if (String(tag).toLowerCase() === 'canvas') S.canvases++;
    return create.apply(null, arguments);
  };
})();
"""

RESET = ("window.__shareSpy.calls.length = 0;"
         "window.__shareSpy.canShare = 0; window.__shareSpy.files = 0;"
         "window.__shareSpy.blobs = 0; window.__shareSpy.canvases = 0;")


def share_and_capture(page, button, label):
    """Tap a share button, wait for the sheet, and return the shared text.

    Fails loudly on anything file-shaped. This is the whole point of the file.
    """
    page.evaluate(RESET)
    page.click(button)
    page.wait_for_function("window.__shareSpy.calls.length > 0", timeout=8000)
    s = page.evaluate("window.__shareSpy")

    assert len(s["calls"]) == 1, (
        "%s: expected exactly one share call, got %d" % (label, len(s["calls"])))
    call = s["calls"][0]
    assert call["keys"] == ["text"], (
        "%s: the share payload must carry text and nothing else, got %r"
        % (label, call["keys"]))
    assert not call["hasFiles"], "%s: a file was attached to the share" % label
    assert s["canShare"] == 0, (
        "%s: navigator.canShare was consulted -- the only reason to ask is to "
        "offer files" % label)
    assert s["files"] == 0, "%s: a File was constructed during the share" % label
    assert s["blobs"] == 0, "%s: canvas.toBlob ran during the share" % label
    assert s["canvases"] == 0, "%s: a canvas was created during the share" % label

    text = call["text"]
    assert text, "%s: shared an empty string" % label
    lines = text.split("\n")
    assert lines[-1].startswith(LINK), (
        "%s: a share must end with the yesternerd.app link, got %r"
        % (label, lines[-1]))
    return text


def emoji_row(text, line_no=1):
    """The result row is always the line under the headline."""
    return text.split("\n")[line_no]


# ---------- the four games ----------
def four_games_share_text_only(p, base):
    """Play all four dailies clean, share each summary. Text only, every time,
    with the headline / emoji row / link shape intact."""
    with H.app(p, init_scripts=(SPY,)) as (page, errors, _ctx):
        H.boot(page, base, DATE)

        # --- Face Value ---
        H.open_daily(page, "who")
        H.dismiss_intro(page, timeout=1200)
        H.play_reveal_daily(page)
        page.wait_for_selector("#rv-sum-share:not([hidden])")
        t = share_and_capture(page, "#rv-sum-share", "Face Value")
        assert t.startswith("FACE VALUE %s \U0001F5BC" % DAY), \
            "Face Value headline changed: %r" % t.split("\n")[0]
        row = emoji_row(t)
        assert row and set(row) <= set("\U0001F7E9\U0001F7E8\U0001F7E5"), \
            "Face Value emoji row has stray glyphs: %r" % row
        assert "pts" in t and "scraps torn" in t, "Face Value score line lost"
        assert "?play=who&ref=share" in t, "Face Value share lost its deep link"
        assert "6-shared-facevalue" in H.gc_events(page)
        page.click("#rv-sum-back")

        # --- Lifeline ---
        H.open_daily(page, "map")
        H.dismiss_intro(page)
        H.play_map_daily(page)
        H.dismiss_install(page)          # game two: the install screen opens
        page.wait_for_selector("#sum-share:not([hidden])")
        t = share_and_capture(page, "#sum-share", "Lifeline")
        assert t.startswith("LIFELINE %s \U0001F5FA" % DAY), \
            "Lifeline headline changed: %r" % t.split("\n")[0]
        row = emoji_row(t)
        assert row and set(row) <= set("✅\U0001F9ED⚰️"), \
            "Lifeline emoji row has stray glyphs: %r" % row
        assert "pts" in t, "Lifeline score line lost"
        assert "?play=map&ref=share" in t, "Lifeline share lost its deep link"
        assert "6-shared-lifeline" in H.gc_events(page)
        page.click("#sum-back")

        # --- Relic ---
        H.open_daily(page, "what")
        H.dismiss_intro(page)
        H.play_reveal_daily(page)
        page.wait_for_selector("#rv-sum-share:not([hidden])")
        t = share_and_capture(page, "#rv-sum-share", "Relic")
        assert t.startswith("RELIC %s \U0001F3FA" % DAY), \
            "Relic headline changed: %r" % t.split("\n")[0]
        row = emoji_row(t)
        assert row and set(row) <= set("\U0001F7E9\U0001F7E8\U0001F7E5"), \
            "Relic emoji row has stray glyphs: %r" % row
        assert "?play=what&ref=share" in t, "Relic share lost its deep link"
        assert "6-shared-relic" in H.gc_events(page)
        page.click("#rv-sum-back")

        # --- Thread ---
        board = H.thread_board(page, N)
        H.open_daily(page, "thread")
        H.dismiss_intro(page)
        H.play_thread_daily(page, board)
        page.wait_for_selector("#conn-sum-share:not([hidden])")
        t = share_and_capture(page, "#conn-sum-share", "Thread")
        assert t.startswith("THREAD %s \U0001F9F5" % DAY), \
            "Thread headline changed: %r" % t.split("\n")[0]
        grid = t.split("\n")[1:-2]       # headline, grid..., human line, link
        assert grid, "Thread share lost its emoji grid"
        widths = set(len(r) for r in grid)
        assert widths == {4}, (
            "Thread grid rows must be four tiles wide and aligned, got %r"
            % [len(r) for r in grid])
        for r in grid:
            assert set(r) <= set("\U0001F7E8\U0001F7E9\U0001F7E6\U0001F7EA⬜"), \
                "Thread grid has stray glyphs: %r" % r
        assert "?play=thread&ref=share" in t, "Thread share lost its deep link"
        assert "6-shared-thread" in H.gc_events(page)

        # --- the full house, on the way home ---
        page.click("#conn-sum-back")
        page.wait_for_selector("#view-daydone:not([hidden])")
        page.wait_for_selector("#dd-share:not([hidden])")
        t = share_and_capture(page, "#dd-share", "full house")
        assert t.startswith("YESTERNERD %s — FULL HOUSE \U0001F3DB" % DAY), \
            "full-house headline changed: %r" % t.split("\n")[0]
        assert "PTS" in emoji_row(t), "full-house score row lost"
        assert t.split("\n")[-1] == LINK + "?ref=share", (
            "the full house has no single game to route to, so it keeps the "
            "bare link: %r" % t.split("\n")[-1])
        assert "6-shared-full-house" in H.gc_events(page)

        H.fail_on_errors(errors, "four_games_share_text_only")
    print("PASS four_games_share_text_only")


# ---------- the wake ----------
THREAD_DETAIL = {"solved": True, "perfect": True, "mistakes": 0,
                 "guesses": [["yellow"] * 4, ["green"] * 4,
                             ["blue"] * 4, ["purple"] * 4]}


def obituary_shares_text_only(p, base):
    """The streak obituary is the other day-done face, and the app's most
    forwarded share. It goes out as text too."""
    last = N - 4
    with H.app(p, init_scripts=(SPY,)) as (page, errors, _ctx):
        for n in (last - 2, last - 1, last):
            H.boot(page, base, H.edition_date(n))
            for g in ("who", "map", "what", "thread"):
                H.seed_completion(page, g, n, score=80,
                                  detail=THREAD_DETAIL if g == "thread" else [])
        H.boot(page, base, H.edition_date(last + 4))    # beyond repair
        page.wait_for_selector("#view-daydone:not([hidden])")
        page.wait_for_selector("#dd-share:not([hidden])")

        t = share_and_capture(page, "#dd-share", "obituary")
        assert t.startswith("YESTERNERD ⚰"), \
            "obituary headline changed: %r" % t.split("\n")[0]
        assert "3-day streak died" in t, "the wake stopped naming the run: %r" % t
        assert "MEMENTO MORI" in t, "the wake lost its sign-off"
        assert t.split("\n")[-1] == LINK + "?ref=share", (
            "obituary share must end with the bare link: %r" % t.split("\n")[-1])
        assert "6-shared-obituary" in H.gc_events(page)

        H.fail_on_errors(errors, "obituary_shares_text_only")
    print("PASS obituary_shares_text_only")


# ---------- the source itself ----------
def source_has_no_image_path():
    """A grep rail, because the browser tests can only prove that the paths
    they walk are clean. No share module may name a file API at all."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    banned = ("canShare", "toBlob", "new File(", "getContext(", "drawCard",
              "files:", "createElement('canvas')")
    bad = []
    for name in ("sharecard.js", "app.js", "mapgame.js", "revealgame.js",
                 "connectionsgame.js"):
        path = os.path.join(root, "js", name)
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                for b in banned:
                    if b in line:
                        bad.append("js/%s:%d %s -> %s" % (name, i, b, line.strip()))
    assert not bad, ("the image-receipt machinery is creeping back:\n  "
                     + "\n  ".join(bad))
    print("PASS source_has_no_image_path")


TESTS = [four_games_share_text_only, obituary_shares_text_only]


def main():
    source_has_no_image_path()
    failed = []
    with H.server() as base:
        with sync_playwright() as p:
            for t in TESTS:
                try:
                    t(p, base)
                except Exception as e:
                    failed.append(t.__name__)
                    print("FAIL %s: %s" % (t.__name__, e))
    print("\n%d/%d share scenarios passed" % (len(TESTS) - len(failed), len(TESTS)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
