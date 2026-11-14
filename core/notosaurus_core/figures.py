"""Figures on cards: geometry, labelled and measured figures, drawn as SVG by the AI
that writes the cards (image models draw text and exact measures badly).

The cards say what to draw (Card.figure, a description); each figure is then drawn
by a short call of its own with the drawing rules below, checked by looking at it
(CHECK_RULES: drawn again with the model's thinking when it's wrong), cleaned (only shapes and
text: nothing that runs or loads anything) and saved next to the card pictures.
"""

import base64
import hashlib
import io
import math
import re
import urllib.parse
from pathlib import Path
from xml.etree import ElementTree

from pydantic import BaseModel, Field

from .errors import AppError
from .models import Card
from .prompts import FIGURE_CHECK_RULES, SVG_FIGURE_RULES

SVG_NS = "http://www.w3.org/2000/svg"
ElementTree.register_namespace("", SVG_NS)
MAX_SIZE = 200_000  # characters: a figure is a few kilobytes
VIEWBOX = "0 0 400 300"

RULES = SVG_FIGURE_RULES


# The figure seen as a picture, against its description: what a light drawing gets wrong
# is placing by eye what belongs to another element (a mark off its segment, an angle's
# arc on the other side of its line); looking at it tells, where its coordinates don't
CHECK_RULES = FIGURE_CHECK_RULES
PNG_WIDTH = 600  # pixels: what the check sees
FONT = Path(__file__).parent / "fonts" / "DejaVuSans.ttf"  # its licence beside it


class Label(BaseModel):
    text: str = Field(description="The name, as written in the description.")
    x: float = Field(description="The point it names, in the SVG's viewBox units: on or inside that part.")
    y: float


class Drawing(BaseModel):
    svg: str = Field(description="The SVG document, starting with <svg.")
    labels: list[Label] = Field(
        default_factory=list,
        description="A labelled scheme's names (a cell's, an organ's parts…), each with the point it names; "
        "set beside the drawing by the app. Empty for any other figure.",
    )


class Checked(BaseModel):
    problem: str = Field(description="The problem, in one short sentence; empty when none.")
    ok: bool


class FigureError(AppError):
    status = 502


# --- Cleaning: an allow-list of shapes, text and their presentation ----------------

ELEMENTS = {
    "svg", "g", "defs", "marker", "title", "desc",
    "path", "line", "polyline", "polygon", "rect", "circle", "ellipse", "text", "tspan",
    # Shaded and shared areas (a hatched intersection): they refer to the figure's own parts only
    "pattern", "clipPath", "mask", "linearGradient", "radialGradient", "stop",
    # A shape drawn again where it is used (Typst's letters): the figure's own, by its id only
    "symbol", "use",
    # A text along one of the figure's own curves (an arc's label), by its id only
    "textPath",
}  # fmt: skip
GEOMETRY = {
    "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "width", "height", "d", "points",
    "dx", "dy", "rotate", "transform", "viewBox", "preserveAspectRatio", "id",
    "refX", "refY", "markerWidth", "markerHeight", "orient", "markerUnits", "textLength", "lengthAdjust",
    "patternUnits", "patternContentUnits", "patternTransform", "clipPathUnits", "maskUnits", "maskContentUnits",
    "gradientUnits", "gradientTransform", "spreadMethod", "offset", "fx", "fy", "startOffset",
}  # fmt: skip
PRESENTATION = {
    "fill", "stroke", "stroke-width", "stroke-dasharray", "stroke-dashoffset", "stroke-linecap",
    "stroke-linejoin", "stroke-miterlimit", "fill-opacity", "stroke-opacity", "opacity", "fill-rule",
    "font-family", "font-size", "font-weight", "font-style", "text-anchor", "dominant-baseline",
    "alignment-baseline", "baseline-shift", "letter-spacing", "word-spacing", "text-decoration",
    "marker-start", "marker-mid", "marker-end", "visibility", "display", "overflow",
    "clip-path", "clip-rule", "mask", "stop-color", "stop-opacity",
    # A label's halo painted under its letters, not over them; the colour currentColor takes
    "paint-order", "color",
}  # fmt: skip
# Attributes that may point at a part of the figure itself ("url(#hatch)"), never elsewhere
REFERENCES = {"marker-start", "marker-mid", "marker-end", "clip-path", "mask", "fill", "stroke"}
INTERNAL_REF = re.compile(r"^url\(\s*#[\w.-]+\s*\)$")
INTERNAL_HREF = re.compile(r"^#[\w.-]+$")  # a <use> of the figure's own shape, never a file or a page
SAFE_VALUE = re.compile(r"^[^<>()\\]*$")  # nothing that could call or load (url(…), expression(…))
# Transforms: geometric functions of numbers only ("rotate(-30 120 80) translate(5,0)")
TRANSFORM = re.compile(r"^(\s*(matrix|translate|scale|rotate|skewX|skewY)\(\s*[-+\d.eE\s,]*\)\s*,?)+\s*$")


def _local(name: str) -> str:
    return name.rsplit("}", 1)[-1]


