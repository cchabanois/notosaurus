"""The geometry family (ctz-euclide and our functions): number lines, intervals, the
trigonometric circle, lengths, fractions, vectors, coordinate frames."""

import json
import math
import re
import tempfile
from itertools import pairwise
from pathlib import Path

import pytest
import typst

from figures.support import _glyphs, drawn_size
from notosaurus_core import figures, figures_typst


def test_a_number_lines_points_and_numbers_placed_from_their_values():
    """A number line draws its points and its numbers from their values (the AI put A at its
    value as a coordinate, -3, on a line starting at -5: off the line, B on the wrong tick):
    a point is placed from the line's first value, a point off the line is refused, the
    numbers the description writes are written with the language's comma."""
    draw = "#ctz-canvas({{ ctz-init(); ctz-draw-number-line({}) }})"
    line = lambda args: figures_typst.compile_svg("geometry", draw.format(args))  # noqa: E731
    assert line("-5, 5, numbers: false, points: (A: -3)") == line("0, 10, numbers: false, points: (A: 2)")
    assert line("-5, 5, points: (A: -3)") != line("-5, 5, points: (A: 2)")
    with pytest.raises(figures_typst.Unusable, match="outside the line"):
        line("-5, 5, points: (A: 7)")
    # a fraction's value as a division, its letter written; its value as a name refused
    assert line("0, 2, step: 0.25, points: (B: 3/4)") == line("0, 2, step: 0.25, points: (B: 0.75)")
    with pytest.raises(figures_typst.Unusable, match="never its value written as its name"):
        line("0, 2, step: 0.25, points: (B: (3/4, $3/4$))")
    decimals = draw.format("2.3, 2.4, step: 0.01, scale: 100, numbers: (2.3, 2.4), points: (F: 2.35)")
    french, english = (
        figures_typst.compile_svg("geometry", f'#set text(lang: "{lang}")\n{decimals}') for lang in ("fr", "en")
    )
    assert french != english


def test_the_geometry_rules_number_lines_compile():
    """Every number line the geometry rule shows compiles in a canvas, as the AI copies them."""
    rules = figures_typst.FAMILIES["geometry"].rules
    rule = next(line for line in rules.splitlines() if line.startswith("- a number line"))
    calls = re.findall(r"`(ctz-draw-number-line\([^`]*\))`", rule)
    assert calls
    for call in calls:
        assert figures_typst.compile_svg("geometry", f"#ctz-canvas({{ ctz-init(); {call} }})").startswith("<svg")


def _measured(expression: str):
    """What a Typst expression of the geometry preamble gives (its functions' arithmetic)."""
    document = figures_typst.FAMILIES["geometry"].preamble.split(figures_typst.EXAMPLE)[0]
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "measure.typ"
        path.write_text(f"{document}\n#metadata({expression}) <measured>\n", encoding="utf-8")
        found = typst.query(
            str(path), "<measured>", field="value", one=True, root=folder, package_path=str(figures_typst.packages())
        )
    return json.loads(found)


def test_a_logarithmic_lines_values_placed_at_their_log10():
    """A logarithmic scale (the AI computed each log10 by hand in comments, or placed its
    points with ctz-def-points from the line's start: off the axis): its values given as they
    are, the preamble places each at its log10, its decades and its 10ⁿ ticks computed."""
    # 4.1e-8 to 2.5e6: the decades 10⁻⁸ to 10⁷, the line about 12 long, 10ⁿ every other
    # decade (0.8 a decade: 1.6 apart)
    m = _measured("_log-measure((), (1.3 / 31557600, 480 / 31557600, 4.2, 26000, 2.5e6), auto, auto)")
    assert (m["lo"], m["hi"], m["step"]) == (-8, 7, 2)
    assert m["scale"] == pytest.approx(12 / 15)
    assert _measured("_log-measure((), (20, 40000, 100000), auto, auto)")["step"] == 1  # 10¹ to 10⁵: 2.4 a decade
    assert _measured("_log-measure((1e-3, 1e3), (5,), auto, 1)")["lo"] == -3  # its first and last as values
    draw = "#ctz-canvas({{ ctz-init(); ctz-draw-number-line({}) }})"
    line = lambda args: figures_typst.compile_svg("geometry", draw.format(args))  # noqa: E731
    # a value lands at its log10, whatever expression gives it; moved, its point moves
    assert line("log: true, points: (A: 1e-3, B: 10 * 10)") == line("log: true, points: (A: 1 / 1000, B: 100)")
    assert line("log: true, points: (A: 1e-3, B: 100)") != line("log: true, points: (A: 1e-3, B: 300)")
    # a whole number of decades further, the same drawing (its ticks written 10ⁿ: none here)
    assert line("log: true, numbers: false, points: (A: 2, B: 20000)") == line(
        "log: true, numbers: false, points: (A: 200, B: 2000000)"
    )
    # its numbers the powers of ten, under its ticks
    numbered = line("log: true, points: (A: 1e-3, B: 1000)")
    assert len(_glyphs(numbered)) > len(_glyphs(line("log: true, numbers: false, points: (A: 1e-3, B: 1000)")))
    with pytest.raises(figures_typst.Unusable, match="never the exponent"):
        line("-3, 2, log: true, points: (A: 1e-3)")
    with pytest.raises(figures_typst.Unusable, match="above 0"):
        line("log: true, points: (A: 0, B: 10)")
    # an interval on it, its bounds where the line put them
    interval = "#ctz-canvas({ ctz-init(); ctz-draw-number-line(log: true, points: (A: 1, B: 1e5)); "
    assert figures_typst.compile_svg("geometry", interval + "ctz-draw-interval(20, none, log: true) })")
    with pytest.raises(figures_typst.Unusable, match="drawn after its line"):
        figures_typst.compile_svg("geometry", "#ctz-canvas({ ctz-init(); ctz-draw-interval(20, 200, log: true) })")


def test_a_number_lines_names_too_close_raised_those_apart_left():
    """Two names written on each other (a log scale's "Voie lactée" and "Andromède", two units
    apart): raised a row, a line down to their point; names that fit stay side by side as
    they were, on one row."""
    rows = lambda placed: _measured(f"_name-rows({placed})")  # noqa: E731
    assert rows("((x: 0, w: 0.3), (x: 1, w: 0.3), (x: 2, w: 0.3))") == [0, 0, 0]
    assert rows("((x: 3.1, w: 2.6), (x: 4.5, w: 2.2))") == [0, 1]
    assert rows("((x: 0, w: 1), (x: 0.3, w: 1), (x: 0.6, w: 1))") == [0, 1, 2]
    assert rows("((x: 0.6, w: 1), (x: 0, w: 1), (x: 5, w: 1))") == [1, 0, 0]  # left to right
    # a name a raised name's line would go up through: moved aside, clear of it, its own point
    # still under it; the others not moved
    shifts = _measured("_name-shifts(((x: 9.9, w: 5.8), (x: 11.5, w: 4.6), (x: 2, w: 1)), (1, 2, 0))")
    assert -5.8 / 2 < shifts[0] < 0 and 9.9 + shifts[0] + 5.8 / 2 < 11.5
    assert shifts[1:] == [0, 0]
    draw = "#ctz-canvas({{ ctz-init(); ctz-draw-number-line(0, 10, numbers: false, points: {}) }})"
    line = lambda points: figures_typst.compile_svg("geometry", draw.format(points))  # noqa: E731
    apart = _glyphs(line("(P: (at: 1, name: [Voie lactée]), Q: (at: 8, name: [Andromède]))"))
    close = _glyphs(line("(P: (at: 5, name: [Voie lactée]), Q: (at: 7, name: [Andromède]))"))
    assert len({round(y, 1) for _, y in apart}) == 1  # one row
    assert len({round(y, 1) for _, y in close}) == 2  # the second raised


