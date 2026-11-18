"""Figures on cards: drawn by the AI (Typst, else SVG), told what to draw again, checked when
asked, shown, exported; a figure or a picture decided."""

import asyncio
import json
import re

import apkg
import pytest
from helpers import plain_image

from app import lessons
from figures.support import SQUARE, TRIANGLE, rule_example
from notosaurus_core import figures, figures_typst, llm, pictures
from notosaurus_core.config import AIConfig
from notosaurus_core.errors import AppError


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


def test_typst_asked_again_with_its_error_then_used(monkeypatch):
    svg, calls = typst_drawing(monkeypatch, ["#ctz-canvas({ ctz-init(", TRIANGLE])
    assert "<use" in svg  # Typst's, its letter
    assert [c["schema"] for c in calls] == ["Kind", "Figure", "Figure"]
    assert "Typst said:" in calls[2]["text"] and "ctz-init(" in calls[2]["text"]
    # Refused twice (a file's import, then unclosed): the SVG drawing, as before
    svg, calls = typst_drawing(monkeypatch, ['#import "other.typ"', "#ctz-canvas({"])
    assert ">A<" in svg and [c["schema"] for c in calls] == ["Kind", "Figure", "Figure", "Drawing"]
    assert "no import" in calls[2]["text"]


def test_the_typst_refused_kept_for_who_asks(monkeypatch):
    """A figure drawn as SVG (Typst refused twice) said nothing of why: the figure bench saw a
    secant's curve drawn wrong as SVG, its Typst gone. Each refused Typst, with what Typst
    said, kept for whoever sets `refusals` (the bench); nobody setting it, nothing kept."""
    from notosaurus_core import figure_making

    kept: list[dict] = []
    token = figure_making.refusals.set(kept)
    try:
        typst_drawing(monkeypatch, ['#import "other.typ"', "#ctz-canvas({"])
    finally:
        figure_making.refusals.reset(token)
    assert [k["typst"] for k in kept] == ['#import "other.typ"', "#ctz-canvas({"]
    assert "no import" in kept[0]["said"] and kept[1]["said"] and kept[0]["family"] == "geometry"
    typst_drawing(monkeypatch, ['#import "other.typ"', "#ctz-canvas({"])
    assert figure_making.refusals.get() is None


def test_a_drawing_too_large_said_so_to_the_ai():
    """Typst's drawing refused for its size was told to the AI as "its SVG was unusable": it
    wrote the same again, then the figure went to SVG. Its size and what makes one so large
    are said."""
    from notosaurus_core import figure_making

    with pytest.raises(figures.FigureError) as e:
        figures.clean("<svg>" + " " * figures.MAX_SIZE + "</svg>")
    said = figure_making._unusable_svg(e.value)
    assert str(figures.MAX_SIZE + 11) in said and "marks" in said
    assert figure_making._unusable_svg(figures.FigureError("figure.invalid")) == "its SVG was unusable"


def test_typst_drawing_nothing_asked_again_then_drawn_as_svg(monkeypatch):
    """An empty answer (a map of what its atlas lacks: the AI leaves it all out) compiles
    to a blank page: refused, asked again, then drawn as SVG, never a blank card."""
    for blank in ("", "#diagram()", "#ctz-canvas({ ctz-init() })"):
        with pytest.raises(figures_typst.Unusable, match="nothing"):
            figures_typst.compile_svg("diagram" if "diagram" in blank else "geometry", blank)
    svg, calls = typst_drawing(monkeypatch, ["", ""])
    assert ">A<" in svg and [c["schema"] for c in calls] == ["Kind", "Figure", "Figure", "Drawing"]
    assert "draws nothing" in calls[2]["text"]


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


