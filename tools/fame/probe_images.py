#!/usr/bin/env python3
"""
probe_images.py -- image-feasibility probe for Dead Famous intake candidates.

For every candidate in universe_people.json, universe_objects.json, and
metrics_input_wave3.json, determine whether a canonical Wikidata image (P18)
exists and whether its Commons license is usable for the game (torn-photo
reveals need a real, properly-licensed image).

Usage:
    python3 probe_images.py

Pipeline (three batched stages, each resumable via a persistent JSON map
under cache/image_probe/state/):

  Stage 1  title -> QID
      enwiki action=query&prop=pageprops&redirects=1, batches of 50.
      universe_people.json already carries a "qid" field, so people skip
      this stage entirely; only objects + wave3 titles are looked up.

  Stage 2  QID -> P18 filename
      wikidata action=wbgetentities&props=claims, batches of 50 ids.
      The first P18 (image) claim's filename is recorded, if any.

  Stage 3  filename -> license
      commons action=query&prop=imageinfo&iiprop=extmetadata|size,
      titles="File:<name>", batches of 50 files. LicenseShortName, Artist
      (HTML-stripped), a "compact" Credit, and pixel width/height are kept.

Design notes:
    - Python 3.9 stdlib only.
    - Every request carries a fixed User-Agent and is globally throttled
      (default 5 req/s -- comfortably under the 8 req/s ceiling, since other
      fetch jobs may be sharing the API at the same time).
    - HTTP 429 / 5xx get exponential backoff (Retry-After honoured); a 404
      or other definitive 4xx is treated as a stable, cacheable answer.
    - Raw HTTP responses are cached under cache/image_probe/raw/ by URL
      hash. On top of that, each stage keeps its own persistent map
      (cache/image_probe/state/*.json) so a killed-and-restarted run only
      re-does the batch it was in the middle of -- transient failures are
      never written into the map, so they're naturally retried.
    - Progress is printed roughly every 200 items processed per stage.
    - This script does not read or write data/, js/, or any metrics_*.jsonl.
      It only adds a new cache/image_probe/ subfolder and writes
      tools/fame/image_availability.json.
"""

import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timezone, datetime
from pathlib import Path

USER_AGENT = "DeadFamousIntake/1.0 (daniel.illes12@gmail.com)"

RATE_PER_SEC = 5.0  # stay well under the 8 req/s ceiling; other jobs share it
MIN_INTERVAL = 1.0 / RATE_PER_SEC
MAX_RETRIES = 5
TIMEOUT_SECONDS = 30
BACKOFF_CAP_SECONDS = 30

BATCH_SIZE = 50
PROGRESS_EVERY = 200
SMALL_THRESHOLD_PX = 800

SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_DIR = SCRIPT_DIR / "cache" / "image_probe"
RAW_CACHE_DIR = CACHE_DIR / "raw"
STATE_DIR = CACHE_DIR / "state"

EN_API = "https://en.wikipedia.org/w/api.php"
WD_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

PEOPLE_PATH = SCRIPT_DIR / "universe_people.json"
OBJECTS_PATH = SCRIPT_DIR / "universe_objects.json"
WAVE3_PATH = SCRIPT_DIR / "metrics_input_wave3.json"
OUTPUT_PATH = SCRIPT_DIR / "image_availability.json"


# ---------------------------------------------------------------------------
# Low-level HTTP: throttling, retries, disk caching
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


def _raw_cache_path(url):
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return RAW_CACHE_DIR / f"{h}.json"


def http_get_json(url):
    """
    GET url, parse JSON, with disk caching / throttling / retry+backoff.

    Returns: {"ok": bool, "status": int|str, "body": dict|None, "error": str|None}

    Caching policy: successful (200) responses and definitive 404 / other
    4xx errors are cached (stable facts). Transient failures (timeouts,
    connection errors, 429/5xx even after retries exhausted) are never
    cached, so a re-run retries them for real.
    """
    cache_file = _raw_cache_path(url)
    if cache_file.exists():
        try:
            STATS.cache_hits += 1
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        _throttle()
        STATS.requests += 1
        req = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                raw = resp.read()
                status = resp.status
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                parsed = None
            result = {"ok": True, "status": status, "body": parsed, "error": None}
            try:
                cache_file.write_text(json.dumps(result), encoding="utf-8")
            except OSError:
                pass
            return result

        except urllib.error.HTTPError as e:
            if e.code == 404:
                result = {"ok": False, "status": 404, "body": None, "error": "not_found"}
                try:
                    cache_file.write_text(json.dumps(result), encoding="utf-8")
                except OSError:
                    pass
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
                return {"ok": False, "status": e.code, "body": None, "error": last_error}
            # other definitive 4xx: stable, cache it
            last_error = f"http_{e.code}"
            result = {"ok": False, "status": e.code, "body": None, "error": last_error}
            try:
                cache_file.write_text(json.dumps(result), encoding="utf-8")
            except OSError:
                pass
            return result

        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            STATS.retries += 1
            last_error = f"{type(e).__name__}:{e}"
            if attempt < MAX_RETRIES:
                time.sleep(min(2 ** attempt, BACKOFF_CAP_SECONDS))
                continue

    return {"ok": False, "status": "error", "body": None,
            "error": last_error or "max_retries_exceeded"}


