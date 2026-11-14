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


def test_nested_sets_single_element_without_its_comma_drawn():
    """A set with one element written without its trailing comma, ($NN$, ($3$)): its element
    itself, not a list of one ("equation has no method map"); a set given by its name alone:
    no element of its own. Each drawn as it means."""
    for alone, listed in (
        ("#nested-sets(($NN$, ($3$)), ($ZZ$, ($-5$,)))", "#nested-sets(($NN$, ($3$,)), ($ZZ$, ($-5$,)))"),
        ("#nested-sets(($NN$), ($ZZ$, ($-5$,)))", "#nested-sets(($NN$, ()), ($ZZ$, ($-5$,)))"),
    ):
        assert figures_typst.compile_svg("sets", alone) == figures_typst.compile_svg("sets", listed)


def test_a_colour_mix_with_more_labels_than_colours_refused():
    """Three names for two colours ran past the parts' list ("index out of bounds"): refused,
    saying a label names a colour."""
    with pytest.raises(figures_typst.Unusable, match="one per colour"):
        figures_typst.compile_svg("sets", '#colour-mix(colours: ("red", "green"), labels: ([R], [G], [B]))')


CLASSIFICATION = """(
  (id: "ev", name: [Êtres vivants], members: ([Escargot],)),
  (id: "v", name: [Vertébrés (squelette interne)], inside: "ev", members: ([Truite],)),
  (id: "t", name: [Tétrapodes (4 membres)], inside: "v", members: ([Lézard],)),
  (id: "m", name: [Mammifères (poils)], inside: "t", members: ([Chat],)),
  (id: "o", name: [Oiseaux (plumes)], inside: "t", members: ([Pigeon],)),
)"""


def test_groups_side_by_side_in_a_group_named_whole():
    """A classification with two groups in a third (the mammals and the birds in the tetrapods):
    nested-sets has no two side by side, so the AI drew the boxes by eye: names cut by a box,
    on one another, the snail on the vertebrates' edge (3 drawings in 3). Laid out by
    nested-groups: every text inside its own box, clear of every smaller box and of the other
    texts; each box inside its group's."""
    check = f"""#context {{
  let l = _groups-layout({CLASSIFICATION})
  let box(id) = l.boxes.find(b => b.id == id).rect
  let within(r, s) = r.at(0) >= s.at(0) and r.at(1) >= s.at(1) and r.at(2) <= s.at(2) and r.at(3) <= s.at(3)
  let meets(r, s) = r.at(0) < s.at(2) and s.at(0) < r.at(2) and r.at(1) < s.at(3) and s.at(1) < r.at(3)
  for b in l.boxes {{
    if b.inside != none {{ assert(within(b.rect, box(b.inside)), message: "a box out of its group") }}
  }}
  for (i, t) in l.texts.enumerate() {{
    assert(within(t.rect, box(t.id)), message: "a text out of its box: " + t.id)
    for b in l.boxes {{
      if b.inside == t.id {{ assert(not meets(t.rect, b.rect), message: "a text on a smaller box: " + t.id) }}
    }}
    for (j, u) in l.texts.enumerate() {{
      assert(i == j or not meets(t.rect, u.rect), message: "two texts on one another")
    }}
  }}
  // the mammals and the birds side by side, in the tetrapods
  assert(box("m").at(2) <= box("o").at(0) and box("m").at(3) == box("o").at(3))
  [checked]
}}"""
    figures_typst.compile_svg("sets", check)
    assert figures_typst.compile_svg("sets", f"#nested-groups(..{CLASSIFICATION})").startswith("<svg")


def test_groups_the_rule_writes_compile_and_wrong_ones_refused():
    """The rule's own call compiles; a group inside one that isn't there, refused saying so."""
    rule = (figures_typst.RULES / "sets.md").read_text(encoding="utf-8")
    call = re.search(r"`(#nested-groups\(.*?\)\))`", rule)
    assert call
    assert figures_typst.compile_svg("sets", call[1]).startswith("<svg")
    with pytest.raises(figures_typst.Unusable, match="another group's id"):
        figures_typst.compile_svg("sets", '#nested-groups((id: "a", name: [A], inside: "b"))')
