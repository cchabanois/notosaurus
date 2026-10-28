"""Figures drawn in Typst, each family with the package made for it (FAMILIES): geometry
with ctz-euclide (marks at their segment's middle, angles between their rays), graphs with
lilaq (a curve computed from its function), sets with cetz-venn, diagrams with fletcher,
circuits with zap, chemistry with alchemist, timelines with cetz (TIMELINE). What can be computed is,
never placed by eye.

The family is the one the AI gave with the figure's description (models.Card.figure_kind),
else a light call picks it from the description (FAMILY_RULES; none of them: the figure is
drawn as SVG, figures.py); the AI then writes the figure's Typst with that family's
sheet (Family.rules), after its preamble (Family.preamble: its packages, the page). It is
compiled in a process of its own, cut after COMPILE_S seconds, with the packages and the
fonts shipped here (typst/: tools/typst_packages.py, fonts/: nothing downloaded), in an empty
folder, nothing read or loaded but them (FORBIDDEN refused first). The SVG is then made black
and grey (a card is black on white) and cleaned (figures.clean).
"""

import importlib.util
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

HERE = Path(__file__).parent
PACKAGES = HERE / "typst"  # tools/typst_packages.py
FONTS = HERE / "fonts"
COMPILE_S = 15  # a figure compiles in well under a second; a loop never ends
MEMORY = 1024 * 1024 * 1024  # bytes, where the system lets us say so

PAGE = "#set page(width: auto, height: auto, margin: 6pt)\n"

# For every family: what to draw exactly, and nothing that loads
COMMON = """\
- draw exactly what the description asks for, nothing more: no title, no caption; write only \
the labels it asks to write (what it names to say what to draw, a function, a shape, a \
theorem, an object, is not a label): one word too many may give the card's answer away;
- black on white, a shaded part light grey (`luma(225)`); about 6 by 4 cm;
- only drawing: no import (the packages are imported already), include, read, image, plugin, \
no file.
A figure is for a pupil's lesson: for anything else, answer an empty answer."""


# zap's switch with its two contacts: closed, its blade lies between them (zap's own closed
# switch is a mere wire, nothing to see)
CONTACTS = """\
#let switch(name, ..args) = {
  let params = args.named()
  let closed = params.remove("closed", default: false)
  symbol("switch", name, ..args.pos(), ..params, draw: (ctx, position, style) => {
    interface((-style.width / 2, -0.2), (style.width / 2, 0.2), io: position.len() < 2)
    let w = style.width / 2
    cetz.draw.set-style(stroke: style.stroke)
    let blade = if closed { (w, 0) } else { (-w + 2 * w * calc.cos(style.angle), 2 * w * calc.sin(style.angle)) }
    cetz.draw.line((-w, 0), blade)
    cetz.draw.circle((-w, 0), radius: 0.06, fill: black)
    cetz.draw.circle((w, 0), radius: 0.06, fill: black)
  })
}
"""

# A timeline drawn with cetz: the years under the line, each text from its date, on a row
# above it, never on another text nor on another's line
TIMELINE = """\
#let timeline(start: 0, end: 10, step: 1, width: 12, events: (), periods: ()) = context {
  let unit = width / (end - start)
  // a date: its year, or (year, month, day): placed within its year
  let at(date) = if type(date) == array {
    (date.at(0) + (date.at(1, default: 1) - 1) / 12 + (date.at(2, default: 1) - 1) / 365 - start) * unit
  } else { (date - start) * unit }
  let gap = 0.25
  let shown(body) = {
    let t = text(9pt, body)
    if measure(t).width > 3cm { block(width: 3cm, t) } else { t }
  }
  let items = (
    events.map(e => (x: at(e.at(0)), body: shown(e.at(1))))
      + periods.map(p => (x: at(p.at(0)), body: shown(p.at(2))))
  ).sorted(key: i => -i.x)
  // From the right: each text starts at its date, above the line, on the first row where it
  // reaches no text on its row and passes over the lines of those it reaches: no line
  // crosses a text
  let placed = ()
  for item in items {
    let size = measure(item.body)
    let right = item.x + 0.1 + size.width / 1cm
    let row = 1
    while not placed.all(q => right + gap <= q.x or row > q.row) { row += 1 }
    placed.push((..item, h: size.height / 1cm, row: row))
  }
  let tall = calc.max(0.4, ..placed.map(p => p.h)) + 0.2
  let y(row) = 0.3 + (row - 1) * tall
  cetz.canvas({
    import cetz.draw: *
    for p in periods {
      rect((at(p.at(0)), -0.14), (at(p.at(1)), 0.14), fill: luma(225), stroke: 0.6pt)
    }
    line((-0.3, 0), (width + 0.6, 0), stroke: 0.8pt, mark: (end: ">", fill: black))
    let year = start
    while year <= end {
      line((at(year), -0.1), (at(year), 0.1), stroke: 0.6pt)
      content((at(year), -0.2), text(8pt, if year < 0 { "−" + str(-year) } else { str(year) }), anchor: "north")
      year += step
    }
    for p in placed {
      line((p.x, 0.14), (p.x, y(p.row) + p.h), stroke: 0.4pt)
      content((p.x + 0.1, y(p.row)), p.body, anchor: "south-west")
    }
    for e in events { circle((at(e.at(0)), 0), radius: 0.07, fill: black) }
  })
}
"""