def _safe_value(name: str, value: str) -> bool:
    if name in REFERENCES and INTERNAL_REF.match(value.strip()):
        return True
    if name.startswith("marker-") or name in ("clip-path", "mask"):
        return value.strip() == "none"
    if name in ("transform", "patternTransform", "gradientTransform"):
        return bool(TRANSFORM.match(value))
    return bool(SAFE_VALUE.match(value)) and "javascript" not in value.lower()


_FONT_SIZE = re.compile(r"^[\d.]+(px|pt|em|rem|%)?(/\S+)?$|^(xx?-)?(small|large)$|^medium$")


def _font(value: str) -> list[tuple[str, str]]:
    """CSS's font shorthand ("italic bold 12px sans-serif") as the properties it sets."""
    words = value.split()
    # the size, the first word read as one; a weight's bare number ("500 12pt") before it isn't
    sizes = [i for i, w in enumerate(words) if _FONT_SIZE.match(w.lower())]
    at = next((i for i in sizes if not (re.fullmatch(r"[1-9]00", words[i]) and i + 1 in sizes)), None)
    if at is None:
        return []
    parts = [("font-size", words[at].split("/")[0])]
    for word in (w.lower() for w in words[:at]):
        if word in ("italic", "oblique"):
            parts.append(("font-style", word))
        elif word in ("bold", "bolder", "lighter") or re.fullmatch(r"[1-9]00", word):
            parts.append(("font-weight", word))
    if words[at + 1 :]:
        parts.append(("font-family", " ".join(words[at + 1 :])))
    return parts


def _in_px(size: str) -> str:
    """A font size in points ("12pt", as blockst writes its labels) in pixels, the same size:
    resvg, which draws the figure for its check, draws no letter at a size in points."""
    points = re.fullmatch(r"\s*([\d.]+)pt\s*", size)
    return f"{float(points[1]) * 4 / 3:g}px" if points else size


def _clean_style(style: str) -> str:
    kept = []
    for declaration in style.split(";"):
        name, _, value = declaration.partition(":")
        name, value = name.strip().lower(), value.strip().removesuffix("!important").strip()
        for part, part_value in _font(value) if name == "font" else [(name, value)]:
            if part in PRESENTATION and part_value and _safe_value(part, part_value):
                kept.append(f"{part}:{_in_px(part_value) if part == 'font-size' else part_value}")
    return ";".join(kept)


# A stylesheet's simple selectors: an element, its classes, or an id ("text.label", ".a", "#t")
_SELECTOR = re.compile(r"^([A-Za-z][\w-]*)?((?:\.[\w-]+)*)$|^#([\w-]+)$")


