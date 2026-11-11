"""The circuit (zap), mechanics (our mechanics function) and chemistry (alchemist)
families."""

import io
import re

import pytest

from notosaurus_core import figures, figures_typst


def test_the_circuit_rules_current_arrow_compiles():
    """The current's arrow the circuit rule shows (said by where the current goes, whatever way
    a component was drawn: the AI's own, from components' `i:`, went up a branch 2 times in 3),
    in the rule's example."""
    rules = figures_typst.FAMILIES["circuit"].rules
    (arrow,) = re.findall(r"`(current-arrow\([^`]*\))`", rules)
    example = re.search(r"exactly so:\n(.*?)\n- ", rules, re.S).group(1)
    body = example.replace("\n})", f"\n  {arrow}\n}})")
    assert arrow in body and figures.clean(figures_typst.compile_svg("circuit", body)).startswith("<svg")


def test_a_closed_switch_is_seen():
    """zap's closed switch is a mere wire: ours keeps its two contacts, closed or open."""
    circuit = '#circuit({{ battery("g", (0, 0), (0, 3)); {} lamp("l", (3, 3), (3, 0)); wire((3, 0), (0, 0)) }})'
    wired = figures_typst.compile_svg("circuit", circuit.format("wire((0, 3), (3, 3));"))
    closed = figures_typst.compile_svg("circuit", circuit.format('switch("k", (0, 3), (3, 3), closed: true);'))
    opened = figures_typst.compile_svg("circuit", circuit.format('switch("k", (0, 3), (3, 3));'))
    assert closed != wired and closed != opened


def test_a_current_arrow_between_two_wires_closes_the_circuit():
    """The AI writes the arrow as one more stretch of wire (a wire, the arrow, a wire): drawn
    with its wire, the circuit as closed as when the arrow is put on a wire."""
    circuit = (
        '#circuit({{ battery("g", (0, 0), (0, 3)); wire((0, 3), (1, 3)); {} wire((2, 3), (3, 3)); '
        'lamp("l", (3, 3), (3, 0)); wire((3, 0), (0, 0)) }})'
    )

    from PIL import Image

    def dark(body: str) -> int:
        png = figures.to_png(figures.clean(figures_typst.compile_svg("circuit", body)))
        return sum(Image.open(io.BytesIO(png)).convert("L").histogram()[:128])

    alone = dark(circuit.format("current-arrow((1, 3), (2, 3), $I$);"))
    on_a_wire = dark(circuit.format("wire((1, 3), (2, 3)); current-arrow((1, 3), (2, 3), $I$);"))
    assert alone == on_a_wire


def test_the_circuit_rules_house_installation_compiles():
    """A house installation drawn by hand (a breaker as dots on the wires, a socket a circle,
    a square or cetz's shapes, its earth wired to the neutral 3 times in 4): the rule's
    breaker, socket and earth wire, as it gives them, compile together with a fuse."""
    rules = figures_typst.FAMILIES["circuit"].rules
    calls = [re.search(rf"`({name}\([^`]*\))`", rules) for name in ("breaker", "socket", "earth-wire")]
    assert all(calls), "the circuit rule shows a house installation's parts"
    body = (
        "#circuit({ wire((0, 3), (1, 3)); wire((0, 0), (1, 0)); "
        + "; ".join(c.group(1) for c in calls if c)
        + '; wire((2.5, 3), (7, 3)); wire((2.5, 0), (7, 0)); fuse("f", (7, 3), (7, 2)) })'
    )
    assert figures.clean(figures_typst.compile_svg("circuit", body)).startswith("<svg")


def test_a_sockets_three_terminals_are_apart():
    """The earth was joined to the neutral at the socket (3 drawings in 4): the socket's phase,
    neutral and earth are three terminals of its own, apart from one another (Typst's assert
    stops the compiling otherwise)."""
    body = """#circuit({
  socket("p", (0, 2), (0, 0))
  cetz.draw.get-ctx(ctx => {
    let (_, a, b, c) = cetz.coordinate.resolve(ctx, "p.phase", "p.neutre", "p.terre")
    for (u, v) in ((a, b), (a, c), (b, c)) { assert(cetz.vector.dist(u, v) > 0.3) }
    // the phase and the neutral where the branch's wires end, above and below
    assert(a.at(1) > c.at(1) and c.at(1) > b.at(1) and c.at(0) > a.at(0))
  })
})"""
    assert figures_typst.compile_svg("circuit", body).startswith("<svg")


