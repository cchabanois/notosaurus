"""The diagram family (fletcher, our tree and network): texts, labels and vertices placed."""

import math
import re

import pytest

from figures.support import _glyphs, drawn_size
from notosaurus_core import figures_typst, typst_source


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


CM = 72 / 2.54  # pt


@pytest.mark.parametrize(
    "body",
    [
        # four boxes of two lines on a row (a chain of steps): 22 cm wide
        '#diagram(spacing: 2em, node((0, 0), [Entrée du microbe\ndans l\'organisme]), edge("-|>"),'
        ' node((1, 0), [Réaction innée\n(inflammation, phagocytose)]), edge("-|>"),'
        ' node((2, 0), [Réaction adaptative\n(lymphocytes B et T)]), edge("-|>"),'
        " node((3, 0), [Mémoire immunitaire]))",
        # a bracket glued to its word: a place to break, the column narrowed too
        '#diagram(node((0, 0), [Antigène présenté]), edge("-|>"), node((1, 0), [Lymphocytes T4(auxiliaires)]),'
        ' edge("-|>"), node((2, 0), [Plasmocytes(anticorps)]), edge("-|>"),'
        " node((3, 0), [Lymphocytes T cytotoxiques(destruction des cellules infectées)]))",
    ],
)
def test_a_wide_diagram_fits_a_card(body):
    """A row of boxes of long texts made a diagram 16 to 22 cm wide: shrunk to a phone's card,
    its text unreadable. Its widest columns narrowed, their texts on more lines, toward 12 cm,
    never narrower than a column's longest word (four columns of "(inflammation," and
    "l'organisme": about 15 cm)."""
    assert _svg_width(figures_typst.compile_svg("diagram", body)) < 16 * CM


def test_a_narrow_diagram_as_it_was():
    """A diagram that fits a card keeps its boxes as wide as their texts."""
    body = '#diagram(node((0, 0), [Pile]), edge("-|>"), node((1, 0), [Lampe]), edge("-|>"), node((2, 0), [Moteur]))'
    one = _svg_width(figures_typst.compile_svg("diagram", body))
    assert one < 200


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


# Boxes joined every which way (elected, appointed, controlled; one arrow each way between two;
# one going past a layer; a box no arrow joins): institutions, as the AI drew them with nodes
# and edges, 26 cm wide, their arrows crossed and their words on one another
SCHEME = (
    '#set text(lang: "fr")\n'
    "#let boxes = (a: [Électeurs du pays], b: [Chef de l'État \\ (le premier personnage)], "
    "c: [Gouvernement et ses ministres], d: [Assemblée des représentants], e: [Seconde chambre], "
    "f: [Cour suprême], g: [Conseil économique])\n"
    '#let arrows = (("a", "b", [élisent pour 7 ans]), ("a", "d", [élisent]), ("b", "c", [nomme]), '
    '("b", "d", [peut dissoudre]), ("d", "c", [contrôle]), ("c", "d", [responsable devant]), '
    '("e", "c", [contrôle]), ("f", "d", [juge ses lois], "--"))\n'
)

APART = """#context {
  let l = _sch-layout(boxes, arrows, "up")
  let solids = l.boxes.map(b => b.at(0)) + l.words.filter(w => w != none).map(w => w.at(0))
  for (i, a) in solids.enumerate() {
    for b in solids.slice(i + 1) { assert(not _sch-meet(a, b), message: "overlap " + repr((a, b))) }
  }
  let names = boxes.keys()
  for (k, (pts, style)) in l.arrows.enumerate() {
    let own = l.words.at(k)
    for i in range(pts.len() - 1) {
      for r in solids {
        if own != none and r == own.at(0) { continue }
        assert(not _sch-hits(pts.at(i), pts.at(i + 1), _sch-grow(r, -1)), message: "arrow " + str(k))
      }
    }
    // its ends on its boxes' sides
    for (p, name) in ((pts.first(), arrows.at(k).at(0)), (pts.last(), arrows.at(k).at(1))) {
      let (x0, y0, x1, y1) = l.boxes.at(names.position(n => n == name)).at(0)
      let side = calc.abs(p.at(1) - y0) < 0.01 or calc.abs(p.at(1) - y1) < 0.01
      assert(x0 <= p.at(0) and p.at(0) <= x1 and side, message: "arrow " + str(k) + " end")
    }
  }
  [ok]
}"""


def test_a_scheme_lays_its_boxes_arrows_and_words_apart():
    """A scheme's places computed: no box or words on another, no arrow through a box or
    through another arrow's words (its own words on it), each arrow from its box to its box."""
    figures_typst.compile_svg("diagram", SCHEME + APART)


UNCROSSED = """#context {
  let l = _sch-layout(boxes, arrows, "down")
  let segs = ()
  for (k, (pts, s)) in l.arrows.enumerate() {
    for i in range(pts.len() - 1) { segs.push((k, pts.at(i), pts.at(i + 1))) }
  }
  let d(a, b, c) = (b.at(0) - a.at(0)) * (c.at(1) - a.at(1)) - (b.at(1) - a.at(1)) * (c.at(0) - a.at(0))
  for (i, (k, p, q)) in segs.enumerate() {
    for (k2, r, s) in segs.slice(i + 1) {
      let crossed = d(p, q, r) * d(p, q, s) < 0 and d(r, s, p) * d(r, s, q) < 0
      assert(k == k2 or not crossed, message: "crossing")
    }
  }
  [ok]
}"""


