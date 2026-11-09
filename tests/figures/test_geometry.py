"""The geometry family (ctz-euclide and our functions): number lines, intervals, the
trigonometric circle, lengths, fractions, vectors, coordinate frames."""

import re

import pytest

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
    ctz-def-mediator's and ctz-def-bisect's are): the AI carried a tangent's points twice as far,
    a line 13 units long on a circle of 6, the circle shrunk (1 drawing in 3). They are at the
    reference segment's length on each side of the point: a tangent at A to a circle of radius
    3, drawn through them, as high as the circle."""
    rule = (figures_typst.RULES / "geometry.md").read_text(encoding="utf-8")
    assert "ctz-def-perp and ctz-def-para give are near" in rule
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
    out of the figure's angle at A, the rightmost of the nearly as good."""
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
