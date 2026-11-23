"""A card's formulas as they go to Anki: none of MathJax's `html` commands.

Anki and AnkiDroid draw a card's formulas, `\\( … \\)` and `\\[ … \\]`, with MathJax and its
`html` extension: `\\href` a link, `\\style` any CSS, `\\class`, `\\cssId` and `\\data` the
card's own classes, ids and attributes. A card's text comes from the AI, an imported or a
shared lesson: escaped as HTML, its formulas would still add links and styles of their own
at review. So inside a formula, `\\style{color: X}{…}` (one colour: a name, #hex or rgb(…))
becomes `{\\color{x}{…}}` (MathJax's colour, as Anki has it; in lower case, as CSS reads it:
MathJax's own "Red" is another red), and every other of these
commands its name written as text (`\\backslash\\text{href}`), its arguments as math: shown,
never run. Text outside formulas is left as it is (Anki shows it as text).

The formulas are found as Anki's MathJax finds them (its ts/mathjax: `\\(` and `\\[` only,
no environment, no escape; MathJax's FindTeX: the closing delimiter outside braces). A text
with gaps is drawn by Anki once per gap, its gaps' markup taken out first (`{{c1::…}}`, its
hint, the line breaks inside a formula): one where any of these still holds such a command
(two pieces joined, or one outside a formula) has every backslash written as "＼", its
formulas then shown as written.

The Android app does the same (Formulas.kt), shared cases (core/shared-cases.json) pinning
both."""

import re

# MathJax's html extension's commands
HTML_COMMANDS = ["href", "style", "class", "cssId", "data"]

_START = re.compile(r"\\[(\[]")
_CLOSE = {"\\(": "\\)", "\\[": "\\]"}
# FindTeX's end pattern: the closing delimiter, a backslash and its next character (not a line
# break: JavaScript's "."), a brace
_END = {close: re.compile(re.escape(close) + r"|\\(?:[a-zA-Z]|[^\n\r\u2028\u2029])|[{}]") for close in _CLOSE.values()}
_COMMAND = re.compile(r"\\([a-zA-Z]+)?")
_COLOUR = re.compile(
    r"\s*color\s*:\s*(#(?:[0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})|[a-z]{1,30}"
    r"|rgba?\(\s*[0-9.]+%?(?:\s*,\s*[0-9.]+%?){2,3}\s*\))\s*;?\s*",
    re.IGNORECASE,
)
_NAMED = re.compile(r"\\(?:" + "|".join(HTML_COMMANDS) + r")(?![a-zA-Z])")
_CLOZE = re.compile(r"\{\{c([0-9]+)::|\}\}")


def anki_text(text: str) -> str:
    """`text` as it goes into an Anki field (before it is escaped): its formulas without
    MathJax's html commands."""
    text = _formulas(text)
    if "{{c" in text and any(_NAMED.search(drawn) for drawn in _drawn(text)):
        return text.replace("\\", "＼")
    return text


def _formulas(text: str) -> str:
    """Every formula of `text` rewritten (_math), found as MathJax's FindTeX finds them."""
    out, done, at = [], 0, 0
    while start := _START.search(text, at):
        close = _CLOSE[start[0]]
        end = _end(text, start.end(), close)
        if end is None:  # never closed: not a formula, the next one looked for after it
            at = start.end()
            continue
        out += [text[done : start.end()], _math(text[start.end() : end])]
        done, at = end, end + len(close)
    return "".join(out) + text[done:]


def _end(text: str, at: int, close: str) -> int | None:
    braces = 0
    for token in _END[close].finditer(text, at):
        if token[0] == close and not braces:
            return token.start()
        if token[0] == "{":
            braces += 1
        elif token[0] == "}" and braces:
            braces -= 1
    return None


def _math(math: str) -> str:
    """A formula's TeX without the html commands: a `\\style` of a colour as `\\color`, the
    others' names as text. A command's name is its letters (`\\\\href`: a line break, then
    "href")."""
    out, done, at = [], 0, 0
    while command := _COMMAND.search(math, at):
        name = command[1]
        if name not in HTML_COMMANDS:
            at = command.end() + (0 if name else 1)  # `\x`: a command; `\{`, `\\`: a symbol
            continue
        out.append(math[done : command.start()])
        css = _argument(math, command.end()) if name == "style" else None
        body = _argument(math, css[1]) if css else None
        colour = _COLOUR.fullmatch(css[0]) if css else None
        if css and body and colour:
            out.append(f"{{\\color{{{colour[1].lower()}}}{{{_math(body[0])}}}}}")
            done = at = body[1]
        else:
            out.append(f"\\backslash\\text{{{name}}}")
            done = at = command.end()
    return "".join(out) + math[done:]


def _argument(math: str, at: int) -> tuple[str, int] | None:
    """The braced argument from `at` (spaces before it skipped), as MathJax reads it, and
    where it ends; None if the next argument isn't braced or never closes."""
    while at < len(math) and math[at].isspace():
        at += 1
    if at >= len(math) or math[at] != "{":
        return None
    start, depth, at = at + 1, 1, at + 1
    while at < len(math):
        c = math[at]
        at += 1
        if c == "\\":
            at += 1
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if not depth:
                return math[start : at - 1], at
    return None


def _drawn(text: str) -> list[str]:
    """What Anki draws of a text with gaps, its markup out (rslib's cloze.rs): the answer
    (every gap shown), each gap's question (that one "[…]" or "[its hint]", the others
    shown); without line breaks (Anki takes the HTML out of a formula, <br> included)."""
    nodes = _gaps(text)
    asked = {None, *_ordinals(nodes)}
    return [_shown(nodes, ordinal).replace("\n", "") for ordinal in asked]


def _gaps(text: str) -> list:
    """`text` parsed as Anki parses gaps: "{{cN::" opens one, "}}" closes the last open, the
    text after "::" in a gap its hint; a gap never closed is left out."""
    output: list = []
    open_gaps: list[tuple[int, list, list]] = []  # number, nodes, [hint]
    at = 0
    while at < len(text):
        token = _CLOZE.search(text, at)
        while token and token[1] is not None and int(token[1]) > 65535:  # not a gap's number (u16)
            token = _CLOZE.search(text, token.start() + 1)
        end = token.start() if token else len(text)
        if end > at:
            plain = text[at:end]
            if open_gaps:
                head, colons, tail = plain.partition("::")
                if colons:
                    plain, open_gaps[-1][2][:] = head, [tail]
                open_gaps[-1][1].append(plain)
            else:
                output.append(plain)
        if not token:
            break
        at = token.end()
        if token[1] is not None:
            open_gaps.append((int(token[1]), [], []))
        elif open_gaps:
            number, nodes, hint = open_gaps.pop()
            (open_gaps[-1][1] if open_gaps else output).append((number, nodes, hint[0] if hint else None))
        else:
            output.append("}}")
    return output


def _ordinals(nodes: list) -> set[int]:
    return {n for node in nodes if isinstance(node, tuple) for n in (node[0], *_ordinals(node[1]))}


def _shown(nodes: list, asked: int | None) -> str:
    return "".join(
        node
        if isinstance(node, str)
        else f"[{node[2] if node[2] is not None else '...'}]"
        if node[0] == asked
        else _shown(node[1], asked)
        for node in nodes
    )
