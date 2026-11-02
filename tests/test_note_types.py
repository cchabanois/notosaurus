"""static/note-types.json: the note types the Android app makes in AnkiDroid, written
from app/note_types/ (tools/note_types.py): the same as the computer's."""

import importlib.util
import json
from pathlib import Path

from app.note_types import common

ROOT = Path(__file__).resolve().parent.parent


def tool():
    spec = importlib.util.spec_from_file_location("note_types", ROOT / "tools" / "note_types.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_up_to_date():
    """Changed app/note_types/: run tools/note_types.py."""
    assert (ROOT / "static" / "note-types.json").read_text(encoding="utf-8") == tool().text()


def test_every_variant_the_app_uses():
    note_types = json.loads((ROOT / "static" / "note-types.json").read_text(encoding="utf-8"))["note_types"]
    assert {nt["family"] for nt in note_types.values()} == {"text", "diagram", "cloze", "choice"}  # a picture: any
    assert len(note_types["text+reverse+typing+dictation"]["cards"]) == 3  # front → back, back → front, dictation
    for key, nt in note_types.items():
        assert nt["key"] in nt["fields"], key
        assert nt["cloze"] == (key == "cloze")
        assert "Audio" in nt["fields"] or nt["family"] in ("cloze", "choice"), key  # the sound: a field


# Each family's fields at each version (the sound's "Audio" left out: an Anki TTS voice has
# none). A note type's fields never change under its name (AnkiDroid can't add one): changed,
# its family's version goes up (common.VERSIONS), its name with it, and its fields go here.
FIELDS = {
    ("text", 1): ["Front", "Back", "Info", "Explanation", "Mnemonic"],  # 1.0.0
    ("text", 2): ["Front", "Back", "Info", "Explanation", "Mnemonic", "Picture", "BackPicture", "Id", "Source"],
    ("choice", 1): [
        "Question",
        "Answer",
        "Choices",
        "AnswerChoices",
        "Picture",
        "BackPicture",
        "Info",
        "Id",
        "Explanation",
        "Mnemonic",
    ],  # 1.0.0
    ("choice", 2): [
        "Question",
        "Answer",
        "Choices",
        "AnswerChoices",
        "Picture",
        "BackPicture",
        "Info",
        "Id",
        "Explanation",
        "Mnemonic",
        "Source",
    ],
    ("diagram", 1): ["Front", "Back", "Info", "Image", "Masks", "AnswerMasks", "Id", "Explanation", "Mnemonic"],
    ("cloze", 1): ["Text", "Extra", "Info", "Id", "Explanation", "Mnemonic"],
}


def test_fields_changed_only_with_a_new_version():
    """A note type's fields changed under the same name: a phone whose AnkiDroid has it would
    keep it lacking them, its cards without their pictures and its new notes taken for
    leftovers. Bump its family's version in common.VERSIONS, and give its fields here."""
    variants = tool().variants()
    variants["text+tts"] = tool().anki.note_type("es_ES", reverse=True, typing=True)  # an Anki voice: no Audio
    for key, nt in variants.items():
        version = common.VERSIONS[nt.family]
        assert [f for f in nt.fields if f != "Audio"] == FIELDS[(nt.family, version)], key
        assert nt.name.endswith(f" v{version}") == (version > 1), key