def _without_at_rules(css: str) -> str:
    """A stylesheet without its comments and at-rules (@import, @font-face, @media…: what
    loads, or what applies only sometimes)."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    out, i = [], 0
    while i < len(css):
        if css[i] != "@":
            out.append(css[i])
            i += 1
            continue
        end = re.search(r"[;{]", css[i:])
        if end is None:
            break
        i += end.end()
        if end.group() == "{":  # its block, nested ones too
            depth = 1
            while i < len(css) and depth:
                depth += {"{": 1, "}": -1}.get(css[i], 0)
                i += 1
    return "".join(out)


def _inline_stylesheets(root: ElementTree.Element) -> None:
    """The figure's <style> rules written on the elements they style, before clean drops
    <style> and class (a stylesheet may load or style what isn't the figure). Only simple
    selectors; their declarations then cleaned as any style is (_clean_style): a shape
    styled by class keeps its colours, never painted black."""
    css = "".join(e.text or "" for e in root.iter() if isinstance(e.tag, str) and _local(e.tag) == "style")
    if not css.strip():
        return
    rules = []  # (specificity, order, element, classes, id, declarations)
    for order, (selectors, declarations) in enumerate(re.findall(r"([^{}]+)\{([^{}]*)\}", _without_at_rules(css))):
        for selector in selectors.split(","):
            matched = _SELECTOR.match(selector.strip())
            if matched is None or not selector.strip():
                continue  # a selector it doesn't read: its rule left out
            tag, classes, ident = (
                matched.group(1),
                [c for c in (matched.group(2) or "").split(".") if c],
                matched.group(3),
            )
            specificity = (1 if ident else 0, len(classes), 1 if tag else 0)
            rules.append((specificity, order, tag, set(classes), ident, declarations))
    rules.sort(key=lambda r: (r[0], r[1]))
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        local, own = _local(element.tag), set(element.get("class", "").split())
        applied = [
            d for _, _, tag, classes, ident, d in rules
            if (ident is None or element.get("id") == ident) and (tag is None or tag == local) and classes <= own
        ]  # fmt: skip
        if applied:
            element.set("style", ";".join([*applied, element.get("style", "")]))  # its own style last: it wins


_SVG_DATA = re.compile(r"^data:image/svg\+xml(;charset=[\w-]+)?(;base64)?,(.*)$", re.DOTALL)


def _inline_svg_images(element: ElementTree.Element, depth: int = 0) -> None:
    """An SVG image held as data (a Typst package drawing its own SVG: blockst's Scratch
    blocks) drawn in its place, its shapes and text cleaned as the figure's own: an <img>
    shows no image within an image's SVG, and the cleaning would drop it."""
    for at, child in enumerate(list(element)):
        if not isinstance(child.tag, str):
            continue
        if _local(child.tag) != "image":
            _inline_svg_images(child, depth)
            continue
        href = next((v for k, v in child.attrib.items() if _local(k) == "href"), "")
        data = _SVG_DATA.match(href.strip())
        if data is None or depth > 2:
            continue  # a picture, a file, a page: dropped by the cleaning
        try:
            text = base64.b64decode(data[3]).decode("utf-8") if data[2] else urllib.parse.unquote(data[3])
            if re.search(r"<!(DOCTYPE|ENTITY)", text, re.IGNORECASE):
                continue
            inner = ElementTree.fromstring(text)
        except (ValueError, ElementTree.ParseError):
            continue
        if _local(inner.tag) != "svg":
            continue
        for part in inner.iter():
            if isinstance(part.tag, str) and not part.tag.startswith("{"):
                part.tag = f"{{{SVG_NS}}}{part.tag}"
        _inline_svg_images(inner, depth + 1)
        group = ElementTree.Element(f"{{{SVG_NS}}}g")
        if child.get("transform"):
            group.set("transform", child.get("transform", ""))
        for name in ("x", "y", "width", "height", "preserveAspectRatio"):
            if child.get(name) is not None:
                inner.set(name, child.get(name, ""))
        inner.attrib.pop("version", None)
        inner.set("overflow", "visible")  # what it draws past its frame (blockst's last arm) shown, fitted
        group.append(inner)
        group.tail = child.tail
        element.remove(child)
        element.insert(at, group)


def _unwrap_links(element: ElementTree.Element) -> None:
    """A link's content kept in its place, the link dropped (a label in an <a>: still shown)."""
    for child in list(element):
        if isinstance(child.tag, str) and _local(child.tag) == "a":
            at = list(element).index(child)
            text, tail = child.text or "", child.tail or ""
            if at == 0:
                element.text = (element.text or "") + text
            else:
                previous = element[at - 1]
                previous.tail = (previous.tail or "") + text
            inner = list(child)
            element.remove(child)
            for k, grandchild in enumerate(inner):
                element.insert(at + k, grandchild)
            if inner:
                inner[-1].tail = (inner[-1].tail or "") + tail
            elif at == 0:
                element.text = (element.text or "") + tail
            else:
                previous = element[at - 1]
                previous.tail = (previous.tail or "") + tail
            _unwrap_links(element)
            return
        _unwrap_links(child)


def _clean(element: ElementTree.Element) -> None:
    for child in list(element):
        if not isinstance(child.tag, str) or _local(child.tag) not in ELEMENTS:
            element.remove(child)  # script, foreignObject, image, a, use, animate…, comments
        else:
            _clean(child)
    for name in list(element.attrib):
        local, value = _local(name), element.attrib[name]
        if local == "style" or local in PRESENTATION:
            value = element.attrib[name] = plain_colours(value)  # its colours #rrggbb, kept
        if local == "font-size":
            value = element.attrib[name] = _in_px(value)
        if local == "style":
            cleaned = _clean_style(value)
            if cleaned:
                element.attrib[name] = cleaned
            else:
                del element.attrib[name]
        elif local == "href" and _local(element.tag) in ("use", "textPath") and INTERNAL_HREF.match(value.strip()):
            continue  # one of the figure's own shapes or curves ("#g1"): nothing loaded
        elif local not in GEOMETRY | PRESENTATION or not _safe_value(local, value):
            del element.attrib[name]  # on…, href, xlink:href, anything unknown or unsafe


# Colours written as functions: CSS's (rgb(…), hsl(…), as the AI writes an SVG) and its newer
# ones (oklab(…), oklch(…), color(srgb-linear …): Typst's mixed colours). A value with
# brackets isn't kept (SAFE_VALUE), the shape then painted black: written #rrggbb(aa) first
_COLOUR = re.compile(r"\b(rgba?|hsla?|oklab|oklch|color)\(([^()]*)\)", re.IGNORECASE)


def _srgb(linear: float) -> int:
    """A linear-light channel as an sRGB byte."""
    x = max(0.0, min(1.0, linear))
    return round(255 * (12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055))


def _hex(name: str, arguments: str) -> str | None:
    """That colour as #rrggbb (#rrggbbaa below full opacity); None, one it doesn't read."""
    name = name.lower()
    main, _, alpha = arguments.partition("/")
    parts = [p for p in re.split(r"[\s,]+", main.strip()) if p]
    if name == "color":
        if not parts or parts[0].lower() != "srgb-linear":
            return None
        parts = parts[1:]
    if len(parts) == 4 and not alpha.strip():
        alpha = parts.pop()

    def number(text: str, percent: float = 1.0) -> float:
        """A value, a percentage of `percent`; an angle in degrees."""
        text = text.strip().lower().removesuffix("deg")
        return float(text[:-1]) * percent / 100 if text.endswith("%") else float(text)

    try:
        if len(parts) != 3:
            return None
        opacity = number(alpha, 1) if alpha.strip() else 1.0
        if name in ("rgb", "rgba"):
            channels = [round(number(p, 255)) for p in parts]
        elif name in ("hsl", "hsla"):
            hue = number(parts[0]) % 360
            saturation, light = (float(p.strip().rstrip("%")) / 100 for p in parts[1:])
            chroma = (1 - abs(2 * light - 1)) * saturation
            x = chroma * (1 - abs((hue / 60) % 2 - 1))
            sextant = [(chroma, x, 0), (x, chroma, 0), (0, chroma, x), (0, x, chroma), (x, 0, chroma), (chroma, 0, x)]
            channels = [round(255 * (v + light - chroma / 2)) for v in sextant[int(hue // 60) % 6]]
        elif name in ("oklab", "oklch"):
            lightness = number(parts[0], 1)
            a, b = number(parts[1], 0.4), number(parts[2], 0.4) if name == "oklab" else number(parts[2])
            if name == "oklch":
                a, b = a * math.cos(math.radians(b)), a * math.sin(math.radians(b))
            lms = [
                (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3,
                (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3,
                (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3,
            ]
            rows = (
                (4.0767416621, -3.3077115913, 0.2309699292),
                (-1.2684380046, 2.6097574011, -0.3413193965),
                (-0.0041960863, -0.7034186147, 1.7076147010),
            )
            channels = [_srgb(sum(k * c for k, c in zip(row, lms, strict=True))) for row in rows]
        else:  # color(srgb-linear …)
            channels = [_srgb(number(p, 1)) for p in parts]
    except ValueError:
        return None
    tail = f"{round(255 * max(0.0, opacity)):02x}" if opacity < 1 else ""
    return "#" + "".join(f"{max(0, min(255, c)):02x}" for c in channels) + tail


def plain_colours(value: str) -> str:
    """An attribute's or a style's colours written as functions, written #rrggbb(aa): the
    same colours, kept by clean (no brackets) and shown by every renderer (AnkiDroid's
    WebView, resvg); the figure's text left as it is."""
    return _COLOUR.sub(lambda m: _hex(m.group(1), m.group(2)) or m.group(0), value)


def clean(svg: str) -> str:
    """The SVG with only shapes, text and their presentation: nothing that runs (scripts,
    event handlers), loads (links, images, external references) or expands (no DTD).
    Sized from its viewBox, so an <img> shows it at its size and scales it down."""
    svg = svg.strip()
    if len(svg) > MAX_SIZE:
        raise FigureError("figure.invalid")
    if re.search(r"<!(DOCTYPE|ENTITY)", svg, re.IGNORECASE):
        raise FigureError("figure.invalid")  # no DTD: no entities to expand or fetch
    try:
        root = ElementTree.fromstring(svg)
    except ElementTree.ParseError as e:
        raise FigureError("figure.invalid") from e
    if _local(root.tag) != "svg":
        raise FigureError("figure.invalid")
    if root.tag != f"{{{SVG_NS}}}svg":  # written without its namespace: give it one
        for element in root.iter():
            if isinstance(element.tag, str) and not element.tag.startswith("{"):
                element.tag = f"{{{SVG_NS}}}{element.tag}"
    _inline_svg_images(root)
    _inline_stylesheets(root)
    _unwrap_links(root)
    _clean(root)
    viewbox = root.get("viewBox") or VIEWBOX
    root.set("viewBox", viewbox)
    try:
        x, y, width, height = (float(v) for v in re.split(r"[\s,]+", viewbox.strip()))
    except ValueError as e:
        raise FigureError("figure.invalid") from e
    if not all(math.isfinite(v) for v in (x, y, width, height)) or width <= 0 or height <= 0:
        raise FigureError("figure.invalid")  # float() takes "nan", "inf", "1e309": no size to show
    root.set("width", f"{width:g}")
    root.set("height", f"{height:g}")
    return ElementTree.tostring(root, encoding="unicode")


OVERFLOW = 150  # in the figure's units (Typst's pt): how far past its frame its drawing is looked for
MARGIN = 6  # around what is drawn, as the Typst families' pages have it
_VIEWBOX = re.compile(r'viewBox="(-?[\d.]+) (-?[\d.]+) ([\d.]+) ([\d.]+)"')


def fitted(svg: str) -> str:
    """The figure's frame grown to what is drawn past it: drawn in the SVG, but cut off by its
    frame (an axis's name lilaq writes past the diagram's end: "temps (mi"; an organ's label
    the AI wrote past its viewBox: "Diaphragm"). Found by drawing the figure once in a frame
    wider by OVERFLOW; the same SVG when nothing passes its frame; as it is without resvg."""
    box = _VIEWBOX.search(svg)
    if box is None:
        return svg
    x, y, w, h = map(float, box.groups())
    wide = _framed(svg, box.group(0), x - OVERFLOW, y - OVERFLOW, w + 2 * OVERFLOW, h + 2 * OVERFLOW)
    try:
        png = to_png(clean(wide))  # resvg reads it cleaned, as the check does
    except FigureError:
        png = None
    if png is None:
        return svg
    from PIL import Image, ImageOps

    image = Image.open(io.BytesIO(png)).convert("L")
    drawn = ImageOps.invert(image).point([0] * 25 + [255] * 231).getbbox()  # what isn't white
    if drawn is None:
        return svg
    k = (w + 2 * OVERFLOW) / image.width  # the figure's units per pixel
    left, top = x - OVERFLOW + drawn[0] * k - MARGIN, y - OVERFLOW + drawn[1] * k - MARGIN
    right, bottom = x - OVERFLOW + drawn[2] * k + MARGIN, y - OVERFLOW + drawn[3] * k + MARGIN
    slack = 2 * k + 1  # a pixel or two of rounding, a stroke's edge
    if left >= x - slack and top >= y - slack and right <= x + w + slack and bottom <= y + h + slack:
        return svg  # within its frame: untouched
    nx, ny = min(x, left), min(y, top)
    nw, nh = max(x + w, right) - nx, max(y + h, bottom) - ny
    svg = _framed(svg, box.group(0), nx, ny, nw, nh)
    # its white ground under it all, its own (Typst's page, the AI's rect) covering its frame only
    opening = re.search(r"<svg[^>]*>", svg)
    if opening is None:
        return svg
    ground = f'<rect x="{nx:.3f}" y="{ny:.3f}" width="{nw:.3f}" height="{nh:.3f}" fill="#ffffff"/>'
    return svg[: opening.end()] + ground + svg[opening.end() :]


def _framed(svg: str, viewbox: str, x: float, y: float, w: float, h: float) -> str:
    """The SVG's frame (its viewBox, and its size with it: the same scale, in its unit) set to
    x, y, w, h."""
    svg = svg.replace(viewbox, f'viewBox="{x:.3f} {y:.3f} {w:.3f} {h:.3f}"', 1)
    svg = re.sub(r'(<svg[^>]*?\swidth=")[\d.]+((?:pt)?")', rf"\g<1>{w:.3f}\g<2>", svg, count=1)
    return re.sub(r'(<svg[^>]*?\sheight=")[\d.]+((?:pt)?")', rf"\g<1>{h:.3f}\g<2>", svg, count=1)


def to_png(svg: str) -> bytes | None:
    """The cleaned figure as a PNG on white, as the check sees it; None when it can't be
    made (resvg not installed, or it fails on this figure)."""
    try:
        import resvg_py
    except ImportError:
        return None
    # Every text in DejaVu Sans, shipped here: resvg's "sans-serif" is Arial, which a Linux
    # computer or the relay's container may not have, and it then draws no letter at all
    # (a figure without its labels: refused by the check every time)
    font = str(FONT)
    try:
        return bytes(
            resvg_py.svg_to_bytes(
                svg_string=svg,
                background="#ffffff",
                width=PNG_WIDTH,
                font_files=[font],
                font_family="DejaVu Sans",
                sans_serif_family="DejaVu Sans",
                serif_family="DejaVu Sans",
                monospace_family="DejaVu Sans",
            )
        )
    except Exception:  # resvg's own errors (a Rust panic told as an exception): no check
        return None


# A label's ink must stand this many pixels (at PNG_WIDTH) inside another's to say they touch:
# two lines of one label, or a word and its exponent, merely meeting at an edge, apart
TOUCHING = 2
# Two phrases on one line (side by side) closer than this, times their height: a gap hardly
# wider than a space between words, read as one phrase (« Fe²⁺ + soude Cl⁻ + nitrate… »)
APART = 0.8
_DEFS = {"defs", "symbol", "marker", "pattern", "clipPath", "mask"}


def _texts(element: ElementTree.Element, parent: ElementTree.Element | None = None):
    """The figure's texts drawn (not in its definitions), each with its parent."""
    if _local(element.tag) in _DEFS:
        return
    for child in list(element):
        if _local(child.tag) == "text":
            yield child, element
        else:
            yield from _texts(child, element)


def label_words(svg: str) -> list[str]:
    """The words of the figure's texts, as written (in its drawing, not its definitions)."""
    try:
        root = ElementTree.fromstring(svg)
    except ElementTree.ParseError:
        return []
    return [w for t, _ in _texts(root) for w in "".join(t.itertext()).split()]


def _label_boxes(svg: str) -> tuple[list[tuple[str, tuple[int, int, int, int]]], float, float, float]:
    """Each text's ink as a box in pixels (at PNG_WIDTH), found by drawing the figure with it
    alone among the texts (the rest of the drawing as it is); and the viewBox's left, top and
    units per pixel, to tell them in the figure's units. ([], 0, 0, 1) without resvg."""
    from PIL import Image, ImageChops

    nothing: tuple[list[tuple[str, tuple[int, int, int, int]]], float, float, float] = ([], 0.0, 0.0, 1.0)
    try:
        root = ElementTree.fromstring(svg)
    except ElementTree.ParseError:
        return nothing
    texts = list(_texts(root))
    if not texts:
        return nothing
    for text, parent in texts:
        parent.remove(text)
    bare = to_png(ElementTree.tostring(root, encoding="unicode"))
    if bare is None:
        return nothing
    base = Image.open(io.BytesIO(bare)).convert("L")
    boxes = []
    for text, parent in texts:
        parent.append(text)
        png = to_png(ElementTree.tostring(root, encoding="unicode"))
        parent.remove(text)
        if png is None:
            continue
        drawn = Image.open(io.BytesIO(png)).convert("L")
        ink = ImageChops.difference(drawn, base).point([0] * 41 + [255] * 215)  # more than 40 apart
        box = ink.getbbox()
        if box is not None:
            boxes.append(("".join(text.itertext()).strip(), box))
    view = _VIEWBOX.search(svg)
    x, y, w = (float(view.group(1)), float(view.group(2)), float(view.group(3))) if view else (0.0, 0.0, base.width)
    return boxes, x, y, w / base.width


def touching_labels(svg: str) -> list[tuple[str, str]]:
    """The figure's texts written on one another, as pairs of their words: the pairs whose
    inks' boxes (_label_boxes) overlap, or two phrases on one line closer than APART times
    their height. The AI writes SVG without measuring its words: two labels centred on tubes
    120 px apart, one 150 px wide (« soudeCl⁻ »). [] without resvg."""
    boxes = _label_boxes(svg)[0]
    touching = []
    for i, (a, (ax0, ay0, ax1, ay1)) in enumerate(boxes):
        for b, (bx0, by0, bx1, by1) in boxes[i + 1 :]:
            across = min(ax1, bx1) - max(ax0, bx0)  # < 0: the gap between them
            down = min(ay1, by1) - max(ay0, by0)
            # two phrases on one line (sharing most of the smaller one's height), too close to read
            # apart (numbers along a scale, a word's letters coloured one by one: never phrases)
            height = min(ay1 - ay0, by1 - by0)
            phrases = " " in a or " " in b
            side_by_side = phrases and down > 0.5 * height and across > -APART * height
            if (across > TOUCHING and down > TOUCHING) or side_by_side:
                touching.append((a, b))
    return touching


def label_extents(svg: str) -> dict[str, tuple[float, float]]:
    """Each text's ink from left to right, in the figure's own units (its viewBox's): what the
    AI can't measure, told to it when its labels touch."""
    boxes, x, _, k = _label_boxes(svg)
    return {text: (round(x + x0 * k), round(x + x1 * k)) for text, (x0, _, x1, _) in boxes}


def save(folder: Path, card: Card, svg: str) -> str:
    """The cleaned figure in the lesson's images/ folder; returns its file name (a card
    picture: shown, exported and pruned like the others)."""
    data = clean(svg).encode()
    folder.mkdir(parents=True, exist_ok=True)
    name = f"picture-{card.id}-{hashlib.sha1(data).hexdigest()[:8]}.svg"
    (folder / name).write_bytes(data)
    return name


# --- Labels set beside the drawing ---------------------------------------------------------
# A labelled scheme (a cell, an organ, a flower) drawn by the AI: its names written by eye fell
# on its outlines ("Noyau" across the cell's membrane, 2 drawings in 3). The AI draws the
# shapes and tells each name's point; they are set here in two columns beside the drawing,
# each in the order of its points from top to bottom, a line from each to its point, never
# on a shape nor on one another.

LABEL_SIZE = 16  # in the viewBox's units: the rule's largest, the drawing grown by its columns
LABEL_LINE = 1.3  # a line's height, times the size
LABEL_WIDTH = 130  # past this, a name goes on two lines (or more)
LABEL_GAP = 14  # between the drawing and a column, a column and the frame
LABEL_ROOM = 4  # between two names in a column
POINT_SLACK = 2  # a point this far past the frame (a stroke's edge) is still inside
SNAP = 12  # a point on the white ground this near the drawing (beside a funnel's edge): brought onto it
OPEN_SNAP = 0.15  # times the drawing's size: a point on the open ground this near a line (the AI's point
# off a rotated arm, 14 to 47 units of 400 away) brought onto it; farther, a region (the air around
# a funnel, 165 away) kept


class LabelError(ValueError):
    """A label the drawing can't take (its point outside it): said to the AI, which draws it again."""


def _measure(text: str) -> float:
    """The text's width in the viewBox's units, at LABEL_SIZE, in the font the figures are drawn in."""
    from PIL import ImageFont

    font = ImageFont.truetype(str(FONT), 100)
    return font.getlength(text) * LABEL_SIZE / 100


def _lines(text: str) -> list[str]:
    """The name cut into lines no wider than LABEL_WIDTH, at its spaces (a long word alone)."""
    lines: list[str] = []
    for word in text.split():
        if lines and _measure(lines[-1] + " " + word) <= LABEL_WIDTH:
            lines[-1] += " " + word
        else:
            lines.append(word)
    return lines or [text]


def _drawn_image(svg: str):
    """The figure drawn in grey levels (to_png), None without resvg."""
    png = to_png(svg)
    if png is None:
        return None
    from PIL import Image

    return Image.open(io.BytesIO(png)).convert("L")


def _ink(image, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
    """What the drawing covers (not its white ground), in its units; its frame without an image."""
    if image is None:
        return x, y, x + w, y + h
    from PIL import ImageOps

    box = ImageOps.invert(image).point([0] * 25 + [255] * 231).getbbox()
    if box is None:
        return x, y, x + w, y + h
    k = w / image.width
    return x + box[0] * k, y + box[1] * k, x + box[2] * k, y + box[3] * k


def _outside(image):
    """The white ground around the drawing, reached from its edge without crossing a line: a
    function telling whether a pixel is on it (a white part closed by lines, a region, is not)."""
    from PIL import ImageDraw, ImageOps

    ground = ImageOps.expand(image.point(lambda v: 255 if v >= 248 else 0), border=1, fill=255)
    ImageDraw.floodfill(ground, (0, 0), 128, thresh=0)
    return lambda i, j: ground.getpixel((i + 1, j + 1)) == 128


def _snapped(image, x: float, y: float, w: float, px: float, py: float, outside=None) -> tuple[float, float]:
    """The point, or the drawing's nearest pixel when it lies on the white ground: SNAP or less
    from it (the AI's point beside the part it names), or OPEN_SNAP of the drawing's size on the
    open ground, nothing closing it in (« chaîne légère » off the antibody's rotated arm), unless
    lines lie on both sides of it (a gap between two shapes: the synaptic cleft); a point
    farther from any line (a region drawn white: the air, the cytoplasm) kept."""
    if image is None:
        return px, py
    k = image.width / w
    cx, cy = round((px - x) * k), round((py - y) * k)
    pixels = image.load()

    def ink(i: int, j: int) -> bool:
        return 0 <= i < image.width and 0 <= j < image.height and pixels[i, j] < 248  # a light fill too

    if ink(cx, cy):
        return px, py
    inside = 0 <= cx < image.width and 0 <= cy < image.height
    far = outside is not None and inside and outside(cx, cy)
    r = math.ceil((OPEN_SNAP * max(w, image.height / k) if far else SNAP) * k)
    if far:
        # a gap between two shapes (the synaptic cleft, open at its ends): lines on both sides
        # of it, up and down or left and right, a region kept, not a part's point gone astray

        def hits(di: int, dj: int) -> bool:
            return any(ink(cx + di * t, cy + dj * t) for t in range(1, r + 1))

        if (hits(0, -1) and hits(0, 1)) or (hits(-1, 0) and hits(1, 0)):
            r = math.ceil(SNAP * k)

    def ring(d: int) -> list[tuple[int, int, int]]:
        """The ink pixels d away from the point (on the square around it), with their distance²."""
        around = [(i, cy - d) for i in range(cx - d, cx + d + 1)] + [(i, cy + d) for i in range(cx - d, cx + d + 1)]
        around += [(cx - d, j) for j in range(cy - d + 1, cy + d)] + [(cx + d, j) for j in range(cy - d + 1, cy + d)]
        return [((i - cx) ** 2 + (j - cy) ** 2, i, j) for i, j in around if ink(i, j)]

    best = None
    for d in range(1, r + 1):
        found = ring(d)
        if found:
            # a nearer pixel may lie on a farther square's side: looked for as far as this one's distance
            reach = min(r, math.ceil(math.sqrt(min(found)[0])))
            best = min(found + [p for e in range(d + 1, reach + 1) for p in ring(e)])
            break
    if best is None or best[0] > r * r:
        return px, py
    return x + best[1] / k, y + best[2] / k


def _cross(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float], d: tuple[float, float]) -> bool:
    """Whether the segments ab and cd cross (touching at an end not counted)."""

    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    d1, d2, d3, d4 = side(c, d, a), side(c, d, b), side(a, b, c), side(a, b, d)
    return d1 * d2 < 0 and d3 * d4 < 0


def _column(names: list[dict], top: float, bottom: float) -> None:
    """Each name's top in its column, in the column's order: as near its point's height as it
    can, none on another (pushed down, then the column up as far as the drawing's top when it
    passes its bottom)."""
    y = -math.inf
    for n in names:
        n["top"] = max(n["py"] - n["h"] / 2, y)
        y = n["top"] + n["h"] + LABEL_ROOM
    if names:
        over = min(y - LABEL_ROOM - bottom, names[0]["top"] - top)
        if over > 0:
            for n in names:
                n["top"] -= over


def _leader_start(n: dict, left: float, right: float) -> tuple[float, float]:
    x = left - LABEL_GAP + 3 if n["side"] == "left" else right + LABEL_GAP - 3
    return x, n["top"] + n["h"] / 2


def labelled(svg: str, labels: list[Label], clamp: bool = False) -> str:
    """The cleaned SVG with its labels set beside its drawing (see above). The same SVG
    without labels; LabelError for a point outside the drawing's frame (brought to its edge
    with `clamp`: the AI asked again and still giving it)."""
    if not labels:
        return svg
    view = _VIEWBOX.search(svg)
    if view is None:
        return svg
    x, y, w, h = map(float, view.groups())
    if clamp:
        labels = [
            Label(text=label.text, x=min(max(label.x, x), x + w), y=min(max(label.y, y), y + h)) for label in labels
        ]
    for label in labels:
        inside_x = x - POINT_SLACK <= label.x <= x + w + POINT_SLACK
        if not (inside_x and y - POINT_SLACK <= label.y <= y + h + POINT_SLACK):
            raise LabelError(
                f"the label « {label.text} » names the point ({label.x:g}, {label.y:g}), outside the drawing "
                f"(its viewBox: {x:g} {y:g} {w:g} {h:g}): give the point on the part it names"
            )
    image = _drawn_image(svg)
    left, top, right, bottom = _ink(image, x, y, w, h)
    middle = (left + right) / 2
    line = LABEL_SIZE * LABEL_LINE
    # a name given at several points (a gene's place on both chromosomes): one name, a line to each
    outside = _outside(image) if image is not None else None
    points: dict[str, list[tuple[float, float]]] = {}
    for label in labels:
        points.setdefault(label.text.strip(), []).append(_snapped(image, x, y, w, label.x, label.y, outside))
    names = []
    for text, at in points.items():
        rows = _lines(text)
        names.append(
            {
                "rows": rows,
                "w": max(_measure(r) for r in rows),
                "h": line * len(rows),
                "points": at,
                "px": sum(p[0] for p in at) / len(at),
                "py": sum(p[1] for p in at) / len(at),
                "side": "left" if sum(p[0] for p in at) / len(at) < middle else "right",
            }
        )
    sides = {s: sorted((n for n in names if n["side"] == s), key=lambda n: n["py"]) for s in ("left", "right")}
    # a column beyond every point of its side (a region's point past the drawing's ink: its line
    # never drawn back across its name)
    left = min([left] + [p[0] - 3 for n in sides["left"] for p in n["points"]])
    right = max([right] + [p[0] + 3 for n in sides["right"] for p in n["points"]])
    for column in sides.values():
        _column(column, top, bottom)
        # two leaders that cross (a far point just above a near one): their names' places swapped
        for _ in range(len(column) ** 2):
            crossing = next(
                (
                    (i, j)
                    for i in range(len(column))
                    for j in range(i + 1, len(column))
                    if any(
                        _cross(_leader_start(column[i], left, right), a, _leader_start(column[j], left, right), b)
                        for a in column[i]["points"]
                        for b in column[j]["points"]
                    )
                ),
                None,
            )
            if crossing is None:
                break
            i, j = crossing
            column[i], column[j] = column[j], column[i]
            _column(column, top, bottom)
    parts = []
    for n in names:
        edge, anchor = (left - LABEL_GAP, "end") if n["side"] == "left" else (right + LABEL_GAP, "start")
        start, middle_y = _leader_start(n, left, right)
        for px, py in n["points"]:
            parts.append(
                f'<line x1="{start:.1f}" y1="{middle_y:.1f}" x2="{px:.1f}" y2="{py:.1f}" '
                'stroke="#333333" stroke-width="1"/>'
                f'<circle cx="{px:.1f}" cy="{py:.1f}" r="2" fill="#333333"/>'
            )
        for k, row in enumerate(n["rows"]):
            base = n["top"] + line * k + LABEL_SIZE
            text = row.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            parts.append(
                f'<text x="{edge:.1f}" y="{base:.1f}" font-family="sans-serif" font-size="{LABEL_SIZE}" '
                f'text-anchor="{anchor}" fill="#000000">{text}</text>'
            )
    widest = {s: max((n["w"] for n in sides[s]), default=0.0) for s in sides}
    tops = [n["top"] for n in names] + [y]
    bottoms = [n["top"] + n["h"] for n in names] + [y + h]
    nx = min(x, left - LABEL_GAP - widest["left"] - LABEL_GAP) if sides["left"] else x
    nr = max(x + w, right + LABEL_GAP + widest["right"] + LABEL_GAP) if sides["right"] else x + w
    ny, nb = min(tops) - MARGIN, max(bottoms) + MARGIN
    ny, nb = min(ny, y), max(nb, y + h)
    svg = _framed(svg, view.group(0), nx, ny, nr - nx, nb - ny)
    opening = re.search(r"<svg[^>]*>", svg)
    closing = svg.rfind("</svg>")
    if opening is None or closing < 0:
        return svg
    ground = f'<rect x="{nx:.3f}" y="{ny:.3f}" width="{nr - nx:.3f}" height="{nb - ny:.3f}" fill="#ffffff"/>'
    return svg[: opening.end()] + ground + svg[opening.end() : closing] + "".join(parts) + svg[closing:]
