"""A lesson's life: created by a generation, saved, edited, listed, deleted — and
the storage beneath it (ids, folders, the summaries the list shows)."""

import asyncio
import json
import os

import pytest
from conftest import extract_lesson

from app import ankiconnect, lessons, storage
from app.models import CARD_ID, LessonIn
from app.routes import lessons as lessons_routes
from notosaurus_core.models import Card, Revision


def test_lesson_saved(client):
    lesson = extract_lesson(client)
    (summary,) = client.get("/api/lessons").json()
    assert summary["id"] == lesson["id"]
    assert summary["card_count"] == len(lesson["cards"])
    assert summary["exported_at"] is None

    photo = client.get(f"/api/lessons/{lesson['id']}/photos/2")
    assert photo.status_code == 200
    assert photo.content == b"photo 2"
    assert client.get(f"/api/lessons/{lesson['id']}/photos/3").status_code == 404


def test_lesson_updated(client):
    lesson = extract_lesson(client)
    edit = {
        "deck": "Espagnol::Leçon 6",
        "cards": [{"front": "le chat", "back": "el gato"}],
        "reverse": True,
        "typing": True,
        "dictation": True,
    }
    res = client.put(f"/api/lessons/{lesson['id']}", json=edit)
    assert res.status_code == 200

    reloaded = client.get(f"/api/lessons/{lesson['id']}").json()
    assert reloaded["deck"] == "Espagnol::Leçon 6"
    assert [c["back"] for c in reloaded["cards"]] == ["el gato"]
    assert reloaded["reverse"] is True and reloaded["typing"] is True and reloaded["dictation"] is True
    assert reloaded["prompt"] == "FR → ES"  # unchanged
    assert client.put("/api/lessons/999", json=edit).status_code == 404


def test_export_marks_the_lesson(client):
    lesson = extract_lesson(client)
    export = {"deck": "Corrigé", "cards": [{"front": "la mère", "back": "la madre"}], "lesson_id": lesson["id"]}
    assert client.post("/api/export", json=export).status_code == 200

    reloaded = client.get(f"/api/lessons/{lesson['id']}").json()
    assert reloaded["deck"] == "Corrigé"
    assert reloaded["exported_at"] is not None


def test_lesson_deleted(client):
    lesson = extract_lesson(client)
    photos = lessons.folder(lesson["id"])
    assert photos.is_dir()

    assert client.delete(f"/api/lessons/{lesson['id']}").status_code == 200
    assert not photos.exists()
    assert client.get(f"/api/lessons/{lesson['id']}").status_code == 404
    assert client.get("/api/lessons").json() == []


def test_one_folder_per_lesson(client, tmp_path):
    lesson = extract_lesson(client)
    folder = tmp_path / "data" / "lessons" / lesson["id"]
    assert lesson["id"].endswith("-espagnol-lecon-5-la-famille")
    assert sorted(p.name for p in folder.iterdir()) == ["lesson.json", "page-1.jpg", "page-2.jpg"]

    saved = json.loads((folder / "lesson.json").read_text(encoding="utf-8"))
    assert saved["deck"] == lesson["deck"]
    assert saved["prompt"] == "FR → ES"
    assert "id" not in saved  # the folder name is the id

    # Same deck the same day: a second folder, not an overwrite
    assert extract_lesson(client)["id"] == lesson["id"] + "-2"


def test_invalid_lesson_id(client):
    for bad in ["..", "../data", "A-majuscule", "-tiret"]:
        assert client.get(f"/api/lessons/{bad}").status_code == 404
    assert lessons.folder("../prompts.json") is None


def test_card_ids_checked(client):
    """A card's id names its picture's file (picture-<id>-<hash>.jpg): from the page, only
    letters and digits, never a path ("..\\" on Windows). Any other is replaced by a fresh one."""
    lesson = extract_lesson(client)
    url = f"/api/lessons/{lesson['id']}"
    for bad in ["../../evil", "..\\..\\evil", "a/b", "ABC", "abc\n", "a" * 41, "é"]:
        cards = [{"id": bad, "front": "le chat", "back": "el gato"}]
        saved = client.put(url, json={"deck": "D", "cards": cards})
        assert saved.status_code == 200, bad
        (card,) = saved.json()["cards"]
        assert card["id"] and card["id"] != bad and CARD_ID.fullmatch(card["id"]), bad
    # The ids Notosaurus, the page and the Android app give (12 hex), none yet, a short one
    cards = [{"id": i, "front": "le chat", "back": "el gato"} for i in ("", "0f3a9c41b2de", "rev1")]
    assert client.put(url, json={"deck": "D", "cards": cards}).status_code == 200
    ids = [c["id"] for c in client.get(url).json()["cards"]]
    assert ids[0] and ids[1:] == ["0f3a9c41b2de", "rev1"]


