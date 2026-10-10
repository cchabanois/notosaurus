"""Generating a lesson: from photos or from the prompt alone, again in place, the
decks the AI is told about, the PDF pages' text, the fun facts, the AI correction."""

import json

from conftest import extract_lesson

from app.models import LessonIn
from notosaurus_core import llm, prompts


def test_extract_fake(client):
    files = [("images", ("p1.jpg", b"\xff\xd8fake", "image/jpeg"))] * 2
    res = client.post("/api/extract", files=files, data={"prompt": "FR → ES", "voice": "es-ES-ElviraNeural"})
    assert res.status_code == 201
    lesson = res.json()
    assert lesson["deck"].startswith("Espagnol")
    assert "2 photo(s)" in lesson["cards"][-1]["front"]
    assert lesson["photo_count"] == 2
    assert lesson["voice"] == "es-ES-ElviraNeural"
    assert lesson["prompt"] == "FR → ES"


def test_extract_rejects_non_image(client):
    files = [("images", ("a.pdf", b"%PDF", "application/pdf"))]
    res = client.post("/api/extract", files=files, data={"prompt": "x"})
    assert res.status_code == 400


def test_failed_extraction_creates_no_lesson(client, monkeypatch):
    monkeypatch.setenv("NOTOSAURUS_LLM", "inconnu")
    files = [("images", ("p.jpg", b"x", "image/jpeg"))]
    assert client.post("/api/extract", files=files, data={"prompt": "x"}).status_code == 502
    assert client.get("/api/lessons").json() == []


def test_lesson_from_the_prompt_alone(client):
    res = client.post("/api/extract", data={"prompt": "Cards with: le chat, le chien"})
    assert res.status_code == 201, res.text
    lesson = res.json()
    assert (lesson["photo_count"], lesson["prompt"]) == (0, "Cards with: le chat, le chien")
    assert "0 photo(s)" in lesson["cards"][-1]["front"]  # the fake provider got no image
    assert client.get(f"/api/lessons/{lesson['id']}").status_code == 200
    body = {"deck": lesson["deck"], "cards": lesson["cards"], "instruction": "add the colours"}
    assert client.post(f"/api/lessons/{lesson['id']}/revise", json=body).status_code == 200  # no photos to send

    # Neither a photo nor a prompt: nothing to work from
    res = client.post("/api/extract", data={"prompt": "  "})
    assert (res.status_code, res.json()["detail"]["code"]) == (400, "extract.no_input")


def test_prompt_only_tells_the_ai_there_is_no_photo():
    from notosaurus_core.models import Deck

    assert "no photo" in prompts._user_text("Cards with: le chat", "", photos=0)
    assert "no photo" not in prompts._user_text("Vocabulary", "", photos=2)
    assert "these instructions (no photo)" in prompts._revision_text("p", Deck(deck="D", cards=[]), "x", "en", photos=0)


def test_extract_fake_cloze(client):
    res = client.post("/api/extract", data={"prompt": "Texte à trous"})
    assert res.status_code == 201
    fronts = [c["front"] for c in res.json()["cards"]]
    assert all("{{c1::" in f for f in fronts)


def test_existing_decks_given_to_the_ai(anki, client, monkeypatch):
    from app import lessons, main

    anki.decks.update({"Maths": 1, "Maths::Fractions": 2, "Espagnol": 3})
    # Lessons: their decks count too (with their parents), another profile's private ones don't
    lessons.create(LessonIn(deck="Histoire::La Révolution", cards=[]), "p", [], owner="Léa")
    lessons.create(LessonIn(deck="Secret::De Paul", cards=[]), "p", [], owner="Paul")
    expected = ["Espagnol", "Histoire", "Histoire::La Révolution", "Maths", "Maths::Fractions"]
    assert client.get("/api/decks").json() == expected  # Léa's view, without Anki's "Default"

    seen = {}

    async def extract_cards(s, images, prompt, deck="", decks=(), **options):
        seen["decks"] = decks
        return await llm.extract_cards(s, images, prompt, deck, decks)

    monkeypatch.setattr(main, "extract_cards", extract_cards)
    assert client.post("/api/extract", data={"prompt": "Les fractions"}).status_code == 201
    assert seen["decks"] == expected
    text = prompts._user_text("Les fractions", "{matière}::{leçon}", 1, decks=expected)
    assert "Existing decks: Espagnol; Histoire; Histoire::La Révolution; Maths; Maths::Fractions" in text


def test_existing_decks_without_anki(client):
    from app import lessons

    lessons.create(LessonIn(deck="Anglais::Leçon 2", cards=[]), "p", [])
    assert client.get("/api/decks").json() == ["Anglais", "Anglais::Leçon 2"]