def test_an_earth_wire_is_green_and_yellow():
    """Drawn plain green 3 times in 4: the earth wire is striped green and yellow, both seen."""
    from PIL import Image

    def colours(body: str) -> set[str]:
        png = figures.to_png(figures.clean(figures_typst.compile_svg("circuit", body)))
        seen = set()
        for _, (r, g, b) in Image.open(io.BytesIO(png)).convert("RGB").getcolors(1 << 24) or []:
            if g > 120 and b < 90 and r < 90:
                seen.add("green")
            if r > 200 and g > 170 and b < 90:
                seen.add("yellow")
        return seen

    assert colours('#circuit({ socket("p", (0, 2), (0, 0)); earth-wire("p.terre", (1, 1)) })') == {"green", "yellow"}
    assert not colours("#circuit({ wire((0, 1), (1, 1)) })")


def test_a_branch_spaces_its_components_evenly():
    """Every component and wire placed by the AI's eye: an ammeter drawn over a resistor of its
    branch (4 drawings in 6). A branch's components spaced evenly along it, wire between each
    two, none on another, even when the branch is too short for them (drawn smaller then)."""
    body = """#let parts = (lamp("a"), resistor("b"), ammeter("c"))
#for length in (6, 3) {
  let spans = branch-layout(length, parts).parts
  let ends = (0,) + spans.flatten() + (length,)
  let gaps = range(0, ends.len(), step: 2).map(i => ends.at(i + 1) - ends.at(i))
  assert(spans.all(((s, e)) => e > s))
  assert(gaps.all(g => g >= 0.4 - 1e-9), message: repr(gaps))
  assert(gaps.all(g => calc.abs(g - gaps.first()) < 1e-9), message: repr(gaps))
}
#circuit({ branch((0, 0), (6, 0), ..parts) })"""
    assert figures_typst.compile_svg("circuit", body).startswith("<svg")


def test_a_branch_is_wired_end_to_end():
    """A branch's top wire missing, a wire dangling (the circuit open): a branch drawn by the
    preamble is wire from end to end, broken only inside its components (a resistor's
    rectangle, white within: one white stretch each along the wire)."""
    from PIL import Image

    body = '#circuit({ branch((0, 0), (8, 0), resistor("a"), resistor("b"), resistor("c")) })'
    png = figures.to_png(figures.clean(figures_typst.compile_svg("circuit", body)))
    image = Image.open(io.BytesIO(png)).convert("L")
    width, height = image.size
    pixels = image.load()
    assert pixels is not None
    # the wire's row: where its first end is
    row = next(y for x in range(width) for y in range(height) if pixels[x, y] < 128)
    line = "".join("#" if pixels[x, row] < 128 else "." for x in range(width)).strip(".")
    assert line.startswith("#") and len(re.findall(r"\.+", line)) == 3, line


def test_a_branchs_current_arrow_is_on_its_wire_leaving_the_generator():
    """The current's arrow drawn too far from its branch to be joined to it (2 in 6), on a
    switch (1 in 6): a branch's current goes on a stretch of its own wire, after the generator
    (the current leaving its +), else on the first, pointing to the branch's second end."""
    body = """#for (parts, after) in (((lamp("l"), battery("g"), ammeter("a")), 1), ((lamp("l"), ammeter("a")), none)) {
  let layout = branch-layout(6, parts, current: true)
  let (s, e) = layout.arrow
  assert(e > s)
  // on wire: in no component's span
  assert(layout.parts.all(((a, b)) => e <= a or b <= s), message: repr(layout))
  // after the generator, before what follows it; else before the first component
  let before = if after == none { 0 } else { layout.parts.at(after).at(1) }
  let next = if after == none { 0 } else { after + 1 }
  assert(before <= s and e <= layout.parts.at(next).at(0), message: repr(layout))
}
#circuit({ branch((0, 0), (0, 4), battery("g"), ammeter("a"), current: $I$) })"""
    assert figures_typst.compile_svg("circuit", body).startswith("<svg")


def test_a_branchs_names_and_its_currents_are_on_opposite_sides():
    """I₁ written on K₁: a branch's components' names on one side of it, its current's name on
    the other, whichever way it goes."""
    from PIL import Image

    def sides(start: str, end: str) -> tuple[float, float, float, float]:
        body = (
            f'#circuit({{ branch({start}, {end}, lamp("l", label: text(fill: rgb("#ff0000"))[L]), '
            'resistor("r", label: text(fill: rgb("#ff0000"))[R]), current: text(fill: rgb("#0000ff"))[I]) })'
        )
        png = figures.to_png(figures.clean(figures_typst.compile_svg("circuit", body)))
        image = Image.open(io.BytesIO(png)).convert("RGB")
        red, blue = [], []
        for y in range(image.height):
            for x in range(image.width):
                r, g, b = image.getpixel((x, y))  # type: ignore[misc]
                if r > 180 and g < 90 and b < 90:
                    red.append((x, y))
                if b > 180 and r < 90 and g < 90:
                    blue.append((x, y))
        assert red and blue
        mean = lambda points, i: sum(p[i] for p in points) / len(points)  # noqa: E731
        return mean(red, 0), mean(red, 1), mean(blue, 0), mean(blue, 1)

    rx, _, bx, _ = sides("(0, 4)", "(0, 0)")  # down: the names on the right, the current's on the left
    assert rx > bx
    rx, _, bx, _ = sides("(0, 0)", "(0, 4)")
    assert rx < bx
    _, ry, _, by = sides("(0, 0)", "(5, 0)")  # rightwards: the names above
    assert ry < by


