#!/usr/bin/env python3
"""
gate_candidates.py -- turn a harvest into a SHORTLIST, by measuring candidates
against the bar the shipped pool already sets.

The harvests (audience_candidates.json, object_candidates_v2.json) are a funnel
mouth, not an intake list. Left ungated they would roughly quadruple the pools
with material that is, on average, markedly less recognisable than what already
ships -- the exact failure the launch review complained about ("too obscure").

Three facts govern this script:

  1. VOLUME IS NOT THE NEED. At 5 rounds a day against the locked 42-day repeat
     target, each game needs 210 items. Face Value has 426, Lifeline 541, Relic
     364. Every pool is already past target, so nothing is added to make the
     rotation work -- only to widen SUBJECT MATTER or to replace a weak item.

  2. THE HONEST BAR IS THE POOL'S OWN DISTRIBUTION. A candidate that scores
     below the shipped pool's 25th percentile is more obscure than three
     quarters of what already airs. Rather than invent a threshold, this reads
     the percentile straight off the live pool, per game, so the bar moves with
     the content instead of drifting away from it.

  3. FAME ALONE SELECTS FOR RECENCY, so it cannot be the only bar. Gated on
     fame at p25, the shortlist opened: Concorde, Volkswagen Beetle, the ISS,
     "passenger car", the Order of the British Empire, Bing Crosby, an F-35,
     Joan Crawford, Shirley Temple, Fred Astaire, Dean Martin, Lucille Ball.
     That is a list of things people look up, not a list of history. Salience
     -- the history-lover score in SALIENCE.md -- is therefore a SECOND
     REQUIRED gate, derived the same way, off the pool's own distribution.

THE THREE GATES

  JUNK      Is it a specific, real, historical object at all? (objects only;
            the people harvest is humans by construction). See JUNK RULES.
  FAME      >= the shipped pool's fame at --percentile, for the most
            permissive game the candidate could serve.
  SALIENCE  >= the shipped pool's salience at the same percentile. Explorers
            and travellers are exempt from this one -- WikiProject coverage of
            exploration is so thin that a low score there means missing data,
            not obscurity (Thesiger 1.2, Speke 4.7 are both well known) -- but
            never from the project's absolute floor of 45.

            The exemption is for MISSING DATA, so it only fires where the data
            is actually missing: the candidate must carry no history-importance
            rating at all. That is the Thesiger case exactly ("thirteen project
            banners and still scores nothing, because none carry an importance
            value"). Without that condition the exemption is a side door for
            anyone whose occupation list happens to include "mountaineer" --
            it let Ansel Adams in at salience 68.5, and his 43.7 history rating
            is a judgement, not a gap. 296 of the 2,520 people read as
            explorers by occupation; only 22 of them have no rating.

JUNK RULES (objects), and why each one is here

  J1 A THING, NOT A KIND OF THING. The shipped Relic pool is 364 named,
     specific things and zero categories. "passenger car", "double bass" and
     "hookah" are categories: they have huge traffic because every article
     about a car, a cello or a shisha links to them, and nobody can be shown a
     photograph of *the* passenger car. Detected two ways: Wikidata typing the
     subject as "type of / class of ..." , or the harvest's own name having no
     capitalised or numeric word in it (Wikidata labels a named thing "Rosetta
     Stone" and a kind of thing "loom").
  J2 REAL AND PHYSICAL. Wikidata typing the subject as fictional, mythical,
     legendary, virtual, a character, software, a protocol, a standard, a
     company or a language. Relic shows a photograph of the object; Pandora's
     box and Hatsune Miku cannot be photographed.
  J3 A THING, NOT A STORY. Wikipedia filing the article under Mythology,
     Folklore, Paranormal, Fictional characters, Software or Video games AND
     Wikidata having no date for it (inception, start, service entry, opening,
     spacecraft launch). This is what catches legends that dodge J2: the
     Flying Dutchman is typed as an ordinary "fluyt" but filed under Folklore
     and Paranormal, and nothing anywhere knows when it is from. Both halves
     are needed, and the conjunction was measured against the shipped pool
     before being adopted: the WikiProject half alone condemns 7 live items
     (Venus de Milo, the Trundholm sun chariot, the Hope Diamond, the Nazca
     lines, the Piri Reis map -- real objects that merely have a myth attached)
     and the date half alone condemns 100 of the 364 (Wikidata has no date for
     the Dead Sea Scrolls, the Benin Bronzes or the Enola Gay). Together they
     condemn 2: the Hope Diamond and Kannon. A 0.5% false-positive rate
     against known-good content is the price of catching ghost ships.
  J4 FIFTY YEARS OLD. Dated 1976 or earlier. Read off the pool, not invented:
     of the 264 shipped Relic items Wikidata can date, 261 (99%) are older
     than 1976, only 10 are post-1950, and the newest thing in the pool is the
     1986 Musee d'Orsay. An F-35, the ISS, the James Webb telescope and a
     Chengdu J-20 are current events with a WikiProject rating, not history.
     The line sits exactly 50 years back, and Concorde (service entry 1976),
     the Model T and Sputnik 1 all clear it.

  J4 is deliberately NOT applied to people. The same measurement on the pool
  says the opposite there: 82 of the 541 Lifeline figures (15%) died in 1976
  or later, 62 since 1990. The pool is happy with recent lives; salience is
  what decides whether a recent life is a historical one.

Usage:
    python3 build_salience.py --skip-universe \
        --candidates audience_candidates.json \
        --candidates object_candidates_v2.json \
        --out ../out/salience-candidates.json
    python3 gate_candidates.py [--percentile 25] [--out shortlist.json]

Reads (all read-only): fame_scores.json, the salience appraisal run,
audience_candidates.json, object_candidates_v2.json, and the three shipped
pools under data/. Writes only the shortlist it is asked for.

A KNOWN LIMIT, worth stating because it shapes the answer. `fame` is a
percentile *within class* (build_scores.py: "percentiles are not comparable
across classes"), and build_scores files the shipped Relic pool under
structure/artefact/artwork while filing almost every harvested object under
its catch-all "other". The candidate side of the fame gate is therefore
measured in a weaker crowd, which makes it harder, not softer: the objects
clearing the bar here have a median of 59,000 daily-view-stat against the
shipped pool's 19,000. The shortlist is conservative for objects. Salience is
free of this -- the appraisal run ranks both sides in one population.

Python 3.9 stdlib only.
"""
import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent.parent / "data"
SALIENCE_RUN = HERE.parent / "out" / "salience-candidates.json"