TUBES = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200" width="400" height="200">
<rect x="70" y="60" width="20" height="100" fill="none" stroke="black"/>
<rect x="190" y="60" width="20" height="100" fill="none" stroke="black"/>
<rect x="310" y="60" width="20" height="100" fill="none" stroke="black"/>
<text x="80" y="40" font-size="14" text-anchor="middle">Cu²⁺ + soude</text>
<text x="200" y="40" font-size="14" text-anchor="middle">Fe²⁺ + soude</text>
<text x="{x}" y="40" font-size="14" text-anchor="middle">Cl⁻ + nitrate d'argent</text>
</svg>"""
SCALE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 60" width="300" height="60">
<line x1="10" y1="20" x2="290" y2="20" stroke="black"/>
"""
SCALE += "".join(f'<text x="{20 + 18 * n}" y="40" font-size="12" text-anchor="middle">{n}</text>' for n in range(15))
SCALE += "</svg>"


def test_labels_written_on_one_another_found():
    """The tubes' labels centred 120 px apart, one 150 px wide: on « Fe²⁺ + soude » (« soudeCl⁻ »),
    or so close beside it that they read as one phrase; 160 px apart, clear. A scale's numbers
    close together, or a word's letters coloured one by one, never phrases: not found."""
    from notosaurus_core import figures

    pair = [("Fe²⁺ + soude", "Cl⁻ + nitrate d'argent")]
    assert figures.touching_labels(TUBES.format(x=310)) == pair  # on it
    assert figures.touching_labels(TUBES.format(x=325)) == pair  # a space's width apart
    assert figures.touching_labels(TUBES.format(x=360)) == []
    assert figures.touching_labels(SCALE) == []


def test_a_figures_labels_on_one_another_drawn_again_told_which(monkeypatch):
    """SVG with labels touching: drawn once again, told which, the new one kept when fewer
    touch and none is left out; else the first."""

    def drawn(second):
        calls = []

        async def answer(s, images, text, schema, system=None, light=False, **options):
            calls.append(text)
            return schema(svg=TUBES.format(x=310) if len(calls) == 1 else second)

        monkeypatch.setattr("notosaurus_core.ai._ask_provider", answer)
        monkeypatch.setattr(figures_typst, "available", lambda: False)
        svg = asyncio.run(llm.draw_figure(AIConfig(llm="gemini"), "trois tubes à essais"))
        return svg, calls

    svg, calls = drawn(TUBES.format(x=360))
    assert len(calls) == 2 and "« Fe²⁺ + soude » (drawn from x = " in calls[1]
    assert re.search(r"« Cl⁻ \+ nitrate d'argent » \(drawn from x = 2\d\d to x = 3\d\d, 1\d\d wide\)", calls[1])
    assert 'x="360"' in svg
    svg, calls = drawn(TUBES.format(x=312))  # no better: the first kept
    assert len(calls) == 2 and 'x="310"' in svg
    # A label left out (the tubes' reagents dropped to make room): the first kept
    svg, calls = drawn(TUBES.format(x=360).replace("Cu²⁺ + soude", ""))
    assert len(calls) == 2 and 'x="310"' in svg
    svg, calls = drawing_with(monkeypatch)  # nothing touching: one call
    assert len(calls) == 1