def test_odd_card_ids_from_the_ai_cleaned(client, monkeypatch):
    """The AI's answer may carry odd ids: the lesson is built all the same, each card with
    a fresh clean id, and none of them ever names a file."""
    lesson = extract_lesson(client)
    odd = ["../x", "Card 1", "..\\evil", "ok12"]

    async def revise(*args, **kwargs):
        cards = [Card(id=i, front=f"front {n}", back=f"back {n}") for n, i in enumerate(odd)]
        return Revision(deck="D", cards=cards, summary="done")

    monkeypatch.setattr(lessons_routes, "revise_cards", revise)
    body = {"deck": "D", "cards": lesson["cards"], "instruction": "fix"}
    revised = client.post(f"/api/lessons/{lesson['id']}/revise", json=body)
    assert revised.status_code == 200
    ids = [c["id"] for c in revised.json()["lesson"]["cards"]]
    assert all(i and CARD_ID.fullmatch(i) for i in ids) and ids[3] == "ok12"
    assert len(set(ids)) == 4 and not set(odd[:3]) & set(ids)
    assert [c["id"] for c in client.get(f"/api/lessons/{lesson['id']}").json()["cards"]] == ids
    assert not any(".." in p.name or " " in p.name for p in lessons.folder(lesson["id"]).rglob("*"))


def test_slugify():
    assert storage.slugify("Espagnol::Leçon 5 - La famille") == "espagnol-lecon-5-la-famille"
    assert storage.slugify("¿Cómo te llamas?") == "como-te-llamas"
    assert storage.slugify("日本語") == ""


def test_lessons_listed_with_one_question_to_anki(client, monkeypatch):
    for owner in ("Léa", "Paul", "Léa"):
        lessons.create(LessonIn(deck=f"{owner}::x", cards=[]), "p", [], owner=owner)
    asked = []

    async def active_profile():
        asked.append(1)
        return "Léa"

    monkeypatch.setattr(ankiconnect, "active_profile", active_profile)
    assert sorted(s["deck"] for s in client.get("/api/lessons").json()) == ["Léa::x", "Léa::x"]
    assert len(asked) == 1  # once for the list, not once per lesson


def test_lesson_list_follows_every_change(client, tmp_path):
    """The summaries are kept between listings: every change still shows."""
    a = lessons.create(LessonIn(deck="A", cards=[]), "p", [])
    assert [s.deck for s in lessons.list_all()] == ["A"]
    lessons.update(a.id, LessonIn(deck="A2", cards=[{"front": "x", "back": "y"}]))
    assert [(s.deck, s.card_count) for s in lessons.list_all()] == [("A2", 1)]
    # Changed by hand, the same size, in place, a moment later: its date tells
    path = tmp_path / "data" / "lessons" / a.id / "lesson.json"
    before = path.stat().st_mtime_ns
    path.write_text(path.read_text(encoding="utf-8").replace('"A2"', '"B2"'), encoding="utf-8")
    os.utime(path, ns=(before + 10**9, before + 10**9))
    assert [s.deck for s in lessons.list_all()] == ["B2"]
    b = lessons.create(LessonIn(deck="C", cards=[]), "p", [])
    assert {s.deck for s in lessons.list_all()} == {"B2", "C"}
    lessons.delete(b.id)
    assert [s.deck for s in lessons.list_all()] == ["B2"]
    # Saved by a newer Notosaurus: not listed, even after being listed
    path.write_text(json.dumps({**json.loads(path.read_text(encoding="utf-8")), "format": 99}), encoding="utf-8")
    assert lessons.list_all() == []


def test_decks_that_meet():
    from app.lesson_notes import _decks_meet

    assert _decks_meet("Maths", "maths") and _decks_meet("Maths", "Maths::Fractions")
    assert _decks_meet("Maths::Fractions", "Maths")
    assert not _decks_meet("Maths", "Mathsx::A") and not _decks_meet("Maths::A", "Maths::B")


def test_version_from_pyproject(client):
    import tomllib
    from pathlib import Path

    version = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert client.get("/api/config").json()["version"] == version
    assert client.get("/api/config").json()["computer_name"]  # the Android app shows it


def test_release_notes(tmp_path, monkeypatch):
    from tools import changelog_section

    changelog = tmp_path / "CHANGELOG.md"
    monkeypatch.setattr(changelog_section, "CHANGELOG", changelog)
    changelog.write_text(
        "# Changelog\n\n## [Unreleased]\n\n- Next thing\n\n## [0.2.0] - 2026-10-01\n\n- Done\n\n"
        "## [0.1.0]\n\n- First\n\n[0.2.0]: https://example.com\n"
    )
    assert changelog_section.notes("0.2.0") == "- Done"  # release being finalized
    assert changelog_section.notes("0.1.0") == "- First"  # last section, before the links
    assert changelog_section.notes("0.3.0") == "- Next thing"  # not finalized yet: Unreleased
    changelog.write_text("# Changelog\n\n## [Unreleased]\n\n## [0.1.0]\n\n- First\n")
    assert changelog_section.notes("0.2.0") == "No changes listed yet."


