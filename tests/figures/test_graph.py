"""The graph family (lilaq): coordinate frames, surfaces, axes and their names, where two
curves meet."""

import re

import pytest

from figures.support import _glyphs, drawn_size
from notosaurus_core import figures_typst


def test_a_coordinate_frame_as_the_graph_rule_writes_it():
    """Points in a coordinate frame (reading or placing coordinates), each call as the graph
    rule gives it: drawn, its grid with it (a line per unit: more lines than without it)."""
    lines = figures_typst.FAMILIES["graph"].rules.splitlines()
    rule = next(line for line in lines if line.startswith("- a coordinate frame"))
    calls = re.findall(r"`((?:#show: lq\.set-grid|lq\.scatter|lq\.place)[^`]*)`", rule)
    assert len(calls) == 4, calls  # the grid, a point, its name, the origin's
    grid, point, name, origin = calls
    axes = "xlim: (-4.5, 4.5), ylim: (-4.5, 4.5), xaxis: (tick-distance: 1, subticks: none), yaxis: (tick-distance: 1)"
    frame = f"#lq.diagram(width: 6cm, height: 6cm, {axes}, {point}, {name}, {origin})"
    with_grid = figures_typst.compile_svg("graph", f"{grid}\n{frame}")
    without = figures_typst.compile_svg("graph", frame)
    assert with_grid.count("<path") > without.count("<path") + 10


def test_the_graph_rules_example_is_orthonormal():
    """The graph rule asks for an orthonormal frame, width / height = xlim's length / ylim's,
    exactly: its example does so (the model copies the example before it reads the rule)."""
    typst = (figures_typst.RULES / "graph.typ").read_text(encoding="utf-8")
    width, height = (float(n) for n in re.search(r"width: ([\d.]+)cm, height: ([\d.]+)cm", typst).groups())
    x0, x1, y0, y1 = (
        float(n) for n in re.search(r"xlim: \(([-\d.]+), ([-\d.]+)\), ylim: \(([-\d.]+), ([-\d.]+)\)", typst).groups()
    )
    assert width / height == pytest.approx((x1 - x0) / (y1 - y0))


def test_the_graph_rules_own_fragments_compile():
    """What the graph rule shows besides its example (the axis's ticks, points, a line)
    compiles too, in that example: a fragment out of step makes every graph with it fail."""
    rules = figures_typst.FAMILIES["graph"].rules
    example = re.search(r"exactly so:\n(.*?)\n- ", rules, re.S).group(1)
    fragments = re.findall(r"`((?:xaxis: |lq\.scatter|lq\.line|lq\.place|named\(|asymptote\()[^`]*)`", rules)
    assert len(fragments) >= 4
    for fragment in fragments:
        body = example.replace("  lq.plot(", f"  {fragment},\n  lq.plot(")
        assert figures_typst.compile_svg("graph", body).startswith("<svg"), fragment


def test_a_graphs_surface_filled_as_the_rule_says():
    """An area (an integral, between two curves, under a density): the AI invented its own
    filling (`lq.area-between`, `lq.polygon`, `lq.area`), refused twice, the figure drawn as
    SVG by eye 8 times in 8. The rule's calls compile and fill between the bounds, computed
    from the functions; the name placed inside, at the surface's centre."""
    rules = figures_typst.FAMILIES["graph"].rules
    example = re.search(r"exactly so:\n(.*?)\n- ", rules, re.S).group(1)
    calls = re.findall(r"`(area(?:-name)?\([^`]*\))`", rules)
    assert len(calls) == 3
    for call in calls:
        body = example.replace("  lq.plot(", f"  {call},\n  lq.plot(")
        assert figures_typst.compile_svg("graph", body).startswith("<svg"), call
    square = "#lq.diagram(xlim: (-1, 3), ylim: (-1, 5), {})"
    xs = "lq.linspace(0, 2, num: 200)"
    ours = figures_typst.compile_svg("graph", square.format("area(x => x * x, 0, 2, fill: red)"))
    lilaqs = f"lq.fill-between({xs}, {xs}.map(x => x * x), y2: {xs}.map(x => 0), fill: red)"
    assert ours == figures_typst.compile_svg("graph", square.format(lilaqs))
    named = figures_typst.compile_svg("graph", square.format("area-name(x => x * x, 0, 2, [A])"))
    # its centre: x = ∫x·x² / ∫x², y = ∫x⁴/2 / ∫x²
    centre = "lq.place(1.5, 1.2, box(fill: white, inset: 0.15em, radius: 2pt)[A], align: center + horizon)"
    there, meant = _glyphs(named), _glyphs(figures_typst.compile_svg("graph", square.format(centre)))
    assert len(there) == len(meant)
    assert all(a == pytest.approx(b, abs=0.5) for a, b in zip(sorted(there), sorted(meant), strict=True))  # pt


