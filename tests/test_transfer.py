"""The lessons in a file (app/transfer.py): exported with what they need (photos, pictures,
sounds, the children, the tests, the prompts; no setting), imported on another installation
or the same one, the newer kept, nothing written outside a lesson's folder."""

import asyncio
import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest
from conftest import ADMIN, extract_lesson

from app import children, exams, lessons, prompts, storage, transfer
from app.errors import AppError
from notosaurus_core import tts

PHONE = "es-ES-Chirp3-HD-Aoede"  # the relay's voice: a lesson from the phone


def run(coroutine):
    """Run on a thread of its own: after the page tests, Playwright's loop runs on this one."""
    with ThreadPoolExecutor(1) as thread:
        return thread.submit(asyncio.run, coroutine).result()


@pytest.fixture
def lesson(client):
    """A lesson with its photos, a sound, a picture, its notes in Anki; a child, a test, a prompt."""
    made = extract_lesson(client)
    folder = lessons.folder(made["id"])
    (folder / "audio").mkdir()
    (folder / "audio" / "la-madre-55895502.mp3").write_bytes(b"ID3 la madre")
    (folder / "images").mkdir()
    (folder / "images" / "picture-a.jpg").write_bytes(b"\xff\xd8 a picture")
    lessons.set_anki_notes(made["id"], "Léa", {made["cards"][0]["id"]: 1234})
    children.save_all([children.Child(id="jules", name="Jules", grade="5e")])
    exams.save("brevet", exams.ExamIn(name="Brevet blanc", lessons=[exams.ExamLesson(lesson=made["id"])]))
    prompts._write([prompts.Prompt(id=1, name="Vocabulaire", text="Une carte par mot")], {})
    return made


def change(id: str, **changes):
    """The lesson saved with these changes, the rest as it is."""
    there = lessons.get(id)
    lessons.update(id, lessons.LessonIn(**{"deck": there.deck, "cards": there.cards, "voice": there.voice, **changes}))


def another_install(monkeypatch, tmp_path, name="other"):
    """Another computer: its own data folder (and its own installation's id)."""
    monkeypatch.setenv("NOTOSAURUS_DATA", str(tmp_path / name))


def test_an_export_holds_the_lessons_and_no_setting(lesson, tmp_path):
    path = tmp_path / "export.zip"
    assert transfer.export(path) == 1
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        manifest = json.loads(z.read("manifest.json"))
    id = lesson["id"]
    assert {f"lessons/{id}/lesson.json", f"lessons/{id}/page-1.jpg", f"lessons/{id}/page-2.jpg"} <= names
    assert {f"lessons/{id}/audio/la-madre-55895502.mp3", f"lessons/{id}/images/picture-a.jpg"} <= names
    assert {"children.json", "exams.json", "prompts.json"} <= names
    assert not any("settings" in n or "install" in n or "ai-calls" in n for n in names)  # no key, no password
    assert (manifest["format"], manifest["app"], manifest["device"], manifest["lessons"]) == (
        1,
        "notosaurus",
        "computer",
        1,
    )
    assert manifest["install"] == transfer.install_id()


def test_imported_on_another_computer(lesson, tmp_path, monkeypatch):
    path = tmp_path / "export.zip"
    transfer.export(path)
    another_install(monkeypatch, tmp_path)
    done = run(transfer.import_(path))
    assert done.dict() == {"added": 1, "replaced": 0, "kept": 0, "children": 1, "exams": 1, "prompts": 1}
    there = lessons.get(lesson["id"])  # the same id: its notes' tag in Anki
    assert [c.front for c in there.cards] == [c["front"] for c in lesson["cards"]] and there.photo_count == 2
    assert there.anki_notes == {}  # another collection's notes: found again by their tag
    folder = lessons.folder(lesson["id"])
    assert (folder / "audio" / "la-madre-55895502.mp3").read_bytes() == b"ID3 la madre"
    assert (folder / "images" / "picture-a.jpg").is_file()
    assert [c.name for c in children.list_all()] == ["Jules"]
    assert [e.name for e in exams.list_all()] == ["Brevet blanc"]
    assert [p.name for p in prompts._read()[0]] == ["Vocabulaire"]
    assert not [p for p in (storage.data_dir() / "lessons").iterdir() if p.name.startswith(".")]  # nothing left over

    # Imported again: nothing twice
    assert run(transfer.import_(path)).dict() == {
        "added": 0,
        "replaced": 0,
        "kept": 1,
        "children": 0,
        "exams": 0,
        "prompts": 0,
    }
    assert len(children.list_all()) == 1 and len(prompts._read()[0]) == 1


def test_imported_back_on_the_same_computer_keeps_its_notes(lesson, tmp_path):
    path = tmp_path / "export.zip"
    transfer.export(path)
    lessons.delete(lesson["id"])
    assert run(transfer.import_(path)).added == 1
    assert lessons.get(lesson["id"]).anki_notes == {"Léa": {lesson["cards"][0]["id"]: 1234}}  # this Anki's still


