"""A card's figure and picture: drawn after the cards, its steps, checked and drawn again, its
credits, a free one found."""

import base64
import io
import os
import re
import threading

import pytest
from helpers import plain_image
from PIL import Image as PILImage

sync_api = pytest.importorskip("playwright.sync_api")

from page.support import (  # noqa: E402
    FRONT_PROMPT,
    edit,
    eventually,
    generate_free,
    lesson,
    lessons,
    open_card,
    png,
)


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


def test_one_drawing_at_a_time_for_a_lesson(page):
    """Pictures asked again while the lesson's are being drawn (a correction adding a card):
    not a second drawing of the same cards (each paid), done once the first ends, if any is
    still missing."""
    held, asked = [], []
    page.route("**/api/lessons/*/pictures", lambda route: held.append(route))
    page.on("request", lambda r: asked.append(r.url) if r.url.endswith("/pictures") else None)
    generate_free(page, "Le triangle rectangle (géométrie)")
    sync_api.expect(page.locator(".card-picture.figure .drawing").first).to_be_visible()
    # Asked again: done once the first ends, at once (a second drawing would wait for its answer)
    again = """() => Promise.race([Alpine.$data(document.querySelector('[x-data]')).drawPictures().then(() => "back"),
                                    new Promise((done) => setTimeout(() => done("drawing"), 5000))])"""
    assert page.evaluate(again) == "back"
    meanwhile = len(asked)
    for route in held:
        route.continue_()
    assert meanwhile == 1
    sync_api.expect(page.locator(".card-picture.figure img").first).to_be_visible()
    page.wait_for_function("() => !Alpine.$data(document.querySelector('[x-data]')).drawingLessons.length")
    assert len(asked) == 1  # every figure drawn by the first: nothing left to draw


def test_a_figure_redrawn_shows_its_steps_and_first_try(page, monkeypatch):
    """Each card says what its picture is being made by; a figure found wrong shows its first
    try, faded, with what was wrong, while it's drawn again."""
    import asyncio

    from app.routes import pictures as routes

    real, go_on = routes.pictures.draw_all, threading.Event()
    first = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" width="400" height="300"></svg>'

    async def draw_all(
        s, folder, cards, draw=False, step=None, photos=None, not_from_lesson=(), previous=None, saved=None
    ):
        step({"card": cards[0].id, "step": "drawing"})
        step({"card": cards[0].id, "step": "redrawing", "problem": "L'angle est du mauvais côté.", "first": first})
        await asyncio.to_thread(go_on.wait, 30)
        return await real(s, folder, cards, draw, step, photos, not_from_lesson)

    monkeypatch.setattr(routes.pictures, "draw_all", draw_all)
    generate_free(page, "Le triangle rectangle (géométrie)")
    open_card(page.locator(".flash").first)  # its steps in the card open (the list: a thumbnail)
    redrawn = page.locator(".card-picture.figure .drawing.redrawing").first
    sync_api.expect(redrawn).to_contain_text("Première version imparfaite : nouveau tracé, plus soigné")
    sync_api.expect(redrawn).to_contain_text("L'angle est du mauvais côté.")
    sync_api.expect(redrawn).to_contain_text("environ 40 s")
    sync_api.expect(redrawn.locator("img.first")).to_be_visible()
    sync_api.expect(page.locator(".flash").nth(1).locator(".drawing:visible")).to_contain_text("En attente")
    # The first try shown at the size a figure is shown at, not shrunk into the 160 px waiting square
    waiting = redrawn.bounding_box()
    go_on.set()
    drawn = page.locator(".card-picture.figure img:not(.first)").first
    sync_api.expect(drawn).to_be_visible()
    assert waiting and waiting["width"] == pytest.approx(drawn.bounding_box()["width"], abs=1)
    assert waiting["height"] == pytest.approx(waiting["width"] * 300 / 400, abs=2)  # its own proportions
    sync_api.expect(page.locator(".drawing.redrawing")).to_have_count(0)


def test_a_figure_corrected_keeps_its_size_while_drawn_again(page):
    """A correction changing what a card's figure shows: while it is drawn again, the old one
    stays at the size it was shown at (the card full screen), a figure narrower than the card
    stretched to its width as before (not at its own size), the drawing's few words over it."""
    narrow = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 150" width="200" height="150"></svg>'
    page.route("**/pictures/picture-*.svg", lambda route: route.fulfill(body=narrow, content_type="image/svg+xml"))
    generate_free(page, "Le triangle rectangle (géométrie)")
    card = page.locator(".flash").first
    shown = card.locator(".card-picture.figure img:not(.first):visible")
    sync_api.expect(shown).to_be_visible()

    def fix(route):  # what the figure shows changed: drawn again
        changed = {**route.request.post_data_json["card"], "picture": None}
        changed["figure"] += " Le carré en rouge."
        route.fulfill(json={"card": changed, "summary": "Figure changée."})

    held = []
    page.route("**/fix-card*", fix)
    page.route("**/api/lessons/*/pictures", lambda route: held.append(route))
    open_card(card)
    sync_api.expect(card).to_have_class(re.compile(r"\bediting\b"))  # full screen
    before = shown.bounding_box()
    field = card.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?")
    field.fill("Le carré en rouge")
    field.press("Enter")
    old = card.locator(".drawing.redrawing:visible img.first")
    sync_api.expect(old).to_be_visible()
    waiting = old.bounding_box()
    assert before and waiting
    assert (waiting["width"], waiting["height"]) == pytest.approx((before["width"], before["height"]), abs=1)
    for route in held:
        route.continue_()
    sync_api.expect(shown).to_be_visible()


