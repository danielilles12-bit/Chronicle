#!/usr/bin/env python3
"""
score_fame.py -- turn raw metrics into a 0-100 fame score.

Usage:
    python3 score_fame.py <metrics.jsonl> <scores.json>

metrics.jsonl is the output of fetch_metrics.py: one JSON object per line
with at least "name", "wiki_title", "pageviews_5y", "languages", "inlinks".

Method:
    - pageviews_5y and inlinks are log-transformed first (ln(1+x)) so a
      handful of mega-famous outliers don't compress everyone else into
      the bottom of the scale.
    - Each of the three metrics (log pageviews, languages, log inlinks) is
      independently converted to a 0-100 percentile rank across the input
      set, using the "average rank" method (ties share the average
      percentile of their group; the minimum value maps to 0, the maximum
      to 100).
    - fame = 0.60 * pv_pct + 0.20 * lang_pct + 0.20 * inlink_pct, rounded
      to 2 decimal places.
    - Missing/null metric values (fetch errors, missing articles) are
      treated as 0 before the log transform -- i.e. they rank at the
      bottom, since we have no evidence of fame for them.

Output: scores.json, a JSON array sorted by fame descending, each item:
    {"name", "wiki_title", "fame", "pv_pct", "lang_pct", "inlink_pct",
     "pageviews_5y", "languages", "inlinks"}
"""

import json
import math
import sys
from pathlib import Path


def average_rank_percentiles(values):
    """
    0-100 percentile rank for each value in `values`, using the average-rank
    (mean rank) method for ties. The minimum value(s) map to 0, the maximum
    value(s) map to 100. A single-element input maps to 100.0.
    """
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [100.0]

    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        # 1-based average rank for the tie group [i, j]
        avg_rank = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1

    return [(r - 1) / (n - 1) * 100.0 for r in ranks]


def _numeric_or_zero(value):
    return value if isinstance(value, (int, float)) else 0


def load_records(metrics_path):
    records = []
    with open(metrics_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 score_fame.py <metrics.jsonl> <scores.json>", file=sys.stderr)
        sys.exit(1)

    metrics_path = sys.argv[1]
    scores_path = Path(sys.argv[2])

    records = load_records(metrics_path)
    if not records:
        scores_path.write_text("[]", encoding="utf-8")
        print(f"No records found in {metrics_path}; wrote empty {scores_path}", file=sys.stderr)
        return

    pv_log = [math.log1p(max(_numeric_or_zero(r.get("pageviews_5y")), 0)) for r in records]
    lang_vals = [_numeric_or_zero(r.get("languages")) for r in records]
    inlink_log = [math.log1p(max(_numeric_or_zero(r.get("inlinks")), 0)) for r in records]

    pv_pcts = average_rank_percentiles(pv_log)
    lang_pcts = average_rank_percentiles(lang_vals)
    inlink_pcts = average_rank_percentiles(inlink_log)

    out = []
    for i, r in enumerate(records):
        pv_pct = pv_pcts[i]
        lang_pct = lang_pcts[i]
        inlink_pct = inlink_pcts[i]
        fame = 0.60 * pv_pct + 0.20 * lang_pct + 0.20 * inlink_pct
        out.append({
            "name": r.get("name"),
            "wiki_title": r.get("wiki_title"),
            "fame": round(fame, 2),
            "pv_pct": round(pv_pct, 2),
            "lang_pct": round(lang_pct, 2),
            "inlink_pct": round(inlink_pct, 2),
            "pageviews_5y": r.get("pageviews_5y"),
            "languages": r.get("languages"),
            "inlinks": r.get("inlinks"),
        })

    out.sort(key=lambda x: x["fame"], reverse=True)
    scores_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(out)} scored records to {scores_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
