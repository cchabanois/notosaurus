"""How large a figure's text is on a card: its smallest text's height in px once the figure is
fitted to a phone's card (CARD_PX), read in its SVG, whichever way it was drawn.

Typst writes each letter as a shape (a <symbol>, its outline at its size, in the figure's
units): its size is found by matching the outline's box to the same letter's drawn at a known
size (_glyphs: the figures' font and the formulas', drawn once by Typst). The AI's own SVG
writes <text> with a font-size. A script (an exponent, an index: "cm²", "v_max") is set
smaller on purpose, beside the text it belongs to: not counted. A letter matched to none (a
formula's arrow over a vector, a script's own glyph) is not counted either, nor a scale's fine
print (FINE_PRINT_PT)."""

import functools
import math
import re
from dataclasses import dataclass
from xml.etree import ElementTree

# A card shows a figure at most 320 px wide and 400 high (a phone's: note-types.json, its
# picture's max-width and max-height), never larger than its size (Typst's pt, a px each)
CARD_PX = (320, 400)

# Typst's text set this small at the figure's own size (in pt) is a scale's, set so on purpose,
# never the figure's words: a protractor's degrees (5.5 pt, as on the instrument)
FINE_PRINT_PT = 6.0
CALIBRATION_PT = 100  # the size the letters are drawn at to be known
# The letters a figure writes: the font's (Latin, Greek, figures' signs), the formulas'
_TEXT = (
    "".join(chr(c) for c in range(0x21, 0x7F))
    + "".join(chr(c) for c in range(0xA1, 0x180) if c != 0xAD)
    + "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩαβγδεζηθικλμνξοπρςστυφχψω"
    + "–—‘’‚“”„†•…‰′″‹›€™−×÷±≤≥≠≈∞→←↑↓↔⇒⇔∈∉⊂∪∩∅√∑∏∫∂∆°ℓ⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻₀₁₂₃₄₅₆₇₈₉₊₋"
)
_MATH = (
    "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "αβγδεζηθικλμνξπρστυφχψωΓΔΘΛΞΠΣΦΨΩ+−=×÷<>≤≥()[],.;:!′∞→←↔⇒⇔·∈∉⊂∪∩∅∑∏∫∂∆≈≠±…%°"
)


def _math(c: str) -> str:
    return "\\" + c if c.isascii() and not c.isalnum() else c


def calibration() -> str:
    """The Typst document that draws every letter of _TEXT and _MATH at CALIBRATION_PT, each
    apart (no ligature), in the font's regular, bold and oblique, and the formulas' italic and upright."""
    text = '"' + " ".join(_TEXT).replace("\\", "\\\\").replace('"', '\\"') + '"'
    math_ = " ".join(f"${_math(c)}$" for c in _MATH)
    upright = " ".join(f"$upright({c})$" for c in _MATH if c.isalpha())
    return (
        "#set page(width: 2000pt, height: auto, margin: 1pt)\n"
        f'#set text(font: "DejaVu Sans", size: {CALIBRATION_PT}pt)\n'
        f"#{{ let t = {text}; t; parbreak(); strong(t); parbreak(); emph(t) }}\n\n{math_}\n\n{upright}\n"
    )


_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_COMMAND = re.compile(r"([MmLlHhVvQqCcTtSsAaZz])([^MmLlHhVvQqCcTtSsAaZz]*)")
_ARGUMENTS = {"M": 2, "L": 2, "H": 1, "V": 1, "Q": 4, "C": 6, "T": 2, "S": 4, "A": 7, "Z": 0}


