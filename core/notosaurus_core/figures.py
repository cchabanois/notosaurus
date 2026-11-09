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


class Drawing(BaseModel):
    svg: str = Field(description="The SVG document, starting with <svg.")


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


def save(folder: Path, card: Card, svg: str) -> str:
    """The cleaned figure in the lesson's images/ folder; returns its file name (a card
    picture: shown, exported and pruned like the others)."""
    data = clean(svg).encode()
    folder.mkdir(parents=True, exist_ok=True)
    name = f"picture-{card.id}-{hashlib.sha1(data).hexdigest()[:8]}.svg"
    (folder / name).write_bytes(data)
    return name
