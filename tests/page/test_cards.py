"""Step 3, the cards: made, edited and saved, formulas, made again, corrected and explained by
the AI, reported."""

import json
import os
import re
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from page.support import (  # noqa: E402
    CLOZE_PROMPT,
    FRONT_PROMPT,
    SAVED,
    eventually,
    field,
    generate_free,
    lesson,
    lessons,
    open_card,
    open_prompt,
)


def test_generate_then_edit_saves_by_itself(page):
    generate_free(page, FRONT_PROMPT)
    assert page.locator(".flash").count() == 6
    (summary,) = lessons(page)
    assert lesson(page, summary["id"])["prompt"] == FRONT_PROMPT  # kept with the lesson…
    assert not [p for p in page.request.get("/api/prompts").json() if not p["builtin"]]  # …not saved as a prompt

    field(page.locator(".flash").first, "back").fill("la mamá")
    sync_api.expect(page.locator(".save-pill")).to_have_class(SAVED)
    assert lesson(page, summary["id"])["cards"][0]["back"] == "la mamá"


def test_one_empty_card_at_a_time(page):
    """ "＋ Add a card": a new card, full screen, « Que doit demander cette carte ? » (the AI
    writes it) ready to type, with a mouse; again while it is still empty (closed): no second
    one, back to it; once it says something, another one."""
    generate_free(page, FRONT_PROMPT)
    cards = page.locator(".flash")
    n = cards.count()
    add = page.get_by_role("button", name="＋ Ajouter une carte")
    add.click()
    sync_api.expect(cards).to_have_count(n + 1)
    asked = cards.last.get_by_role("textbox", name="Que doit demander cette carte ?")
    sync_api.expect(asked).to_be_focused()
    page.keyboard.press("Escape")  # closed, still empty
    sync_api.expect(page.locator(".flash.editing")).to_have_count(0)
    add.click()
    sync_api.expect(cards).to_have_count(n + 1)  # still the empty one
    sync_api.expect(asked).to_be_focused()
    cards.last.locator("textarea.front").fill("el tío")
    page.keyboard.press("Escape")
    add.click()
    sync_api.expect(cards).to_have_count(n + 2)
    sync_api.expect(cards.last.get_by_role("textbox", name="Que doit demander cette carte ?")).to_be_focused()


@pytest.mark.parametrize("page", [{"has_touch": True}], indirect=True, ids=["touch"])
def test_a_card_added_on_a_touch_screen_opens_no_keyboard(page):
    """On a touch screen, a card added (＋, at the end or in the card open) opens with nothing
    focused: no keyboard over it, « Que doit demander cette carte ? » and its 🎙️ often simpler.
    Touched, a field is typed in."""
    generate_free(page, FRONT_PROMPT)
    cards = page.locator(".flash")
    page.get_by_role("button", name="＋ Ajouter une carte").tap()
    added = cards.last
    sync_api.expect(added).to_have_class(re.compile(r"\bediting\b"))
    asked = added.get_by_role("textbox", name="Que doit demander cette carte ?")
    sync_api.expect(asked).to_be_visible()
    page.wait_for_timeout(300)  # its focus would come a frame later
    assert page.evaluate("document.activeElement.matches('textarea, input')") is False
    asked.tap()
    sync_api.expect(asked).to_be_focused()

    added.get_by_role("button", name="Ajouter une carte après celle-ci").tap()
    sync_api.expect(page.locator(".flash.editing")).to_have_count(1)
    page.wait_for_timeout(300)
    assert page.evaluate("document.activeElement.matches('textarea, input')") is False


def test_a_touched_text_is_focused_however_late_its_field_shows(page):
    """A text touched: its field shown (Alpine, at the next frame), then focused. The frames
    late (a busy phone): the field focused all the same, not before it is shown."""
    generate_free(page, FRONT_PROMPT)
    card = page.locator(".flash").first
    page.evaluate(
        """() => { const frame = window.requestAnimationFrame.bind(window);
          window.requestAnimationFrame = (f) => setTimeout(() => frame(f), 150); }"""
    )
    for name in ("back", "info"):
        field(card, name)


def test_long_back_and_info_seen_whole(page):
    """A long answer or note grows its field, as the front: nothing cut on a phone."""
    page.set_viewport_size({"width": 360, "height": 780})
    generate_free(page, FRONT_PROMPT)
    card = page.locator(".flash").first
    long = "une réponse longue, avec une précision qui ne tient pas sur une seule ligne d'un téléphone"
    for name in ("back", "info"):  # the info empty: touched by its placeholder
        box = field(card, name)
        one_line = box.bounding_box()["height"]
        box.fill(long)
        assert box.bounding_box()["height"] > 1.5 * one_line, name  # several lines
        assert box.evaluate("el => el.scrollHeight <= el.clientHeight + 1"), name  # all of it shown
        box.press("Enter")  # one line of text in Anki: Enter adds no line break
        assert box.input_value() == long


def test_no_voice_said_when_no_card_is_read(page):
    """The voice comes with the cards only when one is read: a text with gaps has no sound
    (its back is only an extra), so no voice is said for it."""
    voice = page.locator(".export-options p", has_text="Voix")
    generate_free(page, FRONT_PROMPT)
    sync_api.expect(voice).to_be_visible()
    generate_free(page, CLOZE_PROMPT)
    sync_api.expect(voice).to_be_hidden()


