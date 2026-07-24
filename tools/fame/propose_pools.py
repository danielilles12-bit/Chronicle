#!/usr/bin/env python3
"""
propose_pools.py -- drafts the keep/add/retire content-pool proposal for
Dead Famous (who/map/what) that the owner reviews by hand.

Python 3.9 stdlib only. Deterministic: same inputs always produce the same
pool_proposal.json byte-for-byte (no wall clock, no randomness, no
unsorted filesystem-order dependence). Read-only against data/, js/ and
every existing tools/fame/*.json input -- writes only
tools/fame/pool_proposal.json.

Inputs (read-only): fame_scores.json, gap_report.json, tags.json,
image_availability.json, current_inventory.json, and the read-only Wikidata
claims caches under cache/image_probe/{state,raw}/ and
cache/wikidata_tags/claims/ (P31 "instance of" data, used to build the
Relic playability filter -- see build_playability_filter() docstring).

Run: python3 propose_pools.py
"""
import glob
import hashlib
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "cache")
IMAGE_PROBE_RAW_DIR = os.path.join(CACHE_DIR, "image_probe", "raw")
IMAGE_PROBE_STATE_DIR = os.path.join(CACHE_DIR, "image_probe", "state")
WIKIDATA_TAGS_CLAIMS_DIR = os.path.join(CACHE_DIR, "wikidata_tags", "claims")

GENERATED_ON = "2026-07-23"

OBJECT_CLASSES = ("structure", "artwork", "artefact")
ERA_BUCKETS = ["ancient", "medieval", "early-modern", "nineteenth", "twentieth", "contemporary"]

TARGETS = {"who": 400, "map": 450, "what": 350}

CELEBRITY_FAMILIES = {"performer", "athlete"}
CELEBRITY_CAP_FRACTION = 0.15          # of ADDITIONS, per rule 3
REGION_CAP_FRACTION = 0.45             # of the resulting pool, per spec
RECENT_ENTERTAINMENT_FLOOR_YEAR = 2016
RECENT_ENTERTAINMENT_ALLOWLIST = {"Michael Jackson", "Amy Winehouse"}


