"""The prompts: Notosaurus's (in the page's language, read-only) and the user's."""

import json
import re
from pathlib import Path

from app import prompts, settings


def test_notosaurus_prompts(client):
    """Notosaurus's prompts: in the page's language, read-only, before the user's."""
    fr = client.get("/api/prompts", headers={"X-Notosaurus-Lang": "fr-FR"}).json()
    assert [p["id"] for p in fr] == [f"notosaurus:{k}" for k in prompts.BUILTIN]
    names = {p["id"]: p["name"] for p in fr}
    assert all(p["builtin"] for p in fr) and names["notosaurus:diagram"] == "Schéma ou carte à compléter"
    # First, so picked when nothing was picked before: the AI chooses from the lesson
    assert fr[0]["name"] == "Automatique (d'après la leçon)" and fr[0]["voice"] == "auto"
    en = client.get("/api/prompts", headers={"X-Notosaurus-Lang": "en"}).json()
    assert en[1]["name"] == "Language: vocabulary"  # the same prompts, in English
    de = client.get("/api/prompts", headers={"X-Notosaurus-Lang": "de-AT"}).json()
    assert de[1]["name"] == "Sprache: Vokabeln"
    ja = client.get("/api/prompts", headers={"X-Notosaurus-Lang": "ja"}).json()
    assert ja[1]["name"] == "Language: vocabulary"  # no Japanese file: English

    for method in ("PUT", "DELETE"):
        r = client.request(method, "/api/prompts/notosaurus:questions", json={"name": "x", "text": "y"})
        assert (r.status_code, r.json()["detail"]["code"]) == (403, "prompt.builtin")


def test_duplicate_a_prompt_to_adapt_it(client):
    copy = client.post("/api/prompts/notosaurus:vocabulary/duplicate", headers={"X-Notosaurus-Lang": "fr"}).json()
    assert (copy["name"], copy["builtin"]) == ("Langue : vocabulaire (copie)", False)
    changed = client.put(f"/api/prompts/{copy['id']}", json={**copy, "text": "FR → ES", "voice": "es-ES-ElviraNeural"})
    assert changed.json()["voice"] == "es-ES-ElviraNeural"
    again = client.post(f"/api/prompts/{copy['id']}/duplicate", headers={"X-Notosaurus-Lang": "fr"}).json()
    assert (again["name"], again["text"]) == ("Langue : vocabulaire (copie) (copie)", "FR → ES")
    assert client.post("/api/prompts/notosaurus:nope/duplicate").status_code == 404
    names = [p["name"] for p in client.get("/api/prompts", headers={"X-Notosaurus-Lang": "fr"}).json()]
    assert names[-2:] == ["Langue : vocabulaire (copie)", "Langue : vocabulaire (copie) (copie)"]


def test_notosaurus_prompt_used(client):
    data = {"prompt": "words: le chat", "prompt_id": "notosaurus:dictation"}
    client.post("/api/extract", data=data)
    dictation = next(p for p in client.get("/api/prompts").json() if p["id"] == "notosaurus:dictation")
    assert dictation["used_at"] is not None


def test_old_prompts_file_converted(client, tmp_path):
    """Before, the file was a list seeded with the default prompts."""
    old = [
        {"id": 1, "name": "Vocabulaire FR → ES", "text": "Crée des cartes…", "voice": "es-ES-ElviraNeural"},
        {"id": 3, "name": "Questions / réponses", "text": next(iter(sorted(prompts.REPLACED)))},
        {"id": 6, "name": "Formules de maths", "text": "Les formules de 5e"},
    ]
    path = tmp_path / "data" / "prompts.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(old), encoding="utf-8")
    user = [p for p in client.get("/api/prompts").json() if not p["builtin"]]
    assert [(p["id"], p["name"]) for p in user] == [(1, "Vocabulaire FR → ES"), (6, "Formules de maths")]
    client.post("/api/prompts", json={"name": "Anglais", "text": "FR → EN"})  # written in the new format
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert [p["id"] for p in saved["user"]] == [1, 6, 7]