def test_a_graphs_axes_never_written_with_a_factor():
    """Large values: lilaq wrote "× 10⁵" at the axis's end, on the axis's name ("Ec (J)"). The
    ticks written in full, whatever the AI gives its axis (its own `yaxis`, its position)."""
    graph = (
        "#lq.diagram(width: 8cm, height: 5cm, xlim: (0, 30), ylim: (0, 450000), {}"
        " xlabel: [v (m/s)], ylabel: [Ec (J)], lq.plot((0, 30), (0, 450000), mark: none))"
    )
    own = figures_typst.compile_svg("graph", graph.format("yaxis: (position: 0),"))
    whole = figures_typst.compile_svg("graph", graph.format("yaxis: (position: 0, exponent: none),"))
    assert own == whole
    assert figures_typst.compile_svg("graph", graph.format("")) == figures_typst.compile_svg(
        "graph", graph.format("yaxis: (exponent: none), xaxis: (exponent: none),")
    )


def test_a_graphs_x_axis_name_clear_of_its_last_number():
    """The x axis's name, set by the theme below the axis's end, touched the last tick's number
    ("0,25" against "I (A)"): placed past the arrow, a little apart, it starts well after it."""
    svg = figures_typst.compile_svg(
        "graph",
        "#lq.diagram(width: 6cm, height: 4cm, xlim: (0, 0.26), ylim: (0, 12), xlabel: [I (A)],"
        " lq.plot((0, 0.25), (0, 12.5), mark: none))",
    )
    glyphs = sorted(_glyphs(svg))
    name, numbers = glyphs[-1], glyphs[:-1]
    row = max({y for _, y in numbers}, key=lambda y: sum(g[1] == y for g in numbers))  # the tick numbers' row
    last = max(x for x, y in numbers if y == row)  # the last number's last glyph
    assert name[0] - last > 9  # pt: a digit's width and a gap, at least


def test_a_graphs_close_ticks_names_kept_apart():
    """Ticks the AI names whose values are close ("a = 1" against α, u₂ against u₃: written
    one on the other): the one that would touch goes on a second row, computed; names far
    apart stay on one row."""
    graph = (
        "#lq.diagram(width: 6cm, height: 4cm, xlim: (0, 2), ylim: (0, 1),"
        " xaxis: (ticks: ((1, [aaa]), ({}, [bbb]))), lq.plot((0, 2), (0, 1), mark: none))"
    )

    def rows(second: float) -> int:
        glyphs = _glyphs(figures_typst.compile_svg("graph", graph.format(second)))
        below = max(y for _, y in glyphs) - 20  # the x axis's names, under it
        return len({y for x, y in glyphs if x > 20 and y < below})

    assert rows(1.1) == 2
    assert rows(1.8) == 1


def test_a_plain_number_touching_a_named_value_not_written():
    """The axis numbered 1, 2, 3 and the terms u₂ (1.93) and u₃ (1.98) named on it: u₃ went on
    the second row, "2" fell back on the first, against u₂ ("u₂2"). A plain number touching a
    value named otherwise isn't written (its tick stays); far from any, it is."""
    graph = (
        "#lq.diagram(width: 7cm, height: 4cm, xlim: (0, 3.2), ylim: (0, 3),"
        " xaxis: (ticks: ({})), lq.plot((0, 3), (0, 3), mark: none))"
    )

    def drawn(ticks: str) -> list[tuple[float, float]]:
        return _glyphs(figures_typst.compile_svg("graph", graph.format(ticks)))

    terms = "(1.93, $u_2$), (1.98, $u_3$)"
    assert drawn(f"(1, $1$), (2, $2$), (3, $3$), {terms}") == drawn(f"(1, $1$), (2, []), (3, $3$), {terms}")
    assert drawn("(1, $1$), (2, $2$), (3, $3$)") != drawn("(1, $1$), (2, []), (3, $3$)")


