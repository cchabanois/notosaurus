"""What source() makes of the AI's Typst (typst_source.py) before compiling it: imports dropped, a diagram's
marks and new lines as meant, numbers as the figure's language writes them, symbols left
symbols, fractional columns sized, a circuit's ends made to meet."""

import pytest

from notosaurus_core import figures, figures_typst


def test_a_package_import_dropped_not_refused():
    """The AI imports its family's package again (the preamble gives it): the line dropped, the
    figure compiled at once, no call lost. A file's import or include still refused."""
    typst = (figures_typst.RULES / "graph.typ").read_text(encoding="utf-8")
    example = typst.split(figures_typst.EXAMPLE)[1]
    again = '#import "@preview/lilaq:0.6.0" as lq\n' + example
    assert figures_typst.source("graph", again).count('#import "@preview/lilaq') == 1  # the preamble's
    assert figures.clean(figures_typst.compile_svg("graph", again)).startswith("<svg")
    for refused in ('#import "rules.typ"\n', '#include "x.typ"\n', '#import "/etc/x.typ": *\n'):
        with pytest.raises(figures_typst.Unusable):
            figures_typst.source("graph", refused + example)


def test_a_diagrams_two_bars_drawn_as_an_arrow():
    """The AI writes "-||" for an arrow (two bars, which no school diagram asks for): drawn as
    "-|>", the arrow it meant."""
    arrow = '#diagram(node((0, 0), [A]), edge("{}"), node((1, 0), [B]))'
    assert figures_typst.compile_svg("diagram", arrow.format("-||")) == figures_typst.compile_svg(
        "diagram", arrow.format("-|>")
    )


@pytest.mark.parametrize(
    ("written", "meant"),
    [("-|-", "-"), ("-|->", "-|>"), ("<-|-", "<|-"), ("<-|->", "<|-|>"), ("--|--", "--"), ("<|-|>", "<|-|>")],
)
def test_a_diagrams_barred_line_drawn_plain(written, meant):
    """The AI writes a bar across a line ("-|-" between two characters, "-|->" a flowchart's
    "oui"), which no school diagram asks for: drawn as the line it meant, never dashed by
    the bar's removal, its head the filled one as every arrow's; a head's bar ("<|", "|>") kept."""
    link = '#diagram(node((0, 0), [A]), edge("{}"), node((1, 0), [B]))'
    assert figures_typst.compile_svg("diagram", link.format(written)) == figures_typst.compile_svg(
        "diagram", link.format(meant)
    )


@pytest.mark.parametrize(
    ("written", "meant"),
    [(r"[Accord avec\nle sujet]", r"[Accord avec\ le sujet]"), (r"[avant\le verbe]", r"[avant\ le verbe]")],
)
def test_a_diagrams_new_line_written_as_a_strings_drawn(written, meant):
    """The AI writes a node's new line as a string's ("\\n") or glues the "\\" to the next word:
    Typst's markup only escaped the letter ("avecnle sujet"); drawn as the line break meant."""
    node = "#diagram(node((0, 0), {}))"
    assert figures_typst.compile_svg("diagram", node.format(written)) == figures_typst.compile_svg(
        "diagram", node.format(meant)
    )


def test_a_diagrams_strings_and_maths_left_as_written():
    """A string's "\\n" (a new line already), a code's escape and a text's maths untouched."""
    body = r'#diagram(node((0, 0), "A\nB"), edge("-|>", [$\u{3b1}$ et \#1]), node((1, 0), [B]))'
    assert figures_typst.source("diagram", body).endswith(body + "\n")