def _hash(key):
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Stats helpers (copied verbatim from build_scores.py so the re-percentile
# step uses the exact same maths as the original fame-scoring pass).
# ---------------------------------------------------------------------------

def percentile(sorted_vals, pct):
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    if n == 1:
        return float(sorted_vals[0])
    k = (pct / 100.0) * (n - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def average_rank_percentiles(values):
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
        avg_rank = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return [(r - 1) / (n - 1) * 100.0 for r in ranks]


def _num_or_zero(v):
    return v if isinstance(v, (int, float)) else 0


# ===========================================================================
# PLAYABILITY FILTER for Relic ("what") candidates.
#
# A Relic answer must be a discrete, photographable THING. fame_scores.json
# picks up whole cities, countries, US states and historical polities as
# "structure"/"artefact" class objects (their Wikipedia articles are cross-
# referenced by the same "notable places/things" source lists that also
# yield legitimate buildings/artefacts) -- e.g. "Paris", "Nazi Germany",
# "Pennsylvania", "Vienna", "West Germany", "Budapest" all score in the high
# 90s and would otherwise crowd out real Relic answers. This filter reads
# each candidate's Wikidata P31 ("instance of") chain from the already-
# cached wbgetentities claims responses (probe_images.py / build_tags.py
# both populate this cache; this script only reads it) and excludes:
#   - settlements & administrative/political geography: city, town,
#     village, municipality/commune, country, sovereign state, historical
#     country, kingdom/principality, U.S. state, province, region,
#     district, "historic centre"-style urban quarters, continents, etc.
#   - purely natural features: mountains, rivers, lakes, islands,
#     national parks/nature reserves, valleys, coastlines, etc.
#
# CARVEOUT: ancient/ruined cities that are now a bounded, single-visit
# archaeological landmark (Pompeii, Stonehenge, Petra, Troy, Machu Picchu,
# Angkor, Carthage, Meroe...) are NOT excluded even though their P31 often
# also includes "ancient city" / "city-state" -- they carry a P31 tag from
# CARVEOUT_LABELS (archaeological site, ruins, pyramid, Roman-structure
# subtypes, megalith/henge/tell/necropolis synonyms, "ancient city" itself,
# ...) which never appears on a still-living administrative city in this
# dataset (verified: Paris/Vienna/Budapest/Samarkand/Timbuktu carry none of
# these tags). This is the one deliberate judgement call in this filter --
# see the final report for the worked examples that justified it.
#
# Fallback order per candidate:
#   1. title -> QID (cache/image_probe/state/qid_map.json), QID -> P31
#      (merged cache/image_probe/raw/*.json + cache/wikidata_tags/claims/).
#   2. SUPPLEMENTARY_TITLE_P31 -- a small hand-verified table (see below)
#      for the ~100 object-class titles this run's caches don't cover at
#      all (never probed because they weren't in universe_objects.json).
#      Built by looking up each title's real QID/P31 once by hand against
#      live Wikidata during this session, then frozen here so the script
#      stays fully offline and reproducible.
#   3. NAME_PATTERN_HEURISTICS against the bare title string, for any
#      future title this cache genuinely has nothing on.
#   4. Conservative default: exclude, flagged "p31_unknown".
# ===========================================================================

CARVEOUT_LABELS = {
    "archaeological site", "ancient city", "ancient roman structure",
    "roman city", "roman archaeological site", "ancient egyptian archaeological site",
    "ancient egyptian necropolis", "ancient greek archaeological site",
    "archaeological site in greece", "carthaginian archaeological site",
    "prehistoric archaeological site", "neolithic settlement", "bronze age settlement",
    "stone age site", "paleolithic site", "settlement site", "submerged settlement",
    "former settlement", "abandoned village", "acropolis", "necropolis", "hillfort",
    "gord", "nuraghe", "ziggurat", "cromlech", "henge", "megalith", "stone circle",
    "dolmen", "long barrow", "grave cairn", "stone row", "ruins", "ancient monument",
    "tell", "prehistoric necropolis", "group of archaeological sites",
    "archaeological find", "archaeological artefact", "archaeological artifact museum",
    "archaeological park", "wonder of the ancient world", "egyptian pyramids",
    "smooth-sided pyramid", "pyramid", "nubian pyramids", "roman amphitheatre",
    "roman theatre", "roman aqueduct", "roman limes", "roman villa", "roman temple",
    "roman bridge", "roman colony", "ancient greek temple", "greek colony",
    "proto-city", "organized archaeological site", "irish passage tomb",
    "cave with prehistoric art",
}

# Labels that superficially match a geo/natural keyword pattern below but are
# demonstrably NOT geo/natural -- verified by hand against the specific
# object(s) each one tags in this dataset (Ishtar Gate, Brandenburg Gate,
# Roman walls of Lugo, Buckingham Palace, Bavarian National Museum,
# Predjama Castle, Palm Jumeirah, Ajanta Caves, Suomenlinna, Temple Mount,
# Royal Palace of Caserta all got wrongly caught before these were added).
NOT_GEO_LABEL_OVERRIDE = {
    "city gate", "city walls", "country house", "state museum",
    "pogost",             # a churchyard/parish complex (Kizhi Pogost), not a settlement
    "cadastre", "land register",  # the physical document (e.g. Domesday Book), not a place
}
NOT_NATURAL_LABEL_OVERRIDE = {
    "mountain park", "river monitor", "artificial cave", "artificial island",
    "fortress island", "sacred mountain", "cave castle",
}

NATURAL_LABEL_PATTERNS = [
    r"\bmountain\b", r"\bmountain range\b", r"\bmountain chain\b", r"\bhill\b",
    r"\bisland\b", r"\bpeninsula\b", r"\barchipelago\b", r"\batoll\b",
    r"\breef\b", r"\bcave\b", r"\bvalley\b", r"\bcanyon\b", r"\bplain\b",
    r"\bplateau\b", r"\bhighland\b", r"\bwaterfall\b", r"\blake\b", r"\briver\b",
    r"\bwadi\b", r"\boasis\b", r"\bforest\b", r"\brainforest\b",
    r"\bnational park\b", r"\bnature reserve\b", r"\bprotected area\b",
    r"\bbiosphere reserve\b", r"\bnatural (monument|heritage|region|geographic entity)\b",
    r"\bgeopark\b", r"\bmarine protected area\b", r"natura 2000", r"\bcay\b",
    r"\bspit\b", r"\bescarpment\b", r"\bgraben\b", r"\bvolcan", r"\bsea cave\b",
    r"\bkarst\b", r"\bcoast\b", r"\bgroup of lakes\b", r"\bgeoheritage\b",
    r"\bnature area\b", r"\bmeromictic lake\b", r"\bendorheic lake\b",
    r"\bsteppe lake\b", r"\briver island\b", r"\bwildlife", r"\bfaunal reserve\b",
    r"protected landscape", r"\btropical forest\b", r"\bnational scenic area\b",
    r"\bhot spring\b",
]

GEO_LABEL_PATTERNS = [
    r"\bcity\b", r"\bcity-state\b", r"\btown\b", r"\bvillage\b",
    r"\bhuman settlement\b", r"\burban area\b", r"\burban district\b",
    r"\burban ensemble\b", r"\burban landscape\b", r"\burban project\b",
    r"\bold town\b", r"\bmegacity\b", r"\bglobal city\b", r"\bmetropolis\b",
    r"\bmunicipality", r"\bcommune\b", r"\bcommunes\b", r"\blocality\b",
    r"\bpopulated place\b", r"\bneighbou?rhood\b", r"\bquarter\b", r"\bmedina\b",
    r"\bdistrict\b", r"\bborder city\b", r"\bport city\b", r"\bspa town\b",
    r"\bmill town\b", r"\bmodel village\b", r"\bcounty\b", r"\bcounty-level city\b",
    r"\bcomponent city\b", r"\bhanseatic city\b", r"\bfree imperial city\b",
    r"\bmedieval city\b", r"\bpolis\b", r"\bcompact city\b", r"\bcarfree city\b",
    r"\bcar-free place\b", r"\bcycling city\b", r"\bşəhər\b", r"\bmunicipal part\b",
    r"^country$", r"\bsovereign state\b", r"\bhistorical country\b", r"\bkingdom\b",
    r"\bprincipality\b", r"\bvassal state\b", r"\bcolonial power\b", r"\bdictatorship\b",
    r"^state$", r"\bu\.s\. state\b", r"\bfederated state\b", r"\bfederal state\b",
    r"\bautonomous community\b", r"\bprovince\b", r"^region$", r"\bnatural region\b",
    r"\bhistorical region\b", r"\bmajor regional center\b",
    r"\badministrative (territorial entity|centre|district|division|subdivision)",
    r"\blocal administrative unit\b", r"\bsubdistrict\b", r"\bunparished area\b",
    r"\bcadastral area\b", r"\bcadastral populated place\b", r"\bdisputed territory\b", r"\bnational capital\b",
    r"\bcapital of region\b", r"\bfederal capital\b", r"\bstate capital\b",
    r"\bformer national capital\b", r"\bplanned national capital\b",
    r"\bcommercial capital city\b", r"\bcultural capital\b", r"\bfashion capital\b",
    r"\bfinancial center\b", r"\bdistrict capital\b", r"\bpersonal union\b",
    r"\bcontinent\b", r"\bunincorporated community\b", r"\bmining community\b",
    r"\bwarehouse district\b", r"\bzone of\b", r"\bdepartment of\b",
    r"\bstate in the holy roman empire\b", r"\bcity-kingdom\b",
    r"\bitalian city-state\b", r"\bcity or town\b", r"\bformer capital\b",
    r"\bcouncil area\b", r"\blieutenancy area\b", r"\bscottish district\b",
]


def _label_matches(label_lower, patterns):
    return any(re.search(pat, label_lower) for pat in patterns)


def classify_p31_labels(labels):
    """labels: iterable of lowercased P31 label strings for one entity.
    Returns 'carveout' | 'exclude' | 'keep'."""
    labels = list(labels)
    for lab in labels:
        if lab in CARVEOUT_LABELS:
            return "carveout"
    for lab in labels:
        if lab in NOT_GEO_LABEL_OVERRIDE or lab in NOT_NATURAL_LABEL_OVERRIDE:
            continue
        if _label_matches(lab, NATURAL_LABEL_PATTERNS) or _label_matches(lab, GEO_LABEL_PATTERNS):
            return "exclude"
    return "keep"


# P31 QID -> lowercased English label, for every QID actually seen on any
# object-class QID in this dataset's Wikidata claims cache (harvested once
# via live wbgetentities lookups during this session's research pass, then
# frozen here -- the running script never calls the network).
# Harvested once via live wbgetentities lookups against every P31 value
# actually seen on an object-class QID in this dataset's Wikidata claims
# cache, then frozen here so the running script makes zero network calls.
P31_LABELS = json.loads('''{"Q1000809":"buddharupa","Q1007870":"art gallery","Q101401":"bell","Q101659":"dolmen","Q1021645":"office building","Q1021711":"seaside resort","Q102202066":"samian ware discovery site","Q10300916":"cultural heritage of china","Q1030403":"navigable aqueduct","Q10333504":"historical museum of abomey","Q1035294":"henge","Q10371097":"rough diamond","Q10416961":"working life museum","Q1044204":"gusuku","Q1051067":"pre-dreadnought battleship","Q1051606":"daibutsu","Q1052919":"sea cave","Q10565932":"reijō","Q10594991":"nature area","Q105999":"cargo ship","Q106078286":"component city","Q1060829":"concert hall","Q106259":"polder","Q1062780":"forum","Q10631691":"catholic pilgrimage church","Q106355253":"gospel episode","Q1064905":"concentric castle","Q106491339":"neolithic settlement","Q1066984":"financial center","Q1068623":"transmitter mast","Q1068842":"footbridge","Q106957643":"church slavonic manuscript","Q1070990":"county-level city","Q10742":"autonomous community of spain","Q107425":"landscape","Q10748583":"buddhist temple in vietnam","Q1075310":"sailboat","Q107637871":"transboundary site","Q1076486":"sports venue","Q108060568":"national park","Q108060954":"national park","Q1081138":"historic site","Q108178728":"national capital","Q108325":"chapel","Q10832530":"ironworks","Q10855061":"archaeological find","Q1087471":"relic associated with jesus","Q1088552":"catholic church building","Q108860927":"contemporary art museum","Q108935461":"czech research institution","Q10948212":"confucian royal ancestral shrine","Q109607":"ruins","Q110055303":"rocket model","Q110376455":"government body of australia","Q110390579":"city of united kingdom","Q1107656":"garden","Q11166728":"television tower","Q112132467":"group of archaeological sites","Q112132522":"historical civil building museum","Q112132527":"historical park museum","Q112132534":"military museum building","Q112132542":"palazzo museum","Q112132548":"archaeological artifact museum","Q1121471":"paddle steamer","Q11229656":"tank landing ship","Q11269813":"cave with prehistoric art","Q11271835":"state capital","Q11283094":"agro-industry","Q1128397":"convent","Q1128637":"national symbol","Q1128906":"medina quarter","Q1129474":"cultural landscape","Q11303":"skyscraper","Q1130322":"land reclamation","Q1131329":"grotto","Q113164444":"flyer","Q11331347":"calvary","Q1134686":"frazione","Q11396960":"production company","Q11408014":"exploration ships of antarctica","Q11411019":"kofungun","Q11418818":"commercial capital city","Q11438310":"taisha","Q11446":"ship","Q114496982":"political city","Q11451876":"munakata shrine","Q11452094":"government-operated model factory","Q11458051":"jisha","Q11482300":"hirajiro","Q11482498":"hirayamajiro","Q11486287":"former buddhist temple","Q1149405":"rock shelter","Q11514315":"historical period","Q115154402":"independent museum","Q11571545":"isolated peak","Q11588709":"shintaisan","Q11606300":"last station","Q11608028":"military training ship","Q11613006":"music manuscript","Q1162817":"geographical small region of hungary","Q1165822":"meromictic lake","Q11691318":"kulturdenkmal","Q1169332":"landing craft tank","Q117025897":"colonia augusta","Q11707":"restaurant","Q1172284":"data set","Q117384800":"spacecraft model","Q11741382":"holy trinity column","Q1174791":"escarpment","Q11784935":"eastern orthodox monastery","Q11801536":"winged altarpiece","Q1180262":"residenz","Q1187811":"college town","Q118896406":"twin towers","Q118984909":"unique aircraft model","Q1190275":"fireboat","Q1193438":"bullring","Q1193753":"stone row","Q1195705":"rocca","Q119814":"regalia","Q1200701":"design museum","Q1200957":"tourist destination","Q12031379":"capital of region","Q12042110":"steel bridge","Q120560":"minor basilica","Q12057999":"fortification system","Q120804029":"tumuli group","Q120964921":"organized archaeological site","Q1210334":"railway bridge","Q12104174":"ethnographic museum","Q121076356":"istituto museale ad autonomia speciale","Q1211146":"rock art","Q121117":"supercomputer","Q121289722":"boat class","Q12137573":"paleolithic site","Q1221156":"federated state of germany","Q12223988":"sphinx","Q1223230":"roman bridge","Q12277":"arch","Q12280":"bridge","Q12284":"canal","Q12292478":"estate","Q122949469":"group of manuscripts","Q1236923":"cathedral library","Q123705":"neighborhood","Q12377751":"building or structure under construction","Q1243306":"multi-level bridge","Q1244922":"embankment dam","Q12479773":"first-level administrative country subdivision in indonesia","Q124830213":"museum of a public entity","Q124830411":"museum of the italian ministry of culture","Q12493":"dome","Q124936":"major basilica","Q1249682":"editio princeps","Q1250323":"arched bridge","Q12516":"pyramid","Q1251750":"distillery","Q12518":"tower","Q125316256":"itsukushima shrine","Q125366925":"village in egypt","Q1254933":"astronomical observatory","Q12570":"suspension bridge","Q12573007":"stone sculpture","Q125857545":"carthaginian archaeological site","Q125866553":"ancient egyptian archaeological site","Q125866682":"ancient egyptian necropolis","Q125866985":"prehistoric necropolis","Q1266076":"biblical manuscript","Q127038589":"free-standing tower","Q12774":"french formal garden","Q12781":"giardino all'italiana","Q12783":"english garden","Q1278452":"polyptych","Q12813115":"urban area in sweden","Q12859788":"steamship","Q129268952":"former national capital","Q13016741":"khmer temple","Q13018311":"buddhist site","Q130313562":"first class bullring","Q130326199":"preserved watercraft","Q1306755":"administrative centre","Q1307276":"single-family detached home","Q13136":"reference work","Q131668":"acropolis","Q1316973":"national park","Q1317634":"cauldron","Q1317848":"county of northern ireland","Q1317983":"ship's tender","Q131986827":"residence of the british royal family","Q13217644":"municipality of portugal","Q13218676":"roman aqueduct","Q13218690":"town in hungary","Q1322323":"itinerary","Q1322402":"nonbuilding structure","Q132296770":"roman catholic monastery","Q1324355":"geopark","Q132775089":"renaissance bridge","Q132775244":"ottoman bridge","Q132775289":"gothic revival bridge","Q1329623":"cultural center","Q133067":"mosaic","Q1330974":"active volcano","Q133442":"city-state","Q133444874":"roman ruins","Q133747929":"expiatory temple","Q13406463":"wikimedia list article","Q134194":"fresco painting","Q1343246":"english country house","Q134390":"province of the netherlands","Q134445478":"cultural capital","Q134456340":"cultural heritage of sleman regency","Q134626":"district capital","Q13466456":"house of millions of years","Q134917286":"shikinaisha","Q135009132":"shrines receiving tsukinami-sai and niiname-sai offerings","Q135160342":"kokuhei-sha","Q13539802":"place with town rights and privileges","Q135419779":"shikinai supershrine","Q1361551":"lifeboat","Q13626398":"urban okrug in russia","Q136351774":"ancient roman imperial palace","Q1365316":"shroud","Q136706915":"funeral complex","Q1367500":"marine protected area","Q1368086":"active seti","Q136868":"imamzadeh","Q13691":"artificial island","Q1371288":"vassal state","Q137823":"monitor","Q138030791":"men only space","Q138800422":"clock bell","Q1392581":"cycling city","Q139591219":"epigraphic monument","Q139595919":"reef island","Q139930833":"fundamental law","Q1406161":"artistic theme","Q14083":"dollar","Q1420024":"fishing vessel","Q1422929":"primate city","Q14276458":"deck arch bridge","Q1429218":"cantilever bridge","Q14292916":"municipality of san marino","Q1430687":"aircraft cruiser","Q14350":"radio station","Q1435771":"gopuram","Q143912":"triumphal arch","Q1440300":"observation tower","Q1440476":"lattice tower","Q1454820":"congregational mosque","Q1456099":"step pyramid","Q14562306":"bas-relief","Q1464916":"declaration of independence","Q146924":"roman limes","Q1470705":"fertility deity","Q1473950":"stepwell","Q14752696":"ancient roman structure","Q1480017":"striking clock","Q148837":"polis","Q149621":"district","Q1496857":"prayer book","Q1497364":"building complex","Q1497375":"architectural ensemble","Q1497649":"memory institution","Q14978":"icebreaker","Q1498174":"prison island","Q1499623":"destroyer escort","Q15056993":"aircraft family","Q15056995":"aircraft model","Q15060255":"council area","Q15069452":"natura 2000 site","Q150784":"canyon","Q15092344":"urban area in norway","Q1509716":"collegiate church","Q1510380":"grove","Q15105893":"town in croatia","Q15120977":"grave cairn","Q15135589":"pilgrimage site","Q15142894":"weapon model","Q1517746":"war trophy","Q152285":"urinal","Q15239622":"disputed territory","Q15243209":"historic district","Q15273785":"belgian municipality with the title of city","Q15276":"bulk carrier","Q15284":"municipality","Q15303838":"municipality seat","Q153562":"opera house","Q153813":"extermination camp","Q1547289":"lutherstadt","Q15487029":"patriarchal basilica","Q1549591":"big city","Q1558054":"art colony","Q15584664":"city under municipality jurisdiction in latvia","Q1566035":"korean buddhist temple","Q15661340":"ancient city","Q1569871":"industrial heritage site","Q1570005":"clay tablet","Q1570262":"unfinished building","Q157031":"foundation","Q15709879":"artwork series","Q15727816":"painting series","Q15773317":"television character","Q1581130":"full-rigged ship","Q158218":"truss bridge","Q15835":"japanese garden","Q15836337":"national historical park","Q15840617":"planned national capital","Q158438":"arch bridge","Q158454":"biosphere reserve","Q158555":"cable-stayed bridge","Q15888":"hospital ship","Q15894910":"cultural heritage monument in taipei","Q15911738":"hydroelectric power station","Q1595289":"sacred mountain","Q159719":"power station","Q15978299":"municipality with town privileges in the czech republic","Q160091":"plain","Q160742":"abbey","Q16124843":"municipality of libya","Q16127605":"populated place in syria","Q161705":"frigate","Q1617500":"hieron","Q16191831":"pink diamond","Q1620908":"historical region","Q162602":"river island","Q162827":"atlas","Q162875":"mausoleum","Q1630695":"motor torpedo boat","Q1631162":"botel","Q163359":"local administrative unit in the nuts system","Q163687":"basilica","Q163740":"nonprofit organization","Q1640824":"inscription","Q164099":"hoard","Q164240":"megalith","Q1643843":"cave castle","Q16521":"taxon","Q1652352":"long barrow","Q16560":"palace","Q166118":"archives","Q1662089":"industry museum","Q16629185":"phonograph record","Q16708006":"fictional ship","Q167346":"botanical garden","Q16735822":"history museum","Q16748868":"city walls","Q16823155":"schloss","Q16831714":"government building","Q16884952":"country house","Q16887380":"group","Q16905550":"cycle of frescoes","Q169358":"stratovolcano","Q16966":"domus","Q16970":"church building","Q17000320":"theatre museum","Q170013":"corvette","Q170153":"ziggurat","Q170173":"yacht","Q170483":"sailing ship","Q1708422":"settlement site","Q170980":"obelisk","Q170984":"crown","Q17105874":"cultural history museum","Q171441":"enclave","Q17205":"aircraft carrier","Q1722560":"sepulcral culture","Q17334112":"historical park of thailand","Q173387":"grave","Q17343829":"unincorporated community","Q173603":"helmet","Q17377208":"railway undertaking","Q17413599":"diamond","Q1742059":"lake area","Q1743100":"church town of sweden","Q17431399":"national museum","Q174736":"destroyer","Q174782":"square","Q174844":"megacity","Q17489659":"group of works","Q1752434":"general cargo ship","Q1753652":"sailing yacht","Q1754581":"evangeliary","Q175582":"egyptian pyramids","Q1758856":"communes of algeria and mali","Q1759852":"sculpture garden","Q1763828":"multi-purpose hall","Q177380":"hot spring","Q177597":"naval vessel","Q1779653":"colossal statue","Q178149":"bodhisattva","Q178193":"steamboat","Q1784293":"cordon","Q1785071":"fort","Q178706":"institution","Q178743":"stele","Q179049":"nature reserve","Q179700":"statue","Q18009587":"act of the parliament of england","Q1802963":"mansion","Q180370":"hospital","Q180516":"room","Q180684":"conflict","Q180987":"stupa","Q18142":"tower block","Q181916":"herbarium","Q18210787":"zarih","Q18233199":"state museum","Q18247357":"group of structures or buildings","Q1825472":"covered bridge","Q182683":"biennale","Q184358":"reef","Q1845":"bible","Q184870":"boeing b-29 superfortress","Q1852859":"cadastral populated place in the netherlands","Q18551781":"subdistrict","Q18573970":"group of paintings","Q18577275":"urban project","Q18608436":"quarter of florence","Q18615527":"tram bridge","Q18618819":"national park of australia","Q18618841":"national park of senegal","Q186347":"caravanserai","Q1863818":"maritime museum","Q186685":"marae","Q18674739":"event venue","Q1872284":"municipality of guatemala","Q18758641":"watercraft class","Q187971":"wadi","Q18810488":"category:hohenstaufen castles in southern italy","Q188800":"personal union","Q188913":"plantation","Q188924":"galley","Q189233":"throne","Q189445":"bicameral legislature","Q190157":"radio transmitter","Q191072":"cadastre","Q191093":"province of south africa","Q191413":"zeppelin","Q191826":"tug","Q191851":"vase","Q192110":"self-portrait","Q1921708":"meridian arc","Q1922704":"sun temple","Q192287":"administrative divisions of russia","Q192611":"electoral unit","Q192810":"graben","Q19292278":"seaward defence boat","Q1930585":"victory column","Q1931855":"monolithic church","Q19323827":"mahavihara","Q1935728":"stone circle","Q194029":"roman road","Q19413015":"kitesurf spot","Q19479037":"sculpture series","Q19573550":"painted ceiling","Q1959314":"protected area of russia","Q1967454":"national memorial of the united states","Q19683138":"ramsar site","Q1969178":"nature reserve in israel","Q1969226":"national park of russia","Q197":"airplane","Q1970365":"natural history museum","Q19757":"roman theatre","Q19765902":"archabbey","Q19860854":"destroyed building or structure","Q199403":"tropical forest","Q19953632":"former administrative territorial entity","Q200141":"necropolis","Q200250":"metropolis","Q2006279":"provincial park of canada","Q20097897":"sea fort","Q20105287":"counties of the balearic islands","Q20105726":"three-masted barque","Q20181813":"colonial power","Q20202352":"locality of mexico","Q202435":"lieutenancy area of scotland","Q202527":"minesweeper","Q202570":"ferris wheel","Q2026188":"panoramic painting","Q20268453":"faunal reserve","Q2031836":"eastern orthodox church building","Q203443":"tombstone","Q2037332":"cladding","Q2039348":"municipality of the netherlands","Q204577":"schooner","Q20526152":"national parkin hungary","Q2055789":"irish passage tomb","Q2055880":"passenger vessel","Q205985":"goddess","Q20616831":"submerged settlement","Q20650761":"tender locomotive","Q2065736":"cultural property","Q2069086":"steamdriven pumping station","Q2069494":"steel mill","Q20724701":"city or town in armenia","Q207452":"ship of the line","Q2074737":"municipality of spain","Q207694":"art museum","Q208382":"apollo lunar module","Q208500":"principality","Q208511":"global city","Q2085381":"publishing house","Q20857065":"united states federal agency","Q20871353":"cadastral area in the czech republic","Q2087181":"historic house museum","Q20897549":"art institution","Q209465":"campus","Q209680":"sutra","Q21013138":"geoheritage","Q210223":"sloop","Q210272":"cultural heritage","Q210723":"chalice","Q21112633":"edition of a translation","Q2112349":"district-level town of vietnam","Q2114972":"presidential palace","Q211586":"mechanical calculator","Q2117448":"penannular brooch","Q211969":"viking ship","Q213924":"codex","Q2140699":"wine-producing region","Q21457810":"scottish district","Q21505397":"motor yacht","Q216057":"bark","Q217101":"spit","Q21745157":"destroyed artwork","Q21752084":"roman archaeological site","Q2190251":"arts center","Q2191999":"pogost","Q219760":"bazaar","Q219875":"zone of ethiopia","Q22022298":"rock relief","Q2202509":"roman city","Q220505":"film festival","Q220635":"carrack","Q220659":"archaeological artefact","Q221096":"public–private partnership","Q2240381":"fashion capital","Q225467":"compact city","Q225672":"breviary","Q2264924":"port city","Q22669139":"fresco","Q22674925":"former settlement","Q22698":"park","Q2270442":"horseshoe waterfall","Q22746":"urban park","Q2276925":"municipality of galicia","Q22808404":"station located on surface","Q22923920":"territorial collectivity of france with special status","Q22927616":"commune of france with specific status","Q2293362":"group of sculptures","Q23039057":"bus model","Q2304194":"coastal defense ship","Q23058156":"museum complex","Q2319498":"architectural landmark","Q2332212":"hanging garden","Q23397":"lake","Q23413":"castle","Q23442":"island","Q23790":"natural monument","Q23828039":"village/town/city in lebanon","Q2385804":"educational institution","Q2398990":"technology museum","Q2401485":"expedition","Q240854":"hall","Q2434238":"heritage","Q24354":"theatre building","Q24398318":"religious building","Q24455797":"norse cultural artifact","Q2447856":"traditional ship","Q2453629":"drinking vessel","Q2457903":"choirbook","Q2461104":"turret ship","Q24699794":"museum building","Q2472587":"people","Q248726":"venus figurine","Q2490191":"river valley","Q2506352":"screw frigate","Q251749":"pueblo","Q2525994":"villa urbana","Q253030":"major regional center","Q25484644":"architectural style of an area","Q25530138":"yuan","Q2555896":"municipality of colombia","Q2561694":"city-kingdom of cyprus","Q25653":"ferry","Q257391":"federal capital","Q258913":"kontor","Q2590631":"municipality of hungary","Q25964111":"group of settlements","Q2601071":"royal yacht","Q2607934":"guided missile destroyer","Q2613100":"jain temple","Q261543":"federal state of austria","Q2624046":"mountain chain","Q26263487":"america's cup challengers","Q262882":"statutory city of austria","Q263274":"kremlin","Q2640207":"bilingual dictionary","Q2668072":"collection","Q267596":"ancient greek temple","Q26789694":"plague column","Q2679157":"commune of ivory coast","Q26830017":"state in the holy roman empire","Q26883973":"lost sculpture","Q26945165":"architectural museum","Q26987258":"grand place","Q27096220":"natural geographic entity","Q2713379":"papal basilica","Q2716259":"metropolitan municipality in turkey","Q273081":"clipper","Q2736554":"candi","Q2742167":"religious community","Q27554677":"former capital","Q2755753":"area of london","Q27608973":"natural monument of russia","Q27627826":"separation barrier","Q27686":"hotel","Q2772772":"military museum","Q277759":"book series","Q28152398":"vector supercomputer","Q2828309":"protected area of france","Q28449765":"blue diamond","Q28737012":"museum of culture","Q28777651":"group of protected areas","Q28843552":"factory complex","Q28890616":"group of casts","Q28913685":"woodblock print","Q28966302":"embroidery","Q29048715":"archaeological site in greece","Q29168168":"statue of jesus","Q29168169":"colossal statue of jesus","Q2935978":"irrigation canal","Q2936105":"summit level canal","Q29430681":"triad","Q29431432":"dyad","Q29553":"sanctuary","Q29556224":"city in cyprus","Q2973801":"defense line","Q2977":"cathedral","Q2983893":"quarter","Q298742":"crown jewels","Q2989398":"commune of algeria","Q2989468":"communes d'arrondissement of senegal","Q2989649":"commune of senegal","Q29968665":"fortress island","Q29969011":"urban landscape","Q29969141":"industrial landscape","Q30124446":"legislative building","Q3024240":"historical country","Q30304302":"national park system unit","Q30620203":"abandoned entity","Q30634609":"heritage designation","Q30680562":"red diamond","Q3112873":"three-masted schooner","Q312083":"mappa mundi","Q3131754":"national park of guatemala","Q3139104":"cultural icon","Q3152824":"cultural institution","Q317":"dictatorship","Q317557":"parish church","Q3184121":"municipality of brazil","Q31855":"research institute","Q3196771":"art museum","Q321053":"cenotaph","Q3231690":"car model","Q324233":"torpedo boat","Q3249005":"provincial city of vietnam","Q3257518":"lonja","Q3257686":"locality","Q326561":"fishing trawler","Q327333":"government agency","Q32815":"mosque","Q3284499":"capitol building","Q328468":"nazi concentration camp","Q32880":"architectural style","Q329683":"industrial zone","Q3305213":"painting","Q3317612":"historic grouping","Q331795":"patrol vessel","Q3327862":"urban commune of morocco","Q3329412":"archaeological museum","Q3330834":"egyptological museum","Q333109":"überrest","Q3331189":"version, edition or translation","Q3343298":"non-departmental public body","Q334383":"abbey church","Q33452970":"historic heritage of brazil","Q33506":"museum","Q3362987":"four funnel liner","Q3363945":"archaeological park","Q3364296":"exhibition park","Q3378136":"ancient lighthouse","Q337912":"pilgrims' way","Q337986":"gurdwara","Q33837":"archipelago","Q3393392":"highest point","Q3395377":"ancient monument","Q3397526":"stone bridge","Q3397551":"built-on bridge","Q34038":"waterfall","Q3413443":"four-masted barque","Q34274":"gospel","Q34442":"road","Q3469910":"performing arts center","Q34763":"peninsula","Q3476533":"monumental sculpture","Q3477348":"urban area","Q348":"time capsule","Q34918903":"national park of the united states","Q3497366":"whaling station","Q350895":"abandoned village","Q35112127":"historic building","Q35509":"cave","Q35657":"u.s. state","Q356693":"adhesion railway","Q357679":"arch-gravity dam","Q358":"heritage site","Q358078":"road network","Q35872":"boat","Q35989030":"passport to your national parks cancellation location","Q3624078":"sovereign state","Q3637297":"beatus manuscript","Q3658341":"literary character","Q366301":"research expedition","Q3695082":"sign","Q372363":"geotope","Q3778211":"legal person","Q37947493":"arkansas state park","Q38048707":"historical cultural heritage site","Q38048753":"natural cultural heritage site","Q38048771":"indigenous cultural heritage site","Q3816838":"royal crown","Q381885":"tomb","Q383092":"art academy","Q3844310":"national gallery of armenia","Q384515":"treatise","Q386426":"natural heritage","Q3867560":"italian national museum","Q38723":"higher education institution","Q38911":"region of the czech republic","Q391414":"architectural element","Q3918":"university","Q393259":"national park of indonesia","Q3950":"villa","Q3957":"town","Q3958441":"economic sector","Q39604065":"monad","Q39614":"cemetery","Q39715":"lighthouse","Q3973051":"silk mill","Q39804":"cruise ship","Q39816":"valley","Q39947311":"warehouse district","Q4012861":"mill town","Q402092":"motor ship","Q4022":"river","Q405155":"trade route","Q40555":"death mask","Q41067667":"municipality of tunisia","Q4115680":"italian city-state","Q41176":"building","Q41253":"movie theater","Q4138156":"hydraulic system","Q41397":"genocide","Q4156067":"palace complex","Q4167410":"wikimedia disambiguation page","Q417175":"kingdom","Q42195":"petroglyph","Q42314054":"ammunition model","Q42412840":"abandoned mine","Q42523":"atoll","Q42661374":"horse hill figure","Q4271324":"mythical character","Q427287":"wat","Q42744322":"urban municipality in germany","Q42948":"wall","Q429571":"brilliant","Q429950":"carbonado","Q4306036":"museum-reserve","Q43113623":"part of unesco world heritage site","Q4313794":"populated place in georgia","Q43229":"organization","Q4354421":"coastal motor boat","Q4363262":"smooth-sided pyramid","Q43742":"oasis","Q4421":"forest","Q4443227":"stone age site","Q44539":"temple","Q44613":"monastery","Q44740228":"wall hanging","Q44782":"port","Q448190":"cage cup","Q4501454":"christian relic","Q4502142":"visual artwork","Q451752":"denominação de origem controlada","Q45222314":"landscape heritage zone","Q45400320":"open-access publisher","Q45791":"geoglyph","Q458063":"ancient lake","Q4586781":"royal peculiar","Q4588528":"sacred place","Q45990":"musalla","Q46169":"national park","Q464980":"exhibition","Q465299":"archaeological culture","Q465960":"jesuit missions among the guaraní","Q4671277":"academic institution","Q46831":"mountain range","Q473932":"roll-on/roll-off ship","Q473972":"protected area","Q474":"aqueduct","Q47461344":"written work","Q474748":"amphibious assault ship","Q47508609":"administrative subdivision of french polynesia","Q481289":"official residence","Q4828724":"aviation museum","Q4830453":"business","Q483110":"stadium","Q483453":"fountain","Q48356":"minaret","Q484170":"commune of france","Q48498":"illuminated manuscript","Q486245":"national treasures of south korea","Q486972":"human settlement","Q48982108":"limestone sculpture","Q492807":"good news","Q493522":"municipality of belgium","Q4946461":"spa town","Q49848":"document","Q4989906":"monument","Q5":"human","Q5003624":"memorial","Q503481":"cay","Q50399":"province of mongolia","Q506412":"transporter bridge","Q5098":"province of indonesia","Q511686":"nubian pyramids","Q514480":"inari shrine","Q515":"city","Q5153359":"municipality of the czech republic","Q5156823":"compound","Q518261":"cultural area","Q5191724":"steeple","Q51929311":"largest city","Q52103661":"former island","Q521458":"railway infrastructure manager","Q52177058":"civic building","Q5258439":"royal barge","Q5275":"astronomical clock","Q5281800":"discovered text","Q5283":"diamond","Q5283521":"district of laos","Q53060":"gate","Q532":"village","Q53536964":"royal palace","Q537127":"road bridge","Q5393308":"buddhist temple","Q54050":"hill","Q54074585":"tibetan buddhist monastery","Q54114":"boulevard","Q543654":"rathaus","Q544008":"strict nature reserve","Q544823":"nuclear-powered icebreaker","Q54831":"amphitheatre","Q548611":"district of the czech republic","Q54935504":"city of switzerland","Q55485":"dead-end railway station","Q55594435":"dictionary of the german language","Q55620443":"dictionary of the latin language","Q558330":"municipality of cuba","Q559026":"ship class","Q5592057":"through arch bridge","Q55990535":"computer model","Q56055312":"sepulchral monument","Q56061":"administrative territorial entity","Q56235666":"grand mosque","Q56242045":"anglican church building","Q56242215":"catholic cathedral","Q56242225":"eastern orthodox cathedral","Q56242235":"lutheran cathedral","Q56242250":"anglican or episcopal cathedral","Q56320584":"prehistoric archaeological site","Q56321256":"agricultural sector","Q56557504":"city of iran","Q56557664":"şəhər","Q56580425":"city of oblast significance","Q56750657":"hermitage church","Q5687161":"branch of agriculture","Q569500":"community health center","Q570116":"tourist attraction","Q572916":"found object","Q572995":"natural region of france","Q57318":"free imperial city","Q575727":"museum ship","Q575759":"war memorial","Q5762366":"river monitor","Q5770868":"medieval city","Q57821":"fortification","Q57831":"fortress","Q581830":"carfree city","Q58339518":"town in india","Q58621988":"temple complex","Q586744":"sacramentary","Q588140":"science museum","Q5926864":"group of lakes","Q59341087":"town in nova scotia","Q593485":"liberty ship","Q5975567":"high-speed transport","Q59773381":"automobile model series","Q598227":"militaria","Q5999924":"illinois state park","Q6006":"neon sign","Q60172605":"æstel","Q6024226":"metropolitan municipality","Q6043159":"casino hotel","Q6056746":"campaign","Q605981":"buffalo jump","Q608152":"hospice","Q61020892":"psalter and hours","Q61089180":"municipal part of the czech republic","Q614316":"private museum","Q61457040":"ramsar site in australia","Q6165948":"herbal","Q61760621":"group of monuments","Q618123":"geographical feature","Q61856863":"urban district in schleswig-holstein","Q61961344":"group of physical objects","Q62326":"region of denmark","Q6256":"country","Q626066":"banquet","Q62832":"observatory","Q63099748":"hotel building","Q631305":"rock formation","Q63209072":"city in colombia","Q636041":"solar barque","Q640078":"minelayer","Q641226":"arena","Q64578911":"former hospital","Q64732764":"cave church","Q64953083":"car-free place","Q65007262":"petroglyphic site","Q65064889":"bronze age settlement","Q65096167":"commonwealth war graves commission maintained memorial","Q653139":"volcanic plug","Q653208":"monolith","Q653848":"world map","Q6546372":"lighthouse tender","Q655593":"emporium","Q6581615":"thermae","Q659103":"commune of romania","Q660668":"training vessel","Q66108498":"wonder of the ancient world","Q6617100":"district of yemen","Q6636777":"road-rail bridge","Q665247":"hypogeum","Q66626342":"urban ensemble","Q66661745":"group of artificial physical objects","Q667276":"art exhibition","Q667509":"municipality of austria","Q672598":"land register","Q67376938":"historic county of the united kingdom","Q676050":"old town","Q677678":"fortified town","Q6784672":"municipality of slovakia","Q678552":"imperial cathedral","Q6838244":"chinese aaaaa-rated tourist attraction","Q684740":"real property","Q6882870":"designated spa town","Q688292":"nuraghe","Q6888356":"model village","Q690851":"gospel book","Q6936383":"municipality of lebanon","Q693842":"votive church","Q69391739":"greek colony","Q6958514":"municipal government in india","Q697196":"ocean liner","Q697295":"shrine","Q6974560":"national nature reserve","Q6978246":"national scenic area","Q6988120":"neighborhood of vilnius","Q70208":"municipality of switzerland","Q702492":"urban area","Q7055":"buddha","Q7075":"library","Q707813":"hanseatic city","Q708676":"charitable organization","Q7138926":"parliament building","Q719592":"local council of malta","Q720106":"scroll","Q72082844":"protected area section","Q7251271":"protected area of indonesia","Q7251867":"proto-city","Q7257985":"public service company","Q7265965":"qal'a","Q727002":"charter","Q7275":"state","Q727715":"book of hours","Q728502":"nautical chart","Q7285116":"raised coral atoll","Q728937":"railway line","Q72926449":"church tower","Q7328910":"art collection","Q7362268":"roman amphitheatre","Q7375052":"royal city","Q737988":"patio","Q7400159":"sail training","Q740437":"pinacotheca","Q744099":"hillfort","Q744296":"wooden church","Q746310":"stave church","Q747074":"comune of italy","Q74817647":"aspect in a geographic region","Q7498109":"vessel preserved in museum","Q751030":"department of senegal","Q751876":"château","Q755017":"tell","Q75520":"plateau","Q756780":"roman colony","Q757292":"border checkpoint","Q759882":"protected landscape area","Q76007695":"administrative district of czech municipality with expanded powers","Q76009696":"administrative district of czech municipality with authorized municipal office","Q76529788":"franciscan friary","Q7725310":"series of creative works","Q7725634":"literary work","Q7755":"constitution","Q778129":"light cruiser","Q7814330":"toll bridge","Q7819319":"czech municipality with expanded powers","Q7830262":"township of myanmar","Q7841907":"municipality with authorized municipal office","Q787113":"promenade","Q7897276":"unparished area","Q79007":"street","Q79218":"triptych","Q7930989":"city or town","Q797765":"inclined tower","Q811165":"architectural heritage monument","Q811430":"fixed construction","Q811600":"sacred grove","Q811979":"architectural structure","Q812880":"cube","Q8142":"currency","Q814254":"feature","Q814769":"bone tool","Q815448":"belfry","Q816829":"periodization","Q817056":"benedictine abbey","Q81917":"fortified tower","Q819435":"mining region","Q820084":"mountain park","Q820254":"mining community","Q820477":"mine","Q82117":"city gate","Q824786":"lavra","Q82794":"region","Q828909":"wharf","Q830335":"protected cruiser","Q831515":"lightvessel","Q833913":"sufi lodge","Q83405":"factory","Q835937":"mirror writing","Q838159":"türbe","Q838948":"work of art","Q839954":"archaeological site","Q84015776":"historic landmark","Q840482":"shrine of our lady","Q842402":"hindu temple","Q8432":"civilization","Q844619":"vihara","Q8452914":"district town","Q845945":"shinto shrine","Q847478":"armored cruiser","Q848944":"merchant vessel","Q8502":"mountain","Q8513":"database","Q852190":"shipwreck","Q853854":"clock tower","Q855747":"egyptian temple","Q856314":"bible moralisée","Q85631896":"urban district of bavaria","Q860861":"sculpture","Q861809":"bilingual inscription","Q8658":"12 metre","Q867143":"roman temple","Q871419":"district of austria","Q87167":"manuscript","Q8719053":"music venue","Q87351459":"monastic community","Q875538":"public university","Q877152":"white elephant","Q878223":"highland","Q88291":"citadel","Q88598":"gord","Q88667167":"museum network","Q88778578":"artificial cave","Q892367":"first-rate","Q893745":"national monument","Q893775":"national monument of the united states","Q89468":"kasbah","Q89487741":"city in bulgaria","Q89691":"ksar","Q9019918":"endorheic lake","Q902814":"border city","Q9067730":"monastic rule","Q907116":"monument (spain)","Q9096832":"paleontological site","Q911663":"bascule bridge","Q91315817":"cistercian monastery","Q918230":"roman villa","Q92026":"japanese castle","Q922203":"code of law","Q92275707":"crusader castle","Q9252000":"exhibit","Q9259":"world heritage site","Q92755865":"religious museum","Q928235":"sloop-of-war","Q930314":"vernacular architecture","Q93184":"drawing","Q93288":"contract","Q933091":"steppe lake","Q93342462":"ancient greek archaeological site","Q93352":"coast","Q935773":"cromlech","Q9444":"rainforest","Q94483283":"former convent","Q949819":"ship canal","Q955236":"transboundary protected area","Q956165":"psalter","Q95652804":"a-bombed building","Q96211395":"heritage site in sweden","Q96352513":"religious building ruin","Q96371632":"secularized church","Q96376684":"secularized religious building","Q96382432":"former mosque","Q96440023":"secularized mosque","Q96888669":"academic publisher","Q970092":"crane vessel","Q97588309":"former cathedral","Q97662266":"museum of modern art","Q97824060":"benedictine nunnery","Q98116669":"religious complex","Q98675100":"vice-ministerial level institution","Q98792435":"cultural center","Q99018632":"group of geographic locations","Q99516640":"wall painting"}''')

# Hand-verified P31 label lists for the ~100 object-class titles that
# aren't covered by cache/image_probe/state/qid_map.json at all (never
# probed -- they weren't in universe_objects.json). Looked up once by
# hand against live Wikidata during this session's research pass.
SUPPLEMENTARY_TITLE_P31 = json.loads('''{"Alfred Jewel":["archaeological find","æstel"],"Amber Fort":["palace","fortress"],"American Gothic":["painting"],"Aqueduct of Segovia":["stone bridge","arch bridge","architectural heritage monument","Roman aqueduct"],"Aztec sun stone":["sculpture"],"Baths of Caracalla":["thermae","national museum","archaeological site","ancient Roman structure","archaeological artifact museum","Italian national museum","archaeological park","museum","Museum of the Italian Ministry of Culture"],"Bayon":["temple","archaeological site"],"Belém Tower":["fort","fortified tower","cultural heritage"],"Benin Bronzes":["group of sculptures"],"Blue Mosque, Istanbul":["mosque","historic building"],"Boudha Stupa":["human settlement","stupa"],"Bran Castle":["castle"],"Brooklyn Bridge":["suspension bridge","cable-stayed bridge","multi-level bridge","steel bridge","road bridge","railway bridge"],"Carcassonne":["commune of France"],"Catherine Palace":["palace"],"Charioteer of Delphi":["statue"],"Charles Bridge":["stone bridge","arch bridge","footbridge","street"],"Château de Chambord":["château"],"Codex Gigas":["written work","codex","illuminated manuscript"],"Column of Marcus Aurelius":["victory column","archaeological site","statue"],"Concorde":["aircraft model"],"Copán":["archaeological site"],"Court of the Lions":["patio"],"Ctesiphon":["ancient city","archaeological site"],"Detroit Olympia":["arena"],"Djenné-Djenno":["archaeological site"],"Doge's Palace":["palace","art museum","museum of a public entity"],"Edinburgh Castle":["castle","museum","archaeological site","building complex"],"Girl with a Pearl Earring":["painting"],"Golden Rhinoceros of Mapungubwe":["archaeological artefact"],"Gyeongbokgung":["palace"],"Helianthus":["taxon"],"Hereford Mappa Mundi":["mappa mundi"],"Ishango bone":["archaeological find","bone tool"],"Jerash":["city"],"Kerma":["archaeological site"],"Kilwa Kisiwani":["island","human settlement"],"Knossos":["organized archaeological site","polis"],"Kremlin Wall Necropolis":["cemetery","historic site"],"Laocoön and His Sons":["sculpture","group of sculptures"],"Lascaux":["cave with prehistoric art","Paleolithic site"],"Last Supper":["artistic theme","banquet","gospel episode"],"Library of Celsus":["library","archaeological site","sepulchral monument"],"Lion Gate":["city gate"],"Longmen Grottoes":["grotto","Chinese AAAAA-rated tourist attraction"],"Lycurgus Cup":["cage cup","work of art"],"Mask of Agamemnon":["archaeological find","death mask"],"Matsumoto Castle":["hirajiro","military museum","Japanese castle"],"Mildenhall Treasure":["hoard"],"Moray":["council area","lieutenancy area of Scotland","Scottish district"],"Mortuary temple of Hatshepsut":["house of millions of years"],"Mount Rushmore":["mountain"],"Nabta Playa":["archaeological site"],"Newgrange":["Irish passage tomb","tomb"],"Ollantaytambo":["city"],"Palmyra":["ancient city","ruins","Ancient Greek archaeological site"],"Pamukkale":["hot spring"],"Panama Canal":["ship canal"],"Paro Taktsang":["Tibetan Buddhist monastery","Buddhist temple"],"Pena Palace":["palace","cultural heritage"],"Peterhof Palace":["palace complex","protected area"],"Phaistos Disc":["clay tablet","inscription"],"Pietà (Michelangelo)":["sculpture","cultural property"],"Piri Reis map":["nautical chart","world map"],"Ponte Vecchio":["deck arch bridge","stone bridge","built-on bridge","arched bridge","footbridge"],"Portrait of Terentius Neo":["fresco","work of art"],"Prague Castle":["castle","hillfort"],"Predjama Castle":["cave castle"],"Pyramid of the Sun":["temple","archaeological site","pyramid"],"Pyramids of Meroë":["archaeological site"],"Qutb Minar":["minaret"],"Red Square":["square"],"Registan":["fixed construction","square","architectural ensemble"],"Rialto Bridge":["stone bridge","arch bridge","footbridge","covered bridge","built-on bridge","renaissance bridge"],"Roman Forum":["square","archaeological site","forum","real property","tourist destination","roman ruins"],"Ruins of Gedi":["archaeological site"],"Sacsayhuamán":["archaeological site"],"Shore Temple":["Hindu temple"],"Sistine Chapel ceiling":["painted ceiling","cycle of frescoes"],"St Mark's Basilica":["cathedral","minor basilica"],"St. Peter's Basilica":["major basilica","papal basilica","architectural landmark","parish church","patriarchal basilica"],"Staffordshire Hoard":["archaeological find","hoard"],"Summer Palace":["palace"],"Temple of Apollo (Delphi)":["ancient Greek temple","ruins","archaeological site"],"Temple of Heaven":["temple","Chinese AAAAA-rated tourist attraction"],"The Creation of Adam":["fresco"],"The Great Wave off Kanagawa":["woodblock print"],"The School of Athens":["fresco"],"The Temple of the Golden Pavilion":["literary work"],"Tiananmen":["gate"],"Tiwanaku":["archaeological site","ancient city"],"Trajan's Column":["victory column","archaeological site"],"Trevi Fountain":["sculpture","fountain"],"Trundholm sun chariot":["archaeological artefact","archaeological find","sculpture"],"Tulum":["archaeological site"],"Uffington White Horse":["horse hill figure","archaeological site"],"Verona Arena":["opera house","Roman amphitheatre","archaeological site","theatre building","ancient Roman structure","archaeological artifact museum","historical civil building museum","museum of a public entity"],"Vitruvian Man":["drawing","mirror writing"],"Wawel Castle":["castle","history museum","tourist attraction","museum"],"Westminster Abbey":["Anglican or Episcopal cathedral","Royal Peculiar","abbey church","Anglican church building","collegiate church"],"Windsor Castle":["Residence of the British Royal Family","castle","royal palace","palace","English country house","historic house museum"],"Winged Victory of Samothrace":["statue","archaeological artefact"],"Winter Palace":["château","palace","museum building"],"Wright Flyer":["airplane","Flyer"]}''')

# Titles used as unit tests per the task brief, plus every geo/natural
# false-positive/negative case this session found and hand-verified. Kept
# small on purpose -- this is a spot-check, not the primary mechanism.
KEEP_TITLE_OVERRIDE = {
    # Coarse/misleading primary P31 for this specific famous landmark
    # (verified against live Wikidata during this session's research):
    "Mount Rushmore",       # P31 is literally "mountain" -- it's the carving that matters
    "Peterhof Palace",      # P31 "palace complex"+"protected area" (heritage status, not nature)
    "Boudha Stupa",         # P31 "human settlement"+"stupa" (the stupa's own tiny quarter)
    "Jerash",               # P31 bare "city" -- article is about the Roman ruin city
    "Ollantaytambo",        # P31 bare "city" -- article is about the Inca fortress/terraces
    "Kilwa Kisiwani",       # P31 "island"+"human settlement" -- UNESCO Swahili ruin site
    "Mont-Saint-Michel",    # P31 "commune of France" -- article is about the abbey-islet
    "Sigiriya",             # P31 bare "human settlement" -- the rock fortress/palace ruin
    "Axum",                 # P31 bare "city" -- famous for its ancient obelisks/stelae
    "Lalibela",             # P31 bare "human settlement" -- the rock-hewn churches
    "Mount Nemrut",         # P31 "mountain" -- it's the royal statue sanctuary on top
    "Olmec colossal heads", # no P31 data cached; unambiguous famous Olmec sculptures
    "Fabergé egg",          # no P31 data cached; unambiguous famous jewelled artefacts
    "Robben Island",        # P31 "prison island"+"island" -- the Mandela prison, not geography
    "Elephanta Caves",      # P31 bare "cave" -- rock-cut Hindu temple complex
    "Kanheri Caves",        # P31 bare "cave" -- rock-cut Buddhist monastery complex
    "Seokguram Grotto",     # P31 incl. "cave" -- rock hermitage temple with the seated Buddha
    "Persian Qanat",        # no P31 data cached; unambiguous ancient engineering heritage
    "Museumsinsel (Museum Island), Berlin",  # P31 "neighborhood" -- it's the 5-museum complex
    "Stone Mountain",       # P31 "mountain" -- famous for its carved memorial relief
    "Fort Jesus",           # P31 incl. "national park" (protection status) -- it's a fortress
    "Church of the Ascension, Kolomenskoye",  # P31 incl. "village"/"park" -- it's the church
    "Historic Fortified City of Carcassonne",  # P31 "fortress"/"citadel" -- the citadel itself
    # (contrast plain "Carcassonne", left excluded on purpose -- that title
    # is the modern commune; this more specific title is the citadel)
}
EXCLUDE_TITLE_OVERRIDE = {
    # Genuinely just the modern administrative entity under this exact
    # title, with no structure-specific P31 at all -- left excluded on
    # purpose (a curator wanting the citadel/terraces could add a more
    # specific title, e.g. "Citadel of Carcassonne").
    "Carcassonne", "Moray",
}

NAME_PATTERN_EXCLUDE = [
    r"^Historic Cent(re|er)s? of ", r"^Historic Cent(re|er) of the ",
    r"^Old Town of ", r"^Historic Town of ",
    r"^(Kingdom|Republic|Empire|Duchy|Sultanate|Emirate|Caliphate|Province|"
    r"State|County|Region|Prefecture|Canton) of ",
]


def build_p31_claims_cache():
    """qid -> {P31 label strings, lowercased}, merged read-only from
    cache/image_probe/raw/*.json (wbgetentities props=claims responses)
    and cache/wikidata_tags/claims/<sha1(qid)>.json (build_tags.py's own
    cache of the same). Sorted glob so merge order is deterministic."""
    merged_claims = {}
    for fp in sorted(glob.glob(os.path.join(IMAGE_PROBE_RAW_DIR, "*.json"))):
        try:
            d = load_json(fp)
        except (OSError, json.JSONDecodeError):
            continue
        body = d.get("body") if isinstance(d, dict) else None
        entities = (body or {}).get("entities") if isinstance(body, dict) else None
        if not isinstance(entities, dict):
            continue
        for qid, ent in entities.items():
            if isinstance(ent, dict) and "claims" in ent and qid not in merged_claims:
                merged_claims[qid] = ent["claims"]

    qid_map = {}
    qm_path = os.path.join(IMAGE_PROBE_STATE_DIR, "qid_map.json")
    if os.path.exists(qm_path):
        qid_map = load_json(qm_path)
    needed_qids = sorted({v["qid"] for v in qid_map.values() if v.get("qid")})
    for qid in needed_qids:
        if qid in merged_claims:
            continue
        p = os.path.join(WIKIDATA_TAGS_CLAIMS_DIR, _hash(qid) + ".json")
        if os.path.exists(p):
            try:
                merged_claims[qid] = load_json(p)
            except (OSError, json.JSONDecodeError):
                pass

    qid_p31_labels = {}
    for qid, claims in merged_claims.items():
        p31 = claims.get("P31") or []
        labs = []
        for c in p31:
            v = (c.get("mainsnak") or {}).get("datavalue", {}).get("value", {})
            vid = v.get("id") if isinstance(v, dict) else None
            if vid and vid in P31_LABELS:
                labs.append(P31_LABELS[vid])
        qid_p31_labels[qid] = labs
    return qid_map, qid_p31_labels


def make_playability_checker():
    qid_map, qid_p31_labels = build_p31_claims_cache()

    def check(wiki_title):
        """Returns (passes: bool, flag: str|None)."""
        if wiki_title in KEEP_TITLE_OVERRIDE:
            return True, None
        if wiki_title in EXCLUDE_TITLE_OVERRIDE:
            return False, "playability_filter"

        entry = qid_map.get(wiki_title)
        qid = entry.get("qid") if entry else None
        labels = qid_p31_labels.get(qid) if qid else None

        if not labels:
            sup = SUPPLEMENTARY_TITLE_P31.get(wiki_title)
            if sup is not None:
                labels = [s.lower() for s in sup]

        if labels:
            verdict = classify_p31_labels(labels)
            if verdict == "exclude":
                return False, "playability_filter"
            return True, None

        # No P31 data anywhere -- name-pattern heuristic, then conservative
        # default (exclude, flagged p31_unknown) per spec.
        for pat in NAME_PATTERN_EXCLUDE:
            if re.search(pat, wiki_title):
                return False, "playability_filter"
        if qid is None and entry is None:
            return False, "p31_unknown"
        return False, "p31_unknown"

    return check


# ===========================================================================
# Sensitivity flags -- never silently include or exclude; surfaced for the
# owner's own call regardless of keep/add/retire status.
# ===========================================================================

NAZI_FASCIST_PEOPLE = {
    "Adolf Hitler", "Heinrich Himmler", "Joseph Goebbels", "Hermann Göring",
    "Reinhard Heydrich", "Adolf Eichmann", "Josef Mengele", "Rudolf Höss",
    "Benito Mussolini", "Francisco Franco", "Hideki Tojo", "Rudolf Hess",
    "Albert Speer", "Martin Bormann", "Heinrich Müller", "Klaus Barbie",
    "Julius Streicher", "Ante Pavelić",
}
NAZI_KEYWORD_PATTERN = re.compile(
    r"\b(nazi|third reich|gestapo|waffen-ss|schutzstaffel|holocaust|auschwitz)\b",
    re.IGNORECASE,
)

RELIGIOUS_FOUNDERS = {
    "Muhammad", "Jesus", "The Buddha", "Gautama Buddha", "Guru Nanak",
    "Joseph Smith", "Zoroaster", "Mahavira", "Confucius", "Laozi",
    "Baháʼu'lláh",
}

DARK_ARTEFACTS = {"Little Boy", "Fat Man", "Enola Gay", "Auschwitz concentration camp"}
DARK_KEYWORD_PATTERN = re.compile(
    r"\b(concentration camp|extermination camp|gas chamber|genocide|massacre|pogrom|"
    r"ethnic cleansing)\b",
    re.IGNORECASE,
)


def sensitivity_flags(wiki_title, occupation_family=None):
    flags = []
    if wiki_title in NAZI_FASCIST_PEOPLE or NAZI_KEYWORD_PATTERN.search(wiki_title):
        flags.append("sensitive-nazi")
    if wiki_title in RELIGIOUS_FOUNDERS:
        flags.append("sensitive-religious")
        if wiki_title == "Muhammad":
            flags.append("no-depiction")
    if wiki_title in DARK_ARTEFACTS or DARK_KEYWORD_PATTERN.search(wiki_title):
        flags.append("sensitive-dark")
    return flags


# ===========================================================================
# Loaders
# ===========================================================================

def load_inputs():
    return {
        "fame_scores": load_json(os.path.join(HERE, "fame_scores.json")),
        "gap_report": load_json(os.path.join(HERE, "gap_report.json")),
        "tags": load_json(os.path.join(HERE, "tags.json")),
        "image_availability": load_json(os.path.join(HERE, "image_availability.json")),
        "current_inventory": load_json(os.path.join(HERE, "current_inventory.json")),
    }


# ===========================================================================
# Object re-percentile (AFTER the playability filter): city/country/nature
# pollution removed from the class-relative percentile basis, exactly the
# same formula and weights as build_scores.py (0.50/0.15/0.10/0.25).
# ===========================================================================

def repercentile_objects(fame_scores, playability_check):
    scores = fame_scores["scores"]
    by_class = {c: [] for c in OBJECT_CLASSES}
    survivor_flags = {}
    for s in scores:
        if s["class"] not in OBJECT_CLASSES:
            continue
        passes, flag = playability_check(s["wiki_title"])
        survivor_flags[s["wiki_title"]] = (passes, flag)
        if passes:
            by_class[s["class"]].append(s)

    new_fame = {}
    for cls, items in by_class.items():
        pv_vals = [_num_or_zero(it.get("pv_stat")) for it in items]
        lang_vals = [_num_or_zero(it.get("languages")) for it in items]
        inlink_vals = [_num_or_zero(it.get("inlinks")) for it in items]
        pv_pcts = average_rank_percentiles(pv_vals)
        lang_pcts = average_rank_percentiles(lang_vals)
        inlink_pcts = average_rank_percentiles(inlink_vals)
        for i, it in enumerate(items):
            fam = it.get("family_consensus") or 0.0
            fame = (0.50 * pv_pcts[i] + 0.15 * lang_pcts[i] + 0.10 * inlink_pcts[i]
                    + 0.25 * (fam * 100))
            new_fame[it["wiki_title"]] = round(fame, 2)

    return new_fame, survivor_flags


# ===========================================================================
# Tag / image / fame lookups
# ===========================================================================

def build_lookups(inputs):
    tags = inputs["tags"]
    people_tags = tags["people"]
    object_tags = tags["objects"]
    img = inputs["image_availability"]["items"]
    fame_scores_by_title = {s["wiki_title"]: s for s in inputs["fame_scores"]["scores"]}
    return people_tags, object_tags, img, fame_scores_by_title


def image_status(title, img_lookup):
    rec = img_lookup.get(title)
    if not rec or not rec.get("has_image"):
        return "none"
    if not rec.get("license_ok"):
        return "none"
    return "small" if rec.get("small") else "ok"


def person_occupation(title, people_tags, mb_domain=None):
    """(occupation_family_or_None, source) -- tags.json first, else a
    coarse domain->family fallback for the handful of people tags.json
    doesn't cover (~2% of the person universe)."""
    t = people_tags.get(title)
    if t and t.get("occupation_family"):
        return t["occupation_family"], "tags"
    if mb_domain == "sports":
        return "athlete", "domain_fallback"
    if mb_domain == "arts":
        return "performer", "domain_fallback"
    return None, "unknown"


# ===========================================================================
# Retire/keep split for the CURRENT pool of a game.
# ===========================================================================

def split_current_pool(game, gap_report, new_object_fame=None, survivor_flags=None):
    items = gap_report["pool_health"][game]["items"]
    keep, retire = [], []
    for it in items:
        wt = it.get("wiki_title")
        fame = it.get("fame")
        proposed_bin = it.get("proposed_bin")

        forced_retire_reason = None
        if game == "what" and wt and survivor_flags is not None:
            passes, _flag = survivor_flags.get(wt, (True, None))
            if not passes:
                forced_retire_reason = "fails_playability_filter"

        if game == "what" and wt and new_object_fame is not None and wt in new_object_fame:
            fame = new_object_fame[wt]

        record = dict(it)
        record["fame"] = fame
        is_retire = forced_retire_reason is not None
        if not is_retire and proposed_bin == "E":
            is_retire = True
        if not is_retire and fame is not None and fame < 40:
            is_retire = True

        if is_retire:
            record["_retire_reason"] = forced_retire_reason or "low_fame_or_bin_e"
            retire.append(record)
        else:
            keep.append(record)
    return keep, retire


# ===========================================================================
# Candidate build + addition selection (shared by who/map/what)
# ===========================================================================

def era_of(region_era_tuple):
    return region_era_tuple


def build_who_map_candidates(game, gap_report, people_tags, img_lookup, muhammad_excluded_from):
    mb = gap_report["missing_bankers"][game]
    candidates = []
    excluded_recent = []
    excluded_no_image = []
    for e in mb:
        title = e["wiki_title"]
        name = e["name"]
        if game == muhammad_excluded_from and title == "Muhammad":
            continue  # no-depiction: ineligible for Face Value
        occ, occ_source = person_occupation(title, people_tags, e.get("domain"))
        death_year = e.get("death_year")
        is_celeb_family = occ in CELEBRITY_FAMILIES
        recent_excluded = False
        if is_celeb_family:
            if (isinstance(death_year, (int, float)) and death_year >= RECENT_ENTERTAINMENT_FLOOR_YEAR
                    and name not in RECENT_ENTERTAINMENT_ALLOWLIST):
                recent_excluded = True
        elif occ is None and e.get("policy_flag") == "recent_entertainment" and name not in RECENT_ENTERTAINMENT_ALLOWLIST:
            recent_excluded = True
            is_celeb_family = True  # gap_report's own flag only fires for arts/sports domains
        if recent_excluded:
            excluded_recent.append({"name": name, "wiki_title": title, "fame": e["fame"]})
            continue

        img_stat = image_status(title, img_lookup) if game == "who" else "n/a"
        if game == "who" and img_stat == "none":
            excluded_no_image.append({"name": name, "wiki_title": title, "fame": e["fame"]})
            continue

        t = people_tags.get(title, {})
        candidates.append({
            "name": name, "wiki_title": title, "fame": e["fame"],
            "era": t.get("era"), "region": t.get("region"),
            "occupation_family": occ, "is_celeb_family": is_celeb_family,
            "image": img_stat,
            "flags": sensitivity_flags(title, occ) + (["coords_pending"] if game == "map" else []),
        })
    candidates.sort(key=lambda c: (-c["fame"], c["wiki_title"]))
    return candidates, excluded_recent, excluded_no_image


def build_what_candidates(gap_report, object_tags, img_lookup, new_object_fame, survivor_flags):
    mb = gap_report["missing_bankers"]["what"]
    candidates = []
    excluded_playability = []
    excluded_no_image = []
    for e in mb:
        title = e["wiki_title"]
        name = e["name"]
        passes, flag = survivor_flags.get(title, (False, "p31_unknown"))
        if not passes:
            excluded_playability.append({"name": name, "wiki_title": title, "fame": e["fame"], "flag": flag})
            continue
        img_stat = image_status(title, img_lookup)
        if img_stat == "none":
            excluded_no_image.append({"name": name, "wiki_title": title, "fame": e["fame"]})
            continue
        fame = new_object_fame.get(title, e["fame"])
        t = object_tags.get(title, {})
        kind = t.get("kind") or e.get("object_kind")
        candidates.append({
            "name": name, "wiki_title": title, "fame": fame,
            "era": t.get("era"), "region": t.get("region"), "kind": kind,
            "image": img_stat,
            "flags": sensitivity_flags(title),
        })
    candidates.sort(key=lambda c: (-c["fame"], c["wiki_title"]))
    return candidates, excluded_playability, excluded_no_image


def seed_distribution(keep_records, tag_lookup, is_people):
    region_counts = {}
    region_known = 0
    era_present = set()
    celeb_count = 0
    for r in keep_records:
        wt = r.get("wiki_title")
        t = tag_lookup.get(wt) if wt else None
        if not t:
            continue
        region = t.get("region")
        era = t.get("era")
        if region:
            region_counts[region] = region_counts.get(region, 0) + 1
            region_known += 1
        if era:
            era_present.add(era)
        if is_people and t.get("occupation_family") in CELEBRITY_FAMILIES:
            celeb_count += 1
    return {
        "region_counts": region_counts, "region_known": region_known,
        "era_present": era_present, "celeb_count": celeb_count,
    }


def select_additions(candidates, target_add, seed, is_people_pool):
    region_counts = dict(seed["region_counts"])
    region_known = seed["region_known"]
    era_present = set(seed["era_present"])
    celeb_count = 0  # celeb cap is additions-only per rule 3
    added = []
    added_titles = set()
    deferred = []

    def region_cap_ok(region, era):
        if not region or era == "ancient":  # antiquity liberal: no region cap for ancient people/objects
            return True
        new_known = region_known + 1
        new_count = region_counts.get(region, 0) + 1
        return (new_count / new_known) <= REGION_CAP_FRACTION

    def celeb_cap_ok(is_celeb):
        if not is_people_pool or not is_celeb:
            return True
        new_total = len(added) + 1
        new_celeb = celeb_count + 1
        return (new_celeb / new_total) <= CELEBRITY_CAP_FRACTION

    def accept(c):
        nonlocal region_known, celeb_count
        added.append(c)
        added_titles.add(c["wiki_title"])
        if c.get("region"):
            region_counts[c["region"]] = region_counts.get(c["region"], 0) + 1
            region_known += 1
        if c.get("era"):
            era_present.add(c["era"])
        if is_people_pool and c.get("is_celeb_family"):
            celeb_count += 1

    for c in candidates:
        if len(added) >= target_add:
            break
        is_celeb = bool(c.get("is_celeb_family")) if is_people_pool else False
        if not region_cap_ok(c.get("region"), c.get("era")):
            deferred.append(c)
            continue
        if not celeb_cap_ok(is_celeb):
            deferred.append(c)
            continue
        accept(c)

    progress = True
    while len(added) < target_add and progress and deferred:
        progress = False
        still = []
        for c in deferred:
            if len(added) >= target_add:
                still.append(c)
                continue
            is_celeb = bool(c.get("is_celeb_family")) if is_people_pool else False
            if not region_cap_ok(c.get("region"), c.get("era")):
                still.append(c)
                continue
            if not celeb_cap_ok(is_celeb):
                still.append(c)
                continue
            accept(c)
            progress = True
        deferred = still

    # Swap-improvement pass: fixes the "cold start" case where the single
    # highest-fame candidate overall happens to be cap-constrained (e.g. the
    # #1 fame candidate in the whole list is a performer) -- it gets
    # deferred by the greedy pass above simply because too few additions
    # existed yet for its share to clear the cap, even though a same-
    # category swap later on would clear it comfortably. Once target_add is
    # full, look for an EXACT-CATEGORY victim already in `added` (same
    # region, and same celeb-family status if the candidate is a
    # performer/athlete) with strictly lower fame -- swapping never changes
    # either cap's count, only improves fame, so it is always safe.
    changed = True
    while changed:
        changed = False
        deferred.sort(key=lambda c: (-c["fame"], c["wiki_title"]))
        for c in deferred:
            if c["wiki_title"] in added_titles:
                continue
            is_celeb = bool(c.get("is_celeb_family")) if is_people_pool else False
            c_region = c.get("region")
            victims = [
                a for a in added
                # An unknown region never adds to any region's count, so
                # removing ANY victim (whatever its own region) and adding a
                # region=None candidate can only hold steady or improve
                # region concentration -- only a same-region match is
                # required to guarantee neutrality when c's region IS known.
                if (c_region is None or a.get("region") == c_region)
                and (bool(a.get("is_celeb_family")) if is_people_pool else False) == is_celeb
                and a["fame"] < c["fame"]
            ]
            if not victims:
                continue
            victim = min(victims, key=lambda a: (a["fame"], a["wiki_title"]))
            # Undo the victim's contribution to the running counters, then
            # add c's -- a same-region swap nets to no change (as intended);
            # a None-region c swapped for a known-region victim can only
            # hold steady or improve that region's share (denominator and
            # numerator both shrink by one for the vacated region).
            added.remove(victim)
            added_titles.discard(victim["wiki_title"])
            if victim.get("region"):
                region_counts[victim["region"]] = region_counts.get(victim["region"], 0) - 1
                region_known -= 1
            if is_people_pool and victim.get("is_celeb_family"):
                celeb_count -= 1
            accept(c)
            changed = True
            break

    # Era-non-empty guardrail: force in the single highest-fame remaining
    # candidate for any era bucket left empty, if one exists -- allowed to
    # overshoot target_add slightly, since target is stated as approximate.
    for era in ERA_BUCKETS:
        if era in era_present:
            continue
        candidate_pool = [c for c in candidates if c.get("era") == era and c["wiki_title"] not in added_titles]
        if candidate_pool:
            accept(candidate_pool[0])

    return added


# ===========================================================================
# Distribution snapshots (before/after)
# ===========================================================================

def distribution_snapshot(records, tag_lookup, is_people):
    era_counts = {e: 0 for e in ERA_BUCKETS}
    region_counts = {}
    occ_or_kind_counts = {}
    for r in records:
        wt = r.get("wiki_title")
        t = tag_lookup.get(wt) if wt else None
        era = (t or {}).get("era") if t else r.get("era")
        region = (t or {}).get("region") if t else r.get("region")
        if is_people:
            occ = (t or {}).get("occupation_family") if t else r.get("occupation_family")
        else:
            occ = (t or {}).get("kind") if t else r.get("kind")
        if era in era_counts:
            era_counts[era] += 1
        if region:
            region_counts[region] = region_counts.get(region, 0) + 1
        if occ:
            occ_or_kind_counts[occ] = occ_or_kind_counts.get(occ, 0) + 1
    total = len(records)
    ancient_share = round(era_counts["ancient"] / total, 4) if total else 0.0
    return {
        "total": total,
        "era": era_counts,
        "region": dict(sorted(region_counts.items(), key=lambda kv: -kv[1])),
        "occupation_or_kind": dict(sorted(occ_or_kind_counts.items(), key=lambda kv: -kv[1])),
        "ancient_era_share": ancient_share,
    }


# ===========================================================================
# Output item shaping
# ===========================================================================

def shape_keep_retire_item(record, tag_lookup, img_lookup, is_people, game):
    wt = record.get("wiki_title")
    t = tag_lookup.get(wt) if wt else None
    name = record.get("display_name") or record.get("name")
    era = (t or {}).get("era")
    region = (t or {}).get("region")
    if is_people:
        occ_or_kind = (t or {}).get("occupation_family")
    else:
        occ_or_kind = (t or {}).get("kind")
    if game == "map":
        image = "n/a"
    else:
        image = image_status(wt, img_lookup) if wt else "none"
    flags = sensitivity_flags(wt, occ_or_kind if is_people else None) if wt else []
    out = {
        "name": name, "wiki_title": wt, "fame": record.get("fame"),
        "era": era, "region": region,
        ("occupation_family" if is_people else "kind"): occ_or_kind,
        "image": image, "flags": flags,
        "current_tier": record.get("current_tier"),
        "aired_count": record.get("aired_count"),
    }
    return out


def shape_add_item(cand, is_people, game):
    out = {
        "name": cand["name"], "wiki_title": cand["wiki_title"], "fame": cand["fame"],
        "era": cand.get("era"), "region": cand.get("region"),
        ("occupation_family" if is_people else "kind"): (cand.get("occupation_family") if is_people else cand.get("kind")),
        "image": cand.get("image", "n/a" if game == "map" else "none"),
        "flags": cand.get("flags", []),
    }
    return out


# ===========================================================================
# Main
# ===========================================================================

def main():
    inputs = load_inputs()
    people_tags, object_tags, img_lookup, fame_scores_by_title = build_lookups(inputs)
    gap_report = inputs["gap_report"]

    playability_check = make_playability_checker()
    new_object_fame, survivor_flags = repercentile_objects(inputs["fame_scores"], playability_check)

    per_game = {}
    stats = {}
    excluded_by_policy = {
        "recent_entertainment": [],
        "playability_filter": [],
        "no_image": {"count": 0, "top_20": []},
    }
    flagged_for_owner = {}

    def add_flags(records, game, status):
        for r in records:
            wt = r.get("wiki_title")
            if not wt:
                continue
            fl = r.get("flags")
            if fl is None:
                fl = sensitivity_flags(wt)
            for f in fl:
                if f in ("coords_pending", "small-image"):
                    continue
                flagged_for_owner.setdefault(f, []).append({
                    "name": r.get("name") or r.get("display_name"), "wiki_title": wt,
                    "game": game, "fame": r.get("fame"), "status": status,
                })

    distribution = {}

    # ---- WHO ----
    who_keep, who_retire = split_current_pool("who", gap_report)
    who_candidates, who_excl_recent, who_excl_noimg = build_who_map_candidates(
        "who", gap_report, people_tags, img_lookup, muhammad_excluded_from="who")
    who_target_add = max(0, TARGETS["who"] - len(who_keep))
    who_seed = seed_distribution(who_keep, people_tags, is_people=True)
    who_adds = select_additions(who_candidates, who_target_add, who_seed, is_people_pool=True)

    # ---- MAP ----
    map_keep, map_retire = split_current_pool("map", gap_report)
    map_candidates, map_excl_recent, map_excl_noimg = build_who_map_candidates(
        "map", gap_report, people_tags, img_lookup, muhammad_excluded_from="who")
    map_target_add = max(0, TARGETS["map"] - len(map_keep))
    map_seed = seed_distribution(map_keep, people_tags, is_people=True)
    map_adds = select_additions(map_candidates, map_target_add, map_seed, is_people_pool=True)

    # ---- WHAT ----
    what_keep, what_retire = split_current_pool("what", gap_report, new_object_fame, survivor_flags)
    what_candidates, what_excl_play, what_excl_noimg = build_what_candidates(
        gap_report, object_tags, img_lookup, new_object_fame, survivor_flags)
    what_target_add = max(0, TARGETS["what"] - len(what_keep))
    what_seed = seed_distribution(what_keep, object_tags, is_people=False)
    what_adds = select_additions(what_candidates, what_target_add, what_seed, is_people_pool=False)

    excluded_by_policy["recent_entertainment"] = sorted(
        {r["name"] for r in who_excl_recent} | {r["name"] for r in map_excl_recent})
    excluded_by_policy["playability_filter"] = sorted({r["name"] for r in what_excl_play})

    all_no_image = who_excl_noimg + map_excl_noimg + what_excl_noimg
    seen_titles = set()
    dedup_no_image = []
    for r in sorted(all_no_image, key=lambda r: (-r["fame"], r["wiki_title"])):
        if r["wiki_title"] in seen_titles:
            continue
        seen_titles.add(r["wiki_title"])
        dedup_no_image.append(r)
    excluded_by_policy["no_image"] = {
        "count": len(dedup_no_image),
        "top_20": [{"name": r["name"], "fame": r["fame"]} for r in dedup_no_image[:20]],
    }

    def finalize(game, keep_records, retire_records, add_candidates, tag_lookup, is_people):
        keep_out = [shape_keep_retire_item(r, tag_lookup, img_lookup, is_people, game) for r in keep_records]
        retire_out = [shape_keep_retire_item(r, tag_lookup, img_lookup, is_people, game) for r in retire_records]
        add_out = [shape_add_item(c, is_people, game) for c in add_candidates]

        keep_out.sort(key=lambda r: (-(r["fame"] or 0), r["wiki_title"] or ""))
        retire_out.sort(key=lambda r: (-(r["fame"] or 0), r["wiki_title"] or ""))
        add_out.sort(key=lambda r: (-(r["fame"] or 0), r["wiki_title"] or ""))

        per_game[game] = {"keep": keep_out, "add": add_out, "retire": retire_out}
        stats[game] = {
            "current_pool_size": len(keep_records) + len(retire_records),
            "keep": len(keep_out), "retire": len(retire_out), "add": len(add_out),
            "resulting_pool_size": len(keep_out) + len(add_out),
            "target": TARGETS[game],
        }

        add_flags(keep_out, game, "keep")
        add_flags(retire_out, game, "retire")
        add_flags(add_out, game, "add")

        before = distribution_snapshot(
            [dict(r, **({"region": r.get("region"), "era": r.get("era")})) for r in keep_out + retire_out],
            {}, is_people)
        after = distribution_snapshot(keep_out + add_out, {}, is_people)
        distribution[game] = {"before": before, "after": after}

    finalize("who", who_keep, who_retire, who_adds, people_tags, True)
    finalize("map", map_keep, map_retire, map_adds, people_tags, True)
    finalize("what", what_keep, what_retire, what_adds, object_tags, False)

    flagged_for_owner_sorted = {
        flag: sorted(entries, key=lambda e: (-(e["fame"] or 0), e["wiki_title"]))
        for flag, entries in flagged_for_owner.items()
    }
    flagged_counts = {flag: len(v) for flag, v in flagged_for_owner_sorted.items()}

    output = {
        "generatedOn": GENERATED_ON,
        "targets": TARGETS,
        "per_game": per_game,
        "flagged_for_owner": flagged_for_owner_sorted,
        "excluded_by_policy": excluded_by_policy,
        "distribution": distribution,
        "stats": stats,
        "meta": {
            "flagged_for_owner_counts": flagged_counts,
            "playability_filter_removed_count": len(what_excl_play),
            "celebrity_cap_fraction": CELEBRITY_CAP_FRACTION,
            "region_cap_fraction": REGION_CAP_FRACTION,
            "recent_entertainment_floor_year": RECENT_ENTERTAINMENT_FLOOR_YEAR,
            "recent_entertainment_allowlist": sorted(RECENT_ENTERTAINMENT_ALLOWLIST),
        },
    }

    out_path = os.path.join(HERE, "pool_proposal.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, sort_keys=False)
        f.write("\n")

    print(f"Wrote {out_path}", file=sys.stderr)
    print(json.dumps(stats, indent=2), file=sys.stderr)
    print("flagged_for_owner counts:", flagged_counts, file=sys.stderr)
    print("playability_filter removed (what candidates):", len(what_excl_play), file=sys.stderr)


if __name__ == "__main__":
    main()
