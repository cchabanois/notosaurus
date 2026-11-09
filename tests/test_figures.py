"""Figures on cards: SVG drawn by the AI, cleaned, saved and sent like the pictures."""

import asyncio
import io
import json
import math
import re
from xml.etree import ElementTree

import apkg
import pytest
from helpers import plain_image

from app import lessons
from notosaurus_core import figures, figures_typst, llm, pictures
from notosaurus_core.config import AIConfig
from notosaurus_core.errors import AppError

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


def test_figures_drawn_shown_and_exported(client, tmp_path):
    lesson = client.post("/api/extract", data={"prompt": "Le triangle rectangle (géométrie)"}).json()
    assert all(c["figure"] and not c["picture"] for c in lesson["cards"])
    res = client.post(f"/api/lessons/{lesson['id']}/pictures", json={"draw": True}).json()
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


def test_each_cards_steps_told_as_they_begin(client):
    """Asked as a stream: each card's steps (drawn, then its picture ready), then the answer
    as without it. Not checked: the user asks it (check)."""
    lesson = client.post("/api/extract", data={"prompt": "Le triangle rectangle (géométrie)"}).json()
    res = client.post(
        f"/api/lessons/{lesson['id']}/pictures", json={"draw": True}, headers={"Accept": "application/x-ndjson"}
    )
    lines = [json.loads(line) for line in res.text.splitlines()]
    steps = [(line["card"], line["step"]) for line in lines if "step" in line]
    for card in lesson["cards"]:
        assert [s for c, s in steps if c == card["id"]] == ["drawing", "ready"]
    answer = lines[-1]["result"]
    assert answer["failures"] == 0 and all(c["picture"].endswith(".svg") for c in answer["lesson"]["cards"])


def test_redraw_a_figure_from_its_description(client):
    lesson = client.post("/api/extract", data={"prompt": "géométrie"}).json()
    card = lesson["cards"][0]
    url = f"/api/lessons/{lesson['id']}/cards/{card['id']}/picture/make"
    res = client.post(url, json={"subject": "Un triangle, l'hypoténuse étiquetée « hypoténuse »"}).json()
    assert res["card"]["figure"].startswith("Un triangle") and res["card"]["picture"].endswith(".svg")
    svg = (lessons.folder(lesson["id"]) / "images" / res["card"]["picture"]).read_text(encoding="utf-8")
    assert "hypoténuse" in svg
    # Asked as a stream ("✨ Image" again, then drawn again): its steps, then the answer as before
    for path, body in (("make", {"subject": "Un triangle rectangle"}), ("draw", None)):
        streamed = client.post(
            url.replace("/make", f"/{path}"), json=body, headers={"Accept": "application/x-ndjson"}
        ).text.splitlines()
        lines = [json.loads(line) for line in streamed]
        assert [line["step"]["step"] for line in lines if "step" in line] == ["drawing"]
        assert lines[-1]["result"]["card"]["picture"].endswith(".svg")
    # No picture any more: a text card again
    gone = client.delete(f"/api/lessons/{lesson['id']}/cards/{card['id']}/picture").json()["card"]
    assert (gone["figure"], gone["picture"]) == ("", "")


def test_a_figure_with_the_answer_goes_on_the_back(client, tmp_path):
    """ "What is a tangent?": the figure belongs to the answer, it shows with it only."""
    lesson = client.post("/api/extract", data={"prompt": "géométrie"}).json()
    cards = client.post(f"/api/lessons/{lesson['id']}/pictures", json={"draw": True}).json()["lesson"]["cards"]
    tangent = next(c for c in cards if c["picture_on_back"])
    assert tangent["front"].startswith("Qu'est-ce qu'une tangente")
    body = {"deck": lesson["deck"], "cards": cards, "lesson_id": lesson["id"]}
    package = apkg.export(client, body, tmp_path)
    note = next(n for n in package.notes if package.fields_by_name(n)["Front"].startswith("Qu'est-ce qu'une tangente"))
    fields = package.fields_by_name(note)
    assert fields["Picture"] == "" and fields["BackPicture"].startswith("<img")  # with the answer only
    (template,) = package.models[note[1]]["tmpls"]  # a text card, as any: its picture with the answer
    assert "{{BackPicture}}" not in template["qfmt"] and "{{BackPicture}}" in template["afmt"]


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
            return PicturePlan(
                kind="figure", description="Deux ensembles A et B, leur réunion hachurée", figure_kind="sets"
            )
        return PicturePlan(kind="picture", description="a red apple", search="red apple")

    async def draw(s, subject):  # the image model: never a real one here (no key on the CI, a cost elsewhere)
        return plain_image(64, 64, "red", "PNG")

    monkeypatch.setattr(llm, "plan_picture", plan)
    monkeypatch.setattr(pictures, "draw", draw)
    lesson = client.post("/api/extract", data={"prompt": "FR → ES"}).json()
    cards = [{**lesson["cards"][0], "front": "La réunion de A et B ?", "back": r"\(A \cup B\)"}, lesson["cards"][1]]
    client.put(f"/api/lessons/{lesson['id']}", json={**lesson, "cards": cards})
    url = f"/api/lessons/{lesson['id']}/cards/{{}}/picture/make"
    french = {"X-Notosaurus-Lang": "fr"}

    union = client.post(url.format(cards[0]["id"]), json={"subject": ""}, headers=french).json()["card"]
    assert union["figure"] == "Deux ensembles A et B, leur réunion hachurée" and union["picture"].endswith(".svg")
    assert union["picture_prompt"] == "" and asked[-1] == ("La réunion de A et B ?", r"\(A \cup B\)", "", "French")
    assert union["figure_kind"] == "sets"  # kept: its figure drawn again without asking it

    apple = client.post(url.format(cards[1]["id"]), json={"subject": "une pomme rouge"}, headers=french).json()["card"]
    assert (apple["picture_prompt"], apple["picture_search"], apple["figure"]) == ("a red apple", "red apple", "")
    assert asked[-1][2] == "une pomme rouge"

    # A figure's own description changed: that figure redrawn, nothing decided again
    count = len(asked)
    again = client.post(url.format(cards[0]["id"]), json={"subject": "Deux ensembles, rien de hachuré"}).json()["card"]
    assert again["figure"] == "Deux ensembles, rien de hachuré" and len(asked) == count
    assert again["figure_kind"] == ""  # another figure: its kind asked when drawn


def test_search_written_in_any_language(client, monkeypatch):
    from notosaurus_core import llm, stock

    async def words(s, written, context=""):
        assert context == "La réunion ? → A ∪ B"
        return "union Venn diagram"

    async def as_found(s, subject, context="", pixabay_key=""):
        return
        yield

    monkeypatch.setattr(llm, "search_words", words)
    monkeypatch.setattr(stock, "sorted_as_found", as_found)
    res = client.post(
        "/api/pictures/search", json={"subject": r"\(A \cup B\)", "context": "La réunion ? → A ∪ B"}
    ).json()
    assert res == {"results": [], "words": "union Venn diagram"}


SQUARE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">'
    '<rect width="400" height="300" fill="white"/><text x="20" y="40">A</text></svg>'
)


def drawing_with(monkeypatch, light_svg=SQUARE, problem="", careful=False):
    """draw_figure with a fake AI: the light drawing `light_svg` (with thinking: B), what a
    check found (`problem`); the calls made, in order."""
    calls = []

    async def answer(s, images, text, schema, system=None, light=False, **options):
        calls.append({"schema": schema.__name__, "light": light, "text": text, "images": len(images)})
        return schema(svg=light_svg if light else SQUARE.replace(">A<", ">B<"))

    monkeypatch.setattr("notosaurus_core.ai._ask_provider", answer)
    monkeypatch.setattr(figures_typst, "available", lambda: False)  # the circuit, as SVG (Typst: below)
    svg = asyncio.run(llm.draw_figure(AIConfig(llm="gemini"), "un triangle ABC", problem=problem, careful=careful))
    return svg, calls


def test_a_figure_drawn_light_and_not_checked(monkeypatch):
    """Drawn quickly, one call: not checked (the user asks it, check_figure)."""
    svg, calls = drawing_with(monkeypatch)
    assert ">A<" in svg and svg.startswith("<svg") and 'width="400"' in svg  # cleaned
    assert [(c["schema"], c["light"], c["images"]) for c in calls] == [("Drawing", True, 0)]


def test_a_figure_found_wrong_drawn_again_told_why(monkeypatch):
    """Told the problem: quickly first; with the model's thinking when asked (careful)."""
    svg, calls = drawing_with(monkeypatch, problem="The arc is on the wrong side of the line.")
    assert ">A<" in svg and [(c["schema"], c["light"]) for c in calls] == [("Drawing", True)]
    assert "The arc is on the wrong side of the line." in calls[-1]["text"]
    svg, calls = drawing_with(monkeypatch, problem="The arc is on the wrong side of the line.", careful=True)
    assert ">B<" in svg and [(c["schema"], c["light"]) for c in calls] == [("Drawing", False)]
    assert "The arc is on the wrong side of the line." in calls[-1]["text"]


def test_an_unusable_light_figure_drawn_again_with_thinking(monkeypatch):
    svg, calls = drawing_with(monkeypatch, light_svg="no figure")
    assert ">B<" in svg and [c["light"] for c in calls] == [True, False]


def test_typst_turned_off_figures_drawn_as_svg(monkeypatch):
    """The relay's figures.typst switch (AIConfig.typst): no Typst, even with its kind said."""
    monkeypatch.setattr(figures_typst, "available", lambda: True)
    family = lambda s: asyncio.run(llm._figure_family(s, "un triangle ABC", "geometry"))  # noqa: E731
    assert family(AIConfig(llm="gemini")) == "geometry"
    assert family(AIConfig(llm="gemini", typst=False)) == "other"


def test_a_figure_on_the_front_is_told_its_cards_answer(monkeypatch):
    """A figure goes on the front: drawn knowing the card's question and answer, so that it
    writes nothing giving the answer away, even where its description (shared by the cards
    of one chart: "each sector with its count") writes it. On the back: told nothing."""
    from notosaurus_core.models import Card

    told = {}

    async def drawn(s, text, description, family, light):
        told["text"] = text
        return llm.MadeFigure("<svg/>", "svg", family, False)

    monkeypatch.setattr("notosaurus_core.figure_making._drawn", drawn)
    description = "Diagramme circulaire : Bus 20, À pied 10, chaque secteur avec son effectif"
    for on_back in (False, True):
        card = Card(
            front="Combien d'élèves viennent à pied ?",
            back="10",
            figure=description,
            figure_kind="chart",
            picture_on_back=on_back,
        )
        asyncio.run(pictures.card_picture(AIConfig(llm="gemini"), card))
        assert ("Combien d'élèves viennent à pied ? → 10" in told["text"]) != on_back
        assert ("gives this answer away" in told["text"]) != on_back


def test_figures_turned_off_refused():
    """The relay's figures.draw switch (AIConfig.figures): refused before any AI call."""
    with pytest.raises(AppError) as refused:
        asyncio.run(llm.made_figure(AIConfig(llm="gemini", figures=False), "un triangle ABC"))
    assert (refused.value.code, refused.value.params) == ("relay.feature_off", {"feature": "figures.draw"})


def test_a_figure_checked_when_asked(client, monkeypatch):
    """ "🔍 Check": what the AI sees wrong said, nothing changed; drawn again with the problem
    when the user says so, with the model's thinking."""
    lesson = client.post("/api/extract", data={"prompt": "géométrie"}).json()
    lesson = client.post(f"/api/lessons/{lesson['id']}/pictures", json={"draw": True}).json()["lesson"]
    card = lesson["cards"][0]
    url = f"/api/lessons/{lesson['id']}/cards/{card['id']}/picture"
    assert client.post(f"{url}/check").json() == {"ok": True, "problem": ""}  # the demo AI: right
    seen = []

    async def check(s, description, svg):
        seen.append((description, svg[:4]))
        return "The angle is at B."

    monkeypatch.setattr(llm, "check_figure", check)
    assert client.post(f"{url}/check").json() == {"ok": False, "problem": "The angle is at B."}
    assert seen == [(card["figure"], "<svg")]
    asked = []
    real = llm.made_figure

    async def draw(s, description, step=None, kind="", problem="", careful=False, front=""):
        asked.append((problem, careful))
        return await real(s, description, step, kind, problem, careful, front)

    monkeypatch.setattr(llm, "made_figure", draw)
    told = {False: [{"step": "drawing"}], True: [{"step": "redrawing", "problem": "The angle is at B."}]}
    for careful, steps in told.items():  # quickly, told the problem; then with the model's thinking
        body = {"problem": "The angle is at B.", "careful": careful}
        streamed = client.post(f"{url}/draw", json=body, headers={"Accept": "application/x-ndjson"})
        lines = [json.loads(line) for line in streamed.text.splitlines()]
        assert [line["step"] for line in lines if "step" in line] == steps
        assert asked[-1] == ("The angle is at B.", careful)
        assert lines[-1]["result"]["card"]["picture"].endswith(".svg")
    # A card without a figure: nothing to check
    other = client.post("/api/extract", data={"prompt": "FR → ES"}).json()
    assert client.post(f"/api/lessons/{other['id']}/cards/{other['cards'][0]['id']}/picture/check").status_code == 404


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


TRIANGLE = """#ctz-canvas({
  ctz-init()
  ctz-def-points(A: (0, 0), B: (4, 0), C: (2, 3))
  ctz-draw-polygon("A", "B", "C")
  ctz-draw-angle("A", "B", "C", radius: 0.6)
  ctz-draw-labels(A: "below left")
})"""


