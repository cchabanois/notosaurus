"""The AI's drawing in SVG (figure_svg.py) made readable on a card: its arrows drawn by the app,
their words set beside them, and its labelled scheme's names set beside the drawing, a line from
each to its point, never on a shape nor on one another (each section below says why).
"""

import io
import math
import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from . import figures


class Label(BaseModel):
    text: str = Field(description="The name, as written in the description.")
    x: float = Field(description="The point it names, in the SVG's viewBox units: on or inside that part.")
    y: float


class Arrow(BaseModel):
    text: str = Field(description="The word it carries, as written in the description.")
    x1: float = Field(description="Where it starts, in the SVG's viewBox units.")
    y1: float
    x2: float = Field(description="Its tip, in the SVG's viewBox units.")
    y2: float
    color: str = Field(default="", description="Its colour when the description gives one (#rrggbb), else empty.")


class Drawing(BaseModel):
    svg: str = Field(description="The SVG document, starting with <svg.")
    labels: list[Label] = Field(
        default_factory=list,
        description="A labelled scheme's names (a cell's, an organ's parts…), each with the point it names; "
        "set beside the drawing by the app. Empty for any other figure.",
    )
    arrows: list[Arrow] = Field(
        default_factory=list,
        description="The arrows that carry a word (what enters or leaves, a step, a transformation), each from "
        "where it starts to its tip; drawn by the app, its word set beside it. Empty when there are none.",
    )


# --- Labels set beside the drawing ---------------------------------------------------------
# A labelled scheme (a cell, an organ, a flower) drawn by the AI: its names written by eye fell
# on its outlines ("Noyau" across the cell's membrane, 2 drawings in 3). The AI draws the
# shapes and tells each name's point; they are set here beside the drawing, a line from each to
# its point, never on a shape nor on one another. Columns beside it gave long lines across the
# drawing when its parts stood side by side (steps in a row, 2 drawings in 3) or a name's parts
# on both sides (a flower's petals): the layouts are tried (two columns, a name of both sides in
# both; one column; a row under it, a row over it) and the one whose lines cross the fewest of
# its lines kept, a line crossed weighing CROSSING of the frame's width in lines' length.
# The arrows and their words, set first (arrows_set), are no part of the drawing: a line ran
# through « Lumière », along the light's arrow, a point was brought onto « transcription »'s
# letters. A line through a word or along an arrow weighs ARROW_CROSSING lines; each name is moved
# (ROUTE_REACH at most) for its line to keep WORD_CLEAR from the words and off the arrows; a
# point is never brought onto a word, and no word is set on a label's point.

LABEL_SIZE = 16  # in the viewBox's units: the rule's largest, the drawing grown by its columns
LABEL_LINE = 1.3  # a line's height, times the size
LABEL_WIDTH = 130  # past this, a name goes on two lines (or more)
LABEL_GAP = 14  # between the drawing and a column, a column and the frame
LABEL_ROOM = 4  # between two names in a column
CROSSING = 0.25  # times the frame's width: what a line crossed by a leader weighs, in leaders' length
ARROW_CROSSING = 3  # lines crossed: a leader through an arrow's word, or along its arrow
WORD_CLEAR = 6  # around an arrow's word: a leader nearer seems to touch it on a phone (kept clear where it can)
ALONG_NEAR = 10  # a leader this near an arrow…
ALONG_ANGLE = math.radians(30)  # …at a smaller angle to it…
ALONG_LENGTH = 16  # …past this length runs along it
ROUTE_REACH = 60  # how far a name is moved from its points' height (or abscissa) for its line to miss a word
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

    font = ImageFont.truetype(str(figures.FONT), 100)
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
    """The figure drawn in grey levels (figures.to_png), None without resvg."""
    png = figures.to_png(svg)
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


