"""The circuit (zap), mechanics (our mechanics function) and chemistry (alchemist)
families."""

import io
import json
import math
import re
from itertools import pairwise

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
    let (_, a, b, c) = cetz.coordinate.resolve(ctx, "p.phase", "p.neutral", "p.earth")
    for (u, v) in ((a, b), (a, c), (b, c)) { assert(cetz.vector.dist(u, v) > 0.3) }
    // the phase and the neutral where the branch's wires end, above and below
    assert(a.at(1) > c.at(1) and c.at(1) > b.at(1) and c.at(0) > a.at(0))
  })
})"""
    assert figures_typst.compile_svg("circuit", body).startswith("<svg")


def test_a_sockets_terminals_have_english_names_and_keep_their_old_ones():
    """The socket's terminals were named in French ("neutre", "terre"): named "neutral" and
    "earth" now, the old names (an AI or a rule cached before) still the same points."""
    rules = figures_typst.FAMILIES["circuit"].rules
    assert '"p.earth"' in rules and "terre" not in rules
    body = """#circuit({
  socket("p", (0, 2), (0, 0))
  cetz.draw.get-ctx(ctx => {
    let (_, n, e, old-n, old-e) = cetz.coordinate.resolve(ctx, "p.neutral", "p.earth", "p.neutre", "p.terre")
    assert(n == old-n and e == old-e)
  })
})"""
    assert figures_typst.compile_svg("circuit", body).startswith("<svg")
    for terminal in ("earth", "terre"):
        drawn = f'#circuit({{ socket("p", (0, 2), (0, 0)); earth-wire("p.{terminal}", (1, 1)) }})'
        assert figures_typst.compile_svg("circuit", drawn).startswith("<svg")


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

    assert colours('#circuit({ socket("p", (0, 2), (0, 0)); earth-wire("p.earth", (1, 1)) })') == {"green", "yellow"}
    assert not colours("#circuit({ wire((0, 1), (1, 1)) })")


def _dark_pixels(body: str) -> tuple[set[tuple[int, int]], int, int]:
    """A circuit's PNG: its black pixels, its width and height."""
    from PIL import Image

    image = Image.open(io.BytesIO(figures.to_png(figures.clean(figures_typst.compile_svg("circuit", body)))))
    image = image.convert("RGB")
    dark = {(x, y) for y in range(image.height) for x in range(image.width) if sum(image.getpixel((x, y))) < 150}
    return dark, image.width, image.height


def test_a_two_pole_breaker_opens_both_lines_together():
    """The general circuit breaker cuts the phase and the neutral at once (drawn as dots on a
    wire, by hand): a pole on each line, the phase's row and the neutral's drawn across, and
    their blades joined by a dashed line, a column of dashes between the two rows."""
    dark, width, height = _dark_pixels('#circuit({ breaker("d", (0, 3), (2, 3), (0, 0), (2, 0)) })')
    for row in ({x for x, y in dark if y < height / 4}, {x for x, y in dark if y > 3 * height / 4}):
        assert row and max(row) - min(row) > width * 3 / 4, "a pole across each line"
    between = {(x, y) for x, y in dark if height / 4 < y < 3 * height / 4}
    assert between, "the dashed link"
    rows = sorted({y for _, y in between})
    dashes = 1 + sum(1 for a, b in pairwise(rows) if b > a + 1)
    assert dashes >= 3


def test_an_earth_wires_end_is_earthed():
    """The earth wire ends on zap's earth symbol (black, below its last point), the wire
    itself green and yellow: without it, nothing black."""
    dark, width, _ = _dark_pixels("#circuit({ earth-wire((0, 0), (2, 0)) })")
    assert dark and min(x for x, _ in dark) > width / 2


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
    calls = re.findall(r"`(fragment\([^`]*lewis:[^`]*\))`", rule)
    assert calls, "the chemistry rule shows a Lewis structure's pairs"
    for call in calls:
        assert figures_typst.compile_svg("chemistry", "#skeletize({ " + call + " })").startswith("<svg")


FACED = "(lewis-line(angle: 150deg), lewis-line(angle: 210deg))"  # the H-bond from the left


