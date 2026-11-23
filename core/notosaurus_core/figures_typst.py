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
import contextvars
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

from . import files, text_size, typst_source

HERE = Path(__file__).parent
ARCHIVES = HERE / "typst"  # <name>-<version>.tar.gz, as Typst Universe publishes them (tools/typst_packages.py)
FONTS = HERE / "fonts"
COMPILE_S = 15  # a figure compiles in well under a second; a loop never ends
MEMORY = 1024 * 1024 * 1024  # bytes, where the system lets us say so
# The compiler's environment: what Python and the system need to start it, nothing else. The
# server's own (an AI service's key, the relay's secrets) never reaches the process that runs
# Typst on code the AI wrote (a flaw in Typst found one day could read it)
COMPILE_ENV_KEPT = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE")


def compile_env() -> dict[str, str]:
    """The compiling process's environment (COMPILE_ENV_KEPT). Two malloc arenas at most
    (glibc): each thread of Typst's (an image drawn: an icon) reserves an arena of 64 MB of
    address space, counted by MEMORY's limit though unused; a heavy map with icons went past
    it ("memory allocation of 144 bytes failed")."""
    kept = {name: value for name, value in os.environ.items() if name.upper() in COMPILE_ENV_KEPT}
    return {**kept, "MALLOC_ARENA_MAX": "2"}


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
# a panel of a figure in panels: any kind but panels
PanelKind = Literal[
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
FigureKind = Literal[PanelKind, "panels"]


class Kind(BaseModel):
    family: FigureKind


class Panel(BaseModel):
    """One of a figure's panels: its kind, and what it shows, said as a figure's description."""

    family: PanelKind
    description: str


class Panels(BaseModel):
    panels: list[Panel]


PANELS_RULES = (
    "A figure for a pupil's flashcard is described below: it shows several things of different kinds "
    "side by side. Split it into its panels, from left to right, two or three: for each, its kind and "
    "its own description, written as the figure's description is, with every name, value and unit it "
    "gives for that panel, nothing added; what the panels share (a value, a name) written in each that "
    f"shows it. The kinds: {KINDS}."
)


# What a body may not do: load anything (the packages are given), read a file. Refused as
# names wherever Typst reads them as code (code_view), not only as calls: a name held in a
# variable (`#let r = read`), a package's name in a string imported from it (`#let p =
# "@preview/…"`, `import p`), Typst's own library reached by `std` (`std.read`), are calls
# too. A label's or a comment's words never refused ("import / export", "the json format"):
# a string or a text is used as code only through one of these names, written as code.
# `image`, a name a body's code may hold as a label's word (`content(…, "image")` aside), is
# given another value instead (SHADOWED): the body's `image`, however it is reached, draws
# nothing and says so.
FORBIDDEN_WORDS = ("import", "include", "eval", "std", "read", "json", "csv", "yaml", "toml", "xml", "cbor", "plugin")
# (a data format's text written or read from a string, `json.encode(…)`, reads no file)
FORBIDDEN = re.compile(rf"(?<![\w-])({'|'.join(FORBIDDEN_WORDS)})(?![\w-])(?!\.(?:en|de)code(?![\w-]))")
# after the preamble: its own functions keep Typst's (icon(): a function keeps the names it was
# defined with)
SHADOWED = '#let image(..args) = panic("No image: only drawing commands.")\n'
# The modules a preamble imports whole ("#import "@preview/cetz:0.5.2"", "… as lq"): a body
# may import from them (`import cetz.draw: *`), never anything else; the module it imports
# from never given another value (`cetz = (draw: "@preview/…")`): its name always followed by
# a field
MODULES = sorted(
    {
        alias or source.removeprefix("@preview/").partition(":")[0]
        for family in FAMILIES.values()
        for source, alias, listed in re.findall(
            r'^#import\s+"(@preview/[^"]+)"\s*(?:as\s+([\w-]+))?\s*(?::\s*([^\n]*))?$', family.preamble, re.M
        )
        if alias or not listed
    }
)
_MODULE_IMPORT = re.compile(
    rf"(?<![\w-])import\s+({'|'.join(map(re.escape, MODULES))})(?:\.[A-Za-z_][\w-]*)*(?=[ \t]*(?::|as\b|[;\n}}]|$))"
)


# Statements an embedded `#` starts in a text, that run to the line's end (`#let r = read`)
_STATEMENTS = frozenset(
    ("let", "set", "show", "import", "include", "if", "for", "while", "context", "return", "break", "continue")
)


def _closing(text: str, start: int, end: str) -> int:
    """Where `end` closes what opens at start (a string's quote, a raw's backticks): just
    past it; -1 when it never does."""
    i = start
    while i < len(text):
        if text[i] == "\\" and end == '"':
            i += 2
        elif text.startswith(end, i):
            return i + len(end)
        else:
            i += 1
    return -1


def _comment_end(text: str, i: int) -> int:
    """Just past the comment starting at i (`//` to the line's end, `/* … */` nested); -1
    when a block comment never closes."""
    if text.startswith("//", i):
        end = text.find("\n", i)
        return len(text) if end < 0 else end
    depth = 0
    while i < len(text):
        if text.startswith("/*", i):
            depth, i = depth + 1, i + 2
        elif text.startswith("*/", i):
            depth, i = depth - 1, i + 2
            if not depth:
                return i
        else:
            i += 1
    return -1


def code_view(body: str) -> str | None:
    """The body as Typst reads its code: what is code kept where it stands, the rest (a text,
    a string, a comment, a raw text) blanked, its lines kept. The body is a text (markup): `#`
    starts code there, one expression (`#f(x)[y].z`) or a statement to the line's end (`#let
    …`), `{…}` and `(…)` are code, `[…]` a text again, `$…$` a formula (its names code too).
    Where it can't be told (a string, a comment, a bracket never closed), None: every word then
    checked. What is unsure is taken as code: a text's `[` nests nothing (its first `]` closes
    it), a `//` after `:` is a link, not a comment."""
    out = [c if c == "\n" else " " for c in body]
    stack: list[list] = [["markup", None, True]]  # kind, its closing character, started
    i, n = 0, len(body)
    while i < n:
        kind, closer, started = stack[-1]
        c = body[i]
        if c == "`" and kind != "math":  # a raw text: `x`, ```x```; two alone an empty one
            run = len(body[i:]) - len(body[i:].lstrip("`"))
            end = i + run if run == 2 else _closing(body, i + run, "`" * run)
            if end < 0:
                return None
            if kind == "embed":
                stack[-1][2] = True
            i = end
            continue
        if kind in ("markup", "math"):
            if c == "\\":
                i += 2
            elif body.startswith(("//", "/*"), i) and not (kind == "markup" and body[i - 1 : i] == ":"):
                i = _comment_end(body, i)
                if i < 0:
                    return None
            elif c == "#":
                i += 1
                if i < n and (body[i].isalpha() or body[i] == "_"):
                    word = re.match(r"[^\W\d][\w-]*", body[i:])
                    statement = word is not None and word.group(0) in _STATEMENTS
                    stack.append(["line" if statement else "embed", None, False])
                elif i < n and body[i] in '{(["':
                    stack.append(["embed", None, False])
            elif kind == "math" and c == '"':
                i = _closing(body, i + 1, '"')
                if i < 0:
                    return None
            elif kind == "math" and (c.isalnum() or c == "_"):
                start = i
                while i < n and (body[i].isalnum() or body[i] == "_"):
                    i += 1
                out[start:i] = body[start:i]
            elif c == "$" and kind == "markup":
                stack.append(["math", "$", True])
                i += 1
            elif c == closer:  # a text's `]`, a formula's `$`
                stack.pop()
                i += 1
            else:
                i += 1
            continue
        # code: a block's, an embedded expression's (embed), a statement's (line)
        if kind == "embed" and started and not (c.isalnum() or c in "_-.([{"):
            stack.pop()  # the expression ends: a text again
            continue
        if kind == "line" and c in "\n;":
            rest = body[i + 1 :].lstrip()
            if c == "\n" and re.match(r"else(?![\w-])", rest):  # `}` then `else` on the next line
                i += 1
                continue
            stack.pop()
            continue
        if kind == "line" and (c == "]" or (c == "$" and stack[-2][0] == "math")):
            stack.pop()  # the statement ends with the text or the formula it is in
            continue
        if kind == "embed":
            stack[-1][2] = True
        if c == '"':
            i = _closing(body, i + 1, '"')
            if i < 0:
                return None
        elif body.startswith(("//", "/*"), i):
            i = _comment_end(body, i)
            if i < 0:
                return None
        elif c in "({":
            out[i] = c
            stack.append(["code", ")" if c == "(" else "}", True])
            i += 1
        elif c == "[":
            stack.append(["markup", "]", True])
            i += 1
        elif c == "$":
            stack.append(["math", "$", True])
            i += 1
        elif c in ")}]":
            if kind != "code" or c != closer:
                return None  # closes what isn't open
            out[i] = c
            stack.pop()
            i += 1
        else:
            out[i] = c
            i += 1
    if any(kind in ("code", "math") or (kind == "markup" and closer) for kind, closer, _ in stack):
        return None  # never closed
    return "".join(out)


def forbidden(body: str) -> str:
    """What a body may not write as code (FORBIDDEN), the first found; "" when it has none.
    Its imports from a preamble's module (MODULES) aside, the module's name always a module's.
    A body whose code can't be told (code_view) has every word checked."""
    code = code_view(body)
    code = body if code is None else code
    rest = _MODULE_IMPORT.sub("", code)
    if found := FORBIDDEN.search(rest):
        return found.group(1)
    for module in sorted({m.group(1) for m in _MODULE_IMPORT.finditer(code)}):
        if re.search(rf"(?<![\w.-]){re.escape(module)}(?![\w-])(?!\.)", rest):
            return module
    return ""


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


ICONS = "notosaurus-icons"  # common.typ's icon(), imported by every family
# A timeline's event with its icon: (date, "text", "word"), the word an icon's
_TIMELINE_ICON = re.compile(r'\(\s*[^()]*?,\s*(?:"[^"]*"|\[[^\]]*\])\s*,\s*"[^"]+"\s*,?\s*\)')


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
        if package == ICONS:  # in every preamble (common.typ): only a figure that draws an icon
            reached = _calls(body, "icon") or (family == "timeline" and bool(_TIMELINE_ICON.search(body)))
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


class TooSmall(Unusable):
    """Drawn, but its text too small to read once fitted to a card (readable_px): its SVG and
    that text's height in px, kept when no drawing again does better."""

    def __init__(self, message: str, svg: str, px: float):
        super().__init__(message)
        self.svg = svg
        self.px = px


CARD_PX = text_size.CARD_PX
# A figure's text under this, once fitted to a card, is too small to read: measured in every
# figure of the subjects' benches (3,000 drawings, 1,100 judged right by eye at 320 px), the
# texts judged unreadable came to 3.3 to 6.9 px (institutions spread 26 cm wide, a cycle in
# one long row); at 7, 18 of the right ones would be drawn again (2 %), at 7.5, 38, none
# more of the unreadable ones caught.
MIN_TEXT_PX = 7.0
# A family whose text and its room are set by its preamble, the AI giving only what it says: a
# timeline's names and years, a tree's species, a chart's bars, read at 6.3 to 7 px (judged
# right, all: a frise of the Second World War, a law of 21 bars); drawn again, the AI could only
# write less. Still refused far below (a box plot's axis spread 65 cm: 4 px).
MIN_TEXT_PX_SET = {"timeline": 6.0, "phylogeny": 6.0, "chart": 6.0}


# An icon under this, once the figure is fitted to a card, is a speck (common.typ's icon(): 1.4
# times its text, a 7 px text's at 10 px): grown round its middle, up to twice its size, so as
# not to lie on what is beside it; smaller still, the figure refused
MIN_ICON_PX = 9.0
MAX_ICON_GROWTH = 2.0
# The icons a figure asked for and didn't get (a word no icon has, an SVG of its own that can't
# be drawn): nothing drawn in their place, their words kept here when the caller asks (the
# bench: what to tag next)
icons_missing: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar("icons_missing", default=None)
_ICON_IMAGE = re.compile(r'<image\b[^>]*href="data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)"[^>]*/>')


def _icons_missing(svg: str) -> str:
    """The figure without the marks of its icons not drawn (common.typ's icon()), their words
    kept in icons_missing."""
    missing = icons_missing.get()

    def drop(m: re.Match) -> str:
        inner = base64.b64decode(m[1]).decode("utf-8", "replace")
        found = re.search(r"<!--notosaurus-icon-missing:(.*?)-->", inner)
        if not found:
            return m[0]
        if missing is not None:
            missing.append(html.unescape(found[1]))
        return ""

    return _ICON_IMAGE.sub(drop, svg)


def _icons_grown(svg: str, growth: float) -> str:
    """The figure, its icons each grown `growth` times round its middle."""

    def grow(m: re.Match) -> str:
        if text_size.ICON_MARK not in base64.b64decode(m[1]).decode("utf-8", "replace"):
            return m[0]
        tag = m[0]
        w = float(re.search(r'\swidth="([\d.]+)"', tag)[1])  # type: ignore[index]
        h = float(re.search(r'\sheight="([\d.]+)"', tag)[1])  # type: ignore[index]
        x = float((re.search(r'\sx="([-\d.]+)"', tag) or [0, 0])[1])
        y = float((re.search(r'\sy="([-\d.]+)"', tag) or [0, 0])[1])
        tag = re.sub(r'\s(x|y|width|height)="[^"]*"', "", tag)
        place = (
            f' x="{x - (growth - 1) * w / 2:.3f}" y="{y - (growth - 1) * h / 2:.3f}"'
            f' width="{w * growth:.3f}" height="{h * growth:.3f}"'
        )
        return tag.replace("<image", "<image" + place, 1)

    return _ICON_IMAGE.sub(grow, svg)


def readable_px(svg: str) -> float | None:
    """The height in px of a figure's smallest text once fitted to a card (text_size); None:
    no text."""
    return text_size.smallest_px(svg)


def too_small(family: str, body: str, svg: str) -> TooSmall | None:
    """The refusal of a figure whose text can't be read on a card, telling the AI its size and
    how to draw it so it can; None when it can be read."""
    px = readable_px(figures_clean(svg) if family == "scratch" else svg)
    least = MIN_TEXT_PX_SET.get(family, MIN_TEXT_PX)
    if px is None or px >= least:
        return None
    width, height = text_size.size(svg)
    said = (
        f"Too small to read on a card: it is {width:.0f} wide and {height:.0f} high (Typst's pt); fitted to a "
        f"phone ({CARD_PX[0]} px wide, {CARD_PX[1]} high), its smallest text is {px:.1f} px high, {least:g} at "
        "least. Draw it more compactly, so that it fits a card at nearly its own size: "
    )
    if family == "diagram":
        said += "fewer boxes side by side, each box's text and each arrow's words shorter, no text made smaller"
        if re.search(r"(?<![\w.-])diagram\s*\(", body):  # fletcher's nodes, placed by the AI
            said += "; boxes joined by arrows that are no chain, cycle or flowchart drawn by #scheme, which places them"
            said += " itself"
        said += "."
    else:
        said += "less wide or less high (a smaller scale, things closer together, shorter words), no text made smaller."
    return TooSmall(said, svg, px)


def figures_clean(svg: str) -> str:
    """The SVG cleaned as a card shows it (figures.clean: blockst's blocks drawn in their place)."""
    from . import figures

    try:
        return figures.clean(svg)
    except figures.FigureError:  # refused by the cleaning, as it is on the way to the card
        return svg


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
    if word := forbidden(body):
        raise Unusable(
            "Only drawing commands: no import (but from a module given: import cetz.draw: *), include, "
            f'file or plugin. "{word}" is refused, even held in a variable or in a text: write it otherwise.'
        )
    body = typst_source.latex_math(typst_source.no_fractions(typst_source.unshadowed(body)))
    separator = typst_source.decimal_separator(body)
    body = typst_source.decimal_commas(body, separator == ",")
    preamble = FAMILIES[family].preamble.replace(SEPARATOR, f'#let decimal-separator = "{separator}"')
    if "#let diagram-apart(" in preamble:
        body = typst_source.LQ_DIAGRAM.sub("diagram-apart", body)
    if "#let line-kept(" in preamble:
        body = typst_source.LQ_LINE.sub("line-kept", body)
    return FONT + preamble + SHADOWED + body.strip() + "\n"


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
        _remove_others(folder)
    except OSError:
        if not folder.is_dir():  # not another process's, unpacked meanwhile
            raise
    finally:
        shutil.rmtree(aside, ignore_errors=True)
    return folder


_UNPACKED = re.compile(r"typst-[0-9a-f]{12}")  # packages()'s folders (not one being written aside)


def _remove_others(folder: Path) -> None:
    """The packages unpacked from other archives (an older version's, about 30 MB each)
    removed, `folder` kept: what can't be (another process still reading it) left as it is,
    a link never followed."""
    try:
        others = [p for p in folder.parent.iterdir() if p != folder and _UNPACKED.fullmatch(p.name)]
    except OSError:
        return
    for other in others:
        if not other.is_symlink() and other.is_dir():
            shutil.rmtree(other, ignore_errors=True)


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
    language's, _if_words). Another image (an icon) left as it is: written again, it would lose
    its comments, an icon's mark (text_size.ICON_MARK) among them."""

    def inner(m: re.Match) -> str:
        drawn = ElementTree.fromstring(base64.b64decode(m.group(1)).decode("utf-8"))
        dropped = False
        for block in drawn.iter():
            arrows = [c for c in block if c.tag.endswith("use") and c.get("href") == "#sb-loopArrow"]
            first = next((c.text or "" for c in block if c.tag.endswith("text") and (c.text or "").strip()), "")
            if arrows and first.strip() in _if_words():
                for arrow in arrows:
                    block.remove(arrow)
                dropped = True
        if not dropped:
            return m.group(0)
        ElementTree.register_namespace("", "http://www.w3.org/2000/svg")
        out = ElementTree.tostring(drawn, encoding="unicode")
        return f'href="data:image/svg+xml;base64,{base64.b64encode(out.encode()).decode()}"'

    return _SVG_IMAGE.sub(inner, svg)


def compiled(document: str) -> str:
    """A Typst document's SVG, compiled apart (COMPILER); Unusable when Typst refuses it (its
    message) or takes too long."""
    with tempfile.TemporaryDirectory(prefix="notosaurus-figure-") as folder:
        path = Path(folder) / "figure.typ"
        path.write_text(document, encoding="utf-8")
        try:
            done = subprocess.run(
                [sys.executable, "-P", str(COMPILER), str(MEMORY), str(path), folder, str(packages()), str(FONTS)],
                capture_output=True,
                timeout=COMPILE_S,
                env=compile_env(),
            )
        except subprocess.TimeoutExpired as e:
            raise Unusable("It took too long to compile (a loop?): draw it more simply.") from e
    if done.returncode != 0 or not done.stdout:
        said = done.stderr.decode("utf-8", "replace").strip()
        raise Unusable(said[:800].replace(str(path), "figure.typ") or "It didn't compile.")
    return done.stdout.decode("utf-8")


def compile_svg(family: str, body: str) -> str:
    """The figure's SVG, its colours as drawn; Unusable when Typst refuses it (its message),
    takes too long or draws nothing (an empty answer: a blank page on the card, never redrawn);
    TooSmall when its text can't be read on a card (too_small)."""
    svg = compiled(source(family, body))
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
    if refused := too_small(family, body, svg):
        raise refused
    svg = _icons_missing(svg)
    if (icons := text_size.icons_px(svg)) and min(icons) < MIN_ICON_PX:
        if MIN_ICON_PX / min(icons) > MAX_ICON_GROWTH:
            raise Unusable(
                f"An icon is too small to see on a card: fitted to a phone ({CARD_PX[0]} px wide), it is "
                f"{min(icons):.1f} px high, {MIN_ICON_PX:g} at least. Give the icons a larger size (icon(…, size: "
                "2em)) or draw the figure more compactly."
            )
        svg = _icons_grown(svg, MIN_ICON_PX / min(icons))
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
