"""A card's figure and picture: drawn after the cards, its steps, checked and drawn again, its
credits, a free one found."""

import base64
import io
import os
import threading

import pytest
from helpers import plain_image
from PIL import Image as PILImage

sync_api = pytest.importorskip("playwright.sync_api")

from page.support import (  # noqa: E402
    FRONT_PROMPT,
    generate_free,
    lesson,
    lessons,
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
    redrawn = page.locator(".card-picture.figure .drawing.redrawing").first
    sync_api.expect(redrawn).to_contain_text("Première version imparfaite : nouveau tracé, plus soigné")
    sync_api.expect(redrawn).to_contain_text("L'angle est du mauvais côté.")
    sync_api.expect(redrawn).to_contain_text("environ 40 s")
    sync_api.expect(redrawn.locator("img.first")).to_be_visible()
    sync_api.expect(page.locator(".flash").nth(1).locator(".drawing:visible")).to_contain_text("En attente")
    go_on.set()
    sync_api.expect(page.locator(".card-picture.figure img:not(.first)").first).to_be_visible()
    sync_api.expect(page.locator(".drawing.redrawing")).to_have_count(0)


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


def test_a_figure_checked_on_demand_then_redrawn(page, monkeypatch):
    """ "🔍 Vérifier la figure" in its panel: what the AI sees wrong, then drawn again with
    care when asked; "Garder" keeps it."""
    from notosaurus_core import llm

    async def check(s, description, svg):
        return "L'angle est en B."

    monkeypatch.setattr(llm, "check_figure", check)
    generate_free(page, "Le triangle rectangle (géométrie)")
    card = page.locator(".flash").first
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
    """What drew a figure, each project linked: in its picture panel and under it full screen."""
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
    card = page.locator(".flash").first
    card.locator(".card-picture.figure img:not(.first):visible").click()
    credit = page.locator(".viewer-credit")
    sync_api.expect(credit).to_contain_text("📐 Dessinée par gemini-x avec Typst + lilaq")
    sync_api.expect(credit.get_by_role("link", name="lilaq")).to_have_attribute(
        "href", "https://typst.app/universe/package/lilaq"
    )
    page.keyboard.press("Escape")
    card.get_by_role("button", name="Image").first.click()
    sync_api.expect(card.locator(".picture-source:visible")).to_contain_text("Typst + lilaq")


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