def path_box(d: str) -> tuple[float, float, float, float] | None:
    """The box of a path's points (its curves' control points with them), as a glyph's box
    is: left, bottom, right, top; None when it draws nothing. A move alone ("M 0 0" before
    Typst's "m") is no point of it."""
    x = y = start_x = start_y = 0.0
    xs: list[float] = []
    ys: list[float] = []
    for command, arguments in _COMMAND.findall(d):
        values = [float(v) for v in _NUMBER.findall(arguments)]
        kind, relative, n = command.upper(), command.islower(), _ARGUMENTS[command.upper()]
        if kind == "Z":
            x, y = start_x, start_y
            continue
        if kind != "M":
            xs.append(x)
            ys.append(y)
        for i in range(0, len(values) - n + 1, n):
            p = values[i : i + n]
            if kind == "H":
                x = x + p[0] if relative else p[0]
            elif kind == "V":
                y = y + p[0] if relative else p[0]
            else:
                points = [(p[j], p[j + 1]) for j in range(0, n, 2)] if kind != "A" else [(p[5], p[6])]
                if relative:
                    points = [(x + px, y + py) for px, py in points]
                for px, py in points[:-1]:
                    xs.append(px)
                    ys.append(py)
                x, y = points[-1]
            if kind == "M" and i == 0:
                start_x, start_y = x, y
            if kind != "M" or i > 0:  # a move's further pairs are lines
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


_KEY = 100  # the index's precision: a glyph's box, its height 1, to the hundredth


def _key(box: tuple[float, float, float, float]) -> tuple[int, int, int]:
    left, bottom, right, top = box
    h = top - bottom
    return round(left / h * _KEY), round(bottom / h * _KEY), round(right / h * _KEY)


class Glyphs:
    """The letters known, by the shape of their box (its height 1): their box at 1 pt."""

    def __init__(self, svg: str):
        self.index: dict[tuple[int, int, int], list[tuple[float, float, float, float]]] = {}
        for box in _symbols(ElementTree.fromstring(svg)).values():
            if box is not None and box[3] - box[1] > 0:
                unit = tuple(v / CALIBRATION_PT for v in box)
                self.index.setdefault(_key(box), []).append(unit)  # type: ignore[arg-type]

    def sizes(self, box: tuple[float, float, float, float]) -> set[float]:
        """The sizes (in the figure's units) a letter of this box is drawn at: none for no
        known letter."""
        left, bottom, right, top = box
        h = top - bottom
        if h <= 1e-6:
            return set()
        a, b, c = _key(box)
        found = set()
        for da in (-1, 0, 1):
            for db in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    for unit in self.index.get((a + da, b + db, c + dc), ()):
                        size = h / (unit[3] - unit[1])
                        slack = 1e-3 * size + 1e-3  # Typst writes its outlines to the billionth
                        if (
                            abs(left - unit[0] * size) < slack
                            and abs(bottom - unit[1] * size) < slack
                            and abs(right - unit[2] * size) < slack
                        ):
                            found.add(round(size, 3))
        return found


@functools.cache
def glyphs() -> Glyphs:
    """The letters known, drawn once by this Typst (figures_typst: its fonts, the formulas')."""
    from . import figures_typst

    return Glyphs(figures_typst.compiled(calibration()))


def _local(tag: object) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _symbols(root: ElementTree.Element) -> dict[str, tuple[float, float, float, float] | None]:
    found = {}
    for e in root.iter():
        if _local(e.tag) == "symbol" and e.get("id"):
            paths = " ".join(p.get("d", "") for p in e.iter() if _local(p.tag) == "path")
            found[e.get("id", "")] = path_box(paths)
    return found


Matrix = tuple[float, float, float, float, float, float]
_IDENTITY: Matrix = (1, 0, 0, 1, 0, 0)
_TRANSFORM = re.compile(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)")


def _times(m: Matrix, n: Matrix) -> Matrix:
    return (
        m[0] * n[0] + m[2] * n[1],
        m[1] * n[0] + m[3] * n[1],
        m[0] * n[2] + m[2] * n[3],
        m[1] * n[2] + m[3] * n[3],
        m[0] * n[4] + m[2] * n[5] + m[4],
        m[1] * n[4] + m[3] * n[5] + m[5],
    )


