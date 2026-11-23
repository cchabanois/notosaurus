"""The languages: every file has the same keys as English, every error code raised
anywhere in app/ has a message, the language is resolved, and the answers come in
the page's language."""

import re
from pathlib import Path

from conftest import extract_lesson

from app import ankiconnect, i18n, prompts
from notosaurus_core import relay_api


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
    for path in [*Path("app").glob("*.py"), *Path("core/notosaurus_core").glob("*.py")]:
        codes |= set(
            re.findall(
                r'(?:AppError|ExtractionError|AnkiConnectError|PictureError)\(\s*"([a-z_]+\.[a-z_]+)"',
                path.read_text(encoding="utf-8"),
            )
        )
    codes |= set(ankiconnect.KNOWN_ERRORS.values())
    codes |= set(relay_api.ERRORS) | {"relay.unreachable"}  # the relay's, and its client's when it can't reach it
    assert codes, "no error code found"
    missing = [c for c in sorted(codes) if i18n.get("en", f"errors.{c}") is None]
    assert missing == []


def _translated(messages: dict, key: str) -> bool:
    """`key` is a text of `messages`: one string, or one counted (its plural forms)."""
    found = messages
    for part in key.split("."):
        if not isinstance(found, dict) or part not in found:
            return False
        found = found[part]
    return isinstance(found, str) or (isinstance(found, dict) and "other" in found)


def test_every_key_the_pages_name_is_translated():
    """Every key the pages and their scripts name as it is ($t('…'), t("…"), a fallback
    after ||…) has its text in every language: a key missing shows as itself."""
    tops = "|".join(i18n.messages("en"))
    named = re.compile(rf"""(["'`])((?:{tops})(?:\.[A-Za-z0-9_-]+)+)\1""")
    files = [*Path("static").glob("*.html"), *Path("static").glob("*.js")]
    keys = {
        m[2]
        for path in files
        for m in named.finditer(path.read_text(encoding="utf-8"))
        if not re.search(r"\.(html|js|css|json)$", m[2])  # a file's name (admin.html), not a key
    }
    assert len(keys) > 500, "no key found"
    for lang in i18n.available():
        messages = i18n.messages(lang)
        assert sorted(k for k in keys if not _translated(messages, k)) == [], lang


def test_no_punctuation_glued_to_a_text_in_the_pages():
    """A text and what follows it are one key with a parameter ("Sub-deck: {name}"), each
    language with its own punctuation (French puts a space before ":"), never glued in code."""
    glued = re.compile(r"""\$?\bt\([^()]*\)\s*\+\s*["'`]\s*[:;!?«»]""")
    for path in [*Path("static").glob("*.html"), *Path("static").glob("*.js")]:
        assert glued.findall(path.read_text(encoding="utf-8")) == [], path


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


def test_help_links_go_to_pages_that_exist():
    """The add-on and the pages link to the documentation in the same language folders,
    and those folders are the documentation site's own locales."""
    import json
    import re
    from pathlib import Path

    addon = Path("anki_addon/__init__.py").read_text(encoding="utf-8")
    page = Path("static/i18n.js").read_text(encoding="utf-8")
    site = Path("docs/astro.config.mjs").read_text(encoding="utf-8")
    docs = re.search(r'DOCS = "([^"]+)"', addon)[1]
    assert f'const DOCS = "{docs}";' in page
    folders = set(re.findall(r"^\t{4}'?([\w-]+)'?: \{ label", site, re.M)) - {"root"}
    addon_langs = json.loads(re.search(r"DOCS_LANGS = (\{[^}]+\})", addon)[1])
    assert {f.strip("/") for f in addon_langs.values()} == folders  # every translation reached
    page_langs = dict(re.findall(r"(\w+): \"([\w-]*/?)\"", re.search(r"const DOCS_LANGS = \{([^}]+)\}", page)[1]))
    assert page_langs == {"en": "", "pt": "pt-br/"}  # the others: their own code, as the add-on
    assert all(addon_langs.get(code, f"{code}/") == folder for code, folder in page_langs.items() if code != "en")
    # Every page linked from the app exists in the documentation
    linked = set(re.findall(r"\$docs\('([\w-]*)'\)", Path("static/index.html").read_text(encoding="utf-8")))
    linked |= set(re.findall(r"\$docs\('([\w-]*)'\)", Path("static/admin.html").read_text(encoding="utf-8")))
    linked |= set(re.findall(r'docs_url\("([\w-]+)"\)', addon))
    pages = {p.stem for p in Path("docs/src/content/docs").glob("*.md*")}
    assert linked - {""} <= pages, linked - pages


def test_the_phone_qr_code_tells_of_the_android_app():
    """Anki → Tools → Notosaurus → Open on the phone, and the setup assistant's phone step:
    besides the phone's browser, the Android app shows the computer's page too (free), its
    settings' own words to get there."""
    setup = (i18n.I18N_DIR.parent / "setup.html").read_text(encoding="utf-8")
    assert "setup.phone.androidApp" in setup
    for lang in i18n.available():
        where = i18n.get(lang, "android.where")
        for key in ("addon.phoneSteps", "setup.phone.androidApp"):
            text = i18n.get(lang, key)
            assert "Android" in text and where["title"] in text and where["computer"] in text, (lang, key)


def _strings(d, prefix=""):
    """Every text of a language file, by its key."""
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out |= _strings(v, f"{prefix}{k}.")
        elif isinstance(v, str):
            out[prefix + k] = v
    return out


def test_portuguese_is_brazils():
    """The Portuguese is Brazil's (as the docs, pt-br): the share and transfer strings had come in
    Portugal's ("Partilhar", "ficheiro", "A exportar…") among Brazil's ("Compartilhar", "arquivo")."""
    portugal = re.compile(
        r"\b(partilh\w*|ficheiros?|telemóve(l|is)|palavras?-passe|ecrãs?|noutr[oa]s?|"
        r"utilizador(es)?|demasiado)\b|\b(está|estão|A) a \w+[aei]r\b",
        re.IGNORECASE,
    )
    found = {k: v for k, v in _strings(i18n.messages("pt")).items() if portugal.search(v)}
    assert not found


def test_italian_cards_are_carte():
    """Italian calls a lesson's cards "carte"; "scheda" is a child's record (the French "fiche")
    or the SD card: the share strings had called the cards "schede"."""
    french = _strings(i18n.messages("fr"))
    for key, text in _strings(i18n.messages("it")).items():
        if re.search(r"\bsched[ae]\b", text, re.IGNORECASE):
            assert re.search(r"\bfiches?\b|\bcarte SD\b", french[key]), (key, text)
