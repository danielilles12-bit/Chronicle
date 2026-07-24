#!/usr/bin/env python3
"""
fetch_metrics.py -- collect fame metrics for a list of Wikipedia titles.

Usage:
    python3 fetch_metrics.py <input.json> <output.jsonl>

Input:
    input.json is either:
      - a JSON array of {"name": ..., "wiki_title": ...} objects, or
      - any JSON object containing such a list under a top-level key
        (the first top-level list of dicts having "wiki_title" is used).

Output:
    output.jsonl, one JSON object per line:
      {"name", "wiki_title", "pageviews_5y", "months_present",
       "languages", "inlinks", "error"}
    (an extra "resolved_title" field is included when a title's article
    turned out to be a redirect to a different canonical title.)

Metrics collected per title:
    a) PAGEVIEWS -- Wikimedia REST API per-article monthly pageviews,
       en.wikipedia, all-access, user traffic, 2020070100 - 2025063000.
    b) LANGUAGES -- enwiki action=query&prop=langlinks&lllimit=500,
       count of langlinks + 1 (for English itself). This same call also
       resolves redirects (redirects=1), so the canonical/resolved title
       is reused for the pageviews and inlinks calls that follow.
    c) INLINKS -- enwiki action=query&list=search&srsearch=linksto:"<title>"
       &srlimit=1&srinfo=totalhits -- totalhits is the inbound link count.

Design notes:
    - Python 3.9 stdlib only (urllib.request, json, time, hashlib, pathlib).
    - Every request carries a fixed User-Agent.
    - A global throttle caps the request rate at roughly 8 req/s.
    - HTTP 429 / 5xx responses get exponential backoff, up to 5 tries;
      a 404 (no data) is treated as a definitive, cacheable answer.
    - Every raw API response is cached under tools/fame/cache/<metric>/
      keyed by a hash of the query title, so a killed-and-restarted run
      never re-fetches anything it already has. The output .jsonl file
      itself is also resumable: existing (name, wiki_title) rows are
      skipped on restart.
    - A missing article or missing pageview data never crashes the run;
      the row is written with nulls and a description in "error".
"""

import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "DeadFamousIntake/1.0 (daniel.illes12@gmail.com)"

RATE_PER_SEC = 8.0
MIN_INTERVAL = 1.0 / RATE_PER_SEC
MAX_RETRIES = 5
TIMEOUT_SECONDS = 30
BACKOFF_CAP_SECONDS = 30

PAGEVIEWS_START = "2020070100"
PAGEVIEWS_END = "2025063000"

SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_DIR = SCRIPT_DIR / "cache"

PROGRESS_EVERY = 100


# ---------------------------------------------------------------------------
# Low-level HTTP: throttling, retries, caching
# ---------------------------------------------------------------------------

class Stats:
    def __init__(self):
        self.requests = 0
        self.cache_hits = 0
        self.retries = 0


STATS = Stats()
_last_request_monotonic = [0.0]


def _throttle():
    now = time.monotonic()
    wait = _last_request_monotonic[0] + MIN_INTERVAL - now
    if wait > 0:
        time.sleep(wait)
    _last_request_monotonic[0] = time.monotonic()


def _cache_path(metric, key):
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()
    d = CACHE_DIR / metric
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{h}.json"


def _read_cache(cache_file):
    if cache_file is None or not cache_file.exists():
        return None
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        STATS.cache_hits += 1
        return data
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(cache_file, result):
    if cache_file is None:
        return
    try:
        cache_file.write_text(json.dumps(result), encoding="utf-8")
    except OSError:
        pass