# The first card's figure as drawn in Typst, its sources kept (the demo draws SVG)
DRAWN_IN_TYPST = """() => {
  const c = Alpine.$data(document.querySelector('[x-data]')).cards[0];
  Object.assign(c, { figure_kind: 'geometry', picture_source: { source: 'drawn', engine: 'typst',
    sources: [{ file: c.picture.replace('.svg', '.typ') }] } });
  return { id: c.id, source: JSON.parse(JSON.stringify(c.picture_source)) };
}"""


def _asked_to_draw(page) -> list[dict]:
    """The pictures' requests (POST …/pictures) as sent, held: nothing drawn."""
    asked = []

    def hold(route):
        asked.append(route.request.post_data_json)
        route.fulfill(status=503, json={"detail": {"code": "errors.unreachable"}})

    page.route("**/api/lessons/*/pictures", hold)
    return asked


def test_a_figure_a_card_correction_replaced_drawn_again_from_it(page):
    """A card's correction changing what its figure shows: drawn again from the figure it had
    (`previous`: where it came from, its sources, and its family), what is asked changed and the
    rest kept."""
    generate_free(page, "Le triangle rectangle (géométrie)")
    sync_api.expect(page.locator(".card-picture.figure img").first).to_be_visible()
    was = page.evaluate(DRAWN_IN_TYPST)

    def fix(route):  # what the figure shows changed: its picture and where it came from cleared
        changed = {**route.request.post_data_json["card"], "picture": "", "picture_source": None}
        changed["figure"] += " Le carré en rouge."
        route.fulfill(json={"card": changed, "summary": "Figure changée."})

    page.route("**/fix-card*", fix)
    asked = _asked_to_draw(page)
    card = open_card(page.locator(".flash").first)
    field = card.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?")
    field.fill("Le carré en rouge")
    field.press("Enter")
    for _ in range(50):  # its figure then drawn again
        if asked:
            break
        page.wait_for_timeout(100)
    assert asked[-1]["previous"] == {was["id"]: {"source": was["source"], "kind": "geometry"}}


def test_a_figure_a_lesson_correction_replaced_drawn_again_from_it(page):
    """The lesson's correction changing what a card's figure shows: drawn again from the figure
    it had, as after the card's own; the cards it left as they were, from nothing."""
    import json

    generate_free(page, "Le triangle rectangle (géométrie)")
    sync_api.expect(page.locator(".card-picture.figure img").first).to_be_visible()
    was = page.evaluate(DRAWN_IN_TYPST)

    def revise(route):  # its first card's figure changed: its picture and where it came from cleared
        response = route.fetch()
        items = [json.loads(line) for line in response.text().splitlines() if line.strip()]
        for item in items:
            if "result" in item:
                first = item["result"]["lesson"]["cards"][0]
                first.update(picture="", picture_source=None, figure=first["figure"] + " Le carré en rouge.")
        body = "".join(json.dumps(item) + "\n" for item in items)
        route.fulfill(body=body, content_type=response.headers.get("content-type", ""))

    page.route("**/api/lessons/*/revise*", revise)
    asked = _asked_to_draw(page)
    page.locator(".revise textarea").fill("Le carré en rouge")
    page.locator(".revise .btn.primary").click()
    for _ in range(50):  # its figure then drawn again
        if asked:
            break
        page.wait_for_timeout(100)
    assert asked[-1]["previous"] == {was["id"]: {"source": was["source"], "kind": "geometry"}}


APP = "Alpine.$data(document.querySelector('[x-data]'))"


def _drawn_with(monkeypatch) -> list[tuple[str, list[str]]]:
    """What each figure drawn was drawn from: (its card's description, the Typst it started from)."""
    from app.routes import pictures as routes

    told = []
    real = routes.pictures.figure_or_picture

    async def draw(s, folder, card, *args, previous=(), **kwargs):
        told.append((card.figure, list(previous)))
        return await real(s, folder, card, *args, **kwargs)

    monkeypatch.setattr(routes.pictures, "figure_or_picture", draw)
    return told