def typst_drawing(monkeypatch, bodies, kind="", problem="", careful=False):
    """draw_figure with a fake AI writing the Typst `bodies` in turn (then, asked for SVG,
    SQUARE), its `kind` given or not; the calls made, in order."""
    calls, written = [], iter(bodies)

    async def answer(s, images, text, schema, system=None, light=False, **options):
        calls.append({"schema": schema.__name__, "light": light, "text": text})
        if schema is figures_typst.Kind:
            return schema(family="geometry")
        if schema is figures_typst.Figure:
            return schema(typst=next(written))
        return schema(svg=SQUARE)

    monkeypatch.setattr("notosaurus_core.ai._ask_provider", answer)
    description = "un triangle ABC, l'angle en A marqué"
    svg = asyncio.run(llm.draw_figure(AIConfig(llm="gemini"), description, kind=kind, problem=problem, careful=careful))
    return svg, calls


def test_a_figures_source_says_what_drew_it(monkeypatch):
    """Typst and its family's packages, with their versions (credited where the figure
    shows); an SVG figure, none; careful when drawn with the model's thinking."""
    from notosaurus_core.models import Card

    written = iter([TRIANGLE, TRIANGLE])

    async def answer(s, images, text, schema, system=None, light=False, **options):
        return schema(typst=next(written)) if schema is figures_typst.Figure else schema(svg=SQUARE)

    monkeypatch.setattr("notosaurus_core.ai._ask_provider", answer)
    card = Card(front="Ce triangle ?", back="rectangle", figure="un triangle", figure_kind="geometry")
    made = asyncio.run(pictures.card_picture(AIConfig(llm="gemini"), card))
    origin = made.card.picture_source
    assert (origin.engine, origin.careful) == ("typst", False)
    assert origin.made_with[0].startswith("Typst ") and origin.made_with[1] == "ctz-euclide 0.3.0"
    made = asyncio.run(pictures.card_picture(AIConfig(llm="gemini"), card, problem="x", careful=True))
    assert made.card.picture_source.careful
    svg = asyncio.run(pictures.card_picture(AIConfig(llm="gemini"), card.model_copy(update={"figure_kind": "other"})))
    assert (svg.card.picture_source.engine, svg.card.picture_source.made_with) == ("svg", [])


def test_a_figure_drawn_in_typst_compiled_offline():
    """Typst with the packages and the font shipped (nothing downloaded): an SVG, black and
    grey, its letters kept by the cleaning (their shapes, used where they go)."""
    svg = figures.clean(figures_typst.compile_svg("geometry", TRIANGLE))
    assert svg.startswith("<svg") and "<use" in svg and "<symbol" in svg  # the letter A
    assert set(re.findall(r'(?:fill|stroke)="(#[0-9a-f]{6})"', svg)) <= {"#000000", "#e1e1e1", "#ffffff"}
    assert figures.to_png(svg)


def test_typst_packages_unpacked_once_from_their_archives():
    """One archive per package (tools/typst_packages.py), each where Typst looks for it
    (preview/<name>/<version>/typst.toml), unpacked once: drawn again, the same folder."""
    archives = sorted(figures_typst.ARCHIVES.glob("*.tar.gz"))
    assert archives and not (figures_typst.ARCHIVES / "preview").exists()
    folder = figures_typst.packages()
    for archive in archives:
        name, version = archive.name.removesuffix(".tar.gz").rsplit("-", 1)
        assert (folder / "preview" / name / version / "typst.toml").is_file()
    stamp = (folder / "preview").stat().st_mtime_ns
    assert figures_typst.packages() == folder and (folder / "preview").stat().st_mtime_ns == stamp
    assert [p.name for p in folder.parent.iterdir() if p.name.startswith("typst-")] == [folder.name]


def test_typst_asked_again_with_its_error_then_used(monkeypatch):
    svg, calls = typst_drawing(monkeypatch, ["#ctz-canvas({ ctz-init(", TRIANGLE])
    assert "<use" in svg  # Typst's, its letter
    assert [c["schema"] for c in calls] == ["Kind", "Figure", "Figure"]
    assert "Typst said:" in calls[2]["text"] and "ctz-init(" in calls[2]["text"]
    # Refused twice (a file's import, then unclosed): the SVG drawing, as before
    svg, calls = typst_drawing(monkeypatch, ['#import "other.typ"', "#ctz-canvas({"])
    assert ">A<" in svg and [c["schema"] for c in calls] == ["Kind", "Figure", "Figure", "Drawing"]
    assert "no import" in calls[2]["text"]


def test_typst_drawing_nothing_asked_again_then_drawn_as_svg(monkeypatch):
    """An empty answer (a map of what its atlas lacks: the AI leaves it all out) compiles
    to a blank page: refused, asked again, then drawn as SVG, never a blank card."""
    for blank in ("", "#diagram()", "#ctz-canvas({ ctz-init() })"):
        with pytest.raises(figures_typst.Unusable, match="nothing"):
            figures_typst.compile_svg("diagram" if "diagram" in blank else "geometry", blank)
    svg, calls = typst_drawing(monkeypatch, ["", ""])
    assert ">A<" in svg and [c["schema"] for c in calls] == ["Kind", "Figure", "Figure", "Drawing"]
    assert "draws nothing" in calls[2]["text"]


# Rings drawn as nested nodes, each label at its centre (TYP-09h): the inner fills cover
# the outer ones' labels
RINGS = """#diagram(node-stroke: 0.8pt,
  node((0, 0), [Périurbain], shape: circle, fill: luma(245), radius: 3cm),
  node((0, 0), [Banlieue], shape: circle, fill: luma(225), radius: 2cm),
  node((0, 0), [Ville], shape: circle, fill: rgb("#ffe066"), radius: 1cm),
)"""


def rule_example(family):
    """The example a family's rule shows the AI (typst_rules/<family>.typ), as it compiles:
    geometry's "and so on" a triangle drawn, its points alone drawing nothing."""
    typst = (figures_typst.RULES / f"{family}.typ").read_text(encoding="utf-8")
    return typst.split(figures_typst.EXAMPLE)[1].replace("  ...\n", '  ctz-draw-polygon("A", "B", "C")\n')


def test_the_figures_bench_sees_hidden_labels():
    """tools/bench_figures.py: a label under a filled shape drawn after it, or outside the
    picture, counted and the figure judged wrong; seen, not (the rules' examples: none hidden)."""
    import sys

    sys.path.insert(0, str(figures_typst.HERE.parent.parent / "tools"))
    import bench_figures

    def hidden(svg):
        svg = figures.clean(svg)
        return bench_figures.hidden_labels(svg, figures.to_png(svg))

    rings = figures.clean(figures_typst.compile_svg("diagram", RINGS))
    assert hidden(rings) == 2
    assert bench_figures.by_code(rings)[:2] == (False, "2 label(s) hidden (under a shape, or outside the picture)")
    assert hidden(SQUARE) == 0
    assert hidden(SQUARE.replace("</svg>", '<rect width="400" height="300" fill="white"/></svg>')) == 1
    assert hidden(SQUARE.replace("</svg>", '<text x="900" y="40">B</text></svg>')) == 1
    assert hidden(SQUARE.replace(">A<", ' font-size="4">i<')) == 0  # tiny, but seen
    for family in figures_typst.FAMILIES:
        assert hidden(figures_typst.compile_svg(family, rule_example(family))) == 0, family


def test_a_figures_kind_given_is_not_asked_again(monkeypatch):
    """Its kind said with its description (Card.figure_kind): one call fewer. Not one of
    the families (an old or a wrong one): asked."""
    _, calls = typst_drawing(monkeypatch, [TRIANGLE], kind="geometry")
    assert [c["schema"] for c in calls] == ["Figure"]
    _, calls = typst_drawing(monkeypatch, [TRIANGLE], kind="a map")
    assert [c["schema"] for c in calls] == ["Kind", "Figure"]


def test_a_typst_figure_found_wrong_drawn_again_with_thinking(monkeypatch):
    _, calls = typst_drawing(monkeypatch, [TRIANGLE], problem="The angle is at B.", careful=True)
    assert [(c["schema"], c["light"]) for c in calls] == [("Kind", True), ("Figure", False)]
    assert "The angle is at B." in calls[-1]["text"]


def test_typst_cut_when_too_long_and_nothing_loaded(monkeypatch):
    import subprocess

    def slow(*args, **kwargs):
        raise subprocess.TimeoutExpired("typst", figures_typst.COMPILE_S)

    for bad in ('read("/etc/passwd")', 'image("x.png")', 'plugin("p.wasm")', '#include "x.typ"', 'eval("read(1)")'):
        with pytest.raises(figures_typst.Unusable):
            figures_typst.source("geometry", bad)
    monkeypatch.setattr(subprocess, "run", slow)
    with pytest.raises(figures_typst.Unusable, match="too long"):
        figures_typst.compile_svg("geometry", TRIANGLE)


def test_the_figures_colours_kept():
    """A figure keeps its colours: a lesson's colour code (an atom's, a legend's) is what the
    card teaches, never turned black."""
    body = "#cetz.canvas({ import cetz.draw: *\n circle((0, 0), radius: 0.8, fill: red) })"
    svg = figures_typst.compile_svg("chemistry", body)
    assert re.search(r'fill="#ff4136"|fill="#ff0000"', svg), svg[:300]


def test_credited_with_what_its_typst_uses():
    """A figure credits the packages its Typst really calls, not all its family imports: a
    model of balls drawn with cetz under the chemistry family is cetz's, not alchemist's."""
    balls = "#cetz.canvas({ import cetz.draw: *\n circle((0, 0), radius: 0.8, fill: red) })"
    formula = '#skeletize({ fragment("CH_3"); single(); fragment("OH") })'
    assert figures_typst.made_with("chemistry", balls)[1:] == ["cetz 0.5.2"]
    assert figures_typst.made_with("chemistry", formula)[1:] == ["alchemist 0.2.0"]
    assert figures_typst.made_with("geometry", TRIANGLE)[1:] == ["ctz-euclide 0.3.0"]
    assert figures_typst.made_with("graph", "#lq.diagram(lq.plot((0, 1), (0, 1)))")[1:] == ["lilaq 0.6.0"]
    timeline = "#timeline(start: 1914, end: 1918, events: ((1916, [Verdun]),))"  # our function: what it uses
    assert figures_typst.made_with("timeline", timeline)[1:] == ["cetz 0.5.2"]
    assert figures_typst.made_with("clock", "#clock(10, 25)")[1:] == ["cetz 0.5.2"]
    assert figures_typst.made_with("solid", "#cuboid(3, 3, 3)")[1:] == ["cetz 0.5.2"]
    assert figures_typst.made_with("other", balls) == []


def test_nested_zones_are_no_diagram():
    """fletcher writes a node's text at its centre and draws its boxes side by side: zones
    inside one another (rings, layers) drawn with it hide or pile up their labels (TYP-09h)."""
    assert "never shapes inside one another" in figures_typst.KINDS
    assert "zones nested or overlapping" in figures_typst.KINDS.split('"other"')[1]


def test_a_model_of_balls_is_no_chemistry():
    """The chemistry family draws formulas (its package's): a molecular model of coloured
    balls is "other", said to the AI that picks a figure's kind."""
    assert "never a model of balls" in figures_typst.KINDS and "molecular model" in figures_typst.KINDS


def test_a_use_only_of_the_figures_own_shapes():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 10 10">'
        '<symbol id="g"><path d="M0 0L1 1"/></symbol><use xlink:href="#g"/>'
        '<use xlink:href="https://x.example/a.svg#g"/><use href="data:image/svg+xml,x"/></svg>'
    )
    cleaned = figures.clean(svg)
    assert cleaned.count('href="#g"') == 1 and "x.example" not in cleaned and "data:" not in cleaned


@pytest.mark.parametrize("family", sorted(figures_typst.FAMILIES))
def test_each_familys_rule_example_compiles(family):
    """Each family's Typst (typst_rules/<family>.typ: its preamble, then the example the AI
    is shown) compiles as it is, with the packages shipped: a rule out of step with its
    package (a version changed) shows here."""
    assert figures.clean(figures_typst.compile_svg(family, rule_example(family))).startswith("<svg")


def test_a_package_import_dropped_not_refused():
    """The AI imports its family's package again (the preamble gives it): the line dropped, the
    figure compiled at once, no call lost. A file's import or include still refused."""
    typst = (figures_typst.RULES / "graph.typ").read_text(encoding="utf-8")
    example = typst.split(figures_typst.EXAMPLE)[1]
    again = '#import "@preview/lilaq:0.6.0" as lq\n' + example
    assert figures_typst.source("graph", again).count('#import "@preview/lilaq') == 1  # the preamble's
    assert figures.clean(figures_typst.compile_svg("graph", again)).startswith("<svg")
    for refused in ('#import "rules.typ"\n', '#include "x.typ"\n', '#import "/etc/x.typ": *\n'):
        with pytest.raises(figures_typst.Unusable):
            figures_typst.source("graph", refused + example)


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


def test_a_diagrams_two_bars_drawn_as_an_arrow():
    """The AI writes "-||" for an arrow (two bars, which no school diagram asks for): drawn as
    "-|>", the arrow it meant."""
    arrow = '#diagram(node((0, 0), [A]), edge("{}"), node((1, 0), [B]))'
    assert figures_typst.compile_svg("diagram", arrow.format("-||")) == figures_typst.compile_svg(
        "diagram", arrow.format("-|>")
    )


