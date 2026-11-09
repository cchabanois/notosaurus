"""tools/bench_figures.py: hidden labels counted, a run compiled again."""

from figures.support import SQUARE, rule_example
from notosaurus_core import figures, figures_typst

# Rings drawn as nested nodes, each label at its centre (TYP-09h): the inner fills cover
# the outer ones' labels
RINGS = """#diagram(node-stroke: 0.8pt,
  node((0, 0), [Périurbain], shape: circle, fill: luma(245), radius: 3cm),
  node((0, 0), [Banlieue], shape: circle, fill: luma(225), radius: 2cm),
  node((0, 0), [Ville], shape: circle, fill: rgb("#ffe066"), radius: 1cm),
)"""


def test_the_figures_bench_sees_hidden_labels():
    """tools/bench_figures.py: a label under a filled shape drawn after it, or outside the
    picture, counted and the figure judged wrong; seen, not (the rules' examples: none hidden)."""
    import sys

    sys.path.insert(0, str(figures_typst.HERE.parent.parent / "tools"))
    import bench_figures

    def hidden(svg):
        svg = figures.clean(svg)
        return bench_figures.hidden_labels(svg, figures.to_png(svg))

    rings = figures.clean(figures_typst.compile_svg("diagram", RINGS))
    assert hidden(rings) == 2
    assert bench_figures.by_code(rings)[:2] == (False, "2 label(s) hidden (under a shape, or outside the picture)")
    assert hidden(SQUARE) == 0
    assert hidden(SQUARE.replace("</svg>", '<rect width="400" height="300" fill="white"/></svg>')) == 1
    assert hidden(SQUARE.replace("</svg>", '<text x="900" y="40">B</text></svg>')) == 1
    assert hidden(SQUARE.replace(">A<", ' font-size="4">i<')) == 0  # tiny, but seen
    for family in figures_typst.FAMILIES:
        assert hidden(figures_typst.compile_svg(family, rule_example(family))) == 0, family


def test_the_figures_bench_compiles_a_run_again(tmp_path):
    """tools/bench_figures.py --recompile: a drawing's Typst compiled again with today's
    preamble, an SVG drawing kept as it was, one not drawn said so."""
    import sys

    sys.path.insert(0, str(figures_typst.HERE.parent.parent / "tools"))
    import bench_figures

    (tmp_path / "a-1.typ").write_text('#timeline(start: 1780, end: 1800, events: ((1789, "Bastille"),))')
    (tmp_path / "b-1.svg").write_text(SQUARE)
    typst = bench_figures.recompiled(tmp_path, {"family": "timeline", "typst_file": "a-1.typ", "file": "a-1.svg"})
    assert typst["engine"] == "typst" and typst["svg"].startswith("<svg") and "Bastille" in typst["typst"]
    assert bench_figures.recompiled(tmp_path, {"family": "diagram", "file": "b-1.svg"})["svg"] == SQUARE
    assert bench_figures.recompiled(tmp_path, {"problem": "500 Internal"}) == {"error": "500 Internal"}
