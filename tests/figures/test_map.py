"""The map family (our atlas): places found by any name, history's places, what the atlas
lacks, a map's size."""

import io
import itertools
import json
import re

import pytest

from notosaurus_core import figures, figures_typst


def test_a_map_finds_its_places_by_any_name():
    """A country by its name in any of the page's languages, or its code: the same map; a city
    as the lesson writes it ("Séville", "Seville"): the same dot."""
    maps = {
        figures_typst.compile_svg("map", f'#map(countries: ("{country}",), cities: ("{city}",), labels: false)')
        for country, city in (("Espagne", "Séville"), ("Spain", "Seville"), ("ESP", "SEVILLE"))
    }
    assert len(maps) == 1


@pytest.mark.parametrize(
    ("code", "names"),
    [
        ("CHN", ("Chine", "China", "Cina")),  # Natural Earth's French one: "République populaire de Chine"
        ("USA", ("United States", "Stati Uniti", "EUA", "USA", "EE. UU.")),
        ("CZE", ("République tchèque", "Tschechische Republik", "Cechia", "Tchéquia")),
        ("VNM", ("Vietnã", "Vietnam")),
        ("IRN", ("Irã", "Iran")),
        ("SAU", ("Arabia Saudí", "Arabie saoudite")),
    ],
)
def test_a_country_by_its_usual_name_in_every_language(code, names):
    """A country by the name a lesson gives it in any of the page's languages (CLDR's usual
    ones): the same map as by its code ("Chine" was refused, "China" found)."""
    maps = {figures_typst.compile_svg("map", f'#map(countries: ("{name}",))') for name in (code, *names)}
    assert len(maps) == 1


@pytest.mark.parametrize(
    ("today", "former"),
    [
        (None, ("Constantinople", "Konstantinopel", "Costantinopoli", "Constantinopla")),  # its old town
        (None, ("Lutèce", "Lutetia", "Lutezia", "Lutécia")),
        ("Saint-Pétersbourg", ("Leningrad", "Léningrad", "Petrograd", "Leningrado")),
        ("Volgograd", ("Stalingrad", "Stalingrado")),
        ("Pékin", ("Peking", "Pequim", "Pechino")),
    ],
)
def test_a_city_by_a_former_name(today, former):
    """A city as a history lesson names it, by its name of then in any of the page's languages:
    one dot whatever the language, today's city's when it is only renamed (Leningrad), the old
    town's when it is a place of its own (Constantinople, Lutèce: Wikidata's)."""
    dot = lambda name: figures_typst.compile_svg("map", f'#map(cities: ("{name}",), labels: false)')  # noqa: E731
    dots = {dot(name) for name in former}
    assert len(dots) == 1 and (today is None or dots == {dot(today)})


def test_the_places_of_history_lessons_found():
    """Places of history lessons Natural Earth lacks (Aix-la-Chapelle, Cordoue, Troie, Verdun,
    Austerlitz, Ðiện Biên Phủ…), by their names in the page's languages."""
    for name in (
        "Aix-la-Chapelle",
        "Aquisgrán",
        "Aachen",
        "Cordoue",
        "Córdoba",
        "Troie",
        "Troy",
        "Verdun",
        "Austerlitz",
        "Diên Biên Phu",
        "La Mecque",
        "Mekka",
        "Tenochtitlan",
        "Wittenberg",
        "Canterbury",
    ):
        assert figures_typst.compile_svg("map", f'#map(cities: ("{name}",))').startswith("<svg"), name


def test_a_place_of_history_before_its_namesakes():
    """Two places of one name: a lesson's map with no country chooses the place of history
    (Cordoue in Spain, not Argentina's Córdoba; Waterloo in Belgium), a map of a country its
    own (Argentina's)."""
    dot = lambda body: figures_typst.compile_svg("map", body)  # noqa: E731
    assert dot('#map(cities: ("Cordoue",), labels: false)') == dot('#map(cities: ("Córdoba",), labels: false)')
    assert dot('#map(countries: ("Espagne",), cities: ("Córdoba",), labels: false)') == dot(
        '#map(countries: ("Espagne",), cities: ("Cordoue",), labels: false)'
    )
    argentina = dot('#map(countries: ("Argentine",), cities: ("Córdoba",), labels: false)')
    assert argentina != dot('#map(countries: ("Argentine",), cities: ("Cordoue",), labels: false)')
    assert dot('#map(countries: ("Belgique",), cities: ("Waterloo",), labels: false)') == dot(
        '#map(countries: ("Belgique",), cities: ("Waterloo",), labels: false)'
    )


@pytest.mark.parametrize(
    ("long", "short"),
    [
        ("mer Méditerranée", ("Méditerranée", "Mediterranean", "Mediterraneo", "Mediterrâneo")),
        ("Atlantic Ocean", ("Atlantique", "Atlantic", "Atlantik", "Atlántico", "Atlantico", "Atlântico")),
        ("Adriatic Sea", ("Adriatique", "Adria")),
        ("Caribbean Sea", ("Caraïbes", "Karibik", "mar do Caribe", "mar dei Caraibi")),
        ("English Channel", ("Manche", "Manica", "Ärmelkanal")),
    ],
)
def test_a_sea_by_its_short_name(long, short):
    """A sea or an ocean as a lesson writes it, short, in any of the page's languages
    ("Méditerranée" was refused, "mer Méditerranée" found): the same map."""
    maps = {figures_typst.compile_svg("map", f'#map(waters: ("{name}",), labels: false)') for name in (long, *short)}
    assert len(maps) == 1


def test_a_place_the_atlas_lacks_said_never_guessed():
    """A city the atlas doesn't have (not a capital nor among its country's largest): the
    figure stops, saying so, for the AI to leave it out; never a dot placed by guess."""
    with pytest.raises(figures_typst.Unusable, match=r"no city called .Trifouilly."):
        figures_typst.compile_svg("map", '#map(countries: ("France",), cities: ("Trifouilly",))')
    with pytest.raises(figures_typst.Unusable, match=r"no country called .Atlantide."):
        figures_typst.compile_svg("map", '#map(countries: ("Atlantide",))')


def test_a_map_stays_light():
    """Only what the frame shows is drawn (the countries cut to it, a point the eye wouldn't
    see skipped), its numbers to the tenth: well within a figure's size, Russia included."""
    for country in ("France", "United States of America", "Russia"):
        svg = figures.clean(figures_typst.compile_svg("map", f'#map(countries: ("{country}",))'))
        assert len(svg) < figures.MAX_SIZE / 2, country


def test_a_map_finds_rivers_reliefs_waters_and_regions_by_any_name():
    """A river, a relief, a water and a region by their names in the page's languages (the
    rivers Natural Earth names in English only too: "Rhin"), drawn the same."""
    cases = {
        "rivers": ("Rhin", "Rhine", "Rhein"),
        "reliefs": ("Alpes", "Alps", "Alpi"),
        "waters": ("Manche", "English Channel"),
        "regions": ("Californie", "California"),
    }
    for layer, written in cases.items():
        country = "États-Unis" if layer == "regions" else "France"
        maps = {
            figures_typst.compile_svg("map", f'#map(countries: ("{country}",), {layer}: ("{w}",), labels: false)')
            for w in written
        }
        assert len(maps) == 1, layer


def test_a_map_frames_what_it_is_asked_and_names_it():
    """Without a country, a river is the map (the Danube, Germany to the Black Sea); a sea
    beside the countries framed is named in the frame (the Atlantic beside France)."""
    danube = figures_typst.compile_svg("map", '#map(rivers: ("Danube",))')
    france = figures_typst.compile_svg("map", '#map(countries: ("France",))')
    assert danube != france
    with_sea = figures_typst.compile_svg("map", '#map(countries: ("France",), waters: ("océan Atlantique",))')
    assert len(re.findall(r"<use|<path", with_sea)) > len(re.findall(r"<use|<path", france))  # its name's glyphs


def test_a_region_needs_its_country_and_a_name_the_atlas_has():
    with pytest.raises(figures_typst.Unusable, match=r"put it in countries"):
        figures_typst.compile_svg("map", '#map(regions: ("Bretagne",))')
    with pytest.raises(figures_typst.Unusable, match=r"no region called .Atlantis."):
        figures_typst.compile_svg("map", '#map(countries: ("France",), regions: ("Atlantis",))')
    with pytest.raises(figures_typst.Unusable, match=r"no river called .Trifouille."):
        figures_typst.compile_svg("map", '#map(countries: ("France",), rivers: ("Trifouille",))')


def test_a_region_too_small_to_see_is_circled():
    """Rhode Island, or Hawaii's islands beside the whole United States: a circle around it
    (its colour alone wouldn't show); Texas, seen, has none."""
    for state, circled in (("Rhode Island", True), ("Hawaï", True), ("Texas", False)):
        svg = figures_typst.compile_svg("map", f'#map(countries: ("USA",), regions: ("{state}",), labels: false)')
        assert ("#d9822b" in svg) == circled, state