def test_a_number_lines_numbers_too_close_lowered_and_zones_named():
    """A scale's numbers given close together (20 000, 40 000 and 100 000 Hz on a logarithmic
    line, written on each other): a row lower, a line up to their tick; a large number's
    thousands apart; a stretch the description names (infrasons, ultrasons: the AI made
    points of them) an interval with no bracket, its name under the numbers."""
    draw = "#ctz-canvas({{ ctz-init(); ctz-draw-number-line(log: true, numbers: {}) }})"
    line = lambda numbers: figures_typst.compile_svg("geometry", draw.format(numbers))  # noqa: E731
    assert len({round(y, 1) for _, y in _glyphs(line("(20, 20000)"))}) == 1
    assert len({round(y, 1) for _, y in _glyphs(line("(20, 20000, 40000, 100000)"))}) >= 2
    thousands = "#ctz-canvas({{ ctz-init(); ctz-draw-number-line(0, 20000, step: 10000, scale: 0.0004{}) }})"
    grouped, plain = (
        figures_typst.compile_svg("geometry", thousands.format(numbers))
        for numbers in ("", ", numbers: ((0, [0]), (10000, [10000]), (20000, [20000]))")
    )
    assert grouped != plain

    # 10 000, 20 000: five digits in two groups, 2 then 3, a narrow space between them
    # (U+202F, as school writes them: narrower than a word's space), none in the plain ones
    def digits(svg: str) -> list[list[float]]:
        runs = re.findall(r'<g transform="matrix[^>]*>(.*?)</g>', svg)
        return [[float(x) for x in re.findall(r'x="([\d.]+)"', run)] for run in runs]

    def gaps(xs: list[float]) -> list[float]:
        steps = [b - a for a, b in pairwise(xs)]
        return [step - min(steps) for step in steps]

    for xs in (xs for xs in digits(grouped) if len(xs) == 5):
        extra = gaps(xs)
        assert extra[0] < 0.1 and extra[2:] == pytest.approx([0, 0], abs=0.1)
        assert 1 < extra[1] < 3
    assert all(max(gaps(xs)) < 0.1 for xs in digits(plain) if len(xs) == 5)
    assert sum(len(xs) == 5 for xs in digits(grouped)) == 2
    zones = (
        "#ctz-canvas({{ ctz-init(); ctz-draw-number-line(log: true, numbers: (20, 20000));"
        " ctz-draw-interval(20, 20000, log: true, closed: none{}) }})"
    )
    named, bare = (figures_typst.compile_svg("geometry", zones.format(label)) for label in (", label: [audible]", ""))
    below = min(y for _, y in _glyphs(bare))
    assert any(y > below + 5 for _, y in _glyphs(named))  # its name under the numbers (SVG's y down)
    assert "<path" in bare and bare.count("<path") < figures_typst.compile_svg(
        "geometry", zones.format("").replace("closed: none", "closed: (true, true)")
    ).count("<path")  # no bracket
    # zones side by side: each its colour, their names a row apart when they would touch
    zone = " ctz-draw-interval({}, {}, closed: none, label: [{{}}], first: 0, last: 10);"
    three = (
        "#ctz-canvas({{ ctz-init(); ctz-draw-number-line(0, 10);"
        + "".join(zone.format(a, b) for a, b in ((1, 2), (2, 3), (3, 8)))
        + " }})"
    )
    named = figures_typst.compile_svg("geometry", three.format("first zone", "second zone", "third"))
    assert len(set(re.findall(r'stroke="(#[0-9a-f]{6})"', named))) >= 4  # black and three colours
    short = figures_typst.compile_svg("geometry", three.format("a", "b", "c"))
    assert len({round(y, 1) for _, y in _glyphs(named)}) == len({round(y, 1) for _, y in _glyphs(short)}) + 1


def test_an_intervals_brackets_turned_by_its_bounds():
    """An interval on a number line: its brackets drawn by the preamble from whether each bound
    is closed, open or infinite (by hand, the AI turned one the wrong way half the time)."""
    draw = "#ctz-canvas({{ ctz-init(); ctz-draw-interval({}, first: -3, last: 5) }})"
    shapes = {
        closed: figures_typst.compile_svg("geometry", draw.format(f"-1, 3, closed: {closed}"))
        for closed in ("(true, true)", "(true, false)", "(false, true)", "(false, false)")
    }
    assert len(set(shapes.values())) == 4  # each bound's bracket turned its own way
    figures_typst.compile_svg("geometry", draw.format("2, none, closed: (true, false)"))  # [2 ; +∞[
    figures_typst.compile_svg("geometry", draw.format("none, 1"))  # ]−∞ ; 1]
    # the line drawn by the preamble too: its ticks where the interval's bounds are placed
    line = "#ctz-canvas({ ctz-init(); ctz-draw-number-line(-2, 6, scale: 0.8, arrow: true) })"
    assert figures_typst.compile_svg("geometry", line).startswith("<svg")


def test_an_interval_drawn_on_its_lines_measure():
    """An interval on a line from -5, its first not given again: placed from 0 (-1 to 3 drawn
    at -6 to -2), its infinite end going past the line's when its step was not 1. Placed by the
    line it is drawn on, as when its first and last are given; an infinite end stopping at the
    line's end."""
    line = "#ctz-canvas({{ ctz-init(); ctz-draw-number-line(-5, 5{}){} }})"
    given = figures_typst.compile_svg("geometry", line.format("", "; ctz-draw-interval(-1, 3, first: -5, last: 5)"))
    assert figures_typst.compile_svg("geometry", line.format("", "; ctz-draw-interval(-1, 3)")) == given
    halves = ", step: 0.5"
    bare, _ = drawn_size("geometry", line.format(halves, ""))
    infinite = ("ctz-draw-interval(2, none)", "ctz-draw-interval(none, 2)", "ctz-draw-interval(2, none, first: -5)")
    for interval in infinite:
        width, _ = drawn_size("geometry", line.format(halves, "; " + interval))
        assert width == pytest.approx(bare, abs=0.5), interval


def test_the_trigonometric_circles_points_placed_by_their_angles():
    """The trigonometric circle drawn by the preamble from the angles' values (by eye, the AI
    placed them wrongly and wrote its points' names, "Ppi_2"): an angle changed, the drawing
    changes; the names given are the only ones written."""
    draw = (
        "#ctz-canvas({{ ctz-init();"
        " ctz-draw-unit-circle(angles: (({}, $pi/3$),), project: ({}, $1/2$, $sqrt(3)/2$)) }})"
    )
    sixty = figures_typst.compile_svg("geometry", draw.format(60, 60))
    assert sixty != figures_typst.compile_svg("geometry", draw.format(45, 45))
    assert figures_typst.compile_svg("geometry", draw.format(90, 150)).startswith("<svg")  # on an axis, past it


def test_a_length_written_beside_its_segment_never_on_it():
    """Lengths were written on their segment's line ("4 cm" cut by the side), and a segment
    holding a labelled one got another's length instead of its own (AB = 5 cm written MB =
    3 cm). Drawn by the preamble: beside the segment, away from the figure; [AB] around [AM]
    on a dimension line past [AM]'s label; a point at AM/AB of [AB], computed."""
    figure = """#ctz-canvas({{
      ctz-init()
      ctz-def-points(A: (0, 3.5), B: (-2.5, 0), C: (3.5, 0))
      ctz-def-linear("M", "A", "B", 2/5)
      ctz-draw-polygon("A", "B", "C")
      {}
    }})"""
    svg = figures_typst.compile_svg
    bare = svg("geometry", figure.format(""))
    # its label leaves the segment's line as it is: written beside it, the line not crossed
    one = svg("geometry", figure.format('ctz-draw-length("A", "M", [2 cm], away: "C")'))
    assert one != bare
    both = figure.format(
        'ctz-draw-length("A", "M", [2 cm], away: "C"); ctz-draw-length("A", "B", [5 cm], away: "C", level: 2)'
    )
    assert svg("geometry", both).startswith("<svg")
    # the dimension line: farther from [AB] than [AM]'s label reaches, whatever the label
    longer = both.replace("[2 cm]", "[2,25 cm]")
    assert svg("geometry", longer) != svg("geometry", both)
    assert "ctz-draw-length" in figures_typst.FAMILIES["geometry"].rules


@pytest.mark.parametrize(
    ("shape", "parts", "coloured"),
    [('kind: "disc"', 4, 3), ('kind: "disc"', 12, 7), ('kind: "bar"', 5, 2), ('kind: "rect", rows: 2', 6, 5)],
)
def test_a_fractions_coloured_parts_counted_by_the_preamble(shape, parts, coloured):
    """A fraction on a shape: the AI coloured 1 part of 4 for 3/4, or a triangle across the
    parts. Drawn by the preamble: the shape cut into `parts` equal parts, exactly `coloured`
    filled whole (counted in the SVG: the parts filled with the fraction's colour)."""
    svg = figures_typst.compile_svg("geometry", f"#fraction-shape({shape}, parts: {parts}, coloured: {coloured})")
    filled = len(re.findall(r'fill="#9fc3e7"', svg))
    assert filled == coloured, svg[:300]
    # several shapes side by side: five thirds over two discs
    two = '#fraction-shapes((kind: "disc", parts: 3, coloured: 3), (kind: "disc", parts: 3, coloured: 2))'
    assert len(re.findall(r'fill="#9fc3e7"', figures_typst.compile_svg("geometry", two))) == 5


