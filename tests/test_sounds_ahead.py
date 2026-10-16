"""The backs' sounds made ahead, in the background, after a lesson is saved; and "Add to
Anki" told as it goes (application/x-ndjson)."""

import json
import time

from conftest import SEND, extract_lesson, synthesized

from app import lessons, settings, sounds
from notosaurus_core import tts

VOICE = "es-ES-ElviraNeural"


def wait_for(condition, timeout=5.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.02)
    return False


def save(client, id: str, backs: list[str], voice: str = VOICE) -> None:
    cards = [{"front": f"carte {i}", "back": back} for i, back in enumerate(backs)]
    res = client.put(f"/api/lessons/{id}", json={"deck": "Espagnol", "cards": cards, "voice": voice})
    assert res.status_code == 200


def test_sounds_made_after_a_save_then_found_by_the_send(client, anki, monkeypatch):
    monkeypatch.setattr(sounds, "DELAY", 0.05)
    lesson = extract_lesson(client)
    save(client, lesson["id"], ["la madre", "el padre"])
    assert wait_for(lambda: sorted(synthesized) == ["el padre", "la madre"])
    audio = lessons.audio_dir(lesson["id"])
    rate = settings.current().tts_rate  # the lesson's own: none, the settings'
    assert wait_for(lambda: (audio / tts.filename("el padre", VOICE, rate)).is_file())

    # Sent: its sounds made already, nothing synthesized again
    synthesized.clear()
    res = client.post("/api/anki/send", json={**SEND, "lesson_id": lesson["id"]}).json()
    assert res["audio_failures"] == 0
    assert synthesized == []
    assert set(anki.media) == {tts.filename("la madre", VOICE, rate), tts.filename("el padre", VOICE, rate)}


def test_a_newer_save_replaces_the_job(client, monkeypatch):
    """Saved as the user types: only the backs as last saved are read."""
    monkeypatch.setattr(sounds, "DELAY", 0.3)
    lesson = extract_lesson(client)
    save(client, lesson["id"], ["la mad"])
    save(client, lesson["id"], ["la madre"])
    assert wait_for(lambda: synthesized == ["la madre"])
    time.sleep(0.4)
    assert synthesized == ["la madre"]  # "la mad" never read
    assert not sounds._jobs


def test_nothing_for_a_voice_anki_reads(client, monkeypatch):
    monkeypatch.setattr(sounds, "DELAY", 0.01)
    lesson = extract_lesson(client)
    save(client, lesson["id"], ["la madre"], voice="es_ES")  # Anki's own {{tts}}
    save(client, extract_lesson(client)["id"], ["la madre"], voice="")  # no sound
    assert not sounds._jobs
    time.sleep(0.2)
    assert synthesized == []
    audio = lessons.audio_dir(lesson["id"])
    assert audio is not None and not audio.exists()


def test_the_send_told_as_it_goes(client, anki):
    lesson = extract_lesson(client)
    asked = {**SEND, "lesson_id": lesson["id"], "cards": [*SEND["cards"], {"front": "maman", "back": "la madre"}]}
    res = client.post("/api/anki/send", json=asked, headers={"Accept": "application/x-ndjson"})
    assert res.status_code == 200
    assert res.headers["Content-Type"].startswith("application/x-ndjson")
    lines = [json.loads(line) for line in res.text.splitlines()]
    sounds_ = [line for line in lines if line.get("step") == "sounds"]
    assert sounds_[0] == {"step": "sounds", "done": 0, "total": 2}  # the same back once
    assert sounds_[-1] == {"step": "sounds", "done": 2, "total": 2}
    assert lines[-2] == {"step": "cards"}
    result = lines[-1]["result"]
    assert (result["added"], result["audio_failures"], result["leftovers"]) == (3, 0, [])
    assert client.get(f"/api/lessons/{lesson['id']}").json()["exported_at"] is not None

    # Sent again without the stream: the same answer as ever
    again = client.post("/api/anki/send", json=asked).json()
    assert set(again) == set(result)
    assert (again["added"], again["updated"]) == (0, 3)


def test_the_send_told_as_it_goes_without_a_voice_or_with_an_error(client):
    """No sound to make: straight to the cards; Anki closed: the error as the page knows it."""
    res = client.post("/api/anki/send", json={**SEND, "voice": ""}, headers={"Accept": "application/x-ndjson"})
    lines = [json.loads(line) for line in res.text.splitlines()]
    assert lines == [{"step": "cards"}, {"error": {"code": "anki.unreachable", "params": {}}}]