# The project's documented "never schedule" floor (SALIENCE.md). The gate below
# is far stricter; this survives only as the one thing the explorer exemption
# cannot waive.
SALIENCE_FLOOR = 45
EXPLORATION_FAMILIES = {"exploration", "explorer", "exploration_travel"}
EXPLORATION_OCCUPATIONS = ("explorer", "traveller", "traveler", "navigator",
                           "mountaineer", "polar explorer", "circumnavigator")

# J4: an object must be at least half a century old. See the docstring for the
# measurement of the shipped pool this is read off.
HISTORY_HORIZON_YEAR = 1976

# J1: Wikidata's own word for "this entry describes a KIND of thing".
GENERIC_CLASS_RE = re.compile(
    r"^(type|class|kind|group|category|family|genre) of ", re.I)
# J2: ...and its words for "this is not a physical object with a history".
NOT_A_THING_RE = re.compile(
    r"\b(fiction|fictional|myth|mythical|mythology|mythological|legend|"
    r"legendary|virtual|character|software|video game|protocol|standard|"
    r"company|business|organi[sz]ation|website|brand|trademark|language)\b",
    re.I)
# J3: the WikiProjects that mean "this article is about a story". Only ever
# used in conjunction with "and nothing knows when it is from" -- see the
# docstring for the measurement that forced the conjunction.
STORY_PROJECTS = {"Mythology", "Folklore", "Paranormal", "Fictional characters",
                  "Legendary creatures", "Software", "Video games", "Comics",
                  "Anime and manga"}
BARE_QID_RE = re.compile(r"^Q\d+$")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def fame_index():
    rows = load(HERE / "fame_scores.json")["scores"]
    return {r["wiki_title"]: r for r in rows}