def test_a_map_with_everything_stays_within_a_figures_size():
    """Rivers, reliefs, waters and regions drawn as the countries are (cut to the frame, thinned):
    a full map of France, or the world's oceans, within a figure's size."""
    for body in (
        '#map(countries: ("France",), regions: ("Bretagne", "Occitanie"), rivers: ("Loire", "Seine", "Rhône"), '
        'reliefs: ("Alpes", "Pyrénées"), waters: ("Manche", "mer Méditerranée"), cities: ("Paris", "Lyon"))',
        '#map(waters: ("océan Pacifique", "océan Atlantique", "océan Indien"))',
    ):
        assert len(figures.clean(figures_typst.compile_svg("map", body))) < figures.MAX_SIZE, body


def test_the_atlas_folds_names_as_typst_does():
    """tools/atlas.py and the map function fold a name the same way (one table of marked
    letters, in the atlas): a city found with its marks and ligatures, or without."""
    for written, plain in (("Łódź", "Lodz"), ("Saint-Pétersbourg", "saint petersbourg"), ("Kraków", "KRAKOW")):
        country = "Russie" if written.startswith("Saint") else "Pologne"
        a, b = (
            figures_typst.compile_svg("map", f'#map(countries: ("{country}",), cities: ("{w}",), labels: false)')
            for w in (written, plain)
        )
        assert a == b, written


def test_the_places_of_history_kept_as_listed():
    """tools/atlas-history.json (what Wikidata gave, kept: the same atlas whatever day it is
    made) holds tools/atlas.py's HISTORY, in its order: a place added or removed without
    --refresh-history shows here, not at the next build."""
    import sys

    sys.path.insert(0, str(figures_typst.HERE.parent.parent / "tools"))
    import atlas

    kept = json.loads(atlas.HISTORY_FILE.read_text(encoding="utf-8"))
    assert [p["title"] for p in kept] == [title for title, _ in atlas.HISTORY]
    assert all(p["n"] and len(p["xy"]) == 2 for p in kept)


def _fills(svg: str) -> list[str]:
    """The colours a map fills its shapes with (its text's black left out: the legend's)."""
    return [f for f in re.findall(r'fill="(#[0-9a-f]{6})"', svg) if f != "#000000"]


def test_groups_coloured_one_colour_each_with_a_legend():
    """Countries coloured by group (alliances, a union's members by year): each group its own
    colour, a key under the map in it; the same countries alone in `countries` have neither."""
    entente = '(name: "Entente", countries: ("France", "Royaume-Uni"))'
    alliance = '(name: "Alliance", countries: ("Allemagne", "Italie"))'
    grouped = figures_typst.compile_svg("map", f"#map(groups: ({entente}, {alliance}), labels: false)")
    plain = figures_typst.compile_svg(
        "map", '#map(countries: ("France", "Royaume-Uni", "Allemagne", "Italie"), labels: false)'
    )
    tints = set(_fills(grouped)) - set(_fills(plain))
    assert len(tints) == 2  # one colour a group, nothing else new
    # The legend: the groups' names written under the map (another name, another drawing)
    renamed = figures_typst.compile_svg(
        "map", f"#map(groups: ({entente.replace('Entente', 'Triple-Entente')}, {alliance}), labels: false)"
    )
    assert renamed != grouped
    height = lambda svg: float(re.search(r'height="([\d.]+)pt"', svg).group(1))  # noqa: E731
    assert height(grouped) > height(plain)


def test_groups_all_framed():
    """The frame holds every group (France's and Japan's): each drawn in its colour, not
    only its key in the legend."""
    svg = figures_typst.compile_svg(
        "map", '#map(groups: ((name: "A", countries: ("France",)), (name: "B", countries: ("Japon",))))'
    )
    plain = set(_fills(figures_typst.compile_svg("map", '#map(countries: ("France", "Japon"))')))
    tints = [f for f in _fills(svg) if f not in plain]
    assert len(set(tints)) == 2 and all(tints.count(t) >= 2 for t in set(tints))  # a country and its key


def test_a_country_far_larger_than_the_groups_framed_near_them():
    """Russia beside France and Germany: the map framed on them and Russia's part nearest,
    not to the Pacific (Paris and Berlin wide apart), Russia's own map whole."""
    svg = figures_typst.compile_svg(
        "map",
        '#map(groups: ((name: "A", countries: ("France", "Allemagne")), (name: "B", countries: ("Russie",))), '
        'cities: ("Paris", "Berlin"), labels: false)',
    )
    dots = [float(x) for x in re.findall(r'<path fill="#d62f2f"[^>]*transform="translate\(([\d.]+) ', svg)]
    width = float(re.search(r'width="([\d.]+)pt"', svg).group(1))
    assert len(dots) == 2 and abs(dots[0] - dots[1]) > width / 10


def test_a_region_coloured_in_a_group():
    """A group of regions (China's west), their country shown: drawn in the group's colour."""
    svg = figures_typst.compile_svg(
        "map", '#map(countries: ("Chine",), groups: ((name: "Ouest", regions: ("Tibet", "Xinjiang")),))'
    )
    plain = set(_fills(figures_typst.compile_svg("map", '#map(countries: ("Chine",))')))
    assert len({f for f in _fills(svg) if f not in plain}) == 1


@pytest.mark.parametrize(
    ("groups", "said"),
    [
        ('((name: "A", countries: ("Atlantide",)),)', r"no country called .Atlantide."),
        ('((name: "A", countries: ("France",)), (name: "B", countries: ("France",)))', r"is in two groups"),
        ('((name: "A"),)', r"holds no country nor region"),
        ('(("France",),)', r"a group is \(name"),
        ('((name: "A", countries: ("France",), color: red),)', r"not .color."),
        ("(" + '(name: "A", countries: ("France",)),' * 9 + ")", r"at most 8 groups"),
    ],
)
def test_a_group_wrongly_written_said(groups, said):
    """A group the map can't draw stops the figure, saying why, for the AI to write it again;
    never guessed."""
    with pytest.raises(figures_typst.Unusable, match=said):
        figures_typst.compile_svg("map", f"#map(groups: {groups})")


def _atlas_folder():
    """The atlas package as Typst reads it (unpacked), and its version."""
    version = re.search(r"notosaurus-atlas:([\d.]+)", (figures_typst.RULES / "map.typ").read_text()).group(1)
    return figures_typst.packages() / "preview" / "notosaurus-atlas" / version, version


