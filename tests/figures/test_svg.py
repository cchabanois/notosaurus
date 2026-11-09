"""The figures drawn as SVG (figures.py): cleaned (only shapes and text, nothing that runs or
loads), sized, fitted to their labels, their colours kept, seen as a PNG."""

import re
from xml.etree import ElementTree

import pytest

from figures.support import SQUARE
from notosaurus_core import figures

TRAPPED = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" width="9999" onload="alert(1)">
<script>alert(1)</script><rect width="400" height="300" fill="white"/>
<a href="javascript:alert(1)"><text x="10" y="20">lien</text></a>
<image href="http://evil.test/x.png"/><foreignObject><div>x</div></foreignObject>
<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="5" refY="5" orient="auto">
<path d="M0,0 L10,5 L0,10 z"/></marker></defs>
<line x1="0" y1="0" x2="100" y2="0" stroke="black" marker-end="url(#arrow)" style="stroke-width:2;fill:url(http://evil.test)"/>
<text x="50" y="50" transform="rotate(-30 50 50)" font-family="sans-serif" onclick="x()">hypoténuse</text>
<rect fill="url(http://evil.test/a)" transform="translate(1,2) expression(alert(1))"/><animate attributeName="x"/>
</svg>"""


def test_clean_keeps_only_shapes_and_text():
    svg = figures.clean(TRAPPED)
    for gone in (
        "script",
        "onload",
        "javascript",
        "<image",
        "foreignObject",
        "evil.test",
        "expression",
        "animate",
        "onclick",
    ):
        assert gone not in svg, gone
    for kept in ('transform="rotate(-30 50 50)"', 'marker-end="url(#arrow)"', "hypoténuse", 'style="stroke-width:2"'):
        assert kept in svg, kept
    assert 'width="400" height="300"' in svg  # sized from its viewBox: an <img> shows it at its size


@pytest.mark.parametrize(
    "bad",
    [
        '<!DOCTYPE svg [<!ENTITY x "y">]><svg xmlns="http://www.w3.org/2000/svg"/>',  # no DTD, no entities
        "<html><body/></html>",
        "<svg",
        "<svg>" + "<g/>" * 60000 + "</svg>",  # too big
    ],
    ids=["dtd", "not-svg", "truncated", "too-big"],  # short names: the SVG itself is too long for one
)
def test_clean_refuses(bad):
    with pytest.raises(figures.FigureError):
        figures.clean(bad)


def test_clean_strips_a_kept_elements_dangerous_attributes():
    """A shape kept, its handlers and external references dropped (not the whole element)."""
    svg = figures.clean(
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 400 300">'
        '<rect onclick="alert(1)" href="https://evil.test/" xlink:href="javascript:alert(1)"'
        ' style="fill:url(http://evil.test)" x="1" y="1" width="2" height="2"/></svg>'
    )
    rect = ElementTree.fromstring(svg).find(f"{{{figures.SVG_NS}}}rect")
    assert rect.attrib == {"x": "1", "y": "1", "width": "2", "height": "2"}  # no empty style="" left either
    for gone in ("onclick", "href", "javascript", "evil.test", "style"):
        assert gone not in svg, gone


NO_SIZE = ["a b c d", "0 0 400", "0 0 400 300 1", "0 0 NaN 300", "0 0 400 inf", "0 0 1e309 300", "nan 0 400 300",
           "0 0 -400 300", "0 0 400 0"]  # fmt: skip


@pytest.mark.parametrize("viewbox", NO_SIZE)
def test_clean_refuses_a_viewbox_without_a_size(viewbox):
    with pytest.raises(figures.FigureError) as e:
        figures.clean(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}"><rect width="1" height="1"/></svg>')
    assert e.value.code == "figure.invalid"


def test_clean_sizes_from_the_viewbox():
    svg = figures.clean('<svg xmlns="http://www.w3.org/2000/svg" viewBox="-10,-10 420.5 320"/>')
    assert 'width="420.5" height="320"' in svg  # its origin may be negative, not its size
    assert 'viewBox="0 0 400 300"' in figures.clean("<svg/>")  # none: the one asked for


def test_clean_gives_the_namespace():
    svg = figures.clean('<svg viewBox="0 0 200 100"><circle cx="50" cy="50" r="40"/></svg>')
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"') and "<circle" in svg


def test_shaded_and_shared_areas_kept_inside_the_figure():
    """A hatched intersection: its pattern and clip path kept, referring to the figure only."""
    svg = figures.clean(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"><defs>'
        '<pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"'
        ' href="https://evil.example/p.svg"><line x1="0" y1="0" x2="0" y2="8" stroke="black"/></pattern>'
        '<clipPath id="inA"><circle cx="150" cy="150" r="80"/></clipPath>'
        '<linearGradient id="g"><stop offset="0" stop-color="#ddd"/></linearGradient></defs>'
        '<circle cx="230" cy="150" r="80" fill="url(#hatch)" clip-path="url(#inA)"/>'
        '<rect width="10" height="10" fill="url(https://evil.example/x.svg#a)" clip-path="url(http://evil.example/#c)"/>'
        '<rect width="5" height="5" mask="url(#m) translate" stroke="url(#g)"/></svg>'
    )
    assert "<pattern" in svg and "<clipPath" in svg and "<stop" in svg and 'patternTransform="rotate(45)"' in svg
    assert 'fill="url(#hatch)"' in svg and 'clip-path="url(#inA)"' in svg and 'stroke="url(#g)"' in svg
    assert "evil" not in svg and 'translate"' not in svg  # elsewhere, or not a plain reference: gone


def test_the_check_sees_the_figure_with_its_text():
    """The PNG the check sees: the figure's size, on white, its labels drawn whatever their
    font (the one shipped: a computer, or the relay's container, may have no Arial)."""
    import io

    from PIL import Image

    assert figures.FONT.is_file() and (figures.FONT.parent / "DejaVuSans-LICENSE.txt").is_file()
    for family in ("sans-serif", "serif", "monospace", "Arial", "Times New Roman"):
        png = figures.to_png(figures.clean(SQUARE.replace(">A<", f' font-size="40" font-family="{family}">A∩B<')))
        picture = Image.open(io.BytesIO(png)).convert("L")
        assert picture.size == (figures.PNG_WIDTH, 450)
        assert picture.getextrema()[0] < 100, family  # dark pixels: the letters


def test_a_use_only_of_the_figures_own_shapes():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 10 10">'
        '<symbol id="g"><path d="M0 0L1 1"/></symbol><use xlink:href="#g"/>'
        '<use xlink:href="https://x.example/a.svg#g"/><use href="data:image/svg+xml,x"/></svg>'
    )
    cleaned = figures.clean(svg)
    assert cleaned.count('href="#g"') == 1 and "x.example" not in cleaned and "data:" not in cleaned


