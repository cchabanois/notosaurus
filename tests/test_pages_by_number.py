"""A lesson's pages by their number: page-N.jpg is page N (a card's `page`, a mask's, a frame's,
page_texts[N - 1]). A page missing (its file removed) leaves a gap: every use opens a page by its
number, never the one at its place in a list, and a page added is numbered after every number
the lesson uses (lessons.next_page), never over another."""

import io
import json

from helpers import plain_image, run
from PIL import Image as PILImage

from app import lessons
from app.routes import generation
from notosaurus_core import ai, llm
from notosaurus_core.calls import Image
from notosaurus_core.config import AIConfig
from notosaurus_core.models import Card, Deck, Mask
from notosaurus_core.prompts import _revision_text

S = AIConfig(llm="gemini", gemini_api_key="k")


def width(image: Image) -> int:
    return PILImage.open(io.BytesIO(image.data)).width


def lesson_without_page_3(client) -> dict:
    """A lesson of 5 photos, photo n `100 + n` pixels wide, its page 3 then removed by hand."""
    files = [("images", (f"p{n}.jpg", plain_image(100 + n, 50), "image/jpeg")) for n in range(1, 6)]
    lesson = client.post("/api/extract", files=files, data={"prompt": "FR → ES"}).json()
    lessons.photo_path(lesson["id"], 3).unlink()
    return client.get(f"/api/lessons/{lesson['id']}").json()


def seen_by_the_ai(monkeypatch) -> list[tuple[list[int], str]]:
    """Each call's photos (their widths: their page) and text, the demo AI answering."""
    shown = []
    real = ai._ask_provider

    async def ask(s, images, text, schema, *args, **kwargs):
        shown.append(([width(i) for i in images], text))
        return await real(s, images, text, schema, *args, **kwargs)

    monkeypatch.setattr(ai, "_ask_provider", ask)
    return shown


def test_a_lesson_tells_its_pages_by_their_numbers(client):
    lesson = lesson_without_page_3(client)
    assert (lesson["photo_count"], lesson["pages"]) == (4, [1, 2, 4, 5])
    assert client.get(f"/api/lessons/{lesson['id']}/photos/3").status_code == 404
    assert client.get(f"/api/lessons/{lesson['id']}/photos/5").status_code == 200
    assert "pages" not in (lessons.folder(lesson["id"]) / "lesson.json").read_text()  # its folder's, not kept


def test_a_card_corrected_gets_its_own_page_not_the_one_at_its_place(client, monkeypatch):
    """Page 3 missing: the card from page 5 is sent page-5.jpg (not a 404, not the 4th photo)."""
    lesson = lesson_without_page_3(client)
    shown = seen_by_the_ai(monkeypatch)
    card = {**lesson["cards"][0], "page": 5}
    res = client.post(f"/api/lessons/{lesson['id']}/fix-card", json={"card": card, "instruction": "el padre"})
    assert res.status_code == 200, res.text
    assert shown[0][0] == [105]
    assert res.json()["card"]["page"] == 5


def test_a_card_from_the_missing_page_is_corrected_as_one_whose_page_is_unknown(client, monkeypatch):
    lesson = lesson_without_page_3(client)
    shown = seen_by_the_ai(monkeypatch)
    card = {**lesson["cards"][0], "page": 3}
    res = client.post(f"/api/lessons/{lesson['id']}/fix-card", json={"card": card, "instruction": "el padre"})
    assert res.status_code == 200, res.text
    assert shown[0][0] == [101, 102, 104, 105]  # every page there, none in its place
    assert res.json()["card"]["page"] == 3  # its own, still


def test_a_lesson_corrected_with_a_page_missing(client, monkeypatch):
    """Its pages there sent, the AI told which page each photo is; a card it adds from its 3rd
    photo is from page 4."""
    lesson = lesson_without_page_3(client)
    shown = seen_by_the_ai(monkeypatch)

    async def demo(s, images, text, schema, *args, **kwargs):
        shown.append(([width(i) for i in images], text))
        cards = [{"front": c["front"], "back": c["back"]} for c in lesson["cards"]]
        added = {"front": "le grand-père", "back": "el abuelo", "page": 3}
        return schema.model_validate({"deck": lesson["deck"], "cards": [*cards, added], "summary": "added"})

    monkeypatch.setattr(ai, "_ask_provider", demo)
    body = {"deck": lesson["deck"], "cards": lesson["cards"], "instruction": "ajoute el abuelo"}
    res = client.post(f"/api/lessons/{lesson['id']}/revise", json=body)
    assert res.status_code == 200, res.text
    ((sent, text),) = shown
    assert sent == [101, 102, 104, 105]
    assert "photo 3 is page 4" in text
    assert res.json()["lesson"]["cards"][-1]["page"] == 4


def test_the_revision_numbers_the_photos_as_the_ai_sees_them(monkeypatch):
    """The cards' pages and labels shown as photo numbers; the AI's pages and new labels turned
    back into the lesson's; a card from a page not sent shown without one, keeping its own."""
    sent = []

    async def ask(s, images, text, schema, *args, **kwargs):
        sent.append(text)
        return schema.model_validate(
            {
                "deck": "D",
                "summary": "done",
                "cards": [
                    {"front": "a", "back": "1"},  # its page not written: kept
                    {"front": "b", "back": "2"},  # from page 3, not sent: kept
                    {"front": "c", "back": "3", "page": 2},  # the 2nd photo: page 4
                    {"front": "d", "back": "4", "page": 3, "mask": {"page": 3, "n": 1, "box": [0.1, 0.1, 0.2, 0.2]}},
                ],
            }
        )

    monkeypatch.setattr(ai, "_ask_provider", ask)
    monkeypatch.setattr(ai, "_box_format", lambda s: "fractions")
    cards = [
        Card(id="a", front="a", back="1", page=4, mask=Mask(page=4, n=2, box=[0.5, 0.5, 0.6, 0.6])),
        Card(id="b", front="b", back="2", page=3),
    ]
    photos = [Image(plain_image(40, 30), "image/jpeg")] * 3
    revised = run(llm.revise_cards(S, photos, "p", Deck(deck="D", cards=cards), "add", pages=[1, 4, 5]))
    assert [c.page for c in revised.cards] == [4, 3, 4, 5]
    assert revised.cards[0].mask == cards[0].mask  # its own, by the lesson's numbers
    assert revised.cards[3].mask and revised.cards[3].mask.page == 5
    (text,) = sent
    assert '"page": 2' in text and '"page": 0' in text  # page 4 is photo 2; page 3 isn't sent
    assert "photo 2: [2]" in text  # its labels' numbers, on photo 2


