"""A corrected card stays the card it was (its id: its note in Anki, the child's review history),
whatever the correction rewrote of it: the AI is shown each card's number ("ref") and gives it
back; its texts only when it gives none (correction.found_again)."""

import json
import re

from helpers import run

from notosaurus_core import ai, correction
from notosaurus_core.config import AIConfig
from notosaurus_core.models import Card, Deck

S = AIConfig(llm="gemini", gemini_api_key="k")
WORDS = [("la mère", "la madre"), ("le père", "el padre"), ("le chat", "el gato")]


def lesson() -> list[Card]:
    return [Card(id=f"id{i}", front=f, back=b) for i, (f, b) in enumerate(WORDS)]


def revised(monkeypatch, answer: list[dict]) -> tuple[list[Card], str]:
    """The lesson corrected, the AI answering `answer` (its cards, each with its ref or not):
    the cards as kept, and what the AI was shown."""
    shown = []

    async def ask(s, images, text, schema, *args, **kwargs):
        shown.append(text)
        return schema.model_validate({"deck": "Espagnol", "summary": "ok", "cards": answer})

    monkeypatch.setattr(ai, "_ask_provider", ask)
    revision = run(correction.revise_cards(S, [], "FR → ES", Deck(deck="Espagnol", cards=lesson()), "…"))
    return revision.cards, shown[0]


def test_the_ai_is_shown_each_cards_ref_and_asked_it_back(monkeypatch):
    _, text = revised(monkeypatch, [{"ref": n, "front": f, "back": b} for n, (f, b) in enumerate(WORDS, 1)])
    current = json.loads(re.search(r"Current cards \(JSON\):\n(.*?)\n\nRequested", text, re.S).group(1))
    assert [c["ref"] for c in current["cards"]] == [1, 2, 3]
    assert all("id" not in c for c in current["cards"])  # its id never shown: a number it can't garble
    assert 'the "ref" of the card it is' in text


def test_a_card_rewritten_on_both_sides_keeps_its_id(monkeypatch):
    """Its sides swapped, or both rephrased: neither its front nor its back the same, the same card
    by its ref (by its texts alone, a new note each: « +18 new · −18 removed », the history lost)."""
    swapped = [{"ref": n, "front": b, "back": f} for n, (f, b) in enumerate(WORDS, 1)]
    cards, _ = revised(monkeypatch, swapped)
    assert [c.id for c in cards] == ["id0", "id1", "id2"]
    rephrased = [
        {"ref": 3, "front": "el gato (animal)", "back": "le chat (animal)"},
        {"ref": 1, "front": "Mother", "back": "Madre"},
    ]
    cards, _ = revised(monkeypatch, rephrased)
    assert [c.id for c in cards] == ["id2", "id0"]  # moved too; the father removed


def test_a_card_added_or_unknown_is_new(monkeypatch):
    answer = [
        {"ref": 1, "front": "la mère", "back": "la madre"},
        {"ref": 0, "front": "le frère", "back": "el hermano"},  # added
        {"ref": 9, "front": "la sœur", "back": "la hermana"},  # no such card
        {"ref": 1, "front": "maman", "back": "mamá"},  # a ref already given
    ]
    cards, _ = revised(monkeypatch, answer)
    assert [c.id for c in cards] == ["id0", "", "", ""]


def test_the_same_card_unchanged_wins_over_a_wrong_ref(monkeypatch):
    """An unchanged card is that card whatever its ref says (the AI numbering the cards it returns
    1, 2… after removing one): never another's note."""
    answer = [{"ref": 1, "front": "la mère", "back": "la madre"}, {"ref": 2, "front": "le chat", "back": "el gato"}]
    cards, _ = revised(monkeypatch, answer)
    assert [c.id for c in cards] == ["id0", "id2"]


def test_no_ref_given_found_by_its_texts(monkeypatch):
    """The AI giving no ref (an older answer, the demo): found again by its texts, as before."""
    answer = [{"front": "la mère", "back": "la mamá"}, {"front": "le chien", "back": "el perro"}]
    cards, _ = revised(monkeypatch, answer)
    assert [c.id for c in cards] == ["id0", ""]
