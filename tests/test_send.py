"""Sending straight into Anki through AnkiConnect: added, updated (never
duplicated), note types converted while keeping the review history, sync, and
what happens to a lesson's Anki notes when it is deleted."""

import json

import httpx
from conftest import ADMIN, CLOZE, SEND, FakeAnki, extract_lesson

from app import ankiconnect, settings, tts
from app.main import app


def test_anki_unavailable(client, monkeypatch):
    def refuse(request):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(ankiconnect, "_transport", httpx.MockTransport(refuse))
    status = client.get("/api/anki/status").json()
    assert status == {"available": False, "error": {"code": "anki.unreachable", "params": {}}}
    assert client.post("/api/anki/send", json=SEND).status_code == 502


def test_direct_send_to_anki(anki, client):
    # AnkiConnect doesn't say whether the profile is logged in to AnkiWeb: unknown
    assert client.get("/api/anki/status").json() == {"available": True, "version": 6, "profile": "Léa", "sync": None}
    lesson = extract_lesson(client)
    res = client.post("/api/anki/send", json={**SEND, "lesson_id": lesson["id"]})
    assert res.status_code == 200
    assert res.json() == {
        "added": 2,
        "updated": 0,
        "synced": True,
        "sync_error": None,
        "sync_skipped": False,
        "converted": 0,
        "conversion_unsupported": False,
        "audio_failures": 0,
    }

    (model,) = anki.models.values()
    assert model["inOrderFields"] == ["Front", "Back", "Info", "Audio"]
    assert set(anki.decks) == {"Espagnol::Leçon 5::Vocabulaire", "Espagnol::Leçon 5"}
    mother = anki.notes[1]
    assert mother["fields"]["Audio"] == f"[sound:{tts.filename('la madre', 'es-ES-ElviraNeural')}]"
    assert mother["tags"] == ["famille_proche", f"notosaurus::{lesson['id']}"]  # its lesson, to find it again
    assert anki.notes[2]["fields"]["Front"] == "&lt;b&gt;"
    assert set(anki.media) == {
        tts.filename("la madre", "es-ES-ElviraNeural"),
        tts.filename("el padre", "es-ES-ElviraNeural"),
    }
    assert anki.calls[-1] == "sync"
    assert client.get(f"/api/lessons/{lesson['id']}").json()["exported_at"] is not None

    # Sent again after a correction: notes are updated, not duplicated
    corrected = {**SEND, "cards": [{**SEND["cards"][0], "back": "la mamá"}, SEND["cards"][1]]}
    res = client.post("/api/anki/send", json=corrected).json()
    assert (res["added"], res["updated"]) == (0, 2)
    assert len(anki.notes) == 2
    assert anki.notes[1]["fields"]["Back"] == "la mamá"
    assert "createModel" not in anki.calls[anki.calls.index("sync") :]  # note type reused


def test_send_without_sync_or_with_key(anki, admin):
    admin.put("/api/admin/settings", headers=ADMIN, json={"ankiconnect_key": "k3y", "anki_sync": False})
    res = admin.post("/api/anki/send", json=SEND).json()
    assert res["synced"] is False and "sync" not in anki.calls
    assert set(anki.keys) == {"k3y"}


def test_sync_failure_not_blocking(client, monkeypatch):
    fake = FakeAnki(fail_sync=True)
    monkeypatch.setattr(ankiconnect, "_transport", httpx.MockTransport(fake.handle))
    res = client.post("/api/anki/send", json=SEND).json()
    assert res["added"] == 2 and res["synced"] is False
    assert res["sync_error"] == {
        "code": "anki.error",
        "params": {"action": "sync", "detail": "AnkiWeb: login required"},
    }


def test_anki_not_logged_in_to_ankiweb(client, monkeypatch):
    fake = FakeAnki()
    fake.sync_error = "sync: auth not configured"
    original = fake.handle

    def handle(request):
        if json.loads(request.content)["action"] == "sync":
            return httpx.Response(200, json={"result": None, "error": fake.sync_error})
        return original(request)

    monkeypatch.setattr(ankiconnect, "_transport", httpx.MockTransport(handle))
    res = client.post("/api/anki/send", json=SEND).json()
    assert res["added"] == 2
    assert res["sync_error"]["code"] == "anki.sync_not_logged_in"


def test_no_sync_when_the_profile_is_not_logged_in(anki, client, monkeypatch):
    async def not_logged_in():
        return False

    monkeypatch.setattr(ankiconnect, "sync_configured", not_logged_in)  # what the add-on says
    res = client.post("/api/anki/send", json=SEND).json()
    assert (res["synced"], res["sync_error"], res["sync_skipped"]) == (False, None, True)
    assert "sync" not in anki.calls


def test_addon_mode(client, monkeypatch):
    """In the Anki add-on, the bridge address and key win over saved AnkiConnect settings."""
    from fastapi.testclient import TestClient

    client.post("/api/admin/password", json={"new": "secret"})
    client.put(
        "/api/admin/settings",
        headers=ADMIN,
        json={"ankiconnect_url": "http://autre-pc:8765", "ankiconnect_key": "ancienne"},
    )
    assert settings.current().ankiconnect_url == "http://autre-pc:8765"

    monkeypatch.setenv("NOTOSAURUS_EMBEDDED", "1")
    monkeypatch.setenv("NOTOSAURUS_ANKICONNECT_URL", "http://127.0.0.1:40123")
    monkeypatch.setenv("NOTOSAURUS_ANKICONNECT_KEY", "bridge-key")
    s = settings.current()
    assert (s.ankiconnect_url, s.ankiconnect_key) == ("http://127.0.0.1:40123", "bridge-key")
    with TestClient(app, client=("127.0.0.1", 50000)) as local:
        assert local.get("/api/admin/settings").json()["embedded"] is True


