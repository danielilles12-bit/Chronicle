#!/usr/bin/env python3
"""Validator for reveal-who.json, reveal-what.json and figures.json.

Run from repo root: python3 tools/validate_reveal.py
Exits non-zero on any ERROR.
"""
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trust_schema import validate_trust_fields  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DIFFICULTIES = {"easy", "medium", "hard"}

errors, warns = [], []
err = errors.append
warn = warns.append

# ---------- doubled punctuation (blurbs / figures.fact) ----------
# Any run of 2+ terminal-punctuation characters is suspicious EXCEPT a
# genuine 3-dot ellipsis ("...") — so "..", "!.", "?.", ",," and runs of 4+
# dots all flag, but a legitimate "..." does not.
PUNCT_RUN_RE = re.compile(r"[.!?,]{2,}")


def bad_punct_runs(text):
    return [m.group(0) for m in PUNCT_RUN_RE.finditer(text or "") if m.group(0) != "..."]


# ---------- terminal punctuation layer (js/revealgame.js) ----------
# The renderer (withTerminalPunct) appends "." to a blurb ONLY when it doesn't
# already end in its own terminal mark — so the data must never carry a bare
# "." (that would just be redundant next to the appended one), but "!"/"?"
# endings are fine: the renderer leaves those alone and shows them as-is.
def ends_bare_period(text):
    t = (text or "").rstrip()
    return t.endswith(".") and not t.endswith("...")


# ---------- `years` field sanity (js/revealgame.js clueYears/extractEra) ----------
# Loose lifespan/era shape: digits, ordinal suffixes, "century"/"centuries",
# an en dash or hyphen, "c.", BC/BCE/AD/CE, and the odd trailing "onwards" seen
# in real curated entries (e.g. "12th century onwards"). Anything left over
# after stripping those tokens is a WARN, not an ERROR — this is a loose sanity
# check, not a strict grammar.
YEARS_TOKEN_RE = re.compile(
    r"\d+|century|centuries|onwards|BCE|BC|AD|CE|c\.|st|nd|rd|th|[\s,.\-–]",
    re.IGNORECASE,
)


def odd_years(value):
    if not isinstance(value, str):
        return f"not a string ({value!r})"
    s = value.strip()
    if not s:
        return "empty"
    if not re.search(r"\d", s):
        return "no digit"
    leftover = YEARS_TOKEN_RE.sub("", s).strip()
    if leftover:
        return f"unexpected characters {leftover!r}"
    return None


# ---------- clueYears() parity (js/revealgame.js) ----------
# Mirrors clueYears() exactly: an explicit `years` field wins, else the first
# parenthetical in the blurb that holds a digit.
def clue_years(item):
    years = item.get("years")
    if years:
        return str(years).strip()
    m = re.search(r"\(([^)]*\d[^)]*)\)", item.get("blurb") or "")
    return m.group(1).strip() if m else None


# A "Lived" clue must be a lifespan, never an office/tenure date. "r." (regnal
# "reigned") is checked with a word boundary so it can't false-positive inside
# an unrelated abbreviation like "Mr.".
ROLE_WORD_RE = re.compile(
    r"\b(?:president|reign|in office|pope|elected|crowned|tenure)\b|\br\.",
    re.IGNORECASE,
)

# ---------- normalize() parity (js/match.js) ----------
# A lighter-weight port: lowercase, strip accents/punctuation, drop a
# trailing "by <artist>" clause, drop articles, fold written ordinals to
# roman numerals — enough to catch a reject entry that (after the same
# normalization the matcher applies) is really just the item's own name or
# an accepted variant in disguise.
ARTICLES = {"the", "a", "an"}
NUMWORDS = {
    "first": "i", "second": "ii", "third": "iii", "fourth": "iv", "fifth": "v",
    "sixth": "vi", "seventh": "vii", "eighth": "viii", "ninth": "ix", "tenth": "x",
    "eleventh": "xi", "twelfth": "xii", "thirteenth": "xiii", "fourteenth": "xiv",
    "fifteenth": "xv", "sixteenth": "xvi",
}
ROMAN_BY_NUM = ["", "i", "ii", "iii", "iv", "v", "vi", "vii", "viii",
                "ix", "x", "xi", "xii", "xiii", "xiv", "xv", "xvi"]


