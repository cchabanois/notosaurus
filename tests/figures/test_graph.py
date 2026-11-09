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
    fragments = re.findall(r"`((?:xaxis: |lq\.scatter|lq\.line|lq\.place)[^`]*)`", rules)
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
