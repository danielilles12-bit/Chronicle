#!/usr/bin/env python3
"""Schedule-repetition validator for data/editions.json.

A 22 Jul 2026 launch review found 27 repeated identities/works inside a
30-day window, 10 pairs within 7 days, and adjacent-day collisions (a
Thread tile that gave away the next day's Relic answer). Nothing else in
the repo checks for this, so it will recur with every new content batch.
This is the permanent guard.

Three classes of finding, across the WHOLE manifest:

  0. unknown-id    an id the manifest references that does not exist in its
                    game's pool at all. Born 11 Aug 2026: a hand-edit during
                    the nightly review staged 'alan-turing' — the pool id is
                    'turing' — and every check passed, because js/daily.js
                    silently drops unknown ids (.filter(Boolean)) and the
                    day would simply have aired one round short. Always
                    ERROR; gates the build when the edition is still
                    reachable in the app (today or future, or an aired day
                    inside the 7-day archive window at/after the launch
                    floor).
  1. id-repeat     the same item id (who/map/what/thread) scheduled twice
                    with too short a gap: ERROR under the 28-day hard floor
                    (CLAUDE.md locked decision #5), WARN 28-41 days (under
                    the 42-day target, but legal).
  2. linked-subject two DIFFERENT ids/tiles that resolve to the same real
                    person or work (a Face Value portrait and a Lifeline
                    figure of the same person, a Relic artefact and the
                    person it belongs to, an alias/alternate spelling, a
                    Thread tile matching any of the above) colliding close
                    together: ERROR on adjacent/same-day, WARN within 7
                    days, INFO within 14 (the review's preferred cooldown).

The linking layer (see build_linker()) resolves ids and Thread tile
strings to a canonical subject key using the item `name`/`variants`
fields, js/match.js's normalize() (ported below, same as
tools/validate_reveal.py's match_normalize), and a small curated
ALIAS_LINKS/EXCLUDE_LINKS override list for the handful of cases the data
can't express on its own. Precision is favoured over recall: a shared
string is only trusted automatically when it's unambiguous (exactly one
subject in the whole corpus claims it) or backed by >=2 independent
shared name/variant strings — a single shared nickname/epithet/surname
(e.g. two Roosevelts, two Frederick IIs, "Il Duomo") is never enough on
its own. See the module docstring of build_linker() for the full account.

Run from repo root: python3 tools/validate_schedule.py
  --json              machine-readable findings on stdout
  --manifest PATH      validate an alternate manifest (e.g. a pre-repair
                       snapshot extracted with `git show REV:data/editions.json`)
  --today YYYY-MM-DD   override "today" for the aired/unaired boundary (testing)

Exit code: non-zero only when an ERROR-severity finding involves at least
one UNAIRED edition. Aired history can't be fixed, so the gate stays green
for purely historical findings — they are still printed, just don't fail
the build. This mirrors compile_editions.py verify's legacy/compiled split.
"""
import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import date, timedelta
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAMES = ("who", "map", "what", "thread")
ITEM_GAMES = ("who", "map", "what")

# ---------------------------------------------------------------------------
# normalize() parity (js/match.js) — same port as tools/validate_reveal.py's
# match_normalize: lowercase, strip accents/punctuation, drop a trailing
# "by <artist>" clause, drop articles, fold written/numeric ordinals to
# roman numerals ("Elizabeth the First"/"Elizabeth 2" -> "elizabeth ii").
# ---------------------------------------------------------------------------
ARTICLES = {"the", "a", "an"}
NUMWORDS = {
    "first": "i", "second": "ii", "third": "iii", "fourth": "iv", "fifth": "v",
    "sixth": "vi", "seventh": "vii", "eighth": "viii", "ninth": "ix", "tenth": "x",
    "eleventh": "xi", "twelfth": "xii", "thirteenth": "xiii", "fourteenth": "xiv",
    "fifteenth": "xv", "sixteenth": "xvi",
}
ROMAN_BY_NUM = ["", "i", "ii", "iii", "iv", "v", "vi", "vii", "viii",
                "ix", "x", "xi", "xii", "xiii", "xiv", "xv", "xvi"]