def http_get_json(url, cache_file=None):
    """
    GET url, parse JSON, with caching / throttling / retry+backoff.

    Returns: {"ok": bool, "status": int|str, "body": dict|None, "error": str|None}

    Caching policy: successful (200) responses and definitive 404s and other
    definitive 4xx errors are cached (they are stable facts). Transient
    failures (timeouts, connection errors, and 429/5xx even after retries
    are exhausted) are never cached, so a re-run retries them.
    """
    cached = _read_cache(cache_file)
    if cached is not None:
        return cached

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        _throttle()
        STATS.requests += 1
        req = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                raw = resp.read()
                status = resp.status
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                parsed = None
            result = {"ok": True, "status": status, "body": parsed, "error": None}
            _write_cache(cache_file, result)
            return result

        except urllib.error.HTTPError as e:
            if e.code == 404:
                result = {"ok": False, "status": 404, "body": None, "error": "not_found"}
                _write_cache(cache_file, result)
                return result
            if e.code == 429 or 500 <= e.code < 600:
                STATS.retries += 1
                retry_after = None
                try:
                    retry_after = e.headers.get("Retry-After") if e.headers else None
                except Exception:
                    retry_after = None
                if retry_after and retry_after.strip().isdigit():
                    sleep_s = min(float(retry_after), BACKOFF_CAP_SECONDS)
                else:
                    sleep_s = min(2 ** attempt, BACKOFF_CAP_SECONDS)
                last_error = f"http_{e.code}"
                if attempt < MAX_RETRIES:
                    time.sleep(sleep_s)
                    continue
                result = {"ok": False, "status": e.code, "body": None, "error": last_error}
                return result
            # other definitive 4xx: don't retry, it's a stable outcome
            last_error = f"http_{e.code}"
            result = {"ok": False, "status": e.code, "body": None, "error": last_error}
            _write_cache(cache_file, result)
            return result

        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            STATS.retries += 1
            last_error = f"{type(e).__name__}:{e}"
            if attempt < MAX_RETRIES:
                time.sleep(min(2 ** attempt, BACKOFF_CAP_SECONDS))
                continue

    return {"ok": False, "status": "error", "body": None, "error": last_error or "max_retries_exceeded"}


# ---------------------------------------------------------------------------
# Per-metric fetchers
# ---------------------------------------------------------------------------

def _title_to_underscored(title):
    return title.strip().replace(" ", "_")


def fetch_pageviews(title):
    """Wikimedia REST pageviews, per-article, monthly, en.wikipedia, all-access, user."""
    underscored = _title_to_underscored(title)
    encoded = urllib.parse.quote(underscored, safe="")
    url = (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        f"en.wikipedia/all-access/user/{encoded}/monthly/"
        f"{PAGEVIEWS_START}/{PAGEVIEWS_END}"
    )
    cache_file = _cache_path("pageviews", underscored)
    return http_get_json(url, cache_file)


def fetch_languages_and_resolve(title):
    """
    enwiki action=query&prop=langlinks&lllimit=500, redirects=1.

    lllimit=500 comfortably exceeds the number of language editions any
    article could plausibly have (the practical maximum is a few hundred),
    so a single call is sufficient -- no continuation handling needed.

    This call also resolves redirects, so we return the canonical
    "resolved_title" for reuse by the pageviews/inlinks calls.

    Returns: {"ok", "missing", "error", "resolved_title", "languages"}
    """
    params = {
        "action": "query",
        "format": "json",
        "redirects": "1",
        "prop": "langlinks",
        "lllimit": "500",
        "titles": title,
    }
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    cache_file = _cache_path("languages", title)
    result = http_get_json(url, cache_file)

    if not result.get("ok"):
        return {
            "ok": False, "missing": False, "error": result.get("error"),
            "resolved_title": title, "languages": None,
        }

    body = result.get("body") or {}
    pages = ((body.get("query") or {}).get("pages")) or {}
    page = next(iter(pages.values()), None)
    if page is None:
        return {
            "ok": False, "missing": False, "error": "no_page_data",
            "resolved_title": title, "languages": None,
        }
    if "missing" in page:
        return {
            "ok": False, "missing": True, "error": "page_missing",
            "resolved_title": title, "languages": None,
        }

    resolved_title = page.get("title", title)
    langlinks = page.get("langlinks", []) or []
    languages = len(langlinks) + 1  # +1 for English itself
    return {
        "ok": True, "missing": False, "error": None,
        "resolved_title": resolved_title, "languages": languages,
    }


