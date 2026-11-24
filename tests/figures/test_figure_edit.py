"""A figure drawn again after a correction starts from what it was drawn from: its Typst, kept
beside its picture and named in its card (picture_source.sources), its family the card's
figure_kind, never sent to Anki. What is asked changes, the rest stays."""

import asyncio

import pytest
from pydantic import ValidationError

from figures.support import TRIANGLE
from notosaurus_core import figure_making, figures_typst, llm, pictures, relay_api
from notosaurus_core.config import AIConfig
from notosaurus_core.models import Card, PictureSource, SourceFile

S = AIConfig(llm="gemini", gemini_api_key="k")


def drawing(monkeypatch, typst: str = TRIANGLE) -> list[str]:
    """The AI draws `typst` (in Typst's geometry family when asked which); the texts it was
    sent, kept."""
    sent = []

    async def answer(s, images, text, schema, *args, **kwargs):
        sent.append(text)
        if schema is figures_typst.Kind:
            return figures_typst.Kind(family="geometry")
        return figures_typst.Figure(typst=typst)

    monkeypatch.setattr("notosaurus_core.ai._ask_provider", answer)
    monkeypatch.setattr(figures_typst, "available", lambda: True)
    return sent


def test_a_figures_typst_kept_and_named_by_its_card(monkeypatch, tmp_path):
    """Drawn in Typst: its Typst in a file beside its picture, named in the card's
    picture_source (no other card's, not in Anki), its family in figure_kind (asked of the AI
    when the card had none: kept, not asked again)."""
    sent = drawing(monkeypatch)
    card = Card(id="c1", front="ABC ?", back="rectangle", figure="Un triangle ABC rectangle en A")
    name = asyncio.run(pictures.figure_or_picture(S, tmp_path, card))
    assert card.figure_kind == "geometry" and len(sent) == 2  # its family asked, then drawn
    assert card.picture_source is not None
    assert card.picture_source.sources == [SourceFile(file=name.replace(".svg", ".typ"))]
    assert pictures.kept_sources(tmp_path, card.picture_source) == [TRIANGLE.strip() + "\n"]
    asyncio.run(pictures.figure_or_picture(S, tmp_path, card, fresh=True))
    assert len(sent) == 3  # its family known now: not asked again


def test_kept_sources_only_ours_and_all_there(tmp_path):
    """Read back only by names of ours, beside the picture; one missing: none (drawn anew)."""
    (tmp_path / "picture-c1-ab12cd34.typ").write_text("#a", encoding="utf-8")

    def origin(*files):
        return PictureSource(source="drawn", engine="typst", sources=[SourceFile(file=f) for f in files])

    assert pictures.kept_sources(tmp_path, origin("picture-c1-ab12cd34.typ")) == ["#a"]
    assert pictures.kept_sources(tmp_path, origin("../lesson.json")) == []
    assert pictures.kept_sources(tmp_path, origin("picture-c1-ab12cd34.typ", "picture-c1-ab12cd34-2.typ")) == []
    assert pictures.kept_sources(tmp_path, None) == []


def test_drawn_again_from_its_typst(monkeypatch):
    """Drawn again after a correction ("in red"): the AI told its Typst as drawn before, to
    change what is asked and keep the rest; drawn before in another family: drawn anew."""
    sent = drawing(monkeypatch)
    asyncio.run(
        figure_making.made_figure(
            S, "Le triangle ABC en rouge", kind="geometry", previous=TRIANGLE, previous_kind="geometry"
        )
    )
    assert TRIANGLE.strip() in sent[-1] and "Start from it" in sent[-1]
    asyncio.run(
        figure_making.made_figure(S, "Le triangle ABC", kind="geometry", previous=TRIANGLE, previous_kind="chart")
    )
    assert TRIANGLE.strip() not in sent[-1]


def test_what_comes_back_never_compiled_itself(monkeypatch):
    """What a figure was drawn from comes back from the app: only text for the AI, as its
    description is, never compiled itself; what the AI writes from it is, as always. Calling a
    function the family has no more (renamed since): the rules of today hold, drawn as they say."""
    sent = drawing(monkeypatch)
    compiled = []
    compile_svg = figures_typst.compile_svg

    def watched(family, body):
        compiled.append(body)
        return compile_svg(family, body)

    monkeypatch.setattr(figures_typst, "compile_svg", watched)
    gone = "#old-triangle((0, 0), (4, 0), (0, 3))"
    made = asyncio.run(
        figure_making.made_figure(S, "Le triangle ABC", kind="geometry", previous=gone, previous_kind="geometry")
    )
    assert gone in sent[-1] and "the rules hold" in sent[-1]
    assert compiled == [TRIANGLE]  # the AI's only
    assert made.engine == "typst" and made.typst == TRIANGLE


