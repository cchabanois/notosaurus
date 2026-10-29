"""Figures drawn in Typst, each family with the package made for it (FAMILIES): geometry
with ctz-euclide (marks at their segment's middle, angles between their rays), graphs with
lilaq (a curve computed from its function), sets with cetz-venn, diagrams with fletcher,
circuits with zap, chemistry with alchemist, timelines with cetz (our timeline function).
What can be computed is, never placed by eye. Each family's rule and Typst: typst_rules/.

The family is the one the AI gave with the figure's description (models.Card.figure_kind),
else a light call picks it from the description (FAMILY_RULES; none of them: the figure is
drawn as SVG, figures.py); the AI then writes the figure's Typst with that family's
rule (Family.rules), after its preamble (Family.preamble: its packages, the page). It is
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

# For every family: what to draw exactly, and nothing that loads
COMMON = """\
- draw exactly what the description asks for, nothing more: no title, no caption; write only \
the labels it asks to write (what it names to say what to draw, a function, a shape, a \
theorem, an object, is not a label): one word too many may give the card's answer away;
- black on white, a shaded part light grey (`luma(225)`); about 6 by 4 cm;
- only drawing: no import (the packages are imported already), include, read, image, plugin, \
no file.
A figure is for a pupil's lesson: for anything else, answer an empty answer."""


@dataclass(frozen=True)
class Family:
    preamble: str  # its packages, before what the AI writes
    rules: str  # its rule: how its package draws, exactly


# Each family's rule and Typst, in typst_rules/: <family>.md, the rule the AI is given, its
# example where it says {example}; <family>.typ, compiled whole (by the tests, in an editor):
# the preamble (its packages, the page, our own functions), then from EXAMPLE on the example
RULES = HERE / "typst_rules"
EXAMPLE = "// ---- What the AI writes, from here (the rule's example: everything above is given)\n"


def _family(name: str) -> Family:
    typst = (RULES / f"{name}.typ").read_text(encoding="utf-8")
    preamble, example = typst.split(EXAMPLE)
    rule = (RULES / f"{name}.md").read_text(encoding="utf-8")
    return Family(preamble, rule.replace("{example}", example.removesuffix("\n")))


FAMILIES: dict[str, Family] = {
    name: _family(name) for name in ("geometry", "graph", "sets", "diagram", "circuit", "chemistry", "timeline")
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
    r"(^|[^\w-])(import|include|read|eval|json|csv|yaml|toml|xml|cbor|image|plugin)\s*[\"(]|#\s*(import|include)"
)
_COLOR = re.compile(r'\b(fill|stroke)="#([0-9a-fA-F]{6})"')


_IMPORTED = re.compile(r"@preview/([\w-]+):(\d+\.\d+\.\d+)")


def made_with(family: str) -> list[str]:
    """What a family's figure is drawn with, to credit them: Typst, then the packages its
    preamble imports ("ctz-euclide 0.3.0"); [] for no family of ours."""
    if family not in FAMILIES:
        return []
    from importlib.metadata import PackageNotFoundError, version

    try:
        typst = f"Typst {version('typst')}"
    except PackageNotFoundError:
        typst = "Typst"
    return [typst] + [f"{name} {at}" for name, at in _IMPORTED.findall(FAMILIES[family].preamble)]


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
