"""Fixtures shared by the tests: a paired phone on fresh data, the demo AI (fake
provider), TTS and AnkiConnect faked, and an in-memory AnkiConnect (FakeAnki)."""

import base64
import json
import re

import httpx
import pytest
from fastapi.testclient import TestClient

from app import ankiconnect, prices, settings, tts
from app.main import DEVICE_COOKIE, app

synthesized = []


async def fake_synthesize(text, voice, path):
    if "ÉCHEC" in text:
        raise RuntimeError("network down")
    synthesized.append(text)
    path.write_bytes(b"ID3fake mp3 " + text.encode())


# Public model prices (OpenRouter's list), per token: no network in the tests
PRICES = {
    "openai/gpt-6.1-sol": ("0.000002", "0.00001"),
    "google/gemini-3.8-flash": ("0.00000075", "0.00000375"),
    "anthropic/claude-sonnet-4.6": ("0.000003", "0.000015"),
}


def model_list(request):
    data = [{"id": i, "pricing": {"prompt": p, "completion": c}} for i, (p, c) in PRICES.items()]
    return httpx.Response(200, json={"data": data})


def anki_unreachable(request):
    raise httpx.ConnectError("refused")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTOSAURUS_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("NOTOSAURUS_LLM", "fake")
    monkeypatch.setattr(tts, "_synthesize", fake_synthesize)
    # Never reach a real Anki from the tests: AnkiConnect is "unreachable" unless a test fakes it.
    monkeypatch.setattr(ankiconnect, "_transport", httpx.MockTransport(anki_unreachable))
    monkeypatch.setattr(prices, "_transport", httpx.MockTransport(model_list))
    synthesized.clear()
    with TestClient(app) as c:
        c.cookies.set(DEVICE_COOKIE, settings.device_token())  # a paired phone
        yield c


ADMIN = {"X-Admin-Password": "secret"}


@pytest.fixture
def admin(client):
    assert client.get("/api/admin").json()["password_set"] is False
    assert client.post("/api/admin/password", json={"new": "secret"}).status_code == 204
    return client


def extract_lesson(client, n_photos=2, prompt="FR → ES") -> dict:
    """A lesson generated from n photos with the demo AI."""
    files = [("images", (f"p{i}.jpg", f"photo {i}".encode(), "image/jpeg")) for i in range(1, n_photos + 1)]
    return client.post("/api/extract", files=files, data={"prompt": prompt}).json()


SEND = {
    "deck": "Espagnol::Leçon 5",
    "cards": [
        {"front": "la mère", "back": "la madre", "subdeck": "Vocabulaire", "tags": ["famille proche"]},
        {"front": "<b>", "back": "el padre"},
    ],
    "voice": "es-ES-ElviraNeural",
}


CLOZE = {
    "deck": "Histoire",
    "voice": "es-ES-ElviraNeural",
    "cards": [
        {
            "id": "rev1",
            "front": "La Révolution commence en {{c1::1789}} avec la prise de {{c2::la Bastille}}.",
            "back": "",
        },
        {"id": "rev2", "front": "{{c1::Louis XVI}} est guillotiné en 1793.", "back": "place de la Révolution"},
        {"front": "la madre", "back": "la madre"},
    ],
}


# Bringing a note type up to date: AnkiConnect's actions, missing from an old one
MODEL_ACTIONS = {"modelStyling", "modelFieldNames", "modelTemplates", "modelFieldAdd", "modelTemplateAdd",
                 "updateModelTemplates", "updateModelStyling"}  # fmt: skip


