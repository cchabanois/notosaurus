"""The pages in a real browser (Playwright, headless Chromium): what the API tests
can't see — the page saving as it goes, generating again and undoing, deleting a
lesson, the cloze preview, the settings' order.

Skipped unless Playwright is installed: `pip install -r requirements-page.txt`, then
`python -m playwright install chromium` (or NOTOSAURUS_TEST_CHROMIUM=/usr/bin/chromium
to use the system's). The pages load Alpine.js and KaTeX from a CDN: network needed.
"""

import base64
import io
import os
import re
import socket
import threading
import time

import pytest
from conftest import fake_synthesize
from helpers import plain_image
from PIL import Image as PILImage

sync_api = pytest.importorskip("playwright.sync_api")
import uvicorn  # noqa: E402

from app import settings, storage  # noqa: E402
from app.main import app  # noqa: E402
from notosaurus_core import tts  # noqa: E402

FRONT_PROMPT = "Une carte par mot de la famille"  # demo mode: Spanish family words
CLOZE_PROMPT = "Texte à trous sur la Révolution"  # demo mode: sentences with gaps
SAVED = re.compile(r"\bsaved\b")  # the save pill once the server has the lesson


@pytest.fixture(scope="session")
def server():
    """Notosaurus on a free port, in this process: the tests' settings apply to it."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    runner = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=runner.run, daemon=True)
    thread.start()
    for _ in range(100):
        if runner.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    runner.should_exit = True
    thread.join(5)


@pytest.fixture(scope="session")
def browser():
    with sync_api.sync_playwright() as p:
        executable = os.environ.get("NOTOSAURUS_TEST_CHROMIUM")
        try:
            browser = p.chromium.launch(executable_path=executable) if executable else p.chromium.launch()
        except sync_api.Error as e:  # no browser here: skipped, not 60 errors
            if executable:  # one asked for (CI's Chrome) that can't start: an error, not all skipped
                raise
            pytest.skip(f"no Chromium (python -m playwright install chromium, or NOTOSAURUS_TEST_CHROMIUM): {e}")
        yield browser
        browser.close()


@pytest.fixture
def page(browser, server, tmp_path, monkeypatch):
    """A phone-sized page in French, on fresh data and the demo AI (no key, no cost)."""
    monkeypatch.setenv("NOTOSAURUS_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("NOTOSAURUS_LLM", "fake")
    monkeypatch.setenv("NOTOSAURUS_ANKICONNECT_URL", "http://127.0.0.1:1")  # Anki closed
    for key in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(key, raising=False)  # the same on every computer: no key (.env)
    monkeypatch.setattr(tts, "_synthesize", fake_synthesize)
    context = browser.new_context(locale="fr-FR", viewport={"width": 390, "height": 844}, base_url=server)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    yield page
    # The page's requests done first (a lesson still being saved, its pictures): else one
    # lands after NOTOSAURUS_DATA is the next test's, a lesson made there (a flaky count)
    page.wait_for_load_state("networkidle")
    # A route handler still at work (route.fetch) when the context closes fails the
    # next test's new_context: "Response has been disposed"
    page.unroute_all(behavior="ignoreErrors")
    context.close()
    assert not errors, errors


def new_password(page) -> None:
    """The settings' password typed twice, once the page runs (its title written by it): a
    field filled before, on a slow machine, was emptied as the page started, the form never sent."""
    sync_api.expect(page.get_by_role("heading", name=re.compile("🔐"))).to_be_visible()
    fields = page.locator("input[autocomplete=new-password]")
    fields.first.fill("secret-pw")
    fields.nth(1).fill("secret-pw")


def lessons(page) -> list[dict]:
    return page.request.get("/api/lessons").json()


def lesson(page, id: str) -> dict:
    return page.request.get(f"/api/lessons/{id}").json()


def generate_free(page, prompt: str) -> None:
    """A lesson from a prompt written for this time (no photo)."""
    page.goto("/")
    page.get_by_role("radio", name="✏️ Libre").click()
    page.locator("textarea[x-ref=promptText]").fill(prompt)
    page.get_by_role("button", name="✨ Générer à partir de la consigne seule").click()
    page.locator(".flash").first.wait_for()


def test_the_main_button_takes_the_first_photo(page):
    """No photo yet: "📷 Photographiez la leçon" is not a dead button, it opens the camera."""
    page.goto("/")
    start = page.get_by_role("button", name="📷 Photographiez la leçon")
    sync_api.expect(start).to_be_enabled()
    with page.expect_file_chooser() as chooser:
        start.click()
    assert chooser.value.element.get_attribute("capture") == "environment"


def test_from_the_prompt_alone_only_when_it_can(page):
    """No photo: "from the prompt alone" only for a prompt that can do without one; a
    built-in one as it is reads a lesson ("Automatique"), so not until something is
    written in it. The hint saying how stays."""
    page.goto("/")
    alone = page.get_by_role("button", name="✨ Générer à partir de la consigne seule")
    page.get_by_role("radio", name=re.compile("Automatique")).first.click()
    sync_api.expect(alone).to_be_hidden()
    sync_api.expect(page.locator(".from-prompt .hint")).to_be_visible()
    text = page.locator("textarea[x-ref=promptText]")
    text.fill(text.input_value() + "\nLes animaux de la ferme")
    sync_api.expect(alone).to_be_visible()
    page.get_by_role("radio", name="✏️ Libre").click()
    text.fill("")
    sync_api.expect(alone).to_be_hidden()
    text.fill("chat, chien, vache")
    sync_api.expect(alone).to_be_visible()


def test_the_free_trial_started_said_after_the_first_lesson(page):
    """The Android app: the first lesson starts the free trial; the page asks after it and
    says so in a toast (seen wherever the page is scrolled), once."""
    told = {"trial": None}

    def switches(route):
        trial, told["trial"] = told["trial"], None  # told once
        body = {"notice": None, "disabled": [], "update": False, "store": "https://play.google.com/x", "trial": trial}
        route.fulfill(json=body)

    page.route("**/api/switches", switches)
    page.goto("/")
    told["trial"] = {
        "plan": "free_trial",
        "credits_left": 300,
        "daily_left": 150,
        "ends_at": "2026-11-07T10:00:00+00:00",
    }
    page.get_by_role("radio", name="✏️ Libre").click()
    page.locator("textarea[x-ref=promptText]").fill(FRONT_PROMPT)
    page.get_by_role("button", name="✨ Générer à partir de la consigne seule").click()
    sync_api.expect(page.locator(".toast.ok")).to_contain_text("Essai gratuit : 300 crédits jusqu'au 7 novembre")


def test_touch_targets_and_an_off_button_readable(page):
    """Every small control a finger hits is 44 px at least (its invisible layer), its look
    unchanged; a main button off reads plainly (not a paler teal, 2.2:1 before)."""
    generate_free(page, FRONT_PROMPT)
    sizes = page.evaluate(
        """[...document.querySelectorAll('.flash-actions .icon-btn, .appbar .chip-btn.icon-only')]
           .filter((b) => b.offsetParent)
           .map((b) => {
             const s = getComputedStyle(b, '::after');
             return [b.getBoundingClientRect().width, parseFloat(s.width), parseFloat(s.height)];
           })"""
    )
    assert sizes and all(w < 44 for w, _, _ in sizes)  # small to look at…
    assert all(aw >= 44 and ah >= 44 for _, aw, ah in sizes), sizes  # …44 px to touch
    for scheme in ("light", "dark"):
        page.emulate_media(color_scheme=scheme)
        assert off_contrast(page) >= 4.5, scheme


def off_contrast(page) -> float:
    """A main button off: its text's contrast with its background (WCAG's ratio)."""
    return page.evaluate(
        """(() => {
          const b = document.createElement('button');
          b.className = 'btn primary'; b.disabled = true; b.textContent = 'x';
          document.body.append(b); const s = getComputedStyle(b);
          const linear = (v) => (v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
          const rgb = (c) => c.match(/\\d+/g).slice(0, 3).map((v) => linear(Number(v) / 255));
          const lum = (c) => { const [r, g, bl] = rgb(c); return .2126 * r + .7152 * g + .0722 * bl; };
          const [a, z] = [lum(s.color), lum(s.backgroundColor)].sort((x, y) => y - x);
          b.remove(); return (a + .05) / (z + .05);
        })()"""
    )


def test_generate_then_edit_saves_by_itself(page):
    generate_free(page, FRONT_PROMPT)
    assert page.locator(".flash").count() == 6
    (summary,) = lessons(page)
    assert lesson(page, summary["id"])["prompt"] == FRONT_PROMPT  # kept with the lesson…
    assert not [p for p in page.request.get("/api/prompts").json() if not p["builtin"]]  # …not saved as a prompt

    page.locator(".flash textarea.back").first.fill("la mamá")
    sync_api.expect(page.locator(".save-pill")).to_have_class(SAVED)
    assert lesson(page, summary["id"])["cards"][0]["back"] == "la mamá"


def test_long_back_and_info_seen_whole(page):
    """A long answer or note grows its field, as the front: nothing cut on a phone."""
    page.set_viewport_size({"width": 360, "height": 780})
    generate_free(page, FRONT_PROMPT)
    card = page.locator(".flash").first
    long = "une réponse longue, avec une précision qui ne tient pas sur une seule ligne d'un téléphone"
    for field in ("textarea.back", "textarea.info"):
        box = card.locator(field)
        one_line = box.bounding_box()["height"]
        box.fill(long)
        assert box.bounding_box()["height"] > 1.5 * one_line, field  # several lines
        assert box.evaluate("el => el.scrollHeight <= el.clientHeight + 1"), field  # all of it shown
        box.press("Enter")  # one line of text in Anki: Enter adds no line break
        assert box.input_value() == long


def test_generate_again_in_place_then_undo(page):
    generate_free(page, FRONT_PROMPT)
    (first,) = lessons(page)
    page.locator("textarea[x-ref=promptText]").fill(CLOZE_PROMPT)
    page.get_by_role("button", name="✨ Régénérer").click()
    sync_api.expect(page.locator(".math-preview .gap").first).to_be_visible()  # the gaps, numbered

    (again,) = lessons(page)  # the same lesson, its cards replaced
    assert again["id"] == first["id"]
    assert all("{{c" in c["front"] for c in lesson(page, first["id"])["cards"])
    assert page.locator(".math-preview .gap sup").first.inner_text() == "1"

    page.get_by_role("button", name="↩ Annuler").click()
    sync_api.expect(page.locator(".save-pill")).to_have_class(SAVED)
    undone = lesson(page, first["id"])
    assert undone["cards"][0]["front"] == "la mère" and undone["prompt"] == FRONT_PROMPT


def test_figures_drawn_after_the_cards(page):
    generate_free(page, "Le triangle rectangle (géométrie)")  # demo mode: two figures to draw
    figure = page.locator(".card-picture.figure img").first
    sync_api.expect(figure).to_be_visible()
    assert page.evaluate("img => img.naturalWidth", figure.element_handle()) == 400  # the SVG, at its size
    (summary,) = lessons(page)
    assert all(c["picture"].endswith(".svg") for c in lesson(page, summary["id"])["cards"])
    # The tangent's figure belongs to its answer: shown under it, as in Anki
    tangent = page.locator(".flash", has_text="tangente")
    sync_api.expect(tangent.locator(".card-picture.on-back img")).to_be_visible()
    sync_api.expect(tangent.locator(".card-picture:not(.on-back)")).to_be_hidden()


def test_a_figure_being_drawn_says_how_long(page):
    """A figure takes the model's thinking: its place says so, with roughly how long, a bar
    filling meanwhile; the cards are there already."""
    held = []
    page.route("**/api/lessons/*/pictures", lambda route: held.append(route))
    generate_free(page, "Le triangle rectangle (géométrie)")
    waiting = page.locator(".card-picture.figure .drawing").first
    sync_api.expect(waiting).to_contain_text("Tracé de la figure")
    sync_api.expect(waiting).to_contain_text("environ 10 s")
    sync_api.expect(waiting.locator(".progress")).to_be_visible()
    sync_api.expect(page.locator(".flash textarea.back").first).to_be_editable()  # the cards usable meanwhile
    for route in held:
        route.continue_()
    sync_api.expect(page.locator(".card-picture.figure img").first).to_be_visible()


def test_delete_the_open_lesson(page):
    generate_free(page, FRONT_PROMPT)
    page.locator(".review-head").get_by_role("button", name="Supprimer la leçon").click()
    sheet = page.get_by_role("complementary", name="Supprimer la leçon")
    sync_api.expect(sheet).to_contain_text("Anki n'est pas ouvert")  # Anki closed: the lesson alone
    sheet.get_by_role("button", name="Supprimer la leçon").click()
    sync_api.expect(page.locator(".flash")).to_have_count(0)
    assert lessons(page) == []


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


def png(color: str) -> bytes:
    return plain_image(600, 800, color, "PNG")


def test_photos_and_pictures_seen_in_full(page):
    page.goto("/")
    page.locator('input[type=file][accept="image/*"][multiple]').set_input_files(
        [{"name": f"page-{n}.png", "mimeType": "image/png", "buffer": png(c)} for n, c in ((1, "red"), (2, "blue"))]
    )
    page.locator(".thumb img").first.click()
    viewer = page.locator(".viewer")
    sync_api.expect(viewer).to_be_visible()
    sync_api.expect(viewer.locator(".viewer-count")).to_have_text("1 / 2")
    viewer.get_by_role("button", name="Photo suivante").click()
    sync_api.expect(viewer.locator(".viewer-count")).to_have_text("2 / 2")
    viewer.locator(".viewer-frame img").click()  # its real size, to pan
    sync_api.expect(viewer.locator(".viewer-frame")).to_have_class(re.compile(r"\bzoomed\b"))
    page.keyboard.press("Escape")
    sync_api.expect(viewer).to_be_hidden()

    # A card's figure too, alone: no arrows
    generate_free(page, "Le triangle rectangle (géométrie)")
    page.locator(".card-picture img").first.click()
    sync_api.expect(viewer).to_be_visible()
    sync_api.expect(viewer.locator(".viewer-nav")).to_have_count(0)


def test_fun_facts_as_the_settings_say(page):
    """No switch under the prompt: the fun facts come as the settings say (on at first)."""
    page.goto("/")
    sync_api.expect(page.locator(".switch.fun-facts")).to_have_count(0)
    generate_free(page, FRONT_PROMPT)
    fact = page.locator(".flash .fun-fact textarea").first
    sync_api.expect(fact).to_be_visible()
    assert fact.input_value().startswith("Le savais-tu")
    sync_api.expect(page.locator(".flash .fun-fact:visible")).to_have_count(1)  # the others have none
    # A long one is seen whole, on several lines
    one_line = fact.bounding_box()["height"]
    fact.fill("Le savais-tu ? " + "Ce mot vient du latin et se retrouve dans beaucoup de langues. " * 3)
    assert fact.bounding_box()["height"] > 1.5 * one_line
    assert fact.evaluate("el => el.scrollHeight <= el.clientHeight + 1")


def test_quick_by_default_then_again_carefully(page):
    """Quick by default (the AI thinks little); "Make again, carefully" redoes the lesson
    in its place; "Careful" chosen is kept on the device."""
    sent = []
    page.on("request", lambda r: sent.append((r.url, r.post_data or "")) if r.method == "POST" else None)
    page.goto("/")
    quick = page.get_by_role("radio", name="⚡ Rapide")
    sync_api.expect(quick).to_have_attribute("aria-checked", "true")
    generate_free(page, FRONT_PROMPT)
    body = next(b for u, b in sent if u.endswith("/api/extract"))
    assert 'name="quick"' in body
    again = page.get_by_role("button", name="🎯 Refaire en mode soigné")
    sync_api.expect(again).to_be_visible()

    sent.clear()
    again.click()
    sync_api.expect(again).to_be_hidden()  # made carefully this time
    body = next(b for u, b in sent if "/regenerate" in u)
    assert 'name="quick"' not in body
    assert len(lessons(page)) == 1  # in its place
    sync_api.expect(quick).to_have_attribute("aria-checked", "true")  # the choice above stays

    page.get_by_role("radio", name="🎯 Soigné").click()
    page.reload()  # kept on the device
    sync_api.expect(page.get_by_role("radio", name="🎯 Soigné")).to_have_attribute("aria-checked", "true")


def test_cancel_while_the_cards_are_being_made(page):
    """ "Cancel" in the waiting card: the server is asked to stop this generation, the
    page comes back as it was, no error, no lesson."""
    held, cancelled = [], []

    def cancel_asked(route):
        cancelled.append(route.request.url)
        route.fulfill(json={"cancelled": True})

    page.route("**/api/extract", lambda route: held.append(route))  # the AI still writing
    page.route("**/api/generations/*/cancel", cancel_asked)
    page.goto("/")
    page.get_by_role("radio", name="✏️ Libre").click()
    page.locator("textarea[x-ref=promptText]").fill(FRONT_PROMPT)
    page.get_by_role("button", name="✨ Générer à partir de la consigne seule").click()
    cancel = page.locator(".loading-card .btn")
    sync_api.expect(cancel).to_have_text("Annuler")
    cancel.click()
    sync_api.expect(cancel).to_have_text("Annulation…")
    (route,) = held
    job = re.search(r'name="job"\r\n\r\n(\w+)', route.request.post_data).group(1)
    assert cancelled == [f"{page.url.rstrip('/')}/api/generations/{job}/cancel"]
    lines = '{"card": {"front": "a", "back": "b"}}\n{"cancelled": true}\n'
    route.fulfill(content_type="application/x-ndjson", body=lines)
    sync_api.expect(page.locator(".loading-card")).to_be_hidden()
    sync_api.expect(page.locator(".flash")).to_have_count(0)
    sync_api.expect(page.locator(".error")).to_be_hidden()
    assert page.locator("textarea[x-ref=promptText]").input_value() == FRONT_PROMPT


def test_multiple_choice_wrong_answers_edited(page):
    generate_free(page, "QCM sur la Révolution")
    first = page.locator(".flash").first
    sync_api.expect(first.locator(".choice textarea")).to_have_count(3)
    assert first.locator("textarea.back").get_attribute("placeholder") == "Bonne réponse"
    first.get_by_role("button", name="+ mauvaise réponse").click()
    first.locator(".choice textarea").nth(3).fill("1830")
    first.get_by_role("button", name="Retirer cette réponse").first.click()  # 1715 goes
    sync_api.expect(page.locator(".save-pill")).to_have_class(SAVED)
    (summary,) = lessons(page)
    assert lesson(page, summary["id"])["cards"][0]["choices"] == ["1799", "1804", "1830"]


@pytest.fixture
def clock(monkeypatch):
    """A second more at each save: the lessons made in a test are in order (saved to
    the second, they would all be at the same time)."""
    ticks = iter(range(3600))
    monkeypatch.setattr(storage, "now", lambda: "2026-10-03T10:{:02d}:{:02d}".format(*divmod(next(ticks), 60)))


def test_lessons_grouped_by_subject(page, clock):
    page.goto("/")
    for deck in ("Espagnol::a", "Anglais::Leçon 1", "anglais::Leçon 2::Phrases"):  # the most recent last
        made = page.request.post("/api/extract", multipart={"prompt": FRONT_PROMPT}).json()
        page.request.put(f"/api/lessons/{made['id']}", data={"deck": deck, "cards": made["cards"]})
    page.reload()
    page.get_by_role("button", name="Leçons").click()
    groups = page.locator(".lesson-group")
    sync_api.expect(groups).to_have_count(2)
    titles = [" ".join(h.split()).casefold() for h in groups.locator("h3").all_inner_texts()]
    assert titles == ["anglais 2", "espagnol 1"]  # "anglais", "Anglais": the same deck for Anki
    assert groups.first.locator(".lesson strong").all_inner_texts() == ["Leçon 2 › Phrases", "Leçon 1"]


def test_the_page_stays_still_under_an_open_sheet(page, clock):
    """Scrolling the lessons with a finger (here the wheel), even past their end, never
    moves the lesson behind; the page scrolls again once the sheet is closed."""
    page.goto("/")
    for n in range(12):
        made = page.request.post("/api/extract", multipart={"prompt": FRONT_PROMPT}).json()
        page.request.put(f"/api/lessons/{made['id']}", data={"deck": f"Maths::Leçon {n}", "cards": made["cards"]})
    generate_free(page, FRONT_PROMPT)  # a lesson open behind: a page long enough to scroll
    page.get_by_role("button", name="Leçons").click()
    sync_api.expect(page.locator("html")).to_have_class(re.compile("sheet-open"))
    page.evaluate("scrollTo(0, 400)")  # the lesson behind, scrolled down a little
    before = page.evaluate("scrollY")
    listed = page.locator(".lesson-list")
    sync_api.expect(listed.locator(".lesson").first).to_be_visible()
    box = listed.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    for _ in range(10):
        page.mouse.wheel(0, 800)
    page.wait_for_timeout(300)
    assert page.evaluate("scrollY") == before

    page.keyboard.press("Escape")
    sync_api.expect(page.locator("html")).not_to_have_class(re.compile("sheet-open"))
    page.mouse.wheel(0, 400)
    page.wait_for_function(f"scrollY !== {before}")


def test_many_lessons_recent_folded_and_searched(page, clock):
    page.goto("/")
    decks = [f"Espagnol::Leçon {n}" for n in range(1, 7)] + ["Maths::Fractions", "Maths::Pythagore", "Anglais::Unit 1"]
    for deck in [*decks, "Anglais::Unit 2"]:  # 10 lessons, the most recent last
        made = page.request.post("/api/extract", multipart={"prompt": FRONT_PROMPT}).json()
        page.request.put(f"/api/lessons/{made['id']}", data={"deck": deck, "cards": made["cards"]})
    page.reload()
    page.get_by_role("button", name="Leçons").click()
    sheet = page.locator(".lesson-list")
    heads = sheet.locator(".group-head")
    sync_api.expect(heads).to_have_count(4)  # the recent ones, then the subjects
    sync_api.expect(heads.first.locator(".fold")).to_be_hidden()  # "Recent" doesn't fold (once Alpine has said so)
    assert [" ".join(h.split()).casefold() for h in heads.all_inner_texts()] == [
        "récentes",
        "▸ anglais 2",
        "▸ maths 2",
        "▸ espagnol 6",
    ]
    recent = sheet.locator(".lesson-group").first.locator(".lesson strong")
    assert recent.all_inner_texts() == ["Anglais › Unit 2", "Anglais › Unit 1", "Maths › Pythagore"]
    sync_api.expect(sheet.locator(".lesson:visible")).to_have_count(3)  # the subjects folded

    heads.nth(3).click()  # Espagnol, opened: still open next time
    sync_api.expect(sheet.locator(".lesson:visible")).to_have_count(9)
    page.reload()
    page.get_by_role("button", name="Leçons").click()
    sync_api.expect(sheet.locator(".lesson:visible")).to_have_count(9)

    page.get_by_placeholder("🔍 Chercher une leçon…").fill("lecon 4")  # no accent, no case
    sync_api.expect(sheet.locator(".lesson:visible strong")).to_have_text(["Espagnol › Leçon 4"])
    page.get_by_placeholder("🔍 Chercher une leçon…").fill("chimie")
    sync_api.expect(page.get_by_text("Aucune leçon ne correspond.")).to_be_visible()


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


@pytest.mark.parametrize(
    ("locale", "date"), [("en-GB", "3 Oct, 10:00"), ("en-US", "Oct 3, 10:00 AM"), ("fr-CA", "10 h 00")]
)
def test_dates_in_the_browser_variety(page, clock, browser, server, locale, date):
    """One English text, but the dates as the browser writes them."""
    page.request.post("/api/extract", multipart={"prompt": FRONT_PROMPT})  # saved at 10:00:00
    context = browser.new_context(locale=locale, viewport={"width": 390, "height": 844}, base_url=server)
    try:
        other = context.new_page()
        other.goto("/")
        other.locator(".chip-btn").first.click()
        sync_api.expect(other.locator(".lesson small").first).to_contain_text(date)
    finally:
        context.close()


# What doesn't fit on a narrow phone: the page wider than the screen, a button or
# title cut, a placeholder longer than its field
CUT = """() => {
  const width = document.documentElement.clientWidth, found = [];
  if (document.documentElement.scrollWidth > width) found.push(`page: ${document.documentElement.scrollWidth}px`);
  // An icon's button: no text to cut, its touch layer (::after, 44 px) wider than it on purpose
  const icon = [".icon-btn", ".chip-btn.icon-only", ".thumb-remove", ".thumb-rotate", ".thumb-hide",
    ".toast > button", ".flash .pick"].join(", ");
  for (const el of document.querySelectorAll("button, .chip, .badge, summary, h2, h3, label")) {
    if (el.matches(icon)) continue;
    if (el.getBoundingClientRect().width && el.scrollWidth > el.clientWidth + 2) found.push(el.innerText.trim());
  }
  const canvas = document.createElement("canvas").getContext("2d");
  for (const el of document.querySelectorAll("input[placeholder]")) {
    if (!el.getBoundingClientRect().width || el.value) continue;
    const style = getComputedStyle(el);
    canvas.font = style.font;
    const room = el.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
    if (canvas.measureText(el.placeholder).width > room + 1) found.push(el.placeholder);
  }
  return [...new Set(found)];
}"""


@pytest.mark.parametrize("lang", ["en", "fr", "es", "de", "it", "pt"])
def test_every_language_fits_a_narrow_phone(page, browser, server, lang):
    context = browser.new_context(locale="fr-FR", viewport={"width": 360, "height": 780}, base_url=server)
    context.add_init_script(f"localStorage.setItem('notosaurus.lang', '{lang}')")
    try:
        other = context.new_page()
        other.goto("/")
        other.wait_for_function("document.documentElement.classList.contains('i18n-ready')")
        other.locator(".chip").first.click()  # the free prompt
        other.locator("textarea[x-ref=promptText]").fill("QCM sur la Révolution")
        other.locator(".from-prompt button").click()
        other.locator(".flash").first.wait_for()
        assert other.evaluate(CUT) == []
        other.goto("/admin.html")
        new_password(other)
        other.locator("button.btn.primary.wide").first.click()  # create the password
        other.locator("section.panel h2 .step").first.wait_for()  # the settings, unlocked (About is always there)
        assert other.evaluate(CUT) == []
        other.wait_for_function("Alpine.$data(document.querySelector('[x-data]')).saveState !== 'pending'")
        # The setup assistant, with its longest step: Gemini's key, explained
        other.request.put("/api/admin/settings", headers={"X-Admin-Password": "secret-pw"}, data={"llm": "gemini"})
        other.goto("/setup.html")
        other.locator(".setup-guide").wait_for()
        assert other.evaluate(CUT) == []
    finally:
        context.close()


def test_prompts_follow_the_language(page):
    page.goto("/")
    text = page.locator("textarea[x-ref=promptText]")
    sync_api.expect(text).to_have_value(re.compile(r"^Regarde la leçon"))  # "Automatique", in French
    page.locator(".lang-select select").select_option("de")
    sync_api.expect(text).to_have_value(re.compile(r"^Sieh dir die Lektion an"))  # the same prompt, in German
    sync_api.expect(page.get_by_role("radio", name="⭐ Sprache: Vokabeln")).to_be_visible()
    text.fill("Meine eigene Anweisung")  # changed for this time: kept
    page.locator(".lang-select select").select_option("es")
    sync_api.expect(page.get_by_role("radio", name="⭐ Idioma: vocabulario")).to_be_visible()
    sync_api.expect(text).to_have_value("Meine eigene Anweisung")
    page.get_by_role("radio", name="✏️ Libre").click()  # the free prompt stays free
    text.fill("Lo mío")
    page.locator(".lang-select select").select_option("it")
    sync_api.expect(page.get_by_role("radio", name="✏️ Libere")).to_be_checked()
    sync_api.expect(text).to_have_value("Lo mío")


def test_deleting_a_prompt_is_asked_in_the_app(page):
    """The app's own sheet, not the browser's confirm() (which shows the page's address)."""
    page.request.post("/api/prompts", data={"name": "Definitions", "text": "Les définitions de la leçon"})
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    page.goto("/")
    page.locator(".chip.more").click()
    trash = page.get_by_role("button", name="Supprimer la consigne « Definitions »")
    trash.click()
    asked = page.get_by_role("alertdialog", name="Supprimer la consigne « Definitions » ?")
    asked.get_by_role("button", name="Annuler").click()
    sync_api.expect(asked).to_be_hidden()
    assert [p["name"] for p in page.request.get("/api/prompts").json() if not p["builtin"]] == ["Definitions"]

    trash.click()
    asked.get_by_role("button", name="Supprimer").click()
    sync_api.expect(trash).to_have_count(0)
    assert not [p for p in page.request.get("/api/prompts").json() if not p["builtin"]]
    assert not dialogs


def pdf(pages: int) -> bytes:
    """A PDF of `pages` A4 pages, each of its own colour."""
    import io

    from PIL import Image

    images = [Image.new("RGB", (595, 842), (40 * n % 255, 90, 160)) for n in range(pages)]
    out = io.BytesIO()
    images[0].save(out, "PDF", save_all=True, append_images=images[1:])
    return out.getvalue()


def test_pdf_pages_become_photos(page):
    page.goto("/")
    pdf_input = page.locator("input[type=file][accept*=pdf]")
    pdf_input.set_input_files({"name": "cours.pdf", "mimeType": "application/pdf", "buffer": pdf(3)})
    sync_api.expect(page.locator(".thumb img")).to_have_count(3)  # every page, no question
    assert page.evaluate("img => img.naturalHeight", page.locator(".thumb img").first.element_handle()) == 1600

    # More pages than places left (10 − 3): the user picks them
    pdf_input.set_input_files({"name": "manuel.pdf", "mimeType": "application/pdf", "buffer": pdf(12)})
    sheet = page.locator(".sheet", has=page.locator(".pdf-pages"))
    sync_api.expect(sheet).to_be_visible()
    sync_api.expect(sheet).to_contain_text("« manuel.pdf » a 12 pages : choisissez-en 7 au plus")
    sync_api.expect(sheet.locator(".pdf-page img").first).to_be_visible()  # thumbnails drawn
    for n in range(1, 8):
        sheet.get_by_role("button", name=f"Page {n}", exact=True).click()
    sync_api.expect(sheet.get_by_role("button", name="Page 8", exact=True)).to_be_disabled()
    sheet.get_by_role("button", name="Page 7", exact=True).click()  # one less
    sheet.get_by_role("button", name="Page 12", exact=True).click()
    sheet.get_by_role("button", name="Ajouter 7 pages").click()
    sync_api.expect(page.locator(".thumb img")).to_have_count(10)
    sync_api.expect(sheet).to_be_hidden()

    # Full: said, not added
    pdf_input.set_input_files({"name": "encore.pdf", "mimeType": "application/pdf", "buffer": pdf(1)})
    sync_api.expect(page.get_by_text("Déjà 10 pages")).to_be_visible()
    sync_api.expect(page.locator(".thumb img")).to_have_count(10)


def text_pdf(browser) -> bytes:
    """A real text PDF (a lesson printed by the browser), not a picture of one."""
    context = browser.new_context()
    try:
        page = context.new_page()
        page.set_content("<h1>La Révolution française</h1><p>En 1789, le peuple de Paris prend la Bastille.</p>")
        return page.pdf()
    finally:
        context.close()


def test_pdf_text_kept_with_its_page(page, browser):
    page.goto("/")
    page.locator("input[type=file][accept*=pdf]").set_input_files(
        {"name": "cours.pdf", "mimeType": "application/pdf", "buffer": text_pdf(browser)}
    )
    sync_api.expect(page.locator(".thumb img")).to_have_count(1)
    page.locator(".chip").first.click()  # the free prompt
    page.locator("textarea[x-ref=promptText]").fill("Une carte par date")
    page.get_by_role("button", name="✨ Générer les cartes").click()
    page.locator(".flash").first.wait_for()
    (summary,) = lessons(page)
    (text,) = lesson(page, summary["id"])["page_texts"]
    assert text == "La Révolution française\nEn 1789, le peuple de Paris prend la Bastille."

    # Reopened, then generated again: the text goes with its page again
    page.reload()
    page.locator(".chip-btn").first.click()
    page.locator(".lesson").first.click()
    sync_api.expect(page.locator(".thumb img")).to_have_count(1)
    page.locator("textarea[x-ref=promptText]").fill("Une carte par lieu")
    page.get_by_role("button", name="✨ Régénérer").click()
    sync_api.expect(page.get_by_text("Cartes régénérées")).to_be_visible()
    assert lesson(page, summary["id"])["prompt"] == "Une carte par lieu"
    assert lesson(page, summary["id"])["page_texts"] == [text]


def add_photo(page, buffer: bytes) -> None:
    page.locator('input[type=file][accept="image/*"][multiple]').set_input_files(
        {"name": "page.png", "mimeType": "image/png", "buffer": buffer}
    )
    sync_api.expect(page.locator(".thumb img")).to_have_count(1)


def add_text_pdf(page, browser) -> None:
    page.locator("input[type=file][accept*=pdf]").set_input_files(
        {"name": "cours.pdf", "mimeType": "application/pdf", "buffer": text_pdf(browser)}
    )
    sync_api.expect(page.locator(".thumb img")).to_have_count(1)


def open_hide(page):
    """The first photo's 🖍️ editor, open."""
    page.get_by_role("button", name="Cacher une partie de la page (un nom…)").click()
    editor = page.locator(".hide-editor")
    sync_api.expect(editor).to_be_visible()
    return editor


def stroke(page, y: float) -> None:
    """A stroke across the open editor's photo, at `y` of its height."""
    box = page.locator(".hide-editor canvas").bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.1, box["y"] + box["height"] * y)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * 0.9, box["y"] + box["height"] * y, steps=8)
    page.mouse.up()