def test_a_figure_a_correction_replaced_redrawn_from_it_by_hand(page, monkeypatch):
    """A card's correction changing what its figure shows, its drawing failing: its old Typst
    kept (not pruned once the card is done with), "📐 Dessiner la figure" draws the corrected
    description from it (`previous`); once a figure is drawn, "Redessiner" draws anew, and the
    old figure's Typst is no longer kept for it."""
    from app import lessons as saved_lessons

    generate_free(page, "Le triangle rectangle (géométrie)")
    sync_api.expect(page.locator(".card-picture.figure img").first).to_be_visible()
    was = page.evaluate(DRAWN_IN_TYPST)
    (summary,) = lessons(page)
    typst = saved_lessons.existing_folder(summary["id"]) / "images" / was["source"]["sources"][0]["file"]
    typst.write_text("#circle()", encoding="utf-8")

    def fix(route):  # what the figure shows changed: its picture and where it came from cleared
        changed = {**route.request.post_data_json["card"], "picture": "", "picture_source": None}
        changed["figure"] += " Le carré en rouge."
        route.fulfill(json={"card": changed, "summary": "Figure changée."})

    page.route("**/fix-card*", fix)
    asked = _asked_to_draw(page)  # its drawing fails
    card = open_card(page.locator(".flash").first)
    field = card.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?")
    field.fill("Le carré en rouge")
    field.press("Enter")
    eventually(page, lambda: asked, "drawn again")
    page.wait_for_function(f"() => !{APP}.drawingLessons.length")
    page.evaluate(f"() => {APP}.doneEditing()")  # its pictures pruned: not the figure it is drawn from
    page.wait_for_function(f"() => {APP}.saveState === 'saved' && !{APP}.saveTimer")
    page.wait_for_timeout(300)
    assert typst.is_file()

    told = _drawn_with(monkeypatch)
    corrected = page.evaluate(f"() => {APP}.cards[0].figure")
    assert corrected.endswith("Le carré en rouge.")
    page.get_by_role("alert").get_by_role("button", name="Fermer").click()  # its drawing's failure, said
    open_card(card)
    card.get_by_role("button", name="Plus d'actions").click()
    card.get_by_role("button", name="🖼️ Ajouter une image").click()
    dialog = page.get_by_role("dialog", name="Image")

    def redraw(name: str) -> dict:
        with page.expect_response(lambda r: r.url.endswith("/picture/make")) as made:
            dialog.get_by_role("button", name=name).click()
        assert made.value.ok
        sync_api.expect(dialog.locator(".picture-shown")).to_be_visible()
        return made.value.request.post_data_json

    sent = redraw("📐 Dessiner la figure")  # none shown
    assert sent["previous"] == {"source": was["source"], "kind": "geometry"}
    assert told[-1] == (corrected, ["#circle()"])
    sent = redraw("📐 Redessiner la figure")  # a figure drawn for its description since: another drawing wanted, anew
    assert "previous" not in sent
    assert told[-1] == (corrected, [])
    # Removed then: the old figure no longer waited for, its Typst pruned once the card is done with
    with page.expect_response(lambda r: r.request.method == "DELETE"):
        dialog.get_by_role("button", name="✕ Pas d'image").click()
    dialog.get_by_role("button", name="Terminé").click()
    page.evaluate(f"() => {APP}.doneEditing()")
    eventually(page, lambda: not typst.exists(), "the old figure's Typst pruned")


def test_a_figure_corrected_while_others_are_drawn_redrawn_as_corrected(page, monkeypatch):
    """A card's correction about its figure as drawn, its description changed with it, while
    another card's picture is being drawn: drawn again from the description corrected (the
    lesson saved meanwhile), and the card keeps it."""
    generate_free(page, "Le triangle rectangle (géométrie)")
    page.wait_for_function(f"() => !{APP}.drawingLessons.length && {APP}.cards.every((c) => !c.figure || c.picture)")
    held = []
    page.route("**/api/lessons/*/pictures", lambda route: held.append(route))
    page.evaluate(f"() => {{ {APP}.cards[1].picture = ''; {APP}.drawPictures(); }}")
    eventually(page, lambda: held, "the other card's drawing")
    told = _drawn_with(monkeypatch)

    def fix(route):  # about its figure as drawn, its description changed too: drawn again
        changed = {**route.request.post_data_json["card"]}
        changed["figure"] += " Le carré en rouge."
        problem = "Le carré n'est pas rouge."
        route.fulfill(json={"card": changed, "summary": "Figure changée.", "figure_problem": problem})

    page.route("**/fix-card*", fix)
    card = open_card(page.locator(".flash").first)
    field = card.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?")
    field.fill("Le carré en rouge")
    with page.expect_response(lambda r: r.url.endswith("/picture/draw")) as drawn:
        field.press("Enter")
    assert drawn.value.ok
    drawn.value.finished()
    corrected = page.evaluate(f"() => {APP}.cards[0].figure")
    assert corrected.endswith("Le carré en rouge.")
    assert [figure for figure, _ in told] == [corrected]
    for route in held:
        route.continue_()
    page.wait_for_function(f"() => !{APP}.drawingLessons.length && {APP}.saveState === 'saved' && !{APP}.saveTimer")
    (summary,) = lessons(page)
    assert lesson(page, summary["id"])["cards"][0]["figure"] == corrected


def test_a_figure_corrected_while_drawn_not_given_the_drawing_of_what_it_said(page, monkeypatch):
    """A card corrected again while the figure its first correction asked for is to be drawn:
    what it said before never drawn (the saved card read again when its turn comes: nothing
    paid for a drawing set aside), the card drawn as it says now, still from the figure it had."""
    import asyncio

    from app.routes import pictures as routes

    generate_free(page, "Le triangle rectangle (géométrie)")
    page.wait_for_function(f"() => !{APP}.drawingLessons.length && {APP}.cards.every((c) => !c.figure || c.picture)")
    from app import lessons as saved_lessons

    was = page.evaluate(DRAWN_IN_TYPST)
    (summary,) = lessons(page)
    typst = saved_lessons.existing_folder(summary["id"]) / "images" / was["source"]["sources"][0]["file"]
    typst.write_text("#circle()", encoding="utf-8")
    page.wait_for_function(f"() => {APP}.saveState === 'saved' && !{APP}.saveTimer")
    real, go_on, started = routes.pictures.draw_all, threading.Event(), []

    async def held(*args, **kwargs):  # the first drawing held until the card is corrected again
        started.append(True)
        if len(started) == 1:
            await asyncio.to_thread(go_on.wait, 30)
        return await real(*args, **kwargs)

    monkeypatch.setattr(routes.pictures, "draw_all", held)
    told = _drawn_with(monkeypatch)

    def fix(route):  # what the figure shows changed: its picture and where it came from cleared
        asked = route.request.post_data_json
        changed = {**asked["card"], "picture": "", "picture_source": None}
        changed["figure"] += f" {asked['instruction']}."
        route.fulfill(json={"card": changed, "summary": "Figure changée."})

    page.route("**/fix-card*", fix)
    asked = []
    page.on("request", lambda r: asked.append(r.post_data_json) if r.url.endswith("/pictures") else None)
    card = open_card(page.locator(".flash").first)
    field = card.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?")
    field.fill("Le carré en rouge")
    field.press("Enter")
    eventually(page, lambda: started, "its figure being drawn")
    first = page.evaluate(f"() => {APP}.cards[0].figure")
    field.fill("Le carré en bleu")
    field.press("Enter")
    page.wait_for_function(f"() => {APP}.cards[0].figure.endsWith('Le carré en bleu.')")
    corrected = page.evaluate(f"() => {APP}.cards[0].figure")
    eventually(page, lambda: lesson(page, summary["id"])["cards"][0]["figure"] == corrected, "the correction saved")
    go_on.set()
    eventually(page, lambda: len(asked) == 2, "drawn again as it says now")
    previous = {was["id"]: {"source": was["source"], "kind": "geometry"}}
    assert asked[0]["previous"] == asked[1]["previous"] == previous  # from the figure it had, both times
    page.wait_for_function(f"() => !{APP}.drawingLessons.length && {APP}.cards[0].picture")
    assert first != corrected
    assert [figure for figure, _ in told] == [corrected]  # the first correction's never drawn
    assert [sources for _, sources in told] == [["#circle()"]]
    page.wait_for_function(f"() => {APP}.saveState === 'saved' && !{APP}.saveTimer")
    saved = lesson(page, summary["id"])["cards"][0]
    assert (saved["figure"], saved["picture"]) == (corrected, page.evaluate(f"() => {APP}.cards[0].picture"))