def test_a_card_shown_as_anki_shows_it_until_edited(page):
    """Not edited, a card is as Anki shows it: its formulas drawn, no fields. A touch on one of
    its texts edits it, full screen ("Carte 1 sur …"), the cursor there, the preview under it
    as it's typed; done (its ✕, Escape or Android's back), as Anki shows it again in the list,
    saved."""
    generate_free(page, FRONT_PROMPT)
    cards = page.locator(".flash")
    card, other = cards.nth(0), cards.nth(1)
    back = card.locator("textarea.back")
    sync_api.expect(back).to_be_hidden()
    sync_api.expect(card.locator("textarea")).to_have_count(card.locator("textarea").count())
    assert not [t for t in card.locator("textarea").all() if t.is_visible()]  # no field
    field(card, "back").fill(r"\(x^2\)")
    sync_api.expect(card.locator(".card-sheet-head")).to_contain_text("Carte 1 / ")
    box, view = card.bounding_box(), page.viewport_size
    assert box and view and (box["x"], box["y"], box["width"], box["height"]) == (0, 0, view["width"], view["height"])
    sync_api.expect(card.locator("textarea.front")).to_be_hidden()  # only the one touched
    sync_api.expect(card.locator(".math-preview.back:not(.shown) mjx-container")).to_be_visible()  # under it
    card.get_by_role("button", name="Terminé").click()  # its ✕
    shown = card.locator(".math-preview.back.shown")
    sync_api.expect(back).to_be_hidden()
    sync_api.expect(shown.locator("mjx-container")).to_be_visible()
    sync_api.expect(page.locator(".save-pill")).to_have_class(SAVED)

    shown.click()  # touched in the list: the card open, as Anki shows it (no keyboard)
    sync_api.expect(card).to_have_class(re.compile(r"\bediting\b"))
    sync_api.expect(back).to_be_hidden()
    shown.click()  # the formula touched there: edited
    sync_api.expect(back).to_be_focused()
    sync_api.expect(back).to_have_value(r"\(x^2\)")
    page.keyboard.press("Escape")
    sync_api.expect(page.locator(".flash.editing")).to_have_count(0)
    field(other, "front")  # the list back: another card edited
    assert page.evaluate("window.notosaurusBack()")  # Android's back: done with it
    sync_api.expect(page.locator(".flash.editing")).to_have_count(0)

    # ‹ ›: the previous or the next card, this one done with
    field(card, "back")
    sync_api.expect(card.get_by_role("button", name="Carte précédente")).to_be_disabled()  # the first
    card.get_by_role("button", name="Carte suivante").click()
    sync_api.expect(other).to_have_class(re.compile(r"\bediting\b"))
    sync_api.expect(other.locator(".card-sheet-head")).to_contain_text("Carte 2 / ")
    sync_api.expect(card).not_to_have_class(re.compile(r"\bediting\b"))
    other.get_by_role("button", name="Carte précédente").click()
    sync_api.expect(card).to_have_class(re.compile(r"\bediting\b"))
    page.keyboard.press("Escape")
    sync_api.expect(page.locator(".flash.editing")).to_have_count(0)

    # ✨ asks the AI: the card edited (its correction undoable meanwhile), its texts still drawn;
    # one touched shows its LaTeX, the others drawn
    open_card(card)
    sync_api.expect(card).to_have_class(re.compile(r"\bediting\b"))
    sync_api.expect(shown.locator("mjx-container")).to_be_visible()
    sync_api.expect(back).to_be_hidden()
    shown.click()
    sync_api.expect(back).to_be_focused()
    sync_api.expect(card.locator("textarea.front")).to_be_hidden()


# Whether a drawn formula holds a command MathJax doesn't know: written in red, as in Anki
UNKNOWN_IN_RED = "e => [...e.querySelectorAll('*')].some((n) => getComputedStyle(n).color === 'rgb(255, 0, 0)')"


def test_a_formula_previewed_as_anki_shows_it(page):
    """The preview draws as Anki's MathJax does: what Anki draws (chemistry, its units, an
    arc), drawn; what it doesn't know (\\R, Anki has only \\mathbb{R}), in red as there."""
    generate_free(page, FRONT_PROMPT)
    card = page.locator(".flash").first
    back = field(card, "back")
    preview = card.locator(".math-preview.back:not(.shown)")  # under the field, as it's typed
    for formula, unknown in [
        (r"\(\ce{2H2 + O2 -> 2H2O}\)", False),
        (r"\(R = 220\,\ohm\) et l'arc \(\overparen{AB}\)", False),
        (r"\(x \in \R\)", True),
    ]:
        back.fill(formula)
        sync_api.expect(preview.locator("mjx-container").first).to_be_visible()
        assert preview.evaluate(UNKNOWN_IN_RED) is unknown, formula


def test_formulas_drawn_in_the_helps_and_the_doubt(page):
    """A help's formulas drawn as the back's (its text a click away), the doubt's too."""
    generate_free(page, FRONT_PROMPT)
    page.evaluate(
        r"""Object.assign(document.querySelector('[x-data]')._x_dataStack[0].cards[0], {
            explanation: String.raw`Pour tout \(x\) de \(\mathbb{R}\)`,
            doubt: { reason: String.raw`La limite est \(+\infty\)`, front: "f", back: String.raw`\(-\infty\)` },
        })"""
    )
    card = open_card(page.locator(".flash").first)  # the helps in the card open
    help_shown = card.locator(".card-help .math-preview.shown:visible")
    sync_api.expect(help_shown.locator("mjx-container")).to_have_count(2)
    sync_api.expect(card.locator("textarea.explanation")).to_be_hidden()
    help_shown.click()
    sync_api.expect(card.locator("textarea.explanation")).to_be_focused()
    sync_api.expect(card.locator(".card-doubt mjx-container")).to_have_count(2)  # the reason's, the corrected back's


