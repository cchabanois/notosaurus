"""A figure drawn again after a correction starts from what it was drawn from (its Typst,
kept beside its picture as {"engine", "family", "source"}, never sent to Anki): what is asked
changes, the rest stays."""

import asyncio
import json

from figures.support import TRIANGLE
from notosaurus_core import figure_making, figures_typst, llm, pictures
from notosaurus_core.config import AIConfig
from notosaurus_core.models import Card


def kept(source: str, family: str = "geometry", engine: str = "typst") -> str:
    return json.dumps({"engine": engine, "family": family, "source": source.strip()}, ensure_ascii=False)


S = AIConfig(llm="gemini", gemini_api_key="k")


def drawing(monkeypatch, typst: str = TRIANGLE) -> list[str]:
    """The AI draws `typst` (in Typst's geometry family); the texts it was sent, kept."""
    sent = []

    async def answer(s, images, text, schema, *args, **kwargs):
        sent.append(text)
        return figures_typst.Figure(typst=typst)

    monkeypatch.setattr("notosaurus_core.ai._ask_provider", answer)
    monkeypatch.setattr(figures_typst, "available", lambda: True)
    return sent


def test_a_figures_typst_kept_beside_it(monkeypatch, tmp_path):
    """Drawn in Typst: its family and its Typst in a file beside its picture, which no card
    names (not in Anki); drawn as SVG: nothing kept."""
    drawing(monkeypatch)
    card = Card(
        id="c1", front="ABC ?", back="rectangle", figure="Un triangle ABC rectangle en A", figure_kind="geometry"
    )
    name = asyncio.run(pictures.figure_or_picture(S, tmp_path, card))
    assert json.loads(pictures.kept_figure(tmp_path, name)) == {
        "engine": "typst",
        "family": "geometry",
        "source": TRIANGLE.strip(),
    }
    assert pictures.kept_path(tmp_path, name).name == name.replace(".svg", ".source.json")
    assert pictures.kept_figure(tmp_path, "../" + name) == ""  # only our pictures' names


def test_drawn_again_from_its_typst(monkeypatch):
    """Drawn again after a correction ("in red"): the AI told its Typst as drawn before, to
    change what is asked and keep the rest; another family by now: drawn anew."""
    sent = drawing(monkeypatch)
    asyncio.run(figure_making.made_figure(S, "Le triangle ABC en rouge", kind="geometry", previous=kept(TRIANGLE)))
    assert TRIANGLE.strip() in sent[-1] and "Start from it" in sent[-1] and "no longer compiles" not in sent[-1]
    for other in (kept(TRIANGLE, family="chart"), kept(TRIANGLE, engine="mermaid")):  # another family, engine
        asyncio.run(figure_making.made_figure(S, "Le triangle ABC", kind="geometry", previous=other))
        assert TRIANGLE.strip() not in sent[-1]
    asyncio.run(figure_making.made_figure(S, "Le triangle ABC", kind="geometry", previous="not ours"))
    assert "Start from it" not in sent[-1]


def test_drawn_again_from_typst_whose_functions_are_gone(monkeypatch):
    """Its Typst calls a function the family has no more (renamed since): still told, with
    what Typst says, the rules of today holding; drawn as they say."""
    sent = drawing(monkeypatch)
    gone = "#old-triangle((0, 0), (4, 0), (0, 3))"
    made = asyncio.run(figure_making.made_figure(S, "Le triangle ABC", kind="geometry", previous=kept(gone)))
    assert gone in sent[-1] and "no longer compiles" in sent[-1] and "old-triangle" in sent[-1].split("Typst said:")[1]
    assert made.engine == "typst" and made.typst == TRIANGLE  # drawn with today's


def test_kept_source_only_for_typst():
    made = llm.MadeFigure("<svg/>", "svg", "other", False)
    assert figure_making.kept_source(made) == ""


def test_drawn_again_from_the_picture_it_had(client, monkeypatch):
    """ "Draw" a card's figure again: from the Typst kept beside its picture, or beside the
    one it had before a correction cleared it (`previous`); copied with a lesson copied."""
    from app import lessons
    from app.routes import pictures as routes

    lesson = client.post("/api/extract", data={"prompt": "Le triangle rectangle (géométrie)"}).json()
    cards = client.post(f"/api/lessons/{lesson['id']}/pictures", json={"draw": True}).json()["lesson"]["cards"]
    card = cards[0]
    folder = lessons.existing_folder(lesson["id"]) / "images"
    saved = kept(TRIANGLE)
    pictures.kept_path(folder, card["picture"]).write_text(saved, encoding="utf-8")
    told = []
    drawn = routes.pictures.figure_or_picture

    async def draw(*args, previous="", **kwargs):
        told.append(previous)
        return await drawn(*args, **kwargs)

    monkeypatch.setattr(routes.pictures, "figure_or_picture", draw)
    path = f"/api/lessons/{lesson['id']}/cards/{card['id']}/picture/draw"
    for asked in ({"problem": "C est mal placé"}, {"previous": card["picture"]}, {"previous": "../secret.svg"}):
        pictures.kept_path(folder, card["picture"]).write_text(saved, encoding="utf-8")
        assert client.post(path, json=asked).status_code == 200
    assert told == [saved, saved, ""]  # its own, the one it had, none (not ours)

    # Drawn again as SVG (the demo's): nothing kept for it. Copied for another child: a
    # figure's Typst with its picture
    assert pictures.kept_figure(folder, card["picture"]) == ""
    pictures.kept_path(folder, cards[1]["picture"]).write_text(saved, encoding="utf-8")
    client.put("/api/children", json=[{"id": "mathilde", "name": "Mathilde", "grade": "3e", "decks": "Mathilde::3e"}])
    copy = client.post(f"/api/lessons/{lesson['id']}/copy", json={"child": "mathilde"}).json()
    picture = copy["cards"][1]["picture"]
    assert pictures.kept_figure(lessons.existing_folder(copy["id"]) / "images", picture) == saved


def test_what_comes_back_to_the_relay_bounded():
    """The Typst an app sends back to draw a figure again from: taken as it comes (compiled
    with the guards the AI's Typst has), its size bounded."""
    import pytest
    from pydantic import ValidationError

    from notosaurus_core import relay_api

    card = Card(front="a", back="b", figure="un triangle")
    assert relay_api.CardPictureRequest(card=card, previous="x" * relay_api.MAX_KEPT_FIGURE).previous
    with pytest.raises(ValidationError):
        relay_api.CardPictureRequest(card=card, previous="x" * (relay_api.MAX_KEPT_FIGURE + 1))