def test_a_figure_corrected_again_by_the_lesson_still_drawn_from_the_one_it_had(page):
    """A card's correction changing its figure, its drawing not done (failed), then the lesson's
    correction changing it again: still drawn again from the figure it had."""
    import json

    generate_free(page, "Le triangle rectangle (géométrie)")
    sync_api.expect(page.locator(".card-picture.figure img").first).to_be_visible()
    was = page.evaluate(DRAWN_IN_TYPST)

    def fix(route):  # what the figure shows changed: its picture and where it came from cleared
        changed = {**route.request.post_data_json["card"], "picture": "", "picture_source": None}
        changed["figure"] += " Le carré en rouge."
        route.fulfill(json={"card": changed, "summary": "Figure changée."})

    page.route("**/fix-card*", fix)
    asked = _asked_to_draw(page)  # its drawing fails
    card = open_card(page.locator(".flash").first)
    field = card.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?")
    field.fill("Le carré en rouge")
    field.press("Enter")
    eventually(page, lambda: asked, "drawn again")
    page.wait_for_function(f"() => !{APP}.drawingLessons.length")
    page.get_by_role("alert").get_by_role("button", name="Fermer").click()  # its drawing's failure, said
    page.evaluate(f"() => {APP}.doneEditing()")

    def revise(route):  # its first card's figure changed again
        response = route.fetch()
        items = [json.loads(line) for line in response.text().splitlines() if line.strip()]
        for item in items:
            if "result" in item:
                first = item["result"]["lesson"]["cards"][0]
                first.update(picture="", picture_source=None, figure=first["figure"] + " Le carré en bleu.")
        body = "".join(json.dumps(item) + "\n" for item in items)
        route.fulfill(body=body, content_type=response.headers.get("content-type", ""))

    page.route("**/api/lessons/*/revise*", revise)
    page.locator(".revise textarea").fill("Le carré en bleu")
    page.locator(".revise .btn.primary").click()
    eventually(page, lambda: len(asked) == 2, "drawn again as corrected")
    assert asked[-1]["previous"] == {was["id"]: {"source": was["source"], "kind": "geometry"}}


def test_a_picture_a_correction_replaced_not_taken_from_the_lesson_again(page):
    """A correction that replaces a card's picture ("another photo"): its next one is not cut
    out of the lesson's photos again (the same drawing would come back), the page says so to
    the drawing (not_from_lesson); the other cards' as before."""
    page.route("**/picture-x.jpg", lambda route: route.fulfill(body=png("teal"), content_type="image/png"))
    generate_free(page, FRONT_PROMPT)
    page.evaluate(
        "() => { const c = Alpine.$data(document.querySelector('[x-data]')).cards[0];"
        " Object.assign(c, { picture: 'picture-x.jpg', picture_prompt: 'a mother',"
        " picture_source: { source: 'lesson' } }); }"
    )

    def fix(route):  # what the picture shows changed: its picture gone, to be found again
        changed = {**route.request.post_data_json["card"], "picture": ""}
        changed["picture_prompt"] = "a smiling mother hugging her child"
        route.fulfill(json={"card": changed, "summary": "Image changée."})

    asked = []
    page.route("**/fix-card*", fix)
    page.on("request", lambda r: asked.append(r.post_data_json) if r.url.endswith("/pictures") else None)
    card = open_card(page.locator(".flash").first)
    field = card.get_by_role("textbox", name="Qu'est-ce qui ne va pas ?")
    field.fill("une autre photo")
    field.press("Enter")
    sync_api.expect(card.locator(".card-fixed")).to_contain_text("Image changée.")
    for _ in range(50):  # its picture then looked for
        if asked:
            break
        page.wait_for_timeout(100)
    (summary,) = lessons(page)
    first_id = lesson(page, summary["id"])["cards"][0]["id"]
    assert asked and asked[0]["not_from_lesson"] == [first_id]
    # No free picture fits (the demo finds none): asked before the AI draws one
    ask = page.locator(".notice-bar.ask").filter(has_text=re.compile(r"dessiner par l'IA \?"))
    page.wait_for_function("el => getComputedStyle(el).display !== 'none'", arg=ask.element_handle())