def test_a_vector_drawn_with_its_arrow():
    """A scalar product's vectors drawn as plain segments (0/3): the rule had no vector. Drawn
    by the preamble: its arrow's head at its end (a segment more than the plain one), its name
    toward the head, clear of a point in its middle (a projection H)."""
    figure = "#ctz-canvas({{ ctz-init(); ctz-def-points(A: (0, 0), B: (4, 0), C: (2, 2)); {} }})"
    segment = figures_typst.compile_svg("geometry", figure.format('ctz-draw-segment("A", "B")'))
    vector = figures_typst.compile_svg("geometry", figure.format('ctz-draw-vector("A", "B")'))
    assert vector.count("<path") > segment.count("<path")  # the head
    named = figure.format('ctz-draw-vector("A", "B", label: $arrow(A B)$, away: "C")')
    assert figures_typst.compile_svg("geometry", named) != vector
    assert "ctz-draw-vector" in figures_typst.FAMILIES["geometry"].rules


def test_a_coordinate_frame_drawn_as_the_geometry_rule_says():
    """A circle or a line in a coordinate frame: the rule's own calls compile (the AI wrote
    ctz-draw-axes(-2, 6, -3, 5), positional, refused by Typst 3 times in 3: no frame was
    described), the axes' arrows past the grid's last numbers."""
    rule = (figures_typst.RULES / "geometry.md").read_text(encoding="utf-8")
    calls = re.findall(r"`(ctz-draw-(?:grid|axes)\(xmin:[^`]*\))`", rule)
    assert len(calls) == 2
    body = '#ctz-canvas({{\n  ctz-init()\n  {}\n  {}\n  ctz-def-points(Ω: (2, 1))\n  ctz-draw-circle-r("Ω", 3)\n}})'
    assert figures.clean(figures_typst.compile_svg("geometry", body.format(*calls))).startswith("<svg")


def test_a_trigonometric_circle_with_one_angle():
    """One angle written without its trailing comma, ((60, $M$)) (the AI's, refused 3 times in
    3: Typst reads a pair, not a list of one): the same circle as ((60, $M$),)."""
    circle = "#ctz-canvas({{ ctz-init()\n ctz-draw-unit-circle(angles: {}, project: (60, $1/2$, $sqrt(3)/2$)) }})"
    one = figures_typst.compile_svg("geometry", circle.format("((60, $M$),)"))
    assert figures_typst.compile_svg("geometry", circle.format("((60, $M$))")) == one


def test_a_frames_axes_numbered_at_whole_steps():
    """Axes starting half a unit out (−1.5, as the rule asks): ctz-euclide counted its steps
    from there, "−1.5, −0.5, 0.5" written between the units, on the points and the circle.
    Numbered at the step's multiples, the same numbers wherever the axis starts."""
    frame = "#ctz-canvas({{ ctz-init()\n ctz-draw-axes(xmin: {0}, xmax: 1.5, ymin: {0}, ymax: 1.5) }})"
    numbers = [len(_glyphs(figures_typst.compile_svg("geometry", frame.format(start)))) for start in ("-1.5", "-1")]
    assert numbers[0] == numbers[1]


def test_points_on_the_unit_circle_joined_and_named_as_the_rule_says():
    """Roots of unity drawn in a frame of the AI's own, their names written by hand beside
    letters it added (B and j, C and j² one on the other, 3 times in 3): the unit circle joins
    its points (`join: true`); a point named otherwise than by a letter gets its text from the
    labels, as the rule writes it."""
    circle = "#ctz-canvas({{ ctz-init()\n ctz-draw-unit-circle(angles: ((0, $1$), (120, $j$), (240, $j^2$)){}) }})"
    joined = figures_typst.compile_svg("geometry", circle.format(", join: true"))
    assert joined != figures_typst.compile_svg("geometry", circle.format(""))
    rule = (figures_typst.RULES / "geometry.md").read_text(encoding="utf-8")
    call = re.search(r"`(ctz-draw-labels\(B: \(pos: [^`]*label: [^`]*\)\))`", rule)
    assert call
    body = f"#ctz-canvas({{ ctz-init()\n ctz-def-points(A: (0, 0), B: (2, 1))\n {call[1]} }})"
    assert figures_typst.compile_svg("geometry", body).startswith("<svg")


def test_the_rule_says_where_a_perpendiculars_points_are():
    """The rule said the points of ctz-def-perp and ctz-def-para were far from the figure (only
    ctz-def-bisect's are): the AI carried a tangent's points twice as far,
    a line 13 units long on a circle of 6, the circle shrunk (1 drawing in 3). They are at the
    reference segment's length on each side of the point: a tangent at A to a circle of radius
    3, drawn through them, as high as the circle."""
    rule = (figures_typst.RULES / "geometry.md").read_text(encoding="utf-8")
    assert "ctz-def-perp, ctz-def-para and ctz-def-mediator give are near" in rule
    tangent = """#ctz-canvas({
  ctz-init()
  ctz-def-points(O: (0, 0), A: (3, 0))
  ctz-draw-circle-through("O", "A")
  ctz-def-perp("T1", "T2", ("O", "A"), "A")
  ctz-draw-segment("T1", "T2")
})"""
    width, height = drawn_size("geometry", tangent)
    assert height == pytest.approx(width, rel=0.05)


def test_a_translations_image_placed_clear_of_its_figure():
    """A translation whose vector the description doesn't give (only A to A'): its vector
    computed from the figure, never chosen by eye (by eye, the AI took A' along [AB] half
    the time: the arrow on a side, the image on the figure). For triangles of every shape:
    the image clear of the figure by the gap, the vector 15° at least from every side and
    out of the figure's angle at A and of its opposite (checked), the rightmost of the nearly as good."""
    body = """#let triangles = (
  ((0, 0), (3, 0.5), (1, 2.5)), ((0, 0), (4, 0), (0, 3)), ((0, 0), (3, 1), (2, 3)),
  ((1, 0), (0, 2), (3, 3)), ((0, 0), (5, 0), (2.5, 0.5)), ((0, 0), (1, 4), (-1, 3)),
)
#for pts in triangles {
  let (dx, dy) = _translation-vector(pts, pts.first(), 0, 1)
  let length = calc.sqrt(dx * dx + dy * dy)
  let u = (dx / length, dy / length)
  let along = pts.map(q => q.at(0) * u.at(0) + q.at(1) * u.at(1))
  // the image's projection starts a gap after the figure's ends: they never touch
  assert(calc.min(..along) + length >= calc.max(..along) + 1 - 1e-9, message: "touches")
  for i in range(3) {
    let (a, b) = (pts.at(i), pts.at(calc.rem(i + 1, 3)))
    let s = calc.atan2(b.at(0) - a.at(0), b.at(1) - a.at(1)) / 1deg
    let t = calc.atan2(dx, dy) / 1deg
    let d = calc.rem-euclid(t - s, 180)
    assert(calc.min(d, 180 - d) >= 15, message: "along a side")
  }
  // the vector out of the figure's angle at A (BAC), and out of its opposite: the arrow
  // into neither the figure nor its image
  let t = calc.atan2(dx, dy) / 1deg
  let towards(q) = calc.atan2(q.at(0) - pts.at(0).at(0), q.at(1) - pts.at(0).at(1)) / 1deg
  let (a1, a2) = (towards(pts.at(1)), towards(pts.at(2)))
  let span = calc.rem-euclid(a2 - a1, 360)
  let (from, width) = if span > 180 { (a2, 360 - span) } else { (a1, span) }
  for w in (t, t + 180) {
    assert(calc.rem-euclid(w - from, 360) > width, message: "into the angle at A")
  }
}
#ctz-canvas({
  ctz-init()
  ctz-def-points(A: (0, 0), B: (3, 0.5), C: (1, 2.5))
  ctz-def-translation-image("A'", "A", ("A", "B", "C"))
  ctz-draw-vector("A", "A'")
})"""
    figures_typst.compile_svg("geometry", body)
    rule = figures_typst.FAMILIES["geometry"].rules
    (call,) = re.findall(r"`(ctz-def-translation-image\([^`]*\))`", rule)
    points = "ctz-def-points(A: (0, 0), B: (3, 0.5), C: (1, 2.5))"
    example = f'#ctz-canvas({{ ctz-init(); {points}; {call}; ctz-draw-vector("A", "A\'") }})'
    assert figures_typst.compile_svg("geometry", example).startswith("<svg")