class FakeAnki:
    """In-memory AnkiConnect, enough for Notosaurus's calls."""

    def __init__(self, fail_sync=False, profile="Léa", note_model=True):
        self.models, self.decks, self.media, self.notes = {}, {}, {}, {}
        self.profile = profile
        self.calls, self.keys, self.fail_sync = [], [], fail_sync
        self.note_model = note_model  # AnkiConnect recent enough for updateNoteModel

    def handle(self, request):
        body = json.loads(request.content)
        action, p = body["action"], body["params"]
        self.calls.append(action)
        self.keys.append(body.get("key"))
        result, error = None, None
        if action == "version":
            result = 6
        elif action == "getActiveProfile":
            result = self.profile
        elif action == "getProfiles":
            result = ["Léa", "Paul"]
        elif action == "modelNames":
            result = list(self.models)
        elif action == "createModel":
            self.models[p["modelName"]] = p
        elif action in MODEL_ACTIONS and not self.note_model:
            error = "unsupported action"  # an old AnkiConnect
        elif action == "modelStyling":
            result = {"css": self.models[p["modelName"]]["css"]}
        elif action == "modelFieldNames":
            result = list(self.models[p["modelName"]]["inOrderFields"])
        elif action == "modelTemplates":
            result = {
                t["Name"]: {"Front": t["Front"], "Back": t["Back"]}
                for t in self.models[p["modelName"]]["cardTemplates"]
            }
        elif action == "modelFieldAdd":
            self.models[p["modelName"]]["inOrderFields"].append(p["fieldName"])
        elif action == "modelTemplateAdd":
            self.models[p["modelName"]]["cardTemplates"].append(p["template"])
        elif action == "updateModelTemplates":
            for t in self.models[p["model"]["name"]]["cardTemplates"]:
                t.update(p["model"]["templates"].get(t["Name"], {}))
        elif action == "updateModelStyling":
            self.models[p["model"]["name"]]["css"] = p["model"]["css"]
        elif action == "deckNames":
            result = ["Default", *self.decks]
        elif action == "createDeck":
            result = self.decks.setdefault(p["deck"], 1000 + len(self.decks))
        elif action == "storeMediaFile":
            self.media[p["filename"]] = base64.b64decode(p["data"])
        elif action == "findNotes":
            q = p["query"]
            if tag := re.fullmatch(r'"tag:(.+)"', q):
                result = [i for i, n in self.notes.items() if tag[1] in n["tags"]]
            elif notosaurus := re.fullmatch(r'"deck:(.+)" -"deck:.+::\*" "note:Notosaurus\*"', q):
                result = [
                    i
                    for i, n in self.notes.items()
                    if n["deckName"] == notosaurus[1] and n["modelName"].startswith("Notosaurus")
                ]
            elif deck := re.fullmatch(r'"note:([^"]+)" "deck:([^"]+)" -"deck:[^"]+::\*" -"tag:notosaurus::\*"', q):
                result = [
                    i
                    for i, n in self.notes.items()
                    if (n["modelName"], n["deckName"]) == deck.groups()
                    and not any(t.startswith("notosaurus::") for t in n["tags"])
                ]
            elif re.fullmatch(r'"note:[^"]+" did:\d+', q):
                result = [
                    i for i, n in self.notes.items() if q == f'"note:{n["modelName"]}" did:{self.decks[n["deckName"]]}'
                ]
            else:
                raise AssertionError(f"query not understood by the fake: {q}")
        elif action == "findCards":
            name = re.fullmatch(r'"deck:(.+)"', p["query"])[1]
            result = [
                i for i, n in self.notes.items() if n["deckName"] == name or n["deckName"].startswith(name + "::")
            ]
        elif action == "addTags":
            for i in p["notes"]:
                self.notes[i]["tags"] = [*self.notes[i]["tags"], p["tags"]]
        elif action == "deleteNotes":
            for i in p["notes"]:
                del self.notes[i]
        elif action == "deleteDecks":
            for name in p["decks"]:
                self.decks.pop(name, None)
        elif action == "notesInfo":
            result = [
                {
                    "noteId": i,
                    "modelName": self.notes[i]["modelName"],
                    "fields": {k: {"value": v} for k, v in self.notes[i]["fields"].items()},
                    "tags": self.notes[i]["tags"],
                }
                for i in p["notes"]
            ]
        elif action == "updateNoteModel":
            if not self.note_model:
                error = "unsupported action"
            else:
                note = self.notes[p["note"]["id"]]
                note.update(modelName=p["note"]["modelName"], fields=p["note"]["fields"], tags=p["note"]["tags"])
        elif action == "updateNoteFields":
            self.notes[p["note"]["id"]]["fields"] = p["note"]["fields"]
        elif action == "addNote":
            result = len(self.notes) + 1
            self.notes[result] = p["note"]
        elif action == "sync":
            error = "AnkiWeb: login required" if self.fail_sync else None
        return httpx.Response(200, json={"result": result, "error": error})


@pytest.fixture
def anki(client, monkeypatch):
    fake = FakeAnki()
    monkeypatch.setattr(ankiconnect, "_transport", httpx.MockTransport(fake.handle))
    return fake
