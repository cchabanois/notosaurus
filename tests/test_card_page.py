"""A card's page (Card.page): the lesson's photo it was made from, written by the AI, numbered
among the lesson's photos (a lesson read in several calls), kept by its corrections, and the
one photo sent when the card alone is corrected (correction.fix_photos)."""

import io

from conftest import extract_lesson
from helpers import plain_image, run
from PIL import Image as PILImage

from app import lessons
from app.routes import generation
from notosaurus_core import ai, llm
from notosaurus_core import relay_api as api
from notosaurus_core.calls import Image
from notosaurus_core.config import AIConfig
from notosaurus_core.models import Card, CardFix, Deck, Extraction, Revision
from notosaurus_core.prompts import _fix_text

S = AIConfig(llm="gemini", gemini_api_key="k")


def answering(monkeypatch, answer: dict) -> list[tuple[list[Image], str]]:
    """The AI answers `answer`; the images and the text it was sent, kept (each call's)."""
    sent = []

    async def ask(s, images, text, schema, *args, **kwargs):
        sent.append((list(images), text))
        return schema.model_validate({"summary": "done", **answer})

    monkeypatch.setattr("notosaurus_core.ai._ask_provider", ask)
    return sent


def test_a_cards_page_kept_with_it_and_unknown_on_an_older_one():
    card = Card(front="a", back="b", page=3)
    assert Card.model_validate_json(card.model_dump_json()).page == 3
    assert Card.model_validate({"front": "a", "back": "b"}).page == 0  # made before cards knew theirs


def test_the_ai_writes_it_except_for_one_card_corrected():
    """Written by the AI (not one of Notosaurus's own fields), within Claude's limit (required
    there, written 0 without a photo); not asked of a card corrected alone: it stays its own."""
    for base in (Extraction, Revision):
        card = ai.ai_schema(base, claude=True).model_json_schema()["$defs"]["Card"]
        assert "page" in card["properties"] and "page" in card["required"]
        other = ai.ai_schema(base).model_json_schema()["$defs"]["Card"]
        assert "page" in other["properties"] and "page" not in other["required"]
    for claude in (False, True):
        fix = ai.ai_schema(CardFix, fun_facts=True, helps=True, claude=claude, page=False).model_json_schema()
        assert "page" not in fix["$defs"]["Card"]["properties"]
        assert "page" not in fix["$defs"]["Card"].get("required", [])


def test_a_page_not_among_the_calls_photos_is_unknown(monkeypatch):
    """The AI numbers the photos it is given: a page past them (or none) is 0."""
    cards = [{"front": f"q{n}", "back": "a", "page": page} for n, page in enumerate([1, 2, 3, -1, 0])]
    answering(monkeypatch, {"deck": "D", "cards": cards})
    photos = [Image(plain_image(40, 30), "image/jpeg")] * 2
    found = run(llm.extract_cards(S, photos, "p"))
    assert [c.page for c in found.deck.cards] == [1, 2, 0, 0, 0]


def test_a_client_that_doesnt_ask_for_the_cards_pages_gets_none(monkeypatch):
    """/v1/extract: an app that stores a card's fields as they come without numbering its page
    among the lesson's (1.1.x, completing a lesson) gets every page 0, in the answer and its
    lines; one asking for them (card_pages) gets the AI's."""
    cards = [{"front": f"q{n}", "back": "a", "page": page} for n, page in enumerate([1, 2, 0])]
    answer = {"deck": "D", "cards": cards}

    async def ask(s, images, text, schema, *args, on_card=None, **kwargs):
        for card in cards:
            await on_card(dict(card))
        await on_card(None)  # a restart passes as it is
        return schema.model_validate(answer)

    monkeypatch.setattr("notosaurus_core.ai._ask_provider", ask)
    photos = [Image(plain_image(40, 30), "image/jpeg")] * 2
    for asked, pages in ((None, [0, 0, 0]), (False, [0, 0, 0]), (True, [1, 2, 0])):
        request = api.ExtractRequest(prompt="p", **({} if asked is None else {"card_pages": asked}))
        request = api.ExtractRequest.model_validate_json(request.model_dump_json(exclude_unset=True))
        lines = []

        async def on_card(card, lines=lines):
            lines.append(card)

        found = run(llm.extract_cards(S, photos, request.prompt, request.options(), on_card=on_card))
        assert [c.page for c in found.deck.cards] == pages
        assert [line.get("page", 0) for line in lines[:-1]] == pages and lines[-1] is None
        assert all("page" not in line for line in lines[:-1]) == (not asked)