CELL = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"><rect width="400" height="300" fill="white"/>
<ellipse cx="200" cy="150" rx="150" ry="110" fill="#ffdde8" stroke="black" stroke-width="2"/>
<circle cx="210" cy="140" r="40" fill="#ccccee" stroke="black"/>
<ellipse cx="120" cy="190" rx="25" ry="12" fill="#ffcc99" stroke="black"/></svg>"""
# a near point under a far one on the same side: their leaders would cross in the points' order
CELL_NAMES = [
    ("Membrane plasmique", 340, 110),
    ("Mitochondrie", 120, 190),
    ("Réticulum endoplasmique rugueux", 260, 100),
    ("Paroi", 322, 215),  # on the cell's outline
    ("Noyau", 210, 222),
    ("Vacuole", 300, 230),
    ("Plaste", 250, 240),
]


def _placed(svg):
    """The labels set (their texts' boxes) and their leaders, read back from the SVG."""
    from xml.etree import ElementTree

    from notosaurus_core import figures

    root = ElementTree.fromstring(svg)
    ns = "{http://www.w3.org/2000/svg}"
    texts = [t for t in root.iter(f"{ns}text")]
    lines = [tuple(float(line.get(k)) for k in ("x1", "y1", "x2", "y2")) for line in root.iter(f"{ns}line")]
    boxes = []
    for t in texts:
        x, y, w = float(t.get("x")), float(t.get("y")), figures._measure(t.text)
        x0 = x - w if t.get("text-anchor") == "end" else x
        boxes.append((x0, y - figures.LABEL_SIZE, x0 + w, y + 3))
    return boxes, lines


def test_a_schemes_labels_set_in_columns_beside_it():
    """A cell drawn by the AI, its names written by eye on its membrane ("Noyau" across it,
    2 drawings in 3): the AI gives each name's point, the names are set in columns outside the
    drawing, none on another, their leaders never crossing, each ending at its point."""
    from notosaurus_core import figures

    names = [figures.Label(text=t, x=x, y=y) for t, x, y in CELL_NAMES]
    svg = figures.labelled(figures.clean(CELL), names)
    boxes, lines = _placed(svg)
    assert len(lines) == len(names)
    for x0, _, x1, _ in boxes:  # beside the cell (its ink from x = 50 to 350)
        assert x1 < 50 or x0 > 350, (x0, x1)
    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:
            assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1], (a, b)
    for i, (ax1, ay1, ax2, ay2) in enumerate(lines):
        for bx1, by1, bx2, by2 in lines[i + 1 :]:
            assert not figures._cross((ax1, ay1), (ax2, ay2), (bx1, by1), (bx2, by2))
    assert sorted((x2, y2) for _, _, x2, y2 in lines) == sorted((float(x), float(y)) for _, x, y in CELL_NAMES)
    assert ">Réticulum<" in svg or ">Réticulum endoplasmique<" in svg  # a long name on two lines
    assert "rugueux</text>" in svg and "Réticulum endoplasmique rugueux" not in svg
    assert figures.touching_labels(svg) == []  # nothing for #590's check to draw again


def test_a_drawing_without_labels_unchanged_a_label_outside_it_refused():
    from notosaurus_core import figures

    svg = figures.clean(CELL)
    assert figures.labelled(svg, []) == svg
    with pytest.raises(figures.LabelError, match="« Noyau » names the point"):
        figures.labelled(svg, [figures.Label(text="Noyau", x=520, y=140)])
    clamped = figures.labelled(svg, [figures.Label(text="Noyau", x=520, y=140)], clamp=True)
    assert _placed(clamped)[1][0][2:] == (400.0, 140.0)


def test_a_labels_point_outside_asked_again_then_brought_to_the_edge(monkeypatch):
    """A label's point outside the drawing: the AI asked again, told which; still so, the point
    brought to the drawing's edge, the label kept."""
    calls = []

    async def answer(s, images, text, schema, system=None, light=False, **options):
        calls.append(text)
        if schema is figures_typst.Kind:
            return schema(family="other")
        return schema(svg=CELL, labels=[{"text": "Noyau", "x": 520, "y": 140}])

    monkeypatch.setattr("notosaurus_core.ai._ask_provider", answer)
    svg = asyncio.run(llm.draw_figure(AIConfig(llm="gemini"), "une cellule et son noyau"))
    assert "« Noyau » names the point (520, 140)" in calls[-1] and ">Noyau<" in svg


