"""The backs' sounds made ahead, in the background, after a lesson is saved; and "Add to
Anki" told as it goes (application/x-ndjson)."""

import asyncio
import json
import threading
import time
import types

import pytest
from conftest import SEND, extract_lesson, synthesized
from helpers import sounds_ahead_gone

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


@pytest.fixture
def quiet(monkeypatch) -> threading.Event:
    """The few seconds of quiet a job waits for, over when the test says (set), not after a
    time the test hopes is long enough: the jobs' own `asyncio.sleep`, gated."""
    over = threading.Event()

    async def sleep(delay, result=None):
        while not over.is_set():
            await asyncio.sleep(0.01)
        return result

    gated = types.SimpleNamespace(**{**vars(asyncio), "sleep": sleep})
    monkeypatch.setattr(sounds, "asyncio", gated)
    return over


def test_a_job_started_after_the_cancelling_is_cancelled_too():
    """A job started on a server's loop (its thread) after the page test cancelled its jobs (a
    last save as the page closed): cancelled as well before the next test, within a moment, not
    left to its 5 s of quiet (the end of a test failed so, on main, 2026-11-26)."""
    loop = asyncio.new_event_loop()
    server = threading.Thread(target=loop.run_forever, daemon=True)
    server.start()

    async def late_save() -> None:
        sounds.soon("2026-11-26-late", VOICE)

    try:
        asyncio.run_coroutine_threadsafe(late_save(), loop).result(2)
        assert "2026-11-26-late" in sounds._jobs
        started = time.monotonic()
        assert sounds_ahead_gone(timeout=3)
        assert time.monotonic() - started < 1  # cancelled, not waited out
    finally:
        loop.call_soon_threadsafe(loop.stop)
        server.join(2)
        loop.close()


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


def test_a_newer_save_replaces_the_job(client, quiet):
    """Saved as the user types: only the backs as last saved are read."""
    id = extract_lesson(client)["id"]
    save(client, id, ["la mad"])
    first = sounds._jobs[id]
    save(client, id, ["la madre"])
    assert wait_for(first.done) and first.cancelled()  # replaced while still waiting
    assert sounds._jobs[id] is not first
    quiet.set()
    assert wait_for(lambda: id not in sounds._jobs)  # the newer job done
    assert synthesized == ["la madre"]  # "la mad" never read


def test_nothing_for_a_voice_anki_reads(client, quiet):
    quiet.set()  # a job, if one were started, would not wait
    id = extract_lesson(client)["id"]
    save(client, id, ["la madre"], voice="es_ES")  # Anki's own {{tts}}
    other = extract_lesson(client)["id"]
    save(client, other, ["la madre"], voice="")  # no sound
    assert id not in sounds._jobs and other not in sounds._jobs  # no job: nothing made later either
    assert synthesized == []
    audio = lessons.audio_dir(id)
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
