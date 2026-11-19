"""The maps' atlas (the figures' "map" family, notosaurus_core/typst_rules/map.md): the
countries' outlines and their main cities from Natural Earth (public domain), simplified,
with the map function (notosaurus_core/atlas/lib.typ), as a Typst package of our own:
core/notosaurus_core/typst/notosaurus-atlas-<version>.tar.gz, unpacked with the others
(figures_typst.packages). Nothing is downloaded when a map is drawn. Run again to change
the data or the function (VERSION raised with it), then commit what it wrote.

Besides atlas.json (countries, cities, lakes: every map reads it), files a map reads only
when it asks for them: rivers.json, reliefs.json (mountains, deserts, plains, peninsulas,
islands), waters.json (oceans, seas, gulfs, straits, lakes: their short names too), regions/<country code>.json
(its first-level divisions, and the groups Natural Earth gives them: France's régions), ways.json
(the sea ways a map's routes go by, made from the countries' outlines: seaways; with the
ports, the capes and the canals routes and flows pass).

  .venv/bin/python tools/atlas.py [folder] [--refresh-history]

The regions' names in the page's languages from Wikidata (CC0), by their ISO 3166-2 codes, kept
in tools/atlas-regions.json (the codes it lacks asked; all of them again with --refresh-history).
A country's far parts (its overseas departments, its archipelagos across the sea) are places of
their own in atlas.json ("t", "o" their country); the world's parts (UN M49) groups of countries
("areas"); names.json what a name the map refuses is otherwise (a region, a state of the past).

borders/<year>.json: the states of each of LAYERS' days from OpenHistoricalMap (CC0), as its
database stood on OHM_DATE; the land it leaves to no state filled by historical-basemaps' (GPL-3.0,
its licence shipped); their names from Wikidata (kept in tools/atlas-borders.json, asked again
with --refresh-history). OHM's answers are kept in `folder`, when given (some 150 MB a layer).

The sources read from `folder` when it has them (by their names), else downloaded: Natural
Earth's and CLDR's at a fixed version. The places of history (HISTORY) are read from
tools/atlas-history.json, the sea's passages (PASSAGES: straits, channels, canals) from
tools/atlas-passages.json, committed: the same atlas whatever day it is made; Wikidata is asked
only with --refresh-history (HISTORY or PASSAGES changed, or their data refreshed), which writes
those files again.

Needs shapely (requirements-dev.txt): regions simplified together, their borders shared.
"""

import gzip
import io
import json
import math
import re
import sys
import tarfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import shapely
import shapely.affinity
from shapely.geometry import shape
from shapely.ops import polygonize, polylabel

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core" / "notosaurus_core"
LIB = CORE / "atlas" / "lib.typ"
TARGET = CORE / "typst"
NAME, VERSION = "notosaurus-atlas", "0.15.0"
SOURCE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/"
COUNTRIES = "ne_50m_admin_0_countries.geojson"  # 1:50m: a country's shape, light enough
PLACES = "ne_10m_populated_places.geojson"  # 1:10m: the cities, their names in many languages
RIVERS = "ne_10m_rivers_lake_centerlines.geojson"  # the world's rivers, their names in English only
RIVERS_EUROPE = "ne_10m_rivers_europe.geojson"  # Europe's smaller ones (the Saône, the Somme), named in many languages
RELIEFS = "ne_10m_geography_regions_polys.geojson"  # mountains, deserts, plains, peninsulas…
WATERS = "ne_10m_geography_marine_polys.geojson"  # oceans, seas, gulfs, straits: French and English names
LAKES = "ne_50m_lakes.geojson"
REGIONS = "ne_10m_admin_1_states_provinces.geojson"  # each country's first-level divisions
LANGUAGES = ("FR", "EN", "DE", "ES", "IT", "PT")  # the page's languages
# Countries' usual names (Unicode CLDR: "Chine", "Stati Uniti", "Vietnã"; Natural Earth's are
# sometimes the official ones, "République populaire de Chine"), Brazil's Portuguese as CLDR's pt
CLDR = "https://cdn.jsdelivr.net/npm/cldr-localenames-full@46.0.0/main/{}/territories.json"
CLDR_LANGUAGES = ("fr", "en", "de", "es", "it", "pt")
CLDR_LICENCE = "https://cdn.jsdelivr.net/npm/cldr-localenames-full@46.0.0/LICENSE"  # shipped with them, as it asks
# The places of history lessons Natural Earth lacks or names otherwise (Aix-la-Chapelle,
# Cordoue, Lutèce, Constantinople, Troie): from Wikidata (CC0), each by its English Wikipedia
# article (never ambiguous), its names in the page's languages and its coordinates there, plus
# names Wikidata lacks; preferred among places of the same name when no country tells them apart
WIKIDATA = "https://www.wikidata.org/w/api.php"
WIKIPEDIA = "https://en.wikipedia.org/w/api.php"
HISTORY_FILE = ROOT / "tools" / "atlas-history.json"  # what Wikidata gave for HISTORY, kept
HISTORY = [
    # Antiquity
    *[(t, ()) for t in ("Ur", "Uruk", "Babylon", "Nineveh", "Memphis, Egypt", "Thebes, Egypt", "Giza", "Jericho")],
    *[
        (t, ())
        for t in ("Byblos", "Tyre, Lebanon", "Sidon", "Persepolis", "Troy", "Athens", "Sparta", "Olympia, Greece")
    ],
    *[(t, ()) for t in ("Delphi", "Marathon, Greece", "Alexandria", "Carthage", "Pompeii", "Ostia Antica")],
    *[(t, ()) for t in ("Alesia (city)", "Lutetia", "Lugdunum", "Massalia", "Bibracte", "Gergovia", "Antioch")],
    ("Ancient Corinth", ("Corinthe", "Corinth", "Korinth", "Corinto")),
    *[(t, ()) for t in ("Constantinople", "Byzantium", "Ctesiphon", "Chang'an", "Luoyang", "Pataliputra")],
    # The Middle Ages
    *[(t, ()) for t in ("Aachen", "Ravenna", "Córdoba, Spain", "Toledo, Spain", "Granada", "Kairouan", "Fez, Morocco")],
    *[(t, ()) for t in ("Venice", "Genoa", "Pisa", "Florence", "Bruges", "Ghent", "Lübeck", "Veliky Novgorod")],
    *[(t, ()) for t in ("Reims", "Chartres", "Cluny", "Avignon", "Poitiers", "Tours", "Orléans", "Bouvines")],
    *[(t, ()) for t in ("Crécy-en-Ponthieu", "Azincourt", "Rouen", "Troyes", "Saint-Denis, Seine-Saint-Denis")],
    *[(t, ()) for t in ("Carcassonne", "Aigues-Mortes", "Canterbury", "Hastings", "Santiago de Compostela")],
    *[(t, ()) for t in ("Timbuktu", "Samarkand", "Mecca")],
    # Modern times
    *[(t, ()) for t in ("Palos de la Frontera", "Cádiz", "Kozhikode", "Goa", "Malacca City", "Cusco", "Tenochtitlan")],
    *[(t, ()) for t in ("Santo Domingo", "Wittenberg", "Worms, Germany", "Augsburg", "Geneva", "Trento")],
    *[(t, ()) for t in ("La Rochelle", "Versailles, Yvelines", "Saint-Malo", "Quebec City", "Antwerp", "Edo")],
    # The 18th to 20th centuries
    *[(t, ()) for t in ("Valmy", "Varennes-en-Argonne", "Slavkov u Brna", "Waterloo, Belgium", "Sedan, Ardennes")],
    *[(t, ()) for t in ("Verdun", "Sarajevo", "Hiroshima", "Nagasaki", "Oradour-sur-Glane", "Vichy", "Yalta")],
    ("Điện Biên Phủ", ("Diên Biên Phu", "Dien Bien Phu", "Ðiện Biên Phủ", "Điện Biên Phủ")),
    *[(t, ()) for t in ("Nuremberg", "Potsdam", "Gettysburg, Pennsylvania")],
    # Sites of history that are no towns: the camps of the Shoah, the deportation's
    ("Auschwitz concentration camp", ("Auschwitz", "Auschwitz-Birkenau", "Birkenau", "Oświęcim")),
    ("Treblinka extermination camp", ("Treblinka",)),
    ("Sobibor extermination camp", ("Sobibor", "Sobibór")),
    ("Belzec extermination camp", ("Belzec", "Bełżec")),
    ("Chełmno extermination camp", ("Chelmno", "Chełmno", "Kulmhof")),
    ("Majdanek concentration camp", ("Majdanek", "Lublin-Majdanek")),
    ("Drancy internment camp", ("Drancy", "camp de Drancy")),
    ("Dachau concentration camp", ("Dachau",)),
    ("Buchenwald concentration camp", ("Buchenwald",)),
    ("Bergen-Belsen concentration camp", ("Bergen-Belsen",)),
    ("Ravensbrück concentration camp", ("Ravensbrück", "Ravensbruck")),
    ("Mauthausen concentration camp", ("Mauthausen", "Mauthausen-Gusen")),
    ("Natzweiler-Struthof concentration camp", ("Natzweiler-Struthof", "Struthof", "camp du Struthof")),
]
# The sea's passages (straits, channels, canals) a lesson names that Natural Earth lacks or
# names in two languages only: from Wikidata (CC0), each by its English Wikipedia article, its
# names in the page's languages and its point, plus names Wikidata lacks; one Natural Earth
# has (a name in common, its point in or by its area) given these names too, else a water of
# its own, at its point (waters.json: no area, drawn as a mark at any scale)
PASSAGES_FILE = ROOT / "tools" / "atlas-passages.json"  # what Wikidata gave for PASSAGES, kept
PASSAGES = [
    # Straits and channels: the seas' ways and their narrows
    ("Strait of Hormuz", ("détroit d'Hormuz",)),
    ("Bab al-Mandab Strait", ("Bab-el-Mandeb", "détroit de Bab-el-Mandeb", "Strait of Bab-el-Mandeb")),
    ("Strait of Gibraltar", ()),
    ("Strait of Malacca", ()),
    ("Strait of Dover", ("détroit du Pas-de-Calais", "Pas-de-Calais")),
    ("English Channel", ()),
    ("Bosporus", ("Bosphorus", "détroit du Bosphore")),
    ("Dardanelles", ()),
    ("Kerch Strait", ()),
    ("Strait of Messina", ()),
    ("Strait of Bonifacio", ("détroit de Bonifacio",)),
    ("Strait of Otranto", ()),
    ("Strait of Sicily", ()),
    *[(t, ()) for t in ("Øresund", "Great Belt", "Little Belt", "Fehmarn Belt", "Skagerrak", "Kattegat")],
    *[(t, ()) for t in ("North Channel (Great Britain and Ireland)", "St George's Channel")],
    *[(t, ()) for t in ("Bering Strait", "Strait of Magellan", "Drake Passage", "Beagle Channel", "Le Maire Strait")],
    *[(t, ()) for t in ("Straits of Florida", "Yucatán Channel", "Windward Passage", "Mona Passage", "Cabot Strait")],
    *[(t, ()) for t in ("Strait of Juan de Fuca", "Strait of Georgia", "Strait of Belle Isle", "Denmark Strait")],
    *[(t, ()) for t in ("Davis Strait", "Hudson Strait", "Straits of Tiran", "Mozambique Channel", "Palk Strait")],
    *[(t, ()) for t in ("Sunda Strait", "Lombok Strait", "Singapore Strait", "Makassar Strait", "Torres Strait")],
    *[(t, ()) for t in ("Taiwan Strait", "Luzon Strait", "Korea Strait", "Tsushima Strait", "Tsugaru Strait")],
    *[(t, ()) for t in ("La Pérouse Strait", "Strait of Tartary", "Bass Strait", "Cook Strait")],
    ("Lancaster Sound", ("détroit de Lancaster",)),  # (the North-West Passage's way in)
    # Canals: the ways ships go through the land
    *[(t, ()) for t in ("Suez Canal", "Panama Canal", "Kiel Canal", "Corinth Canal")],
]
# Cities Natural Earth has under their name of today, by their country and that name (folded):
# their former names, in the page's languages (Leningrad, Saïgon, Bombay, Pékin)
OLD_NAMES = {
    ("RUS", "st petersburg"): (
        "Petrograd",
        "Pétrograd",
        "Pietrogrado",
        "Petrogrado",
        "Leningrad",
        "Léningrad",
        "Leningrado",
    ),
    ("RUS", "volgograd"): ("Stalingrad", "Stalingrado", "Tsaritsyne", "Tsaritsyn", "Zarizyn"),
    ("VNM", "ho chi minh city"): ("Saïgon", "Saigon", "Saigón"),
    ("IND", "mumbai"): ("Bombay", "Bombaim"),
    ("IND", "chennai"): ("Madras",),
    ("IND", "kolkata"): ("Calcutta", "Calcutá", "Kalkutta"),
    ("CHN", "beijing"): ("Pékin", "Peking", "Pequim", "Pechino", "Pekín"),
    ("CHN", "guangzhou"): ("Canton", "Kanton", "Cantão", "Cantón"),
    ("CHN", "nanjing"): ("Nankin", "Nanking", "Nanquim", "Nanchino"),
    ("COD", "kinshasa"): ("Léopoldville", "Leopoldville"),
    ("ZWE", "harare"): ("Salisbury",),
    ("MMR", "yangon"): ("Rangoun", "Rangoon", "Rangun"),
    ("POL", "gdansk"): ("Dantzig", "Danzig", "Dánzig", "Danzica"),
    ("POL", "wroclaw"): ("Breslau", "Breslavia"),
    ("RUS", "kaliningrad"): ("Königsberg", "Kœnigsberg", "Konigsberg"),
    ("SVK", "bratislava"): ("Presbourg", "Pressburg", "Presburgo"),
    ("UKR", "lviv"): ("Lemberg", "Lwów", "Lvov", "Léopol"),
    ("UKR", "kyiv"): ("Kiev", "Kiew", "Kíev"),
    ("KAZ", "almaty"): ("Alma-Ata",),
    ("MOZ", "maputo"): ("Lourenço Marques",),
}
# The borders of past years (a map's `year`): OpenHistoricalMap's states (CC0) as they were on
# each layer's day, as its database stood on OHM_DATE (the same atlas whatever day it is made).
# The land it leaves to no state filled by historical-basemaps' states (André Ourednik,
# GPL-3.0, at a fixed commit, its licence shipped): Africa's and Asia's states before their
# colonisation, a state OHM lacks (Egypt in 1914, two of Germany's zones). Their names from
# Wikidata (CC0), kept in BORDERS_FILE
OHM = "https://overpass-api.openhistoricalmap.org/api/interpreter"
OHM_DATE = "2026-11-01T00:00:00Z"
BORDERS_COMMIT = "4b5039e50d8d2464b065bd76ad6086cd4597108d"
BORDERS_SOURCE = f"https://raw.githubusercontent.com/aourednik/historical-basemaps/{BORDERS_COMMIT}/"
BORDERS_YEARS = (1815, 1880, 1900, 1914, 1920, 1930, 1938, 1945, 1960, 1994)  # its layers, the nearest one read
BORDERS_FILE = ROOT / "tools" / "atlas-borders.json"  # what Wikidata gave for the states, kept
# Each layer: the day its borders are taken on, and the years it stands for; another year has none
LAYERS = {
    1815: ("1815-07-01", 1815, 1858),  # the Congress of Vienna's Europe
    1866: ("1866-01-01", 1859, 1870),  # Italy made, Germany not yet
    1880: ("1880-07-01", 1871, 1884),  # after Germany's unity, before Africa's partition
    1900: ("1900-07-01", 1885, 1913),  # Africa partitioned
    1914: ("1914-07-01", 1914, 1918),
    1925: ("1925-07-01", 1919, 1937),  # between the wars
    1938: ("1938-07-01", 1938, 1938),  # after the Anschluss, before Munich
    1942: ("1942-07-01", 1939, 1944),  # Europe under Germany, Asia under Japan
    1946: ("1946-07-01", 1945, 1948),  # Germany's four zones
    1960: ("1960-07-01", 1949, 1974),  # the Cold War, Africa's independence
    1985: ("1985-07-01", 1975, 1991),
}
# The states that ruled others, each by the names a colony's sources give it (OHM's
# colony_of, Wikidata's "part of" and "country", historical-basemaps' SUBJECTO or brackets:
# "Algeria (FR)"), the first word of a colony's name ("British Raj") last of each
EMPIRES = (
    (
        "United Kingdom of Great Britain and Ireland",
        "United Kingdom",
        "British Empire",
        "Britain",
        "Great Britain",
        "GB",
        "UK",
        "UK Lybia",
        "British",
    ),
    (
        "France",
        "French Republic",
        "Kingdom of France",
        "French State",
        "French Empire",
        "Second French Empire",
        "French Third Republic",
        "Bourbon Restoration in France",
        "July Monarchy",
        "Vichy France",
        "French Fourth Republic",
        "French colonial empire",
        "French Union",
        "Overseas France",
        "FR",
        "Frech Lybia",
        "French",
    ),
    ("German Empire", "German Reich", "Germany", "Nazi Germany", "Weimar Republic", "German colonial empire", "German"),
    ("Kingdom of Italy", "Italy", "Fascist Italy", "Italian Empire", "Italian colonial empire", "IT", "Italian"),
    ("Portugal", "Kingdom of Portugal", "First Portuguese Republic", "Estado Novo", "Portuguese Empire", "Portuguese"),
    ("Spain", "Kingdom of Spain", "Spanish Empire", "Spanish"),
    ("Kingdom of the Netherlands", "Netherlands", "United Kingdom of the Netherlands", "Dutch Empire", "Dutch"),
    ("Belgium", "Belgian Empire", "Belgian"),
    ("Empire of Japan", "Japan", "Japanese"),
    ("United States", "United States of America", "USA", "US", "American"),
    ("Russian Empire", "Russia", "Russian"),
    ("Soviet Union", "USSR", "Soviet"),
    ("Denmark", "Kingdom of Denmark", "Danish"),
    ("Ottoman Empire", "Ottoman"),
    ("Union of South Africa", "South Africa"),
    ("New Zealand", "Dominion of New Zealand"),
)
# What OHM calls a state of its own (its place or border_type): Wikidata's "country" never
# makes it a colony (Brazil, the Portuguese Empire's once). (Not a federation: most were a
# colony's, French West Africa's, Indochina's)
SOVEREIGN = {"country", "nation", "kingdom", "empire", "republic", "grand_duchy", "principality"}
# A land a state ruled named as a whole that is two countries today (Korea, Japan's), by the
# English name of either
WHOLE = dict.fromkeys(("North Korea", "South Korea"), "Corée|Korea|Corea|Coreia")
# OHM's colonies that say nowhere whose they were (no colony_of, no Wikidata item)
RULED = {
    "Indochinese Union": "France",
    "Indochinese Federation": "France",
    "Philippine Executive Commission": "Japan",
}
# historical-basemaps' names that are not Wikipedia's articles (where their names come from)
ARTICLES = {
    "Germany (Soviet)": "Soviet occupation zone in Germany",
    "Germany (USA)": "American occupation zone in Germany",
    "Germany (UK)": "British occupation zone in Germany",
    "Germany (France)": "French occupation zone in Germany",
    "Arabia (Nejd)": "Emirate of Nejd and Hasa",
    "Abyssinia": "Ethiopian Empire",
    "Persia": "Qajar Iran",
}
# Wikidata's items OHM gives a past state that stand for another one before a year: the
# names of the article given instead (China's republic before 1949 given Taiwan's)
ITEMS = {"Q865": (1949, "Republic of China (1912–1949)")}
# The short names a state goes by (a page's « URSS », « RDA », « Allemagne » in 1914), by its
# English name (Wikidata's)
GERMANY = "Allemagne|Germany|Deutschland|Alemania|Germania|Alemanha"
RUSSIA = "Russie|Russia|Russland|Rusia|Rússia"
ITALY = "Italie|Italy|Italien|Italia|Itália"
AUSTRIA = "Autriche|Austria|Österreich|Áustria"
POLAND = "Pologne|Poland|Polen|Polonia|Polônia|Polónia"
SOVIET = "URSS|USSR|UdSSR|SSSR|Union soviétique|Soviet Union"
CZECHOSLOVAKIA = "Tchécoslovaquie|Czechoslovakia|Tschechoslowakei|Checoslovaquia|Cecoslovacchia|Checoslováquia"
YUGOSLAVIA = "Yougoslavie|Yugoslavia|Jugoslawien|Iugoslavia|Jugoslávia"
BRITAIN = "Royaume-Uni|United Kingdom|Vereinigtes Königreich|Reino Unido|Regno Unito|Grande-Bretagne|Great Britain"
TURKEY = "Turquie|Turkey|Türkei|Turquía|Turchia|Turquia"
CHINA = "Chine|China|Cina"
JAPAN = "Japon|Japan|Japón|Giappone|Japão"
FRANCE = "France|Frankreich|Francia|França"
INDOCHINA = "Indochine française|Indochine|French Indochina|Indochina|Französisch-Indochina|Indochina francesa"
NETHERLANDS = "Pays-Bas|Netherlands|Niederlande|Países Bajos|Paesi Bassi|Países Baixos|Hollande|Holland"
ALSO = {
    "German Empire": GERMANY,
    "Russian Empire": RUSSIA,
    "Soviet Union": SOVIET,
    "Kingdom of Italy": ITALY,
    "Fascist Italy": ITALY,
    "Kingdom of Serbs, Croats and Slovenes": YUGOSLAVIA,
    "Indochinese Union": INDOCHINA,
    "Indochinese Federation": INDOCHINA,
    "United Kingdom of the Netherlands": NETHERLANDS,
    "Kingdom of the Netherlands": NETHERLANDS,
    "People's Republic of China": CHINA,
    "Bourbon Restoration in France": FRANCE + "|Royaume de France",
    "Second French Empire": FRANCE + "|Second Empire",
    "French Third Republic": FRANCE,
    "Vichy France": FRANCE + "|France de Vichy|régime de Vichy|État français",
    "French Fourth Republic": FRANCE,
    "German Reich": GERMANY + "|Reich|Troisième Reich|Third Reich|Drittes Reich|république de Weimar|Weimar Republic"
    "|Weimarer Republik|República de Weimar|Repubblica di Weimar",  # (one item from 1919 to 1945)
    "Japan": JAPAN,
    "Polish People's Republic": POLAND,
    "Austrian Empire": AUSTRIA,
    "Kingdom of Prussia": "Prusse|Prussia|Preußen|Prusia|Prússia",
    "United Kingdom of Great Britain and Ireland": BRITAIN,
    "United Kingdom": BRITAIN,
    "Ottoman Empire": "Empire turc|Turquie",
    "Turkey": TURKEY,
    "Empire of Japan": JAPAN,
    "Qing dynasty": CHINA + "|Empire chinois",
    "Republic of China (1912–1949)": CHINA,
    "Second Polish Republic": POLAND,
    "First Czechoslovak Republic": CZECHOSLOVAKIA,
    "Czechoslovak Socialist Republic": CZECHOSLOVAKIA,
    "Third Czechoslovak Republic": CZECHOSLOVAKIA,
    "Kingdom of Yugoslavia": YUGOSLAVIA,
    "Federal People's Republic of Yugoslavia": YUGOSLAVIA,
    "Socialist Federal Republic of Yugoslavia": YUGOSLAVIA,
    "East Germany": "RDA|GDR|DDR|Allemagne de l'Est|Ostdeutschland|Germania Est",
    "West Germany": "RFA|FRG|BRD|Allemagne de l'Ouest|Westdeutschland|Germania Ovest",
    "Soviet occupation zone in Germany": "zone soviétique|zone d'occupation soviétique|Soviet zone"
    "|Soviet occupation zone|sowjetische Besatzungszone|SBZ|zona soviética|zona sovietica",
    "American occupation zone in Germany": "zone américaine|zone d'occupation américaine|American zone|US zone"
    "|amerikanische Besatzungszone|zona americana|zona estadounidense",
    "British occupation zone in Germany": "zone britannique|zone d'occupation britannique|British zone"
    "|britische Besatzungszone|zona británica|zona britannica|zona britânica",
    "French occupation zone in Germany": "zone française|zone d'occupation française|French zone"
    "|französische Besatzungszone|zona francesa|zona francese",
}
CITIES = 15  # per country, the most populated, its capital too
NOTABLE = 3  # and the cities Natural Earth ranks this notable or more (Vladivostok), wherever they are
TOLERANCE = 0.03  # degrees: a point closer than this to the line it would cut away goes
SMALLEST = 0.02  # square degrees: smaller islands left out, unless they are the country itself
SCALE = 100  # coordinates kept as integers, in hundredths of a degree (about 1 km)
NEAR = 3  # degrees: a country's rings this near its largest one are framed with it (Corsica, not the Canaries)
FAR = 0.8  # degrees: a past state's land farther from its own, on another country, a land it ruled (Korea, Japan's)