def test_a_lottery_wheel_drawn_from_its_counts():
    """A lottery wheel (3 red, 2 blue, 3 green, a pointer) was drawn as a fraction's disc, its
    parts all blue (2 drawings in 3): `wheel` cuts it into each colour's count of sectors, two
    of a colour never side by side while another can sit between (around it too: the last
    touches the first), its pointer drawn; the rule's call compiles."""
    body = """#for counts in ((3, 2, 3), (4, 1), (1, 1, 1, 1), (5, 5), (2, 6)) {
  let order = _wheel-order(counts)
  for (i, n) in counts.enumerate() { assert(order.filter(c => c == i).len() == n, message: "count") }
  let most = calc.max(..counts)
  if 2 * most <= order.len() {
    for k in range(order.len()) {
      assert(order.at(k) != order.at(calc.rem(k + 1, order.len())), message: "side by side: " + repr(order))
    }
  }
}
#wheel(sectors: ((3, red), (2, blue), (3, green)))"""
    assert figures_typst.compile_svg("geometry", body).startswith("<svg")
    with pytest.raises(figures_typst.Unusable, match="sectors"):
        figures_typst.compile_svg("geometry", "#wheel(sectors: ((0.5, red),))")
    rule = figures_typst.FAMILIES["geometry"].rules
    (call,) = re.findall(r"`(#wheel\([^`]*\))`", rule)
    assert figures_typst.compile_svg("geometry", call).startswith("<svg")


def test_a_triangle_built_from_its_sides():
    """A triangle built with ruler and compass: its third vertex computed at the two lengths
    from the others (AC = 4, BC = 5 on AB = 6), the side as asked; refused when no triangle
    has those lengths (3, 4 and 9: the compass's arcs then never meet); the rule's calls,
    the triangle and its arcs, compile."""
    body = """#ctz-canvas({
  ctz-init()
  ctz-def-points(A: (0, 0), B: (6, 0))
  ctz-def-triangle-sss("C", "A", "B", 4, 5)
  ctz-def-triangle-sss("D", "A", "B", 4, 5, right: true)
  cetz.draw.get-ctx(ctx => {
    let at(n) = cetz.coordinate.resolve(ctx, "ctz:" + n).at(1)
    let d(p, q) = calc.sqrt(calc.pow(p.at(0) - q.at(0), 2) + calc.pow(p.at(1) - q.at(1), 2))
    assert(calc.abs(d(at("C"), at("A")) - 4) < 1e-6 and calc.abs(d(at("C"), at("B")) - 5) < 1e-6, message: "lengths")
    assert(at("C").at(1) > 0 and at("D").at(1) < 0, message: "sides")
  })
  ctz-draw-compass-arc("A", 4, toward: "C")
  ctz-draw-compass-arc("B", 5, toward: 120)
})"""
    assert figures_typst.compile_svg("geometry", body).startswith("<svg")
    with pytest.raises(figures_typst.Unusable, match="no triangle"):
        figures_typst.compile_svg(
            "geometry",
            "#ctz-canvas({ ctz-init(); ctz-def-points(A: (0, 0), B: (9, 0)); "
            'ctz-def-triangle-sss("C", "A", "B", 3, 4) })',
        )
    rule = figures_typst.FAMILIES["geometry"].rules
    calls = "; ".join(re.findall(r"`(ctz-def-triangle-sss\([^`]*\)|ctz-draw-compass-arc\([^`]*\))`", rule))
    body = f"#ctz-canvas({{ ctz-init(); ctz-def-points(A: (0, 0), B: (6, 0)); {calls} }})"
    assert figures_typst.compile_svg("geometry", body).startswith("<svg")


def test_a_protractor_laid_on_its_angle():
    """An angle measured with a protractor: drawn by the preamble from the angle's points (by
    the AI, as SVG twice in 3, not at all once): its 181 ticks, its 19 numbers 0 to 180, as
    wide as its radius on each side of O; its 0 turned with its side [OX); the rule's call compiles."""
    draw = (
        "#ctz-canvas({{ ctz-init(); ctz-def-points(O: (0, 0), X: {x}, Y: (2.57, 3.06)); "
        'ctz-draw-segment("O", "X"); ctz-draw-protractor("O", "X"{opts}) }})'
    )
    flat = draw.format(x="(4, 0)", opts="")
    width, _ = drawn_size("geometry", flat)
    assert width == pytest.approx(7 * 28.35, rel=0.05)  # from its left end (−3) to X (4)
    assert figures_typst.compile_svg("geometry", flat) != figures_typst.compile_svg(
        "geometry", draw.format(x="(0, 4)", opts="")
    )
    assert figures_typst.compile_svg("geometry", draw.format(x="(4, 0)", opts=", clockwise: true")).startswith("<svg")
    rule = figures_typst.FAMILIES["geometry"].rules
    (call,) = re.findall(r"`(ctz-draw-protractor\([^`]*\))`", rule)
    body = f"#ctz-canvas({{ ctz-init(); ctz-def-points(O: (0, 0), X: (4, 0)); {call} }})"
    assert figures_typst.compile_svg("geometry", body).startswith("<svg")


def test_the_rule_writes_an_angles_name_under_its_hat():
    """An angle's name was written (BAC) once in 3, not at all once: the rule shows it under
    its hat, the vertex in the middle, and the call compiles."""
    rule = figures_typst.FAMILIES["geometry"].rules
    assert "name: true" in rule and "never (BAC)" in rule
    body = (
        "#ctz-canvas({ ctz-init(); ctz-def-points(A: (0, 0), B: (4, 0), C: (3, 2.5)); "
        'ctz-draw-angle("A", "B", "C", radius: 0.8, label: $hat(B A C)$) })'
    )
    assert figures_typst.compile_svg("geometry", body).startswith("<svg")


