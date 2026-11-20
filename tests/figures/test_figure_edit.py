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
    assert TRIANGLE.strip() in sent[-1] and "Start from it" in sent[-1] and "no longer compiles" not in sent[-1]
    asyncio.run(
        figure_making.made_figure(S, "Le triangle ABC", kind="geometry", previous=TRIANGLE, previous_kind="chart")
    )
    assert TRIANGLE.strip() not in sent[-1]


def test_drawn_again_from_typst_whose_functions_are_gone(monkeypatch):
    """Its Typst calls a function the family has no more (renamed since): still told, with
    what Typst says, the rules of today holding; drawn as they say."""
    sent = drawing(monkeypatch)
    gone = "#old-triangle((0, 0), (4, 0), (0, 3))"
    made = asyncio.run(
        figure_making.made_figure(S, "Le triangle ABC", kind="geometry", previous=gone, previous_kind="geometry")
    )
    assert gone in sent[-1] and "no longer compiles" in sent[-1] and "old-triangle" in sent[-1].split("Typst said:")[1]
    assert made.engine == "typst" and made.typst == TRIANGLE  # drawn with today's


def test_kept_source_only_for_typst():
    assert figure_making.kept_source(llm.MadeFigure("<svg/>", "svg", "other", False)) == ""


def test_drawn_again_from_its_sources_or_those_it_had(client, monkeypatch):
    """ "Draw" a card's figure again: from the sources its card names, or those of the figure
    it had before a correction cleared it (`previous_source`, its family `previous_kind`);
    copied with a lesson copied, named after its new card."""
    from app import lessons, storage
    from app.routes import pictures as routes

    lesson = client.post("/api/extract", data={"prompt": "Le triangle rectangle (géométrie)"}).json()
    cards = client.post(f"/api/lessons/{lesson['id']}/pictures", json={"draw": True}).json()["lesson"]["cards"]
    folder = lessons.existing_folder(lesson["id"]) / "images"
    name = cards[0]["picture"].replace(".svg", ".typ")
    (folder / name).write_text(TRIANGLE, encoding="utf-8")
    origin = {"source": "drawn", "engine": "typst", "sources": [{"file": name}]}
    saved = storage.read_json(folder.parent / "lesson.json")  # drawn in Typst before (the demo draws SVG)
    for card in saved["cards"][:2]:
        card.update(figure_kind="geometry", picture_source=origin)
    storage.write_json(folder.parent / "lesson.json", saved)
    told = []
    drawn = routes.pictures.figure_or_picture

    async def draw(*args, previous=(), previous_kind="", **kwargs):
        told.append((list(previous), previous_kind))
        return await drawn(*args, **kwargs)

    monkeypatch.setattr(routes.pictures, "figure_or_picture", draw)
    first = f"/api/lessons/{lesson['id']}/cards/{cards[0]['id']}/picture/draw"
    assert client.post(first, json={"problem": "C est mal placé"}).status_code == 200  # its own
    second = f"/api/lessons/{lesson['id']}/cards/{cards[2]['id']}/picture/draw"  # none of its own
    assert client.post(second, json={"previous_source": origin, "previous_kind": "geometry"}).status_code == 200
    unknown = {**origin, "sources": [{"file": "../lesson.json"}]}
    assert client.post(second, json={"previous_source": unknown, "previous_kind": "geometry"}).status_code == 200
    assert told == [([TRIANGLE], "geometry"), ([TRIANGLE], "geometry"), ([], "geometry")]

    # Copied for another child: its sources with its picture, named after its new card
    client.put("/api/children", json=[{"id": "mathilde", "name": "Mathilde", "grade": "3e", "decks": "Mathilde::3e"}])
    copy = client.post(f"/api/lessons/{lesson['id']}/copy", json={"child": "mathilde"}).json()
    copied = copy["cards"][1]
    (source,) = copied["picture_source"]["sources"]
    assert source["file"] == copied["picture"].replace(".svg", ".typ") != name
    images = lessons.existing_folder(copy["id"]) / "images"
    assert pictures.kept_sources(images, PictureSource.model_validate(copied["picture_source"])) == [TRIANGLE]


def test_what_comes_back_to_the_relay_bounded():
    """What an app sends back to draw a figure again from: taken as it comes (compiled with
    the guards the AI's Typst has), its size and count bounded."""
    card = Card(front="a", back="b", figure="un triangle")
    big = "x" * relay_api.MAX_KEPT_FIGURE
    assert relay_api.CardPictureRequest(card=card, previous=[big]).previous == [big]
    for previous in ([big + "x"], ["x"] * 5):
        with pytest.raises(ValidationError):
            relay_api.CardPictureRequest(card=card, previous=previous)
