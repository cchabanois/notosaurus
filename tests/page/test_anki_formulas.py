"""A card's field drawn as Anki draws it: the shipped MathJax set up as Anki's (its
ts/mathjax: the html extension in, so \\href and \\style work there), the field as Notosaurus
writes it for Anki (note_types.common.field_html): no link, no style, class, id or attribute
of the text's choosing; a style of one colour drawn in that colour."""

import html

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from app.note_types.common import field_html  # noqa: E402

# Anki's MathJax (ts/mathjax/index.ts), from the shipped bundle: the html extension left in
CARD = """<!doctype html><meta charset="utf-8">
<script>window.MathJax = {
  tex: {
    displayMath: [["\\\\[", "\\\\]"]], processEscapes: false, processEnvironments: false, processRefs: false,
    packages: { "[+]": ["noerrors", "mathtools", "mhchem"], "[-]": ["textmacros"] },
  },
  loader: { load: ["[tex]/noerrors", "[tex]/mathtools", "[tex]/mhchem"] },
  chtml: { fontURL: "vendor/mathjax/output/chtml/fonts/woff-v2" },
  startup: { typeset: false },
};</script>
<script src="vendor/mathjax/tex-chtml-full.js"></script>
<div id="card">FIELD</div>"""

TEXT = (
    "Front \\(\\href{javascript:alert(1)}{x}\\) and \\(\\style{position:fixed;inset:0}{y}"
    " + \\class{flash}{z} + \\cssId{taken}{w} + \\data{own=1}{v}\\)\nthen \\[\\style{color: Red}{u}\\]"
)

# What the drawn card holds of the text's own: a link, a fixed element, its class, id or
# attribute; and whether something is drawn red
DRAWN = """() => {
  const all = [...document.querySelectorAll('#card *')];
  return {
    formulas: document.querySelectorAll('#card mjx-container').length,
    links: document.querySelectorAll('#card [href]').length,
    fixed: all.some((n) => n.style.position === 'fixed'),
    own: document.querySelectorAll('#card .flash, #taken, #card [data-own]').length,
    red: all.some((n) => getComputedStyle(n).color === 'rgb(255, 0, 0)'),
  };
}"""


def _drawn(browser, server, field: str) -> dict:
    context = browser.new_context(base_url=server)
    try:
        page = context.new_page()
        card = CARD.replace("FIELD", field)
        page.route(f"{server}/anki-card.html", lambda route: route.fulfill(content_type="text/html", body=card))
        page.goto("/anki-card.html")
        page.wait_for_function("() => window.MathJax && MathJax.startup && MathJax.startup.promise")
        page.evaluate("() => MathJax.startup.promise.then(() => MathJax.typesetPromise())")
        return page.evaluate(DRAWN)
    finally:
        context.close()


def test_a_fields_formulas_drawn_by_anki_run_nothing(browser, server):
    # The text merely escaped, as before: Anki's MathJax adds the link and the styles
    unsafe = _drawn(browser, server, html.escape(TEXT).replace("\n", "<br>"))
    assert unsafe["formulas"] == 3 and unsafe["links"] and unsafe["fixed"] and unsafe["own"] == 3, unsafe

    drawn = _drawn(browser, server, field_html(TEXT))
    assert drawn == {"formulas": 3, "links": 0, "fixed": False, "own": 0, "red": True}


# Commands writing CSS of their own in Anki's MathJax (its html extension aside): a box's CSS,
# a token's attributes, a character's font, a frame's colour (given, or defined), an alias
CSS_TEXT = (
    "\\(\\bbox[yellow,5px,border:2px solid red;position:fixed;inset:0]{a}"
    " + \\mmlToken{mi}[style='position:fixed' href='https://example.com' class='flash' id='taken']{b}"
    " + \\unicode[x;position:fixed]{66} + \\unicode{66}"
    " + \\fcolorbox{red;position:fixed}{blue}{c}\\)"
    " \\(\\definecolor{q}{named}{red;position:fixed}\\fcolorbox{q}{blue}{d}\\)"
    " \\(\\let\\b\\bbox{} \\b[position:fixed]{e}\\)"
)


def test_a_fields_formulas_write_no_css_of_their_own_in_anki(browser, server):
    """\\bbox, \\mmlToken, \\unicode, \\fcolorbox: MathJax copies their CSS into the card as
    written (a page covered, a picture fetched at each review); as Notosaurus writes them,
    only a box's colour, padding and border are drawn."""
    unsafe = _drawn(browser, server, html.escape(CSS_TEXT))
    assert unsafe["formulas"] == 3 and unsafe["links"] and unsafe["fixed"] and unsafe["own"] == 2, unsafe

    drawn = _drawn(browser, server, field_html(CSS_TEXT))
    assert drawn["formulas"] == 3 and drawn["links"] == 0 and not drawn["fixed"] and drawn["own"] == 0, drawn
