"""What each mp3 of a lesson says, and with which voice (tts.INDEX): a sound made elsewhere
(the phone's voices, which edge-tts doesn't have) is kept while its card says the same;
this computer's own still follow the lesson's voice and rate."""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from notosaurus_core import files, tts

PHONE = "es-ES-Chirp3-HD-Aoede"  # the relay's voice: made on the phone


@pytest.fixture
def read(monkeypatch, tmp_path):
    """The texts synthesized here (the cache apart from the lesson's folder)."""
    monkeypatch.setattr(files, "_cache_root", lambda: tmp_path / "cache")
    said = []

    async def synthesize(text, voice, path, rate):
        said.append((text, voice))
        path.write_bytes(f"<{voice} {text}>".encode())

    monkeypatch.setattr(tts, "_synthesize", synthesize)
    return said


def run(coroutine):
    """Run on a thread of its own: after the page tests, Playwright's loop runs on this one."""
    with ThreadPoolExecutor(1) as thread:
        return thread.submit(asyncio.run, coroutine).result()


def index(directory):
    return json.loads((directory / tts.INDEX).read_text(encoding="utf-8"))


def imported(directory, name: str, text: str, voice: str = PHONE, rate: str = "-10%"):
    """A sound as the phone left it in the lesson's folder."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_bytes(b"<from the phone>")
    files.write_json(
        directory / tts.INDEX,
        {**(files.read_json(directory / tts.INDEX, {})), name: {"text": text, "voice": voice, "rate": rate}},
    )
    return directory / name


def test_what_each_sound_says_is_kept_with_it(read, tmp_path):
    audio = tmp_path / "lesson" / "audio"
    path = run(tts.tts("la madre", "es-ES-ElviraNeural", audio))
    assert index(audio) == {path.name: {"text": "la madre", "voice": "es-ES-ElviraNeural", "rate": "-10%"}}
    run(tts.tts("la madre", "es-ES-ElviraNeural"))  # a preview, not the lesson's: no index
    assert not (files.cache_dir("tts") / tts.INDEX).exists()


def test_a_sound_made_on_the_phone_kept_while_its_card_says_the_same(read, tmp_path):
    audio = tmp_path / "lesson" / "audio"
    phone = imported(audio, "a1b2c3d4e5f60718.mp3", "la madre")
    assert run(tts.tts("la madre", "es-ES-ElviraNeural", audio)) == phone  # no credit, no voice
    assert read == []
    corrected = run(tts.tts("la mamá", "es-ES-ElviraNeural", audio))  # its card changed: made here
    assert corrected != phone and read == [("la mamá", "es-ES-ElviraNeural")]


def test_this_computers_own_follow_the_lessons_voice(read, tmp_path):
    """Its own voice changed: the sound made again with the new one (not kept as the phone's)."""
    audio = tmp_path / "lesson" / "audio"
    run(tts.tts("la madre", "es-ES-ElviraNeural", audio))
    run(tts.tts("la madre", "es-ES-AlvaroNeural", audio))
    assert read == [("la madre", "es-ES-ElviraNeural"), ("la madre", "es-ES-AlvaroNeural")]


def test_pruned_sounds_leave_the_index(read, tmp_path):
    audio = tmp_path / "lesson" / "audio"
    kept = run(tts.tts("la madre", "es-ES-ElviraNeural", audio))
    imported(audio, "a1b2c3d4e5f60718.mp3", "el padre")
    tts.prune(audio, {kept})
    assert [p.name for p in audio.glob("*.mp3")] == [kept.name]
    assert list(index(audio)) == [kept.name]
