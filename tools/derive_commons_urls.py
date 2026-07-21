#!/usr/bin/env python3
"""Derive full image-credit fields for every reveal-who/reveal-what record
from its `source` filename ("Wikimedia Commons: <filename>").

For each record:
  - Always computable offline: image_source_url, the direct Commons
    file-page URL (MediaWiki title-encoding of the filename).
  - With --online: batch-query the Commons API for imageinfo/extmetadata,
    confirm the file resolves (equivalent to an HTTP 200 on the file page —
    spot-checked by hand against the raw wiki URLs; the API call is the
    same lookup, batched) and that its licence family matches the record's
    stored `license`. Only records that pass BOTH checks get written:
    image_source_url / image_author / image_license / image_license_url /
    image_retrieved. Everything else — no Commons source, file not found,
    licence mismatch — is left untouched and reported to
    tools/out/commons_report.csv for manual review. Nothing is guessed.

Writes are targeted (json.load / mutate specific keys / json.dump with the
same indent=1, ensure_ascii=False, trailing-newline convention already used
in these files) — a full round-trip of an untouched file byte-diffs clean.

Usage:
  python3 tools/derive_commons_urls.py             # offline: URLs only, no writes, no report
  python3 tools/derive_commons_urls.py --online              # verify + write + report
  python3 tools/derive_commons_urls.py --online --dry-run    # verify + report, no writes
"""
import csv
import json
import re
import sys
import urllib.parse
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_rights import (  # noqa: E402
    SOURCE_PREFIX, commons_filename, family_of, fetch_commons_data,
)

ROOT = Path(__file__).resolve().parent.parent
DATA_FILES = ["data/reveal-who.json", "data/reveal-what.json"]
OUT_CSV = ROOT / "tools/out/commons_report.csv"

# A handful of Commons extmetadata Artist values come out doubled (two
# wikidata/template properties concatenated with no separator, e.g.
# "Unknown authorUnknown author") or carrying a raw wiki username namespace
# ("User:Foo"). Fixed here, once, rather than wherever image_author is later
# displayed. Deliberately narrow: multi-contributor strings ("Original: X
# Derivative work: Y") are real attribution chains, not noise, and are left
# exactly as Commons has them.
_DOUBLED_RE = re.compile(r"^(Unknown author|Unknown artist|Anonymous)(Unknown author|Unknown artist)$")


def clean_author(name):
    name = (name or "").strip()
    m = _DOUBLED_RE.match(name)
    if m:
        return m.group(2)
    if name.startswith("User:"):
        return name[len("User:"):]
    if name.startswith("en:User:"):
        return name[len("en:User:"):]
    return name


_GENERIC_AUTHOR_RE = re.compile(
    r"^(unknown (author|artist|photographer)|anonymous|own work|self[- ]?published)$",
    re.IGNORECASE)
# Commons' Credit field commonly ends "(Own work)" or "(<year>)" — boilerplate
# that adds nothing over the bare name once it's standing in for Artist.
_CREDIT_SUFFIX_RE = re.compile(r"\s*\((?:Own work|\d{4})\)\s*$")


def best_author(artist, credit):
    """Some Commons files leave Artist empty/generic and record the real
    photographer only in Credit (e.g. Artist='', Credit='Marie-Lan Nguyen
    (2007)') — Commons' own file-page UI falls back to Credit for display in
    exactly this case, so we do too. Prefers a real Artist name; only drops
    to Credit when Artist is empty or itself generic ("Unknown author")."""
    a = clean_author(artist)
    if a and not _GENERIC_AUTHOR_RE.match(a):
        return a
    c = _CREDIT_SUFFIX_RE.sub("", (credit or "").strip()).strip()
    if c and not _GENERIC_AUTHOR_RE.match(c):
        return c
    return a or c or None


def commons_file_url(filename):
    # MediaWiki canonicalises spaces to underscores in titles; percent-encode
    # everything else so the URL hits the page directly, no redirect hop.
    return "https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(
        filename.replace(" ", "_"), safe="")


