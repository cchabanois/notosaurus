"""💬 A card explained to the pupil, then the follow-ups the AI says would help."""

from conftest import extract_lesson

from notosaurus_core import llm
from notosaurus_core.config import AIConfig
from notosaurus_core.models import Card, Explanation


def test_a_card_explained_then_its_follow_ups(client):
    lesson = client.post("/api/extract", data={"prompt": "QCM sur la Révolution"}).json()
    qcm = lesson["cards"][0]
    url = f"/api/lessons/{lesson['id']}/explain"
    first = client.post(url, json={"card": qcm}).json()
    assert first["text"].startswith("(démo, explain) En quelle année")
    assert first["more"] == ["example", "mnemonic", "why"]  # "why": a multiple choice
    why = client.post(url, json={"card": qcm, "kind": "why"}).json()
    assert why["text"].startswith("(démo, why)") and "why" not in why["more"]  # never the one just given
    # The card as shown is explained, edited or not; the calls are kept with the lesson
    edited = client.post(url, json={"card": {**qcm, "front": "Autre question ?"}}).json()
    assert "Autre question ?" in edited["text"]
    kinds = [c["kind"] for c in client.get(f"/api/lessons/{lesson['id']}").json()["ai_calls"]]
    assert kinds == ["extract", "explain", "explain", "explain"]
    assert client.post(url, json={"card": qcm, "kind": "poem"}).status_code == 422


def test_explaining_needs_a_lesson_one_may_see(anki, client):
    lesson = extract_lesson(client)  # Léa's, private
    url = f"/api/lessons/{lesson['id']}/explain"
    anki.profile = "Paul"
    assert client.post(url, json={"card": lesson["cards"][0]}).status_code == 404
    anki.profile = "Léa"
    assert client.post(url, json={"card": lesson["cards"][0]}).status_code == 200
    assert client.post("/api/lessons/nope/explain", json={"card": lesson["cards"][0]}).status_code == 404


def test_what_the_ai_is_asked(monkeypatch):
    card = Card(front="la Bastille est prise le…", back="14 juillet 1789", choices=["4 août 1789"])
    text = llm._explain_text(card, "why", "Questions sur la Révolution", "Histoire", "French", ["Le 14 juillet 1789…"])
    assert '"front": "la Bastille est prise le…"' in text and '"wrong_options": ["4 août 1789"]' in text
    assert llm.EXPLAIN_ASKS["why"] in text and "Answer in French." in text
    assert "The lesson's text (from its PDF):\n<<<\nLe 14 juillet 1789…\n>>>" in text
    assert "PDF" not in llm._explain_text(card, "explain", "p", "d", "English", ["", "  "])

    # The AI's follow-ups: never the one just given, each once
    async def answer(s, images, text, schema, system, light=False):
        assert system == llm.EXPLAIN_RULES and light and images == []
        return Explanation(text="…", more=["why", "example", "why", "mnemonic"])

    import asyncio

    monkeypatch.setattr(llm, "_generate", answer)
    found = asyncio.run(llm.explain_card(AIConfig(llm="gemini"), card, "why", "p", "d", "French"))
    assert found.more == ["example", "mnemonic"]