def _num_to_roman(tok):
    if tok in NUMWORDS:
        return NUMWORDS[tok]
    m = re.match(r"^(\d{1,2})(?:st|nd|rd|th)?$", tok)
    if m and 1 <= int(m.group(1)) <= 16:
        return ROMAN_BY_NUM[int(m.group(1))]
    return tok


def match_normalize(s):
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("&", "")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return ""
    out = []
    for tok in s.split(" "):
        if tok == "by":
            break
        if tok in ARTICLES:
            continue
        out.append(_num_to_roman(tok))
    return " ".join(out)


# ---------- clueOccupation() parity (js/revealgame.js) ----------
# Mirrors clueOccupation() exactly: WHO blurbs are "Occupation (years) ·
# credit" — the occupation/"Claim to fame" clue is everything before the
# first "(", then (belt and suspenders) before any bare "·" too, with
# trailing middots/commas/whitespace stripped. Face Value only — Relic
# (reveal-what) items use a different pair of clues (initials + era, see
# js/revealgame.js clueDefs()) and never call this function; Lifeline
# (figures.json) has no derivation at all — its "Claim to fame" clue is
# the raw `occupation` field, shown verbatim.
def clue_occupation(item):
    occ = (item.get("blurb") or "").split("(")[0]
    occ = occ.split("·")[0]  # '·' MIDDLE DOT
    occ = occ.strip()
    occ = re.sub(r"[·,\s]+$", "", occ)
    return occ.strip()


# ---------- containsPhrase() guard-rail parity (js/match.js) ----------
# js/match.js was hardened 25 Jul 2026 so a variant composed ENTIRELY of
# structural stopwords and/or bare royal/honorific titles (CORE_STOPWORDS /
# TITLES below, containsPhrase()'s `variantToks.every(...)` guard, js/
# match.js:296-298) can never carry a match on its own: Elizabeth II's "the
# queen" variant must still match "the queen" exactly, but the bare word
# "queen" must never drag "Queen Victoria" or "queen of England" into a
# false match. A player typing just "queen" therefore cannot win the round
# — so a clue containing that word alone leaks nothing. Ported here (not
# duplicated as a hand-written word list) so the leak check can never drift
# from the production matcher; if js/match.js's CORE_STOPWORDS/TITLES ever
# change, update these two sets to match.
CORE_STOPWORDS = {
    "the", "of", "a", "an", "and", "in", "la", "le", "el", "de", "di",
    "von", "van", "der", "den", "da", "du", "al", "ii", "iii",
    "with", "off", "on", "at", "for", "to", "from", "as",
    "girl", "boy", "man", "woman",
}
TITLES = {
    "queen", "king", "emperor", "empress", "tsar", "tsarina", "kaiser",
    "sultan", "pharaoh", "pope", "saint", "st", "sir", "lord", "lady",
    "president", "general", "chancellor",
}


def _matcher_would_refuse(normalized):
    """True when `normalized` is a string containsPhrase() would refuse to
    match on by itself — every one of its tokens is a stopword or a bare
    title. A clue containing such a string leaks nothing a real guess could
    win on."""
    toks = normalized.split(" ")
    return bool(toks) and all(t in CORE_STOPWORDS or t in TITLES for t in toks)


# ---------- paid clue must not leak the answer ----------
# 22 Jul 2026 paid-clue sweep: 33 "Claim to fame" clues literally contained
# (or were exactly) a string the matcher accepts for that same item —
# van-gogh-self's clue was "Vincent van Gogh"; ella-fitzgerald's named "the
# First Lady of Song" (an accepted variant); samuel-morse's contained
# "Morse"; george-eliot's named "Mary Ann Evans". A player could paste the
# clue they just paid for straight into the answer box. Guard against a
# recurrence: ERROR if the normalized clue contains, as a whole-word
# (space-bounded) substring, the item's own name or any variant — but only
# a variant the production matcher would actually accept as a standalone
# guess (see _matcher_would_refuse above); matches under MIN_LEAK_LEN chars
# are also skipped (too short/generic to be a meaningful leak on their own).
MIN_LEAK_LEN = 4


