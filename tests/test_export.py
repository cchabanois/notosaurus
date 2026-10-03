"""The exported .apkg: note types and templates, GUIDs stable across corrections,
the audio read aloud, cloze gaps, typed answers, multiple choice — the real
package, unzipped, its SQLite collection read (tests/apkg.py)."""

import apkg
from conftest import CLOZE, extract_lesson, synthesized

from app import anki, tts
from app.models import Card

EXPORT = {
    "deck": "Espagnol::Leçon 5",
    "cards": [
        {"front": "la mère", "back": "la madre", "info": "nom féminin", "subdeck": "Vocabulaire"},
        {"front": "<b>", "back": "¿Cómo te llamas?", "subdeck": "Phrases"},
        {"front": "", "back": "ignorée : recto vide"},
    ],
    "voice": "es_ES",
    "reverse": True,
}


def test_export_apkg(client, tmp_path):
    res = client.post("/api/export", json=EXPORT)
    assert res.status_code == 200
    assert "attachment" in res.headers["content-disposition"]

    package = apkg.Apkg(res.content, tmp_path)
    assert len(package.notes) == 2
    assert any("&lt;b&gt;" in note[2] for note in package.notes)  # text is HTML-escaped
    (model,) = package.models.values()
    assert [t["name"] for t in model["tmpls"]] == ["Recto → Verso", "Verso → Recto"]
    assert "{{tts es_ES:Back}}" in model["tmpls"][0]["afmt"]
    deck_names = {d["name"] for d in package.decks.values()}
    assert {"Espagnol::Leçon 5::Vocabulaire", "Espagnol::Leçon 5::Phrases"} <= deck_names