def test_an_svgs_labels_past_its_frame_kept_whole():
    """A figure the AI drew as SVG, a label written past its viewBox ("Diaphragme" at x = 380
    in 400): its frame grown to it, a white ground under it all; one within its frame the
    same as the AI wrote it."""
    past = figures.clean(
        '<svg viewBox="0 0 400 300"><rect width="400" height="300" fill="white"/>'
        '<line x1="200" y1="150" x2="370" y2="150" stroke="black"/>'
        '<text x="380" y="155" font-size="16">Diaphragme</text></svg>'
    )
    grown = figures.fitted(past)
    width = float(re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+)', grown).group(1))
    assert width > 400 + 60  # the word's 70 or so units past the frame, kept
    assert '<rect x="' in grown  # its white ground under the part added
    within = figures.clean(SQUARE)
    assert figures.fitted(within) == within


def test_an_svg_figures_colours_kept_whatever_their_notation():
    """An SVG the AI writes (the figures not drawn in Typst) colours with rgb(…), rgba(…),
    hsl(…) as often as with #rrggbb: kept, the same colours, in an attribute or a style; a
    text that reads like one left as it is."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
        '<rect width="4" height="4" fill="rgb(255, 0, 0)"/>'
        '<rect width="4" height="4" fill="rgba(255,0,0,0.5)"/>'
        '<circle r="2" cx="5" cy="5" style="fill: hsl(120, 100%, 25%); stroke: rgb(0 0 255 / 50%)"/>'
        "<text>rgb(1, 2, 3)</text></svg>"
    )
    kept = figures.clean(svg)
    assert re.findall(r'fill="([^"]*)"', kept) == ["#ff0000", "#ff000080"]
    assert "fill:#008000" in kept and "stroke:#0000ff80" in kept
    assert "<text>rgb(1, 2, 3)</text>" in kept


def _kept(body: str) -> str:
    return figures.clean(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">{body}</svg>')


def test_a_stylesheets_simple_rules_written_on_their_shapes():
    """An SVG styled by its <style> (".a { fill: red }", class="a"): clean drops <style> and
    class (a stylesheet may load or restyle the page), the shapes were painted black. Its
    simple rules are written on the elements they style, as CSS would (an element's own style
    last, it wins); what loads or isn't simple is left out."""
    kept = _kept(
        "<style>.a { fill: #ff0000; stroke: rgb(0, 0, 255) } rect { stroke-width: 2 } #t { font-size: 20px }"
        " @import url(https://example.com/a.css); @font-face { src: url(https://example.com/f.woff) }"
        " .b { fill: url(https://example.com/x) } svg > .c { fill: #00ff00 }</style>"
        '<rect class="a" width="5" height="5"/><rect class="a" style="fill:#123456" width="1" height="1"/>'
        '<rect class="b" width="1" height="1"/><text id="t">T</text>'
    )
    assert 'style="stroke-width:2;fill:#ff0000;stroke:#0000ff"' in kept
    assert re.search(r'style="[^"]*fill:#ff0000[^"]*;fill:#123456"', kept)  # its own style last: it wins
    assert 'id="t" style="font-size:20px"' in kept
    assert "example.com" not in kept and "@" not in kept and "#00ff00" not in kept and "<style" not in kept


def test_a_style_font_shorthand_kept_as_its_properties():
    kept = _kept('<text style="font: italic bold 12px/1.2 DejaVu Sans">A</text>')
    assert 'style="font-size:12px;font-style:italic;font-weight:bold;font-family:DejaVu Sans"' in kept


def test_a_labels_halo_painted_under_it_and_current_colour_kept():
    """paint-order (a label's white halo under its letters, not over them) and color (what
    currentColor takes): plain keywords and colours, kept."""
    kept = _kept('<g color="#ff0000"><text paint-order="stroke" stroke="#fff">A</text></g>')
    assert 'color="#ff0000"' in kept and 'paint-order="stroke"' in kept


def test_a_links_content_kept_without_the_link():
    kept = _kept('<text x="1">Avant <a href="https://example.com"><tspan>Lien</tspan> suite</a> après</text>')
    assert '<text x="1">Avant <tspan>Lien</tspan> suite après</text>' in kept and "example.com" not in kept


def test_a_text_along_the_figures_own_curve_kept():
    kept = _kept(
        '<defs><path id="p" d="M0 5 H10"/></defs>'
        '<text><textPath href="#p" startOffset="10%">Arc</textPath><textPath href="https://example.com">X</textPath></text>'
    )
    assert '<textPath href="#p" startOffset="10%">Arc</textPath>' in kept and "example.com" not in kept