def _contains_whole(haystack, needle):
    if not needle:
        return False
    return f" {needle} " in f" {haystack} "


def check_clue_leak(item, iid, label, clue_text, err):
    """error if `clue_text` (already the derived clue, not the raw blurb)
    contains the item's own name/variants as a whole-word substring."""
    nclue = match_normalize(clue_text)
    if not nclue:
        return
    candidates = [item.get("name", "")]
    candidates.extend(item.get("variants") or [])
    seen = set()
    for c in candidates:
        nc = match_normalize(c)
        if not nc or nc in seen:
            continue
        seen.add(nc)
        if len(nc) < MIN_LEAK_LEN or _matcher_would_refuse(nc):
            continue
        if _contains_whole(nclue, nc):
            err(f"{label} {iid}: clue {clue_text!r} leaks the answer — "
                f"contains {c!r} (normalized {nc!r})")


def check_reject_hygiene(item, iid, label, err):
    """error if a reject entry normalizes to the item's own name/variant."""
    rejects = item.get("reject") or []
    if not rejects:
        return
    accepted = {match_normalize(item.get("name", ""))}
    accepted.update(match_normalize(v) for v in (item.get("variants") or []))
    accepted.discard("")
    for r in rejects:
        nr = match_normalize(r)
        if nr and nr in accepted:
            err(f"{label} {iid}: reject entry {r!r} normalizes to its own "
                f"name/variant ({nr!r}) — self-contradicting")


def check_reveal(path):
    items = json.loads((ROOT / path).read_text())
    is_who = path.endswith("reveal-who.json")
    for dup, n in Counter(x.get("id") for x in items).items():
        if n > 1:
            err(f"{path}: duplicate id {dup}")
    variant_owner = {}
    for it in items:
        iid = it.get("id", "?")
        for field in ("name", "kind", "img", "blurb", "license", "source"):
            if not str(it.get(field) or "").strip():
                err(f"{path} {iid}: missing {field}")
        # 31 Jul 2026 rights audit: a CC BY/BY-SA record without
        # image_license_url renders WITHOUT the photographer's name in the
        # in-app credit panel (creditHTML wants author + licence URL) — an
        # attribution breach that shipped 16 times because Commons'
        # extmetadata collapses dual-licensed files to "Public domain".
        # See tools/out/rights-check-2026-07-31/REPORT.md.
        lic = str(it.get("image_license") or it.get("license") or "").strip()
        if lic.upper().startswith("CC BY"):
            if not str(it.get("image_license_url") or "").strip():
                err(f"{path} {iid}: {lic} needs image_license_url — the in-app "
                    f"credit drops the photographer's name without it")
            if not str(it.get("image_author") or it.get("attribution") or "").strip():
                err(f"{path} {iid}: {lic} needs image_author/attribution — the "
                    f"licence requires naming the photographer")
        for run in bad_punct_runs(it.get("blurb")):
            err(f"{path} {iid}: doubled punctuation {run!r} in blurb")
        if ends_bare_period(it.get("blurb")):
            err(f"{path} {iid}: blurb ends in a bare '.' — the renderer appends "
                f"this itself (js/revealgame.js withTerminalPunct); strip it from the data")
        if "years" in it and it.get("years") is not None:
            reason = odd_years(it.get("years"))
            if reason:
                warn(f"{path} {iid}: years {it.get('years')!r} looks odd ({reason})")
        if is_who:
            val = clue_years(it)
            if not val:
                if it.get("kind") == "portrait":
                    warn(f"{path} {iid}: Lived clue (clueYears) yields no value — clue B would be blank")
            elif ROLE_WORD_RE.search(val):
                err(f"{path} {iid}: Lived clue {val!r} reads like an office/role date, not a lifespan")
            occ = clue_occupation(it)
            if occ:
                check_clue_leak(it, iid, path, occ, err)
        check_reject_hygiene(it, iid, path, err)
        if it.get("difficulty") not in DIFFICULTIES:
            err(f"{path} {iid}: bad difficulty {it.get('difficulty')!r}")
        img = ROOT / it.get("img", "")
        if not img.is_file():
            err(f"{path} {iid}: image file missing: {it.get('img')}")
        elif img.stat().st_size < 20_000:
            warn(f"{path} {iid}: image suspiciously small ({img.stat().st_size} bytes)")
        for coord in ("fx", "fy"):
            v = it.get(coord)
            if not isinstance(v, (int, float)) or not (0.0 <= v <= 1.0):
                err(f"{path} {iid}: {coord} out of range: {v!r}")
        fr = it.get("frac")
        if not isinstance(fr, (int, float)) or not (0.05 <= fr <= 1.0):
            err(f"{path} {iid}: frac out of range: {fr!r}")
        vs = it.get("variants") or []
        if not vs:
            err(f"{path} {iid}: no variants")
        for v in vs:
            if v != v.lower().strip():
                err(f"{path} {iid}: variant not normalized: {v!r}")
            if v in variant_owner and variant_owner[v] != iid:
                warn(f"{path}: variant {v!r} shared by {variant_owner[v]} and {iid} "
                     f"(allowed — matcher is per-item — but check it's intentional)")
            variant_owner[v] = iid
        validate_trust_fields(it, f"{path} {iid}", err, warn, has_images=True)
    return len(items)


