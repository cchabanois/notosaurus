"""What every family's preamble shares (typst_rules/common.typ): numbers written once, as the
figure's language writes them, and round graduation steps for any size of values."""

import json

import pytest
import typst

from notosaurus_core import figures_typst


def _value(tmp_path, expression: str, separator: str = "."):
    """What common.typ computes, read back (a Typst value, as JSON)."""
    common = (figures_typst.RULES / "common.typ").read_text(encoding="utf-8")
    page = tmp_path / "query.typ"
    page.write_text(
        common.replace(figures_typst.SEPARATOR, f'#let decimal-separator = "{separator}"')
        + f"\n#metadata({expression}) <value>\n",
        encoding="utf-8",
    )
    return json.loads(typst.query(str(page), "<value>", field="value", one=True, format="json"))


def test_every_family_gets_its_decimal_separator_from_common():
    """One separator, set by figures_typst.source in one place: a family defining its own would
    keep a point in French."""
    for name, family in figures_typst.FAMILIES.items():
        typ = (figures_typst.RULES / f"{name}.typ").read_text(encoding="utf-8")
        assert "#let decimal-separator" not in typ, name
        if "decimal-separator" in typ or "written-number(" in typ:
            assert figures_typst.SHARED in typ and figures_typst.SEPARATOR in family.preamble, name


@pytest.mark.parametrize(
    ("x", "options", "separator", "written"),
    [
        (0.5, "", ",", "0,5"),
        (0.5, "", ".", "0.5"),
        (3 * 0.1, "", ",", "0,3"),  # 0.30000000000000004 as Typst's str writes it
        (-2, "", ",", "−2"),
        (-0.0000001, "", ",", "0"),  # no "−0"
        (3, "digits: 1, zeros: true", ",", "3,0"),
        (2.96, "digits: 1", ",", "3"),
        (-1.25, "digits: 2, zeros: true", ".", "−1.25"),
        (9999, "", ",", "9999"),
        (2500000, "", ",", "2 500 000"),
        (12345.5, "", ",", "12 345,5"),
    ],
)
def test_a_number_written_as_the_language_writes_it(tmp_path, x, options, separator, written):
    args = f"{x!r}" + (f", {options}" if options else "")
    assert _value(tmp_path, f"written-number({args})", separator) == written


@pytest.mark.parametrize(
    ("span", "most", "step"),
    [(10, 10, 1), (8, 10, 1), (25, 10, 2.5), (2500000, 10, 250000), (90000, 8, 20000), (0.05, 10, 0.005)],
)
def test_a_round_step_for_any_size_of_values(tmp_path, span, most, step):
    """A city's inhabitants (millions) as well as a probability (hundredths): the steps once
    stopped at 10 000 and started at 0,1."""
    assert _value(tmp_path, f"round-step({span}, {most})") == pytest.approx(step)


def test_a_line_chart_of_millions_draws():
    """A population over the years: the graduation's step once came back none past 80 000."""
    body = '#chart(kind: "line", values: ((1990, 1200000), (2000, 1900000), (2010, 2500000)))'
    assert figures_typst.compile_svg("chart", body).startswith("<svg")


@pytest.mark.parametrize(
    ("family", "body"),
    [
        (
            "geometry",
            "#ctz-canvas({ ctz-init()\n"
            " ctz-draw-axes(xmin: -1, xmax: 1.5, ymin: -1, ymax: 1.5, xstep: 0.5, ystep: 0.5) })",
        ),
        ("mechanics", '#mechanics(support: "plane", vectors: (("F", 30.5),), marked: ("F",))'),
    ],
)
def test_numbers_the_preamble_computes_follow_the_language(family, body):
    """An axis's 0,5 and a marked angle's 30,5° were written with a point in French."""
    french, english = (figures_typst.compile_svg(family, f'#set text(lang: "{lang}")\n{body}') for lang in ("fr", "en"))
    assert french != english
