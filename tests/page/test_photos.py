"""Step 1, the photos: taken, from the gallery or a PDF, beside the add buttons, seen in full,
turned, a part hidden, the next pages added."""

import base64
import io
import re

import pytest
from helpers import plain_image
from PIL import Image as PILImage

sync_api = pytest.importorskip("playwright.sync_api")

from page.support import (  # noqa: E402
    FRONT_PROMPT,
    PDF_NOTICE,
    add_photo,
    add_text_pdf,
    draft_kept,
    drop,
    editor_pixel,
    generate_free,
    generate_from_photos,
    lesson,
    lessons,
    open_hide,
    open_prompt,
    pdf,
    photo_not_sent,
    png,
    started,
    stroke,
    text_pdf,
)


def test_the_main_button_takes_the_first_photo(page):
    """No photo yet: "📷 Photographiez la leçon" is not a dead button, it opens the camera."""
    page.goto("/")
    start = page.get_by_role("button", name="📷 Photographiez la leçon")
    sync_api.expect(start).to_be_enabled()
    with page.expect_file_chooser() as chooser:
        start.click()
    assert chooser.value.element.get_attribute("capture") == "environment"


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
    viewer.locator(".viewer-frame img").click()  # zoomed in where it's touched
    sync_api.expect(viewer.locator(".viewer-frame")).to_have_class(re.compile(r"\bzoomed\b"))
    page.keyboard.press("Escape")
    sync_api.expect(viewer).to_be_hidden()

    # A card's figure too, alone: no arrows
    generate_free(page, "Le triangle rectangle (géométrie)")
    page.locator(".card-picture img").first.click()
    sync_api.expect(viewer).to_be_visible()
    sync_api.expect(viewer.locator(".viewer-nav")).to_have_count(0)


def test_a_picture_zoomed_with_two_fingers_then_moved(page):
    """In full, a picture zoomed with two fingers about the point between them, moved with one,
    never off the screen; zoomed in, a swipe turns no page; pinched back, the whole picture."""
    page.set_viewport_size({"width": 360, "height": 780})
    page.goto("/")
    page.locator('input[type=file][accept="image/*"][multiple]').set_input_files(
        [{"name": f"page-{n}.png", "mimeType": "image/png", "buffer": png(c)} for n, c in ((1, "red"), (2, "blue"))]
    )
    page.locator(".thumb img").first.click()
    viewer = page.locator(".viewer")
    img = viewer.locator(".viewer-frame img")
    sync_api.expect(img).to_be_visible()
    box = img.bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

    def fingers(kind, *points):
        for n, (x, y) in enumerate(points, 1):
            event = {"pointerId": n, "pointerType": "touch", "isPrimary": n == 1, "clientX": x, "clientY": y}
            img.dispatch_event(kind, event)

    fingers("pointerdown", (cx - 20, cy), (cx + 20, cy))
    fingers("pointermove", (cx - 60, cy), (cx + 60, cy))  # three times as far apart
    fingers("pointerup", (cx - 60, cy), (cx + 60, cy))
    zoomed = img.bounding_box()
    assert 2.8 < zoomed["width"] / box["width"] < 3.2
    assert abs(zoomed["x"] + zoomed["width"] / 2 - cx) < 2  # about the point between the fingers
    sync_api.expect(viewer.locator(".viewer-frame")).to_have_class(re.compile(r"\bzoomed\b"))

    fingers("pointerdown", (cx, cy))
    fingers("pointermove", (cx + 2000, cy))  # far past the picture's edge
    fingers("pointerup", (cx + 2000, cy))
    moved = img.bounding_box()
    assert moved["x"] > zoomed["x"] and moved["x"] <= 1  # moved, its left edge never inside the screen
    viewer.dispatch_event("touchstart", {"touches": [{"identifier": 1, "clientX": cx, "clientY": cy}]})
    lifted = [{"identifier": 1, "clientX": cx - 200, "clientY": cy}]  # a swipe to the left
    viewer.dispatch_event("touchend", {"touches": [], "changedTouches": lifted})
    sync_api.expect(viewer.locator(".viewer-count")).to_have_text("1 / 2")  # zoomed in: no page turned

    fingers("pointerdown", (cx - 90, cy), (cx + 90, cy))
    fingers("pointermove", (cx - 10, cy), (cx + 10, cy))
    fingers("pointerup", (cx - 10, cy), (cx + 10, cy))
    sync_api.expect(viewer.locator(".viewer-frame")).not_to_have_class(re.compile(r"\bzoomed\b"))
    assert abs(img.bounding_box()["width"] - box["width"]) < 1  # the whole picture again


