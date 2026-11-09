"""The solid family (our solids, a frame of space): hidden edges and sections computed,
proportions, lengths beside their lines."""

import io
import re

import pytest

from figures.support import drawn_size
from notosaurus_core import figures, figures_typst


@pytest.mark.parametrize(
    ("body", "hidden"),
    [
        ("#cuboid(5, 3, 2)", 3),  # the three edges at the back bottom left corner
        ("#cuboid(30, 30, 30)", 3),  # a cube, in centimetres: the same, drawn as large
        ("#pyramid(side: 4, height: 5)", 3),  # the base's two back sides, the back edge to the apex
        ('#pyramid(side: 4, height: 5, foot: "O")', 4),  # and its height, inside
        ("#prism(((0, 0), (4, 0), (1, 3)), 4)", 3),  # the base's two back sides, the back edge
        ("#prism(((0, 0), (4, 0), (2, 3)), 6, lying: true)", 3),
        # a section's sides on hidden faces too: the cuboid's back and left, the pyramid's and
        # the prism's two back faces; parallel to the front, its sides on the left and the base
        ("#cuboid(5, 3, 4, section: 2)", 5),
        ('#cuboid(5, 3, 4, names: ("A", "B", "C", "D", "E", "F", "G", "H"), section: (parallel: "ABFE", at: 1))', 5),
        ('#cuboid(5, 3, 4, section: (parallel: "left", at: 1))', 5),
        ("#pyramid(side: 4, height: 6, section: 3)", 5),
        ("#prism(((0, 0), (4, 0), (1, 3)), 4, section: 1)", 5),
        # a round section's back half: with the base's, the sphere's alone (no equator then)
        ("#cylinder(2, 5, section: 2)", 2),
        ("#cone(3, 6, section: 2)", 2),
        ("#sphere(5, section: 3)", 1),
        ('#sphere(5, section: 3, section-centre: "H")', 2),  # and [OH], inside
    ],
)
def test_a_solids_hidden_edges_computed(body, hidden):
    """A polyhedron's hidden edges (dashed) are those whose two faces turn their back to the
    viewer, computed from the solid: never chosen by the AI (an edge dashed in front of a
    cuboid, a hidden one missing: 5 of 8 polyhedra drawn wrong as SVG)."""
    svg = figures.clean(figures_typst.compile_svg("solid", body))
    assert svg.count("stroke-dasharray") == hidden


CUBE_FACES = ", ".join(
    "(" + ", ".join(f'"{v}"' for v in face) + ")" for face in ("ABCD", "EFGH", "ABFE", "BCGF", "CDHG", "DAEH")
)


CUBE_POINTS = (
    "A: (0, 0, 0), B: (1, 0, 0), C: (1, 1, 0), D: (0, 1, 0), E: (0, 0, 1), F: (1, 0, 1), G: (1, 1, 1), H: (0, 1, 1)"
)


@pytest.mark.parametrize(
    ("body", "hidden"),
    [
        ("#space(points: (A: (2, 0, 0), B: (0, 3, 0), C: (0, 0, 1)))", 0),
        # the plane ABC hides the axes from O to where it meets them: three dashed runs
        ('#space(points: (A: (2, 0, 0), B: (0, 3, 0), C: (0, 0, 1)), planes: (("A", "B", "C"),))', 3),
        # a cube by its faces: its three hidden edges
        (f"#space(origin: none, axes: none, units: none, points: ({CUBE_POINTS}), faces: ({CUBE_FACES}))", 3),
    ],
)
def test_a_frame_of_space_computes_what_is_hidden(body, hidden):
    """A frame of space (O ; i, j, k) was drawn as SVG by hand (no family had one): its points
    placed from their coordinates, what a plane or a solid's faces hide dashed, computed."""
    svg = figures.clean(figures_typst.compile_svg("solid", body))
    assert len(re.findall(r'stroke-dasharray="[^"]+"', svg)) == hidden


def test_a_frame_of_space_drawn_as_the_rule_says():
    """The rule's own call compiles; a point's coordinates other than three numbers, or a
    point named but not given, refused saying which."""
    rule = (figures_typst.RULES / "solid.md").read_text(encoding="utf-8")
    call = re.search(r"`(space\(points: [^`]*\))`", rule)
    assert call
    assert figures.clean(figures_typst.compile_svg("solid", "#" + call[1])).startswith("<svg")
    with pytest.raises(figures_typst.Unusable, match="three coordinates"):
        figures_typst.compile_svg("solid", "#space(points: (A: (2, 0),))")
    with pytest.raises(figures_typst.Unusable, match="not in points"):
        figures_typst.compile_svg("solid", '#space(points: (A: (2, 0, 0),), segments: (("A", "B"),))')


def test_a_section_outside_its_solid_refused():
    """A section's plane outside the solid, or parallel to a face it hasn't: refused, saying
    why, for the AI to write it again; never a solid drawn without it."""
    for body, said in (
        ("#cuboid(5, 3, 4, section: 4)", "between 0 and 4"),
        ("#pyramid(side: 4, height: 6, section: -1)", "between 0 and 6"),
        ('#cuboid(5, 3, 4, section: (parallel: "ABFE", at: 1))', "names given"),
        ("#cone(3, 6, section: 6)", "between 0 and 6"),
        ("#sphere(5, section: 5)", "between -5 and 5"),
    ):
        with pytest.raises(figures_typst.Unusable, match=said):
            figures_typst.compile_svg("solid", body)


