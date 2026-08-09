#!/usr/bin/env python3
"""Copy-review builder — a picture-plus-text audit sheet for Daniel.

WHY THIS EXISTS. A flat list of strings is useless for judging copy: nobody
can tell if "Tap to retry" is fine without seeing the card it sits on. This
script drives the REAL app with Playwright, screenshots every screen and
state at 375px wide, reads back the exact copy showing on each one, and
writes ONE self-contained HTML page — audit/copy-review.html — with the
picture beside editable text boxes, grouped by how often a player actually
sees that screen (Tier 1 = every session, down to Tier 3 = rare).

RE-RUN FROM A CLEAN CHECKOUT WITH:

    python3 tools/build_copy_review.py

Requires Python 3.9+, Playwright (`pip install playwright && playwright
install chromium`) and Pillow (already a project dependency — see
tools/make_icons.py). No Node, no build step; this only reads js/, the HTML
pages and data/, and writes audit/copy-review.html. It never touches
application source.

SCOPE NOTES (see the brief this was built against):
  - Screenshots are taken to a throwaway temp directory and embedded as
    data: URIs in the final page — nothing is left on disk outside audit/.
  - The calendar/archive screens (#view-archive, #archive-picker,
    #archive-filters) are skipped: another workstream is deleting them and
    they no longer exist in this checkout at all (verified by grep before
    writing this).
  - The Home section is marked PROVISIONAL in the generated page: a
    concurrent workstream is rebuilding Home, so its copy will move under
    this script and the page should be regenerated after that lands.
  - Baked-into-artwork copy (stamp PNGs) is included and marked read-only,
    per Daniel's explicit ask to keep the whole stamp vocabulary in scope.
"""
import base64
import io
import os
import re
import sys
import tempfile
import time
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TESTS_DIR = os.path.join(ROOT, "tests")
sys.path.insert(0, TESTS_DIR)

import helpers as H  # noqa: E402  (tests/helpers.py — server + app + game-driving helpers)
from playwright.sync_api import sync_playwright  # noqa: E402
from PIL import Image  # noqa: E402

OUT_PATH = os.path.join(ROOT, "audit", "copy-review.html")
SHOT_W = 375
SHOT_H = 820
JPEG_QUALITY = 75

N = H.latest_edition()          # the newest manifest edition — a real, aired "today"
DATE = H.edition_date(N)

SHOT_DIR = tempfile.mkdtemp(prefix="yesternerd-copy-review-")
print("Screenshots (temporary, embedded then discarded):", SHOT_DIR)

# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
_shot_seq = [0]


def esc(s):
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def esc_attr(s):
    """esc() plus quote-escaping, for use inside a double-quoted HTML
    attribute (e.g. data-original="..."). Without this, any copy string
    containing a literal " (there are several — "Report a problem",
    "3 choices", quoted analytics event names) truncates the attribute early
    and corrupts everything after it on that line."""
    return esc(s).replace('"', "&quot;")


def new_ctx(p, **kw):
    """A fresh browser + isolated profile at 375px wide, mobile-flavoured,
    with the same GC-stub / external-host-blocking / error-capture hygiene
    the Python test suite uses (tests/helpers.py:app)."""
    context_args = dict(kw.pop("context_args", None) or {})
    context_args.setdefault("viewport", {"width": SHOT_W, "height": SHOT_H})
    context_args.setdefault("device_scale_factor", 1)
    context_args.setdefault("is_mobile", True)
    context_args.setdefault("has_touch", True)
    return H.app(p, context_args=context_args, **kw)