def test_kept_source_only_for_typst():
    assert figure_making.kept_source(llm.MadeFigure("<svg/>", "svg", "other", False)) == ""


def _typst_lesson(client) -> tuple[dict, list[dict], dict]:
    """A lesson whose first cards' figures were drawn in Typst, their sources kept (the demo
    draws SVG): the lesson, its cards, and where their figure came from."""
    from app import lessons, storage

    lesson = client.post("/api/extract", data={"prompt": "Le triangle rectangle (géométrie)"}).json()
    cards = client.post(f"/api/lessons/{lesson['id']}/pictures", json={"draw": True}).json()["lesson"]["cards"]
    folder = lessons.existing_folder(lesson["id"]) / "images"
    name = cards[0]["picture"].replace(".svg", ".typ")
    (folder / name).write_text(TRIANGLE, encoding="utf-8")
    origin = {"source": "drawn", "engine": "typst", "sources": [{"file": name}]}
    saved = storage.read_json(folder.parent / "lesson.json")
    for card in saved["cards"][:2]:
        card.update(figure_kind="geometry", picture_source=origin)
    storage.write_json(folder.parent / "lesson.json", saved)
    return lesson, saved["cards"], origin


def _told(monkeypatch) -> list[tuple[list[str], str, str]]:
    """What each figure drawn was given to draw it again from: (previous, its kind, its engine)."""
    from app.routes import pictures as routes

    told = []
    drawn = routes.pictures.figure_or_picture

    async def draw(*args, previous=(), previous_kind="", previous_engine="", **kwargs):
        told.append((list(previous), previous_kind, previous_engine))
        return await drawn(*args, **kwargs)

    monkeypatch.setattr(routes.pictures, "figure_or_picture", draw)
    return told


def test_drawn_again_from_its_sources(client, monkeypatch):
    """ "Draw" a card's figure again: from the sources its card names (none: anew); copied with a
    lesson copied, named after its new card."""
    from app import lessons

    lesson, cards, origin = _typst_lesson(client)
    name = origin["sources"][0]["file"]
    told = _told(monkeypatch)
    first = f"/api/lessons/{lesson['id']}/cards/{cards[0]['id']}/picture/draw"
    assert client.post(first, json={"problem": "C est mal placé"}).status_code == 200  # its own
    second = f"/api/lessons/{lesson['id']}/cards/{cards[2]['id']}/picture/draw"  # none of its own
    assert client.post(second, json={}).status_code == 200
    assert [previous for previous, *_ in told] == [[TRIANGLE], []]

    # Copied for another child: its sources with its picture, named after its new card
    client.put("/api/children", json=[{"id": "mathilde", "name": "Mathilde", "grade": "3e", "decks": "Mathilde::3e"}])
    copy = client.post(f"/api/lessons/{lesson['id']}/copy", json={"child": "mathilde"}).json()
    copied = copy["cards"][1]
    (source,) = copied["picture_source"]["sources"]
    assert source["file"] == copied["picture"].replace(".svg", ".typ") != name
    images = lessons.existing_folder(copy["id"]) / "images"
    assert pictures.kept_sources(images, PictureSource.model_validate(copied["picture_source"])) == [TRIANGLE]


def test_what_comes_back_to_the_relay_bounded():
    """What an app sends back to draw a figure again from: text for the AI, its size and count
    bounded."""
    card = Card(front="a", back="b", figure="un triangle")
    big = "x" * relay_api.MAX_KEPT_FIGURE
    assert relay_api.CardPictureRequest(card=card, previous=[big]).previous == [big]
    for previous in ([big + "x"], ["x"] * 5):
        with pytest.raises(ValidationError):
            relay_api.CardPictureRequest(card=card, previous=previous)