def _letters() -> dict[str, str]:
    """Each lower-case Latin letter with a mark, as its plain letters ("é": "e", "œ": "oe"):
    the one table both folds use (this one, lib.typ's: given in atlas.json), Typst having no
    Unicode decomposition."""
    table = {"œ": "oe", "æ": "ae", "ß": "ss", "ø": "o", "ł": "l", "đ": "d", "ħ": "h", "ı": "i", "ŀ": "l"}
    for code in range(0xC0, 0x250):
        letter = chr(code)
        if letter != letter.lower() or letter in table:
            continue
        plain = unicodedata.normalize("NFKD", letter).encode("ascii", "ignore").decode()
        if plain and plain != letter:
            table[letter] = plain
    return table


LETTERS = _letters()


def fold(text: str) -> str:
    """A name as it is looked for (lib.typ's fold, the same): lower case, its marked letters
    plain (LETTERS), its hyphens, apostrophes and dots spaces, its spaces single."""
    plain = "".join(LETTERS.get(c, c) for c in text.lower())
    return re.sub(r"\s+", " ", re.sub(r"[-'’.]", " ", plain)).strip()


def simplified(points: list, tolerance: float) -> list:
    """Douglas-Peucker: the points a line keeps when those nearer than `tolerance` to the
    chord between its ends go (a ring's ends both kept)."""
    if len(points) < 3:
        return points
    (x0, y0), (x1, y1) = points[0], points[-1]
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    far, at = 0.0, 0
    for i, (x, y) in enumerate(points[1:-1], start=1):
        d = abs(dy * x - dx * y + x1 * y0 - y1 * x0) / length if length else math.hypot(x - x0, y - y0)
        if d > far:
            far, at = d, i
    if far <= tolerance:
        return [points[0], points[-1]]
    return simplified(points[: at + 1], tolerance)[:-1] + simplified(points[at:], tolerance)


def area(ring: list) -> float:
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1], strict=True))) / 2


def outline(geometry: dict) -> list:
    """A country's outer rings, simplified, its tiny islands left out (all of them kept for
    an island country, its largest at least)."""
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    rings = one_side([polygon[0] for polygon in polygons])
    largest = max(area(r) for r in rings)
    kept = []
    for ring in rings:
        if area(ring) < SMALLEST and area(ring) < largest:
            continue
        # The ring split at its farthest point from its start: both halves simplified
        far = max(range(len(ring)), key=lambda i: math.hypot(ring[i][0] - ring[0][0], ring[i][1] - ring[0][1]))
        points = simplified(ring[: far + 1], TOLERANCE)[:-1] + simplified(ring[far:], TOLERANCE)
        if len(points) >= 4:
            kept.append([[round(x * SCALE), round(y * SCALE)] for x, y in points[:-1]])
    return kept


def one_side(rings: list) -> list:
    """Rings across the 180th meridian (Russia's far east, the Aleutians, Fiji): the smaller
    side moved by 360° to the larger's, the place in one piece (its frame not the whole world)."""
    if rings and max(x for r in rings for x, _ in r) - min(x for r in rings for x, _ in r) > 300:
        east = sum(area(r) for r in rings if sum(x for x, _ in r) > 0)
        west = sum(area(r) for r in rings if sum(x for x, _ in r) < 0)
        move = (lambda x: x - 360) if east < west else (lambda x: x + 360)
        rings = [[[move(x), y] for x, y in r] if (sum(x for x, _ in r) > 0) == (east < west) else r for r in rings]
    return rings


def box(rings: list) -> list[int]:
    xs = [x for ring in rings for x, _ in ring]
    ys = [y for ring in rings for _, y in ring]
    return [min(xs), min(ys), max(xs), max(ys)]


def main(rings: list) -> list:
    """The rings a country's map frames: its largest and those near it (France with Corsica,
    not French Guiana nor Réunion)."""
    (x0, y0, x1, y1) = box([max(rings, key=area)])

    def gap(ring: list) -> int:  # how far its box is from the largest's, on either axis
        (a0, b0, a1, b1) = box([ring])
        return max(a0 - x1, x0 - a1, b0 - y1, y0 - b1, 0)

    return [r for r in rings if gap(r) <= NEAR * SCALE]


