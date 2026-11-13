"""The optics family (cetz, our functions): a refracted ray at the Snell-Descartes angle, a
total reflection beyond the critical angle, a lens's image computed and its three rays
through it; never placed by the AI's eye."""

import json
import math
import re

import pytest
import typst

from notosaurus_core import figures, figures_typst


def _value(tmp_path, expression: str):
    """What the optics preamble computes, read back (a Typst value, as JSON)."""
    page = tmp_path / "query.typ"
    page.write_text(
        figures_typst.FAMILIES["optics"].preamble + f"\n#metadata({expression}) <value>\n", encoding="utf-8"
    )
    found = typst.query(
        str(page), "<value>", field="value", one=True, format="json", package_path=str(figures_typst.packages())
    )
    return json.loads(found)


def test_light_rays_are_a_family_of_their_own():
    """Refraction and a lens's image were SVG drawn by the AI: an incident ray's arrow pointing
    away from the surface, rays not meeting at B', angles by eye. A family of its own, picked
    for them, never for a diffraction or a shadow."""
    assert "optics" in figures_typst.FAMILIES and "optics" in figures_typst.FigureKind.__args__
    kind = figures_typst.KINDS.split('"optics":')[1].split(";")[0]
    assert "refracted or reflected" in kind and "converging lens" in kind and "never a diffraction" in kind


def test_the_rules_calls_compile():
    rule = (figures_typst.RULES / "optics.md").read_text(encoding="utf-8")
    calls = [c for c in re.findall(r"`(#(?:refraction|lens)\([^`]*\))`", rule) if "…" not in c]
    assert calls  # its example (a refraction) compiles in test_each_familys_rule_example_compiles
    for call in calls:
        assert figures.clean(figures_typst.compile_svg("optics", call)).startswith("<svg")


@pytest.mark.parametrize(("n1", "n2", "i1"), [(1.00, 1.33, 40), (1.00, 1.5, 30), (1.33, 1.00, 30), (1.5, 1.00, 41)])
def test_the_refracted_ray_is_at_the_snell_descartes_angle(tmp_path, n1, n2, i1):
    i2 = _value(tmp_path, f"refracted-angle({n1}, {n2}, {i1})")
    assert i2 == pytest.approx(math.degrees(math.asin(n1 * math.sin(math.radians(i1)) / n2)), abs=1e-6)


def test_beyond_the_critical_angle_the_reflection_is_total(tmp_path):
    """Water to air at 60° (critical angle 48.8°): no refracted ray, the reflected one drawn;
    its angle named only when asked (a label not asked may give a card's answer away)."""
    assert _value(tmp_path, "refracted-angle(1.33, 1.00, 60)") is None
    call = "#refraction(n1: 1.33, n2: 1.00, incidence: 60{})"
    total = figures_typst.compile_svg("optics", call.format(""))
    asked = figures_typst.compile_svg("optics", call.format(", reflected: true"))
    named = figures_typst.compile_svg("optics", call.format(", reflected: true, names: (r: [Z],)"))
    assert total.startswith("<svg") and total != asked and asked != named


@pytest.mark.parametrize(("f", "xa", "h"), [(4, -6, 2), (4, -8, 2), (5, -12, 1.5), (4, -2, 1.5), (3, -1, 1)])
def test_a_lens_three_rays_meet_at_the_computed_image(tmp_path, f, xa, h):
    """1/OA' − 1/OA = 1/f': the ray through O, the one parallel then through F', the one
    through F then parallel, all through B' (a virtual image: their extensions)."""
    xi, hi, hits = _value(tmp_path, f"lens-image({f}, {xa}, {h})")
    assert 1 / xi - 1 / xa == pytest.approx(1 / f)

    def collinear(p, q, r):
        return abs((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])) < 1e-6

    b, b2 = (xa, h), (xi, hi)
    through_o, parallel, through_f = hits
    assert through_o == [0, 0] and collinear(b, through_o, b2)
    assert parallel[1] == pytest.approx(h) and collinear(parallel, (f, 0), b2)  # out through F'
    assert collinear(b, (-f, 0), through_f) and through_f[1] == pytest.approx(hi)  # in through F, out parallel


def test_a_virtual_image_and_hidden_names_compile():
    """A magnifying glass (the object between F and O): its image virtual, dashed; a name a
    card asks for written "?", not shown."""
    plain = figures_typst.compile_svg("optics", "#lens(focal: 4, object: -2, height: 1.5, distances: true)")
    hidden = figures_typst.compile_svg(
        "optics", '#lens(focal: 4, object: -2, height: 1.5, distances: true, hidden: ("OA\'",))'
    )
    assert plain.startswith("<svg") and hidden != plain
    with pytest.raises(figures_typst.Unusable, match="has no image"):
        figures_typst.compile_svg("optics", "#lens(focal: 4, object: -4, height: 1)")