def _query(function: str, items: tuple[str, ...], what: str) -> list:
    """What the atlas's `function` (read-routes, read-flows) finds for `items`, `what` taken
    from each (a Typst expression of `r`)."""
    import shutil
    import tempfile
    from pathlib import Path

    import typst

    folder, version = _atlas_folder()
    source = (
        f'#import "@preview/notosaurus-atlas:{version}": {function}\n'
        f"#let found = {function}(("
        + "".join(r + "," for r in items)
        + '), (), json("ways.json"), json("waters.json"), json("reliefs.json"))\n'
        f"#metadata(found.map(r => {what})) <found>\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        for name in ("ways.json", "waters.json", "reliefs.json"):  # the package's, beside the document
            shutil.copy(folder / name, tmp)
        path = Path(tmp) / "found.typ"
        path.write_text(source, encoding="utf-8")
        found = typst.query(path, "<found>", field="value", root=tmp, package_path=str(folder.parent.parent.parent))
    (value,) = json.loads(found)
    return value


def _ways(*routes: str) -> list[list[tuple[float, float]]]:
    """Each route's way (its points, in degrees) as the map function finds it."""
    return [[(x / 100, y / 100) for x, y in way] for way in _query("read-routes", routes, "r.way")]


def _land():
    """The atlas's land as a sea route sees it: its countries, islands too small to be in the
    way left out (tools/atlas.py, SEA_ISLAND), a turn east and west too."""
    import sys

    import shapely
    import shapely.affinity

    sys.path.insert(0, str(figures_typst.HERE.parent.parent / "tools"))
    import atlas

    folder, _ = _atlas_folder()
    countries = json.loads((folder / "atlas.json").read_text(encoding="utf-8"))["countries"]
    land = shapely.union_all(
        [
            shapely.make_valid(shapely.Polygon([(x / 100, y / 100) for x, y in r]))
            for c in countries.values()
            for r in c["r"]
        ]
    )
    parts = [shapely.Polygon(g.exterior) for g in getattr(land, "geoms", [land]) if g.area >= atlas.SEA_ISLAND]
    whole = shapely.union_all(parts)
    return shapely.union_all([shapely.affinity.translate(whole, dx) for dx in (-360, 0, 360)])


@pytest.mark.parametrize(
    ("route", "check"),
    [
        # Round Africa when no canal is named (Vasco da Gama's), through Suez when it is
        ('(name: "A", places: ("Lisbonne", "Calicut"))', lambda way: min(y for _, y in way) < -34),
        ('(name: "A", places: ("Lisbonne", "canal de Suez", "Calicut"))', lambda way: min(y for _, y in way) > 0),
        # A port at a canal's mouth opens it, leaving or coming
        ('(name: "A", places: ("Singapour", "Suez", "Rotterdam"))', lambda way: min(y for _, y in way) > 0),
        ('(name: "A", places: ("Rotterdam", "Suez"))', lambda way: min(y for _, y in way) > 25),
        # Through the straits (Gibraltar, the Dardanelles and the Bosporus; the Danish ones)
        ('(name: "A", places: ("Marseille", "Odessa"))', lambda way: True),
        ('(name: "A", places: ("Rotterdam", "Saint-Pétersbourg"))', lambda way: True),
        # Through a passage the atlas has as a point (Hormuz: Wikidata's), by it
        (
            '(name: "A", places: ("Basra", "détroit d\'Ormuz", "Bombay"))',
            lambda way: any(abs(x - 56.5) + abs(y - 26.6) < 1.5 for x, y in way),
        ),
        # Across the Pacific, not round the world; never through the Arctic's ice
        (
            '(name: "A", places: ("Shanghai", "Los Angeles"))',
            lambda way: max(x for x, _ in way) - min(x for x, _ in way) < 180,
        ),
        ('(name: "A", places: ("Rotterdam", "Shanghai"))', lambda way: max(y for _, y in way) < 66.5),
    ],
)
def test_a_sea_route_goes_by_sea(route, check):
    """A sea route's way is computed over the sea: none of its legs crosses land, but a port's
    way in from its coast (a city a little inland, up its river's mouth)."""
    import shapely

    land = _land()
    (way,) = _ways(route)
    folder, _ = _atlas_folder()
    cities = {
        (c["x"] / 100, c["y"] / 100) for c in json.loads((folder / "atlas.json").read_text(encoding="utf-8"))["cities"]
    }
    # (a port's way in, a canal's from end to end: over land)
    seen = lambda p: (round((p[0] + 180) % 360 - 180, 2), p[1])  # noqa: E731  (across the 180th meridian)
    legs = [
        shapely.LineString((a, b))
        for a, b in itertools.pairwise(way)
        if seen(a) not in cities and seen(b) not in cities
    ]
    assert len(legs) > 3
    assert not any(leg.crosses(land) or leg.within(land) for leg in legs)
    assert check(way)


def test_a_land_route_goes_from_place_to_place():
    """A route by land: straight from each place to the next, in their order."""
    (way,) = _ways('(name: "Soie", places: ("Xian", "Samarcande", "Bagdad"), by: "land")')
    assert len(way) == 3 and way[0][0] > way[1][0] > way[2][0]


def _colours(svg: str) -> set[str]:
    return set(re.findall(r'(?:fill|stroke)="(#[0-9a-f]{6})"', svg))


def test_routes_and_flows_drawn_in_their_colours_with_a_legend():
    """Each route and each kind of flow in its own colour, its arrows, and a legend under the
    map: with groups too, theirs beside."""
    plain = figures_typst.compile_svg("map", '#map(cities: ("Lisbonne", "Calicut"), labels: false)')
    route = '(name: "Vasco de Gama", places: ("Lisbonne", "Calicut"))'
    drawn = figures_typst.compile_svg("map", f"#map(routes: ({route},), labels: false)")
    assert len(_colours(drawn) - _colours(plain) - {"#000000"}) == 1  # its line and arrows (the legend's text black)
    height = lambda svg: float(re.search(r'height="([\d.]+)pt"', svg).group(1))  # noqa: E731
    flows = '(from: "Mexique", to: "États-Unis", kind: "migrations"), (from: "Maroc", to: "France", kind: "tourisme")'
    both = figures_typst.compile_svg(
        "map",
        f'#map(routes: ({route},), flows: ({flows}), groups: ((name: "G", countries: ("Inde",)),), labels: false)',
    )
    assert len(_colours(both) - _colours(drawn)) >= 3  # the two kinds of flows, the group's tint
    assert height(both) > height(plain)


def test_routes_and_flows_framed():
    """The frame holds every route's way and every flow's ends: the map of a voyage round
    Africa shows its south, a flow from Mexico to France both."""
    lone = figures_typst.compile_svg("map", '#map(cities: ("Lisbonne", "Calicut"), labels: false)')
    round_africa = figures_typst.compile_svg(
        "map", '#map(routes: ((name: "A", places: ("Lisbonne", "Calicut")),), labels: false)'
    )

    def aspect(svg: str) -> float:
        size = re.search(r'width="([\d.]+)pt" height="([\d.]+)pt"', svg)
        return float(size.group(2)) / float(size.group(1))

    assert aspect(round_africa) > aspect(lone) * 1.3  # down to the Cape: taller
    flow = figures_typst.compile_svg("map", '#map(flows: ((from: "Mexico", to: "Paris"),), labels: false)')
    dots = re.findall(r'<path fill="#d62f2f"[^>]*transform="translate\(([\d.]+) ', flow)
    width = float(re.search(r'width="([\d.]+)pt"', flow).group(1))
    assert len(dots) == 2 and abs(float(dots[0]) - float(dots[1])) > width / 3


@pytest.mark.parametrize(
    ("asked", "said"),
    [
        ('routes: ((name: "A", places: ("Lisbonne", "Atlantide")),)', r"no place called .Atlantide."),
        ('routes: ((name: "A", places: ("Lisbonne",)),)', r"fewer than two places"),
        ('routes: ((name: "A", places: ("Paris", "Calicut")),)', r".Paris. is not by the sea"),
        ('routes: ((name: "A", places: ("Lisbonne", "mer Caspienne")),)', r"no way by sea"),
        ('routes: ((name: "A", places: ("Lisbonne", "Calicut"), by: "air"),)', r"by .sea. or by .land."),
        ('routes: ((name: "A", places: ("Lisbonne", "Calicut"), color: red),)', r"not .color."),
        ('routes: (("Lisbonne", "Calicut"),)', r"a route is \(name"),
        ('flows: ((from: "Maroc"),)', r"a flow is \(from"),
        ('flows: ((from: "Maroc", to: "France", value: "beaucoup"),)', r"value is a number"),
        ('flows: ((from: ("Maroc", "Algérie"), to: "France"),)', r"several places .*from-name"),
        ("routes: (" + '(name: "A", places: ("Lisbonne", "Calicut")),' * 9 + ")", r"at most 8 routes"),
    ],
)
def test_a_route_or_flow_wrongly_written_said(asked, said):
    """A route or flow the map can't draw stops the figure, saying why, for the AI to write
    it again; never guessed."""
    with pytest.raises(figures_typst.Unusable, match=said):
        figures_typst.compile_svg("map", f"#map({asked})")


def _point(name: str) -> tuple[float, float]:
    """A city's point in the atlas, in degrees (the first of that name)."""
    folder, _ = _atlas_folder()
    for c in json.loads((folder / "atlas.json").read_text(encoding="utf-8"))["cities"]:
        if name in c["n"]:
            return c["x"] / 100, c["y"] / 100
    raise KeyError(name)


def test_a_city_whose_name_others_share_is_the_one_on_the_way():
    """A route's city whose name other cities bear is the one nearest the places before and
    after it, the most populated only when nothing says otherwise."""
    (east,) = _ways('(name: "A", places: ("Beyrouth", "Tripoli"), by: "land")')
    (west,) = _ways('(name: "A", places: ("Tunis", "Tripoli"), by: "land")')
    assert east[-1][0] > 30 > west[-1][0]


def test_a_place_said_with_its_country():
    """A place followed by its country after a comma is taken in that country; one the atlas
    lacks there is said, its country offered (never a namesake elsewhere, never guessed)."""
    (way,) = _ways('(name: "A", places: ("Madrid", "Valencia, Venezuela"), by: "land")')
    assert way[-1][0] < -60  # Venezuela's, not Spain's
    # (one the atlas lacks there: said, the country offered, never El Salvador's capital)
    with pytest.raises(figures_typst.Unusable, match=r"no place called .San Salvador. in Bahamas.*name the country"):
        figures_typst.compile_svg("map", '#map(routes: ((name: "A", places: ("Lisbonne", "San Salvador, Bahamas")),))')
    figures_typst.compile_svg("map", '#map(cities: ("Valencia, Venezuela",))')


def test_an_ocean_is_all_its_parts():
    """An ocean the atlas holds in parts (north and south) is all of them: a route across the
    North Pacific stays in it, the ocean drawn whole."""
    (way,) = _ways('(name: "A", places: ("Shanghai", "océan Pacifique", "Los Angeles"))')
    assert min(y for _, y in way) > 15
    one = figures_typst.compile_svg("map", '#map(waters: ("North Pacific Ocean",))')
    whole = figures_typst.compile_svg("map", '#map(waters: ("océan Pacifique",))')
    assert len(re.findall(r'fill="#b5d2ec"', whole)) > len(re.findall(r'fill="#b5d2ec"', one))


def test_a_flow_from_a_region_named_tinted_and_from_its_nearest_place():
    """A flow from several places (a region the atlas lacks) is named, its places tinted, its
    arrow leaving from the place nearest where it goes."""
    flow = '(from: ("Mexique", "Brésil", "Colombie"), from-name: "Amérique latine", to: "États-Unis")'
    ((start, end),) = _query("read-flows", (flow,), "(r.from.at, r.to.at)")
    folder, _ = _atlas_folder()
    ways = json.loads((folder / "ways.json").read_text(encoding="utf-8"))
    assert start == ways["countries"]["MEX"]["at"] and end == ways["countries"]["USA"]["at"]
    # A region's name that is a city's too (Kuwait) is the country
    gulf = '(from: "Inde", to: ("Arabie saoudite", "Koweït"), to-name: "Golfe")'
    (kinds,) = _query("read-flows", (gulf,), "r.to.places.map(p => p.kind)")
    assert kinds == ["country", "country"]
    lone = figures_typst.compile_svg("map", '#map(flows: ((from: "Mexique", to: "États-Unis"),), labels: false)')
    region = figures_typst.compile_svg("map", f"#map(flows: ({flow},), labels: false)")
    assert len(_fills(region)) > len(_fills(lone))  # the region's places


def _arrows(svg: str) -> list[tuple[float, float]]:
    """The flows' arrows: each its width and its line's length (start to end)."""
    found = re.findall(
        r'stroke-width="([\d.]+)" stroke-linecap="butt"[^>]*d="M 0 0m [-\d.]+ [-\d.]+c [-\d. ]*? ([-\d.]+) ([-\d.]+)"',
        svg,
    )
    return [(float(w), (float(dx) ** 2 + float(dy) ** 2) ** 0.5) for w, dx, dy in found]


def test_flows_long_enough_to_see_and_their_widths_apart():
    """On a world map an arrow between neighbours is still long enough to see, and the
    arrows' widths tell their values apart: the least the thinnest, the largest the widest."""
    svg = figures_typst.compile_svg(
        "map",
        "#map(flows: ("
        '(from: "Allemagne", to: "Espagne", value: 2), (from: "Chine", to: "Thaïlande", value: 3),'
        '(from: "États-Unis", to: "Mexique", value: 2.5)), labels: false)',
    )
    arrows = _arrows(svg)
    assert len(arrows) == 3
    assert min(length for _, length in arrows) > 12
    widths = [w for w, _ in arrows]
    assert max(widths) >= 3 * min(widths)


def _labels(svg: str) -> list[tuple[float, float, float, float]]:
    """The names' boxes on the map: x, y, width, height."""
    found = re.findall(
        r'<g transform="translate\(([-\d.]+) ([-\d.]+)\)"><path fill="#ffffffb2"[^>]*d="M 0 0v ([\d.]+)h ([\d.]+)v', svg
    )
    return [(float(x), float(y), float(w), float(h)) for x, y, h, w in found]


def test_names_never_cut_by_the_frame():
    """Every name stays whole within the map, the frame grown or the name moved in: a strait
    at the frame's edge too."""
    svg = figures_typst.compile_svg(
        "map",
        '#map(cities: ("Shanghai", "Rotterdam"), routes: ((name: "A", places: ("Shanghai", "Singapour",'
        ' "détroit de Malacca", "canal de Suez", "détroit de Gibraltar", "Rotterdam")),'
        ' (name: "B", places: ("Shanghai", "océan Pacifique", "Los Angeles"))))',
    )
    width, height = (
        float(v) for v in re.search(r'fill="#e8f1f8"[^>]*d="M 0 0v ([\d.]+)h ([\d.]+)v', svg).groups()[::-1]
    )
    labels = _labels(svg)
    assert len(labels) >= 7
    for x, y, w, h in labels:
        assert x >= 0 and y >= 0 and x + w <= width + 0.01 and y + h <= height + 0.01


def test_a_sea_a_route_crosses_named_on_its_way():
    """A sea or an ocean a route crosses is named on itself, where the route crosses it
    (halfway from the place before to the place after), not where the route enters it."""
    svg = figures_typst.compile_svg(
        "map", '#map(routes: ((name: "A", places: ("Séville", "océan Atlantique", "Rio de Janeiro")),))'
    )
    (sea,) = [
        (float(x), float(y))
        for x, y in re.findall(
            r'<g transform="translate\(([-\d.]+) ([-\d.]+)\)"><path fill="#ffffffb2"'
            r'[^<]*<g[^>]*><use[^>]*fill="#1f5a8f"',
            svg,
        )
    ]
    dots = sorted(
        float(y) for y in re.findall(r'<path fill="#d62f2f"[^>]*transform="translate\([\d.]+ ([\d.]+)\)', svg)
    )
    assert dots[0] + 15 < sea[1] < dots[-1] - 15  # well south of Seville, north of Rio


def _atlas_value(tmp_path, expression: str):
    """What the atlas's map function computes, read back (a Typst value, as JSON)."""
    import typst

    version = re.search(r"notosaurus-atlas:([\d.]+)", (figures_typst.RULES / "map.typ").read_text()).group(1)
    page = tmp_path / "query.typ"
    page.write_text(
        f'#import "@preview/notosaurus-atlas:{version}": *\n#metadata({expression}) <value>\n', encoding="utf-8"
    )
    found = typst.query(
        str(page), "<value>", field="value", one=True, format="json", package_path=str(figures_typst.packages())
    )
    return json.loads(found)


def test_a_past_years_states_with_their_borders_then():
    """1914's alliances and the Cold War's blocs: the atlas had today's countries only, the
    Austro-Hungarian Empire, the Soviet Union or East Germany drawn as Austria, Russia or
    nothing. A map's `year` draws that time's states (OpenHistoricalMap), named then in the
    page's languages, by their short names too (« RDA », « Allemagne » in 1914)."""

    def drawn(body):
        return figures_typst.compile_svg("map", body)

    for names in (("Autriche-Hongrie", "Austria-Hungary", "Österreich-Ungarn"), ("URSS", "Union soviétique", "USSR")):
        year = 1914 if "Autriche" in names[0] else 1960
        assert len({drawn(f'#map(year: {year}, countries: ("{n}",), labels: false)') for n in names}) == 1
    # the German Empire's borders are not today's Germany's; 1914's lasts the war
    today = drawn('#map(countries: ("Allemagne",), labels: false)')
    then = {drawn(f'#map(year: {y}, countries: ("Allemagne",), labels: false)') for y in (1914, 1918)}
    assert len(then) == 1 and today not in then
    assert drawn('#map(year: 1985, countries: ("RDA", "RFA"), labels: false)')
    assert drawn('#map(year: 2005, countries: ("Allemagne",), labels: false)') == today  # today's from 1992
    with pytest.raises(figures_typst.Unusable, match="Autriche-Hongrie"):
        drawn('#map(countries: ("Autriche-Hongrie",))')  # today's atlas: no such country


@pytest.mark.parametrize(
    ("year", "states"),
    [
        (1815, ("Prusse", "Empire d'Autriche", "royaume uni des Pays-Bas", "Empire russe", "Royaume-Uni")),
        (1866, ("Italie", "Prusse", "Empire d'Autriche", "royaume de Bavière")),
        (1880, ("Empire allemand", "Autriche-Hongrie", "Italie", "Algérie")),
        (1900, ("Afrique-Occidentale française", "Éthiopie", "Afrique orientale allemande")),
        (1923, ("URSS", "république de Weimar", "Tchécoslovaquie", "Yougoslavie", "Pologne")),
        (1938, ("Troisième Reich", "Tchécoslovaquie", "URSS")),
        (1942, ("Allemagne", "régime de Vichy", "Slovaquie", "Hongrie", "Croatie", "Mandchoukouo")),
        (1946, ("zone d'occupation soviétique en Allemagne", "zone d'occupation française en Allemagne", "Autriche")),
        (1960, ("RDA", "RFA", "Algérie", "Angola", "Chine")),
    ],
)
def test_the_years_of_history_lessons(year, states):
    """The Congress of Vienna's Europe, Italy made, after Germany's unity, Africa partitioned,
    between the wars, before the war, Europe under Germany, Germany's zones, the Cold War:
    every year from 1815 to 1991, its states by their names then or their short names (a
    kingdom of Hungary « Hongrie », the Ethiopian Empire « Éthiopie »: the country of today
    each mostly is)."""
    names = ", ".join(f'"{s}"' for s in states)
    assert figures_typst.compile_svg("map", f"#map(year: {year}, countries: ({names},))").startswith("<svg")


@pytest.mark.parametrize(
    ("year", "land", "ruler"),
    [
        (1880, "Algérie", "France"),
        (1960, "Angola", "Portugal"),
        (1942, "Taïwan", "Japon"),
        (1942, "Corée", "Japon"),
        (1914, "Égypte", "Royaume-Uni"),
        (1914, "Indochine française", "France"),
        (1880, "Sénégal", "France"),
    ],
)
def test_a_land_a_state_ruled_far_from_its_own_is_its(tmp_path, year, land, ruler):
    """Algeria was France's departments, Angola Portugal's province: OpenHistoricalMap draws
    them as part of France or Portugal, and « Algérie » was no state of 1960. A state's land
    far from its own, on another of today's countries, is a land it ruled named as that
    country (Korea, two countries today: « Corée »). Egypt, which OHM lacks in 1914, and
    Senegal in 1880 (« Senegal (FR) ») from historical-basemaps, with their ruler; French
    Indochina, which says nowhere whose it was, France's (RULED)."""
    expression = (
        f"{{ let all = borders({year}); let at(n) = find-country(n, all: all, year: {year}); "
        f'all.at(at("{land}")).at("o", default: none) == at("{ruler}") }}'
    )
    assert _atlas_value(tmp_path, expression)


def test_a_country_of_its_own_is_nobodys_colony(tmp_path):
    """OpenHistoricalMap says Kenya's republic (1985) a colony of the British Empire: a state
    that says it was a country, not a colony, ruled by none; Jamaica's colony (1914) still
    the United Kingdom's."""
    expression = (
        '{ let all = borders(1985); all.at(find-country("Kenya", all: all, year: 1985)).at("o", default: none) }'
    )
    assert _atlas_value(tmp_path, expression) is None
    expression = (
        '{ let all = borders(1914); all.at(find-country("Jamaïque", all: all, year: 1914)).at("o", default: none) }'
    )
    assert _atlas_value(tmp_path, expression) is not None


def test_a_colonial_empire_is_its_ruler_and_every_land_it_ruled(tmp_path):
    """A colonial empire's map (1914) as a group `empire: "France"`: the ruler and its colonies
    and protectorates (OHM's colony_of, Wikidata's « part of », a colony's name: « German
    East Africa »), never a colony listed by hand."""
    groups = '((name: "E", empire: "France"), (name: "A", empire: "Allemagne"))'
    expression = (
        f"read-groups({groups}, all: borders(1914), year: 1914).map(g => g.countries.map(c => borders(1914).at(c).n))"
    )
    french, german = ({name for names in group for name in names} for group in _atlas_value(tmp_path, expression))
    assert {"France", "French West Africa", "Algeria", "French protectorate in Morocco"} <= french
    assert {"German Empire", "Kamerun", "Togoland", "German East Africa"} <= german and "Kamerun" not in french


def test_a_past_years_states_are_places_of_flows():
    """A flow between the Cold War's states (East Germany's refugees to West Germany): from
    each state's inmost point, as a country of today; « RDA » was no place for a flow."""
    flow = '#map(year: 1960, countries: ("RDA", "RFA"), flows: ((from: "RDA", to: "RFA", kind: "réfugiés"),))'
    assert figures_typst.compile_svg("map", flow).startswith("<svg")


@pytest.mark.parametrize(
    ("body", "said"),
    [
        ('#map(year: 1789, countries: ("France",))', "no borders of 1789"),
        ('#map(year: 1914, countries: ("France",), regions: ("Bretagne",))', "no regions on a map of a past year"),
        ('#map(groups: ((name: "E", empire: "France"),))', "an empire is a past year's"),
        ('#map(year: 1914, countries: ("Tchécoslovaquie",))', "no state called"),
    ],
)
def test_a_past_year_the_atlas_lacks_said_never_drawn_wrong(body, said):
    """Another time than the atlas's years (1789, before 1815) refused, said, rather than drawn
    with the borders of another; a state that didn't exist then refused too."""
    with pytest.raises(figures_typst.Unusable, match=said):
        figures_typst.compile_svg("map", body)


def test_the_past_states_names_kept_as_listed():
    """tools/atlas-borders.json (what Wikidata gave the past states, kept: the same atlas
    whatever day it is made) has every name ALSO and ITEMS go by (or OHM's own, for a state
    Wikidata lacks: RULED's): a state Wikidata renamed would lose its short names (« URSS »,
    « Allemagne ») without a word."""
    import sys

    sys.path.insert(0, str(figures_typst.HERE.parent.parent / "tools"))
    import atlas

    kept = json.loads(atlas.BORDERS_FILE.read_text(encoding="utf-8"))
    english = {item["en"] for item in kept["items"].values()} | set(kept["articles"])
    assert set(atlas.ALSO) <= english | set(atlas.RULED)
    assert all(kept["articles"].get(article) for _, article in atlas.ITEMS.values())


def test_a_canal_is_a_water_drawn_where_it_is():
    """A canal the atlas knows (a sea route's, ways.json) is a water too, by any of its names:
    "canal de Suez" in `waters` stopped the figure ("no water called"), the AI then leaving it out."""
    folder, _ = _atlas_folder()
    canals = json.loads((folder / "ways.json").read_text(encoding="utf-8"))["canals"]
    for canal in canals:
        maps = {figures_typst.compile_svg("map", f'#map(waters: ("{n}",), labels: false)') for n in canal["n"]}
        assert len(maps) == 1, canal["n"]
    assert figures_typst.compile_svg("map", '#map(waters: ("canal de Kiel", "canal de Corinthe"))').startswith("<svg")


@pytest.mark.parametrize(
    ("names"),
    [
        ("détroit d'Ormuz", "Strait of Hormuz", "Straße von Hormus", "Estrecho de Ormuz", "stretto di Hormuz"),
        ("pas de Calais", "Strait of Dover", "Straße von Dover", "Paso de Calais", "Stretto di Dover"),
        ("détroit de Béring", "Bering Strait", "Beringstraße", "Estrecho de Bering", "Estreito de Bering"),
        ("Bouches de Bonifacio", "Strait of Bonifacio", "Bocche di Bonifacio", "Estreito de Bonifacio"),
        ("détroit de Gibraltar", "Strait of Gibraltar", "stretto di Gibilterra", "Estrecho de Gibraltar"),
    ],
)
def test_a_strait_by_its_name_in_every_language(names):
    """The sea's passages Natural Earth lacks (Hormuz, Dover, Bering, Bonifacio) or names in
    two languages only (Gibraltar): by their names in the page's languages (Wikidata's), one map."""
    maps = {figures_typst.compile_svg("map", f'#map(waters: ("{n}",), labels: false)') for n in names}
    assert len(maps) == 1


def test_every_water_has_its_sea_ways():
    """ways.json's waters are waters.json's, in its order: a passage added (a point) has the
    nodes a sea route passing it goes by (test_a_sea_route_goes_by_sea: through Hormuz)."""
    folder, _ = _atlas_folder()
    waters = json.loads((folder / "waters.json").read_text(encoding="utf-8"))
    ways = json.loads((folder / "ways.json").read_text(encoding="utf-8"))
    assert len(ways["waters"]) == len(waters)


def _rings(svg: str) -> int:
    """How many small waters are ringed."""
    return len(re.findall(r'stroke="#1f5a8f"', svg))


def test_a_water_too_small_to_see_is_ringed_and_named_within():
    """A strait or a canal on a world map (less than 10pt across, or a point): a ring at its
    place, its name beside it within the frame; a sea seen whole has none."""
    svg = figures_typst.compile_svg(
        "map",
        '#map(waters: ("détroit de Gibraltar", "canal de Suez", "détroit d\'Ormuz", "détroit de Malacca",'
        ' "canal de Panama"))',
    )
    assert _rings(svg) == 5
    width, height = (
        float(v) for v in re.search(r'fill="#e8f1f8"[^>]*d="M 0 0v ([\d.]+)h ([\d.]+)v', svg).groups()[::-1]
    )
    labels = _labels(svg)
    assert len(labels) == 5
    for x, y, w, h in labels:
        assert x >= 0 and y >= 0 and x + w <= width + 0.01 and y + h <= height + 0.01
    for a, b in itertools.combinations(labels, 2):
        assert a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1]
    assert _rings(figures_typst.compile_svg("map", '#map(countries: ("France",), waters: ("mer Méditerranée",))')) == 0