def test_a_picture_shown_as_soon_as_ready(page, monkeypatch):
    """A card's figure shows the moment it is drawn, while another card's is still coming."""
    import asyncio

    from app.routes import pictures as routes

    real, go_on = routes.pictures.draw_all, threading.Event()

    async def draw_all(
        s, folder, cards, draw=False, step=None, photos=None, not_from_lesson=(), previous=None, saved=None
    ):
        folder.mkdir(parents=True, exist_ok=True)
        name = f"picture-{cards[0].id}-0123abcd.svg"
        (folder / name).write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" width="400" height="300"></svg>'
        )
        step({"card": cards[1].id, "step": "drawing"})
        step({"card": cards[0].id, "step": "ready", "picture": name, "figure": cards[0].figure})
        await asyncio.to_thread(go_on.wait, 30)
        return await real(s, folder, cards, draw, step, photos, not_from_lesson)

    monkeypatch.setattr(routes.pictures, "draw_all", draw_all)
    generate_free(page, "Le triangle rectangle (géométrie)")
    first, second = page.locator(".flash").nth(0), page.locator(".flash").nth(1)
    sync_api.expect(first.locator(".card-picture.figure img:not(.first):visible")).to_be_visible()
    sync_api.expect(first.locator(".drawing:visible")).to_have_count(0)
    sync_api.expect(second.locator(".drawing:visible")).to_be_visible()  # still coming
    go_on.set()
    sync_api.expect(second.locator(".card-picture.figure img:not(.first):visible")).to_be_visible()


def test_a_figures_check_says_what_it_does_under_the_figure(page):
    """The card open on a phone: "🔍 Vérifier la figure" written on its button (a lone 🔍 read as
    a zoom, its name only in a tooltip a finger never shows), under the figure, at its right."""
    page.set_viewport_size({"width": 412, "height": 915})
    generate_free(page, "Le triangle rectangle (géométrie)")
    card = open_card(page.locator(".flash").first)
    figure = card.locator(".card-picture.figure img:not(.first):visible")
    sync_api.expect(figure).to_be_visible()
    button = card.locator(".figure-check-btn:visible")
    sync_api.expect(button).to_have_text("🔍 Vérifier la figure")
    shown, under = button.bounding_box(), figure.bounding_box()
    assert shown and under
    assert shown["y"] >= under["y"] + under["height"], (shown, under)  # under it, not beside
    assert shown["x"] + shown["width"] == pytest.approx(under["x"] + under["width"], abs=2), (shown, under)


def test_a_figure_checked_on_demand_then_redrawn(page, monkeypatch):
    """ "🔍 Vérifier la figure" in its panel: what the AI sees wrong, then drawn again with
    care when asked; "Garder" keeps it."""
    from notosaurus_core import llm

    async def check(s, description, svg):
        return "L'angle est en B."

    monkeypatch.setattr(llm, "check_figure", check)
    generate_free(page, "Le triangle rectangle (géométrie)")
    card = open_card(page.locator(".flash").first)
    sync_api.expect(card.locator(".card-picture.figure img:not(.first):visible")).to_be_visible()
    card.get_by_role("button", name="🔍 Vérifier la figure").first.click()  # on the figure itself
    found = card.locator(".figure-check:visible")
    sync_api.expect(found).to_contain_text("La vérification signale : L'angle est en B.")
    found.get_by_role("button", name="Garder").click()
    sync_api.expect(found).to_be_hidden()

    def redraw(name):
        """Drawn again, until its drawing is over: the old figure stays in view meanwhile, and a
        check clicked before the drawing starts would be cleared by it."""
        with page.expect_response(lambda r: r.url.endswith("/picture/draw")) as drawn:
            found.get_by_role("button", name=name, exact=True).click()
        drawn.value.finished()
        sync_api.expect(found).to_be_hidden()
        sync_api.expect(card.locator(".card-picture.figure img:not(.first):visible")).to_be_visible()

    card.get_by_role("button", name="🔍 Vérifier la figure").first.click()
    redraw("📐 Redessiner")  # quickly, told the problem
    card.get_by_role("button", name="🔍 Vérifier la figure").first.click()  # still wrong: with care now
    redraw("📐 Redessiner avec soin")
    card.get_by_role("button", name="🔍 Vérifier la figure").first.click()  # wrong again: still with care
    sync_api.expect(found.get_by_role("button", name="📐 Redessiner avec soin")).to_be_visible()


def test_a_figures_credits_link_its_projects(page, monkeypatch):
    """What drew a figure, each project linked: on its picture's page and under it full screen."""
    from app.routes import pictures as routes

    real = routes.pictures.draw_all

    typst = routes.PictureSource(
        source="drawn", model="gemini-x", engine="typst", made_with=["Typst 0.15.0", "lilaq 0.6.0"]
    )

    async def draw_all(
        s, folder, cards, draw=False, step=None, photos=None, not_from_lesson=(), previous=None, saved=None
    ):
        def told(said):  # each card's picture as Typst drew it
            step({**said, "picture_source": typst.model_dump()} if said["step"] == "ready" else said)

        drawn = await real(s, folder, cards, draw, told, photos, not_from_lesson)
        for card in cards:
            card.picture_source = typst
        return drawn

    monkeypatch.setattr(routes.pictures, "draw_all", draw_all)
    generate_free(page, "Le triangle rectangle (géométrie)")
    card = open_card(page.locator(".flash").first)
    card.locator(".card-picture.figure img:not(.first):visible").click()
    picture = page.get_by_role("dialog", name="Image")
    sync_api.expect(picture.locator(".picture-source:visible")).to_contain_text("Typst + lilaq")
    picture.locator(".picture-shown").click()  # shown large
    credit = page.locator(".viewer-credit")
    sync_api.expect(credit).to_contain_text("📐 Dessinée par gemini-x avec Typst + lilaq")
    sync_api.expect(credit.get_by_role("link", name="lilaq")).to_have_attribute(
        "href", "https://typst.app/universe/package/lilaq"
    )
    page.keyboard.press("Escape")
    sync_api.expect(credit).to_be_hidden()
    sync_api.expect(picture).to_be_visible()  # the viewer closed first, the page under it kept


