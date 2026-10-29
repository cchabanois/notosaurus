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
fonts shipped here (typst/: one archive per package, unpacked once in the cache, packages();
fonts/: nothing downloaded), in an empty folder, nothing read or loaded but them (FORBIDDEN
refused first). The SVG keeps its colours (a lesson's colour code: atoms, a legend) and is cleaned
(figures.clean).
"""

import functools
import hashlib
import importlib.util
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

from pydantic import BaseModel, Field

from . import files

HERE = Path(__file__).parent
ARCHIVES = HERE / "typst"  # <name>-<version>.tar.gz, as Typst Universe publishes them (tools/typst_packages.py)
FONTS = HERE / "fonts"
COMPILE_S = 15  # a figure compiles in well under a second; a loop never ends
MEMORY = 1024 * 1024 * 1024  # bytes, where the system lets us say so

# For every family: what to draw exactly, and nothing that loads
COMMON = """\
- draw exactly what the description asks for, nothing more: no title, no caption; write only \
the labels it asks to write (what it names to say what to draw, a function, a shape, a \
theorem, an object, is not a label): one word too many may give the card's answer away;
- black on white, a shaded part light grey (`luma(225)`); the colours the description gives \
(a colour code: atoms, a legend, a set by its colour), as it says; about 6 by 4 cm;
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
    '"circuit": an electric circuit; "chemistry": a molecule\'s formula written with its atoms\' '
    "symbols and bonds (developed, semi-developed, skeletal, a ring), never a model of balls; "
    '"timeline": dates on a line; "other": anything else (a table, a labelled drawing, a solid in '
    "perspective, a map, a molecular model of coloured balls…)"
)
FAMILY_RULES = f"A figure for a pupil's flashcard is described below. Which kind of figure is it? {KINDS}."
FigureKind = Literal["geometry", "graph", "sets", "diagram", "circuit", "chemistry", "timeline", "other"]


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
    if any(_calls(body, own) for own in _LET.findall(preamble)):
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


def made_with(family: str, body: str) -> list[str]:
    """What a figure was drawn with, to credit them: Typst, then the packages its Typst
    really uses ("ctz-euclide 0.3.0"); [] for no family of ours."""
    if family not in FAMILIES:
        return []
    from importlib.metadata import PackageNotFoundError, version

    try:
        typst = f"Typst {version('typst')}"
    except PackageNotFoundError:
        typst = "Typst"
    return [typst] + [f"{name} {at}" for name, at in used_packages(family, body)]


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


def compile_svg(family: str, body: str) -> str:
    """The figure's SVG, its colours as drawn; Unusable when Typst refuses it (its message) or
    takes too long."""
    document = source(family, body)
    with tempfile.TemporaryDirectory(prefix="notosaurus-figure-") as folder:
        path = Path(folder) / "figure.typ"
        path.write_text(document, encoding="utf-8")
        try:
            done = subprocess.run(
                [sys.executable, "-c", _COMPILE.format(memory=MEMORY), str(path), folder, str(packages()), str(FONTS)],
                capture_output=True,
                timeout=COMPILE_S,
            )
        except subprocess.TimeoutExpired as e:
            raise Unusable("It took too long to compile (a loop?): draw it more simply.") from e
    if done.returncode != 0 or not done.stdout:
        said = done.stderr.decode("utf-8", "replace").strip()
        raise Unusable(said[:800].replace(str(path), "figure.typ") or "It didn't compile.")
    return done.stdout.decode("utf-8")