def generate_from_photos(page, prompt: str) -> dict:
    """A lesson from the photos added and a free prompt: the saved lesson."""
    page.locator(".chip").first.click()  # the free prompt
    page.locator("textarea[x-ref=promptText]").fill(prompt)
    page.get_by_role("button", name="✨ Générer les cartes").click()
    page.locator(".flash").first.wait_for()
    (summary,) = lessons(page)
    return lesson(page, summary["id"])


def photo_not_sent(page, i: int = 0):
    """A photo not sent yet, as it would be sent (its blob in the page), in grey levels."""
    data = page.evaluate(
        """async (i) => {
            const blob = Alpine.$data(document.querySelector('[x-data]')).photos[i].blob;
            const bytes = new Uint8Array(await blob.arrayBuffer());
            let s = "";
            for (const b of bytes) s += String.fromCharCode(b);
            return btoa(s);
        }""",
        i,
    )
    return PILImage.open(io.BytesIO(base64.b64decode(data))).convert("L")


def editor_pixel(page, x: float, y: float) -> int:
    """The open editor's canvas at (`x`, `y`) of its size, in grey level."""
    return page.evaluate(
        """([x, y]) => {
            const c = document.querySelector('.hide-editor canvas');
            const at = [Math.floor(c.width * x), Math.floor(c.height * y)];
            const [r, g, b] = c.getContext('2d').getImageData(...at, 1, 1).data;
            return Math.round((r + g + b) / 3);
        }""",
        [x, y],
    )