def test_a_solid_drawn_the_same_whatever_its_unit():
    """Lengths in any unit: only their ratio shows (a cuboid 5 × 3 × 2 as 50 × 30 × 20)."""
    small = figures_typst.compile_svg("solid", "#cuboid(5, 3, 2)")
    assert figures_typst.compile_svg("solid", "#cuboid(50, 30, 20)") == small


@pytest.mark.parametrize(
    ("body", "ratio"),
    [
        ("#cone(3, 4)", 6 / (4 + 3 * 0.35)),  # its diameter over its height and the base's front half
        ("#cylinder(2, 6)", 4 / (6 + 2 * 2 * 0.35)),  # its diameter over its height and both bases' halves
        ("#sphere(2)", 1),
    ],
)
def test_a_round_solids_proportions_computed(body, ratio):
    """A round solid in proportion to the lengths given: a cone of radius 3 and height 4 wider
    than tall (drawn as SVG by eye: taller, twice in two; a cylinder 2 by 6 almost square)."""
    width, height = drawn_size("solid", body)
    assert width / height == pytest.approx(ratio, rel=0.01)


def test_solids_compared_at_one_scale():
    """Two cylinders of radius 1 and 3 drawn with the same largest: the second three times as
    wide (each alone would be drawn about 4 cm)."""
    thin = drawn_size("solid", "#cylinder(1, 5, largest: 6)")[0]
    wide = drawn_size("solid", "#cylinder(3, 1, largest: 6)")[0]
    assert wide / thin == pytest.approx(3, rel=0.01)


@pytest.mark.parametrize("cone", ["cone(3, 4", "cone(2, 5", "cone(4, 1.5"])
def test_a_cones_height_beside_it(cone):
    """A cone's height ("4 cm") where it fits, never across its slant or its base: the label
    drawn red, no line's pixel under it."""
    from PIL import Image

    def png(label: str) -> Image.Image:
        svg = figures.clean(figures_typst.compile_svg("solid", f"#{cone}, height-label: {label}[4 cm])"))
        return Image.open(io.BytesIO(figures.to_png(svg))).convert("RGB")

    bare, labelled = png("hide"), png("text(fill: rgb(255, 0, 0))")
    lines = {(x, y) for y in range(bare.height) for x in range(bare.width) if sum(bare.getpixel((x, y))) < 300}
    reddish = lambda p: p[0] > 200 and p[1] < 140  # noqa: E731
    reds = {(x, y) for y in range(labelled.height) for x in range(labelled.width) if reddish(labelled.getpixel((x, y)))}
    assert reds and not lines & reds


def test_a_solids_lengths_beside_its_edges():
    """A cuboid's lengths ("10 mm") beside their edges, outwards, never across an edge: the
    labels drawn red, no edge's pixel under them."""
    from PIL import Image

    def png(labels: str) -> Image.Image:
        svg = figures.clean(figures_typst.compile_svg("solid", f"#cuboid(40, 20, 10{labels})"))
        return Image.open(io.BytesIO(figures.to_png(svg))).convert("RGB")

    labels = ", length-label: {}[40 mm], width-label: {}[20 mm], height-label: {}[10 mm]"
    bare = png(labels.replace("{}", "hide"))  # the same place taken, nothing drawn
    labelled = png(labels.replace("{}", "text(fill: rgb(255, 0, 0))"))
    assert bare.size == labelled.size
    edges = {(x, y) for y in range(bare.height) for x in range(bare.width) if sum(bare.getpixel((x, y))) < 300}
    reddish = lambda p: p[0] > 200 and p[1] < 140  # noqa: E731
    reds = {(x, y) for y in range(labelled.height) for x in range(labelled.width) if reddish(labelled.getpixel((x, y)))}
    assert reds and not edges & reds


@pytest.mark.parametrize(
    "body",
    [
        '#sphere(3, centre-name: "O", radius-label: {}[$R = 3$ cm])',  # too long above: beyond its end
        '#sphere(3, centre-name: "O", radius-label: {}[$R$])',
        '#sphere(5, centre-name: "O", section: 3, section-centre: "H", section-label: {}[$r$], '
        "radius-label: {}[5 cm], distance-label: {}[3 cm])",
        '#sphere(5, centre-name: "O", section: 4, section-centre: "H", section-label: {}[3 cm])',
    ],
)
def test_a_spheres_lengths_clear_of_its_lines(body):
    """A sphere's lengths (its radius, a section's) beside their segments, clear of every line,
    the equator's or the section's dashed half, and of the centre's name (the radius's label
    against "O", on the equator: 3 drawings in 3). The labels drawn red, no line within 3
    pixels of them."""
    from PIL import Image

    def png(label: str) -> Image.Image:
        svg = figures.clean(figures_typst.compile_svg("solid", body.replace("{}", label)))
        return Image.open(io.BytesIO(figures.to_png(svg))).convert("RGB")

    bare, labelled = png("hide"), png("text(fill: rgb(255, 0, 0))")
    assert bare.size == labelled.size
    lines = {(x, y) for y in range(bare.height) for x in range(bare.width) if sum(bare.getpixel((x, y))) < 300}
    near = {(x + dx, y + dy) for x, y in lines for dx in range(-3, 4) for dy in range(-3, 4)}
    reddish = lambda p: p[0] > 200 and p[1] < 140  # noqa: E731
    reds = {(x, y) for y in range(labelled.height) for x in range(labelled.width) if reddish(labelled.getpixel((x, y)))}
    assert reds and not near & reds