@dataclass(frozen=True)
class Family:
    preamble: str  # its packages, before what the AI writes
    rules: str  # its sheet: how its package draws, exactly


FAMILIES: dict[str, Family] = {
    "geometry": Family(
        PAGE + '#import "@preview/ctz-euclide:0.3.0": *\n',
        """\
You draw a geometry figure in Typst with ctz-euclide 0.3. Answer the Typst only, exactly so:
#ctz-canvas({
  ctz-init()
  ctz-def-points(A: (0, 0), B: (4, 0), C: (1, 3))
  ...
})
- points: `ctz-def-points(A: (0, 0), B: (4, 0))` (names: letters, digits after them); computed \
ones: `ctz-def-midpoint("I", "A", "B")`, `ctz-def-ll("O", ("A", "C"), ("B", "D"))` (where lines \
AC and BD cross), `ctz-def-mediator("M1", "M2", "A", "B")` (two points of AB's perpendicular \
bisector), `ctz-def-perp("P1", "P2", ("A", "B"), "C")` and `ctz-def-para("P1", "P2", ("A", "B"), \
"C")` (the perpendicular, the parallel to AB through C), `ctz-def-bisect("B1", "B2", "A", "O", \
"B")` (the bisector of angle AOB); compute coordinates from the description (a right angle \
really right, equal sides really equal); where two lines cross (an angle's vertex at a \
crossing, a line cut by another), the point computed with `ctz-def-ll`, never guessed;
- drawing: `ctz-draw-segment("A", "B")`, `ctz-draw-polygon("A", "B", "C")`, \
`ctz-draw-line-add("A", "B", add: (0.5, 0.5))` (a whole line, past A and B: through two points \
near the figure, so that it keeps its size; the points ctz-def-mediator, ctz-def-perp, \
ctz-def-para give lie far: place your own on that line instead, a line's name next to it), \
`ctz-draw-circle-through("O", "A")`, `ctz-draw-circle-r("O", 2)`, `ctz-draw-points("O", "I")` \
(the points to show as dots);
- marks, never drawn by hand: `ctz-draw-mark-segment("A", "O", mark: 1)` (equal lengths: the \
same `mark`, 1, 2 or 3 ticks), `ctz-draw-mark-right-angle("A", "I", "B")` (a right angle at the \
middle point), `ctz-draw-angle("O", "A", "B", radius: 0.6)` (the vertex FIRST: the angle at O \
between OA and OB, always the smaller one; `fill: luma(225)` shaded, `label: $alpha$`; the same angles marked the \
same way);
- labels: `ctz-draw-labels(A: "below left", B: "above")` (each its side: above, below, left, \
right, above left…), only the asked ones, never the points made to draw something; a segment's: \
`ctz-draw-label-segment("O", "M", label: $r$)`; a line's name, as the description writes it: \
`ctz-draw-text(2.2, 2, $(d)$)` (x, y next to the line);
- angles in degrees as numbers where a function takes one (`ctz-def-rotation("B", "A", "O", 60)`).
""",
    ),
    "graph": Family(
        PAGE + '#import "@preview/lilaq:0.6.0" as lq\n#show: lq.theme.schoolbook\n',
        """\
You draw a graph of functions in Typst with lilaq 0.6 (`lq`), the axes crossing at the origin \
(its schoolbook theme, set already). Answer the Typst only, exactly so:
#let xs = lq.linspace(0.05, 6, num: 300)
#lq.diagram(
  width: 6cm, height: 4cm,
  xlim: (-0.5, 6.2), ylim: (-3, 2),
  xlabel: $x$, ylabel: $y$,
  lq.plot(xs, xs.map(calc.ln), mark: none, stroke: black + 1pt),
)
- a curve computed from its function, never drawn by hand: `xs.map(x => calc.pow(x, 2) - 2)`, \
`calc.ln`, `calc.exp`, `calc.sqrt`, `x => 1 / x`, `calc.sin`…; its x values only where it is \
defined (a function undefined at 0: two `lq.linspace`, one each side, two plots);
- `xlim` and `ylim` so that the whole curve asked for shows (its lowest and highest values, a \
vertex, the points named); an orthonormal frame (the same unit on both axes): width / height = \
(xlim's length) / (ylim's length);
- points on it: `lq.scatter((1, calc.e), (0, 1), color: black)` (all x, then all y); a value on \
an axis: `xaxis: (ticks: ((calc.e, $e$), 1, 2, 3))` (a tick with its label); a tick at a value \
that isn't a short number (π, e, √2, π/2…): always with its label as the lesson writes it \
(`(calc.pi / 2, $pi/2$)`), never its digits;
- a line (an asymptote): `lq.line((0, -3), (0, 2), stroke: (dash: "dashed"))`; text: \
`lq.place(2, 1, [$f$], align: left)`.
""",
    ),
    "sets": Family(
        PAGE
        + '#import "@preview/cetz:0.5.2"\n#import "@preview/cetz-venn:0.2.0"\n'
        + "#let hatch = tiling(size: (5pt, 5pt), std.line(start: (0pt, 5pt), end: (5pt, 0pt), stroke: 0.6pt))\n",
        """\
You draw a set (Venn) diagram in Typst with cetz-venn 0.2 (two or three sets). Answer the Typst \
only, exactly so:
#cetz.canvas({
  import cetz.draw: *
  cetz-venn.venn2(name: "v", ab-fill: hatch)
  content("v.a", [$A$])
  content("v.b", [$B$])
})
- `cetz-venn.venn2(...)` or `cetz-venn.venn3(...)`; its parts: `a`, `b`, `c`, `ab`, `ac`, `bc`, \
`abc`, `not-ab` (outside them, in the frame), `not-abc`: `ab-fill: hatch` (hatched, given), \
`a-fill: luma(225)` (shaded), never drawn by hand;
- a part's label at its anchor: `content("v.ab", [$x$])`, the sets' names at `"v.a"`, `"v.b"`.
""",
    ),
    "diagram": Family(
        PAGE + '#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge\n',
        """\
You draw a diagram of boxes and arrows (a flowchart, a cycle, a chain, a tree) in Typst with \
fletcher 0.5. Answer the Typst only, exactly so:
#diagram(node-stroke: 0.8pt, spacing: 2em,
  node((0, 0), [Évaporation]), edge("-|>"),
  node((1, 0), [Condensation]), edge("-|>"),
  node((1, 1), [Précipitations]),
)
- `node((column, row), [text])` on a grid of cells; `edge("-|>")` from the node before to the \
node after; `edge((0, 1), (0, 0), "-|>", [label])` between two cells; `"<|-|>"` both ways, `"--"` \
a plain line, `bend: 30deg` curved;
- a node's shape: `shape: circle`, `corner-radius: 4pt`; texts as the description gives them.
""",
    ),
    "circuit": Family(
        PAGE + '#import "@preview/zap:0.6.0": *\n' + CONTACTS,
        """\
You draw an electric circuit in Typst with zap 0.6. Answer the Typst only, exactly so:
#circuit({
  battery("g", (0, 0), (0, 3), label: $G$)
  switch("k", (0, 3), (3, 3), label: $K$)
  lamp("l", (3, 3), (3, 0), label: $L$)
  wire((3, 0), (0, 0))
})
- no import (zap's components are given); each component between two points, the loop closed \
by `wire`s: `battery`, `vsource` (a generator), `resistor`, `lamp`, `switch` (open, its \
contacts drawn; `closed: true` closed), `led`, `diode`, `capacitor`, `isource`; \
`node("n", (3, 0))` a junction; meters as the description names them, with labels;
- a name per component (`"r1"`), a label as the description writes it; in parallel: two \
branches between the same two points.
""",
    ),
    "chemistry": Family(
        PAGE + '#import "@preview/alchemist:0.2.0": *\n',
        """\
You draw a molecule's formula in Typst with alchemist 0.2. Answer the Typst only, exactly so:
#skeletize({
  fragment("CH_3")
  single()
  fragment("CH_2")
  single()
  fragment("OH")
})
- `fragment("CH_3")` an atom or group (subscripts with `_`); bonds between them: `single()`, \
`double()`, `triple()`, each with `angle: 1` (×45°, from the horizontal: 0 right, 2 up, -2 down) \
or `absolute: 30deg`; `branch({ ... })` a side chain from the last fragment; `cycle(6, { single(); \
double(); ... })` a ring;
- a developed formula: every atom and bond; semi-developed: the groups, as the description says.
""",
    ),
    "timeline": Family(
        PAGE + '#import "@preview/cetz:0.5.2"\n' + TIMELINE,
        """\
You draw a timeline in Typst with the timeline function given (cetz). Answer the Typst only, \
exactly so:
#timeline(start: 1788, end: 1800, step: 2,
  events: (((1789, 7, 14), "Prise de la Bastille, 14 juillet 1789"), (1792, "Proclamation de la République")),
  periods: ((1793, 1794, "La Terreur"),),
)
- `start`, `end` the description's when it gives them, else a little around the dates; `step` \
the years written on the line (ten of them at most); a year before Christ negative (`-52`);
- events and periods as the description gives them, their texts and dates exactly: a date is \
its year (`1792`), or `(year, month, day)` when the description gives its month (`(1789, 8)`) \
or day (`(1789, 7, 14)`): placed within its year, never a fraction of yours; the date written \
in its text as the description writes it; a single item still in `( …, )`; the texts are \
placed by the function, never on one another.
""",
    ),
}

