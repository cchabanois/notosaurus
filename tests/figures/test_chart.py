"""The chart family (our chart function): sectors, bars and lines from their values, what is
written, what is refused."""

import io
import re

import pytest

from notosaurus_core import figures, figures_typst


def test_a_charts_angles_and_heights_come_from_its_counts():
    """A chart's sectors are its counts' shares (1, 1 and 2, 2 the same half pie), computed,
    never given; large counts and a zero drawn too (the bars' graduation by 20s)."""
    semi = '#chart(kind: "semi", values: (("A", {}), ("B", {})))'
    halves = {figures_typst.compile_svg("chart", semi.format(n, n)) for n in (1, 2)}
    assert len(halves) == 1
    pie = figures_typst.compile_svg("chart", '#chart(kind: "pie", values: (("A", 1), ("B", 3)))')
    assert pie != figures_typst.compile_svg("chart", '#chart(kind: "pie", values: (("A", 3), ("B", 1)))')
    for kind in ("bars", "pie", "semi"):
        figures_typst.compile_svg("chart", f'#chart(kind: "{kind}", values: (("A", 230), ("B", 5), ("C", 0)))')


@pytest.mark.parametrize(
    ("values", "lines"),
    [
        ('(("0", 0.2), ("1", 0.5), ("2", 0.3))', 5),  # by tenths up to 0.5
        ('(("0", 0.078), ("1", 0.259), ("2", 0.346), ("3", 0.23))', 7),  # by 0.05 up to 0.35
        ('(("A", 12), ("B", 7), ("C", 3))', 12),  # counts: by units, as before
    ],
)
def test_a_bar_charts_graduation_reads_its_values(values, lines):
    """A probability law's bars (values under 1) graduated by tenths or hundredths, a light
    line at each: never 0 and 1 alone, where no value can be read (6 drawings in 6)."""
    svg = figures_typst.compile_svg("chart", f'#chart(kind: "bars", values: {values})')
    assert svg.count('stroke="#cdcdcd"') == lines


def test_a_charts_counts_written_only_when_asked():
    """None by default (a card asking a count, a frequency or an angle never shows it on its
    chart); "all", or the labels given."""
    for kind in ("bars", "pie", "semi"):
        body = f'#chart(kind: "{kind}", values: (("Chat", 12), ("Chien", 10), ("Lapin", 5)){{}})'
        bare = figures_typst.compile_svg("chart", body.format(""))
        assert bare == figures_typst.compile_svg("chart", body.format(", written: ()")), kind
        some = figures_typst.compile_svg("chart", body.format(', written: ("Chien",)'))
        every = figures_typst.compile_svg("chart", body.format(', written: "all"'))
        assert len({bare, some, every}) == 3, kind


def test_a_line_starts_its_axes_where_its_measures_are():
    """A line's axes meet at its bottom left, from 0 for measures near it, else from the
    graduation under the lowest (a heart rate from 70, years around them): the measures
    fill the frame. Its graduations every round interval they were taken at."""
    from PIL import Image

    heart = "((0, 70), (2, 72), (4, 120), (6, 145), (8, 150), (10, 150), (12, 110), (14, 85), (16, 75))"
    for values in (heart, "((2000, 6.1), (2005, 6.5), (2010, 6.9), (2015, 7.3), (2020, 7.8))"):
        svg = figures_typst.compile_svg("chart", f'#chart(kind: "line", values: {values}, axes: ("x", "y"))')
        image = Image.open(io.BytesIO(figures.to_png(figures.clean(svg)))).convert("RGB")
        red = [
            y for y in range(image.height) for x in range(0, image.width, 2) if image.getpixel((x, y)) == (176, 58, 46)
        ]
        top, bottom = min(red), max(red)
        # its lowest measure on its x axis, its highest at its top: they fill the frame
        assert bottom - top > image.height * 0.6, values
    line = '#chart(kind: "line", values: ((0, 21), (1, 20.4), (2, 19.6)), axes: ("Temps (min)", "Dioxygène (%)"){})'
    bare, written = (figures_typst.compile_svg("chart", line.format(w)) for w in ("", ", written: (2,)"))
    assert bare != written


def test_lines_of_the_same_measure_share_one_axis():
    """Several lines of one measure (an allele's frequency in two populations) on the same
    graduation, each its colour and a legend: one twice as high as the other is drawn twice
    as high, never stretched to its own axis; `second` (another unit) is a single line's."""
    from PIL import Image

    body = '#chart(kind: "line", values: (("A", ((0, 0), (10, 5))), ("B", ((0, 0), (10, 10)))), axes: ("x", "y"))'
    image = Image.open(io.BytesIO(figures.to_png(figures.clean(figures_typst.compile_svg("chart", body)))))
    image = image.convert("RGB")
    plot = image.crop((0, 0, int(image.width * 0.7), image.height))  # the legend at the right left out

    def height(colour):
        ys = [y for y in range(plot.height) for x in range(0, plot.width, 2) if plot.getpixel((x, y)) == colour]
        return max(ys) - min(ys)

    assert height((31, 95, 168)) == pytest.approx(2 * height((176, 58, 46)), rel=0.1)
    with pytest.raises(figures_typst.Unusable, match="single line"):
        figures_typst.compile_svg("chart", body[:-1] + ', second: (values: ((0, 1), (1, 2)), axis: "z"))')


