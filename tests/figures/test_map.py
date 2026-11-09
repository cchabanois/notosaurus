"""The map family (our atlas): places found by any name, history's places, what the atlas
lacks, a map's size."""

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