@pytest.mark.parametrize(
    ("written", "meant"),
    [("-|-", "-"), ("-|->", "-|>"), ("<-|-", "<|-"), ("<-|->", "<|-|>"), ("--|--", "--"), ("<|-|>", "<|-|>")],
)
def test_a_diagrams_barred_line_drawn_plain(written, meant):
    """The AI writes a bar across a line ("-|-" between two characters, "-|->" a flowchart's
    "oui"), which no school diagram asks for: drawn as the line it meant, never dashed by
    the bar's removal, its head the filled one as every arrow's; a head's bar ("<|", "|>") kept."""
    link = '#diagram(node((0, 0), [A]), edge("{}"), node((1, 0), [B]))'
    assert figures_typst.compile_svg("diagram", link.format(written)) == figures_typst.compile_svg(
        "diagram", link.format(meant)
    )


def test_a_diagrams_long_text_goes_on_the_next_line():
    """A node's long text, its newlines only spaces in Typst: wrapped, not one line that makes
    the whole diagram tiny; a short one as it was."""
    width = lambda svg: float(re.search(r'width="([\d.]+)', svg).group(1))  # noqa: E731
    text = "Le trésor est retrouvé\ngrâce à Ben Gunn sur l'île, après la mutinerie de Long John Silver"
    long = figures_typst.compile_svg("diagram", f"#diagram(node((0, 0), [{text}]))")
    assert width(long) < 160  # pt: 4.5cm and its stroke and margins
    short = figures_typst.compile_svg("diagram", "#diagram(node((0, 0), [Le trésor]))")
    assert width(short) < 80


def _svg_width(svg: str) -> float:
    return float(re.search(r'width="([\d.]+)', svg).group(1))


def test_a_diagrams_arrow_labels_clear_of_its_boxes():
    """An arrow's label longer than the gap the AI gave its two boxes lay on them: the gap
    widened to the label (its width along a row, beside an arrow going down, and both for a
    slanting one in the middle of a cycle); a short label leaves the gap as given."""
    label = "énergie lumineuse utile"
    alone = _svg_width(figures_typst.compile_svg("diagram", f"#diagram(node((0, 0), [{label}]))"))
    chain = '#diagram(spacing: 1em, node((0, 0), [Pile]), edge("-|>", {}), node((1, 0), [Lampe]))'
    bare = _svg_width(figures_typst.compile_svg("diagram", chain.format("")))
    labelled = _svg_width(figures_typst.compile_svg("diagram", chain.format(f"[{label}]")))
    assert labelled - bare > alone - 20  # pt: the label's width (the node's alone, its inset and stroke)
    wide = chain.replace("1em", "3em")  # wide enough for a short label: as given
    assert _svg_width(figures_typst.compile_svg("diagram", wide.format("[a]"))) == _svg_width(
        figures_typst.compile_svg("diagram", wide.format(""))
    )
    # a cycle: a label beside an arrow going down and one on the slanting arrow, the same gap
    cycle = (
        "#diagram(spacing: 1em, node((0, 0), [A]), node((1, 0), [B]), node((0, 1), [C]),"
        ' edge((0, 1), (0, 0), "-|>", [Évaporation]), edge((1, 0), (0, 1), "-|>", [Ruissellement]))'
    )
    word = _svg_width(figures_typst.compile_svg("diagram", "#diagram(node((0, 0), [Ruissellement]))"))
    assert _svg_width(figures_typst.compile_svg("diagram", cycle)) > 2 * word


@pytest.mark.parametrize(
    ("written", "meant"),
    [(r"[Accord avec\nle sujet]", r"[Accord avec\ le sujet]"), (r"[avant\le verbe]", r"[avant\ le verbe]")],
)
def test_a_diagrams_new_line_written_as_a_strings_drawn(written, meant):
    """The AI writes a node's new line as a string's ("\\n") or glues the "\\" to the next word:
    Typst's markup only escaped the letter ("avecnle sujet"); drawn as the line break meant."""
    node = "#diagram(node((0, 0), {}))"
    assert figures_typst.compile_svg("diagram", node.format(written)) == figures_typst.compile_svg(
        "diagram", node.format(meant)
    )


def test_a_diagrams_strings_and_maths_left_as_written():
    """A string's "\\n" (a new line already), a code's escape and a text's maths untouched."""
    body = r'#diagram(node((0, 0), "A\nB"), edge("-|>", [$\u{3b1}$ et \#1]), node((1, 0), [B]))'
    assert figures_typst.source("diagram", body).endswith(body + "\n")


@pytest.mark.parametrize(
    ("family", "body"),
    [
        (
            "graph",
            "#let xs = lq.linspace(0, 0.25, num: 20)\n"
            "#lq.diagram(width: 6cm, height: 4cm, xlim: (0, 0.26), ylim: (0, 12), lq.plot(xs, xs.map(x => 50 * x)))",
        ),
        ("chart", '#chart(kind: "line", values: ((0, 0.5), (1, 1.5), (2, 2.5)), written: (1,))'),
    ],
)
def test_a_figures_numbers_written_as_its_language_writes_them(family, body):
    """The numbers a preamble writes itself (an axis's, a chart's values): with the decimal
    separator of the language the AI says the figure is in (a comma in French, German…), a
    point in English and when it says none, never one for every language."""
    said = lambda lang: f'#set text(lang: "{lang}")\n{body}'  # noqa: E731
    assert '#let decimal-separator = ","' in figures_typst.source(family, said("fr"))
    assert '#let decimal-separator = "."' in figures_typst.source(family, said("en"))
    french, german = (figures_typst.compile_svg(family, said(lang)) for lang in ("fr", "de"))
    english, unsaid = figures_typst.compile_svg(family, said("en")), figures_typst.compile_svg(family, body)
    assert french == german != english == unsaid


def test_a_decimal_comma_in_maths_drawn_tight():
    """Typst's maths spaces a comma out ("0, 3"): a decimal one quoted, tight; LaTeX's `0{,}3`
    (the AI writing LaTeX) whatever the language, a comma between digits only in a language
    writing a decimal comma (an English list "1,2" left as written)."""
    body = '#diagram(node((0, 0), [A]), edge("-", [$0{,}3$ et $0,7$]), node((1, 0), [B]))'
    french = figures_typst.source("diagram", '#set text(lang: "fr")\n' + body)
    english = figures_typst.source("diagram", '#set text(lang: "en")\n' + body)
    assert '$0","3$ et $0","7$' in french
    assert '$0","3$ et $0,7$' in english
    # a number the AI quoted itself (`$times "1,5"$`): text already, left whole, never cut in
    # two strings drawn "1, 5"
    quoted = figures_typst.source("diagram", '#set text(lang: "fr")\n' + body.replace("0,7", 'times "1,5"'))
    assert '$times "1,5"$' in quoted


def test_an_arrow_written_with_html_entities_drawn():
    """The AI writes an arrow's ">" as HTML does ("-|&gt;"): Typst refused it twice, the
    figure drawn as SVG instead; read as ">" (Typst has no such entity)."""
    body = '#diagram(node((0, 0), [A]), edge("-|&gt;"), node((1, 0), [B]), edge("&lt;|-"), node((2, 0), [C]))'
    assert figures_typst.compile_svg("diagram", body).startswith("<svg")


def test_a_drawing_past_its_page_kept_whole():
    """A graph's axis names, written by lilaq past the diagram's ends: the page grown to them
    ("temps (min)", not "te"); a figure within its page the same as Typst made it."""
    body = (
        "#lq.diagram(width: 6cm, height: 4cm, xlim: (0, 15), ylim: (-10, 25),\n"
        "  xaxis: (position: 0, label: [temps (min)]), yaxis: (position: 0, label: [température (°C)]),\n"
        "  lq.plot((0, 4, 10, 14), (20, 0, 0, -10), mark: none))"
    )
    width = float(re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+)', figures_typst.compile_svg("graph", body)).group(1))
    assert width > 6 * 28.35 + 12 + 40  # the diagram, its margins, and "temps (min)" past its end
    cuboid = figures_typst.compile_svg("solid", "#cuboid(5, 3, 2)")
    assert "<rect" not in cuboid.split(">", 1)[1][:200]  # within its page: no ground of ours


def test_each_familys_rule_and_typst_in_their_files():
    """A rule says where its example goes ({example}, once), its Typst where the AI's part
    starts (EXAMPLE, once); the example is in the rule the AI is given."""
    for family, made in figures_typst.FAMILIES.items():
        rule = (figures_typst.RULES / f"{family}.md").read_text(encoding="utf-8")
        typst = (figures_typst.RULES / f"{family}.typ").read_text(encoding="utf-8")
        assert rule.count("{example}") == 1 and typst.count(figures_typst.EXAMPLE) == 1, family
        assert typst.split(figures_typst.EXAMPLE)[1].strip() in made.rules and "{example}" not in made.rules


def test_a_map_finds_its_places_by_any_name():
    """A country by its name in any of the page's languages, or its code: the same map; a city
    as the lesson writes it ("Séville", "Seville"): the same dot."""
    maps = {
        figures_typst.compile_svg("map", f'#map(countries: ("{country}",), cities: ("{city}",), labels: false)')
        for country, city in (("Espagne", "Séville"), ("Spain", "Seville"), ("ESP", "SEVILLE"))
    }
    assert len(maps) == 1


@pytest.mark.parametrize(
    ("code", "names"),
    [
        ("CHN", ("Chine", "China", "Cina")),  # Natural Earth's French one: "République populaire de Chine"
        ("USA", ("United States", "Stati Uniti", "EUA", "USA", "EE. UU.")),
        ("CZE", ("République tchèque", "Tschechische Republik", "Cechia", "Tchéquia")),
        ("VNM", ("Vietnã", "Vietnam")),
        ("IRN", ("Irã", "Iran")),
        ("SAU", ("Arabia Saudí", "Arabie saoudite")),
    ],
)
def test_a_country_by_its_usual_name_in_every_language(code, names):
    """A country by the name a lesson gives it in any of the page's languages (CLDR's usual
    ones): the same map as by its code ("Chine" was refused, "China" found)."""
    maps = {figures_typst.compile_svg("map", f'#map(countries: ("{name}",))') for name in (code, *names)}
    assert len(maps) == 1


@pytest.mark.parametrize(
    ("today", "former"),
    [
        (None, ("Constantinople", "Konstantinopel", "Costantinopoli", "Constantinopla")),  # its old town
        (None, ("Lutèce", "Lutetia", "Lutezia", "Lutécia")),
        ("Saint-Pétersbourg", ("Leningrad", "Léningrad", "Petrograd", "Leningrado")),
        ("Volgograd", ("Stalingrad", "Stalingrado")),
        ("Pékin", ("Peking", "Pequim", "Pechino")),
    ],
)
def test_a_city_by_a_former_name(today, former):
    """A city as a history lesson names it, by its name of then in any of the page's languages:
    one dot whatever the language, today's city's when it is only renamed (Leningrad), the old
    town's when it is a place of its own (Constantinople, Lutèce: Wikidata's)."""
    dot = lambda name: figures_typst.compile_svg("map", f'#map(cities: ("{name}",), labels: false)')  # noqa: E731
    dots = {dot(name) for name in former}
    assert len(dots) == 1 and (today is None or dots == {dot(today)})


def test_the_places_of_history_lessons_found():
    """Places of history lessons Natural Earth lacks (Aix-la-Chapelle, Cordoue, Troie, Verdun,
    Austerlitz, Ðiện Biên Phủ…), by their names in the page's languages."""
    for name in (
        "Aix-la-Chapelle",
        "Aquisgrán",
        "Aachen",
        "Cordoue",
        "Córdoba",
        "Troie",
        "Troy",
        "Verdun",
        "Austerlitz",
        "Diên Biên Phu",
        "La Mecque",
        "Mekka",
        "Tenochtitlan",
        "Wittenberg",
        "Canterbury",
    ):
        assert figures_typst.compile_svg("map", f'#map(cities: ("{name}",))').startswith("<svg"), name


def test_a_place_of_history_before_its_namesakes():
    """Two places of one name: a lesson's map with no country chooses the place of history
    (Cordoue in Spain, not Argentina's Córdoba; Waterloo in Belgium), a map of a country its
    own (Argentina's)."""
    dot = lambda body: figures_typst.compile_svg("map", body)  # noqa: E731
    assert dot('#map(cities: ("Cordoue",), labels: false)') == dot('#map(cities: ("Córdoba",), labels: false)')
    assert dot('#map(countries: ("Espagne",), cities: ("Córdoba",), labels: false)') == dot(
        '#map(countries: ("Espagne",), cities: ("Cordoue",), labels: false)'
    )
    argentina = dot('#map(countries: ("Argentine",), cities: ("Córdoba",), labels: false)')
    assert argentina != dot('#map(countries: ("Argentine",), cities: ("Cordoue",), labels: false)')
    assert dot('#map(countries: ("Belgique",), cities: ("Waterloo",), labels: false)') == dot(
        '#map(countries: ("Belgique",), cities: ("Waterloo",), labels: false)'
    )


@pytest.mark.parametrize(
    ("long", "short"),
    [
        ("mer Méditerranée", ("Méditerranée", "Mediterranean", "Mediterraneo", "Mediterrâneo")),
        ("Atlantic Ocean", ("Atlantique", "Atlantic", "Atlantik", "Atlántico", "Atlantico", "Atlântico")),
        ("Adriatic Sea", ("Adriatique", "Adria")),
        ("Caribbean Sea", ("Caraïbes", "Karibik", "mar do Caribe", "mar dei Caraibi")),
        ("English Channel", ("Manche", "Manica", "Ärmelkanal")),
    ],
)
def test_a_sea_by_its_short_name(long, short):
    """A sea or an ocean as a lesson writes it, short, in any of the page's languages
    ("Méditerranée" was refused, "mer Méditerranée" found): the same map."""
    maps = {figures_typst.compile_svg("map", f'#map(waters: ("{name}",), labels: false)') for name in (long, *short)}
    assert len(maps) == 1


