"""Figures on cards: SVG drawn by the AI, cleaned, saved and sent like the pictures."""

import asyncio
import json
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

    monkeypatch.setattr(llm, "_ask_provider", answer)
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

    async def draw(s, description, step=None, kind="", problem="", careful=False):
        asked.append((problem, careful))
        return await real(s, description, step, kind, problem, careful)

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

    monkeypatch.setattr(llm, "_ask_provider", answer)
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

    monkeypatch.setattr(llm, "_ask_provider", answer)
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
    assert figures_typst.made_with("other", balls) == []


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
    typst = (figures_typst.RULES / f"{family}.typ").read_text(encoding="utf-8")
    example = typst.split(figures_typst.EXAMPLE)[1].replace("  ...\n", "")  # (geometry's: "and so on")
    assert figures.clean(figures_typst.compile_svg(family, example)).startswith("<svg")


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


def test_each_familys_rule_and_typst_in_their_files():
    """A rule says where its example goes ({example}, once), its Typst where the AI's part
    starts (EXAMPLE, once); the example is in the rule the AI is given."""
    for family, made in figures_typst.FAMILIES.items():
        rule = (figures_typst.RULES / f"{family}.md").read_text(encoding="utf-8")
        typst = (figures_typst.RULES / f"{family}.typ").read_text(encoding="utf-8")
        assert rule.count("{example}") == 1 and typst.count(figures_typst.EXAMPLE) == 1, family
        assert typst.split(figures_typst.EXAMPLE)[1].strip() in made.rules and "{example}" not in made.rules


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


def test_a_closed_switch_is_seen():
    """zap's closed switch is a mere wire: ours keeps its two contacts, closed or open."""
    circuit = '#circuit({{ battery("g", (0, 0), (0, 3)); {} lamp("l", (3, 3), (3, 0)); wire((3, 0), (0, 0)) }})'
    wired = figures_typst.compile_svg("circuit", circuit.format("wire((0, 3), (3, 3));"))
    closed = figures_typst.compile_svg("circuit", circuit.format('switch("k", (0, 3), (3, 3), closed: true);'))
    opened = figures_typst.compile_svg("circuit", circuit.format('switch("k", (0, 3), (3, 3));'))
    assert closed != wired and closed != opened


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


def test_a_figure_of_no_family_drawn_as_svg(monkeypatch):
    calls = []

    async def answer(s, images, text, schema, system=None, light=False, **options):
        calls.append(schema.__name__)
        if schema is figures_typst.Kind:
            return schema(family="other")
        return schema(svg=SQUARE)

    monkeypatch.setattr(llm, "_ask_provider", answer)
    svg = asyncio.run(llm.draw_figure(AIConfig(llm="gemini"), "un tableau de valeurs"))
    assert ">A<" in svg and calls == ["Kind", "Drawing"]