def _num_to_roman(tok):
    if tok in NUMWORDS:
        return NUMWORDS[tok]
    m = re.match(r"^(\d{1,2})(?:st|nd|rd|th)?$", tok)
    if m and 1 <= int(m.group(1)) <= 16:
        return ROMAN_BY_NUM[int(m.group(1))]
    return tok


def normalize(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("&", "")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return ""
    out = []
    for tok in s.split(" "):
        if tok == "by":
            break
        if tok in ARTICLES:
            continue
        out.append(_num_to_roman(tok))
    return " ".join(out)


# ---------------------------------------------------------------------------
# Curated linking overrides — verified by hand against the live pools
# (tools/validate_schedule.py has no access to a "these are the same
# person" ground truth beyond what's below). Each entry is a pair of
# (game, id) keys into reveal-who.json ("who"), figures.json ("map") or
# reveal-what.json ("what").
#
# ALIAS_LINKS: genuine same-subject pairs the automatic layer misses
# because the who/map naming conventions differ enough that they share
# only ONE variant string (below the >=2 auto-link threshold — see
# build_linker). All five were confirmed by reading both records: the
# honorific ("Pope"/"Kaiser") is present in one pool's `name`/variants and
# absent in the other's.
ALIAS_LINKS = [
    (("who", "ibn-sina"), ("map", "avicenna")),              # same person, Latinised name only overlaps on "avicenna"
    (("who", "pope-benedict-xvi"), ("map", "benedict-xvi")),  # same person, "Pope" prefix only on the who side
    (("who", "pope-john-paul-ii"), ("map", "john-paul-ii")),  # same person, ditto
    (("who", "kaiser-wilhelm-ii"), ("map", "wilhelm-ii")),    # same person, "Kaiser" prefix only on the who side
    (("who", "cecil-rhodes"), ("map", "cecil-john-rhodes")),  # same person, map side carries the middle name
]

# EXCLUDE_LINKS: pairs the automatic ">=2 shared strings" heuristic would
# otherwise wrongly merge. Currently just one real case found in the live
# data: Florence Cathedral and Milan Cathedral are both informally called
# "Il Duomo" in Italian (2 shared strings: "duomo" and "il duomo" — really
# one signal said twice) but are different buildings in different cities.
# This list is the general safety valve for the class of false link the
# task calls out by name: "Hindenburg the airship" and "Hindenburg the
# person" must never merge just because they'd share the bare surname —
# no such person entry exists in the live pools today, so there is nothing
# to exclude yet, but if one is ever added with a bare "hindenburg"
# variant, add it here (or rely on the ambiguity check in resolve_text,
# which independently refuses to use a string claimed by 2+ subjects for
# Thread-tile resolution regardless of this list).
EXCLUDE_LINKS = [
    (("what", "florence-cathedral-dome"), ("what", "milan-cathedral")),
    # RMS Queen Elizabeth 2 (ocean liner) vs Elizabeth II / Queen Elizabeth
    # II (the monarch it's named for) — without this, signal B's exact
    # name-equality check merges them, because normalize()'s digit->roman
    # folding makes the ship's own name "Queen Elizabeth 2" normalize
    # identically to "Queen Elizabeth II". A vehicle named after a person
    # is not the person — the same principle as the task's own Hindenburg
    # example, just tripped by a different signal.
    (("what", "qe2"), ("map", "elizabeth-ii")),
    (("what", "qe2"), ("who", "queen-elizabeth-ii")),
]

# A shared string owned by more than this many raw items is treated as
# hopelessly generic (never a link signal, never a registry entry) —
# purely a performance/sanity cap; nothing in the live pools comes close.
MAX_OWNERS_FOR_LINKING = 8


# ---------------------------------------------------------------------------
# Union-Find over (game, id) keys
# ---------------------------------------------------------------------------
class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


# ---------------------------------------------------------------------------
# The linking layer
# ---------------------------------------------------------------------------
def build_linker(pools_root=ROOT):
    """Resolve who/map/what item ids AND free-text Thread tile strings to a
    canonical "subject" key — the same real person or work, however it's
    spelled or which game it's in.

    Signals used, strongest first (all transitive-safe: every one asserts
    "these are literally the same real-world identity", never a looser
    "related to" relationship — an artefact and its creator, for
    instance, is deliberately NOT auto-linked here: that relation isn't
    transitive, chaining it through a union-find would eventually merge
    unrelated subjects (e.g. an artefact linking its creator would risk
    bridging that creator to whoever else the artefact depicts), and none
    of the 7 known offenders need it):

      A. the same id string used in two different pools (who/map/what) —
         unambiguous ground truth (e.g. 'mozart' is the id in both
         reveal-who.json and figures.json for the same person).
      B. two different ids whose primary `name` field normalizes to the
         exact same string (e.g. who:lincoln "Abraham Lincoln" and
         map:abraham-lincoln "Abraham Lincoln").
      C. two different ids that share >=2 distinct normalized name/variant
         strings. A single shared string is deliberately NOT enough —
         the live data has several real people who share exactly one
         bare nickname/epithet/surname with someone else entirely
         (Mahatma Gandhi / Indira Gandhi via "gandhi", FDR / Theodore
         Roosevelt via "roosevelt", Henry Ford / Gerald Ford via "ford",
         Louis / Neil Armstrong via "armstrong", John / John Quincy Adams
         via "adams", Elizabeth / Zachary Taylor via "taylor", Frederick
         Barbarossa / Hayreddin Barbarossa via "barbarossa", Harper Lee /
         Robert E. Lee via "lee", Charlemagne / Charles I of England via
         "charles i" (!), Mary I / Mary Queen of Scots via "queen mary",
         William III / William the Silent via "william of orange",
         Alexander II of Russia / Simon Bolivar via "the liberator",
         the US Constitution / USS Constitution via "constitution", and
         Elizabeth II / the RMS Queen Elizabeth 2 liner via "queen
         elizabeth ii" — a direct parallel to the task's own Hindenburg
         example (a vehicle named after/for a person is not the person).
         Requiring 2 independent shared strings clears every one of
         these while still catching e.g. Timur/Tamerlane (3 shared:
         "timur", "tamerlane", "timur the lame") and the two curated
         Van Gogh portrait entries (2 shared: "van gogh", "vincent van
         gogh") without any manual curation.
      D. ALIAS_LINKS (curated, see above) for the handful of same-subject
         pairs that share exactly one string (below C's threshold).

    EXCLUDE_LINKS is checked before applying signal C, so a pair that
    would otherwise cross the >=2 threshold can still be vetoed by hand.

    Returns (items, groups, subject_of, resolve_text, label_of):
      items       (game,id) -> {"name": raw name, "strings": {normalized}}
      groups      canonical root -> set of member (game,id) keys
      subject_of  (game, id) -> root, or None if the id isn't in the pools
      resolve_text(text) -> (root_or_None, ambiguous: bool) — normalizes
                  `text` (a Thread tile or group label) and looks it up in
                  the registry built from every group's combined strings;
                  resolves ONLY when exactly one subject claims that exact
                  string. When 2+ subjects claim it, returns (None, True)
                  — "ambiguous", never guessed at, exactly the same
                  precision-first stance as signal C/EXCLUDE_LINKS.
      label_of(root) -> human-readable label for reporting/--json
    """
    who = json.loads((pools_root / "data/reveal-who.json").read_text(encoding="utf-8"))
    what = json.loads((pools_root / "data/reveal-what.json").read_text(encoding="utf-8"))
    figs = json.loads((pools_root / "data/figures.json").read_text(encoding="utf-8"))

    items = {}
    for game, pool in (("who", who), ("what", what), ("map", figs)):
        for x in pool:
            iid = x.get("id")
            if not iid:
                continue
            strs = {normalize(x.get("name", ""))}
            for v in x.get("variants") or []:
                strs.add(normalize(v))
            strs.discard("")
            items[(game, iid)] = {"name": x.get("name", ""), "strings": strs}

    uf = UnionFind()
    for key in items:
        uf.find(key)

    # EXCLUDE_LINKS gates every automatic signal (A/B/C alike) — found by
    # testing, not just guessed at: signal B alone would otherwise merge
    # ('what','qe2') — the RMS Queen Elizabeth 2 ocean liner — with the
    # monarch, because normalize()'s digit->roman folding (built so "Henry
    # 8" answers "Henry VIII") makes the ship's own name "Queen Elizabeth
    # 2" normalize to the identical string as "Queen Elizabeth II". Same
    # trap as the task's own Hindenburg example, just on the name-equality
    # signal instead of the variant-overlap one.
    exclude_set = {frozenset(p) for p in EXCLUDE_LINKS}

    def safe_union(a, b):
        if frozenset((a, b)) not in exclude_set:
            uf.union(a, b)

    # Signal A: same id string across different pools.
    by_id = defaultdict(list)
    for (game, iid) in items:
        by_id[iid].append((game, iid))
    for iid, keys in by_id.items():
        for a, b in combinations(keys, 2):
            safe_union(a, b)

    # Signal B: exact normalized `name` equality across different ids.
    by_name = defaultdict(list)
    for key, rec in items.items():
        nm = normalize(rec["name"])
        if nm:
            by_name[nm].append(key)
    for nm, keys in by_name.items():
        for a, b in combinations(keys, 2):
            safe_union(a, b)

    # Signal C: >=2 shared normalized strings between different ids,
    # subject to EXCLUDE_LINKS.
    inv = defaultdict(set)
    for key, rec in items.items():
        for s in rec["strings"]:
            inv[s].add(key)
    pair_shared = defaultdict(set)
    for s, owners in inv.items():
        if len(owners) < 2 or len(owners) > MAX_OWNERS_FOR_LINKING:
            continue
        for a, b in combinations(sorted(owners), 2):
            if a[1] == b[1]:
                continue
            pair_shared[(a, b)].add(s)
    for (a, b), strs in pair_shared.items():
        if len(strs) >= 2:
            safe_union(a, b)

    # Signal D: curated aliases (only if both ids still exist).
    for a, b in ALIAS_LINKS:
        if a in items and b in items:
            uf.union(a, b)

    groups = defaultdict(set)
    for key in items:
        groups[uf.find(key)].add(key)

    registry = defaultdict(set)
    for root, members in groups.items():
        pool_strings = set()
        for m in members:
            pool_strings |= items[m]["strings"]
        for s in pool_strings:
            registry[s].add(root)

    def subject_of(game, iid):
        key = (game, iid)
        return uf.find(key) if key in items else None

    def resolve_text(text):
        s = normalize(text)
        if not s:
            return None, False
        roots = registry.get(s)
        if not roots:
            return None, False
        if len(roots) > 1:
            return None, True
        return next(iter(roots)), False

    def label_of(root):
        members = sorted(groups.get(root, []))
        names = sorted({items[m]["name"] for m in members if items[m].get("name")})
        if names:
            return " / ".join(names)
        return " / ".join(f"{g}:{i}" for g, i in members)

    return items, groups, subject_of, resolve_text, label_of


# ---------------------------------------------------------------------------
# Epoch — parsed from js/daily.js, never hardcoded here
# ---------------------------------------------------------------------------
def load_epoch():
    src = (ROOT / "js/daily.js").read_text(encoding="utf-8")
    m = re.search(r"EPOCH\s*=\s*new Date\((\d+),\s*(\d+),\s*(\d+)\)", src)
    if not m:
        print("validate_schedule: FATAL — could not find `EPOCH = new Date(...)` "
              "in js/daily.js", file=sys.stderr)
        sys.exit(1)
    y, mo0, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return date(y, mo0 + 1, d)  # JS Date month is 0-based


def edition_date(epoch, n):
    return epoch + timedelta(days=n)


def edition_index(epoch, d):
    return (d - epoch).days


# ---------------------------------------------------------------------------
# Rule 0 — ids that don't exist (the 'alan-turing' guard, 11 Aug 2026)
# ---------------------------------------------------------------------------
def check_unknown_ids(editions, items, connections_by_id, today_idx, launch=0):
    """Every id the manifest references must exist in its game's pool.

    who/map/what ids are checked against the pools build_linker() loaded;
    thread ids against data/connections.json. Reachability decides gating:
    an unknown id today/future or inside the 7-day archive window (>= the
    launch floor, before which the archive cannot reach) is a live break —
    the app would serve a short day. Anything older is historical
    bookkeeping, same stance as the other rules.
    """
    findings = []
    for n, ed in editions:
        d = ed.get("date", "")
        reachable = n >= launch and n >= today_idx - 6
        for game in ITEM_GAMES:
            for iid in ed.get(game) or []:
                if (game, iid) not in items:
                    findings.append({
                        "rule": "unknown-id", "severity": "ERROR",
                        "edition": n, "date": d, "game": game, "id": iid,
                        "gates": reachable,
                    })
        for bid in ed.get("thread") or []:
            if bid not in connections_by_id:
                findings.append({
                    "rule": "unknown-id", "severity": "ERROR",
                    "edition": n, "date": d, "game": "thread", "id": bid,
                    "gates": reachable,
                })
    return findings


# ---------------------------------------------------------------------------
# Rule 1 — same item id, gap too short
# ---------------------------------------------------------------------------
def check_id_repeats(editions, today_idx, launch=0):
    occ = defaultdict(list)  # id -> [(edition, date, game), ...]
    for n, ed in editions:
        d = date.fromisoformat(ed["date"])
        for game in GAMES:
            for iid in ed.get(game) or []:
                occ[iid].append((n, d, game))

    findings = []
    for iid, occs in occ.items():
        occs.sort(key=lambda t: t[0])
        for (n1, d1, g1), (n2, d2, g2) in zip(occs, occs[1:]):
            if n1 < launch <= n2:
                continue  # launch blindfold — see main()
            gap = (d2 - d1).days
            if gap < 28:
                sev = "ERROR"
            elif gap <= 41:
                sev = "WARN"
            else:
                continue
            findings.append({
                "rule": "id-repeat",
                "severity": sev,
                "gap_days": gap,
                "id": iid,
                "a": {"edition": n1, "date": d1.isoformat(), "game": g1},
                "b": {"edition": n2, "date": d2.isoformat(), "game": g2},
                "gates": sev == "ERROR" and n2 > today_idx,
            })
    return findings


# ---------------------------------------------------------------------------
# Rule 2/3 — linked subjects colliding
# ---------------------------------------------------------------------------
def check_linked_subjects(editions, subject_of, resolve_text, label_of, connections_by_id, today_idx, launch=0):
    occ = defaultdict(list)  # root -> [(edition, date, kind, raw_key, display), ...]
    ambiguous = []

    for n, ed in editions:
        d = date.fromisoformat(ed["date"])
        for game in ITEM_GAMES:
            for iid in ed.get(game) or []:
                root = subject_of(game, iid)
                if root is None:
                    continue
                occ[root].append((n, d, "item", iid, f"{game}/{iid}"))
        for bid in ed.get("thread") or []:
            board = connections_by_id.get(bid)
            if not board:
                continue
            texts = []
            for g in board.get("groups", []):
                texts.append(g.get("label", ""))
                texts.extend(g.get("items", []))
            seen_today = set()
            for t in texts:
                if not (t or "").strip():
                    continue
                root, is_ambiguous = resolve_text(t)
                if is_ambiguous:
                    ambiguous.append({
                        "edition": n, "date": d.isoformat(), "board": bid, "text": t,
                    })
                    continue
                if root is None or root in seen_today:
                    continue
                seen_today.add(root)
                occ[root].append((n, d, "tile", t, f"Thread tile '{t}' ({bid})"))

    findings = []
    for root, occs in occ.items():
        if len(occs) < 2:
            continue
        occs.sort(key=lambda t: t[0])
        for (n1, d1, k1, raw1, disp1), (n2, d2, k2, raw2, disp2) in zip(occs, occs[1:]):
            if k1 == "item" and k2 == "item" and raw1 == raw2:
                continue  # exact same id repeating — rule 1's job, not ours
            if n1 < launch <= n2:
                continue  # launch blindfold — see main()
            gap = (d2 - d1).days
            if gap <= 1:
                sev = "ERROR"
            elif gap <= 7:
                sev = "WARN"
            elif gap <= 14:
                sev = "INFO"
            else:
                continue
            findings.append({
                "rule": "linked-subject",
                "severity": sev,
                "gap_days": gap,
                "subject": label_of(root),
                "a": {"edition": n1, "date": d1.isoformat(), "detail": disp1},
                "b": {"edition": n2, "date": d2.isoformat(), "detail": disp2},
                "gates": sev == "ERROR" and n2 > today_idx,
            })
    return findings, ambiguous


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def fmt_unknown(f):
    gate = "" if f["gates"] else " (unreachable, no gate)"
    kind = "board" if f["game"] == "thread" else "item"
    pool = "connections" if f["game"] == "thread" else f["game"]
    return (f"unknown id '{f['id']}' in №{f['edition']} ({f['date']}, {f['game']}) — "
            f"no such {kind} in the {pool} pool{gate}")


def fmt_id_repeat(f):
    gate = "" if f["gates"] else " (historical, no gate)" if f["severity"] == "ERROR" else ""
    a, b = f["a"], f["b"]
    return (f"id '{f['id']}' repeats after {f['gap_days']}d: "
            f"№{a['edition']} ({a['date']}, {a['game']}) -> "
            f"№{b['edition']} ({b['date']}, {b['game']}){gate}")


def fmt_linked(f):
    gate = "" if f["gates"] else " (historical, no gate)" if f["severity"] == "ERROR" else ""
    a, b = f["a"], f["b"]
    return (f"linked subject '{f['subject']}' collides after {f['gap_days']}d: "
            f"№{a['edition']} ({a['date']}) {a['detail']} -> "
            f"№{b['edition']} ({b['date']}) {b['detail']}{gate}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=None, help="alternate data/editions.json path")
    ap.add_argument("--today", default=None, metavar="YYYY-MM-DD",
                    help="override today's date (testing)")
    ap.add_argument("--json", action="store_true", help="emit machine-readable findings")
    args = ap.parse_args()

    manifest_path = Path(args.manifest) if args.manifest else (ROOT / "data/editions.json")
    today = date.fromisoformat(args.today) if args.today else date.today()

    epoch = load_epoch()
    today_idx = edition_index(epoch, today)

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"validate_schedule: FATAL — cannot read {manifest_path}: {e}", file=sys.stderr)
        sys.exit(1)

    raw_editions = manifest.get("editions")
    if not isinstance(raw_editions, dict) or not raw_editions:
        print("validate_schedule: FATAL — manifest has no editions", file=sys.stderr)
        sys.exit(1)
    editions = sorted(((int(k), v) for k, v in raw_editions.items()), key=lambda kv: kv[0])

    try:
        connections = json.loads((ROOT / "data/connections.json").read_text(encoding="utf-8"))
    except Exception as e:
        print(f"validate_schedule: FATAL — cannot read data/connections.json: {e}", file=sys.stderr)
        sys.exit(1)
    connections_by_id = {c["id"]: c for c in connections if c.get("id")}

    items, groups, subject_of, resolve_text, label_of = build_linker()

    # Launch blindfold (owner ruling 29 Jul 2026): the app came into
    # existence on launch day. A pre-launch airing colliding with a
    # post-launch one is not a finding — virtually nobody saw the former.
    # Pre-launch-only pairs stay reported (historical bookkeeping).
    try:
        launch = json.loads((ROOT / "tools/editions.config.json")
                            .read_text(encoding="utf-8")).get("launch_edition", 0)
    except Exception:
        launch = 0

    unknown_findings = check_unknown_ids(editions, items, connections_by_id,
                                         today_idx, launch)
    id_findings = check_id_repeats(editions, today_idx, launch)
    linked_findings, ambiguous = check_linked_subjects(
        editions, subject_of, resolve_text, label_of, connections_by_id,
        today_idx, launch)

    if args.json:
        out = {
            "epoch": epoch.isoformat(),
            "today": today.isoformat(),
            "today_edition_index": today_idx,
            "edition_range": [editions[0][0], editions[-1][0]],
            "unknown_id_findings": unknown_findings,
            "id_repeat_findings": id_findings,
            "linked_subject_findings": linked_findings,
            "ambiguous_tile_matches": ambiguous,
            "summary": {
                "unknown_id_errors": len(unknown_findings),
                "id_repeat_errors": sum(1 for f in id_findings if f["severity"] == "ERROR"),
                "id_repeat_warns": sum(1 for f in id_findings if f["severity"] == "WARN"),
                "linked_errors": sum(1 for f in linked_findings if f["severity"] == "ERROR"),
                "linked_warns": sum(1 for f in linked_findings if f["severity"] == "WARN"),
                "linked_infos": sum(1 for f in linked_findings if f["severity"] == "INFO"),
                "gating_errors": sum(1 for f in unknown_findings + id_findings + linked_findings
                                     if f["severity"] == "ERROR" and f["gates"]),
            },
        }
        print(json.dumps(out, indent=1, ensure_ascii=False))
        sys.exit(1 if out["summary"]["gating_errors"] else 0)

    all_findings = unknown_findings + id_findings + linked_findings
    order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    all_findings.sort(key=lambda f: (order[f["severity"]],
                                     f["a"]["edition"] if "a" in f else f["edition"]))

    for f in all_findings:
        if f["rule"] == "unknown-id":
            line = fmt_unknown(f)
        elif f["rule"] == "id-repeat":
            line = fmt_id_repeat(f)
        else:
            line = fmt_linked(f)
        print(f"{f['severity']:<5} {line}")

    for a in ambiguous:
        print(f"INFO  ambiguous Thread tile '{a['text']}' in {a['board']} "
              f"(№{a['edition']}, {a['date']}) matches 2+ subjects — not used for linking")

    n_id_err = sum(1 for f in id_findings if f["severity"] == "ERROR")
    n_id_warn = sum(1 for f in id_findings if f["severity"] == "WARN")
    n_link_err = sum(1 for f in linked_findings if f["severity"] == "ERROR")
    n_link_warn = sum(1 for f in linked_findings if f["severity"] == "WARN")
    n_link_info = sum(1 for f in linked_findings if f["severity"] == "INFO")
    gating = [f for f in all_findings if f["severity"] == "ERROR" and f["gates"]]
    historical_err = [f for f in all_findings if f["severity"] == "ERROR" and not f["gates"]]

    print(f"validate_schedule: editions {editions[0][0]}..{editions[-1][0]} "
          f"(today = edition {today_idx}, {today.isoformat()}) — "
          f"unknown-id {len(unknown_findings)}E, "
          f"id-repeat {n_id_err}E/{n_id_warn}W, linked-subject {n_link_err}E/{n_link_warn}W/{n_link_info}I, "
          f"{len(ambiguous)} ambiguous tile match(es) — "
          f"{len(gating)} gating error(s), {len(historical_err)} historical-only error(s)")
    sys.exit(1 if gating else 0)


if __name__ == "__main__":
    main()
