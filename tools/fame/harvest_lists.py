"""
Generic harvester for Wikipedia "List of X" pages that use wikitables or
bullet/numbered lists, where each row/line represents one specific object.
Config-driven: tools/fame/list_sources.py holds the per-page settings.
"""
import json
import os
import re
import sys

import wputils

HERE = os.path.dirname(os.path.abspath(__file__))

FILE_LINK_RE = re.compile(r"^\s*(File|Image):", re.IGNORECASE)
SKIP_NS_PREFIXES = ("Wikipedia:", "Category:", "Template:", "Help:",
                     "Portal:", "Special:", "wikt:")


def _clean_target(target):
    return target.strip()


REF_TAG_RE = re.compile(r"<ref[^>]*>.*?</ref>", re.IGNORECASE | re.DOTALL)
REF_SELFCLOSE_RE = re.compile(r"<ref[^>]*/>", re.IGNORECASE)
CITE_TEMPLATE_RE = re.compile(r"\{\{[Cc]ite[^{}]*\}\}")
SORT_TEMPLATE_RE = re.compile(r"\{\{sort\|[^|{}]*\|(\[\[[^\]]+\]\])\}\}",
                               re.IGNORECASE)


def strip_citation_noise(chunk):
    """Remove <ref>...</ref>, self-closing refs, and {{cite ...}} templates
    so citation-embedded wikilinks don't get mistaken for the row's subject.
    Unwraps {{sort|key|[[Link]]}} down to the plain [[Link]]."""
    chunk = REF_TAG_RE.sub("", chunk)
    chunk = REF_SELFCLOSE_RE.sub("", chunk)
    chunk = CITE_TEMPLATE_RE.sub("", chunk)
    chunk = SORT_TEMPLATE_RE.sub(r"\1", chunk)
    return chunk


ITALIC_LINK_RE = re.compile(
    r"''+\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*?))?\]\]''+"
    r"|\[\[([^\]|#]+)(?:#[^\]|]*)?\|''+([^\]]*?)''+\]\]"
)


def first_italic_wikilink(chunk):
    """Prefer a wikilink that is italicised in wikitext -- Wikipedia's MOS
    italicises creative-work titles (paintings, ships, manuscripts...),
    which lets us skip past citation/author links that come first."""
    for m in ITALIC_LINK_RE.finditer(chunk):
        if m.group(1):
            target, display = m.group(1), m.group(2)
        else:
            target, display = m.group(3), m.group(4)
        target = target.strip()
        if FILE_LINK_RE.match(target) or any(
                target.startswith(p) for p in SKIP_NS_PREFIXES):
            continue
        display = display.strip() if display else target
        return target, display
    return None, None


def _all_real_wikilinks(chunk):
    out = []
    for m in wputils.WIKILINK_RE.finditer(chunk):
        target = m.group(1).strip()
        if FILE_LINK_RE.match(target):
            continue
        if any(target.startswith(p) for p in SKIP_NS_PREFIXES):
            continue
        display = m.group(2)
        display = display.strip() if display else target
        out.append((target, display))
    return out


def first_real_wikilink(chunk, keyword=None):
    chunk = strip_citation_noise(chunk)
    if keyword:
        for target, display in _all_real_wikilinks(chunk):
            if keyword.lower() in target.lower() or \
                    keyword.lower() in display.lower():
                return target, display
    italic_target, italic_display = first_italic_wikilink(chunk)
    if italic_target:
        return italic_target, italic_display
    links = _all_real_wikilinks(chunk)
    if links:
        return links[0]
    return None, None


def truncate_before_headings(wikitext, patterns):
    """Cut the wikitext at the first heading matching any pattern (regex,
    case-insensitive) so we don't scrape unrelated trailing sections."""
    if not patterns:
        return wikitext
    combined = re.compile(
        r"^==+\s*(?:" + "|".join(patterns) + r")[^=\n]*==+",
        re.IGNORECASE | re.MULTILINE)
    m = combined.search(wikitext)
    if m:
        return wikitext[:m.start()]
    return wikitext


def harvest_table_page(title, min_row_len=3, stop_headings=None,
                        keyword=None):
    """
    Split wikitext on wikitable row separators ('\\n|-') and pull the first
    real wikilink out of each chunk. Works for most simple wikitables
    regardless of whether cells use '!' (scope=row) or plain '|' syntax.
    If `keyword` is given, a link containing that keyword (in target or
    display text) is preferred over the row's first link -- useful when a
    row's earlier columns (dynasty, ruler, city...) outrank the actual
    subject column.
    """
    wt = wputils.get_wikitext(title)
    if not wt:
        return None, "missing"
    wt = truncate_before_headings(wt, stop_headings or
                                   [r"see also", r"references",
                                    r"external links", r"notes"])
    chunks = re.split(r"\n\|-", wt)
    if chunks:
        chunks = chunks[1:]  # drop pre-table lead/intro chunk
    items = []
    for chunk in chunks:
        if len(chunk.strip()) < min_row_len:
            continue
        target, display = first_real_wikilink(chunk, keyword=keyword)
        if not target:
            continue
        items.append({"raw_title": target, "name": display,
                       "context": chunk[:400]})
    return items, "table"