def test_prompt_crud(client):
    created = client.post("/api/prompts", json={"name": "Anglais", "text": "FR → EN"}).json()
    assert created["id"]

    updated = client.put(
        f"/api/prompts/{created['id']}",
        json={"name": "Anglais", "text": "FR → EN, vocabulaire", "voice": "en-GB-SoniaNeural"},
    ).json()
    assert updated["voice"] == "en-GB-SoniaNeural"

    assert client.delete(f"/api/prompts/{created['id']}").status_code == 204
    assert client.delete(f"/api/prompts/{created['id']}").status_code == 404
    assert client.put("/api/prompts/999", json={"name": "x", "text": "y"}).status_code == 404


def test_prompt_used(client):
    prompt = client.get("/api/prompts").json()[1]
    assert prompt["used_at"] is None

    files = [("images", ("p.jpg", b"x", "image/jpeg"))]
    data = {"prompt": prompt["text"], "prompt_id": str(prompt["id"])}
    assert client.post("/api/extract", files=files, data=data).status_code == 201

    used = {c["id"]: c["used_at"] for c in client.get("/api/prompts").json()}
    assert used[prompt["id"]] is not None
    assert sum(v is not None for v in used.values()) == 1


def test_prompts_in_a_file(client, tmp_path):
    client.post("/api/prompts", json={"name": "Anglais", "text": "FR → EN"})
    saved = json.loads((tmp_path / "data" / "prompts.json").read_text(encoding="utf-8"))
    assert [(p["id"], p["name"]) for p in saved["user"]] == [(1, "Anglais")]  # Notosaurus's aren't copied


def test_dictation_prompt_starts_lessons_with_its_options(client):
    prompts = {p["id"]: p for p in client.get("/api/prompts").json()}
    dictation = prompts["notosaurus:dictation"]
    assert (dictation["name"], dictation["voice"]) == ("Dictation", "auto")
    assert dictation["dictation"] is True and dictation["dictation_only"] is True  # its cards: dictations alone
    gaps = prompts["notosaurus:dictation_gaps"]  # the hardest words of a text, one a card
    assert (gaps["name"], gaps["dictation_only"], gaps["voice"]) == ("Gap dictation", True, "auto")
    table = prompts["notosaurus:table"]  # a table by heart: its answers typed
    assert (table["name"], table["typing"], table["dictation"]) == ("Table to learn", True, False)
    blanks = prompts["notosaurus:blanks"]  # the sentences with a blank, typed: no dictation
    assert (blanks["name"], blanks["typing"], blanks["dictation"]) == ("Fill in the word", True, False)

    # The page sends the prompt's options with the generation: the lesson starts with them
    data = {
        "prompt": dictation["text"],
        "voice": "auto",
        "prompt_id": dictation["id"],
        "dictation": "true",
        "dictation_only": "true",
    }
    lesson = client.post("/api/extract", data=data).json()
    assert lesson["dictation"] is True and lesson["dictation_only"] is True
    plain = client.post("/api/extract", data={"prompt": "FR → ES"}).json()
    assert plain["typing"] is False and plain["dictation_only"] is False
    only = client.post("/api/extract", data={"prompt": "Dictée", "dictation_only": "true"}).json()
    assert only["dictation"] is True  # dictation alone is a dictation

    # A copy keeps them, to be changed
    copy = client.post("/api/prompts/notosaurus:dictation/duplicate").json()
    assert copy["dictation"] is True and copy["dictation_only"] is True and copy["builtin"] is False
    changed = client.put(f"/api/prompts/{copy['id']}", json={**copy, "dictation_only": False}).json()
    assert changed["dictation"] is True and changed["dictation_only"] is False


