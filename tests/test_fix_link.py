"""The "✎ Notosaurus" link under every answer in Anki (app/note_types/common.py): the card
opened in Notosaurus, built on the card from the note's tag and key field."""

import json
from pathlib import Path

from app import anki
from app.note_types import common

ROOT = Path(__file__).resolve().parent.parent


def _answers(nt) -> list[str]:
    return [t["afmt"] for t in nt.templates]


def test_every_note_type_links_back_with_its_key():
    keyed = {
        anki.note_type("es-ES-ElviraNeural", reverse=True, typing=True, dictation=True): "Front",
        anki.note_type("es_ES", reverse=False): "Front",
        anki.diagram_note_type("es-ES-ElviraNeural"): "Id",  # "lesson:page:n": the question repeats
        anki.picture_note_type("es-ES-ElviraNeural", on_back=True): "Id",
        anki.cloze_note_type(): "Id",
        anki.choice_note_type(): "Id",
    }
    for nt, key in keyed.items():
        for answer in _answers(nt):
            assert f'data-key="{{{{text:{key}}}}}"' in answer and 'data-tags="{{Tags}}"' in answer, nt.name
            assert answer.count("✎ Notosaurus") == 1 and answer.count(common.FIX_SCRIPT) == 1, nt.name
            assert answer.index("{{/Mnemonic}}") < answer.index("✎ Notosaurus")  # last, under the helps
        assert key in nt.fields and all("nfix" not in t["qfmt"] for t in nt.templates), nt.name  # never on the front


def test_the_link_opens_the_app_or_the_computers_page_nowhere_else():
    script = common.FIX_SCRIPT
    assert "intent://fix?" in script and "package=app.notosaurus" in script  # Android: the app
    assert "http://localhost:8000/?" in script  # the computer: the add-on's page
    assert "browser_fallback_url" in script  # the app missing: Google Play's page
    assert 'display="none"' in script  # neither (AnkiWeb, AnkiMobile): hidden
    assert "notosaurus::" in script and "encodeURIComponent" in script  # the lesson's tag, the key encoded


def test_the_android_note_types_have_it_too():
    note_types = json.loads((ROOT / "static" / "note-types.json").read_text(encoding="utf-8"))["note_types"]
    assert all(all("✎ Notosaurus" in c["back"] for c in nt["cards"]) for nt in note_types.values())