@pytest.mark.parametrize(
    "figure",
    [
        # a triangle's height: its length beside it once fell on the side [AB]
        """ctz-def-points(B: (0, 0), C: (6, 0), H: (2, 0), A: (2, 4))
  ctz-draw-polygon("A", "B", "C")
  ctz-draw-segment("A", "H")
  ctz-draw-length("B", "C", [6 cm], away: "A")
  ctz-draw-length("A", "H", [4 cm], away: "C")""",
        # a diameter's length, written at its middle, fell on the centre O
        """ctz-def-points(O: (0, 0), A: (-3, 0), B: (3, 0), P: (0, 3))
  ctz-draw-circle-r("O", 3)
  ctz-draw-segment("A", "B")
  ctz-draw-points("O")
  ctz-draw-length("A", "B", [6 cm], away: "P")""",
        # a narrow angle's value, at ctz-euclide's fixed distance, lay over a side
        """ctz-def-points(A: (0, 0), B: (5, 0), C: (3.06, 2.57))
  ctz-draw-polygon("A", "B", "C")
  ctz-draw-angle("A", "B", "C", radius: 0.8, label: [40°])
  ctz-draw-length("A", "C", [4 cm], away: "B")""",
        # a length across which two compass arcs pass (a triangle that can't be built)
        """ctz-def-points(A: (0, 0), B: (9, 0))
  ctz-draw-segment("A", "B")
  ctz-draw-compass-arc("A", 3, toward: "B", span: 70)
  ctz-draw-compass-arc("B", 4, toward: "A", span: 70)
  ctz-draw-length("A", "B", [9 cm])""",
        # a length written before the arcs that cross it: placed once they are drawn
        """ctz-def-points(A: (0, 0), B: (9, 0))
  ctz-draw-segment("A", "B")
  ctz-draw-length("A", "B", [9 cm])
  ctz-draw-compass-arc("A", 3, toward: "B", span: 70)
  ctz-draw-compass-arc("B", 4, toward: "A", span: 70)""",
        # words naming a circle's segments, the diameter askew and cut by its centre
        """ctz-def-points(O: (0, 0), A: (3, 0), B: (-2.12, 2.12), C: (2.12, -2.12))
  ctz-draw-circle-r("O", 3)
  ctz-draw-segment("B", "C")
  ctz-draw-segment("O", "A")
  ctz-draw-points("O")
  ctz-draw-length("O", "A", [rayon])
  ctz-draw-length("B", "C", [diamètre])""",
        # a vector's name placed after a relation written as a point's name under the figure
        """ctz-def-points(A: (0, 0), B: (3, 2), C: (5, 0), T: (2.5, -0.8))
  ctz-draw-vector("A", "B", label: $arrow(A B)$, away: "C")
  ctz-draw-vector("B", "C", label: $arrow(B C)$, away: "A")
  ctz-draw-vector("A", "C", label: $arrow(A C)$, away: "B")
  ctz-draw-labels(A: "below left", B: "above", C: "below right",
    T: (pos: "center", label: [$arrow(A B) + arrow(B C) = arrow(A C)$]))""",
        # a line's name in a frame, crossing the x axis: once on the axis and its numbers
        """ctz-draw-grid(xmin: -1, xmax: 5, ymin: -1, ymax: 5, stroke: luma(220) + 0.4pt)
  ctz-draw-axes(xmin: -1, xmax: 5.5, ymin: -1, ymax: 5.5)
  ctz-def-points(P: (2.3, -0.6), Q: (-0.3, 4.6), A: (1, 2))
  ctz-draw-line-add("P", "Q")
  ctz-draw-line-name("P", "Q", $(d)$)""",
        # a relation written under the figure, its vectors' names placed after it
        """ctz-def-points(A: (0, 0), B: (3, 2), C: (5, 0))
  ctz-draw-caption([$arrow(A B) + arrow(B C) = arrow(A C)$])
  ctz-draw-vector("A", "B", label: $arrow(A B)$, away: "C")
  ctz-draw-vector("B", "C", label: $arrow(B C)$, away: "A")
  ctz-draw-vector("A", "C", label: $arrow(A C)$, away: "B")
  ctz-draw-labels(A: "below left", B: "above", C: "below right")""",
        # a line's name, written by hand at coordinates, fell on a point of it
        """ctz-def-points(D1: (-2, 0), D2: (3, 0), A: (1, 3))
  ctz-draw-line-add("D1", "D2")
  ctz-def-perp("P1", "P2", ("D1", "D2"), "A")
  ctz-def-ll("H", ("D1", "D2"), ("P1", "P2"))
  ctz-draw-line-add("H", "A")
  ctz-draw-points("A", "H")
  ctz-draw-line-name("D1", "D2", $(d)$)
  ctz-draw-line-name("H", "A", $(d')$)""",
    ],
)
def test_a_text_the_preamble_places_stands_clear_of_the_drawing(figure):
    """A length, an angle's value and a line's name placed by the preamble where no stroke,
    circle, point or other text is in their way (bench of the collège's figures: 4 cm on a
    side, 6 cm on a centre, 40° on a side, (d') on its point A): every text placed is checked
    against the whole drawing at the end."""
    # checked once the texts are placed, at the canvas's end
    check = """_later(() => cetz.draw.get-ctx(ctx => {
    // the texts the preamble placed (the AI's own, written where it put them: kept as they are)
    let texts = _drawn(ctx).texts.filter(t => not t.at("fixed", default: false))
    assert(texts.len() > 0, message: "nothing placed")
    for t in texts {
      let hits = _box-hits(ctx, t.c, t.hw, t.hh, skip: t.skip)
      assert(hits == 0, message: "a text on the drawing: " + repr(t.c))
    }
  }), ())"""
    body = f"#ctz-canvas({{\n  ctz-init()\n  {figure}\n  {check}\n}})"
    assert figures_typst.compile_svg("geometry", body).startswith("<svg")


def test_a_length_stays_at_its_segments_middle():
    """A diameter's length moved along it to clear the centre O read as the radius's (6 cm
    beside [AO]): a length is written facing its segment's middle, a segment cut by a point
    (O on [AB]) on a dimension line over its whole length."""
    body = """#ctz-canvas({
  ctz-init()
  ctz-def-points(O: (0, 0), A: (-3, 0), B: (3, 0), P: (0, 3))
  ctz-draw-circle-r("O", 3)
  ctz-draw-segment("A", "B")
  ctz-draw-points("O")
  ctz-draw-length("A", "B", [6 cm], away: "P")
  _later(() => cetz.draw.get-ctx(ctx => {
    let t = _drawn(ctx).texts.first()
    assert(calc.abs(t.c.at(0)) < 1e-6, message: "slid along: " + repr(t.c))
    // the dimension line over the whole diameter, from A's side to B's
    let dims = _drawn(ctx).segments.filter(s => calc.abs(s.at(0).at(1)) > 0.3)
    let whole(s) = calc.abs(s.at(0).at(0) + 3) < 1e-6 and calc.abs(s.at(1).at(0) - 3) < 1e-6
    assert(dims.any(whole), message: "no dimension line")
  }), ())
})"""
    assert figures_typst.compile_svg("geometry", body).startswith("<svg")


def test_a_word_naming_a_segment_never_on_a_dimension_line():
    """A word naming a diameter cut by its centre went on a dimension line, askew over the
    circle and across the other words (2 drawings in 3): a word stays beside its segment, only
    a measure goes on a dimension line."""
    body = """#ctz-canvas({{
  ctz-init()
  ctz-def-points(O: (0, 0), B: (-2.12, 2.12), C: (2.12, -2.12))
  ctz-draw-circle-r("O", 3)
  ctz-draw-segment("B", "C")
  ctz-draw-points("O")
  ctz-draw-length("B", "C", {label})
  _later(() => cetz.draw.get-ctx(ctx => {{
    assert(_drawn(ctx).segments.len() == {segments}, message: repr(_drawn(ctx).segments.len()))
  }}), ())
}})"""
    assert figures_typst.compile_svg("geometry", body.format(label="[diamètre]", segments=1)).startswith("<svg")
    assert figures_typst.compile_svg("geometry", body.format(label="[6 cm]", segments=2)).startswith("<svg")


def test_an_angles_name_written_by_its_function():
    """An angle's name the AI wrote "(BAC)" 2 drawings in 3, the rule notwithstanding:
    `name: true` writes BAC under its hat, the vertex in the middle; the rule's call compiles."""
    draw = (
        "#ctz-canvas({{ ctz-init(); ctz-def-points(A: (0, 0), B: (4, 0), C: (3, 2.5)); "
        'ctz-draw-angle("A", "B", "C", radius: 0.8{}) }})'
    )
    named = figures_typst.compile_svg("geometry", draw.format(", name: true"))
    assert named == figures_typst.compile_svg("geometry", draw.format(", label: $hat(B A C)$"))
    assert named != figures_typst.compile_svg("geometry", draw.format(""))
    # its width counted from its letters, the hat over them (counted as one, it lay on a side)
    width = (
        '#ctz-canvas({ ctz-init(); ctz-def-points(A: (0, 0), B: (4, 0)); ctz-draw-segment("A", "B"); '
        "cetz.draw.get-ctx(ctx => { "
        "assert(_name-chars($hat(B A C)$) == 3, message: repr(_name-chars($hat(B A C)$))) }) })"
    )
    assert figures_typst.compile_svg("geometry", width).startswith("<svg")
    rule = figures_typst.FAMILIES["geometry"].rules
    assert "never (BAC)" in rule
    (call,) = re.findall(r"`(ctz-draw-angle\([^`]*name: true\))`", rule)
    body = f"#ctz-canvas({{ ctz-init(); ctz-def-points(A: (0, 0), B: (4, 0), C: (3, 2.5)); {call} }})"
    assert figures_typst.compile_svg("geometry", body).startswith("<svg")


def test_a_vectors_name_clear_of_a_relation_written_under_the_figure():
    """Chasles' relation written as a point's name under the triangle, AB + BC = AC: the name of
    the vector AC, placed below it (away from B), fell on it (2 drawings in 3). The points'
    names are known to the texts placed after them: AC's name stands clear of the relation."""
    body = """#ctz-canvas({
  ctz-init()
  ctz-def-points(A: (0, 0), B: (3, 2), C: (5, 0), T: (2.5, -0.8))
  ctz-draw-vector("A", "B", label: $arrow(A B)$, away: "C")
  ctz-draw-vector("B", "C", label: $arrow(B C)$, away: "A")
  ctz-draw-vector("A", "C", label: $arrow(A C)$, away: "B")
  ctz-draw-labels(A: "below left", B: "above", C: "below right",
    T: (pos: "center", label: [$arrow(A B) + arrow(B C) = arrow(A C)$]))
  _later(() => cetz.draw.get-ctx(ctx => {
    let placed = _drawn(ctx).texts.filter(t => not t.at("fixed", default: false))
    let ac = placed.last()
    // the relation's box: centred on T, as wide as its letters
    let (hw, hh) = (0.11 * 13 + 0.06, 0.24)
    let apart = calc.abs(ac.c.at(0) - 2.5) > ac.hw + hw or calc.abs(ac.c.at(1) + 0.8) > ac.hh + hh
    assert(apart, message: "AC's name on the relation: " + repr(ac.c))
  }), ())
})"""
    assert figures_typst.compile_svg("geometry", body).startswith("<svg")