def test_cloze_sent_to_anki(anki, client):
    res = client.post("/api/anki/send", json=CLOZE).json()
    assert (res["added"], res["updated"]) == (3, 0)
    cloze_model = anki.models["Notosaurus texte à trous"]
    assert cloze_model["isCloze"] is True and cloze_model["inOrderFields"] == ["Text", "Extra", "Info", "Id"]
    assert anki.models[next(m for m in anki.models if m.startswith("Notosaurus recto"))]["isCloze"] is False
    assert anki.notes[2]["fields"]["Extra"] == "place de la Révolution"

    # The text corrected (a gap moved): the same note, found by the card's id
    corrected = {**CLOZE, "cards": [{**CLOZE["cards"][0], "front": "La Révolution commence en {{c1::1789}}."}]}
    res = client.post("/api/anki/send", json=corrected).json()
    assert (res["added"], res["updated"]) == (0, 1)
    assert anki.notes[1]["fields"]["Text"] == "La Révolution commence en {{c1::1789}}."


def test_delete_a_lesson_and_its_anki_notes(anki, client):
    lesson = extract_lesson(client)
    body = {"deck": "Espagnol::Leçon 5", "cards": lesson["cards"], "lesson_id": lesson["id"]}
    client.post("/api/anki/send", json=body)
    sent = len(anki.notes)
    # A note of the user's own in the same deck, and one sent before notes had the lesson's tag
    anki.notes[100] = {"deckName": "Espagnol::Leçon 5", "modelName": "Basic", "fields": {}, "tags": []}
    older = next(i for i, n in anki.notes.items() if n["fields"].get("Front") == "la mère")
    anki.notes[older]["tags"] = []
    url = f"/api/lessons/{lesson['id']}"
    client.put(url, json=body)  # the lesson as sent

    assert client.get(f"{url}/anki-notes").json() == {"available": True, "count": sent}
    res = client.delete(f"{url}?anki=true").json()
    assert res["anki_deleted"] == sent and res["synced"] is True
    assert list(anki.notes) == [100]  # the user's own note stays...
    assert "Espagnol::Leçon 5" in anki.decks  # ...and so does its deck
    assert "Espagnol::Leçon 5::Vocabulaire" not in anki.decks  # an emptied subdeck goes
    assert client.get(url).status_code == 404


def test_delete_a_lesson_keeping_its_anki_notes(anki, client):
    lesson = extract_lesson(client)
    client.post("/api/anki/send", json={"deck": lesson["deck"], "cards": lesson["cards"], "lesson_id": lesson["id"]})
    notes = dict(anki.notes)
    res = client.delete(f"/api/lessons/{lesson['id']}").json()
    assert res["anki_deleted"] == 0 and anki.notes == notes and "deleteNotes" not in anki.calls


def test_deleting_a_lesson_keeps_another_lessons_notes(anki, client):
    first, second = extract_lesson(client), extract_lesson(client)  # the same lesson made twice, same deck
    for lesson in (first, second):
        body = {"deck": "Espagnol::Leçon 7", "cards": lesson["cards"], "lesson_id": lesson["id"]}
        client.post("/api/anki/send", json=body)
        client.put(f"/api/lessons/{lesson['id']}", json=body)
    # Same fronts: the second send updated the first's notes, which carry both tags now
    assert len(anki.notes) == 6
    url = f"/api/lessons/{first['id']}"
    assert client.get(f"{url}/anki-notes").json()["count"] == 0  # all shared with the other lesson
    client.delete(f"{url}?anki=true")
    assert len(anki.notes) == 6
    assert client.get(f"/api/lessons/{second['id']}/anki-notes").json()["count"] == 6  # alone now


def test_options_changed_after_a_send_keep_the_notes(anki, client):
    lesson = extract_lesson(client)
    body = {"deck": "Espagnol", "cards": lesson["cards"], "voice": "es_ES", "lesson_id": lesson["id"]}
    assert client.post("/api/anki/send", json=body).json()["added"] == 6
    ids = sorted(anki.notes)

    # Typed answer and reverse card switched on: the same notes, moved to the new note type
    res = client.post("/api/anki/send", json={**body, "typing": True, "reverse": True}).json()
    assert (res["added"], res["updated"], res["converted"]) == (0, 6, 6)
    assert sorted(anki.notes) == ids
    converted = {n["modelName"] for n in anki.notes.values()}
    assert converted == {"Notosaurus recto/verso + inverse à taper (TTS Anki es_ES)"}
    assert all(f"notosaurus::{lesson['id']}" in n["tags"] for n in anki.notes.values())

    # Sent again unchanged: plain updates
    res = client.post("/api/anki/send", json={**body, "typing": True, "reverse": True}).json()
    assert (res["added"], res["updated"], res["converted"]) == (0, 6, 0)


def test_options_changed_with_an_old_ankiconnect(client, monkeypatch):
    fake = FakeAnki(note_model=False)
    monkeypatch.setattr(ankiconnect, "_transport", httpx.MockTransport(fake.handle))
    lesson = extract_lesson(client)
    body = {"deck": "Espagnol", "cards": lesson["cards"], "voice": "es_ES", "lesson_id": lesson["id"]}
    client.post("/api/anki/send", json=body)
    res = client.post("/api/anki/send", json={**body, "typing": True}).json()
    assert (res["added"], res["converted"], res["conversion_unsupported"]) == (6, 0, True)  # as before, and said