def test_a_smooth_line_goes_through_its_measures_and_never_beyond():
    """A curve through measures (a concentration over time): through every one, never above
    the highest nor below the lowest between two (a plateau stays flat), drawn by the chart,
    never a function the AI fits to them."""
    from PIL import Image

    body = '#chart(kind: "line", values: ((0, 0), (1, 5), (2, 5), (3, 5), (4, 1)), axes: ("t", "y"){})'

    def reach(extra):
        image = Image.open(
            io.BytesIO(figures.to_png(figures.clean(figures_typst.compile_svg("chart", body.format(extra)))))
        )
        image = image.convert("RGB")
        red = [y for y in range(image.height) for x in range(image.width) if image.getpixel((x, y)) == (176, 58, 46)]
        return min(red), max(red)

    straight, smooth = reach(""), reach(", smooth: true")
    drawn = {figures_typst.compile_svg("chart", body.format(extra)) for extra in ("", ", smooth: true")}
    assert len(drawn) == 2  # a curve, not the straight lines
    assert abs(smooth[0] - straight[0]) <= 1 and abs(smooth[1] - straight[1]) <= 1


def test_a_line_marks_its_events_and_stretches():
    """An event at an x (a dashed line, its label under the axis) and a stretch of x
    (shaded), placed by the chart from their values: each changes the drawing."""
    line = '#chart(kind: "line", values: ((0, 2), (10, 8), (20, 4)), axes: ("t", "y"){})'
    drawn = {
        figures_typst.compile_svg("chart", line.format(extra))
        for extra in ("", ', marks: ((10, "arrêt"),)', ', spans: ((2, 6, "effort"),)')
    }
    assert len(drawn) == 3


def test_a_second_measure_on_its_own_axis():
    """Two measures of different units over the same x: the second on a right axis of its
    own, in another colour, never left out."""
    from PIL import Image

    body = (
        '#chart(kind: "line", values: ((1960, 317), (2020, 414)), axes: ("Année", "A (ppm)"),'
        ' second: (values: ((1960, 0), (2020, 1.0)), axis: "B (°C)"))'
    )
    image = Image.open(io.BytesIO(figures.to_png(figures.clean(figures_typst.compile_svg("chart", body)))))
    blue = sum(1 for p in image.convert("RGB").getdata() if p == (31, 95, 168))
    assert blue > 50  # its line, its numbers


def test_a_line_without_values_shows_no_numbers_on_its_y_axis():
    """numbered: false, the description giving no value for y: its shape only."""
    line = '#chart(kind: "line", values: ((1, 1), (5, 1), (28, 5)), axes: ("Jours", "y"){})'
    numbered, bare = (figures_typst.compile_svg("chart", line.format(n)) for n in ("", ", numbered: false"))
    assert len(bare) < len(numbered)


def test_a_bar_charts_long_names_never_overlap():
    """Each bar has its name's width at least: long names widen the chart, never overlap."""

    def width(names):
        values = ", ".join(f'("{n}", {i + 1})' for i, n in enumerate(names))
        svg = figures_typst.compile_svg("chart", f'#chart(kind: "bars", values: ({values},))')
        return float(re.search(r'<svg[^>]*\swidth="([\d.]+)', svg).group(1))

    short = width(["A", "B", "C", "D", "E"])
    assert width(["Réfrigérateurs", "Congélateurs", "Lave-vaisselle", "Téléviseurs", "Aspirateurs"]) > 1.5 * short


def test_a_chart_refuses_what_it_cant_draw():
    for body, said in (
        ('#chart(kind: "bars", values: (("A", 1),), marks: ((1, "x"),))', "a line's only"),
        ('#chart(kind: "line", values: ((0, 1), (1, 2)), spans: ((3, 2, "x"),))', "from < to"),
        ('#chart(kind: "line", values: ((0, 1), (1, 2)), marks: (("a", "x"),))', "x a number"),
        ('#chart(kind: "line", values: ((0, 1), (1, 2)), second: (values: ((0, 1),)))', "two measures at least"),
        ('#chart(kind: "line", values: ((0, 1),))', "two at least"),
        ('#chart(kind: "line", values: (("lundi", 1), ("mardi", 2)))', "each a number"),
        ('#chart(kind: "area", values: (("A", 1),))', "kind is"),
        ('#chart(kind: "pie", values: (("A", 0), ("B", 0)))', "add up to more than 0"),
        ('#chart(kind: "pie", values: ("A", "B"))', "pairs"),
    ):
        with pytest.raises(figures_typst.Unusable, match=said):
            figures_typst.compile_svg("chart", body)