@pytest.mark.parametrize(("engine", "used"), [("typst", True), ("", False), ("mermaid", False)])
def test_drawn_again_only_from_an_engine_it_knows(monkeypatch, engine, used):
    """What an app sends back says its language (previous_engine, the card's
    picture_source.engine): Typst's taken; none, or one a figure isn't drawn again from,
    nothing assumed of it: drawn anew."""
    sent = drawing(monkeypatch)
    card = Card(id="c1", front="ABC ?", back="rectangle", figure="Le triangle ABC", figure_kind="geometry")
    asyncio.run(pictures.card_picture(S, card, previous=[TRIANGLE], previous_kind="geometry", previous_engine=engine))
    assert ("Start from it" in sent[-1]) == used


def test_made_again_from_its_typst_when_its_description_changed(client, monkeypatch):
    """ "📐 Redraw the figure" (/picture/make) with its description changed: drawn again from the
    sources its card names, what is asked changed and the rest kept; the same description, or
    none: drawn anew (another drawing wanted)."""
    lesson, cards, _ = _typst_lesson(client)
    told = _told(monkeypatch)
    make = f"/api/lessons/{lesson['id']}/cards/{cards[0]['id']}/picture/make"
    assert client.post(make, json={"subject": cards[0]["figure"]}).status_code == 200
    assert client.post(make, json={}).status_code == 200
    assert [previous for previous, *_ in told] == [[], []]
    other = f"/api/lessons/{lesson['id']}/cards/{cards[1]['id']}/picture/make"
    assert client.post(other, json={"subject": "Le triangle ABC rectangle en A, en rouge"}).status_code == 200
    assert told[-1] == ([TRIANGLE], "geometry", "typst")


def test_drawn_again_after_a_correction_from_the_figure_it_had(client, monkeypatch):
    """A correction changed a figure's description (its picture and picture_source cleared): the
    page's `previous` (by card id, the figure it had: its source and family) reaches the drawing,
    from its Typst; the other cards drawn anew, a source not ours read as none."""
    from app import lessons, storage

    lesson, cards, origin = _typst_lesson(client)
    folder = lessons.existing_folder(lesson["id"])
    saved = storage.read_json(folder / "lesson.json")
    for card in saved["cards"][:3]:  # as the correction left them
        card.update(picture="", picture_source=None, figure=card["figure"] + " en rouge")
    storage.write_json(folder / "lesson.json", saved)
    told = _told(monkeypatch)
    unknown = {**origin, "sources": [{"file": "../lesson.json"}]}
    previous = {cards[0]["id"]: {"source": origin, "kind": "geometry"}, cards[1]["id"]: {"source": unknown}}
    res = client.post(f"/api/lessons/{lesson['id']}/pictures", json={"previous": previous})
    assert res.status_code == 200
    assert sorted(told) == sorted([([TRIANGLE], "geometry", "typst"), ([], "", "typst"), ([], "", "")])


def test_made_again_after_a_correction_from_the_figure_it_had(client, monkeypatch):
    """ "📐 Redraw the figure" (/picture/make) on a figure a correction changed, not drawn again
    since (its drawing failed): the page's `previous` (the figure it had: its source and family)
    reaches the drawing, from its Typst, its description the same as the card's; none sent (a
    figure drawn since), or a source not ours: drawn anew."""
    from app import lessons, storage

    lesson, cards, origin = _typst_lesson(client)
    folder = lessons.existing_folder(lesson["id"])
    saved = storage.read_json(folder / "lesson.json")
    corrected = saved["cards"][0]
    # As the correction left it
    corrected.update(picture="", picture_source=None, figure=corrected["figure"] + " en rouge")
    storage.write_json(folder / "lesson.json", saved)
    told = _told(monkeypatch)
    make = f"/api/lessons/{lesson['id']}/cards/{cards[0]['id']}/picture/make"
    asked = {"subject": corrected["figure"], "previous": {"source": origin, "kind": "geometry"}}
    assert client.post(make, json=asked).status_code == 200
    assert told[-1] == ([TRIANGLE], "geometry", "typst")
    assert client.post(make, json={"subject": corrected["figure"]}).status_code == 200
    unknown = {"source": {**origin, "sources": [{"file": "../lesson.json"}]}, "kind": "geometry"}
    assert client.post(make, json={"subject": corrected["figure"], "previous": unknown}).status_code == 200
    assert [previous for previous, *_ in told[1:]] == [[], []]
