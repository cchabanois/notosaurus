"""One card corrected on its own (llm.fix_card): the AI writes that card alone; it stays
the same card (its id, its diagram label), its picture kept unless what to draw changed."""

import asyncio

import pytest

from notosaurus_core import llm
from notosaurus_core.config import AIConfig
from notosaurus_core.models import Card, Deck, Mask, PictureSource, SourceFile

S = AIConfig(llm="gemini", gemini_api_key="k")


def answering(monkeypatch, *cards: dict, refused: bool = False) -> list[str]:
    """The AI answers these cards; the texts it was sent, kept."""
    sent = []

    async def answer(s, images, text, schema, *args, **kwargs):
        sent.append(text)
        return schema.model_validate({"cards": list(cards), "summary": "<b>Date</b> fixed", "refused": refused})

    monkeypatch.setattr("notosaurus_core.ai._ask_provider", answer)
    return sent


def fix(card: Card, instruction: str = "the answer is 1789", others=("When did Louis XVI die?",)):
    return asyncio.run(llm.fix_card(S, [], "History, lesson 3", "History", card, instruction, others, "French"))


def test_the_card_corrected_as_asked(monkeypatch):
    sent = answering(monkeypatch, {"front": "The storming of the Bastille?", "back": "**1789**"})
    card = Card(id="c1", front="The storming of the Bastille?", back="1792")
    fixed = fix(card)
    assert (fixed.card.id, fixed.card.back, fixed.summary) == ("c1", "[1789]", "[Date] fixed")  # plain text
    (text,) = sent
    assert "the answer is 1789" in text and "- When did Louis XVI die?" in text and '"1792"' in text
    assert '"c1"' not in text  # its id: Notosaurus's, not the AI's


def test_it_stays_the_same_card(monkeypatch):
    """Its diagram label and its picture stay, whatever the AI wrote of them."""
    mask = Mask(page=1, n=2, box=[0.1, 0.1, 0.2, 0.2])
    answering(monkeypatch, {"front": "What is (2)? (the organ)", "back": "the heart"})
    card = Card(id="c2", front="What is (2)?", back="the hart", mask=mask, picture="p.jpg", picture_prompt="a heart")
    card.voice = "en-GB-Chirp3-HD-Aoede"  # its sound's, made on the phone
    fixed = fix(card, "the spelling of heart").card
    assert (fixed.id, fixed.mask, fixed.picture, fixed.picture_prompt) == ("c2", mask, "p.jpg", "a heart")
    assert fixed.voice == card.voice


COMMONS = PictureSource(
    source="commons", licence="CC BY-SA 4.0", title="Heart", page="https://commons.wikimedia.org/wiki/File:Heart.jpg"
)


def test_a_picture_kept_with_where_it_comes_from(monkeypatch):
    """Its text corrected, its picture kept: where it comes from too (a free picture's
    licence and page, its Anki note's Source), never written by the AI."""
    answering(monkeypatch, {"front": "What is this organ?", "back": "the heart", "picture_prompt": "a heart"})
    card = Card(id="c2", front="What is this organ?", back="the hart", picture="p.jpg", picture_prompt="a heart")
    card.picture_source = COMMONS
    assert fix(card, "the spelling of heart").card.picture_source == COMMONS
    answering(monkeypatch, {"front": "What is this organ?", "back": "the heart", "picture_prompt": "a lung"})
    fixed = fix(card, "it is a lung").card
    assert (fixed.picture, fixed.picture_source) == ("", None)  # what to draw changed: found again


def test_a_lesson_corrected_keeps_where_its_pictures_come_from(monkeypatch):
    """The lesson's correction: a card kept keeps its picture's source."""
    seeing(monkeypatch, {"deck": "Biology", "cards": [{"front": "What is this organ?", "back": "the heart"}]})
    card = Card(id="c2", front="What is this organ?", back="the hart", picture="p.jpg", picture_prompt="a heart")
    card.picture_source = COMMONS
    deck = Deck(deck="Biology", cards=[card])
    revised = asyncio.run(llm.revise_cards(S, [], "Biology", deck, "the spelling of heart", "French"))
    assert [(c.id, c.picture, c.picture_source) for c in revised.cards] == [("c2", "p.jpg", COMMONS)]


def test_a_figure_corrected_is_drawn_again(monkeypatch):
    answering(monkeypatch, {"front": "ABC?", "back": "right-angled", "figure": "ABC, right-angled at B"})
    card = Card(id="c3", front="ABC?", back="right-angled", figure="ABC, right-angled at A", picture="f.svg")
    fixed = fix(card, "the right angle is at B").card
    assert (fixed.figure, fixed.picture) == ("ABC, right-angled at B", "")  # to draw again