def test_a_place_the_atlas_lacks_said_never_guessed():
    """A city the atlas doesn't have (not a capital nor among its country's largest): the
    figure stops, saying so, for the AI to leave it out; never a dot placed by guess."""
    with pytest.raises(figures_typst.Unusable, match=r"no city called .Trifouilly."):
        figures_typst.compile_svg("map", '#map(countries: ("France",), cities: ("Trifouilly",))')
    with pytest.raises(figures_typst.Unusable, match=r"no country called .Atlantide."):
        figures_typst.compile_svg("map", '#map(countries: ("Atlantide",))')


def test_a_map_stays_light():
    """Only what the frame shows is drawn (the countries cut to it, a point the eye wouldn't
    see skipped), its numbers to the tenth: well within a figure's size, Russia included."""
    for country in ("France", "United States of America", "Russia"):
        svg = figures.clean(figures_typst.compile_svg("map", f'#map(countries: ("{country}",))'))
        assert len(svg) < figures.MAX_SIZE / 2, country


def test_a_map_finds_rivers_reliefs_waters_and_regions_by_any_name():
    """A river, a relief, a water and a region by their names in the page's languages (the
    rivers Natural Earth names in English only too: "Rhin"), drawn the same."""
    cases = {
        "rivers": ("Rhin", "Rhine", "Rhein"),
        "reliefs": ("Alpes", "Alps", "Alpi"),
        "waters": ("Manche", "English Channel"),
        "regions": ("Californie", "California"),
    }
    for layer, written in cases.items():
        country = "États-Unis" if layer == "regions" else "France"
        maps = {
            figures_typst.compile_svg("map", f'#map(countries: ("{country}",), {layer}: ("{w}",), labels: false)')
            for w in written
        }
        assert len(maps) == 1, layer


def test_a_map_frames_what_it_is_asked_and_names_it():
    """Without a country, a river is the map (the Danube, Germany to the Black Sea); a sea
    beside the countries framed is named in the frame (the Atlantic beside France)."""
    danube = figures_typst.compile_svg("map", '#map(rivers: ("Danube",))')
    france = figures_typst.compile_svg("map", '#map(countries: ("France",))')
    assert danube != france
    with_sea = figures_typst.compile_svg("map", '#map(countries: ("France",), waters: ("océan Atlantique",))')
    assert len(re.findall(r"<use|<path", with_sea)) > len(re.findall(r"<use|<path", france))  # its name's glyphs


def test_a_region_needs_its_country_and_a_name_the_atlas_has():
    with pytest.raises(figures_typst.Unusable, match=r"put it in countries"):
        figures_typst.compile_svg("map", '#map(regions: ("Bretagne",))')
    with pytest.raises(figures_typst.Unusable, match=r"no region called .Atlantis."):
        figures_typst.compile_svg("map", '#map(countries: ("France",), regions: ("Atlantis",))')
    with pytest.raises(figures_typst.Unusable, match=r"no river called .Trifouille."):
        figures_typst.compile_svg("map", '#map(countries: ("France",), rivers: ("Trifouille",))')


def test_a_region_too_small_to_see_is_circled():
    """Rhode Island, or Hawaii's islands beside the whole United States: a circle around it
    (its colour alone wouldn't show); Texas, seen, has none."""
    for state, circled in (("Rhode Island", True), ("Hawaï", True), ("Texas", False)):
        svg = figures_typst.compile_svg("map", f'#map(countries: ("USA",), regions: ("{state}",), labels: false)')
        assert ("#d9822b" in svg) == circled, state


def test_a_map_with_everything_stays_within_a_figures_size():
    """Rivers, reliefs, waters and regions drawn as the countries are (cut to the frame, thinned):
    a full map of France, or the world's oceans, within a figure's size."""
    for body in (
        '#map(countries: ("France",), regions: ("Bretagne", "Occitanie"), rivers: ("Loire", "Seine", "Rhône"), '
        'reliefs: ("Alpes", "Pyrénées"), waters: ("Manche", "mer Méditerranée"), cities: ("Paris", "Lyon"))',
        '#map(waters: ("océan Pacifique", "océan Atlantique", "océan Indien"))',
    ):
        assert len(figures.clean(figures_typst.compile_svg("map", body))) < figures.MAX_SIZE, body


def test_the_atlas_folds_names_as_typst_does():
    """tools/atlas.py and the map function fold a name the same way (one table of marked
    letters, in the atlas): a city found with its marks and ligatures, or without."""
    for written, plain in (("Łódź", "Lodz"), ("Saint-Pétersbourg", "saint petersbourg"), ("Kraków", "KRAKOW")):
        country = "Russie" if written.startswith("Saint") else "Pologne"
        a, b = (
            figures_typst.compile_svg("map", f'#map(countries: ("{country}",), cities: ("{w}",), labels: false)')
            for w in (written, plain)
        )
        assert a == b, written


def test_the_places_of_history_kept_as_listed():
    """tools/atlas-history.json (what Wikidata gave, kept: the same atlas whatever day it is
    made) holds tools/atlas.py's HISTORY, in its order: a place added or removed without
    --refresh-history shows here, not at the next build."""
    import sys

    sys.path.insert(0, str(figures_typst.HERE.parent.parent / "tools"))
    import atlas

    kept = json.loads(atlas.HISTORY_FILE.read_text(encoding="utf-8"))
    assert [p["title"] for p in kept] == [title for title, _ in atlas.HISTORY]
    assert all(p["n"] and len(p["xy"]) == 2 for p in kept)


def test_a_coordinate_frame_as_the_graph_rule_writes_it():
    """Points in a coordinate frame (reading or placing coordinates), each call as the graph
    rule gives it: drawn, its grid with it (a line per unit: more lines than without it)."""
    lines = figures_typst.FAMILIES["graph"].rules.splitlines()
    rule = next(line for line in lines if line.startswith("- a coordinate frame"))
    calls = re.findall(r"`((?:#show: lq\.set-grid|lq\.scatter|lq\.place)[^`]*)`", rule)
    assert len(calls) == 4, calls  # the grid, a point, its name, the origin's
    grid, point, name, origin = calls
    axes = "xlim: (-4.5, 4.5), ylim: (-4.5, 4.5), xaxis: (tick-distance: 1, subticks: none), yaxis: (tick-distance: 1)"
    frame = f"#lq.diagram(width: 6cm, height: 6cm, {axes}, {point}, {name}, {origin})"
    with_grid = figures_typst.compile_svg("graph", f"{grid}\n{frame}")
    without = figures_typst.compile_svg("graph", frame)
    assert with_grid.count("<path") > without.count("<path") + 10


def test_the_graph_rules_example_is_orthonormal():
    """The graph rule asks for an orthonormal frame, width / height = xlim's length / ylim's,
    exactly: its example does so (the model copies the example before it reads the rule)."""
    typst = (figures_typst.RULES / "graph.typ").read_text(encoding="utf-8")
    width, height = (float(n) for n in re.search(r"width: ([\d.]+)cm, height: ([\d.]+)cm", typst).groups())
    x0, x1, y0, y1 = (
        float(n) for n in re.search(r"xlim: \(([-\d.]+), ([-\d.]+)\), ylim: \(([-\d.]+), ([-\d.]+)\)", typst).groups()
    )
    assert width / height == pytest.approx((x1 - x0) / (y1 - y0))


def test_the_graph_rules_own_fragments_compile():
    """What the graph rule shows besides its example (the axis's ticks, points, a line)
    compiles too, in that example: a fragment out of step makes every graph with it fail."""
    rules = figures_typst.FAMILIES["graph"].rules
    example = re.search(r"exactly so:\n(.*?)\n- ", rules, re.S).group(1)
    fragments = re.findall(r"`((?:xaxis: |lq\.scatter|lq\.line|lq\.place)[^`]*)`", rules)
    assert len(fragments) >= 4
    for fragment in fragments:
        body = example.replace("  lq.plot(", f"  {fragment},\n  lq.plot(")
        assert figures_typst.compile_svg("graph", body).startswith("<svg"), fragment


def test_a_graphs_surface_filled_as_the_rule_says():
    """An area (an integral, between two curves, under a density): the AI invented its own
    filling (`lq.area-between`, `lq.polygon`, `lq.area`), refused twice, the figure drawn as
    SVG by eye 8 times in 8. The rule's calls compile and fill between the bounds, computed
    from the functions; the name placed inside, at the surface's centre."""
    rules = figures_typst.FAMILIES["graph"].rules
    example = re.search(r"exactly so:\n(.*?)\n- ", rules, re.S).group(1)
    calls = re.findall(r"`(area(?:-name)?\([^`]*\))`", rules)
    assert len(calls) == 3
    for call in calls:
        body = example.replace("  lq.plot(", f"  {call},\n  lq.plot(")
        assert figures_typst.compile_svg("graph", body).startswith("<svg"), call
    square = "#lq.diagram(xlim: (-1, 3), ylim: (-1, 5), {})"
    xs = "lq.linspace(0, 2, num: 200)"
    ours = figures_typst.compile_svg("graph", square.format("area(x => x * x, 0, 2, fill: red)"))
    lilaqs = f"lq.fill-between({xs}, {xs}.map(x => x * x), y2: {xs}.map(x => 0), fill: red)"
    assert ours == figures_typst.compile_svg("graph", square.format(lilaqs))
    named = figures_typst.compile_svg("graph", square.format("area-name(x => x * x, 0, 2, [A])"))
    # its centre: x = ∫x·x² / ∫x², y = ∫x⁴/2 / ∫x²
    centre = "lq.place(1.5, 1.2, box(fill: white, inset: 0.15em, radius: 2pt)[A], align: center + horizon)"
    there, meant = _glyphs(named), _glyphs(figures_typst.compile_svg("graph", square.format(centre)))
    assert len(there) == len(meant)
    assert all(a == pytest.approx(b, abs=0.5) for a, b in zip(sorted(there), sorted(meant), strict=True))  # pt


def test_a_number_lines_points_and_numbers_placed_from_their_values():
    """A number line draws its points and its numbers from their values (the AI put A at its
    value as a coordinate, -3, on a line starting at -5: off the line, B on the wrong tick):
    a point is placed from the line's first value, a point off the line is refused, the
    numbers the description writes are written with the language's comma."""
    draw = "#ctz-canvas({{ ctz-init(); ctz-draw-number-line({}) }})"
    line = lambda args: figures_typst.compile_svg("geometry", draw.format(args))  # noqa: E731
    assert line("-5, 5, numbers: false, points: (A: -3)") == line("0, 10, numbers: false, points: (A: 2)")
    assert line("-5, 5, points: (A: -3)") != line("-5, 5, points: (A: 2)")
    with pytest.raises(figures_typst.Unusable, match="outside the line"):
        line("-5, 5, points: (A: 7)")
    # a fraction's value as a division, its letter written; its value as a name refused
    assert line("0, 2, step: 0.25, points: (B: 3/4)") == line("0, 2, step: 0.25, points: (B: 0.75)")
    with pytest.raises(figures_typst.Unusable, match="never its value written as its name"):
        line("0, 2, step: 0.25, points: (B: (3/4, $3/4$))")
    decimals = draw.format("2.3, 2.4, step: 0.01, scale: 100, numbers: (2.3, 2.4), points: (F: 2.35)")
    french, english = (
        figures_typst.compile_svg("geometry", f'#set text(lang: "{lang}")\n{decimals}') for lang in ("fr", "en")
    )
    assert french != english


def test_the_geometry_rules_number_lines_compile():
    """Every number line the geometry rule shows compiles in a canvas, as the AI copies them."""
    rules = figures_typst.FAMILIES["geometry"].rules
    rule = next(line for line in rules.splitlines() if line.startswith("- a number line"))
    calls = re.findall(r"`(ctz-draw-number-line\([^`]*\))`", rule)
    assert calls
    for call in calls:
        assert figures_typst.compile_svg("geometry", f"#ctz-canvas({{ ctz-init(); {call} }})").startswith("<svg")


def test_the_circuit_rules_current_arrow_compiles():
    """The current's arrow the circuit rule shows (said by where the current goes, whatever way
    a component was drawn: the AI's own, from components' `i:`, went up a branch 2 times in 3),
    in the rule's example."""
    rules = figures_typst.FAMILIES["circuit"].rules
    (arrow,) = re.findall(r"`(current-arrow\([^`]*\))`", rules)
    example = re.search(r"exactly so:\n(.*?)\n- ", rules, re.S).group(1)
    body = example.replace("\n})", f"\n  {arrow}\n}})")
    assert arrow in body and figures.clean(figures_typst.compile_svg("circuit", body)).startswith("<svg")


def test_an_intervals_brackets_turned_by_its_bounds():
    """An interval on a number line: its brackets drawn by the preamble from whether each bound
    is closed, open or infinite (by hand, the AI turned one the wrong way half the time)."""
    draw = "#ctz-canvas({{ ctz-init(); ctz-draw-interval({}, first: -3, last: 5) }})"
    shapes = {
        closed: figures_typst.compile_svg("geometry", draw.format(f"-1, 3, closed: {closed}"))
        for closed in ("(true, true)", "(true, false)", "(false, true)", "(false, false)")
    }
    assert len(set(shapes.values())) == 4  # each bound's bracket turned its own way
    figures_typst.compile_svg("geometry", draw.format("2, none, closed: (true, false)"))  # [2 ; +∞[
    figures_typst.compile_svg("geometry", draw.format("none, 1"))  # ]−∞ ; 1]
    # the line drawn by the preamble too: its ticks where the interval's bounds are placed
    line = "#ctz-canvas({ ctz-init(); ctz-draw-number-line(-2, 6, scale: 0.8, arrow: true) })"
    assert figures_typst.compile_svg("geometry", line).startswith("<svg")


