"""A lesson's life: created by a generation, saved, edited, listed, deleted — and
the storage beneath it (ids, folders, the summaries the list shows)."""

import json
import os

from conftest import extract_lesson

from app import ankiconnect, lessons, storage
from app.models import LessonIn


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
    from app.main import _decks_meet

    assert _decks_meet("Maths", "maths") and _decks_meet("Maths", "Maths::Fractions")
    assert _decks_meet("Maths::Fractions", "Maths")
    assert not _decks_meet("Maths", "Mathsx::A") and not _decks_meet("Maths::A", "Maths::B")


def test_version_from_pyproject(client):
    import tomllib
    from pathlib import Path

    version = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert client.get("/api/config").json()["version"] == version


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
