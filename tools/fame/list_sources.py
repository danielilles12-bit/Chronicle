"""
Config for harvest_lists.run_sources(): curated Wikipedia "List of X" pages,
each vetted by hand for reasonable precision (finite, fame-selected sets --
not indiscriminate country-by-country indexes like "List of castles").
"""

SOURCES = [
    {
        "title": "List of most expensive paintings",
        "mode": "table", "tag": "most-expensive-paintings",
        "kind": "painting", "region": None, "era_hint": None,
    },
    {
        "title": "List of diamonds",
        "mode": "table", "tag": "famous-diamonds",
        "kind": "artefact", "region": None, "era_hint": None,
    },
    {
        "title": "List of Roman amphitheatres",
        "mode": "table", "tag": "roman-amphitheatres",
        "kind": "building", "region": None, "era_hint": "classical",
        "prefer_keyword": "amphitheat",
    },
    {
        "title": "List of illuminated manuscripts",
        "mode": "bullet", "tag": "illuminated-manuscripts",
        "kind": "manuscript", "region": None, "era_hint": None,
        "link_picker": "trailing_paren",
    },
    {
        "title": "List of museum ships",
        "mode": "table", "tag": "museum-ships",
        "kind": "artefact", "region": None, "era_hint": None,
    },
    {
        "title": "List of colossal sculptures in situ",
        "mode": "sectioned-bullet", "tag": "colossal-sculptures",
        "kind": "sculpture", "region": None, "era_hint": None,
    },
    {
        "title": "List of tallest statues",
        "mode": "table", "tag": "tallest-statues",
        "kind": "sculpture", "region": None, "era_hint": "modern",
    },
    {
        "title": "List of Egyptian pyramids",
        "mode": "table", "tag": "egyptian-pyramids",
        "kind": "site", "region": "Africa", "era_hint": "ancient",
        "prefer_keyword": "pyramid",
    },
    {
        "title": "List of the oldest mosques",
        "mode": "table", "tag": "oldest-mosques",
        "kind": "building", "region": None, "era_hint": None,
    },
    {
        "title": "List of largest mosques",
        "mode": "table", "tag": "largest-mosques",
        "kind": "building", "region": None, "era_hint": None,
    },
    {
        "title": "List of largest art museums",
        "mode": "table", "tag": "largest-art-museums",
        "kind": "building", "region": None, "era_hint": "modern",
    },
    {
        "title": "List of most-visited museums",
        "mode": "table", "tag": "most-visited-museums",
        "kind": "building", "region": None, "era_hint": "modern",
    },
    {
        "title": "List of obelisks in Rome",
        "mode": "table", "tag": "obelisks-rome",
        "kind": "monument", "region": "Europe", "era_hint": None,
        "prefer_keyword": "obelisk",
    },
]
