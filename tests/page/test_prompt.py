"""Step 2, the prompt: Notosaurus's and one's own, folded once made, from the prompt alone,
quick or careful, dictated, tidied up."""

import os
import re

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from page.support import (  # noqa: E402
    FRONT_PROMPT,
    draft_kept,
    generate_free,
    lessons,
    open_prompt,
    png,
    started,
)


def test_the_prompt_folds_once_the_cards_are_made(page):
    """Once the lesson has cards, step 2 is one line (its prompt, its speed): the cards come
    first. Its buttons stay; "✏️ Modifier" opens it; a prompt changed since says it isn't
    applied until made again, then folds again."""
    generate_free(page, "Les capitales d'Europe")
    folded = page.locator(".prompt-folded")
    sync_api.expect(folded).to_be_visible()
    sync_api.expect(folded).to_contain_text("✏️ Libre")
    sync_api.expect(folded).to_contain_text("Les capitales d'Europe")
    sync_api.expect(page.locator("textarea[x-ref=promptText]")).to_be_hidden()
    sync_api.expect(page.get_by_role("radio", name="✏️ Libre")).to_be_hidden()
    regenerate = page.get_by_role("button", name="✨ Régénérer")
    sync_api.expect(regenerate).to_be_visible()  # its button in view, folded
    not_applied = page.get_by_text("Modifiée depuis la création des cartes")
    sync_api.expect(not_applied).to_be_hidden()

    folded.get_by_role("button", name="✏️ Modifier").click()
    sync_api.expect(folded).to_be_hidden()
    page.locator("textarea[x-ref=promptText]").fill("Les capitales d'Europe et leurs pays")
    sync_api.expect(not_applied).to_be_visible()

    regenerate.click()
    sync_api.expect(folded).to_be_visible()  # made again: folded again
    sync_api.expect(folded).to_contain_text("et leurs pays")
    sync_api.expect(not_applied).to_be_hidden()

    page.get_by_role("button", name="Nouvelle leçon").click()  # no cards: open, as before
    sync_api.expect(page.locator("textarea[x-ref=promptText]")).to_be_visible()
    sync_api.expect(folded).to_be_hidden()


def test_a_prompt_of_several_lines_is_the_lessons_own(page):
    """A form sends its line ends as \\r\\n, kept in the lesson: a prompt of several lines (the
    Automatic one) was "changed since the cards were made" at once, and the lesson opened
    again said "✏️ Libre" instead of its prompt."""
    page.goto("/")
    started(page)
    gallery = page.locator('input[type=file][accept="image/*"][multiple]')
    gallery.set_input_files({"name": "p1.png", "mimeType": "image/png", "buffer": png("white")})
    page.get_by_role("radio", name="⭐ Automatique (d'après la leçon)").click()
    page.get_by_role("button", name="✨ Générer les cartes").click()
    page.locator(".flash").first.wait_for()
    folded = page.locator(".prompt-folded")
    sync_api.expect(folded).to_contain_text("⭐ Automatique")
    sync_api.expect(page.get_by_text("Modifiée depuis la création des cartes")).to_be_hidden()

    draft_kept(page)
    page.reload()  # the lesson open again
    started(page)
    page.locator(".flash").first.wait_for()
    sync_api.expect(folded).to_contain_text("⭐ Automatique")
    sync_api.expect(page.get_by_text("Modifiée depuis la création des cartes")).to_be_hidden()


def test_a_short_topic_without_photo(page):
    """Automatic chosen, a topic of one word written in it ("Les capitales"): the button
    below makes the cards from it, no photo asked (it took three words: it stayed on the photo)."""
    page.goto("/")
    started(page)
    page.get_by_role("radio", name="⭐ Automatique (d'après la leçon)").click()
    field = page.locator("textarea[x-ref=promptText]")
    field.fill(field.input_value() + "\nLes capitales")
    button = page.locator(".bottom-bar button.btn.primary.wide").first
    sync_api.expect(button).to_have_text("✨ Générer à partir de la consigne seule")
    button.click()
    page.locator(".flash").first.wait_for()


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
    sync_api.expect(page.locator(".prompt-folded")).to_contain_text("⚡ Rapide")  # the choice above stays
    open_prompt(page)
    sync_api.expect(quick).to_have_attribute("aria-checked", "true")

    page.get_by_role("radio", name="🎯 Soigné").click()
    page.reload()  # kept on the device
    started(page)
    open_prompt(page)
    sync_api.expect(page.get_by_role("radio", name="🎯 Soigné")).to_have_attribute("aria-checked", "true")


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