def test_a_relation_written_under_the_whole_figure():
    """Chasles' relation written by the AI as a point's name near C fell on C (1 drawing in 3):
    `ctz-draw-caption` writes it under the whole figure, centred, once it is all drawn; the
    rule's call compiles."""
    body = """#ctz-canvas({
  ctz-init()
  ctz-def-points(A: (0, 0), B: (3, 2), C: (5, 0))
  ctz-draw-polygon("A", "B", "C")
  ctz-draw-caption([$arrow(A B) + arrow(B C) = arrow(A C)$])
  _later(() => cetz.draw.get-ctx(ctx => {
    let t = _drawn(ctx).texts.last()
    assert(t.c.at(1) + t.hh < -0.2, message: "not under the figure: " + repr(t.c))
    assert(calc.abs(t.c.at(0) - 2.5) < 1e-6, message: "not centred: " + repr(t.c))
  }), ())
})"""
    assert figures_typst.compile_svg("geometry", body).startswith("<svg")
    rule = figures_typst.FAMILIES["geometry"].rules
    (call,) = re.findall(r"`(ctz-draw-caption\([^`]*\))`", rule)
    example = f'#ctz-canvas({{ ctz-init(); ctz-def-points(A: (0, 0), B: (3, 2)); ctz-draw-segment("A", "B"); {call} }})'
    assert figures_typst.compile_svg("geometry", example).startswith("<svg")


def test_a_lines_name_off_the_axes_of_its_frame():
    """A normal vector's line, crossing the x axis, its name (d) written on the axis among its
    numbers (1 drawing in 3): the axes and their numbers are known to the names placed after
    them, the name stays off the band the x axis and its numbers take."""
    body = """#ctz-canvas({
  ctz-init()
  ctz-draw-grid(xmin: -1, xmax: 5, ymin: -1, ymax: 5, stroke: luma(220) + 0.4pt)
  ctz-draw-axes(xmin: -1, xmax: 5.5, ymin: -1, ymax: 5.5)
  ctz-def-points(A: (1, 2), P1: (0, 4), P2: (2.5, -1), B: (3, 3))
  ctz-draw-line-add("P1", "P2")
  ctz-draw-line-name("P1", "P2", $(d)$)
  ctz-draw-vector("A", "B", label: $arrow(n)$)
  ctz-draw-mark-right-angle("P1", "A", "B")
  ctz-draw-points("A")
  ctz-draw-labels(A: "below left")
  _later(() => cetz.draw.get-ctx(ctx => {
    let t = _drawn(ctx).texts.filter(t => not t.at("fixed", default: false)).first()
    let (low, high) = (t.c.at(1) - t.hh, t.c.at(1) + t.hh)
    assert(high < -0.45 or low > 0.05, message: "on the x axis: " + repr(t.c))
  }), ())
})"""
    assert figures_typst.compile_svg("geometry", body).startswith("<svg")


def test_the_rule_names_a_line_by_its_function():
    """The rule shows a line's name by ctz-draw-line-name, never by ctz-draw-text at
    coordinates: its call compiles."""
    rule = figures_typst.FAMILIES["geometry"].rules
    assert "ctz-draw-text(2.2, 2" not in rule
    (call,) = set(re.findall(r"`(ctz-draw-line-name\([^`]*\))`", rule))
    body = f'#ctz-canvas({{ ctz-init(); ctz-def-points(A: (0, 0), B: (3, 1)); ctz-draw-line-add("A", "B"); {call} }})'
    assert figures_typst.compile_svg("geometry", body).startswith("<svg")


def test_a_symmetry_centre_placed_clear_of_its_figure():
    """A symmetry about a point the description doesn't place: its centre computed from the
    figure, never placed by eye (by eye, the AI put a vertex in line with B and O 2 drawings
    in 3: [BB'] over [CC'], their marks in a heap at O). For triangles of every shape: the
    image clear of the figure by the gap, no two vertices within 10° of a line through the
    centre, the image on the right of the figure; the rule's call compiles."""
    body = """#let triangles = (
  ((0, 0), (3, 0.5), (1, 2.5)), ((0, 0), (4, 0), (0, 3)), ((0, 0), (3, 1), (2, 3)),
  ((1, 0), (0, 2), (3, 3)), ((0, 0), (5, 0), (2.5, 0.5)), ((0, 0), (1, 4), (-1, 3)),
)
#for pts in triangles {
  let o = _symmetry-centre(pts, 1.5)
  let image = pts.map(q => (2 * o.at(0) - q.at(0), 2 * o.at(1) - q.at(1)))
  // apart along the line from the figure's centre to O: the image a gap after the figure
  let g = (pts.map(q => q.at(0)).sum() / 3, pts.map(q => q.at(1)).sum() / 3)
  let (ux, uy) = (o.at(0) - g.at(0), o.at(1) - g.at(1))
  let along(q) = q.at(0) * ux + q.at(1) * uy
  let gap = (calc.min(..image.map(along)) - calc.max(..pts.map(along))) / calc.sqrt(ux * ux + uy * uy)
  assert(gap >= 1.5 - 1e-9, message: "touches")
  assert(ux > 0, message: "image on the left")
  let angle(q) = calc.atan2(q.at(0) - o.at(0), q.at(1) - o.at(1)) / 1deg
  for i in range(3) {
    for j in range(i + 1, 3) {
      let d = calc.rem-euclid(angle(pts.at(i)) - angle(pts.at(j)), 180)
      assert(calc.min(d, 180 - d) >= 10, message: "two vertices in line with the centre")
    }
  }
}
#ctz-canvas({
  ctz-init()
  ctz-def-points(A: (0, 0), B: (3, 0.5), C: (1, 2.5))
  ctz-def-symmetry-centre("O", ("A", "B", "C"))
  ctz-def-symmetry("A'", "A", "O")
  ctz-draw-segment("A", "A'")
})"""
    figures_typst.compile_svg("geometry", body)
    rule = figures_typst.FAMILIES["geometry"].rules
    (call,) = re.findall(r"`(ctz-def-symmetry-centre\([^`]*\))`", rule)
    points = "ctz-def-points(A: (0, 0), B: (3, 0.5), C: (1, 2.5))"
    image = 'ctz-def-symmetry("A\'", "A", "O"); ctz-draw-segment("A", "A\'")'
    example = f"#ctz-canvas({{ ctz-init(); {points}; {call}; {image} }})"
    assert figures_typst.compile_svg("geometry", example).startswith("<svg")


def test_a_figures_axis_drawn_through_its_own_points():
    """An axis of symmetry with ends at coordinates of the AI's own missed an equilateral
    triangle's centre 1 drawing in 3: the rule has it through two points of the figure,
    computed (a vertex and the opposite side's midpoint)."""
    rule = figures_typst.FAMILIES["geometry"].rules
    assert "axis of symmetry" in rule and "never ends at coordinates of your own" in rule


@pytest.mark.parametrize(
    ("shape", "rings", "tiles"),
    [("hexagon", 1, 7), ("hexagon", 2, 19), ("square", 1, 9), ("triangle", 1, 21)],
)
def test_a_tiling_computed_edge_to_edge(shape, rings, tiles):
    """A tiling of hexagons drawn by the AI as SVG had them overlapping (1 drawing in 3):
    `tiling` places every tile edge to edge, as many as its rings hold; coloured "alternate",
    its tiles take three colours (hexagons) or two, "centre" one tile coloured."""
    svg = figures.clean(figures_typst.compile_svg("geometry", f'#tiling(shape: "{shape}", rings: {rings})'))
    assert svg.count("<path") == tiles + 1  # and the page's background
    alternate = figures.clean(
        figures_typst.compile_svg("geometry", f'#tiling(shape: "{shape}", rings: {rings}, fill: "alternate")')
    )
    fills = set(re.findall(r'fill="(#[0-9a-f]{6})"', alternate)) - {"#ffffff"}
    assert len(fills) == (3 if shape == "hexagon" else 2)
    centre = figures.clean(
        figures_typst.compile_svg("geometry", f'#tiling(shape: "{shape}", rings: {rings}, fill: "centre")')
    )
    assert len(set(re.findall(r'fill="(#[0-9a-f]{6})"', centre)) - {"#ffffff"}) == 1


