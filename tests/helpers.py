"""Shared plumbing for the Dead Famous Playwright suite (P4.1).

Conventions (Session 6):
- Chromium primary, iPhone-13 viewport, served by python3 -m http.server.
- Every page loads with ?test=1 so window.__CHRONICLE_TEST__ is available
  (it is also enabled on 127.0.0.1, but the flag keeps intent explicit).
- GoatCounter is stubbed by an init script: events land in window.__gc as
  their DISPLAY names, and the real count.js never loads (external requests
  are aborted), so tests are hermetic and assert on analytics honestly.
- "Today" is injected via ?dailydate=YYYY-MM-DD. Flow tests pin themselves
  to the NEWEST edition in data/editions.json (manifest-served, with 7+
  aired days behind it) so they stay deterministic as the manifest grows.
"""
import contextlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import date, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PORT = 8200 + (os.getpid() % 400)
EPOCH = date(2026, 6, 29)          # keep in sync with js/daily.js

GC_STUB = ("window.goatcounter={count:function(o){"
           "(window.__gc=window.__gc||[]).push(o.path)}};")

# Wait until boot() ran AND every data file the four games need is loaded.
BOOTED = ("window.__CHRONICLE_TEST__ && __CHRONICLE_TEST__.data"
          " && __CHRONICLE_TEST__.data.editions && __CHRONICLE_TEST__.data.reveal"
          " && __CHRONICLE_TEST__.data.figures && __CHRONICLE_TEST__.data.connections")


# ---------- manifest-derived test calendar ----------
def manifest():
    with open(os.path.join(ROOT, "data", "editions.json"), encoding="utf-8") as f:
        return json.load(f)


def latest_edition():
    """Newest manifest edition — the anchor 'today' for deterministic tests."""
    return max(int(k) for k in manifest()["editions"])


def edition_date(n):
    return (EPOCH + timedelta(days=n)).isoformat()


def app_url(base, dailydate=None, extra=""):
    u = base + "/index.html?test=1"
    if dailydate:
        u += "&dailydate=" + dailydate
    return u + extra


# ---------- server ----------
@contextlib.contextmanager
def server(port=None):
    port = port or PORT
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--directory", ROOT],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        base = "http://127.0.0.1:%d" % port
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/index.html", timeout=1)
                break
            except Exception:
                time.sleep(0.25)
        else:
            raise RuntimeError("static server did not start")
        yield base
    finally:
        proc.terminate()
        proc.wait()


# ---------- pages ----------
def _capture_errors(page, errors):
    def on_console(m):
        if m.type != "error":
            return
        url = (m.location or {}).get("url", "")
        # External analytics is stubbed/blocked; its resource errors are noise.
        if "zgo.at" in url or "goatcounter" in url or "zgo.at" in m.text:
            return
        errors.append("console: " + m.text)
    page.on("console", on_console)
    page.on("pageerror", lambda e: errors.append("pageerror: " + str(e)))


def _block_external(ctx):
    def route(r):
        host = r.request.url.split("/")[2].split(":")[0]
        if host in ("127.0.0.1", "localhost"):
            r.continue_()
        else:
            r.abort()
    ctx.route("**/*", route)


@contextlib.contextmanager
def page_on(p, engine="chromium", base=None, device="iPhone 13"):
    """Back-compat shape (match_harness): yields (page, errors)."""
    with app(p, engine=engine, device=device) as (page, errors, _ctx):
        yield page, errors


@contextlib.contextmanager
def app(p, engine="chromium", device="iPhone 13", init_scripts=(),
        block_external=True):
    """A fresh profile: gc stubbed, external hosts blocked, errors captured."""
    browser = getattr(p, engine).launch()
    ctx = browser.new_context(**dict(p.devices[device])) if device else browser.new_context()
    if block_external:
        _block_external(ctx)
    ctx.add_init_script(GC_STUB)
    for s in init_scripts:
        ctx.add_init_script(s)
    page = ctx.new_page()
    errors = []
    _capture_errors(page, errors)
    try:
        yield page, errors, ctx
    finally:
        browser.close()


def boot(page, base, dailydate=None, extra=""):
    page.goto(app_url(base, dailydate, extra))
    page.wait_for_function(BOOTED)