def test_the_prompts_button_says_what_it_does(page):
    """Under the prompt: one of Notosaurus's is seen (it can't be changed); one of yours,
    edited (its name, deck); its text changed in the field, those changes saved into it."""
    page.request.post("/api/prompts", data={"name": "Definitions", "text": "Les définitions de la leçon"})
    page.goto("/")
    actions = page.locator(".prompt-actions")
    page.get_by_role("radio", name="⭐ Automatique (d'après la leçon)").click()
    sync_api.expect(actions.get_by_role("button", name="👁️ Voir la consigne")).to_be_visible()

    page.locator(".chip.more").click()
    page.locator(".picker-item", has_text="Definitions").click()
    sync_api.expect(actions.get_by_role("button", name="✏️ Modifier la consigne")).to_be_visible()
    page.locator("textarea[x-ref=promptText]").fill("Les définitions et les exemples de la leçon")
    actions.get_by_role("button", name="💾 Enregistrer les changements").click()
    sync_api.expect(actions.get_by_role("button", name="✏️ Modifier la consigne")).to_be_visible()
    (mine,) = [p for p in page.request.get("/api/prompts").json() if not p["builtin"]]
    assert (mine["name"], mine["text"]) == ("Definitions", "Les définitions et les exemples de la leçon")


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


def test_dictation_heard_by_the_phone_as_it_comes(page):
    """The phone's own speech recognition ("live"): the text shows in the field while it
    listens, after what was there, then the whole of it at stop; the 🎤 offered even with the
    relay's dictation turned off (it isn't used)."""
    heard = iter(["Douze", "Douze cartes sur el", "Douze cartes sur el abuelo"])
    texts = []

    live = {"dictation": True, "dictation_live": True}
    page.route("**/api/config", lambda route: route.fulfill(json={**route.fetch().json(), **live}))
    page.route("**/api/switches", lambda route: route.fulfill(json={"disabled": ["speech.transcribe"]}))
    page.route("**/api/dictation/start", lambda route: route.fulfill(json={"listening": True, "live": True}))
    last = "Douze cartes sur el abuelo"
    page.route("**/api/dictation/heard", lambda route: route.fulfill(json={"text": next(heard, last)}))
    page.route(
        "**/api/dictation/stop",
        lambda route: (texts.append(1), route.fulfill(json={"text": "Douze cartes sur el abuelo et la abuela"})),
    )
    page.goto("/")
    field = page.get_by_role("textbox", name="Texte de la consigne")
    field.fill("Vocabulaire espagnol")
    page.get_by_role("button", name="Dicter").first.click()
    sync_api.expect(field).to_have_value("Vocabulaire espagnol\nDouze cartes sur el abuelo")  # as it comes
    page.get_by_role("button", name="Arrêter et écrire le texte").click()
    sync_api.expect(field).to_have_value("Vocabulaire espagnol\nDouze cartes sur el abuelo et la abuela")
    sync_api.expect(field).to_be_enabled()
    assert texts == [1]