def test_page_files_revalidated(client):
    for path in ("/", "/admin.html", "/app.js", "/style.css", "/i18n/fr.json"):
        res = client.get(path)
        assert res.status_code == 200 and res.headers["cache-control"] == "no-cache", path
    etag = client.get("/style.css").headers["etag"]
    assert client.get("/style.css", headers={"If-None-Match": etag}).status_code == 304  # unchanged: nothing re-sent


def test_a_creation_that_fails_midway_leaves_nothing(client, tmp_path):
    """A photo that can't be written (a full disk…): no half lesson, neither its
    temporary folder nor the final one, and the error reaches the caller."""
    root = tmp_path / "data" / "lessons"
    with pytest.raises(TypeError):  # the second photo isn't bytes: written after the first
        lessons.create(LessonIn(deck="D", cards=[]), "p", [b"photo 1", None])
    assert not root.exists() or list(root.iterdir()) == []
    assert lessons.list_all() == []
    # The next one is made as usual, in the name the failed one would have had
    made = lessons.create(LessonIn(deck="D", cards=[]), "p", [b"photo 1"])
    assert [p.name for p in root.iterdir()] == [made.id] and made.photo_count == 1


def test_a_lesson_deleted_while_listed_just_disappears(client, monkeypatch):
    """Another request deletes a lesson between a look at its file and its reading:
    the list goes on without it, opening it finds nothing; no error."""
    kept = lessons.create(LessonIn(deck="Kept", cards=[]), "p", [])
    listed = lessons.create(LessonIn(deck="Listed", cards=[]), "p", [])
    assert {s.id for s in lessons.list_all()} == {kept.id, listed.id}  # its summary kept
    lessons.update(listed.id, LessonIn(deck="Listed again", cards=[]))  # read again next time
    gone = lessons.create(LessonIn(deck="Gone", cards=[]), "p", [])
    read, doomed = lessons._read, {gone.id, listed.id}

    def deleted_meanwhile(path):
        if path.name in doomed:
            assert lessons.delete(path.name)
        return read(path)

    monkeypatch.setattr(lessons, "_read", deleted_meanwhile)
    assert [s.id for s in lessons.list_all()] == [kept.id]
    assert client.get("/api/lessons").json()[0]["id"] == kept.id

    opened = lessons.create(LessonIn(deck="Opened", cards=[]), "p", [])
    doomed.add(opened.id)
    assert lessons.get(opened.id) is None


def test_edit_saves_what_the_change_changed(client):
    made = lessons.create(LessonIn(deck="D", cards=[Card(front="a", back="b")], voice="es_ES"), "p", [])
    lessons.set_anki_notes(made.id, "Alice", {"x": 1})

    def change(draft):
        draft.cards[0].back = "B"
        draft.cards.append(Card(front="c", back="d"))
        draft.shared = True  # never through a content change
        return "done"

    saved, result = asyncio.run(lessons.edit(made.id, change))
    assert result == "done"
    again = lessons.get(made.id)
    assert again == saved
    assert [(c.front, c.back) for c in again.cards] == [("a", "B"), ("c", "d")]
    assert again.cards[1].id  # new cards get their id
    assert again.cards[0].id == made.cards[0].id
    assert (again.deck, again.voice, again.shared, again.exported_at) == ("D", "es_ES", False, None)
    assert again.anki_notes == {"Alice": {"x": 1}} and again.updated_at >= made.updated_at


def test_edit_keeps_what_changed_meanwhile_and_nothing_on_failure(client):
    made = lessons.create(LessonIn(deck="D", cards=[Card(front="a", back="b")]), "p", [])

    async def slow(draft):  # the deck renamed during an AI call: the rename stays
        lessons.update(made.id, LessonIn(deck="Renamed", cards=draft.cards))
        draft.cards[0].back = "B"

    saved, _ = asyncio.run(lessons.edit(made.id, slow))
    assert (saved.deck, saved.cards[0].back) == ("Renamed", "B")

    def failing(draft):
        draft.cards[0].back = "lost"
        draft.cards.clear()
        raise RuntimeError("the AI failed")

    with pytest.raises(RuntimeError):
        asyncio.run(lessons.edit(made.id, failing))
    assert [c.back for c in lessons.get(made.id).cards] == ["B"]  # the copy never leaked back


def test_edit_of_a_lesson_gone(client):
    from app.errors import AppError

    with pytest.raises(AppError) as e:
        asyncio.run(lessons.edit("no-such-lesson", lambda draft: None))
    assert e.value.status == 404
