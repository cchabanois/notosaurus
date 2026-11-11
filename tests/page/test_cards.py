"""Step 3, the cards: made, edited and saved, formulas, made again, corrected and explained by
the AI, reported."""

import os
import re
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from page.support import (  # noqa: E402
    CLOZE_PROMPT,
    FRONT_PROMPT,
    SAVED,
    generate_free,
    lesson,
    lessons,
    open_prompt,
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


def test_one_empty_card_at_a_time(page):
    """ "＋ Add a card": a new card, its front ready to type; again while it is still empty:
    no second one, back to it; once it says something, another one."""
    generate_free(page, FRONT_PROMPT)
    cards = page.locator(".flash")
    n = cards.count()
    add = page.get_by_role("button", name="＋ Ajouter une carte")
    add.click()
    sync_api.expect(cards).to_have_count(n + 1)
    front = cards.last.locator("textarea.front")
    sync_api.expect(front).to_be_focused()
    page.locator(".field.deck input").click()  # elsewhere
    add.click()
    sync_api.expect(cards).to_have_count(n + 1)  # still the empty one
    sync_api.expect(front).to_be_focused()
    front.fill("el tío")
    add.click()
    sync_api.expect(cards).to_have_count(n + 2)
    sync_api.expect(cards.last.locator("textarea.front")).to_be_focused()


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


def test_no_voice_said_when_no_card_is_read(page):
    """The voice comes with the cards only when one is read: a text with gaps has no sound
    (its back is only an extra), so no voice is said for it."""
    voice = page.locator(".export-options p", has_text="Voix")
    generate_free(page, FRONT_PROMPT)
    sync_api.expect(voice).to_be_visible()
    generate_free(page, CLOZE_PROMPT)
    sync_api.expect(voice).to_be_hidden()


def test_a_formula_shown_once_its_text_while_edited(page):
    """A formula: only as the card shows it; a click shows its text to edit, the preview under
    it as it's typed; out of it, the formula alone again."""
    generate_free(page, FRONT_PROMPT)
    card = page.locator(".flash").first
    back = card.locator("textarea.back")
    back.fill(r"\(x^2\)")
    card.locator("textarea.front").click()  # out of the back
    shown = card.locator(".math-preview.back.shown")
    sync_api.expect(shown).to_be_visible()
    sync_api.expect(back).to_be_hidden()
    sync_api.expect(shown.locator("mjx-container")).to_be_visible()
    shown.click()
    sync_api.expect(back).to_be_focused()
    sync_api.expect(back).to_have_value(r"\(x^2\)")
    sync_api.expect(card.locator(".math-preview.back:not(.shown)")).to_be_visible()  # the preview, under it
    card.locator("textarea.front").click()
    sync_api.expect(back).to_be_hidden()
    sync_api.expect(page.locator(".save-pill")).to_have_class(SAVED)


# Whether a drawn formula holds a command MathJax doesn't know: written in red, as in Anki
UNKNOWN_IN_RED = "e => [...e.querySelectorAll('*')].some((n) => getComputedStyle(n).color === 'rgb(255, 0, 0)')"


def test_a_formula_previewed_as_anki_shows_it(page):
    """The preview draws as Anki's MathJax does: what Anki draws (chemistry, its units, an
    arc), drawn; what it doesn't know (\\R, Anki has only \\mathbb{R}), in red as there."""
    generate_free(page, FRONT_PROMPT)
    card = page.locator(".flash").first
    back = card.locator("textarea.back")
    shown = card.locator(".math-preview.back.shown")
    for formula, unknown in [
        (r"\(\ce{2H2 + O2 -> 2H2O}\)", False),
        (r"\(R = 220\,\ohm\) et l'arc \(\overparen{AB}\)", False),
        (r"\(x \in \R\)", True),
    ]:
        if back.is_hidden():
            shown.click()
        back.fill(formula)
        card.locator("textarea.front").click()  # out of the back
        sync_api.expect(shown.locator("mjx-container").first).to_be_visible()
        assert shown.evaluate(UNKNOWN_IN_RED) is unknown, formula


def test_formulas_drawn_in_the_helps_and_the_doubt(page):
    """A help's formulas drawn as the back's (its text a click away), the doubt's too."""
    generate_free(page, FRONT_PROMPT)
    page.evaluate(
        r"""Object.assign(document.querySelector('[x-data]')._x_dataStack[0].cards[0], {
            explanation: String.raw`Pour tout \(x\) de \(\mathbb{R}\)`,
            doubt: { reason: String.raw`La limite est \(+\infty\)`, front: "f", back: String.raw`\(-\infty\)` },
        })"""
    )
    card = page.locator(".flash").first
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
    card = page.locator(".flash").first
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
    fact = page.locator(".flash .fun-fact textarea").first
    sync_api.expect(fact).to_be_visible()
    assert fact.input_value().startswith("Le savais-tu")
    sync_api.expect(page.locator(".flash .fun-fact:visible")).to_have_count(1)  # the others have none
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
    """The card's "Cancel" while the AI corrects it: the server asked to stop it (its job),
    the card as it was, its field open with the instruction, no error."""
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
    first.get_by_role("button", name="Plus d'actions").click()
    first.get_by_role("button", name="✨ Corriger cette carte").click()
    field = first.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?")
    field.fill("la mamá")
    field.press("Enter")
    cancel = first.locator(".card-fix .btn.soft")
    sync_api.expect(cancel).to_be_enabled()  # while the AI writes too
    cancel.click()
    sync_api.expect(cancel).to_have_text("Annulation…")
    (route,) = held
    job = re.search(r"[?&]job=(\w+)", route.request.url).group(1)
    assert cancelled == [f"{page.url.split('#')[0].rstrip('/')}/api/generations/{job}/cancel"]
    route.fulfill(status=409, json={"detail": {"code": "extract.cancelled", "params": {}}})
    sync_api.expect(cancel).to_have_text("Annuler")
    sync_api.expect(field).to_be_enabled()
    assert field.input_value() == "la mamá" and back.input_value() == before
    sync_api.expect(page.locator(".error")).to_be_hidden()
    cancel.click()  # not busy: closes the field
    sync_api.expect(field).to_be_hidden()


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
    card = page.locator(".flash").first
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
    for field in ("textarea.explanation", "textarea.mnemonic"):
        box = page.locator(f".card-help:visible {field}").first
        assert box.evaluate("el => getComputedStyle(el).resize") == "none", field
        one_line = box.bounding_box()["height"]
        box.fill("Une première ligne")
        box.press("End")
        box.press("Enter")
        box.type("puis une seconde, assez longue pour ne pas tenir sur une ligne d'un téléphone")
        assert "\n" in box.input_value(), field  # its line break kept
        assert box.bounding_box()["height"] > 2.5 * one_line, field  # several lines
        assert box.evaluate("el => el.scrollHeight <= el.clientHeight + 1"), field  # all of it shown


def test_helps_as_the_settings_say(page):
    """No switch under the prompt: the helps come as the settings say (on at first)."""
    page.goto("/")
    sync_api.expect(page.locator(".switch.helps")).to_have_count(0)
    generate_free(page, FRONT_PROMPT)
    sync_api.expect(page.locator(".card-help textarea").first).to_have_value("(démo) Pourquoi c'est la réponse.")
    sync_api.expect(page.locator(".card-help:visible")).to_have_count(2)  # an explanation, a mnemonic: the others none


def test_one_card_corrected_by_the_ai(page):
    """⋯ → "✨ Correct this card": a field under the card (focused); the demo AI makes its
    back what was asked; the card marked changed, saved, "↩ Undo" puts it back. The others
    untouched. Escape closes the field."""
    generate_free(page, FRONT_PROMPT)
    cards = page.locator(".flash")
    first, second = cards.nth(0), cards.nth(1)
    back = first.locator("textarea").nth(1)
    before, other = back.input_value(), second.locator("textarea").nth(1).input_value()
    first.get_by_role("button", name="Plus d'actions").click()
    first.get_by_role("button", name="✨ Corriger cette carte").click()
    field = first.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?")
    sync_api.expect(field).to_be_focused()
    page.keyboard.press("Escape")
    sync_api.expect(field).to_be_hidden()

    first.get_by_role("button", name="Plus d'actions").click()
    first.get_by_role("button", name="✨ Corriger cette carte").click()
    field.fill("la mamá")
    field.press("Enter")
    sync_api.expect(back).to_have_value("la mamá")
    sync_api.expect(field).to_be_hidden()
    sync_api.expect(first.locator(".card-fixed")).to_contain_text("Carte corrigée (démo).")
    sync_api.expect(first.locator(".flash-badge")).to_be_visible()  # marked changed
    assert second.locator("textarea").nth(1).input_value() == other
    sync_api.expect(page.locator(".save-pill")).to_have_class(SAVED)
    (summary,) = lessons(page)
    assert lesson(page, summary["id"])["cards"][0]["back"] == "la mamá"

    first.get_by_role("button", name="↩ Annuler").click()
    sync_api.expect(back).to_have_value(before)
    sync_api.expect(first.locator(".card-fixed")).to_be_hidden()
    saved = f"fetch('/api/lessons/{summary['id']}').then(r => r.json()).then(l => l.cards[0].back === {before!r})"
    page.wait_for_function(f"() => {saved}")  # the card as it was, saved again


def test_a_card_just_added_written_by_the_ai(page):
    """A card just added (empty): ⋯ → "✨ Write with the AI", asked what it should ask; the
    demo AI writes its back from that. Filled, it is corrected again, no more written."""
    generate_free(page, FRONT_PROMPT)
    page.get_by_role("button", name="＋ Ajouter une carte").click()
    added = page.locator(".flash").last
    added.get_by_role("button", name="Plus d'actions").click()
    added.get_by_role("button", name="✨ Écrire avec l'IA").click()
    field = added.get_by_role("textbox", name="Que doit demander cette carte ?")
    field.fill("le grand-père en espagnol")
    added.get_by_role("button", name="Écrire", exact=True).click()
    sync_api.expect(added.locator("textarea").nth(1)).to_have_value("le grand-père en espagnol")
    added.get_by_role("button", name="Plus d'actions").click()
    sync_api.expect(added.get_by_role("button", name="✨ Corriger cette carte")).to_be_visible()


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
    first.get_by_role("button", name="Plus d'actions").click()
    first.get_by_role("button", name="✨ Corriger cette carte").click()
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