def test_the_trigonometric_circles_points_placed_by_their_angles():
    """The trigonometric circle drawn by the preamble from the angles' values (by eye, the AI
    placed them wrongly and wrote its points' names, "Ppi_2"): an angle changed, the drawing
    changes; the names given are the only ones written."""
    draw = (
        "#ctz-canvas({{ ctz-init();"
        " ctz-draw-unit-circle(angles: (({}, $pi/3$),), project: ({}, $1/2$, $sqrt(3)/2$)) }})"
    )
    sixty = figures_typst.compile_svg("geometry", draw.format(60, 60))
    assert sixty != figures_typst.compile_svg("geometry", draw.format(45, 45))
    assert figures_typst.compile_svg("geometry", draw.format(90, 150)).startswith("<svg")  # on an axis, past it


def test_nested_sets_elements_each_in_its_own_ring():
    """Sets inside one another (ℕ ⊂ ℤ ⊂ … ⊂ ℝ), drawn by the AI by eye: −5 in ℕ, 0,25 in ℤ.
    Laid out by the preamble: each text (its middle) inside its set's ellipse and outside the
    next smaller one, checked by Typst itself (an assert failing, the figure isn't made)."""
    check = """#context {
      let inside(s, p) = { let (cy, a, b) = s; calc.pow(p.at(0) / a, 2) + calc.pow((p.at(1) - cy) / b, 2) < 1 }
      let (shapes, placed) = _nested-layout(LEVELS)
      for (k, p, c) in placed {
        assert(inside(shapes.at(k), p), message: "outside its set")
        if k > 0 { assert(not inside(shapes.at(k - 1), p), message: "inside a smaller set") }
      }
      nested-sets(..LEVELS)
    }"""
    levels = (
        "(([N], ([3],)), ([Z], ([-5],)), ([D], ([0,25],)), ([Q], ([1/3],)),"
        " ([R], ([racine de 2], [pi], [un nombre long])))"
    )
    assert figures_typst.compile_svg("sets", check.replace("LEVELS", levels)).startswith("<svg")


def test_a_graphs_axes_never_written_with_a_factor():
    """Large values: lilaq wrote "× 10⁵" at the axis's end, on the axis's name ("Ec (J)"). The
    ticks written in full, whatever the AI gives its axis (its own `yaxis`, its position)."""
    graph = (
        "#lq.diagram(width: 8cm, height: 5cm, xlim: (0, 30), ylim: (0, 450000), {}"
        " xlabel: [v (m/s)], ylabel: [Ec (J)], lq.plot((0, 30), (0, 450000), mark: none))"
    )
    own = figures_typst.compile_svg("graph", graph.format("yaxis: (position: 0),"))
    whole = figures_typst.compile_svg("graph", graph.format("yaxis: (position: 0, exponent: none),"))
    assert own == whole
    assert figures_typst.compile_svg("graph", graph.format("")) == figures_typst.compile_svg(
        "graph", graph.format("yaxis: (exponent: none), xaxis: (exponent: none),")
    )


def _glyphs(svg: str) -> list[tuple[float, float]]:
    """Where each text run of a Typst SVG is drawn (x, its baseline's y), its groups' moves added."""
    stack, glyphs = [(0.0, 0.0)], []
    for tag in re.findall(r"<g(?:\s[^>]*)?>|</g>", svg):
        if tag == "</g>":
            stack.pop()
            continue
        x, y = stack[-1]
        if moved := re.search(r'transform="translate\(([-\d.]+)(?:[ ,]([-\d.]+))?\)"', tag):
            x, y = x + float(moved[1]), y + float(moved[2] or 0)
        elif text := re.search(r'transform="matrix\(1 0 0 -1 ([-\d.]+) ([-\d.]+)\)"', tag):
            x, y = x + float(text[1]), y + float(text[2])
            glyphs.append((x, y))
        stack.append((x, y))
    return glyphs


def test_a_graphs_x_axis_name_clear_of_its_last_number():
    """The x axis's name, set by the theme below the axis's end, touched the last tick's number
    ("0,25" against "I (A)"): placed past the arrow, a little apart, it starts well after it."""
    svg = figures_typst.compile_svg(
        "graph",
        "#lq.diagram(width: 6cm, height: 4cm, xlim: (0, 0.26), ylim: (0, 12), xlabel: [I (A)],"
        " lq.plot((0, 0.25), (0, 12.5), mark: none))",
    )
    glyphs = sorted(_glyphs(svg))
    name, numbers = glyphs[-1], glyphs[:-1]
    row = max({y for _, y in numbers}, key=lambda y: sum(g[1] == y for g in numbers))  # the tick numbers' row
    last = max(x for x, y in numbers if y == row)  # the last number's last glyph
    assert name[0] - last > 9  # pt: a digit's width and a gap, at least


def test_a_graphs_close_ticks_names_kept_apart():
    """Ticks the AI names whose values are close ("a = 1" against α, u₂ against u₃: written
    one on the other): the one that would touch goes on a second row, computed; names far
    apart stay on one row."""
    graph = (
        "#lq.diagram(width: 6cm, height: 4cm, xlim: (0, 2), ylim: (0, 1),"
        " xaxis: (ticks: ((1, [aaa]), ({}, [bbb]))), lq.plot((0, 2), (0, 1), mark: none))"
    )

    def rows(second: float) -> int:
        glyphs = _glyphs(figures_typst.compile_svg("graph", graph.format(second)))
        below = max(y for _, y in glyphs) - 20  # the x axis's names, under it
        return len({y for x, y in glyphs if x > 20 and y < below})

    assert rows(1.1) == 2
    assert rows(1.8) == 1


@pytest.mark.parametrize("name", ["lambda", "pi", "Delta"])
def test_a_variable_named_like_a_symbol_leaves_the_symbol_in_formulas(name):
    """`#let lambda = 1.5`, then `$lambda$` for the arrow's name: Typst read the variable,
    "1.5" written where λ was meant (a wavelength). The variable renamed where code reads it:
    the formula's name is the symbol again; `#lambda` in it, and the code, keep its value."""
    with_variable = f"#let {name} = 1.5\n$x = {name}$ #box(width: {name} * 1cm)"
    meant = f"#let other = 1.5\n$x = {name}$ #box(width: other * 1cm)"
    assert figures_typst.compile_svg("graph", with_variable) == figures_typst.compile_svg("graph", meant)
    value = f"#let {name} = 1.5\n$#{name}$"
    assert figures_typst.compile_svg("graph", value) == figures_typst.compile_svg("graph", "$1.5$")
    # a word in a text, a field (calc.pi) and a longer name untouched
    text = f"#let {name} = 1\n#text[le mot {name}] #calc.pi #let {name}-max = 2"
    assert f"le mot {name}]" in figures_typst.source("graph", text) and "calc.pi" in figures_typst.source("graph", text)


def test_a_grids_fractional_columns_sized_by_their_content():
    """Four molecules in a grid of `1fr` columns: a figure's page is as wide as what it holds,
    so the columns had no width, the molecules drawn one on another. Sized by their content:
    the same figure as `auto` columns; a fraction elsewhere (`h(1fr)`) left as written."""
    molecule = '[#skeletize({{ fragment("CH_3"); single(); fragment("{}") }}) \\ {}]'
    cells = ", ".join(molecule.format(g, n) for g, n in (("OH", "Éthanol"), ("CHO", "Éthanal")))
    grid = "#grid(columns: COLUMNS, column-gutter: 2em, " + cells + ")"
    fractions = figures_typst.compile_svg("chemistry", grid.replace("COLUMNS", "(1fr, 1fr)"))
    assert fractions == figures_typst.compile_svg("chemistry", grid.replace("COLUMNS", "(auto, auto)"))
    assert "#h(1fr)" in figures_typst.source("chemistry", "#h(1fr)")


def test_a_length_written_beside_its_segment_never_on_it():
    """Lengths were written on their segment's line ("4 cm" cut by the side), and a segment
    holding a labelled one got another's length instead of its own (AB = 5 cm written MB =
    3 cm). Drawn by the preamble: beside the segment, away from the figure; [AB] around [AM]
    on a dimension line past [AM]'s label; a point at AM/AB of [AB], computed."""
    figure = """#ctz-canvas({{
      ctz-init()
      ctz-def-points(A: (0, 3.5), B: (-2.5, 0), C: (3.5, 0))
      ctz-def-linear("M", "A", "B", 2/5)
      ctz-draw-polygon("A", "B", "C")
      {}
    }})"""
    svg = figures_typst.compile_svg
    bare = svg("geometry", figure.format(""))
    # its label leaves the segment's line as it is: written beside it, the line not crossed
    one = svg("geometry", figure.format('ctz-draw-length("A", "M", [2 cm], away: "C")'))
    assert one != bare
    both = figure.format(
        'ctz-draw-length("A", "M", [2 cm], away: "C"); ctz-draw-length("A", "B", [5 cm], away: "C", level: 2)'
    )
    assert svg("geometry", both).startswith("<svg")
    # the dimension line: farther from [AB] than [AM]'s label reaches, whatever the label
    longer = both.replace("[2 cm]", "[2,25 cm]")
    assert svg("geometry", longer) != svg("geometry", both)
    assert "ctz-draw-length" in figures_typst.FAMILIES["geometry"].rules


def test_where_two_curves_meet_computed_and_marked():
    """Two lines' intersection the description asks for, marked by the AI with a dot too
    small to see and its coordinates left out: computed by the preamble (Typst itself
    checks the points), its dot, its dotted lines and its coordinates all drawn."""
    check = """#{
      let near(p, q) = calc.abs(p.at(0) - q.at(0)) < 1e-6 and calc.abs(p.at(1) - q.at(1)) < 1e-6
      let lines = _meet-points(x => 2 * x - 1, x => -x + 2, -1, 3)
      assert(lines.len() == 1 and near(lines.at(0), (1, 1)), message: repr(lines))
      let curve = _meet-points(x => calc.pow(x, 2) - 1, x => x + 1, -1.5, 3)
      assert(curve.len() == 2 and near(curve.at(0), (-1, 0)) and near(curve.at(1), (2, 3)), message: repr(curve))
      [checked]
    }"""
    assert figures_typst.compile_svg("graph", check).startswith("<svg")
    drawn = (
        '#set text(lang: "fr")\n#lq.diagram(xlim: (-1, 3), ylim: (-2, 4), meet(x => 2 * x - 1, x => -x + 2, -1, 3{}))'
    )
    svg = lambda options: figures_typst.compile_svg("graph", drawn.format(options))  # noqa: E731
    # each part kept (a diagram's elements are dictionaries: several merged into the last)
    assert len({svg(""), svg(", lines: true"), svg(", label: auto"), svg(", lines: true, label: auto")}) == 4
    assert "meet(" in figures_typst.FAMILIES["graph"].rules


@pytest.mark.parametrize(
    ("shape", "parts", "coloured"),
    [('kind: "disc"', 4, 3), ('kind: "disc"', 12, 7), ('kind: "bar"', 5, 2), ('kind: "rect", rows: 2', 6, 5)],
)
def test_a_fractions_coloured_parts_counted_by_the_preamble(shape, parts, coloured):
    """A fraction on a shape: the AI coloured 1 part of 4 for 3/4, or a triangle across the
    parts. Drawn by the preamble: the shape cut into `parts` equal parts, exactly `coloured`
    filled whole (counted in the SVG: the parts filled with the fraction's colour)."""
    svg = figures_typst.compile_svg("geometry", f"#fraction-shape({shape}, parts: {parts}, coloured: {coloured})")
    filled = len(re.findall(r'fill="#9fc3e7"', svg))
    assert filled == coloured, svg[:300]
    # several shapes side by side: five thirds over two discs
    two = '#fraction-shapes((kind: "disc", parts: 3, coloured: 3), (kind: "disc", parts: 3, coloured: 2))'
    assert len(re.findall(r'fill="#9fc3e7"', figures_typst.compile_svg("geometry", two))) == 5


def test_a_venn_parts_name_wider_than_it_goes_outside():
    """ "A ∩ B" written in a two-set lens (0.75 wide) lay on both circles, three drawings out
    of three. A part's name that fits stays in it; a wider one goes under the diagram, a line
    joining it to its part."""
    venn = '#cetz.canvas({{ cetz-venn.venn2(name: "v"); part-label("v.ab", {}) }})'
    svg = figures_typst.compile_svg
    short = svg("sets", venn.format("[$x$]"))
    long = svg("sets", venn.format("[$A inter B$]"))
    bare = svg("sets", '#cetz.canvas({ cetz-venn.venn2(name: "v") })')
    height = lambda s: float(re.search(r'height="([\d.]+)', s).group(1))  # noqa: E731
    assert height(short) == height(bare)  # in the lens
    assert height(long) > height(bare) + 10  # under the diagram
    assert "part-label" in figures_typst.FAMILIES["sets"].rules


def test_a_vector_drawn_with_its_arrow():
    """A scalar product's vectors drawn as plain segments (0/3): the rule had no vector. Drawn
    by the preamble: its arrow's head at its end (a segment more than the plain one), its name
    toward the head, clear of a point in its middle (a projection H)."""
    figure = "#ctz-canvas({{ ctz-init(); ctz-def-points(A: (0, 0), B: (4, 0), C: (2, 2)); {} }})"
    segment = figures_typst.compile_svg("geometry", figure.format('ctz-draw-segment("A", "B")'))
    vector = figures_typst.compile_svg("geometry", figure.format('ctz-draw-vector("A", "B")'))
    assert vector.count("<path") > segment.count("<path")  # the head
    named = figure.format('ctz-draw-vector("A", "B", label: $arrow(A B)$, away: "C")')
    assert figures_typst.compile_svg("geometry", named) != vector
    assert "ctz-draw-vector" in figures_typst.FAMILIES["geometry"].rules


