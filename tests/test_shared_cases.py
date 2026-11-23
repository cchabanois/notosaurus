"""The cases Python, Kotlin (the Android app) and JavaScript (the page) must agree on:
core/shared-cases.json, read by the three test suites. Python's answers are the reference:
a change here changes the file, and the other two must follow (SharedCasesTest.kt,
tests/frontend/shared-cases.test.mjs)."""

import json
from pathlib import Path

import pytest

from app.anki import _deck_name
from app.exams import common_deck, tag_text
from notosaurus_core.cards import kept_ids, same_text, text_key
from notosaurus_core.correction import fix_photos, revise_photos
from notosaurus_core.models import Card
from notosaurus_core.pictures import drawing_calls
from notosaurus_core.tts import filename, speakable, spoken, spoken_sides

CASES = json.loads((Path(__file__).parent.parent / "core" / "shared-cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES["tag_text"], ids=lambda c: c["in"])
def test_a_tests_tag(case):
    assert tag_text(case["in"]) == case["out"]


@pytest.mark.parametrize("case", CASES["common_deck"], ids=lambda c: "|".join(c["in"]))
def test_the_deck_holding_a_tests_lessons(case):
    assert common_deck(case["in"]) == case["out"]


@pytest.mark.parametrize("case", CASES["deck_name"], ids=lambda c: f"{c['deck']}|{c['subdeck']}")
def test_a_cards_deck(case):
    assert _deck_name(case["deck"], case["subdeck"]) == case["out"]


@pytest.mark.parametrize("case", CASES["speakable"], ids=lambda c: c["in"])
def test_what_a_voice_reads(case):
    assert speakable(case["in"]) == case["out"]


@pytest.mark.parametrize("case", CASES["spoken"], ids=lambda c: c["back"])
def test_a_cards_sound(case):
    assert spoken(Card(front=case["front"], back=case["back"]), case["dictation"]) == case["out"]


@pytest.mark.parametrize("case", CASES["spoken_sides"], ids=lambda c: f"{c['front']}|{c['sound']}")
def test_what_each_side_says(case):
    card = Card(front=case["front"], back=case["back"], choices=case["choices"], sound=case["sound"])
    assert list(spoken_sides(card, case["dictation"])) == case["out"]


@pytest.mark.parametrize("case", CASES["sound_file"], ids=lambda c: c["text"])
def test_a_sounds_file(case):
    """The same name on the phone (Speech.fileName): a lesson's sounds go from one to the other."""
    assert filename(case["text"], case["voice"], case["rate"]) == case["out"]


@pytest.mark.parametrize("case", CASES["fix_photos"], ids=lambda c: c["name"])
def test_the_photos_sent_to_correct_a_card(case):
    """The page a card comes from alone, when known; else the lesson's photos when a call takes
    them all; else none: the phone's GenerationRoutes (Generation.fixPhotos) the same."""
    assert fix_photos(case["page"], case["photos"]) == (case["out"], case["sent"])


@pytest.mark.parametrize("case", CASES["drawing_calls"], ids=lambda c: c["name"])
def test_the_calls_looking_for_the_lessons_drawings(case):
    """Each card's drawing looked for on its page and its neighbours, an unknown page's on
    every page ten at a time: the phone's Pictures.drawingCalls the same."""
    calls = [{"pages": call.pages, "cards": call.cards} for call in drawing_calls(case["pages"], case["photos"])]
    assert calls == case["out"]


@pytest.mark.parametrize("case", CASES["revise_photos"], ids=lambda c: c["name"])
def test_the_photos_sent_to_correct_a_lesson(case):
    """Every page when a call takes them all; else none, the lesson corrected from its cards:
    the phone's GenerationRoutes (Generation.revisePhotos) the same."""
    assert revise_photos(case["photos"]) == (case["out"], case["sent"])


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


@pytest.mark.parametrize("case", CASES["figure_source_files"], ids=lambda c: f"{c['picture']}|{c['count']}")
def test_a_figures_source_files(case, tmp_path):
    """What a figure was drawn from, beside its picture: the same names on the phone
    (Pictures.keepSources), read back by either (a lesson goes from one to the other)."""
    from notosaurus_core.models import PictureSource
    from notosaurus_core.pictures import keep_sources, kept_sources

    contents = [f"// source {n}" for n in range(case["count"])]
    files = keep_sources(tmp_path, case["picture"], contents)
    assert [f.file for f in files] == case["out"]
    assert kept_sources(tmp_path, PictureSource(source="drawn", engine="typst", sources=files)) == contents


@pytest.mark.parametrize("case", CASES["figure_sources_pruned"], ids=lambda c: c["name"])
def test_a_figures_sources_pruned_with_it(case, tmp_path):
    """The pictures no card uses removed with their sources, the others' kept: the phone's
    Pictures.pruned the same."""
    from notosaurus_core.pictures import prune

    # Names told apart by their case alone are one file on Windows and macOS: never a case's
    assert len({name.casefold() for name in case["files"]}) == len(case["files"])
    for name in case["files"]:
        (tmp_path / name).write_text("x", encoding="utf-8")
    cards = [Card(front="f", back="b", picture=p) for p in case["pictures"]]
    assert prune(tmp_path, cards) == case["removed"]
    assert sorted(p.name for p in tmp_path.iterdir()) == case["out"]