def test_the_listening_mic_shows_it_while_the_finger_is_still_on_it(page):
    """Listening, the 🎤 is a disc of the main colour, its microphone white. A phone keeps a
    tapped button :hover: its pale hover background came over the listening one, the white
    microphone on it nearly invisible."""
    live = {"dictation": True, "dictation_live": True}
    page.route("**/api/config", lambda route: route.fulfill(json={**route.fetch().json(), **live}))
    page.route("**/api/dictation/start", lambda route: route.fulfill(json={"listening": True, "live": True}))
    page.route("**/api/dictation/heard", lambda route: route.fulfill(json={"text": ""}))
    page.route("**/api/dictation/stop", lambda route: route.fulfill(json={"text": ""}))
    page.goto("/")
    page.get_by_role("button", name="Dicter").first.click()  # the pointer stays on it, as a finger does
    listening = page.get_by_role("button", name="Arrêter et écrire le texte").first
    sync_api.expect(listening).to_have_class(re.compile(r"\blistening\b"))
    listening.hover()
    colours = listening.evaluate(
        """el => [getComputedStyle(el).backgroundColor,
                  getComputedStyle(document.documentElement).getPropertyValue('--primary').trim()]"""
    )
    probe = page.evaluate(
        "c => { const d = document.createElement('div'); d.style.color = c; document.body.append(d); "
        "const v = getComputedStyle(d).color; d.remove(); return v }",
        colours[1],
    )
    assert colours[0] == probe, colours
    listening.click()


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
    # Material's microphone, as Android apps draw it (vendor/material): outlined, then filled
    # while it listens; no emoji in it (its name is its label)
    mic = page.locator("button.mic").first
    icon = "e => getComputedStyle(e, '::before').maskImage"
    sync_api.expect(mic).to_have_text("")
    assert "vendor/material/mic.svg" in mic.evaluate(icon)
    assert page.request.get("/vendor/material/mic.svg").headers["content-type"].startswith("image/svg+xml")
    page.get_by_role("button", name="Dicter").first.click()
    sync_api.expect(page.get_by_text("J'écoute… appuyez sur le micro quand vous avez fini.").first).to_be_visible()
    assert "vendor/material/mic-fill.svg" in mic.evaluate(icon)
    sync_api.expect(page.get_by_role("textbox", name="Texte de la consigne")).to_be_disabled()  # waits for its text
    if shots := os.environ.get("NOTOSAURUS_SHOTS"):  # to look at it: a folder for the screenshot
        page.screenshot(path=f"{shots}/dictation.png")
    page.get_by_role("button", name="Arrêter et écrire le texte").click()
    field = page.get_by_role("textbox", name="Texte de la consigne")
    sync_api.expect(field).to_have_value(re.compile("Douze cartes sur el abuelo et la abuela.$"))
    assert stopped == [{"kind": "prompt"}]
    sync_api.expect(field).to_be_enabled()
    # Added at the end of a long prompt: the field scrolled to it, in sight (not focused: no keyboard)
    assert field.evaluate(
        "(f) => f.scrollHeight > f.clientHeight && f.scrollTop + f.clientHeight >= f.scrollHeight - 2"
    )
    assert not field.evaluate("(f) => f === document.activeElement")

    # A lesson shown: the 🎤 still there, on the instructions and on the correction (the
    # lesson's own "dictation" option once replaced it)
    page.get_by_role("radio", name="✏️ Libre").click()
    page.locator("textarea[x-ref=promptText]").fill(FRONT_PROMPT)
    page.get_by_role("button", name="✨ Générer à partir de la consigne seule").click()
    page.locator(".flash").first.wait_for()
    sync_api.expect(page.locator(".revise").get_by_role("button", name="Dicter")).to_be_visible()
    open_prompt(page)  # folded once the cards are made: its 🎤 with it
    sync_api.expect(page.get_by_role("button", name="Dicter")).to_have_count(2)
    sync_api.expect(page.locator(".save-pill")).not_to_have_class(re.compile(r"\berror\b"))
    sync_api.expect(page.get_by_role("button", name="Dicter").first).to_be_enabled()


def test_dictation_stopped_by_a_tap_elsewhere(page):
    """Listening: a tap anywhere else stops it as ⏹ does, the text written, and does only
    that (the card's ⋯ tapped then doesn't open); scrolling doesn't stop it; the app gone to
    the background does."""
    stopped = []
    page.route("**/api/config", lambda route: route.fulfill(json={**route.fetch().json(), "dictation": True}))
    page.route("**/api/dictation/start", lambda route: route.fulfill(json={"listening": True}))
    page.route(
        "**/api/dictation/stop",
        lambda route: (stopped.append(route.request.post_data_json), route.fulfill(json={"text": "ajoute le frère"})),
    )
    generate_free(page, FRONT_PROMPT)
    revise = page.locator(".revise")
    field = revise.locator("textarea")
    listening = page.get_by_text("J'écoute… appuyez sur le micro quand vous avez fini.").first

    revise.get_by_role("button", name="Dicter").click()
    sync_api.expect(listening).to_be_visible()
    page.mouse.wheel(0, 400)  # scrolling: still listening
    page.wait_for_timeout(300)
    sync_api.expect(listening).to_be_visible()
    assert stopped == []
    page.locator(".count-line").click()  # elsewhere
    sync_api.expect(field).to_have_value("ajoute le frère")
    assert stopped == [{"kind": "correction"}]

    revise.get_by_role("button", name="Dicter").click()
    sync_api.expect(listening).to_be_visible()
    first = page.locator(".flash").first
    first.get_by_role("button", name="Plus d'actions").click()  # only stops it
    sync_api.expect(listening).to_be_hidden()
    sync_api.expect(first.locator(".card-menu-items")).to_be_hidden()
    assert len(stopped) == 2

    revise.get_by_role("button", name="Dicter").click()
    sync_api.expect(listening).to_be_visible()
    page.evaluate("""() => {
        Object.defineProperty(document, "hidden", { value: true, configurable: true });
        document.dispatchEvent(new Event("visibilitychange"));
    }""")
    sync_api.expect(listening).to_be_hidden()
    assert len(stopped) == 3


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