def test_the_diagram_rules_edges_compile():
    """Every edge the diagram rule shows (its line styles, a label on its arrow, two arrows
    side by side) compiles between two nodes: a fragment out of step with fletcher (a "bend"
    inside the marks: refused 3 times) would make every diagram with it fail."""
    rules = figures_typst.FAMILIES["diagram"].rules
    edges = re.findall(r"`(edge\([^`]*\))`", rules)
    assert len(edges) >= 2
    for edge in edges:
        body = f"#diagram(node((0, 0), [A]), node((1, 0), [B]), node((0, 1), [C]), {edge})"
        assert figures_typst.compile_svg("diagram", body).startswith("<svg"), edge


def test_a_data_graphs_axis_at_its_frames_start():
    """Data far from 0 (years): the schoolbook theme draws the vertical axis at x = 0, the
    figure then grown to it, the curve a speck (the world's population, 1800 to 2020); placed
    at the frame's start as the rule says, the figure keeps its 8 cm."""
    body = (
        "#lq.diagram(width: 8cm, height: 5cm, xlim: (1780, 2040), ylim: (0, 9),{axis}\n"
        "  lq.plot((1800, 1927, 1960, 1999, 2022), (1, 2, 3, 6, 8), mark: none))"
    )
    width = lambda body: drawn_size("graph", body)[0] / 28.35  # noqa: E731  (cm)
    assert width(body.format(axis="")) > 30  # the axis at year 0
    assert "yaxis: (position: 1780)" in figures_typst.FAMILIES["graph"].rules
    assert width(body.format(axis=" yaxis: (position: 1780),")) < 10


def test_a_closed_switch_is_seen():
    """zap's closed switch is a mere wire: ours keeps its two contacts, closed or open."""
    circuit = '#circuit({{ battery("g", (0, 0), (0, 3)); {} lamp("l", (3, 3), (3, 0)); wire((3, 0), (0, 0)) }})'
    wired = figures_typst.compile_svg("circuit", circuit.format("wire((0, 3), (3, 3));"))
    closed = figures_typst.compile_svg("circuit", circuit.format('switch("k", (0, 3), (3, 3), closed: true);'))
    opened = figures_typst.compile_svg("circuit", circuit.format('switch("k", (0, 3), (3, 3));'))
    assert closed != wired and closed != opened


def test_a_current_arrow_between_two_wires_closes_the_circuit():
    """The AI writes the arrow as one more stretch of wire (a wire, the arrow, a wire): drawn
    with its wire, the circuit as closed as when the arrow is put on a wire."""
    circuit = (
        '#circuit({{ battery("g", (0, 0), (0, 3)); wire((0, 3), (1, 3)); {} wire((2, 3), (3, 3)); '
        'lamp("l", (3, 3), (3, 0)); wire((3, 0), (0, 0)) }})'
    )

    from PIL import Image

    def dark(body: str) -> int:
        png = figures.to_png(figures.clean(figures_typst.compile_svg("circuit", body)))
        return sum(Image.open(io.BytesIO(png)).convert("L").histogram()[:128])

    alone = dark(circuit.format("current-arrow((1, 3), (2, 3), $I$);"))
    on_a_wire = dark(circuit.format("wire((1, 3), (2, 3)); current-arrow((1, 3), (2, 3), $I$);"))
    assert alone == on_a_wire


def test_a_circuits_ends_a_hair_apart_meet():
    """An arrow written 0.1 short of the switch and the lamp it goes between: the wire cut there,
    the circuit open. Its ends moved onto theirs, drawn as when they meet; a shape drawn with
    cetz near the circuit left where it is."""
    circuit = (
        '#circuit({{ battery("g", (0, 0), (0, 4)); wire((0, 4), (2, 4)); '
        'switch("k", (2, 4), (2, 2.5), closed: true); {} lamp("l", (2, 1.7), (2, 0)); wire((2, 0), (0, 0)); '
        "cetz.draw.circle((2.1, 0.5), radius: 0.05) }})"
    )
    apart = figures_typst.source("circuit", circuit.format("current-arrow((2, 2.4), (2, 1.8), $I$);"))
    meeting = figures_typst.source("circuit", circuit.format("current-arrow((2, 2.5), (2, 1.7), $I$);"))
    assert apart == meeting and "(2.1, 0.5)" in apart


def test_a_timelines_texts_never_on_one_another():
    """Events a year apart, long texts: each on its own row, the figure taller for it."""
    one = figures_typst.compile_svg(
        "timeline", '#timeline(start: 1780, end: 1800, step: 5, events: ((1789, "Prise de la Bastille"),))'
    )
    crowded = figures_typst.compile_svg(
        "timeline",
        '#timeline(start: 1780, end: 1800, step: 5, events: ((1789, "Prise de la Bastille"), '
        '(1790, "Fête de la Fédération"), (1791, "Fuite à Varennes")), periods: ((1793, 1794, "La Terreur"),))',
    )
    height = lambda svg: float(re.search(r'height="([\d.]+)', svg).group(1))  # noqa: E731
    assert height(crowded) > height(one) * 1.5


def test_a_line_of_moments_writes_no_number():
    """A verb's tenses placed by their order (-1, 0 the present): `step: none` writes no number
    under the line (it wrote "−3", "−2"…), only the texts' letters; `now` marks the present
    across the line, its text under it, `past` and `future` written at the line's ends."""
    texts = '((-1, "Passé"), (0, "Présent"))'
    tenses = f"#timeline(start: -2, end: 2, step: none, events: {texts})"
    svg = figures_typst.compile_svg("timeline", tenses)
    assert svg.count("<use") == len("PasséPrésent")  # a glyph each, no number's
    numbered = figures_typst.compile_svg("timeline", tenses.replace("step: none", "step: 1"))
    assert numbered.count("<use") > svg.count("<use")
    now = figures_typst.compile_svg("timeline", tenses.replace("step: none", 'step: none, now: "Nu"'))
    drawn = lambda svg: svg.split("<defs")[0].count("<path")  # noqa: E731 (the glyphs' are in defs)
    assert drawn(now) > drawn(svg) and now.count("<use") == svg.count("<use") + 2
    ends = figures_typst.compile_svg("timeline", tenses.replace("step: none", 'step: none, past: "P", future: "F"'))
    assert ends.count("<use") == svg.count("<use") + 2


def hand_angle(png: bytes, colour: tuple[int, int, int]) -> float:
    """Where a clock's hand of that colour points: degrees from twelve o'clock, clockwise."""
    import io
    import math

    from PIL import Image

    image = Image.open(io.BytesIO(png)).convert("RGB")
    near = lambda p: sum(abs(a - b) for a, b in zip(p, colour, strict=True)) < 120  # noqa: E731
    points = [(x, y) for y in range(image.height) for x in range(image.width) if near(image.getpixel((x, y)))]
    dx = sum(x for x, _ in points) / len(points) - image.width / 2
    dy = sum(y for _, y in points) / len(points) - image.height / 2
    return math.degrees(math.atan2(dx, -dy)) % 360


@pytest.mark.parametrize(("hour", "minute"), [(10, 30), (3, 0), (8, 45), (15, 20)])
def test_a_clocks_hands_placed_by_the_time(hour, minute):
    """The hands where the time puts them, the hour hand between its hours as the minutes go
    by (half past ten: halfway from 10 to 11), never by eye."""
    body = f"#clock({hour}, {minute}, numbers: false, hour-color: rgb(255, 0, 0), minute-color: rgb(0, 0, 255))"
    png = figures.to_png(figures.clean(figures_typst.compile_svg("clock", body)))
    assert abs(hand_angle(png, (255, 0, 0)) - (hour % 12 + minute / 60) * 30) < 3
    assert abs(hand_angle(png, (0, 0, 255)) - minute * 6) % 360 < 3


def test_a_clock_at_an_impossible_time_refused():
    """A time that isn't one (25 h, 60 min, a half hour as 10.5): refused, saying why, for the
    AI to write it again; never a face drawn at a guess. 15 h is 3 o'clock's face."""
    for body in ("#clock(25, 0)", "#clock(10, 60)", "#clock(10.5, 0)"):
        with pytest.raises(figures_typst.Unusable, match="whole number"):
            figures_typst.compile_svg("clock", body)
    assert figures_typst.compile_svg("clock", "#clock(15, 30)") == figures_typst.compile_svg("clock", "#clock(3, 30)")


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


def test_a_probability_tree_as_wide_as_it_is_high():
    """A tree's places computed (three Bernoulli trials, eight leaves: placed by the AI, a strip
    three times as high as wide, unreadable once fitted, 3 drawings in 3): about as wide as high.
    A branch not (name, label) or (name, label, branches): refused, saying how."""
    two = "(($S$, [0,3]{0}), ($E$, [0,7]{0}))"
    body = "#tree" + two.format(", " + two.format(", " + two.format("")))
    width, height = drawn_size("diagram", body)
    assert 0.6 < width / height < 1.6
    with pytest.raises(figures_typst.Unusable, match="each branch"):
        figures_typst.compile_svg("diagram", '#tree(("A", [0,4], "B"), "C")')


def test_a_networks_vertices_placed_so_that_no_edges_cross():
    """A graph of graph theory: its vertices placed by the AI's eye (drawn by hand 2 times in 3),
    now on a circle in the order that crosses the fewest edges, not the order they are listed
    in (A, B, C, D, E around it crosses three times here; A, B, D, E, C none). The rule's own
    call compiles; an edge naming no vertex is refused, saying which."""
    rule = (figures_typst.RULES / "diagram.md").read_text(encoding="utf-8")
    call = re.search(r"`(#network\(.*?\))`", rule)
    assert call and figures_typst.compile_svg("diagram", call[1]).startswith("<svg")
    edges = [("A", "B"), ("A", "C"), ("B", "C"), ("B", "D"), ("C", "D"), ("C", "E"), ("D", "E")]
    body = '#network(vertices: ("A", "B", "C", "D", "E"), edges: ({}))'.format(
        ", ".join(f'("{a}", "{b}")' for a, b in edges)
    )
    names = _glyphs(figures_typst.compile_svg("diagram", body))  # the vertices' names, A to E
    assert len(names) == 5
    cx, cy = sum(x for x, _ in names) / 5, sum(y for _, y in names) / 5
    around = sorted(range(5), key=lambda i: math.atan2(names[i][1] - cy, names[i][0] - cx))
    at = {"ABCDE"[v]: around.index(v) for v in range(5)}
    chords = [tuple(sorted((at[a], at[b]))) for a, b in edges]
    crossing = [
        (p, q)
        for i, p in enumerate(chords)
        for q in chords[i + 1 :]
        if len({*p, *q}) == 4 and (p[0] < q[0] < p[1]) != (p[0] < q[1] < p[1])
    ]
    assert crossing == []
    with pytest.raises(figures_typst.Unusable, match="not one of the vertices"):
        figures_typst.compile_svg("diagram", '#network(vertices: ("A", "B"), edges: (("A", "C"),))')


def test_a_networks_weights_never_on_one_another():
    """Two edges crossing in their middles (a complete graph's diagonals): their weights moved
    along them, apart, never written one on the other."""
    edges = '("A", "B", [1]), ("A", "C", [2]), ("A", "D", [3]), ("B", "C", [4]), ("B", "D", [5]), ("C", "D", [6])'
    svg = figures_typst.compile_svg("diagram", f'#network(vertices: ("A", "B", "C", "D"), edges: ({edges}))')
    weights = _glyphs(svg)[4:]
    assert len(weights) == 6
    assert min(math.dist(p, q) for i, p in enumerate(weights) for q in weights[i + 1 :]) > 10  # pt


def test_a_coordinate_frame_drawn_as_the_geometry_rule_says():
    """A circle or a line in a coordinate frame: the rule's own calls compile (the AI wrote
    ctz-draw-axes(-2, 6, -3, 5), positional, refused by Typst 3 times in 3: no frame was
    described), the axes' arrows past the grid's last numbers."""
    rule = (figures_typst.RULES / "geometry.md").read_text(encoding="utf-8")
    calls = re.findall(r"`(ctz-draw-(?:grid|axes)\(xmin:[^`]*\))`", rule)
    assert len(calls) == 2
    body = '#ctz-canvas({{\n  ctz-init()\n  {}\n  {}\n  ctz-def-points(Ω: (2, 1))\n  ctz-draw-circle-r("Ω", 3)\n}})'
    assert figures.clean(figures_typst.compile_svg("geometry", body.format(*calls))).startswith("<svg")


def test_a_trigonometric_circle_with_one_angle():
    """One angle written without its trailing comma, ((60, $M$)) (the AI's, refused 3 times in
    3: Typst reads a pair, not a list of one): the same circle as ((60, $M$),)."""
    circle = "#ctz-canvas({{ ctz-init()\n ctz-draw-unit-circle(angles: {}, project: (60, $1/2$, $sqrt(3)/2$)) }})"
    one = figures_typst.compile_svg("geometry", circle.format("((60, $M$),)"))
    assert figures_typst.compile_svg("geometry", circle.format("((60, $M$))")) == one


def test_a_frames_axes_numbered_at_whole_steps():
    """Axes starting half a unit out (−1.5, as the rule asks): ctz-euclide counted its steps
    from there, "−1.5, −0.5, 0.5" written between the units, on the points and the circle.
    Numbered at the step's multiples, the same numbers wherever the axis starts."""
    frame = "#ctz-canvas({{ ctz-init()\n ctz-draw-axes(xmin: {0}, xmax: 1.5, ymin: {0}, ymax: 1.5) }})"
    numbers = [len(_glyphs(figures_typst.compile_svg("geometry", frame.format(start)))) for start in ("-1.5", "-1")]
    assert numbers[0] == numbers[1]


