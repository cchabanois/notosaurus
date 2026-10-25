"""The "✎ Notosaurus" link under every answer in Anki (app/note_types/common.py): the card
opened in Notosaurus, built on the card from the note's tag and key field."""

import json
import subprocess
from pathlib import Path

import pytest

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
    # Android: an https page of the documentation (AnkiDroid lets a card open those), which opens the app
    assert common.FIX_PAGE.startswith("https://") and f'"{common.FIX_PAGE}?"' in script
    assert "intent:" not in script  # blocked by AnkiDroid unless a setting allows it: never straight from the card
    assert "http://localhost:8000/?" in script  # the computer: the add-on's page
    assert 'display="none"' in script  # neither (AnkiWeb, AnkiMobile): hidden
    assert "notosaurus::" in script and "encodeURIComponent" in script  # the lesson's tag, the key encoded
    assert "{" not in script.replace("(function(){", "").replace("){", "").replace("}})();", "")  # no f-string left


def test_the_documentations_page_opens_the_app():
    page = (ROOT / "docs" / "public" / "fix" / "index.html").read_text(encoding="utf-8")
    assert "intent://fix?" in page and "package=app.notosaurus" in page  # Android: the app
    assert "browser_fallback_url" in page and "play.google.com" in page  # the app missing: Google Play
    assert "http://localhost:8000/?" in page  # opened on a computer all the same: the add-on's page
    assert "location.search" in page  # the lesson and the card, passed on as they came


def test_the_android_note_types_have_it_too():
    note_types = json.loads((ROOT / "static" / "note-types.json").read_text(encoding="utf-8"))["note_types"]
    assert all(all("✎ Notosaurus" in c["back"] for c in nt["cards"]) for nt in note_types.values())


@pytest.mark.parametrize(
    ("html", "body", "agent", "pycmd", "opens"),
    [
        ("", "card card1 win", "Mozilla/5.0", False, "http://localhost:8000/?"),  # Anki: its platform on <body>
        ("win", "card card1", "Mozilla/5.0", False, "http://localhost:8000/?"),  # …or on <html> (Anki 26.09)
        ("", "card card1", "Mozilla/5.0", True, "http://localhost:8000/?"),  # …or no class at all: its pycmd
        ("android", "card", "Mozilla/5.0 (Linux; Android 14)", False, common.FIX_PAGE + "?"),  # AnkiDroid
        ("", "card", "Mozilla/5.0 (iPhone)", False, None),  # AnkiMobile, AnkiWeb: hidden
    ],
)
def test_the_link_where_the_card_is_shown(html, body, agent, pycmd, opens):
    """The script run (node, a pretend page): the link opens the app or the computer's page,
    whichever Anki shows the card; hidden elsewhere."""
    page = f"""
    const link = {{ dataset: {{ tags: "notosaurus notosaurus::2026-10-24-lecon", key: "le chat" }},
                    parentNode: {{ style: {{}} }}, href: "#" }};
    globalThis.document = {{ documentElement: {{ className: {json.dumps(html)} }},
                             body: {{ className: {json.dumps(body)} }}, querySelectorAll: () => [link] }};
    globalThis.navigator = {{ userAgent: {json.dumps(agent)} }};
    {"globalThis.pycmd = () => {};" if pycmd else ""}
    {common.FIX_SCRIPT.removeprefix("<script>").removesuffix("</script>")}
    console.log(JSON.stringify({{ href: link.href, hidden: link.parentNode.style.display === "none" }}));
    """
    shown = json.loads(subprocess.run(["node", "-e", page], capture_output=True, text=True, check=True).stdout)
    if opens is None:
        assert shown["hidden"]
    else:
        assert not shown["hidden"] and shown["href"] == f"{opens}lesson=2026-10-24-lecon&key=le%20chat"
