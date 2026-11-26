"""The colours a description gives a vector, a ray, a current's or a voltage's arrow, field
lines: drawn in them, what is computed computed as before; none given: black, as before."""

import re

import pytest

from notosaurus_core import figures, figures_typst

RED, BLUE, GREEN = "#ff4136", "#0074d9", "#2ecc40"

CIRCUIT = (
    '#circuit({{\n branch((0, 3), (4.5, 3), switch("k", label: $K$, closed: true), lamp("l", label: $L${lamp}), '
    "current: $I${current})\n wire((4.5, 3), (4.5, 0))\n"
    'battery("g", (4.5, 0), (0, 0), label: $G$)\n wire((0, 0), (0, 3))\n}})'
)


def colours(family: str, body: str) -> set[str]:
    svg = figures.clean(figures_typst.compile_svg(family, body))
    return {c.lower() for c in re.findall(r'(?:stroke|fill)="(#[0-9a-fA-F]{6})', svg)}


@pytest.mark.parametrize(
    ("family", "body", "plain", "given"),
    [
        # a force's arrow and name, on a slope (with a scale too); on a track
        (
            "mechanics",
            '#mechanics(support: "slope", vectors: (("P", "down", red), ("R", "normal", blue)))',
            '#mechanics(support: "slope", vectors: (("P", "down"), ("R", "normal")))',
            {RED, BLUE},
        ),
        (
            "mechanics",
            '#mechanics(support: "plane", scale: (2, "N"), vectors: (("P", "down", 4, red),))',
            '#mechanics(support: "plane", scale: (2, "N"), vectors: (("P", "down", 4),))',
            {RED},
        ),
        (
            "mechanics",
            '#track(heights: (3, 0, 2), points: ("A", "B", "C"), at: "A", vectors: (("P", "down", red),))',
            '#track(heights: (3, 0, 2), points: ("A", "B", "C"), at: "A", vectors: (("P", "down"),))',
            {RED},
        ),
        # a lens's rays by name, computed as before (a virtual image's dashed back too); a
        # surface's; a telescope's beam
        (
            "optics",
            "#lens(focal: 3, object: -6, height: 1.5, colours: (centre: red, parallel: blue))",
            "#lens(focal: 3, object: -6, height: 1.5)",
            {RED, BLUE},
        ),
        (
            "optics",
            "#lens(focal: 3, object: -2, height: 1, colours: (focal: green))",
            "#lens(focal: 3, object: -2, height: 1)",
            {GREEN},
        ),
        (
            "optics",
            "#refraction(incidence: 40, reflected: true, colours: (incident: red, refracted: blue))",
            "#refraction(incidence: 40, reflected: true)",
            {RED, BLUE},
        ),
        ("optics", "#telescope(colour: red)", "#telescope()", {RED}),
        # the current's arrow, the voltage's
        (
            "circuit",
            CIRCUIT.format(lamp="", current=", current-colour: red"),
            CIRCUIT.format(lamp="", current=""),
            {RED},
        ),
        (
            "circuit",
            CIRCUIT.format(lamp=", voltage: $U_L$, voltage-colour: blue", current=""),
            CIRCUIT.format(lamp=", voltage: $U_L$", current=""),
            {BLUE},
        ),
        (
            "field",
            '#field(magnets: ((at: (0, 0), north: "right"),), colour: blue)',
            '#field(magnets: ((at: (0, 0), north: "right"),))',
            {BLUE},
        ),
    ],
)
def test_a_colour_the_description_gives_is_drawn(family, body, plain, given):
    """Asked for « the weight in red », « the ray through O in red », « the current's arrow in
    red », « the field lines in blue », the functions drew black: the AI left the colour out
    (no way to give it), and a correction said it done. Without them: none of these colours."""
    assert given <= colours(family, body)
    assert not (given & colours(family, plain))


@pytest.mark.parametrize(
    ("family", "body", "said"),
    [
        ("mechanics", '#mechanics(vectors: (("P", "down", "red"),))', "a colour last when the description gives one"),
        (
            "optics",
            "#lens(colours: (center: red))",
            "colours: the rays by name, each a colour: (centre: red, parallel: red, focal: red)",
        ),
        ("optics", '#refraction(colours: (incident: "red"))', "colours: the rays by name"),
        (
            "circuit",
            CIRCUIT.format(lamp="", current=', current-colour: "red"'),
            "current-colour, the current's arrow's, is a colour",
        ),
        (
            "field",
            '#field(magnets: ((at: (0, 0), north: "right"),), colour: "blue")',
            "colour is the field lines' colour",
        ),
    ],
)
def test_a_colour_written_otherwise_refused_saying_how(family, body, said):
    """A colour written as text, or a ray named otherwise: refused saying how (Typst's message,
    given back to the AI)."""
    with pytest.raises(figures_typst.Unusable, match=re.escape(said)):
        figures_typst.compile_svg(family, body)