def test_points_on_the_unit_circle_joined_and_named_as_the_rule_says():
    """Roots of unity drawn in a frame of the AI's own, their names written by hand beside
    letters it added (B and j, C and j² one on the other, 3 times in 3): the unit circle joins
    its points (`join: true`); a point named otherwise than by a letter gets its text from the
    labels, as the rule writes it."""
    circle = "#ctz-canvas({{ ctz-init()\n ctz-draw-unit-circle(angles: ((0, $1$), (120, $j$), (240, $j^2$)){}) }})"
    joined = figures_typst.compile_svg("geometry", circle.format(", join: true"))
    assert joined != figures_typst.compile_svg("geometry", circle.format(""))
    rule = (figures_typst.RULES / "geometry.md").read_text(encoding="utf-8")
    call = re.search(r"`(ctz-draw-labels\(B: \(pos: [^`]*label: [^`]*\)\))`", rule)
    assert call
    body = f"#ctz-canvas({{ ctz-init()\n ctz-def-points(A: (0, 0), B: (2, 1))\n {call[1]} }})"
    assert figures_typst.compile_svg("geometry", body).startswith("<svg")


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


def test_a_charts_angles_and_heights_come_from_its_counts():
    """A chart's sectors are its counts' shares (1, 1 and 2, 2 the same half pie), computed,
    never given; large counts and a zero drawn too (the bars' graduation by 20s)."""
    semi = '#chart(kind: "semi", values: (("A", {}), ("B", {})))'
    halves = {figures_typst.compile_svg("chart", semi.format(n, n)) for n in (1, 2)}
    assert len(halves) == 1
    pie = figures_typst.compile_svg("chart", '#chart(kind: "pie", values: (("A", 1), ("B", 3)))')
    assert pie != figures_typst.compile_svg("chart", '#chart(kind: "pie", values: (("A", 3), ("B", 1)))')
    for kind in ("bars", "pie", "semi"):
        figures_typst.compile_svg("chart", f'#chart(kind: "{kind}", values: (("A", 230), ("B", 5), ("C", 0)))')


@pytest.mark.parametrize(
    ("values", "lines"),
    [
        ('(("0", 0.2), ("1", 0.5), ("2", 0.3))', 5),  # by tenths up to 0.5
        ('(("0", 0.078), ("1", 0.259), ("2", 0.346), ("3", 0.23))', 7),  # by 0.05 up to 0.35
        ('(("A", 12), ("B", 7), ("C", 3))', 12),  # counts: by units, as before
    ],
)
def test_a_bar_charts_graduation_reads_its_values(values, lines):
    """A probability law's bars (values under 1) graduated by tenths or hundredths, a light
    line at each: never 0 and 1 alone, where no value can be read (6 drawings in 6)."""
    svg = figures_typst.compile_svg("chart", f'#chart(kind: "bars", values: {values})')
    assert svg.count('stroke="#cdcdcd"') == lines


def test_a_charts_counts_written_only_when_asked():
    """None by default (a card asking a count, a frequency or an angle never shows it on its
    chart); "all", or the labels given."""
    for kind in ("bars", "pie", "semi"):
        body = f'#chart(kind: "{kind}", values: (("Chat", 12), ("Chien", 10), ("Lapin", 5)){{}})'
        bare = figures_typst.compile_svg("chart", body.format(""))
        assert bare == figures_typst.compile_svg("chart", body.format(", written: ()")), kind
        some = figures_typst.compile_svg("chart", body.format(', written: ("Chien",)'))
        every = figures_typst.compile_svg("chart", body.format(', written: "all"'))
        assert len({bare, some, every}) == 3, kind


def test_a_line_starts_its_axes_where_its_measures_are():
    """A line's axes meet at its bottom left, from 0 for measures near it, else from the
    graduation under the lowest (a heart rate from 70, years around them): the measures
    fill the frame. Its graduations every round interval they were taken at."""
    from PIL import Image

    heart = "((0, 70), (2, 72), (4, 120), (6, 145), (8, 150), (10, 150), (12, 110), (14, 85), (16, 75))"
    for values in (heart, "((2000, 6.1), (2005, 6.5), (2010, 6.9), (2015, 7.3), (2020, 7.8))"):
        svg = figures_typst.compile_svg("chart", f'#chart(kind: "line", values: {values}, axes: ("x", "y"))')
        image = Image.open(io.BytesIO(figures.to_png(figures.clean(svg)))).convert("RGB")
        red = [
            y for y in range(image.height) for x in range(0, image.width, 2) if image.getpixel((x, y)) == (176, 58, 46)
        ]
        top, bottom = min(red), max(red)
        # its lowest measure on its x axis, its highest at its top: they fill the frame
        assert bottom - top > image.height * 0.6, values
    line = '#chart(kind: "line", values: ((0, 21), (1, 20.4), (2, 19.6)), axes: ("Temps (min)", "Dioxygène (%)"){})'
    bare, written = (figures_typst.compile_svg("chart", line.format(w)) for w in ("", ", written: (2,)"))
    assert bare != written


def test_lines_of_the_same_measure_share_one_axis():
    """Several lines of one measure (an allele's frequency in two populations) on the same
    graduation, each its colour and a legend: one twice as high as the other is drawn twice
    as high, never stretched to its own axis; `second` (another unit) is a single line's."""
    from PIL import Image

    body = '#chart(kind: "line", values: (("A", ((0, 0), (10, 5))), ("B", ((0, 0), (10, 10)))), axes: ("x", "y"))'
    image = Image.open(io.BytesIO(figures.to_png(figures.clean(figures_typst.compile_svg("chart", body)))))
    image = image.convert("RGB")
    plot = image.crop((0, 0, int(image.width * 0.7), image.height))  # the legend at the right left out

    def height(colour):
        ys = [y for y in range(plot.height) for x in range(0, plot.width, 2) if plot.getpixel((x, y)) == colour]
        return max(ys) - min(ys)

    assert height((31, 95, 168)) == pytest.approx(2 * height((176, 58, 46)), rel=0.1)
    with pytest.raises(figures_typst.Unusable, match="single line"):
        figures_typst.compile_svg("chart", body[:-1] + ', second: (values: ((0, 1), (1, 2)), axis: "z"))')


def test_a_smooth_line_goes_through_its_measures_and_never_beyond():
    """A curve through measures (a concentration over time): through every one, never above
    the highest nor below the lowest between two (a plateau stays flat), drawn by the chart,
    never a function the AI fits to them."""
    from PIL import Image

    body = '#chart(kind: "line", values: ((0, 0), (1, 5), (2, 5), (3, 5), (4, 1)), axes: ("t", "y"){})'

    def reach(extra):
        image = Image.open(
            io.BytesIO(figures.to_png(figures.clean(figures_typst.compile_svg("chart", body.format(extra)))))
        )
        image = image.convert("RGB")
        red = [y for y in range(image.height) for x in range(image.width) if image.getpixel((x, y)) == (176, 58, 46)]
        return min(red), max(red)

    straight, smooth = reach(""), reach(", smooth: true")
    drawn = {figures_typst.compile_svg("chart", body.format(extra)) for extra in ("", ", smooth: true")}
    assert len(drawn) == 2  # a curve, not the straight lines
    assert abs(smooth[0] - straight[0]) <= 1 and abs(smooth[1] - straight[1]) <= 1


def test_a_line_marks_its_events_and_stretches():
    """An event at an x (a dashed line, its label under the axis) and a stretch of x
    (shaded), placed by the chart from their values: each changes the drawing."""
    line = '#chart(kind: "line", values: ((0, 2), (10, 8), (20, 4)), axes: ("t", "y"){})'
    drawn = {
        figures_typst.compile_svg("chart", line.format(extra))
        for extra in ("", ', marks: ((10, "arrêt"),)', ', spans: ((2, 6, "effort"),)')
    }
    assert len(drawn) == 3


def test_a_second_measure_on_its_own_axis():
    """Two measures of different units over the same x: the second on a right axis of its
    own, in another colour, never left out."""
    from PIL import Image

    body = (
        '#chart(kind: "line", values: ((1960, 317), (2020, 414)), axes: ("Année", "A (ppm)"),'
        ' second: (values: ((1960, 0), (2020, 1.0)), axis: "B (°C)"))'
    )
    image = Image.open(io.BytesIO(figures.to_png(figures.clean(figures_typst.compile_svg("chart", body)))))
    blue = sum(1 for p in image.convert("RGB").getdata() if p == (31, 95, 168))
    assert blue > 50  # its line, its numbers


def test_a_line_without_values_shows_no_numbers_on_its_y_axis():
    """numbered: false, the description giving no value for y: its shape only."""
    line = '#chart(kind: "line", values: ((1, 1), (5, 1), (28, 5)), axes: ("Jours", "y"){})'
    numbered, bare = (figures_typst.compile_svg("chart", line.format(n)) for n in ("", ", numbered: false"))
    assert len(bare) < len(numbered)


def test_a_bar_charts_long_names_never_overlap():
    """Each bar has its name's width at least: long names widen the chart, never overlap."""

    def width(names):
        values = ", ".join(f'("{n}", {i + 1})' for i, n in enumerate(names))
        svg = figures_typst.compile_svg("chart", f'#chart(kind: "bars", values: ({values},))')
        return float(re.search(r'<svg[^>]*\swidth="([\d.]+)', svg).group(1))

    short = width(["A", "B", "C", "D", "E"])
    assert width(["Réfrigérateurs", "Congélateurs", "Lave-vaisselle", "Téléviseurs", "Aspirateurs"]) > 1.5 * short


def test_a_chart_refuses_what_it_cant_draw():
    for body, said in (
        ('#chart(kind: "bars", values: (("A", 1),), marks: ((1, "x"),))', "a line's only"),
        ('#chart(kind: "line", values: ((0, 1), (1, 2)), spans: ((3, 2, "x"),))', "from < to"),
        ('#chart(kind: "line", values: ((0, 1), (1, 2)), marks: (("a", "x"),))', "x a number"),
        ('#chart(kind: "line", values: ((0, 1), (1, 2)), second: (values: ((0, 1),)))', "two measures at least"),
        ('#chart(kind: "line", values: ((0, 1),))', "two at least"),
        ('#chart(kind: "line", values: (("lundi", 1), ("mardi", 2)))', "each a number"),
        ('#chart(kind: "area", values: (("A", 1),))', "kind is"),
        ('#chart(kind: "pie", values: (("A", 0), ("B", 0)))', "add up to more than 0"),
        ('#chart(kind: "pie", values: ("A", "B"))', "pairs"),
    ):
        with pytest.raises(figures_typst.Unusable, match=said):
            figures_typst.compile_svg("chart", body)


def test_a_solid_drawn_the_same_whatever_its_unit():
    """Lengths in any unit: only their ratio shows (a cuboid 5 × 3 × 2 as 50 × 30 × 20)."""
    small = figures_typst.compile_svg("solid", "#cuboid(5, 3, 2)")
    assert figures_typst.compile_svg("solid", "#cuboid(50, 30, 20)") == small


def drawn_size(family: str, body: str) -> tuple[float, float]:
    """A figure's drawing, its page's margins (6 pt each side) left out: width, height in pt."""
    box = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', figures_typst.compile_svg(family, body))
    return float(box.group(1)) - 12, float(box.group(2)) - 12


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


def test_a_figure_of_no_family_drawn_as_svg(monkeypatch):
    calls = []

    async def answer(s, images, text, schema, system=None, light=False, **options):
        calls.append(schema.__name__)
        if schema is figures_typst.Kind:
            return schema(family="other")
        return schema(svg=SQUARE)

    monkeypatch.setattr("notosaurus_core.ai._ask_provider", answer)
    svg = asyncio.run(llm.draw_figure(AIConfig(llm="gemini"), "un tableau de valeurs"))
    assert ">A<" in svg and calls == ["Kind", "Drawing"]


@pytest.mark.parametrize("family", sorted(figures_typst.FAMILIES))
def test_every_familys_text_in_the_svg_figures_font(family):
    """A figure's text in DejaVu Sans, whichever family draws it: not Typst's own serif."""
    plain = figures_typst.compile_svg(family, '#text("Mi 12")')
    sans = figures_typst.compile_svg(family, '#text(font: "DejaVu Sans", "Mi 12")')
    assert plain == sans


def test_the_figures_bench_compiles_a_run_again(tmp_path):
    """tools/bench_figures.py --recompile: a drawing's Typst compiled again with today's
    preamble, an SVG drawing kept as it was, one not drawn said so."""
    import sys

    sys.path.insert(0, str(figures_typst.HERE.parent.parent / "tools"))
    import bench_figures

    (tmp_path / "a-1.typ").write_text('#timeline(start: 1780, end: 1800, events: ((1789, "Bastille"),))')
    (tmp_path / "b-1.svg").write_text(SQUARE)
    typst = bench_figures.recompiled(tmp_path, {"family": "timeline", "typst_file": "a-1.typ", "file": "a-1.svg"})
    assert typst["engine"] == "typst" and typst["svg"].startswith("<svg") and "Bastille" in typst["typst"]
    assert bench_figures.recompiled(tmp_path, {"family": "diagram", "file": "b-1.svg"})["svg"] == SQUARE
    assert bench_figures.recompiled(tmp_path, {"problem": "500 Internal"}) == {"error": "500 Internal"}


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