# A birth/death city segment named by more figures' occupations than this
# (Rome, London, Paris, Vienna, Florence, Athens ... — imperial/dynastic
# capitals a big chunk of the pool is tied to) is common enough that naming
# it doesn't meaningfully narrow down which dot on the map is being
# described, so it's downgraded to WARN alongside the country-level case
# rather than blocking the build. Empirically (figures.json, 24 Jul 2026):
# of 727 distinct birth/death city segments, 697 (96%) are used by <=3
# figures — those are the real, specific pinpoints this check exists to
# catch (Shackleton/"South Georgia", Pizarro/"Lima", Richard II/
# "Pontefract" ...); the handful above the threshold are shared capitals.
COMMON_PLACE_THRESHOLD = 3


def build_place_frequency(figs):
    """normalized birth/death place FIRST segment (the city) -> how many
    figures in the pool use it, for check_map_place_leak's common-place
    downgrade."""
    freq = Counter()
    for f in figs:
        for end in ("birth", "death"):
            place = (f.get(end) or {}).get("place") or ""
            parts = [p.strip() for p in place.split(",") if p.strip()]
            if parts:
                freq[match_normalize(parts[0])] += 1
    return freq


def check_map_place_leak(fig, fid, err, warn, place_freq):
    """Lifeline's puzzle is inferring the figure from birth/death geography
    shown only as map coordinates during the round (js/mapgame.js) — an
    `occupation` clue that names the birth/death place in text hands part
    of that over for free. ERROR when a specific, rare city/region segment
    leaks (a real giveaway); WARN when only the LAST comma-separated
    segment of `place` (the country) matches, or when the matched segment
    is a common shared capital (see COMMON_PLACE_THRESHOLD) — both are
    real but much weaker giveaways than a named, rare city, so they're
    downgraded rather than blocking the build. A single-segment place (no
    comma at all) can't be told apart from a bare country by the
    country-check, so it falls through to the frequency check instead."""
    occ = match_normalize(fig.get("occupation") or "")
    if not occ:
        return
    for end in ("birth", "death"):
        place = (fig.get(end) or {}).get("place") or ""
        parts = [p.strip() for p in place.split(",") if p.strip()]
        for i, part in enumerate(parts):
            npart = match_normalize(part)
            if len(npart) < MIN_LEAK_LEN or all(t in CORE_STOPWORDS for t in npart.split(" ")):
                continue
            if not _contains_whole(occ, npart):
                continue
            msg = (f"figures {fid}: occupation {fig.get('occupation')!r} leaks the "
                   f"{end} place — contains {part!r} (normalized {npart!r})")
            if len(parts) > 1 and i == len(parts) - 1:
                warn(msg + " [country-level only]")
            elif place_freq.get(npart, 0) > COMMON_PLACE_THRESHOLD:
                warn(msg + f" [shared by {place_freq[npart]} figures' birth/death place — weak signal]")
            else:
                err(msg)


