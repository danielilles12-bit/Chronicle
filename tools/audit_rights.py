#!/usr/bin/env python3
"""Licence audit for data/reveal-who.json and data/reveal-what.json.

For every image record, checks the stored `license` field against:
  1. Hints in the `source` filename (always available, offline)
  2. (--online) the real Wikimedia Commons licence for that exact file,
     via action=query&prop=imageinfo&iiprop=extmetadata

Writes tools/out/rights_report.csv and prints a summary with every
MISMATCH called out.

Usage:
  python3 tools/audit_rights.py            # filename-hint check only
  python3 tools/audit_rights.py --online   # also query the Commons API
"""
import csv
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "ChronicleContentBot/1.0 (daniel.illes12@gmail.com)"}

DATA_FILES = ["data/reveal-who.json", "data/reveal-what.json"]
OUT_CSV = ROOT / "tools/out/rights_report.csv"
SOURCE_PREFIX = "Wikimedia Commons: "
BATCH_SIZE = 50


def api(params):
    params = dict(params, format="json")
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


# ---------------------------------------------------------------------------
# Licence-family normalisation
# ---------------------------------------------------------------------------

def family_of(lic):
    """Normalise a licence string (stored, or Commons LicenseShortName) into
    a family: PD, CC0, CC BY-SA, CC BY, other. Returns None for empty input."""
    if not lic:
        return None
    low = lic.lower().strip()
    if "public domain" in low or low.startswith("pd") or "pd-" in low:
        return "PD"
    if "cc0" in low:
        return "CC0"
    if "by-sa" in low:
        return "CC BY-SA"
    if "by" in low:
        return "CC BY"
    return "other"


def commons_filename(source):
    """Extract the bare Commons filename from a 'Wikimedia Commons: X' source
    string. Returns None for any other source format (treated as unverified)."""
    if not source or not source.startswith(SOURCE_PREFIX):
        return None
    fn = source[len(SOURCE_PREFIX):].strip()
    return fn or None


def hint_family(source):
    """Detect a licence family from hints in the source filename itself
    (case-insensitive). Returns None when no hint is present."""
    fn = commons_filename(source)
    text = fn if fn is not None else (source or "")
    low = text.lower()
    if "by-sa" in low or "cc-by-sa" in low:
        return "CC BY-SA"
    if "cc-by" in low or "(by)" in low:
        return "CC BY"
    if "cc0" in low:
        return "CC0"
    if re.search(r"\bpd\b", low) or "public domain" in low:
        return "PD"
    return None


# ---------------------------------------------------------------------------
# Commons API batch lookup
# ---------------------------------------------------------------------------

def query_batch(titles):
    """titles: list of 'File:...' strings (<=50). Returns dict of
    requested-title -> {'license': str|None, 'artist': str|None,
    'credit': str|None, 'license_url': str|None} or None (file missing /
    no imageinfo). Some Commons files leave Artist empty and record the
    photographer only in Credit (e.g. "Marie-Lan Nguyen (2007)") — callers
    that want a display name should fall back to credit when artist is
    empty or generic ("Unknown author")."""
    try:
        d = api({
            "action": "query",
            "titles": "|".join(titles),
            "prop": "imageinfo",
            "iiprop": "extmetadata",
        })
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        print(f"  ! Commons API error for batch of {len(titles)}: {e}", file=sys.stderr)
        return {t: None for t in titles}

    q = d.get("query", {})
    orig_of = {t: t for t in titles}
    for n in q.get("normalized", []):
        orig_of[n["to"]] = n["from"]
    for n in q.get("converted", []):
        orig_of[n["to"]] = orig_of.get(n["from"], n["from"])

    result = {t: None for t in titles}
    for page in q.get("pages", {}).values():
        final_title = page.get("title", "")
        orig_title = orig_of.get(final_title, final_title)
        if orig_title not in result:
            continue
        if "missing" in page or "imageinfo" not in page:
            result[orig_title] = None
            continue
        ii = page["imageinfo"][0]
        meta = ii.get("extmetadata", {})

        def get(key):
            return strip_tags(meta.get(key, {}).get("value", ""))

        lic = get("LicenseShortName") or get("License") or get("UsageTerms")
        artist = get("Artist")
        credit = get("Credit")
        license_url = get("LicenseUrl")
        result[orig_title] = {
            "license": lic or None, "artist": artist or None,
            "credit": credit or None, "license_url": license_url or None,
        }
    return result