@pytest.mark.parametrize(
    ("family", "body"),
    [
        (
            "graph",
            "#let xs = lq.linspace(0, 0.25, num: 20)\n"
            "#lq.diagram(width: 6cm, height: 4cm, xlim: (0, 0.26), ylim: (0, 12), lq.plot(xs, xs.map(x => 50 * x)))",
        ),
        ("chart", '#chart(kind: "line", values: ((0, 0.5), (1, 1.5), (2, 2.5)), written: (1,))'),
    ],
)
def test_a_figures_numbers_written_as_its_language_writes_them(family, body):
    """The numbers a preamble writes itself (an axis's, a chart's values): with the decimal
    separator of the language the AI says the figure is in (a comma in French, German…), a
    point in English and when it says none, never one for every language."""
    said = lambda lang: f'#set text(lang: "{lang}")\n{body}'  # noqa: E731
    assert '#let decimal-separator = ","' in figures_typst.source(family, said("fr"))
    assert '#let decimal-separator = "."' in figures_typst.source(family, said("en"))
    french, german = (figures_typst.compile_svg(family, said(lang)) for lang in ("fr", "de"))
    english, unsaid = figures_typst.compile_svg(family, said("en")), figures_typst.compile_svg(family, body)
    assert french == german != english == unsaid


def test_a_decimal_comma_in_maths_drawn_tight():
    """Typst's maths spaces a comma out ("0, 3"): a decimal one quoted, tight; LaTeX's `0{,}3`
    (the AI writing LaTeX) whatever the language, a comma between digits only in a language
    writing a decimal comma (an English list "1,2" left as written)."""
    body = '#diagram(node((0, 0), [A]), edge("-", [$0{,}3$ et $0,7$]), node((1, 0), [B]))'
    french = figures_typst.source("diagram", '#set text(lang: "fr")\n' + body)
    english = figures_typst.source("diagram", '#set text(lang: "en")\n' + body)
    assert '$0","3$ et $0","7$' in french
    assert '$0","3$ et $0,7$' in english
    # a number the AI quoted itself (`$times "1,5"$`): text already, left whole, never cut in
    # two strings drawn "1, 5"
    quoted = figures_typst.source("diagram", '#set text(lang: "fr")\n' + body.replace("0,7", 'times "1,5"'))
    assert '$times "1,5"$' in quoted


def test_an_arrow_written_with_html_entities_drawn():
    """The AI writes an arrow's ">" as HTML does ("-|&gt;"): Typst refused it twice, the
    figure drawn as SVG instead; read as ">" (Typst has no such entity)."""
    body = '#diagram(node((0, 0), [A]), edge("-|&gt;"), node((1, 0), [B]), edge("&lt;|-"), node((2, 0), [C]))'
    assert figures_typst.compile_svg("diagram", body).startswith("<svg")


@pytest.mark.parametrize("name", ["lambda", "pi", "Delta"])
def test_a_variable_named_like_a_symbol_leaves_the_symbol_in_formulas(name):
    """`#let lambda = 1.5`, then `$lambda$` for the arrow's name: Typst read the variable,
    "1.5" written where λ was meant (a wavelength). The variable renamed where code reads it:
    the formula's name is the symbol again; `#lambda` in it, and the code, keep its value."""
    with_variable = f"#let {name} = 1.5\n$x = {name}$ #box(width: {name} * 1cm)"
    meant = f"#let other = 1.5\n$x = {name}$ #box(width: other * 1cm)"
    assert figures_typst.compile_svg("graph", with_variable) == figures_typst.compile_svg("graph", meant)
    value = f"#let {name} = 1.5\n$#{name}$"
    assert figures_typst.compile_svg("graph", value) == figures_typst.compile_svg("graph", "$1.5$")
    # a word in a text, a field (calc.pi) and a longer name untouched
    text = f"#let {name} = 1\n#text[le mot {name}] #calc.pi #let {name}-max = 2"
    assert f"le mot {name}]" in figures_typst.source("graph", text) and "calc.pi" in figures_typst.source("graph", text)