def test_the_revision_says_which_page_each_photo_is_only_when_they_differ():
    deck = Deck(deck="D", cards=[Card(front="q", back="a")])
    gap = _revision_text("p", deck, "fix", "French", 3, pages=[1, 2, 4])
    assert "photo 1 is page 1, photo 2 is page 2, photo 3 is page 4" in gap
    for pages in ([], [1, 2, 3]):
        assert "is page" not in _revision_text("p", deck, "fix", "French", 3, pages=pages)


def test_a_cards_drawing_looked_for_on_its_own_page(client, monkeypatch):
    """Page 3 missing: the card from page 5 is looked for on its page and its neighbour there,
    4 (not as a card whose page is unknown, past the 4 photos), its drawing cut out of page 5."""
    lesson = lesson_without_page_3(client)
    sent = []

    async def find_drawings(s, images, cards):
        widths = [width(i) for i in images]
        sent.append(widths)
        return {0: (widths.index(105), [0.1, 0.1, 0.5, 0.5])}

    cut = []
    monkeypatch.setattr(llm, "find_drawings", find_drawings)
    monkeypatch.setattr("notosaurus_core.pictures.cut_out", lambda photo, box: cut.append(photo) or plain_image(10, 10))
    cards = [{**lesson["cards"][0], "picture_prompt": "a cat", "figure": "", "picture": "", "page": 5}]
    assert client.put(f"/api/lessons/{lesson['id']}", json={"deck": lesson["deck"], "cards": cards}).status_code == 200
    res = client.post(f"/api/lessons/{lesson['id']}/pictures", json={})
    assert res.status_code == 200, res.text
    assert sent == [[104, 105]]
    assert [width(Image(c, "image/jpeg")) for c in cut] == [105]


def completing(client, monkeypatch, lesson: dict, pages: list[int], texts: list[str] | None = None) -> dict:
    """The lesson completed with one new photo (2 px wide), its card on it."""
    real = generation.extract_cards

    async def next_page(s, images, prompt, options, **kwargs):
        found = await real(s, images, prompt, options, **kwargs)
        found.deck.cards = [llm.Card(front="la famille", back="la familia", page=1)]
        return found

    monkeypatch.setattr(generation, "extract_cards", next_page)
    data = {"prompt": "FR → ES", **({"page_texts": json.dumps(texts)} if texts else {})}
    files = [("images", ("p.jpg", plain_image(2, 50), "image/jpeg"))]
    res = client.post(f"/api/lessons/{lesson['id']}/complete", files=files, data=data)
    assert res.status_code == 200, res.text
    done = res.json()
    assert done["pages"] == pages
    return done


def test_a_page_added_after_the_last_one_missing_takes_a_new_number(client, monkeypatch):
    """The last page (5) removed, cards still from it: the next page is 6, never 5 again (their
    "page 5" would point at it)."""
    files = [("images", (f"p{n}.jpg", plain_image(100 + n, 50), "image/jpeg")) for n in range(1, 6)]
    lesson = client.post("/api/extract", files=files, data={"prompt": "FR → ES"}).json()
    cards = [{**c, "page": 5} for c in lesson["cards"]]
    lesson = client.put(f"/api/lessons/{lesson['id']}", json={"deck": lesson["deck"], "cards": cards}).json()
    lessons.photo_path(lesson["id"], 5).unlink()
    done = completing(client, monkeypatch, lesson, [1, 2, 3, 4, 6])
    assert done["cards"][-1]["page"] == 6
    assert {c["page"] for c in done["cards"][:-1]} == {5}
    assert width(Image(lessons.photo(lesson["id"], 6), "image/jpeg")) == 2


def test_a_page_added_with_one_missing_in_the_middle_writes_over_none(client, monkeypatch):
    """Page 3 removed: the next page is 6, page 5 untouched (not written over as the 5th)."""
    lesson = lesson_without_page_3(client)
    before = lessons.photo(lesson["id"], 5)
    done = completing(client, monkeypatch, lesson, [1, 2, 4, 5, 6], texts=["the new page's text"])
    assert lessons.photo(lesson["id"], 5) == before
    assert done["cards"][-1]["page"] == 6
    assert done["photo_count"] == 5
    assert done["page_texts"] == ["", "", "", "", "", "the new page's text"]  # page 6's at index 5


def test_a_page_added_to_a_lesson_none_missing_comes_after_its_last(client, monkeypatch):
    files = [("images", (f"p{n}.jpg", plain_image(100 + n, 50), "image/jpeg")) for n in range(1, 3)]
    lesson = client.post("/api/extract", files=files, data={"prompt": "FR → ES"}).json()
    done = completing(client, monkeypatch, lesson, [1, 2, 3], texts=["t"])
    assert (done["cards"][-1]["page"], done["page_texts"]) == (3, ["", "", "t"])