def shot(page, name, full_page=True):
    """Screenshot straight to JPEG at quality 75, already 375px wide (no
    resize needed: device_scale_factor is pinned to 1 in new_ctx)."""
    _shot_seq[0] += 1
    path = os.path.join(SHOT_DIR, "%03d-%s.jpg" % (_shot_seq[0], re.sub(r"[^a-z0-9]+", "-", name.lower())))
    page.screenshot(path=path, type="jpeg", quality=JPEG_QUALITY, full_page=full_page)
    # Pillow pass: guarantee the width really is 375 regardless of any stray
    # device pixel ratio, and strip incidental metadata. Cheap insurance.
    im = Image.open(path).convert("RGB")
    if im.width != SHOT_W:
        h = round(im.height * SHOT_W / im.width)
        im = im.resize((SHOT_W, h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=JPEG_QUALITY)
    data = buf.getvalue()
    return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")


def txt(page, sel):
    """Trimmed innerText of the first match, or '' if it isn't there/visible."""
    try:
        loc = page.locator(sel).first
        if loc.count() == 0:
            return ""
        return (loc.inner_text() or "").strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# the screen/field model
# ---------------------------------------------------------------------------
SCREENS = []  # list of screen dicts, appended to as we go


def add_screen(id_, tier, title, image, fields, note=None, provisional=False):
    SCREENS.append({
        "id": id_, "tier": tier, "title": title, "image": image,
        "fields": fields, "note": note, "provisional": provisional,
    })


_field_seq = [0]


def field(label, value, file, line, note=None):
    _field_seq[0] += 1
    return {
        "uid": "f%d" % _field_seq[0], "label": label, "value": value or "",
        "file": file, "line": line, "note": note,
    }


def set_note(n):
    """A shared caption glued onto the first field of a rotating/banded set,
    so the group reads as one thing in the generated page."""
    return n


# ===========================================================================
# TIER 1 — every session
# ===========================================================================

def capture_home_screens():
    with sync_playwright() as p:
        # ---- stranger (first-ever visitor) ----
        with new_ctx(p) as (page, errors, _ctx):
            H.boot(page, base, DATE)
            page.wait_for_selector("#stranger-hero:not([hidden])")
            img = shot(page, "home-stranger")
            add_screen(
                "home-stranger", 1, "Home — first-time visitor",
                img,
                [
                    field("Headline", txt(page, ".stranger-headline"), "index.html", 162),
                    field("Caption", txt(page, ".stranger-caption"), "index.html", 163),
                    field("Demo image alt text", page.get_attribute(".stranger-demo", "alt") or "",
                          "index.html", 167,
                          note="Screen-reader text for the frozen demo board image — not visible copy, "
                               "but read aloud."),
                    field("Play button", txt(page, "#stranger-play"), "index.html", 168),
                    field("Reassurance line", txt(page, ".stranger-reassure"), "index.html", 169),
                    field("\"Also in today's issue\" label", txt(page, ".stranger-also"), "index.html", 170),
                    field("Footer", txt(page, ".home-foot"), "index.html", 206,
                          note="\"Works offline\", the Your Legacy / Sound-on toggles, and the build tag "
                               "all live in one footer line."),
                ],
            )
            H.fail_on_errors([e for e in errors if "assets/img" not in e], "home-stranger")

        # ---- regular player: today in progress, punch card, day cards, letters plate ----
        with new_ctx(p) as (page, errors, _ctx):
            H.boot(page, base, DATE)
            H.seed_completion(page, "who", N, score=72)
            H.boot(page, base, DATE)  # repaint Home from the ledger we just wrote
            page.wait_for_selector("#letters-plate:not([hidden])")
            img = shot(page, "home-regular")
            add_screen(
                "home-regular", 1, "Home — returning player",
                img,
                [
                    field("Dateline (edition number + weekday)", txt(page, "#dateline"), "js/app.js", 366,
                          note="Template: “№ {edition} // {Weekday}” — datelineHTML()."),
                    field("Face Value card status", txt(page, '[data-hero="who"] [data-status]'),
                          "js/app.js", 209,
                          note="statusLabel(): “Done · {score} pts” done, "
                               "“Resume today’s puzzle” mid-round, blank otherwise."),
                    field("Face Value tagline", txt(page, '[data-hero="who"] .hero-tagline'),
                          "js/app.js", 165),
                    field("Lifeline tagline", txt(page, '[data-hero="map"] .hero-tagline'),
                          "js/app.js", 172),
                    field("Relic tagline", txt(page, '[data-hero="what"] .hero-tagline'),
                          "js/app.js", 180),
                    field("Thread tagline", txt(page, '[data-hero="thread"] .hero-tagline'),
                          "js/app.js", 188),
                    field("Done day-card label", "{points} pts", "js/app.js", 386,
                          note="dayCardLabels(). A past day nobody has opened carries NO status line "
                               "at all — silence, not a word (Daniel, 7 Aug 2026), so there is nothing "
                               "to edit for that state."),
                    field("In-progress day-card label", "Resume", "js/app.js", 388),
                    field("Letters plate heading", txt(page, ".lt-head"), "index.html", 189),
                    field("Letters plate sub-line", txt(page, ".lt-sub"), "index.html", 190),
                    field("Letters plate button", txt(page, "#lt-btn"), "js/feedback.js", 143,
                          note="Swaps to “Email the editor →” offline."),
                    field("Letters plate stamp word", "Yesternerd", "index.html", 197),
                    field("Footer", txt(page, ".home-foot"), "index.html", 206),
                ],
            )
            H.fail_on_errors([e for e in errors if "assets/img" not in e], "home-regular")


def capture_facevalue_flow():
    with sync_playwright() as p:
        with new_ctx(p) as (page, errors, _ctx):
            H.boot(page, base, DATE)
            H.open_daily(page, "who")
            # Face Value skips the first-run intro on purpose (teach-by-doing,
            # revealgame.js) — dismiss_intro is a no-op here, kept for safety.
            H.dismiss_intro(page, timeout=1200)
            page.wait_for_selector("#view-reveal:not([hidden])")
            page.wait_for_function("__CHRONICLE_TEST__.revealRound !== undefined")

            img_play = shot(page, "fv-play")
            add_screen(
                "fv-play", 1, "Face Value — round in play",
                img_play,
                [
                    field("Prompt", txt(page, "#rv-prompt"), "js/revealgame.js", 825,
                          note="“Who is this? Tear towards the answer.” for a face, "
                               "“What is this?…” for Relic."),
                    field("Worth readout", txt(page, "#rv-worth"), "js/revealgame.js", 483,
                          note="“WORTH: {n} PTS · each tear −10”, changing near the "
                               "floor of 10 (revealgame.js:477-483)."),
                    field("Input placeholder", page.get_attribute("#rv-input", "placeholder") or "",
                          "index.html", 353),
                    field("Guess button", txt(page, "#rv-guess-btn"), "index.html", 354),
                    field("Clue A (Face Value)", txt(page, "#rv-clue-a"), "js/revealgame.js", 114,
                          note="“Claim to fame” for Face Value, “First letters” for Relic."),
                    field("Clue B (Face Value)", txt(page, "#rv-clue-b"), "js/revealgame.js", 115,
                          note="“Lived to/from” for Face Value, “Era” for Relic."),
                    field("Rescue button", txt(page, "#rv-mcq"), "index.html", 359,
                          note="“3 choices · round worth {n}” — MCQ_COST=80, revealgame.js:33."),
                    field("Scrap tear aria-label", "Tear scrap {n}", "js/revealgame.js", 508),
                    field("Blocked-tap: already torn", "Already torn.", "js/revealgame.js", 524),
                    field("Blocked-tap: not adjacent", "Choose a scrap next to an open space.",
                          "js/revealgame.js", 525),
                    field("Blocked-tap: rescue open", "Tearing is closed — pick one of the three.",
                          "js/revealgame.js", 526,
                          note=set_note("The three “blocked tap” lines above are a set: only one "
                                        "shows at a time, chosen by why the tap failed.")),
                ],
            )

            # First guess in this browser session, in a typed-answer game:
            # the once-per-game warning sheet intercepts it.
            name = page.evaluate("__CHRONICLE_TEST__.revealRound.name")
            page.fill("#rv-input", name)
            page.click("#rv-guess-btn")
            page.wait_for_selector("#guess-warn:not([hidden])")
            img_warn = shot(page, "fv-guesswarn")
            add_screen(
                "fv-guesswarn", 1, "First-guess warning (any typed-answer game, once)",
                img_warn,
                [
                    field("Heading", txt(page, "#guess-warn h3"), "index.html", 527),
                    field("Body", txt(page, "#guess-warn-copy"), "js/guesswarn.js", 44,
                          note="Template: “Are you sure? A wrong guess costs {cost} points.” Cost is 15 "
                               "in Face Value/Lifeline, 15 in Relic."),
                    field("Confirm button", txt(page, "#guess-warn-go"), "index.html", 530),
                    field("Cancel button", txt(page, "#guess-warn-back"), "js/guesswarn.js", 50,
                          note="“Keep tearing” in Face Value and Relic; “Keep looking” in Lifeline, "
                               "which has nothing to tear."),
                ],
                note="Fires once per game (Face Value, Lifeline, Relic each ask separately) on the very "
                     "first guess a player submits, ever, on this device.",
            )
            page.click("#guess-warn-go")
            page.wait_for_selector("#guess-warn", state="hidden")
            page.wait_for_selector("#rv-next:not([hidden])")

            img_correct = shot(page, "fv-verdict-correct")
            add_screen(
                "fv-verdict-correct", 1, "Face Value — round verdict (correct)",
                img_correct,
                [
                    field("Verdict badge (this round)", txt(page, "#rv-badge b"), "js/revealgame.js", 38,
                          note=set_note("CORRECT_VERDICTS — the badge rotates through these six by round "
                                        "number, never at random, so a reloaded round always shows the "
                                        "same word.")),
                    field("Verdict 2", "History remembers.", "js/revealgame.js", 39),
                    field("Verdict 3", "Straight to the record.", "js/revealgame.js", 39),
                    field("Verdict 4", "Ink it.", "js/revealgame.js", 40),
                    field("Verdict 5", "On the record.", "js/revealgame.js", 40),
                    field("Verdict 6", "First take.", "js/revealgame.js", 40),
                    field("Feedback line", txt(page, "#rv-feedback"), "js/revealgame.js", 1028,
                          note="Template: “{name} — {blurb} +{n} pts”, with a streak-bonus "
                               "or “(picked from three)” aside where it applies."),
                    field("Credit button aria-label", "Photo credit", "index.html", 340),
                    field("Next button (mid-run)", "Next ›", "js/revealgame.js", 1046),
                    field("Next button (last round)", "See results ›", "js/revealgame.js", 1046),
                ],
            )

            page.click("#rv-next")
            page.wait_for_selector("#view-reveal:not([hidden])")
            page.wait_for_function("__CHRONICLE_TEST__.revealRound !== undefined")
            # Deliberately wrong: a text guess only docks the round, it does not
            # resolve it (the player keeps guessing) — captured as its own state.
            page.fill("#rv-input", "Definitely Not The Answer")
            page.click("#rv-guess-btn")
            page.wait_for_selector("#rv-wrong-note:not([hidden])")
            img_wrongguess = shot(page, "fv-wrong-guess")
            add_screen(
                "fv-wrong-guess", 1, "Face Value — a wrong guess (round still open)",
                img_wrongguess,
                [
                    field("First-wrong-guess teaching note", txt(page, "#rv-wrong-note"),
                          "js/revealgame.js", 1238,
                          note="“Not them — −15” in Face Value/Lifeline, “Not that "
                               "— −15” in Relic. Shown as a one-shot the FIRST wrong guess "
                               "anywhere in the app, then only the strikethrough chip carries it."),
                    field("Guess chip penalty", "-15", "js/revealgame.js", 148),
                ],
            )
            # Resolve this round as a loss via the "3 choices" rescue, picking a
            # WRONG option, to show the wrong-verdict bank + the 0pt reveal.
            page.click("#rv-mcq")
            page.wait_for_selector("#rv-mcq-chips:not([hidden])")
            correct_name = page.evaluate("__CHRONICLE_TEST__.revealRound.name")
            wrong_btn = page.locator("#rv-mcq-chips button").filter(has_not_text=correct_name).first
            wrong_btn.click()
            page.wait_for_selector("#rv-next:not([hidden])")
            img_wrong = shot(page, "fv-verdict-wrong")
            add_screen(
                "fv-verdict-wrong", 1, "Face Value — round verdict (wrong / gave up)",
                img_wrong,
                [
                    field("Verdict badge (this round)", txt(page, "#rv-badge b"), "js/revealgame.js", 42,
                          note=set_note("WRONG_VERDICTS — same rotation rule as the correct set above.")),
                    field("Verdict 2", "The dead disagree.", "js/revealgame.js", 43),
                    field("Verdict 3", "The record says no.", "js/revealgame.js", 43),
                    field("Verdict 4", "Citation needed.", "js/revealgame.js", 44),
                    field("Verdict 5", "Not them.", "js/revealgame.js", 44),
                    field("Feedback line", txt(page, "#rv-feedback"), "js/revealgame.js", 1031,
                          note="Template: “It was {name} — {blurb} 0 pts”."),
                ],
            )
            page.click("#rv-next")
            page.wait_for_selector("#view-reveal:not([hidden])")
            # Finish the run correctly.
            while True:
                page.wait_for_selector("#view-reveal:not([hidden])")
                page.wait_for_function("__CHRONICLE_TEST__.revealRound !== undefined")
                nm = page.evaluate("__CHRONICLE_TEST__.revealRound.name")
                page.fill("#rv-input", nm)
                page.click("#rv-guess-btn")
                page.wait_for_selector("#rv-next:not([hidden])")
                last = "results" in page.inner_text("#rv-next").lower()
                page.click("#rv-next")
                if last:
                    break
            page.wait_for_selector("#view-revealsum:not([hidden])")
            img_sum = shot(page, "fv-summary")
            add_screen(
                "fv-summary", 1, "Face Value — end-of-round summary",
                img_sum,
                [
                    field("Receipt header", txt(page, "#view-revealsum [data-receipt-head]"),
                          "js/revealgame.js", 1053, note="“Yesternerd · Face Value · №{n}”."),
                    field("Total label", "Total:", "index.html", 278),
                    field("Remark band 1 (≥88)", "A connoisseur of the ages.", "js/revealgame.js", 1064,
                          note=set_note("Remarks band — one line shown depending on the score, recalibrated "
                                        "28 Jul 2026 for the 3-round daily.")),
                    field("Remark band 2 (≥60)", "A sharp eye for history.", "js/revealgame.js", 1065),
                    field("Remark band 3 (≥35)", "A good eye — keep looking.", "js/revealgame.js", 1066),
                    field("Remark band 4 (≥15)", "The details are coming into focus.", "js/revealgame.js", 1067),
                    field("Remark band 5 (0+)", "Every expert starts by squinting.", "js/revealgame.js", 1068),
                    field("Turn-the-page button", txt(page, "#rv-sum-turn") or "Play the next puzzle ›",
                          "js/app.js", 503, note="“Call it a day ›” once every daily is played."),
                    field("Share button", "Share the tear-up", "index.html", 396),
                    field("Encore button", txt(page, "#rv-sum-encore") or "Encore: {Weekday} ›",
                          "js/app.js", 357),
                    field("Play again button", "Play again", "index.html", 398),
                    field("Home button", "Home", "index.html", 399),
                    field("Report-a-problem link", "Report a problem", "index.html", 401),
                    field("Stamp — real score (baked into artwork, read-only)",
                          "Alea iacta fest", "index.html", 384,
                          note="This is NOT live text — it is drawn into "
                               "assets/brand/stamp-alea-iacta-fest.png. Changing the wording means "
                               "re-exporting that artwork, not editing a string. The value shown here is "
                               "the image's alt text."),
                    field("Stamp — zero score", "Damnatio memoriae / struck from the record",
                          "index.html", 386, note="Live text, unlike the stamp above."),
                ],
            )
            H.fail_on_errors([e for e in errors if "assets/img" not in e], "facevalue-flow")

            # Re-open the now-completed daily: the solution recap only shows
            # on re-entry, never on the live finish that just happened.
            page.click("#rv-sum-home")
            page.wait_for_selector("#view-home:not([hidden])")
            H.open_daily(page, "who")
            page.wait_for_selector("#view-revealsum:not([hidden])")
            page.wait_for_selector("#rv-sum-solution:not([hidden])")
            img_sol = shot(page, "fv-solution")
            add_screen(
                "fv-solution", 2, "Face Value — reopened result (solution recap)",
                img_sol,
                [
                    field("Solution heading", txt(page, ".sum-solution-head"), "js/revealgame.js", 1113),
                    field("Per-round name + blurb", txt(page, ".sol-round .sol-name"), "js/revealgame.js", 1128),
                ],
                note="Only appears when re-opening an ALREADY finished daily (from Home or the Archive) "
                     "— never on the live finish, which just watched the same reveal happen.",
            )


def capture_lifeline_flow():
    with sync_playwright() as p:
        with new_ctx(p) as (page, errors, _ctx):
            H.boot(page, base, DATE)
            H.open_daily(page, "map")
            intro_seen = H.dismiss_intro(page, timeout=1500)
            if intro_seen:
                pass  # captured separately below on a fresh context
            page.wait_for_selector("#view-map:not([hidden])")
            page.wait_for_function("__CHRONICLE_TEST__.mapRound !== undefined")
            img_play = shot(page, "map-play")
            add_screen(
                "map-play", 1, "Lifeline — round in play",
                img_play,
                [
                    field("Question line", txt(page, "#map-question"), "index.html", 245),
                    field("Worth readout", txt(page, "#map-worth"), "js/mapgame.js", 379),
                    field("Input placeholder", page.get_attribute("#map-input", "placeholder") or "",
                          "index.html", 249),
                    field("Guess button", txt(page, "#map-guess-btn"), "index.html", 250),
                    field("Hint: Claim to fame", txt(page, "#hint-occ"), "index.html", 253),
                    field("Hint: Initials", txt(page, "#hint-ini"), "index.html", 254),
                    field("Rescue: 3 choices", txt(page, "#map-mcq"), "index.html", 255),
                ],
            )
            # First guess in this session: warn, confirm, then a deliberate
            # WRONG guess to capture the wrong-guess chip + note.
            page.fill("#map-input", "Nobody In Particular")
            page.click("#map-guess-btn")
            H.dismiss_guess_warn(page)
            page.wait_for_selector("#map-wrong-note:not([hidden])")
            img_wrong = shot(page, "map-wrong")
            add_screen(
                "map-wrong", 1, "Lifeline — wrong guess",
                img_wrong,
                [
                    field("Wrong-guess note", txt(page, "#map-wrong-note"), "js/mapgame.js", 977,
                          note="“Not them — −15”, the same one-shot teaching pattern as "
                               "Face Value/Relic."),
                    field("Guess chip penalty", "-15", "js/mapgame.js", 438),
                ],
            )
            name = page.evaluate("__CHRONICLE_TEST__.mapRound.name")
            page.fill("#map-input", name)
            page.click("#map-guess-btn")
            page.wait_for_selector("#map-next:not([hidden])")
            img_verdict = shot(page, "map-verdict")
            add_screen(
                "map-verdict", 1, "Lifeline — round verdict (correct)",
                img_verdict,
                [
                    field("Feedback line", txt(page, "#map-feedback"), "js/mapgame.js", 741,
                          note="Template: “{name} — born {place}, {year}; died {place}, {year}. "
                               "+{n} pts”, plus an optional fun-fact line."),
                    field("Next button (mid-run)", "Next round ›", "js/mapgame.js", 771),
                    field("Next button (last round)", "See results ›", "js/mapgame.js", 771),
                ],
            )
            last_after_verdict = "results" in page.inner_text("#map-next").lower()
            page.click("#map-next")
            while not last_after_verdict:
                page.wait_for_selector("#view-map:not([hidden])")
                page.wait_for_function("__CHRONICLE_TEST__.mapRound !== undefined")
                nm = page.evaluate("__CHRONICLE_TEST__.mapRound.name")
                page.fill("#map-input", nm)
                page.click("#map-guess-btn")
                page.wait_for_selector("#map-next:not([hidden])")
                last = "results" in page.inner_text("#map-next").lower()
                page.click("#map-next")
                if last:
                    break
            page.wait_for_selector("#view-mapsum:not([hidden])")
            img_sum = shot(page, "map-summary")
            add_screen(
                "map-summary", 1, "Lifeline — end-of-round summary",
                img_sum,
                [
                    field("Receipt header", txt(page, "#view-mapsum [data-receipt-head]"),
                          "js/mapgame.js", 778),
                    field("Remark band 1 (≥88)", "Immortalised.", "js/mapgame.js", 786,
                          note=set_note("Remarks band — one line by score, mirrors Face Value/Relic's "
                                        "bands but Lifeline-flavoured.")),
                    field("Remark band 2 (≥60)", "A household name.", "js/mapgame.js", 787),
                    field("Remark band 3 (≥35)", "Fifteen minutes of fame.", "js/mapgame.js", 788),
                    field("Remark band 4 (≥15)", "Getting warm.", "js/mapgame.js", 789),
                    field("Remark band 5 (0+)", "A footnote.", "js/mapgame.js", 790),
                    field("Share button", "Share the run", "index.html", 292),
                ],
            )
            H.fail_on_errors([e for e in errors if "assets/img" not in e], "lifeline-flow")

        # Lifeline's first-run intro, captured fresh (it is skipped by the
        # flow above once we've already dismissed it).
        with new_ctx(p) as (page, errors, _ctx):
            H.boot(page, base, DATE)
            H.open_daily(page, "map")
            page.wait_for_selector("#intro-card:not([hidden])")
            img_intro = shot(page, "map-intro")
            add_screen(
                "map-intro", 2, "Lifeline — first-run rules card",
                img_intro,
                [
                    field("Kicker", txt(page, "#intro-kicker"), "js/app.js", 529),
                    field("Title", txt(page, "#intro-title"), "js/app.js", 532),
                    field("Body", txt(page, "#intro-copy"), "js/app.js", 533),
                    field("Body (pricing)", txt(page, "#intro-copy2"), "js/app.js", 534),
                    field("Play button", txt(page, "#intro-play"), "js/app.js", 586,
                          note="Template: “Play №{n} ›”. Reopened from the topbar “?” "
                               "it instead says “Got it ›” (js/app.js:606)."),
                ],
                note="Shown once, before a game's very first daily; the topbar “?” reopens the "
                     "same card any time as a dismissable overlay.",
            )
            H.fail_on_errors([e for e in errors if "assets/img" not in e], "lifeline-intro")


def capture_relic_flow():
    with sync_playwright() as p:
        with new_ctx(p) as (page, errors, _ctx):
            H.boot(page, base, DATE)
            H.open_daily(page, "what")
            page.wait_for_selector("#intro-card:not([hidden])")
            img_intro = shot(page, "what-intro")
            add_screen(
                "what-intro", 2, "Relic — first-run rules card",
                img_intro,
                [
                    field("Kicker", txt(page, "#intro-kicker"), "js/app.js", 546),
                    field("Title", txt(page, "#intro-title"), "js/app.js", 549),
                    field("Body", txt(page, "#intro-copy"), "js/app.js", 550),
                    field("Body (pricing)", txt(page, "#intro-copy2"), "js/app.js", 551),
                ],
                note="Same shared overlay as Lifeline's, with Relic's own art, colour and copy.",
            )
            H.dismiss_intro(page, timeout=2500)
            page.wait_for_selector("#view-reveal:not([hidden])")
            page.wait_for_function("__CHRONICLE_TEST__.revealRound !== undefined")
            img_play = shot(page, "what-play")
            add_screen(
                "what-play", 1, "Relic — round in play",
                img_play,
                [
                    field("Prompt", txt(page, "#rv-prompt"), "js/revealgame.js", 825),
                    field("Clue A (Relic)", txt(page, "#rv-clue-a"), "js/revealgame.js", 119,
                          note="“First letters” — Face Value's equivalent is “Claim to fame”."),
                    field("Clue B (Relic)", txt(page, "#rv-clue-b"), "js/revealgame.js", 120,
                          note="“Era” — Face Value's equivalent is “Lived to/from”. Hidden "
                               "entirely for an undatable relic."),
                ],
            )
            page.click("#rv-mcq")
            page.wait_for_selector("#rv-mcq-chips:not([hidden])")
            img_mcq = shot(page, "what-mcq")
            add_screen(
                "what-mcq", 1, "Relic — \"3 choices\" rescue open",
                img_mcq,
                [
                    field("Three option chips", txt(page, "#rv-mcq-chips"), "js/revealgame.js", 950,
                          note="The three names are the round's own answer plus two curated distractors "
                               "(tools/build_mcq.py) — not editable copy, listed for completeness."),
                ],
                note="Opening this closes tearing and both clue slips for the rest of the round "
                     "(the “the rescue closes the shop” rule).",
            )
            item_name = page.evaluate("__CHRONICLE_TEST__.revealRound.name")
            page.click('#rv-mcq-chips button:has-text("%s")' % item_name.replace('"', ""))
            page.wait_for_selector("#rv-next:not([hidden])")
            last_after_mcq = "results" in page.inner_text("#rv-next").lower()
            page.click("#rv-next")
            while not last_after_mcq:
                page.wait_for_selector("#view-reveal:not([hidden])")
                page.wait_for_function("__CHRONICLE_TEST__.revealRound !== undefined")
                nm = page.evaluate("__CHRONICLE_TEST__.revealRound.name")
                page.fill("#rv-input", nm)
                page.click("#rv-guess-btn")
                H.dismiss_guess_warn(page)
                page.wait_for_selector("#rv-next:not([hidden])")
                last = "results" in page.inner_text("#rv-next").lower()
                page.click("#rv-next")
                if last:
                    break
            page.wait_for_selector("#view-revealsum:not([hidden])")
            img_sum = shot(page, "what-summary")
            add_screen(
                "what-summary", 1, "Relic — end-of-round summary",
                img_sum,
                [
                    field("Receipt header", txt(page, "#view-revealsum [data-receipt-head]"),
                          "js/revealgame.js", 1053),
                    field("Share button", "Share the tear-up", "index.html", 396),
                ],
                note="Shares Face Value's remark bands and stamps — see the Face Value summary "
                     "section rather than repeating them here.",
            )
            H.fail_on_errors([e for e in errors if "assets/img" not in e], "relic-flow")


def capture_thread_flow():
    with sync_playwright() as p:
        with new_ctx(p) as (page, errors, _ctx):
            H.boot(page, base, DATE)
            board = H.thread_board(page, N)
            H.open_daily(page, "thread")
            page.wait_for_selector("#intro-card:not([hidden])")
            img_intro = shot(page, "thread-intro")
            add_screen(
                "thread-intro", 2, "Thread — first-run rules card",
                img_intro,
                [
                    field("Kicker", txt(page, "#intro-kicker"), "js/app.js", 520),
                    field("Title", txt(page, "#intro-title"), "js/app.js", 523),
                    field("Body", txt(page, "#intro-copy"), "js/app.js", 524),
                    field("Body (pricing)", txt(page, "#intro-copy2"), "js/app.js", 525),
                ],
            )
            H.dismiss_intro(page, timeout=2500)
            page.wait_for_selector("#view-conn:not([hidden])")
            img_play = shot(page, "thread-play")
            add_screen(
                "thread-play", 1, "Thread — board in play",
                img_play,
                [
                    field("Puzzle title (topbar)", txt(page, "#conn-puzzle-title"), "js/connectionsgame.js", 121,
                          note="Set per edition from data/connections.json — content, not app copy, "
                               "included here only for context."),
                    field("Shuffle button", txt(page, "#conn-shuffle"), "index.html", 417),
                    field("Deselect-all button", txt(page, "#conn-deselect"), "index.html", 418),
                    field("Submit button", txt(page, "#conn-submit"), "index.html", 419),
                ],
            )
            # A deliberately wrong guess: 3 from the first group + 1 from the second.
            g0, g1 = board["groups"][0], board["groups"][1]
            wrong_pick = g0["items"][:3] + [g1["items"][0]]
            H.click_tiles(page, wrong_pick)
            page.click("#conn-submit")
            page.wait_for_selector("#conn-feedback:not([hidden])")
            img_wrong = shot(page, "thread-wrong")
            add_screen(
                "thread-wrong", 1, "Thread — wrong guess",
                img_wrong,
                [
                    field("\"One away\" message", "One thread loose.", "js/connectionsgame.js", 341,
                          note=set_note("Two wrong-guess messages, chosen by whether 3 of the 4 picks "
                                        "shared a colour (“one away”) or not.")),
                    field("Plain wrong message", "Knot quite.", "js/connectionsgame.js", 341),
                    field("Mistake dots", "4 dots, losing one per wrong guess", "index.html", 410,
                          note="Visual only, no text to edit — listed for completeness."),
                ],
            )
            # Solve the rest of the board for real. The wrong guess above did
            # not remove or find any tiles, so every group is still intact and
            # selectable exactly as play_thread_daily expects.
            page.wait_for_timeout(300)
            for g in board["groups"]:
                H.click_tiles(page, g["items"])
                page.click("#conn-submit")
                if g is not board["groups"][-1]:
                    page.wait_for_selector("#conn-found .conn-group-%s" % g["colour"])
            page.wait_for_selector("#view-connsum:not([hidden])")
            img_sum = shot(page, "thread-summary")
            add_screen(
                "thread-summary", 1, "Thread — end-of-round summary",
                img_sum,
                [
                    field("Receipt header", "Yesternerd · Thread", "index.html", 433),
                    field("\"Board solved\" row", "Board solved", "js/connectionsgame.js", 463),
                    field("Mistakes row", "Mistake{s} × {n}", "js/connectionsgame.js", 464),
                    field("House-floor row", "House floor / nobody leaves empty-handed",
                          "js/connectionsgame.js", 466),
                    field("Perfect-run message", "Not a thread out of place.", "js/connectionsgame.js", 473,
                          note=set_note("Closing message — one of four depending on how the board "
                                        "went.")),
                    field("Frayed-but-solved message", "Frayed, but intact.", "js/connectionsgame.js", 474),
                    field("By-a-thread message (≥3 mistakes)", "By a thread.", "js/connectionsgame.js", 474),
                    field("Lost message", "The thread snapped.", "js/connectionsgame.js", 475),
                    field("Share button", "Share the thread", "index.html", 447),
                    field("Encore button", "Encore ›", "index.html", 448),
                ],
            )
            H.fail_on_errors([e for e in errors if "assets/img" not in e], "thread-flow")


def capture_day_done_screens():
    with sync_playwright() as p:
        # ---- plain full-house celebration (streak 1, no milestone) ----
        with new_ctx(p) as (page, errors, _ctx):
            H.boot(page, base, DATE)
            for g in H.manifest() and ["who", "map", "what", "thread"]:
                pass
            for g, detail in (("who", []), ("map", []), ("what", []),
                              ("thread", {"solved": True, "perfect": False, "mistakes": 1, "guesses": []})):
                H.seed_completion(page, g, N, score=70, detail=detail)
            H.boot(page, base, DATE)
            page.wait_for_selector("#view-daydone:not([hidden])")
            img = shot(page, "daydone-celebration")
            add_screen(
                "daydone-celebration", 1, "End of day — You Made History",
                img,
                [
                    field("Title", txt(page, "#dd-title"), "js/app.js", 1061),
                    field("Score label", txt(page, "#dd-score-label"), "js/app.js", 1062),
                    field("Streak label", txt(page, "#dd-streak-label"), "js/app.js", 1066),
                    field("Streak stamp (Memento mori)", "", "index.html", 470,
                          note="Only shown on the OBITUARY face, hidden here — see the obituary screen."),
                    field("Carpet diem stamp", txt(page, "#dd-carpet"), "index.html", 473),
                    field("Countdown template", "New games in {hh}:{mm}:{ss}", "js/app.js", 1021,
                          note="countdownText() — ticks live to local midnight."),
                    field("Share button", txt(page, "#dd-share"), "js/app.js", 1077,
                          note="“Share today’s receipt” on this face."),
                    field("Home button", "Home", "index.html", 477),
                    field("Complaints-desk stamp head", txt(page, "#dd-letters-head"), "js/feedback.js", 121,
                          note="“Tell us where it hurts” on this face, “Any last words?” "
                               "on the obituary."),
                    field("Complaints-desk stamp line", txt(page, "#dd-letters-line"), "js/feedback.js", 121),
                ],
            )
            H.fail_on_errors([e for e in errors if "assets/img" not in e], "daydone-celebration")

        # ---- edition-closed quiet ending (some lost) ----
        with new_ctx(p) as (page, errors, _ctx):
            H.boot(page, base, DATE)
            for g, sc, detail in (("who", 60, []), ("map", 55, []), ("what", 40, []),
                                  ("thread", 0, {"solved": False, "perfect": False, "mistakes": 4, "guesses": []})):
                H.seed_completion(page, g, N, score=sc, detail=detail)
            H.boot(page, base, DATE)
            page.wait_for_selector("#issue-closed:not([hidden])")
            img = shot(page, "home-issue-closed")
            add_screen(
                "home-issue-closed", 1, "End of day — quiet ending (a loss in the mix)",
                img,
                [
                    field("Verdict line", txt(page, "#ic-verdict"), "js/app.js", 1046,
                          note="Template: “№{n}, done. Some got away.”"),
                    field("Total label", txt(page, "#ic-label") or "Today's total", "index.html", 110),
                    field("Countdown", txt(page, "#ic-countdown"), "js/app.js", 1021),
                ],
                note="Shown on Home itself (not a separate screen) once all four of today's games are "
                     "played but at least one scored zero — the quiet counterpart to You Made "
                     "History above.",
            )
            H.fail_on_errors([e for e in errors if "assets/img" not in e], "home-issue-closed")


# ===========================================================================
# TIER 2 — weekly-ish
# ===========================================================================

def capture_obituary_and_milestone():
    with sync_playwright() as p:
        # ---- obituary: a 3-day full-house run that just went past repair ----
        with new_ctx(p) as (page, errors, _ctx):
            last = N - 6  # comfortably inside the manifest era and the archive window
            for n in (last - 2, last - 1, last):
                H.boot(page, base, H.edition_date(n))
                for g, detail in (("who", []), ("map", []), ("what", []),
                                  ("thread", {"solved": True, "perfect": False, "mistakes": 1, "guesses": []})):
                    H.seed_completion(page, g, n, score=65, detail=detail)
            H.boot(page, base, H.edition_date(last + 4))  # first day genuinely beyond repair
            page.wait_for_selector("#view-daydone:not([hidden])")
            img = shot(page, "daydone-obituary")
            add_screen(
                "daydone-obituary", 2, "End of day — You're History (obituary)",
                img,
                [
                    field("Title", txt(page, "#dd-title"), "js/app.js", 1089),
                    field("Score label", txt(page, "#dd-score-label"), "js/app.js", 1090),
                    field("Streak label (Rest in peace)", txt(page, "#dd-streak-label"), "js/app.js", 1092),
                    field("Memento mori stamp", txt(page, "#dd-stamp"), "index.html", 470),
                    field("Share button", txt(page, "#dd-share"), "js/app.js", 1109,
                          note="“Share the obituary” on this face."),
                    field("Complaints-desk stamp head (obituary)", txt(page, "#dd-letters-head"),
                          "js/feedback.js", 122),
                    field("Complaints-desk stamp line (obituary)", txt(page, "#dd-letters-line"),
                          "js/feedback.js", 122),
                ],
                note="Fires the first day a streak is genuinely beyond its 2-day repair window — "
                     "never a day early, and only once per dead streak.",
            )
            H.fail_on_errors([e for e in errors if "assets/img" not in e], "obituary")

        # ---- celebration WITH a milestone postmark (streak = 2) ----
        with new_ctx(p) as (page, errors, _ctx):
            for n in (N - 1, N):
                H.boot(page, base, H.edition_date(n))
                for g, detail in (("who", []), ("map", []), ("what", []),
                                  ("thread", {"solved": True, "perfect": True, "mistakes": 0, "guesses": []})):
                    H.seed_completion(page, g, n, score=80, detail=detail)
            H.boot(page, base, DATE)
            page.wait_for_selector("#dd-milestone:not([hidden])")
            img = shot(page, "daydone-milestone")
            add_screen(
                "daydone-milestone", 2, "End of day — milestone postmark",
                img,
                [
                    field("Milestone postmark", txt(page, "#dd-milestone"), "js/app.js", 1075,
                          note="Template: “№{streak}” over “days running”. Shown at "
                               "streaks 2, 3, 5, 7, 10, 25, 50, 100 — front-loaded because early days "
                               "move retention most."),
                ],
                note="The rest of this screen's copy is identical to the plain celebration screen in "
                     "Tier 1 — only the postmark badge is new here.",
            )
            H.fail_on_errors([e for e in errors if "assets/img" not in e], "milestone")


def capture_letters_and_shares():
    add_screen(
        "letters-plate-detail", 2, "Letters to the Editor — full copy set",
        None,
        [
            field("Home plate heading", "Got opinions?\nWrite in.", "index.html", 189),
            field("Home plate sub-line", "Praise, gripes, corrections, a clue that felt unfair — the "
                                          "editor reads everything.", "index.html", 190),
            field("Home plate button (online)", "Write to the editor →", "js/feedback.js", 143),
            field("Home plate button (offline)", "Email the editor →", "js/feedback.js", 143),
            field("Home plate offline note", "You're offline — this opens your mail app", "index.html", 204),
            field("Your Legacy coupon kicker", "Something to say?", "index.html", 511),
            field("Your Legacy coupon line", "Write to the editor →", "index.html", 511),
            field("Home footer word", "Write to us", "index.html", 207),
            field("Day-done stamp — full house", "Tell us where it hurts / The editor reads every one →",
                  "js/feedback.js", 121),
            field("Day-done stamp — obituary", "Any last words? / Tell the editor what killed it →",
                  "js/feedback.js", 122),
        ],
        note="Already visible in context on the Home and end-of-day screenshots above; gathered here "
             "as its own group because Daniel asked for the letters copy reviewed as a set. See "
             "'letters-plate-detail' has no picture of its own — use the Home and end-of-day "
             "screenshots for the visual.",
    )
    add_screen(
        "share-templates", 2, "Share text templates (no screenshot — see note)",
        None,
        [
            field("Thread share", "THREAD №{issue} 🧵 / {emoji grid} / {result line}",
                  "js/sharecard.js", 61),
            field("Lifeline share", "LIFELINE №{issue} 🗺️ / {emoji row} / {score line}",
                  "js/sharecard.js", 72),
            field("Face Value / Relic share", "{FACE VALUE|RELIC} №{issue} {glyph} / {emoji row} / "
                                               "{score} pts · {n} scraps torn", "js/sharecard.js", 80),
            field("Full-house share", "YESTERNERD №{issue} — FULL HOUSE 🏛️ / {emoji "
                                       "line} / {streak flame line}", "js/sharecard.js", 86),
            field("Obituary share", "YESTERNERD ☠️ / My {n}-day streak died. / RIP №{a}–"
                                     "№{b}. MEMENTO MORI.", "js/sharecard.js", 92),
            field("Copied-to-clipboard toast", "Copied — paste it anywhere", "js/sharecard.js", 255),
            field("Sharing-unavailable toast", "Sharing unavailable here", "js/sharecard.js", 256),
        ],
        note="These build the text OS share sheets carry, plus a separate canvas-drawn image receipt "
             "with the same numbers (js/sharecard.js drawCard). Both render off-DOM at share time, "
             "outside the app's own screens, so there is no app screenshot to take — the summary "
             "screens above (which carry the Share button) are the closest visual context.",
    )


def capture_install_screens():
    with sync_playwright() as p:
        specs = [
            ("installSafari", "install-safari", "Save it as an app — iOS Safari"),
            ("installChromeIOS", "install-chrome-ios", "Save it as an app — Chrome on iPhone"),
            ("installNative", "install-native", "Save it as an app — Android (native prompt)"),
            ("installGeneric", "install-generic", "Save it as an app — other browsers"),
            ("webviewInstagram", "install-webview-instagram", "Escape page — opened inside Instagram"),
            ("webviewGeneric", "install-webview-generic", "Escape page — opened inside another app"),
        ]
        for action, sid, title in specs:
            with new_ctx(p) as (page, errors, _ctx):
                H.boot(page, base, DATE)
                page.evaluate("a => __CHRONICLE_TEST__.install.force[a]()", action)
                page.wait_for_selector("#install-screen:not([hidden])")
                img = shot(page, sid)
                fields = [
                    field("Headline", txt(page, "#install-headline"), "js/install.js", 183 if "webview" not in sid
                          else 254),
                    field("Lede", txt(page, ".install-lede"), "js/install.js", 180 if "webview" not in sid
                          else 271),
                ]
                if action == "installNative":
                    fields += [
                        field("CTA button", "Save it now", "js/install.js", 193),
                        field("Note under the button", "{Chrome|Your browser} will ask you to confirm.\n"
                                                         "Nothing to download, nothing to sign up for.",
                              "js/install.js", 195),
                    ]
                elif action in ("installSafari", "installChromeIOS"):
                    fields += [
                        field("Step 1", "Tap Share", "js/install.js", 200 if action == "installChromeIOS" else 210),
                        field("Step 1 note",
                              "Top right, next to the address bar. Not the ⋯ at the bottom."
                              if action == "installChromeIOS"
                              else "It's in the bar by the address. Can't see it? It's behind the ⋯ pill.",
                              "js/install.js", 201 if action == "installChromeIOS" else 211),
                        field("Step 2 row", "Add to Home Screen", "js/install.js", 204),
                        field("Step 2 note", "Tap View More if you don't see it, then Add to Home Screen.",
                              "js/install.js", 205),
                        field("Saved-it button", "I've saved it ›", "js/install.js", 243),
                        field("Maybe-later link", "Maybe later", "js/install.js", 244),
                    ]
                elif action == "installGeneric":
                    fields += [
                        field("Step 1", "Tap the ⋮ menu", "js/install.js", 221),
                        field("Step 1 note", "It sits next to the address bar.", "js/install.js", 221),
                        field("Step 2 row", "Install app", "js/install.js", 223),
                        field("Step 2 note", "Or Add to Home screen — browsers word it differently.",
                              "js/install.js", 224),
                    ]
                else:  # webview escapes
                    fields += [
                        field("Step 1 note", "It's at the top right of this screen." if action == "webviewInstagram"
                              else "It's in the corner of this screen.", "js/install.js", 258),
                        field("Step 2 row", "Open in external browser" if action == "webviewInstagram"
                              else "Open in browser", "js/install.js", 261),
                        field("Copy-link button", "Copy the link", "js/install.js", 279),
                        field("Copy-link note", "then paste it in Safari or Chrome.", "js/install.js", 280),
                    ]
                add_screen(sid, 2, title, img, fields,
                           note="One of six branches (js/install.js, first-match-wins detection): iOS "
                                "Safari, Chrome-on-iPhone, Android's native one-tap dialog, everything "
                                "else, and two in-app-browser escape pages. All share the LEDE and "
                                "HEADLINE constants (js/install.js:180-183).")
                H.fail_on_errors([e for e in errors if "assets/img" not in e], sid)

        # the strip left behind after "Maybe later". Reached the real way (two
        # finished games), not via force(): a QA-forced preview deliberately
        # does not spend the real ask or leave the strip behind (see
        # tests/test_install.py:qa_panel_summons_every_branch), so force()
        # cannot be used to reach this particular state.
        with new_ctx(p) as (page, errors, _ctx):
            H.boot(page, base, DATE)
            finish = ("(g) => document.dispatchEvent(new CustomEvent('gamefinished',"
                      " {detail: {game: g, daily: true}}))")
            page.evaluate(finish, "who")
            page.evaluate(finish, "map")
            page.wait_for_selector("#install-screen:not([hidden])")
            page.click("#install-later")
            page.wait_for_selector("#install-tip:not([hidden])")
            img = shot(page, "install-strip")
            add_screen(
                "install-strip", 2, "Install strip (what \"Maybe later\" leaves on Home)",
                img,
                [
                    field("Strip line", txt(page, ".install-tip-line"), "index.html", 122),
                    field("Strip button", txt(page, "#install-tip-btn"), "index.html", 123),
                ],
                note="One line, one button, an × that kills it for good. Reopens the same screen "
                     "the player just declined.",
            )
            H.fail_on_errors([e for e in errors if "assets/img" not in e], "install-strip")


def capture_ledger_screens():
    with sync_playwright() as p:
        with new_ctx(p) as (page, errors, _ctx):
            H.boot(page, base, DATE)
            page.click("#ledger-link")
            page.wait_for_selector("#view-ledger:not([hidden])")
            page.wait_for_selector(".ledger-empty-line")
            img = shot(page, "ledger-empty")
            add_screen(
                "ledger-empty", 2, "Your Legacy — empty state",
                img,
                [
                    field("Kicker", txt(page, ".ledger-kicker"), "js/ledger.js", 206),
                    field("Title", txt(page, ".ledger-title"), "js/ledger.js", 206),
                    field("Empty subtitle", txt(page, ".ledger-since"), "js/ledger.js", 155,
                          note="“History starts at midnight.” when empty, otherwise “In the "
                               "making since №{n}.”"),
                    field("Empty headline", txt(page, ".ledger-empty-line"), "js/ledger.js", 198),
                    field("Empty sub-line", txt(page, ".ledger-empty-sub"), "js/ledger.js", 199),
                    field("Table legend", txt(page, ".ledger-legend"), "js/ledger.js", 186),
                    field("Carry coupon", "Moving house? / Carry your record over →", "index.html", 515),
                ],
            )
            H.fail_on_errors([e for e in errors if "assets/img" not in e], "ledger-empty")

        with new_ctx(p) as (page, errors, _ctx):
            for n in (N - 3, N - 2, N - 1):
                H.boot(page, base, H.edition_date(n))
                for g, detail in (("who", []), ("map", []), ("what", []),
                                  ("thread", {"solved": True, "perfect": True, "mistakes": 0, "guesses": []})):
                    H.seed_completion(page, g, n, score=85, detail=detail)
            H.boot(page, base, DATE)  # today itself left unplayed, so no moment screen intercepts
            page.click("#ledger-link")
            page.wait_for_selector("#view-ledger:not([hidden])")
            page.wait_for_selector(".ledger-stamp")
            img = shot(page, "ledger-populated")
            add_screen(
                "ledger-populated", 2, "Your Legacy — with a record on it",
                img,
                [
                    field("Flourish line", txt(page, ".ledger-flourish"), "js/ledger.js", 118,
                          note="“Your crowning glory: {game} — {score} in a single day.” "
                               "Marked FLAGGED FOR VOICE REVIEW in source."),
                    field("Perfect-day stamp", txt(page, ".ledger-stamp"), "js/ledger.js", 192,
                          note="“Habent sua fata” (Latin: books have their fates) over "
                               "“{n} perfect day(s)”. Marked FLAGGED FOR VOICE REVIEW in source."),
                    field("Tally labels", "Days played / Full houses / Perfect days", "js/ledger.js", 160),
                    field("Streak labels", "Full-house streak / Longest ever", "js/ledger.js", 166),
                    field("Table column headers", "Game / Played / Win% / Cur. / Best / High",
                          "js/ledger.js", 176),
                ],
            )
            H.fail_on_errors([e for e in errors if "assets/img" not in e], "ledger-populated")


def capture_carry_screens():
    with sync_playwright() as p:
        with new_ctx(p) as (page, errors, _ctx):
            H.boot(page, base, DATE)
            H.seed_completion(page, "who", N, score=70)
            page.click("#ledger-link")
            page.wait_for_selector("#view-ledger:not([hidden])")
            page.click("#carry-open")
            page.wait_for_selector("#carry-sheet:not([hidden])")
            page.wait_for_selector("#carry-payload")
            page.wait_for_function(
                "document.querySelector('#carry-payload').value.length > 0", timeout=8000)
            img = shot(page, "carry-export")
            add_screen(
                "carry-export", 3, "Carry (moving house) — export",
                img,
                [
                    field("Title", txt(page, "#carry-title"), "js/carry.js", 855),
                    field("Lede", txt(page, "#carry-lede"), "js/carry.js", 762),
                    field("Manifest lines", txt(page, "#carry-manifest"), "js/carry.js", 860,
                          note="“{n}-day {streak label}”, “{n} issue(s) on the record”, "
                               "and an optional settings line."),
                    field("Copy-code button", "Copy code", "index.html", 587),
                    field("Copy-link button", "Copy link", "index.html", 588),
                    field("Help line", txt(page, "#carry-help"), "js/carry.js", 767,
                          note=set_note("Two variants depending on whether the link is short enough to "
                                        "survive: link-first, or code-first for a very long payload.")),
                    field("Arrived-from-elsewhere label", "Arrived from another device?", "index.html", 591),
                    field("Paste placeholder", "Paste the code (or the link) here", "index.html", 592),
                    field("Bring-it-in button", "Bring it in", "index.html", 594),
                    field("Close button", "Close", "index.html", 605),
                ],
            )
            H.fail_on_errors([e for e in errors if "assets/img" not in e], "carry-export")

            payload = page.evaluate("async () => (await __CHRONICLE_TEST__.carry.exportNow()).payload")

        with new_ctx(p) as (page, errors, _ctx):
            url = H.app_url(base, DATE) + "#carry=" + payload
            page.goto(url)
            page.wait_for_function(H.BOOTED)
            page.wait_for_selector("#carry-sheet:not([hidden])")
            page.wait_for_selector("#carry-confirm-row:not([hidden])")
            img = shot(page, "carry-import")
            add_screen(
                "carry-import", 3, "Carry (moving house) — something arrived",
                img,
                [
                    field("Title", txt(page, "#carry-title"), "js/carry.js", 920),
                    field("Lede", txt(page, "#carry-lede"), "js/carry.js", 921,
                          note="Template: “Carry {n}-day {streak label} + {n} issue(s) over to this "
                               "device?”"),
                    field("Merge line", "Merged with what's already here — nothing is deleted, the "
                                        "better record wins.", "js/carry.js", 928),
                    field("Confirm button", "Carry it over", "index.html", 599),
                    field("Decline button", "Not now", "index.html", 600),
                    field("Bad-code reasons", txt(page, "#carry-lede") or "", "js/carry.js", 776,
                          note=set_note("REASONS bank — one shown depending on exactly what was wrong "
                                        "with a pasted code.")),
                    field("Reason: not a code", "That doesn't look like a carry code. Copy the whole thing "
                                                 "— it's one long unbroken line.", "js/carry.js", 776),
                    field("Reason: damaged", "That code arrived damaged — something clipped it on the "
                                              "way. Copy it again, all of it.", "js/carry.js", 777),
                    field("Reason: wrong version", "That code was made by a different version of the app. "
                                                    "Make a fresh one on the old device.", "js/carry.js", 778),
                    field("Reason: too old to unzip", "This browser is too old to unpack that code. Try a "
                                                       "different browser on this device.", "js/carry.js", 779),
                    field("Reason: too big", "That code is far too big to be one of ours.", "js/carry.js", 780),
                    field("Reason: empty", "That code is empty — there was nothing on the record to "
                                            "carry.", "js/carry.js", 781),
                    field("Already-carried title", "Already here", "js/carry.js", 892),
                    field("Already-carried lede", "This record was carried over already — nothing left "
                                                   "to do. Your streak is safe.", "js/carry.js", 893),
                    field("Carried-over title", "Carried over", "js/carry.js", 936),
                    field("Carried-over lede (something added)", "Done. Your record travelled.",
                          "js/carry.js", 937),
                    field("Carried-over lede (nothing new)", "Everything on that code was already here — "
                                                              "nothing to add.", "js/carry.js", 938),
                ],
                note="Reached by opening a carry link on a fresh device/browser — rare by nature. "
                     "The bad-code and already-carried states share this same sheet with different text; "
                     "shown here as a set since only one appears per attempt.",
            )
            H.fail_on_errors([e for e in errors if "assets/img" not in e], "carry-import")


def capture_static_pages():
    pages = [
        ("about.html", 3, "About page"),
        ("how-to-play.html", 2, "How to play page"),
        ("privacy.html", 3, "Privacy page"),
        ("sources.html", 3, "Sources page (top section — the register itself is generated data)"),
        ("corrections.html", 3, "Corrections page"),
        ("press.html", 3, "Press kit (not linked from the app's own navigation)"),
        ("404.html", 3, "404 — page not found"),
    ]
    with sync_playwright() as p:
        with new_ctx(p) as (page, _errors, _ctx):
            for filename, tier, title in pages:
                page.goto(base + "/" + filename)
                page.wait_for_load_state("networkidle")
                # Sources.html's register can run to hundreds of rows; clip the
                # screenshot to the static intro copy plus a peek at the table,
                # not the whole generated register (that part is data, not copy).
                full = filename != "sources.html"
                img = shot(page, filename.replace(".html", ""), full_page=full)
                headings = page.locator("main h2").all_inner_texts() if page.locator("main").count() else []
                paras = page.locator("main > p").all_inner_texts() if page.locator("main").count() else []
                fields = []
                for h in headings[:8]:
                    fields.append(field("Heading", h.strip(), filename, None))
                for para in paras[:6]:
                    fields.append(field("Paragraph", para.strip(), filename, None))
                title_text = txt(page, "title") or page.title()
                fields.insert(0, field("Page <title>", page.title(), filename, 6))
                if filename == "sources.html":
                    fields.append(field("Register note", "Everything below the intro is GENERATED from "
                                                            "data/*.json by tools/build_sources_page.py — "
                                                            "editing it here would be overwritten on the next "
                                                            "run. Out of scope for this review.", filename, 63))
                if filename == "corrections.html":
                    fields.append(field("Empty-log line", txt(page, ".corr-empty"), filename, 45))
                add_screen(filename.replace(".html", "-page"), tier, title, img, fields,
                           note="Static content page — line numbers are omitted where a paragraph's "
                                "exact line shifts easily; open the file and search for the text.")


def capture_error_and_offline_states():
    with sync_playwright() as p:
        # ---- "couldn't load — tap to retry" on a Home card ----
        with new_ctx(p, block_external=False) as (page, errors, ctx):
            def route(r):
                host = r.request.url.split("/")[2].split(":")[0]
                if host not in ("127.0.0.1", "localhost"):
                    r.abort()
                elif "/data/editions.json" in r.request.url:
                    r.abort()
                else:
                    r.continue_()
            ctx.route("**/*", route)
            page.goto(H.app_url(base, DATE))
            page.wait_for_function(
                "window.__CHRONICLE_TEST__ && __CHRONICLE_TEST__.data && __CHRONICLE_TEST__.data.figures")
            page.click('[data-hero="map"]')
            page.wait_for_function(
                "() => { const el = document.querySelector('[data-hero=\"map\"] [data-status]');"
                " return !!el && (el.innerText||'').toLowerCase().indexOf('retry') !== -1; }",
                timeout=15000)
            img = shot(page, "home-retry")
            add_screen(
                "home-retry", 3, "Error — couldn't load a game's schedule",
                img,
                [
                    field("Loading label", "spinning up the presses…", "js/app.js", 1249),
                    field("Failure label", txt(page, '[data-hero="map"] [data-status]'), "js/app.js", 1255,
                          note="Same tap retries — the failed download is not remembered as a verdict."),
                ],
                note="data/editions.json (the daily manifest) failed to load. The same wording covers any "
                     "of the four games' data files failing.",
            )
            H.fail_on_errors([e for e in errors if "editions.json" not in e], "home-retry")

        # ---- offline round: the image never arrived ----
        with new_ctx(p, block_external=False) as (page, errors, ctx):
            def route(r):
                host = r.request.url.split("/")[2].split(":")[0]
                if host not in ("127.0.0.1", "localhost"):
                    r.abort()
                elif "/assets/img/" in r.request.url:
                    r.abort()
                else:
                    r.continue_()
            ctx.route("**/*", route)
            page.goto(H.app_url(base, DATE))
            page.wait_for_function(H.BOOTED)
            H.open_daily(page, "who")
            H.dismiss_intro(page, timeout=1200)
            page.wait_for_selector("#view-reveal:not([hidden])")
            page.wait_for_selector("#rv-offline:not([hidden])", timeout=15000)
            img = shot(page, "reveal-offline")
            add_screen(
                "reveal-offline", 3, "Offline — this round's image never arrived",
                img,
                [
                    field("Notice", txt(page, "#rv-offline"), "index.html", 337),
                    field("Retry button", txt(page, "#rv-offline-retry"), "index.html", 338),
                    field("Retry button (still failing)", "Still offline — retry", "js/revealgame.js", 1268),
                ],
                note="The “aeroplane case”: covers the frame with an honest notice instead of "
                     "dealing nine scraps over a blank image.",
            )
            H.fail_on_errors([e for e in errors if "assets/img" not in e], "reveal-offline")

        # ---- save-failure toast ----
        with new_ctx(p, init_scripts=(
                "Storage.prototype.setItem = function(){ "
                "throw new DOMException('quota','QuotaExceededError'); };",)) as (page, errors, _ctx):
            page.goto(H.app_url(base, DATE))
            page.wait_for_function(H.BOOTED)
            page.wait_for_selector(".df-save-toast", timeout=8000)
            img = shot(page, "save-failure-toast")
            add_screen(
                "save-failure-toast", 3, "Error — progress isn't saving on this device",
                img,
                [
                    field("Toast message", txt(page, ".df-save-toast"), "js/storage.js", 114),
                    field("Dismiss button aria-label", "Dismiss", "js/storage.js", 118),
                ],
                note="One-time-per-session notice when localStorage refuses a write (full disk, private "
                     "browsing). Shown here by forcing every write to fail.",
            )
            H.fail_on_errors([e for e in errors if "assets/img" not in e], "save-failure-toast")

        # ---- new-edition bar (via the ?qa=1 forcing panel; no other route reaches it) ----
        with new_ctx(p) as (page, errors, _ctx):
            H.boot(page, base, DATE, extra="&qa=1")
            page.wait_for_selector("#qa-panel")
            page.click("#qa-panel .qa-btn:has-text('New edition bar')")
            page.wait_for_selector("#new-edition")
            page.evaluate("() => { const p = document.getElementById('qa-panel'); if (p) p.remove(); }")
            img = shot(page, "new-edition-bar")
            add_screen(
                "new-edition-bar", 3, "\"Off the presses\" — a new version is ready",
                img,
                [
                    field("Bar text (iOS)", "✨ New version ready — pull down to refresh",
                          "js/app.js", 1517),
                    field("Bar text (everywhere else)", "✨ New version ready — tap to refresh",
                          "js/app.js", 1518),
                ],
                note="Appears once a freshly-deployed service worker has taken over underneath the "
                     "running page — captured here via the ?qa=1 forcing panel (the QA panel itself "
                     "is hidden from the screenshot; it is developer furniture, not app copy).",
            )
            H.fail_on_errors([e for e in errors if "assets/img" not in e], "new-edition-bar")


def capture_sr_announcements():
    items = [
        ("Round start", "Round {n} of {total}.", "js/revealgame.js", 821),
        ("Round start (Lifeline)", "Round {n} of {total}.", "js/mapgame.js", 591),
        ("Correct answer", "{Verdict} {name}. Plus {n} points.", "js/revealgame.js", 1022),
        ("Wrong / revealed", "It was {name}. 0 points.", "js/revealgame.js", 1023),
        ("Correct answer (Lifeline)", "Correct — {name}. Plus {n} points.", "js/mapgame.js", 754),
        ("Clue bought", "{Clue label}: {value}. Worth {n} points.", "js/revealgame.js", 237),
        ("Rescue opened", "Three choices: {a}, {b}, {c}. Pick one for {n} points. Tearing and clues "
                           "are closed.", "js/revealgame.js", 967),
        ("Blocked tap", "Already torn. / Choose a scrap next to an open space. / Tearing is closed — "
                         "pick one of the three.", "js/revealgame.js", 540),
        ("Thread group solved (not last)", "Correct — {label}. {n} of 4 groups found.",
         "js/connectionsgame.js", 323),
        ("Thread board solved", "Correct — {label}. All four groups found.", "js/connectionsgame.js", 320),
        ("Thread wrong guess", "Wrong group. / Wrong group — one away. {n} guesses left.",
         "js/connectionsgame.js", 346),
        ("Thread run complete", "Board solved. {n} points. / The thread snapped. 0 points.",
         "js/connectionsgame.js", 413),
        ("Run complete (Face Value/Relic/Lifeline)", "Run complete. Final score {n} points.",
         "js/revealgame.js", 1177),
        ("First wrong guess, spoken", "{Not them|Not that} − {n}. Worth {n} points.",
         "js/revealgame.js", 1239),
    ]
    fields = [field(label, value, f, ln) for label, value, f, ln in items]
    add_screen(
        "sr-announcements", 3, "Screen-reader announcements (no screenshot — spoken, not shown)",
        None, fields,
        note="One shared, visually-hidden live region (#sr-live in index.html, line 621) carries these "
             "across all four games. They are copy too — a screen-reader player hears every one of "
             "them, even though nothing changes on screen.",
    )


def capture_stamp_vocabulary():
    fields = [
        field("Memento mori (obituary streak stamp)", "Memento mori", "index.html", 470),
        field("Carpet diem (full-house stamp)", "Carpet diem", "index.html", 473),
        field("Damnatio memoriae (zero-score receipt stamp)",
              "Damnatio memoriae\nstruck from the record", "index.html", 282,
              note="Appears identically on all three rounds-game summaries: index.html:282 (Lifeline), "
                   "386 (Face Value/Relic), 440 (Thread)."),
        field("Habent sua fata (Your Legacy perfect-day stamp)",
              "Habent sua fata\n{n} perfect day(s)", "js/ledger.js", 192,
              note="Latin: “books have their fates”. Marked FLAGGED FOR VOICE REVIEW in source."),
        field("Alea iacta fest — BAKED INTO ARTWORK, READ-ONLY", "Alea iacta fest",
              "assets/brand/stamp-alea-iacta-fest.png",
              None,
              note="This is a PNG, not text — the words are drawn into the image itself. Referenced "
                   "from index.html:280/384/440 as an <img>; its alt text (shown as this field's value) "
                   "is the only editable-in-HTML part. Changing the wording means re-exporting the "
                   "artwork in whatever tool made it, not editing a string in this codebase."),
    ]
    add_screen(
        "stamp-vocabulary", 2, "Stamp vocabulary (gathered from across the app)",
        None, fields,
        note="Daniel asked for the whole stamp vocabulary reviewed together. Every one of these already "
             "appears in context on a screenshot above (the day-done, receipt and Your Legacy screens) "
             "— this section exists only to put them side by side.",
    )


# ===========================================================================
# HTML generation
# ===========================================================================
TIER_INFO = {
    1: ("Tier 1 — every session", "expanded"),
    2: ("Tier 2 — weekly-ish", "collapsed"),
    3: ("Tier 3 — rare", "collapsed"),
}


def render_field(screen_id, f):
    uid = "%s-%s" % (screen_id, f["uid"])
    loc = f["file"]
    if f.get("line"):
        loc += ":" + str(f["line"])
    note_html = ""
    if f["note"]:
        note_html = '<p class="cr-note">%s</p>' % esc(f["note"]).replace("\n", "<br>")
    return """
      <div class="cr-field">
        <div class="cr-field-head">
          <label for="%s">%s</label>
          <code class="cr-loc">%s</code>
        </div>
        <textarea id="%s" data-original="%s" rows="%d">%s</textarea>
        %s
      </div>""" % (
        esc_attr(uid), esc(f["label"]), esc(loc), esc_attr(uid),
        esc_attr(f["value"]), max(2, min(8, (f["value"] or "").count("\n") + 2)),
        esc(f["value"]), note_html,
    )


def render_screen(s):
    prov = ""
    if s["provisional"]:
        prov = '<span class="cr-badge cr-badge-provisional">PROVISIONAL</span>'
    note = ""
    if s["note"]:
        note = '<p class="cr-screen-note">%s</p>' % esc(s["note"]).replace("\n", "<br>")
    if s["image"]:
        media = '<img src="%s" alt="Screenshot: %s" loading="lazy">' % (s["image"], esc_attr(s["title"]))
    else:
        media = '<div class="cr-no-shot">No screenshot for this state — see the note.</div>'
    fields_html = "\n".join(render_field(s["id"], f) for f in s["fields"])
    return """
    <article class="cr-screen" id="screen-%s">
      <div class="cr-screen-head">
        <h3>%s %s</h3>
        %s
      </div>
      <div class="cr-screen-body">
        <div class="cr-media">%s</div>
        <div class="cr-fields">%s</div>
      </div>
    </article>""" % (esc(s["id"]), esc(s["title"]), prov, note, media, fields_html)


PAGE_CSS = """
:root{
  --bg:#F2EFE6; --ink:#141414; --card:#ffffff; --line:#d8d2c2; --muted:#6b675c;
  --accent:#b3282d; --accent-soft:#f7e3e0; --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
}
@media (prefers-color-scheme: dark){
  :root{ --bg:#17140f; --ink:#f2efe6; --card:#221e17; --line:#3a3428; --muted:#a49d8c;
    --accent:#e2726b; --accent-soft:#3a201d; }
}
:root[data-theme="dark"]{ --bg:#17140f; --ink:#f2efe6; --card:#221e17; --line:#3a3428; --muted:#a49d8c;
  --accent:#e2726b; --accent-soft:#3a201d; }
:root[data-theme="light"]{ --bg:#F2EFE6; --ink:#141414; --card:#ffffff; --line:#d8d2c2; --muted:#6b675c;
  --accent:#b3282d; --accent-soft:#f7e3e0; }
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",
  Roboto,Helvetica,Arial,sans-serif;margin:0;padding:0 0 80px}
.cr-wrap{max-width:1100px;margin:0 auto;padding:24px 18px}
h1{font-size:26px;margin:0 0 6px}
.cr-lede{color:var(--muted);max-width:70ch}
.cr-topnote{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;
  margin:18px 0 28px}
.cr-topnote p{margin:6px 0}
.cr-topnote b{color:var(--accent)}
.cr-tier-heading{display:flex;align-items:baseline;gap:10px;margin:36px 0 6px;
  border-bottom:2px solid var(--line);padding-bottom:8px}
.cr-tier-heading h2{margin:0;font-size:20px}
.cr-tier-heading small{color:var(--muted)}
details.cr-tier > summary{cursor:pointer;font-size:16px;font-weight:700;padding:10px 0;list-style:none}
details.cr-tier > summary::-webkit-details-marker{display:none}
details.cr-tier > summary::before{content:"\\25B8 ";display:inline-block;transition:transform .15s}
details.cr-tier[open] > summary::before{transform:rotate(90deg)}
.cr-screen{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;
  margin:16px 0}
.cr-screen-head h3{margin:0 0 4px;font-size:17px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.cr-badge{font-size:11px;font-weight:800;letter-spacing:.04em;padding:2px 8px;border-radius:999px}
.cr-badge-provisional{background:var(--accent-soft);color:var(--accent);border:1px solid var(--accent)}
.cr-screen-note{color:var(--muted);font-size:14px;margin:4px 0 10px;max-width:80ch}
.cr-screen-body{display:grid;grid-template-columns:260px 1fr;gap:18px}
@media (max-width:760px){.cr-screen-body{grid-template-columns:1fr}}
.cr-media img{width:100%;border-radius:8px;border:1px solid var(--line);display:block}
.cr-no-shot{border:1px dashed var(--line);border-radius:8px;padding:18px;color:var(--muted);
  font-size:14px;text-align:center}
.cr-fields{display:flex;flex-direction:column;gap:14px}
.cr-field-head{display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap}
.cr-field-head label{font-weight:700;font-size:13.5px}
.cr-loc{font-family:var(--mono);font-size:11px;color:var(--muted);background:transparent}
textarea{width:100%;font:14px/1.4 var(--mono);padding:8px 10px;border-radius:8px;
  border:1px solid var(--line);background:var(--bg);color:var(--ink);resize:vertical}
textarea:focus{outline:2px solid var(--accent);outline-offset:1px}
.cr-note{color:var(--muted);font-size:12.5px;margin:2px 0 0}
.cr-copybar{position:sticky;bottom:0;background:var(--card);border-top:1px solid var(--line);
  padding:12px 18px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;z-index:5}
.cr-copybtn{background:var(--accent);color:#fff;border:none;border-radius:999px;padding:10px 20px;
  font-weight:800;font-size:14px;cursor:pointer}
.cr-copybtn:active{transform:translateY(1px)}
.cr-copystatus{color:var(--muted);font-size:13px}
.cr-copyrow{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.cr-out{display:block;width:100%;margin-top:10px;min-height:120px;max-height:34vh;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;line-height:1.5;
  padding:10px;border:1px solid var(--line);border-radius:8px;background:var(--bg);
  color:var(--ink);resize:vertical;white-space:pre}
.cr-out[hidden]{display:none}
"""

PAGE_JS = """
function collectChanges(){
  var out = [];
  document.querySelectorAll('.cr-screen').forEach(function(scr){
    var heading = scr.querySelector('h3').textContent.trim();
    var changed = [];
    scr.querySelectorAll('textarea').forEach(function(t){
      if (t.value !== t.dataset.original) {
        var label = t.closest('.cr-field').querySelector('label').textContent.trim();
        var loc = t.closest('.cr-field').querySelector('.cr-loc').textContent.trim();
        changed.push(label + ' (' + loc + '):\\n' + t.value);
      }
    });
    if (changed.length) out.push('== ' + heading + ' ==\\n' + changed.join('\\n\\n'));
  });
  return out.join('\\n\\n');
}
// Edits are autosaved to this browser so a reload, a stray tap or a closed tab
// can never bin an afternoon's work. Keyed by screen + label so the key stays
// stable when the page is regenerated and screens shift position.
var SAVE_KEY = 'yesternerd-copy-review-edits-v1';

function fieldKey(t){
  var scr = t.closest('.cr-screen').querySelector('h3').textContent.trim();
  var label = t.closest('.cr-field').querySelector('label').textContent.trim();
  return scr + '||' + label;
}
function saveEdits(){
  var store = {};
  document.querySelectorAll('.cr-screen textarea').forEach(function(t){
    if (t.value !== t.dataset.original) store[fieldKey(t)] = t.value;
  });
  try { localStorage.setItem(SAVE_KEY, JSON.stringify(store)); } catch (e) {}
}
function restoreEdits(){
  var store;
  try { store = JSON.parse(localStorage.getItem(SAVE_KEY) || '{}'); } catch (e) { return 0; }
  var n = 0;
  document.querySelectorAll('.cr-screen textarea').forEach(function(t){
    var v = store[fieldKey(t)];
    if (typeof v === 'string' && v !== t.value) { t.value = v; n++; }
  });
  return n;
}

// The clipboard API is blocked inside a sandboxed frame, so the text box below
// is the real mechanism and the clipboard call is only an opportunistic bonus.
function copyAll(){
  var text = collectChanges();
  var status = document.getElementById('cr-status');
  var out = document.getElementById('cr-out');
  if (!text) {
    out.hidden = true;
    status.textContent = 'No changes yet \\u2014 edit a box above first.';
    return;
  }
  var blocks = text.split('\\n\\n== ').length;
  out.hidden = false;
  out.value = text;
  out.focus();
  out.select();
  status.textContent = blocks + ' change block(s) ready below \\u2014 press Cmd+C (or Ctrl+C) to copy, then paste into chat.';
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(function(){
      status.textContent = 'Copied ' + blocks + ' change block(s). Paste into chat. (Also shown below, just in case.)';
    }, function(){});
  }
}

document.getElementById('cr-copyall').addEventListener('click', copyAll);
document.addEventListener('input', function(e){
  if (e.target && e.target.tagName === 'TEXTAREA' && e.target.closest('.cr-screen')) saveEdits();
});
(function(){
  var n = restoreEdits();
  if (n) {
    document.getElementById('cr-status').textContent =
      'Restored ' + n + ' edit(s) you made earlier in this browser.';
  }
})();
"""


def build_html():
    generated = datetime.now().strftime("%d %b %Y, %H:%M")
    tiers_html = []
    for tier in (1, 2, 3):
        label, mode = TIER_INFO[tier]
        screens = [s for s in SCREENS if s["tier"] == tier]
        body = "\n".join(render_screen(s) for s in screens)
        if tier == 1:
            tiers_html.append('<div class="cr-tier-heading"><h2>%s</h2><small>%d screens — shown open</small></div>%s'
                               % (esc(label), len(screens), body))
        else:
            tiers_html.append(
                '<details class="cr-tier"><summary>%s — %d screens (tap to open)</summary>%s</details>'
                % (esc(label), len(screens), body))
    total = len(SCREENS)
    with_shots = len([s for s in SCREENS if s["image"]])
    html = """<title>Yesternerd copy review</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>%s</style>
<div class="cr-wrap">
  <h1>Yesternerd — copy review</h1>
  <p class="cr-lede">Every screen and state, as a picture, with its wording in an editable box next to
  it. Generated %s from edition №%d on branch data in this checkout.</p>
  <div class="cr-topnote">
    <p><b>You can stop after Tier 1</b> and still have covered most of what a player actually reads —
    Tiers 2 and 3 are folded shut below; open a section only if you want to go further.</p>
    <p>To send edits back: change any box you want to fix, then press <b>Copy all my changes</b> at the
    bottom of the page. Your changes appear in a text box there — select them and copy, then paste into
    chat. Untouched boxes are left out automatically.</p>
    <p><b>Your edits are saved in this browser as you type</b>, so closing the tab or reloading the page
    will not lose them.</p>
    <p>%d screens/states captured, %d with a screenshot (the rest are text-only sets — share
    templates, screen-reader announcements, and the baked-into-artwork stamp — explained where they
    appear).</p>
  </div>
  %s
  <div class="cr-copybar">
    <div class="cr-copyrow">
      <button class="cr-copybtn" id="cr-copyall" type="button">Copy all my changes</button>
      <span class="cr-copystatus" id="cr-status"></span>
    </div>
    <textarea id="cr-out" class="cr-out" readonly hidden
              aria-label="Your changes, ready to copy"></textarea>
  </div>
</div>
<script>%s</script>
""" % (PAGE_CSS, esc(generated), N, total, with_shots, "\n".join(tiers_html), PAGE_JS)
    return html


# ===========================================================================
# main
# ===========================================================================
def main():
    global base
    with H.server() as srv_base:
        base = srv_base
        t0 = time.time()
        capture_home_screens()
        capture_facevalue_flow()
        capture_lifeline_flow()
        capture_relic_flow()
        capture_thread_flow()
        capture_day_done_screens()
        capture_obituary_and_milestone()
        capture_letters_and_shares()
        capture_install_screens()
        capture_ledger_screens()
        capture_carry_screens()
        capture_error_and_offline_states()
        capture_sr_announcements()
        capture_stamp_vocabulary()
        capture_static_pages()
        print("Captured %d screens/states in %.1fs" % (len(SCREENS), time.time() - t0))

    html = build_html()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    size = os.path.getsize(OUT_PATH)
    print("Wrote %s (%.2f MB)" % (OUT_PATH, size / 1024 / 1024))
    if size > 10 * 1024 * 1024:
        print("WARNING: over the 10 MB budget.")

    import shutil
    shutil.rmtree(SHOT_DIR, ignore_errors=True)


if __name__ == "__main__":
    main()
