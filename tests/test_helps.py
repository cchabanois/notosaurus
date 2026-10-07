"""Helps on the back (an explanation, a way to remember it), asked for at generation;
their switch's default in the settings."""

import apkg
from conftest import ADMIN

from app import anki
from notosaurus_core import llm
from notosaurus_core.config import AIConfig


def test_helps_only_when_asked(client):
    assert llm.HELPS not in llm._user_text("Vocabulary", "", photos=1)
    assert llm.HELPS in llm._user_text("Vocabulary", "", photos=1, helps=True)
    plain = client.post("/api/extract", data={"prompt": "FR → ES"}).json()
    assert not any(c["explanation"] or c["mnemonic"] for c in plain["cards"])
    asked = client.post("/api/extract", data={"prompt": "FR → ES", "helps": "true"}).json()
    assert asked["cards"][0]["explanation"] and asked["cards"][-1]["mnemonic"]  # the demo: one of each
    again = client.post(f"/api/lessons/{plain['id']}/regenerate", data={"prompt": "FR → ES", "helps": "true"}).json()
    assert again["cards"][0]["explanation"]


def test_helps_on_the_back_in_anki(client, tmp_path):
    cards = [
        {"front": "le parapluie", "back": "el paraguas", "mnemonic": "para + agua: <qui arrête l'eau>"},
        {"front": "Aire du disque", "back": "π r²", "explanation": "Un disque découpé en parts…"},
        {"front": "en {{c1::1789}}", "back": "", "explanation": "La Révolution."},
    ]
    package = apkg.export(client, {"deck": "D", "cards": cards}, tmp_path)
    for model in package.models.values():  # every note type: the two fields, shown on the back only
        assert [f["name"] for f in model["flds"]][-2:] == ["Explanation", "Mnemonic"]
        assert all("{{Explanation}}" in t["afmt"] and "{{Explanation}}" not in t["qfmt"] for t in model["tmpls"])
    fields = {package.fields(n)[0]: package.fields_by_name(n) for n in package.notes}
    assert fields["le parapluie"]["Mnemonic"] == "para + agua: <qui arrête l'eau>"
    assert "&lt;qui" in package.notes[0][2]  # escaped in the field, as the other fields
    assert (fields["Aire du disque"]["Explanation"], fields["Aire du disque"]["Mnemonic"]) == (
        "Un disque découpé en parts…",
        "",
    )
    assert fields["en {{c1::1789}}"]["Explanation"] == "La Révolution."
    assert anki.BACK_INFO.endswith("{{/Mnemonic}}")


def test_the_switch_default_is_set_in_the_settings(admin):
    assert admin.get("/api/config").json()["card_helps"] is False  # off at first
    assert admin.put("/api/admin/settings", headers=ADMIN, json={"card_helps": True}).status_code == 200
    assert admin.get("/api/config").json()["card_helps"] is True


def test_what_the_ai_fills(monkeypatch):
    """The AI sees only what it fills: never the fields Notosaurus sets, the fun facts and
    helps only when asked (Anthropic refuses too complex a response schema)."""
    import asyncio

    from notosaurus_core.models import Extraction

    def card_fields(schema):
        return set(schema.model_fields["cards"].annotation.__args__[0].model_fields)

    plain = card_fields(llm.ai_schema(Extraction))
    assert not plain & {"picture", "id", "fun_fact", "explanation", "mnemonic"} and {"front", "back"} <= plain
    assert {"explanation", "mnemonic"} <= card_fields(llm.ai_schema(Extraction, helps=True))
    assert "fun_fact" in card_fields(llm.ai_schema(Extraction, fun_facts=True))

    async def answer(s, images, text, schema, system=None, **options):
        return schema(deck="D", cards=[{"front": "a", "back": "b", "explanation": "c"}])

    monkeypatch.setattr(llm, "_generate", answer)
    found = asyncio.run(llm.extract_cards(AIConfig(llm="gemini"), [], "p", helps=True))
    card = found.deck.cards[0]
    from notosaurus_core.models import Card

    assert isinstance(card, Card) and (card.explanation, card.id, card.picture) == ("c", "", "")  # Notosaurus's own
