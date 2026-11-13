"""Typst's plumbing (figures_typst.py): the packages shipped and unpacked once, compiled
offline and cut when too long, the families' rules and preambles, the kinds, the credits."""

import re

import pytest

from figures.support import TRIANGLE, rule_example
from notosaurus_core import figures, figures_typst


def test_a_figure_drawn_in_typst_compiled_offline():
    """Typst with the packages and the font shipped (nothing downloaded): an SVG, black and
    grey, its letters kept by the cleaning (their shapes, used where they go)."""
    svg = figures.clean(figures_typst.compile_svg("geometry", TRIANGLE))
    assert svg.startswith("<svg") and "<use" in svg and "<symbol" in svg  # the letter A
    assert set(re.findall(r'(?:fill|stroke)="(#[0-9a-f]{6})"', svg)) <= {"#000000", "#e1e1e1", "#ffffff"}
    assert figures.to_png(svg)


def test_typst_packages_unpacked_once_from_their_archives():
    """One archive per package (tools/typst_packages.py), each where Typst looks for it
    (preview/<name>/<version>/typst.toml), unpacked once: drawn again, the same folder."""
    archives = sorted(figures_typst.ARCHIVES.glob("*.tar.gz"))
    assert archives and not (figures_typst.ARCHIVES / "preview").exists()
    folder = figures_typst.packages()
    for archive in archives:
        name, version = archive.name.removesuffix(".tar.gz").rsplit("-", 1)
        assert (folder / "preview" / name / version / "typst.toml").is_file()
    stamp = (folder / "preview").stat().st_mtime_ns
    assert figures_typst.packages() == folder and (folder / "preview").stat().st_mtime_ns == stamp
    assert [p.name for p in folder.parent.iterdir() if p.name.startswith("typst-")] == [folder.name]


def test_typst_cut_when_too_long_and_nothing_loaded(monkeypatch):
    import subprocess

    def slow(*args, **kwargs):
        raise subprocess.TimeoutExpired("typst", figures_typst.COMPILE_S)

    for bad in ('read("/etc/passwd")', 'image("x.png")', 'plugin("p.wasm")', '#include "x.typ"', 'eval("read(1)")'):
        with pytest.raises(figures_typst.Unusable):
            figures_typst.source("geometry", bad)
    monkeypatch.setattr(subprocess, "run", slow)
    with pytest.raises(figures_typst.Unusable, match="too long"):
        figures_typst.compile_svg("geometry", TRIANGLE)


def test_the_figures_colours_kept():
    """A figure keeps its colours: a lesson's colour code (an atom's, a legend's) is what the
    card teaches, never turned black."""
    body = "#cetz.canvas({ import cetz.draw: *\n circle((0, 0), radius: 0.8, fill: red) })"
    svg = figures_typst.compile_svg("chemistry", body)
    assert re.search(r'fill="#ff4136"|fill="#ff0000"', svg), svg[:300]


def test_credited_with_what_its_typst_uses():
    """A figure credits the packages its Typst really calls, not all its family imports: a
    model of balls drawn with cetz under the chemistry family is cetz's, not alchemist's."""
    balls = "#cetz.canvas({ import cetz.draw: *\n circle((0, 0), radius: 0.8, fill: red) })"
    formula = '#skeletize({ fragment("CH_3"); single(); fragment("OH") })'
    assert figures_typst.made_with("chemistry", balls)[1:] == ["cetz 0.5.2"]
    assert figures_typst.made_with("chemistry", formula)[1:] == ["alchemist 0.2.0"]
    polar = formula.replace("})", '; charge("fragment-0", "δ+") })')  # our charges, drawn with cetz
    assert sorted(figures_typst.made_with("chemistry", polar)[1:]) == ["alchemist 0.2.0", "cetz 0.5.2"]
    assert figures_typst.made_with("geometry", TRIANGLE)[1:] == ["ctz-euclide 0.3.0"]
    assert figures_typst.made_with("graph", "#lq.diagram(lq.plot((0, 1), (0, 1)))")[1:] == ["lilaq 0.6.0"]
    timeline = "#timeline(start: 1914, end: 1918, events: ((1916, [Verdun]),))"  # our function: what it uses
    assert figures_typst.made_with("timeline", timeline)[1:] == ["cetz 0.5.2"]
    assert figures_typst.made_with("clock", "#clock(10, 25)")[1:] == ["cetz 0.5.2"]
    assert figures_typst.made_with("solid", "#cuboid(3, 3, 3)")[1:] == ["cetz 0.5.2"]
    assert figures_typst.made_with("other", balls) == []


def test_nested_zones_are_no_diagram():
    """fletcher writes a node's text at its centre and draws its boxes side by side: zones
    inside one another (rings, layers) drawn with it hide or pile up their labels (TYP-09h)."""
    assert "never shapes inside one another" in figures_typst.KINDS
    assert "zones nested or overlapping" in figures_typst.KINDS.split('"other"')[1]


def test_a_model_of_balls_is_no_chemistry():
    """The chemistry family draws formulas (its package's): a molecular model of coloured
    balls is "other", said to the AI that picks a figure's kind."""
    assert "never a model of balls" in figures_typst.KINDS and "molecular model" in figures_typst.KINDS


