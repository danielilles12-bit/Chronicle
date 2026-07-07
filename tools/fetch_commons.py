#!/usr/bin/env python3
"""Search/fetch Wikimedia Commons images for reveal-game items.

  python3 tools/fetch_commons.py search "Isaac Newton portrait Kneller"
  python3 tools/fetch_commons.py fetch "File:Portrait of Sir Isaac Newton, 1689.jpg" isaac-newton

search: prints top file titles + sizes for a query (namespace 6).
fetch:  downloads a ~1200px thumb to assets/img/<id>.jpg and prints a JSON
        stub with license/attribution/source filled from extmetadata.
"""
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "ChronicleContentBot/1.0 (daniel.illes12@gmail.com)"}


def api(params):
    params = dict(params, format="json")
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def search(query, limit=6):
    d = api({"action": "query", "list": "search", "srsearch": query,
             "srnamespace": 6, "srlimit": limit})
    for hit in d["query"]["search"]:
        print(hit["title"])


def fetch(title, item_id):
    d = api({"action": "query", "titles": title, "prop": "imageinfo",
             "iiprop": "url|extmetadata|size", "iiurlwidth": 1200})
    page = next(iter(d["query"]["pages"].values()))
    if "imageinfo" not in page:
        sys.exit(f"no imageinfo for {title!r} — check the exact file title")
    ii = page["imageinfo"][0]
    meta = ii.get("extmetadata", {})
    lic = strip_tags(meta.get("LicenseShortName", {}).get("value", ""))
    artist = strip_tags(meta.get("Artist", {}).get("value", ""))
    out = ROOT / "assets/img" / f"{item_id}.jpg"
    url = ii.get("thumburl") or ii["url"]
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        out.write_bytes(r.read())
    stub = {
        "id": item_id,
        "img": f"assets/img/{item_id}.jpg",
        "license": lic,
        "attribution": artist,
        "source": "Wikimedia Commons: " + title.replace("File:", ""),
        "_bytes": out.stat().st_size,
        "_size": f"{ii.get('width')}x{ii.get('height')}",
    }
    print(json.dumps(stub, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "search":
        search(sys.argv[2])
    elif cmd == "fetch":
        fetch(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