def names(properties: dict, own: str, *more: str) -> list[str]:
    """A place's names, the page's languages first (in LANGUAGES' order), its own, distinct."""
    found = [properties.get(f"NAME_{lang}") or properties.get(f"name_{lang.lower()}") or "" for lang in LANGUAGES]
    return list(dict.fromkeys(n.strip() for n in [*found, own, *more] if n and n.strip()))


def download(name: str, folder: Path | None = None, url: str | None = None) -> dict:
    """A JSON file, from `folder` when it has it (by that name), else from its URL (Natural
    Earth's, by default)."""
    if folder and (folder / name).is_file():
        return json.loads((folder / name).read_text(encoding="utf-8"))
    request = urllib.request.Request(url or SOURCE + name, headers={"User-Agent": "notosaurus-atlas (tools/atlas.py)"})
    for wait in (10, 30, 60, 0):  # Wikipedia's and Wikidata's APIs ask to wait when asked too often (429)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as e:
            if e.code != 429 or not wait:
                raise
            time.sleep(wait)
    raise AssertionError("unreachable")


def download_text(name: str, folder: Path | None, url: str) -> str:
    """A text file, from `folder` when it has it (by that name), else from its URL."""
    if folder and (folder / name).is_file():
        return (folder / name).read_text(encoding="utf-8")
    request = urllib.request.Request(url, headers={"User-Agent": "notosaurus-atlas (tools/atlas.py)"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8")


def usual_names(folder: Path | None = None) -> dict[str, list[str]]:
    """Each country's usual names in the page's languages, by its two-letter code (CLDR):
    its short and variant ones too ("UK", "Birmanie"); the world's parts' by their M49 code
    ("030": Asie orientale)."""
    found: dict[str, list[str]] = defaultdict(list)
    for lang in CLDR_LANGUAGES:
        data = download(f"cldr-{lang}.json", folder, CLDR.format(lang))
        for key, name in data["main"][lang]["localeDisplayNames"]["territories"].items():
            code = key.split("-alt-")[0]
            if (len(code) == 2 and code.isalpha()) or (len(code) == 3 and code.isdigit()):  # (M49's: "030")
                found[code].append(name)
    return found


def history(folder: Path | None = None, refresh: bool = False) -> list[dict]:
    """HISTORY's places, as HISTORY_FILE keeps them; from Wikidata when `refresh` (then kept)."""
    return kept_places(HISTORY, HISTORY_FILE, "wikidata", folder, refresh)


def passages(folder: Path | None = None, refresh: bool = False) -> list[dict]:
    """PASSAGES' straits, channels and canals, as PASSAGES_FILE keeps them; from Wikidata when
    `refresh` (then kept)."""
    return kept_places(PASSAGES, PASSAGES_FILE, "wikidata-passages", folder, refresh)


def kept_places(listed: list, file: Path, prefix: str, folder: Path | None, refresh: bool) -> list[dict]:
    """A list's places (its articles' titles, their names Wikidata lacks), as `file` keeps
    them; from Wikidata when `refresh` (then kept); the places added to the list since, asked
    alone, the others kept as they were."""
    titles = [t for t, _ in listed]
    if not refresh:
        before = {p["title"]: p for p in json.loads(file.read_text(encoding="utf-8"))}
        new = [(t, more) for t, more in listed if t not in before]
        if not new and list(before) == titles:
            return [{"n": before[t]["n"], "xy": tuple(before[t]["xy"])} for t in titles]
        found = dict(zip([t for t, _ in new], wikidata_places(new, prefix + "-new", None) if new else [], strict=True))
        places = [found[t] if t in found else {"n": before[t]["n"], "xy": tuple(before[t]["xy"])} for t in titles]
    else:
        places = wikidata_places(listed, prefix, folder)
    kept = [{"title": t, "n": p["n"], "xy": list(p["xy"])} for t, p in zip(titles, places, strict=True)]
    file.write_text(json.dumps(kept, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return places


def wikidata_places(listed: list, prefix: str, folder: Path | None = None) -> list[dict]:
    """A list's places from Wikidata: (names, (longitude, latitude)) each, the names it gives
    in the page's languages then the list's own."""
    titles = [t for t, _ in listed]
    entities: dict[str, dict] = {}
    for start in range(0, len(titles), 45):  # the API's most per call: 50
        batch = titles[start : start + 45]
        query = urllib.parse.urlencode(
            {
                "action": "wbgetentities",
                "sites": "enwiki",
                "titles": "|".join(batch),
                "props": "labels|claims|sitelinks",
                "languages": "fr|en|de|es|it|pt|pt-br",
                "sitefilter": "enwiki",
                "redirects": "yes",
                "format": "json",
            }
        )
        data = download(f"{prefix}-{start}.json", folder, f"{WIKIDATA}?{query}")
        for entity in data["entities"].values():
            if "missing" not in entity:
                entities[entity["sitelinks"]["enwiki"]["title"]] = entity
    places = []
    for title, more in listed:
        entity = entities.get(title)
        if entity is None:
            raise SystemExit(f"Wikidata has no place for the article {title!r}")
        point = entity["claims"]["P625"][0]["mainsnak"]["datavalue"]["value"]
        labels = [
            entity["labels"][lang]["value"]
            for lang in ("fr", "en", "de", "es", "it", "pt-br", "pt")
            if lang in entity["labels"]
        ]
        places.append({"n": list(dict.fromkeys([*labels, *more])), "xy": (point["longitude"], point["latitude"])})
    return places


def overpass(name: str, folder: Path | None, query: str) -> dict:
    """What OpenHistoricalMap's Overpass answers `query` (as its database stood on OHM_DATE),
    from `folder` when it has it (by that name), else asked, then kept there: a layer's
    states are some 150 MB."""
    if folder and (folder / name).is_file():
        return json.loads((folder / name).read_text(encoding="utf-8"))
    query = f'[out:json][timeout:900][date:"{OHM_DATE}"];{query}'
    request = urllib.request.Request(
        OHM, data=urllib.parse.urlencode({"data": query}).encode(), headers={"User-Agent": "notosaurus-atlas"}
    )
    for wait in (30, 60, 120, 0):  # (busy: 429, or 504 when its queue is full)
        try:
            with urllib.request.urlopen(request, timeout=1200) as response:
                raw = response.read()
            break
        except urllib.error.HTTPError as e:
            if e.code not in (429, 504) or not wait:
                raise
            time.sleep(wait)
    if folder:
        (folder / name).write_bytes(raw)
    return json.loads(raw)


def on(tags: dict, day: str) -> bool:
    """Whether an OHM state was on `day` (its dates as OHM writes them: "1914", "1914-09")."""
    start, end = tags.get("start_date", ""), tags.get("end_date", "")
    return bool(start) and start[:10] <= day and (not end or end[:10] > day)


def bare(name: str) -> str:
    """A name without the years OHM writes after it: « Japan (1953-1968) »."""
    return re.sub(r"\s*\(\d{4}\s*[-–]\s*(\d{4})?\)$", "", name)


def bare_hb(name: str) -> str:
    """A name of historical-basemaps without its ruler in brackets: « Senegal (FR) »."""
    return re.sub(r"\s*\([^()]*\)$", "", name)


def english(tags: dict) -> str:
    return bare(tags.get("name:en") or tags.get("name") or "")


def ohm_shapes(data: dict) -> list[tuple[dict, object]]:
    """Each OHM state's tags and shape: its outer ways' polygons, its inner ones taken away,
    simplified to a tenth of what the atlas keeps."""
    found = []
    for relation in data["elements"]:
        lines: dict[str, list] = {"outer": [], "inner": []}
        for member in relation.get("members", []):
            if member["type"] == "way" and len(member.get("geometry") or []) >= 2:
                points = [(p["lon"], p["lat"]) for p in member["geometry"]]
                lines["inner" if member.get("role") == "inner" else "outer"].append(shapely.LineString(points))
        outer, inner = (shapely.union_all(list(polygonize(shapely.union_all(ls)))) for ls in lines.values())
        made = shapely.make_valid(outer.difference(inner) if not inner.is_empty else outer)
        made = shapely.make_valid(made.simplify(TOLERANCE / 10))
        if not made.is_empty:
            found.append((relation["tags"], made))
    return found


def wikidata_items(folder: Path | None, refresh: bool, ids: set[str], titles: set[str]) -> dict:
    """The states' Wikidata items (by their Q-ids: their names in the page's languages,
    English, and the English names of what Wikidata says they were part of and the country
    they were in) and historical-basemaps' states' names (by their Wikipedia article), as
    BORDERS_FILE keeps them; the missing ones asked (all of them when `refresh`), then kept."""
    kept = {} if refresh or not BORDERS_FILE.is_file() else json.loads(BORDERS_FILE.read_text(encoding="utf-8"))
    items, articles = kept.get("items", {}), kept.get("articles", {})
    if set(items) == ids and set(articles) == titles:
        return {"items": items, "articles": articles}
    items, articles = {q: items[q] for q in ids & set(items)}, {t: articles[t] for t in titles & set(articles)}

    def entities(asked: list[str], props: str, name: str) -> dict:
        found = {}
        for start in range(0, len(asked), 45):  # the API's most per call: 50
            query = urllib.parse.urlencode(
                {
                    "action": "wbgetentities",
                    "ids": "|".join(asked[start : start + 45]),
                    "props": props,
                    "languages": "fr|en|de|es|it|pt|pt-br",
                    "format": "json",
                }
            )
            found |= download(f"{name}-{start}.json", folder, f"{WIKIDATA}?{query}").get("entities", {})
        return found

    def labels(entity: dict) -> list[str]:
        said = entity.get("labels", {})
        return list(
            dict.fromkeys(said[lang]["value"] for lang in ("fr", "en", "de", "es", "it", "pt-br", "pt") if lang in said)
        )

    def claimed(entity: dict, prop: str) -> list[str]:
        values = [c["mainsnak"].get("datavalue", {}).get("value", {}) for c in entity.get("claims", {}).get(prop, [])]
        return [v["id"] for v in values if isinstance(v, dict) and "id" in v]

    asked = sorted(ids - set(items))
    found = entities(asked, "labels|claims", "wikidata-states") if asked else {}
    linked = sorted({q for e in found.values() for p in ("P361", "P17") for q in claimed(e, p)})
    linked_names = entities(linked, "labels", "wikidata-linked") if linked else {}

    def in_english(q: str) -> str:
        return linked_names.get(q, {}).get("labels", {}).get("en", {}).get("value", "")

    for q in asked:
        entity = found.get(q, {})
        items[q] = {
            "n": labels(entity),
            "en": entity.get("labels", {}).get("en", {}).get("value", ""),
            "part": [n for n in map(in_english, claimed(entity, "P361")) if n],
            "country": [n for n in map(in_english, claimed(entity, "P17")) if n and q not in claimed(entity, "P17")],
        }
    # historical-basemaps' states: each article's item, past its redirect (Wikipedia's API)
    asked_titles = sorted(titles - set(articles))
    for start in range(0, len(asked_titles), 45):
        batch = asked_titles[start : start + 45]
        query = urllib.parse.urlencode(
            {"action": "query", "prop": "pageprops", "ppprop": "wikibase_item", "redirects": 1}
            | {"titles": "|".join(batch), "format": "json"}
        )
        pages = download(f"wikipedia-borders-{start}.json", folder, f"{WIKIPEDIA}?{query}")["query"]
        moved = {r["from"]: r["to"] for r in pages.get("normalized", []) + pages.get("redirects", [])}
        of = {p["title"]: p["pageprops"]["wikibase_item"] for p in pages["pages"].values() if "pageprops" in p}
        named = entities(sorted(set(of.values())), "labels", f"wikidata-articles-{start}") if of else {}
        for title in batch:
            target = title
            while target in moved:
                target = moved[target]
            articles[title] = labels(named.get(of.get(target, ""), {})) or [title]
    BORDERS_FILE.write_text(
        json.dumps({"items": items, "articles": articles}, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"items": items, "articles": articles}


def empire_of(name: str) -> int | None:
    """Which of EMPIRES a name says (a whole name, else a name's first word: « British »)."""
    for i, said in enumerate(EMPIRES):
        if name in said[:-1]:
            return i
    first = name.split(" ")[0]
    return next((i for i, said in enumerate(EMPIRES) if first == said[-1]), None)


def name_state(state: dict, year: int, named: dict, today: dict) -> dict:
    """A state's names (Wikidata's, OHM's, ALSO's, today's country's of the same name), the
    empire it is (EMPIRES) and what says the empire it belonged to ("said")."""
    tags = state.get("tags", {})
    until, instead = ITEMS.get(tags.get("wikidata", ""), (0, ""))
    item = named["items"].get(tags.get("wikidata", ""), {}) if year >= until else {}
    name = state.get("name", "")
    title = instead if year < until else ARTICLES.get(name, bare_hb(name))
    own = str(item.get("en") or title or english(tags))
    said = item.get("n", []) if item else named["articles"].get(title, [])
    given = [bare(tags.get(f"name:{lang.lower()}", "")) for lang in LANGUAGES]
    given += [english(tags), bare(tags.get("name", "")), name]
    also = ALSO.get(own, "").split("|")
    now = today.get(tags.get("wikidata", "-"), []) if year >= until else []  # (not Taiwan's for China's of 1942)
    all_names = [*said, *given, *also, *today.get(fold(own), []), *now]
    state["n"] = list(dict.fromkeys(n.strip() for n in all_names if n and n.strip()))
    whole = [empire_of(n) for n in (own, english(tags)) if n and n in {m for e in EMPIRES for m in e[:-1]}]
    state["is"] = whole[0] if whole else None
    if tags:
        # who it belonged to: OHM's colony_of (unless it says it was a country, no colony: Kenya
        # in 1985), Wikidata's "part of", its name, Wikidata's "country" (never a state's of its
        # own: Wikidata's are often today's)
        sovereign = bool({tags.get("place"), tags.get("border_type")} & SOVEREIGN)
        free = tags.get("place") == "country" and tags.get("border_type") in (None, *SOVEREIGN)
        state["said"] = [RULED.get(english(tags), ""), "" if free else tags.get("colony_of", "")]
        state["said"] += [] if sovereign else item.get("part", [])
        state["said"] += [own, english(tags), *([] if sovereign else item.get("country", []))]
    else:
        bracket = re.search(r"\(([^()]+)\)$", state.get("name", ""))
        subject = state.get("subject", "")
        state["said"] = [subject if subject != state.get("name") else "", bracket.group(1) if bracket else ""]
    return state


def ruled_by(state: dict, present: set) -> int | None:
    """The empire (EMPIRES) a state belonged to, among those that are a state that year: the
    first its sources say ("said"), never the one it is."""
    for said in state.get("said", []):
        empire = empire_of(said) if said else None
        if empire is not None and empire != state["is"] and empire in present:
            return empire
    return None


def past_states(year: int, data: dict, extra: dict, named: dict, today: dict, nations: list) -> dict:
    """A year's states, as the atlas's countries (their names, keys, frames and rings; "o" the
    state a colony belonged to): OHM's (`data`), one state each (its parts joined by their
    Wikidata item), a smaller one taken from a larger one it lies in (Manchukuo from China,
    a colony from the federation it was part of), cut to the land; a state's land far from its
    own on another of today's countries (a tenth of it at least), a land it ruled named as that country (Algeria,
    France's departments; Angola, Portugal's province); the land left to none, a state of
    historical-basemaps (`extra`) lying in it at least by half (joined to OHM's state of the
    same name: its part OHM lacks); the rest drawn, nameless. `nations`: today's countries'
    names and land (Natural Earth's)."""
    day = LAYERS[year][0]
    by_key: dict[str, list] = defaultdict(list)
    for tags, made in ohm_shapes(data):
        if on(tags, day):
            by_key[tags.get("wikidata") or english(tags)].append((tags, made))
    land = shapely.union_all([nation for _, nation in nations])
    nations_tree = shapely.STRtree([nation for _, nation in nations])
    coast = land.buffer(0.1)  # (OHM's states reach into the sea, some: their waters)
    states = []
    for key, found in by_key.items():
        tags = max(found, key=lambda f: f[1].area)[0]
        made = shapely.make_valid(shapely.union_all([m for _, m in found]).intersection(coast))
        if not made.is_empty:
            states.append({"key": key, "tags": tags, "shape": made, "size": made.area})
    for state in states:
        name_state(state, year, named, today)
    # a state lying in a larger one taken from it (Manchukuo from China), unless both are the
    # same empire's lands: a colony in the federation it belonged to (Upper Senegal and Niger,
    # Mauritania in French West Africa) leaves the federation whole
    present = {s["is"] for s in states if s["is"] is not None}
    empires = [ruled_by(s, present) for s in states]
    tree = shapely.STRtree([s["shape"] for s in states])
    for n, state in enumerate(states):
        inside = [
            states[i]["shape"]
            for i in tree.query(state["shape"])
            if states[i]["size"] < state["size"] and (empires[i] is None or empires[i] != empires[n])
        ]
        if inside:
            state["shape"] = shapely.make_valid(state["shape"].difference(shapely.union_all(inside)))
    states = [s for s in states if s["shape"].area > max(SMALLEST, s["size"] / 50)]
    # a state's land far from its own (beyond FAR of its largest part) on another of today's countries
    for i, state in enumerate(list(states)):
        pieces = [g for g in parts(state["shape"]) if g.geom_type == "Polygon"]
        if len(pieces) < 2 or not state["n"]:
            continue
        # its home: the country of today it is named as (France, not Algeria, larger), else
        # the one under its largest part
        keys = {fold(n) for n in state["n"]}
        largest = max(pieces, key=lambda g: g.area)
        home = next(
            (n for n, (now, _) in enumerate(nations) if keys & {fold(m) for m in now}),
            max(nations_tree.query(largest), key=lambda n: nations[n][1].intersection(largest).area, default=0),
        )
        # (its largest part there: metropolitan France, not Algeria; Prussia's core, its Rhineland near)
        mainland = [g for g in pieces if g.intersects(nations[home][1])]
        if not mainland:
            continue
        core = max(mainland, key=lambda g: g.area)
        far = [g for g in pieces if g.distance(core) > FAR]
        if not far:
            continue
        # each far part on the country of today most of it lies on (Spanish Sahara's on Western
        # Sahara, not on the cape of Morocco it reaches)
        on_nation: dict[int, list] = defaultdict(list)
        for g in far:
            # (the smallest of those holding most of it: Natural Earth's Morocco holds Western Sahara)
            holding = [n for n in nations_tree.query(g) if nations[n][1].intersection(g).area >= g.area / 2]
            best = min(holding, key=lambda n: nations[n][1].area, default=home)
            if best != home:
                on_nation[best].append(g)
        for n, found in on_nation.items():
            names_now, nation = nations[n]
            piece = shapely.make_valid(shapely.union_all(found))
            if piece.area >= max(nation.area / 10, SMALLEST):  # (1880's Algeria: its coast)
                # (named so unless another state goes by that name, or lies on that country and
                # holds a tenth of it: Indonesia beside Dutch New Guinea, Morocco's French
                # protectorate beside Spain's lands)
                # (its usual names: Taiwan's « Republic of China » was China's in 1942)
                taken = any(set(names_now[:2]) & set(other["n"]) for other in states if "tags" in other)
                more = any(
                    2 * (there := other["shape"].intersection(nation).area) >= other["shape"].area
                    and there >= nation.area / 10
                    for other in states
                    if other is not state and other["n"]
                )
                whole = [w for n, w in WHOLE.items() if n in names_now]
                land_names = [] if taken or more else [*whole[0].split("|"), *names_now] if whole else names_now
                states.append({"key": f"{state['key']}-{n}", "n": land_names, "shape": piece, "of": i, "said": []})
                state["shape"] = shapely.make_valid(state["shape"].difference(piece))
    # the land left to none: historical-basemaps' states
    known = {fold(n): i for i, s in enumerate(states) if "tags" in s for n in s["n"]}
    left = land.difference(shapely.union_all([s["shape"] for s in states]))
    filled = []
    for i, feature in enumerate(extra["features"]):
        name = (feature["properties"]["NAME"] or "").strip()
        if not name:
            continue
        whole = shapely.make_valid(shape(feature["geometry"]))
        within = shapely.make_valid(whole.intersection(left))
        if within.area < max(whole.area / 2, SMALLEST):
            continue
        left = left.difference(within)
        title = ARTICLES.get(name, bare_hb(name))
        same = next((known[fold(n)] for n in [name, *named["articles"].get(title, [])] if fold(n) in known), None)
        if same is not None:  # (OHM's France lacking a part of France)
            states[same]["shape"] = shapely.make_valid(states[same]["shape"].union(within))
            continue
        # named as a country of today, that country's land within it too, taken from OHM's state
        # it lies in (Egypt, the Ottoman Empire's vassal in OHM's 1880, its own state then)
        country = next((n for n, (now, _) in enumerate(nations) if fold(bare_hb(name)) in {fold(m) for m in now}), None)
        if country is not None:
            more = shapely.make_valid(whole.intersection(nations[country][1]).difference(within))
            if more.area >= SMALLEST:
                for other in states:
                    if other["shape"].intersects(more):
                        other["shape"] = shapely.make_valid(other["shape"].difference(more))
                within = shapely.make_valid(within.union(more))
        state = {"key": f"hb-{i}", "name": name, "subject": feature["properties"].get("SUBJECTO") or ""}
        states.append(name_state(state | {"shape": within}, year, named, today))
        known |= {fold(n): len(states) - 1 for n in states[-1]["n"]}  # (its parts, two states of it)
        filled.append(name)
    print(f"  {year}: {len(filled)} states of historical-basemaps on the land OHM leaves: {', '.join(sorted(filled))}")
    # a state that is most of a country of today, and that country most of it, named as it too
    # (« Hongrie » the kingdom of Hungary of 1942, « Éthiopie » the Ethiopian Empire), unless
    # another state goes by that name
    for state in states:
        for n in nations_tree.query(state["shape"]) if state["n"] else []:
            names_now, nation = nations[n]
            common = state["shape"].intersection(nation).area
            mostly = common >= 0.7 * nation.area and nation.area >= 0.5 * state["shape"].area
            if mostly and not any(set(names_now) & set(other["n"]) for other in states if other is not state):
                state["n"] = list(dict.fromkeys([*state["n"], *names_now]))
    states.append({"key": "~", "n": [], "shape": left, "said": []})  # (the land no state was given)
    for state in states:
        state.setdefault("is", None)
    order = sorted(range(len(states)), key=lambda i: states[i]["key"])
    codes = {i: f"{year}-{n}" for n, i in enumerate(order)}
    rulers: dict[int, int] = {}
    for i, state in enumerate(states):  # each empire's state: its largest
        larger = state["is"] not in rulers or states[rulers[state["is"]]]["shape"].area < state["shape"].area
        if state["is"] is not None and larger:
            rulers[state["is"]] = i
    countries = {}
    for i in order:
        state = states[i]
        polygons = [g for g in parts(state["shape"]) if g.geom_type in ("Polygon", "MultiPolygon")]
        flat = shapely.MultiPolygon([p for g in polygons for p in parts(g)])  # (no line left of a difference)
        rings = outline(json.loads(shapely.to_geojson(flat))) if not flat.is_empty else []
        if not rings:
            continue
        shapes = [shapely.make_valid(shapely.Polygon([(x / SCALE, y / SCALE) for x, y in r])) for r in rings]
        polygons_drawn = [g for s in shapes for g in parts(s) if g.geom_type == "Polygon"]
        (x0, y0, x1, y1) = box(rings)
        at = [(x0 + x1) // 2, (y0 + y1) // 2]  # (a sliver no polygon is left of: its frame's middle)
        if polygons_drawn:
            inmost = polylabel(max(polygons_drawn, key=lambda g: g.area), tolerance=0.05)
            at = [round(inmost.x * SCALE), round(inmost.y * SCALE)]
        entry = {
            "n": state["n"],
            "at": at,
            # (Wikidata's "Austria–Hungary" found as "Austria-Hungary" too)
            "k": sorted({fold(n) for n in state["n"]} | {fold(n.replace("–", "-")) for n in state["n"]}),
            "b": box(rings),
            "f": box(main(rings)),
            "r": rings,
        }
        if "of" in state:
            entry["o"] = codes[state["of"]]
        empire = None if "of" in state else ruled_by(state, set(rulers))
        if empire is not None and rulers[empire] != i:
            entry["o"] = codes[rulers[empire]]
        countries[codes[i]] = entry
    return {"year": year, "countries": countries}


def two_letters(properties: dict) -> str:
    """A country's two-letter code (ISO 3166-1), Natural Earth's own when it gives none."""
    code = properties.get("ISO_A2")
    return properties.get("ISO_A2_EH") or "" if code in (None, "-99") else code


def atlas(countries: dict, places: dict, usual: dict | None = None, past: list | None = None) -> dict:
    out_countries, codes = {}, {}
    for feature in countries["features"]:
        p = feature["properties"]
        code = p["ADM0_A3"]
        rings = outline(feature["geometry"])
        if not rings:
            continue
        all_names = names(p, p["NAME"])
        out_countries[code] = {
            "n": all_names,
            "k": sorted({fold(n) for n in all_names} | {code.lower()}),
            "b": box(rings),
            "f": box(main(rings)),
            "r": rings,
        }
        codes[code] = True
    # A dependency's holder (Greenland's, Bermuda's, French Polynesia's): "o", its code
    sovereigns = {
        p["SOVEREIGNT"]: p["ADM0_A3"]
        for f in countries["features"]
        if (p := f["properties"])["ADMIN"] == p["SOVEREIGNT"]
    }
    for feature in countries["features"]:
        p = feature["properties"]
        holder = sovereigns.get(p["SOVEREIGNT"])
        if (
            p["ADM0_A3"] in out_countries
            and holder in out_countries
            and holder != p["ADM0_A3"]
            and p["TYPE"] != "Indeterminate"
        ):
            out_countries[p["ADM0_A3"]]["o"] = holder
    # The usual names (CLDR) of a two-letter code only one country has (the Australian
    # territories have Australia's), and never a name another country already goes by
    holders: dict[str, list[str]] = defaultdict(list)
    for feature in countries["features"]:
        if feature["properties"]["ADM0_A3"] in out_countries:
            holders[two_letters(feature["properties"])].append(feature["properties"]["ADM0_A3"])
    taken = defaultdict(set)
    for code, country in out_countries.items():
        for key in country["k"]:
            taken[key].add(code)
    added: dict[str, set[str]] = defaultdict(set)
    for two, held in holders.items():
        if two and len(held) == 1:
            for name in (usual or {}).get(two, []):
                if not taken[fold(name)] - {held[0]}:
                    added[fold(name)].add(held[0])
    for key, held in added.items():
        if len(held) == 1:
            (code,) = held
            out_countries[code]["k"] = sorted(set(out_countries[code]["k"]) | {key})
    by_country: dict[str, list] = {}
    for feature in places["features"]:
        p = feature["properties"]
        code = p["ADM0_A3"]
        # (a territory too small for the countries' scale, its towns its holder's: Gibraltar,
        # Longyearbyen; chosen among its own, as a country's)
        if code in codes or p.get("SOV_A3") in codes:
            by_country.setdefault(code, []).append(p | {"_xy": feature["geometry"]["coordinates"]})
    cities = []
    for own, found in sorted(by_country.items()):
        code = own if own in codes else found[0]["SOV_A3"]
        found.sort(key=lambda p: -(p.get("POP_MAX") or 0))
        capitals = [p for p in found if p.get("ADM0CAP") == 1]
        notable = [p for p in found if (p.get("SCALERANK") or 99) <= NOTABLE]
        chosen = list({id(p): p for p in capitals + found[:CITIES] + notable}.values())
        for p in chosen:
            x, y = p["_xy"]
            (left, _, right, _) = out_countries[code]["b"]
            if x * SCALE < left - 180 * SCALE:  # on its country's side of the 180th meridian
                x += 360
            elif x * SCALE > right + 180 * SCALE:
                x -= 360
            all_names = names(p, p["NAME"])
            cities.append(
                {
                    "c": code,
                    "n": all_names,
                    "k": sorted({fold(n) for n in all_names}),
                    "x": round(x * SCALE),
                    "y": round(y * SCALE),
                    "p": p.get("POP_MAX") or 0,
                    "cap": p.get("ADM0CAP") == 1,
                }
            )
    for city in cities:  # their former names (Leningrad, Saïgon)
        for key in city["k"]:
            for old in OLD_NAMES.get((city["c"], key), ()):
                city["k"] = sorted(set(city["k"]) | {fold(old)})
    for place in past or []:
        add_place(place, cities, countries)
    return {"scale": SCALE, "letters": LETTERS, "countries": out_countries, "cities": cities}


def add_place(place: dict, cities: list[dict], countries: dict) -> None:
    """A place of history: its names added to Natural Earth's city when it is the same (one of
    its names, within 0.3°), else a city of its own, in the country it lies in (or the nearest:
    a coast); preferred ("h") among places of the same name when no country tells them apart."""
    x, y = place["xy"]
    keys = {fold(n) for n in place["n"]}
    for city in cities:
        if (
            keys & set(city["k"])
            and abs(city["x"] - x * SCALE) <= 0.3 * SCALE
            and abs(city["y"] - y * SCALE) <= 0.3 * SCALE
        ):
            city["k"] = sorted(set(city["k"]) | keys)
            city["h"] = 1
            return
    point = shapely.Point(x, y)
    shapes = [(f["properties"]["ADM0_A3"], shape(f["geometry"])) for f in countries["features"]]
    code = min(shapes, key=lambda item: item[1].distance(point))[0]
    cities.append(
        {
            "c": code,
            "n": place["n"],
            "k": sorted(keys),
            "x": round(x * SCALE),
            "y": round(y * SCALE),
            "p": 0,
            "cap": False,
            "h": 1,
        }
    )


# Rivers Natural Earth names in English or locally only, or in parts named apart (the
# Yangtze's upper course): Natural Earth's names of its parts, then its names in the page's
# languages (looked for, never shown: a label is the name the figure was given)
RIVER_NAMES = [
    (("Rhine", "Rhein", "Rhin", "Nederrijn"), ("Rhin", "Rhine", "Rhein", "Rin", "Reno")),
    (("Danube", "Donau"), ("Danube", "Donau", "Danubio", "Danúbio", "Duna", "Dunărea")),
    (("Thames",), ("Tamise", "Thames", "Themse", "Támesis", "Tamigi", "Tâmisa")),
    (
        (
            "Nile",
            "Albert Nile",
            "Victoria Nile",
            "Bahr el Jebel",
            "El Bahr el Abyad",
            "Rosetta Branch",
            "Damietta Branch",
        ),
        ("Nil", "Nile", "Nilo"),
    ),
    (("Abay", "El Bahr el Azraq"), ("Nil Bleu", "Blue Nile", "Blauer Nil", "Nilo Azul", "Nilo Azzurro")),
    (("Amazonas",), ("Amazone", "Amazon", "Amazonas", "Rio delle Amazzoni", "Rio Amazonas")),
    (
        ("Yangtze", "Chang Jiang", "Jinsha", "Tongtian"),
        (
            "Yangzi Jiang",
            "Yangzi",
            "Yangtsé",
            "Yangtze",
            "Jangtsekiang",
            "Yangtsé-Kiang",
            "Fleuve Bleu",
            "Fiume Azzurro",
        ),
    ),
    (
        ("Huang",),
        ("Fleuve Jaune", "Huang He", "Yellow River", "Gelber Fluss", "Río Amarillo", "Fiume Giallo", "Rio Amarelo"),
    ),
    (("Ganges",), ("Gange", "Ganges", "Ganga")),
    (("Mekong", "Lancang"), ("Mékong", "Mekong", "Mecong")),
    (("Dnepre", "Dnipro"), ("Dniepr", "Dnieper", "Dnipro", "Dnepr", "Dniéper", "Dnepr")),
    (("Vistula",), ("Vistule", "Vistula", "Weichsel", "Vístula", "Vistola", "Wisła")),
    (("Oder",), ("Oder", "Odra")),
    (("Elbe",), ("Elbe", "Elba", "Labe")),
    (("Tajo", "Tejo"), ("Tage", "Tagus", "Tajo", "Tejo", "Tago")),
    (("Euphrates", "Al Furat", "Firat"), ("Euphrate", "Euphrates", "Euphrat", "Éufrates", "Eufrate", "Eufrates")),
    (("Tigris", "Dicle"), ("Tigre", "Tigris", "Tigri")),
    (("St. Lawrence",), ("Saint-Laurent", "Saint Lawrence", "Sankt-Lorenz-Strom", "San Lorenzo", "São Lourenço")),
    (("Zambezi",), ("Zambèze", "Zambezi", "Sambesi", "Zambeze")),
    (("Sénégal",), ("Sénégal", "Senegal")),
    (("Severnaya Dvina",), ("Dvina septentrionale", "Northern Dvina", "Nördliche Dwina", "Dvina Septentrional")),
    (("Amu  Darya",), ("Amou-Daria", "Amu Darya", "Amudarja", "Amu Daria")),
    (("Syr  Darya",), ("Syr-Daria", "Syr Darya", "Syrdarja", "Sir Daria")),
    (("São  Francisco",), ("São Francisco", "San Francisco")),
    (("Ayeyarwady",), ("Irrawaddy", "Ayeyarwady", "Irawadi")),
    (("Salween", "Nu"), ("Salouen", "Salween", "Saluen")),
    (("Heilong Jiang", "Amur"), ("Amour", "Amur")),
    (("Orinoco",), ("Orénoque", "Orinoco", "Orinoko")),
    (("Ural",), ("Oural", "Ural")),
    (("Yenisey",), ("Ienisseï", "Yenisei", "Yenisey", "Jenissei", "Yeniséi", "Enisej")),
    (("Lena",), ("Léna", "Lena")),
    (("Neva",), ("Néva", "Neva", "Newa")),
    (("Paraná",), ("Parana", "Paraná")),
    (("Ebro",), ("Èbre", "Ebro", "Ebre")),
    (("Po",), ("Pô", "Po")),
    (("Tevere",), ("Tibre", "Tiber", "Tíber", "Tevere", "Tibre")),
    (("Mississippi",), ("Mississippi", "Misisipi")),
    (("Missouri",), ("Missouri", "Misuri")),
    (("Volga",), ("Volga", "Wolga")),
    (("Seine",), ("Seine", "Sena")),
    (("Loire",), ("Loire", "Loira")),
    (("Rhône",), ("Rhône", "Rhone", "Ródano", "Rodano", "Ródano")),
    (("Garonne",), ("Garonne", "Garona")),
    (("Meuse", "Maas"), ("Meuse", "Maas", "Mosa")),
    (("Moselle", "Mosel"), ("Moselle", "Mosel", "Mosela", "Mosella")),
]
DETAIL = 400  # a place's extent over this: the least its drawing keeps (a map draws it about 230 points wide)
TILE = 4  # degrees: a large area's name has a place in each tile this wide
RIVER_GAP = 1  # degrees: a river's parts this near each other one river (two Colorados apart)
# Reliefs Natural Earth misnames (its French name of the Apennines is the Ligurian ones'):
# their names added, as RIVER_NAMES'
RELIEF_NAMES = [
    (("APPENNINI",), ("Apennins", "Apennines", "Apennin", "Apeninos", "Appennini")),
]
# What a relief is drawn as: Natural Earth's classes
RELIEF_KINDS = {
    "Range/mtn": "mountain", "Foothills": "mountain", "Gorge": "mountain",
    "Plateau": "plateau", "Desert": "desert",
    "Plain": "plain", "Lowland": "plain", "Basin": "plain", "Valley": "plain", "Delta": "plain",
    "Wetlands": "plain", "Tundra": "plain",
    "Pen/cape": "land", "Peninsula": "land", "Isthmus": "land", "Island": "land",
    "Island group": "land", "Coast": "land", "Geoarea": "land", "Continent": "land",
}  # fmt: skip


def ints(points) -> list:
    return [[round(x * SCALE), round(y * SCALE)] for x, y in points]


def parts(geometry) -> list:
    """A shapely geometry's single parts (its polygons, its lines)."""
    return list(getattr(geometry, "geoms", [geometry])) if not geometry.is_empty else []


def tolerance(*geometries) -> float:
    """How much a drawing of these keeps: what its map can show, TOLERANCE at least (Russia's
    regions drawn coarser than France's: they are never seen at France's scale)."""
    x0, y0, x1, y1 = shapely.total_bounds(geometries)
    return max(TOLERANCE, min(max(x1 - x0, y1 - y0), 180) / DETAIL)


def area_of(geometry, simplify: float | None = None) -> dict:
    """A drawn area: its outer rings (simplified, unless it already is: `simplify` its
    tolerance; its parts too small to see left out but its largest), the places a name goes
    (each part's point farthest inside it, the largest first)."""
    detail = simplify or tolerance(geometry)
    polygons = sorted(parts(geometry.simplify(detail) if simplify is None else geometry), key=lambda g: -g.area)
    polygons = [g for g in polygons if g.geom_type == "Polygon"]
    if not polygons:
        return {}
    kept = [g for g in polygons if g.area >= (3 * detail) ** 2] or polygons[:1]
    rings = one_side([list(g.exterior.coords)[:-1] for g in kept])
    rings = [ints(r) for r in rings if len(r) >= 3]
    # Where its name goes: each part's point farthest inside; a large one's, in each tile too
    # (an ocean named wherever a map shows it)
    pieces = list(kept[:8])
    x0, y0, x1, y1 = geometry.bounds
    tile = TILE
    if max(x1 - x0, y1 - y0) > 2 * TILE:
        for i in range(math.ceil((x1 - x0) / tile)):
            for j in range(math.ceil((y1 - y0) / tile)):
                square = shapely.box(x0 + i * tile, y0 + j * tile, x0 + (i + 1) * tile, y0 + (j + 1) * tile)
                piece = max(parts(kept[0].intersection(square)), key=lambda g: g.area, default=None)
                if piece is not None and piece.geom_type == "Polygon" and piece.area >= tile * tile / 8:
                    pieces.append(piece)
    places = []
    for g in pieces:
        point = polylabel(g, tolerance=0.05)
        x = point.x + (360 if point.x < min(x for x, _ in rings[0]) / SCALE - 180 else 0)
        places.append([round(x * SCALE), round(point.y * SCALE)])
    return {"b": box(rings), "r": rings, "at": places}


def named(all_names: list[str], extra: dict) -> dict:
    return {"n": all_names, "k": sorted({fold(n) for n in all_names})} | extra


def rivers(main_rivers: dict, europe: dict) -> list:
    aliases = {fold(part): i for i, (found, _) in enumerate(RIVER_NAMES) for part in found}
    groups: dict = defaultdict(list)
    for feature in main_rivers["features"] + europe["features"]:
        p = feature["properties"]
        own = (p.get("name") or "").strip()
        if not own or p.get("featurecla") != "River" or not feature["geometry"]:
            continue
        key = aliases.get(fold(own), fold(own))
        groups[key].append((names(p, own, p.get("name_en") or ""), shape(feature["geometry"])))
    out = []
    for key, found in groups.items():
        # Its parts near each other: one river each (the Colorado of the United States, Argentina's)
        clusters: list[list] = []
        for item in found:
            near = [c for c in clusters if any(item[1].distance(other) <= RIVER_GAP for _, other in c)]
            for c in near:
                clusters.remove(c)
            clusters.append([item] + [x for c in near for x in c])
        for cluster in clusters:
            whole = shapely.line_merge(shapely.union_all([g for _, g in cluster]))
            line = whole.simplify(tolerance(whole) / 2)
            lines = one_side([list(g.coords) for g in parts(line) if len(g.coords) >= 2])
            lines = [ints(points) for points in lines]
            if not lines:
                continue
            own = [n for found_names, _ in cluster for n in found_names]
            all_names = list(dict.fromkeys(list(RIVER_NAMES[key][1]) + own if isinstance(key, int) else own))
            out.append(named(all_names, {"b": box(lines), "l": lines, "len": round(line.length * 10)}))
    return out


def reliefs(regions: dict) -> list:
    added = {fold(part): more for found, more in RELIEF_NAMES for part in found}
    out = []
    for feature in regions["features"]:
        p = feature["properties"]
        kind = RELIEF_KINDS.get(p.get("FEATURECLA"))
        drawn = area_of(shape(feature["geometry"])) if kind and feature["geometry"] else {}
        if drawn:
            more = added.get(fold(p["NAME"]), ())
            all_names = list(dict.fromkeys([*more, *names(p, p["NAME"], p.get("NAMEALT") or "")]))
            out.append(named(all_names, drawn | {"c": kind}))
    return out


# Seas' and oceans' short names that their long ones don't give (water_keys does the rest:
# "Méditerranée", "Atlantic"), by Natural Earth's English name
WATER_NAMES = {
    "Atlantic Ocean": ("Atlantik",),
    "Pacific Ocean": ("Pazifik",),
    "Indian Ocean": ("Indik",),
    "Adriatic Sea": ("Adria",),
    "Aegean Sea": ("Ägäis",),
    "Caribbean Sea": ("Caraïbes", "Karibik", "Caribe", "mar do Caribe", "Caraibi", "mar dei Caraibi"),
    "English Channel": ("Manica", "Mancha"),
    "Laptev Sea": ("mer des Laptev",),  # (the French say both)
    "Baffin Bay": ("baie de Baffin",),
}
_GENERIC = ("mer ", "ocean ", "oceano ", "mar ", "mare ", "la ")  # folded, before a sea's own name
_LINKS = {"du", "de", "des", "d", "of", "del", "dei", "della", "do", "da", "das", "dos", "di", "degli"}


def water_keys(all_names: list[str]) -> set[str]:
    """A sea's names as a lesson writes them, short: without "mer", "océan", "mar", "oceano"
    ahead or "Sea", "Ocean" behind ("Méditerranée", "Atlantique", "Pacific"), unless what is
    left starts with a link ("mer du Nord"), and WATER_NAMES'."""
    keys = set()
    for name in all_names:
        key = fold(name)
        for generic in _GENERIC:
            rest = key.removeprefix(generic)
            if rest != key and rest and rest.split()[0] not in _LINKS:
                keys.add(rest)
        for generic in (" ocean", " sea"):
            if key.endswith(generic) and key != generic.strip():
                keys.add(key.removesuffix(generic))
        keys |= {fold(n) for n in WATER_NAMES.get(name, ())}
    return keys


PASSAGE_NEAR = 10  # degrees: a passage's point this near a water of the same name's area is that water


def waters(marine: dict, lakes: dict, passages: list | None = None) -> list:
    """The seas, gulfs, straits and lakes (Natural Earth's), then the passages (PASSAGES) it
    lacks: a point each ("r" empty), with the canals' names (CANALS) when it is one."""
    out = []
    for feature in marine["features"] + lakes["features"]:
        p = feature["properties"]
        own = (p.get("name") or "").strip()
        drawn = area_of(shape(feature["geometry"])) if own and feature["geometry"] else {}
        if drawn:
            lake = feature in lakes["features"]  # drawn over the land, not under it
            water = named(names(p, own, p.get("namealt") or "", p.get("name_alt") or ""), drawn | {"lake": lake})
            water["k"] = sorted(set(water["k"]) | water_keys(water["n"]))
            out.append(water)
    canals = {fold(n): canal_names for canal_names, _ in CANALS for n in canal_names}
    for passage in passages or []:
        more = [n for found in passage["n"] if fold(found) in canals for n in canals[fold(found)]]
        all_names = list(dict.fromkeys([*passage["n"], *more]))
        keys = {fold(n) for n in all_names}
        x, y = passage["xy"]
        near = PASSAGE_NEAR * SCALE
        at = [round(x * SCALE), round(y * SCALE)]
        same = [
            w
            for w in out
            if not w["lake"]
            and keys & set(w["k"])
            and w["b"][0] - near <= at[0] <= w["b"][2] + near
            and w["b"][1] - near <= at[1] <= w["b"][3] + near
        ]
        if same:
            for w in same:
                w["n"] = list(dict.fromkeys([*w["n"], *all_names]))
                w["k"] = sorted(set(w["k"]) | keys | water_keys(all_names))
            continue
        water = named(all_names, {"b": [*at, *at], "r": [], "at": [at], "lake": False})
        water["k"] = sorted(set(water["k"]) | water_keys(all_names))
        out.append(water)
    return out


def lake_rings(lakes: dict) -> list:
    """Every map's lakes (Geneva's, the Great Lakes): drawn as water, nothing more."""
    return [area_of(shape(f["geometry"])) for f in lakes["features"] if f["geometry"]]


REGIONS_FILE = ROOT / "tools" / "atlas-regions.json"  # what Wikidata gave for the regions' codes, kept
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"


def iso_code(text: str | None) -> str:
    """An ISO 3166-2 code as Natural Earth writes it ("IT-25", "ES.AN"), as ISO does; "" else."""
    text = (text or "").strip().replace(".", "-")
    return text if re.fullmatch(r"[A-Z]{2}-[A-Z0-9]{1,3}", text) else ""


def region_codes(admin1: dict) -> list[str]:
    """The ISO codes of every region and group of regions Natural Earth has."""
    found = set()
    for f in admin1["features"]:
        p = f["properties"]
        found |= {iso_code(p.get("iso_3166_2")), iso_code(p.get("region_cod"))}
    return sorted(found - {""})


def region_names(admin1: dict, refresh: bool = False) -> dict[str, list[str]]:
    """Each region's names in the page's languages from Wikidata (CC0), by its ISO code
    ("IT-75": Pouilles, Apulia, Apulien, Apulia, Puglia, Apúlia), as REGIONS_FILE keeps them;
    the codes it lacks asked (all with `refresh`), then kept."""
    codes = region_codes(admin1)
    kept = {} if refresh or not REGIONS_FILE.is_file() else json.loads(REGIONS_FILE.read_text(encoding="utf-8"))
    asked = [c for c in codes if c not in kept]
    for start in range(0, len(asked), 400):
        batch = asked[start : start + 400]
        query = (
            "SELECT ?code ?l WHERE { VALUES ?code {"
            + " ".join(f'"{c}"' for c in batch)
            + '} ?i wdt:P300 ?code. ?i rdfs:label ?l. FILTER(LANG(?l) IN ("fr","en","de","es","it","pt")) }'
        )
        url = WIKIDATA_SPARQL + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
        found: dict = defaultdict(dict)
        for b in download(f"wikidata-regions-{start}.json", None, url)["results"]["bindings"]:
            found[b["code"]["value"]][b["l"]["xml:lang"]] = b["l"]["value"]
        for code in batch:
            kept[code] = [found[code][lang] for lang in ("fr", "en", "de", "es", "it", "pt") if lang in found[code]]
    kept = {c: list(dict.fromkeys(kept[c])) for c in codes}
    REGIONS_FILE.write_text(
        json.dumps(kept, ensure_ascii=False, separators=(",", ":"))[1:-1].replace('],"', '],\n"').join("{}") + "\n",
        encoding="utf-8",
    )
    return kept


def regions(admin1: dict, wikidata: dict | None = None) -> dict[str, dict]:
    """Per country: its first-level divisions (France's départements, the United States'
    states), and the groups Natural Earth gives them (France's régions), simplified together
    (shapely's coverage_simplify: a border shared stays one line); each by its names in the
    page's languages, Natural Earth's and Wikidata's (`wikidata`, by ISO code: "Pouilles",
    "Puglia" for Natural Earth's "Apulia")."""
    wikidata = wikidata or {}
    by_country: dict = defaultdict(list)
    for feature in admin1["features"]:
        if feature["geometry"]:
            by_country[feature["properties"]["adm0_a3"]].append(feature)
    out = {}
    for code, features in by_country.items():
        shapes = [shapely.make_valid(shape(f["geometry"])) for f in features]
        # Drawn as the country's largest part can show (the United States' lower 48, not
        # Alaska and the Aleutians across the Pacific: Rhode Island stays itself)
        detail = tolerance(max((g for shape_ in shapes for g in parts(shape_)), key=lambda g: g.area))
        units = []
        for f, g in zip(features, shapely.coverage_simplify(shapes, detail), strict=True):
            p = f["properties"]
            drawn = area_of(g, simplify=detail)
            if drawn:
                more = wikidata.get(iso_code(p.get("iso_3166_2")), [])
                own = names(p, p["name"], p.get("gn_name") or "", p.get("woe_name") or "")
                units.append(named(list(dict.fromkeys([*own, *more])), drawn))
        members: dict = defaultdict(list)
        group_codes: dict = {}
        for f, g in zip(features, shapes, strict=True):
            if (f["properties"].get("region") or "").strip():
                members[f["properties"]["region"].strip()].append(g)
                group_codes.setdefault(f["properties"]["region"].strip(), iso_code(f["properties"].get("region_cod")))
        groups = []
        if len(members) > 1:
            group_names = list(members)
            merged = [shapely.union_all(members[n]) for n in group_names]
            for n, g in zip(group_names, shapely.coverage_simplify(merged, detail), strict=True):
                drawn = area_of(g, simplify=detail)
                if drawn:
                    groups.append(named(list(dict.fromkeys([*wikidata.get(group_codes[n], []), n])), drawn))
        if units:
            out[code] = {"units": units, "groups": groups}
    return out


# A country's far parts (its overseas departments, its archipelagos across the sea): places
# of their own, found by their names like a country, drawn by their land, "o" their country
ISLAND_KINDS = {"Island", "Island group"}  # Natural Earth's reliefs that name an archipelago
GROUP_CODES = {"Canary Is.": "IC"}  # a group Natural Earth names only so: its CLDR code
FAR_SHARE = 0.25  # a far part's land holds less than this of its country's


SMALL_LAND = 3  # degrees: a land smaller than this across drawn from the 1:10m regions, by its own size
FINE = 0.004  # degrees: the least a small land's outline is simplified by


def fine_rings(geometry) -> list:
    """A small land's rings as an inset magnifies it: Natural Earth's 1:10m outline, each part
    simplified by its own size (a 400th of it, FINE at least), not the countries' scale (La
    Réunion an island, not a heptagon; Saint Helena beside Ascension); the parts too small to
    see beside the largest left out, but the largest."""
    x0, y0, x1, y1 = geometry.bounds
    least = (3 * max(FINE, max(x1 - x0, y1 - y0) / DETAIL)) ** 2
    polygons = sorted((g for g in parts(geometry) if g.geom_type == "Polygon"), key=lambda g: -g.area)
    kept = [g for g in polygons if g.area >= least] or polygons[:1]
    simple = []
    for g in kept:
        a0, b0, a1, b1 = g.bounds
        g = g.simplify(max(FINE, max(a1 - a0, b1 - b0) / DETAIL))
        if g.geom_type == "Polygon" and not g.is_empty:
            simple.append(list(g.exterior.coords)[:-1])
    rings = []
    for ring in one_side(simple):
        points = ints(ring)
        points = [p for i, p in enumerate(points) if i == 0 or p != points[i - 1]]
        if len(points) >= 3 and area(points) > 0:
            rings.append(points)
    return rings


def refine_small(countries: dict, admin1: dict) -> None:
    """The islands smaller than SMALL_LAND across (Bermuda, Saint Helena, the Caymans,
    Malta): their outlines from the 1:10m regions, by their own size; a land with a border
    keeps its country's outline, its neighbours' (Luxembourg's border one line)."""
    by_country: dict = defaultdict(list)
    for f in admin1["features"]:
        if f["geometry"]:
            by_country[f["properties"]["adm0_a3"]].append(shapely.make_valid(shape(f["geometry"])))
    lands = {code: shapely.union_all(found) for code, found in by_country.items()}
    tree_codes = list(lands)
    tree = shapely.STRtree([lands[c] for c in tree_codes])
    for code, c in countries.items():
        (x0, y0, x1, y1) = c["b"]
        if code not in lands or max(x1 - x0, y1 - y0) >= SMALL_LAND * SCALE:
            continue
        near = tree.query(lands[code], predicate="dwithin", distance=0.05)
        if any(tree_codes[i] != code for i in near):
            continue
        rings = fine_rings(lands[code])
        if rings:
            c |= {"r": rings, "b": box(rings), "f": box(main(rings))}


def territories(admin1: dict, countries: dict, usual: dict, relief: dict) -> dict:
    """Each country's first-level divisions lying farther than NEAR from its main part
    (Guadeloupe, the Azores, Hawaii, Svalbard, the Galápagos), or their groups when all of a
    group is (the Canaries, not their two provinces), or those of one ISO code (the Caribbean
    Netherlands: Bonaire, Saba, Sint Eustatius): their names (Natural Earth's, CLDR's by
    their code, an archipelago's that covers them), the country's rings on them (else their
    own), "o" the country's code, "t" a part of it."""
    islands = [
        (names(p, p["NAME"], p.get("NAMEALT") or ""), shapely.make_valid(shape(f["geometry"])))
        for f in relief["features"]
        if (p := f["properties"]).get("FEATURECLA") in ISLAND_KINDS and f["geometry"]
    ]
    by_country: dict = defaultdict(list)
    for f in admin1["features"]:
        if f["geometry"] and f["properties"]["adm0_a3"] in countries:
            by_country[f["properties"]["adm0_a3"]].append(f)
    taken = {key for c in countries.values() for key in c["k"]}
    out: dict = {}
    for code, features in sorted(by_country.items()):
        (x0, y0, x1, y1) = countries[code]["f"]

        def far(g, x0=x0, y0=y0, x1=x1, y1=y1) -> bool:
            (a0, b0, a1, b1) = (round(v * SCALE) for v in g.bounds)
            gaps = [max(a0 - x1, x0 - a1, b0 - y1, y0 - b1)]
            gaps += [max(a0 + d - x1, x0 - a1 - d, b0 - y1, y0 - b1) for d in (-360 * SCALE, 360 * SCALE)]
            return min(gaps) > NEAR * SCALE

        units = [(f["properties"], shapely.make_valid(shape(f["geometry"]))) for f in features]
        # (a part, not a half of the country: the divisions near each other one land, those of
        # a land as large as FAR_SHARE of the country never far: Peninsular Malaysia, Svalbard
        # is)
        # (their sizes on the ground: a degree of longitude shortened by its latitude's cosine)
        sizes = [g.area * math.cos(math.radians(g.centroid.y)) for _, g in units]
        whole = sum(sizes)
        lands = list(range(len(units)))

        def root(i: int, lands: list = lands) -> int:
            while lands[i] != i:
                i = lands[i]
            return i

        for i, (_, a) in enumerate(units):
            for j in range(i):
                if shapely.distance(a, units[j][1]) <= NEAR:
                    lands[root(i)] = root(j)
        land_area: dict = defaultdict(float)
        for i in range(len(units)):
            land_area[root(i)] += sizes[i]
        large = {id(units[i][0]) for i in range(len(units)) if land_area[root(i)] >= FAR_SHARE * whole}

        def apart(g, p=None, far=far, large: set = large) -> bool:
            return far(g) and id(p) not in large

        if not any(apart(g, p) for p, g in units):
            continue
        pieces = []  # (names, CLDR code or "", properties, geometry, a single division)
        members: dict = defaultdict(list)
        for p, g in units:
            if (p.get("region") or "").strip():
                members[p["region"].strip()].append((p, g))
        grouped = set()
        for name, found in members.items():
            if len(found) > 1 and all(apart(g, p) for p, g in found):
                pieces.append(
                    ([name], GROUP_CODES.get(name, ""), found[0][0], shapely.union_all([g for _, g in found]), False)
                )
                grouped |= {id(p) for p, _ in found}
        # (of one ISO code: "NL-BQ1", "NL-BQ2", "NL-BQ3" the Caribbean Netherlands, "BQ")
        by_iso: dict = defaultdict(list)
        for p, g in units:
            iso = re.sub(r"\d+$", "", (p.get("iso_3166_2") or "").split("-")[-1])
            if apart(g, p) and id(p) not in grouped and len(iso) == 2 and iso.isalpha():
                by_iso[iso].append((p, g))
        for iso, found in by_iso.items():
            if len(found) > 1:
                pieces.append(([], iso, found[0][0], shapely.union_all([g for _, g in found]), False))
        for p, g in units:
            if apart(g, p) and id(p) not in grouped:
                iso = (p.get("iso_3166_2") or "").split("-")[-1]
                pieces.append(
                    (
                        names(p, p["name"], p.get("gn_name") or "", p.get("woe_name") or ""),
                        iso if len(iso) == 2 else "",
                        p,
                        g,
                        True,
                    )
                )
        for own, iso, p, g, single in pieces:
            # CLDR's names of its code when they are its own (FR-GP: Guadeloupe) or it has none
            # of its own (BQ, IC), an archipelago's covering most of it
            cldr = usual.get(iso, []) if iso.isalpha() and len(iso) == 2 else []
            folded = {fold(n) for n in own}
            more = list(cldr) if not own or not single or folded & {fold(n) for n in cldr} else []
            # (an archipelago that is it, most of each within the other: the Canaries, Hawaii)
            same = [
                island_names
                for island_names, island in islands
                if island.intersects(g) and island.intersection(g).area >= 0.5 * max(island.area, g.area)
            ]
            all_names = list(dict.fromkeys([*more, *own, *(n for found in same for n in found)]))
            keys = {fold(n) for n in all_names} - taken
            if not keys:
                continue
            # Its own outline, as an inset magnifies it (its country's is drawn at its scale)
            rings = fine_rings(g)
            if not rings:
                continue
            key = p.get("gu_a3") if single else None
            name = (
                key
                if key and key != code and key not in countries and key not in out
                else f"{code}-{fold(all_names[0]).replace(' ', '-')}"
            )
            out[name] = {
                "n": all_names,
                "k": sorted(keys),
                "b": box(rings),
                "f": box(main(rings)),
                "r": rings,
                "o": code,
                "t": 1,
            }
            taken |= keys
    return out


def small_lands(admin1: dict, countries_geo: dict, countries: dict, usual: dict) -> dict:
    """The lands too small for the countries' scale that Natural Earth's regions have (Monaco,
    the Vatican, Gibraltar, Sint Maarten, Tuvalu): countries of their own, by their names and
    CLDR's, "o" the country holding a dependency."""
    holders = {
        p["SOV_A3"]: p["ADM0_A3"]
        for f in countries_geo["features"]
        if (p := f["properties"])["ADMIN"] == p["SOVEREIGNT"] and p["ADM0_A3"] in countries
    }
    by_code: dict = defaultdict(list)
    for f in admin1["features"]:
        if f["geometry"] and f["properties"]["adm0_a3"] not in countries:
            by_code[f["properties"]["adm0_a3"]].append(f)
    taken = {key for c in countries.values() for key in c["k"]}
    # (CLDR's names of a code no country of the atlas has: Gibraltar's GI, not Australia's AU)
    held = {two_letters(f["properties"]) for f in countries_geo["features"]}
    out = {}
    for code, features in sorted(by_code.items()):
        p = features[0]["properties"]
        two = p.get("iso_a2") or ""
        own = names(p, p["admin"]) if len(features) > 1 else names(p, p["name"], p["admin"])
        cldr = usual.get(two, []) if two.isalpha() and two not in held else []
        all_names = list(dict.fromkeys([*cldr, *own]))
        keys = {fold(n) for n in all_names} - taken
        land = shapely.union_all([shapely.make_valid(shape(f["geometry"])) for f in features])
        rings = fine_rings(land)
        if not rings:  # (smaller than the atlas's hundredth of a degree: the Vatican, a square of it)
            x, y = round(land.centroid.x * SCALE), round(land.centroid.y * SCALE)
            rings = [[[x, y], [x + 1, y], [x + 1, y + 1], [x, y + 1]]]
        if not keys or not rings:
            continue
        land = {"n": all_names, "k": sorted(keys | {code.lower()}), "b": box(rings), "f": box(main(rings)), "r": rings}
        holder = holders.get(p.get("sov_a3"))
        if holder and holder != code:
            land["o"] = holder
        out[code] = land
        taken |= keys
    return out


# The world's parts a lesson names (East Asia, Latin America, Sub-Saharan Africa): groups of
# countries a map colours or names, by the United Nations' geoscheme (M49) as Natural Earth
# gives each country's, their names CLDR's (by their M49 code) and these; and two of usage
AREAS = {  # M49 code: Natural Earth's subregions (or continents, "*" before) it holds, more names
    "002": (("*Africa",), ()),
    "015": (("Northern Africa",), ("Afrique septentrionale",)),
    "202": (("Western Africa", "Eastern Africa", "Middle Africa", "Southern Africa"), ("Afrique noire",)),
    "011": (("Western Africa",), ()),
    "014": (("Eastern Africa",), ()),
    "017": (("Middle Africa",), ()),
    "018": (("Southern Africa",), ()),
    "019": (("*Americas",), ()),
    "021": (
        ("Northern America",),
        (
            "Amérique du Nord",
            "North America",
            "Nordamerika",
            "América del Norte",
            "America del Nord",
            "América do Norte",
        ),
    ),
    "013": (("Central America",), ()),
    "029": (("Caribbean",), ()),
    "005": (("South America",), ()),
    "419": (("Central America", "Caribbean", "South America"), ()),
    "142": (("*Asia",), ()),
    "030": (
        ("Eastern Asia",),
        ("Asie de l'Est", "East Asia", "Ostasien", "Asia del Este", "Asia dell'Est", "Ásia do Leste"),
    ),
    "035": (("South-Eastern Asia",), ()),
    "034": (("Southern Asia",), ()),
    "143": (("Central Asia",), ()),
    "145": (("Western Asia",), ("Asie de l'Ouest",)),
    "150": (("*Europe",), ()),
    "154": (("Northern Europe",), ()),
    "155": (("Western Europe",), ()),
    "039": (("Southern Europe",), ()),
    "151": (("Eastern Europe",), ()),
    "009": (("*Oceania",), ()),
    "053": (("Australia and New Zealand",), ()),
}
USAGE_AREAS = [  # the Middle East and the Maghreb as French lessons draw them
    (
        (
            "Moyen-Orient",
            "Middle East",
            "Naher Osten",
            "Mittlerer Osten",
            "Oriente Medio",
            "Medio Oriente",
            "Médio Oriente",
            "Oriente Médio",
        ),
        (
            "EGY",
            "ISR",
            "PSX",
            "LBN",
            "SYR",
            "JOR",
            "IRQ",
            "IRN",
            "TUR",
            "SAU",
            "YEM",
            "OMN",
            "ARE",
            "QAT",
            "BHR",
            "KWT",
            "CYP",
        ),
    ),
    (("Maghreb", "Magreb", "Magrebe"), ("MAR", "DZA", "TUN")),
]


def areas(countries_geo: dict, countries: dict, usual: dict) -> list[dict]:
    """AREAS and USAGE_AREAS: their names (CLDR's, then theirs) and the countries they hold
    ("c", the atlas's codes; a dependency with its region, never a far part of a country)."""
    sub: dict = defaultdict(list)
    for f in countries_geo["features"]:
        p = f["properties"]
        if p["ADM0_A3"] in countries:
            sub[p["SUBREGION"]].append(p["ADM0_A3"])
            sub["*" + p["REGION_UN"]].append(p["ADM0_A3"])
    out = []
    taken = {key for c in countries.values() for key in c["k"]}
    for m49, (held, more) in AREAS.items():
        all_names = list(dict.fromkeys([*usual.get(m49, []), *more]))
        codes = sorted({code for h in held for code in sub[h]})
        out.append(named(all_names, {"c": codes}))
    for all_names, codes in USAGE_AREAS:
        out.append(named(list(all_names), {"c": [c for c in codes if c in countries]}))
    # (a name a country or another area has too: theirs)
    seen = set(taken)
    for a in out:
        a["k"] = [k for k in a["k"] if k not in seen]
        seen |= set(a["k"])
    return [a for a in out if a["k"]]


# The sea ways (ways.json): what a map's routes go by. Nodes off the coasts and over the open
# sea, each joined to the nearest it sees (no land between) in each direction; a sea route is
# the shortest way through them, found when the map is drawn (lib.typ)
SEA_ISLAND = 0.05  # square degrees: a smaller island is no obstacle (a route may cross Malta)
SEA_OFF = 0.25  # degrees: a node this far off a coast's corner, in the middle of a channel narrower
SEA_CORNERS = 0.1  # degrees: the coasts simplified this much, their corners kept as nodes
SEA_GRID = 8  # degrees between the open sea's nodes
SEA_CONES = 12  # directions a node is joined in: the nearest it sees in each
SEA_SEEN = 10  # nodes tried in each direction, the nearest first
SEA_PORT = 1  # degrees: a city this near a coast is a port, a country's or an island's nodes this near it
SEA_PASSAGE = 5  # degrees: a passage's point (a strait at sea, the Drake Passage) by its nearest node this near
# The canals a route may go through, only when it names them (Vasco da Gama never did): their
# names, and their ends as the atlas's cities (by their English name, folded) and countries
CANALS = [
    (
        ("canal de Suez", "Suez Canal", "Sueskanal", "Suezkanal", "canale di Suez"),
        (("EGY", "port said"), ("EGY", "suez")),
    ),
    (
        ("canal de Panama", "Panama Canal", "Panamakanal", "canale di Panama", "canal de Panamá"),
        (("PAN", "colon"), ("PAN", "panama")),
    ),
]
CAPES = "ne_10m_geography_regions_points.geojson"  # capes (Good Hope, Horn) as points, named in many languages


def _east(dx):
    """A longitude's difference, the short way round (the Pacific crossed, not the world)."""
    return (dx + 180) % 360 - 180


def seaways(world: dict, marine: list, relief: list, points: dict) -> dict:
    """The sea ways: the nodes ("p"), each one's neighbours and how far ("a": node, distance,
    …, in hundredths of a degree, a degree of longitude shortened by its latitude's cosine);
    for each city a port ("cities": where it meets the sea, then its nodes, or null), for each
    country its point (polylabel's) and the nodes off its coast, for each water ("waters",
    waters.json's order) and each island, peninsula or coast ("reliefs") the nodes in or by
    it, the capes, the canals (CANALS)."""
    import numpy as np

    polygons = [
        shapely.make_valid(shapely.Polygon([(x / SCALE, y / SCALE) for x, y in ring]))
        for c in world["countries"].values()
        for ring in c["r"]
    ]
    land = shapely.union_all(polygons)
    obstacles = [shapely.Polygon(g.exterior) for g in parts(land) if g.geom_type == "Polygon" and g.area >= SEA_ISLAND]
    whole = shapely.union_all(obstacles)
    # The land on a cylinder: a way across the 180th meridian sees what lies beyond
    wrapped = shapely.union_all([shapely.affinity.translate(whole, dx) for dx in (-360, 0, 360)])
    shapely.prepare(wrapped)
    coasts = [
        shapely.LineString(cs[i : i + 17])
        for g in parts(wrapped)
        for ring in (g.exterior, *g.interiors)
        for cs in [list(ring.coords)]
        for i in range(0, len(cs) - 1, 16)
    ]
    tree = shapely.STRtree(coasts)

    def blocked(segments: list) -> "np.ndarray":
        """Whether each segment ((x, y), (x, y)) crosses a coast."""
        out = np.zeros(len(segments), bool)
        if segments:
            out[tree.query(shapely.linestrings(segments), predicate="intersects")[0]] = True
        return out

    def across(rays: list) -> "np.ndarray":
        """How far each ray (x, y, its direction) goes over the sea, up to 2 SEA_OFF (inf)."""
        eps = 0.005
        lines = shapely.linestrings(
            [[(x + nx * eps, y + ny * eps), (x + nx * 2 * SEA_OFF, y + ny * 2 * SEA_OFF)] for x, y, nx, ny in rays]
        )
        far = np.full(len(rays), np.inf)
        ray_i, coast_i = tree.query(lines, predicate="intersects")
        if len(ray_i):
            hits = shapely.intersection(lines[ray_i], np.array(coasts, dtype=object)[coast_i])
            np.minimum.at(far, ray_i, shapely.distance(shapely.points([rays[i][:2] for i in ray_i]), hits))
        return far

    def outward(g) -> list:
        """A polygon's points, each with its direction away from it, and whether it is a corner."""
        ring = list(g.exterior.coords)[:-1]
        if not g.exterior.is_ccw:
            ring = ring[::-1]
        out = []
        for i in range(len(ring)):
            (x0, y0), (x1, y1), (x2, y2) = ring[i - 1], ring[i], ring[(i + 1) % len(ring)]
            la, lb = math.hypot(x1 - x0, y1 - y0) or 1, math.hypot(x2 - x1, y2 - y1) or 1
            nx, ny = (y1 - y0) / la + (y2 - y1) / lb, -(x1 - x0) / la - (x2 - x1) / lb
            length = math.hypot(nx, ny)
            if length > 1e-9:
                out.append((x1, y1, nx / length, ny / length, (x1 - x0) * (y2 - y1) - (y1 - y0) * (x2 - x1) < 0))
        return out

    found = []
    # The coasts' corners, a little off (less where the water is narrower)
    corners = [
        p[:4]
        for g in obstacles
        if g.simplify(SEA_CORNERS).geom_type == "Polygon"
        for p in outward(g.simplify(SEA_CORNERS))
        if p[4]
    ]
    for (x, y, nx, ny), h in zip(corners, across(corners), strict=True):
        found.append((x + nx * min(SEA_OFF, h / 2), y + ny * min(SEA_OFF, h / 2), False))
    # The channels narrower than 2 SEA_OFF (a strait, the Bosporus): a node in their middle
    shores = [p[:4] for g in obstacles for p in outward(g)]
    for (x, y, nx, ny), h in zip(shores, across(shores), strict=True):
        if h < 2 * SEA_OFF:
            found.append((x + nx * h / 2, y + ny * h / 2, True))
    kept = ~shapely.contains(wrapped, shapely.points([(x, y) for x, y, _ in found]))
    found = [f for f, k in zip(found, kept, strict=True) if k]
    # The open sea, a degree from any coast at least
    grid = []
    for y in range(-76, 84, SEA_GRID):
        step = SEA_GRID / max(math.cos(math.radians(y)), 0.25)
        grid += [(-180 + i * step, y) for i in range(math.ceil(360 / step))]
    open_sea = shapely.distance(wrapped, shapely.points(grid)) > 1
    found += [(x, y, False) for (x, y), k in zip(grid, open_sea, strict=True) if k]
    # One node a cell, smaller in the channels; where ways.json keeps it (to its hundredth of a
    # degree: what is seen from there is seen from where it is drawn), off the land still
    nodes, seen = [], set()
    for x, y, narrow in found:
        cell = 0.08 if narrow else 0.3
        key = (narrow, round(_east(x) / cell), round(y / cell))
        if key not in seen:
            seen.add(key)
            nodes.append((round(_east(x) * SCALE) / SCALE, round(y * SCALE) / SCALE))
    nodes = [n for n, inland in zip(nodes, shapely.contains(wrapped, shapely.points(nodes)), strict=True) if not inland]

    def area_of_rings(rings: list):
        return shapely.union_all(
            [shapely.make_valid(shapely.Polygon([(x / SCALE, y / SCALE) for x, y in r])) for r in rings if len(r) >= 3]
        )

    # Each sea, strait or gulf with a node in it (a strait narrower than the channels' cells,
    # the Bosporus): its name's place
    # (a passage's point, no area: its nearest node, below)
    water_areas = [None if w["lake"] or not w["r"] else area_of_rings(w["r"]) for w in marine]
    for w, area in zip(marine, water_areas, strict=True):
        if area is not None and w["at"] and not shapely.contains(area, shapely.points(nodes)).any():
            x, y = w["at"][0][0] / SCALE, w["at"][0][1] / SCALE
            if not wrapped.contains(shapely.Point(x, y)):
                nodes.append((round(_east(x) * SCALE) / SCALE, y))

    def toward(sources: list, limit: float = 60) -> list:
        """For each point, the nodes it sees, the nearest in each direction: (node, distance)."""
        nodes_xy = np.array(nodes)
        segments, meta = [], []
        for i, (x, y) in enumerate(sources):
            dx = _east(nodes_xy[:, 0] - x)
            ex, ey = dx * np.cos(np.radians((nodes_xy[:, 1] + y) / 2)), nodes_xy[:, 1] - y
            d = np.hypot(ex, ey)
            cone = ((np.arctan2(ey, ex) + math.pi) / (2 * math.pi) * SEA_CONES).astype(int) % SEA_CONES
            counts = [0] * SEA_CONES
            for j in np.argsort(d)[:500]:
                if d[j] > limit:
                    break
                if d[j] > 1e-9 and counts[cone[j]] < SEA_SEEN:
                    counts[cone[j]] += 1
                    segments.append([(x, y), (x + dx[j], nodes_xy[j, 1])])
                    meta.append((i, int(j), int(cone[j]), float(d[j])))
        best: dict = {}
        for (i, j, c, d), b in zip(meta, blocked(segments), strict=True):
            if not b and ((i, c) not in best or d < best[(i, c)][1]):
                best[(i, c)] = (j, d)
        out: list = [[] for _ in sources]
        for (i, _), (j, d) in sorted(best.items()):
            out[i].append((j, d))
        return out

    edges = {}
    for i, seen_from in enumerate(toward(nodes)):
        for j, d in seen_from:
            edges[(min(i, j), max(i, j))] = d
    # The nodes joined to the others only (an island's bay seeing nothing left out)
    linked = sorted({i for pair in edges for i in pair})
    number = {old: new for new, old in enumerate(linked)}
    nodes = [nodes[i] for i in linked]
    adjacent: list = [[] for _ in nodes]
    for (i, j), d in sorted(edges.items()):
        adjacent[number[i]] += [number[j], round(d * SCALE)]
        adjacent[number[j]] += [number[i], round(d * SCALE)]
    nodes_xy = np.array(nodes)
    node_points = shapely.points(nodes)

    def port(xy: tuple[float, float]) -> list | None:
        """Where a place by the sea meets it (off its coast), then the nodes seen from there."""
        point = shapely.Point(xy)
        if wrapped.contains(point):
            coast = shapely.ops.nearest_points(wrapped.boundary, point)[0]
            far = coast.distance(point)
            if far > SEA_PORT:
                return None
            ux, uy = (coast.x - point.x) / (far or 1), (coast.y - point.y) / (far or 1)
            xy = (coast.x + ux * 0.02, coast.y + uy * 0.02)
        return [round(xy[0] * SCALE), round(xy[1] * SCALE)]

    def ports(places: list) -> list:
        at = [port(xy) for xy in places]
        starts = [(x / SCALE, y / SCALE) for x, y in (a for a in at if a)]
        seen_from = iter(toward(starts, limit=10))
        out = []
        for a in at:
            if a is None:
                out.append(None)
                continue
            seen = [j for j, _ in next(seen_from)]
            if not seen:  # in a river's mouth narrower than the nodes see: the nearest nodes
                x, y = a[0] / SCALE, a[1] / SCALE
                d = np.hypot(_east(nodes_xy[:, 0] - x) * math.cos(math.radians(y)), nodes_xy[:, 1] - y)
                seen = [int(j) for j in np.argsort(d)[:3] if d[j] <= SEA_PORT]
            out.append([*a, *seen] if seen else None)
        return out

    def by(area) -> list[int]:
        """The nodes within SEA_PORT of an area (a country, an island)."""
        near = shapely.dwithin(area, node_points, SEA_PORT)
        return [int(i) for i in np.flatnonzero(near)]

    # Countries: where a route or a flow from them is drawn from (their largest part's
    # inmost point), the nodes off their coast
    countries = {}
    for code, c in sorted(world["countries"].items()):
        shapes = [shapely.make_valid(shapely.Polygon([(x / SCALE, y / SCALE) for x, y in r])) for r in c["r"]]
        largest = max((g for s in shapes for g in parts(s) if g.geom_type == "Polygon"), key=lambda g: g.area)
        inmost = polylabel(largest, tolerance=0.05)
        countries[code] = {"at": [round(inmost.x * SCALE), round(inmost.y * SCALE)], "s": by(shapely.union_all(shapes))}
    cities = ports([(c["x"] / SCALE, c["y"] / SCALE) for c in world["cities"]])

    waters_nodes = []
    for w, area in zip(marine, water_areas, strict=True):
        inside = [] if area is None else [int(i) for i in np.flatnonzero(shapely.contains(area, node_points))]
        # A strait narrower than the coasts drawn (Gibraltar's at this scale), a passage's point:
        # the nearest node within SEA_PORT (none for a sea within the land, the Caspian: no way
        # by sea goes there)
        if not w["lake"] and not inside and w["at"]:
            x, y = w["at"][0][0] / SCALE, w["at"][0][1] / SCALE
            d = np.hypot(_east(nodes_xy[:, 0] - x) * math.cos(math.radians(y)), nodes_xy[:, 1] - y)
            inside = [int(np.argmin(d))] if d.min() <= (SEA_PORT if w["r"] else SEA_PASSAGE) else []
        waters_nodes.append(inside)
    reliefs_nodes = [by(area_of_rings(r["r"])) if r["c"] == "land" else [] for r in relief]
    capes = []
    cape_features = [f for f in points["features"] if f["properties"]["featurecla"] == "cape"]
    for f, at in zip(cape_features, ports([tuple(f["geometry"]["coordinates"]) for f in cape_features]), strict=True):
        p = f["properties"]
        if at:
            all_names = names(p, p["name"], p.get("name_alt") or "")
            x, y = f["geometry"]["coordinates"]
            capes.append(named(all_names, {"x": round(x * SCALE), "y": round(y * SCALE), "s": at}))
    by_name = {(c["c"], k): i for i, c in enumerate(world["cities"]) for k in c["k"]}
    canals = []
    for canal_names, ends in CANALS:
        at = [world["cities"][by_name[end]] for end in ends]
        canals.append(
            named(
                list(canal_names),
                {"ends": [cities[by_name[end]] for end in ends], "xy": [[c["x"], c["y"]] for c in at]},
            )
        )
    return {
        "p": [[round(x * SCALE), round(y * SCALE)] for x, y in nodes],
        "a": adjacent,
        "cities": cities,
        "countries": countries,
        "waters": waters_nodes,
        "reliefs": reliefs_nodes,
        "capes": capes,
        "canals": canals,
    }


TOML = f"""[package]
name = "{NAME}"
version = "{VERSION}"
entrypoint = "lib.typ"
authors = ["Notosaurus"]
license = "AGPL-3.0-or-later"
description = "School maps: countries, cities, regions, rivers, reliefs, seas, from Natural Earth (public domain)."
"""
NOTICE = """The map function (lib.typ) is Notosaurus's (AGPL-3.0-or-later). The data (the .json
files) is made from Natural Earth (https://www.naturalearthdata.com/), public domain: 1:50m
countries and lakes; 1:10m populated places, rivers, geographic regions and points (capes),
marine areas and first-level divisions; simplified by tools/atlas.py, the sea ways (ways.json)
computed from them. The countries' usual names in each
language from Unicode CLDR 46 (https://cldr.unicode.org/), under the Unicode License v3: its
copyright and permission notice in LICENSE-CLDR, beside this file. The places of history and
the sea's straits, channels and canals Natural Earth lacks from Wikidata
(https://www.wikidata.org/, CC0). The borders of past years (borders/<year>.json) from
OpenHistoricalMap (https://www.openhistoricalmap.org/, its contributors, CC0); the land it leaves
to no state (Africa's and Asia's states before their colonisation) from historical-basemaps by
André Ourednik (https://github.com/aourednik/historical-basemaps), under the GNU General Public
License v3: its text in LICENSE-historical-basemaps, beside this file; their states' names from
Wikidata (CC0).
"""


def build(folder: Path | None = None, refresh_history: bool = False) -> None:
    files = (COUNTRIES, PLACES, RIVERS, RIVERS_EUROPE, RELIEFS, WATERS, LAKES, REGIONS, CAPES)
    with ThreadPoolExecutor() as pool:  # all at once
        countries, places, main_rivers, europe, relief, marine, lakes, admin1, capes = pool.map(
            lambda name: download(name, folder), files
        )
    usual = usual_names(folder)
    world = atlas(countries, places, usual, history(folder, refresh_history)) | {
        "lakes": lake_rings(lakes),
        "years": [[year, start, end] for year, (_, start, end) in LAYERS.items()],
    }
    world["areas"] = areas(countries, world["countries"], usual)
    found_territories = territories(admin1, world["countries"], usual, relief)
    # The borders of past years: OHM's states of each layer's day (two layers asked at once:
    # Overpass serves two queries at a time), historical-basemaps' nearest layer for the land
    # OHM leaves to none
    ever = overpass("ohm-states.json", folder, 'rel["boundary"="administrative"]["admin_level"="2"];out tags;')
    asked = {
        year: ",".join(str(r["id"]) for r in ever["elements"] if on(r["tags"], day))
        for year, (day, _, _) in LAYERS.items()
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        ohm = dict(
            zip(
                LAYERS,
                pool.map(lambda y: overpass(f"ohm-{y}.json", folder, f"rel(id:{asked[y]});out geom;"), LAYERS),
                strict=True,
            )
        )
    nearest = {year: min(BORDERS_YEARS, key=lambda y: (abs(y - year), y)) for year in LAYERS}
    with ThreadPoolExecutor() as pool:
        extra = dict(
            zip(
                set(nearest.values()),
                pool.map(
                    lambda y: download(f"world_{y}.geojson", folder, f"{BORDERS_SOURCE}geojson/world_{y}.geojson"),
                    set(nearest.values()),
                ),
                strict=True,
            )
        )
    drawn = {r["id"] for data in ohm.values() for r in data["elements"]}
    ids = {r["tags"]["wikidata"] for r in ever["elements"] if r["id"] in drawn and "wikidata" in r["tags"]}
    titles = {article for until, article in ITEMS.values()} | {
        ARTICLES.get(n, bare_hb(n))
        for data in extra.values()
        for f in data["features"]
        if (n := (f["properties"]["NAME"] or "").strip())
    }
    named = wikidata_items(folder, refresh_history, ids, titles)
    # today's countries' names (a state of the past named as one of them: « France ») and land
    today = {key: country["n"] for country in world["countries"].values() for key in country["k"]}
    today |= {  # (and by its Wikidata item: OHM's Italy of 1960 is Q38, Natural Earth's Italy)
        f["properties"]["WIKIDATAID"]: world["countries"][f["properties"]["ADM0_A3"]]["n"]
        for f in countries["features"]
        if f["properties"].get("WIKIDATAID") and f["properties"]["ADM0_A3"] in world["countries"]
    }
    nations = [
        (world["countries"][code]["n"], shapely.make_valid(shape(f["geometry"])))
        for f in countries["features"]
        if (code := f["properties"]["ADM0_A3"]) != "ATA" and code in world["countries"]
    ]
    world["countries"] |= found_territories | small_lands(admin1, countries, world["countries"], usual)
    refine_small(world["countries"], admin1)

    def text(data) -> str:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    all_reliefs, all_waters = reliefs(relief), waters(marine, lakes, passages(folder, refresh_history))
    all_regions = regions(admin1, region_names(admin1, refresh_history))
    contents = {
        "typst.toml": TOML,
        "lib.typ": LIB.read_text(encoding="utf-8"),
        "NOTICE": NOTICE,
        "LICENSE-CLDR": download_text("cldr-LICENSE", folder, CLDR_LICENCE),
        "LICENSE-historical-basemaps": download_text("historical-basemaps-LICENSE", folder, BORDERS_SOURCE + "LICENSE"),
        "atlas.json": text(world),
        "rivers.json": text(rivers(main_rivers, europe)),
        "reliefs.json": text(all_reliefs),
        "waters.json": text(all_waters),
        "ways.json": text(seaways(world, all_waters, all_reliefs, capes)),
    } | {f"regions/{code}.json": text(data) for code, data in sorted(all_regions.items())}
    states = {year: past_states(year, ohm[year], extra[nearest[year]], named, today, nations) for year in LAYERS}
    contents |= {f"borders/{year}.json": text(data) for year, data in states.items()}
    # What a name the map refuses is, read only then (said in the refusal): the countries
    # whose regions bear it, the years whose states do
    region_keys: dict = defaultdict(set)
    for code, data in all_regions.items():
        if code not in world["countries"]:
            continue
        for r in data["units"] + data["groups"]:
            for key in r["k"]:
                region_keys[key].add(code)
    state_names: dict = defaultdict(set)
    for year, data in states.items():
        for state in data["countries"].values():
            for key in state["k"]:
                state_names[key].add(year)
    contents["names.json"] = text(
        {
            "regions": {k: sorted(v) for k, v in sorted(region_keys.items())},
            "states": {k: sorted(v) for k, v in sorted(state_names.items())},
        }
    )
    for old in TARGET.glob(f"{NAME}-*.tar.gz"):
        old.unlink()
    archive = TARGET / f"{NAME}-{VERSION}.tar.gz"
    # gzip's header without a date (mtime=0), as the files': the same sources, the same archive
    with (
        archive.open("wb") as raw,
        gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as packed,
        tarfile.open(fileobj=packed, mode="w") as tar,
    ):
        for name, content in contents.items():
            raw = content.encode()
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.mode = len(raw), 0, 0o644
            tar.addfile(info, io.BytesIO(raw))
    sizes = ", ".join(f"{n} {len(c.encode()) // 1024} KB" for n, c in contents.items() if not n.startswith("regions/"))
    regions_size = sum(len(c.encode()) for n, c in contents.items() if n.startswith("regions/")) // 1024
    print(f"{archive.relative_to(ROOT)}: {archive.stat().st_size // 1024} KB ({sizes}, regions/ {regions_size} KB)")


if __name__ == "__main__":
    arguments = [a for a in sys.argv[1:] if a != "--refresh-history"]
    build(Path(arguments[0]) if arguments else None, "--refresh-history" in sys.argv[1:])