def test_a_card_just_added_written(monkeypatch):
    """Still empty (just added): asked to write it from the lesson, not to correct it."""
    sent = answering(monkeypatch, {"front": "Le passé composé d'aller ?", "back": "je suis allé"})
    fixed = fix(Card(id="new", front="", back=""), "le passé composé d'aller").card
    assert (fixed.id, fixed.back) == ("new", "je suis allé")
    (text,) = sent
    assert "A card to write for this lesson (still empty): le passé composé d'aller" in text
    assert "The card to correct" not in text


@pytest.mark.parametrize(("cards", "refused", "code"), [((), False, "llm.invalid_answer"), ((), True, "llm.refused")])
def test_no_card_back(monkeypatch, cards, refused, code):
    answering(monkeypatch, *cards, refused=refused)
    with pytest.raises(llm.ExtractionError) as e:
        fix(Card(front="a", back="b"))
    assert e.value.code == code


def test_the_route_answers_the_card_without_saving_it(client):
    """The page's /api/lessons/{id}/fix-card (the demo AI): the card corrected as sent (an
    unsaved edit included), its id kept; the lesson as it was, the page saves it."""
    lesson = client.post("/api/extract", data={"prompt": "Une carte par mot de la famille"}).json()
    card = {**lesson["cards"][0], "front": "edited, not saved yet"}
    others = [c["front"] for c in lesson["cards"][1:]]
    body = {"card": card, "instruction": "la réponse est el padre", "others": others}
    res = client.post(f"/api/lessons/{lesson['id']}/fix-card", json=body)
    assert res.status_code == 200
    fixed = res.json()
    assert (fixed["card"]["front"], fixed["card"]["back"]) == ("edited, not saved yet", "la réponse est el padre")
    assert fixed["card"]["id"] == card["id"] and fixed["summary"]
    assert client.get(f"/api/lessons/{lesson['id']}").json()["cards"] == lesson["cards"]
    calls = client.get(f"/api/lessons/{lesson['id']}").json().get("ai_calls", [])
    assert not calls or calls[-1]["kind"] == "fix"  # paid for, kept with the lesson (none in the demo)

    assert client.post(f"/api/lessons/{lesson['id']}/fix-card", json={**body, "instruction": ""}).status_code == 422
    assert client.post("/api/lessons/nope/fix-card", json=body).status_code == 404


TRIANGLE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    '<path d="M10 90 L90 90 L50 10 Z" fill="none" stroke="#000"/></svg>'
)


def seeing(monkeypatch, answer: dict) -> list:
    """The AI answers `answer`; the images it was shown, kept (each call's)."""
    shown = []

    async def ask(s, images, text, schema, *args, **kwargs):
        shown.append((list(images), text))
        return schema.model_validate({"summary": "Figure", **answer})

    monkeypatch.setattr("notosaurus_core.ai._ask_provider", ask)
    return shown


def test_the_figure_as_drawn_shown_and_its_problem_said(monkeypatch):
    """A request about a figure's drawing ("E is on the wrong side"): the AI is shown the
    drawing, after the photos, and says what is wrong in it: its picture kept until it is
    drawn again, told that problem."""
    card = Card(id="c4", front="ABC?", back="a triangle", figure="Triangle ABC", picture="f.svg")
    told = {
        "cards": [{"front": "ABC?", "back": "a triangle", "figure": "Triangle ABC"}],
        "figure_problem": "C is under AB",
    }
    shown = seeing(monkeypatch, told)
    fixed = asyncio.run(
        llm.fix_card(
            S, [], "Geometry", "Maths", card, "C est au mauvais endroit", (), "French", figure_svg=TRIANGLE_SVG
        )
    )
    ((images, text),) = shown
    assert [i.media_type for i in images] == ["image/png"] and "The last image is this card's figure" in text
    assert (fixed.figure_problem, fixed.card.picture, fixed.card.figure) == ("C is under AB", "f.svg", "Triangle ABC")


