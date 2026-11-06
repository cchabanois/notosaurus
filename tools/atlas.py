"""The maps' atlas (the figures' "map" family, notosaurus_core/typst_rules/map.md): the
countries' outlines and their main cities from Natural Earth (public domain), simplified,
with the map function (notosaurus_core/atlas/lib.typ), as a Typst package of our own:
core/notosaurus_core/typst/notosaurus-atlas-<version>.tar.gz, unpacked with the others
(figures_typst.packages). Nothing is downloaded when a map is drawn. Run again to change
the data or the function (VERSION raised with it), then commit what it wrote.

Besides atlas.json (countries, cities, lakes: every map reads it), files a map reads only
when it asks for them: rivers.json, reliefs.json (mountains, deserts, plains, peninsulas,
islands), waters.json (oceans, seas, gulfs, straits, lakes), regions/<country code>.json
(its first-level divisions, and the groups Natural Earth gives them: France's régions).

  .venv/bin/python tools/atlas.py [folder]  (the Natural Earth files read there when it has them)

Needs shapely (requirements-dev.txt): regions simplified together, their borders shared.
"""

import io
import json
import math
import re
import sys
import tarfile
import unicodedata
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import shapely
from shapely.geometry import shape
from shapely.ops import polylabel

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core" / "notosaurus_core"
LIB = CORE / "atlas" / "lib.typ"
TARGET = CORE / "typst"
NAME, VERSION = "notosaurus-atlas", "0.2.0"
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
CITIES = 15  # per country, the most populated, its capital too
NOTABLE = 3  # and the cities Natural Earth ranks this notable or more (Vladivostok), wherever they are
TOLERANCE = 0.03  # degrees: a point closer than this to the line it would cut away goes
SMALLEST = 0.02  # square degrees: smaller islands left out, unless they are the country itself
SCALE = 100  # coordinates kept as integers, in hundredths of a degree (about 1 km)
NEAR = 3  # degrees: a country's rings this near its largest one are framed with it (Corsica, not the Canaries)


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


def download(name: str, folder: Path | None = None) -> dict:
    if folder and (folder / name).is_file():
        return json.loads((folder / name).read_text(encoding="utf-8"))
    with urllib.request.urlopen(SOURCE + name, timeout=120) as response:
        return json.loads(response.read())


def atlas(countries: dict, places: dict) -> dict:
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
    by_country: dict[str, list] = {}
    for feature in places["features"]:
        p = feature["properties"]
        code = p["ADM0_A3"]
        if code in codes:
            by_country.setdefault(code, []).append(p | {"_xy": feature["geometry"]["coordinates"]})
    cities = []
    for code, found in sorted(by_country.items()):
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
    return {"scale": SCALE, "letters": LETTERS, "countries": out_countries, "cities": cities}


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


def waters(marine: dict, lakes: dict) -> list:
    out = []
    for feature in marine["features"] + lakes["features"]:
        p = feature["properties"]
        own = (p.get("name") or "").strip()
        drawn = area_of(shape(feature["geometry"])) if own and feature["geometry"] else {}
        if drawn:
            lake = feature in lakes["features"]  # drawn over the land, not under it
            out.append(named(names(p, own, p.get("namealt") or "", p.get("name_alt") or ""), drawn | {"lake": lake}))
    return out


def lake_rings(lakes: dict) -> list:
    """Every map's lakes (Geneva's, the Great Lakes): drawn as water, nothing more."""
    return [area_of(shape(f["geometry"])) for f in lakes["features"] if f["geometry"]]


def regions(admin1: dict) -> dict[str, dict]:
    """Per country: its first-level divisions (France's départements, the United States'
    states), and the groups Natural Earth gives them (France's régions), simplified together
    (shapely's coverage_simplify: a border shared stays one line)."""
    by_country: dict = defaultdict(list)
    for feature in admin1["features"]:
        if feature["geometry"]:
            by_country[feature["properties"]["adm0_a3"]].append(feature)
    out = {}
    for code, features in by_country.items():
        shapes = [shapely.make_valid(shape(f["geometry"])) for f in features]
        detail = tolerance(*shapes)
        units = []
        for f, g in zip(features, shapely.coverage_simplify(shapes, detail), strict=True):
            p = f["properties"]
            drawn = area_of(g, simplify=detail)
            if drawn:
                units.append(named(names(p, p["name"], p.get("gn_name") or "", p.get("woe_name") or ""), drawn))
        members: dict = defaultdict(list)
        for f, g in zip(features, shapes, strict=True):
            if (f["properties"].get("region") or "").strip():
                members[f["properties"]["region"].strip()].append(g)
        groups = []
        if len(members) > 1:
            group_names = list(members)
            merged = [shapely.union_all(members[n]) for n in group_names]
            for n, g in zip(group_names, shapely.coverage_simplify(merged, detail), strict=True):
                drawn = area_of(g, simplify=detail)
                if drawn:
                    groups.append(named([n], drawn))
        if units:
            out[code] = {"units": units, "groups": groups}
    return out


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
countries and lakes; 1:10m populated places, rivers, geographic regions, marine areas and
first-level divisions; simplified by tools/atlas.py.
"""


def build(folder: Path | None = None) -> None:
    files = (COUNTRIES, PLACES, RIVERS, RIVERS_EUROPE, RELIEFS, WATERS, LAKES, REGIONS)
    with ThreadPoolExecutor() as pool:  # all at once
        countries, places, main_rivers, europe, relief, marine, lakes, admin1 = pool.map(
            lambda name: download(name, folder), files
        )
    world = atlas(countries, places) | {"lakes": lake_rings(lakes)}

    def text(data) -> str:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    contents = {
        "typst.toml": TOML,
        "lib.typ": LIB.read_text(encoding="utf-8"),
        "NOTICE": NOTICE,
        "atlas.json": text(world),
        "rivers.json": text(rivers(main_rivers, europe)),
        "reliefs.json": text(reliefs(relief)),
        "waters.json": text(waters(marine, lakes)),
    } | {f"regions/{code}.json": text(data) for code, data in sorted(regions(admin1).items())}
    for old in TARGET.glob(f"{NAME}-*.tar.gz"):
        old.unlink()
    archive = TARGET / f"{NAME}-{VERSION}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name, content in contents.items():
            raw = content.encode()
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.mode = len(raw), 0, 0o644
            tar.addfile(info, io.BytesIO(raw))
    sizes = ", ".join(f"{n} {len(c.encode()) // 1024} KB" for n, c in contents.items() if not n.startswith("regions/"))
    regions_size = sum(len(c.encode()) for n, c in contents.items() if n.startswith("regions/")) // 1024
    print(f"{archive.relative_to(ROOT)}: {archive.stat().st_size // 1024} KB ({sizes}, regions/ {regions_size} KB)")


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