# dotted, or dashed: an interaction either way
@pytest.mark.parametrize("arrives", ['single(stroke: (dash: "dotted"))', 'single(stroke: (dash: "dashed"))'])
def test_a_lewis_structures_pairs_face_a_hydrogen_bond(arrives):
    """A hydrogen bond (a dotted link) to the second water's O, its bonds up and down-right:
    #592 counted the dots as a bond and turned both pairs away from the H (1 drawing in 3).
    An interaction is no bond: the pairs face it, the H arriving between them."""
    body = (
        '#skeletize({ fragment("H"); single(angle: 1); fragment("O", lewis: pairs(2)); single(angle: -1); '
        'fragment("H"); ARRIVES; fragment("O", lewis: LEWIS); branch({ single(angle: 2); fragment("H") }); '
        'single(angle: -1); fragment("H") })'
    ).replace("ARRIVES", arrives)
    drawn = lambda lewis: figures_typst.compile_svg("chemistry", body.replace("LEWIS", lewis))  # noqa: E731
    assert drawn("pairs(2)") == drawn(FACED)


@pytest.mark.parametrize("down", [True, False])
def test_a_lewis_structures_pairs_set_where_its_bonds_leave_room(down):
    """Water's O at the bottom, its bonds going up at 45° and 135°: the AI set its two pairs at
    45° and 135°, on the bonds (the rule's example's angles, copied, 2 times in 3). Their
    directions computed from the atom's bonds: `pairs(2)` draws them in the widest gaps, as
    written by hand there (down-left, down-right; up, the molecule turned), and a pair written
    on a bond is moved there too."""
    to_o = -1 if down else 1  # the bond from the first H to O: down to an O at the bottom
    water = f'#skeletize({{ fragment("H"); single(angle: {to_o}); fragment("O", lewis: LEWIS); '
    water += f'single(angle: {-to_o}); fragment("H") }})'
    drawn = lambda lewis: figures_typst.compile_svg("chemistry", water.replace("LEWIS", lewis))  # noqa: E731
    free = (
        "(lewis-line(angle: 225deg), lewis-line(angle: 315deg))"
        if down
        else "(lewis-line(angle: 45deg), lewis-line(angle: 135deg))"
    )
    on_bonds = (
        "(lewis-line(angle: 45deg), lewis-line(angle: 135deg))"
        if down
        else "(lewis-line(angle: 225deg), lewis-line(angle: 315deg))"
    )
    assert drawn("pairs(2)") == drawn(free)
    assert drawn(on_bonds) == drawn(free)


def test_a_lewis_structures_pair_set_by_its_branches_bonds():
    """NH3, its N's three bonds two branches (down-right, down-left) and a bond on (left):
    `pairs(1)` sets its pair in the widest gap they leave, halfway (67.5°: from 315° round to
    180°), as written there by hand; not straight up, as if the branches weren't seen."""
    nh3 = (
        '#skeletize({ fragment("N", lewis: LEWIS); branch({ single(angle: -1); fragment("H") }); '
        'branch({ single(angle: -3); fragment("H") }); single(angle: 4); fragment("H") })'
    )
    drawn = lambda lewis: figures_typst.compile_svg("chemistry", nh3.replace("LEWIS", lewis))  # noqa: E731
    assert drawn("pairs(1)") == drawn("(lewis-line(angle: 67.5deg),)")


def test_a_lewis_structures_ring_atoms_pairs_kept_as_written():
    """An atom in a ring: its bonds' angles are the ring's, which the preamble doesn't reckon;
    its pairs kept where they are written, as alchemist alone draws them."""
    ring = (
        '#SKELETIZE({ fragment("C"); cycle(5, { single(); '
        'fragment("O", lewis: (lewis-line(angle: 0deg), lewis-line(angle: 180deg))); single(); single(); single() }) })'
    )
    drawn = lambda skeletize: figures_typst.compile_svg("chemistry", ring.replace("SKELETIZE", skeletize))  # noqa: E731
    assert drawn("skeletize") == drawn("_alchemist.skeletize")


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


def _mechanics_image(body: str):
    """A mechanics scene drawn in grey levels, and how many of its pixels make a centimetre."""
    from PIL import Image

    svg = figures.clean(figures_typst.compile_svg("mechanics", f"#mechanics({body})"))
    image = Image.open(io.BytesIO(figures.to_png(svg))).convert("L")
    width = float(re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+)', svg).group(1))  # in pt
    return image, image.width / width * 72 / 2.54