def check_figures():
    figs = json.loads((ROOT / "data/figures.json").read_text())
    for dup, n in Counter(f.get("id") for f in figs).items():
        if n > 1:
            err(f"figures: duplicate id {dup}")
    for dup, n in Counter(f.get("name", "").lower() for f in figs).items():
        if n > 1:
            err(f"figures: duplicate name {dup!r}")
    place_freq = build_place_frequency(figs)
    variant_owner = {}
    for f in figs:
        fid = f.get("id", "?")
        if f.get("difficulty") not in DIFFICULTIES:
            err(f"figures {fid}: bad difficulty")
        if not str(f.get("occupation") or "").strip():
            err(f"figures {fid}: missing occupation")
        else:
            check_clue_leak(f, fid, "figures", f.get("occupation"), err)
            check_map_place_leak(f, fid, err, warn, place_freq)
        for run in bad_punct_runs(f.get("fact")):
            err(f"figures {fid}: doubled punctuation {run!r} in fact")
        check_reject_hygiene(f, fid, "figures", err)
        for v in f.get("variants") or []:
            if v != v.lower().strip():
                err(f"figures {fid}: variant not normalized: {v!r}")
            if v in variant_owner and variant_owner[v] != fid:
                warn(f"figures: variant {v!r} shared by {variant_owner[v]} and {fid} "
                     f"(allowed — matcher is per-item — but check it's intentional)")
            variant_owner[v] = fid
        for end in ("birth", "death"):
            e = f.get(end) or {}
            y = e.get("year")
            if not isinstance(y, int) or not (-4000 <= y <= 2026):
                err(f"figures {fid}: bad {end} year {y!r}")
            if not str(e.get("place") or "").strip():
                err(f"figures {fid}: missing {end} place")
            lat, lon = e.get("lat"), e.get("lon")
            if not isinstance(lat, (int, float)) or not (-90 <= lat <= 90):
                err(f"figures {fid}: bad {end} lat {lat!r}")
            if not isinstance(lon, (int, float)) or not (-180 <= lon <= 180):
                err(f"figures {fid}: bad {end} lon {lon!r}")
        by = (f.get("birth") or {}).get("year")
        dy = (f.get("death") or {}).get("year")
        if isinstance(by, int) and isinstance(dy, int) and by >= dy:
            err(f"figures {fid}: birth {by} not before death {dy}")
        validate_trust_fields(f, f"figures {fid}", err, warn, has_images=False)
    return len(figs)


# ---------- Wikipedia title health (tools/fame/title_health.json) ----------
# Pool records carry no wiki_title, so every fame/salience tool resolves an
# item from its display name. A bare ambiguous name ("Seneca", "Charles V",
# "Vasa") lands on a DISAMBIGUATION page — a few hundred bytes of links with
# no pageviews, no inbound links and no WikiProject assessments — and the
# item then scores near zero on every metric derived from it. That is what
# put Mihrimah Sultan at the "13.9th fame percentile" in the launch review:
# her item resolved to a 531-byte disambiguation stub, not her biography.
#
# The online check lives in tools/fame/build_salience.py, which writes
# title_health.json; this is the offline assertion over its output. The file
# being absent disables the check rather than failing the suite, matching how
# the other fame-signal consumers degrade (see compile_editions.load_signal_indices).
TITLE_HEALTH_PATH = ROOT / "tools/fame/title_health.json"
TITLE_STATUS_BLURB = {
    "disambiguation": "resolves to a Wikipedia DISAMBIGUATION page",
    "missing": "resolves to a Wikipedia article that does not exist",
    "too_short": "resolves to an implausibly short Wikipedia article",
    "unresolved": "could not be resolved to any Wikipedia article",
}

