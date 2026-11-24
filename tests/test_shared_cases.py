"""The cases Python, Kotlin (the Android app) and JavaScript (the page) must agree on:
core/shared-cases.json, read by the three test suites. Python's answers are the reference:
a change here changes the file, and the other two must follow (SharedCasesTest.kt,
tests/frontend/shared-cases.test.mjs)."""

import json
from pathlib import Path

import pytest

from app.anki import _deck_name
from app.exams import common_deck, tag_text
from notosaurus_core import correction
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


@pytest.mark.parametrize("case", CASES["next_page"], ids=lambda c: c["name"])
def test_the_number_of_a_page_added_to_a_lesson(case):
    """After the highest page number used anywhere in the lesson: the phone's Lessons.nextPage
    the same."""
    from app.lessons import next_page
    from notosaurus_core.models import Frame

    lesson = case["lesson"]
    cards = [Card(front="f", back="b", **c) for c in lesson.get("cards", [])]
    frames = [Frame(**f) for f in lesson.get("frames", [])]
    assert next_page(case["files"], cards, frames, lesson.get("page_texts", [])) == case["out"]


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
    revised, before = [Card(**c) for c in case["made"]], [Card(**c) for c in case["before"]]
    correction._keep_ids(revised, before)
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


def _child(c: dict | None):
    from app.children import Child

    return Child(**c) if c else None


@pytest.mark.parametrize("case", CASES["same_level"], ids=lambda c: f"{c['a']}|{c['b']}")
def test_two_deck_levels_the_same(case):
    """A child's level told in a deck: its case, its accents and an ordinal's ending aside,
    any script's letters kept (Children.same on the phone, sameLevel in the page)."""
    from app.children import same_level

    assert (same_level(case["a"]) == same_level(case["b"])) == case["out"]


@pytest.mark.parametrize("case", CASES["split_deck"], ids=lambda c: c["deck"])
def test_a_deck_split_into_the_childrens_levels_and_the_rest(case):
    """The children's levels a deck starts with, and what the AI sees: Children.splitDeck."""
    from app.children import split_deck

    assert list(split_deck(case["deck"], [_child(c) for c in case["children"]])) == case["out"]


@pytest.mark.parametrize("case", CASES["deck_for"], ids=lambda c: c["deck"])
def test_a_lessons_deck_in_its_childs_decks(case):
    """Children.deckFor the same."""
    from app.children import deck_for

    assert deck_for(_child(case["child"]), case["deck"]) == case["out"]


@pytest.mark.parametrize("case", CASES["decks_for_ai"], ids=lambda c: c["child"] or "none")
def test_the_decks_the_ai_may_reuse(case):
    """A child's own and no child's, never another's: Children.decksForAi the same."""
    from app.children import decks_for_ai

    every = [_child(c) for c in case["children"]]
    child = next((c for c in every if c and c.id == case["child"]), None)
    assert decks_for_ai(case["decks"], [c for c in every if c], child) == case["out"]


@pytest.mark.parametrize("case", CASES["new_deck_name"], ids=lambda c: c["name"])
def test_each_lesson_its_own_deck(case):
    """A deck that exists (Anki's, another lesson's) never a new lesson's: the phone's
    Generation.existing and freeName the same."""
    from app.decks import existing, free_name

    assert free_name(case["deck"], existing(case["anki"], case["lessons"], case["own"])) == case["out"]


@pytest.mark.parametrize("case", CASES["shared_deck"], ids=lambda c: c["rest"])
def test_a_lessons_deck_in_a_shared_package(case):
    """ExportRoutes.sharedDeck the same."""
    from app.routes.generation import _shared_deck

    assert _shared_deck(case["top"], case["rest"], case["common"]) == case["out"]


@pytest.mark.parametrize("case", CASES["shared_id"], ids=lambda c: c["in"])
def test_a_lessons_id_in_a_shared_package(case):
    """ExportRoutes.sharedId the same."""
    from app.routes.generation import _shared_id

    assert _shared_id(case["in"]) == case["out"]


@pytest.mark.parametrize("case", CASES["package_name"], ids=lambda c: c["in"])
def test_a_packages_file_name(case):
    """ExportRoutes.packageName the same."""
    from app.routes.generation import _filename

    assert _filename(case["in"]) == case["out"]


@pytest.mark.parametrize("case", CASES["package_deck"], ids=lambda c: f"{c['name']}|{c['default']}|{c['common']}")
def test_a_shared_packages_own_deck(case):
    """The name asked, else the test's, else the lessons' common deck: ExportRoutes.packageDeck."""
    from app.routes.generation import _package_deck

    assert _package_deck(case["name"], case["default"], case["common"]) == case["out"]


@pytest.mark.parametrize("case", CASES["speech_rate"], ids=lambda c: json.dumps(c))
def test_a_lessons_speech_rate(case):
    """Speech.rate the same."""
    from app.routes.generation import _rate

    assert _rate(case["slowed"], case["speed"], foreign=case["foreign"], dictation=case["dictation"]) == case["out"]


@pytest.mark.parametrize("case", CASES["learned_language"], ids=lambda c: json.dumps(c))
def test_the_language_being_learned(case):
    """Speech.learned the same."""
    from app.routes.generation import _learned

    assert _learned(case["language"], case["pupil"], spelling=case["spelling"]) == case["out"]


@pytest.mark.parametrize("case", CASES["page_texts"], ids=lambda c: f"{c['raw']}|{c['photos']}")
def test_the_pages_texts_sent_by_the_page(case):
    """Generation.pageTexts the same."""
    from app.routes.generation import _page_texts

    assert _page_texts(case["raw"], case["photos"]) == case["out"]


@pytest.mark.parametrize("case", CASES["standing_instructions"], ids=lambda c: json.dumps(c["child"]))
def test_the_standing_instructions_told_the_ai(case):
    """Generation.standingInstructions (with Children.forAi) the same."""
    from app import children, settings

    child = children.Child(id="c", name="Jules", **case["child"]) if case["child"] else None
    told = settings.standing_instructions(settings.Settings(instructions=case["instructions"]), children.for_ai(child))
    assert told == case["out"]


@pytest.mark.parametrize("case", CASES["anki_formula"], ids=lambda c: c["name"])
def test_a_cards_formulas_as_they_go_to_anki(case):
    """A card's text as it goes to Anki: its formulas without MathJax's html commands (a link,
    a style), the phone's the same (Formulas.ankiText); the text outside them as it is."""
    from app.note_types.formulas import anki_text

    assert anki_text(case["in"]) == case["out"]


@pytest.mark.parametrize("case", CASES["merged_card"], ids=lambda c: c["name"])
def test_an_edits_card_merged_into_the_saved_one(case):
    """A card an edit changed merged into the card as saved now: a picture drawn from a
    description changed meanwhile set aside. The phone's Pictures.mergedCards the same."""
    from app.lessons import merged_cards

    before, after, now = (Card(**case[k]) for k in ("before", "after", "now"))
    assert merged_cards([before], [after], [now]) == [Card(**case["out"])]
