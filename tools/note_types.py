"""Write static/note-types.json: the Anki note types as app/anki.py makes them (with a
voice: the back's sound in an "Audio" field), in every variant the Android app uses. The
app (android/, its assets copied from static/) makes its AnkiDroid note types from it
instead of a copy of its own. A test checks it is up to date.

Usage: .venv/bin/python tools/note_types.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

from app import anki  # noqa: E402

OUT = ROOT / "static" / "note-types.json"
VOICE = "es-ES-ElviraNeural"  # any edge-tts voice: the sound is a field (not Anki's {{tts}})


def spec(nt: anki.NoteType) -> dict:
    return {
        "name": nt.name,
        "family": nt.family,
        "fields": list(nt.fields),
        "key": nt.key,  # which note an update is for
        "cloze": nt.cloze,
        "cards": [{"name": t["name"], "front": t["qfmt"], "back": t["afmt"]} for t in nt.templates],
        "css": nt.css,
    }


def variants() -> dict[str, anki.NoteType]:
    """Each note type by its family and options ("text+reverse+typing", "picture+back")."""
    found = {}
    for reverse in (False, True):
        for typing in (False, True):
            for dictation in (False, True):
                options = [o for o, on in (("reverse", reverse), ("typing", typing), ("dictation", dictation)) if on]
                found["+".join(["text", *options])] = anki.note_type(VOICE, reverse, typing, dictation)
    for typing in (False, True):
        found["diagram" + ("+typing" if typing else "")] = anki.diagram_note_type(VOICE, typing)
        for on_back in (False, True):
            options = [o for o, on in (("back", on_back), ("typing", typing)) if on]
            found["+".join(["picture", *options])] = anki.picture_note_type(VOICE, typing, on_back)
    found["cloze"] = anki.cloze_note_type()
    found["choice"] = anki.choice_note_type()
    return found


def text() -> str:
    note_types = {key: spec(nt) for key, nt in variants().items()}
    return json.dumps({"note_types": note_types}, ensure_ascii=False, indent=1) + "\n"


if __name__ == "__main__":
    OUT.write_text(text(), encoding="utf-8")
    print(OUT)
