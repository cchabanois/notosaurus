"""A dictation's cards never show their answer on the front (cards.blank_dictations)."""

import asyncio

from notosaurus_core import cards, llm
from notosaurus_core.config import AIConfig
from notosaurus_core.models import Card


def blanked(front: str, back: str) -> str:
    card = Card(front=front, back=back)
    cards.blank_dictations([card])
    return card.front


def test_the_word_written_on_the_front_blanked():
    assert blanked("Écris le mot : [maison]", "maison") == "Écris le mot : …"  # emphasised (TYP-07)
    assert blanked("Écris le mot : maison", "maison") == "Écris le mot : …"
    assert blanked("Il habite une Maison bleue.", "maison") == "Il habite une … bleue."


def test_an_empty_front_gets_its_blank():
    """ANK-08: no front written, no note in Anki (its first field): the blank alone."""
    assert blanked("", "chaton") == "…" and blanked("  ", "Le chat dort.") == "…"
    assert blanked("", "") == ""  # nothing to write: left as it is
    # Its sound the word once, as with no front: a lesson's sounds made before found again
    from notosaurus_core import tts

    assert tts.spoken(Card(front="…", back="chaton"), dictation=True) == "chaton"
    assert tts.spoken(Card(front="", back="chaton"), dictation=True) == "chaton"


def test_a_front_with_its_blank_or_ambiguous_kept():
    assert blanked("la maison de … poupée", "la") == "la maison de … poupée"  # the other "la" isn't it
    assert blanked("la maison de la poupée", "la") == "la maison de la poupée"  # which one?
    assert blanked("Phrase 3", "Le chat dort.") == "Phrase 3"
    assert blanked("Écris le mot : maisonnette", "maison") == "Écris le mot : maisonnette"  # a whole word only


def test_extraction_of_a_dictation_never_gives_its_answer(monkeypatch):
    """Applied to what the AI wrote for a dictation alone; another lesson's cards untouched."""
    for dictation, front in ((True, "Écris le mot : …"), (False, "Écris le mot : [maison]")):

        async def answer(s, images, text, schema, system=None, dictation=dictation, **options):
            card = {"front": "Écris le mot : <b>maison</b>", "back": "maison", "figure_kind": ""}
            return schema.model_validate({"deck": "Dictée", "cards": [card], "dictation": dictation})

        monkeypatch.setattr(llm, "_ask_provider", answer)
        found = asyncio.run(llm.extract_cards(AIConfig(llm="gemini"), [], "Dictée : maison"))
        assert found.deck.cards[0].front == front