@pytest.mark.parametrize("angle", [20, 30, 45])
def test_a_body_drawn_on_a_slope_rests_on_its_line(angle):
    """The drawing itself: the block's underside on the slope's line, never sunk into it nor
    above it. The slope's line read right of the block, carried under it: the block's lowest
    pixels in each column on it, within a stroke."""
    image, _ = _mechanics_image(f'support: "slope", angle: {angle}')
    px, (w, h) = image.load(), image.size
    block = [(x, y) for x in range(w) for y in range(h) if abs(px[x, y] - 215) <= 2]  # its grey fill
    right = max(x for x in range(w) if any(px[x, y] < 128 for y in range(h)))  # the slope's top
    x1, x2 = (max(x for x, _ in block) + right) // 2, right - 8
    y1, y2 = (next(y for y in range(h) if px[x, y] < 250) for x in (x1, x2))  # the slope's line there
    lowest: dict[int, int] = {}
    for x, y in block:
        lowest[x] = max(lowest.get(x, 0), y)
    gaps = [y1 + (y2 - y1) * (x - x1) / (x2 - x1) - y for x, y in lowest.items()]
    assert -3 < min(gaps) < 4, min(gaps)  # its corner on the line, its underside along it


def _uprights(body: str) -> list[tuple[float, float]]:
    """A mechanics scene's upright strokes longer than 0.5 cm (its vertical arrows): each one's
    place across and its length, in cm."""
    image, per_cm = _mechanics_image(body)
    px = image.load()
    columns = []
    for x in range(image.width):
        best = run = 0
        for y in range(image.height):
            run = run + 1 if px[x, y] < 128 else 0
            best = max(best, run)
        if best > 0.5 * per_cm:
            columns.append((x, best))
    strokes: list[list[tuple[int, int]]] = []
    for x, length in columns:
        if strokes and x - strokes[-1][-1][0] <= 1:
            strokes[-1].append((x, length))
        else:
            strokes.append([(x, length)])
    return [(sum(x for x, _ in s) / len(s) / per_cm, max(n for _, n in s) / per_cm) for s in strokes]


def test_vectors_going_the_same_way_are_drawn_apart():
    """Two vectors up from one point: two arrows, about 0.28 cm apart (on one another, they
    were one arrow)."""
    (a, _), (b, _) = _uprights('vectors: (("F", "up"), ("G", "up"))')
    assert 0.2 < b - a < 0.4, (a, b)
    assert len(_uprights('vectors: (("F", "up"),)')) == 1


def test_a_vectors_length_drawn_from_its_scale():
    """`scale: (2, "N")`, 1 cm for 2 N: a vector of 4 N drawn 2 cm long, of 2 N 1 cm; without a
    scale, its third value a factor of the 1.5 cm a vector is."""
    for body, cm in (
        ('scale: (2, "N"), vectors: (("F", "up", 4),)', 2),
        ('scale: (2, "N"), vectors: (("F", "up", 2),)', 1),
        ('vectors: (("F", "up", 2),)', 3),
    ):
        ((_, length),) = _uprights(body)
        assert abs(length - cm) < 0.15, (body, length)


def test_a_bodys_shape_drawn_as_given():
    """A ball on the plane drawn as a ball (its lighter grey), not as the block a body on a
    plane is otherwise; a block as a block."""

    def greys(body: str) -> set[int]:
        image, _ = _mechanics_image(f'support: "plane"{body}')
        counts = image.histogram()
        return {v for v in (215, 225) if counts[v] > 1000}  # a block's fill, a ball's

    assert greys("") == greys(', shape: "block"') == {215}
    assert greys(', shape: "ball"') == {225}


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


def _chrono_drawing(body: str) -> dict[str, list]:
    """A chronophotography's SVG: its positions' centres (its black dots, in order), its
    velocities' arrows (blue lines: start x, y, then dx, dy), where its texts are written
    (x, the baseline's y), their groups' moves added."""
    svg = figures_typst.compile_svg("mechanics", f"#chronophotography({body})")
    number = r"(-?[\d.]+(?:e-?\d+)?)"
    stack, drawn = [(0.0, 0.0)], {"dots": [], "arrows": [], "texts": []}
    for tag in re.findall(r"<g(?:\s[^>]*)?>|</g>|<path[^>]*>", svg):
        if tag == "</g>":
            stack.pop()
            continue
        x, y = stack[-1]
        if moved := re.search(rf'transform="translate\({number}(?:[ ,]{number})?\)"', tag):
            x, y = x + float(moved[1]), y + float(moved[2] or 0)
        elif text := re.search(rf'transform="matrix\(1 0 0 -1 {number} {number}\)"', tag):
            x, y = x + float(text[1]), y + float(text[2])
            drawn["texts"].append((x, y))
        if tag.startswith("<g"):
            stack.append((x, y))
            continue
        d = re.search(r' d="M 0 0(?:m ([-\d.]+) ([-\d.]+))?\s*([lhvc]) ?([-\d.]+)(?: ([-\d.]+))?', tag)
        if d is None:
            continue
        a, b = float(d[1] or 0), float(d[2] or 0)
        if 'fill="#000000"' in tag and d[3] == "c" and a > 2:  # a position (a circle's centre: smaller)
            drawn["dots"].append((x + a, y + b + a))  # a circle's path starts at its right end: its radius a
        elif 'fill="none" stroke="#1f5fbf"' in tag:
            u = float(d[4]) if d[3] in "lh" else 0.0
            v = float(d[5]) if d[3] == "l" else float(d[4]) if d[3] == "v" else 0.0
            drawn["arrows"].append((x + a, y + b, u, v))
    return drawn