def test_a_cards_picture_touched_opens_its_page(page):
    """The picture touched in the card edited: its page full screen, everything that changes it
    there (no 🖼️ on the card any more); « Terminé » or Escape back to the card, still edited."""
    generate_free(page, "Le triangle rectangle (géométrie)")
    card = open_card(page.locator(".flash").first)
    sync_api.expect(card.locator(".flash-actions").get_by_role("button", name="Image", exact=True)).to_have_count(0)
    figure = card.locator(".card-picture.figure img:not(.first):visible")
    figure.click()
    picture = page.get_by_role("dialog", name="Image")
    sync_api.expect(picture).to_be_visible()
    sync_api.expect(page.locator(".viewer")).to_be_hidden()  # not only shown large
    sync_api.expect(picture.locator(".picture-shown")).to_be_visible()
    for name in ("📐 Redessiner la figure", "📷 Prendre une photo", "🖼️ Galerie", "✕ Pas d'image"):
        sync_api.expect(picture.get_by_text(name, exact=True)).to_be_visible()
    sync_api.expect(picture.get_by_text("Au verso (avec la réponse)")).to_be_visible()
    sync_api.expect(picture.get_by_label("La figure à dessiner (étiquettes comprises)")).not_to_have_value("")
    picture.get_by_role("button", name="Terminé").click()
    sync_api.expect(picture).to_be_hidden()
    sync_api.expect(card).to_have_class(re.compile(r"\bediting\b"))

    figure.click()
    sync_api.expect(picture).to_be_visible()
    page.keyboard.press("Escape")
    sync_api.expect(picture).to_be_hidden()
    sync_api.expect(card).to_have_class(re.compile(r"\bediting\b"))  # the card not closed with it


def test_a_cards_picture_taken_with_the_camera(page):
    """On the picture's page, "📷 Take a photo" takes one (capture: on the phone the document
    scanner, as the lesson's pages), "🖼️ Gallery" chooses one; either is the card's picture."""
    generate_free(page, "Le triangle rectangle (géométrie)")
    card = open_card(page.locator(".flash").first)
    card.locator(".card-picture.figure img:not(.first):visible").click()
    picture = page.get_by_role("dialog", name="Image")
    camera = picture.locator("label", has_text="📷 Prendre une photo").locator("input[type=file]")
    gallery = picture.locator("label", has_text="🖼️ Galerie").locator("input[type=file]")
    sync_api.expect(camera).to_have_attribute("capture", "environment")
    assert gallery.get_attribute("capture") is None  # the phone's photos, not the camera
    camera.set_input_files([{"name": "photo.png", "mimeType": "image/png", "buffer": png("teal")}])
    sync_api.expect(picture.locator(".picture-source:visible")).to_contain_text("Votre photo")
    (summary,) = lessons(page)
    assert lesson(page, summary["id"])["cards"][0]["picture_source"]["source"] == "photo"


def test_what_a_picture_shows_seen_whole(page):
    """On the picture's page, what it shows (a figure's description, a few sentences) is seen
    whole: a box as tall as its text, over several lines, not one line cut. Shift+Enter a new
    line in it."""
    generate_free(page, "Le triangle rectangle (géométrie)")
    card = open_card(page.locator(".flash").first)
    card.locator(".card-picture.figure img:not(.first):visible").click()
    subject = page.get_by_role("dialog", name="Image").get_by_label("La figure à dessiner (étiquettes comprises)")
    subject.fill("Un triangle rectangle ABC, rectangle en C. " * 4)
    seen = """el => el.scrollHeight <= el.clientHeight + 1
        && el.clientHeight > 2 * parseFloat(getComputedStyle(el).lineHeight)"""
    page.wait_for_function(seen, arg=subject.element_handle())
    subject.press("End")
    subject.press("Shift+Enter")
    assert subject.input_value().endswith("\n")


def test_a_picture_on_the_back_shows_no_drawing_frame(page):
    """A card whose picture goes on the back shows its picture alone: no "Dessin…" frame
    under it, even once a step was told again (the bar's duration, set as the whole style,
    wiped the frame's hiding)."""
    generate_free(page, "Le triangle rectangle (géométrie)")
    back = page.locator(".flash").nth(2).locator(".card-picture.on-back")
    sync_api.expect(back.locator("img:not(.first):visible")).to_be_visible()
    # What the bar's duration depends on changing again (a step told, then over): the style
    # set again, the frame still hidden
    page.evaluate(
        "() => { const card = Alpine.$data(document.querySelector('[x-data]')).cards[2];"
        " card._step = 'lesson'; return new Promise((done) => setTimeout(() => { card._step = ''; done(); }, 50)); }"
    )
    sync_api.expect(back.locator("img:not(.first):visible")).to_be_visible()
    sync_api.expect(back.locator(".drawing:visible")).to_have_count(0)