def _matrix(transform: str | None) -> Matrix:
    m = _IDENTITY
    for name, arguments in _TRANSFORM.findall(transform or ""):
        a = [float(v) for v in _NUMBER.findall(arguments)] or [0.0]
        if name == "matrix" and len(a) == 6:
            n: Matrix = (a[0], a[1], a[2], a[3], a[4], a[5])
        elif name == "translate":
            n = (1, 0, 0, 1, a[0], a[1] if len(a) > 1 else 0)
        elif name == "scale":
            n = (a[0], 0, 0, a[1] if len(a) > 1 else a[0], 0, 0)
        elif name == "rotate":
            r = math.radians(a[0])
            n = (math.cos(r), math.sin(r), -math.sin(r), math.cos(r), 0, 0)
            if len(a) == 3:
                n = _times(_times((1, 0, 0, 1, a[1], a[2]), n), (1, 0, 0, 1, -a[1], -a[2]))
        elif name in ("skewX", "skewY"):
            t = math.tan(math.radians(a[0]))
            n = (1, 0, t, 1, 0, 0) if name == "skewX" else (1, t, 0, 1, 0, 0)
        else:
            continue
        m = _times(m, n)
    return m


def _scale(m: Matrix) -> float:
    return math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))


@dataclass
class Run:
    """A run of text drawn at one size: its size, where it stands (left, right, baseline), in
    the figure's units; a script when the text says so (an SVG's baseline-shift)."""

    size: float
    left: float
    right: float
    base: float
    script: bool = False


_FONT_SIZE = re.compile(r"([\d.]+)\s*(px|pt|em|rem|%)?")


def _font_size(value: str, inherited: float) -> float:
    m = _FONT_SIZE.match(value.strip())
    if not m:
        return inherited
    size, unit = float(m[1]), m[2]
    if unit == "pt":
        return size * 4 / 3
    if unit in ("em", "rem"):
        return size * inherited
    if unit == "%":
        return size / 100 * inherited
    return size


def _style(e: ElementTree.Element, name: str) -> str | None:
    found = re.search(rf"(?:^|;)\s*{name}\s*:\s*([^;]+)", e.get("style") or "")
    return found[1].strip() if found else e.get(name)


def runs(svg: str) -> list[Run]:
    """The figure's runs of text, each at its size, where it stands, in the figure's units."""
    root = ElementTree.fromstring(svg)
    symbols = _symbols(root)
    known = glyphs() if symbols else None
    found: list[Run] = []

    def walk(e: ElementTree.Element, m: Matrix, size: float, top: bool = False) -> None:
        tag = _local(e.tag)
        if tag in ("defs", "symbol", "marker", "clipPath", "mask", "pattern", "title", "desc", "style"):
            return
        m = _times(m, _matrix(e.get("transform")))
        if tag == "svg" and not top:  # an SVG within (blockst's blocks, inlined): its frame its scale
            box = [float(v) for v in _NUMBER.findall(e.get("viewBox") or "")]
            if len(box) == 4 and box[2] > 0 and box[3] > 0:
                w, h = _NUMBER.match(e.get("width") or ""), _NUMBER.match(e.get("height") or "")
                k = min(float(w[0]) / box[2] if w else 1.0, float(h[0]) / box[3] if h else 1.0)
                x, y = float(e.get("x") or 0), float(e.get("y") or 0)
                m = _times(m, (k, 0, 0, k, x - box[0] * k, y - box[1] * k))
        if (value := _style(e, "font-size")) is not None:
            size = _font_size(value, size)
        if tag in ("text", "tspan") and (e.text or "").strip():
            x = float((_NUMBER.findall(e.get("x") or "") or [0])[0])
            y = float((_NUMBER.findall(e.get("y") or "") or [0])[0])
            shift = (_style(e, "baseline-shift") or "").strip()
            k = _scale(m)
            left = m[0] * x + m[2] * y + m[4]
            found.append(
                Run(
                    size * k,
                    left,
                    left + 0.55 * size * k * len(e.text or ""),
                    m[1] * x + m[3] * y + m[5],
                    script=tag == "tspan" and shift not in ("", "0", "baseline"),
                )
            )
        uses = [c for c in e if _local(c.tag) == "use"]
        if uses and known is not None:
            votes: dict[float, int] = {}
            left = right = None
            for use in uses:
                href = next((v for k, v in use.attrib.items() if _local(k) == "href"), "").removeprefix("#")
                box = symbols.get(href)
                if box is None:
                    continue
                x = float(use.get("x") or 0)
                left = x + box[0] if left is None else min(left, x + box[0])
                right = x + box[2] if right is None else max(right, x + box[2])
                for s in known.sizes(box):
                    votes[s] = votes.get(s, 0) + 1
            if votes and left is not None and right is not None:
                s = max(votes, key=lambda v: (votes[v], v))
                if s * _scale(m) >= FINE_PRINT_PT:
                    found.append(Run(s * _scale(m), m[0] * left + m[4], m[0] * right + m[4], m[5]))
        for child in e:
            walk(child, m, size)

    walk(root, _IDENTITY, 16.0, top=True)  # an SVG's text without a size: 16 px, as browsers draw it
    return found