# The kinds of figures, said to the AI that describes a figure (models.Card.figure_kind) or
# picks its family (FAMILY_RULES)
KINDS = (
    '"geometry": points, segments, lines, circles, polygons, angles, their marks (a theorem, a '
    'construction); "graph": the graph of one or more functions in a frame; "sets": a Venn diagram of '
    'two or three sets; "diagram": boxes and arrows (a flowchart, a cycle, a chain, a classification); '
    '"circuit": an electric circuit; "chemistry": a molecule\'s formula; "timeline": dates on a line; '
    '"other": anything else (a table, a labelled drawing, a solid in perspective, a map…)'
)
FAMILY_RULES = f"A figure for a pupil's flashcard is described below. Which kind of figure is it? {KINDS}."
FigureKind = Literal["geometry", "graph", "sets", "diagram", "circuit", "chemistry", "timeline", "other"]


class Kind(BaseModel):
    family: FigureKind


# What a body may not do: load anything (the packages are given), read a file
FORBIDDEN = re.compile(
    r"(^|[^\w-])(import|include|read|json|csv|yaml|toml|xml|cbor|image|plugin)\s*[\"(]|#\s*(import|include)"
)
_COLOR = re.compile(r'\b(fill|stroke)="#([0-9a-fA-F]{6})"')