def test_where_two_curves_meet_computed_and_marked():
    """Two lines' intersection the description asks for, marked by the AI with a dot too
    small to see and its coordinates left out: computed by the preamble (Typst itself
    checks the points), its dot, its dotted lines and its coordinates all drawn."""
    check = """#{
      let near(p, q) = calc.abs(p.at(0) - q.at(0)) < 1e-6 and calc.abs(p.at(1) - q.at(1)) < 1e-6
      let lines = _meet-points(x => 2 * x - 1, x => -x + 2, -1, 3)
      assert(lines.len() == 1 and near(lines.at(0), (1, 1)), message: repr(lines))
      let curve = _meet-points(x => calc.pow(x, 2) - 1, x => x + 1, -1.5, 3)
      assert(curve.len() == 2 and near(curve.at(0), (-1, 0)) and near(curve.at(1), (2, 3)), message: repr(curve))
      [checked]
    }"""
    assert figures_typst.compile_svg("graph", check).startswith("<svg")
    drawn = (
        '#set text(lang: "fr")\n#lq.diagram(xlim: (-1, 3), ylim: (-2, 4), meet(x => 2 * x - 1, x => -x + 2, -1, 3{}))'
    )
    svg = lambda options: figures_typst.compile_svg("graph", drawn.format(options))  # noqa: E731
    # each part kept (a diagram's elements are dictionaries: several merged into the last)
    assert len({svg(""), svg(", lines: true"), svg(", label: auto"), svg(", lines: true, label: auto")}) == 4
    assert "meet(" in figures_typst.FAMILIES["graph"].rules


def test_a_data_graphs_axis_at_its_frames_start():
    """Data far from 0 (years): the schoolbook theme draws the vertical axis at x = 0, the
    figure then grown to it, the curve a speck (the world's population, 1800 to 2020); placed
    at the frame's start as the rule says, the figure keeps its 8 cm."""
    body = (
        "#lq.diagram(width: 8cm, height: 5cm, xlim: (1780, 2040), ylim: (0, 9),{axis}\n"
        "  lq.plot((1800, 1927, 1960, 1999, 2022), (1, 2, 3, 6, 8), mark: none))"
    )
    width = lambda body: drawn_size("graph", body)[0] / 28.35  # noqa: E731  (cm)
    assert width(body.format(axis="")) > 30  # the axis at year 0
    assert "yaxis: (position: 1780)" in figures_typst.FAMILIES["graph"].rules
    assert width(body.format(axis=" yaxis: (position: 1780),")) < 10


def _dashes(svg: str) -> list[tuple[float, float, float, float]]:
    """A Typst SVG's dashed lines, (x, y) of their start and their end, in their frame's own
    coordinates (an asymptote's pieces are drawn in the frame)."""
    lines = []
    for tag in re.findall(r"<path [^>]*stroke-dasharray[^>]*>", svg):
        moved = re.search(r"translate\(([-\d.]+)(?: ([-\d.]+))?\)", tag)
        x, y = float(moved[1]), float(moved[2] or 0)
        way, length = re.search(r'd="M 0 0([hv]) ([-\d.]+)"', tag).groups()
        dx, dy = (float(length), 0.0) if way == "h" else (0.0, float(length))
        lines.append((x, y, x + dx, y + dy))
    return sorted(lines)


