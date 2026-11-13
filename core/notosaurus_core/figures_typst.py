"""Figures drawn in Typst, each family with the package made for it (FAMILIES): geometry
with ctz-euclide (marks at their segment's middle, angles between their rays), graphs with
lilaq (a curve computed from its function), sets with cetz-venn, diagrams with fletcher,
circuits with zap, chemistry with alchemist, timelines with cetz (our timeline function),
maps with our atlas (notosaurus-atlas: Natural Earth's countries and cities, tools/atlas.py),
clocks with cetz (our clock function: its hands placed by the time), solids with cetz (our
cuboid, prism, pyramid in cavalier perspective, their hidden edges computed; cylinder, cone,
sphere as textbooks draw them, in proportion), charts and phylogenetic trees with cetz (our
chart and phylogeny functions: a tree built from what each species has), sequences aligned
in Typst (our sequences function: letters in columns, their differences framed, computed), a body's vectors with cetz
(our mechanics function: each given by its direction, on an orbit, a plane, a slope), tables of
values in Typst (our value-table function: cells measured, totals summed, arrows beside it),
Scratch scripts with blockst (each block drawn from its text, one Scratch doesn't have refused),
light's rays with cetz (our refraction and lens functions: the Snell-Descartes angle, the image
and its rays computed).
What can be computed is, never placed by eye. Each family's rule and Typst: typst_rules/.

The family is the one the AI gave with the figure's description (models.Card.figure_kind),
else a light call picks it from the description (FAMILY_RULES; none of them: the figure is
drawn as SVG, figures.py); the AI then writes the figure's Typst with that family's
rule (Family.rules), after its preamble (Family.preamble: its packages, the page), its slips
mended first (source(): typst_source.py makes it what the AI meant). It is compiled in a
process of its own, cut after COMPILE_S seconds, with the packages and the fonts shipped here
(typst/: one archive per package, unpacked once in the cache, packages(); fonts/: nothing
downloaded), in an empty folder, nothing read or loaded but them (FORBIDDEN refused first).
The SVG keeps its colours (a lesson's colour code: atoms, a legend) and is cleaned
(figures.clean).
"""

import base64
import functools
import hashlib
import html
import importlib.util
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree

from pydantic import BaseModel, Field

from . import files, typst_source

HERE = Path(__file__).parent
ARCHIVES = HERE / "typst"  # <name>-<version>.tar.gz, as Typst Universe publishes them (tools/typst_packages.py)
FONTS = HERE / "fonts"
COMPILE_S = 15  # a figure compiles in well under a second; a loop never ends
MEMORY = 1024 * 1024 * 1024  # bytes, where the system lets us say so

# Every family's text in the font the SVG figures are drawn in (fonts/, shipped): a figure
# reads the same whichever way it was drawn, plainer for a child than Typst's own serif;
# formulas keep their mathematical font
FONT = '#set text(font: "DejaVu Sans")\n'

# What a figure is drawn with, credited with its licence and its page (the licences page:
# Typst, its packages, the maps' data), in figure_credits.json: one list, served to the
# apps by the relay (/v1/credits) and by the computer (/api/credits), so that a package
# added here is credited without a new app (tests/test_licences.py: every one shipped)
CREDITS: list[dict[str, str]] = json.loads((HERE / "figure_credits.json").read_text(encoding="utf-8"))

# For every family: what to draw exactly, and nothing that loads
COMMON = (HERE / "typst_rules" / "common.md").read_text(encoding="utf-8").removesuffix("\n")


@dataclass(frozen=True)
class Family:
    preamble: str  # its packages, before what the AI writes
    rules: str  # its rule: how its package draws, exactly


