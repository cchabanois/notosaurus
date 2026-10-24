"""The cases Python, Kotlin (the Android app) and JavaScript (the page) must agree on:
core/shared-cases.json, read by the three test suites. Python's answers are the reference:
a change here changes the file, and the other two must follow (SharedCasesTest.kt,
tests/frontend/shared-cases.test.mjs)."""

import json
from pathlib import Path

import pytest

from app.exams import common_deck, tag_text
from notosaurus_core.models import Card
from notosaurus_core.tts import speakable, spoken

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