def fetch_commons_data(filenames):
    """filenames: iterable of bare Commons filenames (no 'File:' prefix).
    Returns dict filename -> {'license': str|None, 'artist': str|None} or None."""
    uniq = sorted(set(filenames))
    titles = [f"File:{fn}" for fn in uniq]
    title_to_fn = {f"File:{fn}": fn for fn in uniq}

    out = {}
    for i in range(0, len(titles), BATCH_SIZE):
        batch = titles[i:i + BATCH_SIZE]
        print(f"  querying Commons for {len(batch)} files "
              f"({i + len(batch)}/{len(titles)})...")
        res = query_batch(batch)
        for title, val in res.items():
            out[title_to_fn[title]] = val
        if i + BATCH_SIZE < len(titles):
            time.sleep(1)
    return out


# ---------------------------------------------------------------------------
# Main audit
# ---------------------------------------------------------------------------

def load_records(rel_path):
    with open(ROOT / rel_path, encoding="utf-8") as f:
        return json.load(f)


def main():
    if {"-h", "--help"} & set(sys.argv[1:]):
        print(__doc__.strip())
        return
    online = "--online" in sys.argv[1:]

    all_records = []  # (data_file_basename, record)
    for rel in DATA_FILES:
        for rec in load_records(rel):
            all_records.append((Path(rel).name, rec))

    commons_data = {}
    if online:
        filenames = []
        for _, rec in all_records:
            fn = commons_filename(rec.get("source", ""))
            if fn:
                filenames.append(fn)
        print(f"Querying Wikimedia Commons for {len(set(filenames))} unique files...")
        commons_data = fetch_commons_data(filenames)

    rows = []
    counts = {"OK": 0, "MISMATCH": 0, "UNVERIFIED": 0}
    mismatches = []

    for data_file, rec in all_records:
        rec_id = rec.get("id", "?")
        stored_lic = rec.get("license", "")
        stored_fam = family_of(stored_lic)

        source = rec.get("source", "")
        fn_hint_fam = hint_family(source)

        commons_lic = None
        commons_fam = None
        fn = commons_filename(source)
        if online and fn:
            info = commons_data.get(fn)
            if info:
                commons_lic = info.get("license")
                commons_fam = family_of(commons_lic)

        detected_fam = commons_fam if commons_fam is not None else fn_hint_fam

        if detected_fam is None:
            verdict = "UNVERIFIED"
        elif detected_fam == stored_fam:
            verdict = "OK"
        else:
            verdict = "MISMATCH"

        counts[verdict] += 1
        if verdict == "MISMATCH":
            mismatches.append({
                "file": data_file, "id": rec_id,
                "stored": stored_lic, "stored_fam": stored_fam,
                "fn_hint_fam": fn_hint_fam, "commons_lic": commons_lic,
                "commons_fam": commons_fam,
            })

        rows.append({
            "file": data_file,
            "id": rec_id,
            "stored_license": stored_lic,
            "filename_hint": fn_hint_fam or "",
            "commons_license": commons_lic or "",
            "verdict": verdict,
        })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "file", "id", "stored_license", "filename_hint",
            "commons_license", "verdict",
        ])
        w.writeheader()
        w.writerows(rows)

    print()
    print(f"Wrote {len(rows)} rows to {OUT_CSV.relative_to(ROOT)}")
    print()
    print("Verdict counts:")
    for k in ("OK", "MISMATCH", "UNVERIFIED"):
        print(f"  {k}: {counts[k]}")

    if mismatches:
        print()
        print(f"MISMATCHES ({len(mismatches)}):")
        for m in mismatches:
            detected = m["commons_fam"] or m["fn_hint_fam"]
            detail = []
            if m["fn_hint_fam"]:
                detail.append(f"filename hint={m['fn_hint_fam']}")
            if m["commons_lic"]:
                detail.append(f"commons={m['commons_lic']} ({m['commons_fam']})")
            print(f"  [{m['file']}] {m['id']}: stored='{m['stored']}' "
                  f"({m['stored_fam']}) vs detected={detected}  "
                  f"[{'; '.join(detail)}]")


if __name__ == "__main__":
    main()