# Each family's rule and Typst, in typst_rules/: <family>.md, the rule the AI is given, its
# example where it says {example}; <family>.typ, compiled whole (by the tests, in an editor):
# the preamble (its packages, the page, our own functions), then from EXAMPLE on the example
RULES = HERE / "typst_rules"
EXAMPLE = "// ---- What the AI writes, from here (the rule's example: everything above is given)\n"
# What every preamble shares (the decimal separator, numbers written as the language writes
# them, round steps): typst_rules/common.typ, imported by each family's .typ and inlined in
# its preamble, each figure compiled alone from its source
SHARED = '#import "common.typ": *\n'


def _family(name: str) -> Family:
    typst = (RULES / f"{name}.typ").read_text(encoding="utf-8")
    preamble, example = typst.split(EXAMPLE)
    preamble = preamble.replace(SHARED, (RULES / "common.typ").read_text(encoding="utf-8"), 1)
    rule = (RULES / f"{name}.md").read_text(encoding="utf-8")
    return Family(preamble, rule.replace("{example}", example.removesuffix("\n")))


FAMILIES: dict[str, Family] = {
    name: _family(name)
    for name in (
        "geometry",
        "graph",
        "sets",
        "diagram",
        "circuit",
        "chemistry",
        "timeline",
        "map",
        "clock",
        "solid",
        "chart",
        "sequence",
        "phylogeny",
        "mechanics",
        "table",
        "scratch",
        "optics",
        "field",
    )
}

# The kinds of figures, said to the AI that describes a figure (models.Card.figure_kind) or
# picks its family (FAMILY_RULES)
KINDS = (HERE / "typst_rules" / "kinds.md").read_text(encoding="utf-8").removesuffix("\n")
FAMILY_RULES = f"A figure for a pupil's flashcard is described below. Which kind of figure is it? {KINDS}."
FigureKind = Literal[
    "geometry",
    "graph",
    "sets",
    "diagram",
    "circuit",
    "chemistry",
    "timeline",
    "map",
    "clock",
    "solid",
    "chart",
    "sequence",
    "phylogeny",
    "mechanics",
    "table",
    "scratch",
    "optics",
    "field",
    "other",
]


class Kind(BaseModel):
    family: FigureKind


# What a body may not do: load anything (the packages are given), read a file
FORBIDDEN = re.compile(
    r"(^|[^\w-])(import|include|read|eval|json|csv|yaml|toml|xml|cbor|image|plugin)\s*[\"(]|#\s*(import|include)"
)


# A package's import ("#import "@preview/lilaq:0.6.0" as lq", "…: diagram, node, edge"), and
# what a figure's Typst calls: credited for what it uses only (made_with)
_IMPORT = re.compile(r'^#?import\s+"([^"]+)"\s*(?:as\s+([\w-]+))?\s*(?::\s*([^\n]*))?$', re.M)
_LET = re.compile(r"^#let\s+([A-Za-z][\w-]*)", re.M)
_NAME = re.compile(r"^[A-Za-z][\w-]*$")


def _items(listed: str) -> set[str]:
    """The names an import lists ("diagram, node, edge as e"): what they're bound to."""
    names = {item.strip().split(" as ")[-1].strip() for item in listed.split(",")}
    return {n for n in names if _NAME.match(n)}


@functools.cache
def _exports(name: str, version: str) -> tuple[frozenset[str], tuple[tuple[str, str, str], ...]]:
    """What a shipped package gives a glob import ("*"): the names its entrypoint defines or
    re-exports, and the packages it imports as modules (their binding, name, version)."""
    path = ARCHIVES / f"{name}-{version}.tar.gz"
    if not path.is_file():
        return frozenset(), ()
    with tarfile.open(path, mode="r:gz") as tar:
        try:
            meta = tomllib.loads(tar.extractfile("typst.toml").read().decode())  # type: ignore[union-attr]
        except KeyError:
            return frozenset(), ()
        names: set[str] = set()
        modules: list[tuple[str, str, str]] = []

        def read(file: str, seen: set[str]) -> None:
            if file in seen:
                return
            seen.add(file)
            try:
                text = tar.extractfile(file).read().decode("utf-8", "replace")  # type: ignore[union-attr]
            except KeyError:
                return
            names.update(_LET.findall(text))
            for source, alias, listed in _IMPORT.findall(text):
                listed = listed.strip()
                if source.startswith("@preview/"):
                    package, _, at = source.removeprefix("@preview/").partition(":")
                    if not listed:
                        modules.append((alias or package, package, at))
                    elif listed != "*":
                        names.update(_items(listed))
                elif listed == "*":
                    read(posixpath.normpath(posixpath.join(posixpath.dirname(file), source)), seen)
                elif listed:
                    names.update(_items(listed))

        read(meta["package"]["entrypoint"], set())
    return frozenset(names), tuple(modules)


