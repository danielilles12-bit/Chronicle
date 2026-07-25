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


def check_figures():
    figs = json.loads((ROOT / "data/figures.json").read_text())
    for dup, n in Counter(f.get("id") for f in figs).items():
        if n > 1:
            err(f"figures: duplicate id {dup}")
    for dup, n in Counter(f.get("name", "").lower() for f in figs).items():
        if n > 1:
            err(f"figures: duplicate name {dup!r}")
    variant_owner = {}
    for f in figs:
        fid = f.get("id", "?")
        if f.get("difficulty") not in DIFFICULTIES:
            err(f"figures {fid}: bad difficulty")
        if not str(f.get("occupation") or "").strip():
            err(f"figures {fid}: missing occupation")
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


def main():
    nwho = check_reveal("data/reveal-who.json")
    nwhat = check_reveal("data/reveal-what.json")
    nfig = check_figures()
    for w in warns:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"reveal-who {nwho}, reveal-what {nwhat}, figures {nfig} — "
          f"{len(errors)} errors, {len(warns)} warnings")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