def test_an_asymptote_across_the_frame_broken_at_the_axis_numbers():
    """The limit y = 3 drawn by the AI with `lq.line` from the frame's edge ran into the y
    axis's number 3, read "−3". `asymptote(y: 3)` spans the whole frame, both sides of the
    axis, broken only over the number's column and the axis (computed from the size, the
    limits and the number's width), resumed past it; the same for x = 2 and the x axis."""
    frame = "#lq.diagram(width: 8cm, height: 5cm, xlim: (-3, 5), ylim: (-2, 3.5), {})"
    width, height = 8 / 2.54 * 72, 5 / 2.54 * 72  # pt
    axis_x, axis_y = 3 / 8 * width, 3.5 / 5.5 * height
    left, right = _dashes(figures_typst.compile_svg("graph", frame.format("asymptote(y: 3, label: none)")))
    assert left[0] == pytest.approx(0) and right[2] == pytest.approx(width)
    assert left[2] < axis_x - 9  # pt: the ticks' pad and the number's width before it
    assert axis_x < right[0] < axis_x + 6
    vertical = _dashes(figures_typst.compile_svg("graph", frame.format("asymptote(x: 2, label: none)")))
    top, bottom = sorted(vertical, key=lambda d: d[1])
    assert top[1] == pytest.approx(0) and bottom[3] == pytest.approx(height)
    assert axis_y - 6 < top[3] < axis_y
    assert bottom[1] > axis_y + 12  # pt: the ticks' pad and the number's height below it
    # the frame starting just before the axis: no stub of a dash left before the number (it
    # would read as a minus sign)
    for start in (-0.45, -0.5, -0.55, -0.6, -0.65):
        near = (
            f"#lq.diagram(width: 8cm, height: 5cm, xlim: ({start}, 6.8), ylim: (-0.3, 3.5),"
            " yaxis: (tick-distance: 1), asymptote(y: 3, label: none))"
        )
        pieces = _dashes(figures_typst.compile_svg("graph", near))
        assert all(end - begin > 8 for begin, _, end, _ in pieces), (start, pieces)  # pt
    # on an axis (y = 0 at −∞): the axis itself, no dashes blurring it
    assert _dashes(figures_typst.compile_svg("graph", frame.format("asymptote(y: 0, label: none)"))) == []
    # away from the numbers, a line drawn whole
    assert len(_dashes(figures_typst.compile_svg("graph", frame.format("asymptote(y: 2.5, label: none)")))) == 1
    assert "asymptote(" in figures_typst.FAMILIES["graph"].rules


def test_an_asymptote_named_by_its_equation_where_no_curve_is():
    """The line's name was written 1 time in 3: written by default ("y = 1,5", the figure's
    decimal separator), at its end on the side the curve leaves free."""
    body = (
        '#set text(lang: "fr")\n#let xs = lq.linspace(0.2, 4, num: 100)\n'
        "#lq.diagram(width: 8cm, height: 7cm, xlim: (-4, 4), ylim: (-2, 5),"
        " lq.plot(xs, xs.map(x => 1 / x + 1.5), mark: none), asymptote(y: 1.5{}))"
    )
    svg = lambda label: figures_typst.compile_svg("graph", body.format(label))  # noqa: E731
    named, bare = svg(""), svg(", label: none")
    assert named != bare
    assert named == svg(', label: $y = #"1,5"$')

    # its name at the right end, below the line where the curve comes from above, above it
    # where the curve comes from below
    def name(curve: str, label: str) -> set[tuple[float, float]]:
        drawn = lambda more: figures_typst.compile_svg("graph", body.replace("1 / x + 1.5", curve).format(more))  # noqa: E731
        return set(_glyphs(drawn(label))) - set(_glyphs(drawn(", label: none")))

    under, over = name("1 / x + 1.5", ""), name("1.5 - 1 / x", "")
    assert under and over and all(x > 150 for x, _ in under | over)  # pt: the right end
    assert min(y for _, y in under) > max(y for _, y in over) + 10  # pt: either side of the line