def salience_run(path):
    """(title -> scored row, pool items) from a build_salience.py candidate run.

    The pool items travel in the same file on purpose: `salience` is a
    percentile, so the bar and the candidates have to come out of one ranking
    or the comparison is meaningless.
    """
    blob = load(path)
    if not blob.get("counts", {}).get("candidate_titles"):
        raise SystemExit(
            "%s holds no candidate scores. Build the appraisal run first:\n"
            "  python3 build_salience.py --skip-universe \\\n"
            "      --candidates audience_candidates.json \\\n"
            "      --candidates object_candidates_v2.json \\\n"
            "      --out %s" % (path, SALIENCE_RUN))
    return {t["wiki_title"]: t for t in blob["titles"]}, blob["items"]


def shipped_names():
    """Every name and accepted variant already in a shipped pool.

    The harvests dedupe against the universe and inventory files, which misses
    ~20 items that are live in the game but reached the pools by another route.
    They score highly, so they crowd the top of any shortlist -- exactly where a
    reviewer's attention goes. Catch them here, against the pools themselves.
    """
    out = set()
    for fn in ("reveal-who.json", "reveal-what.json", "figures.json"):
        for item in load(DATA / fn):
            out.add(item["name"].strip().lower())
            for v in item.get("variants") or []:
                out.add(v.strip().lower())
    return out


def pool_bar(items, game, field, pct):
    """The value at the given percentile of what this game already ships."""
    vals = sorted(i[field] for i in items
                  if i.get("game") == game and i.get(field) is not None)
    if not vals:
        return None
    return vals[min(int(len(vals) * pct / 100), len(vals) - 1)]


def explorer_exemption(cand, scored):
    """True when a low salience here is missing data rather than obscurity.

    Both halves are required: the candidate has to be an explorer or
    traveller, AND English Wikipedia has to have failed to rate them -- see
    the docstring.
    """
    if (scored or {}).get("components", {}).get("history_importance") is not None:
        return False
    fam = {(cand.get(k) or "").lower()
           for k in ("domain", "primary_family", "kind")}
    if fam & EXPLORATION_FAMILIES:
        return True
    if any(f.lower() in EXPLORATION_FAMILIES for f in cand.get("families") or []):
        return True
    occ = " ".join(cand.get("occupations") or []).lower()
    return any(word in occ for word in EXPLORATION_OCCUPATIONS)


