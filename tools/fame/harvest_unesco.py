"""
Harvest UNESCO World Heritage Sites (cultural + mixed, natural excluded)
from per-country "List of World Heritage Sites in X" Wikipedia articles.
Falls back to category membership for countries without such a list page.
"""
import json
import os
import re
import sys

import wputils
from regions import region_for_country
from kindguess import guess_kind

HERE = os.path.dirname(os.path.abspath(__file__))

FILE_LINK_RE = re.compile(r"^\s*File:", re.IGNORECASE)
IMAGE_LINK_RE = re.compile(r"^\s*Image:", re.IGNORECASE)


def get_country_categories():
    data = wputils.api_get(wputils.EN_API, {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": "Category:World Heritage Sites by country",
        "cmlimit": "500",
        "formatversion": "2",
    })
    cats = [c["title"] for c in data["query"]["categorymembers"]
            if c["title"].startswith("Category:World Heritage Sites in ")]
    countries = [c[len("Category:World Heritage Sites in "):] for c in cats]
    return countries


def split_rows(wikitext):
    """
    Locate the main WHS wikitable (has a header row mentioning 'Site' and
    'Criteria'/'UNESCO data') and split it into per-site row chunks keyed
    on '! scope="row"'.
    """
    rows = []
    # Find all row-header start positions
    starts = [m.start() for m in re.finditer(r'!\s*scope="row"', wikitext)]
    if not starts:
        return rows
    starts.append(len(wikitext))
    for i in range(len(starts) - 1):
        chunk = wikitext[starts[i]:starts[i + 1]]
        rows.append(chunk)
    return rows


def first_wikilink(chunk):
    for m in wputils.WIKILINK_RE.finditer(chunk):
        target = m.group(1).strip()
        if FILE_LINK_RE.match(target) or IMAGE_LINK_RE.match(target):
            continue
        display = m.group(2)
        display = display.strip() if display else target
        return target, display
    return None, None


def is_natural_only(chunk):
    low = chunk.lower()
    has_natural = "(natural)" in low
    has_cultural = "(cultural)" in low
    has_mixed = "(mixed)" in low
    # some rows phrase it as "natural, previously..." etc. Be lenient:
    if has_cultural or has_mixed:
        return False
    if has_natural:
        return True
    # No explicit marker found (rare/irregular formatting) -> keep, don't
    # drop items we can't classify (precision-first happens at merge time).
    return False


TENTATIVE_HEADING_RE = re.compile(
    r"^==+\s*[^=\n]*tentative[^=\n]*==+", re.IGNORECASE | re.MULTILINE)


def truncate_before_tentative(wikitext):
    m = TENTATIVE_HEADING_RE.search(wikitext)
    if m:
        return wikitext[:m.start()]
    return wikitext


def harvest_country(country):
    list_title = f"List of World Heritage Sites in {country}"
    wt = wputils.get_wikitext(list_title)
    items = []
    if wt and "scope=\"row\"" in wt:
        wt = truncate_before_tentative(wt)
        for chunk in split_rows(wt):
            target, display = first_wikilink(chunk)
            if not target:
                continue
            if is_natural_only(chunk):
                continue
            items.append({
                "raw_title": target,
                "name": display,
                "country": country,
            })
        if items:
            return items, "list-table"

    # Fallback: category membership (small countries, single-site, etc.)
    cat_title = f"Category:World Heritage Sites in {country}"
    data = wputils.api_get(wputils.EN_API, {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": cat_title,
        "cmlimit": "500",
        "cmnamespace": "0",
        "formatversion": "2",
    })
    for c in data.get("query", {}).get("categorymembers", []):
        title = c["title"]
        if title.startswith("List of "):
            continue
        items.append({
            "raw_title": title,
            "name": title,
            "country": country,
        })
    return items, "category-fallback"


def main():
    countries = get_country_categories()
    print(f"# countries: {len(countries)}", file=sys.stderr)

    all_items = []
    fallback_used = []
    for idx, country in enumerate(countries):
        try:
            items, method = harvest_country(country)
        except Exception as e:
            print(f"ERROR {country}: {e}", file=sys.stderr)
            continue
        if method == "category-fallback":
            fallback_used.append(country)
        for it in items:
            it["region"] = region_for_country(country)
            all_items.append(it)
        print(f"[{idx+1}/{len(countries)}] {country}: {len(items)} ({method})",
              file=sys.stderr)

    print(f"TOTAL raw rows: {len(all_items)}", file=sys.stderr)
    print(f"Fallback countries ({len(fallback_used)}): {fallback_used}",
          file=sys.stderr)

    out_path = os.path.join(HERE, "raw", "unesco_raw.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=1)
    print(f"Wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