def api_get(base, params):
    params = dict(params)
    params.setdefault("format", "json")
    qs = urllib.parse.urlencode(params, safe="|:")
    url = f"{base}?{qs}"
    return http_get_json(url)


# ---------------------------------------------------------------------------
# Persistent per-stage state maps (resumability)
# ---------------------------------------------------------------------------

def _state_path(name):
    return STATE_DIR / name


def load_state(name):
    p = _state_path(name)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(name, data):
    p = _state_path(name)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def dedup_preserve_order(seq):
    seen = set()
    out = []
    for x in seq:
        if x is None or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def chunked(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def progress(label, done, total, start):
    if done < total and (done % PROGRESS_EVERY) >= BATCH_SIZE and done != total:
        return
    elapsed = time.monotonic() - start
    rate = done / elapsed if elapsed > 0 else 0.0
    print(f"[{label}] {done}/{total} done "
          f"({rate:.1f}/s, {elapsed:.0f}s elapsed, "
          f"{STATS.requests} reqs, {STATS.cache_hits} cache hits)", flush=True)


# ---------------------------------------------------------------------------
# Stage 1: title -> QID  (objects + wave3 only; people already have one)
# ---------------------------------------------------------------------------

def stage1_resolve_qids(titles, qid_map):
    pending = [t for t in titles if t not in qid_map]
    total_all = len(titles)
    if not pending:
        print(f"[stage1] all {total_all} titles already resolved (cache)", flush=True)
        return
    print(f"[stage1] resolving QIDs for {len(pending)}/{total_all} titles "
          f"({total_all - len(pending)} already cached)", flush=True)

    start = time.monotonic()
    done = total_all - len(pending)
    for batch in chunked(pending, BATCH_SIZE):
        params = {
            "action": "query",
            "formatversion": "2",
            "prop": "pageprops",
            "ppprop": "wikibase_item",
            "redirects": "1",
            "titles": "|".join(batch),
        }
        result = api_get(EN_API, params)
        if result.get("ok"):
            body = result.get("body") or {}
            query = body.get("query") or {}
            norm_map = {n["from"]: n["to"] for n in query.get("normalized", [])}
            redir_map = {r["from"]: r["to"] for r in query.get("redirects", [])}
            pages_by_title = {p.get("title"): p for p in query.get("pages", [])}
            for orig in batch:
                cur = orig
                if cur in norm_map:
                    cur = norm_map[cur]
                if cur in redir_map:
                    cur = redir_map[cur]
                page = pages_by_title.get(cur)
                if page is None:
                    qid_map[orig] = {"qid": None, "resolved_title": cur, "missing": True}
                elif page.get("missing"):
                    qid_map[orig] = {"qid": None, "resolved_title": cur, "missing": True}
                else:
                    qid = (page.get("pageprops") or {}).get("wikibase_item")
                    qid_map[orig] = {"qid": qid, "resolved_title": cur, "missing": False}
        # else: transient failure for the whole batch -- leave these titles
        # out of qid_map so a re-run retries them.
        save_state("qid_map.json", qid_map)
        done += len(batch)
        progress("stage1", done, total_all, start)


# ---------------------------------------------------------------------------
# Stage 2: QID -> P18 filename
# ---------------------------------------------------------------------------

def stage2_fetch_p18(qids, p18_map):
    pending = [q for q in qids if q not in p18_map]
    total_all = len(qids)
    if not pending:
        print(f"[stage2] all {total_all} QIDs already resolved (cache)", flush=True)
        return
    print(f"[stage2] fetching P18 for {len(pending)}/{total_all} QIDs "
          f"({total_all - len(pending)} already cached)", flush=True)

    start = time.monotonic()
    done = total_all - len(pending)
    for batch in chunked(pending, BATCH_SIZE):
        params = {
            "action": "wbgetentities",
            "ids": "|".join(batch),
            "props": "claims",
        }
        result = api_get(WD_API, params)
        if result.get("ok"):
            body = result.get("body") or {}
            entities = body.get("entities") or {}
            for qid in batch:
                ent = entities.get(qid)
                if ent is None or "missing" in ent:
                    p18_map[qid] = {"file": None, "missing": True}
                    continue
                claims = ent.get("claims") or {}
                p18_claims = claims.get("P18") or []
                filename = None
                if p18_claims:
                    try:
                        filename = p18_claims[0]["mainsnak"]["datavalue"]["value"]
                    except (KeyError, IndexError, TypeError):
                        filename = None
                p18_map[qid] = {"file": filename, "missing": False}
        # else: leave pending for retry
        save_state("p18_map.json", p18_map)
        done += len(batch)
        progress("stage2", done, total_all, start)


# ---------------------------------------------------------------------------
# Stage 3: filename -> license / dimensions
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(s):
    if not s:
        return None
    text = _TAG_RE.sub(" ", s)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text).strip()
    return text or None


