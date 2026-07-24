"""
Fill in missing 'region' for universe_objects.json entries using Wikidata:
enwiki title -> wikibase_item (Q-id) -> P17 (country) or P131 (admin
location) claim -> Q-id -> English label -> regions.region_for_country().
Only touches objects whose region is currently null.
"""
import json
import os
import sys

import wputils
from regions import region_for_country

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, "universe_objects.json")


def batched(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def get_wikibase_items(titles):
    result = {}
    for batch in batched(titles, 50):
        data = wputils.api_get(wputils.EN_API, {
            "action": "query", "titles": "|".join(batch),
            "prop": "pageprops", "ppprop": "wikibase_item",
            "formatversion": "2",
        })
        for p in data.get("query", {}).get("pages", []):
            qid = p.get("pageprops", {}).get("wikibase_item")
            if qid:
                result[p["title"]] = qid
    return result


def get_country_claims(qids):
    """qid -> country-or-location Q-id (P17 preferred, else P131)."""
    result = {}
    for batch in batched(qids, 50):
        data = wputils.api_get(wputils.WD_API, {
            "action": "wbgetentities", "ids": "|".join(batch),
            "props": "claims", "format": "json",
        })
        for qid, ent in data.get("entities", {}).items():
            claims = ent.get("claims", {})
            loc_qid = None
            for prop in ("P17", "P131"):
                c = claims.get(prop)
                if c:
                    try:
                        loc_qid = c[0]["mainsnak"]["datavalue"]["value"]["id"]
                        break
                    except (KeyError, IndexError):
                        continue
            if loc_qid:
                result[qid] = loc_qid
    return result


def get_labels(qids):
    result = {}
    for batch in batched(qids, 50):
        data = wputils.api_get(wputils.WD_API, {
            "action": "wbgetentities", "ids": "|".join(batch),
            "props": "labels", "languages": "en", "format": "json",
        })
        for qid, ent in data.get("entities", {}).items():
            label = ent.get("labels", {}).get("en", {}).get("value")
            if label:
                result[qid] = label
    return result


def main():
    with open(OUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    objects = data["objects"]

    missing = [o for o in objects if not o.get("region")]
    print(f"Objects missing region: {len(missing)}", file=sys.stderr)
    titles = [o["wiki_title"] for o in missing]

    title_to_qid = get_wikibase_items(titles)
    print(f"Resolved wikibase items: {len(title_to_qid)}", file=sys.stderr)

    qid_to_loc = get_country_claims(list(set(title_to_qid.values())))
    print(f"Resolved country/location claims: {len(qid_to_loc)}",
          file=sys.stderr)

    loc_qids = list(set(qid_to_loc.values()))
    loc_labels = get_labels(loc_qids)
    print(f"Resolved location labels: {len(loc_labels)}", file=sys.stderr)

    filled = 0
    unresolved_labels = set()
    for o in missing:
        qid = title_to_qid.get(o["wiki_title"])
        if not qid:
            continue
        loc_qid = qid_to_loc.get(qid)
        if not loc_qid:
            continue
        label = loc_labels.get(loc_qid)
        if not label:
            continue
        region = region_for_country(label)
        if region:
            o["region"] = region
            filled += 1
        else:
            unresolved_labels.add(label)

    print(f"Filled region for {filled} objects", file=sys.stderr)
    print(f"Still-missing count: "
          f"{sum(1 for o in objects if not o.get('region'))}",
          file=sys.stderr)
    print(f"Sample unresolved location labels (not in country map): "
          f"{sorted(unresolved_labels)[:30]}", file=sys.stderr)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"Rewrote {OUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