def test_the_newer_lesson_kept(lesson, tmp_path, monkeypatch):
    path = tmp_path / "export.zip"
    transfer.export(path)
    another_install(monkeypatch, tmp_path)
    run(transfer.import_(path))
    # Changed here since: the export's older, kept as it is here
    change(lesson["id"], deck="Changé ici")
    assert run(transfer.import_(path)).kept == 1
    assert lessons.get(lesson["id"]).deck == "Changé ici"
    # An export made after a change there: replaces it
    monkeypatch.setenv("NOTOSAURUS_DATA", str(tmp_path / "data"))
    storage_now = storage.now
    monkeypatch.setattr(storage, "now", lambda: "2099-01-01T00:00:00")
    change(lesson["id"], deck="Changé là-bas")
    monkeypatch.setattr(storage, "now", storage_now)
    newer = tmp_path / "newer.zip"
    transfer.export(newer)
    another_install(monkeypatch, tmp_path)
    assert run(transfer.import_(newer)).replaced == 1
    assert lessons.get(lesson["id"]).deck == "Changé là-bas"


def test_a_lesson_from_the_phone_gets_a_voice_of_this_computer(lesson, tmp_path, monkeypatch):
    """Its voice the relay's: each card keeps it (its sound, made there), the lesson gets
    this computer's voice of that language."""
    change(lesson["id"], voice=PHONE)
    path = tmp_path / "export.zip"
    transfer.export(path)
    another_install(monkeypatch, tmp_path)
    asked = []

    async def voice_for(language, chosen=None):
        asked.append(language)
        return "es-ES-ElviraNeural"

    monkeypatch.setattr(tts, "voice_for", voice_for)
    run(transfer.import_(path))
    there = lessons.get(lesson["id"])
    assert asked == ["es-ES"] and there.voice == "es-ES-ElviraNeural"
    assert {c.voice for c in there.cards} == {PHONE}


def zip_of(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buffer.getvalue()


MANIFEST = json.dumps({"format": 1, "app": "notosaurus", "install": "elsewhere"}).encode()


def test_only_lessons_folders_written(client, tmp_path):
    """A file made by hand: nothing outside a lesson's folder, nothing but our names."""
    path = tmp_path / "bad.zip"
    lesson = json.dumps(
        {
            "deck": "D",
            "cards": [],
            "prompt": "p",
            "created_at": "2026-10-30T10:00:00",
            "updated_at": "2026-10-30T10:00:00",
        }
    )
    path.write_bytes(
        zip_of(
            {
                "manifest.json": MANIFEST,
                "lessons/ok-lesson/lesson.json": lesson.encode(),
                "lessons/ok-lesson/../../../evil.txt": b"x",
                "lessons/../evil/lesson.json": lesson.encode(),
                "lessons/Bad Name/lesson.json": lesson.encode(),
                "settings.json": b'{"llm": "evil"}',
            }
        )
    )
    assert run(transfer.import_(path)).added == 1
    data = storage.data_dir()
    assert (
        not (tmp_path / "evil.txt").exists()
        and not (data / "evil.txt").exists()
        and not (data.parent / "evil").exists()
    )
    assert sorted(p.name for p in (data / "lessons").iterdir()) == ["ok-lesson"]
    assert (
        "evil" not in (data / "settings.json").read_text(encoding="utf-8")
        if (data / "settings.json").exists()
        else True
    )


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"not a zip", "transfer.not_an_export"),
        (zip_of({"lessons/a/lesson.json": b"{}"}), "transfer.not_an_export"),  # no manifest
        (zip_of({"manifest.json": json.dumps({"format": 99, "app": "notosaurus"}).encode()}), "transfer.too_new"),
    ],
)
def test_not_an_export(client, tmp_path, content, code):
    path = tmp_path / "bad.zip"
    path.write_bytes(content)
    with pytest.raises(AppError) as e:
        run(transfer.import_(path))
    assert e.value.code == code


def test_the_settings_routes(admin, lesson, tmp_path):
    res = admin.get("/api/admin/transfer", headers=ADMIN)
    assert res.status_code == 200 and res.headers["content-type"] == "application/zip"
    assert res.headers["content-disposition"].startswith('attachment; filename="notosaurus-')
    assert admin.get("/api/admin/transfer").status_code == 401  # the settings' password
    lessons.delete(lesson["id"])
    done = admin.post(
        "/api/admin/transfer", headers=ADMIN, files={"file": ("export.zip", res.content, "application/zip")}
    )
    assert done.status_code == 200 and done.json()["added"] == 1
    refused = admin.post("/api/admin/transfer", headers=ADMIN, files={"file": ("x.zip", b"nope", "application/zip")})
    assert refused.status_code == 400 and refused.json()["detail"]["code"] == "transfer.not_an_export"