def test_the_rule_shows_a_tiling_that_compiles():
    rule = figures_typst.FAMILIES["geometry"].rules
    (call,) = re.findall(r"`(#tiling\([^`]*\))`", rule)
    assert figures_typst.compile_svg("geometry", call).startswith("<svg")


def test_an_intervals_centre_and_its_distances():
    """|x − 3| ≤ 2 on a number line: the interval [1 ; 5], its centre 3 and the distance 2 on
    each side, drawn by the AI without the distances (1 drawing in 3) or as SVG: `centre: true`
    marks the centre and writes the half-length, computed, over each half; refused without
    two bounds; the rule's call compiles."""
    draw = "#ctz-canvas({{ ctz-init(); ctz-draw-number-line(-2, 8); ctz-draw-interval(1, 5, first: -2, last: 8{}) }})"
    _, plain = drawn_size("geometry", draw.format(""))
    _, centred = drawn_size("geometry", draw.format(", centre: true"))
    assert centred > plain + 0.4 * 28.35  # the arrows and their numbers over the line
    with pytest.raises(figures_typst.Unusable, match="two bounds"):
        figures_typst.compile_svg(
            "geometry", draw.format(", centre: true").replace("ctz-draw-interval(1, 5", "ctz-draw-interval(1, none")
        )
    rule = figures_typst.FAMILIES["geometry"].rules
    (call,) = re.findall(r"`(ctz-draw-interval\([^`]*centre: true\))`", rule)
    body = f"#ctz-canvas({{ ctz-init(); ctz-draw-number-line(-2, 8); {call} }})"
    assert figures_typst.compile_svg("geometry", body).startswith("<svg")


def test_the_real_line_wound_round_the_circle():
    """The real line wound round the trigonometric circle, drawn by the AI: a circle with
    nothing wound, or names on one another (0 drawings in 3). `ctz-draw-wrapping` draws it from
    the values: each number's stretch on the tangent line and its arc, as long as it, in the
    same colour; π/2 comes onto (0 ; r), π onto (−r ; 0). Its size follows: π r tall above
    the axis. The rule's call compiles."""
    draw = "#ctz-canvas({{ ctz-init(); ctz-draw-wrapping(numbers: {numbers}, r: 2) }})"
    half = figures_typst.compile_svg("geometry", draw.format(numbers="((0, $0$, $I$), (calc.pi / 2, $pi/2$, $J$))"))
    whole = figures_typst.compile_svg("geometry", draw.format(numbers="((0, $0$, $I$), (calc.pi, $pi$, none))"))
    assert half != whole
    _, h_half = drawn_size("geometry", draw.format(numbers="((calc.pi / 2, $pi/2$),)"))
    _, h_whole = drawn_size("geometry", draw.format(numbers="((calc.pi, $pi$),)"))
    assert h_whole - h_half == pytest.approx(2 * math.pi / 2 * 28.35, rel=0.1)  # π r − π r / 2, in pt
    rule = figures_typst.FAMILIES["geometry"].rules
    (call,) = re.findall(r"`(ctz-draw-wrapping\([^`]*\))`", rule)
    assert figures_typst.compile_svg("geometry", f"#ctz-canvas({{ ctz-init(); {call} }})").startswith("<svg")


def test_a_rotations_arrowed_arc_drawn_from_its_points():
    """A rotation's direction shown by an arrowed arc the preamble draws from the point, the
    centre and the image (the AI guessed ctz-draw-arc's arguments, `mark:`, `radius:`,
    `start:`, refused twice: the figure drawn as SVG): the way it turns given, the arc from
    the point to its image; a point onto itself refused; the rule's call compiles."""
    draw = (
        '#ctz-canvas({{ ctz-init(); ctz-def-points(O: (0, 0), A: (2, 0)); ctz-def-rotation("A\'", "A", "O", 90); {} }})'
    )

    def arc(args: str) -> str:
        return figures_typst.compile_svg("geometry", draw.format(f'ctz-draw-rotation-arc("A", "O", "A\'"{args})'))

    assert arc("") != arc(", clockwise: true")  # a quarter turn one way, three the other
    assert arc("") != arc(", label: [90°]")
    with pytest.raises(figures_typst.Unusable, match="apart from it"):
        figures_typst.compile_svg("geometry", draw.format('ctz-draw-rotation-arc("A", "O", "A")'))
    rule = figures_typst.FAMILIES["geometry"].rules
    (call,) = re.findall(r"`(ctz-draw-rotation-arc\([^`]*\))`", rule)
    assert figures_typst.compile_svg("geometry", draw.format(call)).startswith("<svg")


def test_a_rotations_arc_turns_the_way_it_is_given():
    """A quarter turn anticlockwise from A (2, 0) about O: its arc a quarter of a circle, the
    radius wide and high; `clockwise: true` the three quarters the other way, its diameter wide
    and high (each way drawn the other's way: the same two drawings, swapped)."""
    draw = (
        '#ctz-canvas({{ ctz-init(); ctz-def-points(O: (0, 0), A: (2, 0)); ctz-def-rotation("A\'", "A", "O", 90); '
        'ctz-draw-rotation-arc("A", "O", "A\'"{}) }})'
    )
    radius = 0.9 * 28.35  # the arc's default radius, in pt
    quarter = drawn_size("geometry", draw.format(""))
    three_quarters = drawn_size("geometry", draw.format(", clockwise: true"))
    assert all(0.8 * radius < side < 1.3 * radius for side in quarter), quarter
    assert all(1.8 * radius < side < 2.3 * radius for side in three_quarters), three_quarters


@pytest.mark.parametrize("add", ["", ", add: (0.2, 0.2)", ", add: (0.5, 0.5)", ", add: 2"])
def test_a_whole_line_goes_little_past_its_points(add):
    """A line past its two points by 15 % of the figure at most, whatever `add` asks: the
    tangent to a circle of radius 3, `add: (0.5, 0.5)` on its points 6 apart, ran 3 past
    each, the figure 12.4 cm tall (the circle 6): shrunk on a card, its text with it."""
    tangent = """#ctz-canvas({{
  ctz-init()
  ctz-def-points(O: (0, 0), A: (3, 0))
  ctz-def-perp("T1", "T2", ("O", "A"), "A")
  ctz-draw-circle-r("O", 3)
  ctz-draw-line-add("T1", "T2"{})
}})"""
    _, height = drawn_size("geometry", tangent.format(add))
    assert height <= (6 + 2 * 0.9) * 28.35 + 1
    # nor does the rule show an `add` carrying a line farther (it did, beside its own bullet
    # saying never)
    assert "add: (0.5, 0.5)" not in (figures_typst.RULES / "geometry.md").read_text(encoding="utf-8")


def test_a_half_line_stays_one():
    """`add: (0, …)`: nothing past its first point (a half-line from it)."""
    ray = """#ctz-canvas({{
  ctz-init()
  ctz-def-points(O: (0, 0), A: (2, 0), B: (0, 2))
  ctz-draw-segment("O", "B")
  ctz-draw-line-add("O", "A", add: ({}, 0.5))
}})"""
    assert drawn_size("geometry", ray.format(0))[0] < drawn_size("geometry", ray.format(0.2))[0]


def _distance_to_line(point, a, b):
    """The distance from a point to the line through a and b."""
    (px, py), (ax, ay), (bx, by) = point, a, b
    return abs((bx - ax) * (py - ay) - (by - ay) * (px - ax)) / ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5


def _crossing(first, second):
    """Where the line through first's two points crosses the line through second's."""
    (x1, y1), (x2, y2) = first
    (x3, y3), (x4, y4) = second
    d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / d
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


SUN = "(centre: (0, 0), r: 2)"