def test_formulas_drawn_in_the_info_and_the_fun_fact(page):
    """TYP-02: the info's formulas, the "did you know"'s too, drawn as the helps' (their text a
    click away), never their LaTeX shown as it is."""
    generate_free(page, FRONT_PROMPT)
    page.evaluate(
        r"""Object.assign(document.querySelector('[x-data]')._x_dataStack[0].cards[0], {
            info: String.raw`Exemple : si \(\frac{BC}{BD} = \frac{BE}{BA}\)`,
            fun_fact: String.raw`Il vaut \(\pi\) environ`,
        })"""
    )
    card = open_card(page.locator(".flash").first)  # the info in the card open
    info = card.locator(".meta .math-preview.shown:visible")
    sync_api.expect(info.locator("mjx-container")).to_have_count(1)
    sync_api.expect(card.locator("textarea.info")).to_be_hidden()
    sync_api.expect(card.locator(".fun-fact .math-preview.shown:visible mjx-container")).to_have_count(1)
    if shots := os.environ.get("NOTOSAURUS_SHOTS"):  # to look at it: a folder for the screenshot
        card.screenshot(path=f"{shots}/info-formula.png")
    info.click()
    sync_api.expect(card.locator("textarea.info")).to_be_focused()
    sync_api.expect(card.locator("textarea.info")).to_have_value(r"Exemple : si \(\frac{BC}{BD} = \frac{BE}{BA}\)")


def test_generate_again_in_place_then_undo(page):
    generate_free(page, FRONT_PROMPT)
    (first,) = lessons(page)
    open_prompt(page)
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


def test_while_waiting_what_the_ai_is_at(page, monkeypatch):
    """The waiting card says what the AI is at: slow to answer, asked again elsewhere
    (another route or model); then the cards counted as they come."""
    import asyncio

    from notosaurus_core import llm
    from notosaurus_core.providers import demo

    real, go_on = demo._demo, threading.Event()

    async def busy(s, answer, on_card):
        llm.tell({"step": "slow"})
        await asyncio.sleep(0.5)
        llm.tell({"step": "fallback"})
        await asyncio.to_thread(go_on.wait, 30)
        return await real(s, answer, on_card)

    monkeypatch.setattr(demo, "_demo", busy)
    page.goto("/")
    page.get_by_role("radio", name="✏️ Libre").click()
    page.locator("textarea[x-ref=promptText]").fill("Vocabulaire")
    page.get_by_role("button", name="✨ Générer à partir de la consigne seule").click()
    waiting = page.locator(".loading-card")
    sync_api.expect(waiting).to_contain_text("L'IA met plus de temps que d'habitude à répondre")
    sync_api.expect(waiting).to_contain_text("L'IA ne répond pas : nouvel essai par un autre chemin")
    go_on.set()
    page.locator(".flash").first.wait_for()


def test_fun_facts_as_the_settings_say(page):
    """No switch under the prompt: the fun facts come as the settings say (on at first)."""
    page.goto("/")
    sync_api.expect(page.locator(".switch.fun-facts")).to_have_count(0)
    generate_free(page, FRONT_PROMPT)
    fact = field(page.locator(".flash", has=page.locator(".fun-fact:not([style*='display: none'])")).first, "fun_fact")
    assert fact.input_value().startswith("Le savais-tu")
    assert (
        page.evaluate("Alpine.$data(document.querySelector('[x-data]')).cards.filter((c) => c.fun_fact).length") == 1
    )  # the others have none
    # A long one is seen whole, on several lines
    one_line = fact.bounding_box()["height"]
    fact.fill("Le savais-tu ? " + "Ce mot vient du latin et se retrouve dans beaucoup de langues. " * 3)
    assert fact.bounding_box()["height"] > 1.5 * one_line
    assert fact.evaluate("el => el.scrollHeight <= el.clientHeight + 1")


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


def test_cancel_while_the_lesson_is_corrected(page):
    """ "Cancel" in the waiting card while the AI corrects the lesson: the server asked to
    stop this correction (its job), the cards as they were, the instruction kept, no error."""
    generate_free(page, FRONT_PROMPT)
    before = [c.input_value() for c in page.locator(".flash textarea").all()]
    held, cancelled = [], []

    def cancel_asked(route):
        cancelled.append(route.request.url)
        route.fulfill(json={"cancelled": True})

    page.route("**/api/lessons/*/revise*", lambda route: held.append(route))  # the AI still correcting
    page.route("**/api/generations/*/cancel", cancel_asked)
    field = page.locator(".revise textarea")
    field.fill("supprime la dernière carte")
    page.locator(".revise .btn.primary").click()
    cancel = page.locator(".loading-card .btn")
    sync_api.expect(cancel).to_have_text("Annuler")
    cancel.click()
    sync_api.expect(cancel).to_have_text("Annulation…")
    (route,) = held
    job = re.search(r"[?&]job=(\w+)", route.request.url).group(1)
    assert cancelled == [f"{page.url.split('#')[0].rstrip('/')}/api/generations/{job}/cancel"]
    route.fulfill(content_type="application/x-ndjson", body='{"cancelled": true}\n')
    sync_api.expect(page.locator(".loading-card")).to_be_hidden()
    sync_api.expect(page.locator(".error")).to_be_hidden()
    assert [c.input_value() for c in page.locator(".flash textarea").all()] == before
    assert field.input_value() == "supprime la dernière carte"


def test_cancel_while_a_card_is_corrected(page):
    """The card's "Cancel" while the AI corrects it: this correction dropped at once, its
    field closed, the server asked to stop it (its job); an answer coming anyway changes
    nothing: the card as it was, no error."""
    generate_free(page, FRONT_PROMPT)
    first = page.locator(".flash").first
    back = first.locator("textarea").nth(1)
    before = back.input_value()
    held, cancelled = [], []

    def cancel_asked(route):
        cancelled.append(route.request.url)
        route.fulfill(json={"cancelled": True})

    page.route("**/api/lessons/*/fix-card*", lambda route: held.append(route))
    page.route("**/api/generations/*/cancel", cancel_asked)
    open_card(first)
    field = first.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?")
    field.fill("la mamá")
    field.press("Enter")
    cancel = first.locator(".card-fix .btn.soft")
    sync_api.expect(cancel).to_be_enabled()  # while the AI writes too
    cancel.click()
    sync_api.expect(field).to_have_value("")  # dropped at once, the field empty again
    sync_api.expect(cancel).to_be_hidden()
    (route,) = held
    job = re.search(r"[?&]job=(\w+)", route.request.url).group(1)
    assert cancelled == [f"{page.url.split('#')[0].rstrip('/')}/api/generations/{job}/cancel"]
    card = {"front": "la mère", "back": "la mamá"}
    route.fulfill(json={"card": card, "summary": "Corrigée."})  # done just before it was stopped
    page.wait_for_timeout(300)
    assert back.input_value() == before
    sync_api.expect(first.locator(".card-fixed")).to_be_hidden()
    sync_api.expect(page.locator(".error")).to_be_hidden()


