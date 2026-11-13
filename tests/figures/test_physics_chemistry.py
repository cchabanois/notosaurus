"""The circuit (zap), mechanics (our mechanics function) and chemistry (alchemist)
families."""

import io
import json
import math
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
    calls = re.findall(r"`(fragment\([^`]*lewis:[^`]*\))`", rule)
    assert calls, "the chemistry rule shows a Lewis structure's pairs"
    for call in calls:
        assert figures_typst.compile_svg("chemistry", "#skeletize({ " + call + " })").startswith("<svg")


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