def test_fun_facts_only_when_asked(client):
    # Off by default: the AI isn't told about them
    assert prompts.FUN_FACTS not in prompts._user_text("Vocabulary", "", photos=1)
    assert prompts.FUN_FACTS in prompts._user_text("Vocabulary", "", photos=1, fun_facts=True)
    files = [("images", ("p.png", b"img", "image/png"))]
    plain = client.post("/api/extract", files=files, data={"prompt": "FR → ES"}).json()
    assert not any(c["fun_fact"] for c in plain["cards"])
    asked = client.post("/api/extract", files=files, data={"prompt": "FR → ES", "fun_facts": "true"}).json()
    assert asked["cards"][0]["fun_fact"]
    again = client.post(f"/api/lessons/{plain['id']}/regenerate", data={"prompt": "FR → ES", "fun_facts": "true"})
    assert again.json()["cards"][0]["fun_fact"]  # generated again with them


def test_each_lesson_has_a_deck_of_its_own(anki, client):
    first = extract_lesson(client)
    assert first["deck"] == "Espagnol::Leçon 5 - La famille"
    # The same lesson made again: its own deck, next to the first one's
    second = extract_lesson(client)
    assert second["deck"] == "Espagnol::Leçon 5 - La famille (2)"
    assert extract_lesson(client)["deck"] == "Espagnol::Leçon 5 - La famille (3)"

    # A deck the user has in Anki counts too, whatever its case
    client.delete(f"/api/lessons/{second['id']}")
    anki.decks["espagnol::leçon 5 - la famille (2)"] = 99
    assert extract_lesson(client)["deck"] == "Espagnol::Leçon 5 - La famille (4)"

    # Sent to Anki, then generated again: the lesson keeps its own deck
    client.post("/api/anki/send", json={"deck": first["deck"], "cards": first["cards"], "lesson_id": first["id"]})
    again = client.post(f"/api/lessons/{first['id']}/regenerate", data={"prompt": "FR → ES"}).json()
    assert again["deck"] == "Espagnol::Leçon 5 - La famille"


def test_regenerate_replaces_the_lesson(client, tmp_path):
    from app import lessons

    lesson = extract_lesson(client)
    url = f"/api/lessons/{lesson['id']}"
    folder = lessons.folder(lesson["id"])
    (folder / "images").mkdir()
    (folder / "images" / "picture-old-12345678.jpg").write_bytes(b"old picture")

    # Another prompt, one photo instead of two: the same lesson, its content replaced
    files = [("images", ("p.jpg", b"new photo", "image/jpeg"))]
    new = client.post(f"{url}/regenerate", files=files, data={"prompt": "Texte à trous", "voice": "auto"}).json()
    assert new["id"] == lesson["id"] and new["created_at"] == lesson["created_at"]
    assert new["prompt"] == "Texte à trous" and new["deck"] == "Histoire::La Révolution française"
    assert all("{{c" in c["front"] for c in new["cards"])
    assert (new["photo_count"], (folder / "page-1.jpg").read_bytes()) == (1, b"new photo")
    assert not (folder / "page-2.jpg").exists()
    assert len(new["ai_calls"]) == 2  # the first generation's, then this one
    assert [x["id"] for x in client.get("/api/lessons").json()] == [lesson["id"]]  # no second lesson
    assert (folder / "images" / "picture-old-12345678.jpg").exists()  # kept for "Undo"

    # "Undo": the page sends the old version back, prompt included
    old = {k: lesson[k] for k in ("deck", "cards", "voice", "frames", "prompt", "choice")}
    undone = client.put(url, json=old).json()
    assert (undone["prompt"], undone["deck"], undone["cards"]) == (lesson["prompt"], lesson["deck"], lesson["cards"])

    # Pictures no card uses any more go at the next export
    client.post("/api/export", json={**old, "lesson_id": lesson["id"]})
    assert not (folder / "images" / "picture-old-12345678.jpg").exists()


def test_regenerate_keeps_the_review_options(client):
    lesson = extract_lesson(client)
    url = f"/api/lessons/{lesson['id']}"
    client.put(url, json={"deck": lesson["deck"], "cards": lesson["cards"], "reverse": True, "typing": True})
    new = client.post(f"{url}/regenerate", data={"prompt": "FR → ES", "dictation": "true"}).json()
    assert (new["reverse"], new["typing"], new["dictation"]) == (True, True, True)  # the prompt's added


# --- The AI correction --------------------------------------------------------