def test_the_ais_svg_drawing_kept_for_who_asks(monkeypatch):
    """A change to how labels are placed was judged on new drawings only, the AI drawing each
    its own way: the AI's SVG drawing, its labels and their points, kept for whoever sets
    `answers` (the bench, to label the same drawings again), with what the app made of it."""
    from notosaurus_core import figure_making

    async def answer(s, images, text, schema, system=None, light=False, **options):
        if schema is figures_typst.Kind:
            return schema(family="other")
        return schema(svg=CELL, labels=[{"text": "Noyau", "x": 210, "y": 222}])

    monkeypatch.setattr("notosaurus_core.ai._ask_provider", answer)
    kept: list[dict] = []
    token = figure_making.answers.set(kept)
    try:
        svg = asyncio.run(llm.draw_figure(AIConfig(llm="gemini"), "une cellule et son noyau"))
    finally:
        figure_making.answers.reset(token)
    assert [k["drawing"]["labels"] for k in kept] == [[{"text": "Noyau", "x": 210, "y": 222}]]
    assert kept[0]["drawing"]["svg"] == CELL and kept[0]["svg"] == svg and kept[0]["clamp"] is False
    asyncio.run(llm.draw_figure(AIConfig(llm="gemini"), "une cellule et son noyau"))
    assert figure_making.answers.get() is None


def test_a_name_for_several_parts_set_once_a_line_to_each():
    """A gene's place on both chromosomes of a pair, one name: given at each point, set once
    with a line to each (a single point between them named nothing, 3 drawings in 3)."""
    from notosaurus_core import figures

    pair = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"><rect width="400" height="300" fill="white"/>'
        '<rect x="140" y="40" width="30" height="220" rx="12" fill="#dde" stroke="black"/>'
        '<rect x="230" y="40" width="30" height="220" rx="12" fill="#dde" stroke="black"/></svg>'
    )
    gene = "gène du groupe sanguin"
    svg = figures.labelled(
        figures.clean(pair),
        [
            figures.Label(text="allèle A", x=155, y=90),
            figures.Label(text=gene, x=155, y=95),
            figures.Label(text=gene, x=245, y=95),
            figures.Label(text="allèle O", x=245, y=90),
        ],
    )
    _, lines = _placed(svg)
    assert svg.count(">gène du groupe<") + svg.count(f">{gene}<") == 1
    assert len(lines) == 4 and {(x2, y2) for _, _, x2, y2 in lines} >= {(155.0, 95.0), (245.0, 95.0)}
    for i, (ax1, ay1, ax2, ay2) in enumerate(lines):
        for bx1, by1, bx2, by2 in lines[i + 1 :]:
            assert not figures._cross((ax1, ay1), (ax2, ay2), (bx1, by1), (bx2, by2))


FUNNEL = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"><rect width="400" height="300" fill="white"/>'
    '<polygon points="100,60 220,60 160,160" fill="none" stroke="black" stroke-width="3"/></svg>'
)


def test_a_point_beside_its_part_brought_onto_it():
    """The AI's point for « entonnoir » just beside the funnel's edge, on the white ground
    (2 drawings in 3): its line ended in the void. Brought onto the drawing; a point farther
    from any line (a region drawn white) kept."""
    from notosaurus_core import figures

    svg = figures.labelled(figures.clean(FUNNEL), [figures.Label(text="entonnoir", x=200, y=110)])
    (_, _, x2, y2), *_ = _placed(svg)[1]
    assert abs(x2 - 192) < 4 and abs(y2 - 105) < 6, (x2, y2)  # on the funnel's right edge
    kept = figures.labelled(figures.clean(FUNNEL), [figures.Label(text="air", x=300, y=250)])
    assert _placed(kept)[1][0][2:] == (300.0, 250.0)


