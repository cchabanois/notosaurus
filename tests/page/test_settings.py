"""The settings and the setup assistant: voices, the phone's address, lessons exported, the
service, features turned off."""

import re
import time

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from app import settings  # noqa: E402
from page.support import (  # noqa: E402
    CUT,
    FRONT_PROMPT,
    generate_free,
    new_password,
)


def test_features_turned_off_hidden(page):
    """Features turned off by the relay (relay_api.FEATURES): their buttons hidden."""
    shown = page.locator(".speed")
    pdf = page.locator("label.add-tile", has_text="PDF")

    def switches(disabled):
        body = {"notice": None, "disabled": disabled, "update": False, "store": "", "trial": None}
        page.route("**/api/switches", lambda route: route.fulfill(json=body))
        page.goto("/")

    switches([])
    sync_api.expect(shown).to_be_visible()
    sync_api.expect(pdf).to_be_visible()
    page.unroute("**/api/switches")
    switches(["ai.careful", "lesson.pdf"])
    sync_api.expect(shown).to_be_hidden()
    sync_api.expect(pdf).to_be_hidden()


def test_a_voice_chosen_per_language(page):
    """Settings → Voices: a language's voice chosen (its usual one otherwise), listened to."""
    voices = [
        {"voice": "es-ES-ElviraNeural", "locale": "es-ES", "gender": "Female"},
        {"voice": "es-ES-AlvaroNeural", "locale": "es-ES", "gender": "Male"},
        {"voice": "en-GB-SoniaNeural", "locale": "en-GB", "gender": "Female"},
    ]
    page.route("**/api/voices", lambda route: route.fulfill(json=voices))
    page.goto("/admin.html")
    new_password(page)
    page.get_by_role("button", name="Créer et continuer").click()
    choice = page.locator(".voice-choice")
    choice.locator("select.voice-add").select_option("es-ES")
    row = choice.locator(".voice-row")
    sync_api.expect(row).to_contain_text("espagnol")
    row.locator("select").select_option("es-ES-AlvaroNeural")
    sync_api.expect(row.locator("select option:checked")).to_have_text("Alvaro · homme")
    for _ in range(50):  # saved as it changes, after a short pause
        if settings.current().voices == {"es-ES": "es-ES-AlvaroNeural"}:
            break
        time.sleep(0.1)
    assert settings.current().voices == {"es-ES": "es-ES-AlvaroNeural"}


def test_the_phones_address_with_its_token_under_the_qr_code(page):
    """Typed instead of scanned (no scanner on the phone), the address under the QR code is
    the QR code's own, its token too: the address alone reaches Notosaurus, not letting the
    phone in."""
    page.goto("/admin.html")
    new_password(page)
    page.get_by_role("button", name="Créer et continuer").click()
    shown = page.locator(".phones .qr-address code")
    sync_api.expect(shown).to_have_text(re.compile(r"^http://.+/\?k=\S+$"))
    assert shown.inner_text() == page.locator(".phones p.hint a").get_attribute("href")  # the QR code's link


def test_a_voice_that_cant_be_heard_says_why(page):
    """Settings → Voices → ▶: a sound that can't be made (the relay's credits used up…) is
    said with its reason, not left silent."""
    voices = [{"voice": "es-ES-AlvaroNeural", "locale": "es-ES", "gender": "Male"}]
    page.route("**/api/voices", lambda route: route.fulfill(json=voices))
    failed = {"detail": {"code": "tts.failed", "params": {"detail": "no credits left"}}}
    page.route("**/api/tts?*", lambda route: route.fulfill(status=502, json=failed))
    page.goto("/admin.html")
    new_password(page)
    page.get_by_role("button", name="Créer et continuer").click()
    choice = page.locator(".voice-choice")
    choice.locator("select.voice-add").select_option("es-ES")
    choice.locator(".voice-row").get_by_role("button", name="Écouter").click()
    sync_api.expect(page.get_by_role("alert")).to_contain_text("no credits left")


