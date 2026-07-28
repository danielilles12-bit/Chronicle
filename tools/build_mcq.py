#!/usr/bin/env python3
"""Multiple-choice distractor generator (Daniel's "ultimate clue", 28 Jul 2026).

For every Face Value portrait, Relic artefact and Lifeline figure, pick TWO
in-pool distractor names and bake them into the data files as
`"mcq": ["Name A", "Name B"]`. The client shows the real answer plus these
two as the last-resort clue; a correct pick pays a capped score.

Design brief (Daniel): distractors must be *genuinely difficult* even on
easy rounds — for Vivien Leigh, think Elizabeth Taylor, not Genghis Khan.
"Similar kind" beats "similar obscurity": a famous target gets famous
same-type distractors.

Quality rules, in order of weight:
  1. Same occupation/kind. Lifeline figures carry `occupation` directly;
     who/what items resolve occupation_family/kind via tools/fame/tags.json
     (the same alias index the edition compiler uses).
  2. Era proximity by death year (tags/universe/figures), and for PORTRAITS
     a hard photography-era gate: a photographed face (death >= 1850) never
     gets a bust-era distractor, and vice versa. The torn image gives away
     the medium; an implausible-era name is a giveaway, not a distractor.
  3. Gender must match for portraits when known (the image gives it away).
     Source: Wikidata P21 by QID (batched, cached in
     tools/fame/mcq_gender.json), falling back to blurb pronouns.
  4. Fame: prefer distractors at similar-or-higher fame than the target.
  5. Region: mild preference for the same macroregion (an "actress of a
     similar kind" is usually also from a similar world).

Hard exclusions: the item itself; any candidate whose name/variants overlap
the target's (two ids for one person — the herodotus problem); candidates
with no display name.

Deterministic: pure function of the data files + caches. No RNG — every
player sees the same three options for a given round (Wordle convention),
and re-runs without data changes are no-ops.

Run from repo root:  python3 tools/build_mcq.py [--check] [--offline]
  --check    validate existing mcq fields instead of writing (CI-friendly)
  --offline  never touch the network (gender falls back to cache + pronouns)
"""
import json
import sys
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAME = ROOT / "tools/fame"
GENDER_CACHE = FAME / "mcq_gender.json"

WHO = ROOT / "data/reveal-who.json"
WHAT = ROOT / "data/reveal-what.json"
FIGS = ROOT / "data/figures.json"

ERA_ORDER = ["ancient", "classical", "medieval", "early-modern", "nineteenth",
             "twentieth", "contemporary"]
PHOTO_YEAR = 1850   # death at/after this = plausibly photographed

# Curated (family, fine) overrides for items tags.json mislabels — grow this
# list as spot-checks find more. (tutankhamun sits as 'religious' in tags,
# which paired his gold mask with Moses instead of fellow pharaohs. The tags
# mislabel also nudges the edition compiler's tone caps — flagged 28 Jul,
# fix belongs in build_tags, not here.)
OCC_OVERRIDES = {
    "tutankhamun": ("ruler", "PHARAOH"),
    "akhenaten": ("ruler", "PHARAOH"),
    "ramesses-ii": ("ruler", "PHARAOH"),
    "hatshepsut": ("ruler", "PHARAOH"),
}