def _extmeta_value(extmetadata, key):
    entry = (extmetadata or {}).get(key)
    if not entry:
        return None
    return entry.get("value")


def stage3_fetch_license(filenames, license_map):
    pending = [f for f in filenames if f not in license_map]
    total_all = len(filenames)
    if not pending:
        print(f"[stage3] all {total_all} files already resolved (cache)", flush=True)
        return
    print(f"[stage3] fetching license/size for {len(pending)}/{total_all} files "
          f"({total_all - len(pending)} already cached)", flush=True)

    start = time.monotonic()
    done = total_all - len(pending)
    for batch in chunked(pending, BATCH_SIZE):
        titles = ["File:" + fn for fn in batch]
        params = {
            "action": "query",
            "formatversion": "2",
            "prop": "imageinfo",
            "iiprop": "extmetadata|size",
            "titles": "|".join(titles),
        }
        result = api_get(COMMONS_API, params)
        if result.get("ok"):
            body = result.get("body") or {}
            query = body.get("query") or {}
            by_title = {p.get("title"): p for p in query.get("pages", [])}
            for fn in batch:
                page = by_title.get("File:" + fn)
                if page is None or page.get("missing"):
                    license_map[fn] = {"missing": True}
                    continue
                ii_list = page.get("imageinfo") or []
                if not ii_list:
                    license_map[fn] = {"missing": True, "note": "no_imageinfo"}
                    continue
                ii = ii_list[0]
                width = ii.get("width")
                height = ii.get("height")
                extm = ii.get("extmetadata") or {}
                license_short = _extmeta_value(extm, "LicenseShortName")
                artist = strip_html(_extmeta_value(extm, "Artist"))
                credit_stripped = strip_html(_extmeta_value(extm, "Credit"))
                credit = credit_stripped if (credit_stripped and len(credit_stripped) <= 300) else None
                license_map[fn] = {
                    "missing": False,
                    "license": license_short,
                    "artist": artist,
                    "credit": credit,
                    "width": width,
                    "height": height,
                }
        # else: leave pending for retry
        save_state("license_map.json", license_map)
        done += len(batch)
        progress("stage3", done, total_all, start)


# ---------------------------------------------------------------------------
# License classification
# ---------------------------------------------------------------------------

_PD_RE = re.compile(r"\bpublic\s*domain\b|\bpd\b|\bcc0\b", re.I)
_CC_BAD_RE = re.compile(r"\b(nc|nd|noncommercial|non-commercial|noderivs?|no-derivs?)\b", re.I)
# Matches "CC BY", "CC BY-SA" (any version string trailing) as well as the
# older Commons/Flickr shortname style that spells it out as "Attribution"
# / "Attribution-ShareAlike" without a "CC" prefix -- same licenses, just an
# older label. NC/ND variants are excluded above before this ever runs.
_CC_BY_RE = re.compile(
    r"\bcc[\s\-]?by(?:[\s\-]?sa)?\b"
    r"|\battribution(?:[\s\-]?share\s?alike)?\b",
    re.I,
)


def classify_license(license_short_name):
    """True for public domain / CC0 / CC BY / CC BY-SA variants; else False."""
    if not license_short_name:
        return False
    s = license_short_name.strip()
    if _PD_RE.search(s):
        return True
    if _CC_BAD_RE.search(s):
        return False
    if _CC_BY_RE.search(s):
        return True
    return False


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------

