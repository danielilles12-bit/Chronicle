"""
Shared HTTP + Wikipedia helpers for the Relic universe-of-objects harvester.
Python 3.9 stdlib only. No third-party deps.
"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import hashlib

UA = "DeadFamousIntake/1.0 (daniel.illes12@gmail.com)"
RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
os.makedirs(RAW_DIR, exist_ok=True)

_MIN_INTERVAL = 1.0 / 8.0  # max ~8 req/s
_last_request_ts = [0.0]


def _throttle():
    now = time.monotonic()
    wait = _MIN_INTERVAL - (now - _last_request_ts[0])
    if wait > 0:
        time.sleep(wait)
    _last_request_ts[0] = time.monotonic()


def _cache_path(url):
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return os.path.join(RAW_DIR, h + ".json")


def fetch_url(url, use_cache=True, max_retries=6):
    """GET a URL with UA header, disk caching, retry+backoff on 429/5xx."""
    cache_file = _cache_path(url)
    if use_cache and os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return meta["body"]

    attempt = 0
    backoff = 1.0
    while True:
        attempt += 1
        _throttle()
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            if use_cache:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump({"url": url, "body": body}, f)
            return body
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt <= max_retries:
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt <= max_retries:
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue
            raise


EN_API = "https://en.wikipedia.org/w/api.php"
WD_API = "https://www.wikidata.org/w/api.php"


def api_get(base, params, use_cache=True):
    params = dict(params)
    params.setdefault("format", "json")
    qs = urllib.parse.urlencode(params, safe="|")
    url = f"{base}?{qs}"
    body = fetch_url(url, use_cache=use_cache)
    return json.loads(body)


def get_wikitext(title, use_cache=True):
    """Fetch raw wikitext of the latest revision of a page."""
    data = api_get(EN_API, {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "titles": title,
        "formatversion": "2",
    }, use_cache=use_cache)
    pages = data.get("query", {}).get("pages", [])
    if not pages:
        return None
    page = pages[0]
    if "missing" in page:
        return None
    revs = page.get("revisions")
    if not revs:
        return None
    return revs[0]["slots"]["main"]["content"]


def canonicalize_titles(titles, batch_size=50):
    """
    Given a list of raw wikilink titles, resolve redirects/normalization
    via the enwiki API. Returns dict raw_title -> {"title": canonical,
    "missing": bool, "exists": bool}.
    """
    result = {}
    titles = list(dict.fromkeys(titles))  # dedup preserve order
    for i in range(0, len(titles), batch_size):
        batch = titles[i:i + batch_size]
        data = api_get(EN_API, {
            "action": "query",
            "titles": "|".join(batch),
            "redirects": "1",
            "formatversion": "2",
        })
        query = data.get("query", {})
        norm_map = {}
        for n in query.get("normalized", []):
            norm_map[n["from"]] = n["to"]
        redir_map = {}
        for r in query.get("redirects", []):
            redir_map[r["from"]] = r["to"]
        pages_by_title = {}
        for p in query.get("pages", []):
            pages_by_title[p["title"]] = p

        for raw in batch:
            cur = raw
            if cur in norm_map:
                cur = norm_map[cur]
            if cur in redir_map:
                cur = redir_map[cur]
            page = pages_by_title.get(cur)
            if page is None:
                result[raw] = {"title": cur, "missing": True, "exists": False}
            else:
                missing = "missing" in page
                is_disambig = False
                result[raw] = {
                    "title": page.get("title", cur),
                    "missing": missing,
                    "exists": not missing,
                    "pageid": page.get("pageid"),
                }
    return result


def enrich_titles(titles, batch_size=20):
    """
    For canonical (existing) enwiki titles, fetch pageprops (to detect
    disambiguation pages) and categories (to heuristically detect person
    articles via birth/death/'Living people' categories).
    Returns dict title -> {"is_disambig": bool, "is_person": bool}.
    """
    result = {}
    titles = list(dict.fromkeys(titles))
    person_cat_re = re.compile(
        r"\b(births|deaths)\b"
        r"|^living people$"
        r"|\bpeople\b"
        r"|\b(monarchs|emperors|empresses|kings|queens|popes|pharaohs|"
        r"philosophers|religious leaders|founders of religions|"
        r"presidents|prime ministers|politicians|monks|nuns|saints|"
        r"rulers)\b",
        re.IGNORECASE)
    for i in range(0, len(titles), batch_size):
        batch = titles[i:i + batch_size]
        data = api_get(EN_API, {
            "action": "query",
            "titles": "|".join(batch),
            "prop": "pageprops|categories",
            "ppprop": "disambiguation",
            "cllimit": "max",
            "formatversion": "2",
        })
        pages = data.get("query", {}).get("pages", [])
        for p in pages:
            title = p.get("title")
            if not title:
                continue
            is_disambig = "pageprops" in p and \
                "disambiguation" in p.get("pageprops", {})
            is_person = False
            for c in p.get("categories", []):
                cname = c.get("title", "").replace("Category:", "")
                if person_cat_re.search(cname):
                    is_person = True
                    break
            result[title] = {"is_disambig": is_disambig,
                              "is_person": is_person}
    return result


WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")


def extract_wikilinks(wikitext):
    """Return list of (target_title, display_text_or_None) from wikitext."""
    out = []
    for m in WIKILINK_RE.finditer(wikitext):
        target = m.group(1).strip()
        display = m.group(2)
        if display is not None:
            display = display.strip()
        out.append((target, display))
    return out