def test_the_demo_ai_gives_its_cards_a_page():
    """NOTOSAURUS_LLM=fake: its cards shared among the photos, so the page shows a card's page."""
    photos = [Image(plain_image(40, 30), "image/jpeg")] * 2
    found = run(llm.extract_cards(AIConfig(llm="fake"), photos, "FR → ES"))
    assert {c.page for c in found.deck.cards} == {1, 2}
    assert {c.page for c in run(llm.extract_cards(AIConfig(llm="fake"), [], "FR → ES")).deck.cards} == {0}


def test_a_lesson_completed_numbers_its_new_cards_pages_from_its_own(client, monkeypatch):
    """The next pages' cards: their pages counted after the lesson's (the AI numbered them among
    the call's photos), 0 staying unknown; the older cards keep theirs, still the same photo:
    completing adds photos, never moves one."""
    lesson = extract_lesson(client)  # 2 photos, the demo's cards on pages 1 and 2
    url = f"/api/lessons/{lesson['id']}"
    before = [c["page"] for c in lesson["cards"]]
    assert set(before) == {1, 2}
    photos = [lessons.photo(lesson["id"], n) for n in (1, 2)]
    real = generation.extract_cards

    async def next_pages(s, images, prompt, options, **kwargs):
        found = await real(s, images, prompt, options, **kwargs)
        found.deck.cards = [
            llm.Card(front="le grand-père", back="el abuelo", page=2),  # the call's second photo
            llm.Card(front="la grand-mère", back="la abuela", page=1),
            llm.Card(front="la famille", back="la familia"),  # unknown
        ]
        return found

    monkeypatch.setattr(generation, "extract_cards", next_pages)
    files = [("images", (f"p{n}.jpg", f"page {n}".encode(), "image/jpeg")) for n in (3, 4)]
    done = client.post(f"{url}/complete", files=files, data={"prompt": "FR → ES"}).json()

    assert [c["page"] for c in done["cards"][-3:]] == [4, 3, 0]
    assert [c["page"] for c in done["cards"][:-3]] == before
    assert [lessons.photo(lesson["id"], n) for n in (1, 2)] == photos  # their pages still these photos
    assert lessons.photo(lesson["id"], 4) == b"page 4"


def test_a_lesson_made_again_numbers_its_pages_from_one(client):
    lesson = extract_lesson(client, n_photos=3)
    files = [("images", ("p.jpg", b"only page", "image/jpeg"))]
    again = client.post(f"/api/lessons/{lesson['id']}/regenerate", files=files, data={"prompt": "FR → ES"}).json()
    assert {c["page"] for c in again["cards"]} == {1}


def test_a_lesson_corrected_keeps_its_cards_pages(monkeypatch):
    """A card kept keeps its page unless the AI gives another (one of the lesson's photos, all
    sent: numbered as the lesson's); a card added gets the AI's."""
    cards = [
        Card(id="a", front="la mère", back="la madre", page=2),
        Card(id="b", front="le père", back="el padre", page=3),
        Card(id="c", front="la sœur", back="la hermana", page=1),
    ]
    answering(
        monkeypatch,
        {
            "deck": "D",
            "cards": [
                {"front": "la mère", "back": "la madre"},  # its page not written: kept
                {"front": "le père", "back": "el padre", "page": 1},  # moved by the AI
                {"front": "la sœur", "back": "la hermana", "page": 9},  # not a photo: kept
                {"front": "le frère", "back": "el hermano", "page": 3},  # added
                {"front": "la tante", "back": "la tía", "page": 7},  # added, not a photo: unknown
            ],
        },
    )
    photos = [Image(plain_image(40, 30), "image/jpeg")] * 3
    revised = run(llm.revise_cards(S, photos, "p", Deck(deck="D", cards=cards), "add the brother"))
    assert [(c.id, c.page) for c in revised.cards] == [("a", 2), ("b", 1), ("c", 1), ("", 3), ("", 0)]


def test_a_card_corrected_alone_keeps_its_page(monkeypatch):
    sent = answering(monkeypatch, {"cards": [{"front": "q", "back": "fixed", "page": 5}]})
    card = Card(id="c1", front="q", back="wrong", page=2)
    photo = [Image(plain_image(40, 30), "image/jpeg")]
    fixed = run(llm.fix_card(S, photo, "p", "D", card, "fix it", photos_sent="card")).card
    assert (fixed.back, fixed.page) == ("fixed", 2)
    ((_, text),) = sent
    assert '"page"' not in text  # numbered among the lesson's photos, not the one it sees


