"""Step 1, the photos: taken, from the gallery or a PDF, beside the add buttons, seen in full,
turned, a part hidden, cropped, the next pages added."""

import base64
import io
import re
import time

import pytest
from helpers import plain_image
from PIL import Image as PILImage

sync_api = pytest.importorskip("playwright.sync_api")

from page.support import (  # noqa: E402
    CROP_BUTTON,
    FRONT_PROMPT,
    HIDE_BUTTON,
    PDF_NOTICE,
    add_pdf_pages,
    add_photo,
    add_text_pdf,
    close_viewer,
    crop_box,
    crop_corner,
    draft_kept,
    drop,
    editor_pixel,
    eventually,
    field,
    generate_free,
    generate_from_photos,
    halves,
    lesson,
    lessons,
    open_card,
    open_hide,
    open_prompt,
    pdf,
    photo_not_sent,
    photo_sent,
    png,
    settled,
    started,
    stroke,
    text_pdf,
)


def test_the_main_button_takes_the_first_photo(page):
    """No photo yet: "📷 Photographiez la leçon" is not a dead button, it opens the camera; which
    may give several pages at once (the Android app's document scanner)."""
    page.goto("/")
    start = page.get_by_role("button", name="📷 Photographiez la leçon")
    sync_api.expect(start).to_be_enabled()
    with page.expect_file_chooser() as chooser:
        start.click()
    assert chooser.value.element.get_attribute("capture") == "environment"
    assert chooser.value.is_multiple()


