"""The maps' atlas (the figures' "map" family, notosaurus_core/typst_rules/map.md): the
countries' outlines and their main cities from Natural Earth (public domain), simplified,
with the map function (notosaurus_core/atlas/lib.typ), as a Typst package of our own:
core/notosaurus_core/typst/notosaurus-atlas-<version>.tar.gz, unpacked with the others
(figures_typst.packages). Nothing is downloaded when a map is drawn. Run again to change
the data or the function (VERSION raised with it), then commit what it wrote.

  .venv/bin/python tools/atlas.py
"""

import io
import json
import math
import re
import tarfile
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core" / "notosaurus_core"
LIB = CORE / "atlas" / "lib.typ"
TARGET = CORE / "typst"
NAME, VERSION = "notosaurus-atlas", "0.1.0"
SOURCE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/"
COUNTRIES = "ne_50m_admin_0_countries.geojson"  # 1:50m: a country's shape, light enough
PLACES = "ne_10m_populated_places.geojson"  # 1:10m: the cities, their names in many languages
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
    rings = [polygon[0] for polygon in polygons]
    # Across the 180th meridian (Russia's far east, the Aleutians, Fiji): its smaller side
    # moved by 360° to the larger's, the country in one piece (its frame not the whole world)
    if max(x for r in rings for x, _ in r) - min(x for r in rings for x, _ in r) > 300:
        east = sum(area(r) for r in rings if sum(x for x, _ in r) > 0)
        west = sum(area(r) for r in rings if sum(x for x, _ in r) < 0)
        move = (lambda x: x - 360) if east < west else (lambda x: x + 360)
        rings = [[[move(x), y] for x, y in r] if (sum(x for x, _ in r) > 0) == (east < west) else r for r in rings]
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


def names(properties: dict, own: str) -> list[str]:
    """A place's names, the page's languages first (in LANGUAGES' order), its own, distinct."""
    found = [properties.get(f"NAME_{lang}") or "" for lang in LANGUAGES] + [own]
    return list(dict.fromkeys(n.strip() for n in found if n and n.strip()))


def download(name: str) -> dict:
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


TOML = f"""[package]
name = "{NAME}"
version = "{VERSION}"
entrypoint = "lib.typ"
authors = ["Notosaurus"]
license = "AGPL-3.0-or-later"
description = "School maps: a country, its neighbours, its cities, from Natural Earth (public domain)."
"""
NOTICE = """The map function (lib.typ) is Notosaurus's (AGPL-3.0-or-later). The data (atlas.json)
is made from Natural Earth (https://www.naturalearthdata.com/), public domain:
1:50m countries and 1:10m populated places, simplified by tools/atlas.py.
"""


def build() -> None:
    with ThreadPoolExecutor() as pool:  # both at once
        countries, places = pool.map(download, (COUNTRIES, PLACES))
    data = json.dumps(atlas(countries, places), ensure_ascii=False, separators=(",", ":"))
    for old in TARGET.glob(f"{NAME}-*.tar.gz"):
        old.unlink()
    archive = TARGET / f"{NAME}-{VERSION}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name, content in (
            ("typst.toml", TOML),
            ("lib.typ", LIB.read_text(encoding="utf-8")),
            ("atlas.json", data),
            ("NOTICE", NOTICE),
        ):
            raw = content.encode()
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.mode = len(raw), 0, 0o644
            tar.addfile(info, io.BytesIO(raw))
    print(f"{archive.relative_to(ROOT)}: {archive.stat().st_size // 1024} KB, atlas.json {len(data) // 1024} KB")


if __name__ == "__main__":
    build()