def test_find_a_free_picture(page):
    """A card without a picture, ⋯ → “🖼️ Add a picture” → “🔍 Find a picture”: the AI decides a
    picture, the free pictures that fit are offered (its choice first, ⭐), one tapped becomes
    the card's."""
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
    first = edit(page.locator(".flash").first)
    first.get_by_role("button", name="Plus d'actions").click()
    first.get_by_role("button", name="🖼️ Ajouter une image").click()
    sync_api.expect(page.get_by_role("dialog", name="Image")).to_be_visible()
    find = page.get_by_role("dialog", name="Image").locator(".picture-actions button.btn").first
    sync_api.expect(find).to_have_text("🔍 Trouver une image")
    find.click()
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
    sync_api.expect(find).to_have_text("🔍 Chercher une autre image")  # it has one now: another looked for


def test_a_picture_shown_large_in_the_card_open(page):
    """A card's picture (a photo, not a figure), in the card open: as wide as the card allows
    (up to 400 px), in its own proportions, not the list's 160 px square."""
    photo = plain_image(800, 500, "teal", "JPEG")
    page.route("**/picture-x.jpg", lambda route: route.fulfill(body=photo, content_type="image/jpeg"))
    page.set_viewport_size({"width": 360, "height": 780})
    generate_free(page, FRONT_PROMPT)
    page.evaluate("Alpine.$data(document.querySelector('[x-data]')).cards[0].picture = 'picture-x.jpg'")
    card = open_card(page.locator(".flash").first)
    img = card.locator(".card-picture:not(.figure) img:visible")
    sync_api.expect(img).to_be_visible()
    page.wait_for_function("img => img.complete && img.naturalWidth > 0", arg=img.element_handle())
    box = img.bounding_box()
    assert box and box["width"] > 250 and box["width"] / box["height"] == pytest.approx(800 / 500, rel=0.03)


def test_a_photo_checked_against_its_card_then_changed(page, monkeypatch):
    """A card's photo (here in a figure's place): « 🔍 Vérifier l'image », looked at against
    the card; what is wrong said, « 🖼️ Changer l'image » opens its picture's panel (another
    free one, drawn, one's own). A figure keeps « Vérifier la figure » and « Redessiner »."""
    from notosaurus_core import llm

    async def check(s, card, meant, data, media_type):
        return "Un baby-foot, sans rapport avec la carte."

    monkeypatch.setattr(llm, "check_picture", check)
    generate_free(page, "Le triangle rectangle (géométrie)")
    card = open_card(page.locator(".flash").first)
    sync_api.expect(card.get_by_role("button", name="🔍 Vérifier la figure")).to_be_visible()
    (summary,) = lessons(page)
    folder = page.evaluate("Alpine.$data(document.querySelector('[x-data]')).lessonId")
    jpeg = plain_image(400, 300, "teal", "JPEG")
    upload = page.request.post(
        f"/api/lessons/{folder}/cards/{lesson(page, summary['id'])['cards'][0]['id']}/picture",
        multipart={"photo": {"name": "photo.jpg", "mimeType": "image/jpeg", "buffer": jpeg}},
    )
    assert upload.ok
    page.evaluate(
        "(c) => Object.assign(Alpine.$data(document.querySelector('[x-data]')).cards[0], c)", upload.json()["card"]
    )
    check_button = card.get_by_role("button", name="🔍 Vérifier l'image")
    sync_api.expect(check_button).to_be_visible()
    check_button.click()
    found = card.locator(".figure-check:visible")
    sync_api.expect(found).to_contain_text("Un baby-foot, sans rapport avec la carte.")
    sync_api.expect(found.get_by_role("button", name="📐 Redessiner")).to_be_hidden()
    found.get_by_role("button", name="🖼️ Changer l'image").click()
    sync_api.expect(card.locator(".picture-panel")).to_be_visible()


def test_the_pictures_to_draw_are_the_open_lessons_only(page):
    """The bar offering to draw a lesson's pictures with the AI (none free fits them): gone
    when another lesson is opened, its "Draw" never paying for that one's."""
    generate_free(page, FRONT_PROMPT)  # no picture asked
    (other,) = lessons(page)
    page.route(
        "**/api/lessons/*/pictures",
        lambda route: route.fulfill(json={"lesson": {"cards": []}, "failures": 0, "error": None, "to_draw": ["c1"]}),
    )
    generate_free(page, "Le triangle rectangle (géométrie)")  # figures: none drawn, offered
    bar = page.locator(".notice-bar.ask")
    sync_api.expect(bar).to_be_visible()
    page.evaluate("id => Alpine.$data(document.querySelector('[x-data]')).openLesson(id)", other["id"])
    page.wait_for_function("id => Alpine.$data(document.querySelector('[x-data]')).lessonId === id", arg=other["id"])
    sync_api.expect(bar).to_be_hidden()


