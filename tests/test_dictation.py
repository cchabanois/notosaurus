"""A dictation (the app's 🎤) as the text its speaker meant to type: llm.transcribe."""

import asyncio

import pytest
from helpers import HearingGemini

from notosaurus_core import llm
from notosaurus_core.config import AIConfig
from notosaurus_core.providers import gemini

RECORDING = llm.Image(b"\xff\xf1 adts frames", "audio/aac")


def test_gemini_hears_the_recording(monkeypatch):
    fake = HearingGemini('{"text": " Fais dix cartes sur el abuelo et la abuela. "}')
    monkeypatch.setattr(gemini, "_gemini_client", lambda s: fake)
    s = AIConfig(llm="gemini", model="gemini-3.5-flash", gemini_api_key="k")
    text = asyncio.run(llm.transcribe(s, RECORDING, "prompt", "French"))
    assert text == "Fais dix cartes sur el abuelo et la abuela."
    ((contents, config),) = fake.calls
    audio, request = contents
    assert audio.inline_data.mime_type == "audio/aac" and audio.inline_data.data == RECORDING.data
    assert "instructions for making flashcards" in request and "The app is in French" in request
    assert "no rephrasing" in config.system_instruction  # their words, cleaned up only


def test_a_correction_is_said_so(monkeypatch):
    fake = HearingGemini('{"text": "Enlève la carte sur el tío."}')
    monkeypatch.setattr(gemini, "_gemini_client", lambda s: fake)
    s = AIConfig(llm="gemini", model="gemini-3.5-flash", gemini_api_key="k")
    asyncio.run(llm.transcribe(s, RECORDING, "correction"))
    assert "a correction of a lesson's flashcards" in fake.calls[0][0][1]


def test_only_gemini_hears():
    with pytest.raises(llm.ExtractionError) as e:
        asyncio.run(llm.transcribe(AIConfig(llm="anthropic", anthropic_api_key="k"), RECORDING, "prompt"))
    assert e.value.code == "llm.no_audio"


def test_the_demo_ai():
    with llm.recording("transcribe") as calls:
        text = asyncio.run(llm.transcribe(AIConfig(llm="fake"), RECORDING, "prompt"))
    assert "abuelo" in text and [c.model for c in calls] == ["fake"]
