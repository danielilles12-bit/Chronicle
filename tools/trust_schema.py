#!/usr/bin/env python3
"""Shared constants + validation for the P3 "trust surface" fields.

Every field here is OPTIONAL on every record (figures.json, reveal-who.json,
reveal-what.json, connections.json) — see DEAD_FAMOUS_AUDITED_PLAN.md P3.1.
Nothing in this module requires a field to be present; it only checks shape
when a field IS present, so existing unsourced records keep validating clean.

Fact-sourcing fields (all record types):
  fact_sources[]   direct URLs backing the record's factual claims
  confidence       'established' | 'disputed' | 'traditional' | 'legend'
  reviewed_by      who last checked this record
  reviewed_on      ISO date (YYYY-MM-DD) of that review
  tags             {region, era, topic, sensitivity} — each a string or
                    list of strings; editorial classification, not enforced
                    against a controlled vocabulary

Image-credit fields (reveal-who.json / reveal-what.json only):
  image_author         creator name (Commons 'Artist')
  image_source_url     direct Commons file-page URL
  image_license        licence short name (mirrors the legacy `license`
                        field under the new namespace)
  image_license_url    URL to the licence's legal text
  image_retrieved      ISO date the credit was last verified against Commons
  image_modifications  free text, e.g. "cropped" — left unset unless known;
                        the reveal UI omits that clause when absent rather
                        than guess at processing history this module can't
                        verify
"""
import re
from datetime import date

CONFIDENCE_VALUES = {"established", "disputed", "traditional", "legend"}
TAG_KEYS = {"region", "era", "topic", "sensitivity"}
IMAGE_FIELDS = (
    "image_author", "image_source_url", "image_license",
    "image_license_url", "image_retrieved", "image_modifications",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def is_url(s):
    return isinstance(s, str) and bool(_URL_RE.match(s.strip()))


def is_iso_date(s):
    if not isinstance(s, str) or not _DATE_RE.match(s):
        return False
    try:
        date.fromisoformat(s)
        return True
    except ValueError:
        return False


def is_sourced(rec):
    """True once a record carries both a non-empty fact_sources list and a
    valid confidence tag — the joint bar P3.6's require_sources gate checks
    (P3.6: 'every item entering a signed-off manifest must be sourced and
    confidence-tagged first')."""
    fs = rec.get("fact_sources")
    return (
        isinstance(fs, list) and len(fs) > 0 and all(is_url(u) for u in fs)
        and rec.get("confidence") in CONFIDENCE_VALUES
    )


def validate_trust_fields(rec, ctx, err, warn, has_images):
    """Validate the optional trust-surface fields on `rec` if present.

    ctx: label prefix for messages, e.g. "reveal-who.json napoleon".
    err/warn: callables taking a message string (match the validator scripts'
    own err()/warn() collectors).
    has_images: whether this record type carries the image_* fields
    (reveal-who/reveal-what only — figures.json and connections.json have no
    per-record image, so an image_* field there is flagged, not silently
    accepted).
    """
    if "fact_sources" in rec:
        fs = rec["fact_sources"]
        if not isinstance(fs, list) or not fs:
            err(f"{ctx}: fact_sources must be a non-empty list when present")
        else:
            for u in fs:
                if not is_url(u):
                    err(f"{ctx}: fact_sources entry not a URL: {u!r}")

    if "confidence" in rec and rec["confidence"] not in CONFIDENCE_VALUES:
        err(f"{ctx}: bad confidence {rec['confidence']!r} "
            f"(want one of {sorted(CONFIDENCE_VALUES)})")

    if "reviewed_by" in rec and not str(rec["reviewed_by"] or "").strip():
        err(f"{ctx}: reviewed_by is present but empty")

    if "reviewed_on" in rec and not is_iso_date(rec["reviewed_on"]):
        err(f"{ctx}: reviewed_on not an ISO date (YYYY-MM-DD): {rec['reviewed_on']!r}")

    if "tags" in rec:
        tags = rec["tags"]
        if not isinstance(tags, dict):
            err(f"{ctx}: tags must be an object")
        else:
            for k, v in tags.items():
                if k not in TAG_KEYS:
                    warn(f"{ctx}: unrecognised tags key {k!r} "
                         f"(expected one of {sorted(TAG_KEYS)})")
                ok = (isinstance(v, str) and v.strip()) or (
                    isinstance(v, list) and v
                    and all(isinstance(x, str) and x.strip() for x in v)
                )
                if not ok:
                    err(f"{ctx}: tags.{k} must be a non-empty string or "
                        f"list of non-empty strings: {v!r}")

    if has_images:
        if "image_author" in rec and not str(rec["image_author"] or "").strip():
            err(f"{ctx}: image_author is present but empty")
        if "image_source_url" in rec and not is_url(rec["image_source_url"]):
            err(f"{ctx}: image_source_url not a URL: {rec['image_source_url']!r}")
        if "image_license" in rec and not str(rec["image_license"] or "").strip():
            err(f"{ctx}: image_license is present but empty")
        if "image_license_url" in rec and not is_url(rec["image_license_url"]):
            err(f"{ctx}: image_license_url not a URL: {rec['image_license_url']!r}")
        if "image_retrieved" in rec and not is_iso_date(rec["image_retrieved"]):
            err(f"{ctx}: image_retrieved not an ISO date: {rec['image_retrieved']!r}")
        if "image_modifications" in rec and not isinstance(rec["image_modifications"], str):
            err(f"{ctx}: image_modifications must be a string")
    else:
        for f in IMAGE_FIELDS:
            if f in rec:
                warn(f"{ctx}: {f} present but this record type has no image")