def test_auto_voice_follows_the_language_of_the_backs(client):
    lesson = client.post("/api/extract", data={"prompt": "FR → ES", "voice": "auto"}).json()
    assert lesson["voice"] == "es-ES-ElviraNeural"  # the fake AI says the backs are es-ES
    voices = {p["id"]: p["voice"] for p in client.get("/api/prompts").json()}
    assert voices["notosaurus:sentences"] == voices["notosaurus:vocabulary"] == "auto"
    assert voices["notosaurus:questions"] == ""
    settings.save({"voices": {"es-ES": "es-ES-AlvaroNeural"}})  # chosen in the settings
    assert (
        client.post("/api/extract", data={"prompt": "FR → ES", "voice": "auto"}).json()["voice"] == "es-ES-AlvaroNeural"
    )


def test_no_auto_voice_in_the_pupils_own_language(client):
    """A lesson in the pupil's own language ("Français" for a French pupil) is no language
    being learned: no voice, whatever the AI said, unless the cards are a dictation."""
    spanish_page = {"X-Notosaurus-Lang": "es"}  # the demo AI says the backs are es-ES
    lesson = client.post("/api/extract", data={"prompt": "Literatura", "voice": "auto"}, headers=spanish_page).json()
    assert lesson["voice"] == ""
    data = {"prompt": "Dictado", "voice": "auto", "typing": "true", "dictation": "true"}
    assert client.post("/api/extract", data=data, headers=spanish_page).json()["voice"] == "es-ES-ElviraNeural"
    url = f"/api/lessons/{lesson['id']}/regenerate"  # the same rule when generating again
    assert client.post(url, data={"prompt": "Literatura", "voice": "auto"}, headers=spanish_page).json()["voice"] == ""
    french_page = {"X-Notosaurus-Lang": "fr"}  # Spanish for a French pupil: a language being learned
    assert client.post("/api/extract", data={"prompt": "FR → ES", "voice": "auto"}, headers=french_page).json()[
        "voice"
    ] == ("es-ES-ElviraNeural")


def test_automatic_prompt_says_what_the_ai_chose(client):
    (auto,) = [p for p in client.get("/api/prompts").json() if p["id"] == "notosaurus:auto"]
    lesson = client.post("/api/extract", data={"prompt": auto["text"], "voice": "auto"}).json()
    assert lesson["choice"] == "Vocabulaire d'espagnol : français → espagnol"  # demo mode's choice
    assert client.get(f"/api/lessons/{lesson['id']}").json()["choice"] == lesson["choice"]  # kept
    saved = client.put(f"/api/lessons/{lesson['id']}", json={"deck": "Autre", "cards": lesson["cards"]}).json()
    assert saved["choice"] == lesson["choice"]  # not lost when the lesson is edited
    assert client.post("/api/extract", data={"prompt": "FR → ES"}).json()["choice"] == ""


def test_the_android_app_has_the_same_prompts():
    """The app lists Notosaurus's prompts too (Prompts.kt): the same, in the same order."""
    kotlin = Path("android/app/src/main/java/app/notosaurus/Prompts.kt").read_text(encoding="utf-8")
    listed = re.search(r"BUILTIN = listOf\(([^)]*)\)", kotlin).group(1)
    assert tuple(re.findall(r'"(\w+)"', listed)) == prompts.BUILTIN


def test_a_dictation_in_the_pupils_own_language_has_their_voice():
    """For their own language the AI gives none: a dictation (or typed answers) still needs
    a voice, the page's language."""
    from app.routes.generation import _learned

    assert _learned("", "fr", spelling=True) == "fr"
    assert _learned("", "fr-FR", spelling=True) == "fr"
    assert _learned("es-ES", "fr", spelling=True) == "es-ES"  # a language learned: its own
    assert _learned("fr-FR", "fr", spelling=True) == "fr-FR"
    assert _learned("fr-FR", "fr", spelling=False) == ""  # not a dictation: no voice
    assert _learned("", "fr", spelling=False) == ""


