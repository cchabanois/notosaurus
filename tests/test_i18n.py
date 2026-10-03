"""The languages: every file has the same keys as English, every error code raised
anywhere in app/ has a message, the language is resolved, and the answers come in
the page's language."""

import re
from pathlib import Path

from conftest import extract_lesson

from app import ankiconnect, i18n, prompts


def _keys(d, prefix=""):
    keys = set()
    for k, v in d.items():
        if isinstance(v, dict):
            keys |= _keys(v, f"{prefix}{k}.")
        elif k != "defaultPrompts":
            keys.add(prefix + k)
    return keys


def test_all_languages_have_the_same_keys():
    reference = _keys(i18n.messages("en"))
    for lang in i18n.available():
        keys = _keys(i18n.messages(lang))
        assert keys == reference, f"{lang}: missing {sorted(reference - keys)}, extra {sorted(keys - reference)}"
        assert set(i18n.get(lang, "builtinPrompts")) == set(prompts.BUILTIN)


def test_all_error_codes_translated():
    """Every AppError code raised in the code has a message in English."""
    codes = set()
    for path in Path("app").glob("*.py"):
        codes |= set(
            re.findall(
                r'(?:AppError|ExtractionError|AnkiConnectError|PictureError)\(\s*"([a-z_]+\.[a-z_]+)"',
                path.read_text(encoding="utf-8"),
            )
        )
    codes |= set(ankiconnect.KNOWN_ERRORS.values())
    assert codes, "no error code found"
    missing = [c for c in sorted(codes) if i18n.get("en", f"errors.{c}") is None]
    assert missing == []


def test_language_choice(monkeypatch):
    assert i18n.resolve("fr-FR") == "fr"
    assert i18n.resolve("pt-BR") == "pt" and i18n.resolve("pt_PT") == "pt"
    assert i18n.resolve("ja-JP", "en-US") == "en"
    assert i18n.resolve("ja") is None
    monkeypatch.setenv("NOTOSAURUS_LANG", "fr_FR")  # Anki's language, set by the add-on
    assert i18n.anki_language() == "fr"
    monkeypatch.setenv("NOTOSAURUS_LANG", "ja_JP")
    assert i18n.anki_language() == "en"  # no Japanese file
    monkeypatch.delenv("NOTOSAURUS_LANG")
    assert i18n.anki_language() is None  # standalone: the browser decides


def test_lang_route(client, monkeypatch):
    assert client.get("/api/lang").json() == {
        "lang": None,
        "available": ["de", "en", "es", "fr", "it", "pt"],
        "names": {
            "de": "Deutsch",
            "en": "English",
            "es": "Español",
            "fr": "Français",
            "it": "Italiano",
            "pt": "Português (Brasil)",
        },
    }
    monkeypatch.setenv("NOTOSAURUS_LANG", "fr_FR")
    assert client.get("/api/lang").json()["lang"] == "fr"


def test_revision_summary_in_page_language(client):
    lesson = extract_lesson(client)
    body = {"deck": "D", "cards": [{"front": "a", "back": "b"}], "instruction": "remove the last card"}
    res = client.post(f"/api/lessons/{lesson['id']}/revise", json=body, headers={"X-Notosaurus-Lang": "fr"})
    assert res.json()["summary"] == "Dernière carte supprimée (démo)."