def test_a_schemes_arrows_cross_only_where_they_must():
    """Boxes given in an order that crosses their arrows (each one's children the other's):
    ordered by the layout, layer by layer, none crossing."""
    body = (
        "#let boxes = (r: [Racine], a: [Gauche], b: [Droite], c: [Fille de droite], d: [Fille de gauche])\n"
        '#let arrows = (("r", "a"), ("r", "b"), ("a", "d"), ("b", "c"))\n'
    )
    figures_typst.compile_svg("diagram", body + UNCROSSED)


def test_a_scheme_fits_a_card():
    """Seven boxes and eight arrows with their words: within a phone's card (320 × 400) at
    the text's own size, never shrunk to unreadable."""
    body = SCHEME + '#scheme(boxes: boxes, arrows: arrows, flow: "up")'
    width, height = drawn_size("diagram", body)
    assert width <= 320 and height <= 400
    svg = figures_typst.compile_svg("diagram", body)
    assert figures_typst.readable_px(svg, body) >= 9


def test_a_schemes_wide_layer_goes_on_below():
    """Six boxes under one: more than a card's width side by side, some on a layer below."""
    boxes = "#let boxes = (o: [Organisation des pays du monde]"
    boxes += "".join(f", p{i}: [Organe principal numéro {i}]" for i in range(6)) + ")\n"
    arrows = "#let arrows = (" + ", ".join(f'("o", "p{i}", "-")' for i in range(6)) + ")\n"
    layers = """#context {
  let l = _sch-layout(boxes, arrows, "down")
  let tops = l.boxes.map(b => calc.round(b.at(0).at(1))).dedup()
  assert(tops.len() >= 3, message: repr(tops))
  [ok]
}"""
    figures_typst.compile_svg("diagram", boxes + arrows + layers)
    width, _ = drawn_size("diagram", boxes + arrows + "#scheme(boxes: boxes, arrows: arrows)")
    assert width <= 320


def test_an_arrow_from_a_box_to_itself_refused():
    """An arrow from a box to itself (an assembly that votes): drawn over the box, its words on
    the box's name. Refused, told why, in a scheme and in nodes and edges (a graph's loop: network)."""
    looped = '#scheme(boxes: (a: [A], b: [B]), arrows: (("a", "a", [vote]), ("a", "b")))'
    with pytest.raises(figures_typst.Unusable, match="itself"):
        figures_typst.compile_svg("diagram", looped)
    with pytest.raises(figures_typst.Unusable, match="itself"):
        figures_typst.compile_svg("diagram", '#diagram(node((0, 0), [A]), edge((0, 0), (0, 0), "-|>", [vote]))')
    network = '#network(vertices: ("A", "B"), edges: (("A", "A"), ("A", "B")), directed: true)'
    figures_typst.compile_svg("diagram", network)


def test_a_diagram_too_small_to_read_refused():
    """A diagram whose text, fitted to a phone's card, is too small to read (a row of boxes
    and long words on its arrows: 3 px): refused, told its size and how to draw it compactly;
    its drawing kept with the refusal. The same on two rows: drawn."""
    row = ", ".join(
        f'node(({i}, 0), [Une étape numéro {i} du processus]), edge("-|>", [ce qui passe de {i} à la suivante])'
        for i in range(5)
    )
    with pytest.raises(figures_typst.TooSmall, match="px high") as refused:
        figures_typst.compile_svg("diagram", f"#diagram({row}, node((5, 0), [Fin]))")
    assert refused.value.px < figures_typst.MIN_TEXT_PX and "<svg" in refused.value.svg
    rows = (
        '#diagram(node((0, 0), [Une étape]), edge("-|>", [passe à]), node((1, 0), [La suivante]),'
        ' edge("-|>"), node((1, 1), [Fin]))'
    )
    figures_typst.compile_svg("diagram", rows)


def test_smallest_text():
    assert typst_source.smallest_text("#diagram(node((0, 0), [A]))") == 11
    assert typst_source.smallest_text("node((0, 0), [A \\ #text(size: 0.75em)[b]])") == 11 * 0.75
    assert typst_source.smallest_text("#set text(size: 9pt)\n#text(size: 0.8em)[b]") == pytest.approx(7.2)


def test_a_schemes_arrows_closing_a_loop_go_back():
    """Arrows around loops (two chambers elect a head, who appoints ministers, who answer to
    both): the arrows that close them, given last, go back between the same layers; the
    boxes in the order the arrows go, both chambers side by side (followed from the first box,
    the second chamber, reached through the ministers, went above them)."""
    body = (
        "#let boxes = (a: [Électeurs], b: [Chambre], s: [Seconde chambre], c: [Chef], d: [Ministres])\n"
        '#let arrows = (("a", "b", [élisent]), ("b", "c", [élit]), ("s", "c", [élit]), ("c", "d", [nomme]),'
        ' ("d", "b", [répond devant]), ("d", "s", [répond devant]))\n'
    )
    check = """#context {
  let l = _sch-layout(boxes, arrows, "down")
  let (a, b, s, c, d) = l.boxes.map(b => b.at(0).at(1))
  assert(a < b and b == s and s < c and c < d, message: repr((a, b, s, c, d)))
  // the last arrows from the lowest box up
  for k in (4, 5) {
    let pts = l.arrows.at(k).at(0)
    assert(pts.first().at(1) > pts.last().at(1))
  }
  [ok]
}"""
    figures_typst.compile_svg("diagram", body + check)


def test_a_schemes_words_of_no_letter_are_none():
    """An arrow's words written as a dash ([-], "no words"): no words drawn on it."""
    body = """#context {
  let l = _sch-layout((a: [A], b: [B]), (("a", "b", [-]), ("b", "a", [ — ])), "down")
  assert(l.words.all(w => w == none))
  [ok]
}"""
    figures_typst.compile_svg("diagram", body)
