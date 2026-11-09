"""The table family (our value-table function): columns measured, totals summed, numbers
written, arrows."""

from xml.etree import ElementTree

import pytest

from notosaurus_core import figures_typst


def _table(body: str) -> str:
    return figures_typst.compile_svg("table", "#value-table(" + body + ")")


def _width(svg: str) -> float:
    return float(ElementTree.fromstring(svg).get("width", "0").removesuffix("pt"))


def test_a_tables_columns_are_as_wide_as_their_cells():
    """A table drawn as SVG had its columns' widths guessed: « Demi-pensionnaire » ran over
    the next cell (0 of 3). Drawn by value-table, each column as wide as its widest cell,
    measured: a longer header widens the table by about the text added."""
    short = _table('header: ("", "DP", "Externe"), rows: (("Fille", 70, 30), ("Garçon", 60, 40))')
    long = _table('header: ("", "Demi-pensionnaire", "Externe"), rows: (("Fille", 70, 30), ("Garçon", 60, 40))')
    # the values' columns alike, each as wide as "Demi-pensionnaire" (15 letters more than "DP")
    assert _width(long) - _width(short) > 2 * 15 * 4


def test_a_tables_totals_are_summed():
    """The totals of each row and column, and the grand total, summed by value-table: the
    same table as one whose totals were written out; a total of what is no number refused."""
    summed = _table('header: ("", "A", "B"), rows: (("Fille", 70, 30), ("Garçon", 60, 40)), totals: "Total"')
    written = _table(
        'header: ("", "A", "B", "Total"), rows: (("Fille", 70, 30, 100), ("Garçon", 60, 40, 100), '
        '("Total", 130, 70, 200))'
    )
    assert summed == written
    rows_only = _table('header: ("", "A", "B"), rows: (("Fille", 70, 30), ("Garçon", 60, 40)), totals: (right: "T")')
    assert rows_only == _table('header: ("", "A", "B", "T"), rows: (("Fille", 70, 30, 100), ("Garçon", 60, 40, 100))')
    with pytest.raises(figures_typst.Unusable, match="number"):
        _table('rows: (("Fille", 70, "beaucoup"),), totals: "Total"')


def test_a_tables_numbers_are_written_as_its_language_writes_them():
    """A number written with the figure's decimal separator, its zeros kept: a measure's
    "3,0" and "0,030" were drawn "3" and "0,03" (0 of 3); a total with as many decimals as
    the numbers summed."""
    fr = '#set text(lang: "fr")\n'

    def table(body: str) -> str:
        return figures_typst.compile_svg("table", fr + "#value-table(" + body + ")")

    assert table("rows: ((1.5, 2),)") == table('rows: (("1,5", 2),)') == table('rows: (("1.5", 2),)')
    assert table('rows: (("3,0", 2),)') != table('rows: (("3", 2),)')
    assert table('rows: (("0,030", 2),)') != table('rows: (("0,03", 2),)')
    summed = table('rows: (("I", "0,015", "0,015"),), totals: (right: "T")')
    assert summed == table('header: ("", "", "", "T"), rows: (("I", "0,015", "0,015", "0,030"),)')


def test_a_tables_arrows_join_the_rows_and_columns_given():
    """A proportionality table's arrows (× 3 from a row to the next, × 2 from a column to
    another) drawn from the rows and columns they join: one that joins none refused."""
    plain = _table("rows: ((2, 5, 7), (6, 15, 21))")
    for side in ("right", "left"):
        arrowed = _table(f"rows: ((2, 5, 7), (6, 15, 21)), {side}: ((1, 2, $times 3$),)")
        assert _width(arrowed) > _width(plain)
        with pytest.raises(figures_typst.Unusable, match="rows"):
            _table(f"rows: ((2, 5, 7), (6, 15, 21)), {side}: ((1, 3, $times 3$),)")
    for side in ("above", "below"):
        assert _table(f"rows: ((2, 5, 7), (6, 15, 21)), {side}: ((1, 2, $times 2$),)") != plain
        with pytest.raises(figures_typst.Unusable, match="columns"):
            _table(f"rows: ((2, 5, 7), (6, 15, 21)), {side}: ((1, 4, $times 2$),)")