# an antibody's arm drawn rotated: the AI gives its points as if it were not (45 units off it)
ARM = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"><rect width="400" height="300" fill="white"/>
<g transform="rotate(35, 200, 200)">
<rect x="194" y="60" width="12" height="140" fill="#4A90E2" stroke="black"/></g></svg>"""


def test_a_point_off_a_rotated_part_brought_onto_it():
    """« chaîne légère » named a point 25 to 47 units beside the antibody's arm, on the open
    ground (the arm drawn rotated, the point given as if it were not): 3 drawings in 3, its line
    ended in the void. A point on the open ground this near a line brought onto it; one far from
    any (the air around a funnel) kept."""
    from notosaurus_core import figures

    svg = figures.labelled(figures.clean(ARM), [figures.Label(text="chaîne légère", x=300, y=150)])
    (_, _, x2, y2), *_ = _placed(svg)[1]
    image = figures._drawn_image(figures.clean(ARM))
    k = image.width / 400
    assert image.getpixel((round(x2 * k), round(y2 * k))) < 248, (x2, y2)  # on the arm
    kept = figures.labelled(figures.clean(FUNNEL), [figures.Label(text="air", x=300, y=250)])
    assert _placed(kept)[1][0][2:] == (300.0, 250.0)


# two membranes face to face, open at both ends: the synaptic cleft between them
CLEFT = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"><rect width="400" height="300" fill="white"/>'
    '<rect x="100" y="90" width="200" height="20" fill="#f4c27a" stroke="black"/>'
    '<rect x="100" y="150" width="200" height="20" fill="#9ccbe8" stroke="black"/></svg>'
)


def test_a_point_between_two_shapes_kept_in_the_gap():
    """« fente synaptique » named the gap between two membranes, open at its ends (reached
    from the frame through white, as the open ground is): lines on both sides of it, it is a
    region, kept there, never pulled onto a membrane as a point beside a part is."""
    from notosaurus_core import figures

    svg = figures.labelled(figures.clean(CLEFT), [figures.Label(text="fente synaptique", x=200, y=130)])
    assert _placed(svg)[1][0][2:] == (200.0, 130.0)


# a cell drawn white, its outline closing it in
WHITE_CELL = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"><rect width="400" height="300" fill="white"/>'
    '<circle cx="200" cy="150" r="80" fill="white" stroke="black" stroke-width="2"/></svg>'
)


def test_a_point_in_a_region_closed_in_kept():
    """« cytoplasme » named a point inside the cell, 40 units from its outline, the cell drawn
    white: closed in by lines (the frame's white never reaches it), a region kept, never
    pulled onto the outline as a point on the open ground this near a line is."""
    from notosaurus_core import figures

    svg = figures.labelled(figures.clean(WHITE_CELL), [figures.Label(text="cytoplasme", x=200, y=110)])
    assert _placed(svg)[1][0][2:] == (200.0, 110.0)


def test_a_column_beyond_a_point_past_the_drawing():
    """A region's point past the drawing's ink (the cytoplasm, white, right of the shapes): the
    column set beyond it, its line never drawn back across its name."""
    from notosaurus_core import figures

    svg = figures.labelled(figures.clean(FUNNEL), [figures.Label(text="cytoplasme", x=330, y=110)])
    boxes, ((x1, _, x2, _),) = _placed(svg)
    assert boxes[0][0] > 330 and x1 > x2


def test_a_diagram_too_small_to_read_drawn_again_the_more_readable_kept(monkeypatch):
    """A diagram too small to read on a card (figures_typst.TooSmall): drawn again, told its
    text's size; still too small, the more readable of the two kept, never one drawn as SVG
    instead (its texts a guess, its arrows placed by eye)."""

    def row(n: int) -> str:
        step = 'node(({i}, 0), [Une étape numéro {i} du long processus]), edge("-|>", [vers la suivante])'
        return "#diagram(" + ", ".join(step.format(i=i) for i in range(n)) + f", node(({n}, 0), [Fin]))"

    svg, calls = typst_drawing(monkeypatch, [row(7), row(5)], kind="diagram")
    assert [c["schema"] for c in calls] == ["Figure", "Figure"]
    assert "px high" in calls[1]["text"] and "#scheme" in calls[1]["text"]
    assert "<use" in svg  # Typst's
    width = lambda svg: float(re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+)', svg).group(1))  # noqa: E731
    assert width(svg) == pytest.approx(width(_compiled_anyway(row(5))), rel=0.01)


def _compiled_anyway(body: str) -> str:
    try:
        return figures_typst.compile_svg("diagram", body)
    except figures_typst.TooSmall as e:
        return e.svg


CIRCUIT = rule_example("circuit")


def panels_drawing(monkeypatch, split):
    """A figure in panels drawn by a fake AI: its kind "panels", split as `split` says (a list
    of (family, description), or an unusable answer), a circuit's Typst and a triangle's; the
    figure made and the calls, in order."""
    calls = []

    async def answer(s, images, text, schema, system=None, light=False, **options):
        calls.append((schema.__name__, text))
        if schema is figures_typst.Kind:
            return schema(family="panels")
        if schema is figures_typst.Panels:
            if split is None:
                raise llm.ExtractionError("llm.invalid_answer")
            return schema(panels=[figures_typst.Panel(family=f, description=d) for f, d in split])
        if schema is figures_typst.Figure:
            return schema(typst=CIRCUIT if "circuit" in text else TRIANGLE)
        return schema(svg=SQUARE)

    monkeypatch.setattr("notosaurus_core.ai._ask_provider", answer)
    description = "un circuit RC et, à côté, un triangle"
    made = asyncio.run(llm.made_figure(AIConfig(llm="gemini"), description))
    return made, calls


def test_a_figure_of_two_kinds_drawn_in_panels(monkeypatch):
    """A capacitor's charge: its circuit and the curve of its voltage, two kinds in one figure,
    drawn in one family (the curve placed by eye in the circuit's, or left out: 1/3). Split
    into its panels, each drawn by its own kind, set side by side; credited to each one's
    packages."""
    split = [("circuit", "le circuit RC"), ("geometry", "un triangle ABC")]
    made, calls = panels_drawing(monkeypatch, split)
    assert [c[0] for c in calls[:2]] == ["Kind", "Panels"]
    assert sorted(c[1].split(": ", 1)[1] for c in calls[2:]) == ["le circuit RC", "un triangle ABC"]
    assert (made.family, made.engine) == ("panels", "typst")
    assert [p.family for p in made.panels] == ["circuit", "geometry"]
    width, height = (float(v) for v in re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', made.svg).groups())
    assert width > 1.5 * height  # side by side
    credited = llm.figure_credits(made)
    assert any(c.startswith("zap ") for c in credited) and any(c.startswith("ctz-euclide ") for c in credited)


def test_a_figure_not_split_drawn_as_one(monkeypatch):
    """Its panels unusable, or one only: the figure drawn as one, in SVG."""
    for split in (None, [("circuit", "le circuit RC")]):
        made, calls = panels_drawing(monkeypatch, split)
        assert (made.family, made.engine, made.panels) == ("other", "svg", ())
        assert [c[0] for c in calls] == ["Kind", "Panels", "Drawing"]


def test_panels_keep_their_own_ids():
    """Two drawings set side by side: an id they share (Typst names its glyphs alike) kept apart,
    each reference following its own; each panel as tall as the tallest."""
    drawn = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 {}">'
        '<defs><path id="g" d="M0 0h{}"/></defs><use href="#g"/></svg>'
    )
    both = figures.side_by_side([drawn.format(50, 1), drawn.format(100, 2)])
    assert sorted(re.findall(r'\bid="([^"]+)"', both)) == ["p0-g", "p1-g"]
    assert sorted(re.findall(r'href="#([^"]+)"', both)) == ["p0-g", "p1-g"]
    assert 'viewBox="0 0 308 100"' in both  # 100 × 2 (as tall as the other), a gap of 8, then 100


def test_figures_in_panels_are_a_kind():
    """The kinds say when a figure goes in panels (things of different kinds together), and a
    panel is never in panels itself."""
    kinds = dict(re.findall(r'"(\w+)": (.*?)(?=; "\w+": |$)', figures_typst.KINDS))
    assert "panels" in kinds and "panels" in figures_typst.FigureKind.__args__
    with pytest.raises(ValueError):
        figures_typst.Panel(family="panels", description="x")  # type: ignore[arg-type]
