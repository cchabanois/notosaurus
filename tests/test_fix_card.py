"""One card corrected on its own (llm.fix_card): the AI writes that card alone; it stays
the same card (its id, its diagram label), its picture kept unless what to draw changed."""

import asyncio

import pytest

from notosaurus_core import llm
from notosaurus_core.config import AIConfig
from notosaurus_core.models import Card, Mask

S = AIConfig(llm="gemini", gemini_api_key="k")


def answering(monkeypatch, *cards: dict, refused: bool = False) -> list[str]:
    """The AI answers these cards; the texts it was sent, kept."""
    sent = []

    async def answer(s, images, text, schema, *args, **kwargs):
        sent.append(text)
        return schema.model_validate({"cards": list(cards), "summary": "<b>Date</b> fixed", "refused": refused})

    monkeypatch.setattr(llm, "_ask_provider", answer)
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
    fixed = fix(card, "the spelling of heart").card
    assert (fixed.id, fixed.mask, fixed.picture, fixed.picture_prompt) == ("c2", mask, "p.jpg", "a heart")


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