def test_cancel_while_a_card_correction_is_dictated(page):
    """The card's ✕ while its correction is being dictated: not taken for a tap elsewhere
    (which would only stop listening and write it): the microphone stopped, what it heard
    dropped, the card closed, no error."""
    page.route("**/api/config", lambda route: route.fulfill(json={**route.fetch().json(), "dictation": True}))
    page.route("**/api/dictation/start", lambda route: route.fulfill(json={"listening": True, "live": True}))
    page.route("**/api/dictation/heard", lambda route: route.fulfill(json={"text": "la réponse est"}))
    stopped = []
    page.route(
        "**/api/dictation/stop", lambda route: (stopped.append(1), route.fulfill(json={"text": "la réponse est"}))
    )
    generate_free(page, FRONT_PROMPT)
    first = page.locator(".flash").first
    back = first.locator("textarea").nth(1)
    before = back.input_value()
    open_card(first)
    field = first.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?")
    first.locator(".card-fix button.mic").click()
    sync_api.expect(field).to_have_value("la réponse est")  # heard as it comes
    first.get_by_role("button", name="Terminé").click()
    sync_api.expect(field).to_be_hidden()
    sync_api.expect(page.locator(".card-fix")).to_have_count(0)
    page.wait_for_timeout(300)
    assert stopped == [1] and back.input_value() == before
    sync_api.expect(page.locator(".error")).to_be_hidden()


def test_multiple_choice_wrong_answers_edited(page):
    generate_free(page, "QCM sur la Révolution")
    first = page.locator(".flash").first
    field(first, "back")  # edited: its wrong answers can be added and removed
    sync_api.expect(first.locator(".choice textarea")).to_have_count(3)
    assert first.locator("textarea.back").get_attribute("placeholder") == "Bonne réponse"
    first.get_by_role("button", name="+ mauvaise réponse").click()
    first.locator(".choice textarea").nth(3).fill("1830")
    first.get_by_role("button", name="Retirer cette réponse").first.click()  # 1715 goes
    sync_api.expect(page.locator(".save-pill")).to_have_class(SAVED)
    (summary,) = lessons(page)
    assert lesson(page, summary["id"])["cards"][0]["choices"] == ["1799", "1804", "1830"]


def test_a_card_explained_then_its_follow_ups(page):
    generate_free(page, "QCM sur la Révolution")
    card = open_card(page.locator(".flash").first)
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
    card = open_card(page.locator(".flash").first)
    card.get_by_role("button", name="Plus d'actions").click()
    card.get_by_role("button", name="Signaler").click()
    sheet = page.get_by_role("dialog", name="Signaler un contenu")
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
    sheet.get_by_label("Choquant ou inapproprié").check()
    # The whole card as seen: its texts and its explanation, shown
    sync_api.expect(sheet.locator(".report-preview")).to_contain_text("explain: (démo, explain)")
    sync_api.expect(sheet.locator(".report-preview")).to_contain_text("En quelle année")
    send.click()
    sync_api.expect(sheet).to_contain_text("Merci")
    assert sent[1]["kind"] == "card" and sent[1]["reason"] == "offensive" and "Front: " in sent[1]["content"]


def test_a_card_reported_with_its_picture_and_dropped(page):
    """A card with a figure reported: the whole card and its figure sent; then the figure
    alone removed, the card kept."""
    sent = []
    page.route("**/api/config", lambda route: route.fulfill(json={**route.fetch().json(), "report": True}))
    page.route(
        "**/api/lessons/*/report",
        lambda route: (sent.append(route.request.post_data_json), route.fulfill(json={"received": True})),
    )
    generate_free(page, "Le triangle rectangle (géométrie)")
    card = open_card(page.locator(".flash").first)
    sync_api.expect(card.locator(".card-picture img:not(.first):visible")).to_be_visible()
    card.get_by_role("button", name="Plus d'actions").click()
    card.get_by_role("button", name="Signaler").click()
    sheet = page.get_by_role("dialog", name="Signaler un contenu")
    sheet.get_by_label("Faux").check()
    sync_api.expect(sheet).to_contain_text("L'image est envoyée aussi")
    sync_api.expect(sheet.locator(".report-preview")).to_contain_text("Picture: ")
    sheet.get_by_role("button", name="Envoyer").click()
    sync_api.expect(sheet).to_contain_text("Merci")
    (report,) = sent
    assert report["picture"].startswith("data:image/svg+xml;base64,") and report["content"].startswith("Front: ")
    sheet.get_by_role("button", name="Retirer l'image").click()
    sync_api.expect(card.locator(".card-picture img:visible")).to_have_count(0)
    sync_api.expect(page.locator(".flash")).to_have_count(3)  # the card kept


def test_an_option_card_is_its_radio_all_over(page):
    """A finger anywhere on a choice's card (TalkBack's explore by touch) is on its radio,
    said with its state, not on its text alone."""
    page.goto("/")
    card = (
        '<label class="option" id="zz"><input type="radio" name="zz" checked>'
        "<strong>Ici</strong><small>Le détail</small></label>"
    )
    page.evaluate("(html) => document.body.insertAdjacentHTML('afterbegin', html)", card)
    for part in ("#zz strong", "#zz small", "#zz"):
        box = page.locator(part).bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        assert page.evaluate("([x, y]) => document.elementFromPoint(x, y).tagName", [x, y]) == "INPUT", part
    sync_api.expect(page.get_by_role("radio", name="Ici Le détail")).to_be_checked()


