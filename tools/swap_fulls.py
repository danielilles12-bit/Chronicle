#!/usr/bin/env python3
"""Replace the two full-format puzzles in data/puzzles.json with clued 15x15s.

Numbering is derived with the same algorithm the validator uses, so position
and numbering errors are impossible by construction. Fails loudly if any
answer lacks a clue or any clue lacks an answer.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from validate_puzzles import numbering  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
FULLS = json.load(open(os.path.join(ROOT, "tools", "out", "fulls.json")))

PUZZLES = [
    {
        "source": FULLS[0]["grid"],
        "id": "full-1", "title": "Across the Ages",
        "clues": {
            ("across", "ANG"): "Lee who directed 1995's Austen adaptation \"Sense and Sensibility\"",
            ("across", "CADDY"): "Tea ___, the Victorian pantry box",
            ("across", "OCEAN"): "\"In 1492, Columbus sailed the ___ blue\"",
            ("across", "PAR"): "Standard on the old Scottish links",
            ("across", "HIREE"): "Fresh recruit to the firm",
            ("across", "PRICE"): "The Louisiana Purchase's was $15 million",
            ("across", "ADO"): "\"Much ___ About Nothing\"",
            ("across", "IDEAL"): "Perfect form, in Plato's philosophy",
            ("across", "TIGHT"): "Like a blockade that actually works",
            ("across", "RIVER"): "The Rubicon, for one",
            ("across", "ALPS"): "Range Hannibal crossed with elephants in 218 BC",
            ("across", "SHE"): "\"___ who must be obeyed\" (H. Rider Haggard, 1887)",
            ("across", "TREXARM"): "Tiny-limbed pose named for a Cretaceous predator",
            ("across", "UNIT"): "Legion or cohort, e.g.",
            ("across", "RICO"): "Anti-racketeering law of 1970, briefly",
            ("across", "CLUSTER"): "Close-packed bunch, as of Aegean islands",
            ("across", "ACT"): "The Stamp ___ of 1765",
            ("across", "UNSEEN"): "Like most of an iceberg, as the Titanic learned",
            ("across", "RAE"): "John ___, Arctic explorer who learned the Franklin expedition's fate",
            ("across", "AWL"): "Piercing tool in cobblers' kits since antiquity",
            ("across", "SAUDI"): "___ Arabia, kingdom unified in 1932",
            ("across", "ATF"): "Federal agcy. with roots in Prohibition enforcement",
            ("across", "HEE"): "\"___ Haw,\" cornpone variety show that debuted in 1969",
            ("across", "ESTEEM"): "High regard",
            ("across", "MCS"): "Mic wielders, briefly",
            ("across", "HDVIDEO"): "What home movies became in the late 2000s, briefly",
            ("across", "AMOK"): "Run ___ (rampage, from a Malay word)",
            ("across", "ENYA"): "\"Orinoco Flow\" singer of 1988",
            ("across", "INERTIA"): "Subject of Newton's first law",
            ("across", "ELF"): "Sprite of Norse folklore",
            ("across", "UPON"): "\"Once ___ a time...\"",
            ("across", "TEAMS"): "Constantinople's chariot-racing Blues and Greens, e.g.",
            ("across", "BRAUN"): "Wernher von ___, rocket pioneer",
            ("across", "OCTET"): "Schubert wrote a famous one in 1824",
            ("across", "PAC"): "Election-funding org. — the first was formed in 1944",
            ("across", "RINSE"): "Wash lightly",
            ("across", "SHELL"): "What a WWI howitzer lobbed",
            ("across", "EGO"): "Freudian coinage",
            ("across", "ANDES"): "Mountains of the Inca",
            ("across", "HORSE"): "Troy's wooden undoing",
            ("across", "SET"): "What the sun famously never did on the British Empire",
            ("down", "APART"): "\"Things fall ___\" (Yeats line that titled Achebe's novel)",
            ("down", "AHH"): "Sigh of a legionary easing into the baths",
            ("down", "BRA"): "Garment patented by Mary Phelps Jacob in 1914",
            ("down", "NADIR"): "Rock bottom — a term astronomy took from Arabic",
            ("down", "AWED"): "Like the first viewers of Tutankhamun's gold in 1922",
            ("down", "ERIN"): "Ireland, in old poetry",
            ("down", "GROVERCLEVELAND"): "President both before and after Benjamin Harrison",
            ("down", "EXIT"): "Way out",
            ("down", "INFUSE"): "Steep, as tea",
            ("down", "CHIRAC"): "French president from 1995 to 2007",
            ("down", "EDY"): "Joseph ___, ice-cream maker who teamed with Dreyer in 1928",
            ("down", "NES"): "8-bit Nintendo console of 1985, briefly",
            ("down", "AID"): "What the Marshall Plan delivered",
            ("down", "ROUSSEAU"): "\"The Social Contract\" philosopher, 1762",
            ("down", "DREAM"): "King's 1963 speech had a famous one",
            ("down", "NATO"): "Alliance founded in 1949",
            ("down", "POSH"): "Fancy — folk etymology claims it's from \"port out, starboard home\"",
            ("down", "DEAL"): "FDR's New ___",
            ("down", "SUE"): "What Dred Scott did for his freedom",
            ("down", "OCHO"): "Eight, to the Armada's admirals",
            ("down", "YELP"): "Stepped-on hound's cry",
            ("down", "CEDE"): "Hand over, as territory by treaty",
            ("down", "INTER"): "Lay in a barrow, say",
            ("down", "SULEIMAN"): "Ottoman sultan his subjects called \"the Lawgiver\"",
            ("down", "ELS"): "Chicago's elevated trains, running since 1892",
            ("down", "OPT"): "Choose (to)",
            ("down", "NUN"): "Sister of a medieval abbey",
            ("down", "METTLE"): "What Thermopylae tested",
            ("down", "CRISIS"): "The Cuban Missile ___",
            ("down", "MORE"): "Thomas who wrote \"Utopia\" — and lost his head",
            ("down", "EIGHTTRACKTAPES"): "Car-audio relics that faded away by the early 1980s",
            ("down", "ACHE"): "Long (for), as an exile does for home",
            ("down", "EATS"): "Diner fare, slangily",
            ("down", "IMAGE"): "Caesar's, on a denarius",
            ("down", "NET"): "Weapon of the gladiator called a retiarius",
            ("down", "REF"): "Bout official, briefly",
            ("down", "ASCOT"): "Royal racecourse since 1711",
        },
    },
    {
        "source": FULLS[2]["grid"],
        "id": "full-2", "title": "Old Europe",
        "clues": {
            ("across", "COSMIC"): "Like the spheres of Aristotle's heavens",
            ("across", "COB"): "What maize kernels ride on — a New World gift to the Old",
            ("across", "RAGS"): "___-to-riches story, like Carnegie's",
            ("across", "ALTERS"): "Amends, as a constitution",
            ("across", "EMU"): "Flightless Aussie that \"won\" a 1932 war against the army",
            ("across", "IDLE"): "Like a mothballed fleet",
            ("across", "VERSAILLES"): "Palace where the 1919 treaty was signed",
            ("across", "GRAN"): "Family elder, fondly",
            ("across", "EAT"): "Break bread",
            ("across", "ALL"): "\"___ Quiet on the Western Front\"",
            ("across", "FIONA"): "Name behind an 1890s literary hoax — and a 2001 cartoon princess",
            ("across", "ABE"): "Lincoln, familiarly",
            ("across", "ELSIE"): "Borden's cow mascot since the 1930s",
            ("across", "EDICT"): "The ___ of Nantes, Henry IV's 1598 toleration decree",
            ("across", "NIT"): "Pedant's find",
            ("across", "LENTIL"): "Esau sold his birthright for a stew of them",
            ("across", "TEE"): "Starting point at St Andrews",
            ("across", "NOEL"): "Christmas, in old carols",
            ("across", "ARI"): "___ Fleischer, early-2000s White House spokesman",
            ("across", "NIB"): "Point a scribe dipped in ink",
            ("across", "REAM"): "500 sheets — once 480, by old convention",
            ("across", "EXAM"): "Imperial China's civil-service ordeal",
            ("across", "NBA"): "League founded in 1946, for short",
            ("across", "MTV"): "Channel that debuted on Aug. 1, 1981",
            ("across", "GAME"): "The Great ___, the Anglo-Russian contest over Central Asia",
            ("across", "AMA"): "Grp. that fought Medicare's creation in the 1960s",
            ("across", "ASPIRE"): "Aim high, as Icarus did unwisely",
            ("across", "VAL"): "Kilmer who played Doc Holliday",
            ("across", "FIRST"): "Like Washington, among presidents",
            ("across", "ALARM"): "What Paul Revere's ride raised",
            ("across", "EEK"): "Mouse-spotter's squeak",
            ("across", "FLAKE"): "Bit of the snow that doomed Napoleon's retreat",
            ("across", "TIC"): "Nervous habit",
            ("across", "OAR"): "Trireme propeller",
            ("across", "ELBA"): "Napoleon's first island exile",
            ("across", "METTERNICH"): "Austrian who steered the Congress of Vienna",
            ("across", "CELT"): "Ancient Gaul or Briton",
            ("across", "ANI"): "Ruined Armenian capital called the city of 1,001 churches",
            ("across", "RANCHO"): "Estate on a Spanish-colonial land grant",
            ("across", "TREE"): "Genealogist's chart",
            ("across", "WTA"): "Org. Billie Jean King co-founded in 1973",
            ("across", "ANAKIN"): "Skywalker whose screen saga began in 1977",
            ("down", "CAV"): "Air ___: Vietnam-era helicopter units, briefly",
            ("down", "ANN"): "Cape ___, Mass., named for James I's queen",
            ("down", "AFFECT"): "Have an influence on",
            ("down", "OLE"): "Cry at a corrida",
            ("down", "BIO"): "Plutarch specialty, for short",
            ("down", "MILLER"): "Arthur who set \"The Crucible\" in 1692 Salem",
            ("down", "STREETER"): "Ruth ___, first director of the WWII Women Marines",
            ("down", "ARABLE"): "Like land worth conquering",
            ("down", "MESA"): "Flat-topped landform of the old Southwest",
            ("down", "LEN"): "Deighton of Cold War spy fiction",
            ("down", "SKATE"): "Glide like a Dutch canal-traveler of old",
            ("down", "IRATE"): "Wrathful as Achilles",
            ("down", "ABATE"): "Die down, as a siege bombardment",
            ("down", "CSI"): "Forensics franchise that debuted in 2000, briefly",
            ("down", "LLAMAS"): "Pack animals of the Inca",
            ("down", "MAW"): "Gaping mouth",
            ("down", "LASER"): "1960 invention now used in eye surgery",
            ("down", "PATENT"): "Edison filed more than a thousand of them",
            ("down", "CELLINI"): "Benvenuto with the scandalous autobiography",
            ("down", "MILITIA"): "The Minutemen, for example",
            ("down", "OMELET"): "Dish whose name France gave the world",
            ("down", "TRACT"): "Pamphlet of the sort Reformation presses churned out",
            ("down", "BUS"): "What Rosa Parks boarded into history",
            ("down", "INEVER"): "\"Well, ___!\" (scandalized Victorian's cry)",
            ("down", "ERA"): "Equal Rights Amendment, briefly",
            ("down", "FELIX"): "The Cat of silent-film cartoons",
            ("down", "MORAN"): "Bugs ___, Capone's North Side rival",
            ("down", "RIGID"): "Like Spartan discipline",
            ("down", "BAG"): "Diplomatic pouch, e.g.",
            ("down", "ANNA"): "Governess Leonowens of 1860s Siam",
            ("down", "ADROIT"): "Deft — a word from the French",
            ("down", "MAVERICK"): "Unbranded calf, named for Texas rancher Samuel",
            ("down", "GLANCE"): "Quick look",
            ("down", "MAE"): "West who scandalized the 1920s stage",
            ("down", "CHI"): "X of the Greek alphabet",
            ("down", "SENATE"): "Rome's deliberative body",
            ("down", "ELK"): "Beast on a Stone Age cave wall",
            ("down", "HON"): "Sweetie, in a 1940s diner",
        },
    },
]


def build(p):
    grid = p["source"]
    size = len(grid)
    derived = numbering(grid, size)
    clues = {"across": [], "down": []}
    used = set()
    for (dirn, num), (r, c, answer) in sorted(derived.items(), key=lambda kv: kv[0][1]):
        key = (dirn, answer)
        if key not in p["clues"]:
            sys.exit("MISSING CLUE for %s %s (%s)" % (p["id"], dirn, answer))
        used.add(key)
        clues[dirn].append({"num": num, "row": r, "col": c,
                            "answer": answer, "clue": p["clues"][key]})
    extra = set(p["clues"]) - used
    if extra:
        sys.exit("CLUES WITH NO SLOT in %s: %s" % (p["id"], sorted(extra)))
    return {"id": p["id"], "format": "full", "size": size, "title": p["title"],
            "grid": grid, "clues": clues}


def main():
    path = os.path.join(ROOT, "data", "puzzles.json")
    puzzles = json.load(open(path))
    puzzles = [z for z in puzzles if z["format"] != "full"]
    for p in PUZZLES:
        puzzles.append(build(p))
    with open(path, "w") as f:
        json.dump(puzzles, f, indent=1)
    print("puzzles.json now has:", [(z["id"], z["size"]) for z in puzzles])


if __name__ == "__main__":
    main()