def _calls(code: str, name: str) -> bool:
    return re.search(rf"(?<![\w.-]){re.escape(name)}\s*\(", code) is not None


def used_packages(family: str, body: str) -> list[tuple[str, str]]:
    """The packages a figure's Typst really uses, among its family's ("ctz-euclide", "0.3.0"):
    a name it calls or a module it reaches ("lq.", "cetz."); our own functions of the preamble
    (timeline, switch) count with what they use."""
    preamble = FAMILIES[family].preamble if family in FAMILIES else ""
    code = body
    # a package's own function the preamble wraps (chemistry's skeletize) stays the package's
    wrapped: set[str] = set()
    for source, _, listed in _IMPORT.findall(preamble):
        if source.startswith("@preview/") and listed.strip() == "*":
            package, _, at = source.removeprefix("@preview/").partition(":")
            wrapped |= _exports(package, at)[0]
    if any(_calls(body, own) for own in _LET.findall(preamble) if own not in wrapped):
        code += "\n" + preamble.split("\n", 2)[-1]  # what our functions call too
    used: list[tuple[str, str]] = []
    for source, alias, listed in _IMPORT.findall(preamble):
        if not source.startswith("@preview/"):
            continue
        package, _, at = source.removeprefix("@preview/").partition(":")
        listed = listed.strip()
        reached = f"{alias or package}." in code
        if listed == "*":
            names, modules = _exports(package, at)
            reached = reached or any(_calls(code, n) for n in names)
            for binding, inner, inner_at in modules:
                if f"{binding}." in code and (inner, inner_at) not in used:
                    used.append((inner, inner_at))
        elif listed:
            reached = reached or any(_calls(code, n) for n in _items(listed))
        if reached and (package, at) not in used:
            used.append((package, at))
    return used


@functools.cache
def typst_version() -> str:
    """Typst's own version, the compiler typst-py ships (Typst 0.15.1 in typst-py 0.15.2): its
    sys.version, else the Python package's; "" without Typst."""
    try:
        import json

        import typst

        return json.loads(typst.query(b"#metadata(str(sys.version)) <v>", "<v>", field="value"))[0]
    except Exception:  # an older typst-py, or none
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("typst")
        except PackageNotFoundError:
            return ""


def made_with(family: str, body: str) -> list[str]:
    """What a figure was drawn with, to credit them: Typst, then the packages its Typst
    really uses ("ctz-euclide 0.3.0"); [] for no family of ours."""
    if family not in FAMILIES:
        return []
    typst = f"Typst {typst_version()}".strip()
    return [typst] + [f"{name} {at}" for name, at in used_packages(family, body)]


def available() -> bool:
    """Typst installed (the typst package): else the figures are drawn as SVG."""
    return importlib.util.find_spec("typst") is not None


class Figure(BaseModel):
    typst: str = Field(description="The figure's Typst, as the rule shows it.")


class Unusable(Exception):
    """Not compiled: what Typst said (for the AI to correct it), or why it was refused."""


# The preambles' (common.typ): the separator their own numbers are written with, set here
SEPARATOR = '#let decimal-separator = "."'