def test_the_circuit_rules_branch_compiles():
    """The branch the circuit rule shows, between two rails, compiles."""
    rules = figures_typst.FAMILIES["circuit"].rules
    (call,) = re.findall(r"`(branch\([^`]*\))`", rules)
    body = f"#circuit({{ wire((0, 4), (3, 4)); wire((0, 0), (3, 0)); {call} }})"
    assert figures.clean(figures_typst.compile_svg("circuit", body)).startswith("<svg")


def test_the_chemistry_rule_says_how_to_draw_a_lewis_structures_pairs():
    """Without it the AI drew a Lewis structure's non-bonding pairs as bonds to no atom, or
    left them out (0 of 12 right): the rule's Lewis call, as it gives it, draws them."""
    rule = figures_typst.FAMILIES["chemistry"].rules
    calls = re.findall(r"`(fragment\([^`]*lewis-line[^`]*)`", rule)
    assert calls, "the chemistry rule shows a Lewis structure's pairs"
    for call in calls:
        assert figures_typst.compile_svg("chemistry", "#skeletize({ " + call + " })").startswith("<svg")


def test_a_bodys_vectors_point_where_their_support_says():
    """A vector given by its direction, computed from the support: on a circle "along" is the
    tangent the body turns along and "centre" towards the centre, on a slope "normal" is
    out of it, on the ground "back" against the motion; never an angle of the AI's."""
    drawn = lambda body: figures_typst.compile_svg("mechanics", f"#mechanics({body})")  # noqa: E731
    circle = 'support: "circle", at: 0, vectors: (("v", {}),)'
    assert drawn(circle.format('"along"')) == drawn(circle.format("90"))
    assert drawn(circle.format('"centre"')) == drawn(circle.format("180"))
    assert drawn("clockwise: true, " + circle.format('"along"')) == drawn(circle.format("270"))
    slope = 'support: "slope", angle: 30, vectors: (("R", {}),)'
    assert drawn(slope.format('"normal"')) == drawn(slope.format("120"))
    assert drawn(slope.format('"downhill"')) == drawn(slope.format("210"))
    plane = 'support: "plane", vectors: (("f", {}),)'
    pendulum = 'support: "pendulum", angle: 30, vectors: (("T", {}),)'  # its string at 300°
    assert drawn(pendulum.format('"centre"')) == drawn(pendulum.format("120"))
    assert drawn(plane.format('"back"')) == drawn(plane.format("180"))
    for wrong, said in (('vectors: (("F", "centre"),)', "circle's"), ('vectors: (("F", "sideways"),)', "direction")):
        with pytest.raises(figures_typst.Unusable, match=said):
            drawn(wrong)


def test_a_bodys_hidden_vector_name_is_not_shown():
    """A card asking which force: its name written "?", whatever it was."""
    body = '#mechanics(hidden: ("{0}",), vectors: (("P", "down"), ("{0}", "up")))'
    asked = figures_typst.compile_svg("mechanics", body.format("R"))
    assert asked == figures_typst.compile_svg("mechanics", body.format("T"))
    assert asked != figures_typst.compile_svg("mechanics", body.format("R").replace('hidden: ("R",), ', ""))


def test_a_body_on_a_slope_rests_on_it():
    """The block's underside on the slope's line, never sunk into it: the body's foot (its
    point less its half height, across the slope) on the line from the slope's foot."""
    for angle in (20, 30, 45):
        figures_typst.compile_svg(
            "mechanics",
            f"""#let (fx, fy) = slope-foot({angle})
#let (px, py) = on-slope({angle}, 0.45)
#let (bx, by) = (px + 0.45 * calc.sin({angle} * 1deg), py - 0.45 * calc.cos({angle} * 1deg))
#assert(calc.abs((bx - fx) * calc.sin({angle} * 1deg) - (by - fy) * calc.cos({angle} * 1deg)) < 1e-9)
#mechanics(support: "slope", angle: {angle})""",
        )


