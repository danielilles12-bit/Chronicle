#!/usr/bin/env python3
"""Play the Zoom In game deterministically: assert the reveal-scoring math,
forgiving-but-strict matching, and kill-before-Next resume."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
from helpers import server, page_on, fail_on_errors  # noqa: E402


def item(pg):
    r = pg.evaluate("window.__CHRONICLE_TEST__.revealRound")
    d = pg.evaluate("window.__CHRONICLE_TEST__.data.reveal")
    return next(x for x in d if x["id"] == r["id"])


def main():
    with server() as base, sync_playwright() as p:
        with page_on(p, "webkit") as (pg, errors):
            pg.goto(base + "/?revealseed=7")
            pg.wait_for_selector("#card-reveal")
            pg.click("#card-reveal")
            pg.wait_for_selector("#rv-start")
            pg.click("#rv-start")
            pg.wait_for_selector("#rv-frame")

            total = int(pg.text_content("#rv-progress").split("of")[1])
            score = 0
            for i in range(total):
                it = item(pg)
                if i == 0:                       # nailed from the first crop -> 100
                    pg.fill("#rv-input", it["name"]); pg.click("#rv-guess-btn")
                    score += 100
                elif i == 1:                     # one wrong (reveals more) then right -> 80 +10 streak
                    pg.fill("#rv-input", "totally wrong"); pg.click("#rv-guess-btn")
                    pg.wait_for_timeout(150)
                    pg.fill("#rv-input", it["name"]); pg.click("#rv-guess-btn")
                    score += 90
                else:                            # give up -> 0, streak broken
                    pg.click("#rv-reveal")
                pg.wait_for_selector("#rv-feedback", state="visible")
                assert it["name"] in pg.text_content("#rv-feedback"), it["name"]
                shown = pg.text_content("#rv-score").strip()
                assert shown == "%d pts" % score, (shown, score, i)
                pg.click("#rv-next")

            pg.wait_for_selector("#rv-sum-total")
            assert pg.text_content("#rv-sum-total").strip() == str(score)
            assert pg.locator("#rv-sum-rounds li").count() == total
            print("zoom-in session total:", score)

            # best persists; the finished session clears
            pg.click("#rv-sum-home")
            pg.click("#card-reveal")
            assert str(score) in pg.text_content("#rv-best")
            assert pg.locator("#rv-resume").is_hidden(), "finished session must clear"

            # forgiving-but-strict matching (numeral guard still bites)
            checks = pg.evaluate("""(() => {
              const T = window.__CHRONICLE_TEST__;
              const by = id => T.data.reveal.find(x => x.id === id);
              return {
                variant: T.isMatch('lincoln', by('lincoln')),
                typo: T.isMatch('napoleon bonapart', by('napoleon')),
                tutShort: T.isMatch('king tut', by('tut-mask')),
                liz1not2: T.isMatch('elizabeth ii', by('elizabeth-i')),
              };
            })()""")
            assert checks["variant"] and checks["typo"] and checks["tutShort"], checks
            assert checks["liz1not2"] is False, "Elizabeth II must not match Elizabeth I"

            # an interrupted session resumes at the next unanswered round
            pg.click("#rv-start")
            pg.wait_for_selector("#rv-frame")
            it = item(pg)
            pg.fill("#rv-input", it["name"]); pg.click("#rv-guess-btn")
            pg.wait_for_selector("#rv-feedback", state="visible")
            sb = pg.text_content("#rv-score").strip()
            pg.reload()                                  # killed before tapping Next
            pg.wait_for_selector("#card-reveal")
            pg.click("#card-reveal")
            pg.wait_for_selector("#rv-resume", state="visible")
            assert "round 2" in pg.text_content("#rv-resume")
            pg.click("#rv-resume")
            pg.wait_for_selector("#rv-frame")
            assert pg.text_content("#rv-progress").strip().startswith("Round 2")
            assert pg.text_content("#rv-score").strip() == sb
            assert item(pg)["id"] != it["id"], "resume must not replay the scored round"

            fail_on_errors(errors, "zoom in")
    print("ZOOM IN TESTS OK (total %d)" % score)


if __name__ == "__main__":
    main()
