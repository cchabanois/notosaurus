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


def test_a_figure_redrawn_shows_its_steps_and_first_try(page, monkeypatch):
    """Each card says what its picture is being made by; a figure found wrong shows its first
    try, faded, with what was wrong, while it's drawn again."""
    import asyncio

    from app.routes import pictures as routes

    real, go_on = routes.pictures.draw_all, threading.Event()
    first = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" width="400" height="300"></svg>'

    async def draw_all(s, folder, cards, draw=False, step=None, photos=None):
        step({"card": cards[0].id, "step": "drawing"})
        step({"card": cards[0].id, "step": "redrawing", "problem": "L'angle est du mauvais côté.", "first": first})
        await asyncio.to_thread(go_on.wait, 30)
        return await real(s, folder, cards, draw, step, photos)

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


def test_a_picture_shown_as_soon_as_ready(page, monkeypatch):
    """A card's figure shows the moment it is drawn, while another card's is still coming."""
    import asyncio

    from app.routes import pictures as routes

    real, go_on = routes.pictures.draw_all, threading.Event()

    async def draw_all(s, folder, cards, draw=False, step=None, photos=None):
        folder.mkdir(parents=True, exist_ok=True)
        name = f"picture-{cards[0].id}-0123abcd.svg"
        (folder / name).write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" width="400" height="300"></svg>'
        )
        step({"card": cards[1].id, "step": "drawing"})
        step({"card": cards[0].id, "step": "ready", "picture": name, "figure": cards[0].figure})
        await asyncio.to_thread(go_on.wait, 30)
        return await real(s, folder, cards, draw, step, photos)

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

    async def draw_all(s, folder, cards, draw=False, step=None, photos=None):
        def told(said):  # each card's picture as Typst drew it
            step({**said, "picture_source": typst.model_dump()} if said["step"] == "ready" else said)

        drawn = await real(s, folder, cards, draw, told, photos)
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
    for name in ("✨ Changer l'image", "📷 Prendre une photo", "🖼️ Galerie", "✕ Pas d'image"):
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
    """On the picture's page, "📷 Take a photo" opens the camera (capture, as the lesson's
    pages), "🖼️ Gallery" the photos; either, the photo is the card's picture, its own."""
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
    """A card without a picture, ⋯ → “🖼️ Add a picture” → “✨ Image”: the AI decides a
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
