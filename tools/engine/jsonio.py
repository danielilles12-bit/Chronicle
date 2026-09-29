#!/usr/bin/env python3
"""Save a repo JSON file in its own committed format.

The data files do not share one indent (reveal-*.json, connections.json,
editions.json and mcq_overrides.json use 1; figures.json uses 2), and
re-dumping with the wrong one buries a two-line change in a 20k-line diff.
save() reads the file's current indent and keeps it, with ensure_ascii off
and a trailing newline.

    from jsonio import load, save     # sys.path.insert(0, "tools/engine")
    d = load("data/connections.json"); ...; save("data/connections.json", d)
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _path(p):
    p = Path(p)
    return p if p.is_absolute() else ROOT / p


def load(p):
    return json.loads(_path(p).read_text())


def indent_of(p):
    p = _path(p)
    if not p.exists():
        return 1
    for line in p.read_text().splitlines()[1:6]:
        m = re.match(r"^( +)\S", line)
        if m:
            return len(m.group(1))
    return 1


def save(p, data):
    p = _path(p)
    p.write_text(json.dumps(data, indent=indent_of(p), ensure_ascii=False) + "\n")
