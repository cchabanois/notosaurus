"""A card's formulas as they reach Anki: sent through AnkiConnect, in a package, in a shared
package, none of MathJax's html commands (a link, a style) that Anki's MathJax would run at
review; a style of one colour kept as \\color. The rule itself: app/note_types/formulas.py,
its cases in core/shared-cases.json."""

import re

import apkg
from conftest import extract_lesson

# A command of MathJax's html extension, anywhere in a field
HTML_COMMAND = re.compile(r"\\(?:href|style|class|cssId|data)(?![a-zA-Z])")

LINK = r"\(\href{javascript:alert(1)}{x}\)"
STYLED = r"\(\style{position:fixed;inset:0}{y} + \class{flash}{z} + \cssId{taken}{w} + \data{a=1}{v}\)"
COLOURED = r"\(\style{color: red}{u}\)"
CARDS = [
    {
        "front": f"Front {LINK}",
        "back": f"Back {STYLED}",
        "info": f"Info {COLOURED}",
        "fun_fact": f"Fact {LINK}",
        "explanation": f"Why {STYLED}",
        "mnemonic": f"Remember {LINK}",
    },
    {"front": f"Which? {LINK}", "back": f"This {COLOURED}", "choices": [f"That {STYLED}", f"Other {LINK}"]},
    {"id": "gap", "front": f"Gap {{{{c1::{LINK}}}}} and {STYLED}", "back": f"Extra {LINK}"},
]
LESSON = {"deck": "Maths", "cards": CARDS, "voice": "es-ES-ElviraNeural"}


def _checked(fields: list[str]) -> None:
    text = "\n".join(fields)
    assert "Front" in text and "Which?" in text and "Gap" in text  # every card's note
    assert not HTML_COMMAND.search(text), text
    assert r"\color{red}" in text  # the style of one colour, kept as Anki's colour


def test_formulas_sent_through_ankiconnect_run_nothing(anki, client):
    res = client.post("/api/anki/send", json=LESSON)
    assert res.status_code == 200, res.text
    assert len(anki.notes) == 3
    _checked([value for note in anki.notes.values() for value in note["fields"].values()])


def test_formulas_in_a_package_run_nothing(client, tmp_path):
    package = apkg.export(client, LESSON, tmp_path)
    _checked([field for note in package.notes for field in package.fields(note)])


def test_formulas_in_a_shared_package_run_nothing(client, tmp_path):
    made = extract_lesson(client)
    assert client.put(f"/api/lessons/{made['id']}", json={"deck": "Maths", "cards": CARDS}).status_code == 200
    res = client.post("/api/export/shared", json={"lessons": [made["id"]]})
    assert res.status_code == 200, res.text
    package = apkg.Apkg(res.content, tmp_path)
    _checked([field for note in package.notes for field in package.fields(note)])