def source(family: str, body: str) -> str:
    """The Typst document of a figure of `family`: its preamble, then what the AI wrote."""
    # "<" and ">" written as HTML's entities (an arrow "-|&gt;"): Typst has none of them
    body = typst_source.PACKAGE_IMPORT.sub("", body).replace("&gt;", ">").replace("&lt;", "<")
    if family == "diagram":
        marked = typst_source.EDGE_MARKS.sub(typst_source.unbarred, body)
        edged = typst_source.edges(marked, lambda a: typst_source.labels_aside(typst_source.unworded(a)))
        body = typst_source.broken_lines(edged)
    if family == "circuit":
        body = typst_source.joined_ends(body)
    if FORBIDDEN.search(body):
        raise Unusable("Only drawing commands: no import, include, file or plugin.")
    body = typst_source.no_fractions(typst_source.unshadowed(body))
    separator = typst_source.decimal_separator(body)
    body = typst_source.decimal_commas(body, separator == ",")
    preamble = FAMILIES[family].preamble.replace(SEPARATOR, f'#let decimal-separator = "{separator}"')
    if "#let diagram-apart(" in preamble:
        body = typst_source.LQ_DIAGRAM.sub("diagram-apart", body)
    if "#let line-kept(" in preamble:
        body = typst_source.LQ_LINE.sub("line-kept", body)
    return FONT + preamble + body.strip() + "\n"


COMPILER = HERE / "typst_compile.py"  # run apart: a figure that loops never stops the server


def packages() -> Path:
    """The packages' folder Typst reads (preview/<name>/<version>/), unpacked from the
    archives once, in the cache: under a name made of the archives' own, so that a package
    changed is a new folder; written aside then renamed, never seen half unpacked."""
    archives = sorted(ARCHIVES.glob("*.tar.gz"))
    key = hashlib.sha256("\n".join(a.name for a in archives).encode()).hexdigest()[:12]
    folder = files.cache_dir(f"typst-{key}")
    if folder.is_dir():
        return folder
    folder.parent.mkdir(parents=True, exist_ok=True)
    aside = Path(tempfile.mkdtemp(prefix="typst-", dir=folder.parent))
    try:
        for archive in archives:
            name, version = archive.name.removesuffix(".tar.gz").rsplit("-", 1)
            with tarfile.open(archive, mode="r:gz") as tar:
                tar.extractall(aside / "preview" / name / version, filter="data")
        os.replace(aside, folder)
    except OSError:
        if not folder.is_dir():  # not another process's, unpacked meanwhile
            raise
    finally:
        shutil.rmtree(aside, ignore_errors=True)
    return folder


_SVG_IMAGE = re.compile(r'href="data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)"')
_UNKNOWN_BLOCK = re.compile(r'<path[^>]*fill="#bfbfbf"[^>]*/>((?:(?!<path).)*)', re.IGNORECASE | re.DOTALL)


def _unknown_blocks(svg: str) -> list[str]:
    """The blocks blockst drew grey in a Scratch script, as their words read: the ones Scratch
    doesn't have in that language (a block's words of the AI's own, "tourner à droite de"),
    drawn without an error."""
    found = []
    for data in _SVG_IMAGE.findall(svg):
        inner = base64.b64decode(data).decode("utf-8", "replace")
        for after in _UNKNOWN_BLOCK.findall(inner):
            words = re.findall(r"<text[^>]*>([^<]*)</text>", after)
            found.append(html.unescape(" ".join(w.strip() for w in words if w.strip())))
    return found


@functools.cache
def _if_words() -> frozenset[str]:
    """The first word of Scratch's "if" block in each language blockst has ("si", "if",
    "falls"…), read from its own translations (its plugin)."""
    plugins = packages().glob("preview/blockst/*/libs/scratch/plugins/scratchblocks_wasm.wasm")
    text = "".join(p.read_bytes().decode("utf-8", "replace") for p in plugins)
    return frozenset(m.split()[0] for m in re.findall(r'CONTROL_IF = "([^"%]+)%1', text) if m.split())