def gc_events(page):
    return page.evaluate("window.__gc || []")


def fail_on_errors(errors, label):
    if errors:
        print("FAIL [%s] console/page errors:" % label)
        for e in errors:
            print("  -", e)
        raise AssertionError("console errors in " + label)


# ---------- app flows ----------
def dismiss_intro(page, timeout=2500):
    """Click through a game's first-run intro card if it appears."""
    try:
        page.wait_for_selector("#intro-card:not([hidden])", timeout=timeout)
    except Exception:
        return False
    page.click("#intro-play")
    page.wait_for_selector("#intro-card", state="hidden")
    return True


def open_daily(page, game):
    """Tap a game's hero card on Home (waits for Home to be interactive)."""
    page.wait_for_selector('[data-hero="%s"]' % game)
    page.click('[data-hero="%s"]' % game)


def play_reveal_daily(page):
    """Answer every Face Value / Relic round correctly via the test hooks."""
    while True:
        page.wait_for_selector("#view-reveal:not([hidden])")
        page.wait_for_function("__CHRONICLE_TEST__.revealRound !== undefined")
        name = page.evaluate("__CHRONICLE_TEST__.revealRound.name")
        page.fill("#rv-input", name)
        page.click("#rv-guess-btn")
        page.wait_for_selector("#rv-next:not([hidden])")
        last = "results" in page.inner_text("#rv-next").lower()
        page.click("#rv-next")
        if last:
            break
    page.wait_for_selector("#view-revealsum:not([hidden])")


def play_map_daily(page):
    """Answer every Lifeline round correctly via the test hooks."""
    while True:
        page.wait_for_selector("#view-map:not([hidden])")
        page.wait_for_function("__CHRONICLE_TEST__.mapRound !== undefined")
        name = page.evaluate("__CHRONICLE_TEST__.mapRound.name")
        page.fill("#map-input", name)
        page.click("#map-guess-btn")
        page.wait_for_selector("#map-next:not([hidden])")
        last = "results" in page.inner_text("#map-next").lower()
        page.click("#map-next")
        if last:
            break
    page.wait_for_selector("#view-mapsum:not([hidden])")


def thread_board(page, n):
    """The edition's board object (groups with colour/label/items)."""
    return page.evaluate("n => __CHRONICLE_TEST__.daily.getEdition('thread', n)[0]", n)


def click_tiles(page, items):
    for it in items:
        page.locator("#conn-grid").get_by_role("button", name=it, exact=True).click()


def play_thread_daily(page, board):
    """Solve the whole board group by group."""
    for g in board["groups"]:
        click_tiles(page, g["items"])
        page.click("#conn-submit")
        if len([x for x in board["groups"]]) and g is not board["groups"][-1]:
            page.wait_for_selector("#conn-found .conn-group-%s" % g["colour"])
    page.wait_for_selector("#view-connsum:not([hidden])")


def seed_completion(page, game, n, score=80, detail=None):
    """Write a ledger entry through the real recordDailyCompletion path."""
    page.evaluate(
        "a => __CHRONICLE_TEST__.daily.recordDailyCompletion(a.g, a.n, "
        "{score: a.s, detail: a.d})",
        {"g": game, "n": n, "s": score,
         "d": detail if detail is not None else []})


def ledger(page):
    return page.evaluate("__CHRONICLE_TEST__.store.getDailyLedger()")


def reveal_worth(page):
    return page.evaluate("__CHRONICLE_TEST__.revealDebug.worth()")


def map_worth(page):
    import re
    txt = page.inner_text("#map-worth")
    m = re.search(r"(\d+)", txt)
    return int(m.group(1)) if m else None


def tab_until(page, pred, max_tabs=200):
    """Press Tab until the focused element satisfies pred({id,text,cls})."""
    for _ in range(max_tabs):
        info = page.evaluate(
            "() => { const a = document.activeElement;"
            " return { id: (a && a.id) || '',"
            " text: a ? (a.textContent || '').trim() : '',"
            " cls: (a && a.className) || '' }; }")
        if pred(info):
            return True
        page.keyboard.press("Tab")
    return False