def test_a_photo_seen_in_full_turned_and_a_name_hidden(page):
    """A lesson's photo seen in full: turned from there (the photo shown follows), a name
    hidden from there (its editor above the viewer), as from its thumbnail."""
    page.goto("/")
    page.locator('input[type=file][accept="image/*"][multiple]').set_input_files(
        [{"name": "page-1.png", "mimeType": "image/png", "buffer": png("red")}]
    )
    page.locator(".thumb img").first.click()
    viewer = page.locator(".viewer")
    shown = viewer.locator(".viewer-frame img")
    shown.wait_for()
    page.wait_for_function("() => document.querySelector('.viewer-frame img').naturalWidth === 600")
    shown.click()  # zoomed in: turned, the photo is seen whole again (the old zoom means nothing on it)
    sync_api.expect(viewer.locator(".viewer-frame")).to_have_class(re.compile(r"\bzoomed\b"))
    viewer.get_by_role("button", name="Tourner la photo d'un quart de tour").click()
    page.wait_for_function("() => document.querySelector('.viewer-frame img').naturalWidth === 800")
    sync_api.expect(viewer.locator(".viewer-frame")).not_to_have_class(re.compile(r"\bzoomed\b"))
    assert shown.evaluate("el => el.style.transform") == "translate(0px, 0px) scale(1)"
    viewer.get_by_role("button", name="Cacher une partie de la page (un nom…)").click()
    sync_api.expect(page.get_by_role("dialog", name="Cacher ce que l'IA ne doit pas voir")).to_be_visible()
    page.keyboard.press("Escape")  # the editor closes, the viewer stays
    sync_api.expect(page.get_by_role("dialog", name="Cacher ce que l'IA ne doit pas voir")).to_be_hidden()
    sync_api.expect(viewer).to_be_visible()


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

    # The page opened again (the lesson open again by itself), then generated again: the
    # text goes with its page again
    draft_kept(page)
    page.reload()
    started(page)
    sync_api.expect(page.locator(".thumb img")).to_have_count(1)
    open_prompt(page)
    sync_api.expect(page.locator("textarea[x-ref=promptText]")).to_have_value("Une carte par date")
    page.locator("textarea[x-ref=promptText]").fill("Une carte par lieu")
    page.get_by_role("button", name="✨ Régénérer").click()
    sync_api.expect(page.get_by_text("Cartes régénérées")).to_be_visible()
    assert lesson(page, summary["id"])["prompt"] == "Une carte par lieu"
    assert lesson(page, summary["id"])["page_texts"] == [text]


@pytest.mark.parametrize("width", [360, 411])
def test_the_add_buttons_beside_the_pages_on_a_phone(page, width):
    """Pages taken: the camera, gallery and PDF buttons first (always in the same place), two
    pages high, each a finger's size and the same as pages come, their names whole. One page
    (the most) shown large beside them (a narrow phone's 360 dp: in the one column left, it
    went under them); more, four beside them, then under them. (Three stacked in a page's
    cell made it half as tall again as the pages.)"""
    page.set_viewport_size({"width": width, "height": 860})
    page.goto("/")
    heights = []
    for n, color in enumerate(("red", "blue", "green", "orange", "purple"), start=1):
        page.locator('input[type=file][accept="image/*"][multiple]').set_input_files(
            {"name": f"page-{n}.png", "mimeType": "image/png", "buffer": plain_image(300, 400, color)}
        )
        sync_api.expect(page.locator(".thumb img")).to_have_count(n)
        thumbs = [t.bounding_box() for t in page.locator(".thumb").all()]
        stack = page.locator(".add-stack").bounding_box()
        assert stack["x"] < thumbs[0]["x"] and stack["y"] == thumbs[0]["y"], (n, thumbs, stack)  # first
        if n == 1 and width > 360:  # two columns wide, as tall as the buttons
            assert thumbs[0]["width"] > 2 * stack["width"] and abs(thumbs[0]["height"] - stack["height"]) <= 1
        elif n == 1:  # the one column left beside them
            assert abs(stack["width"] - thumbs[0]["width"]) <= 1, (n, thumbs, stack)
        else:  # a page's column, two pages high
            assert abs(stack["width"] - thumbs[0]["width"]) <= 1, (n, thumbs, stack)
            assert stack["height"] <= 2 * thumbs[0]["height"] + 16, (n, thumbs, stack)
        heights.append([t.bounding_box()["height"] for t in page.locator(".add-tile:visible").all()])
        assert min(heights[-1]) >= 44, n  # a finger's size
        assert max(heights[-1]) - min(heights[0]) <= 3, heights  # the same as pages come
        cut = "[...document.querySelectorAll('.add-stack .add-tile')].some(e => e.scrollWidth > e.clientWidth + 1)"
        assert not page.evaluate(cut), n
    assert thumbs[4]["x"] == stack["x"] and thumbs[4]["y"] > stack["y"] + stack["height"]  # the fifth under them