@pytest.mark.parametrize(
    "body, velocity",
    [
        ('motion: "thrown", n: 7, velocity: (1, 2, 4, 5)', (1, 2, 4, 5)),
        ('motion: "circle", n: 8, velocity: (1, 3, 6)', (1, 3, 6)),
        ('motion: "accelerated", n: 6, velocity: (1, 3, 4)', (1, 3, 4)),
    ],
)
def test_a_chronophotographys_velocities_along_its_trajectory(body, velocity):
    """Each velocity drawn from its position along the trajectory: its arrow's direction
    within 15° of the chord between the positions around it (the tangent's, near enough),
    and shorter than the shortest step (clear of the next position)."""
    drawn = _chrono_drawing(body)
    dots, arrows = drawn["dots"], drawn["arrows"]
    assert len(arrows) == len(velocity)
    step = min(math.dist(dots[i], dots[(i + 1) % len(dots)]) for i in range(len(dots) - 1))
    for i, (x, y, dx, dy) in zip(velocity, arrows, strict=True):
        assert math.dist((x, y), dots[i]) < 1
        before, after = dots[i - 1], dots[(i + 1) % len(dots)]
        chord = math.atan2(after[1] - before[1], after[0] - before[0])
        turn = abs((math.atan2(dy, dx) - chord + math.pi) % (2 * math.pi) - math.pi)
        assert math.degrees(turn) < 15, (i, math.degrees(turn))
        assert 0 < math.hypot(dx, dy) < step


def test_a_chronophotographys_crowded_names_on_alternate_sides():
    """Positions closer than their names are wide (a uniform motion's 12 positions): every
    other name on the other side of the line, the names' baselines alternating below and
    above it; apart (5 positions), all on one side."""

    def drawn(n: int) -> tuple[float, list[float]]:
        found = _chrono_drawing(f'motion: "uniform", n: {n}, numbered: true')
        return found["dots"][0][1], [y for _, y in sorted(found["texts"])]

    line, crowded = drawn(12)
    assert len(crowded) == 12
    assert all((a > line) != (b > line) for a, b in pairwise(crowded))
    line, apart = drawn(5)
    assert len(apart) == 5 and all(y > line for y in apart)


# A molecule's polarity laid out on the molecule alchemist draws (chemistry.typ's _layout):
# the AI drew it by hand (raw cetz), 0 of 4 right: an angle's arc outside its angle, its value
# on the dipole's arrow, the arrow through an atom, a charge far from its atom
WATER = """fragment("H", name: "H1")
  single(absolute: 37.75deg)
  fragment("O", name: "O")
  single(absolute: -37.75deg)
  fragment("H", name: "H2")"""
HCL = 'fragment("H", name: "H")\n  single()\n  fragment("Cl", name: "Cl")'
CO2 = 'fragment("O", name: "O1")\n  double()\n  fragment("C", name: "C")\n  double()\n  fragment("O", name: "O2")'
PROPANONE = """fragment("CH_3")
  single(angle: 1)
  fragment("C", name: "C")
  branch({ double(angle: 2); fragment("O", name: "O") })
  single(angle: -1)
  fragment("CH_3")"""

SUMMARY = """(ctx => {
  let r(p) = p.map(x => calc.round(x, digits: 3))
  let l = _layout(ctx, MARKS, _split(({ MOLECULE })).at(2))
  panic(json.encode((
    atoms: l.atoms.pairs().map(((n, b)) => (n, r(_centre(b)))).to-dict(),
    rects: l.atoms.values().map(r),
    charges: l.charges.map(c => (atom: c.atom, at: r(_centre(c.rect)), rect: r(c.rect))),
    angles: l.angles.map(a => (start: a.start.deg(), delta: a.delta.deg(), label: r(_centre(a.rect)))),
    arrows: l.bond-arrows.map(b => (tail: r(b.tail), head: r(b.head))),
    moment: if l.moment == none { none } else { (tail: r(l.moment.tail), head: r(l.moment.head)) },
    zero: l.zero != none,
  ), pretty: false))
},)"""


