#!/usr/bin/env python3
"""Complete every shipped crossword end-to-end through the real UI (WebKit,
iPhone viewport), plus direction toggle, check/reveal, wrong-fill toast and
persistence."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
from helpers import ROOT, server, page_on, fail_on_errors  # noqa: E402


def cw_state(pg):
    return pg.evaluate("window.__CHRONICLE_TEST__.cw")


def open_puzzle(pg, pid):
    pg.click('.cwitem[data-pid="%s"]' % pid)
    pg.wait_for_selector("#cw-grid .cell:not(.block)")


def solve_correctly(pg, leave_one_wrong=False):
    """Type the correct letter at whatever cell the engine selects."""
    wrong_at = None
    for _ in range(1200):
        st = cw_state(pg)
        if st["completed"]:
            break
        entries, sol = st["entries"], st["sol"]
        empties = [i for i, s in enumerate(sol) if s != "#" and not entries[i]]
        if not empties:
            break
        i = st["sel"]
        if not entries[i] or entries[i] != sol[i]:
            if leave_one_wrong and len(empties) == 1 and wrong_at is None:
                wrong_at = i
                pg.keyboard.press("X" if sol[i] != "X" else "Z")
            else:
                pg.keyboard.press(sol[i])
        else:
            pg.keyboard.press(sol[i])
    return wrong_at


def main():
    puzzles = json.load(open(os.path.join(ROOT, "data", "puzzles.json")))
    with server() as base, sync_playwright() as p:
        with page_on(p, "webkit") as (pg, errors):
            pg.goto(base + "/")
            pg.wait_for_selector("#card-crossword")

            # --- solve every puzzle in the real UI ---
            for pz in puzzles:
                pg.click("#card-crossword")
                pg.wait_for_selector(".cwitem")
                open_puzzle(pg, pz["id"])
                solve_correctly(pg)
                st = cw_state(pg)
                assert st["completed"], "%s did not complete" % pz["id"]
                pg.wait_for_selector("#cw-done", state="visible")
                sub = pg.text_content("#cw-done-sub")
                assert "solved in" in sub, sub
                pg.click("#cw-done-back")
                pg.wait_for_selector(".cwitem")
                state = pg.text_content('.cwitem[data-pid="%s"] .cw-state' % pz["id"])
                assert "✓" in state, "list does not show solved state for " + pz["id"]
                pg.click("#view-cwlist [data-back]")
                pg.wait_for_selector("#card-crossword")
                print("solved:", pz["id"])

            fail_on_errors(errors, "solve-all")

        # --- interaction details on a fresh profile ---
        with page_on(p, "webkit") as (pg, errors):
            pg.goto(base + "/")
            pg.wait_for_selector("#card-crossword")
            pg.click("#card-crossword")
            pg.wait_for_selector(".cwitem")
            first = puzzles[0]
            open_puzzle(pg, first["id"])

            # direction toggle: tapping the selected cell flips direction
            st = cw_state(pg)
            sel = st["sel"]
            assert st["dir"] == "across"
            pg.click('#cw-grid .cell[data-i="%d"]' % sel)
            assert cw_state(pg)["dir"] == "down", "tap same cell should toggle to down"
            pg.click("#cw-clue-current")
            assert cw_state(pg)["dir"] == "across", "clue bar tap should toggle back"

            # type a wrong letter, check square marks it, reveal square fixes it
            st = cw_state(pg)
            sel = st["sel"]
            wrong = "X" if st["sol"][sel] != "X" else "Z"
            pg.keyboard.press(wrong)
            pg.click('#cw-grid .cell[data-i="%d"]' % sel)  # reselect
            pg.click("#cw-menu-btn")
            pg.click('#cw-sheet [data-check="square"]')
            assert pg.locator('#cw-grid .cell[data-i="%d"].wrong' % sel).count() == 1, \
                "check square should mark the wrong letter"
            pg.click("#cw-menu-btn")
            pg.click('#cw-sheet [data-reveal="square"]')
            st = cw_state(pg)
            assert st["entries"][sel] == st["sol"][sel], "reveal square should correct the cell"
            assert pg.locator('#cw-grid .cell[data-i="%d"].revealed' % sel).count() == 1

            # clue list overlay opens and navigates
            pg.click("#cw-cluelist-btn")
            pg.wait_for_selector("#cw-cluelist", state="visible")
            pg.click("#cw-cluelist-down .tab" if False else '#cw-cluelist .tab[data-tab="down"]')
            pg.click("#cw-cluelist-down li")
            assert cw_state(pg)["dir"] == "down"

            # fill the grid with one wrong letter -> toast, no celebration
            wrong_at = solve_correctly(pg, leave_one_wrong=True)
            pg.wait_for_selector("#cw-toast", state="visible")
            assert not cw_state(pg)["completed"]
            assert pg.locator("#cw-done").is_hidden(), "no celebration on incorrect grid"
            pg.click('#cw-grid .cell[data-i="%d"]' % wrong_at)
            st = cw_state(pg)
            pg.keyboard.press(st["sol"][wrong_at])
            pg.wait_for_selector("#cw-done", state="visible")
            assert cw_state(pg)["completed"], "fixing the wrong letter should complete"

            fail_on_errors(errors, "interactions")

        # --- persistence across reload ---
        with page_on(p, "webkit") as (pg, errors):
            pg.goto(base + "/")
            pg.wait_for_selector("#card-crossword")
            pg.click("#card-crossword")
            open_puzzle(pg, puzzles[0]["id"])
            st = cw_state(pg)
            sel = st["sel"]
            pg.keyboard.press(st["sol"][sel])
            pg.reload()
            pg.wait_for_selector("#card-crossword")
            pg.click("#card-crossword")
            state = pg.text_content('.cwitem[data-pid="%s"] .cw-state' % puzzles[0]["id"])
            assert "In progress" in state, "progress should survive reload, got: " + state
            open_puzzle(pg, puzzles[0]["id"])
            st2 = cw_state(pg)
            assert st2["entries"][sel] == st["sol"][sel], "entry should survive reload"
            fail_on_errors(errors, "persistence")

    print("CROSSWORD TESTS OK (%d puzzles solved end-to-end)" % len(puzzles))


if __name__ == "__main__":
    main()
