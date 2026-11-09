"""What the figure tests share: a figure drawn as SVG (SQUARE) and one in Typst (TRIANGLE), a
family's rule example as it compiles, where a Typst SVG's texts are drawn, a drawing's size."""

import re

from notosaurus_core import figures_typst

SQUARE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">'
    '<rect width="400" height="300" fill="white"/><text x="20" y="40">A</text></svg>'
)


TRIANGLE = """#ctz-canvas({
  ctz-init()
  ctz-def-points(A: (0, 0), B: (4, 0), C: (2, 3))
  ctz-draw-polygon("A", "B", "C")
  ctz-draw-angle("A", "B", "C", radius: 0.6)
  ctz-draw-labels(A: "below left")
})"""


def rule_example(family):
    """The example a family's rule shows the AI (typst_rules/<family>.typ), as it compiles:
    geometry's "and so on" a triangle drawn, its points alone drawing nothing."""
    typst = (figures_typst.RULES / f"{family}.typ").read_text(encoding="utf-8")
    return typst.split(figures_typst.EXAMPLE)[1].replace("  ...\n", '  ctz-draw-polygon("A", "B", "C")\n')


def _glyphs(svg: str) -> list[tuple[float, float]]:
    """Where each text run of a Typst SVG is drawn (x, its baseline's y), its groups' moves added."""
    stack, glyphs = [(0.0, 0.0)], []
    for tag in re.findall(r"<g(?:\s[^>]*)?>|</g>", svg):
        if tag == "</g>":
            stack.pop()
            continue
        x, y = stack[-1]
        if moved := re.search(r'transform="translate\(([-\d.]+)(?:[ ,]([-\d.]+))?\)"', tag):
            x, y = x + float(moved[1]), y + float(moved[2] or 0)
        elif text := re.search(r'transform="matrix\(1 0 0 -1 ([-\d.]+) ([-\d.]+)\)"', tag):
            x, y = x + float(text[1]), y + float(text[2])
            glyphs.append((x, y))
        stack.append((x, y))
    return glyphs


def drawn_size(family: str, body: str) -> tuple[float, float]:
    """A figure's drawing, its page's margins (6 pt each side) left out: width, height in pt."""
    box = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', figures_typst.compile_svg(family, body))
    return float(box.group(1)) - 12, float(box.group(2)) - 12