def _without_if_arrows(svg: str) -> str:
    """blockst draws a loop's arrow at the foot of an "if" block too, as if it looped: the
    arrow kept for loops only (repeat, forever), an "if"'s dropped (its first word its
    language's, _if_words)."""

    def inner(m: re.Match) -> str:
        drawn = ElementTree.fromstring(base64.b64decode(m.group(1)).decode("utf-8"))
        for block in drawn.iter():
            arrows = [c for c in block if c.tag.endswith("use") and c.get("href") == "#sb-loopArrow"]
            first = next((c.text or "" for c in block if c.tag.endswith("text") and (c.text or "").strip()), "")
            if arrows and first.strip() in _if_words():
                for arrow in arrows:
                    block.remove(arrow)
        ElementTree.register_namespace("", "http://www.w3.org/2000/svg")
        out = ElementTree.tostring(drawn, encoding="unicode")
        return f'href="data:image/svg+xml;base64,{base64.b64encode(out.encode()).decode()}"'

    return _SVG_IMAGE.sub(inner, svg)


def compile_svg(family: str, body: str) -> str:
    """The figure's SVG, its colours as drawn; Unusable when Typst refuses it (its message),
    takes too long or draws nothing (an empty answer: a blank page on the card, never redrawn)."""
    document = source(family, body)
    with tempfile.TemporaryDirectory(prefix="notosaurus-figure-") as folder:
        path = Path(folder) / "figure.typ"
        path.write_text(document, encoding="utf-8")
        try:
            done = subprocess.run(
                [sys.executable, "-P", str(COMPILER), str(MEMORY), str(path), folder, str(packages()), str(FONTS)],
                capture_output=True,
                timeout=COMPILE_S,
            )
        except subprocess.TimeoutExpired as e:
            raise Unusable("It took too long to compile (a loop?): draw it more simply.") from e
    if done.returncode != 0 or not done.stdout:
        said = done.stderr.decode("utf-8", "replace").strip()
        raise Unusable(said[:800].replace(str(path), "figure.typ") or "It didn't compile.")
    svg = done.stdout.decode("utf-8")
    if _blank(svg):
        raise Unusable("It draws nothing: the page is blank.")
    if family == "scratch" and (unknown := _unknown_blocks(svg)):
        raise Unusable(
            "Scratch has no block "
            + ", ".join(f'"{block}"' for block in unknown)
            + " (drawn grey): write each block in the words Scratch shows in the language given,"
            " a block of your own defined by Scratch's define block and used with call."
        )
    if family == "scratch":
        svg = _without_if_arrows(svg)
    svg = _fitted(svg)
    # A map's outlines: thousands of points, each written to the billionth of a point by
    # Typst: kept to the tenth (nothing seen changes), the figure several times lighter
    return _rounded_paths(svg) if family == "map" else svg


# What draws something in Typst's SVG: its page's background is one path, the first
_DRAWING = {"path", "use", "image", "text", "rect", "circle", "ellipse", "line", "polyline", "polygon"}


def _blank(svg: str) -> bool:
    """Typst's page with nothing on it but its background."""
    drawn = [e for e in ElementTree.fromstring(svg).iter() if str(e.tag).rsplit("}", 1)[-1] in _DRAWING]
    return len(drawn) <= 1


def _fitted(svg: str) -> str:
    """The page grown to what Typst draws past it (an axis's name lilaq writes past the
    diagram's end: "temps (mi"): figures.fitted."""
    from . import figures

    return figures.fitted(svg)


_NUMBER = re.compile(r"-?\d+\.\d{2,}")


def _rounded_paths(svg: str) -> str:
    """Each path's numbers (its d) to one decimal."""

    def one(m: re.Match) -> str:
        return m.group(1) + _NUMBER.sub(lambda n: f"{float(n.group()):.1f}", m.group(2)) + m.group(3)

    return re.sub(r'( d=")([^"]*)(")', one, svg)
