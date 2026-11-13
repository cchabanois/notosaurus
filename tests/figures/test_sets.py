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


def test_nested_groups_side_by_side_each_in_its_own_box():
    """A classification whose group splits (mammals and birds both in tetrapods): the chain of
    ellipses couldn't draw it, the AI drew rectangles by eye, names past their boxes and on one
    another. A tree of groups, laid out by the preamble: checked by Typst itself, every box in
    its parent, sibling boxes apart, every text (measured) in its own box, outside its
    sub-groups' boxes and clear of every other text."""
    check = """#context {
      let (boxes, texts) = _nest-box(TREE, "0", 0)
      let span(t) = (x0: t.x - t.w / 2, x1: t.x + t.w / 2, y0: t.y - t.h / 2, y1: t.y + t.h / 2)
      let within(t, r) = { let s = span(t); s.x0 >= r.x0 and s.x1 <= r.x1 and s.y0 >= r.y0 and s.y1 <= r.y1 }
      let meet(a, b) = a.x0 < b.x1 and b.x0 < a.x1 and a.y0 < b.y1 and b.y0 < a.y1
      let parent(p) = p.split(".").slice(0, -1).join(".")
      let under(p, q) = p.starts-with(q + ".")
      for r in boxes.filter(r => r.path != "0") {
        let up = boxes.find(b => b.path == parent(r.path))
        assert(r.x0 > up.x0 and r.x1 < up.x1 and r.y0 > up.y0 and r.y1 < up.y1, message: "a box out of its parent")
        for s in boxes.filter(s => s.path != r.path and parent(s.path) == parent(r.path)) {
          assert(not meet(r, s), message: "sibling boxes overlap")
        }
      }
      for t in texts {
        assert(within(t, boxes.find(b => b.path == t.box)), message: "a text out of its box")
        for r in boxes.filter(r => under(r.path, t.box)) {
          assert(not meet(span(t), r), message: "a text in a sub-group")
        }
        for u in texts.filter(u => u != t) { assert(not meet(span(t), span(u)), message: "texts on one another") }
      }
      assert(texts.filter(t => t.kind == "name").len() == boxes.len())
      nested-sets(TREE)
    }"""
    tree = (
        "nest([Êtres vivants], [escargot], [une méduse au nom très long], nest([Vertébrés (squelette interne)],"
        " [truite], nest([Tétrapodes (4 membres)], [lézard], [grenouille],"
        " nest([Mammifères (poils)], [chat], [chauve-souris]), nest([Oiseaux (plumes)], [pigeon]),"
        " nest([Un groupe au nom bien plus long que ses membres], [x]), nest([Crocodiliens], [caïman]),"
        " nest([Tortues], [tortue]))))"
    )
    assert figures_typst.compile_svg("sets", check.replace("TREE", tree)).startswith("<svg")
    # sibling groups side by side: mammals and birds on one row, the parent's elements under it
    rows = """#context {
      let (boxes, texts) = _nest-box(nest([T], [lézard], nest([Mammifères], [chat]), nest([Oiseaux], [pigeon])), "0", 0)
      let (m, o) = (boxes.at(1), boxes.at(2))
      assert(m.y0 == o.y0 and m.x1 < o.x0, message: "not side by side")
      let own = texts.find(t => t.kind == "item" and t.box == "0")
      assert(own.y - own.h / 2 > m.y1, message: "the parent's element not under its groups")
      [drawn]
    }"""
    figures_typst.compile_svg("sets", rows)


def test_nested_groups_as_a_chain_drawn_as_the_chain():
    """A tree whose every group holds one group at most is a chain: drawn as the chain's
    ellipses, exactly as the chain's own call draws it."""
    tree = "#nested-sets(nest($RR$, $sqrt(2)$, $pi$, nest($ZZ$, $-5$, nest($NN$, $3$))))"
    chain = "#nested-sets(($NN$, ($3$,)), ($ZZ$, ($-5$,)), ($RR$, ($sqrt(2)$, $pi$)))"
    assert figures_typst.compile_svg("sets", tree) == figures_typst.compile_svg("sets", chain)
    assert "nest(" in figures_typst.FAMILIES["sets"].rules


def test_nested_sets_given_as_one_list_drawn_as_given_one_by_one():
    """The chain's sets wrapped in one list, ((name, elements), …), or their names and
    elements one after the other in it, (name, elements, name, elements): refused ("each set
    is (its name, (its elements,))"), the figure drawn as SVG by eye, 3 drawings of 6. Each
    set its own, as when given one by one."""
    one_by_one = figures_typst.compile_svg("sets", "#nested-sets(([N], ([3],)), ([Z], ([-5],)), ([R], ([pi],)))")
    for listed in (
        "#nested-sets((([N], ([3],)), ([Z], ([-5],)), ([R], ([pi],))))",
        "#nested-sets(([N], ([3],), [Z], ([-5],), [R], ([pi],)))",
    ):
        assert figures_typst.compile_svg("sets", listed) == one_by_one