def layout(molecule: str, marks: str) -> dict:
    """Where the marks go on the molecule, as the preamble computes them."""
    summary = SUMMARY.replace("MOLECULE", molecule).replace("MARKS", marks)
    with pytest.raises(figures_typst.Unusable) as said:
        figures_typst.compile_svg("chemistry", f"#skeletize({{\n  {molecule}\n  {summary}\n}})")
    message = str(said.value)
    return json.loads(message[message.index("{") : message.rindex("}") + 1])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _meet(r, s):
    return r[0] < s[2] and s[0] < r[2] and r[1] < s[3] and s[1] < r[3]


def test_a_charge_set_on_its_atoms_free_side():
    """Each charge beside its atom, opposite its bonds, clear of every atom and other charge."""
    got = layout(WATER, 'charge("O", "δ-") + charge(("H1", "H2"), "δ+")')
    atoms, charges = got["atoms"], {c["atom"]: c for c in got["charges"]}
    o = atoms["O"]
    bonds = [_sub(atoms["H1"], o), _sub(atoms["H2"], o)]
    for bond in bonds:  # the oxygen's on the side its bonds don't go
        assert _dot(_sub(charges["O"]["at"], o), bond) < 0
    for h in ("H1", "H2"):  # each hydrogen's on its far side from the oxygen
        assert _dot(_sub(charges[h]["at"], atoms[h]), _sub(o, atoms[h])) < 0
    rects = [c["rect"] for c in got["charges"]]
    for i, rect in enumerate(rects):
        assert not any(_meet(rect, atom) for atom in got["rects"])
        assert not any(_meet(rect, other) for other in rects[i + 1 :])
    got = layout(HCL, 'charge("H", "δ+") + charge("Cl", "δ-")')
    charges = {c["atom"]: c["at"] for c in got["charges"]}
    assert charges["H"][0] < got["atoms"]["H"][0] and charges["Cl"][0] > got["atoms"]["Cl"][0]


def test_a_bond_angles_arc_inside_the_angle():
    """The arc spans the angle between the two bonds, on its inside, its value inside it too."""
    got = layout(WATER, 'bond-angle("H1", "O", "H2", "104,5°")')
    (angle,) = got["angles"]
    assert abs(abs(angle["delta"]) - 104.5) < 0.5
    middle = math.radians(angle["start"] + angle["delta"] / 2)
    assert math.sin(middle) < -0.99  # the hydrogens are below: the angle opens downwards
    o, label = got["atoms"]["O"], angle["label"]
    to_label = _sub(label, o)
    for h in ("H1", "H2"):  # the value between the two bonds, nearer the oxygen than the hydrogens
        other = "H2" if h == "H1" else "H1"
        bond, other_bond = _sub(got["atoms"][h], o), _sub(got["atoms"][other], o)
        cross = lambda a, b: a[0] * b[1] - a[1] * b[0]  # noqa: E731
        assert cross(bond, to_label) * cross(bond, other_bond) > 0
    assert label[1] > got["atoms"]["H1"][1] - 0.2


@pytest.mark.parametrize(
    ("molecule", "charges", "towards"),
    [
        (WATER, 'charge("O", "2δ-") + charge(("H1", "H2"), "δ+")', (0, -1)),  # to the hydrogens
        (HCL, 'charge("H", "δ+") + charge("Cl", "δ-")', (-1, 0)),  # to the hydrogen
    ],
    ids=["water", "hydrogen-chloride"],
)
def test_a_dipole_moment_computed_from_the_charges(molecule, charges, towards):
    """From δ- towards δ+ by default, the other way with from: "positive", beside the molecule
    (no atom on its line)."""
    for from_, sign in (("", 1), ('from: "positive"', -1)):
        got = layout(molecule, f"{charges} + dipole({from_})")
        moment = got["moment"]
        way = _sub(moment["head"], moment["tail"])
        assert _dot(way, towards) * sign > 0.9 * math.hypot(*way)
        for rect in got["rects"]:
            for i in range(11):
                p = [moment["tail"][k] + (moment["head"][k] - moment["tail"][k]) * i / 10 for k in (0, 1)]
                assert not (rect[0] <= p[0] <= rect[2] and rect[1] <= p[1] <= rect[3])


def test_a_symmetric_molecules_dipole_moment_is_null():
    """CO2's charges cancel: no arrow; written p = 0 when asked."""
    charges = 'charge("C", "2δ+") + charge(("O1", "O2"), "δ-")'
    got = layout(CO2, f"{charges} + dipole()")
    assert got["moment"] is None and not got["zero"]
    got = layout(CO2, f"{charges} + dipole(zero: true)")
    assert got["moment"] is None and got["zero"]


