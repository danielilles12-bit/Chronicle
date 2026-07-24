"""
Harvest specific named works/structures from Wikipedia:Vital articles/Level 4/Arts.
Only pulls sections that list SPECIFIC, single instances (not general topics):
 - Specific structures
 - Cultural venues (by region sub-heading: Africa/Americas/Asia/Europe/General)
 - Painting
 - Sculpture
"""
import json
import os
import re
import sys

import wputils

HERE = os.path.dirname(os.path.abspath(__file__))

SKIP_NS_PREFIXES = ("Wikipedia:", "Category:", "File:", "Image:", "Template:",
                     "Help:", "Portal:", "Special:")


def find_section_span(wikitext, heading_pattern, level_min=2, level_max=4):
    """
    Find a section whose heading text matches heading_pattern (regex, applied
    to the stripped heading text). Returns (start_of_body, end_of_body) where
    end is the position of the next heading at the SAME or SHALLOWER level.
    """
    heading_re = re.compile(r"^(==+)\s*([^=\n]+?)\s*==+\s*$", re.MULTILINE)
    headings = [(m.start(), m.end(), len(m.group(1)), m.group(2))
                for m in heading_re.finditer(wikitext)]
    for i, (start, end, level, text) in enumerate(headings):
        clean_text = re.sub(r"\{\{anchor\|[^}]*\}\}", "", text).strip()
        if re.search(heading_pattern, clean_text, re.IGNORECASE):
            body_start = end
            body_end = len(wikitext)
            for j in range(i + 1, len(headings)):
                if headings[j][2] <= level:
                    body_end = headings[j][0]
                    break
            return body_start, body_end, clean_text
    return None


def extract_list_links(chunk):
    """
    Extract one (raw_title, display) pair per numbered/bulleted list line
    ('#' or '*' prefixed), taking the first non-namespaced wikilink on the
    line. Falls back to nested '##' lines too.
    """
    items = []
    for line in chunk.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("#") or stripped.startswith("*")):
            continue
        for m in wputils.WIKILINK_RE.finditer(stripped):
            target = m.group(1).strip()
            if any(target.startswith(p) for p in SKIP_NS_PREFIXES):
                continue
            display = m.group(2)
            display = display.strip() if display else target
            items.append((target, display))
            break  # first real link only
    return items


def main():
    wt = wputils.get_wikitext("Wikipedia:Vital articles/Level 4/Arts")
    if not wt:
        print("Could not fetch Vital Arts page", file=sys.stderr)
        sys.exit(1)

    results = []

    # 1. Specific structures (buildings/monuments/sites)
    span = find_section_span(wt, r"^Specific structures$")
    if span:
        body_start, body_end, _ = span
        for target, display in extract_list_links(wt[body_start:body_end]):
            results.append({
                "raw_title": target, "name": display,
                "vital_section": "Specific structures", "region": None,
            })

    # 2. Cultural venues, walk sub-headings for region hints
    span = find_section_span(wt, r"^Cultural venues$")
    if span:
        body_start, body_end, _ = span
        sub_re = re.compile(r"^===+\s*([^=\n]+?)\s*===+\s*$", re.MULTILINE)
        subs = [(m.start(), m.end(), m.group(1)) for m in
                sub_re.finditer(wt, body_start, body_end)]
        for i, (sstart, send, stext) in enumerate(subs):
            chunk_end = subs[i + 1][0] if i + 1 < len(subs) else body_end
            chunk = wt[send:chunk_end]
            region_map = {
                "Africa": "Africa", "Americas": "North America",
                "Asia": "East Asia", "Europe": "Europe",
            }
            region = region_map.get(stext.strip())
            for target, display in extract_list_links(chunk):
                results.append({
                    "raw_title": target, "name": display,
                    "vital_section": f"Cultural venues: {stext.strip()}",
                    "region": region,
                })

    # 3. Painting
    span = find_section_span(wt, r"^Painting$")
    if span:
        body_start, body_end, _ = span
        for target, display in extract_list_links(wt[body_start:body_end]):
            results.append({
                "raw_title": target, "name": display,
                "vital_section": "Painting", "region": None,
            })

    # 4. Sculpture
    span = find_section_span(wt, r"^Sculpture$")
    if span:
        body_start, body_end, _ = span
        for target, display in extract_list_links(wt[body_start:body_end]):
            results.append({
                "raw_title": target, "name": display,
                "vital_section": "Sculpture", "region": None,
            })

    print(f"Total vital items: {len(results)}", file=sys.stderr)
    for r in results:
        print(f"  [{r['vital_section']}] {r['raw_title']}", file=sys.stderr)

    out_path = os.path.join(HERE, "raw", "vital_raw.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print(f"Wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