@pytest.mark.parametrize(
    ("written", "close"),
    [
        ("détroit de Gibraltare", "détroit de Gibraltar"),  # a letter too many
        ("golfe de Gascogn", "golfe de Gascogne"),
        ("détroit d'Hormouz", "Hormuz"),  # its own word a letter from the atlas's
    ],
)
def test_a_water_the_atlas_lacks_said_with_the_nearest_it_has(written, close):
    """A name the atlas lacks, written a letter or two from one it has: the figure stops
    naming it, for the AI to write it so; one far from all: "leave it out" only."""
    with pytest.raises(figures_typst.Unusable, match=rf"no water called .{re.escape(written)}.*it has .*{close}"):
        figures_typst.compile_svg("map", f'#map(waters: ("{written}",))')
    with pytest.raises(figures_typst.Unusable, match=r"no water called .Trifouille. in the atlas: leave it out"):
        figures_typst.compile_svg("map", '#map(waters: ("Trifouille",))')


def test_the_passages_kept_as_listed():
    """tools/atlas-passages.json (what Wikidata gave, kept) holds tools/atlas.py's PASSAGES,
    in its order, each with its names and its point."""
    import sys

    sys.path.insert(0, str(figures_typst.HERE.parent.parent / "tools"))
    import atlas

    kept = json.loads(atlas.PASSAGES_FILE.read_text(encoding="utf-8"))
    assert [p["title"] for p in kept] == [title for title, _ in atlas.PASSAGES]
    assert all(p["n"] and len(p["xy"]) == 2 for p in kept)


