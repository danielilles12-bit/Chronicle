"""
Final precision pass over universe_objects.json.

Some single-source lists (Roman amphitheatres, oldest/largest mosques)
frequently redirect to a plain modern city article when the structure
itself has no dedicated Wikipedia page -- those rows are dropped when
the item has no other corroborating source and no on-topic keyword in
its title. Also removes stray non-object noise (events, dynasties/
empires-as-topics, measurement units) that slipped through upstream
extraction, wherever it appears.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, "universe_objects.json")

TAG_KEYWORD_REQUIREMENTS = {
    "roman-amphitheatres": re.compile(
        r"amphitheat|arena|coliseum|colosseum", re.IGNORECASE),
    "oldest-mosques": re.compile(
        r"mosq|masj|jami|shrine|imam|minaret|dargah|tekke|zawiya",
        re.IGNORECASE),
    "largest-mosques": re.compile(
        r"mosq|masj|jami|shrine|imam|minaret|dargah|tekke|zawiya",
        re.IGNORECASE),
    "famous-diamonds": re.compile(
        r"diamond|carbonado|noor|koh-?i-?noor", re.IGNORECASE),
}

# Titles that are topics/events/measurement units, not photographable
# objects -- caught wherever they occur, regardless of source tag.
EVENT_OR_TOPIC_RE = re.compile(
    r"^(Battle of |Siege of |War of |Invasion of |Fall of |Sack of |"
    r"Campaign of )"
    r"|\b(tragedy|massacre|uprising|rebellion|incident|disaster|"
    r"colonisation|colonization)\b"
    r"|^(Carat \(mass\))$"
    r"| Dynasty of | Dynasty$"
    r"|^(Roman Egypt|British Raj)$",
    re.IGNORECASE,
)

EXPLICIT_TITLE_DROPS = {
    "Piazza del Quirinale", "Roman Egypt", "Thirteenth Dynasty of Egypt",
    "Jagersfontein Mine", "Carat (mass)", "British Raj",
    "British colonisation of South Australia",
    "Empire of Japan", "Kingdom of Great Britain", "Kingdom of Italy",
    "Republic of China (1912-1949)", "Republic of China (1912–1949)",
    "Russian Empire", "Sasanian Empire",
    "Maya civilization", "Chachapoya culture",
}


def main():
    with open(OUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    objects = data["objects"]

    kept = []
    dropped_keyword = 0
    dropped_event = 0
    dropped_explicit = 0

    for o in objects:
        title = o["wiki_title"]
        tags = o.get("from_lists", [])

        if title in EXPLICIT_TITLE_DROPS:
            dropped_explicit += 1
            continue

        if EVENT_OR_TOPIC_RE.search(title):
            dropped_event += 1
            continue

        if len(tags) == 1 and tags[0] in TAG_KEYWORD_REQUIREMENTS:
            pattern = TAG_KEYWORD_REQUIREMENTS[tags[0]]
            if not pattern.search(title):
                dropped_keyword += 1
                continue

        kept.append(o)

    print(f"Dropped (single-source, off-topic redirect): "
          f"{dropped_keyword}", file=sys.stderr)
    print(f"Dropped (event/topic/unit pattern): {dropped_event}",
          file=sys.stderr)
    print(f"Dropped (explicit title blocklist): {dropped_explicit}",
          file=sys.stderr)
    print(f"Kept: {len(kept)} / {len(objects)}", file=sys.stderr)

    data["objects"] = kept
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"Rewrote {OUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