def normalise(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return " ".join("".join(c if c.isalnum() or c.isspace() else " "
                            for c in s.lower()).split())


def name_keys(item):
    keys = {normalise(item.get("name", ""))}
    for v in item.get("variants") or []:
        keys.add(normalise(v))
    keys.discard("")
    return keys


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, items):
    path.write_text(json.dumps(items, indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def build_alias_index(records, *key_fields):
    idx = {}
    for r in records:
        for f in key_fields:
            k = r.get(f)
            if k:
                idx.setdefault(normalise(k), r)
    return idx


def lookup(idx, item):
    for nm in [item.get("name")] + list(item.get("variants") or []):
        if nm and normalise(nm) in idx:
            return idx[normalise(nm)]
    return None


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------
def load_signals():
    tags = load(FAME / "tags.json")
    tag_people = build_alias_index(
        [dict(v, _k=k) for k, v in tags.get("people", {}).items()], "_k")
    tag_objects = build_alias_index(
        [dict(v, _k=k) for k, v in tags.get("objects", {}).items()], "_k")
    fame_rows = load(FAME / "fame_scores.json")["scores"]
    fame_idx = build_alias_index(fame_rows, "name", "wiki_title")
    uni = load(FAME / "universe_people.json")
    if isinstance(uni, dict):   # container dict with metadata keys
        uni = next(v for v in uni.values() if isinstance(v, list))
    uni_idx = build_alias_index(uni, "name", "wiki_title")
    return tag_people, tag_objects, fame_idx, uni_idx


def death_year(item, tag_rec, uni_rec):
    if isinstance(item.get("death"), dict) and item["death"].get("year") is not None:
        return item["death"]["year"]
    for rec in (tag_rec, uni_rec):
        if rec and rec.get("death_year") is not None:
            return rec["death_year"]
    return None


def era_rank(tag_rec):
    if tag_rec and tag_rec.get("era") in ERA_ORDER:
        return ERA_ORDER.index(tag_rec["era"])
    return None


# ---------------------------------------------------------------------------
# Gender (portraits only)
# ---------------------------------------------------------------------------
def blurb_gender(item):
    text = " %s " % normalise(item.get("blurb", ""))
    fem = sum(text.count(" %s " % w) for w in ("she", "her", "hers", "herself"))
    masc = sum(text.count(" %s " % w) for w in ("he", "his", "him", "himself"))
    if fem and not masc:
        return "female"
    if masc and not fem:
        return "male"
    return None


def fetch_wikidata_genders(qids):
    """qid -> 'male'/'female'/None via wbgetentities, 50 at a time."""
    out = {}
    for i in range(0, len(qids), 50):
        batch = qids[i:i + 50]
        url = ("https://www.wikidata.org/w/api.php?action=wbgetentities&format=json"
               "&props=claims&ids=" + urllib.parse.quote("|".join(batch)))
        req = urllib.request.Request(url, headers={
            "User-Agent": "DeadFamous-mcq-builder/1.0 (deadfamous.app)"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
        for qid, ent in (data.get("entities") or {}).items():
            claims = (ent.get("claims") or {}).get("P21") or []
            val = None
            for c in claims:
                v = (((c.get("mainsnak") or {}).get("datavalue") or {})
                     .get("value") or {})
                val = {"Q6581097": "male", "Q6581072": "female"}.get(v.get("id"), val)
            out[qid] = val
    return out


def resolve_genders(who_items, uni_idx, offline):
    cache = load(GENDER_CACHE) if GENDER_CACHE.exists() else {}
    by_id = {}
    missing = {}
    for item in who_items:
        if item["id"] in cache:
            by_id[item["id"]] = cache[item["id"]]
            continue
        g = blurb_gender(item)
        uni = lookup(uni_idx, item)
        qid = uni.get("qid") if uni else None
        if qid and not offline:
            missing[item["id"]] = (qid, g)
        else:
            by_id[item["id"]] = g
    if missing:
        try:
            fetched = fetch_wikidata_genders(sorted({q for q, _ in missing.values()}))
        except Exception as e:
            print(f"build_mcq: WARNING — Wikidata gender fetch failed ({e}); "
                  f"falling back to blurb pronouns", file=sys.stderr)
            fetched = {}
        for item_id, (qid, fallback) in missing.items():
            by_id[item_id] = fetched.get(qid) or fallback
    cache.update(by_id)
    GENDER_CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n",
                            encoding="utf-8")
    return by_id


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------
def occupation_of(game, item, tag_people, tag_objects, uni_idx):
    """(broad family, fine occupation) — either may be None.

    NOTE figures.json's own `occupation` field is the Claim-to-fame HINT
    SENTENCE ("Guitarist who turned feedback into a national anthem"), not
    a category — never match on it. People in both games resolve the broad
    family via tags.json and the finer slot (MUSICIAN vs COMPOSER) via the
    harvest universe; objects use tags kind as the family."""
    if item.get("id") in OCC_OVERRIDES:
        return OCC_OVERRIDES[item["id"]]
    if game == "what":
        rec = lookup(tag_objects, item)
        return ((rec or {}).get("kind"), None)
    rec = lookup(tag_people, item)
    uni = lookup(uni_idx, item)
    family = (rec or {}).get("occupation_family") \
        or (uni or {}).get("domain")
    fine = (uni or {}).get("occupation")
    return (family, fine)


def pick_distractors(game, items, signals, genders):
    tag_people, tag_objects, fame_idx, uni_idx = signals
    tag_idx = tag_objects if game == "what" else tag_people

    meta = {}
    for it in items:
        tag = lookup(tag_idx, it)
        uni = lookup(uni_idx, it) if game != "what" else None
        fame_rec = lookup(fame_idx, it)
        meta[it["id"]] = {
            "keys": name_keys(it),
            "occ": occupation_of(game, it, tag_people, tag_objects, uni_idx),
            "dy": death_year(it, tag, uni),
            "era": era_rank(tag),
            "region": (tag or {}).get("region"),
            "fame": (fame_rec or {}).get("fame"),
            "gender": genders.get(it["id"]) if genders else None,
        }

    out = {}
    for t in items:
        tm = meta[t["id"]]
        scored = []
        for c in items:
            if c["id"] == t["id"]:
                continue
            cm = meta[c["id"]]
            if tm["keys"] & cm["keys"]:
                continue          # same person under two ids
            if game == "who" and tm["dy"] is not None and cm["dy"] is not None:
                if (tm["dy"] >= PHOTO_YEAR) != (cm["dy"] >= PHOTO_YEAR):
                    continue      # photo face vs bust-era name = giveaway
            if game == "who" and tm["gender"] and cm["gender"] \
                    and tm["gender"] != cm["gender"]:
                continue          # the torn portrait shows this
            score = 0.0
            t_fam, t_fine = tm["occ"]
            c_fam, c_fine = cm["occ"]
            if t_fam and c_fam and t_fam == c_fam:
                score += 100.0
            if t_fine and c_fine and t_fine == c_fine:
                score += 40.0
            if tm["dy"] is not None and cm["dy"] is not None:
                score += max(0.0, 60.0 - abs(tm["dy"] - cm["dy"]) / 5.0)
            elif tm["era"] is not None and cm["era"] is not None:
                score += max(0.0, 40.0 - 20.0 * abs(tm["era"] - cm["era"]))
            if tm["fame"] is not None and cm["fame"] is not None:
                if cm["fame"] >= tm["fame"] - 10:
                    score += 25.0
                score -= min(25.0, abs(tm["fame"] - cm["fame"]) / 4.0)
            if tm["region"] and cm["region"] and tm["region"] == cm["region"]:
                score += 10.0
            if game == "who" and tm["gender"] and not cm["gender"]:
                score -= 15.0     # unknown gender is a risk on a portrait
            scored.append((-score, c["id"], c["name"]))
        scored.sort()
        out[t["id"]] = [nm for _, _, nm in scored[:2]]
    return out


def check_items(game, items):
    bad = []
    for it in items:
        mcq = it.get("mcq")
        if (not isinstance(mcq, list) or len(mcq) != 2
                or any(not isinstance(x, str) or not x.strip() for x in mcq)
                or len({normalise(x) for x in mcq} | {normalise(it["name"])}) != 3
                or ({normalise(x) for x in mcq} & name_keys(it))):
            bad.append(f"{game}/{it['id']}: bad mcq {mcq!r}")
    return bad


def main():
    check_only = "--check" in sys.argv[1:]
    offline = "--offline" in sys.argv[1:]

    who_all = load(WHO)
    what_all = load(WHAT)
    figs = load(FIGS)
    # reveal-who.json holds portraits only by construction, but filter by
    # kind anyway so a future mixed file can't cross-pollinate distractors.
    who = [x for x in who_all if x.get("kind") == "portrait"]
    what = [x for x in what_all if x.get("kind") != "portrait"]

    if check_only:
        bad = (check_items("who", who) + check_items("what", what)
               + check_items("map", figs))
        for b in bad:
            print("ERROR " + b, file=sys.stderr)
        print(f"build_mcq --check: {len(who) + len(what) + len(figs)} items, "
              f"{len(bad)} errors")
        return 1 if bad else 0

    signals = load_signals()
    genders = resolve_genders(who, signals[3], offline)

    for game, items, path, all_items in (
            ("who", who, WHO, who_all),
            ("what", what, WHAT, what_all),
            ("map", figs, FIGS, figs)):
        picks = pick_distractors(game, items, signals,
                                 genders if game == "who" else None)
        n = 0
        for it in all_items:
            if it["id"] in picks and len(picks[it["id"]]) == 2:
                if it.get("mcq") != picks[it["id"]]:
                    it["mcq"] = picks[it["id"]]
                    n += 1
        save(path, all_items)
        short = [i for i, p in picks.items() if len(p) < 2]
        print(f"build_mcq: {game}: {len(items)} items, {n} mcq fields written"
              + (f", {len(short)} SHORT: {short[:5]}" if short else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
