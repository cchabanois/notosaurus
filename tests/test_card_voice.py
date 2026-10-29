"""A card's own voice (Card.voice), else the lesson's (tts.card_voice): a sound made on the
phone, with the relay's voices, kept in a lesson moved to this computer; the voice that
this computer can't read with gives way to the lesson's once the card changes."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from notosaurus_core import files, llm, tts
from notosaurus_core.models import Card, Revision

LESSON = "es-ES-ElviraNeural"
PHONE = "es-ES-Chirp3-HD-Aoede"  # the relay's voice: its sounds made on the phone


def run(coroutine):
    """Run on a thread of its own: after the page tests, Playwright's loop runs on this one."""
    with ThreadPoolExecutor(1) as thread:
        return thread.submit(asyncio.run, coroutine).result()


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


def phone_sound(audio, text, voice=PHONE, rate="-10%"):
    """A sound as the phone left it in the lesson's folder (the same name as here)."""
    audio.mkdir(parents=True, exist_ok=True)
    path = audio / tts.filename(text, voice, rate)
    path.write_bytes(b"<from the phone>")
    return path


def test_the_voice_of_a_cards_sound(tmp_path):
    audio = tmp_path / "audio"
    plain = Card(front="la mère", back="la madre")
    assert tts.card_voice(plain, LESSON, "la madre", audio) == LESSON  # most cards: the lesson's
    own = Card(front="la mère", back="la madre", voice="es-ES-AlvaroNeural")
    assert tts.card_voice(own, LESSON, "la madre", audio) == "es-ES-AlvaroNeural"  # one this computer has
    phone = Card(front="la mère", back="la madre", voice=PHONE)
    assert tts.card_voice(phone, LESSON, "la madre", audio) == LESSON  # neither read here nor there
    phone_sound(audio, "la madre")
    assert tts.card_voice(phone, LESSON, "la madre", audio) == PHONE  # its sound there: kept


def test_a_lesson_from_the_phone_keeps_its_sounds(read, tmp_path):
    audio = tmp_path / "lesson" / "audio"
    kept = phone_sound(audio, "la madre")
    cards = [
        Card(front="la mère", back="la madre", voice=PHONE),  # as it came
        Card(front="le père", back="el padre"),  # added here
        Card(front="le fils", back="el hijo", voice=PHONE),  # corrected here: its phone's sound is gone
    ]
    voices = tts.spoken_voices(cards, LESSON, audio, "-10%")
    assert voices == {"la madre": PHONE, "el padre": LESSON, "el hijo": LESSON}
    audio_of, failures = run(tts.tts_voices(voices, audio, "-10%"))
    assert audio_of["la madre"] == kept and failures == 0  # no new one: the phone's
    assert read == [("el padre", LESSON), ("el hijo", LESSON)]


def test_the_ai_never_writes_it():
    """Notosaurus's, as a card's id or picture: not in what the AI fills."""
    (card,) = llm.ai_schema(Revision).model_fields["cards"].annotation.__args__
    assert "voice" not in card.model_fields and "front" in card.model_fields


def test_a_cards_phone_voice_previewed(client):
    """🔊 on a card whose voice is the phone's (the page says it): its sound if it came with
    the lesson, else read in the lesson's voice."""
    from conftest import extract_lesson, synthesized

    from app import lessons

    lesson = extract_lesson(client)
    client.put(
        f"/api/lessons/{lesson['id']}", json={"deck": "D", "cards": lesson["cards"], "voice": LESSON, "rate": "-10%"}
    )
    params = {"text": "la madre", "voice": PHONE, "lesson": lesson["id"], "rate": "-10%"}
    phone_sound(lessons.audio_dir(lesson["id"]), "la madre")
    assert client.get("/api/tts", params=params).content == b"<from the phone>"
    params["text"] = "el padre"  # no sound of the phone's: the lesson's voice
    assert client.get("/api/tts", params=params).status_code == 200
    assert synthesized == ["el padre"]