def test_a_shadows_rays_tangent_to_the_source_and_the_body():
    """An eclipse's rays were drawn by the AI's eye, as SVG (none touching the Earth, meeting
    anywhere): the preamble computes them, the external common tangents of the source and the
    body (each at a radius from both centres), meeting at the cone's apex on the axis; the
    penumbra's, the internal ones, crossing between them; from a point source, its tangents
    to the body."""
    layout = f"_shadow-layout({SUN}, (centre: (8, 1), r: 0.8), penumbra: true)"
    ext, inner = _measured(f"{layout}.ext"), _measured(f"{layout}.inner-rays")
    for ray in ext + inner:
        assert _distance_to_line((0, 0), *ray) == pytest.approx(2)
        assert _distance_to_line((8, 1), *ray) == pytest.approx(0.8)
    # the cone's apex: where the limiting rays meet, on the axis, D × R / (R − r) from the source
    apex = _measured(f"{layout}.apex")
    assert _crossing(*ext) == pytest.approx(apex)
    d = (8**2 + 1**2) ** 0.5
    assert apex == pytest.approx([8 / d * d * 2 / 1.2, 1 / d * d * 2 / 1.2])
    # the penumbra's rays cross between the source and the body
    x, _ = _crossing(*inner)
    assert 0 < x < 8
    # each ray stops at the apex
    assert _measured(f"{layout}.ext-ends") == [pytest.approx(apex)] * 2
    # a point source: its rays from it, tangent to the body, no apex (the shadow widens)
    point = "_shadow-layout((centre: (0, 0), r: 0), (centre: (4, 0), r: 1))"
    for start, contact in _measured(f"{point}.ext"):
        assert start == pytest.approx([0, 0])
        assert _distance_to_line((4, 0), start, contact) == pytest.approx(1)
    assert _measured(f"{point}.apex") is None


def test_a_flat_bodys_shadow_cone_ends_where_its_rays_meet():
    """A flat body (a bar seen edge on): its cone's apex taken as a disc's, D × R / (R − r),
    though its rays, through its ends, meet sooner (4.8 drawn, 4.52 true): with no screen they
    ran past each other, the shadow a crossed bow-tie. Its apex where its rays cross the axis,
    the cone ending there."""
    layout = f'_shadow-layout({SUN}, (centre: (3, 0), r: 0.75, shape: "segment"))'
    ext, apex = _measured(f"{layout}.ext"), _measured(f"{layout}.apex")
    assert apex == pytest.approx(_crossing(*ext)) and apex[1] == pytest.approx(0)
    assert apex[0] == pytest.approx(4.52, abs=0.01)
    assert _measured(f"{layout}.ext-ends") == [pytest.approx(apex)] * 2
    # a disc's, as it was
    disc = _measured(f"_shadow-layout({SUN}, (centre: (3, 0), r: 0.75)).apex")
    assert disc == pytest.approx([3 * 2 / 1.25, 0])


def test_a_shadow_behind_its_body_cast_on_its_screen():
    """The shade was drawn between the source and the body (the lit side): the shadow cone is
    behind the body, from its contacts to the rays' ends beyond it; a screen's cast shadow is
    where the rays meet it, between them, a planet's on its surface."""
    point = "_shadow-layout((centre: (0, 0), r: 0), (centre: (4, 0), r: 1), screen: (at: 9))"
    ext, ends = _measured(f"{point}.ext"), _measured(f"{point}.ext-ends")
    for (_, contact), end in zip(ext, ends, strict=True):
        assert contact[0] > 3 and end[0] > contact[0]
    cast = _measured(f"{point}.cast-umbra")
    assert [p[0] for p in cast] == pytest.approx([9, 9])
    # on the screen, between the rays: wider than the body, the source a point
    assert sorted(p[1] for p in cast)[0] < -1 < 1 < sorted(p[1] for p in cast)[1]
    for (start, contact), p in zip(ext, cast, strict=True):
        assert _distance_to_line(p, start, contact) == pytest.approx(0, abs=1e-6)
    # the source wider than the body: a screen beyond the apex is reached by the penumbra only
    wide = f"_shadow-layout({SUN}, (centre: (8, 0), r: 0.8), screen: (at: 20), penumbra: true)"
    assert _measured(f"{wide}.cast-umbra") is None
    assert _measured(f"{wide}.cast-penumbra") is not None
    # a planet the shadow reaches (a solar eclipse): the apex inside it, the shadow cast on its
    # surface
    planet = f"_shadow-layout({SUN}, (centre: (7, 0), r: 0.6), screen: (r: 1.5))"
    centre, apex = _measured(f"{planet}.sc"), _measured(f"{planet}.apex")
    assert ((apex[0] - centre[0]) ** 2 + apex[1] ** 2) ** 0.5 < 1.5
    for p in _measured(f"{planet}.cast-umbra"):
        assert ((p[0] - centre[0]) ** 2 + p[1] ** 2) ** 0.5 == pytest.approx(1.5)
        assert p[0] < centre[0]  # on the side facing the body
    with pytest.raises(Exception, match="behind the body"):
        _measured("_shadow-layout((centre: (0, 0), r: 0), (centre: (4, 0), r: 1), screen: (at: 3))")


def test_a_body_inside_the_shadow_fits_its_cone():
    """The Moon in the Earth's shadow was placed and sized by eye (outside the cone, or the
    cone ending short of it): it is on the axis, past the Earth, its whole disc inside the
    cone, whatever `along`."""
    for along in (0.2, 0.5, 0.8):
        layout = f"_shadow-layout({SUN}, (centre: (8, 0), r: 0.8), inside: (along: {along}))"
        inner, ext = _measured(f"{layout}.inner"), _measured(f"{layout}.ext")
        (x, y), r = inner["centre"], inner["r"]
        assert y == pytest.approx(0) and x - r > 8.8
        for ray in ext:
            assert _distance_to_line((x, y), *ray) > r


def test_the_geometry_rules_shadows_compile():
    """Every shadow the geometry rule shows compiles, as the AI copies it, and draws its own
    shadow and its penumbra when asked."""
    rules = figures_typst.FAMILIES["geometry"].rules
    rule = next(line for line in rules.splitlines() if line.startswith("- a shadow"))
    calls = re.findall(r"`(ctz-draw-shadow\([^`]*\))`", rule)
    assert calls
    draw = lambda call: figures_typst.compile_svg("geometry", f"#ctz-canvas({{ ctz-init(); {call} }})")  # noqa: E731
    for call in calls:
        assert draw(call).startswith("<svg")
    ball = "source: (centre: (0, 0), r: 1, name: [lampe]), body: (centre: (5, 0), r: 0.7), screen: (name: [écran])"
    plain = draw(f"ctz-draw-shadow({ball})")
    assert draw(f"ctz-draw-shadow({ball}, own: true)") != plain
    assert draw(f"ctz-draw-shadow({ball}, penumbra: true)") != plain
    assert draw(f"ctz-draw-shadow({ball}, labels: (cast: [ombre portée]))") != plain


@pytest.mark.parametrize(
    ("body", "said"),
    [
        ('#fraction-shape(kind: "rect", parts: 4, coloured: 1, rows: 0)', "rows is a rectangle's number of rows"),
        ("#cetz.canvas({ ctz-draw-interval(none, none) })", "an interval has a bound"),
    ],
)
def test_a_fraction_or_an_interval_refused_saying_why(body, said):
    """A rectangle of 0 rows (its parts divided by zero), an interval with neither bound nor the
    line's last value (the maximum of nothing): refused, saying what they take."""
    with pytest.raises(figures_typst.Unusable, match=said):
        figures_typst.compile_svg("geometry", body)
    # the whole line, its ends given: drawn
    figures_typst.compile_svg("geometry", "#cetz.canvas({ ctz-draw-interval(none, none, first: -5, last: 5) })")


def test_the_whole_logarithmic_line_as_an_interval():
    """`ctz-draw-interval(none, none, log: true)`, the whole of a logarithmic line (its ends
    its own): it took the maximum of no bound and raised "expected at least one value". Now
    drawn, over the line alone (the drawing no larger)."""
    line = "#ctz-canvas({{ ctz-init(); ctz-draw-number-line(log: true, points: (A: 1, B: 1e5)){} }})"
    bare = figures_typst.compile_svg("geometry", line.format(""))
    whole = figures_typst.compile_svg("geometry", line.format("; ctz-draw-interval(none, none, log: true)"))
    assert whole != bare
    assert drawn_size("geometry", line.format("; ctz-draw-interval(none, none, log: true)")) == pytest.approx(
        drawn_size("geometry", line.format("")), abs=1
    )