def available() -> bool:
    """Typst installed (the typst package): else the figures are drawn as SVG."""
    return importlib.util.find_spec("typst") is not None


class Figure(BaseModel):
    typst: str = Field(description="The figure's Typst, as the sheet shows it.")


class Unusable(Exception):
    """Not compiled: what Typst said (for the AI to correct it), or why it was refused."""


def source(family: str, body: str) -> str:
    """The Typst document of a figure of `family`: its preamble, then what the AI wrote."""
    if FORBIDDEN.search(body):
        raise Unusable("Only drawing commands: no import, include, file or plugin.")
    return FAMILIES[family].preamble + body.strip() + "\n"


_COMPILE = """\
import sys, typst
try:  # the memory it may take, where the system lets us say so (not on Windows: no resource)
    import resource
    resource.setrlimit(resource.RLIMIT_AS, ({memory}, {memory}))
except Exception:
    pass
try:
    svg = typst.compile(sys.argv[1], format="svg", root=sys.argv[2], package_path=sys.argv[3],
                        package_cache_path=sys.argv[2], font_paths=[sys.argv[4]], ignore_system_fonts=True)
except Exception as e:
    sys.stderr.write(str(e))
    sys.exit(1)
sys.stdout.buffer.write(svg)
"""


def compile_svg(family: str, body: str) -> str:
    """The figure's SVG, black and grey; Unusable when Typst refuses it (its message) or
    takes too long."""
    document = source(family, body)
    with tempfile.TemporaryDirectory(prefix="notosaurus-figure-") as folder:
        path = Path(folder) / "figure.typ"
        path.write_text(document, encoding="utf-8")
        try:
            done = subprocess.run(
                [sys.executable, "-c", _COMPILE.format(memory=MEMORY), str(path), folder, str(PACKAGES), str(FONTS)],
                capture_output=True,
                timeout=COMPILE_S,
            )
        except subprocess.TimeoutExpired as e:
            raise Unusable("It took too long to compile (a loop?): draw it more simply.") from e
    if done.returncode != 0 or not done.stdout:
        said = done.stderr.decode("utf-8", "replace").strip()
        raise Unusable(said[:800].replace(str(path), "figure.typ") or "It didn't compile.")
    return monochrome(done.stdout.decode("utf-8"))


def monochrome(svg: str) -> str:
    """The packages' colours (a blue curve, red marks) black, their light fills light grey:
    a card is black on white, as the SVG figures."""

    def grey(match: re.Match) -> str:
        what, hex_ = match.group(1), match.group(2)
        r, g, b = (int(hex_[i : i + 2], 16) for i in (0, 2, 4))
        if max(r, g, b) - min(r, g, b) < 16:  # a grey already
            return match.group(0)
        light = (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.6
        return f'{what}="{"#e1e1e1" if what == "fill" and light else "#000000"}"'

    return _COLOR.sub(grey, svg)