def test_a_curves_name_set_along_it_clear_of_what_is_drawn():
    """The names of the curves and lines (𝒞f, y = x, y = 0,5x + 2) were placed by the AI's eye
    with `lq.place`: on the other line, on each other. `named(…)` sets the name along its own
    curve, computed, clear of the other curves and of the segments drawn (`lq.line`, the
    cobweb's dotted steps)."""
    frame = (
        "#lq.diagram(width: 6cm, height: 6cm, xlim: (-3, 3), ylim: (-3, 3), {},"
        " lq.place(-2.5, -2.5, [O]), lq.place(2.5, 2.5, [O]))"
    )

    def name(body: str) -> tuple[float, float]:
        """Where "A" is drawn, in the data: from two "O" placed at (−2.5, −2.5) and (2.5, 2.5)."""
        glyphs = _glyphs(figures_typst.compile_svg("graph", frame.format(body)))
        bare = _glyphs(figures_typst.compile_svg("graph", frame.format(body.replace("[A]", "none"))))
        ((x, y),) = set(glyphs) - set(bare)
        o = _glyphs(figures_typst.compile_svg("graph", frame.format(body.replace("[A]", "none")).replace("[O]", "[]")))
        (low, high) = sorted(set(bare) - set(o))
        (ax, ay), (bx, by) = (low, high) if low[1] > high[1] else (high, low)  # (−2.5, −2.5) lower
        return -2.5 + 5 * (x - ax) / (bx - ax), -2.5 + 5 * (y - ay) / (by - ay)

    line = "named(lq.plot((-3, 3), (-3, 3), mark: none), [A])"
    alone = name(line)
    assert 0.1 < abs(alone[0] - alone[1]) / 2**0.5 < 1.2  # beside y = x, near it
    # another line through that place: the name elsewhere along y = x, clear of it
    cx, cy = alone[0] + 0.2, alone[1] + 0.1
    other = f"lq.plot(({cx - 2}, {cx + 2}), ({cy + 2}, {cy - 2}), mark: none)"
    moved = name(f"{other}, {line}")
    assert abs(moved[0] + moved[1] - cx - cy) / 2**0.5 > 0.5  # units from y = −x + c
    # a segment (`lq.line`, its ends kept by line-kept) through it: the name moved too
    segment = f"lq.line(({cx}, {cy - 1}), ({cx}, {cy + 1}))"
    assert abs(name(f"{segment}, {line}")[0] - cx) > 0.3
    assert "named(" in figures_typst.FAMILIES["graph"].rules
    assert "line-kept(" in figures_typst.source("graph", "#lq.diagram(lq.line((0, 0), (1, 1)))")


def test_a_curve_through_its_points():
    """A curve known by its points (no formula): computed through each of them exactly, falling
    then rising then falling as they do, level at its minimum and maximum, sloping at its ends
    (the AI's own polynomials missed a marked point 1 drawing in 6, came flat into their ends 2
    in 6). Points not (x, y) numbers, or two with one x: refused, saying why."""
    body = """#let f = through(((-3, 2), (-1, -2), (2, 3), (4, 0)))
#for (x, y) in ((-3, 2), (-1, -2), (2, 3), (4, 0)) { assert(calc.abs(f(x) - y) < 1e-9, message: "misses a point") }
#let xs = range(0, 701).map(i => -3 + i / 100)
#let ys = xs.map(f)
#for i in range(700) {
  let (x, dy) = (xs.at(i), ys.at(i + 1) - ys.at(i))
  let rising = x >= -1 and x < 2
  if rising { assert(dy >= -1e-9, message: "not rising") } else { assert(dy <= 1e-9, message: "not falling") }
}
#let slope(x) = (f(x + 1e-4) - f(x - 1e-4)) / 2e-4
#assert(calc.abs(slope(-1)) < 1e-3 and calc.abs(slope(2)) < 1e-3, message: "not level")
#assert((f(-3 + 1e-3) - f(-3)) / 1e-3 < -0.5 and (f(4) - f(4 - 1e-3)) / 1e-3 < -0.5, message: "flat at an end")
#lq.diagram(lq.plot(xs, ys, mark: none))"""
    assert figures_typst.compile_svg("graph", body).startswith("<svg")
    refused = (("((0, 1),)", "two at least"), ("((0, 1), (0, 2))", "the same x"), ('(("a", 1), (2, 3))', "numbers"))
    for bad, said in refused:
        with pytest.raises(figures_typst.Unusable, match=said):
            figures_typst.compile_svg("graph", f"#let f = through({bad})\n#f(1)")


