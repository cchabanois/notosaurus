"""A figure's text as large as a card shows it (text_size.py): measured in its SVG, whichever
way it was drawn; a figure too small to read refused (figures_typst.TooSmall), told its size."""

import pytest

from figures.support import rule_example
from notosaurus_core import figures, figures_typst, text_size

MARGIN = 12  # a Typst figure's page: 6 pt each side


def _wide(width: float) -> str:
    """A word at Typst's size (11 pt) in a figure `width` pt wide: shown at 320 px, its text
    11 × 320 / (width + MARGIN) px high."""
    return f'#block(width: {width:.3f}pt)[#text("Mi 12")]'


def _width_for(px: float) -> float:
    return 11 * text_size.CARD_PX[0] / px - MARGIN


@pytest.mark.parametrize("family", sorted(figures_typst.FAMILIES))
def test_every_familys_text_too_small_to_read_refused(family):
    """A figure so wide that its text, fitted to a phone's card, is under its family's least
    (MIN_TEXT_PX, or MIN_TEXT_PX_SET: a timeline's, set by its preamble): refused, told the
    size measured and its own, its drawing kept with the refusal; just above it: drawn."""
    least = figures_typst.MIN_TEXT_PX_SET.get(family, figures_typst.MIN_TEXT_PX)
    with pytest.raises(figures_typst.TooSmall) as refused:
        figures_typst.compile_svg(family, _wide(_width_for(least - 0.3)))
    assert refused.value.px == pytest.approx(least - 0.3, abs=0.05)
    assert f"{least - 0.3:.1f} px high, {least:g} at least" in str(refused.value)
    assert "<svg" in refused.value.svg
    assert figures_typst.compile_svg(family, _wide(_width_for(least + 0.2))).startswith("<svg")


@pytest.mark.parametrize("family", sorted(figures_typst.FAMILIES))
def test_every_familys_example_readable_on_a_card(family):
    """The example each rule shows the AI: read on a card, never refused."""
    figures_typst.compile_svg(family, rule_example(family))


def test_a_typst_texts_size_read_from_its_letters():
    """Typst writes each letter as a shape: its size found from the same letter known, in the
    figures' font (plain, bold, italic) and in the formulas'; an exponent or an index (set
    smaller beside its text on purpose) and a protractor's degrees (a scale's fine print) not
    counted."""
    measured = lambda body: text_size.smallest_px(figures_typst.compile_svg("geometry", body))  # noqa: E731
    assert measured("#text(size: 9pt)[Évaporation]") == pytest.approx(9)
    assert measured("#text(size: 8pt)[*eau* _vapeur_]") == pytest.approx(8)
    assert measured("#text(size: 9pt)[$f(x) = 2 x + 1$]") == pytest.approx(9)
    assert measured("#text(size: 10pt)[3 cm#super[2], H#sub[2]O, $v_(max) = 3 x^2$]") == pytest.approx(10)
    assert measured("#text(size: 10pt)[Lune] #text(size: 8pt)[Terre]") == pytest.approx(8)
    protractor = (
        '#ctz-canvas({ ctz-init(); ctz-def-points(O: (0, 0), X: (4, 0)); ctz-draw-segment("O", "X"); '
        'ctz-draw-protractor("O", "X"); ctz-draw-labels(O: "below") })'
    )
    assert measured(protractor) == pytest.approx(11)


def test_an_svgs_text_size_read_from_its_font_sizes():
    """The AI's SVG: each text's font-size (written, in its style, inherited, in em), times its
    transforms, fitted to the card; an index set by baseline-shift not counted."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400" width="800" height="400">'
        '<g font-size="20"><text x="10" y="40">Noyau</text>'
        '<text x="10" y="80" style="font-size:0.8em">Membrane</text>'
        '<g transform="scale(0.5)"><text x="10" y="200" font-size="30">ADN</text></g>'
        '<text x="10" y="300">CO<tspan baseline-shift="sub" font-size="10">2</tspan></text></g></svg>'
    )
    assert text_size.smallest_px(svg) == pytest.approx(15 * 320 / 800)
    assert text_size.smallest_px(svg.replace('viewBox="0 0 800 400"', 'viewBox="0 0 320 160"')) == pytest.approx(15)
    assert text_size.smallest_px('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"/>') is None


def test_an_svgs_refusal_says_its_size_and_how_large_to_write():
    """Told the AI: its viewBox, its smallest text once fitted, the font-size read at this size."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 800">'
        '<text x="9" y="40" font-size="20">Rein</text></svg>'
    )
    said = text_size.svg_too_small(figures.clean(svg), 7)
    assert "viewBox is 1600 wide and 800 high" in said and "4.0 px high, 7 at least" in said
    assert "at least 35 in this viewBox" in said
    assert text_size.svg_too_small(svg.replace("1600 800", "400 200"), 7) == ""