def test_the_correction_says_what_its_photos_are():
    """One photo, the card's page: said so (it sees "a photo", not the lesson's numbering);
    none of a lesson that has some: said, not a lesson "without photo"."""
    card = Card(front="q", back="a", page=7)
    card_page = _fix_text("p", "D", card, (), "fix", "French", 1, sent="card")
    assert "The photo shown is the lesson's page this card comes from" in card_page
    assert "7" not in card_page
    none = _fix_text("p", "D", card, (), "fix", "French", 0, sent="none")
    assert "photos are not shown" in none and "(no photo)" not in none
    assert "(no photo)" in _fix_text("p", "D", card, (), "fix", "French", 0)  # a lesson without photo
    assert "these photos with" in _fix_text("p", "D", card, (), "fix", "French", 3)
    drawn = _fix_text("p", "D", card, (), "fix", "French", 1, figure=True, sent="card")
    assert "image after the photo)" in drawn


def widths(images: list[Image]) -> list[int]:
    return [PILImage.open(io.BytesIO(i.data)).width for i in images]


def lesson_of(client, count: int) -> dict:
    """A lesson of `count` photos (10 a call, then completed), photo n `100 + n` pixels wide."""
    files = [("images", (f"p{n}.jpg", plain_image(100 + n, 50), "image/jpeg")) for n in range(1, count + 1)]
    lesson = client.post("/api/extract", files=files[:10], data={"prompt": "FR → ES"}).json()
    if count > 10:
        url = f"/api/lessons/{lesson['id']}/complete"
        lesson = client.post(url, files=files[10:], data={"prompt": "FR → ES"}).json()
    assert lesson["photo_count"] == count
    return lesson


def fix_sent(client, monkeypatch, lesson: dict, card: dict) -> tuple[list[int], str]:
    """The card corrected through the route (the demo AI): the widths of the photos the AI was
    sent, and its text."""
    shown = []
    real = ai._ask_provider

    async def ask(s, images, text, schema, *args, **kwargs):
        shown.append((widths(images), text))
        return await real(s, images, text, schema, *args, **kwargs)

    monkeypatch.setattr(ai, "_ask_provider", ask)
    body = {"card": card, "instruction": "la réponse est el padre"}
    res = client.post(f"/api/lessons/{lesson['id']}/fix-card", json=body)
    assert res.status_code == 200, res.text
    assert res.json()["card"]["page"] == card.get("page", 0)
    ((sent, text),) = shown
    return sent, text


def test_correcting_a_card_sends_its_page_alone(client, monkeypatch):
    lesson = lesson_of(client, 3)
    card = {**lesson["cards"][0], "page": 2}
    assert fix_sent(client, monkeypatch, lesson, card)[0] == [102]


def test_correcting_an_older_card_sends_the_lessons_photos(client, monkeypatch):
    """Its page unknown (or not one of the lesson's): every photo, as before, when a call takes
    them all."""
    lesson = lesson_of(client, 3)
    for page in (0, 4):
        card = {**lesson["cards"][0], "page": page}
        assert fix_sent(client, monkeypatch, lesson, card)[0] == [101, 102, 103]
    older = {k: v for k, v in lesson["cards"][0].items() if k != "page"}  # as 1.1 saved it
    assert fix_sent(client, monkeypatch, lesson, older)[0] == [101, 102, 103]


def test_an_older_card_of_a_long_lesson_corrected_without_its_photos(client, monkeypatch):
    """12 photos, more than a call takes, the card's page unknown: none sent, the AI told so."""
    lesson = lesson_of(client, 12)
    card = {**lesson["cards"][0], "page": 0}
    sent, text = fix_sent(client, monkeypatch, lesson, card)
    assert sent == [] and "photos are not shown" in text
    known = {**lesson["cards"][0], "page": 11}
    assert fix_sent(client, monkeypatch, lesson, known)[0] == [111]


def test_a_saved_lessons_cards_keep_their_page(client):
    lesson = extract_lesson(client)
    url = f"/api/lessons/{lesson['id']}"
    cards = [{**c, "front": c["front"] + "!"} for c in lesson["cards"]]
    saved = client.put(url, json={"deck": lesson["deck"], "cards": cards}).json()
    assert [c["page"] for c in saved["cards"]] == [c["page"] for c in lesson["cards"]]
