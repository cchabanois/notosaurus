"""Figures drawn in Typst, each family with the package made for it (FAMILIES): geometry
with ctz-euclide (marks at their segment's middle, angles between their rays), graphs with
lilaq (a curve computed from its function), sets with cetz-venn, diagrams with fletcher,
circuits with zap, chemistry with alchemist, timelines with cetz (our timeline function),
maps with our atlas (notosaurus-atlas: Natural Earth's countries and cities, tools/atlas.py),
clocks with cetz (our clock function: its hands placed by the time), solids with cetz (our
cuboid, prism, pyramid in cavalier perspective, their hidden edges computed; cylinder, cone,
sphere as textbooks draw them, in proportion).
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
from xml.etree import ElementTree

from pydantic import BaseModel, Field

from . import files

HERE = Path(__file__).parent
ARCHIVES = HERE / "typst"  # <name>-<version>.tar.gz, as Typst Universe publishes them (tools/typst_packages.py)
FONTS = HERE / "fonts"
COMPILE_S = 15  # a figure compiles in well under a second; a loop never ends
MEMORY = 1024 * 1024 * 1024  # bytes, where the system lets us say so

# Every family's text in the font the SVG figures are drawn in (fonts/, shipped): a figure
# reads the same whichever way it was drawn, plainer for a child than Typst's own serif;
# formulas keep their mathematical font
FONT = '#set text(font: "DejaVu Sans")\n'

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


def _family(name: str) -> Family:
    typst = (RULES / f"{name}.typ").read_text(encoding="utf-8")
    preamble, example = typst.split(EXAMPLE)
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
    "other",
]


class Kind(BaseModel):
    family: FigureKind


# A package imported by the AI though its family's preamble gives it ("#import
# "@preview/lilaq:0.6.0" as lq" again): the line dropped rather than the figure refused, an AI
# call saved; a package the preamble doesn't give then fails as any unknown name (Typst says so)
PACKAGE_IMPORT = re.compile(r'^[ \t]*#import[ \t]+"@preview/[^"\n]+"[^\n]*\n?', re.M)
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


# An edge's string with a bar in it ("-|>", "-|-", "-|->"): fletcher's marks
EDGE_MARKS = re.compile(r'"([-<>|.=~]*\|[-<>|.=~]*)"')


def _unbarred(marks: re.Match) -> str:
    """An edge's bars kept only as part of a head ("<|", "|>"): one elsewhere ("-|-", "-|->")
    draws a bar across the line, which no school diagram asks for; the AI's "-||" (two bars)
    meant an arrow, "-|>". Its bar out, an arrow's head is the filled one ("-|->" → "-|>") as
    every other arrow's: the AI writes "-|->" whatever the rule says of fletcher's marks."""
    s = marks.group(1)
    if s == "-||":
        return '"-|>"'
    kept, i = "", 0
    while i < len(s):
        c, i = s[i], i + 1
        if c != "|" or s[i - 2 : i - 1] == "<" or s[i : i + 1] == ">":
            kept += c
        elif kept[-1:] in ("-", ".", "=", "~"):  # the bar out, the line it cut whole again:
            while s[i : i + 1] == kept[-1]:  # "-|-" a plain line, never "--" dashed
                i += 1
    if kept != s:
        kept = re.sub(r"(?<!\|)>$", "|>", re.sub(r"^<(?!\|)", "<|", kept))
    return f'"{kept or "-"}"'


def _broken_lines(body: str) -> str:
    """A text's new line written as a string's ("Accord avec\\nle sujet") or a "\\" glued to
    the next word ("avant\\le verbe"): in Typst's markup a backslash before a letter only
    escapes it ("avecnle", "avantle"), so it becomes the line break meant ("\\ "). Only in a
    text (within [ ]), outside its maths; a string of the code ("…\\n…") is one already."""
    out: list[str] = []
    depth, math, string, i = 0, False, False, 0
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            after = body[i + 1]
            if depth and not math and after.isalpha() and body[i + 1 : i + 3] != "u{":
                out.append("\\ " if after == "n" else "\\ " + after)
            else:
                out.append(c + after)
            i += 2
            continue
        if string:
            string = c != '"'
        elif depth == 0 and c == '"':
            string = True
        elif c == "[":
            depth += 1
        elif c == "]" and depth:
            depth -= 1
            math = math and depth > 0
        elif c == "$" and depth:
            math = not math
        out.append(c)
        i += 1
    return "".join(out)


# The language the AI says its figure is in (its first line, `#set text(lang: "fr")`, the
# description's): numbers written as that language writes them. A decimal comma in these
# (ISO 639-1); a point in the others (English, Chinese, Japanese…) and when none is said.
LANGUAGE = re.compile(r'#set\s+text\([^)]*\blang:\s*"([a-zA-Z]{2,3})"')
DECIMAL_COMMA = frozenset(
    [
        "fr",
        "de",
        "es",
        "it",
        "pt",
        "nl",
        "ca",
        "eu",
        "gl",
        "ro",
        "pl",
        "cs",
        "sk",
        "sl",
        "hr",
        "sr",
        "bs",
        "bg",
        "ru",
        "uk",
        "be",
        "lt",
        "lv",
        "et",
        "fi",
        "sv",
        "da",
        "no",
        "nb",
        "nn",
        "is",
        "tr",
        "el",
        "hu",
        "sq",
        "mk",
        "az",
        "kk",
        "ka",
        "hy",
        "id",
        "vi",
        "af",
    ]
)
# The preambles' (graph, chart): the separator their own numbers are written with, set here
SEPARATOR = '#let decimal-separator = "."'
MATH = re.compile(r"\$[^$]*\$")


def decimal_separator(body: str) -> str:
    """ "," when the figure's language (its `#set text(lang: …)`) writes a decimal comma, else "."."""
    said = LANGUAGE.search(body)
    return "," if said and said.group(1).lower() in DECIMAL_COMMA else "."