@pytest.mark.parametrize("family", sorted(figures_typst.FAMILIES))
def test_each_familys_rule_example_compiles(family):
    """Each family's Typst (typst_rules/<family>.typ: its preamble, then the example the AI
    is shown) compiles as it is, with the packages shipped: a rule out of step with its
    package (a version changed) shows here."""
    assert figures.clean(figures_typst.compile_svg(family, rule_example(family))).startswith("<svg")


def test_a_drawing_past_its_page_kept_whole():
    """A graph's axis names, written by lilaq past the diagram's ends: the page grown to them
    ("temps (min)", not "te"); a figure within its page the same as Typst made it."""
    body = (
        "#lq.diagram(width: 6cm, height: 4cm, xlim: (0, 15), ylim: (-10, 25),\n"
        "  xaxis: (position: 0, label: [temps (min)]), yaxis: (position: 0, label: [température (°C)]),\n"
        "  lq.plot((0, 4, 10, 14), (20, 0, 0, -10), mark: none))"
    )
    width = float(re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+)', figures_typst.compile_svg("graph", body)).group(1))
    assert width > 6 * 28.35 + 12 + 40  # the diagram, its margins, and "temps (min)" past its end
    cuboid = figures_typst.compile_svg("solid", "#cuboid(5, 3, 2)")
    assert "<rect" not in cuboid.split(">", 1)[1][:200]  # within its page: no ground of ours


def test_each_familys_rule_and_typst_in_their_files():
    """A rule says where its example goes ({example}, once), its Typst where the AI's part
    starts (EXAMPLE, once); the example is in the rule the AI is given."""
    for family, made in figures_typst.FAMILIES.items():
        rule = (figures_typst.RULES / f"{family}.md").read_text(encoding="utf-8")
        typst = (figures_typst.RULES / f"{family}.typ").read_text(encoding="utf-8")
        assert rule.count("{example}") == 1 and typst.count(figures_typst.EXAMPLE) == 1, family
        assert typst.split(figures_typst.EXAMPLE)[1].strip() in made.rules and "{example}" not in made.rules


@pytest.mark.parametrize("family", sorted(figures_typst.FAMILIES))
def test_every_familys_text_in_the_svg_figures_font(family):
    """A figure's text in DejaVu Sans, whichever family draws it: not Typst's own serif."""
    plain = figures_typst.compile_svg(family, '#text("Mi 12")')
    sans = figures_typst.compile_svg(family, '#text(font: "DejaVu Sans", "Mi 12")')
    assert plain == sans


@pytest.mark.parametrize(
    "colour",
    [
        "color.mix(red, blue)",
        "color.mix(green, red, blue)",
        "oklch(60%, 0.15, 200deg)",
        "color.hsl(200deg, 50%, 50%)",
        "color.linear-rgb(20%, 40%, 60%)",
        "color.mix(red, blue).transparentize(40%)",
    ],
)
def test_a_typst_colour_kept_as_typst_makes_it(colour):
    """Typst writes a mixed colour (oklab by default), an oklch, an hsl or a linear RGB as
    CSS's newer functions, which figures.clean drops (a value with brackets): a pH scale's
    bands came out black. Written #rrggbb(aa) instead, Typst's own colour (to-hex), kept by
    the clean and painted."""
    import io

    from PIL import Image

    def filled(body: str) -> list[str]:
        svg = figures.clean(figures_typst.compile_svg("geometry", body))
        return [v for v in re.findall(r'fill="([^"]*)"', svg) if v not in ("#ffffff", "none")]

    rect = "#rect(width: 2cm, height: 1cm, fill: {})"
    assert filled(rect.format(colour)) == filled(rect.format(f"rgb(({colour}).to-hex())")) != []
    png = figures.to_png(figures.clean(figures_typst.compile_svg("geometry", rect.format(colour))))
    middle = Image.open(io.BytesIO(png)).convert("RGB")
    assert middle.getpixel((middle.width // 2, middle.height // 2)) != (0, 0, 0)


def test_a_figure_credits_the_typst_that_drew_it():
    """Typst's own version, the compiler typst-py ships: typst-py 0.15.2 ships Typst 0.15.1,
    there is no Typst 0.15.2 to credit."""
    import json

    import typst

    engine = json.loads(typst.query(b"#metadata(str(sys.version)) <v>", "<v>", field="value"))[0]
    assert figures_typst.made_with("clock", "#clock(10, 25)")[0] == f"Typst {engine}"


def test_typsts_message_read_whole_whatever_the_systems_encoding(monkeypatch):
    """Typst's message is told to the AI to correct the figure. Its process wrote it in the
    system's encoding (cp1252 on Windows): "…" or "δ" came out as "\\ufffd". Written in
    UTF-8 as it is read, whatever the encoding."""
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")  # Windows' console
    with pytest.raises(figures_typst.Unusable) as refused:
        figures_typst.compile_svg("geometry", '#assert(false, message: "pas O…N, ni δ, ni é")')
    assert "pas O…N, ni δ, ni é" in str(refused.value)