def test_a_bonds_polarisation_beside_its_bond():
    """The bond's arrow parallel to it, from its first atom to its second, off its line."""
    got = layout(PROPANONE, 'bond-dipole("C", "O")')
    (arrow,) = got["arrows"]
    c, o = got["atoms"]["C"], got["atoms"]["O"]
    bond, way = _sub(o, c), _sub(arrow["head"], arrow["tail"])
    assert _dot(bond, way) > 0.99 * math.hypot(*bond) * math.hypot(*way)
    off = _sub(arrow["tail"], c)
    assert abs(bond[0] * off[1] - bond[1] * off[0]) / math.hypot(*bond) > 0.2  # off the bond's line


def test_a_charges_value_read_from_its_label():
    """ "2δ-" and $2 delta^-$ alike: the dipole moment weighs the charges by their values."""
    labels = '("δ+", "δ-", "2δ-", $2 delta^-$, $delta^+$, "3δ+", "δ−", "-δ", $delta^(-)$)'
    with pytest.raises(figures_typst.Unusable) as said:
        values = f"{labels}.map(l => _charge-value(l).at(0))"
        figures_typst.compile_svg("chemistry", f"#panic(json.encode({values}, pretty: false))")
    message = str(said.value)
    assert json.loads(message[message.index("[") :]) == [1, -1, -2, -2, 1, 3, -1, -1, -1]


def test_the_chemistry_rules_polarity_compiles():
    """The polarity calls the rule shows, on a molecule whose atoms they name, draw their labels."""
    rule = figures_typst.FAMILIES["chemistry"].rules
    calls = re.findall(r"`((?:charge|bond-angle|dipole|bond-dipole)\([^`]*\))`", rule)
    assert {c.split("(")[0] for c in calls} == {"charge", "bond-angle", "dipole", "bond-dipole"}
    molecule = """fragment("Cl", name: "Cl1")
  single(absolute: 38deg)
  fragment("S", name: "S")
  single(absolute: -38deg)
  fragment("Cl", name: "Cl2")"""
    bare = figures_typst.compile_svg("chemistry", f"#skeletize({{ {molecule} }})")
    marked = figures_typst.compile_svg("chemistry", f"#skeletize({{ {molecule}\n  {'\n  '.join(calls)} }})")
    assert marked.count("<use") > bare.count("<use") + 4  # the charges, the angle's value, p


def test_a_throws_angle_is_the_descriptions():
    """ "Launched at 45°": the rule never said a throw takes its angle, so the parabola was
    always launched at 60°. The rule says it; the angle given draws another parabola."""
    rule = figures_typst.FAMILIES["mechanics"].rules
    (chrono,) = [line for line in rule.splitlines() if line.startswith("- a chronophotography")]
    assert "`angle`" in chrono and "horizontal" in chrono
    drawn = lambda body: figures_typst.compile_svg("mechanics", f"#chronophotography({body})")  # noqa: E731
    assert drawn("angle: 45") != drawn("")


def test_a_slopes_angle_takes_the_lessons_name():
    """A lesson naming the slope's angle θ: α was always written. `theta` names it, the rule
    says so; without it, α as before."""
    assert "`theta` the angle's name when the description names it" in figures_typst.FAMILIES["mechanics"].rules
    slope = '#mechanics(support: "slope", angle: 25, vectors: (("P", "down"),){})'
    drawn = lambda more: figures_typst.compile_svg("mechanics", slope.format(more))  # noqa: E731
    assert drawn("") == drawn(", theta: $alpha$")
    assert drawn(", theta: $theta$") != drawn("")