def load_people():
    data = json.loads(PEOPLE_PATH.read_text(encoding="utf-8"))
    out = []
    for p in data["people"]:
        out.append({
            "name": p.get("name"),
            "wiki_title": p["wiki_title"],
            "qid": p.get("qid"),
            "category": "people",
        })
    return out


def load_objects():
    data = json.loads(OBJECTS_PATH.read_text(encoding="utf-8"))
    out = []
    for o in data["objects"]:
        out.append({
            "name": o.get("name"),
            "wiki_title": o["wiki_title"],
            "qid": None,
            "category": "objects",
        })
    return out


def load_wave3():
    data = json.loads(WAVE3_PATH.read_text(encoding="utf-8"))
    out = []
    for w in data:
        out.append({
            "name": w.get("name"),
            "wiki_title": w["wiki_title"],
            "qid": None,
            "category": "wave3",
        })
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    RAW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    people = load_people()
    objects = load_objects()
    wave3 = load_wave3()
    all_items = people + objects + wave3
    print(f"Loaded {len(people)} people, {len(objects)} objects, "
          f"{len(wave3)} wave3 = {len(all_items)} total candidates", flush=True)

    # --- Stage 1: resolve QIDs for items that don't already have one ---
    qid_map = load_state("qid_map.json")
    titles_needing_qid = dedup_preserve_order(
        it["wiki_title"] for it in all_items if it["qid"] is None)
    stage1_resolve_qids(titles_needing_qid, qid_map)

    for it in all_items:
        if it["qid"] is not None:
            it["_qid"] = it["qid"]
        else:
            entry = qid_map.get(it["wiki_title"])
            it["_qid"] = entry.get("qid") if entry else None

    n_with_qid = sum(1 for it in all_items if it["_qid"])
    print(f"[stage1] {n_with_qid}/{len(all_items)} candidates have a resolvable QID", flush=True)

    # --- Stage 2: QID -> P18 filename ---
    p18_map = load_state("p18_map.json")
    qids_needed = dedup_preserve_order(it["_qid"] for it in all_items if it["_qid"])
    stage2_fetch_p18(qids_needed, p18_map)

    # --- Stage 3: filename -> license/size ---
    license_map = load_state("license_map.json")
    filenames_needed = dedup_preserve_order(
        p18_map.get(q, {}).get("file") for q in qids_needed if p18_map.get(q, {}).get("file"))
    stage3_fetch_license(filenames_needed, license_map)

    # --- Assemble deliverable ---
    items_out = {}
    summary = {cat: {"total": 0, "with_image": 0, "license_ok": 0, "license_ok_and_big": 0}
               for cat in ("people", "objects", "wave3")}

    for it in all_items:
        wt = it["wiki_title"]
        qid = it["_qid"]
        p18_entry = p18_map.get(qid) if qid else None
        file = p18_entry.get("file") if p18_entry else None
        has_image = bool(file)

        lic_entry = license_map.get(file) if file else None
        license_name = None
        artist = None
        width = None
        height = None
        if lic_entry and not lic_entry.get("missing"):
            license_name = lic_entry.get("license")
            artist = lic_entry.get("artist")
            width = lic_entry.get("width")
            height = lic_entry.get("height")

        min_dim = min(width, height) if (width and height) else None
        small = bool(min_dim is not None and min_dim < SMALL_THRESHOLD_PX)
        license_ok = classify_license(license_name)

        items_out[wt] = {
            "qid": qid,
            "has_image": has_image,
            "file": file,
            "license": license_name,
            "license_ok": bool(license_ok),
            "artist": artist,
            "min_dimension_px": min_dim,
            "small": small,
        }

        s = summary[it["category"]]
        s["total"] += 1
        if has_image:
            s["with_image"] += 1
        if license_ok:
            s["license_ok"] += 1
        if license_ok and min_dim is not None and min_dim >= SMALL_THRESHOLD_PX:
            s["license_ok_and_big"] += 1

    output = {
        "generatedOn": date.today().isoformat(),
        "items": items_out,
        "summary": summary,
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nWrote {OUTPUT_PATH} with {len(items_out)} items", flush=True)
    print(json.dumps(summary, indent=2), flush=True)
    print(f"Total HTTP requests: {STATS.requests}, cache hits: {STATS.cache_hits}, "
          f"retries: {STATS.retries}", flush=True)


if __name__ == "__main__":
    main()