def test_a_figure_to_draw_again_keeps_its_typst(monkeypatch):
    """Its drawing wrong, its description changed too: kept until drawn again, with where it
    comes from (its Typst sources, drawn again from them, #702)."""
    origin = PictureSource(
        source="drawn", engine="typst", made_with=["Typst 0.15.0"], sources=[SourceFile(file="f.typ")]
    )
    card = Card(id="c4", front="ABC?", back="a triangle", figure="Triangle ABC", picture="f.svg")
    card.picture_source = origin
    told = {
        "cards": [{"front": "ABC?", "back": "a triangle", "figure": "Triangle ABC in red"}],
        "figure_problem": "C is under AB",
    }
    seeing(monkeypatch, told)
    fixed = asyncio.run(llm.fix_card(S, [], "", "Maths", card, "en rouge", (), "French", figure_svg=TRIANGLE_SVG))
    assert (fixed.figure_problem, fixed.card.picture, fixed.card.picture_source) == ("C is under AB", "f.svg", origin)


def test_a_figure_changed_and_its_drawing_wrong_kept_until_drawn_again(monkeypatch):
    """Its description changed too ("in red", and a label misplaced): the picture still kept,
    drawn again from the new description told the problem; no figure shown, no problem said."""
    card = Card(id="c5", front="ABC?", back="a triangle", figure="Triangle ABC", picture="f.svg")
    told = {
        "cards": [{"front": "ABC?", "back": "a triangle", "figure": "Triangle ABC in red"}],
        "figure_problem": "A hidden",
    }
    seeing(monkeypatch, told)
    fixed = asyncio.run(llm.fix_card(S, [], "", "Maths", card, "en rouge", (), "French", figure_svg=TRIANGLE_SVG))
    assert (fixed.card.picture, fixed.figure_problem) == ("f.svg", "A hidden")
    shown = seeing(monkeypatch, told)
    fixed = asyncio.run(llm.fix_card(S, [], "", "Maths", card, "en rouge", (), "French"))  # its drawing not given
    ((images, text),) = shown
    assert images == [] and "last image" not in text
    assert (fixed.card.picture, fixed.figure_problem) == ("", "")  # drawn again from its new description


def test_a_figure_that_cant_be_drawn_left_out_of_the_correction(monkeypatch):
    """Its drawing not an SVG the cleaning keeps (a DTD, not XML): the card corrected all the
    same, the AI shown no figure, never the correction failed for its drawing."""
    card = Card(id="c6", front="ABC?", back="a triangle", figure="Triangle ABC", picture="f.svg")
    for unusable in ('<!DOCTYPE svg [<!ENTITY a "b">]><svg/>', "not a figure"):
        shown = seeing(monkeypatch, {"cards": [{"front": "ABC?", "back": "a right triangle"}]})
        fixed = asyncio.run(llm.fix_card(S, [], "", "Maths", card, "rectangle", (), "French", figure_svg=unusable))
        ((images, text),) = shown
        assert images == [] and "last image" not in text
        assert fixed.card.back == "a right triangle"


def test_the_figure_drawn_off_the_event_loop(monkeypatch):
    """Drawing a figure takes a while (a large one, seconds): done in a thread of its own, the
    server's other requests answered meanwhile."""
    import threading

    from notosaurus_core import figures

    threads = []

    def to_png(svg):
        threads.append(threading.current_thread())
        return b"png"

    monkeypatch.setattr(figures, "to_png", to_png)
    seeing(monkeypatch, {"cards": [{"front": "ABC?", "back": "a triangle", "figure": "Triangle ABC"}]})
    card = Card(id="c7", front="ABC?", back="a triangle", figure="Triangle ABC", picture="f.svg")
    asyncio.run(llm.fix_card(S, [], "", "Maths", card, "en rouge", (), "French", figure_svg=TRIANGLE_SVG))
    assert threads and threads[0] is not threading.main_thread()


def test_corrections_quick_when_asked(monkeypatch):
    """The page's "Quick": a lesson's correction and a card's asked with the model thinking
    little (as right, about 30 % faster, measured); carefully when not asked (older pages)."""
    from notosaurus_core.models import Deck

    asked = []

    async def answer(s, images, text, schema, *args, quick=False, **kwargs):
        asked.append(quick)
        return schema.model_validate({"cards": [{"front": "a", "back": "b"}], "summary": "ok", "deck": "D"})

    monkeypatch.setattr("notosaurus_core.ai._ask_provider", answer)
    card, deck = Card(front="a", back="c"), Deck(deck="D", cards=[Card(front="a", back="c")])
    for quick in (True, False):
        asyncio.run(llm.fix_card(S, [], "p", "D", card, "b", (), "French", quick=quick))
        asyncio.run(llm.revise_cards(S, [], "p", deck, "b", "French", quick=quick))
    asyncio.run(llm.fix_card(S, [], "p", "D", card, "b", (), "French"))
    assert asked == [True, True, False, False, False]