def test_a_curve_by_conditions_and_the_point_it_defines():
    """A curve given by conditions only (f(a) < 0 < f(b), and c where f(c) = 0): the AI's own
    formula reversed the signs 1 drawing in 6 and its c, written by eye, lay off the crossing.
    Through points chosen to hold every condition, the crossing's x computed by `meet-x` (the
    one in the range; none there, or several: refused, saying so), its tick and its dot exactly there.
    The rule's own fragments for it compile together."""
    check = """#{
      let f = through(((-1, -2), (1, 0.5), (3, 2)))
      let c = meet-x(f, x => 0, -1, 3)
      assert(calc.abs(f(c)) < 1e-9 and c > -1 and c < 1, message: repr(c))
      let k = meet-x(x => calc.pow(x, 2), x => 2, 0, 3)
      assert(calc.abs(k - calc.sqrt(2)) < 1e-9, message: repr(k))
      let right = meet-x(x => calc.pow(x, 2) - 1, x => 0, 0, 3)
      assert(calc.abs(right - 1) < 1e-9, message: repr(right))
      [checked]
    }"""
    assert figures_typst.compile_svg("graph", check).startswith("<svg")
    with pytest.raises(figures_typst.Unusable, match="don't meet"):
        figures_typst.compile_svg("graph", "#meet-x(x => x, x => 5, 0, 1)")
    with pytest.raises(figures_typst.Unusable, match="2 times"):
        figures_typst.compile_svg("graph", "#meet-x(x => calc.pow(x, 2) - 1, x => 0, -3, 3)")
    lines = figures_typst.FAMILIES["graph"].rules.splitlines()
    starts = ("- a curve the description gives by conditions", "- a point the curve defines")
    rule = "\n".join(line for line in lines if line.startswith(starts))
    lets = re.findall(r"`(#let [^`]*)`", rule)
    assert len(lets) == 4, lets  # the letters, the curve, the point, two points
    *lets, two = lets
    tick, dot = re.search(r"`(\(c, \$c\$\))`", rule).group(1), re.search(r"`(meet\(f, [^`]*)`", rule).group(1)
    # k: a value the curve reaches, halfway between its ends' (above its minimum)
    lets.insert(2, "#let k = (f(a) + f(b)) / 2")
    body = (
        "\n".join(lets)
        + f"""
#let xs = lq.linspace(a, b, num: 100)
#lq.diagram(xaxis: (ticks: ((a, $a$), {tick}, (b, $b$))), yaxis: (ticks: ((f(a), $f(a)$),)),
  lq.plot(xs, xs.map(f), mark: none), {dot})"""
    )
    assert figures_typst.compile_svg("graph", body).startswith("<svg")
    # two points named (c₁, c₂): a level the curve crosses twice, both marked
    twice = body.replace("#let k = (f(a) + f(b)) / 2", "#let k = 1.5").replace("#let c = ", f"{two}\n#let c = c1 // ")
    assert figures_typst.compile_svg("graph", twice).startswith("<svg")


def test_a_curve_through_two_points_alone_curved():
    """A function given by its two ends only (decreasing from f(a) to f(b)): through two points it
    was a straight segment, read as an affine function (6 drawings in 6). Now a gentle curve,
    through both exactly, falling all the way; straight only when asked (`straight: true`)."""
    body = """#let f = through(((1, 4), (5, 1)))
#assert(calc.abs(f(1) - 4) < 1e-9 and calc.abs(f(5) - 1) < 1e-9, message: "misses an end")
#let xs = range(0, 401).map(i => 1 + i / 100)
#for i in range(400) { assert(f(xs.at(i + 1)) < f(xs.at(i)), message: "not falling") }
#assert(calc.abs(f(3) - 2.5) > 0.3, message: "straight: " + repr(f(3)))
#let g = through(((1, 4), (5, 1)), straight: true)
#assert(calc.abs(g(3) - 2.5) < 1e-9, message: "not straight")
#let h = through(((0, -1), (2, 3)))
#for i in range(200) { assert(h((i + 1) / 100) > h(i / 100), message: "not rising") }
#lq.diagram(lq.plot(xs, xs.map(f), mark: none))"""
    assert figures_typst.compile_svg("graph", body).startswith("<svg")