def test_photos_and_pictures_seen_in_full(page):
    page.goto("/")
    page.locator('input[type=file][accept="image/*"][multiple]:not([capture])').set_input_files(
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

    # A card's figure too, alone: no arrows. In the card open, its page first, the picture on it
    generate_free(page, "Le triangle rectangle (géométrie)")
    open_card(page.locator(".flash").first).locator(".card-picture img").first.click()
    page.get_by_role("dialog", name="Image").locator(".picture-shown").click()
    sync_api.expect(viewer).to_be_visible()
    sync_api.expect(viewer.locator(".viewer-nav")).to_have_count(0)


def test_a_picture_zoomed_with_two_fingers_then_moved(page):
    """In full, a picture zoomed with two fingers about the point between them, moved with one,
    never off the screen; zoomed in, a swipe turns no page; pinched back, the whole picture."""
    page.set_viewport_size({"width": 360, "height": 780})
    page.goto("/")
    page.locator('input[type=file][accept="image/*"][multiple]:not([capture])').set_input_files(
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
    hidden from there (its editor above the viewer): from there only, the thumbnail has ✕ alone."""
    page.goto("/")
    page.locator('input[type=file][accept="image/*"][multiple]:not([capture])').set_input_files(
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
    viewer.get_by_role("button", name=HIDE_BUTTON, exact=True).click()
    sync_api.expect(page.get_by_role("dialog", name="Préparer la photo")).to_be_visible()
    page.keyboard.press("Escape")  # the editor closes, the viewer stays
    sync_api.expect(page.get_by_role("dialog", name="Préparer la photo")).to_be_hidden()
    sync_api.expect(viewer).to_be_visible()


def test_pdf_pages_become_photos(page):
    page.goto("/")
    pdf_input = page.locator("input[type=file][accept*=pdf]")
    pdf_input.set_input_files({"name": "une-page.pdf", "mimeType": "application/pdf", "buffer": pdf(1)})
    sync_api.expect(page.locator(".thumb img")).to_have_count(1)  # one page: no question
    page.locator(".thumb").get_by_role("button", name=re.compile("Retirer")).first.click()
    sync_api.expect(page.locator(".thumb img")).to_have_count(0)

    # Several pages: seen before they are added, all ticked when they fit; one untouched
    pdf_input.set_input_files({"name": "cours.pdf", "mimeType": "application/pdf", "buffer": pdf(4)})
    sheet = page.locator(".sheet", has=page.locator(".pdf-pages"))
    sync_api.expect(sheet).to_contain_text("« cours.pdf » a 4 pages : touchez celles à ne pas ajouter")
    sync_api.expect(sheet.get_by_role("button", name="Page 4", exact=True)).to_have_attribute("aria-pressed", "true")
    sheet.get_by_role("button", name="Page 4", exact=True).click()
    sheet.get_by_role("button", name="Ajouter 3 pages").click()
    sync_api.expect(page.locator(".thumb img")).to_have_count(3)
    assert page.evaluate("img => img.naturalHeight", page.locator(".thumb img").first.element_handle()) == 1600

    # More pages than places left (30 − 3): the user picks them
    pdf_input.set_input_files({"name": "manuel.pdf", "mimeType": "application/pdf", "buffer": pdf(28)})
    sheet = page.locator(".sheet", has=page.locator(".pdf-pages"))
    sync_api.expect(sheet).to_be_visible()
    said = "« manuel.pdf » a 28 pages : choisissez-en 27 au plus (une leçon tient en 30 pages"
    sync_api.expect(sheet).to_contain_text(said)
    sync_api.expect(sheet.locator(".pdf-page img").first).to_be_visible()  # thumbnails drawn
    for n in range(1, 28):
        sheet.get_by_role("button", name=f"Page {n}", exact=True).click()
    sync_api.expect(sheet.get_by_role("button", name="Page 28", exact=True)).to_be_disabled()
    sheet.get_by_role("button", name="Page 27", exact=True).click()  # one less
    sheet.get_by_role("button", name="Page 28", exact=True).click()
    sheet.get_by_role("button", name="Ajouter 27 pages").click()
    sync_api.expect(page.locator("figure.thumb img")).to_have_count(30)
    sync_api.expect(sheet).to_be_hidden()

    # Full: said, not added
    pdf_input.set_input_files({"name": "encore.pdf", "mimeType": "application/pdf", "buffer": pdf(1)})
    sync_api.expect(page.get_by_text("Déjà 30 pages")).to_be_visible()
    sync_api.expect(page.locator("figure.thumb img")).to_have_count(30)


def test_more_pages_than_one_call_reads_are_sent_in_several(page):
    """A PDF of 12 pages: the AI reads 10 at a time. The first 10 make the lesson, the next 2
    complete it, at one click; every page in the lesson, none left to send."""
    calls = []
    page.on(
        "request",
        lambda r: (
            calls.append(r.url.split("/")[-1])
            if r.method == "POST" and ("/api/extract" in r.url or r.url.endswith("/complete"))
            else None
        ),
    )
    page.goto("/")
    page.locator("input[type=file][accept*=pdf]").set_input_files(
        {"name": "cours.pdf", "mimeType": "application/pdf", "buffer": pdf(12)}
    )
    add_pdf_pages(page, 12)
    sync_api.expect(page.locator("figure.thumb img")).to_have_count(12)
    made = generate_from_photos(page, "FR → ES")
    page.wait_for_function("() => !document.querySelector('[x-data]')._x_dataStack[0].loading")  # every call made
    made = lesson(page, made["id"])
    # the server reads 10 pages a call at most: 12 pages in two calls, the second completing
    assert (made["photo_count"], len(made["ai_calls"])) == (12, 2)
    assert calls == ["extract", "complete"]
    assert page.evaluate("() => document.querySelector('[x-data]')._x_dataStack[0].newPages().length") == 0


def test_a_lesson_read_in_several_calls_has_its_pictures_drawn_once_after_the_last(page):
    """12 pages read in two calls, its cards asking for figures: their pictures asked once,
    after the second call (drawn after each, the first drawing wrote back the cards it began
    with, the next pages' gone, and the second drew the first pages' again). Photos, not a
    PDF: what is tested is the calls, not pdf.js drawing 12 pages (slow on a busy machine)."""
    calls = []
    page.on(
        "request",
        lambda r: (
            calls.append(r.url.split("/")[-1])
            if r.method == "POST" and re.search(r"/api/extract$|/complete$|/pictures$", r.url)
            else None
        ),
    )
    page.route(
        "**/api/lessons/*/pictures",
        lambda route: route.fulfill(json={"lesson": {"cards": []}, "failures": 0, "error": None, "to_draw": []}),
    )
    page.goto("/")
    page.locator('input[type=file][accept="image/*"][multiple]:not([capture])').set_input_files(
        [
            {"name": f"page{n}.png", "mimeType": "image/png", "buffer": plain_image(60, 80, (20 * n, 90, 160), "PNG")}
            for n in range(12)
        ]
    )
    sync_api.expect(page.locator("figure.thumb img")).to_have_count(12)
    made = generate_from_photos(page, "Le triangle rectangle (géométrie)")  # figures to draw
    page.wait_for_function("() => !document.querySelector('[x-data]')._x_dataStack[0].loading")  # every call made
    assert any(c["figure"] for c in lesson(page, made["id"])["cards"])
    settled(page)  # a drawing asked late, once an answer is read, would be seen
    assert calls == ["extract", "complete", "pictures"]


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
    went under them); more, beside them, then under them on a narrow phone (more than four:
    test_more_pages_than_the_strip_holds). (Three stacked in a page's
    cell made it half as tall again as the pages.)"""
    page.set_viewport_size({"width": width, "height": 860})
    page.goto("/")
    heights = []
    for n, color in enumerate(("red", "blue", "green", "orange"), start=1):
        page.locator('input[type=file][accept="image/*"][multiple]:not([capture])').set_input_files(
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
    if width == 360:  # two columns: the third and fourth under them
        assert thumbs[2]["x"] == stack["x"] and thumbs[2]["y"] > stack["y"] + stack["height"]


@pytest.mark.parametrize("width", [360, 380, 400, 420, 440, 460])
def test_the_one_page_beside_the_add_buttons_with_the_text_twice_as_large(page, width):
    """The phone's text twice as large (Android's font size): a lesson's one page beside the
    buttons still, whatever columns the strip has. (A gap in rem moved two columns' width
    from the query's, and the page went under them again.)"""
    page.set_viewport_size({"width": width, "height": 860})
    page.goto("/")
    page.add_style_tag(content="html { font-size: 200%; }")
    page.locator('input[type=file][accept="image/*"][multiple]:not([capture])').set_input_files(
        {"name": "page-1.png", "mimeType": "image/png", "buffer": plain_image(300, 400, "red")}
    )
    sync_api.expect(page.locator(".thumb img")).to_have_count(1)
    # Once laid out (the larger text and the page's image come after the page): measured then
    page.wait_for_function(
        """() => {
          const t = document.querySelector('.thumb').getBoundingClientRect();
          const s = document.querySelector('.add-stack').getBoundingClientRect();
          return t.x > s.x + s.width && Math.abs(t.y - s.y) < 0.5;
        }""",
        timeout=5000,
    )


def test_the_add_buttons_off_once_the_lesson_has_its_thirty_pages(page):
    """Thirty pages, a lesson's most: the add buttons off, the camera's saying so; a page
    removed, on again."""
    page.goto("/")
    page.locator('input[type=file][accept="image/*"][multiple]:not([capture])').set_input_files(
        [{"name": f"page-{n}.png", "mimeType": "image/png", "buffer": plain_image(300, 400, "red")} for n in range(30)]
    )
    sync_api.expect(page.locator("figure.thumb img")).to_have_count(30)
    sync_api.expect(page.locator(".add-tile.primary")).to_contain_text("30 pages au plus")
    for chooser in page.locator(".add-stack input[type=file]").all():
        sync_api.expect(chooser).to_be_disabled()
    page.locator(".thumb-remove").first.click()
    sync_api.expect(page.locator(".thumb-more")).to_have_text("+26")  # 29 pages: three, then "+26"
    sync_api.expect(page.locator(".add-tile.primary")).to_contain_text("Page suivante")
    for chooser in page.locator(".add-stack input[type=file]").all():
        sync_api.expect(chooser).to_be_enabled()


def test_the_camera_off_while_the_pages_given_are_read(page):
    """Pages given (the app's scanner, the gallery) are read one by one: meanwhile the camera's
    input is off, its next capture would empty the app's folder they are read from (pages
    "unreadable") and tell its scanner the places left before them."""
    page.goto("/")
    camera = page.locator("input[type=file][capture]")
    sync_api.expect(camera).to_be_enabled()
    page.evaluate(
        """() => {
          const held = new Promise((go) => { window.readOn = go; });
          const real = window.resize;
          window.resize = async (file) => { await held; return real(file); };
        }"""
    )
    page.locator('input[type=file][accept="image/*"][multiple]:not([capture])').set_input_files(
        [{"name": f"page-{n}.png", "mimeType": "image/png", "buffer": png("white")} for n in (1, 2)]
    )
    sync_api.expect(camera).to_be_disabled()
    page.evaluate("window.readOn()")
    sync_api.expect(page.locator(".thumb img")).to_have_count(2)
    sync_api.expect(camera).to_be_enabled()


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
    close_viewer(page)
    sync_api.expect(page.locator(".thumb-masked:visible")).to_have_count(1)
    # On the page: its number, ✕, and the mark of what it hides (turned, hidden from the viewer)
    sync_api.expect(page.locator(".strip figure.thumb button")).to_have_count(1)
    sync_api.expect(page.locator(".strip figure.thumb button")).to_have_text("✕")

    saved = generate_from_photos(page, "Une carte par mot")
    sent = PILImage.open(io.BytesIO(page.request.get(f"/api/lessons/{saved['id']}/photos/1").body())).convert("L")
    width, height = sent.size
    assert sent.getpixel((width // 2, height // 10)) < 40  # black: the name
    assert sent.getpixel((width // 2, height // 2)) > 215  # white: un-blacked
    assert sent.getpixel((width // 2, height * 8 // 10)) > 215  # never touched
    page.locator(".strip .thumb img").first.click()
    hide = page.locator(".viewer").get_by_role("button", name=HIDE_BUTTON, exact=True)
    sync_api.expect(hide).to_be_hidden()  # sent: nothing left to hide


def test_done_the_viewer_shows_the_photo_hidden_at_once(page):
    """ "Terminé": the viewer under the editor already shows the blacked-out photo when the
    editor goes, never the photo as it was for an instant (the name seen again: a parent
    thinks it wasn't hidden)."""
    page.goto("/")
    add_photo(page, png("white"))
    editor = open_hide(page)
    stroke(page, 0.1)  # the name
    # What the viewer shows the moment the editor is hidden
    page.evaluate("""() => {
        const editor = document.querySelector('.hide-editor');
        window.seenWhenClosed = null;
        new MutationObserver(() => {
            if (window.seenWhenClosed || getComputedStyle(editor).display !== 'none') return;
            const img = document.querySelector('.viewer-frame img');
            const canvas = document.createElement('canvas');
            canvas.width = img.naturalWidth || 1;
            canvas.height = img.naturalHeight || 1;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0);
            const top = ctx.getImageData(canvas.width / 2, canvas.height / 10, 1, 1).data;
            window.seenWhenClosed = { complete: img.complete && img.naturalWidth > 0, top: top[0], alpha: top[3] };
        }).observe(editor, { attributes: true });
    }""")
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(editor).to_be_hidden()
    seen = page.evaluate("window.seenWhenClosed")
    assert seen["complete"], seen  # the new photo decoded, not loading
    assert seen["alpha"] == 255 and seen["top"] < 40, seen  # black where the name was


def test_a_pdf_page_with_a_hidden_part_goes_without_its_text(page, browser):
    """Its text holds the hidden name too: the page is sent as a picture only, and the editor says so."""
    page.goto("/")
    add_text_pdf(page, browser)
    editor = open_hide(page)
    sync_api.expect(editor.get_by_text(PDF_NOTICE)).to_be_visible()
    stroke(page, 0.1)
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(editor).to_be_hidden()
    close_viewer(page)

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
    sync_api.expect(page.locator(".thumb-masked:visible")).to_have_count(1)

    open_hide(page)
    editor.get_by_role("button", name="Tout dénoircir").click()
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(editor).to_be_hidden()
    sync_api.expect(page.locator(".thumb-masked:visible")).to_have_count(0)
    assert photo_not_sent(page).tobytes() == original.tobytes()
    close_viewer(page)

    saved = generate_from_photos(page, "Une carte par date")
    assert saved["page_texts"] == ["La Révolution française\nEn 1789, le peuple de Paris prend la Bastille."]


def test_hidden_parts_seen_again_and_cancel_changes_nothing(page):
    """The editor reopened shows what is blacked out; "Annuler" leaves the photo and its mask as they were."""
    page.goto("/")
    add_photo(page, png("white"))
    editor = open_hide(page)
    stroke(page, 0.1)
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(page.locator(".thumb-masked:visible")).to_have_count(1)  # done: the photo blacked out
    hidden = photo_not_sent(page)

    open_hide(page)
    assert editor_pixel(page, 0.5, 0.1) < 40  # still blacked out
    assert editor_pixel(page, 0.5, 0.5) > 215
    editor.get_by_role("button", name="Tout dénoircir").click()  # then thought better of it
    stroke(page, 0.5)
    editor.get_by_role("button", name="Annuler").click()
    sync_api.expect(editor).to_be_hidden()
    sync_api.expect(page.locator(".thumb-masked:visible")).to_have_count(1)
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
    sync_api.expect(page.locator(".thumb-masked:visible")).to_have_count(1)
    page.locator(".viewer").get_by_role("button", name="Tourner la photo d'un quart de tour").click()
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
    sync_api.expect(page.locator(".thumb-masked:visible")).to_have_count(0)
    original = photo_not_sent(page)  # the turned original, all white
    assert original.size == (800, 600)
    assert original.getextrema()[0] > 215


BLUE = (0, 0, 255)
RED = (255, 0, 0)


def near(pixel, color, tolerance=60) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(pixel, color, strict=True))


def thumb_size(page) -> tuple[int, int]:
    """The first thumbnail's picture, in pixels, once shown."""
    page.wait_for_function("(i => i && i.complete && i.naturalWidth > 0)(document.querySelector('.strip .thumb img'))")
    return tuple(page.evaluate("(i => [i.naturalWidth, i.naturalHeight])(document.querySelector('.strip .thumb img'))"))


def test_a_photo_cropped_by_its_frames_corners(page):
    """ "Recadrer": the frame on the whole photo at first, its corners dragged; only the part kept
    is shown and sent (the thumbnail, the AI's photo, the lesson's)."""
    page.goto("/")
    add_photo(page, halves())  # 600 × 800, red | blue
    editor = open_hide(page)
    sync_api.expect(page.locator(".hide-stage .crop-frame")).to_be_hidden()  # blacking out: no frame
    editor.get_by_role("button", name="Recadrer", exact=True).click()
    sync_api.expect(page.locator(".hide-stage .crop-handle:visible")).to_have_count(4)
    assert crop_box(page) == [0, 0, 1, 1]  # the whole photo at first
    crop_corner(page, "nw", 0.5, 0.25)  # the blue half, its top quarter left out
    assert crop_box(page) == pytest.approx([0.5, 0.25, 1, 1], abs=0.01)
    stroke(page, 0.5)  # cropping: no stroke blacks anything out
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(editor).to_be_hidden()
    close_viewer(page)

    width, height = thumb_size(page)
    assert (width, height) == pytest.approx((300, 600), abs=6)
    kept = photo_not_sent(page, mode="RGB")
    assert kept.size == (width, height)
    assert all(near(kept.getpixel(at), BLUE) for at in [(5, 5), (width // 2, height // 2), (width - 5, height - 5)])
    sync_api.expect(page.locator(".thumb-masked:visible")).to_have_count(0)  # nothing blacked out

    sent = []
    page.on("request", lambda r: sent.append(r) if r.url.endswith("/api/extract") else None)
    saved = generate_from_photos(page, "Une carte par mot")
    assert sent  # what the AI was sent: the cropped photo, as the lesson keeps it
    photo = photo_sent(page, saved["id"])
    assert photo.size == (width, height)
    assert near(photo.getpixel((width // 2, height // 2)), BLUE)


def test_the_viewers_crop_and_black_out_buttons_open_the_editor_in_their_mode(page):
    """Two buttons, one editor: the crop one opens it cropping (the frame's corners), 🖍️ blacking
    out (no frame); its modes in that order, cropping first; its title speaks of both."""
    page.goto("/")
    add_photo(page, halves())
    editor = open_hide(page, crop=True)
    sync_api.expect(page.get_by_role("dialog", name="Préparer la photo")).to_be_visible()
    modes = editor.locator(".hide-modes button")
    sync_api.expect(modes).to_have_text(["Recadrer", "⬛ Noircir", "◻️ Dénoircir"])
    sync_api.expect(editor.get_by_role("button", name="Recadrer", exact=True)).to_have_attribute("aria-pressed", "true")
    sync_api.expect(page.locator(".hide-stage .crop-handle:visible")).to_have_count(4)
    sync_api.expect(editor.get_by_role("button", name="Tout garder")).to_be_visible()
    editor.get_by_role("button", name="Annuler").click()
    sync_api.expect(editor).to_be_hidden()

    open_hide(page)  # 🖍️
    paint, crop = (editor.get_by_role("button", name=name, exact=True) for name in ("Noircir", "Recadrer"))
    sync_api.expect(paint).to_have_attribute("aria-pressed", "true")
    sync_api.expect(crop).to_have_attribute("aria-pressed", "false")
    sync_api.expect(page.locator(".hide-stage .crop-frame")).to_be_hidden()
    sync_api.expect(editor.get_by_role("button", name="Tout dénoircir")).to_be_visible()


def test_cropping_turned_off_by_the_relay(page):
    """lesson.crop turned off (relay_api.FEATURES): no crop button in the viewer, the editor
    blacking out only (no "Recadrer" mode, its hint not naming it). A photo cropped before
    stays cropped: its crop may have cut a name out of the page."""
    viewer = page.locator(".viewer")
    crop_button = viewer.get_by_role("button", name=CROP_BUTTON, exact=True)
    page.goto("/")
    add_photo(page, halves())
    editor = open_hide(page, crop=True)  # on: the crop button, the "Recadrer" mode
    sync_api.expect(editor.locator(".hide-modes button")).to_have_text(["Recadrer", "⬛ Noircir", "◻️ Dénoircir"])
    crop_corner(page, "nw", 0.5, 0.25)
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(editor).to_be_hidden()
    close_viewer(page)
    cropped = thumb_size(page)
    assert cropped == pytest.approx((300, 600), abs=6)

    page.evaluate("Alpine.$data(document.querySelector('[x-data]')).switches.disabled = ['lesson.crop']")
    page.locator(".strip .thumb img").first.click()
    sync_api.expect(viewer.get_by_role("button", name=HIDE_BUTTON, exact=True)).to_be_visible()
    sync_api.expect(crop_button).to_be_hidden()
    editor = open_hide(page)
    sync_api.expect(editor.locator(".hide-modes button:visible")).to_have_text(["⬛ Noircir", "◻️ Dénoircir"])
    sync_api.expect(editor.locator(".hide-hint")).not_to_contain_text("Recadrer")
    sync_api.expect(page.locator(".hide-stage .crop-handle:visible")).to_have_count(0)
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(editor).to_be_hidden()
    close_viewer(page)
    assert thumb_size(page) == cropped  # the crop made before kept

    page.route(
        "**/api/switches",
        lambda route: route.fulfill(
            json={"notice": None, "disabled": ["lesson.crop"], "update": False, "store": "", "trial": None}
        ),
    )
    draft_kept(page)
    page.goto("/")  # told by the relay as the page loads; the photo in progress kept, cropped
    sync_api.expect(page.locator(".strip .thumb img")).to_have_count(1)
    assert thumb_size(page) == cropped
    page.locator(".strip .thumb img").first.click()
    sync_api.expect(viewer.get_by_role("button", name=HIDE_BUTTON, exact=True)).to_be_visible()
    sync_api.expect(crop_button).to_be_hidden()


@pytest.mark.parametrize("lang", ["en", "fr", "es", "de", "it", "pt"])
def test_the_editors_buttons_fit_a_narrow_phone(page, browser, server, lang):
    """Opened by the crop button on a 360-pixel-wide phone: its three modes and its actions all on the
    screen, in every language (none cut at an edge)."""
    context = browser.new_context(locale="fr-FR", viewport={"width": 360, "height": 780}, base_url=server)
    context.add_init_script(f"localStorage.setItem('notosaurus.lang', '{lang}')")
    try:
        other = context.new_page()
        other.goto("/")
        other.wait_for_function("document.documentElement.classList.contains('i18n-ready')")
        add_photo(other, halves())
        other.locator(".strip .thumb img").first.click()
        other.locator(".viewer-actions button").nth(2).click()  # crop
        sync_api.expect(other.locator(".hide-stage .crop-handle:visible")).to_have_count(4)
        cut = other.evaluate("""() => [...document.querySelectorAll('.hide-tools button')]
            .filter((b) => b.offsetParent)
            .map((b) => [b.textContent.trim(), b.getBoundingClientRect()])
            .filter(([, r]) => r.left < 0 || r.right > innerWidth)
            .map(([text]) => text)""")
        assert cut == []
    finally:
        context.close()


def test_each_viewer_button_marked_by_what_it_did(page):
    """The crop button drawn with Material's crop icon (vendor/material, no emoji in it). Once
    the photo is cropped, a dot in its corner (its background kept: a filled button reads as
    pressed), told to screen readers; 🖍️'s dot once something is blacked out on it."""
    page.goto("/")
    add_photo(page, halves())
    viewer = page.locator(".viewer")
    crop, hide = (viewer.get_by_role("button", name=name, exact=True) for name in (CROP_BUTTON, HIDE_BUTTON))
    dot = "e => getComputedStyle(e, '::after').content"
    background = "e => getComputedStyle(e).backgroundColor"
    page.locator(".strip .thumb img").first.click()
    sync_api.expect(crop).to_have_text("")
    assert "vendor/material/crop.svg" in crop.locator(".crop-icon").evaluate("e => getComputedStyle(e).maskImage")
    assert page.request.get("/vendor/material/crop.svg").headers["content-type"].startswith("image/svg+xml")
    before = crop.evaluate(background)
    for button in (crop, hide):
        assert button.evaluate(dot) == "none"
        sync_api.expect(button).not_to_have_attribute("aria-describedby", re.compile("."))

    editor = open_hide(page, crop=True)
    # Its mode in the editor: the same icon, its name kept
    mode = editor.get_by_role("button", name="Recadrer", exact=True)
    assert "vendor/material/crop.svg" in mode.locator(".crop-icon").evaluate("e => getComputedStyle(e).maskImage")
    sync_api.expect(mode).not_to_contain_text("✂️")
    crop_corner(page, "nw", 0.5, 0)
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(editor).to_be_hidden()
    sync_api.expect(crop).to_have_accessible_description("Page recadrée")
    assert crop.evaluate(dot) != "none"
    assert crop.evaluate(background) == before
    assert hide.evaluate(dot) == "none"
    sync_api.expect(hide).not_to_have_attribute("aria-describedby", re.compile("."))

    open_hide(page)
    stroke(page, 0.5)
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(editor).to_be_hidden()
    sync_api.expect(hide).to_have_accessible_description("Une partie de cette page est cachée")
    assert hide.evaluate(dot) != "none"
    assert hide.evaluate(background) == before


def test_crop_and_black_out_gone_once_the_photo_is_sent(page):
    """Both buttons on a photo not sent yet; neither once it is (what was sent can't change)."""
    page.goto("/")
    add_photo(page, png("white"))
    viewer = page.locator(".viewer")
    page.locator(".strip .thumb img").first.click()
    for name in (CROP_BUTTON, HIDE_BUTTON):
        sync_api.expect(viewer.get_by_role("button", name=name, exact=True)).to_be_visible()
    close_viewer(page)
    generate_from_photos(page, "Une carte par mot")
    page.locator(".strip .thumb img").first.click()
    sync_api.expect(viewer.get_by_role("button", name="Tourner la photo d'un quart de tour")).to_be_visible()
    for name in (CROP_BUTTON, HIDE_BUTTON):
        sync_api.expect(viewer.get_by_role("button", name=name, exact=True)).to_be_hidden()


def test_keep_it_all_gives_the_whole_photo_and_its_text_back(page, browser):
    """A PDF page cropped goes without its text (it holds what is cropped out); "Tout garder"
    then done: the original page, its text sent with it again."""
    page.goto("/")
    add_text_pdf(page, browser)
    original = photo_not_sent(page)
    editor = open_hide(page)
    crop_corner(page, "se", -0.5, -0.5)
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(editor).to_be_hidden()
    assert photo_not_sent(page).size[0] < original.size[0] * 0.6
    assert page.evaluate("Alpine.$data(document.querySelector('[x-data]')).photos[0].text") == ""

    open_hide(page)
    editor.get_by_role("button", name="Recadrer", exact=True).click()
    assert crop_box(page) == pytest.approx([0, 0, 0.5, 0.5], abs=0.01)  # the frame where it was left
    editor.get_by_role("button", name="Tout garder").click()
    assert crop_box(page) == [0, 0, 1, 1]
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(editor).to_be_hidden()
    assert photo_not_sent(page).tobytes() == original.tobytes()
    close_viewer(page)
    saved = generate_from_photos(page, "Une carte par date")
    assert saved["page_texts"] == ["La Révolution française\nEn 1789, le peuple de Paris prend la Bastille."]


def test_a_photo_turned_turns_its_crop(page):
    """↻ on a portrait photo cropped to its right (blue) half: the bottom half of the landscape
    one, the frame turned with it."""
    page.goto("/")
    add_photo(page, halves())
    editor = open_hide(page)
    crop_corner(page, "nw", 0.5, 0)
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(editor).to_be_hidden()
    page.locator(".viewer").get_by_role("button", name="Tourner la photo d'un quart de tour").click()
    page.wait_for_function("document.querySelector('.thumb img').naturalWidth === 800")  # turned: 800 × 300
    turned = photo_not_sent(page, mode="RGB")
    assert turned.size == pytest.approx((800, 300), abs=6)
    assert near(turned.getpixel((400, 150)), BLUE)

    open_hide(page)
    editor.get_by_role("button", name="Recadrer", exact=True).click()
    assert crop_box(page) == pytest.approx([0, 0.5, 1, 1], abs=0.01)  # the original's bottom half
    editor.get_by_role("button", name="Tout garder").click()
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(editor).to_be_hidden()
    whole = photo_not_sent(page, mode="RGB")  # the turned original: red on top, blue below
    assert whole.size == (800, 600)
    assert near(whole.getpixel((400, 100)), RED) and near(whole.getpixel((400, 500)), BLUE)


def test_a_photo_cropped_and_blacked_out(page):
    """Both together: blacked out, then cropped; the editor reopened shows both, the photo sent
    is the part kept with what is blacked out in it."""
    page.goto("/")
    add_photo(page, halves())
    editor = open_hide(page)
    stroke(page, 0.5)  # a band across the middle
    crop_corner(page, "nw", 0.5, 0.25)  # the blue half's lower part
    editor.get_by_role("button", name="Noircir", exact=True).click()
    stroke(page, 0.9)  # blacked out once cropped too: the whole photo's mask
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(editor).to_be_hidden()
    sync_api.expect(page.locator(".thumb-masked:visible")).to_have_count(1)

    kept = photo_not_sent(page, mode="RGB")
    assert kept.size == pytest.approx((300, 600), abs=6)
    w, h = kept.size
    # the original's y = 400, 720, 600 → the part kept's 200, 520, 400
    assert near(kept.getpixel((w // 2, h * 200 // 600)), (0, 0, 0))
    assert near(kept.getpixel((w // 2, h * 520 // 600)), (0, 0, 0))
    assert near(kept.getpixel((w // 2, h * 400 // 600)), BLUE)

    open_hide(page)  # the whole photo again, what is blacked out on it, the frame where it was
    assert editor_pixel(page, 0.2, 0.5) < 40  # the band, on the red half left out too
    assert editor_pixel(page, 0.2, 0.75) > 40
    assert crop_box(page) == pytest.approx([0.5, 0.25, 1, 1], abs=0.01)
    editor.get_by_role("button", name="Annuler").click()
    sync_api.expect(editor).to_be_hidden()
    close_viewer(page)
    saved = generate_from_photos(page, "Une carte par mot")
    photo = photo_sent(page, saved["id"])
    assert photo.size == (w, h)
    assert near(photo.getpixel((w // 2, h * 200 // 600)), (0, 0, 0))
    assert near(photo.getpixel((w // 2, h * 400 // 600)), BLUE)


def test_a_cropped_photo_found_again_after_a_reload(page):
    """The lesson in progress kept by the host (the draft): its photo found again cropped."""
    page.goto("/")
    started(page)
    add_photo(page, halves())
    editor = open_hide(page)
    crop_corner(page, "nw", 0.5, 0.25)
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(editor).to_be_hidden()
    close_viewer(page)
    page.wait_for_function(
        "(d => d.photos.length && d.draftPhotosSent === d.photos.map((p) => p.url).join(' '))"
        "(Alpine.$data(document.querySelector('[x-data]')))"
    )
    page.reload()
    started(page)
    sync_api.expect(page.locator(".strip .thumb img")).to_have_count(1)
    assert thumb_size(page) == pytest.approx((300, 600), abs=6)
    kept = photo_not_sent(page, mode="RGB")
    assert near(kept.getpixel((150, 300)), BLUE)


def test_a_photo_cropped_while_the_host_still_keeps_it_found_again_cropped(page):
    """The lesson in progress kept by the host one save after the other: the photo cropped
    while the host is still keeping it as it came (a slow save), the cropped one kept; the
    older save never lands after it (the name the crop cut out back after a restart)."""
    held, kept = [], []  # the first save, held; those after it, once the host has them

    def hold_the_first(route):
        if route.request.method != "PUT":
            route.continue_()
        elif not held:
            held.append(route)
        else:  # sent cropped or not: the photo as it is when it is sent
            cropped = page.evaluate("Boolean(Alpine.$data(document.querySelector('[x-data]')).photos[0].crop)")
            route.fulfill(response=route.fetch())
            kept.append(cropped)

    page.goto("/")
    started(page)
    page.route("**/api/draft", hold_the_first)
    add_photo(page, halves())
    while not held:  # the photo as it came, being kept
        page.wait_for_timeout(50)
    editor = open_hide(page)
    crop_corner(page, "nw", 0.5, 0.25)
    editor.get_by_role("button", name="Terminé").click()
    sync_api.expect(editor).to_be_hidden()
    # Sent at once (a moment after the change), the cropped photo would be kept before the
    # first save lands: given the time to
    for _ in range(40):
        if any(kept):
            break
        page.wait_for_timeout(50)
    held[0].continue_()
    draft_kept(page)
    photo = PILImage.open(io.BytesIO(page.request.get("/api/draft/photos/1").body()))
    assert photo.size == pytest.approx((300, 600), abs=6)


def test_a_photo_put_in_place_of_another_turns_itself(page):
    """A saved lesson's photo removed, another chosen from the gallery, then turned: that one
    turned, in the page. It turned the lesson's old photo at the server, by its number, and
    showed it in place of the new one (the page's photos no longer the server's)."""
    page.goto("/")
    gallery = page.locator('input[type=file][accept="image/*"][multiple]:not([capture])')
    gallery.set_input_files({"name": "p1.png", "mimeType": "image/png", "buffer": png("white")})
    page.locator(".chip").first.click()  # the free prompt
    page.locator("textarea[x-ref=promptText]").fill(FRONT_PROMPT)
    page.get_by_role("button", name="✨ Générer les cartes").click()
    page.locator(".flash").first.wait_for()
    (summary,) = lessons(page)

    page.locator(".thumb-remove").first.click()
    gallery.set_input_files({"name": "p2.png", "mimeType": "image/png", "buffer": png("blue")})
    sync_api.expect(page.locator(".thumb img")).to_have_count(1)
    shown = "Alpine.$data(document.querySelector('[x-data]')).photos[0].blob"
    page.evaluate(f"window.before = {shown}")
    page.locator(".thumb img").first.click()  # turned from the viewer
    page.locator(".viewer").get_by_role("button", name="Tourner la photo d'un quart de tour").click()
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
    gallery = page.locator('input[type=file][accept="image/*"][multiple]:not([capture])')
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
    add_pdf_pages(page, 2)
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


COLORS = ("red", "blue", "green", "orange", "purple", "yellow", "navy", "teal", "maroon", "olive")


@pytest.mark.parametrize("width", [360, 1280])
def test_more_pages_than_the_strip_holds(page, width):
    """More pages than the strip's two rows hold beside the add buttons (four on a narrow phone,
    as many as its columns give on a wider screen): the section no taller than with four, its
    last place the next page veiled, "+N" (the pages not shown, itself with them), opening
    them all in a sheet, in order, each with its ✕; a tap there shows one in full."""
    page.set_viewport_size({"width": width, "height": 780})
    page.goto("/")
    gallery = page.locator('input[type=file][accept="image/*"][multiple]:not([capture])')

    def add(colors, start):
        files = [
            {"name": f"page-{n}.png", "mimeType": "image/png", "buffer": plain_image(300, 400, color)}
            for n, color in enumerate(colors, start=start)
        ]
        gallery.set_input_files(files)

    add(COLORS[:4], 1)
    sync_api.expect(page.locator(".strip figure.thumb img")).to_have_count(4)
    section = page.locator("section.panel").filter(has=page.locator(".strip"))
    four = section.bounding_box()["height"]
    sync_api.expect(page.locator(".thumb-more")).to_have_count(0)

    add(COLORS[4:], 5)
    sync_api.expect(page.locator(".strip figure.thumb")).to_have_count(10)
    columns = page.locator(".strip").evaluate("(e) => getComputedStyle(e).gridTemplateColumns.split(' ').length")
    capacity = max(4, 2 * (columns - 1))
    assert capacity == (4 if width == 360 else 2 * (columns - 1)) and (width == 360 or capacity > 4), columns
    shown = page.locator(".strip figure.thumb:visible")
    sync_api.expect(shown).to_have_count(capacity - 1)
    more = page.locator(".strip .thumb-more")
    sync_api.expect(more).to_have_text(f"+{10 - capacity + 1}")
    sync_api.expect(more.locator("button")).to_have_count(0)  # no buttons on it
    # As tall as with four (the buttons' 3:8 and two pages with their gap: a few px apart)
    assert abs(section.bounding_box()["height"] - four) <= 6
    last, tile = shown.last.bounding_box(), more.bounding_box()
    assert abs(tile["width"] - last["width"]) <= 1 and abs(tile["height"] - last["height"]) <= 1  # a page's place
    urls = [img.get_attribute("src") for img in page.locator(".strip figure.thumb img").all()]
    assert more.locator("img").get_attribute("src") == urls[capacity - 1]  # the next page, veiled

    more.click()
    sheet = page.get_by_role("dialog", name="Toutes les pages")
    sync_api.expect(sheet).to_be_visible()
    pages = sheet.locator("figure.thumb img")
    sync_api.expect(pages).to_have_count(10)
    assert [img.get_attribute("src") for img in pages.all()] == urls  # all of them, in order
    # No ✕ on its pages: a page removed by a stray tap no more; chosen, then removed together
    sync_api.expect(sheet.locator("figure.thumb button")).to_have_count(0)
    sheet.get_by_role("button", name="Sélectionner").click()
    sync_api.expect(sheet.get_by_role("heading")).to_have_text("0 page choisie")
    remove = sheet.get_by_role("button", name="🗑️ Retirer")
    sync_api.expect(remove).to_be_disabled()
    pages.nth(1).click()
    pages.nth(3).click()
    pages.nth(5).click()
    pages.nth(5).click()  # chosen, then not
    sync_api.expect(sheet.get_by_role("heading")).to_have_text("2 pages choisies")
    sync_api.expect(sheet.locator("figure.thumb.chosen")).to_have_count(2)
    sync_api.expect(page.locator(".viewer")).to_be_hidden()  # a tap chooses, it shows nothing
    remove.click()
    sync_api.expect(pages).to_have_count(8)
    del urls[3], urls[1]
    assert [img.get_attribute("src") for img in pages.all()] == urls
    sync_api.expect(sheet.get_by_role("heading")).to_have_text("Toutes les pages")

    # A long press chooses its page at once; "Annuler": none removed
    pages.nth(0).click(button="right")
    sync_api.expect(sheet.get_by_role("heading")).to_have_text("1 page choisie")
    sheet.get_by_role("button", name="Annuler").click()
    sync_api.expect(sheet.get_by_role("heading")).to_have_text("Toutes les pages")
    sync_api.expect(pages).to_have_count(8)

    pages.nth(2).click()
    viewer = page.locator(".viewer")
    sync_api.expect(viewer.locator(".viewer-count")).to_have_text("3 / 8")
    sync_api.expect(viewer.locator(".viewer-frame img")).to_have_attribute("src", urls[2])
    viewer.get_by_role("button", name="Retirer cette page").click()  # 🗑️
    sync_api.expect(pages).to_have_count(7)
    sync_api.expect(viewer.locator(".viewer-frame img")).to_have_attribute("src", urls[3])
    page.keyboard.press("Escape")  # the viewer closed, the sheet still there
    sync_api.expect(viewer).to_be_hidden()
    sync_api.expect(sheet).to_be_visible()
    page.keyboard.press("Escape")
    sync_api.expect(sheet).to_be_hidden()


def test_a_page_removed_from_the_viewer(page):
    """The viewer's 🗑️ (not a second ✕: the viewer's close): the page shown removed, the next
    one shown in its place (the one before when it was the last); the last page removed, the
    viewer closed."""
    page.goto("/")
    page.locator('input[type=file][accept="image/*"][multiple]:not([capture])').set_input_files(
        [{"name": f"page-{n}.png", "mimeType": "image/png", "buffer": png(c)} for n, c in enumerate(COLORS[:3])]
    )
    sync_api.expect(page.locator(".thumb img")).to_have_count(3)
    urls = [img.get_attribute("src") for img in page.locator(".thumb img").all()]
    page.locator(".thumb img").nth(1).click()
    viewer = page.locator(".viewer")
    remove = viewer.get_by_role("button", name="Retirer cette page")
    sync_api.expect(remove).to_have_text("🗑️")
    remove.click()
    assert [img.get_attribute("src") for img in page.locator(".thumb img").all()] == [urls[0], urls[2]]
    sync_api.expect(viewer.locator(".viewer-count")).to_have_text("2 / 2")
    sync_api.expect(viewer.locator(".viewer-frame img")).to_have_attribute("src", urls[2])  # the next one
    remove.click()
    sync_api.expect(viewer.locator(".viewer-frame img")).to_have_attribute("src", urls[0])  # the one before
    remove.click()
    sync_api.expect(viewer).to_be_hidden()
    sync_api.expect(page.locator(".thumb")).to_have_count(0)


def test_what_was_shared_to_the_app_becomes_the_lessons_pages(page):
    """Android's "Share" to Notosaurus (a photo, the school's PDF, a text): the app keeps them
    and opens the page with ?shared; the page takes them as a new lesson's pages, the text
    drawn on a page of its own and given with it as a PDF page's text is (its exact words)."""
    taken = []
    files = {"1": ("image/png", png("white")), "2": ("application/pdf", pdf(2))}
    text = "La Révolution française\n\nEn 1789, le peuple de Paris prend la Bastille."
    listed = [
        {"n": 1, "name": "cahier.png", "type": "image/png"},
        {"n": 2, "name": "Leçon.pdf", "type": "application/pdf"},
    ]
    waiting = [{"files": listed, "text": text, "skipped": []}]

    def host(route):  # the app's LocalServer (Shared.kt), as the page calls it
        request = route.request
        if request.method == "DELETE":
            taken.append("deleted")
            route.fulfill(json={})
        elif request.url.endswith("/api/shared"):
            route.fulfill(json=waiting.pop(0) if waiting else {"files": [], "text": "", "skipped": []})
        else:
            kind, body = files[request.url.rsplit("/", 1)[1]]
            route.fulfill(body=body, content_type=kind)

    page.route("**/api/shared**", host)
    page.goto("/?shared=1")
    started(page)
    add_pdf_pages(page, 2)  # the PDF's pages seen, as any PDF's
    sync_api.expect(page.locator(".thumb img")).to_have_count(4)  # the photo, the PDF's 2 pages, the text
    texts = page.evaluate("Alpine.$data(document.querySelector('[x-data]')).photos.map((p) => p.text ?? '')")
    assert texts[0] == "" and texts[3] == text
    assert taken == ["deleted"]  # taken once
    assert "shared" not in page.url  # opened again (the settings, a reload): not taken again

    # Shared again, the page open (the lesson in progress, not made yet): told by the app, added
    waiting.append({"files": [listed[0]], "text": "", "skipped": ["archive.zip"]})
    assert page.evaluate("window.notosaurusShared()") is True
    page.wait_for_function("Alpine.$data(document.querySelector('[x-data]')).photos.length === 5")
    sync_api.expect(page.get_by_text("« archive.zip » n'a pas été ajouté")).to_be_visible()


def share_pending(page) -> bool:
    """A share left with the app, to be taken once the page is free (takeShared): still so
    once the page's turn to take it (app.js: a setTimeout once it is free) has passed."""
    return page.evaluate(
        "() => new Promise((done) => setTimeout(() =>"
        " done(Alpine.$data(document.querySelector('[x-data]')).sharePending)))"
    )


def _share_host(page, colors: list[str]):
    """The app's LocalServer (Shared.kt) keeping a share of one photo of each of `colors`,
    once given (`share()`), until the page takes it: what the page asked of it, in order."""
    asked, waiting = [], []

    def host(route):
        request = route.request
        if request.method == "DELETE":
            asked.append("delete")
            waiting.clear()
            route.fulfill(json={})
        elif request.url.endswith("/api/shared"):
            asked.append("get")
            route.fulfill(json=waiting[0] if waiting else {"files": [], "text": "", "skipped": []})
        else:
            route.fulfill(body=png(colors[int(request.url.split("/")[-1].split("?")[0]) - 1]), content_type="image/png")

    page.route("**/api/shared**", host)

    def share():
        waiting.append(
            {
                "id": "s1",
                "files": [{"n": n + 1, "name": f"p{n}.png", "type": "image/png"} for n in range(len(colors))],
                "text": "",
                "skipped": [],
            }
        )
        assert page.evaluate("window.notosaurusShared()") is True  # the app told, as MainActivity does

    return asked, share


def _page_color(page, i: int = 0) -> list[int]:
    """The `i`th page's colour, as the page holds it."""
    return page.evaluate(
        """async (i) => {
            const blob = Alpine.$data(document.querySelector('[x-data]')).photos[i].blob;
            const bitmap = await createImageBitmap(blob);
            const ctx = new OffscreenCanvas(1, 1).getContext("2d");
            ctx.drawImage(bitmap, 0, 0, 1, 1);
            return [...ctx.getImageData(0, 0, 1, 1).data.slice(0, 3)];
        }""",
        i,
    )


def test_a_share_while_a_lesson_is_made_is_taken_once_it_is(page):
    """Shared to the app while the first lesson is being made: left with the app (said) until
    the lesson is made, then taken as a new lesson's page (taken at once, it was added to the
    pages being read and dropped when the lesson came back, the app's copy gone already)."""
    asked, share = _share_host(page, ["teal"])
    held = []
    page.route("**/api/extract", lambda route: held.append(route))
    page.goto("/")
    started(page)
    add_photo(page, png("white"))
    page.locator(".chip").first.click()  # the free prompt
    page.locator("textarea[x-ref=promptText]").fill(FRONT_PROMPT)
    page.get_by_role("button", name="✨ Générer les cartes").click()
    eventually(page, lambda: held, "the lesson asked")
    share()
    sync_api.expect(page.get_by_text("Partage reçu")).to_be_visible()
    assert share_pending(page)  # left with the app meanwhile, not taken
    assert asked == []
    held[0].continue_()
    page.wait_for_function(
        "(d => !d.loading && !d.lessonId && d.photos.length === 1 && !d.shareTaking)"
        "(Alpine.$data(document.querySelector('[x-data]')))"
    )
    # Its pages added, then the share told it is taken (its DELETE, sent before shareTaking
    # ends): answered
    settled(page)
    assert asked == ["get", "delete"]
    assert all(
        abs(a - b) < 8 for a, b in zip(_page_color(page), (0, 128, 128), strict=True)
    )  # the shared page, in a new lesson
    (made,) = lessons(page)
    assert lesson(page, made["id"])["photo_count"] == 1  # the lesson made, with its own page


def test_a_share_while_a_card_is_open_waits_for_it_to_be_closed(page):
    """Shared to the app while a card is open full screen: the card left as it is (the user
    may be writing in it), the share taken once it is closed, as a new lesson."""
    asked, share = _share_host(page, ["teal"])
    generate_free(page, FRONT_PROMPT)
    card = open_card(page.locator(".flash").first)
    share()
    sync_api.expect(page.get_by_text("Partage reçu")).to_be_visible()
    assert share_pending(page)
    assert asked == []
    sync_api.expect(card).to_have_class(re.compile(r"\bediting\b"))
    page.keyboard.press("Escape")
    page.wait_for_function(
        "(d => !d.lessonId && d.photos.length === 1 && !d.shareTaking)"
        "(Alpine.$data(document.querySelector('[x-data]')))"
    )
    settled(page)  # its DELETE, sent before shareTaking ends, answered
    assert asked == ["get", "delete"]
    assert page.evaluate("Alpine.$data(document.querySelector('[x-data]')).editing") == ""


def test_a_host_without_sharing_leaves_the_page_as_it_is(page):
    """The computer's host has no /api/shared: ?shared there changes nothing."""
    page.goto("/?shared=1")
    started(page)
    sync_api.expect(page.locator(".thumb img")).to_have_count(0)
    assert page.evaluate("Alpine.$data(document.querySelector('[x-data]')).error") == ""


def test_a_web_pages_address_alone_shared_adds_nothing_and_says_what_to_share(page):
    """A browser shares a page as its address: no lesson page holding a link, said instead."""

    def host(route):
        if route.request.method == "DELETE":
            route.fulfill(json={})
        else:
            route.fulfill(json={"files": [], "text": "", "skipped": [], "error": "share.link_only"})

    page.route("**/api/shared**", host)
    page.goto("/?shared=1")
    started(page)
    sync_api.expect(page.get_by_text("Ce partage ne contient que l'adresse d'une page web.")).to_be_visible()
    assert page.evaluate("Alpine.$data(document.querySelector('[x-data]')).photos.length") == 0


def test_a_diagram_in_the_list_leaves_its_texts_the_cards_width(page):
    """A diagram's card in the compact list, on a phone: the photo above, its question and answer
    under it the card's whole width (seen 2026-11-22: beside the photo, squeezed to a few pixels,
    « Qu' c… »)."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto("/")
    add_photo(page, halves())
    generate_from_photos(page, "Une carte par mot")
    page.evaluate("""() => {
        const app = Alpine.$data(document.querySelector('[x-data]'));
        app.cards[0].mask = { page: 1, box: [0.2, 0.25, 0.3, 0.3], n: 1 };
    }""")
    card = page.locator(".flash").first
    sync_api.expect(card.locator(".diagram .mask.target")).to_be_attached()
    page.wait_for_function("document.querySelector('.diagram img').complete")
    whole, clip, body = card.evaluate(  # in one frame: the page may still be scrolling to the cards
        """(c) => [c, c.querySelector('.diagram-clip'), c.querySelector('.flash-body')]
          .map((e) => e.getBoundingClientRect()).map((r) => ({ y: r.y, width: r.width, height: r.height }))"""
    )
    assert body["width"] >= 0.8 * whole["width"], (body, whole)  # the card's width, not a sliver
    assert clip["y"] + clip["height"] <= body["y"] + 1, (clip, body)  # the photo above its texts


def test_a_diagrams_frame_kept_when_its_cards_come_back_new(page):
    """A diagram's cards replaced by new ones, as a correction or its undo gives them (the same
    keys, none of the page's own fields): its frame still the photo's part it was, its photo
    already loaded (seen 2026-11-24: after « Corriger », the lesson's title shown instead of the
    labels, the photo's proportions lost with the cards)."""
    page.goto("/")
    add_photo(page, halves())
    generate_from_photos(page, "Une carte par mot")
    data = "Alpine.$data(document.querySelector('[x-data]'))"
    page.evaluate(f"""() => {{ const app = {data};
        app.frames = [{{ page: 1, box: [0.1, 0.2, 0.5, 0.4] }}];
        app.cards[0].mask = {{ page: 1, box: [0.2, 0.25, 0.3, 0.3], n: 1 }}; }}""")
    card = page.locator(".flash").first
    page.wait_for_function("document.querySelector('.diagram img').complete")
    ratio = "(c => { const r = c.querySelector('.diagram-clip').getBoundingClientRect(); return r.width / r.height; })"
    before = card.evaluate(ratio)
    assert before == pytest.approx((0.4 * 600) / (0.2 * 800), rel=0.03)
    page.evaluate(f"""() => {{ const app = {data};
        const fresh = (c) => Object.fromEntries(Object.entries(c).filter(([k]) => !k.startsWith('_')));
        app.cards = app.cards.map(fresh); }}""")
    page.wait_for_timeout(300)
    assert card.evaluate(ratio) == pytest.approx(before, rel=0.03)


def test_a_diagram_in_the_list_shows_only_its_frame(page):
    """A diagram's card: only what Anki shows of the photo (its frame), its mask on it, nothing to
    drag, in the list and in the card open; touched there, the whole photo full screen, its
    frame's and mask's handles, how to move them, until « Terminé » (or Escape: the card stays)."""
    page.goto("/")
    add_photo(page, halves())
    generate_from_photos(page, "Une carte par mot")
    page.evaluate("""() => {
        const app = Alpine.$data(document.querySelector('[x-data]'));
        app.frames = [{ page: 1, box: [0.1, 0.2, 0.5, 0.4] }];
        app.cards[0].mask = { page: 1, box: [0.2, 0.25, 0.3, 0.3], n: 1 };
    }""")
    card = page.locator(".flash").first
    clip = card.locator(".diagram-clip")
    sync_api.expect(card.locator(".diagram .mask.target")).to_be_attached()
    page.wait_for_function("document.querySelector('.diagram img').complete")
    # The frame (the mask inside it, with its margin): 0.1..0.5 × 0.2..0.4 of a 600 × 800 photo
    box = clip.bounding_box()
    assert box and box["width"] / box["height"] == pytest.approx((0.4 * 600) / (0.2 * 800), rel=0.03)
    sync_api.expect(card.locator(".crop-handle:visible, .handle:visible, .crop-frame:visible")).to_have_count(0)
    sync_api.expect(page.get_by_text("faites glisser un masque", exact=False).filter(visible=True)).to_have_count(0)

    open_card(card)  # the card open: its frame still, larger, nothing to drag
    sync_api.expect(card.locator(".crop-handle:visible")).to_have_count(0)
    box = clip.bounding_box()
    assert box and box["width"] > 260 and box["width"] / box["height"] == pytest.approx(1.5, rel=0.03)

    clip.click()  # touched: the whole photo full screen, its handles, how to move them
    sync_api.expect(clip).to_have_class(re.compile(r"\bopen\b"))
    sync_api.expect(card.locator(".crop-handle:visible")).to_have_count(4)
    sync_api.expect(clip.get_by_text("faites glisser un masque", exact=False)).to_be_visible()
    whole = card.locator(".diagram img").bounding_box()
    assert whole and whole["width"] / whole["height"] == pytest.approx(600 / 800, rel=0.02)
    page.keyboard.press("Escape")  # closes it alone: the card stays open
    sync_api.expect(clip).not_to_have_class(re.compile(r"\bopen\b"))
    sync_api.expect(card).to_have_class(re.compile(r"\bediting\b"))
    clip.click()
    clip.get_by_role("button", name="Terminé").click()
    sync_api.expect(clip).not_to_have_class(re.compile(r"\bopen\b"))
    sync_api.expect(card).to_have_class(re.compile(r"\bediting\b"))


@pytest.mark.parametrize("page", [{"has_touch": True}], indirect=True, ids=["touch"])
def test_a_diagrams_card_swiped_from_its_photo_not_from_its_mask(page):
    """A diagram's card open: a finger swiped on its photo's frame turns to the next card, as
    anywhere on it; edited full screen (#721), one on its mask (dragged there, to cover the
    label) doesn't."""
    from page.test_cards import _swipe

    page.goto("/")
    add_photo(page, halves())
    generate_from_photos(page, "Une carte par mot")
    page.evaluate("""() => {
        const app = Alpine.$data(document.querySelector('[x-data]'));
        app.cards[0].mask = { page: 1, box: [0.2, 0.25, 0.4, 0.35], n: 1 };
    }""")
    cards = page.locator(".flash")
    first, second = cards.nth(0), cards.nth(1)
    first.locator(".flash-body").tap(position={"x": 4, "y": 4})
    sync_api.expect(first).to_have_class(re.compile(r"\bediting\b"))
    clip = first.locator(".diagram-clip")
    clip.click()  # full screen: its mask dragged, not the card
    sync_api.expect(clip).to_have_class(re.compile(r"\bopen\b"))
    _swipe(first.locator(".diagram .mask.target"), -150)
    # Not followed by the card (touchCard moves it with the finger, at once): never turned
    assert first.evaluate("(card) => [card.style.transform, card.style.transition]") == ["", ""]
    sync_api.expect(first).to_have_class(re.compile(r"\bediting\b"))
    page.keyboard.press("Escape")  # the full screen closed: the card stays open
    sync_api.expect(clip).not_to_have_class(re.compile(r"\bopen\b"))
    _swipe(first.locator(".diagram img"), -150)  # its frame: the next card
    sync_api.expect(second).to_have_class(re.compile(r"\bediting\b"))


def three_pages(page) -> dict:
    """A lesson made from 3 pages by the demo AI: its cards on pages 1, 2, 3, 1… (Card.page)."""
    page.goto("/")
    page.locator('input[type=file][accept="image/*"][multiple]:not([capture])').set_input_files(
        [{"name": f"page-{n}.png", "mimeType": "image/png", "buffer": png(c)} for n, c in enumerate(COLORS[:3])]
    )
    sync_api.expect(page.locator(".thumb img")).to_have_count(3)
    made = generate_from_photos(page, "FR → ES")
    assert [c["page"] for c in made["cards"]][:3] == [1, 2, 3]
    return made


def test_a_card_shows_the_lesson_page_it_comes_from(page):
    """The open card's "📄 p. 3": the lesson's pages in full at that one (‹ › to the others);
    Escape closes them, the card still open. None for a card whose page isn't known, or isn't
    one of the lesson's."""
    three_pages(page)
    card = open_card(page.locator(".flash").nth(2))
    chip = card.get_by_role("button", name="Voir la page 3 du cours")
    sync_api.expect(chip).to_have_text("📄 p. 3")
    sync_api.expect(page.locator(".flash").nth(1).locator(".card-page")).to_be_hidden()  # the list's: none
    chip.click()
    viewer = page.locator(".viewer")
    sync_api.expect(viewer.locator(".viewer-count")).to_have_text("3 / 3")
    src = viewer.locator(".viewer-frame img").get_attribute("src")
    assert src == page.locator(".thumb img").nth(2).get_attribute("src")
    viewer.get_by_role("button", name="Photo précédente").click()
    sync_api.expect(viewer.locator(".viewer-count")).to_have_text("2 / 3")
    page.keyboard.press("Escape")
    sync_api.expect(viewer).to_be_hidden()
    sync_api.expect(card).to_have_class(re.compile(r"\bediting\b"))  # the card still open

    data = "Alpine.$data(document.querySelector('[x-data]'))"
    for unknown in (0, 4):  # older than pages; past the lesson's
        page.evaluate(f"{data}.cards[2].page = {unknown}")
        sync_api.expect(card.locator(".card-page")).to_be_hidden()


def test_a_read_only_lessons_cards_show_their_page(page):
    """A lesson read only (another profile's), whose cards open none: each card's page there, seen
    in full all the same (nothing of the lesson changed)."""
    three_pages(page)
    data = "Alpine.$data(document.querySelector('[x-data]'))"
    page.evaluate(f"{data}.lessonOwner = 'Léa'")  # Anki closed: another profile's lesson
    page.wait_for_function(f"{data}.readOnly()")
    chip = page.locator(".flash").nth(1).get_by_role("button", name="Voir la page 2 du cours")
    sync_api.expect(chip).to_be_visible()
    chip.click()
    viewer = page.locator(".viewer")
    sync_api.expect(viewer.locator(".viewer-count")).to_have_text("2 / 3")
    sync_api.expect(viewer.get_by_role("button", name="Retirer cette page")).to_be_hidden()  # viewing only


def test_a_card_keeps_its_page_through_an_edit(page):
    """A card's page (written by the AI) saved with it when it is edited: the page keeps the card's
    fields it doesn't show."""
    made = three_pages(page)
    field(page.locator(".flash").nth(2), "back").fill("los tres")
    eventually(page, lambda: lesson(page, made["id"])["cards"][2]["back"] == "los tres", "the edit saved")
    assert [c["page"] for c in lesson(page, made["id"])["cards"]] == [c["page"] for c in made["cards"]]


def test_a_pdf_picked_as_the_page_opens_counted_against_the_servers_room(page):
    """A PDF picked before the server's settings are read (a slow start): its pages counted
    against the lesson's room as the server says it (30), not the page's default (10): all
    ticked, not none."""

    def late(route):
        time.sleep(1.5)
        route.continue_()

    page.route("**/api/config", late)
    page.goto("/")
    page.locator("input[type=file][accept*=pdf]").set_input_files(
        {"name": "cours.pdf", "mimeType": "application/pdf", "buffer": pdf(12)}
    )
    add_pdf_pages(page, 12)
    sync_api.expect(page.locator("figure.thumb img")).to_have_count(12)