def load_records(rel_path):
    text = (ROOT / rel_path).read_text(encoding="utf-8")
    return json.loads(text), text.endswith("\n")


def save_records(rel_path, items, trailing_newline):
    out = json.dumps(items, indent=1, ensure_ascii=False)
    if trailing_newline:
        out += "\n"
    (ROOT / rel_path).write_text(out, encoding="utf-8")


def main():
    online = "--online" in sys.argv[1:]
    dry_run = "--dry-run" in sys.argv[1:]

    per_file = {}
    all_filenames = []
    for rel in DATA_FILES:
        items, trailing_nl = load_records(rel)
        per_file[rel] = {"items": items, "trailing_nl": trailing_nl}
        for rec in items:
            fn = commons_filename(rec.get("source", ""))
            if fn:
                all_filenames.append(fn)

    print(f"{sum(len(v['items']) for v in per_file.values())} records total, "
          f"{len(all_filenames)} with a Wikimedia Commons source filename")

    commons_data = {}
    if online:
        print(f"Verifying {len(set(all_filenames))} unique files against Commons...")
        commons_data = fetch_commons_data(all_filenames)

    today = date.today().isoformat()
    report_rows = []
    written = 0
    skipped_no_source = 0

    for rel, bundle in per_file.items():
        changed = False
        for rec in bundle["items"]:
            rec_id = rec.get("id", "?")
            source = rec.get("source", "")
            fn = commons_filename(source)

            if not fn:
                skipped_no_source += 1
                report_rows.append({
                    "file": Path(rel).name, "id": rec_id,
                    "reason": "source is not a 'Wikimedia Commons: <file>' string",
                    "stored_license": rec.get("license", ""),
                    "detail": source,
                })
                continue

            source_url = commons_file_url(fn)

            if not online:
                continue  # offline mode: nothing verified, nothing written

            info = commons_data.get(fn)
            if info is None:
                report_rows.append({
                    "file": Path(rel).name, "id": rec_id,
                    "reason": "not found on Commons",
                    "stored_license": rec.get("license", ""),
                    "detail": fn,
                })
                continue

            commons_lic = info.get("license")
            commons_fam = family_of(commons_lic)
            stored_fam = family_of(rec.get("license", ""))
            if commons_fam != stored_fam:
                report_rows.append({
                    "file": Path(rel).name, "id": rec_id,
                    "reason": "licence mismatch",
                    "stored_license": rec.get("license", ""),
                    "detail": f"commons={commons_lic!r} ({commons_fam}) vs stored ({stored_fam})",
                })
                continue

            if dry_run:
                written += 1
                continue

            rec["image_source_url"] = source_url
            author = best_author(info.get("artist"), info.get("credit"))
            if author:
                rec["image_author"] = author
            if commons_lic:
                rec["image_license"] = commons_lic
            if info.get("license_url"):
                rec["image_license_url"] = info["license_url"]
            rec["image_retrieved"] = today
            written += 1
            changed = True

        if changed:
            save_records(rel, bundle["items"], bundle["trailing_nl"])

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "id", "reason", "stored_license", "detail"])
        w.writeheader()
        w.writerows(report_rows)

    print()
    if not online:
        print("Offline run: URLs are computable but nothing was verified or written.")
        print("Re-run with --online to verify against Commons and populate image_* fields.")
    else:
        print(f"{'Would write' if dry_run else 'Wrote'} image credit fields to {written} records.")
        print(f"{len(report_rows)} records need manual review "
              f"(written to {OUT_CSV.relative_to(ROOT)}):")
        by_reason = {}
        for r in report_rows:
            by_reason.setdefault(r["reason"], 0)
            by_reason[r["reason"]] += 1
        for reason, n in sorted(by_reason.items()):
            print(f"  {reason}: {n}")


if __name__ == "__main__":
    main()