def test_a_crossing_left_out_of_its_range_refused():
    """A curve of the AI's own crossing the axis three times, one c named: `meet-x` and `meet`
    given a range narrowed to hold one crossing (5 drawings in 6). `meet` checks the whole curve
    drawn and refuses, saying where its crossings are; over the whole curve, or with `some: true`
    (the description asking for those only), it draws. `meet-x` counts as asked (`n`). A curve
    undefined past its plot (ln) and a line drawn wider: checked without failing."""
    wave = """#let f = through(((1, -2), (3, 1.5), (4.5, -0.8), (6, 2.5)))
#let xs = lq.linspace(1, 6, num: 200)
#lq.diagram(lq.plot(xs, xs.map(f), mark: none), meet(f, x => 0, {}))"""
    with pytest.raises(figures_typst.Unusable, match="meet 3 times"):
        figures_typst.compile_svg("graph", wave.format("1.5, 3.5"))
    assert figures_typst.compile_svg("graph", wave.format("1, 6")).startswith("<svg")
    assert figures_typst.compile_svg("graph", wave.format("1.5, 3.5, some: true")).startswith("<svg")
    counted = """#let f = through(((1, -2), (3, 1.5), (4.5, -0.8), (6, 2.5)))
#let xs = meet-x(f, x => 0, 1, 6, n: 3)
#assert(xs.len() == 3 and xs.all(x => calc.abs(f(x)) < 1e-9), message: repr(xs))
#lq.diagram(lq.plot(xs, xs.map(f)))"""
    assert figures_typst.compile_svg("graph", counted).startswith("<svg")
    with pytest.raises(figures_typst.Unusable, match="3 times"):
        figures_typst.compile_svg("graph", counted.replace(", n: 3", ""))
    # `meet` told how many: as many there, else refused
    assert figures_typst.compile_svg("graph", wave.format("1, 6, n: 3")).startswith("<svg")
    with pytest.raises(figures_typst.Unusable, match="not 2"):
        figures_typst.compile_svg("graph", wave.format("1, 6, n: 2"))
    # two meets marking one crossing each: both marked, drawn
    two = """#let xs = lq.linspace(-3, 3, num: 200)
#lq.diagram(lq.plot(xs, xs.map(x => calc.pow(x, 2)), mark: none), lq.plot(xs, xs.map(x => x + 2), mark: none),
  meet(x => calc.pow(x, 2), x => x + 2, -2, 0), meet(x => calc.pow(x, 2), x => x + 2, 1, 3))"""
    assert figures_typst.compile_svg("graph", two).startswith("<svg")
    ln = """#let xs = lq.linspace(0.2, 5, num: 100)
#let ts = lq.linspace(-1, 5, num: 50)
#lq.diagram(lq.plot(xs, xs.map(calc.ln), mark: none), lq.plot(ts, ts.map(x => x / 2), mark: none),
  meet(calc.ln, x => x / 2, 0.5, 3))"""
    assert figures_typst.compile_svg("graph", ln).startswith("<svg")


def test_a_single_tick_without_its_trailing_comma():
    """One value named on an axis, `ticks: ((4, $M$))`: Typst reads the pair itself, not a list
    of one pair, and lilaq refused it (a maximum M named alone, Typst refusing it twice, the
    figure drawn as SVG instead): taken as the one tick it means, drawn as with the comma."""
    body = "#lq.diagram(xlim: (0, 5), ylim: (0, 5), yaxis: (ticks: {}), lq.plot((0, 5), (1, 4)))"
    alone = figures_typst.compile_svg("graph", body.format("((4, $M$))"))
    assert alone == figures_typst.compile_svg("graph", body.format("((4, $M$),)"))


@pytest.mark.parametrize(
    ("big", "kept"), [("6cm, height: 12cm", "4.5cm, height: 9cm"), ("12cm, height: 3cm", "9cm, height: 2.25cm")]
)
def test_a_frame_too_large_for_a_card_shrunk_whole(big, kept):
    """A frame taller or wider than 9 cm (x² up to 9 against x from −3 to 3, orthonormal: 7 by
    13 cm) drawn smaller, both sides by the same factor (still orthonormal), its text kept:
    a card shows a figure at most 320 px wide and half the screen tall."""
    body = """#let xs = lq.linspace(-3, 3)
#lq.diagram(width: {}, xlim: (-3.5, 3.5), ylim: (-1, 10), lq.plot(xs, xs.map(x => x * x), mark: none))"""
    assert figures_typst.compile_svg("graph", body.format(big)) == figures_typst.compile_svg("graph", body.format(kept))