def test_a_grids_fractional_columns_sized_by_their_content():
    """Four molecules in a grid of `1fr` columns: a figure's page is as wide as what it holds,
    so the columns had no width, the molecules drawn one on another. Sized by their content:
    the same figure as `auto` columns; a fraction elsewhere (`h(1fr)`) left as written."""
    molecule = '[#skeletize({{ fragment("CH_3"); single(); fragment("{}") }}) \\ {}]'
    cells = ", ".join(molecule.format(g, n) for g, n in (("OH", "Éthanol"), ("CHO", "Éthanal")))
    grid = "#grid(columns: COLUMNS, column-gutter: 2em, " + cells + ")"
    fractions = figures_typst.compile_svg("chemistry", grid.replace("COLUMNS", "(1fr, 1fr)"))
    assert fractions == figures_typst.compile_svg("chemistry", grid.replace("COLUMNS", "(auto, auto)"))
    assert "#h(1fr)" in figures_typst.source("chemistry", "#h(1fr)")


def test_an_edges_unreadable_marks_still_an_arrow():
    """The AI writes the arrow as marks fletcher can't read ("-|Side", "-|_", "-|/"), the whole
    figure refused. Drawn as the rule's arrow, or left out where the edge has its marks
    already; fletcher's own marks kept."""
    edge = "#diagram(node((0, 0), [Solide]), node((2, 0), [Liquide]), edge((0, 0), (2, 0), {}, [fusion]))"
    arrow = figures_typst.compile_svg("diagram", edge.format('"-|>"'))
    for slip in ('"-|Side"', '"-|_"', '"-| >"', '"-|/"'):
        assert figures_typst.compile_svg("diagram", edge.format(slip)) == arrow
    assert figures_typst.compile_svg("diagram", edge.format('"-|Side-shift", "-|>"')) == arrow
    both = figures_typst.compile_svg("diagram", edge.format('"<|-|>"'))
    assert figures_typst.compile_svg("diagram", edge.format('"<|-Cli"')) == both
    marked = figures_typst.compile_svg("diagram", edge.format('marks: (none, "head")'))
    assert figures_typst.compile_svg("diagram", edge.format('"-|Side-shift:none", marks: (none, "head")')) == marked
    assert '"-hook->"' in figures_typst.source("diagram", edge.format('"-hook->"'))


def test_two_arrows_each_way_have_their_labels_apart():
    """Two arrows each way between two nodes, shifted aside: each label on its shift's side,
    away from the other arrow, whatever side the AI wrote (its two labels meeting between them)."""
    pair = (
        "#diagram(node((0, 0), [Solide]), node((1, 1), [Gaz]), "
        'edge((0, 0), (1, 1), "-|>", [sublimation], shift: 4pt, label-side: {}), '
        'edge((1, 1), (0, 0), "-|>", [condensation], shift: 4pt, label-side: {}))'
    )
    apart = figures_typst.compile_svg("diagram", pair.format("left", "left"))
    assert figures_typst.compile_svg("diagram", pair.format("right", "right")) == apart
    assert "label-side: right" in figures_typst.source("diagram", pair.replace("4pt", "-4pt").format("left", "left"))


def test_a_circuits_ends_a_hair_apart_meet():
    """An arrow written 0.1 short of the switch and the lamp it goes between: the wire cut there,
    the circuit open. Its ends moved onto theirs, drawn as when they meet; a shape drawn with
    cetz near the circuit left where it is."""
    circuit = (
        '#circuit({{ battery("g", (0, 0), (0, 4)); wire((0, 4), (2, 4)); '
        'switch("k", (2, 4), (2, 2.5), closed: true); {} lamp("l", (2, 1.7), (2, 0)); wire((2, 0), (0, 0)); '
        "cetz.draw.circle((2.1, 0.5), radius: 0.05) }})"
    )
    apart = figures_typst.source("circuit", circuit.format("current-arrow((2, 2.4), (2, 1.8), $I$);"))
    meeting = figures_typst.source("circuit", circuit.format("current-arrow((2, 2.5), (2, 1.7), $I$);"))
    assert apart == meeting and "(2.1, 0.5)" in apart