def _decimal_commas(body: str, comma: bool) -> str:
    """A decimal comma in maths as the language writes it: Typst's maths spaces a comma out
    ("0, 3"), a quoted one stays tight ("0,3"). LaTeX's own (`0{,}3`, the AI writing LaTeX)
    meant one whatever the language; a comma between digits only in a language writing one
    (a list "1,2" in English stays as it was)."""

    def tight(math: re.Match) -> str:
        m = re.sub(r"(\d)\s*\{,\}\s*(?=\d)", r'\1","', math.group(0))
        return re.sub(r"(\d),(?=\d)", r'\1","', m) if comma else m

    return MATH.sub(tight, body)


# Math symbols an AI also names its variables after (`#let lambda = 1.5`): in a formula,
# Typst reads a name as the variable in scope before the symbol, so `$lambda$` wrote "1.5"
GREEK = [
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "zeta",
    "eta",
    "theta",
    "iota",
    "kappa",
    "lambda",
    "mu",
    "nu",
    "xi",
    "omicron",
    "pi",
    "rho",
    "sigma",
    "tau",
    "upsilon",
    "phi",
    "chi",
    "psi",
    "omega",
]
SYMBOL_NAMES = frozenset(GREEK + [g.capitalize() for g in GREEK])
LET_NAME = re.compile(r"\blet\s+([A-Za-z]+)\b")


def _segments(body: str) -> list[tuple[str, str]]:
    """The body cut into pieces, each "code", "text" (within [ ]) or "math" (between two `$`,
    in a text or straight in the code: `place(1, 2, $lambda$)`), with what it holds. A `$`
    escaped or in a string of the code is no formula; a quote in a text is a character."""
    pieces: list[tuple[str, str]] = []
    start, depth, math, string, i = 0, 0, False, False, 0

    def kind() -> str:
        return "math" if math else "text" if depth else "code"

    while i < len(body):
        c = body[i]
        if c == "\\":
            i += 2
            continue
        if string:
            string = c != '"'
        elif c == '"' and depth == 0 and not math:
            string = True
        elif c in "[]$" and not (math and c != "$") and not (c == "]" and not depth):
            pieces.append((kind(), body[start:i]))
            start = i
            if c == "$":
                math = not math
            else:
                depth += 1 if c == "[" else -1
        i += 1
    pieces.append((kind(), body[start:]))
    return pieces


def _unshadowed(body: str) -> str:
    """A variable named after a math symbol (`lambda`, `pi`) renamed wherever code reads it,
    so that the same name in a formula is the symbol again, as the AI meant it: in the code,
    the name alone (not a field, `calc.pi`, nor part of a longer name); in a text or a
    formula, only where code is embedded (`#lambda`, `#str(lambda)`)."""
    names = {n for n in LET_NAME.findall(body) if n in SYMBOL_NAMES}
    if not names:
        return body
    alone = re.compile(rf"(?<![\w.-])({'|'.join(sorted(names))})(?![\w]|-[A-Za-z])")

    def renamed(code: str) -> str:
        return alone.sub(r"\1-value", code)

    def embedded(text: str) -> str:
        # `#name`, or a `#call(…)`'s arguments: code within a text or a formula
        out, i = [], 0
        for m in re.finditer(r"#[\w.-]+(\((?:[^()]|\([^()]*\))*\))?", text):
            out.append(text[i : m.start()])
            out.append(renamed(m.group(0)))
            i = m.end()
        return "".join(out) + text[i:]

    return "".join(renamed(s) if k == "code" else embedded(s) for k, s in _segments(body))


def source(family: str, body: str) -> str:
    """The Typst document of a figure of `family`: its preamble, then what the AI wrote."""
    # "<" and ">" written as HTML's entities (an arrow "-|&gt;"): Typst has none of them
    body = PACKAGE_IMPORT.sub("", body).replace("&gt;", ">").replace("&lt;", "<")
    if family == "diagram":
        body = _broken_lines(EDGE_MARKS.sub(_unbarred, body))
    if FORBIDDEN.search(body):
        raise Unusable("Only drawing commands: no import, include, file or plugin.")
    body = _unshadowed(body)
    separator = decimal_separator(body)
    body = _decimal_commas(body, separator == ",")
    preamble = FAMILIES[family].preamble.replace(SEPARATOR, f'#let decimal-separator = "{separator}"')
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