@pytest.mark.parametrize(
    "colour",
    [
        "color.mix(red, blue)",
        "color.mix(green, red, blue)",
        "oklch(60%, 0.15, 200deg)",
        "color.hsl(200deg, 50%, 50%)",
        "color.linear-rgb(20%, 40%, 60%)",
        "color.mix(red, blue).transparentize(40%)",
    ],
)
def test_a_typst_colour_kept_as_typst_makes_it(colour):
    """Typst writes a mixed colour (oklab by default), an oklch, an hsl or a linear RGB as
    CSS's newer functions, which figures.clean drops (a value with brackets): a pH scale's
    bands came out black. Written #rrggbb(aa) instead, Typst's own colour (to-hex), kept by
    the clean and painted."""
    import io

    from PIL import Image

    def filled(body: str) -> list[str]:
        svg = figures.clean(figures_typst.compile_svg("geometry", body))
        return [v for v in re.findall(r'fill="([^"]*)"', svg) if v not in ("#ffffff", "none")]

    rect = "#rect(width: 2cm, height: 1cm, fill: {})"
    assert filled(rect.format(colour)) == filled(rect.format(f"rgb(({colour}).to-hex())")) != []
    png = figures.to_png(figures.clean(figures_typst.compile_svg("geometry", rect.format(colour))))
    middle = Image.open(io.BytesIO(png)).convert("RGB")
    assert middle.getpixel((middle.width // 2, middle.height // 2)) != (0, 0, 0)


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


def test_a_figure_credits_the_typst_that_drew_it():
    """Typst's own version, the compiler typst-py ships: typst-py 0.15.2 ships Typst 0.15.1,
    there is no Typst 0.15.2 to credit."""
    import json

    import typst

    engine = json.loads(typst.query(b"#metadata(str(sys.version)) <v>", "<v>", field="value"))[0]
    assert figures_typst.made_with("clock", "#clock(10, 25)")[0] == f"Typst {engine}"


def test_colours_mixed_are_computed():
    """Additive synthesis adds the lights (red and green yellow, the three white, on black);
    subtractive multiplies the filters (cyan and magenta blue, the three black, on white):
    each part's colour computed, the synthesis' pure colours ("green" isn't Typst's #2ecc40)."""

    def fills(body: str) -> set[str]:
        return set(re.findall(r'fill="(#[0-9a-f]{6})"', figures.clean(figures_typst.compile_svg("sets", body))))

    added = fills('#colour-mix(kind: "additive", colours: ("red", "green", "blue"))')
    assert {"#ff0000", "#00ff00", "#0000ff", "#ffff00", "#ff00ff", "#00ffff", "#ffffff", "#000000"} <= added
    taken = fills('#colour-mix(kind: "subtractive", colours: ("cyan", "magenta", "yellow"))')
    assert {"#00ffff", "#ff00ff", "#ffff00", "#0000ff", "#00ff00", "#ff0000", "#000000"} <= taken
    assert fills('#colour-mix(colours: ("red", "green"))') >= {"#ff0000", "#00ff00", "#ffff00"}
    with pytest.raises(figures_typst.Unusable, match="a colour is one of"):
        figures_typst.compile_svg("sets", '#colour-mix(colours: ("rouge", "vert"))')


def test_a_mixed_colour_a_card_asks_is_not_shown():
    """ "Which colour at the centre?": the centre left grey with a question mark, its white not
    drawn (it would give the answer on the front)."""
    body = '#colour-mix(kind: "additive", colours: ("red", "green", "blue"){})'
    shown = figures.clean(figures_typst.compile_svg("sets", body.format("")))
    asked = figures.clean(figures_typst.compile_svg("sets", body.format(', ask: ("abc",)')))
    assert "#8c8c8c" in asked and "#8c8c8c" not in shown  # the centre grey, not white
    assert asked.count('fill="#ffffff"') <= shown.count('fill="#ffffff"')


def test_the_chemistry_rule_says_how_to_draw_a_lewis_structures_pairs():
    """Without it the AI drew a Lewis structure's non-bonding pairs as bonds to no atom, or
    left them out (0 of 12 right): the rule's Lewis call, as it gives it, draws them."""
    rule = figures_typst.FAMILIES["chemistry"].rules
    calls = re.findall(r"`(fragment\([^`]*lewis-line[^`]*)`", rule)
    assert calls, "the chemistry rule shows a Lewis structure's pairs"
    for call in calls:
        assert figures_typst.compile_svg("chemistry", "#skeletize({ " + call + " })").startswith("<svg")


def test_sequences_differences_are_computed_and_framed():
    """Aligned sequences: the letters where variants of the same kind differ are framed,
    computed from the letters, never placed; a strand and its transcript or its complement
    (different everywhere) are no variants, never framed; a protein under its codons."""
    seq = lambda rows, extra="": figures_typst.compile_svg("sequence", f"#sequences({extra}rows: ({rows}))")  # noqa: E731
    alleles = '("1", "ATG GCA TTC"), ("2", "ATG GCG TTC")'
    assert seq(alleles) != seq(alleles, "framed: false, ")
    assert seq(alleles) != seq('("1", "ATG GCA TTC"), ("2", "ATG GGA TTC")')  # elsewhere, framed elsewhere
    same = '("1", "ATG GCA TTC"), ("2", "ATG GCA TTC")'
    assert seq(same) == seq(same, "framed: false, ")
    strand = '("ADN", "TAC GGA CTT"), '
    for unlike in (strand + '("ARNm", "AUG CCU GAA")', strand + '("Brin", "ATG CCT GAA")'):
        assert seq(unlike) == seq(unlike, "framed: false, ")
    codons = '("ARNm", "AUG CCU GAA"), ("Protéine", {})'
    assert seq(codons.format('"Met-Pro-Glu"')) == seq(codons.format('("Met", "Pro", "Glu")'))
    with pytest.raises(figures_typst.Unusable, match="aligned"):
        seq('("1", "ATG GCA TTC"), ("2", "ATG GA TTC")')


def test_a_sequences_asked_letter_is_not_shown():
    """A card asking which letter: written "?", whatever it was."""
    body = '#sequences(ask: (("2", 6),), rows: (("1", "ATG GCA TTC"), ("2", "ATG GC{} TTC")))'
    asked = figures_typst.compile_svg("sequence", body.format("G"))
    assert asked == figures_typst.compile_svg("sequence", body.format("T"))
    assert asked != figures_typst.compile_svg("sequence", body.format("G").replace('ask: (("2", 6),), ', ""))


def _table(body: str) -> str:
    return figures_typst.compile_svg("table", "#value-table(" + body + ")")


def _width(svg: str) -> float:
    return float(ElementTree.fromstring(svg).get("width", "0").removesuffix("pt"))


def test_a_tables_columns_are_as_wide_as_their_cells():
    """A table drawn as SVG had its columns' widths guessed: « Demi-pensionnaire » ran over
    the next cell (0 of 3). Drawn by value-table, each column as wide as its widest cell,
    measured: a longer header widens the table by about the text added."""
    short = _table('header: ("", "DP", "Externe"), rows: (("Fille", 70, 30), ("Garçon", 60, 40))')
    long = _table('header: ("", "Demi-pensionnaire", "Externe"), rows: (("Fille", 70, 30), ("Garçon", 60, 40))')
    # the values' columns alike, each as wide as "Demi-pensionnaire" (15 letters more than "DP")
    assert _width(long) - _width(short) > 2 * 15 * 4


def test_a_tables_totals_are_summed():
    """The totals of each row and column, and the grand total, summed by value-table: the
    same table as one whose totals were written out; a total of what is no number refused."""
    summed = _table('header: ("", "A", "B"), rows: (("Fille", 70, 30), ("Garçon", 60, 40)), totals: "Total"')
    written = _table(
        'header: ("", "A", "B", "Total"), rows: (("Fille", 70, 30, 100), ("Garçon", 60, 40, 100), '
        '("Total", 130, 70, 200))'
    )
    assert summed == written
    rows_only = _table('header: ("", "A", "B"), rows: (("Fille", 70, 30), ("Garçon", 60, 40)), totals: (right: "T")')
    assert rows_only == _table('header: ("", "A", "B", "T"), rows: (("Fille", 70, 30, 100), ("Garçon", 60, 40, 100))')
    with pytest.raises(figures_typst.Unusable, match="number"):
        _table('rows: (("Fille", 70, "beaucoup"),), totals: "Total"')


def test_a_tables_numbers_are_written_as_its_language_writes_them():
    """A number written with the figure's decimal separator, its zeros kept: a measure's
    "3,0" and "0,030" were drawn "3" and "0,03" (0 of 3); a total with as many decimals as
    the numbers summed."""
    fr = '#set text(lang: "fr")\n'

    def table(body: str) -> str:
        return figures_typst.compile_svg("table", fr + "#value-table(" + body + ")")

    assert table("rows: ((1.5, 2),)") == table('rows: (("1,5", 2),)') == table('rows: (("1.5", 2),)')
    assert table('rows: (("3,0", 2),)') != table('rows: (("3", 2),)')
    assert table('rows: (("0,030", 2),)') != table('rows: (("0,03", 2),)')
    summed = table('rows: (("I", "0,015", "0,015"),), totals: (right: "T")')
    assert summed == table('header: ("", "", "", "T"), rows: (("I", "0,015", "0,015", "0,030"),)')


def test_a_tables_arrows_join_the_rows_and_columns_given():
    """A proportionality table's arrows (× 3 from a row to the next, × 2 from a column to
    another) drawn from the rows and columns they join: one that joins none refused."""
    plain = _table("rows: ((2, 5, 7), (6, 15, 21))")
    for side in ("right", "left"):
        arrowed = _table(f"rows: ((2, 5, 7), (6, 15, 21)), {side}: ((1, 2, $times 3$),)")
        assert _width(arrowed) > _width(plain)
        with pytest.raises(figures_typst.Unusable, match="rows"):
            _table(f"rows: ((2, 5, 7), (6, 15, 21)), {side}: ((1, 3, $times 3$),)")
    for side in ("above", "below"):
        assert _table(f"rows: ((2, 5, 7), (6, 15, 21)), {side}: ((1, 2, $times 2$),)") != plain
        with pytest.raises(figures_typst.Unusable, match="columns"):
            _table(f"rows: ((2, 5, 7), (6, 15, 21)), {side}: ((1, 4, $times 2$),)")


def test_a_phylogenetic_tree_is_built_from_what_each_species_has():
    """The groups sharing a character are the tree's groups, computed: the order the
    characters are listed in changes nothing, a lone character written without its comma
    neither; characters whose groups overlap without nesting are refused (no tree has both),
    never drawn at a guess."""
    tree = '#phylogeny(species: (("Truite", ()), ("Grenouille", {}), ("Chat", {})))'
    ladder = figures_typst.compile_svg("phylogeny", tree.format('("membres",)', '("membres", "poils")'))
    assert ladder == figures_typst.compile_svg("phylogeny", tree.format('("membres")', '("poils", "membres")'))
    assert ladder != figures_typst.compile_svg("phylogeny", tree.format('("membres",)', '("membres",)'))
    overlapping = tree.format('("membres", "poils")', '("membres",)').replace("()", '("poils",)')
    with pytest.raises(figures_typst.Unusable, match="overlap without nesting"):
        figures_typst.compile_svg("phylogeny", overlapping)


def test_a_phylogenetic_trees_hidden_names_are_not_shown():
    """A card asking which species or which innovation: written "?", not its name."""
    tree = '#phylogeny({}species: (("Truite", ()), ("Grenouille", ("membres",)), ("Chat", ("membres", "poils"))))'
    bare = figures_typst.compile_svg("phylogeny", tree.format(""))
    for hidden in ('"poils"', '"Chat"'):
        body = tree.format(f"hidden: ({hidden},), ")
        asked = figures_typst.compile_svg("phylogeny", body)
        assert asked != bare
        assert asked == figures_typst.compile_svg("phylogeny", body.replace(hidden, '"x"'))


def test_a_bodys_vectors_point_where_their_support_says():
    """A vector given by its direction, computed from the support: on a circle "along" is the
    tangent the body turns along and "centre" towards the centre, on a slope "normal" is
    out of it, on the ground "back" against the motion; never an angle of the AI's."""
    drawn = lambda body: figures_typst.compile_svg("mechanics", f"#mechanics({body})")  # noqa: E731
    circle = 'support: "circle", at: 0, vectors: (("v", {}),)'
    assert drawn(circle.format('"along"')) == drawn(circle.format("90"))
    assert drawn(circle.format('"centre"')) == drawn(circle.format("180"))
    assert drawn("clockwise: true, " + circle.format('"along"')) == drawn(circle.format("270"))
    slope = 'support: "slope", angle: 30, vectors: (("R", {}),)'
    assert drawn(slope.format('"normal"')) == drawn(slope.format("120"))
    assert drawn(slope.format('"downhill"')) == drawn(slope.format("210"))
    plane = 'support: "plane", vectors: (("f", {}),)'
    pendulum = 'support: "pendulum", angle: 30, vectors: (("T", {}),)'  # its string at 300°
    assert drawn(pendulum.format('"centre"')) == drawn(pendulum.format("120"))
    assert drawn(plane.format('"back"')) == drawn(plane.format("180"))
    for wrong, said in (('vectors: (("F", "centre"),)', "circle's"), ('vectors: (("F", "sideways"),)', "direction")):
        with pytest.raises(figures_typst.Unusable, match=said):
            drawn(wrong)


def test_a_bodys_hidden_vector_name_is_not_shown():
    """A card asking which force: its name written "?", whatever it was."""
    body = '#mechanics(hidden: ("{0}",), vectors: (("P", "down"), ("{0}", "up")))'
    asked = figures_typst.compile_svg("mechanics", body.format("R"))
    assert asked == figures_typst.compile_svg("mechanics", body.format("T"))
    assert asked != figures_typst.compile_svg("mechanics", body.format("R").replace('hidden: ("R",), ', ""))
