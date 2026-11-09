"""The diagram family (fletcher, our tree and network): texts, labels and vertices placed."""

import math
import re

import pytest

from figures.support import _glyphs, drawn_size
from notosaurus_core import figures_typst


def test_a_diagrams_long_text_goes_on_the_next_line():
    """A node's long text, its newlines only spaces in Typst: wrapped, not one line that makes
    the whole diagram tiny; a short one as it was."""
    width = lambda svg: float(re.search(r'width="([\d.]+)', svg).group(1))  # noqa: E731
    text = "Le trésor est retrouvé\ngrâce à Ben Gunn sur l'île, après la mutinerie de Long John Silver"
    long = figures_typst.compile_svg("diagram", f"#diagram(node((0, 0), [{text}]))")
    assert width(long) < 160  # pt: 4.5cm and its stroke and margins
    short = figures_typst.compile_svg("diagram", "#diagram(node((0, 0), [Le trésor]))")
    assert width(short) < 80


def _svg_width(svg: str) -> float:
    return float(re.search(r'width="([\d.]+)', svg).group(1))


def test_a_diagrams_arrow_labels_clear_of_its_boxes():
    """An arrow's label longer than the gap the AI gave its two boxes lay on them: the gap
    widened to the label (its width along a row, beside an arrow going down, and both for a
    slanting one in the middle of a cycle); a short label leaves the gap as given."""
    label = "énergie lumineuse utile"
    alone = _svg_width(figures_typst.compile_svg("diagram", f"#diagram(node((0, 0), [{label}]))"))
    chain = '#diagram(spacing: 1em, node((0, 0), [Pile]), edge("-|>", {}), node((1, 0), [Lampe]))'
    bare = _svg_width(figures_typst.compile_svg("diagram", chain.format("")))
    labelled = _svg_width(figures_typst.compile_svg("diagram", chain.format(f"[{label}]")))
    assert labelled - bare > alone - 20  # pt: the label's width (the node's alone, its inset and stroke)
    wide = chain.replace("1em", "3em")  # wide enough for a short label: as given
    assert _svg_width(figures_typst.compile_svg("diagram", wide.format("[a]"))) == _svg_width(
        figures_typst.compile_svg("diagram", wide.format(""))
    )
    # a cycle: a label beside an arrow going down and one on the slanting arrow, the same gap
    cycle = (
        "#diagram(spacing: 1em, node((0, 0), [A]), node((1, 0), [B]), node((0, 1), [C]),"
        ' edge((0, 1), (0, 0), "-|>", [Évaporation]), edge((1, 0), (0, 1), "-|>", [Ruissellement]))'
    )
    word = _svg_width(figures_typst.compile_svg("diagram", "#diagram(node((0, 0), [Ruissellement]))"))
    assert _svg_width(figures_typst.compile_svg("diagram", cycle)) > 2 * word


def test_the_diagram_rules_edges_compile():
    """Every edge the diagram rule shows (its line styles, a label on its arrow, two arrows
    side by side) compiles between two nodes: a fragment out of step with fletcher (a "bend"
    inside the marks: refused 3 times) would make every diagram with it fail."""
    rules = figures_typst.FAMILIES["diagram"].rules
    edges = re.findall(r"`(edge\([^`]*\))`", rules)
    assert len(edges) >= 2
    for edge in edges:
        body = f"#diagram(node((0, 0), [A]), node((1, 0), [B]), node((0, 1), [C]), {edge})"
        assert figures_typst.compile_svg("diagram", body).startswith("<svg"), edge


def test_a_probability_tree_as_wide_as_it_is_high():
    """A tree's places computed (three Bernoulli trials, eight leaves: placed by the AI, a strip
    three times as high as wide, unreadable once fitted, 3 drawings in 3): about as wide as high.
    A branch not (name, label) or (name, label, branches): refused, saying how."""
    two = "(($S$, [0,3]{0}), ($E$, [0,7]{0}))"
    body = "#tree" + two.format(", " + two.format(", " + two.format("")))
    width, height = drawn_size("diagram", body)
    assert 0.6 < width / height < 1.6
    with pytest.raises(figures_typst.Unusable, match="each branch"):
        figures_typst.compile_svg("diagram", '#tree(("A", [0,4], "B"), "C")')


def test_a_networks_vertices_placed_so_that_no_edges_cross():
    """A graph of graph theory: its vertices placed by the AI's eye (drawn by hand 2 times in 3),
    now on a circle in the order that crosses the fewest edges, not the order they are listed
    in (A, B, C, D, E around it crosses three times here; A, B, D, E, C none). The rule's own
    call compiles; an edge naming no vertex is refused, saying which."""
    rule = (figures_typst.RULES / "diagram.md").read_text(encoding="utf-8")
    call = re.search(r"`(#network\(.*?\))`", rule)
    assert call and figures_typst.compile_svg("diagram", call[1]).startswith("<svg")
    edges = [("A", "B"), ("A", "C"), ("B", "C"), ("B", "D"), ("C", "D"), ("C", "E"), ("D", "E")]
    body = '#network(vertices: ("A", "B", "C", "D", "E"), edges: ({}))'.format(
        ", ".join(f'("{a}", "{b}")' for a, b in edges)
    )
    names = _glyphs(figures_typst.compile_svg("diagram", body))  # the vertices' names, A to E
    assert len(names) == 5
    cx, cy = sum(x for x, _ in names) / 5, sum(y for _, y in names) / 5
    around = sorted(range(5), key=lambda i: math.atan2(names[i][1] - cy, names[i][0] - cx))
    at = {"ABCDE"[v]: around.index(v) for v in range(5)}
    chords = [tuple(sorted((at[a], at[b]))) for a, b in edges]
    crossing = [
        (p, q)
        for i, p in enumerate(chords)
        for q in chords[i + 1 :]
        if len({*p, *q}) == 4 and (p[0] < q[0] < p[1]) != (p[0] < q[1] < p[1])
    ]
    assert crossing == []
    with pytest.raises(figures_typst.Unusable, match="not one of the vertices"):
        figures_typst.compile_svg("diagram", '#network(vertices: ("A", "B"), edges: (("A", "C"),))')


def test_a_networks_weights_never_on_one_another():
    """Two edges crossing in their middles (a complete graph's diagonals): their weights moved
    along them, apart, never written one on the other."""
    edges = '("A", "B", [1]), ("A", "C", [2]), ("A", "D", [3]), ("B", "C", [4]), ("B", "D", [5]), ("C", "D", [6])'
    svg = figures_typst.compile_svg("diagram", f'#network(vertices: ("A", "B", "C", "D"), edges: ({edges}))')
    weights = _glyphs(svg)[4:]
    assert len(weights) == 6
    assert min(math.dist(p, q) for i, p in enumerate(weights) for q in weights[i + 1 :]) > 10  # pt