def test_helps_as_tall_as_their_text_never_dragged(page):
    """The explanation and the mnemonic as tall as their text, its lines kept (Enter a new line,
    a <br> in Anki), with no handle to drag: a scroll on a phone caught it, the field grew."""
    page.set_viewport_size({"width": 360, "height": 780})
    generate_free(page, FRONT_PROMPT)
    for name in ("explanation", "mnemonic"):
        with_it = page.locator(".card-help:not([style*='display: none'])", has=page.locator(f"textarea.{name}"))
        box = field(page.locator(".flash", has=with_it).first, name)
        assert box.evaluate("el => getComputedStyle(el).resize") == "none", name
        one_line = box.bounding_box()["height"]
        box.fill("Une première ligne")
        box.press("End")
        box.press("Enter")
        box.type(
            "puis une seconde, assez longue pour ne pas tenir sur une ligne d'un téléphone, même la carte en grand"
        )
        assert "\n" in box.input_value(), name  # its line break kept
        assert box.bounding_box()["height"] > 2.5 * one_line, name  # several lines
        assert box.evaluate("el => el.scrollHeight <= el.clientHeight + 1"), name  # all of it shown
        page.keyboard.press("Escape")  # the list back, for the next one


def test_helps_as_the_settings_say(page):
    """No switch under the prompt: the helps come as the settings say (on at first)."""
    page.goto("/")
    sync_api.expect(page.locator(".switch.helps")).to_have_count(0)
    generate_free(page, FRONT_PROMPT)
    sync_api.expect(page.locator(".card-help textarea").first).to_have_value("(démo) Pourquoi c'est la réponse.")
    helps = page.evaluate(
        "Alpine.$data(document.querySelector('[x-data]')).cards"
        ".map((c) => [c.explanation, c.mnemonic].filter(Boolean).length)"
    )
    assert sum(helps) == 2  # an explanation, a mnemonic: the others none


def test_a_cards_sub_deck_under_its_info_or_offered(page):
    """A card's info written: its whole line, the sub-deck under it (beside it, the info was
    squeezed into a narrow column, seen 2026-11-22). No sub-deck: "+ sous-paquet", as
    "+ info", not a pill that reads as a sub-deck named so."""
    page.set_viewport_size({"width": 390, "height": 844})
    generate_free(page, FRONT_PROMPT)
    page.evaluate(
        """() => Object.assign(Alpine.$data(document.querySelector('[x-data]')).cards[0], {
            info: 'Une précision assez longue pour tenir sur plusieurs lignes d\\'un téléphone, sans être écrasée.',
            subdeck: 'Fonctions de référence de Seconde et Première' })"""
    )
    card = open_card(page.locator(".flash").first)
    info, tag = card.locator(".meta .math-preview.info"), card.locator(".subdeck-tag")
    sync_api.expect(tag).to_have_text("🗂 Fonctions de référence de Seconde et Première")
    meta = card.locator(".meta").bounding_box()
    assert info.bounding_box()["width"] > 0.9 * meta["width"]  # its whole line
    assert tag.bounding_box()["y"] >= info.bounding_box()["y"] + info.bounding_box()["height"] - 1  # under it

    page.evaluate("() => { Alpine.$data(document.querySelector('[x-data]')).cards[0].subdeck = ''; }")
    sync_api.expect(tag).to_have_text("+ sous-paquet")
    sync_api.expect(tag).to_have_class(re.compile(r"\bempty\b"))


def test_one_card_corrected_by_the_ai(page):
    """The card open, its "✨ Correct with AI" field at the bottom; the demo AI makes its back
    what was asked; the card marked changed, saved, "↩ Undo" puts it back. The others
    untouched. Escape closes the card."""
    generate_free(page, FRONT_PROMPT)
    cards = page.locator(".flash")
    first, second = cards.nth(0), cards.nth(1)
    back = first.locator("textarea").nth(1)
    before, other = back.input_value(), second.locator("textarea").nth(1).input_value()
    open_card(first)
    field = first.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?")
    field.focus()
    page.keyboard.press("Escape")
    sync_api.expect(field).to_be_hidden()

    open_card(first)
    field.fill("la mamá")
    field.press("Enter")
    sync_api.expect(back).to_have_value("la mamá")
    sync_api.expect(field).to_have_value("")  # still there, for another one
    sync_api.expect(first.locator(".card-fixed")).to_contain_text("Carte corrigée (démo).")
    sync_api.expect(first.locator(".flash-badge")).to_be_visible()  # marked changed
    assert second.locator("textarea").nth(1).input_value() == other
    sync_api.expect(page.locator(".save-pill")).to_have_class(SAVED)
    (summary,) = lessons(page)
    assert lesson(page, summary["id"])["cards"][0]["back"] == "la mamá"

    first.get_by_role("button", name="↩ Annuler").click()
    sync_api.expect(back).to_have_value(before)
    sync_api.expect(first.locator(".card-fixed")).to_be_hidden()
    eventually(
        page, lambda: lesson(page, summary["id"])["cards"][0]["back"] == before, "the card as it was, saved again"
    )


def _said_with_a_formula(
    page, url, field, said=r"Ajout de l'intégrale \(\int_{1}^{4} f(x)\,\mathrm{d}x\) sur la figure."
):
    """The AI's answer at `url` as it came, its `field` (what it says it did) written `said`:
    by default with a formula, as it writes them: \\( … \\)."""

    def answer(route):
        response = route.fetch()
        kind = response.headers.get("content-type", "")
        if "ndjson" not in kind:
            route.fulfill(json={**response.json(), field: said})
            return
        items = [json.loads(line) for line in response.text().splitlines() if line.strip()]
        for item in items:
            if "result" in item:
                item["result"][field] = said
        route.fulfill(body="".join(json.dumps(item) + "\n" for item in items), content_type=kind)

    page.route(url, answer)


def _drawn(where):
    sync_api.expect(where.locator("mjx-container")).to_be_visible()
    sync_api.expect(where).not_to_contain_text("\\int")  # not its text


