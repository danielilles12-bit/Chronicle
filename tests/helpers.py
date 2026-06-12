"""Shared test plumbing: static server, browser contexts, console-error capture."""
import contextlib
import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PORT = 8200 + (os.getpid() % 400)


@contextlib.contextmanager
def server():
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--directory", ROOT],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        base = "http://127.0.0.1:%d" % PORT
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


@contextlib.contextmanager
def page_on(p, engine="webkit", base=None, device="iPhone 13"):
    """A page with console error capture; device=None gives a plain desktop context."""
    browser = getattr(p, engine).launch()
    ctx = browser.new_context(**dict(p.devices[device])) if device else browser.new_context()
    page = ctx.new_page()
    errors = []
    page.on("console", lambda m: errors.append("console: " + m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append("pageerror: " + str(e)))
    try:
        yield page, errors
    finally:
        browser.close()


def fail_on_errors(errors, label):
    if errors:
        print("FAIL [%s] console/page errors:" % label)
        for e in errors:
            print("  -", e)
        raise AssertionError("console errors in " + label)