@pytest.mark.parametrize(("at", "name"), [(60, "Terre"), (200, "Soleil"), (310, "Jupiter")])
def test_an_orbits_radius_starts_at_its_centre(at, name):
    """The radius was drawn under the centre's body (the Earth's disc), so it seemed to start
    at its surface: a checker refused the rule's own example 3 times in 3. Drawn over the
    disc from its very centre, the body's name (in red here) beside it, never crossed."""
    import math

    from PIL import Image

    body = (
        f'#mechanics(support: "circle", centre: text(fill: rgb("#ff0000"))[{name}], at: {at},'
        ' radius: $r$, body: [S], vectors: (("v", "along"), ("F", "centre")))'
    )
    png = figures.to_png(figures.clean(figures_typst.compile_svg("mechanics", body)))
    image = Image.open(io.BytesIO(png)).convert("RGB")
    width = image.width
    pixels = list(image.getdata())
    where = lambda keep: [(i % width, i // width) for i, p in enumerate(pixels) if keep(p)]  # noqa: E731
    disc = where(lambda p: p == (225, 225, 225))
    x0, x1 = min(x for x, _ in disc), max(x for x, _ in disc)
    y0, y1 = min(y for _, y in disc), max(y for _, y in disc)
    (cx, cy), radius = ((x0 + x1) / 2, (y0 + y1) / 2), (x1 - x0) / 2
    a = math.radians(at + 135)  # the radius's way
    for t in (0.0, 0.3, 0.6, 0.9):  # its line's pixels across the disc, from the centre
        px, py = cx + t * radius * math.cos(a), cy - t * radius * math.sin(a)
        around = range(-2, 3)
        near = [image.getpixel((round(px) + dx, round(py) + dy)) for dx in around for dy in around]
        assert any(sum(p) < 200 for p in near), (t, px, py)
    red = where(lambda p: p[0] > 150 and p[1] < 100 and p[2] < 100)
    rx0, rx1 = min(x for x, _ in red), max(x for x, _ in red)
    ry0, ry1 = min(y for _, y in red), max(y for _, y in red)
    crossed = [(x, y) for x, y in where(lambda p: sum(p) < 200) if rx0 <= x <= rx1 and ry0 <= y <= ry1]
    assert not crossed


def test_a_body_on_a_track_drawn_as_the_rule_says():
    """A skater on a U ramp drawn as SVG by hand: a stick figure at a random tilt, once at B
    instead of A, its texts placed by eye. The rule's own track compiles; a point that isn't
    the track's refused, saying which are."""
    rule = figures_typst.FAMILIES["mechanics"].rules
    (call,) = re.findall(r"`(#track\([^`]*\))`", rule)
    assert figures.clean(figures_typst.compile_svg("mechanics", call)).startswith("<svg")
    with pytest.raises(figures_typst.Unusable, match="no point of the track"):
        figures_typst.compile_svg("mechanics", '#track(points: ("A", "B"), at: "C")')


def test_a_tracks_profile_and_body_computed():
    """The profile through its key points, flat at each (a top, a hollow), the body on it at
    its point: never placed by eye."""
    check = """#let (knots, w) = track-places((3, 0, 2))
#assert(knots.at(0).at(1) > knots.at(2).at(1) and knots.at(2).at(1) > knots.at(1).at(1))
#for k in knots {
  let (p, slope) = track-at(knots, w, k.at(0))
  assert(calc.abs(p.at(1) - k.at(1)) < 1e-9 and calc.abs(slope) < 1e-9)
}
#context {
  let l = track-layout(heights: (3, 0, 2), points: ("A", "B", "C"), at: "B")
  let b = l.knots.at(1)
  assert(calc.abs(l.centre.at(0) - b.at(0)) < 1e-9 and l.centre.at(1) > b.at(1))
}
#track(heights: (3, 0, 2), points: ("A", "B", "C"), at: "B")"""
    assert figures_typst.compile_svg("mechanics", check).startswith("<svg")


def test_a_tracks_texts_clear_of_the_track_and_of_one_another():
    """Each point's name and note, the body's name, the vectors' names: none on the track, the
    ground or another text (the skater's note written in the middle of the ramp before)."""
    check = """#context {
  let l = track-layout(heights: (3, 0, 3), points: ("A", "B", ""), at: "A", body: [skateur],
    notes: (A: [énergie potentielle maximale, vitesse nulle], B: [énergie cinétique maximale]),
    vectors: (("P", "down"), ("R", "normal")))
  let inside(p, ((x0, y0), (x1, y1))) = p.at(0) > x0 and p.at(0) < x1 and p.at(1) > y0 and p.at(1) < y1
  let meets(((a0, b0), (a1, b1)), ((x0, y0), (x1, y1))) = a0 < x1 and x0 < a1 and b0 < y1 and y0 < b1
  assert(l.texts.len() == 7)  // 2 vectors, A and B, the body, 2 notes
  for (i, (c, q, anchor, b)) in l.texts.enumerate() {
    assert(not (l.fine + l.ground).any(p => inside(p, b)), message: "a text on the track: " + repr(c))
    for (j, t) in l.texts.enumerate() { assert(i == j or not meets(b, t.at(3)), message: "two texts on one another") }
  }
}
#track(points: ("A", "B"), at: "A")"""
    assert figures_typst.compile_svg("mechanics", check).startswith("<svg")


PLAIN_WATER = 'fragment("H"); single(angle: 1); fragment("O", lewis: pairs(2)); single(angle: -1); fragment("H")'


@pytest.mark.parametrize("angle", [0, 90, -10])
def test_a_throw_at_no_angle_refused(angle):
    """A throw at 0° (no flight: every position at the launch, its width 0 divided by) or at 90°
    (straight up: the scale out of bounds): refused, saying a throw's angle."""
    with pytest.raises(figures_typst.Unusable, match="angle is a throw's angle"):
        figures_typst.compile_svg("mechanics", f'#chronophotography(motion: "thrown", angle: {angle})')


def test_a_velocity_at_rest_drawn_as_none():
    """A fall's velocity asked at its first position, at rest: every velocity 0, the arrows'
    lengths divided by it. No arrow there, the others drawn."""
    rest = figures_typst.compile_svg("mechanics", '#chronophotography(motion: "falling", n: 4, velocity: (0,))')
    bare = figures_typst.compile_svg("mechanics", '#chronophotography(motion: "falling", n: 4)')
    assert rest == bare
    moving = figures_typst.compile_svg("mechanics", '#chronophotography(motion: "falling", n: 4, velocity: (0, 3))')
    assert "1f5fbf" in moving.lower()


@pytest.mark.parametrize(
    ("body", "said"),
    [
        # the dots from O to N, no H between them (1 drawing in 3)
        (
            'fragment("H"); single(angle: -1); fragment("O", lewis: pairs(2)); branch({ single(angle: 1); '
            'fragment("H") }); single(stroke: (dash: "dotted")); fragment("N", lewis: pairs(1)); '
            'single(); fragment("H")',
            "not O…N",
        ),
        # water given a third H, by a branch written before its O (2 drawings in 3): H3O, not water
        (
            'branch({ single(absolute: 135deg); fragment("H") }); branch({ single(absolute: 225deg); fragment("H") }); '
            'fragment("O", lewis: pairs(2)); single(absolute: -30deg); fragment("H")',
            "O has 3 bonds",
        ),
        ('fragment("C"); double(); fragment("C"); triple(); fragment("C")', "C has 5 bonds"),
    ],
)
def test_a_molecule_wrong_in_its_atoms_refused_saying_why(body, said):
    """A hydrogen bond between two heavy atoms, an O with three H: drawn as written, a wrong
    molecule. Refused, saying what is wrong, so that the AI writes it again."""
    with pytest.raises(figures_typst.Unusable, match=said):
        figures_typst.compile_svg("chemistry", "#skeletize({ " + body + " })")


@pytest.mark.parametrize(
    "body",
    [
        PLAIN_WATER,
        PLAIN_WATER + '; single(stroke: (dash: "dotted")); fragment("O", lewis: pairs(2)); single(); fragment("H")',
        # ions written with their charge: H3O+, NH4+
        'fragment("H"); single(angle: 1); fragment("O^+", lewis: pairs(1)); branch({ single(angle: -2); '
        'fragment("H") }); single(angle: -1); fragment("H")',
        'fragment("H"); single(); fragment("N^+"); branch({ single(angle: 2); fragment("H") }); '
        'branch({ single(angle: -2); fragment("H") }); single(); fragment("H")',
        'fragment("O", lewis: pairs(2)); double(); fragment("C"); double(); fragment("O", lewis: pairs(2))',
        'fragment("OH"); single(); cycle(6, { single(); double(); single(); double(); single(); double() })',
    ],
)
def test_a_right_molecule_drawn(body):
    assert figures_typst.compile_svg("chemistry", "#skeletize({ " + body + " })").startswith("<svg")


@pytest.mark.parametrize(
    ("body", "said"),
    [
        ('branch((0, 0), (0, 0), lamp("l"))', "two ends are two different points"),
        ('branch((0, 0), (3, 0), lamp("l"), wire((0, 0), (1, 0)))', "given without points, each one of battery"),
        ('branch((0, 0), (3, 0), lamp("l"), "R")', "given without points, each one of battery"),
        ('branch((0, 0), (1, 0), lamp("l"), resistor("r"), resistor("r2"), battery("g"), current: $I$)', "too short"),
    ],
)
def test_a_branch_refused_saying_why(body, said):
    """A branch from a point to itself (divided by zero), a wire or a text among its components
    (an error inside its layout), or too short for its components even drawn at their smallest
    (drawn over one another): refused, saying what a branch takes."""
    with pytest.raises(figures_typst.Unusable, match=said):
        figures_typst.compile_svg("circuit", f"#circuit({{ {body} }})")