def fetch_inlinks(title):
    """enwiki action=query&list=search&srsearch=linksto:"<title>"&srlimit=1&srinfo=totalhits."""
    safe_title = title.replace('"', '\\"')
    query_str = f'linksto:"{safe_title}"'
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": query_str,
        "srlimit": "1",
        "srinfo": "totalhits",
    }
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    cache_file = _cache_path("inlinks", title)
    return http_get_json(url, cache_file)


# ---------------------------------------------------------------------------
# Per-item processing
# ---------------------------------------------------------------------------

def process_item(name, wiki_title):
    error_parts = []

    lang_result = fetch_languages_and_resolve(wiki_title)
    resolved_title = lang_result["resolved_title"]
    languages = lang_result["languages"]
    if not lang_result["ok"]:
        error_parts.append(f"languages:{lang_result.get('error')}")

    pv_result = fetch_pageviews(resolved_title)
    pageviews_5y = None
    months_present = None
    if pv_result.get("ok"):
        items = (pv_result.get("body") or {}).get("items") or []
        pageviews_5y = sum(it.get("views", 0) for it in items)
        months_present = len(items)
    elif pv_result.get("status") == 404:
        # No pageview data recorded for this article at all.
        pageviews_5y = 0
        months_present = 0
    else:
        error_parts.append(f"pageviews:{pv_result.get('error')}")

    il_result = fetch_inlinks(resolved_title)
    inlinks = None
    if il_result.get("ok"):
        searchinfo = ((il_result.get("body") or {}).get("query") or {}).get("searchinfo") or {}
        inlinks = searchinfo.get("totalhits")
    else:
        error_parts.append(f"inlinks:{il_result.get('error')}")

    record = {
        "name": name,
        "wiki_title": wiki_title,
        "pageviews_5y": pageviews_5y,
        "months_present": months_present,
        "languages": languages,
        "inlinks": inlinks,
        "error": ";".join(error_parts) if error_parts else None,
    }
    if resolved_title != wiki_title:
        record["resolved_title"] = resolved_title
    return record


# ---------------------------------------------------------------------------
# Input loading / output resumability
# ---------------------------------------------------------------------------

def _is_item_list(value):
    return (
        isinstance(value, list)
        and len(value) > 0
        and all(isinstance(x, dict) and "wiki_title" in x for x in value)
    )


def load_input_items(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if _is_item_list(data):
        return data
    if isinstance(data, dict):
        for value in data.values():
            if _is_item_list(value):
                return value
    raise SystemExit(
        f"Could not find a top-level list of {{'wiki_title': ...}} objects in {path}"
    )


def load_done_keys(output_path):
    done = set()
    if not output_path.exists():
        return done
    with output_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            done.add((rec.get("name"), rec.get("wiki_title")))
    return done


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 fetch_metrics.py <input.json> <output.jsonl>", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    items = load_input_items(input_path)
    total = len(items)
    done_keys = load_done_keys(output_path)

    if done_keys:
        print(f"Resuming: {len(done_keys)} items already in {output_path}", file=sys.stderr)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    processed_this_run = 0

    with output_path.open("a", encoding="utf-8") as out_f:
        for idx, item in enumerate(items, 1):
            wiki_title = item.get("wiki_title")
            name = item.get("name") or wiki_title
            if not wiki_title:
                continue
            key = (name, wiki_title)
            if key in done_keys:
                continue

            record = process_item(name, wiki_title)
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_f.flush()
            done_keys.add(key)
            processed_this_run += 1

            if idx % PROGRESS_EVERY == 0 or idx == total:
                elapsed = time.monotonic() - start
                print(
                    f"[{idx}/{total}] this_run={processed_this_run} "
                    f"requests={STATS.requests} cache_hits={STATS.cache_hits} "
                    f"retries={STATS.retries} elapsed={elapsed:.1f}s",
                    file=sys.stderr,
                )

    elapsed = time.monotonic() - start
    remaining = max(total - len(done_keys), 0)
    print(
        f"Done. {processed_this_run} items processed this run, "
        f"{len(done_keys)}/{total} total rows in output ({remaining} remaining). "
        f"HTTP requests={STATS.requests} cache_hits={STATS.cache_hits} "
        f"retries={STATS.retries} elapsed={elapsed:.1f}s",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