def test_a_bodys_scene_is_drawn_from_its_values():
    """Two bodies acting on each other, a vector's index and Greek letter as the AI writes
    them, an angle's value: computed by the function, never written by the AI."""
    drawn = lambda body: figures_typst.compile_svg("mechanics", f"#mechanics({body})")  # noqa: E731
    pair = 'body: [Terre], other: [Lune], vectors: (("F", "towards"),), others: (("G", {}),)'
    assert drawn(pair.format('"towards"')) == drawn(pair.format("180"))
    assert drawn(pair.format('"away"')) == drawn(pair.format("0"))
    named = 'vectors: (("{}", "up"),)'
    assert drawn(named.format("F_(T/L)")) == drawn(named.format(r"F_(text(T)\\/L)"))
    assert drawn(named.format("F_(T/L)")) == drawn(named.format("F_(T slash L)"))
    assert drawn(named.format("Pi")) == drawn(named.format("Π"))
    pulled = 'support: "plane", vectors: (("F", 30),), marked: {}'
    assert drawn(pulled.format('("F",)')) == drawn(pulled.format("(F: [30°])"))
    assert drawn(pulled.format('("F",)')) != drawn(pulled.format("()"))
    for wrong, said in (
        ('support: "slope", other: [B], vectors: (("F", "towards"),)', "stand alone"),
        ('vectors: (("F", "towards"),)', "other body"),
        ('support: "slope", path: ([A], [B]), vectors: ()', "plane"),
    ):
        with pytest.raises(figures_typst.Unusable, match=said):
            drawn(wrong)


def test_vectors_going_the_same_way_are_side_by_side():
    """Archimedes' thrust and the string's pull both up: two arrows, never one over the
    other (and the string between them)."""
    drawn = lambda body: figures_typst.compile_svg("mechanics", f"#mechanics({body})")  # noqa: E731
    both = drawn('vectors: (("F", "up"), ("G", "up"))')
    assert both != drawn('vectors: (("F", "up"), ("G", 90.5))')
    hung = 'support: "liquid", string: true, vectors: (("F", "up"), ("Pi", "up"))'
    assert drawn(hung).startswith("<svg")


def test_a_chronophotographys_positions_are_computed_from_its_motion():
    """A ball thrown drawn in SVG: its points set apart from the curve drawn through them (a
    Bézier whose top isn't the points', 0 of 3), a fall's first positions on one another.
    Computed: a throw's positions equally spaced across, rising less and less then falling
    more and more, symmetric; a fall's gaps growing; a circle's on it, equally spaced."""
    check = """#let (times, k, pts) = chrono-places("thrown", 7)
#let dx = range(6).map(i => pts.at(i + 1).at(0) - pts.at(i).at(0))
#assert(dx.all(d => calc.abs(d - dx.first()) < 1e-9))
#let dy = range(6).map(i => pts.at(i + 1).at(1) - pts.at(i).at(1))
#assert(range(5).all(i => dy.at(i + 1) < dy.at(i)))
#assert(calc.abs(pts.first().at(1) - pts.last().at(1)) < 1e-9 and calc.abs(dy.at(2) + dy.at(3)) < 1e-9)
#let (times, k, fall) = chrono-places("falling", 6)
#let gaps = range(5).map(i => fall.at(i).at(1) - fall.at(i + 1).at(1))
#assert(range(4).all(i => gaps.at(i + 1) > gaps.at(i)) and gaps.first() > 0.16)
#let (times, k, round) = chrono-places("circle", 8)
#assert(round.all(p => calc.abs(calc.sqrt(p.at(0) * p.at(0) + p.at(1) * p.at(1)) - k) < 1e-9))
#chronophotography(n: 7, names: "M", velocity: (2, 4), change: (3,))"""
    assert figures_typst.compile_svg("mechanics", check).startswith("<svg")


def test_a_chronophotographys_change_of_velocity_is_computed():
    """Δv between the positions around it: down for a throw, wherever it is drawn; never at
    the first or the last position, nor at a position that isn't."""
    drawn = lambda body: figures_typst.compile_svg("mechanics", f"#chronophotography({body})")  # noqa: E731
    assert drawn('names: "M", change: (3,)') != drawn('names: "M"')
    for wrong, said in (
        ("change: (0,)", "never at the first"),
        ("velocity: (9,)", "positions' numbers"),
        ('motion: "orbit"', "motion is one of"),
    ):
        with pytest.raises(figures_typst.Unusable, match=said):
            drawn(wrong)


def test_an_accelerated_chronophotographys_first_positions_stand_apart():
    """Two motions compared: the accelerated one's first two positions drawn on one another
    (from rest, a gap a sixth of the others'). Already moving: its gaps growing, the first
    wider than a position."""
    check = """#let (times, k, pts) = chrono-places("accelerated", 7)
#let gaps = range(6).map(i => pts.at(i + 1).at(0) - pts.at(i).at(0))
#assert(range(5).all(i => gaps.at(i + 1) > gaps.at(i)) and gaps.first() > 0.5)
#chronophotography(motion: "accelerated")"""
    assert figures_typst.compile_svg("mechanics", check).startswith("<svg")
