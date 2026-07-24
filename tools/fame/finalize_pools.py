#!/usr/bin/env python3
"""
finalize_pools.py -- applies Daniel's 2026-07-24 pool-review verdicts
(verdicts-pool-2026-07-24.txt, including the five live amendments appended
to that file during this session) to pool_proposal.json, producing
tools/fame/final_pools.json.

Python 3.9 stdlib only. Read-only against pool_proposal.json, fame_scores.json,
tags.json, image_availability.json, universe_objects.json,
current_inventory.json, and propose_pools.py (imported for its playability
filter / sensitivity-flag helpers -- not modified). Writes only
tools/fame/final_pools.json.

Run: python3 finalize_pools.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import propose_pools as pp  # noqa: E402  (re-use its playability/sensitivity logic)

GENERATED_ON = "2026-07-24"
TARGETS = {"who": 400, "map": 450, "what": 350}


def load(name):
    with open(os.path.join(HERE, name), "r", encoding="utf-8") as f:
        return json.load(f)


def dump(obj, name):
    path = os.path.join(HERE, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, sort_keys=False)
        f.write("\n")
    return path


# ===========================================================================
# SECTION 1 -- verdict tables transcribed from verdicts-pool-2026-07-24.txt
# ===========================================================================

# [QUEUE] INCLUDE -- these people were already drafted as "add" or "keep" in
# pool_proposal.json (that's *why* they showed up in flagged_for_owner for
# review). The owner's verdict is simply: confirm them. We don't add or
# remove anything here -- we just relabel provenance so the finalized file
# shows *why* each one is in the pool. Keyed by (game, wiki_title).
QUEUE_INCLUDE = {
    ("who", "Adolf Hitler"), ("map", "Adolf Hitler"),
    ("who", "Jesus"), ("map", "Jesus"),
    ("who", "Benito Mussolini"), ("map", "Benito Mussolini"),
    ("what", "Little Boy"),
    ("what", "Enola Gay"),
    ("who", "Confucius"), ("map", "Confucius"),
    ("who", "Joseph Smith"),
    ("map", "Adolf Eichmann"),          # not a "who" candidate -- map only
    ("who", "The Buddha"), ("map", "The Buddha"),
    ("map", "Guru Nanak"),              # not a "who" candidate -- map only
}

# [QUEUE] EXCLUDE -- remove everywhere they appear, matched on exact
# wiki_title (never on substring -- "Muhammad Ali" / "Muhammad Ali Jinnah"
# are unrelated people and must NOT be touched).
QUEUE_EXCLUDE_WIKI_TITLES = {"Muhammad", "Auschwitz concentration camp", "Rwandan genocide"}

# [CONTESTED] -- the engine had proposed retiring all 12 of these "what"
# items; the owner confirmed 6 of the retirements and overrode the other 6
# back to keep.
CONTESTED_RETIRE_CONFIRMED = {
    "Carcassonne", "Cappadocia", "Pamukkale", "Moray",
    "Stone Town Zanzibar Door", "Olympia Stadium",
}
CONTESTED_KEEP_OVERRIDE = {
    "Great Mosque of Kairouan", "Naqsh-e Rustam", "Carnac Stones",
    "Gedi Ruins", "Great Buddha of Kamakura", "Rila Monastery",
}

# [VETO ADDS -- Relic] -- remove these 26 named "what" additions outright.
# Matched on the proposal's `name` field, which is an exact match for 25 of
# the 26; "Lumbini" is the one case where the proposal's display name is
# longer ("Lumbini, the Birthplace of the Lord Buddha") -- handled via the
# wiki_title override below instead of a name match.
VETO_ADD_NAMES = {
    "Boeing 747", "Burj Khalifa", "Volkswagen Beetle", "Carthage",
    "Willis Tower", "One World Trade Center", "Ephesus", "Fabergé egg",
    "Taipei 101", "Tyre", "Petronas Towers", "Ford Model T", "CN Tower",
    "Delphi", "London Eye", "Guernica", "Memphis", "Museum of Modern Art",
    "Burj Al Arab", "The Shard", "Thebes", "Mycenae", "Byblos",
    "Robben Island", "Marina Bay Sands",
}
VETO_ADD_WIKI_TITLES_EXTRA = {"Lumbini"}  # "Lumbini, the Birthplace of the Lord Buddha"

# GUERNICA FINDING (recorded for the report, not used for logic): the
# proposal's "Guernica" add row has wiki_title "Guernica (Picasso)" and is
# sourced from fame_scores.json as name="Guernica" / class "structure" --
# i.e. this was the Picasso PAINTING, not the Basque town. The veto removes
# it either way; recorded here so the finding survives in the code, not just
# the chat.
GUERNICA_WAS = "the Picasso painting (wiki_title 'Guernica (Picasso)'), not the town"

# ===========================================================================
# SECTION 2 -- Rule 1/2/3 extrapolation verdicts (owner's live amendments
# during review superseded the original brief for Chichen Itza / Teotihuacan
# / Petra; Pompeii is the one surviving swap). See the appended
# [AMENDMENT]/[CANONICAL TEST]/[ARTICULATION] blocks in
# verdicts-pool-2026-07-24.txt for the exact wording this codifies.
# ===========================================================================

# -- Rule-3 swap: name denotes a sprawling area bigger than any one picture.
# Pompeii is the sole case that fails the "postcard test" (many iconic
# images, each of something IN it, none fused with the name itself) among
# everything reviewed. The specific standing part becomes the new "what"
# addition; the old whole-site entry is retired with a pointer to its
# replacement.
RULE3_SWAP_KEEP_WIKI_TITLE = "Pompeii"
RULE3_SWAP_REPLACEMENT = {
    "name": "Villa of the Mysteries",
    "wiki_title": "Villa of the Mysteries",
    "fame": 98.73,          # inherited from Pompeii's slot -- no independent
                             # score exists locally for this title (not in
                             # fame_scores.json); carried over so its tier/
                             # ranking position in the pool doesn't collapse.
    "era": "ancient", "region": "Europe", "kind": "building",
    "image": "ok",           # manual assessment: the Roman frescoes are
                              # extremely well photographed and long PD;
                              # not machine-verified against
                              # image_availability.json (no entry there).
    "answer_aliases": ["pompeii"],
    "flags": [],
}

# -- Rule-3 NO-swaps (owner amendments): these stay wholesale, but gain
# answer_aliases so the fused specific building/part is also accepted.
# wiki_title -> aliases to ADD (existing name is always still accepted).
RULE3_ALIAS_ADDITIONS = {
    "Petra": ["al-khazneh", "the treasury", "treasury"],
    "Chichen Itza": ["el castillo"],
    "Teotihuacan": ["pyramid of the sun"],
    "Cahokia": ["cahokia"],  # trivial (== own name) but explicit per verdict
    "Angkor Wat": ["angkor"],  # own generous-alias judgment call -- see report
}

# -- Rule-3 fusion MERGE: "Pyramid of the Sun" already existed as its own
# standalone "what" keep item (fame 88.56, previously aired). Now that
# Teotihuacan stays wholesale with "pyramid of the sun" as an accepted
# alias, keeping BOTH as separate pool entries would let two different
# answers both legitimately match a photo of the same pyramid. Folded the
# older, lower-fame entry out; it survives only as an alias on Teotihuacan.
RULE3_MERGE_OUT_KEEP_WIKI_TITLE = "Pyramid of the Sun"
RULE3_MERGE_OUT_INTO = "Teotihuacan"

# -- Rule-3 drops: whole-site "what" ADDITIONS where the specific/iconic
# building is a SEPARATE, already-present pool item (own generous-alias
# judgment additions above cover Angkor Wat; these two duplicate-scope
# whole-site entries are simply redundant with what's already in the pool).
RULE3_DROP_ADD_NAMES = {
    "Archeological site of Olympia",  # "Statue of Zeus at Olympia" already
                                       # covers Olympia's other, distinct
                                       # famous image (the temple/statue,
                                       # vs. the stadium track) -- two rival
                                       # images, not one fused postcard.
    "Angkor",                          # owner's own text: "Angkor Wat temple
                                       # itself is already a specific
                                       # building, fine" -- Angkor Wat/
                                       # Bayon/Ta Prohm are three genuinely
                                       # distinct famous images, so the
                                       # broad park name doesn't get its own
                                       # slot on top of Angkor Wat.
}

# -- Rule-3 cut (an ADD candidate, no ancient-site exception applies):
# Mantua is a living modern Italian city (not ruins), so neither the "fused
# postcard" nor the "less-famous non-Western site" (Gedi) exception rescues
# it -- it is squarely "a whole town" with no widely-known single building
# to stand in for it. (It was proposed as an addition, never previously
# aired, so it's cut from `add`, not `keep`.)
RULE3_DROP_ADD_NAMES_EXTRA_MANTUA = {"Mantua"}

# -- Rule-1 cut: an umbrella institution (21 museums + a zoo), not a single
# specific structure. Its actual flagship building ("Smithsonian Institution
# Building", aka "The Castle") isn't separately scored in any local data
# file, so there's nothing safe to swap it for.
RULE1_CUT_ADD_NAMES = {"Smithsonian Institution"}

# -- Rule-2 cut: Statue of Unity (India) completed 2018 -- squarely "built
# in the last 10-20 years".
RULE2_CUT_ADD_NAMES = {"Statue of Unity"}

# -- flagged_confirm: kept despite genuine rule tension, surfaced for the
# owner rather than decided unilaterally (mirrors the Space Shuttle
# precedent the brief itself called out).
FLAGGED_CONFIRM = [
    {"name": "Space Shuttle", "wiki_title": "Space Shuttle", "game": "what",
     "reason": "Rule 1 tension: a vehicle family (multiple orbiters flew), not one named "
               "individual craft -- but the owner saw it ranked #10 in the add list and did "
               "not veto it, so kept rather than silently cut."},
    {"name": "Saturn V", "wiki_title": "Saturn V", "game": "what",
     "reason": "Same Rule 1 tension as Space Shuttle (a rocket family used across multiple "
               "Apollo missions, not one named individual vehicle); ranked #21 in the add "
               "list, visible but not vetoed."},
    {"name": "Easter Island Moai", "wiki_title": "Moai", "game": "what",
     "reason": "Rule 1 tension named explicitly in the brief: a type of statue, but each "
               "moai is extremely distinctive in silhouette from any angle -- tie-break test "
               "says in."},
    {"name": "Sydney Opera House", "wiki_title": "Sydney Opera House", "game": "what",
     "reason": "Rule 2 borderline: completed 1973, but iconic from every angle -- the brief's "
               "own worked example of a likely-IN 1970s building, kept rather than cut."},
    {"name": "Troy", "wiki_title": "Troy", "game": "what",
     "reason": "Rule 3 tension: a whole ancient city by kind, and one of the most famous place "
               "names in the Western canon, but the surviving ruins have no single fused "
               "'postcard' image and no independently famous specific building to swap in "
               "(unlike Pompeii/Villa of the Mysteries) -- kept, flagged rather than guessed."},
]

# -- rule_casualties: cut beyond the owner's explicit vetoes, by rule
# extrapolation. `game` is always "what" (Relic) -- the new rules are
# Relic-only.
RULE_CASUALTIES = [
    {"name": "Smithsonian Institution", "wiki_title": "Smithsonian Institution",
     "rule": "rule1-type-not-a-thing",
     "reason": "Umbrella institution (21 museums + a zoo), not a single specific structure; "
               "its actual landmark building ('The Castle') has no local fame/image data to "
               "swap in."},
    {"name": "Statue of Unity", "wiki_title": "Statue of Unity",
     "rule": "rule2-modern-building",
     "reason": "Completed 2018 -- squarely 'built in the last 10-20 years'."},
    {"name": "Archeological site of Olympia", "wiki_title": "Olympia, Greece",
     "rule": "rule3-whole-site-redundant",
     "reason": "Whole sanctuary generates two rival famous images (the stadium track vs. the "
               "Statue/Temple of Zeus); 'Statue of Zeus at Olympia' already covers the site "
               "in the pool."},
    {"name": "Angkor", "wiki_title": "Angkor",
     "rule": "rule3-whole-site-redundant",
     "reason": "Angkor Wat's towers, Bayon's faces and Ta Prohm's tree-roots are three "
               "genuinely distinct famous images; owner's own text says Angkor Wat (already "
               "kept) is 'already a specific building, fine' -- no separate whole-park slot "
               "needed."},
    {"name": "Mantua", "wiki_title": "Mantua",
     "rule": "rule3-whole-city",
     "reason": "A living modern Italian city, not ruins -- no ancient-site exception applies, "
               "and no single widely-known building stands in for it."},
    {"name": "Pyramid of the Sun", "wiki_title": "Pyramid of the Sun",
     "rule": "rule3-fusion-merge",
     "reason": "Same physical complex as the (retained, wholesale) Teotihuacan entry, which "
               "now carries 'pyramid of the sun' as an accepted alias -- keeping both risked "
               "two pool answers matching one photograph, so this standalone, lower-fame "
               "entry was folded out."},
]

# New Carcassonne item mandated by the [CONTESTED] RETIRE verdict itself
# ("but add the castle/fortified-city as its own item, answer must accept
# 'carcassonne'"). Real scored/tagged/image data already exists locally for
# this exact title (universe_objects.json + tags.json + image_availability.json
# + fame_scores.json all carry "Cité de Carcassonne" / "Historic Fortified
# City of Carcassonne" -- it was already hand-verified in propose_pools.py's
# own KEEP_TITLE_OVERRIDE table as the correct, more-specific title,
# distinct from the plain "Carcassonne" city article that's being retired).
CARCASSONNE_NEW_ITEM_WIKI_TITLE = "Cité de Carcassonne"
CARCASSONNE_NEW_ITEM_NAME = "Historic Fortified City of Carcassonne"


# ===========================================================================
# SECTION 3 -- helpers
# ===========================================================================

def find_by_name(items, name):
    for it in items:
        if it.get("name") == name:
            return it
    return None


def find_by_wiki_title(items, wiki_title):
    for it in items:
        if it.get("wiki_title") == wiki_title:
            return it
    return None


def remove_by_name(items, name):
    idx = next((i for i, it in enumerate(items) if it.get("name") == name), None)
    if idx is None:
        return None
    return items.pop(idx)


def remove_by_wiki_title(items, wiki_title):
    idx = next((i for i, it in enumerate(items) if it.get("wiki_title") == wiki_title), None)
    if idx is None:
        return None
    return items.pop(idx)


def with_provenance(item, provenance):
    out = dict(item)
    out["provenance"] = provenance
    return out


def sort_pool(items):
    items.sort(key=lambda r: (-(r.get("fame") or 0), r.get("wiki_title") or ""))
    return items


# ===========================================================================
# SECTION 4 -- who / map (queue verdicts only; no Relic-rule extrapolation
# applies to these two games)
# ===========================================================================

def finalize_who_or_map(game, proposal):
    keep = [dict(x) for x in proposal["per_game"][game]["keep"]]
    add = [dict(x) for x in proposal["per_game"][game]["add"]]
    retire = [dict(x) for x in proposal["per_game"][game]["retire"]]

    removed = []
    if game == "map":
        for wt in QUEUE_EXCLUDE_WIKI_TITLES:
            r = remove_by_wiki_title(keep, wt)
            if r:
                removed.append(r)
            r2 = remove_by_wiki_title(add, wt)
            if r2:
                removed.append(r2)

    def tag(items, default_provenance):
        out = []
        for it in items:
            wt = it.get("wiki_title")
            prov = "verdict-include" if (game, wt) in QUEUE_INCLUDE else default_provenance
            out.append(with_provenance(it, prov))
        return out

    keep_out = tag(keep, "keep")
    add_out = tag(add, "add")
    retire_out = [with_provenance(r, None) for r in retire]
    for r in removed:
        r2 = dict(r)
        r2["provenance"] = None
        r2["retire_reason"] = "owner-queue-exclude"
        retire_out.append(r2)

    sort_pool(keep_out)
    sort_pool(add_out)
    sort_pool(retire_out)
    return {"keep": keep_out, "add": add_out, "retire": retire_out}, removed


# ===========================================================================
# SECTION 5 -- what (Relic): queue verdicts + contested + vetoes + rule
# extrapolation + backfill
# ===========================================================================

MODEL_LINE_PATTERN = re.compile(
    r"\b(Boeing \d|Airbus [A-Z]?\d|Douglas DC-?\d|Ford Model|Volkswagen|"
    r"Chevrolet|Toyota|Mark\s+[IVXLCDM]+\b|Type\s+\d+\b|-class\b|"
    r"\bClass\b.*\bsubmarine|\bModel\s+[A-Z0-9]+\b)",
    re.IGNORECASE,
)


def finalize_what(proposal, fame_scores, tags, image_availability):
    keep = [dict(x) for x in proposal["per_game"]["what"]["keep"]]
    add = [dict(x) for x in proposal["per_game"]["what"]["add"]]
    retire = [dict(x) for x in proposal["per_game"]["what"]["retire"]]

    notes = {"guernica": GUERNICA_WAS}

    # --- 1. Queue excludes (Auschwitz, Rwandan genocide memorial sites) ---
    for wt in ("Auschwitz concentration camp", "Rwandan genocide"):
        r = remove_by_wiki_title(add, wt)
        if r:
            r2 = dict(r)
            r2["provenance"] = None
            r2["retire_reason"] = "owner-queue-exclude"
            retire.append(r2)

    # --- 2. Contested retirement: move the 6 KEEP-verdict items back from
    #        retire -> keep. The other 6 (confirmed-retire) simply stay put.
    for name in CONTESTED_KEEP_OVERRIDE:
        r = remove_by_name(retire, name)
        if r is None:
            print(f"WARNING: contested-keep item not found in retire list: {name}", file=sys.stderr)
            continue
        r2 = dict(r)
        r2.pop("_retire_reason", None)
        keep.append(r2)
    for name in CONTESTED_RETIRE_CONFIRMED:
        if not find_by_name(retire, name):
            print(f"WARNING: contested-retire item not found in retire list: {name}", file=sys.stderr)

    # --- 3. Veto adds: remove 26 named "what" additions outright ---
    for name in VETO_ADD_NAMES:
        r = remove_by_name(add, name)
        if r is None:
            print(f"WARNING: veto-add item not found in add list: {name}", file=sys.stderr)
            continue
        r2 = dict(r)
        r2["provenance"] = None
        r2["retire_reason"] = "owner-veto"
        retire.append(r2)
    for wt in VETO_ADD_WIKI_TITLES_EXTRA:
        r = remove_by_wiki_title(add, wt)
        if r is None:
            print(f"WARNING: veto-add (wiki_title) item not found in add list: {wt}", file=sys.stderr)
            continue
        r2 = dict(r)
        r2["provenance"] = None
        r2["retire_reason"] = "owner-veto"
        retire.append(r2)

    # --- 4. Rule-1/2/3 cuts (all from the `add` candidate list -- Mantua
    #        included, since it was a proposed addition, never previously
    #        aired) ---
    all_add_cuts = (RULE1_CUT_ADD_NAMES | RULE2_CUT_ADD_NAMES | RULE3_DROP_ADD_NAMES
                     | RULE3_DROP_ADD_NAMES_EXTRA_MANTUA)
    for name in all_add_cuts:
        r = remove_by_name(add, name)
        if r is None:
            print(f"WARNING: rule-cut add item not found: {name}", file=sys.stderr)
            continue
        r2 = dict(r)
        r2["provenance"] = None
        cas = next((c for c in RULE_CASUALTIES if c["name"] == name), None)
        r2["retire_reason"] = f"{cas['rule']}: {cas['reason']}" if cas else "rule-extrapolation"
        retire.append(r2)

    # --- 5. Rule-3 fusion merge: fold "Pyramid of the Sun" out of keep ---
    r = remove_by_wiki_title(keep, RULE3_MERGE_OUT_KEEP_WIKI_TITLE)
    if r is None:
        print(f"WARNING: merge-out keep item not found: {RULE3_MERGE_OUT_KEEP_WIKI_TITLE}", file=sys.stderr)
    else:
        r2 = dict(r)
        r2["provenance"] = None
        cas = next((c for c in RULE_CASUALTIES if c["name"] == "Pyramid of the Sun"), None)
        r2["retire_reason"] = f"{cas['rule']}: {cas['reason']}" if cas else "rule-extrapolation"
        retire.append(r2)

    # --- 6. Rule-3 swap: Pompeii (keep) -> Villa of the Mysteries (add) ---
    pompeii = remove_by_wiki_title(keep, RULE3_SWAP_KEEP_WIKI_TITLE)
    if pompeii is None:
        print("WARNING: Pompeii not found in keep list for rule-3 swap", file=sys.stderr)
    else:
        p2 = dict(pompeii)
        p2["provenance"] = None
        p2["retire_reason"] = ("rule3-swap-to-part: name denotes a sprawling area bigger than "
                                "any one picture (fails the postcard test) -> replaced by "
                                "'Villa of the Mysteries'")
        retire.append(p2)
        new_item = dict(RULE3_SWAP_REPLACEMENT)
        new_item["provenance"] = "rule-swap"
        add.append(new_item)

    # --- 7. Rule-3 alias additions (no item movement, just accepted answers) ---
    for wt, aliases in RULE3_ALIAS_ADDITIONS.items():
        it = find_by_wiki_title(keep, wt) or find_by_wiki_title(add, wt)
        if it is None:
            print(f"WARNING: alias target not found: {wt}", file=sys.stderr)
            continue
        existing = list(dict.fromkeys(it.get("answer_aliases", []) + aliases))
        it["answer_aliases"] = existing

    # --- 8. New Carcassonne fortified-city item (mandated by the contested
    #        retirement verdict itself) ---
    fame_by_title = {s["wiki_title"]: s for s in fame_scores["scores"]}
    carc_tag = tags["objects"].get(CARCASSONNE_NEW_ITEM_WIKI_TITLE, {})
    carc_img = pp.image_status(CARCASSONNE_NEW_ITEM_WIKI_TITLE, image_availability["items"])
    carc_fame = fame_by_title.get(CARCASSONNE_NEW_ITEM_WIKI_TITLE, {}).get("fame")
    add.append({
        "name": CARCASSONNE_NEW_ITEM_NAME,
        "wiki_title": CARCASSONNE_NEW_ITEM_WIKI_TITLE,
        "fame": carc_fame,
        "era": carc_tag.get("era"),
        "region": carc_tag.get("region"),
        "kind": carc_tag.get("kind"),
        "image": carc_img,
        "flags": [],
        "answer_aliases": ["carcassonne"],
        "provenance": "verdict-include",
    })

    # --- 9. Tag remaining items' default provenance + verdict-include ---
    def default_tag(items, default_provenance):
        for it in items:
            if "provenance" in it and it["provenance"]:
                continue
            wt = it.get("wiki_title")
            it["provenance"] = "verdict-include" if ("what", wt) in QUEUE_INCLUDE else default_provenance

    default_tag(keep, "keep")
    default_tag(add, "add")

    return keep, add, retire, notes


# fame_scores.json's `name` field is a raw harvested display label and is
# occasionally a generic/misleading fragment rather than the article's real
# common name (e.g. "Cathedral" for wiki_title "Seville Cathedral", "Fort"
# for "Lahore Fort", "HK$" for "Hong Kong dollar") -- discovered by running
# an early draft of this backfill and eyeballing the output. wiki_title is
# used as the display name instead for every automated backfill pick, to
# avoid resurfacing that data-quality quirk in the finalized pool.

# Specific candidates hand-excluded after inspecting an early backfill run,
# for reasons the automated filters below don't (and structurally can't)
# catch:
BACKFILL_EXCLUDE_WIKI_TITLES = {
    "Hong Kong dollar",   # a currency/monetary system, not a specific artefact
                          # (mistagged as artwork/painting upstream)
    "Assisi",             # a whole living Italian town (mistagged "building"
                          # in tags.json) -- same rule-3 issue as Mantua
    "Stone Mountain",     # carved Confederate memorial (Lee/Jackson/Davis) --
                          # genuinely sensitive in a way the nazi/religious/
                          # dark keyword patterns don't catch; needs the
                          # owner's own review, not silent auto-inclusion
    "Louvre Pyramid",     # 1989 -- exactly the brief's own "flag if torn"
                          # calibration example; excluded from automated
                          # backfill rather than silently added
    "AEC Routemaster",    # a bus MODEL (thousands built) -- rule 1
    "Macintosh 128K",     # a computer MODEL -- rule 1
    "Space Needle",       # 1962 observation tower -- same silhouette-tower
                          # profile as the vetoed CN Tower (1976); Tokyo
                          # Tower (1958) survived un-vetoed, so this is a
                          # genuine judgment call and excluded from
                          # unreviewed automated backfill out of caution
}


def build_backfill(current_titles, needed_count, fame_scores, tags, image_availability):
    """Pull next-best playable candidates from the scored object universe to
    fill Relic back toward ~350. Conservative w.r.t. the three rules:
    contemporary era excluded (rule 2), obvious vehicle/model-line name
    patterns excluded (rule 1), and kind=="site" excluded altogether (rule 3
    -- avoids re-introducing whole-settlement judgment calls in an
    unreviewed, automated pass). No candidate carrying ANY sensitivity flag
    is added, per instruction -- those need the owner's own review first.
    """
    playability_check = pp.make_playability_checker()
    new_object_fame, survivor_flags = pp.repercentile_objects(fame_scores, playability_check)
    object_tags = tags["objects"]
    img_items = image_availability["items"]

    candidates = []
    for s in fame_scores["scores"]:
        if s["class"] not in pp.OBJECT_CLASSES:
            continue
        wt = s["wiki_title"]
        if wt in current_titles or wt in BACKFILL_EXCLUDE_WIKI_TITLES:
            continue
        passes, _flag = survivor_flags.get(wt, (False, "p31_unknown"))
        if not passes:
            continue
        flags = pp.sensitivity_flags(wt)
        if flags:
            continue  # no new sensitive-flag items without owner review
        img_stat = pp.image_status(wt, img_items)
        if img_stat == "none":
            continue
        t = object_tags.get(wt, {})
        era = t.get("era")
        if era == "contemporary":
            continue  # rule 2
        kind = t.get("kind") or s["sources"].get("object_kind")
        if kind == "site":
            continue  # rule 3 -- conservative: no unreviewed whole-place backfill
        if MODEL_LINE_PATTERN.search(s["name"]) or MODEL_LINE_PATTERN.search(wt):
            continue  # rule 1
        fame = new_object_fame.get(wt, s["fame"])
        candidates.append({
            "name": wt, "wiki_title": wt, "fame": fame,
            "era": era, "region": t.get("region"), "kind": kind,
            "image": img_stat, "flags": [], "provenance": "backfill",
        })

    candidates.sort(key=lambda c: (-c["fame"], c["wiki_title"]))
    seen = set(current_titles)
    picked = []
    for c in candidates:
        if len(picked) >= needed_count:
            break
        if c["wiki_title"] in seen:
            continue
        seen.add(c["wiki_title"])
        picked.append(c)
    return picked


# ===========================================================================
# SECTION 6 -- main
# ===========================================================================

def main():
    proposal = load("pool_proposal.json")
    fame_scores = load("fame_scores.json")
    tags = load("tags.json")
    image_availability = load("image_availability.json")

    who_result, who_removed = finalize_who_or_map("who", proposal)
    map_result, map_removed = finalize_who_or_map("map", proposal)
    what_keep, what_add, what_retire, what_notes = finalize_what(
        proposal, fame_scores, tags, image_availability)

    # Exclude anything already keep/add (avoid duplicates) AND anything just
    # retired (veto'd / rule-cut / contested-retire-confirmed) -- a vetoed
    # item must never quietly re-enter through the automated backfill pass.
    excluded_titles = {
        it["wiki_title"] for it in what_keep + what_add + what_retire if it.get("wiki_title")
    }
    current_total = len(what_keep) + len(what_add)
    needed = max(0, TARGETS["what"] - current_total)
    backfill = build_backfill(excluded_titles, needed, fame_scores, tags, image_availability)
    what_add.extend(backfill)

    sort_pool(what_keep)
    sort_pool(what_add)
    sort_pool(what_retire)

    per_game = {
        "who": who_result,
        "map": map_result,
        "what": {"keep": what_keep, "add": what_add, "retire": what_retire},
    }

    stats = {}
    for game in ("who", "map", "what"):
        k = len(per_game[game]["keep"])
        a = len(per_game[game]["add"])
        r = len(per_game[game]["retire"])
        stats[game] = {
            "keep": k, "add": a, "retire": r,
            "resulting_pool_size": k + a,
            "target": TARGETS[game],
        }
    stats["what"]["backfill_added"] = len(backfill)

    output = {
        "generatedOn": GENERATED_ON,
        "sourceProposal": {"file": "pool_proposal.json", "generatedOn": proposal.get("generatedOn")},
        "verdictsFile": "verdicts-pool-2026-07-24.txt",
        "targets": TARGETS,
        "per_game": per_game,
        "flagged_confirm": FLAGGED_CONFIRM,
        "rule_casualties": RULE_CASUALTIES,
        "notes": what_notes,
        "stats": stats,
    }

    out_path = dump(output, "final_pools.json")
    print(f"Wrote {out_path}", file=sys.stderr)
    print(json.dumps(stats, indent=2), file=sys.stderr)
    print("backfill picked:", [c["name"] for c in backfill], file=sys.stderr)
    print("who removed (queue exclude):", [r["name"] for r in who_removed], file=sys.stderr)
    print("map removed (queue exclude):", [r["name"] for r in map_removed], file=sys.stderr)


if __name__ == "__main__":
    main()
