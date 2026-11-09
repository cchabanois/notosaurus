"""The sets family (cetz-venn and our functions): nested sets, a Venn diagram's parts,
colours mixed."""

import re

import pytest

from notosaurus_core import figures, figures_typst


def test_nested_sets_elements_each_in_its_own_ring():
    """Sets inside one another (ℕ ⊂ ℤ ⊂ … ⊂ ℝ), drawn by the AI by eye: −5 in ℕ, 0,25 in ℤ.
    Laid out by the preamble: each text (its middle) inside its set's ellipse and outside the
    next smaller one, checked by Typst itself (an assert failing, the figure isn't made)."""
    check = """#context {
      let inside(s, p) = { let (cy, a, b) = s; calc.pow(p.at(0) / a, 2) + calc.pow((p.at(1) - cy) / b, 2) < 1 }
      let (shapes, placed) = _nested-layout(LEVELS)
      for (k, p, c) in placed {
        assert(inside(shapes.at(k), p), message: "outside its set")
        if k > 0 { assert(not inside(shapes.at(k - 1), p), message: "inside a smaller set") }
      }
      nested-sets(..LEVELS)
    }"""
    levels = (
        "(([N], ([3],)), ([Z], ([-5],)), ([D], ([0,25],)), ([Q], ([1/3],)),"
        " ([R], ([racine de 2], [pi], [un nombre long])))"
    )
    assert figures_typst.compile_svg("sets", check.replace("LEVELS", levels)).startswith("<svg")


def test_a_venn_parts_name_wider_than_it_goes_outside():
    """ "A ∩ B" written in a two-set lens (0.75 wide) lay on both circles, three drawings out
    of three. A part's name that fits stays in it; a wider one goes under the diagram, a line
    joining it to its part."""
    venn = '#cetz.canvas({{ cetz-venn.venn2(name: "v"); part-label("v.ab", {}) }})'
    svg = figures_typst.compile_svg
    short = svg("sets", venn.format("[$x$]"))
    long = svg("sets", venn.format("[$A inter B$]"))
    bare = svg("sets", '#cetz.canvas({ cetz-venn.venn2(name: "v") })')
    height = lambda s: float(re.search(r'height="([\d.]+)', s).group(1))  # noqa: E731
    assert height(short) == height(bare)  # in the lens
    assert height(long) > height(bare) + 10  # under the diagram
    assert "part-label" in figures_typst.FAMILIES["sets"].rules


def test_colours_mixed_are_computed():
    """Additive synthesis adds the lights (red and green yellow, the three white, on black);
    subtractive multiplies the filters (cyan and magenta blue, the three black, on white):
    each part's colour computed, the synthesis' pure colours ("green" isn't Typst's #2ecc40)."""

    def fills(body: str) -> set[str]:
        return set(re.findall(r'fill="(#[0-9a-f]{6})"', figures.clean(figures_typst.compile_svg("sets", body))))

    added = fills('#colour-mix(kind: "additive", colours: ("red", "green", "blue"))')
    assert {"#ff0000", "#00ff00", "#0000ff", "#ffff00", "#ff00ff", "#00ffff", "#ffffff", "#000000"} <= added
    taken = fills('#colour-mix(kind: "subtractive", colours: ("cyan", "magenta", "yellow"))')
    assert {"#00ffff", "#ff00ff", "#ffff00", "#0000ff", "#00ff00", "#ff0000", "#000000"} <= taken
    assert fills('#colour-mix(colours: ("red", "green"))') >= {"#ff0000", "#00ff00", "#ffff00"}
    with pytest.raises(figures_typst.Unusable, match="a colour is one of"):
        figures_typst.compile_svg("sets", '#colour-mix(colours: ("rouge", "vert"))')


def test_a_mixed_colour_a_card_asks_is_not_shown():
    """ "Which colour at the centre?": the centre left grey with a question mark, its white not
    drawn (it would give the answer on the front)."""
    body = '#colour-mix(kind: "additive", colours: ("red", "green", "blue"){})'
    shown = figures.clean(figures_typst.compile_svg("sets", body.format("")))
    asked = figures.clean(figures_typst.compile_svg("sets", body.format(', ask: ("abc",)')))
    assert "#8c8c8c" in asked and "#8c8c8c" not in shown  # the centre grey, not white
    assert asked.count('fill="#ffffff"') <= shown.count('fill="#ffffff"')
