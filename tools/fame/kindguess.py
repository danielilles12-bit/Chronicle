"""
Best-effort 'kind' classifier for harvested titles/names.
kind in: building, monument, site, painting, sculpture, artefact, manuscript
"""
import re

_PAINTING_HINTS = [
    "madonna", "portrait of", "the last supper", "mona lisa",
]
_SCULPTURE_KEYWORDS = [
    "statue", "sculpture", "bust of", "colossus", "sphinx", "moai",
]
_MANUSCRIPT_KEYWORDS = [
    "codex", "manuscript", "gospel", "book of", "scroll", "papyrus",
    "bible", "folio", "chronicle", "psalter", "diary of",
]
_ARTEFACT_KEYWORDS = [
    "mask of", "bust of", "throne", "crown", "sword", "dagger", "armor",
    "armour", "diamond", "jewel", "vase", "urn", "amphora", "coin",
    "shroud", "stone of", "tablet", "figurine", "shield of", "shipwreck",
    "wreck of", " ship", "warship", "chalice", "reliquary", "astrolabe",
    "clock", "globe", "helmet", "sarcophagus of", "mummy of",
]
_MONUMENT_KEYWORDS = [
    "monument", "memorial", "obelisk", "arch of", "triumphal arch",
    "column of", "cenotaph", "menhir", "megalith", "geoglyph", "gate of",
    "wall of", "great wall", "cross of", "fountain",
]
_BUILDING_KEYWORDS = [
    "cathedral", "basilica", "church", "chapel", "abbey", "mosque",
    "minaret", "synagogue", "temple", "pagoda", "shrine", "monastery",
    "palace", "castle", "fort", "fortress", "citadel", "tower", "bridge",
    "museum", "library", "opera house", "theatre", "theater", "stadium",
    "lighthouse", "mausoleum", "tomb of", "villa", "manor", "house",
    "hall", "station", "aqueduct", "dam", "gate", "wat ", "stupa",
    "colosseum", "coliseum", "amphitheatre", "amphitheater", "arena",
]
_SITE_KEYWORDS = [
    "ruins of", "necropolis", "pyramid", "acropolis", "archaeological",
    "excavation", "old town", "historic centre", "historic center",
    "old city", "walled city", "rock-cut", "cave of", "caves of",
    "burial mound", "kurgan", "settlement", "city of", "ancient city",
]


def guess_kind(name, default="site"):
    n = (name or "").lower()

    def any_in(keys):
        return any(k in n for k in keys)

    if any_in(_MANUSCRIPT_KEYWORDS):
        return "manuscript"
    if any_in(_PAINTING_HINTS):
        return "painting"
    if any_in(_SCULPTURE_KEYWORDS):
        return "sculpture"
    if any_in(_ARTEFACT_KEYWORDS):
        return "artefact"
    if any_in(_MONUMENT_KEYWORDS):
        return "monument"
    if any_in(_BUILDING_KEYWORDS):
        return "building"
    if any_in(_SITE_KEYWORDS):
        return "site"
    return default