def junk_verdict(cand, scored):
    """None if the candidate is a specific real historical object, else why not.

    People are exempt: the audience harvest is humans with birth and death
    dates by construction, so J1/J3/J4 have nothing to say about them and J2
    would only ever fire on a data error.
    """
    name = (cand.get("name") or "").strip()
    labels = (scored or {}).get("instance_of_labels") or []
    status = (scored or {}).get("title_status")

    if BARE_QID_RE.match(name):
        return "no article behind it (the name is a bare Wikidata id)"
    if status and status != "ok":
        return "the article is %s" % status.replace("_", " ")
    if scored is None or (scored.get("class") != "artefact"):
        return None

    if any(GENERIC_CLASS_RE.match(l) for l in labels):
        return "a kind of thing, not a thing (Wikidata: %s)" % labels[0]
    if not any(w[:1].isupper() or w[:1].isdigit()
               for w in re.split(r"[\s\-—/]+", name)):
        return "a kind of thing, not a thing (no name, just a common noun)"
    hit = next((l for l in labels if NOT_A_THING_RE.search(l)), None)
    if hit:
        return "not a physical historical object (Wikidata: %s)" % hit

    year = scored.get("dated_year")
    story = sorted(set(scored.get("wikiprojects") or []) & STORY_PROJECTS)
    if year is None and story:
        return ("a story, not a thing (undated, and Wikipedia files it under %s)"
                % ", ".join(story))
    if year is not None and year > HISTORY_HORIZON_YEAR:
        return "too recent (%d) — less than fifty years old" % year
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--percentile", type=int, default=25,
                    help="percentile of the shipped pool a candidate must clear "
                         "on BOTH fame and salience (default 25; use 50 for a "
                         "stricter, median bar)")
    ap.add_argument("--salience", default=str(SALIENCE_RUN),
                    help="the build_salience.py run that scored the candidates "
                         "alongside the pools")
    ap.add_argument("--out", default=None, help="write the shortlist here")
    args = ap.parse_args()

    fame = fame_index()
    scores, pool_items = salience_run(args.salience)

    games = ("who", "map", "what")
    fbars = {g: pool_bar(pool_items, g, "fame", args.percentile) for g in games}
    sbars = {g: pool_bar(pool_items, g, "salience", args.percentile)
             for g in games}
    print("the shipped pool at p%d --" % args.percentile)
    for g in games:
        print("  %-5s fame %.1f, salience %.1f" % (g, fbars[g], sbars[g]))

    already = shipped_names()
    kept, rejected, junked_but_scored = [], {}, []

    def reject(reason):
        rejected[reason] = rejected.get(reason, 0) + 1

    for src, path, plays in (
        ("people", HERE / "audience_candidates.json", ("who", "map")),
        ("objects", HERE / "object_candidates_v2.json", ("what",)),
    ):
        if not path.exists():
            continue
        blob = load(path)
        items = blob["candidates"] if isinstance(blob, dict) and "candidates" in blob else blob
        scored_n = 0
        for c in items:
            title = c.get("wiki_title") or c.get("name")
            if (c.get("name") or "").strip().lower() in already:
                reject("already in a shipped pool")
                continue
            if c.get("recognition") == "specialist" or \
                    c.get("recognition_tier") == "specialist":
                reject("harvest itself calls it specialist")
                continue

            sc = scores.get(title)
            row = fame.get(title)
            fbar = min(fbars[g] for g in plays)
            sbar = min(sbars[g] for g in plays)
            f = row["fame"] if row else None
            sal = (sc or {}).get("salience")
            clears_fame = f is not None and f >= fbar
            exempt = explorer_exemption(c, sc)
            clears_sal = sal is not None and (
                sal >= sbar or (exempt and sal >= SALIENCE_FLOOR))

            junk = junk_verdict(c, sc)
            if junk:
                if clears_fame and clears_sal:
                    junked_but_scored.append(
                        {"name": c.get("name"), "fame": round(f, 1),
                         "salience": round(sal, 1), "why": junk})
                reject("junk: " + junk.split(" (")[0].split(" —")[0])
                continue
            if row is None:
                reject("never measured (no fame score)")
                continue
            scored_n += 1
            if not clears_fame:
                reject("below the pool's fame bar")
                continue
            if sal is None:
                reject("no salience score")
                continue
            if not clears_sal:
                reject("below the pool's salience bar")
                continue

            kept.append({
                "source": src, "name": c.get("name"), "wiki_title": title,
                "fame": round(f, 1), "salience": round(sal, 1),
                "combined": round((f + sal) / 2, 1),
                "kind": c.get("kind") or c.get("primary_family"),
                "region": c.get("region") or c.get("culture_region"),
                "dated_year": sc.get("dated_year"),
                "death_year": c.get("death_year"),
                "occupations": (c.get("occupations") or [])[:3],
                "instance_of": (sc.get("instance_of_labels") or [])[:3],
                "history_rating": sc["components"].get("history_best_rating"),
                "history_project": sc["components"].get("history_best_project"),
                "in_our_time": sc["components"].get("in_our_time"),
                "vital_level": sc["components"].get("vital_level"),
                "explorer_exemption": bool(exempt and sal < sbar),
            })
        print("  %s: %d candidates, %d measurable against the pool"
              % (src, len(items), scored_n))

    kept.sort(key=lambda r: -r["combined"])
    total = sum(rejected.values()) + len(kept)
    print("\nSHORTLIST: %d of %d candidates clear every gate" % (len(kept), total))
    for k, v in sorted(rejected.items(), key=lambda kv: -kv[1]):
        print("  rejected, %-38s %5d" % (k, v))
    if junked_but_scored:
        print("\n%d junk-rejected candidates would have cleared both score "
              "bars:" % len(junked_but_scored))
        for r in sorted(junked_but_scored, key=lambda r: -r["fame"]):
            print("  %-38s fame %5.1f salience %5.1f -- %s"
                  % (r["name"][:38], r["fame"], r["salience"], r["why"]))

    if args.out:
        Path(args.out).write_text(
            json.dumps({"bar_percentile": args.percentile,
                        "fame_bars": fbars, "salience_bars": sbars,
                        "counts": {"candidates": total, "shortlisted": len(kept),
                                   "rejected": rejected},
                        "junked_but_scored": junked_but_scored,
                        "shortlist": kept}, indent=1, ensure_ascii=False),
            encoding="utf-8")
        print("\nwrote %s" % args.out)


if __name__ == "__main__":
    main()
