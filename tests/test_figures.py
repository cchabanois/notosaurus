"""Figures on cards: SVG drawn by the AI, cleaned, saved and sent like the pictures."""

import apkg
import pytest

from app import lessons
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


def test_clean_gives_the_namespace():
    svg = figures.clean('<svg viewBox="0 0 200 100"><circle cx="50" cy="50" r="40"/></svg>')
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"') and "<circle" in svg


def test_figures_drawn_shown_and_exported(client, tmp_path):
    lesson = client.post("/api/extract", data={"prompt": "Le triangle rectangle (géométrie)"}).json()
    assert all(c["figure"] and not c["picture"] for c in lesson["cards"])
    res = client.post(f"/api/lessons/{lesson['id']}/pictures").json()
    assert res["failures"] == 0
    cards = res["lesson"]["cards"]
    assert all(c["picture"].endswith(".svg") for c in cards)

    # Served as an image that can't run anything, even opened on its own
    r = client.get(f"/api/lessons/{lesson['id']}/pictures/{cards[1]['picture']}")
    assert r.headers["content-type"] == "image/svg+xml"
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert "« c »" not in r.text and ">c<" in r.text  # the label from the description

    # In the package: the card with its figure
    body = {"deck": lesson["deck"], "cards": cards, "lesson_id": lesson["id"]}
    package = apkg.export(client, body, tmp_path)
    assert {cards[0]["picture"], cards[1]["picture"]} <= set(package.media_map.values())
    assert any(f'<img src="{cards[0]["picture"]}">' in note[2] for note in package.notes)


def test_redraw_a_figure_from_its_description(client):
    lesson = client.post("/api/extract", data={"prompt": "géométrie"}).json()
    card = lesson["cards"][0]
    url = f"/api/lessons/{lesson['id']}/cards/{card['id']}/picture/draw"
    res = client.post(url, json={"subject": "Un triangle, l'hypoténuse étiquetée « hypoténuse »"}).json()
    assert res["card"]["figure"].startswith("Un triangle") and res["card"]["picture"].endswith(".svg")
    svg = (lessons.folder(lesson["id"]) / "images" / res["card"]["picture"]).read_text(encoding="utf-8")
    assert "hypoténuse" in svg
    # No picture any more: a text card again
    gone = client.delete(f"/api/lessons/{lesson['id']}/cards/{card['id']}/picture").json()["card"]
    assert (gone["figure"], gone["picture"]) == ("", "")


def test_a_figure_with_the_answer_goes_on_the_back(client, tmp_path):
    """ "What is a tangent?": the figure belongs to the answer, it shows with it only."""
    lesson = client.post("/api/extract", data={"prompt": "géométrie"}).json()
    cards = client.post(f"/api/lessons/{lesson['id']}/pictures").json()["lesson"]["cards"]
    tangent = next(c for c in cards if c["picture_on_back"])
    assert tangent["front"].startswith("Qu'est-ce qu'une tangente")
    body = {"deck": lesson["deck"], "cards": cards, "lesson_id": lesson["id"]}
    package = apkg.export(client, body, tmp_path)
    on_back = next(m for m in package.models.values() if m["name"].startswith("Notosaurus image au verso"))
    (template,) = on_back["tmpls"]
    assert "{{Picture}}" not in template["qfmt"] and "{{Picture}}" in template["afmt"]
    assert template["name"] == "Image"  # as on the front: a note moves between them keeping its card


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


def test_draw_decides_a_figure_or_a_picture(client, monkeypatch):
    """“🎨 Draw” on a card with nothing: the AI decides from the card (and what was written,
    any language) a figure or a picture, and describes it."""
    from notosaurus_core import llm
    from notosaurus_core.models import PicturePlan

    asked = []

    async def plan(s, front, back, written="", language="English"):
        asked.append((front, back, written, language))
        if "\\cup" in back:
            return PicturePlan(kind="figure", description="Deux ensembles A et B, leur réunion hachurée")
        return PicturePlan(kind="picture", description="a red apple", search="red apple")

    monkeypatch.setattr(llm, "plan_picture", plan)
    lesson = client.post("/api/extract", data={"prompt": "FR → ES"}).json()
    cards = [{**lesson["cards"][0], "front": "La réunion de A et B ?", "back": r"\(A \cup B\)"}, lesson["cards"][1]]
    client.put(f"/api/lessons/{lesson['id']}", json={**lesson, "cards": cards})
    url = f"/api/lessons/{lesson['id']}/cards/{{}}/picture/draw"
    french = {"X-Notosaurus-Lang": "fr"}

    union = client.post(url.format(cards[0]["id"]), json={"subject": ""}, headers=french).json()["card"]
    assert union["figure"] == "Deux ensembles A et B, leur réunion hachurée" and union["picture"].endswith(".svg")
    assert union["picture_prompt"] == "" and asked[-1] == ("La réunion de A et B ?", r"\(A \cup B\)", "", "French")

    apple = client.post(url.format(cards[1]["id"]), json={"subject": "une pomme rouge"}, headers=french).json()["card"]
    assert (apple["picture_prompt"], apple["picture_search"], apple["figure"]) == ("a red apple", "red apple", "")
    assert asked[-1][2] == "une pomme rouge"

    # A figure's own description changed: that figure redrawn, nothing decided again
    count = len(asked)
    again = client.post(url.format(cards[0]["id"]), json={"subject": "Deux ensembles, rien de hachuré"}).json()["card"]
    assert again["figure"] == "Deux ensembles, rien de hachuré" and len(asked) == count


def test_search_written_in_any_language(client, monkeypatch):
    from notosaurus_core import llm, stock

    async def words(s, written, context=""):
        assert context == "La réunion ? → A ∪ B"
        return "union Venn diagram"

    async def search(subject, pixabay_key=""):
        return []

    monkeypatch.setattr(llm, "search_words", words)
    monkeypatch.setattr(stock, "search", search)
    res = client.post(
        "/api/pictures/search", json={"subject": r"\(A \cup B\)", "context": "La réunion ? → A ∪ B"}
    ).json()
    assert res == {"results": [], "words": "union Venn diagram"}