def test_lessons_exported_then_imported_from_the_settings(page, tmp_path):
    """Settings → "Back up or move my lessons": the file downloaded, then taken in again (the
    lesson there already: kept), what was done said."""
    generate_free(page, FRONT_PROMPT)
    page.goto("/admin.html")
    new_password(page)
    page.get_by_role("button", name="Créer et continuer").click()
    with page.expect_download() as download:
        page.get_by_role("button", name="⬇️ Exporter mes leçons").click()
    saved = tmp_path / download.value.suggested_filename
    download.value.save_as(saved)
    assert saved.name.startswith("notosaurus-") and saved.suffix == ".zip"
    sync_api.expect(page.get_by_role("status")).to_contain_text("Leçons exportées")
    page.locator(".admin-transfer input[type=file]").set_input_files(str(saved))
    sync_api.expect(page.get_by_role("status")).to_contain_text("0 leçon(s) ajoutée(s)")
    sync_api.expect(page.get_by_role("status")).to_contain_text("1 déjà à jour")


def test_settings_show_what_the_service_needs(page):
    page.goto("/admin.html")
    new_password(page)
    page.get_by_role("button", name="Créer et continuer").click()
    address = page.get_by_placeholder("http://localhost:11434/v1")
    page.locator(".options .option", has_text="OpenRouter").click()
    sync_api.expect(page.get_by_text("Clé API OpenRouter")).to_be_visible()
    sync_api.expect(address).to_be_hidden()
    # Its recommended models are buttons, in order (the first is the default); the field
    # suggests them, then every model the service lists, as one types
    chips = page.locator(".chips").first.get_by_role("button")
    sync_api.expect(chips).to_have_count(5)
    sync_api.expect(chips.first).to_have_text(re.compile(r"^⭐ Gemini 3\.8 Flash · 1,3"))
    sync_api.expect(chips.first).to_have_class(re.compile(r"\bactive\b"))  # the default
    chips.nth(2).click()
    assert page.evaluate("Alpine.$data(document.querySelector('[x-data]')).form.model") == "anthropic/claude-sonnet-5.5"
    page.evaluate(
        "Alpine.$data(document.querySelector('[x-data]')).loadedModels = ['a/one', 'google/gemini-3.8-flash']"
    )
    assert page.locator("#model-suggestions option").count() == 6
    sync_api.expect(page.get_by_text("avec le coût d'une leçon")).to_be_visible()
    page.locator(".options .option", has_text="Autre service compatible OpenAI").click()
    sync_api.expect(address).to_be_visible()  # only this one has an address
    # It can't draw, and no other service has a key: said where the pictures are set
    sync_api.expect(page.locator(".picture-summary")).to_contain_text(
        "ne dessine pas, et aucun autre service n'a de clé"
    )
    # In the order things are set: the service, its access, then the model
    # (without the "?" linking some titles to the documentation)
    shown = page.locator("section.panel h2:visible").all_inner_texts()
    titles = [" ".join(t.split()).removesuffix(" ?") for t in shown]
    assert titles[:4] == ["1 Service d'IA", "2 Accès", "3 Modèle", "4 Images des cartes"]
    # The settings save themselves a moment later: done before the next test's data
    page.wait_for_function("Alpine.$data(document.querySelector('[x-data]')).saveState === 'saved'")