PDF_NOTICE = re.compile("^Sur une page de PDF, son texte n'est alors pas envoyé")


def test_a_name_hidden_before_the_photo_is_sent(page):
    """Blacked out with a finger, un-blacked the same way; only the blacked-out photo is sent."""
    page.goto("/")
    add_photo(page, png("white"))
    editor = open_hide(page)
    sync_api.expect(editor.get_by_text(PDF_NOTICE)).to_be_hidden()  # a photo: no text to leave out
    stroke(page, 0.1)  # the name
    stroke(page, 0.5)  # a mistake…
    editor.get_by_role("button", name="Dénoircir", exact=True).click()
    stroke(page, 0.5)  # …un-blacked
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(editor).to_be_hidden()
    sync_api.expect(page.locator(".thumb-hide.used")).to_have_count(1)

    saved = generate_from_photos(page, "Une carte par mot")
    sent = PILImage.open(io.BytesIO(page.request.get(f"/api/lessons/{saved['id']}/photos/1").body())).convert("L")
    width, height = sent.size
    assert sent.getpixel((width // 2, height // 10)) < 40  # black: the name
    assert sent.getpixel((width // 2, height // 2)) > 215  # white: un-blacked
    assert sent.getpixel((width // 2, height * 8 // 10)) > 215  # never touched
    sync_api.expect(page.locator(".thumb-hide")).to_be_hidden()  # sent: nothing left to hide


def test_a_pdf_page_with_a_hidden_part_goes_without_its_text(page, browser):
    """Its text holds the hidden name too: the page is sent as a picture only, and the editor says so."""
    page.goto("/")
    add_text_pdf(page, browser)
    editor = open_hide(page)
    sync_api.expect(editor.get_by_text(PDF_NOTICE)).to_be_visible()
    stroke(page, 0.1)
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(editor).to_be_hidden()

    sent = []
    page.on("request", lambda r: sent.append(r.post_data_buffer or b""))
    assert not any(generate_from_photos(page, "Une carte par date")["page_texts"])
    assert not any(b"Bastille" in body for body in sent)  # not even sent to the server


def test_un_black_all_gives_the_original_and_its_text_back(page, browser):
    """Everything un-blacked then done: the original photo, the PDF page's text sent with it again."""
    page.goto("/")
    add_text_pdf(page, browser)
    original = photo_not_sent(page)
    editor = open_hide(page)
    stroke(page, 0.1)
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(page.locator(".thumb-hide.used")).to_have_count(1)

    open_hide(page)
    editor.get_by_role("button", name="Tout dénoircir").click()
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(editor).to_be_hidden()
    sync_api.expect(page.locator(".thumb-hide.used")).to_have_count(0)
    assert photo_not_sent(page).tobytes() == original.tobytes()

    saved = generate_from_photos(page, "Une carte par date")
    assert saved["page_texts"] == ["La Révolution française\nEn 1789, le peuple de Paris prend la Bastille."]


def test_hidden_parts_seen_again_and_cancel_changes_nothing(page):
    """The editor reopened shows what is blacked out; "Annuler" leaves the photo and its mask as they were."""
    page.goto("/")
    add_photo(page, png("white"))
    editor = open_hide(page)
    stroke(page, 0.1)
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(page.locator(".thumb-hide.used")).to_have_count(1)  # done: the photo blacked out
    hidden = photo_not_sent(page)

    open_hide(page)
    assert editor_pixel(page, 0.5, 0.1) < 40  # still blacked out
    assert editor_pixel(page, 0.5, 0.5) > 215
    editor.get_by_role("button", name="Tout dénoircir").click()  # then thought better of it
    stroke(page, 0.5)
    editor.get_by_role("button", name="Annuler").click()
    sync_api.expect(editor).to_be_hidden()
    sync_api.expect(page.locator(".thumb-hide.used")).to_have_count(1)
    assert photo_not_sent(page).tobytes() == hidden.tobytes()

    open_hide(page)
    assert editor_pixel(page, 0.5, 0.1) < 40
    assert editor_pixel(page, 0.5, 0.5) > 215


def test_a_photo_turned_turns_what_it_hides(page):
    """↻ on a portrait photo with a stripe hidden at its top: the stripe on the right of the landscape one."""
    page.goto("/")
    add_photo(page, png("white"))  # 600 × 800
    editor = open_hide(page)
    stroke(page, 0.1)
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(page.locator(".thumb-hide.used")).to_have_count(1)
    page.get_by_role("button", name="Tourner la photo d'un quart de tour").click()
    page.wait_for_function("document.querySelector('.thumb img').naturalWidth === 800")  # landscape now
    turned = photo_not_sent(page)
    assert turned.size == (800, 600)
    assert turned.getpixel((720, 300)) < 40  # the stripe, now on the right
    assert turned.getpixel((400, 300)) > 215
    assert turned.getpixel((80, 300)) > 215

    open_hide(page)  # the mask turned with it
    assert editor_pixel(page, 0.9, 0.5) < 40
    assert editor_pixel(page, 0.1, 0.5) > 215
    editor.get_by_role("button", name="Tout dénoircir").click()
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(page.locator(".thumb-hide.used")).to_have_count(0)
    original = photo_not_sent(page)  # the turned original, all white
    assert original.size == (800, 600)
    assert original.getextrema()[0] > 215


def test_the_next_page_added_days_later(page):
    """A lesson reopened, a page added: "Add the new page's cards" reads it alone, its cards
    come after the lesson's (marked new), the ones made already stay."""
    page.goto("/")
    gallery = page.locator('input[type=file][accept="image/*"][multiple]')
    gallery.set_input_files({"name": "p1.png", "mimeType": "image/png", "buffer": png("white")})
    page.locator(".chip").first.click()  # the free prompt
    page.locator("textarea[x-ref=promptText]").fill(FRONT_PROMPT)
    page.get_by_role("button", name="✨ Générer les cartes").click()
    page.locator(".flash").first.wait_for()
    (summary,) = lessons(page)
    made = lesson(page, summary["id"])["cards"]
    complete = page.get_by_role("button", name="➕ Ajouter les cartes de la nouvelle page")
    sync_api.expect(complete).to_be_hidden()  # no new page yet

    gallery.set_input_files({"name": "p2.png", "mimeType": "image/png", "buffer": png("blue")})
    complete.click()
    sync_api.expect(page.locator(".flash")).to_have_count(2 * len(made))
    sync_api.expect(page.get_by_text("cartes ajoutées depuis les nouvelles pages")).to_be_visible()
    sync_api.expect(page.locator(".flash-badge:visible")).to_have_count(len(made))  # the new ones
    sync_api.expect(complete).to_be_hidden()  # read now
    saved = lesson(page, summary["id"])
    assert saved["cards"][: len(made)] == made and saved["photo_count"] == 2
    assert len(lessons(page)) == 1


def test_a_card_explained_then_its_follow_ups(page):
    generate_free(page, "QCM sur la Révolution")
    card = page.locator(".flash").first
    card.get_by_role("button", name="Expliquer cette carte").click()
    bubble = card.locator(".explain")
    sync_api.expect(bubble).to_contain_text("(démo, explain) En quelle année")
    assert bubble.bounding_box()["width"] > 0.8 * card.bounding_box()["width"]  # under the card, not beside it
    # Only the follow-ups the AI offered (the demo: an example, a way to remember, and why: a QCM)
    sync_api.expect(bubble.locator(".chip")).to_have_text(
        ["Un exemple", "Une astuce pour retenir", "Pourquoi c'est juste ?"]
    )
    bubble.get_by_role("button", name="Pourquoi c'est juste ?").click()
    sync_api.expect(bubble.locator(".explain-block").nth(1)).to_contain_text("Pourquoi : (démo, why)")
    sync_api.expect(bubble.locator(".chip")).to_have_text(["Un exemple", "Une astuce pour retenir"])  # asked: gone

    bubble.get_by_role("button", name="Garder dans « Info »").click()  # on the back in Anki
    sync_api.expect(page.locator(".save-pill")).to_have_class(SAVED)
    (summary,) = lessons(page)
    info = lesson(page, summary["id"])["cards"][0]["info"]
    assert "(démo, explain)" in info and "(démo, why)" in info
    card.get_by_role("button", name="Expliquer cette carte").click()  # again: folded, nothing asked
    sync_api.expect(bubble).to_be_hidden()
    assert [c["kind"] for c in lesson(page, summary["id"])["ai_calls"]].count("explain") == 2


def test_a_card_and_its_explanation_reported_in_the_app(page):
    """The app's page (config "report") reports the AI's content to Notosaurus: exactly what
    the sheet shows; the computer, its own AI, has nothing to report to."""
    generate_free(page, "QCM sur la Révolution")
    sync_api.expect(page.get_by_role("button", name="Signaler").first).to_be_hidden()

    sent = []
    page.route("**/api/config", lambda route: route.fulfill(json={**route.fetch().json(), "report": True}))

    def report(route):
        sent.append(route.request.post_data_json)
        route.fulfill(json={"received": True})

    page.route("**/api/lessons/*/report", report)
    generate_free(page, "QCM sur la Révolution")
    card = page.locator(".flash").first
    card.get_by_role("button", name="Plus d'actions").click()
    card.get_by_role("button", name="Signaler").click()
    sheet = page.get_by_role("dialog", name="Signaler un contenu")
    sync_api.expect(sheet.locator(".chips")).to_be_hidden()  # no explanation, no picture: the card
    send = sheet.get_by_role("button", name="Envoyer")
    sync_api.expect(send).to_be_disabled()  # a reason first
    sheet.get_by_label("Faux").check()
    sheet.locator("textarea").fill("La date est fausse")
    preview = sheet.locator(".report-preview").inner_text()
    send.click()
    sync_api.expect(sheet).to_contain_text("Merci")
    assert sent == [
        {"kind": "card", "reason": "wrong", "comment": "La date est fausse", "content": preview, "picture": ""}
    ]
    assert preview.startswith("Front: ") and "En quelle année" in preview

    sheet.get_by_role("button", name="Fermer").last.click()
    card.get_by_role("button", name="Expliquer cette carte").click()
    sync_api.expect(card.locator(".explain")).to_contain_text("(démo, explain)")
    card.get_by_role("button", name="Plus d'actions").click()
    card.get_by_role("button", name="Signaler").click()
    sheet.get_by_role("button", name="L'explication").click()
    sheet.get_by_label("Choquant ou inapproprié").check()
    sync_api.expect(sheet.locator(".report-preview")).to_contain_text("explain: (démo, explain)")
    send.click()
    sync_api.expect(sheet).to_contain_text("Merci")
    assert sent[1]["kind"] == "explanation" and sent[1]["reason"] == "offensive"


def test_the_decks_offered_are_the_chosen_childs_and_no_ones(page):
    jules = {"id": "jules", "name": "Jules", "grade": "5e", "decks": "Jules::5e"}
    mathilde = {"id": "mathilde", "name": "Mathilde", "grade": "3e", "decks": "Mathilde"}
    page.request.put("/api/children", data=[jules, mathilde])
    decks = ["Jules::5ème::Anglais", "Mathilde::SVT", "Maths::Fractions", "Jules"]
    page.route("**/api/decks", lambda route: route.fulfill(json=decks))
    generate_free(page, FRONT_PROMPT)
    page.locator("input[list=decks]").focus()

    def offered():
        return page.locator("#decks option").evaluate_all("options => options.map((o) => o.value)")

    sync_api.expect(page.locator("#decks option")).not_to_have_count(0)
    assert offered() == ["Jules::5ème::Anglais", "Maths::Fractions", "Jules"]  # Jules is chosen first
    page.evaluate("document.querySelector('[x-data]')._x_dataStack[0].chooseChild('mathilde')")
    sync_api.expect(page.locator("#decks option")).to_have_count(2)
    assert offered() == ["Mathilde::SVT", "Maths::Fractions"]


def test_helps_as_the_settings_say(page):
    """No switch under the prompt: the helps come as the settings say (on at first)."""
    page.goto("/")
    sync_api.expect(page.locator(".switch.helps")).to_have_count(0)
    generate_free(page, FRONT_PROMPT)
    sync_api.expect(page.locator(".card-help textarea").first).to_have_value("(démo) Pourquoi c'est la réponse.")
    sync_api.expect(page.locator(".card-help:visible")).to_have_count(2)  # an explanation, a mnemonic: the others none


def test_no_support_link_where_notosaurus_is_paid_for(page):
    """The Android app's own page (its subscription) says donations: false."""
    page.goto("/")
    sync_api.expect(page.locator(".support-link")).to_be_visible()

    def paid(route):
        config = route.fetch().json()
        route.fulfill(json={**config, "donations": False})

    page.route("**/api/config", paid)
    page.reload()
    page.wait_for_function("document.documentElement.classList.contains('i18n-ready')")
    sync_api.expect(page.locator(".support-link")).to_be_hidden()


def test_no_apkg_where_the_cards_go_straight_to_ankidroid(page, anki):
    """The Android app's own page says apkg: false: "Add to Anki" alone."""
    generate_free(page, FRONT_PROMPT)
    sync_api.expect(page.get_by_role("button", name="Télécharger le fichier .apkg")).to_be_visible()

    def app(route):
        route.fulfill(json={**route.fetch().json(), "apkg": False})

    page.route("**/api/config", app)
    generate_free(page, FRONT_PROMPT)
    sync_api.expect(page.get_by_role("button", name="Télécharger le fichier .apkg")).to_be_hidden()
    sync_api.expect(page.get_by_role("button", name=re.compile("Anki"))).not_to_have_count(0)


def test_review_in_ankidroid_once_sent(page, anki):
    """The Android app's page (review_in_anki): "📚 Review" once the lesson is sent."""
    asked = []

    def app(route):
        route.fulfill(json={**route.fetch().json(), "review_in_anki": True})

    page.route("**/api/config", app)
    page.route(
        "**/api/anki/review",
        lambda route: (asked.append(route.request.post_data_json), route.fulfill(json={"opened": True})),
    )
    generate_free(page, FRONT_PROMPT)
    review = page.locator(".bar-row").get_by_role("button", name="📚 Réviser")
    sync_api.expect(review).to_be_hidden()  # not sent yet
    page.get_by_role("button", name="📥 Ajouter à Anki").click()
    sync_api.expect(page.locator(".toast.ok").get_by_role("button", name="📚 Réviser")).to_be_visible()
    # Sent: sending again updates its cards
    sync_api.expect(page.get_by_role("button", name="🔄 Mettre à jour dans Anki")).to_be_visible()
    review.click()
    sync_api.expect(page.locator(".toast.ok")).to_be_hidden()
    assert [a["deck"] for a in asked] == [page.locator(".field.deck input").input_value()]


def test_cards_left_over_in_anki_deleted_when_asked(page, anki):
    """A card deleted after a send: the next send says its note is left in Anki, with its
    text, and deletes it only on "Delete from Anki"."""
    generate_free(page, FRONT_PROMPT)
    page.get_by_role("button", name="📥 Ajouter à Anki").click()
    update = page.get_by_role("button", name="🔄 Mettre à jour dans Anki")
    sync_api.expect(update).to_be_visible()
    notes = len(anki.notes)
    first = page.locator(".flash").first
    gone = first.locator("textarea").first.input_value()
    first.get_by_role("button", name="Plus d'actions").click()
    first.get_by_role("button", name="Supprimer la carte").click()
    update.click()
    sheet = page.locator("aside.sheet", has_text="Cartes en trop dans Anki")
    sync_api.expect(sheet).to_be_visible()
    sync_api.expect(sheet.locator(".leftovers li").first).to_have_text(gone)
    sheet.get_by_role("button", name="Supprimer d'Anki").click()
    sync_api.expect(sheet).to_be_hidden()
    assert len(anki.notes) == notes - 1


def test_the_apps_welcome_accepted_once(page):
    """The app's first launch: a parent's tool, Gemini, the privacy policy. Accept stays off
    until ticked; accepted, it goes (the app keeps it). Not on the computer (no "welcome")."""
    accepted = []

    def config(route):
        route.fulfill(json={**route.fetch().json(), "welcome": 1, "welcome_accepted": bool(accepted)})

    page.route("**/api/config", config)
    page.route("**/api/welcome", lambda route: (accepted.append(1), route.fulfill(json={"accepted": 1})))
    page.goto("/")
    welcome = page.get_by_role("dialog", name="Avant de commencer")
    sync_api.expect(welcome).to_be_visible()
    sync_api.expect(welcome).to_contain_text("Gemini de Google")
    sync_api.expect(welcome.get_by_role("link", name="Politique de confidentialité")).to_have_attribute(
        "href", re.compile(r"/fr/app-privacy/")
    )
    accept = welcome.get_by_role("button", name="Accepter")
    sync_api.expect(accept).to_be_disabled()
    welcome.get_by_label("Je suis un parent (un adulte) et j'accepte la politique de confidentialité.").check()
    accept.click()
    sync_api.expect(welcome).to_be_hidden()
    assert accepted == [1]
    page.reload()
    sync_api.expect(page.locator(".flash, .tagline").first).to_be_visible()
    sync_api.expect(welcome).to_be_hidden()  # once


def test_no_welcome_on_the_computer(page):
    page.goto("/")
    page.locator(".tagline").wait_for()
    sync_api.expect(page.get_by_role("dialog", name="Avant de commencer")).to_be_hidden()


def test_ankidroid_installed_from_the_message(page, anki):
    """The app without AnkiDroid: "Add to Anki" says so, with a button to install it
    (Google Play only opens when asked)."""
    installs = []
    page.route(
        "**/api/anki/send",
        lambda route: route.fulfill(status=400, json={"detail": {"code": "anki.android_missing", "params": {}}}),
    )
    page.route("**/api/anki/install", lambda route: (installs.append(1), route.fulfill(json={"opened": True})))
    generate_free(page, FRONT_PROMPT)
    page.get_by_role("button", name="📥 Ajouter à Anki").click()
    toast = page.locator(".toast[role=alert]")
    sync_api.expect(toast).to_contain_text("AnkiDroid")
    assert installs == []
    toast.get_by_role("button", name="Installer AnkiDroid").click()
    sync_api.expect(toast).to_be_hidden()
    assert installs == [1]

    # Another error: no such button
    page.route(
        "**/api/anki/send",
        lambda route: route.fulfill(
            status=502, json={"detail": {"code": "anki.android_failed", "params": {"detail": "x"}}}
        ),
    )
    page.get_by_role("button", name="📥 Ajouter à Anki").click()
    sync_api.expect(toast).to_be_visible()
    sync_api.expect(toast.get_by_role("button", name="Installer AnkiDroid")).to_be_hidden()


def test_the_children_of_the_open_anki_profile(page):
    """On the computer, a card belongs to the Anki profile it was made in: only the open
    profile's are offered; a profile's only child chosen by itself. The profile stays said
    under the name (where the cards go), nowhere else."""
    kids = [
        {"id": "jules", "name": "Jules", "anki_profile": "Famille"},
        {"id": "mathilde", "name": "Mathilde", "anki_profile": "Famille"},
        {"id": "tom", "name": "Tom"},  # made before: the profile it is next seen in
    ]
    page.request.put("/api/children", data=kids)
    open_profile = {"name": "Famille"}
    page.route(
        "**/api/anki/status",
        lambda route: route.fulfill(json={"available": True, "profile": open_profile["name"]}),
    )
    page.goto("/")
    chip = page.get_by_role("button", name="Enfants")
    sync_api.expect(page.locator(".brand-profile")).to_contain_text("Famille")  # a shared profile: said
    chip.click()
    sheet = page.get_by_role("dialog", name="Enfants")
    sync_api.expect(sheet).not_to_contain_text("profil Anki")  # the children, not the profile
    sync_api.expect(sheet.locator(".child-rows li:visible")).to_have_count(3)  # Tom: this profile's now
    sheet.locator(".child-row", has_text="Mathilde").click()
    sync_api.expect(chip).to_contain_text("Mathilde")
    owners = {c["id"]: c["anki_profile"] for c in page.request.get("/api/children").json()}
    assert owners == {"jules": "Famille", "mathilde": "Famille", "tom": "Famille"}

    open_profile["name"] = "Léa"  # her own profile: none of the family's; a card made here is hers
    sync_api.expect(page.locator(".brand-profile")).to_contain_text("Léa", timeout=8000)
    sync_api.expect(chip).to_contain_text("Pour qui ?")
    chip.click()
    sheet.locator("input.child-name").fill("Léa")
    sheet.get_by_role("button", name="Enregistrer").click()
    sync_api.expect(sheet.locator(".child-rows li:visible")).to_have_count(1)
    sheet.get_by_role("button", name="Fermer").click()
    sync_api.expect(chip).to_contain_text("Léa")  # its only child, chosen
    sync_api.expect(page.locator(".brand-profile")).to_contain_text("Léa")  # always said
    assert page.request.get("/api/children").json()[-1]["anki_profile"] == "Léa"

    open_profile["name"] = "Famille"  # back: Léa's card not offered
    sync_api.expect(chip).not_to_contain_text("Léa", timeout=8000)


def test_a_childs_class_typed_freely_the_countrys_suggested(page):
    """The class: the language's classes suggested (and the higher ones), any other typed
    ("Maths Sup", another country's): told as it is, its decks named after it."""
    page.goto("/")
    page.get_by_role("button", name="Enfants").click()
    sheet = page.get_by_role("dialog", name="Enfants")
    sheet.locator("input.child-name").fill("Léa")
    grade = sheet.get_by_placeholder("Choisissez ou écrivez : 4e, Maths Sup…")
    suggested = sheet.locator("datalist#child-grades option").evaluate_all("(o) => o.map((e) => e.value)")
    assert suggested[0] == "CP" and "Terminale" in suggested and "Prépa" in suggested
    grade.fill("Maths Sup")
    grade.press("Tab")  # its change: the class set
    sync_api.expect(sheet.get_by_role("button", name="Léa::Maths Sup")).to_be_visible()  # its decks suggested
    sheet.get_by_role("button", name="Léa::Maths Sup").click()
    sheet.get_by_role("button", name="Enregistrer").click()
    (child,) = page.request.get("/api/children").json()
    assert (child["grade"], child["decks"]) == ("Maths Sup", "Léa::Maths Sup")


def test_a_lesson_copied_for_another_child(page):
    """⧉ Copy for…: the other children; the copy (its decks) opened, for that child."""
    kids = [
        {"id": "jules", "name": "Jules", "grade": "5e", "decks": "Jules::5e"},
        {"id": "mathilde", "name": "Mathilde", "grade": "3e", "decks": "Mathilde::3e"},
    ]
    page.request.put("/api/children", data=kids)
    generate_free(page, FRONT_PROMPT)
    deck = page.locator("input[list=decks]")
    sync_api.expect(deck).to_have_value(re.compile(r"^Jules::5e::"))
    page.get_by_role("button", name="⧉ Copier pour…").click()
    sheet = page.get_by_role("dialog", name="Copier pour…")
    sync_api.expect(sheet.locator(".child-row")).to_have_count(1)  # not Jules: his already
    sheet.locator(".child-row", has_text="Mathilde").click()
    sync_api.expect(page.locator(".toast.ok")).to_contain_text("Copiée pour Mathilde")
    sync_api.expect(deck).to_have_value(re.compile(r"^Mathilde::3e::"))
    sync_api.expect(page.get_by_role("button", name="Enfants")).to_contain_text("Mathilde")
    assert sorted(summary["child"] for summary in lessons(page)) == ["jules", "mathilde"]


def test_no_profile_badge_where_there_are_no_profiles(page):
    """The Android app (AnkiDroid doesn't say its profile) says profiles: false."""
    page.route("**/api/anki/status", lambda route: route.fulfill(json={"available": True, "profile": None}))
    page.goto("/")
    sync_api.expect(page.locator(".brand-profile")).to_be_visible()  # "none": no profile open in Anki

    def phone(route):
        route.fulfill(json={**route.fetch().json(), "profiles": False})

    page.route("**/api/config", phone)
    page.reload()
    page.wait_for_function("document.documentElement.classList.contains('i18n-ready')")
    sync_api.expect(page.locator(".brand-profile")).to_be_hidden()


def test_help_links_in_the_page_language(page):
    docs = "https://cchabanois.github.io/notosaurus/"
    page.goto("/")
    sync_api.expect(page.locator(".docs-link")).to_have_attribute("href", docs + "fr/")  # the footer
    sync_api.expect(page.get_by_role("link", name="☕ Soutenir Notosaurus")).to_have_attribute(
        "href", "https://ko-fi.com/notosaurus"
    )
    generate_free(page, FRONT_PROMPT)
    page.locator(".chip-btn").first.click()  # the lessons sheet: its own page
    sync_api.expect(page.get_by_role("link", name="Aide : Mes leçons")).to_have_attribute("href", docs + "fr/lessons/")
    page.locator(".lang-select select").select_option("pt")
    sync_api.expect(page.locator(".docs-link")).to_have_attribute("href", docs + "pt-br/")


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


def test_dictation_in_the_app(page):
    """The Android app's page (dictation): 🎤 in the instructions' corner; once to listen,
    again to stop, the text said then in the field. On the computer: no 🎤."""
    page.goto("/")
    mic = page.get_by_role("button", name="Dicter").first
    sync_api.expect(page.get_by_role("textbox", name="Texte de la consigne")).to_be_visible()
    sync_api.expect(mic).to_be_hidden()

    stopped = []
    page.route("**/api/config", lambda route: route.fulfill(json={**route.fetch().json(), "dictation": True}))
    page.route("**/api/dictation/start", lambda route: route.fulfill(json={"listening": True}))
    page.route(
        "**/api/dictation/stop",
        lambda route: (
            stopped.append(route.request.post_data_json),
            route.fulfill(json={"text": "Douze cartes sur el abuelo et la abuela."}),
        ),
    )
    page.goto("/")
    page.get_by_role("button", name="Dicter").first.click()
    sync_api.expect(page.get_by_text("J'écoute… appuyez sur ⏹ quand vous avez fini.").first).to_be_visible()
    sync_api.expect(page.get_by_role("textbox", name="Texte de la consigne")).to_be_disabled()  # waits for its text
    if shots := os.environ.get("NOTOSAURUS_SHOTS"):  # to look at it: a folder for the screenshot
        page.screenshot(path=f"{shots}/dictation.png")
    page.get_by_role("button", name="Arrêter et écrire le texte").click()
    field = page.get_by_role("textbox", name="Texte de la consigne")
    sync_api.expect(field).to_have_value(re.compile("Douze cartes sur el abuelo et la abuela.$"))
    assert stopped == [{"kind": "prompt"}]
    sync_api.expect(field).to_be_enabled()

    # A lesson shown: the 🎤 still there, on the instructions and on the correction (the
    # lesson's own "dictation" option once replaced it)
    page.get_by_role("radio", name="✏️ Libre").click()
    page.locator("textarea[x-ref=promptText]").fill(FRONT_PROMPT)
    page.get_by_role("button", name="✨ Générer à partir de la consigne seule").click()
    page.locator(".flash").first.wait_for()
    sync_api.expect(page.get_by_role("button", name="Dicter")).to_have_count(2)
    sync_api.expect(page.locator(".revise").get_by_role("button", name="Dicter")).to_be_visible()
    sync_api.expect(page.locator(".save-pill")).not_to_have_class(re.compile(r"\berror\b"))
    sync_api.expect(page.get_by_role("button", name="Dicter").first).to_be_enabled()


def test_tidy_up_the_instructions(page):
    """“✨ Tidy up” under the instructions (the demo AI marks them), “↩” brings them back."""
    page.goto("/")
    tidy = page.get_by_role("button", name="✨ Mettre au propre")
    page.get_by_role("radio", name="⭐ Automatique (d'après la leçon)").click()
    sync_api.expect(page.get_by_role("textbox", name="Texte de la consigne")).not_to_have_value("")
    sync_api.expect(tidy).to_be_hidden()  # Notosaurus's own, as they are: tidy already
    page.get_by_role("radio", name="✏️ Libre").click()
    field = page.get_by_role("textbox", name="Texte de la consigne")
    sync_api.expect(tidy).to_be_hidden()  # nothing to tidy up
    field.fill("la famille en espagnol, dix non douze")
    tidy.click()
    sync_api.expect(field).to_have_value("(démo) la famille en espagnol, dix non douze")
    if shots := os.environ.get("NOTOSAURUS_SHOTS"):
        page.screenshot(path=f"{shots}/tidy.png")
    page.locator(".prompt-actions.tidy").get_by_role("button", name="↩ Annuler").click()
    sync_api.expect(field).to_have_value("la famille en espagnol, dix non douze")


def test_find_a_free_picture(page):
    """🖼️ → “✨ Image”: the AI decides a picture, the free pictures that fit are offered (its
    choice first, ⭐), one tapped becomes the card's."""
    previews = []
    for colour in ("#c0392b", "#2e86de", "#27ae60", "#f39c12", "#8e44ad", "#16a085"):
        previews.append("data:image/jpeg;base64," + base64.b64encode(plain_image(120, 90, colour)).decode())
    results = [
        {"source": source, "id": f"{source}-{n}", "title": f"Picture {n}", "preview": preview, "licence": "CC0"}
        for n, (source, preview) in enumerate(zip(["commons", "openverse"] * 3, previews, strict=True))
    ]
    asked = []
    page.route(
        "**/api/pictures/search",
        lambda route: (asked.append(route.request.post_data_json), route.fulfill(json={"results": results})),
    )

    def found(route):
        out = io.BytesIO()
        PILImage.new("RGB", (300, 300), "#2e86de").save(out, "JPEG")
        lesson_id, card_id = route.request.url.split("/api/lessons/")[1].split("/cards/")
        card_id = card_id.split("/")[0]
        page_lesson = page.request.get(f"/api/lessons/{lesson_id}").json()
        card = next(c for c in page_lesson["cards"] if c["id"] == card_id)
        route.fulfill(json={"card": {**card, "picture": "picture-x.jpg"}, "lesson": page_lesson})

    page.route("**/picture/found", found)
    generate_free(page, FRONT_PROMPT)
    first = page.locator(".flash").first
    first.get_by_role("button", name="Image", exact=True).click()
    first.get_by_role("button", name="✨ Image").click()
    picks = first.locator(".found-pick")
    sync_api.expect(picks).to_have_count(6)
    sync_api.expect(picks.first.locator(".found-best")).to_be_visible()  # the AI's choice
    sync_api.expect(picks.nth(1).locator(".found-best")).to_be_hidden()
    sync_api.expect(
        first.get_by_text("Images libres de droits (Wikimedia Commons, Openverse) : touchez celle qui va.")
    ).to_be_visible()
    assert asked[0]["subject"]
    if shots := os.environ.get("NOTOSAURUS_SHOTS"):
        first.screenshot(path=f"{shots}/found.png")
    picks.nth(1).click()
    sync_api.expect(picks).to_have_count(0)  # chosen: the grid goes


def drop(page, target, files: list[tuple[str, str, bytes]]) -> None:
    """Files dragged from the computer and let go on `target` (a locator), as a browser does it."""
    payload = [{"name": n, "type": t, "data": base64.b64encode(b).decode()} for n, t, b in files]
    target.evaluate(
        """(el, files) => {
            const data = new DataTransfer();
            for (const f of files) {
                const bytes = Uint8Array.from(atob(f.data), (c) => c.charCodeAt(0));
                data.items.add(new File([bytes], f.name, { type: f.type }));
            }
            for (const type of ["dragenter", "dragover", "drop"]) {
                el.dispatchEvent(new DragEvent(type, { dataTransfer: data, bubbles: true, cancelable: true }));
            }
        }""",
        payload,
    )


def test_photos_and_pdfs_dropped_on_their_tiles(page):
    """The computer: an image let go on “Gallery”, a PDF on “PDF”: added as if picked."""
    page.goto("/")
    gallery = page.locator(".add-tile", has_text="Galerie")
    drop(page, gallery, [("page-1.png", "image/png", png("red")), ("page-2.png", "image/png", png("blue"))])
    sync_api.expect(page.locator(".thumb img")).to_have_count(2)
    drop(page, page.locator(".add-tile", has_text="PDF"), [("cours.pdf", "application/pdf", pdf(2))])
    sync_api.expect(page.locator(".thumb img")).to_have_count(4)  # its two pages

    # Let go anywhere else: nothing added, and the page stays (not opened by the browser)
    prevented = page.locator("textarea[x-ref=promptText]").evaluate(
        """(el) => {
            const data = new DataTransfer();
            data.items.add(new File(["x"], "x.png", { type: "image/png" }));
            const event = new DragEvent("drop", { dataTransfer: data, bubbles: true, cancelable: true });
            el.dispatchEvent(event);
            return event.defaultPrevented;
        }"""
    )
    assert prevented and page.locator(".thumb img").count() == 4


def test_a_tests_lessons_sent_from_its_sheet(page):
    """Lessons of a test not in Anki yet: sent from the test's sheet, one or all, without
    opening each."""
    page.goto("/")
    made = [page.request.post("/api/extract", multipart={"prompt": FRONT_PROMPT}).json() for _ in range(2)]
    exam = {"name": "Interro", "date": "2026-10-30", "lessons": [{"lesson": m["id"]} for m in made]}
    page.request.put("/api/exams/interro", data=exam)
    page.route("**/api/anki/status", lambda route: route.fulfill(json={"available": True, "profile": None}))
    sent = []

    def send(route):
        sent.append(route.request.post_data_json["lesson_id"])
        route.fulfill(json={"added": 2, "updated": 0, "leftovers": [], "synced": False})

    page.route("**/api/anki/send", send)
    page.reload()
    page.wait_for_function("document.documentElement.classList.contains('i18n-ready')")
    page.evaluate(
        "(async () => { const app = document.querySelector('[x-data]')._x_dataStack[0];"
        " await app.loadExams(); app.openExams(app.exams[0]); })()"
    )
    page.get_by_role("button", name="📥 Tout envoyer à Anki (2 leçons)").click()
    sync_api.expect(page.get_by_role("button", name="📥 Tout envoyer à Anki (2 leçons)")).to_be_enabled()
    assert sent == [m["id"] for m in made]


def test_a_test_made_from_my_lessons_then_its_lessons_ticked(page):
    """ "＋ New test" in My lessons, with no test yet and no lesson open: made empty; its
    lessons then ticked from its sheet."""
    page.goto("/")
    made = [page.request.post("/api/extract", multipart={"prompt": FRONT_PROMPT}).json() for _ in range(2)]
    page.reload()
    page.get_by_role("button", name="Leçons").click()
    page.get_by_role("button", name="＋ Nouveau contrôle").click()
    sheet = page.get_by_role("dialog", name="Contrôles à préparer")
    sheet.get_by_placeholder("ex. : Interro SVT de lundi").fill("Interro")
    sheet.get_by_role("button", name="Créer").click()
    sheet.get_by_role("button", name="＋ Ajouter des leçons").click()
    sync_api.expect(sheet.locator(".exam-add li")).to_have_count(2)
    sheet.locator(".exam-add input[type=checkbox]").first.check()
    sheet.get_by_role("button", name="Ajouter 1 leçon").click()
    sync_api.expect(sheet.locator(".exam-lessons li")).to_have_count(1)
    (exam,) = page.request.get("/api/exams").json()
    assert exam["name"] == "Interro"
    assert [p["lesson"] for p in exam["lessons"]] in ([made[0]["id"]], [made[1]["id"]])


def test_a_lesson_that_looks_wrong_corrected_or_kept(page):
    """A pupil's notes with a wrong date: the card says what the lesson says, with why it
    looks wrong; "Correct" takes the AI's correction, "Keep" keeps the lesson."""
    generate_free(page, "Les dates d'histoire")
    wrong = page.locator(".flash").nth(1)
    sync_api.expect(wrong.locator(".card-doubt")).to_contain_text("1915 est l'année du génocide arménien")
    sync_api.expect(page.locator(".flash").first.locator(".card-doubt")).to_be_hidden()
    wrong.get_by_role("button", name="Corriger").click()
    sync_api.expect(wrong.locator(".card-doubt")).to_be_hidden()
    sync_api.expect(wrong.locator("textarea.back")).to_have_value("1941 – 1945")
    sync_api.expect(page.locator(".save-pill")).to_have_class(SAVED)
    (summary,) = lessons(page)
    card = lesson(page, summary["id"])["cards"][1]
    assert (card["front"], card["back"], card["doubt"]) == ("Génocide des Juifs (Shoah)", "1941 – 1945", None)

    generate_free(page, "Les dates d'histoire")
    wrong = page.locator(".flash").nth(1)
    wrong.get_by_role("button", name="Garder la leçon").click()
    sync_api.expect(wrong.locator(".card-doubt")).to_be_hidden()
    sync_api.expect(wrong.locator("textarea.back")).to_have_value("1915")