def extract_trailing_paren_wikilink(line):
    """
    For lines shaped 'Location, Holder, Shelfmark (Common Name)' (the
    convention used by List of illuminated manuscripts), return the first
    wikilink found inside the LAST parenthetical group on the line. Lines
    with no wikilinked name in that trailing group are not specific named
    works and are skipped (returns None, None).
    """
    idx = line.rfind("(")
    if idx == -1:
        return None, None
    tail = line[idx:]
    return first_real_wikilink(tail)


def harvest_bullet_page(title, stop_headings=None, link_picker=None):
    """Extract first wikilink from every '*' or '#' bulleted line."""
    wt = wputils.get_wikitext(title)
    if not wt:
        return None, "missing"
    wt = truncate_before_headings(wt, stop_headings or
                                   [r"see also", r"references",
                                    r"external links", r"notes"])
    picker = link_picker or (lambda line: first_real_wikilink(line))
    items = []
    for line in wt.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("*") or stripped.startswith("#")):
            continue
        target, display = picker(stripped)
        if not target:
            continue
        items.append({"raw_title": target, "name": display,
                       "context": stripped[:400]})
    return items, "bullet"


AMBIGUOUS_CONTINENT_HEADINGS = {"asia", "americas"}
DIRECT_REGION_HEADINGS = {
    "africa": "Africa", "europe": "Europe", "oceania": "Oceania",
    "middle east": "Middle East", "north america": "North America",
    "south america": "South America",
}


def harvest_sectioned_bullets(title, stop_headings=None):
    """
    Bullet-list page organised as ==Continent== / ===Country=== headings
    (e.g. List of colossal sculptures in situ). Tracks the nearest country
    or unambiguous continent heading as each item's region.
    """
    from regions import region_for_country
    wt = wputils.get_wikitext(title)
    if not wt:
        return None, "missing"
    wt = truncate_before_headings(wt, stop_headings or
                                   [r"see also", r"references",
                                    r"external links", r"notes"])
    heading_re = re.compile(r"^(==+)\s*([^=\n]+?)\s*==+\s*$")
    region = None
    items = []
    for line in wt.splitlines():
        hm = heading_re.match(line.strip())
        if hm:
            text = hm.group(2).strip()
            key = text.lower()
            country_region = region_for_country(text)
            if country_region:
                region = country_region
            elif key in DIRECT_REGION_HEADINGS:
                region = DIRECT_REGION_HEADINGS[key]
            elif key in AMBIGUOUS_CONTINENT_HEADINGS:
                region = None
            continue
        stripped = line.strip()
        if not (stripped.startswith("*") or stripped.startswith("#")):
            continue
        target, display = first_real_wikilink(stripped)
        if not target:
            continue
        items.append({"raw_title": target, "name": display,
                       "context": stripped[:400], "region": region})
    return items, "sectioned-bullet"


def run_sources(sources, out_filename):
    """
    sources: list of dicts with keys:
      title (wikipedia page title)
      mode ('table' or 'bullet')
      tag (from_lists tag)
      kind (default kind or None)
      region (default region or None)
      stop_headings (optional list of regex strings)
    """
    all_items = []
    for src in sources:
        mode = src.get("mode", "table")
        try:
            if mode == "table":
                items, status = harvest_table_page(
                    src["title"], stop_headings=src.get("stop_headings"),
                    keyword=src.get("prefer_keyword"))
            else:
                picker = None
                if src.get("link_picker") == "trailing_paren":
                    picker = extract_trailing_paren_wikilink
                if mode == "sectioned-bullet":
                    items, status = harvest_sectioned_bullets(
                        src["title"], stop_headings=src.get("stop_headings"))
                else:
                    items, status = harvest_bullet_page(
                        src["title"], stop_headings=src.get("stop_headings"),
                        link_picker=picker)
        except Exception as e:
            print(f"ERROR {src['title']}: {e}", file=sys.stderr)
            continue
        if items is None:
            print(f"MISSING {src['title']}", file=sys.stderr)
            continue
        for it in items:
            it["tag"] = src["tag"]
            it["kind"] = src.get("kind")
            if not it.get("region"):
                it["region"] = src.get("region")
            it["era_hint"] = src.get("era_hint")
        all_items.extend(items)
        print(f"{src['title']} [{src['tag']}]: {len(items)} items ({mode})",
              file=sys.stderr)

    out_path = os.path.join(HERE, "raw", out_filename)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=1)
    print(f"TOTAL: {len(all_items)} -> {out_path}", file=sys.stderr)
    return all_items