# ---------- Wikipedia SUBJECT health (the same file) ----------
# The check above proves the article exists, isn't a disambiguation page and
# is long enough. It cannot prove the article is about the right THING, and
# the 25 Jul 2026 re-tier audit found eight pool items where it wasn't —
# every one of them reporting status "ok". `sunflowers` resolved to
# Helianthus, the sunflower plant *genus*, and inherited the flower's fame of
# 93.1, which nearly promoted a van Gogh canvas to easy; `olympia-stadium`
# resolved to Detroit Olympia, an American ice-hockey arena.
#
# tools/fame/build_salience.py's check_subjects() is the online half (a
# Wikidata instance-of type check plus a name↔title token check that the
# item's own `variants` can satisfy); this is the offline assertion over its
# output, and it degrades exactly like the status check above — an older
# title_health.json without the field reports "unknown" and is treated as
# not-yet-checked rather than as a failure.
SUBJECT_STATUS_BLURB = {
    "type_mismatch": "resolves to a Wikipedia article about the WRONG KIND "
                     "of subject",
    "name_mismatch": "resolves to a Wikipedia article whose title names "
                     "something else",
}


def check_title_health():
    if not TITLE_HEALTH_PATH.exists():
        warn("title health: tools/fame/title_health.json missing — Wikipedia "
             "title check skipped (regenerate with tools/fame/build_salience.py)")
        return 0
    try:
        data = json.loads(TITLE_HEALTH_PATH.read_text())
    except (OSError, ValueError) as e:
        warn(f"title health: could not read title_health.json ({e}) — check skipped")
        return 0

    rows = data.get("items") or []
    covered = {(r.get("game"), r.get("id")) for r in rows}
    n_unchecked = 0
    for r in rows:
        status = r.get("status")
        if status != "ok":
            blurb = TITLE_STATUS_BLURB.get(status, f"has title status {status!r}")
            err(f"{r.get('game')} {r.get('id')}: {blurb} "
                f"({r.get('wiki_title')!r}) — add a verified title to "
                f"TITLE_OVERRIDES in tools/fame/build_salience.py")
            continue
        subject = r.get("subject_status")
        if subject is None or subject == "unknown":
            # No Wikidata item behind the article (or a title_health.json
            # generated before the subject check existed): not evidence of a
            # problem, just an absence of evidence.
            n_unchecked += 1
            continue
        if subject == "ok":
            continue
        blurb = SUBJECT_STATUS_BLURB.get(
            subject, f"has subject status {subject!r}")
        detail = r.get("subject_detail")
        err(f"{r.get('game')} {r.get('id')}: {blurb} "
            f"({r.get('wiki_title')!r}"
            + (f" — {detail}" if detail else "") + ") — pin the right "
            f"article in TITLE_OVERRIDES in tools/fame/build_salience.py")
    if n_unchecked:
        warn(f"title health: {n_unchecked} item(s) have no Wikidata subject "
             f"check (regenerate with tools/fame/build_salience.py)")

    # New pool items that predate the last health run have never been
    # checked. That is a warning, not an error: it must not block a content
    # session, but it should be visible so the manifest gets regenerated.
    for game, rel in (("who", "data/reveal-who.json"),
                      ("map", "data/figures.json"),
                      ("what", "data/reveal-what.json")):
        for e in json.loads((ROOT / rel).read_text()):
            if (game, e.get("id")) not in covered:
                warn(f"{game} {e.get('id')}: not in title_health.json — "
                     f"Wikipedia title never verified (regenerate with "
                     f"tools/fame/build_salience.py)")
    return len(rows)


def main():
    nwho = check_reveal("data/reveal-who.json")
    nwhat = check_reveal("data/reveal-what.json")
    nfig = check_figures()
    ntitles = check_title_health()
    for w in warns:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"reveal-who {nwho}, reveal-what {nwhat}, figures {nfig}, "
          f"titles checked {ntitles} — "
          f"{len(errors)} errors, {len(warns)} warnings")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
