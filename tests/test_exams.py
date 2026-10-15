"""The tests to prepare (app/exams.py): lessons, whole or some cards, gathered under a tag
on their notes in Anki, which follows the test's changes; what the page is told."""

import httpx
from conftest import anki_unreachable, extract_lesson

from app import ankiconnect, exams

INTERRO = {"name": "Interro SVT de lundi", "date": "2026-10-20"}


def _sent(client, lesson: dict) -> dict:
    """The lesson's own cards sent to Anki (its notes recorded)."""
    body = {"deck": lesson["deck"], "cards": lesson["cards"], "voice": "", "lesson_id": lesson["id"]}
    assert client.post("/api/anki/send", json=body).status_code == 200
    return client.get(f"/api/lessons/{lesson['id']}").json()


def _tags(anki) -> dict[int, set[str]]:
    return {i: {t for t in n["tags"] if t.startswith(exams.TAG_PREFIX)} for i, n in anki.notes.items()}


def test_a_test_tags_its_lessons_notes_whole_or_some_cards(anki, client):
    lesson = _sent(client, extract_lesson(client))
    ids = [c["id"] for c in lesson["cards"]]
    assert client.get("/api/exams").json() == []

    res = client.put("/api/exams/interro-svt", json={**INTERRO, "lessons": [{"lesson": lesson["id"]}]})
    assert res.status_code == 200
    view = res.json()
    assert view["tag"] == "Exam::Interro_SVT_de_lundi" and view["search"] == "tag:Exam::Interro_SVT_de_lundi"
    assert view["anki"] is True and view["date"] == "2026-10-20"
    assert view["lessons"] == [
        {"lesson": lesson["id"], "cards": None, "deck": lesson["deck"], "total": len(ids), "in_anki": len(ids)}
    ]
    assert view["deck"] == lesson["deck"]
    assert all(tags == {"Exam::Interro_SVT_de_lundi"} for tags in _tags(anki).values())  # every note

    # Some of its cards only: the others lose the tag
    some = [{"lesson": lesson["id"], "cards": ids[:1]}]
    res = client.put("/api/exams/interro-svt", json={**INTERRO, "lessons": some})
    assert res.json()["lessons"][0]["total"] == 1 and res.json()["lessons"][0]["in_anki"] == 1
    tagged = [i for i, tags in _tags(anki).items() if tags]
    assert len(tagged) == 1 and anki.notes[tagged[0]]["fields"]["Front"] == lesson["cards"][0]["front"]

    # Renamed: the tag follows
    renamed = {**INTERRO, "name": "Brevet blanc", "lessons": [{"lesson": lesson["id"]}]}
    res = client.put("/api/exams/interro-svt", json=renamed)
    assert res.json()["tag"] == "Exam::Brevet_blanc"
    assert all(tags == {"Exam::Brevet_blanc"} for tags in _tags(anki).values())
    assert [e["name"] for e in client.get("/api/exams").json()] == ["Brevet blanc"]

    # Deleted: the notes stay, without the tag
    assert client.delete("/api/exams/interro-svt").json() == {"deleted": True, "anki": True}
    assert len(anki.notes) == len(ids) and not any(_tags(anki).values())
    assert client.delete("/api/exams/interro-svt").status_code == 404


def test_cards_sent_after_the_test_was_made_carry_its_tag(anki, client):
    lesson = extract_lesson(client)
    res = client.put("/api/exams/interro-svt", json={**INTERRO, "lessons": [{"lesson": lesson["id"]}]})
    assert res.json()["lessons"][0]["in_anki"] == 0  # nothing in Anki yet
    _sent(client, lesson)
    assert anki.notes and all(tags == {"Exam::Interro_SVT_de_lundi"} for tags in _tags(anki).values())
    assert client.get("/api/exams").json()[0]["lessons"][0]["in_anki"] == len(lesson["cards"])
    # Sent again (a correction): the tag kept, not doubled
    _sent(client, lesson)
    assert all(n["tags"].count("Exam::Interro_SVT_de_lundi") == 1 for n in anki.notes.values())


def test_a_lesson_deleted_leaves_the_test_and_a_missing_one_is_skipped(anki, client):
    lesson, other = extract_lesson(client), extract_lesson(client)
    parts = [{"lesson": lesson["id"]}, {"lesson": other["id"]}, {"lesson": "2026-01-01-gone"}]
    view = client.put("/api/exams/interro-svt", json={**INTERRO, "lessons": parts}).json()
    assert [p["lesson"] for p in view["lessons"]] == [lesson["id"], other["id"]]  # the missing one dropped
    client.delete(f"/api/lessons/{other['id']}")
    assert [p["lesson"] for p in client.get("/api/exams").json()[0]["lessons"]] == [lesson["id"]]
    assert exams.get("interro-svt").lessons[0].lesson == lesson["id"]


def test_anki_closed_the_test_is_saved_all_the_same(anki, client, monkeypatch):
    lesson = _sent(client, extract_lesson(client))
    monkeypatch.setattr(ankiconnect, "_transport", httpx.MockTransport(anki_unreachable))
    res = client.put("/api/exams/interro-svt", json={**INTERRO, "lessons": [{"lesson": lesson["id"]}]})
    assert res.status_code == 200 and res.json()["anki"] is False  # saved; the tags at the next send
    assert exams.get("interro-svt") is not None
    assert client.delete("/api/exams/interro-svt").json() == {"deleted": True, "anki": False}


def test_refused(client):
    assert client.put("/api/exams/Interro SVT", json=INTERRO).status_code == 422  # not an id
    assert client.put("/api/exams/a", json={"name": ""}).status_code == 422
    assert client.put("/api/exams/a", json={**INTERRO, "date": "lundi"}).status_code == 422


def test_the_tag_and_the_deck_anki_studies_in():
    assert exams.tag_text("Interro SVT de lundi") == "Interro_SVT_de_lundi"
    assert exams.tag_text('Maths : "chapitre 3" *') == "Maths_chapitre_3"
    assert exams.tag_text("  ") == "exam"
    assert exams.common_deck(["SVT::Chapitre 1", "SVT::Chapitre 2::Trous"]) == "SVT"
    assert exams.common_deck(["Jules::5e::SVT", "jules::5e::Histoire"]) == "Jules::5e"
    assert exams.common_deck(["SVT", "Histoire"]) == ""  # no deck holds both: the search instead
    assert exams.common_deck([]) == ""