def test_a_dictation_the_ai_recognised_makes_dictation_cards_alone(client, monkeypatch):
    """Automatic: the AI says the page is a dictation to prepare; the lesson's cards are
    then dictation cards alone, heard in the pupil's own language."""
    from app.routes import generation
    from notosaurus_core.llm import Extracted
    from notosaurus_core.models import Card, Deck

    async def extract(*_, **__):
        cards = [Card(front="Le chat boit du …", back="lait")]
        return Extracted(
            deck=Deck(deck="Français::Dictée", cards=cards), turns=[], frames=[], choice="Une dictée.", dictation=True
        )

    monkeypatch.setattr(generation, "extract_cards", extract)
    page = {"X-Notosaurus-Lang": "fr"}
    lesson = client.post("/api/extract", data={"prompt": "Automatique", "voice": "auto"}, headers=page).json()
    assert lesson["dictation"] is True and lesson["dictation_only"] is True
    assert lesson["voice"].startswith("fr-")  # the pupil's own language: its dictation's voice


def test_the_options_the_ai_read_in_the_instructions(client, monkeypatch):
    """One's own prompt: a typed answer, a dictation of each card, as its text asks (the AI
    says so); its voice "auto", the backs' language's."""
    from app.routes import generation
    from notosaurus_core.llm import Extracted
    from notosaurus_core.models import Card, Deck

    async def extract(*_, **__):
        cards = [Card(front="la mère", back="la madre")]
        deck = Deck(deck="Espagnol::Famille", cards=cards)
        return Extracted(deck=deck, turns=[], frames=[], back_language="es-ES", typing=True, dictation_card=True)

    monkeypatch.setattr(generation, "extract_cards", extract)
    data = {"prompt": "Vocabulaire espagnol, réponse tapée, avec une dictée", "voice": "auto"}
    lesson = client.post("/api/extract", data=data).json()
    assert (lesson["typing"], lesson["dictation"], lesson["dictation_only"]) == (True, True, False)
    assert lesson["voice"] == "es-ES-ElviraNeural"


def test_the_backs_speed():
    """Slowed (the settings' slowdown) for a language being learned or a dictation, normal
    for the pupil's own language; what the instructions say first."""
    from app.routes.generation import _rate

    assert _rate("-25%", "", foreign=True, dictation=False) == "-25%"
    assert _rate("-25%", "", foreign=False, dictation=True) == "-25%"  # time to write
    assert _rate("-25%", "", foreign=False, dictation=False) == "+0%"  # a history lesson
    assert _rate("-25%", "normal", foreign=True, dictation=False) == "+0%"
    assert _rate("-25%", "slow", foreign=False, dictation=False) == "-25%"
    assert _rate("+0%", "slow", foreign=False, dictation=False) == "-10%"  # asked: slowed all the same
    assert _rate("+0%", "", foreign=True, dictation=True) == "+0%"  # the settings don't slow


def test_a_lesson_keeps_its_speed(client, monkeypatch):
    from app.routes import generation
    from notosaurus_core.llm import Extracted
    from notosaurus_core.models import Card, Deck

    found = {"back_language": "", "speed": ""}

    async def extract(*_, **__):
        deck = Deck(deck="Histoire", cards=[Card(front="1789", back="La Révolution")])
        return Extracted(deck=deck, turns=[], frames=[], **found)

    monkeypatch.setattr(generation, "extract_cards", extract)
    page = {"X-Notosaurus-Lang": "fr"}
    assert client.post("/api/extract", data={"prompt": "p"}, headers=page).json()["rate"] == "+0%"
    found["back_language"] = "es-ES"
    lesson = client.post("/api/extract", data={"prompt": "p"}, headers=page).json()
    assert lesson["rate"] == "-10%"  # the settings' default
    assert client.get(f"/api/lessons/{lesson['id']}").json()["rate"] == "-10%"
    found["speed"] = "normal"
    assert client.post("/api/extract", data={"prompt": "p"}, headers=page).json()["rate"] == "+0%"


def test_the_automatic_prompt_knows_a_dictation():
    import json
    from pathlib import Path

    for lang in Path(__file__).resolve().parent.parent.joinpath("static/i18n").glob("*.json"):
        auto = json.loads(lang.read_text(encoding="utf-8"))["builtinPrompts"]["auto"]["text"]
        assert auto.count("\n- ") >= 7, lang.name  # its cases, a dictation to prepare among them
