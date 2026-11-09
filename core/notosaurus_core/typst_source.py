"""What the AI writes in Typst, made what it meant before it is compiled (figures_typst.source
calls these): a package imported again dropped (PACKAGE_IMPORT); a diagram's edges as fletcher
reads them (a bar across a line taken out, marks it can't read made the rule's arrow, a shifted
edge's label on its side) and its texts' new lines as breaks; a circuit's ends a hair apart made
to meet; a variable named after a math symbol renamed where code reads it; a grid's fractional
columns sized by their content; decimal commas as the figure's language writes them; lilaq's
diagram drawn by the preamble's own where it has one (LQ_DIAGRAM).
"""

import math
import re
from collections.abc import Callable

# A package imported by the AI though its family's preamble gives it ("#import
# "@preview/lilaq:0.6.0" as lq" again): the line dropped rather than the figure refused, an AI
# call saved; a package the preamble doesn't give then fails as any unknown name (Typst says so)
PACKAGE_IMPORT = re.compile(r'^[ \t]*#import[ \t]+"@preview/[^"\n]+"[^\n]*\n?', re.M)


# An edge's string with a bar in it ("-|>", "-|-", "-|->"): fletcher's marks
EDGE_MARKS = re.compile(r'"([-<>|.=~]*\|[-<>|.=~]*)"')


def unbarred(marks: re.Match) -> str:
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


# An edge's marks string fletcher can't read: the AI's light model writes the arrow "-|>" as
# "-|Side", "-|Cli", "-|_", "-| >" or "-|/", the more as two arrows each way are shifted aside,
# Typst refusing the whole figure. Read: a line ("-", "--", "..", "=", "~") with a head at
# either end or none, as the rule and fletcher write them; or a mark named (its
# default-marks.typ). Anything else a slip, its bars already dropped (unbarred).
HEAD = r"(?:<\||\|>|<<|>>|<|>|\||[xXoO*@])"
READABLE_MARKS = re.compile(rf"{HEAD}?(?:--|-|\.\.|\.|==|=|~){HEAD}?")
MARK_NAMES = {
    "head", "doublehead", "triplehead", "harpoon", "straight", "solid", "stealth", "latex", "cone", "circle",
    "square", "diamond", "bar", "cross", "bracket", "parenthesis", "hook", "hooks", "crowfoot",
}  # fmt: skip
EDGE_CALL = re.compile(r"(?<![\w.-])edge\(")
STRING = re.compile(r'"(?:[^"\\]|\\.)*"')


def _marks_string(args: str, string: re.Match[str]) -> bool:
    """A string of an edge's that is its marks: an argument of its own (not part of an
    expression), a line or a head first ("-", "<", ".", "=", "~")."""
    text = string.group(0)
    alone = args[: string.start()].rstrip()[-1:] in ("", ",") and args[string.end() :].lstrip()[:1] in ("", ",")
    return alone and (text[1:2] in ("-", "<", ".", "=", "~") or text[1:3] == "|>")


def edges(body: str, fix: Callable[[str], str]) -> str:
    """Each `edge(…)`'s arguments made `fix(arguments)`."""
    out, i = [], 0
    for m in EDGE_CALL.finditer(body):
        if m.start() < i:
            continue
        depth, j = 1, m.end()
        while j < len(body) and depth:
            depth += {"(": 1, ")": -1}.get(body[j], 0)
            j += 1
        out.append(body[i : m.end()] + fix(body[m.end() : j - 1]) + ")")
        i = j
    return "".join(out) + body[i:]


def _readable_marks(marks: str) -> bool:
    """Marks fletcher reads (READABLE_MARKS, MARK_NAMES)."""
    return bool(READABLE_MARKS.fullmatch(marks)) or any(name in marks for name in MARK_NAMES)


def unworded(args: str) -> str:
    """An edge's marks string fletcher can't read (READABLE_MARKS, MARK_NAMES) made the rule's
    arrow ("-|>", "<|-|>" when it began with a head), or dropped where the edge has its marks
    already (another marks string, `marks:`)."""
    strings = [x for x in STRING.finditer(args) if _marks_string(args, x)]
    bad = [x for x in strings if not _readable_marks(x.group(0)[1:-1])]
    marked = len(strings) > len(bad) or re.search(r"(?<![\w-])marks\s*:", args)
    for x in reversed(bad):
        if marked or x is not bad[0]:
            comma = re.match(r"\s*,?", args[x.end() :])
            args = args[: x.start()] + args[x.end() + (comma.end() if comma else 0) :]
        else:
            args = args[: x.start()] + ('"<|-|>"' if x.group(0).startswith('"<') else '"-|>"') + args[x.end() :]
    return args


# An edge shifted aside (one of two arrows each way between two nodes): its label on the side
# it is shifted to, away from its twin (fletcher: a positive shift to the left), whatever side
# the AI wrote: on the other side, the two arrows' labels meet between them.
SHIFT = re.compile(r"(?<![\w-])shift\s*:\s*(-?)\s*\d*\.?\d+\s*(pt|em|mm|cm)?(?=\s*[,)]|\s*$)")
LABEL_SIDE = re.compile(r"(?<![\w-])label-side\s*:\s*(left|right|center)")