def test_revision_by_instruction(client):
    lesson = extract_lesson(client)
    n = len(lesson["cards"])
    body = {
        "deck": lesson["deck"],
        "cards": lesson["cards"],
        "voice": "es-ES-ElviraNeural",
        "instruction": "supprime la dernière carte",
    }
    res = client.post(f"/api/lessons/{lesson['id']}/revise", json=body)
    assert res.status_code == 200
    assert res.json()["summary"]
    assert len(res.json()["lesson"]["cards"]) == n - 1

    # Saved on the server, with the voice sent by the page
    saved = client.get(f"/api/lessons/{lesson['id']}").json()
    assert len(saved["cards"]) == n - 1
    assert saved["voice"] == "es-ES-ElviraNeural"

    # Works on the cards sent (possibly unsaved edits), not the stored ones
    body = {"deck": "D", "cards": [{"front": "le chat", "back": "el gato"}], "instruction": "ajoute les couleurs"}
    cards = client.post(f"/api/lessons/{lesson['id']}/revise", json=body).json()["lesson"]["cards"]
    assert [c["front"] for c in cards] == ["le chat", "(demo addition)"]


def test_revision_errors(client, monkeypatch):
    body = {"deck": "D", "cards": [], "instruction": "x"}
    assert client.post("/api/lessons/unknown/revise", json=body).status_code == 404
    lesson = extract_lesson(client)
    assert client.post(f"/api/lessons/{lesson['id']}/revise", json={**body, "instruction": ""}).status_code == 422
    monkeypatch.setenv("NOTOSAURUS_LLM", "inconnu")
    assert client.post(f"/api/lessons/{lesson['id']}/revise", json=body).status_code == 502


def test_pdf_page_texts_go_to_the_ai_and_stay_with_the_lesson(client, monkeypatch):
    from app import main

    page = "La Révolution française commence en 1789 avec la prise de la Bastille."
    # Only the PDF pages with text: a photo ("") and a scan (a few stray characters) have none
    text = prompts._user_text("Q/R", "", photos=3, texts=[page, "", " i . "])
    assert (
        f"Text of photo 1, from its PDF:\n<<<\n{page}\n>>>" in text and "photo 2" not in text and "photo 3" not in text
    )
    assert "Text of photo" not in prompts._user_text("Q/R", "", photos=1)
    assert len(prompts._user_text("Q/R", "", photos=1, texts=["x" * 20_000])) < 9_000  # a page at most PAGE_TEXT_MAX

    seen = []

    async def extract_cards(s, images, prompt, deck="", decks=(), page_texts=(), **options):
        seen.append(list(page_texts))
        return await llm.extract_cards(s, images, prompt, deck, decks)

    monkeypatch.setattr(main, "extract_cards", extract_cards)
    files = [("images", (f"p{n}.png", b"img", "image/png")) for n in (1, 2)]
    texts = json.dumps([page, ""])
    lesson = client.post("/api/extract", files=files, data={"prompt": "FR → ES", "page_texts": texts}).json()
    assert seen[-1] == [page, ""] and lesson["page_texts"] == [page, ""]
    assert "page_texts" not in client.get("/api/lessons").json()[0]  # not in the lists
    again = client.post(
        f"/api/lessons/{lesson['id']}/regenerate", files=files, data={"prompt": "FR → ES", "page_texts": texts}
    ).json()
    assert again["page_texts"] == [page, ""]
    # One text per photo, or none: the AI never gets a text on the wrong photo
    client.post("/api/extract", files=files, data={"prompt": "FR → ES", "page_texts": json.dumps([page])})
    assert seen[-1] == []


def test_a_figure_meant_but_left_undescribed_is_described(monkeypatch):
    """The model set a card's picture on the back but described no figure (now and then,
    thinking little): one light call, seeing the page, describes it. Other cards: no call."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    from notosaurus_core.config import AIConfig
    from notosaurus_core.models import CardFigure, Figures

    calls = []

    async def generate(s, images, text, schema, system=None, **options):
        calls.append((schema.__name__, text, len(images)))
        if schema is Figures:
            return Figures(figures=[CardFigure(card=0, figure="Deux ensembles A et B, leur partie commune hachurée")])
        cards = [
            {"front": "L'intersection de A et B ?", "back": "Les éléments communs", "picture_on_back": True},
            {"front": "Notation ?", "back": "A ∩ B"},
            {"front": "Le produit cartésien ?", "back": "Les couples", "picture_on_back": True, "figure": "Un tableau"},
        ]
        return schema.model_validate({"deck": "Maths", "cards": cards})

    monkeypatch.setattr(llm, "_generate", generate)
    s = AIConfig(llm="gemini", gemini_api_key="k")
    with ThreadPoolExecutor(1) as pool:
        found = pool.submit(asyncio.run, llm.extract_cards(s, [], "Automatique")).result()
    assert [c.figure for c in found.deck.cards] == [
        "Deux ensembles A et B, leur partie commune hachurée",
        "",
        "Un tableau",
    ]
    assert [name for name, _, _ in calls][1] == "Figures" and len(calls) == 2
    assert "0. L'intersection de A et B ? → Les éléments communs" in calls[1][1]  # only the card left undescribed