def test_a_map_centred_on_a_pole():
    """The Arctic of a HGGSP lesson (its countries, its ocean, the sea routes along Russia and
    through Canada's islands) and Antarctica: drawn as seen from above the pole, never as a
    band across the top of a world map; within a figure's size, every Arctic coast in it."""
    arctic = (
        '#map(pole: "north", countries: ("Russie", "Canada", "États-Unis", "Norvège", "Groenland"), '
        'waters: ("océan Arctique",), routes: ((name: "Route maritime du Nord", places: ("Mourmansk", '
        '"mer de Kara", "mer de Laptev", "mer des Tchouktches"), by: "sea"), (name: "Passage du Nord-Ouest", '
        'places: ("mer de Baffin", "passage du Nord-Ouest", "mer de Beaufort", "mer des Tchouktches"), by: "sea")))'
    )
    south = '#map(pole: "south", countries: ("Antarctique",), waters: ("océan Austral",))'
    flat = '#map(countries: ("Russie", "Canada", "États-Unis", "Norvège", "Groenland"))'
    drawn = [figures.clean(figures_typst.compile_svg("map", body)) for body in (arctic, south, flat)]
    assert all(len(svg) < figures.MAX_SIZE for svg in drawn)
    assert drawn[0] != drawn[2]
    with pytest.raises(figures_typst.Unusable, match="pole"):
        figures_typst.compile_svg("map", '#map(pole: "arctic", countries: ("Canada",))')