@pytest.mark.parametrize("width", [360, 380, 400, 420, 440, 460])
def test_the_one_page_beside_the_add_buttons_with_the_text_twice_as_large(page, width):
    """The phone's text twice as large (Android's font size): a lesson's one page beside the
    buttons still, whatever columns the strip has. (A gap in rem moved two columns' width
    from the query's, and the page went under them again.)"""
    page.set_viewport_size({"width": width, "height": 860})
    page.goto("/")
    page.add_style_tag(content="html { font-size: 200%; }")
    page.locator('input[type=file][accept="image/*"][multiple]').set_input_files(
        {"name": "page-1.png", "mimeType": "image/png", "buffer": plain_image(300, 400, "red")}
    )
    sync_api.expect(page.locator(".thumb img")).to_have_count(1)
    thumb, stack = page.locator(".thumb").bounding_box(), page.locator(".add-stack").bounding_box()
    assert thumb["x"] > stack["x"] + stack["width"] and thumb["y"] == stack["y"], (thumb, stack)


def test_the_add_buttons_off_once_the_lesson_has_its_ten_pages(page):
    """Ten pages, a lesson's most: the add buttons off, the camera's saying so; a page
    removed, on again."""
    page.goto("/")
    page.locator('input[type=file][accept="image/*"][multiple]').set_input_files(
        [{"name": f"page-{n}.png", "mimeType": "image/png", "buffer": plain_image(300, 400, "red")} for n in range(10)]
    )
    sync_api.expect(page.locator(".thumb img")).to_have_count(10)
    sync_api.expect(page.locator(".add-tile.primary")).to_contain_text("10 pages au plus")
    for chooser in page.locator(".add-stack input[type=file]").all():
        sync_api.expect(chooser).to_be_disabled()
    page.locator(".thumb-remove").first.click()
    sync_api.expect(page.locator(".add-tile.primary")).to_contain_text("Page suivante")
    for chooser in page.locator(".add-stack input[type=file]").all():
        sync_api.expect(chooser).to_be_enabled()


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


def test_a_photo_put_in_place_of_another_turns_itself(page):
    """A saved lesson's photo removed, another chosen from the gallery, then turned: that one
    turned, in the page. It turned the lesson's old photo at the server, by its number, and
    showed it in place of the new one (the page's photos no longer the server's)."""
    page.goto("/")
    gallery = page.locator('input[type=file][accept="image/*"][multiple]')
    gallery.set_input_files({"name": "p1.png", "mimeType": "image/png", "buffer": png("white")})
    page.locator(".chip").first.click()  # the free prompt
    page.locator("textarea[x-ref=promptText]").fill(FRONT_PROMPT)
    page.get_by_role("button", name="✨ Générer les cartes").click()
    page.locator(".flash").first.wait_for()
    (summary,) = lessons(page)

    page.locator(".thumb-remove").first.click()
    gallery.set_input_files({"name": "p2.png", "mimeType": "image/png", "buffer": png("blue")})
    sync_api.expect(page.locator(".thumb-rotate")).to_have_count(1)
    shown = "Alpine.$data(document.querySelector('[x-data]')).photos[0].blob"
    page.evaluate(f"window.before = {shown}")
    page.locator(".thumb-rotate").first.click()
    page.wait_for_function(f"{shown} !== window.before")  # turned, wherever it was
    data = page.evaluate(
        """async () => {
            const blob = Alpine.$data(document.querySelector('[x-data]')).photos[0].blob;
            const bytes = new Uint8Array(await blob.arrayBuffer());
            let s = "";
            for (const b of bytes) s += String.fromCharCode(b);
            return btoa(s);
        }"""
    )
    shown = PILImage.open(io.BytesIO(base64.b64decode(data))).convert("RGB")
    assert shown.size == (800, 600)  # turned: 600 × 800 before
    red, green, blue = shown.getpixel((400, 300))
    assert blue > 200 and red < 60, (red, green, blue)  # the new photo, not the lesson's white one
    assert lesson(page, summary["id"])["photo_count"] == 1  # the lesson's own untouched until sent


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