def test_export_guid_stable(client, tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a = apkg.export(client, EXPORT, tmp_path / "a")
    # Corrected back, same front and deck → same GUID, so Anki updates the note.
    corrected = {**EXPORT, "cards": [{**EXPORT["cards"][0], "back": "la mamá"}]}
    b = apkg.export(client, corrected, tmp_path / "b")
    assert b.notes[0][0] in set(a.guids)


def test_export_has_the_apkg_type(client):
    res = client.post("/api/export", json=EXPORT)
    assert res.headers["content-type"] == "application/apkg"  # AnkiDroid opens it from the download


def test_export_empty(client):
    res = client.post("/api/export", json={"deck": "X", "cards": [{"front": "", "back": ""}]})
    assert res.status_code == 400


AUDIO_EXPORT = {
    "deck": "Espagnol::Leçon 5",
    "cards": [
        {"front": "la mère", "back": "la madre"},
        {"front": "maman", "back": "la madre"},  # same back → a single mp3
        {"front": "le père", "back": "ÉCHEC"},
    ],
    "voice": "es-ES-ElviraNeural",
}


def test_export_audio_edge_tts(client, tmp_path):
    res = client.post("/api/export", json=AUDIO_EXPORT)
    assert res.status_code == 200
    assert res.headers["X-Notosaurus-Audio-Failures"] == "1"
    assert synthesized == ["la madre"]

    package = apkg.Apkg(res.content, tmp_path)
    (model,) = package.models.values()
    assert [f["name"] for f in model["flds"]] == ["Front", "Back", "Info", "Audio"]
    assert "{{Audio}}" in model["tmpls"][0]["afmt"]
    sounds = [note[2].split("\x1f")[3] for note in package.notes]
    assert sounds.count(f"[sound:{tts.filename('la madre', 'es-ES-ElviraNeural')}]") == 2
    assert "" in sounds  # the failed card goes out without sound
    assert package.media == [tts.filename("la madre", "es-ES-ElviraNeural")]


def test_audio_in_the_lesson(client):
    lesson = extract_lesson(client)
    export = {**AUDIO_EXPORT, "lesson_id": lesson["id"]}
    client.post("/api/export", json=export)
    client.post("/api/export", json=export)
    assert synthesized == ["la madre"]  # kept in the lesson folder, not synthesized again

    from app import lessons

    audio = lessons.audio_dir(lesson["id"])
    assert [p.name for p in audio.iterdir()] == [tts.filename("la madre", "es-ES-ElviraNeural")]
    assert tts.filename("la madre", "es-ES-ElviraNeural").startswith("la-madre-")

    # Back corrected: the new mp3 replaces the old one
    corrected = {**export, "cards": [{"front": "la mère", "back": "la mamá"}]}
    client.post("/api/export", json=corrected)
    assert [p.name for p in audio.iterdir()] == [tts.filename("la mamá", "es-ES-ElviraNeural")]


def test_preview_then_export_reuses_the_sound(client):
    lesson = extract_lesson(client)
    params = {"text": "la madre", "voice": "es-ES-ElviraNeural", "lesson": lesson["id"]}
    assert client.get("/api/tts", params=params).status_code == 200
    client.post("/api/export", json={**AUDIO_EXPORT, "lesson_id": lesson["id"]})
    assert synthesized == ["la madre"]


def test_voice_preview(client):
    res = client.get("/api/tts", params={"text": "hola", "voice": "es-ES-ElviraNeural"})
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/mpeg"
    assert client.get("/api/tts", params={"text": "hola", "voice": "es_ES"}).status_code == 400


def test_voice_for_a_language(monkeypatch):
    import asyncio

    from app import tts

    available = [
        {"voice": "es-MX-JorgeNeural", "locale": "es-MX", "gender": "Male"},
        {"voice": "de-AT-IngridNeural", "locale": "de-AT", "gender": "Female"},
        {"voice": "ja-JP-KeitaNeural", "locale": "ja-JP", "gender": "Male"},
        {"voice": "ja-JP-NanamiNeural", "locale": "ja-JP", "gender": "Female"},
    ]

    async def voices():
        return available

    monkeypatch.setattr(tts, "voices", voices)
    voice = lambda language: asyncio.run(tts.voice_for(language))  # noqa: E731
    assert voice("es-ES") == voice("es") == "es-ES-ElviraNeural"  # preferred
    assert voice("es-MX") == "es-MX-DaliaNeural"
    assert voice("de-AT") == "de-AT-IngridNeural"  # that variety, not the preferred German one
    assert voice("ja-JP") == voice("ja") == "ja-JP-NanamiNeural"  # a female voice first
    assert voice("xx") == voice("") == ""


def test_formulas_shown_by_anki_not_read_aloud(client, tmp_path):
    assert tts.has_math(r"aire : \(\pi r^2\)") and tts.has_math(r"\[\frac{a}{b}\]")
    assert not tts.has_math("a² + b² = c²") and not tts.has_math("(a + b) / 2")
    export = {
        "deck": "Maths",
        "voice": "es-ES-ElviraNeural",
        "cards": [
            {"front": "aire du disque", "back": r"\(\pi r^2\)"},  # a formula: no sound
            {"front": "la madre", "back": "la madre"},
        ],
    }
    synthesized.clear()
    package = apkg.export(client, export, tmp_path)
    assert synthesized == ["la madre"]
    (disc,) = [note[2] for note in package.notes if "pi r" in note[2]]
    assert r"\(\pi r^2\)" in disc  # kept as is: Anki draws it (MathJax)
    assert "[sound:" not in disc


def test_cloze_cards_one_anki_card_per_gap(client, tmp_path):
    assert anki.is_cloze("en {{c1::1789}}") and anki.is_cloze("{{c12::x::indice}}")
    assert not anki.is_cloze("{{Front}}") and not anki.is_cloze("une {accolade}")
    synthesized.clear()
    package = apkg.export(client, CLOZE, tmp_path)
    assert synthesized == ["la madre"]  # a text with gaps isn't read aloud, even with a back

    (cloze,) = [m for m in package.models.values() if m["type"] == 1]  # Anki's cloze note type
    assert cloze["name"] == "Notosaurus texte à trous"
    assert [f["name"] for f in cloze["flds"]] == ["Text", "Extra", "Info", "Id"]
    assert "{{cloze:Text}}" in cloze["tmpls"][0]["qfmt"]
    texts = {note[2].split("\x1f")[0]: note[2].split("\x1f") for note in package.notes}
    bastille = texts[CLOZE["cards"][0]["front"]]
    assert bastille[1:] == ["", "", "rev1"]  # no back needed; the card's id tells the note
    assert package.cards == 2 + 1 + 1  # one Anki card per gap number


def test_line_breaks_kept_in_anki(client, tmp_path):
    cards = [
        {"front": "Les 3 couleurs :\nbleu, blanc, rouge", "back": "le drapeau <français>"},
        {"id": "c1", "front": "Vers 1 : {{c1::Maître corbeau}}\nVers 2 : sur un arbre perché", "back": ""},
    ]
    package = apkg.export(client, {"deck": "Test", "cards": cards, "voice": ""}, tmp_path)
    fields = sorted(note[2].split("\x1f")[0] for note in package.notes)
    assert fields == [
        "Les 3 couleurs :<br>bleu, blanc, rouge",
        "Vers 1 : {{c1::Maître corbeau}}<br>Vers 2 : sur un arbre perché",
    ]


def test_typed_answer_and_dictation(client, tmp_path):
    export = {
        "deck": "Espagnol",
        "voice": "es-ES-ElviraNeural",
        "typing": True,
        "dictation": True,
        "cards": [
            {"front": "la mère", "back": "la madre"},
            {"front": "aire du disque", "back": r"\(\pi r^2\)"},  # a formula: neither typed nor heard
        ],
    }
    package = apkg.export(client, export, tmp_path)
    by_name = {m["name"]: m for m in package.models.values()}
    typed = by_name["Notosaurus recto/verso à taper + dictée (audio)"]
    recto, dictation = typed["tmpls"]
    assert recto["qfmt"].endswith("{{type:Back}}") and "{{type:Back}}" in recto["afmt"]
    assert "{{FrontSide}}" not in recto["afmt"]  # the box shown once
    assert dictation["qfmt"] == '<div class="dictation">🎧</div>{{Audio}}{{type:Back}}'
    assert "Notosaurus recto/verso (audio)" in by_name  # the formula's note type, as before
    assert package.cards == 2 + 1

    # Without a voice, nothing to hear: no dictation card
    package = apkg.export(client, {**export, "voice": "", "cards": export["cards"][:1]}, tmp_path)
    assert [m["name"] for m in package.models.values()] == ["Notosaurus recto/verso à taper (audio)"]


def test_plain_note_types_keep_their_ids(client):
    """Users already have these note types in Anki: the new options mustn't change them."""
    assert anki._model(anki.note_type("es_ES", False)).model_id == anki._stable_id("model", "TTS Anki es_ES", "False")
    assert anki._model(anki.note_type("", True)).model_id == anki._stable_id("model", "audio", "True")
    typed = anki._model(anki.note_type("", False, typing=True)).model_id
    assert typed != anki._model(anki.note_type("", False)).model_id


def test_note_type_ids_are_unique():
    """A package carries note types by id: two different ones must never share it."""
    from itertools import product

    names: dict[int, set[str]] = {}
    for voice, reverse, typing, dictation in product(["", "es_ES", "es-ES-ElviraNeural"], *[[False, True]] * 3):
        nt = anki.note_type(voice, reverse, typing, dictation)
        names.setdefault(anki._model(nt).model_id, set()).add(nt.name)
    for nt in (anki.diagram_note_type("", t) for t in (False, True)):
        names.setdefault(anki._model(nt).model_id, set()).add(nt.name)
    for voice, typing, on_back in product(["", "es_ES"], [False, True], [False, True]):
        nt = anki.picture_note_type(voice, typing, on_back)
        names.setdefault(anki._model(nt).model_id, set()).add(nt.name)
    assert all(len(n) == 1 for n in names.values())


def test_same_front_twice_one_note_each(anki, client, tmp_path):
    cards = [{"front": "le vol", "back": "el vuelo"}, {"front": "le vol", "back": "el robo"}]
    body = {"deck": "Espagnol", "cards": cards, "voice": ""}
    assert client.post("/api/anki/send", json=body).json()["added"] == 2
    corrected = {**body, "cards": [{**cards[0], "back": "el vuelo (avion)"}, cards[1]]}
    assert client.post("/api/anki/send", json=corrected).json()["updated"] == 2
    # In a package too: a GUID each
    package = apkg.export(client, body, tmp_path)
    assert len(set(package.guids)) == 2


def test_multiple_choice_and_true_false(client, tmp_path):
    lesson = client.post("/api/extract", data={"prompt": "QCM sur la Révolution"}).json()
    assert [len(c["choices"]) for c in lesson["cards"]] == [3, 3, 1, 1]
    synthesized.clear()
    body = {
        "deck": "D",
        "cards": lesson["cards"],
        "voice": "es-ES-ElviraNeural",
        "typing": True,
        "lesson_id": lesson["id"],
    }
    package = apkg.export(client, body, tmp_path)
    assert synthesized == []  # the options are read, not heard
    (model,) = package.models.values()  # neither typed nor with a sound: the same note type
    assert model["name"] == "Notosaurus QCM"
    fields = [f["name"] for f in model["flds"]]
    first = dict(zip(fields, package.fields(package.notes[0]), strict=True))
    assert first["Answer"] == "1789"
    assert first["Choices"].count("<li>") == 4 and "right" not in first["Choices"]
    assert (
        first["AnswerChoices"].count('class="wrong"') == 3 and '<li class="right">1789</li>' in first["AnswerChoices"]
    )

    # The order: fixed per card, the right one anywhere; true/false always alphabetical
    card = Card(front="En quelle année ?", back="1789", choices=["1715", "1799", "1804"])
    assert anki.choice_order(card) == anki.choice_order(card.model_copy())
    fronts = [f"Question {n}" for n in range(20)]
    firsts = {anki.choice_order(Card(front=f, back="right", choices=["a", "b", "c"]))[0] for f in fronts}
    assert "right" in firsts and len(firsts) > 1
    assert anki.choice_order(Card(front="x", back="Vrai", choices=["Faux"])) == ["Faux", "Vrai"]
    assert anki.choice_order(Card(front="y", back="Faux", choices=["Vrai"])) == ["Faux", "Vrai"]

    # Not a multiple choice: no wrong answer left, or a text with gaps
    assert not anki.is_choice(Card(front="q", back="r", choices=["  "]))
    assert not anki.is_choice(Card(front="en {{c1::1789}}", back="", choices=["x"]))


def test_fun_facts_only_when_asked(client, tmp_path):
    # In Anki: under the info, on the back; escaped like the other fields
    cards = [{"front": "la mère", "back": "la madre", "info": "f.", "fun_fact": "Vient du latin <mater>."}]
    package = apkg.export(client, {"deck": "D", "cards": cards}, tmp_path)
    info = package.notes[0][2].split("\x1f")[2]
    assert info == 'f.<div style="margin-top:8px;font-style:italic">💡 Vient du latin &lt;mater&gt;.</div>'