def test_a_ring_round_the_pole_drawn_without_its_seam():
    """Natural Earth cuts a ring that goes round the world along the 180th meridian and the
    pole (Antarctica's): seen from above the pole, its outline drew a line from its coast to
    the pole. The outline leaves its seams out, the land stays whole."""
    from PIL import Image

    svg = figures_typst.compile_svg("map", '#map(pole: "south", countries: ("Antarctique",), labels: false)')
    image = Image.open(io.BytesIO(figures.to_png(figures.clean(svg)))).convert("L")
    (w, h) = image.size
    # (the pole at the middle; the 180th meridian down from it, short of the Ross Sea's coast)
    assert all(image.getpixel((w // 2, h // 2 + dy)) > 200 for dy in range(3, h // 15))


def test_every_place_the_atlas_lacks_said_at_once():
    """A route through two places the atlas lacks was refused for the first only: the AI fixed
    it, met the second and gave up (the Arctic's sea routes, drawn by hand). Every one said in
    one message, the next try fixes them all."""
    body = (
        '#map(routes: ((name: "R", places: ("Mourmansk", "mer de Nulle-Part", "mer des Tchouktches"), by: "sea"),'
        ' (name: "P", places: ("Halifax", "baie de Nulle-Part"), by: "sea")))'
    )
    with pytest.raises(figures_typst.Unusable, match='"mer de Nulle-Part", "baie de Nulle-Part"'):
        figures_typst.compile_svg("map", body)


@pytest.mark.parametrize("water", ["mer des Laptev", "baie de Baffin"])
def test_the_arctic_waters_as_french_writes_them(water):
    """« mer des Laptev » and « baie de Baffin », as French writes them too (Natural Earth:
    « mer de Laptev », « mer de Baffin »)."""
    assert figures_typst.compile_svg("map", f'#map(pole: "north", waters: ("{water}",))').startswith("<svg")


def test_a_water_named_where_it_is_on_a_map_centred_on_a_pole():
    """A water's name goes at its own place, as drawn: on a map centred on the pole, the Arctic
    Ocean's was put where its longitude and latitude would be on a flat map, in a corner."""
    from PIL import Image, ImageChops

    def drawn(labels):
        body = f'#map(pole: "north", waters: ("océan Arctique",), labels: {labels})'
        svg = figures_typst.compile_svg("map", body)
        return Image.open(io.BytesIO(figures.to_png(figures.clean(svg)))).convert("RGB")

    # (where the name is: what it changes on the map)
    (x0, y0, x1, y1) = ImageChops.difference(drawn("true"), drawn("false")).getbbox()
    (w, h) = drawn("false").size
    assert w / 4 < (x0 + x1) / 2 < 3 * w / 4 and h / 4 < (y0 + y1) / 2 < 3 * h / 4


def test_a_region_that_is_a_country_shown_as_one():
    """« Danemark par le Groenland »: the AI put Greenland among Denmark's regions, but the
    atlas has it as a country of its own, and the map was refused (the Arctic drawn by hand)."""
    body = '#map(pole: "north", countries: ("Danemark", "États-Unis"), regions: ("Groenland", "Alaska"))'
    assert figures_typst.compile_svg("map", body).startswith("<svg")


def _past_states(year: int) -> dict:
    """A year's states as the atlas ships them (borders/<year>.json in its archive)."""
    import tarfile

    (archive,) = figures_typst.ARCHIVES.glob("notosaurus-atlas-*.tar.gz")
    with tarfile.open(archive) as tar:
        return json.loads(tar.extractfile(f"borders/{year}.json").read())["countries"]


def _holding(states: dict, lon: float, lat: float) -> list[str]:
    """The names (the first of each) of the states whose rings hold a point."""
    x, y = lon * 100, lat * 100

    def within(ring):
        inside = False
        for (ax, ay), (bx, by) in zip(ring, ring[1:] + ring[:1], strict=True):
            if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
                inside = not inside
        return inside

    return [s["n"][0] if s["n"] else "" for s in states.values() if any(within(r) for r in s["r"])]


def test_a_federation_keeps_its_colonies_land():
    """French West Africa in 1914 was no more than a piece of today's Niger: OpenHistoricalMap
    draws its colonies over it (Upper Senegal and Niger, Mauritania), and each, lying in it,
    was taken from it. A land lying in another of the same empire is a part of it, the
    federation whole; a state lying in another's (Manchukuo in China) still taken from it."""
    then = _past_states(1914)
    for city, lon, lat in (
        ("Dakar", -17.44, 14.69),
        ("Conakry", -13.68, 9.51),
        ("Bamako", -8.0, 12.65),
        ("Niamey", 2.11, 13.51),
    ):
        assert "Afrique-Occidentale française" in _holding(then, lon, lat), city
    harbin = _holding(_past_states(1942), 126.63, 45.75)
    assert "Mandchoukouo" in harbin and not any("Chine" in n for n in harbin)


def test_a_name_the_atlas_lacks_answered_at_once():
    """The nearest names to one the atlas lacks were measured against every name of every
    water, each folded again: 9 seconds a figure, past the compile's limit under load (the
    tests on Windows cancelled). Measured on the keys folded already, those too long or too
    short skipped: the answer at once, the names as the atlas writes them. Timed against the
    same maps with names the atlas has, drawn just before on the machine as busy (every core
    at work, the packages unpacked first: a fixed limit failed then): no slower than them."""
    import time

    def timed(*maps: tuple[str, str | None]) -> float:
        start = time.monotonic()
        for body, refusal in maps:
            if refusal is None:
                figures_typst.compile_svg("map", body)
            else:
                with pytest.raises(figures_typst.Unusable, match=refusal):
                    figures_typst.compile_svg("map", body)
        return time.monotonic() - start

    known = ('#map(waters: ("golfe de Gascogne",))', None), ('#map(rivers: ("Loire",))', None)
    timed(known[0])  # the packages unpacked (a new atlas: its archive), not timed
    drawn = timed(*known)
    refused = timed(
        ('#map(waters: ("golfe de Gascogn",))', 'it has "golfe de Gascogne"'),
        ('#map(rivers: ("Loir",))', 'it has "Loire"'),
    )
    assert refused < 3 * drawn + 1, (refused, drawn)


def test_real_places_are_a_map_a_plan_is_not():
    """The kinds sent a map of real places with a lesson's own sites or areas to "other" (sites
    of an event, rural areas: "no map"), drawn as free SVG with invented coasts, and let a
    town's sectors go to the map (a country with its capital, no sector). Real towns and areas
    of real land are the map's; a town's inside, a plan, a front drawn across the land are
    other's."""
    kinds = dict(re.findall(r'"(\w+)": (.*?)(?=; "\w+": |$)', figures_typst.KINDS))
    assert "sites of an event, are its cities" in kinds["map"]
    assert "rural areas" in kinds["map"] and "regions or countries coloured by group" in kinds["map"]
    assert "a town's inside" in kinds["map"] and "a front" in kinds["map"]
    assert "a plan or a sketch of a town" in kinds["other"]
    assert "never a box plot nor a crystal, nor real countries, regions or towns" in kinds["other"]


def _apart(labels: list[tuple[float, float, float, float]]) -> bool:
    return all(
        a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1]
        for a, b in itertools.combinations(labels, 2)
    )


def test_a_routes_passages_ringed_their_names_apart():
    """The straits and the canal a route passes, too small to see on a world map: a ring at
    each, as waters' are, and every name apart (« détroit de Gibraltar » was written against
    « détroit de Malacca », east of the Mediterranean, with no mark for either)."""
    svg = figures_typst.compile_svg(
        "map",
        '#map(cities: ("Shanghai", "Singapour", "Rotterdam", "Los Angeles"), routes: ((name: "A", places:'
        ' ("Shanghai", "Singapour", "détroit de Malacca", "canal de Suez", "détroit de Gibraltar", "Rotterdam"),'
        ' by: "sea"), (name: "B", places: ("Shanghai", "océan Pacifique", "Los Angeles"), by: "sea")))',
    )
    assert _rings(svg) >= 3
    labels = _labels(svg)
    assert len(labels) == 8
    assert _apart(labels)


def test_small_regions_named_beside_their_circles_apart():
    """Regions too small to see, close together (Guadeloupe and Martinique on a map of France
    and its overseas regions): each name beside its circle, none on another's (« Martinique »
    was written on « Guadeloupe »)."""
    svg = figures_typst.compile_svg(
        "map",
        '#map(countries: ("France",), regions: ("Guadeloupe", "Martinique", "Guyane", "La Réunion", "Mayotte"))',
    )
    labels = _labels(svg)
    assert len(labels) == 5
    assert _apart(labels)


@pytest.mark.parametrize(
    ("part", "country"),
    [
        ("Guadeloupe", "France"),  # an overseas department: one of France's regions only
        ("Açores", "Portugal"),
        ("îles Canaries", "Espagne"),  # a group of provinces, by CLDR's name
        ("Hawaï", "États-Unis"),
        ("Svalbard", "Norvège"),
        ("Pays-Bas caribéens", "Pays-Bas"),  # Bonaire, Saba and Sint Eustatius: one ISO code
        ("Galápagos", "Équateur"),
    ],
)
def test_a_countrys_far_part_is_a_place_of_its_own(part, country):
    """Any country's far part (an overseas department, an archipelago across the sea) found
    by its name like a country, its map framed on it: "Guadeloupe" was refused as a country,
    then as a relief, and the drawing fell back to SVG."""
    alone = figures_typst.compile_svg("map", f'#map(countries: ("{part}",), labels: false)')
    assert alone != figures_typst.compile_svg("map", f'#map(countries: ("{country}",), labels: false)')


def _height(svg: str) -> float:
    return float(re.search(r'height="([\d.]+)pt"', svg).group(1))


def test_a_country_with_its_far_parts_draws_them_in_insets():
    """A country with its far parts or lands (Denmark, Greenland and the Faroes; the United
    States with Hawaii): the country's map, each far one in an inset under it, named; not a
    world map where the country is a speck. `insets: false`: where they lie, one map."""
    for asked in ('"Danemark", "Groenland", "îles Féroé"', '"États-Unis", "Hawaï", "Porto Rico"'):
        insets = figures_typst.compile_svg("map", f"#map(countries: ({asked}), labels: false)")
        one = figures_typst.compile_svg("map", f"#map(countries: ({asked}), labels: false, insets: false)")
        assert _height(insets) > _height(one) * 1.2, asked
    # (a land near its country, Jersey by the United Kingdom: no inset)
    near = figures_typst.compile_svg("map", '#map(countries: ("Royaume-Uni", "Jersey"), labels: false)')
    assert near == figures_typst.compile_svg(
        "map", '#map(countries: ("Royaume-Uni", "Jersey"), labels: false, insets: false)'
    )


def test_a_part_of_the_world_is_its_countries():
    """A part of the world a lesson names (East Asia, Latin America, the Maghreb) is its
    countries: in a group, coloured; a flow's end, tinted and named ("Asie de l'Est" was
    refused as a place)."""
    group = lambda countries: figures_typst.compile_svg(  # noqa: E731
        "map", f'#map(groups: ((name: "A", countries: {countries}),), labels: false)'
    )
    assert group('("Maghreb",)') == group('("Maroc", "Algérie", "Tunisie")')
    assert group('("Asie de l\'Est",)') != group('("Chine",)')
    (places,) = _query("read-flows", ('(from: "Asie de l\'Est", to: "Amérique latine")',), "r.to.places.len()")
    assert places > 20


@pytest.mark.parametrize(
    ("body", "said"),
    [
        ('#map(countries: ("Basse-Saxe",))', r"Basse-Saxe.* is a region of Allemagne"),
        ('#map(countries: ("France",), regions: ("Bavière",))', r"Bavière.* is a region of Allemagne"),
        ('#map(countries: ("Prusse",))', r"Prusse.* is a state of the past.*1815"),
        ('#map(year: 1942, countries: ("Pologne",))', r"no state called .Pologne. in 1942.*Reich allemand"),
        ('#map(countries: ("France",), reliefs: ("Guadeloupe",))', r"Guadeloupe.* is a part of France .*in countries"),
        ('#map(cities: ("Groenland",))', r"Groenland.* is a country: in countries"),
    ],
)
def test_a_refusal_says_what_the_atlas_has_instead(body, said):
    """A name the atlas has as something else: the refusal says what (a region and its
    country, a state of a past year, the year's states on a country's land, a country's far
    part), for the next try to be right, never "leave it out" when it can tell."""
    with pytest.raises(figures_typst.Unusable, match=said):
        figures_typst.compile_svg("map", body)


def test_the_sites_of_history_are_places():
    """The camps of the Shoah are places of history lessons, on a map of 1942 too (Auschwitz
    was refused: no town of its country's largest)."""
    svg = figures_typst.compile_svg(
        "map", '#map(year: 1942, countries: ("Reich allemand",), cities: ("Auschwitz", "Treblinka", "Drancy"))'
    )
    assert svg.startswith("<svg")


@pytest.mark.parametrize(
    ("country", "names"),
    [
        ("Italie", ("Lombardie", "Lombardia", "Lombardy")),  # a group of provinces
        ("Italie", ("Pouilles", "Puglia", "Apulia")),
        ("Espagne", ("Andalousie", "Andalucía", "Andalusia")),
        ("Allemagne", ("Bavière", "Bayern", "Bavaria")),
    ],
)
def test_a_region_by_its_name_in_every_language(country, names):
    """Any country's regions by their names in the page's languages and their own ("Lombardie",
    "Puglia" were refused: Natural Earth names Italy's regions once, in Italian or English)."""
    maps = {
        figures_typst.compile_svg("map", f'#map(countries: ("{country}",), regions: ("{n}",), labels: false)')
        for n in names
    }
    assert len(maps) == 1


@pytest.mark.parametrize("land", ["Gibraltar", "Sint Maarten", "Monaco", "Vatican", "Tuvalu"])
def test_a_land_too_small_for_the_countries_scale_is_a_country(land):
    """Gibraltar, Sint Maarten, Monaco: lands Natural Earth's countries leave out, found as
    countries ("Gibraltar" was refused, and the British territories' map fell back to SVG)."""
    assert figures_typst.compile_svg("map", f'#map(countries: ("{land}",), labels: false)').startswith("<svg")


def _bubbles(svg: str) -> list[float]:
    """The radii of the proportional circles, in their drawing's order (the map's, largest
    first, then the legend's)."""
    return [float(r) for r in re.findall(r'stroke="#b52020"[^>]*d="M 0 0m 0 ([\d.]+)c', svg)]


def test_cities_sized_by_their_values():
    """Proportional circles: a city's circle's area its value (four times the value, twice the
    radius), the legend the largest's and a round one under it; "population", the atlas's
    own (Tokyo's larger than Paris's)."""
    svg = figures_typst.compile_svg(
        "map", '#map(cities: ("Paris", "Lyon"), values: ("Paris": 36, "Lyon": 9), unit: "millions", labels: false)'
    )
    big, small, *legend = _bubbles(svg)
    assert big == pytest.approx(2 * small, rel=0.02)
    assert len(legend) == 2 and legend[0] == pytest.approx(big, rel=0.02)
    plain = figures_typst.compile_svg("map", '#map(cities: ("Paris", "Lyon"), labels: false)')
    height = lambda svg: float(re.search(r'height="([\d.]+)pt"', svg).group(1))  # noqa: E731
    assert height(svg) > height(plain) and _bubbles(plain) == []
    tokyo, paris, *_ = _bubbles(
        figures_typst.compile_svg(
            "map", '#map(cities: ("Tokyo", "Paris"), values: "population", unit: "millions", labels: false)'
        )
    )
    assert tokyo > 1.5 * paris
    with pytest.raises(figures_typst.Unusable, match=r"values need their unit"):
        figures_typst.compile_svg("map", '#map(cities: ("Paris",), values: ("Paris": 2))')


def _dashed_length(svg: str) -> float:
    """How long the dashed lines are (a zone's outline), along their segments."""
    total = 0.0
    for d in re.findall(r'stroke-dasharray="[^"]*" d="([^"]+)"', svg):
        for dx, dy in re.findall(r"l ([-\d.]+) ([-\d.]+)", d):
            total += (float(dx) ** 2 + float(dy) ** 2) ** 0.5
    return total


def test_a_zone_is_one_area_outlined_with_its_name_in_the_legend():
    """A zone of regions (two départements side by side): tinted, its outline dashed without
    the border they share (one area: shorter than their two outlines); one spanning cities (a
    megalopolis) rounded around them; each named in the legend."""
    zone = lambda regions: figures_typst.compile_svg(  # noqa: E731
        "map", f'#map(countries: ("France",), zones: ((name: "Z", regions: ({regions})),), labels: false)'
    )
    both, meuse, marne = zone('"Meuse", "Haute-Marne"'), zone('"Meuse",'), zone('"Haute-Marne",')
    assert 0 < _dashed_length(both) < 0.95 * (_dashed_length(meuse) + _dashed_length(marne))
    plain = figures_typst.compile_svg("map", '#map(countries: ("États-Unis",), labels: false)')
    megalopolis = figures_typst.compile_svg(
        "map",
        '#map(countries: ("États-Unis",), zones: ((name: "Mégalopolis", places: ("Boston", "New York",'
        ' "Washington")),), labels: false)',
    )
    height = lambda svg: float(re.search(r'height="([\d.]+)pt"', svg).group(1))  # noqa: E731
    assert _dashed_length(megalopolis) > 0 and height(megalopolis) > height(plain)


@pytest.mark.parametrize(
    ("zones", "said"),
    [
        ('((regions: ("Meuse",)),)', r"a zone is \(name"),
        ('((name: "Z"),)', r"covers nothing"),
        ('((name: "Z", regions: ("Meuse",), colour: red),)', r"not .colour."),
        ('((name: "Z", regions: ("Atlantis",)),)', r"no region called .Atlantis."),
    ],
)
def test_a_zone_wrongly_written_said(zones, said):
    with pytest.raises(figures_typst.Unusable, match=said):
        figures_typst.compile_svg("map", f'#map(countries: ("France",), zones: {zones})')


def test_countries_named_on_their_land_or_beside_it():
    """A map of several countries (Southern Africa's) names each: on its land where its name
    fits (Angola, Namibia), beside it with a line where it doesn't (Zimbabwe); `names: false`
    none; a single country is not named."""
    body = '#map(countries: ("Afrique du Sud", "Namibie", "Botswana", "Angola", "Zimbabwe", "Mozambique"){})'
    named, bare = (figures_typst.compile_svg("map", body.format(extra)) for extra in ("", ", names: false"))
    assert len(_labels(named)) == 6 and _labels(bare) == []
    assert re.search(r'<path[^>]*stroke="#5a5a5a"', named)  # a line to a name beside its country
    assert _labels(figures_typst.compile_svg("map", '#map(countries: ("France",))')) == []


def test_a_frame_asked_wins_over_what_is_drawn():
    """The colonial empires of 1914 framed on Africa: the map as tall as Africa, not as wide
    as the world the British Empire spans."""
    size = lambda svg: tuple(float(v) for v in re.search(r'width="([\d.]+)pt" height="([\d.]+)pt"', svg).groups())  # noqa: E731
    groups = 'groups: ((name: "R", empire: "Royaume-Uni"), (name: "F", empire: "France")), labels: false'
    world = size(figures_typst.compile_svg("map", f"#map(year: 1914, {groups})"))
    africa = size(figures_typst.compile_svg("map", f'#map(year: 1914, frame: "Afrique", {groups})'))
    assert world[0] > world[1] * 1.2 and africa[1] > africa[0]
    with pytest.raises(figures_typst.Unusable, match=r"no place called .Atlantide. to frame"):
        figures_typst.compile_svg("map", '#map(countries: ("France",), frame: "Atlantide")')


def test_an_empire_with_a_land_of_no_name():
    """Spain's empire in 1914: one of its lands has no name in the atlas ("array is empty",
    the figure refused); its code then, the map drawn."""
    assert figures_typst.compile_svg("map", '#map(year: 1914, groups: ((name: "E", empire: "Espagne"),))').startswith(
        "<svg"
    )


def test_every_country_shown_named_even_crowded():
    """West Africa's small countries side by side: each named, on its land or beside it with a
    line where no place is clear (Zimbabwe, Botswana once left out), never dropped."""
    names = (
        "Sénégal",
        "Gambie",
        "Guinée-Bissau",
        "Guinée",
        "Sierra Leone",
        "Liberia",
        "Côte d'Ivoire",
        "Ghana",
        "Togo",
        "Bénin",
        "Burkina Faso",
        "Mali",
    )
    countries = ", ".join(f'"{n}"' for n in names)
    svg = figures_typst.compile_svg("map", f'#map(countries: ({countries}), cities: ("Dakar", "Accra"))')
    assert len(_labels(svg)) == len(names) + 2


def test_a_circles_legend_writes_its_unit():
    """The circles' legend: each of its two numbers with its unit ("37,4 millions"), not
    numbers alone: a unit four letters longer, eight glyphs more."""
    glyphs = lambda unit: len(  # noqa: E731
        re.findall(
            r"<use",
            figures_typst.compile_svg(
                "map", f'#map(cities: ("Paris",), values: ("Paris": 2), unit: "{unit}", labels: false)'
            ),
        )
    )
    assert glyphs("QQQQQ") - glyphs("Q") == 8


def test_a_part_of_the_world_shown_names_each_of_its_countries():
    """A part of the world in countries (the Maghreb) with another country: each of its
    countries named by its own name, as when listed one by one (the names were paired with
    the countries in order, "Maghreb" written on Morocco and "France" on Algeria)."""
    svg = lambda countries: figures_typst.compile_svg("map", f"#map(countries: ({countries}))")  # noqa: E731
    assert svg('"Maghreb", "France"') == svg('"Maroc", "Algérie", "Tunisie", "France"')


def test_circles_zones_and_a_frame_on_a_country_with_far_parts():
    """A country with its far parts (France and Guadeloupe) and circles, a zone or a frame:
    one map with them (the map with insets took none of them: "unexpected argument")."""
    for extra in (
        'cities: ("Paris",), values: ("Paris": 2), unit: "millions"',
        'zones: ((name: "Z", regions: ("Bretagne",)),)',
        'frame: "France"',
    ):
        svg = figures_typst.compile_svg("map", f'#map(countries: ("France", "Guadeloupe"), {extra})')
        assert svg.startswith("<svg"), extra


@pytest.mark.parametrize("land", ["La Réunion", "Bermudes", "Sainte-Hélène", "îles Caïmans", "Guadeloupe"])
def test_a_small_land_has_its_real_outline(land):
    """An inset magnifies a small land: its outline from Natural Earth's 1:10m regions, by its
    own size (La Réunion was a heptagon, Bermuda and Saint Helena triangles: the countries'
    1:50m outline simplified at their scale)."""
    folder, _ = _atlas_folder()
    countries = json.loads((folder / "atlas.json").read_text(encoding="utf-8"))["countries"]
    code = next(code for code, c in countries.items() if land.lower() in (n.lower() for n in c["n"]))
    assert max(len(r) for r in countries[code]["r"]) >= 14, countries[code]["r"]