def _scripts(found: list[Run]) -> list[Run]:
    """The runs set as a script of another: much smaller, beside it (just after it, or above
    or under it) and off its baseline, as an exponent, an index or a formula's limits are."""
    scripts = []
    for s in found:
        if s.script:
            scripts.append(s)
            continue
        for b in found:
            if b.size < 1.25 * s.size:
                continue
            gap = max(s.left - b.right, b.left - s.right)
            if gap <= 0.6 * b.size and 0.1 * b.size <= abs(s.base - b.base) <= 1.2 * b.size:
                scripts.append(s)
                break
    return scripts


_VIEWBOX = re.compile(r'viewBox="\s*[-\d.e]+[\s,]+[-\d.e]+[\s,]+([\d.e]+)[\s,]+([\d.e]+)')


def size(svg: str) -> tuple[float, float]:
    """The figure's size, its viewBox's (a card shows it a px per unit); 0, 0 without one."""
    opening = re.search(r"<svg[^>]*>", svg)
    box = _VIEWBOX.search(opening[0]) if opening else None
    return (float(box[1]), float(box[2])) if box else (0.0, 0.0)


def card_scale(svg: str) -> float:
    """How much smaller the figure is shown on a card than its size (1: as large)."""
    w, h = size(svg)
    return min(1.0, CARD_PX[0] / w if w else 1.0, CARD_PX[1] / h if h else 1.0)


def smallest_px(svg: str) -> float | None:
    """The height in px of the figure's smallest text, scripts aside, once fitted to a card;
    None: no text to read."""
    found = runs(svg)
    scripts = _scripts(found)
    sizes = [r.size for r in found if not any(r is s for s in scripts)]
    if not sizes:
        return None
    return min(sizes) * card_scale(svg)


def svg_too_small(svg: str, least: float) -> str:
    """What the AI is told of its SVG whose text can't be read on a card ("" when it can): its
    size, its smallest text's, and the font-size that would be read at this size."""
    px = smallest_px(svg)
    if px is None or px >= least:
        return ""
    w, h = size(svg)
    k = card_scale(svg)
    return (
        f"Your drawing is too small to read on a card: its viewBox is {w:.0f} wide and {h:.0f} high; fitted to a "
        f"phone ({CARD_PX[0]} px wide, {CARD_PX[1]} high), its smallest text is {px:.1f} px high, {least:g} at "
        f"least. Draw it again in a smaller viewBox (about {CARD_PX[0] * 5 // 4} wide at most) with the same "
        f"font-sizes, or with every font-size at least {math.ceil(least / k)} in this viewBox; never a label "
        "left out."
    )