def test_what_the_ai_says_it_did_shows_its_formulas(page):
    """What a correction says it did, and an explanation, show their formulas drawn as the
    cards do, not their LaTeX (seen 2026-11-20: "l'intégrale \\(\\int_{1}^{4} …\\)")."""
    generate_free(page, FRONT_PROMPT)
    first = page.locator(".flash").first

    _said_with_a_formula(page, "**/api/lessons/*/fix-card*", "summary")
    open_card(first)
    field = first.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?")
    field.fill("la mamá")
    field.press("Enter")
    _drawn(first.locator(".card-fixed"))

    _said_with_a_formula(page, "**/api/lessons/*/explain", "text")
    first.get_by_role("button", name="Expliquer cette carte").click()
    _drawn(first.locator(".explain-block").first)
    first.get_by_role("button", name="Terminé").click()  # the list back

    _said_with_a_formula(page, "**/api/lessons/*/revise*", "summary")
    page.locator(".revise textarea").fill("plus court")
    page.locator(".revise .btn.primary").click()
    _drawn(page.locator(".revision-result"))


def test_a_card_corrected_then_undone_shows_its_figure_again(page):
    """A card's correction that draws its figure again, undone while the card is edited: its
    figure as it was, shown (it was removed as soon as the new one was drawn: the undone card
    showed a broken picture, its description instead, 2026-11-20). Done with the card, the
    one the undone correction drew is removed, the card's kept."""
    generate_free(page, "Le triangle rectangle (géométrie)")
    card = page.locator(".flash").first
    img = card.locator(".card-picture img:not(.first):visible")
    sync_api.expect(img).to_be_visible()
    before = img.get_attribute("src")

    def figure_wrong(route):  # the AI says what is wrong in the figure: drawn again, with another label
        answer = route.fetch().json()
        answer["card"]["figure"] = "Un triangle rectangle, son côté « côté opposé » marqué"
        route.fulfill(json={**answer, "figure_problem": "Le côté opposé n'est pas marqué"})

    page.route("**/api/lessons/*/fix-card*", figure_wrong)
    open_card(card)
    field = card.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?")
    field.fill("marque le côté opposé")
    field.press("Enter")
    sync_api.expect(img).not_to_have_attribute("src", before)  # drawn again
    drawn = img.get_attribute("src")
    sync_api.expect(page.locator(".save-pill")).to_have_class(SAVED)

    card.get_by_role("button", name="↩ Annuler").click()
    sync_api.expect(img).to_have_attribute("src", before)
    assert page.request.get(before).ok  # still there (the browser's cache would show it anyway: a reload wouldn't)
    page.wait_for_function("img => img.complete && img.naturalWidth > 0", arg=img.element_handle())  # not broken
    sync_api.expect(page.locator(".save-pill")).to_have_class(SAVED)

    assert page.request.get(drawn).ok  # kept until the card is done with
    card.get_by_role("button", name="Terminé").click()  # its ✕
    eventually(page, lambda: page.request.get(drawn).status == 404, f"{drawn} kept")  # the undone one's: gone
    assert page.request.get(before).ok  # the card's: kept


@pytest.mark.parametrize("page", [{"has_touch": True}], indirect=True, ids=["touch"])
def test_a_card_corrected_on_a_touch_screen_opens_no_keyboard(page):
    """On a touch screen, a card touched in the list opens with its correction's field
    unfocused: no keyboard over the card, the 🎙️ beside it often simpler. Touched, the field is
    typed in."""
    generate_free(page, FRONT_PROMPT)
    first = page.locator(".flash").first
    first.locator(".flash-body").tap(position={"x": 4, "y": 4})
    field = first.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?")
    sync_api.expect(field).to_be_visible()
    sync_api.expect(field).not_to_be_focused()
    field.tap()
    sync_api.expect(field).to_be_focused()


def _swipe(target, dx: float, dy: float = 0, *, let_go: bool = True) -> None:
    """One finger drawn across `target` from its middle, by (dx, dy), in a few moves; let go
    (or still down: `let_go` False, then _let_go)."""
    target.evaluate(
        """(el, [dx, dy, letGo]) => {
          const r = el.getBoundingClientRect(), x = r.x + r.width / 2, y = r.y + r.height / 2;
          const at = (f) => new Touch({ identifier: 1, target: el, clientX: x + f * dx, clientY: y + f * dy });
          const send = (type, touch, down) => el.dispatchEvent(new TouchEvent(type,
            { bubbles: true, cancelable: true, touches: down ? [touch] : [], changedTouches: [touch] }));
          send("touchstart", at(0), true);
          for (const f of [0.25, 0.5, 1]) send("touchmove", at(f), true);
          window._swipeEnd = () => send("touchend", at(1), false);
          if (letGo) window._swipeEnd();
        }""",
        [dx, dy, let_go],
    )


def _let_go(page) -> None:
    page.evaluate("window._swipeEnd()")


