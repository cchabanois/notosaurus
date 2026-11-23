"""The lesson corrected as a whole ("Correct the cards with the AI"): its photos sent when a
call takes them all, none above (correction.revise_photos), the AI then told its pages aren't
shown and correcting from the cards, which keep their page and their place on a diagram."""

import io

from helpers import plain_image, run
from PIL import Image as PILImage

from notosaurus_core import ai, llm
from notosaurus_core.calls import Image
from notosaurus_core.config import AIConfig
from notosaurus_core.models import Card, Deck, Mask, Revision
from notosaurus_core.prompts import _revision_text

S = AIConfig(llm="gemini", gemini_api_key="k")
NOT_SHOWN = "The lesson's photos (its pages) are not shown here"


def lesson_of(client, count: int) -> dict:
    """A lesson of `count` photos (10 a call, then completed), photo n `100 + n` pixels wide."""
    files = [("images", (f"p{n}.jpg", plain_image(100 + n, 50), "image/jpeg")) for n in range(1, count + 1)]
    lesson = client.post("/api/extract", files=files[:10], data={"prompt": "FR → ES"}).json()
    if count > 10:
        url = f"/api/lessons/{lesson['id']}/complete"
        lesson = client.post(url, files=files[10:], data={"prompt": "FR → ES"}).json()
    assert lesson["photo_count"] == count
    return lesson


def revise_sent(client, monkeypatch, lesson: dict) -> tuple[list[int], str, dict]:
    """The lesson corrected through the route (the demo AI): the widths of the photos the AI
    was sent, its text, and the answer."""
    shown = []
    real = ai._ask_provider

    async def ask(s, images, text, schema, *args, **kwargs):
        shown.append(([PILImage.open(io.BytesIO(i.data)).width for i in images], text))
        return await real(s, images, text, schema, *args, **kwargs)

    monkeypatch.setattr(ai, "_ask_provider", ask)
    body = {"deck": lesson["deck"], "cards": lesson["cards"], "instruction": "ajoute el abuelo"}
    res = client.post(f"/api/lessons/{lesson['id']}/revise", json=body)
    assert res.status_code == 200, res.text
    ((sent, text),) = shown
    return sent, text, res.json()


def test_a_lesson_a_call_takes_is_corrected_with_all_its_pages(client, monkeypatch):
    lesson = lesson_of(client, 10)
    sent, text, _ = revise_sent(client, monkeypatch, lesson)
    assert sent == list(range(101, 111))
    assert NOT_SHOWN not in text


def test_a_longer_lesson_is_corrected_from_its_cards(client, monkeypatch):
    """11 pages, more than a call takes: none sent (the relay would refuse them), the AI told
    so; the cards keep their page, the lesson its photos."""
    lesson = lesson_of(client, 11)
    sent, text, answer = revise_sent(client, monkeypatch, lesson)
    assert sent == [] and NOT_SHOWN in text
    revised = answer["lesson"]
    assert revised["photo_count"] == 11
    pages = {c["id"]: c["page"] for c in lesson["cards"]}
    kept = [c for c in revised["cards"] if c["id"] in pages]
    assert kept and all(c["page"] == pages[c["id"]] for c in kept)
    assert [c["page"] for c in revised["cards"] if c["id"] not in pages] == [0]  # the card added


def test_the_prompt_tells_pages_not_shown_from_a_lesson_without_photos():
    """Not shown: said, the AI working from the cards and saying what it couldn't do; not a
    lesson "made from these instructions (no photo)". Without a photo the cards' pages aren't
    shown (numbered among photos the AI doesn't see)."""
    deck = Deck(deck="D", cards=[Card(front="q", back="a", page=7)])
    none = _revision_text("p", deck, "check against the lesson", "French", 0, sent="none")
    assert NOT_SHOWN in none and "(no photo)" not in none
    assert "never make up what the lesson says" in none
    assert "what you could not do without the pages" in none
    assert '"page"' not in none
    without = _revision_text("p", deck, "fix", "French", 0)
    assert "(no photo)" in without and NOT_SHOWN not in without and '"page"' not in without
    shown = _revision_text("p", deck, "fix", "French", 2)
    assert "these photos with" in shown and NOT_SHOWN not in shown and '"page": 7' in shown


def test_no_page_asked_of_the_ai_without_a_photo(monkeypatch):
    schemas = []

    async def ask(s, images, text, schema, *args, **kwargs):
        schemas.append(schema.model_json_schema()["$defs"]["Card"]["properties"])
        return schema.model_validate({"deck": "D", "cards": [{"front": "q", "back": "a"}], "summary": "ok"})

    monkeypatch.setattr(ai, "_ask_provider", ask)
    deck = Deck(deck="D", cards=[Card(front="q", back="a", page=3)])
    run(llm.revise_cards(S, [], "p", deck, "fix", photos_sent="none"))
    run(llm.revise_cards(S, [Image(plain_image(40, 30), "image/jpeg")], "p", deck, "fix"))
    assert ["page" in properties for properties in schemas] == [False, True]


def test_a_diagram_card_keeps_its_place_without_the_photos(monkeypatch):
    """A label hidden on a diagram keeps its mask (it is on a photo not sent), and its page; a
    mask the AI gives a new card, on no photo it saw, is dropped."""
    mask = Mask(page=4, n=2, box=[0.2, 0.1, 0.4, 0.3])
    before = [Card(id="c1", front="What is (2)?", back="mouth", mask=mask, page=4)]
    answer = {
        "deck": "D",
        "cards": [
            {"front": "What is (2)?", "back": "the mouth"},
            {"front": "What is (3)?", "back": "nose", "mask": {"page": 4, "n": 3, "box": [1, 2, 3, 4]}},
        ],
        "summary": "ok",
    }

    async def ask(s, images, text, schema, *args, **kwargs):
        return schema.model_validate(answer)

    monkeypatch.setattr(ai, "_ask_provider", ask)
    for provider in ("gemini", "openai", "fake"):  # every box format: the demo AI's in fractions
        s = S.model_copy(update={"llm": provider})
        revision: Revision = run(llm.revise_cards(s, [], "p", Deck(deck="D", cards=before), "x", photos_sent="none"))
        kept, added = revision.cards
        assert kept.mask == mask and kept.page == 4 and kept.id == "c1"
        assert added.mask is None and added.page == 0