def _outside(image, k: float):
    """The open ground around the drawing: a function telling whether a pixel is on it. The
    frame's edge counts as a line, and a gap narrower than 2 × SNAP between lines (a nuclear
    pore, an outline's dashes) as closed: the white then falls into zones, and the open ground
    is a zone reaching all four sides of the frame, the drawing standing in it. A zone the
    drawing closes against the frame (the nucleus, left of an envelope drawn from the frame's
    top to its bottom: 2 drawings in 3) is a region, as one its lines close all round is; so is
    any zone when a line crosses the whole frame. `k`: the image's pixels per unit."""
    from PIL import ImageDraw, ImageFilter

    # at one pixel per STEP units (a line kept: a cell with any ink in it is ink), the ink grown
    # by SNAP, so that a gap of twice that closes
    step = max(1, round(k * SNAP / 6))
    ground = image.point(lambda v: 255 if v >= 248 else 0)
    small = ground.reduce(step) if step > 1 else ground
    small = small.point(lambda v: 255 if v == 255 else 0)
    grow = math.ceil(SNAP * k / step)
    zones = small.filter(ImageFilter.MinFilter(2 * grow + 1))
    width, height = zones.size
    pixels = zones.load()
    sides = {
        "top": [(i, 0) for i in range(width)],
        "bottom": [(i, height - 1) for i in range(width)],
        "left": [(0, j) for j in range(height)],
        "right": [(width - 1, j) for j in range(height)],
    }
    zone = 0
    for border in sides.values():
        for i, j in border:
            if pixels[i, j] == 255 and zone < 254:
                zone += 1
                ImageDraw.floodfill(zones, (i, j), zone, thresh=0)
    reached = [{pixels[i, j] for i, j in border} for border in sides.values()]
    open_zones = set.intersection(*reached) - {0, 255}
    return lambda i, j: pixels[min(i // step, width - 1), min(j // step, height - 1)] in open_zones


def _snapped(image, x: float, y: float, w: float, px: float, py: float, outside=None) -> tuple[float, float]:
    """The point, or the drawing's nearest pixel when it lies on the white ground: SNAP or less
    from it (the AI's point beside the part it names), or OPEN_SNAP of the drawing's size on the
    open ground (`outside`: « chaîne légère » off the antibody's rotated arm), unless
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
        n["top"] = max(n.get("ty", n["py"]) - n["h"] / 2, y)
        y = n["top"] + n["h"] + LABEL_ROOM
    if names:
        over = min(y - LABEL_ROOM - bottom, names[0]["top"] - top)
        if over > 0:
            for n in names:
                n["top"] -= over


def _leader_start(n: dict, left: float, right: float) -> tuple[float, float]:
    x = left - LABEL_GAP + 3 if n["side"] == "left" else right + LABEL_GAP - 3
    return x, n["top"] + n["h"] / 2


def _uncrossed(names: list[dict], place, start) -> None:
    """Names placed in their order (`place`), two whose leaders cross (a far point just above a
    near one) swapped and placed again, until none cross. `start`: a name's leader's start."""
    place(names)
    for _ in range(len(names) ** 2):
        crossing = next(
            (
                (i, j)
                for i in range(len(names))
                for j in range(i + 1, len(names))
                if any(
                    _cross(start(names[i]), a, start(names[j]), b)
                    for a in names[i]["points"]
                    for b in names[j]["points"]
                )
            ),
            None,
        )
        if crossing is None:
            break
        i, j = crossing
        names[i], names[j] = names[j], names[i]
        place(names)


def _routed(n: dict, marks: "Marks | None", start) -> float:
    """How far (nearest first, up to ROUTE_REACH) the name is moved for its lines to pass
    WORD_CLEAR or more from the arrows' words and along none of their arrows (`marks`); 0 when
    they do already or no move clears them all. `start`: its leader's start, moved by that much."""
    if marks is None or not marks.words:
        return 0
    words = _grown(marks)

    def clear(a: tuple[float, float]) -> bool:
        return not any(
            any(_through(a, p, b) for b in words) or any(_along(a, p, *line) > ALONG_LENGTH for line in marks.lines)
            for p in n["points"]
        )

    for d in range(ROUTE_REACH + 1):
        for move in (d, -d) if d else (0,):
            if clear(start(move)):
                return move
    return 0


def _in_columns(
    names: list[dict],
    sides: dict[str, str],
    left: float,
    right: float,
    top: float,
    bottom: float,
    marks: "Marks | None" = None,
):
    """The names set in columns beside the drawing, each on its side (`sides`, by its text), a
    column in the order of its points from top to bottom; in the names' order (_set). Each as
    near its points' height as its lines keep clear of the arrows and their words (_routed)."""
    names = [{**n, "side": sides[n["text"]]} for n in names]
    columns = {s: sorted((n for n in names if n["side"] == s), key=lambda n: n["py"]) for s in ("left", "right")}
    # a column beyond every point of its side (a region's point past the drawing's ink: its line
    # never drawn back across its name)
    left = min([left] + [p[0] - 3 for n in columns["left"] for p in n["points"]])
    right = max([right] + [p[0] + 3 for n in columns["right"] for p in n["points"]])
    for n in names:
        sx = _leader_start({**n, "top": 0, "h": 0}, left, right)[0]
        n["ty"] = n["py"] + _routed(n, marks, lambda move, n=n, sx=sx: (sx, n["py"] + move))
    for column in columns.values():
        _uncrossed(column, lambda c: _column(c, top, bottom), lambda n: _leader_start(n, left, right))
    placed = []
    for n in names:
        edge, anchor = (left - LABEL_GAP, "end") if n["side"] == "left" else (right + LABEL_GAP, "start")
        placed.append(_set(n, edge, anchor, edge - n["w"] if anchor == "end" else edge, _leader_start(n, left, right)))
    return placed


def _set(n: dict, x: float, anchor: str, x0: float, start: tuple[float, float]) -> dict:
    """A name set: its text's x and anchor, its box (from x0), its leader's start."""
    return {**n, "x": x, "anchor": anchor, "box": (x0, n["top"], x0 + n["w"], n["top"] + n["h"]), "start": start}


def _row(names: list[dict], low: float, high: float, edge: float, below: bool, marks: "Marks | None" = None):
    """The names in a row under the drawing (`below`) or above it, at `edge`, each as near
    over or under its points as it can (as near as its lines keep clear of the arrows and their
    words: _routed), in their order from left to right, none on another, the row kept between
    `low` and `high` as far as it fits."""
    sy = edge + LABEL_GAP - 3 if below else edge - LABEL_GAP + 3

    def place(row: list[dict]) -> None:
        x = low
        for n in row:
            n["x0"] = max(n["tx"] - n["w"] / 2, x)
            x = n["x0"] + n["w"] + LABEL_GAP
        if row:
            over = min(x - LABEL_GAP - high, row[0]["x0"] - low)
            if over > 0:
                for n in row:
                    n["x0"] -= over
        for n in row:
            n["top"] = edge + LABEL_GAP if below else edge - LABEL_GAP - n["h"]

    def start(n: dict) -> tuple[float, float]:
        return n["x0"] + n["w"] / 2, (n["top"] - 3 if below else n["top"] + n["h"] + 3)

    row = sorted(({**n} for n in names), key=lambda n: n["px"])
    for n in row:
        n["tx"] = n["px"] + _routed(n, marks, lambda move, n=n: (n["px"] + move, sy))
    _uncrossed(row, place, start)
    placed = {n["text"]: n for n in row}
    return [_set(r, r["x0"] + r["w"] / 2, "middle", r["x0"], start(r)) for r in (placed[n["text"]] for n in names)]


def _along(a: tuple[float, float], b: tuple[float, float], p: tuple[float, float], q: tuple[float, float]) -> float:
    """How long the segment ab runs along the segment pq: within ALONG_NEAR of it, at less than
    ALONG_ANGLE to it (one unit at a time); 0 crossing it more steeply."""
    qx, qy = q[0] - p[0], q[1] - p[1]
    squared = qx * qx + qy * qy or 1.0
    length = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
    if abs((b[0] - a[0]) * qy - (b[1] - a[1]) * qx) / (length * math.sqrt(squared)) > math.sin(ALONG_ANGLE):
        return 0.0
    steps = max(1, round(length))
    near = 0
    for t in range(steps + 1):
        sx, sy = a[0] + (b[0] - a[0]) * t / steps, a[1] + (b[1] - a[1]) * t / steps
        u = min(1.0, max(0.0, ((sx - p[0]) * qx + (sy - p[1]) * qy) / squared))
        near += math.hypot(sx - p[0] - u * qx, sy - p[1] - u * qy) <= ALONG_NEAR
    return near * length / steps


def _overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _grown(marks: "Marks | None") -> list[tuple[float, float, float, float]]:
    """The arrows' words' boxes, grown by WORD_CLEAR: what the labels' lines and names keep clear of."""
    if marks is None:
        return []
    return [(b[0] - WORD_CLEAR, b[1] - WORD_CLEAR, b[2] + WORD_CLEAR, b[3] + WORD_CLEAR) for b in marks.words]


def _crossings(image, x: float, y: float, w: float, placed: list[dict], marks: "Marks | None" = None) -> int:
    """How many lines the leaders cross: the drawing's (a run of ink along a leader, the one
    its point lies in not counted), one another's, and the other names; the arrows' words
    (a leader through one's box, a name on one) and their arrows (a leader along one) weigh
    ARROW_CROSSING each."""
    count = 0
    if marks is not None:
        words = marks.words
        for n in placed:
            count += ARROW_CROSSING * sum(_overlap(n["box"], b) for b in words)
            for p in n["points"]:
                count += ARROW_CROSSING * sum(_through(n["start"], p, b) for b in words)
                count += ARROW_CROSSING * sum(_along(n["start"], p, *line) > ALONG_LENGTH for line in marks.lines)
    if image is not None:
        k = image.width / w
        pixels = image.load()
        for n in placed:
            for px, py in n["points"]:
                sx, sy = n["start"]
                steps = max(1, round(math.hypot(px - sx, py - sy) * k))
                runs, was = 0, False
                for t in range(steps + 1):
                    i, j = round((sx + (px - sx) * t / steps - x) * k), round((sy + (py - sy) * t / steps - y) * k)
                    ink = 0 <= i < image.width and 0 <= j < image.height and pixels[i, j] < 248
                    runs += ink and not was
                    was = ink
                count += runs - was
    leaders = [(n["start"], p, n["text"]) for n in placed for p in n["points"]]
    for i, (a, b, ta) in enumerate(leaders):
        count += sum(_cross(a, b, c, d) for c, d, tb in leaders[i + 1 :] if tb != ta)
        for other in placed:
            if other["text"] != ta and _through(a, b, other["box"]):
                count += 1
    return count


def _through(a: tuple[float, float], b: tuple[float, float], box: tuple[float, float, float, float]) -> bool:
    """Whether the segment ab passes through the box."""
    x0, y0, x1, y1 = box
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if any(x0 < p[0] < x1 and y0 < p[1] < y1 for p in (a, b)):
        return True
    return any(_cross(a, b, corners[i], corners[(i + 1) % 4]) for i in range(4))


def _length(placed: list[dict]) -> float:
    return sum(math.hypot(px - n["start"][0], py - n["start"][1]) for n in placed for px, py in n["points"])


def labelled(svg: str, labels: list[Label], clamp: bool = False, marks: "Marks | None" = None) -> str:
    """The cleaned SVG with its labels set beside its drawing (see above), clear of the arrows
    and words `marks` says arrowed set. The same SVG without labels; LabelError for a point
    outside the drawing's frame (brought to its edge with `clamp`: the AI asked again and still
    giving it)."""
    if not labels:
        return svg
    view = figures._VIEWBOX.search(svg)
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
    # a point brought onto the drawing's lines, never onto an arrow's word (no part of it)
    bare = image
    if image is not None and marks is not None and marks.words:
        from PIL import ImageDraw

        bare, k = image.copy(), image.width / w
        for b in marks.words:
            ImageDraw.Draw(bare).rectangle([(b[0] - x) * k, (b[1] - y) * k, (b[2] - x) * k, (b[3] - y) * k], fill=255)
    outside = _outside(bare, bare.width / w) if bare is not None else None
    # a name given at several points (a gene's place on both chromosomes): one name, a line to each
    points: dict[str, list[tuple[float, float]]] = {}
    for label in labels:
        points.setdefault(label.text.strip(), []).append(_snapped(bare, x, y, w, label.x, label.y, outside))

    def name(text: str, at: list[tuple[float, float]], key: str) -> dict:
        rows = _lines(text)
        return {
            "text": key,
            "rows": rows,
            "w": max(_measure(r) for r in rows),
            "h": line * len(rows),
            "points": at,
            "px": sum(p[0] for p in at) / len(at),
            "py": sum(p[1] for p in at) / len(at),
        }

    names = [name(text, at, text) for text, at in points.items()]
    by_mean = {n["text"]: "left" if n["px"] < middle else "right" for n in names}
    # the layouts tried: two columns (each name on its points' side; a name whose points lie on
    # both sides, as a flower's petals, written in both), one column, a row under or over it
    layouts = [_in_columns(names, by_mean, left, right, top, bottom, marks)]
    split, sides = [], {}
    for n in names:
        parts = {s: [p for p in n["points"] if (p[0] < middle) == (s == "left")] for s in ("left", "right")}
        if all(parts.values()) and len(n["points"]) > 1:
            for s in ("left", "right"):
                split.append(name(n["text"], parts[s], f"{n['text']}\0{s}"))
                sides[split[-1]["text"]] = s
        else:
            split.append(n)
            sides[n["text"]] = by_mean[n["text"]]
    if len(split) > len(names):
        layouts.append(_in_columns(split, sides, left, right, top, bottom, marks))
    for s in ("left", "right"):
        layouts.append(_in_columns(names, dict.fromkeys(by_mean, s), left, right, top, bottom, marks))
    # a row only within the frame's width: wider, it would make the whole figure smaller
    under = max([bottom] + [p[1] + 3 for n in names for p in n["points"]])
    over = min([top] + [p[1] - 3 for n in names for p in n["points"]])
    rows = (_row(names, x, x + w, under, True, marks), _row(names, x, x + w, over, False, marks))
    for row in rows:
        if all(x - 0.5 <= n["box"][0] and n["box"][2] <= x + w + 0.5 for n in row):
            layouts.append(row)
    # the one whose leaders cross the fewest lines, then the shortest (the first on a tie)
    placed = min(layouts, key=lambda p: _crossings(image, x, y, w, p, marks) * CROSSING * w + _length(p))
    parts = []
    for n in placed:
        start, middle_y = n["start"]
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
                f'<text x="{n["x"]:.1f}" y="{base:.1f}" font-family="sans-serif" font-size="{LABEL_SIZE}" '
                f'text-anchor="{n["anchor"]}" fill="#000000">{text}</text>'
            )
    nx = min([x] + [n["box"][0] - LABEL_GAP for n in placed])
    nr = max([x + w] + [n["box"][2] + LABEL_GAP for n in placed])
    ny = min([n["top"] for n in placed] + [y]) - figures.MARGIN
    nb = max([n["top"] + n["h"] for n in placed] + [y + h]) + figures.MARGIN
    ny, nb = min(ny, y), max(nb, y + h)
    svg = figures._framed(svg, view.group(0), nx, ny, nr - nx, nb - ny)
    opening = re.search(r"<svg[^>]*>", svg)
    closing = svg.rfind("</svg>")
    if opening is None or closing < 0:
        return svg
    ground = f'<rect x="{nx:.3f}" y="{ny:.3f}" width="{nr - nx:.3f}" height="{nb - ny:.3f}" fill="#ffffff"/>'
    return svg[: opening.end()] + ground + svg[opening.end() : closing] + "".join(parts) + svg[closing:]


# --- Arrows and their words --------------------------------------------------------------------
# The words the AI wrote on its own arrows, placed by eye, fell on the drawing's outlines
# (« Dioxyde de carbone » across the chloroplast's, 3 drawings in 3). The AI gives each such
# arrow, from where it starts to its tip, with its word; the app draws it and sets the word beside
# it, along its normal, at the first spot free of ink.

ARROW_WIDTH = 2  # its line, in the viewBox's units
ARROW_HEAD = 10  # its head's length; its width, 0.7 of that
ARROW_GAP = 3  # between the arrow and its word
ARROW_REACH = 60  # how far from its arrow a word is looked for, past that set where least ink lies
ARROW_ALONG = (0.5, 0.35, 0.65, 0.2, 0.8, 0.0, 1.0)  # where along the arrow, from its start
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$|^#[0-9a-fA-F]{3}$")


def _escaped(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _arrow_shape(a: Arrow) -> str:
    """The arrow as SVG: its line stopped at its head, the head a triangle at its tip."""
    colour = a.color if _COLOR.match(a.color.strip()) else "#000000"
    dx, dy = a.x2 - a.x1, a.y2 - a.y1
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    head = min(ARROW_HEAD, length * 0.6)
    bx, by = a.x2 - ux * head, a.y2 - uy * head
    half = head * 0.35
    left, right = (bx - uy * half, by + ux * half), (bx + uy * half, by - ux * half)
    return (
        f'<line x1="{a.x1:.1f}" y1="{a.y1:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{colour}" '
        f'stroke-width="{ARROW_WIDTH}"/>'
        f'<polygon points="{a.x2:.1f},{a.y2:.1f} {left[0]:.1f},{left[1]:.1f} {right[0]:.1f},{right[1]:.1f}" '
        f'fill="{colour}"/>'
    )


def _inserted(svg: str, parts: str) -> str:
    closing = svg.rfind("</svg>")
    return svg[:closing] + parts + svg[closing:] if closing >= 0 else svg


def _word_box(image, x: float, y: float, k: float, box: tuple[float, float, float, float]) -> int:
    """How much ink lies in the box (in the viewBox's units); past the frame, none (the frame
    is grown to hold a word set there)."""
    i0, j0 = max(0, round((box[0] - x) * k)), max(0, round((box[1] - y) * k))
    i1, j1 = min(image.width, round((box[2] - x) * k)), min(image.height, round((box[3] - y) * k))
    if i0 >= i1 or j0 >= j1:
        return 0
    crop = image.crop((i0, j0, i1, j1)).point(lambda v: 1 if v < 248 else 0)
    return crop.histogram()[1]


@dataclass
class Marks:
    """What arrowed set, in the viewBox's units: the labels' lines and names kept clear of it."""

    words: list[tuple[float, float, float, float]] = field(default_factory=list)  # each word's box
    lines: list[tuple[tuple[float, float], tuple[float, float]]] = field(default_factory=list)  # each arrow


def arrowed(svg: str, arrows: list[Arrow]) -> str:
    """The cleaned SVG with its arrows drawn and their words set beside them (see above), its
    frame grown to a word set past it (no room within it beside its arrow); the same SVG
    without arrows."""
    return arrows_set(svg, arrows)[0]


def arrows_set(svg: str, arrows: list[Arrow], points: list[tuple[float, float]] | None = None) -> tuple[str, Marks]:
    """arrowed's SVG, and where it set the arrows and their words (labelled keeps clear of them);
    no word within WORD_CLEAR of the labels' `points` (a word on a region's point: its label's
    line could only end on it)."""
    marks = Marks()
    arrows = [a for a in arrows if math.hypot(a.x2 - a.x1, a.y2 - a.y1) > 0]
    if not arrows:
        return svg, marks
    view = figures._VIEWBOX.search(svg)
    if view is None:
        return svg, marks
    x, y, w, h = map(float, view.groups())
    arrows = [
        a.model_copy(
            update={
                "x1": min(max(a.x1, x), x + w),
                "y1": min(max(a.y1, y), y + h),
                "x2": min(max(a.x2, x), x + w),
                "y2": min(max(a.y2, y), y + h),
            }
        )
        for a in arrows
    ]
    svg = _inserted(svg, "".join(_arrow_shape(a) for a in arrows))
    marks.lines = [((a.x1, a.y1), (a.x2, a.y2)) for a in arrows]
    image = _drawn_image(svg)
    if image is None:
        return svg, marks
    from PIL import ImageDraw

    k = image.width / w
    drawn = ImageDraw.Draw(image)
    for px, py in points or []:
        r = WORD_CLEAR * k
        drawn.ellipse([(px - x) * k - r, (py - y) * k - r, (px - x) * k + r, (py - y) * k + r], fill=0)
    line = LABEL_SIZE * LABEL_LINE
    words = []
    for a in arrows:
        rows = _lines(a.text.strip()) if a.text.strip() else []
        if not rows:
            continue
        bw, bh = max(_measure(r) for r in rows) + 2, line * len(rows)
        length = math.hypot(a.x2 - a.x1, a.y2 - a.y1)
        ux, uy = (a.x2 - a.x1) / length, (a.y2 - a.y1) / length
        nx, ny = -uy, ux
        if ny > 0 or (ny == 0 and nx < 0):
            nx, ny = -nx, -ny  # its first side the one above it (right of an upright arrow)
        reach = abs(nx) * bw / 2 + abs(ny) * bh / 2  # from the box's middle to its side facing the arrow
        spots = (  # nearest first, from its middle along it, on either side
            (a.x1 + (a.x2 - a.x1) * t + side * nx * (ARROW_GAP + d + reach),
             a.y1 + (a.y2 - a.y1) * t + side * ny * (ARROW_GAP + d + reach))
            for d in range(0, ARROW_REACH + 1, 2)
            for t in ARROW_ALONG
            for side in (1, -1)
        )  # fmt: skip
        best: tuple[int, tuple[float, float, float, float]] | None = None  # the first free, else the least ink
        for cx, cy in spots:
            box = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
            ink = _word_box(image, x, y, k, box)
            if best is None or ink < best[0]:
                best = (ink, box)
            if ink == 0:
                break
        if best is None:
            continue
        box = best[1]
        marks.words.append(box)
        drawn.rectangle([(box[0] - x) * k, (box[1] - y) * k, (box[2] - x) * k, (box[3] - y) * k], fill=0)
        middle = (box[0] + box[2]) / 2
        for n, row in enumerate(rows):
            base = box[1] + line * n + LABEL_SIZE
            words.append(
                f'<text x="{middle:.1f}" y="{base:.1f}" font-family="sans-serif" font-size="{LABEL_SIZE}" '
                f'text-anchor="middle" fill="#000000">{_escaped(row)}</text>'
            )
    return figures.fitted(_inserted(svg, "".join(words))), marks  # a word set past the frame: the frame grown to it