@pytest.mark.parametrize("page", [{"has_touch": True}], indirect=True, ids=["touch"])
def test_a_card_open_swiped_to_the_next(page):
    """The card open full screen follows a finger swiped sideways, the next one beside it (to
    the left: no background seen between them); let go far enough: the next card, this one done
    with; to the right, the previous one. Not far enough, they come back. From a field too (its
    correction's): a quick stroke selects nothing there. A stroke up or down (a scroll) moves
    nothing."""
    generate_free(page, FRONT_PROMPT)
    cards = page.locator(".flash")
    first, second = cards.nth(0), cards.nth(1)
    first.locator(".flash-body").tap(position={"x": 4, "y": 4})  # opened from the list
    sync_api.expect(first).to_have_class(re.compile(r"\bediting\b"))
    front = first.locator(".front-row")
    moved = "el => el.style.transform"
    _swipe(front, -30, -120, let_go=False)  # a scroll
    assert first.evaluate(moved) == ""
    _let_go(page)
    _swipe(first.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?"), -150)  # from a field
    sync_api.expect(second).to_have_class(re.compile(r"\bediting\b"))
    _swipe(second.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?"), 150)
    sync_api.expect(first).to_have_class(re.compile(r"\bediting\b"))
    _swipe(front, -40, let_go=False)  # followed, the next one beside it…
    assert first.evaluate(moved) == "translateX(-40px)"
    sync_api.expect(second).to_have_class(re.compile(r"\bpeek\b"))
    # …shown as it will be once edited: its correction's field, its empty texts offered
    sync_api.expect(second.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?")).to_be_visible()
    sync_api.expect(second.locator(".card-sheet-head")).to_contain_text("Carte 2 / ")
    a, b = first.bounding_box(), second.bounding_box()
    assert a and b and b["x"] == pytest.approx(a["x"] + a["width"], abs=1) and b["y"] == a["y"]
    _let_go(page)  # …not far enough: back
    sync_api.expect(first).to_have_attribute("style", re.compile(r"^(?!.*translateX)"))
    sync_api.expect(second).not_to_have_class(re.compile(r"\bpeek\b"))
    sync_api.expect(second.locator(".card-fix")).to_have_count(0)  # not edited: without it again
    sync_api.expect(first).to_have_class(re.compile(r"\bediting\b"))
    _swipe(front, -150)
    sync_api.expect(second).to_have_class(re.compile(r"\bediting\b"))
    sync_api.expect(second).not_to_have_class(re.compile(r"\bpeek\b"))
    sync_api.expect(first).not_to_have_class(re.compile(r"\bediting\b"))
    _swipe(second.locator(".front-row"), 150)
    sync_api.expect(first).to_have_class(re.compile(r"\bediting\b"))
    _swipe(front, 150)  # the first: none before it
    page.wait_for_timeout(300)
    sync_api.expect(first).to_have_class(re.compile(r"\bediting\b"))


def test_a_card_just_added_written_by_the_ai(page):
    """A card just added (empty): its field asks what it should ask, the demo AI writes its
    back from that. Filled, it is corrected again, no more written."""
    generate_free(page, FRONT_PROMPT)
    page.get_by_role("button", name="＋ Ajouter une carte").click()
    added = page.locator(".flash").last
    field = added.get_by_role("textbox", name="Que doit demander cette carte ?")
    field.fill("le grand-père en espagnol")
    added.get_by_role("button", name="Écrire", exact=True).click()
    sync_api.expect(added.locator("textarea").nth(1)).to_have_value("le grand-père en espagnol")
    sync_api.expect(added.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?")).to_be_visible()


def test_a_card_correction_dictated(page):
    """The Android app's page: the card's field has its 🎤, heard as a correction."""
    stopped = []
    page.route("**/api/config", lambda route: route.fulfill(json={**route.fetch().json(), "dictation": True}))
    page.route("**/api/dictation/start", lambda route: route.fulfill(json={"listening": True}))
    page.route(
        "**/api/dictation/stop",
        lambda route: (stopped.append(route.request.post_data_json), route.fulfill(json={"text": "plutôt la mamá"})),
    )
    generate_free(page, FRONT_PROMPT)
    first = page.locator(".flash").first
    open_card(first)
    fix = first.locator(".card-fix")
    fix.get_by_role("button", name="Dicter").click()
    fix.get_by_role("button", name="Arrêter et écrire le texte").click()
    sync_api.expect(fix.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?")).to_have_value("plutôt la mamá")
    assert stopped == [{"kind": "correction"}]


def test_a_lesson_that_looks_wrong_corrected_or_kept(page):
    """A pupil's notes with a wrong date: the card says what the lesson says, with why it
    looks wrong; "Correct" takes the AI's correction, "Keep" keeps the lesson."""
    generate_free(page, "Les dates d'histoire")
    wrong = page.locator(".flash").nth(1)
    sync_api.expect(wrong.locator(".card-doubt")).to_contain_text("1915 est l'année du génocide arménien")
    sync_api.expect(page.locator(".flash").first.locator(".card-doubt")).to_be_hidden()
    wrong.get_by_role("button", name="Corriger", exact=True).click()
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


def test_the_list_compact_a_card_touched_opens(page):
    """The list compact: a card's front and back, none of its buttons nor its helps; touched
    anywhere, it opens full screen with them (nothing focused: no keyboard), its « ✨ Corriger
    avec l'IA » field at the bottom. « ▶ Relire carte par carte » opens the first."""
    generate_free(page, FRONT_PROMPT)
    first = page.locator(".flash").first
    sync_api.expect(first.get_by_role("button", name="Plus d'actions")).to_be_hidden()
    sync_api.expect(first.locator(".flash-actions button:visible")).to_have_count(1)  # 🔊 alone…
    first.locator(".flash-actions .listen").click()  # …heard there, the card not opened
    sync_api.expect(first).not_to_have_class(re.compile(r"\bediting\b"))
    sync_api.expect(first.locator(".card-help:visible")).to_have_count(0)
    sync_api.expect(first.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?")).to_have_count(0)
    first.locator(".math-preview.back.shown").click()  # its back: the card open, not its back edited
    sync_api.expect(first).to_have_class(re.compile(r"\bediting\b"))
    sync_api.expect(first.locator("textarea.back")).to_be_hidden()
    more = first.get_by_role("button", name="Plus d'actions")
    sync_api.expect(more).to_be_visible()
    # Its actions at its top right, its front below them the whole width
    m, front, card = more.bounding_box(), first.locator(".front-row").bounding_box(), first.bounding_box()
    assert m and front and card and m["y"] + m["height"] <= front["y"] and m["x"] + m["width"] > card["width"] - 30
    sync_api.expect(first.locator(".card-help:visible").first).to_be_visible()
    sync_api.expect(first.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?")).to_be_visible()
    page.keyboard.press("Escape")
    sync_api.expect(page.locator(".flash.editing")).to_have_count(0)
    page.get_by_role("button", name="▶ Relire carte par carte").click()
    sync_api.expect(first).to_have_class(re.compile(r"\bediting\b"))


def test_cards_added_from_the_card_open_and_the_lessons_end(page):
    """＋ in the card open: an empty card just after it, open, ready to write; left
    empty, it goes. › after the last card: the lesson's end, how many cards were looked over,
    a card to add there (kept once written)."""
    generate_free(page, FRONT_PROMPT)
    cards = page.locator(".flash")
    n = cards.count()
    open_card(cards.first).get_by_role("button", name="Ajouter une carte après celle-ci").click()
    sync_api.expect(cards).to_have_count(n + 1)
    added = cards.nth(1)
    sync_api.expect(added).to_have_class(re.compile(r"\bediting\b"))
    sync_api.expect(added.locator(".card-sheet-head")).to_contain_text("Carte 2 / ")
    sync_api.expect(added.get_by_role("textbox", name="Que doit demander cette carte ?")).to_be_focused()
    page.keyboard.press("Escape")  # left empty: gone
    sync_api.expect(cards).to_have_count(n)

    open_card(cards.last).get_by_role("button", name="Carte suivante").click()
    end = page.locator(".lesson-end")
    sync_api.expect(end).to_contain_text(f"✓ {n} cartes relues")
    sync_api.expect(page.locator(".flash.editing")).to_have_count(1)  # the end, alone
    end.get_by_role("button", name="＋ Ajouter une carte").click()
    sync_api.expect(end).to_have_count(0)
    added = cards.nth(n)
    sync_api.expect(added).to_have_class(re.compile(r"\bediting\b"))
    added.locator("textarea.front").fill("el tío")
    page.keyboard.press("Escape")
    sync_api.expect(cards).to_have_count(n + 1)  # written: kept, last
    sync_api.expect(cards.last).to_contain_text("el tío")


def test_the_correction_field_at_the_bottom_out_of_the_way_while_typing(page):
    """The card open: its « ✨ Corriger avec l'IA » field at the very bottom of the screen (nothing
    seen below it), a short card's too (always in the same place), « Corriger » at its right as a
    message is sent; hidden while one of its texts is typed (the keyboard up), back once left."""
    page.set_viewport_size({"width": 360, "height": 780})
    generate_free(page, FRONT_PROMPT)
    card = open_card(page.locator(".flash").first)
    fix = card.locator(".card-fix")
    box = fix.bounding_box()
    assert box and box["y"] + box["height"] == pytest.approx(780, abs=1)  # at the very bottom
    text = card.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?").bounding_box()
    send = card.get_by_role("button", name="Corriger", exact=True).bounding_box()
    assert text and send and send["x"] >= text["x"] + text["width"]  # at its right…
    assert send["y"] < text["y"] + text["height"] and send["y"] + send["height"] > text["y"]  # …on its line
    field(card, "back")
    sync_api.expect(fix).to_be_hidden()
    card.locator(".card-sheet-head span").click()  # the text left
    sync_api.expect(fix).to_be_visible()


def test_the_list_shows_a_picture_where_anki_does(page):
    """In the compact list, a card's picture where Anki shows it: above its front (not beside
    its texts), or after its back."""
    page.set_viewport_size({"width": 360, "height": 780})
    generate_free(page, "Le triangle rectangle (géométrie)")
    sync_api.expect(page.locator(".flash .drawing:visible")).to_have_count(0)  # every one drawn
    page.wait_for_function("[...document.querySelectorAll('.flash .card-picture img')].every((i) => i.complete)")
    first = page.locator(".flash").first
    pic = first.locator(".card-picture img:visible").bounding_box()
    front = first.locator(".front-row").bounding_box()
    assert pic and front and pic["y"] + pic["height"] / 2 < front["y"]  # above it (not beside)
    tangent = page.locator(".flash", has_text="tangente")
    pic = tangent.locator(".card-picture.on-back img:visible").bounding_box()
    back = tangent.locator(".math-preview.back.shown").bounding_box()
    assert back and pic and pic["y"] + pic["height"] / 2 > back["y"] + back["height"]  # after it


def test_what_a_lesson_correction_did_reads_beside_or_above_its_buttons(page):
    """What a quick correction of the lesson did, on a phone, beside ↩ Undo and 🎯 Again
    carefully: read in lines of several words, under no button (seen 2026-11-21: a word a line,
    the buttons over it)."""
    page.set_viewport_size({"width": 412, "height": 915})
    generate_free(page, FRONT_PROMPT)

    said = (
        "Ajout de 8 cartes de questions-réponses sur les notions clés de la leçon (caryotype, "
        "chromosomes homologues, gènes et allèles)"
    )
    _said_with_a_formula(page, "**/api/lessons/*/revise*", "summary", said)
    page.locator(".revise textarea").fill("plus court")
    page.locator(".revise .btn.primary").click()
    result = page.locator(".revision-result")
    sync_api.expect(result.get_by_role("button", name="🎯 Refaire avec soin")).to_be_visible()
    layout = result.evaluate(
        """(r) => {
          const text = r.querySelector('strong');
          const box = (e) => e.getBoundingClientRect();
          const t = box(text);
          const over = [...r.querySelectorAll('button')].filter((b) => b.offsetParent).some((b) => {
            const o = box(b);
            return o.left < t.right && o.right > t.left && o.top < t.bottom && o.bottom > t.top;
          });
          const lines = t.height / parseFloat(getComputedStyle(text).lineHeight);
          return { over, lines, cut: text.scrollWidth > text.clientWidth + 1, width: t.width };
        }"""
    )
    assert not layout["over"], layout  # no button over the text
    assert not layout["cut"], layout
    # Several words a line (not one): counted in words, as the lines' number depends on the fonts
    # (5 lines on CI's Chrome where 4 here, the same width)
    assert len(said.split()) / layout["lines"] >= 3, layout
