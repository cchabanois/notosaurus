"""The cases Python, Kotlin (the Android app) and JavaScript (the page) must agree on:
core/shared-cases.json, read by the three test suites. Python's answers are the reference:
a change here changes the file, and the other two must follow (SharedCasesTest.kt,
tests/frontend/shared-cases.test.mjs)."""

import json
from pathlib import Path

import pytest

from app.exams import common_deck, tag_text
from notosaurus_core.cards import kept_ids, same_text, text_key
from notosaurus_core.models import Card
from notosaurus_core.tts import filename, speakable, spoken

CASES = json.loads((Path(__file__).parent.parent / "core" / "shared-cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES["tag_text"], ids=lambda c: c["in"])
def test_a_tests_tag(case):
    assert tag_text(case["in"]) == case["out"]


@pytest.mark.parametrize("case", CASES["common_deck"], ids=lambda c: "|".join(c["in"]))
def test_the_deck_holding_a_tests_lessons(case):
    assert common_deck(case["in"]) == case["out"]


@pytest.mark.parametrize("case", CASES["speakable"], ids=lambda c: c["in"])
def test_what_a_voice_reads(case):
    assert speakable(case["in"]) == case["out"]


@pytest.mark.parametrize("case", CASES["spoken"], ids=lambda c: c["back"])
def test_a_cards_sound(case):
    assert spoken(Card(front=case["front"], back=case["back"]), case["dictation"]) == case["out"]


@pytest.mark.parametrize("case", CASES["sound_file"], ids=lambda c: c["text"])
def test_a_sounds_file(case):
    """The same name on the phone (Speech.fileName): a lesson's sounds go from one to the other."""
    assert filename(case["text"], case["voice"], case["rate"]) == case["out"]


@pytest.mark.parametrize("case", CASES["kept_ids"], ids=lambda c: c["name"])
def test_a_card_made_again_keeps_its_id(case):
    """A lesson made again in its place (Lessons.regenerated on the phone): the same cards keep
    their ids, so their notes and history in Anki."""
    made, before = [Card(**c) for c in case["made"]], [Card(**c) for c in case["before"]]
    assert kept_ids(made, before) == case["out"]


@pytest.mark.parametrize("case", CASES["same_text"], ids=lambda c: f"{c['a']}|{c['b']}")
def test_two_texts_the_same(case):
    """What a card made again may differ by (a capital, a final full stop, a typographic
    quote) and what it may not (an accent, a digit): Lessons.textKey on the phone."""
    assert (text_key(case["a"]), same_text(case["a"], case["b"])) == (case["key"], case["out"])


@pytest.mark.parametrize(
    "case",
    [c for c in CASES["kept_ids"] if not any(m.get("id") or m.get("subdeck") for m in c["made"])],
    ids=lambda c: c["name"],
)
def test_a_card_corrected_by_the_ai_is_the_card_made_again(case):
    """The AI's correction finds a card again as a lesson made again does (cards.matching):
    one rule, so a fix to it holds for both. (A correction may move a card to another part
    of the deck; its cards come with no id.)"""
    from notosaurus_core import llm

    revised, before = [Card(**c) for c in case["made"]], [Card(**c) for c in case["before"]]
    llm._keep_ids(revised, before)
    assert [c.id for c in revised] == case["out"]


@pytest.mark.parametrize("case", CASES["info_field"], ids=lambda c: c["name"])
def test_a_cards_info_field(case):
    """The Info field as the computer writes it (note_types.common.info), the phone the same
    (Anki.info): a note sent from one device is up to date from the other."""
    from app.note_types.common import info

    assert info(Card(front="f", back="b", info=case["info"], fun_fact=case["fun_fact"])) == case["out"]
