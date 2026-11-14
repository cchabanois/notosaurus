"""The map family (our atlas): places found by any name, history's places, what the atlas
lacks, a map's size."""

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
