"""Standing instructions for the AI: for everyone in the settings; per child in its card
(app/children.py), the instructions per Anki profile of before made cards linked to it."""

import json
import types

from conftest import ADMIN

from app import ankiconnect, settings, storage
from notosaurus_core.providers import openai_like


def test_saved_in_the_settings(admin):
    saved = admin.put("/api/admin/settings", headers=ADMIN, json={"instructions": " Spanish from Spain "}).json()
    assert saved["instructions"] == "Spanish from Spain"
    # Other settings saved later leave them alone
    assert admin.put("/api/admin/settings", headers=ADMIN, json={"tts_rate": "-5%"}).json()["instructions"]
    # Per Anki profile: no longer set here (the children's cards)
    admin.put("/api/admin/settings", headers=ADMIN, json={"profile_instructions": {"Léa": "year 8"}})
    assert settings.current().profile_instructions == {}


def test_sent_with_the_request_for_the_profile(admin, monkeypatch):
    """The instructions per Anki profile of before: the card made of them, linked to the
    profile, is the child of the lessons made in it (none chosen), its name never told."""
    admin.put("/api/admin/settings", headers=ADMIN, json={"instructions": "Spanish from Spain"})
    stored = storage.read_json(settings._path())
    stored["profile_instructions"] = {"Léa": "in year 8", "Paul": "year 6"}
    storage.write_json(settings._path(), stored)
    monkeypatch.setenv("NOTOSAURUS_LLM", "openai")
    monkeypatch.setenv("NOTOSAURUS_MODEL", "gpt-6.1-sol")
    sent = []

    class Completions:
        async def create(self, **kwargs):
            sent.append(kwargs["messages"][-1]["content"][-1]["text"])
            content = json.dumps({"deck": "D", "cards": [{"front": "a", "back": "b"}]})
            message = types.SimpleNamespace(content=content)
            return types.SimpleNamespace(usage=None, model="m", choices=[types.SimpleNamespace(message=message)])

    client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=Completions()))
    monkeypatch.setattr(openai_like, "_openai_client", lambda s: client)

    async def lea():
        return "Léa"

    monkeypatch.setattr(ankiconnect, "active_profile", lea)
    lesson = admin.post("/api/extract", data={"prompt": "words: le chat"}).json()
    assert "Spanish from Spain" in sent[0] and "in year 8" in sent[0] and "year 6" not in sent[0]
    assert "Léa" not in sent[0] and lesson["child"] == "lea"
    assert sent[0].index("in year 8") < sent[0].index("Instructions: words: le chat")  # before the request

    # A correction: the instructions of the lesson's owner
    body = {"deck": "D", "cards": lesson["cards"], "instruction": "add one"}
    admin.post(f"/api/lessons/{lesson['id']}/revise", json=body)
    assert "in year 8" in sent[1]


def test_nothing_added_without_instructions():
    assert settings.standing_instructions(settings.Settings()) == ""
    assert settings.standing_instructions(settings.Settings(profile_instructions={"Paul": "year 6"})) == ""
