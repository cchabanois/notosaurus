"""static/note-types.json: the note types the Android app makes in AnkiDroid, written
from app/anki.py (tools/note_types.py): the same as the computer's."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def tool():
    spec = importlib.util.spec_from_file_location("note_types", ROOT / "tools" / "note_types.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_up_to_date():
    """Changed app/anki.py: run tools/note_types.py."""
    assert (ROOT / "static" / "note-types.json").read_text(encoding="utf-8") == tool().text()


def test_every_variant_the_app_uses():
    note_types = json.loads((ROOT / "static" / "note-types.json").read_text(encoding="utf-8"))["note_types"]
    assert {nt["family"] for nt in note_types.values()} == {"text", "diagram", "picture", "cloze", "choice"}
    assert len(note_types["text+reverse+typing+dictation"]["cards"]) == 3  # front → back, back → front, dictation
    for key, nt in note_types.items():
        assert nt["key"] in nt["fields"], key
        assert nt["cloze"] == (key == "cloze")
        assert "Audio" in nt["fields"] or nt["family"] in ("cloze", "choice"), key  # the sound: a field