def test_a_figure_turned_into_a_photo_stays_the_figure_until_one_is_chosen(page, monkeypatch):
    """A figure's description emptied, "📐 Redessiner la figure": the AI decides a photo, free
    ones offered. Given up (« Terminé »): the card is still the figure, its drawing and its
    description, its « 🔍 Vérifier la figure » working. One chosen: the figure gone, the photo
    and what it shows kept."""
    from notosaurus_core import llm, stock
    from notosaurus_core.models import PicturePlan, PictureSource

    async def plan(s, front, back, asked, language):
        return PicturePlan(kind="picture", description="a set square on a desk", search="set square")

    async def check(s, description, svg):
        return "L'angle droit n'est pas marqué."

    async def fetch(source, id_, pixabay_key=""):
        return plain_image(300, 200, "teal", "JPEG"), PictureSource(source="commons", licence="CC0")

    monkeypatch.setattr(llm, "plan_picture", plan)
    monkeypatch.setattr(llm, "check_figure", check)
    monkeypatch.setattr(stock, "fetch", fetch)
    preview = "data:image/jpeg;base64," + base64.b64encode(plain_image(120, 90, "#2e86de")).decode()
    results = [
        {"source": "commons", "id": f"File:{n}.jpg", "title": f"{n}", "preview": preview, "licence": "CC0"}
        for n in (1, 2)
    ]
    page.route("**/api/pictures/search", lambda route: route.fulfill(json={"results": results}))
    generate_free(page, "Le triangle rectangle (géométrie)")
    card = open_card(page.locator(".flash").first)
    sync_api.expect(card.locator(".card-picture.figure img:not(.first):visible")).to_be_visible()  # drawn
    (summary,) = lessons(page)
    before = lesson(page, summary["id"])["cards"][0]
    assert before["figure"] and before["picture"].endswith(".svg")
    dialog = page.get_by_role("dialog", name="Image")

    def turn_into_a_photo():
        card.locator(".card-picture.figure img:not(.first):visible").click()
        dialog.get_by_label("La figure à dessiner (étiquettes comprises)").fill("")
        dialog.get_by_role("button", name="📐 Redessiner la figure").click()
        sync_api.expect(card.locator(".found-pick")).to_have_count(2)

    turn_into_a_photo()
    dialog.get_by_role("button", name="Terminé").click()  # the search given up
    sync_api.expect(dialog).to_be_hidden()
    after = lesson(page, summary["id"])["cards"][0]
    assert (after["figure"], after["figure_kind"], after["picture"]) == (
        before["figure"],
        before["figure_kind"],
        before["picture"],
    )
    assert after["picture_prompt"] == ""
    card.get_by_role("button", name="🔍 Vérifier la figure").first.click()
    sync_api.expect(card.locator(".figure-check:visible")).to_contain_text("L'angle droit n'est pas marqué.")

    turn_into_a_photo()
    with page.expect_response(lambda r: r.url.endswith("/picture/found")) as chosen:
        card.locator(".found-pick").nth(1).click()
    assert chosen.value.ok
    sync_api.expect(card.locator(".found-pick")).to_have_count(0)
    after = lesson(page, summary["id"])["cards"][0]
    assert (after["figure"], after["figure_kind"]) == ("", "")
    assert (after["picture_prompt"], after["picture_search"]) == ("a set square on a desk", "set square")
    assert after["picture"].endswith(".jpg") and after["picture_source"]["source"] == "commons"


def test_a_figure_turned_into_a_photo_none_found_asked_about_the_photo_once(page, monkeypatch):
    """A figure the AI turns into a photo, no free one fitting: the question names the photo
    decided (the card is still the figure: its own description isn't it). The picture's page
    left and opened again: nothing of that visit left (neither the question nor a decision sent
    later with the user's own photo)."""
    from notosaurus_core import llm
    from notosaurus_core.models import PicturePlan

    async def plan(s, front, back, asked, language):
        return PicturePlan(kind="picture", description="a set square on a desk", search="set square")

    monkeypatch.setattr(llm, "plan_picture", plan)
    page.route("**/api/pictures/search", lambda route: route.fulfill(json={"results": []}))
    generate_free(page, "Le triangle rectangle (géométrie)")
    card = open_card(page.locator(".flash").first)
    figure = card.locator(".card-picture.figure img:not(.first):visible")
    figure.click()
    dialog = page.get_by_role("dialog", name="Image")
    dialog.get_by_label("La figure à dessiner (étiquettes comprises)").fill("")
    dialog.get_by_role("button", name="📐 Redessiner la figure").click()
    asked = dialog.locator(".draw-ask")
    sync_api.expect(asked).to_contain_text("« a set square on a desk »")
    dialog.get_by_role("button", name="Terminé").click()

    figure.click()  # again: afresh
    sync_api.expect(asked).to_be_hidden()
    with page.expect_request(lambda r: r.method == "POST" and r.url.endswith("/picture")) as sent:
        dialog.locator("label", has_text="🖼️ Galerie").locator("input[type=file]").set_input_files(
            [{"name": "photo.png", "mimeType": "image/png", "buffer": png("teal")}]
        )
    assert b'name="decided"' not in (sent.value.post_data_buffer or b"")
    sync_api.expect(dialog.locator(".picture-source:visible")).to_contain_text("Votre photo")
    (summary,) = lessons(page)
    after = lesson(page, summary["id"])["cards"][0]
    assert after["figure"] and after["picture_prompt"] == ""  # still the figure, its photo the user's


def test_the_pictures_camera_off_while_pages_are_read(page):
    """While files are read into the lesson's pages, the picture's 📷 is off as the lesson's is:
    on the phone, its capture would empty the folder they are read from."""
    generate_free(page, "Le triangle rectangle (géométrie)")
    card = open_card(page.locator(".flash").first)
    card.locator(".card-picture.figure img:not(.first):visible").click()
    camera = page.get_by_role("dialog", name="Image").locator("label", has_text="📷 Prendre une photo")
    sync_api.expect(camera.locator("input[type=file]")).to_be_enabled()
    page.evaluate("Alpine.$data(document.querySelector('[x-data]')).filesReading++")
    sync_api.expect(camera.locator("input[type=file]")).to_be_disabled()
    sync_api.expect(camera).to_have_class(re.compile(r"\bdisabled\b"))
    page.evaluate("Alpine.$data(document.querySelector('[x-data]')).filesReading--")
    sync_api.expect(camera.locator("input[type=file]")).to_be_enabled()