def test_admin_lessons_by_owner_then_subject(page, clock):
    page.goto("/admin.html")
    new_password(page)
    page.get_by_role("button", name="Créer et continuer").click()
    page.wait_for_function("Alpine.$data(document.querySelector('[x-data]')).saveState === 'saved'")
    admin = {"X-Admin-Password": "secret-pw"}
    for deck, owner in (
        ("Anglais::Leçon 1", "Léa"),
        ("Maths::Fractions", "Paul"),
        ("Anglais::Leçon 2", "Léa"),
        ("SVT", ""),
    ):
        made = page.request.post("/api/extract", multipart={"prompt": FRONT_PROMPT}).json()
        page.request.put(f"/api/lessons/{made['id']}", data={"deck": deck, "cards": made["cards"]})
        page.request.put(f"/api/admin/lessons/{made['id']}", headers=admin, data={"owner": owner})
    page.reload()
    owners = page.locator(".owner-group > summary strong")
    sync_api.expect(owners).to_have_text(["👤 Léa", "👤 Paul", "Personne (commune à tous)"])  # nobody's last
    lea = page.locator(".owner-group").first
    sync_api.expect(lea.locator("> summary small")).to_contain_text("2 leçons")
    sync_api.expect(page.locator(".admin-lesson-head:visible")).to_have_count(0)  # folded: the owners alone
    lea.locator("> summary").click()
    sync_api.expect(page.locator(".admin-lesson-head:visible")).to_have_count(2)
    sync_api.expect(lea.locator(".subject-group h3")).to_have_text(["Anglais"])
    sync_api.expect(lea.locator(".admin-lesson-head strong")).to_have_text(["Leçon 2", "Leçon 1"])
    sync_api.expect(page.locator(".owner-group").last.locator(".admin-lesson-head strong")).to_have_text(["SVT"])

    dialogs = []  # deleted after a question in the page's own sheet, not the browser's confirm()
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    page.locator(".owner-group").last.locator("> summary").click()
    page.locator(".owner-group").last.get_by_role("button", name="Supprimer la leçon").click()
    page.get_by_role("alertdialog", name=re.compile("« SVT »")).get_by_role("button", name="Supprimer").click()
    sync_api.expect(owners).to_have_text(["👤 Léa", "👤 Paul"])
    assert not dialogs


def test_the_setup_assistant(page, monkeypatch):
    """No AI yet: the page offers the assistant; the key checked, the phone seen pairing, ready."""
    from app.routes import admin, devices

    monkeypatch.setenv("NOTOSAURUS_LLM", "gemini")  # the default, without its key
    monkeypatch.setattr(devices, "last_paired", None)

    async def check(s):  # the key's test, without calling Google
        assert s.gemini_api_key == "AIza-test"
        # A free key: no quota for the latest model, the fallback answered
        return {"vision": True, "json": True, "answer": "red", "model": "gemini-3.5-flash", "quota": "gemini-3.8-flash"}

    monkeypatch.setattr(admin, "check", check)
    page.goto("/")
    page.get_by_role("link", name="Configurer Notosaurus").click()
    new_password(page)
    page.get_by_role("button", name="Créer et continuer").click()

    sync_api.expect(page.get_by_role("heading", name="Quelle IA lit les leçons ?")).to_be_visible()
    sync_api.expect(page.get_by_text("Obtenir une clé Gemini (2 minutes)")).to_be_visible()
    sync_api.expect(page.get_by_role("link", name="aistudio.google.com/apikey")).to_have_attribute(
        "href", "https://aistudio.google.com/apikey"
    )
    next_ = page.get_by_role("button", name="Suivant →")
    sync_api.expect(next_).to_be_disabled()  # not before the key works
    assert page.evaluate(CUT) == []
    page.get_by_label("Clé API Gemini").fill("AIza-test")
    page.get_by_role("button", name="🔌 Vérifier la clé").click()  # saves the key, then tests it
    sync_api.expect(page.get_by_text("✓ Votre clé fonctionne avec gemini-3.5-flash")).to_contain_text(
        "gemini-3.8-flash n'est pas inclus"
    )
    next_.click()

    sync_api.expect(page.get_by_role("heading", name="Ouvrir Notosaurus sur le téléphone")).to_be_visible()
    sync_api.expect(page.get_by_text("En attente du téléphone…")).to_be_visible()
    # The phone scans the QR code (on the Wi-Fi: not this computer)
    page.wait_for_function("Alpine.$data(document.querySelector('[x-data]')).pollTimer")  # the QR code shown
    page.request.get(f"/?k={settings.device_token()}", headers={"X-Forwarded-For": "192.168.1.20"})
    sync_api.expect(page.get_by_text("✓ Le téléphone est connecté.")).to_be_visible()
    page.get_by_role("button", name="Suivant →").click()

    sync_api.expect(page.get_by_role("heading", name="Notosaurus est prêt !")).to_be_visible()
    page.get_by_role("link", name="Ouvrir Notosaurus").click()
    sync_api.expect(page.get_by_role("heading", name="Photos de la leçon")).to_be_visible()
    sync_api.expect(page.locator(".setup-banner")).to_be_hidden()  # configured now
