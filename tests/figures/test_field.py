"""The field family (cetz, our functions): a magnet's or charges' field lines computed, from
north to south, from + to −, never drawn by the AI's eye."""

import json

import pytest
import typst

from notosaurus_core import figures_typst


def _value(tmp_path, expression: str):
    """What the field preamble computes, read back (a Typst value, as JSON)."""
    page = tmp_path / "query.typ"
    page.write_text(figures_typst.FAMILIES["field"].preamble + f"\n#metadata({expression}) <value>\n", encoding="utf-8")
    found = typst.query(
        str(page), "<value>", field="value", one=True, format="json", package_path=str(figures_typst.packages())
    )
    return json.loads(found)


def test_field_lines_are_a_family_of_their_own():
    """A bar magnet's field lines were SVG drawn by the AI: loops through the magnet, petals
    crossing one another, lines leaving the south pole (3 drawings in 3 wrong). A family of
    their own, for magnets and charges, never a uniform field between plates."""
    assert "field" in figures_typst.FAMILIES and "field" in figures_typst.FigureKind.__args__
    kind = figures_typst.KINDS.split('"field":')[1].split(";")[0]
    assert "magnet" in kind and "charges" in kind and "never a uniform field" in kind


def test_a_magnets_lines_go_from_north_to_south(tmp_path):
    """Outside a magnet whose north is on the right, the field points away from N on its axis
    and towards S beyond it; a line leaving N above it comes back into S (not into N), never
    through the magnet."""
    magnets = '((at: (0, 0), north: "right"),)'
    sources = f"_sources({magnets}, ())"
    fx, _ = _value(tmp_path, f"field-at({sources}, (3, 0))")
    gx, _ = _value(tmp_path, f"field-at({sources}, (-3, 0))")
    assert fx > 0 and gx > 0  # rightwards on both sides: out of N, into S
    line = _value(tmp_path, f"field-line({sources}, {magnets}, (1.5, 0.6), (-5, -4, 5, 4))")
    assert line["end"] == "sink"
    last = line["pts"][-1]
    assert last[0] < 0  # ended on the south half (left)
    assert all(abs(y) >= 0.39 or abs(x) > 1.5 for x, y in line["pts"])  # never inside the body


def test_a_positive_charges_lines_reach_the_negative_one(tmp_path):
    charges = '((at: (-2, 0), sign: "+"), (at: (2, 0), sign: "-"))'
    sources = f"_sources((), {charges})"
    line = _value(tmp_path, f"field-line({sources}, (), (-1.8, 0.1), (-6, -5, 6, 5))")
    assert line["end"] == "sink" and line["pts"][-1][0] > 1.5


def test_the_rules_example_and_two_magnets_compile():
    for body in (
        '#field(magnets: ((at: (-2.5, 0), north: "right"), (at: (2.5, 0), north: "left")))',
        '#field(magnets: ((at: (0, 0), north: "up"),))',
        '#field(charges: ((at: (0, 0), sign: "-"),))',
    ):
        assert figures_typst.compile_svg("field", body).startswith("<svg")


@pytest.mark.parametrize(
    ("body", "said"),
    [
        ('#field(magnets: ((at: (0, 0), north: "east"),))', "north one of"),
        ('#field(charges: ((at: (0, 0), sign: "±"),))', "a charge is"),
        ("#field()", "needs a magnet or a charge"),
    ],
)
def test_a_field_refuses_what_it_cant_draw(body, said):
    with pytest.raises(figures_typst.Unusable, match=said):
        figures_typst.compile_svg("field", body)