def labels_aside(args: str) -> str:
    """A shifted edge's label on its shift's side (SHIFT)."""
    shift = SHIFT.search(args)
    if not shift or not re.search(r"\d*\.?\d*[1-9]", shift.group(0)):
        return args
    side = "right" if shift.group(1) else "left"
    if LABEL_SIDE.search(args):
        return LABEL_SIDE.sub(f"label-side: {side}", args)
    return args + f", label-side: {side}" if "[" in args else args


def broken_lines(body: str) -> str:
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
MATH = re.compile(r"\$[^$]*\$")


def decimal_separator(body: str) -> str:
    """ "," when the figure's language (its `#set text(lang: …)`) writes a decimal comma, else "."."""
    said = LANGUAGE.search(body)
    return "," if said and said.group(1).lower() in DECIMAL_COMMA else "."


def decimal_commas(body: str, comma: bool) -> str:
    """A decimal comma in maths as the language writes it: Typst's maths spaces a comma out
    ("0, 3"), a quoted one stays tight ("0,3"). LaTeX's own (`0{,}3`, the AI writing LaTeX)
    meant one whatever the language; a comma between digits only in a language writing one
    (a list "1,2" in English stays as it was)."""

    def tight_outside_strings(math: str) -> str:
        m = re.sub(r"(\d)\s*\{,\}\s*(?=\d)", r'\1","', math)
        return re.sub(r"(\d),(?=\d)", r'\1","', m) if comma else m

    def tight(math: re.Match) -> str:
        # a number quoted in the formula (`$times "1,5"$`) is text, written as it is: its
        # comma left alone, never cut in two strings ("1", "5": "1, 5")
        pieces = re.split(r'("[^"]*")', math.group(0))
        return "".join(p if i % 2 else tight_outside_strings(p) for i, p in enumerate(pieces))

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


def unshadowed(body: str) -> str:
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


# A grid's or a table's columns (rows) given as fractions of the page (`columns: (1fr, 1fr)`):
# a figure's page is as wide as what it holds, so a fraction of it is nothing, every column
# drawn on the others (four molecules one on another). Each such size made `auto`.
TRACKS = re.compile(r"\b(columns|rows)\s*:\s*(\((?:[^()]|\([^()]*\))*\)|[\d.]+fr\b)")
FRACTION = re.compile(r"(?<![\w.])[\d.]*\d\s*fr\b")


def no_fractions(body: str) -> str:
    """Grids' and tables' fractional tracks sized by their content instead (TRACKS)."""
    return TRACKS.sub(lambda m: f"{m.group(1)}: {FRACTION.sub('auto', m.group(2))}", body)


# A circuit's ends meant to meet, the AI leaving them a hair apart (an arrow ending 0.1 short of
# a lamp): the wire cut there, the circuit drawn open. A wire's or a current's arrow's end closer
# than JOIN to a point of the circuit's (zap's elements, not shapes drawn with cetz) is moved
# onto it, a component's point first: never two of a circuit's points, at least 0.5 apart.
POINT = re.compile(r"\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)")
CALLER = re.compile(r"([\w.-]+)\s*$")
CONNECTORS = {"wire", "current-arrow"}
JOIN = 0.15


def _caller(body: str, at: int) -> str:
    """The name of the call whose parentheses hold position `at` ("" for none)."""
    depth = 0
    for i in range(at - 1, -1, -1):
        if body[i] == ")":
            depth += 1
        elif body[i] == "(":
            if depth == 0:
                m = CALLER.search(body, 0, i)
                return m.group(1) if m else ""
            depth -= 1
    return ""


def joined_ends(body: str) -> str:
    """A circuit's wires and current's arrows ending a hair from a point of it made to meet it."""
    points = []
    for m in POINT.finditer(body):
        name = _caller(body, m.start())
        if name and "." not in name:  # zap's, not a shape drawn with cetz
            points.append((m, (float(m[1]), float(m[2])), name in CONNECTORS))
    targets = sorted({p for _, p, _ in points}, key=lambda p: min(c for _, q, c in points if q == p))
    moved: dict[int, tuple[float, float]] = {}
    for m, point, connector in points:
        if connector:
            near = [t for t in targets if 0 < math.dist(point, t) < JOIN]
            if near:
                moved[m.start()] = near[0]
    if not moved:
        return body
    out, i = [], 0
    for m in POINT.finditer(body):
        if m.start() in moved:
            x, y = moved[m.start()]
            out.append(body[i : m.start()] + f"({x:g}, {y:g})")
            i = m.end()
    return "".join(out) + body[i:]


# A diagram drawn by the preamble's own `diagram-apart` where it has one (graph: the ticks'
# names kept apart, computed), the AI writing lilaq's `lq.diagram(…)` as lilaq documents it
LQ_DIAGRAM = re.compile(r"(?<![\w.-])lq\.diagram(?=\s*\()")
