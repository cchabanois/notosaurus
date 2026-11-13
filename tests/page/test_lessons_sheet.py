"""The lessons: 📚 Mes leçons, grouped, searched, deleted, copied; the lesson in progress found
again; the sheets."""

import re

import pytest
from helpers import plain_image

sync_api = pytest.importorskip("playwright.sync_api")

from page.support import (  # noqa: E402
    FRONT_PROMPT,
    add_photo,
    generate_free,
    lessons,
    started,
)


def test_delete_the_open_lesson(page):
    generate_free(page, FRONT_PROMPT)
    page.locator(".review-head").get_by_role("button", name="Supprimer la leçon").click()
    sheet = page.get_by_role("dialog", name="Supprimer la leçon")
    sync_api.expect(sheet).to_contain_text("Anki n'est pas ouvert")  # Anki closed: the lesson alone
    sheet.get_by_role("button", name="Supprimer la leçon").click()
    sync_api.expect(page.locator(".flash")).to_have_count(0)
    assert lessons(page) == []


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


def test_android_back_closes_the_open_sheet_first(page):
    """Android's back button (MainActivity) asks the page first: an open sheet closed, as
    Escape closes it (true); none open: false, the app goes back or closes."""
    page.goto("/")
    made = page.request.post("/api/extract", multipart={"prompt": FRONT_PROMPT}).json()
    page.request.put(f"/api/lessons/{made['id']}", data={"deck": "Maths::Leçon", "cards": made["cards"]})
    page.reload()
    assert page.evaluate("notosaurusBack()") is False
    page.get_by_role("button", name="Leçons").click()
    sync_api.expect(page.locator(".lesson-list")).to_be_visible()
    assert page.evaluate("notosaurusBack()") is True
    sync_api.expect(page.locator(".lesson-list")).to_be_hidden()
    assert page.evaluate("notosaurusBack()") is False


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


@pytest.mark.parametrize("width", [360, 1280])
def test_the_lessons_bar_keeps_its_buttons_inside(page, width):
    """A lesson's bottom bar once sent: ".apkg" beside "✓ Up to date in Anki", both inside
    the row, on a phone as on a tablet (the soft Anki button kept a full row's width)."""
    page.set_viewport_size({"width": width, "height": 800})
    page.route("**/api/anki/status", lambda route: route.fulfill(json={"available": True, "profile": None}))
    page.route(
        "**/api/anki/send",
        lambda route: route.fulfill(json={"added": 2, "updated": 0, "leftovers": [], "synced": False}),
    )
    page.goto("/")
    page.wait_for_function("document.documentElement.classList.contains('i18n-ready')")
    page.locator(".chip").first.click()  # the free prompt
    page.locator("textarea[x-ref=promptText]").fill(FRONT_PROMPT)
    page.locator(".bottom-bar button.btn.primary.wide").first.click()
    row = page.locator(".bottom-bar .bar-row").last
    row.get_by_role("button", name="Ajouter à Anki").click()  # sent: now soft, as wide
    sync_api.expect(row.get_by_role("button", name="✓ À jour dans Anki")).to_be_visible()
    sync_api.expect(row.get_by_role("button", name="Partager les cartes")).to_be_visible()
    box = row.bounding_box()
    for button in row.locator("button:visible").all():
        b = button.bounding_box()
        assert box["x"] - 1 <= b["x"] and b["x"] + b["width"] <= box["x"] + box["width"] + 1, button.inner_text()


def test_the_lesson_in_progress_found_again(page):
    """Left before it is made (the settings, a link, the phone closing the app): its photos
    and its prompt found again when the page opens again; once made, the lesson open again;
    a new lesson, nothing."""
    page.goto("/")
    page.get_by_role("radio", name="✏️ Libre").click()
    page.locator("textarea[x-ref=promptText]").fill("Une carte par capitale")
    add_photo(page, plain_image(400, 300, "red"))
    page.get_by_role("link", name="Réglages").click()  # kept before the page is left
    page.wait_for_url("**/admin.html")
    page.goto("/")
    sync_api.expect(page.locator(".thumb img")).to_have_count(1)
    sync_api.expect(page.locator("textarea[x-ref=promptText]")).to_have_value("Une carte par capitale")
    sync_api.expect(page.get_by_role("radio", name="✏️ Libre")).to_be_checked()

    page.get_by_role("button", name="✨ Générer les cartes").click()
    page.locator(".flash").first.wait_for()
    deck = page.locator("input[list=decks]").input_value()
    page.wait_for_timeout(800)  # (kept a moment after the change)
    page.reload()
    sync_api.expect(page.locator("input[list=decks]")).to_have_value(deck)  # the lesson made, open again
    sync_api.expect(page.locator(".flash").first).to_be_visible()

    page.get_by_role("button", name="Nouvelle leçon").click()
    page.wait_for_timeout(800)
    page.reload()
    sync_api.expect(page.locator(".flash")).to_have_count(0)
    sync_api.expect(page.locator(".thumb img")).to_have_count(0)


def test_a_lesson_made_open_again_in_the_same_session_only(page, browser, server):
    """A lesson made, the page opened again: in the same session (back from the settings),
    the lesson open again on its cards, in view; in a new one (the app launched again, a new
    tab), a new lesson, the one made in the lessons. A lesson not made yet: found again."""
    page.set_viewport_size({"width": 360, "height": 780})  # a phone: the photos and prompt fill it
    page.goto("/")
    page.get_by_role("radio", name="✏️ Libre").click()
    page.locator("textarea[x-ref=promptText]").fill("Une carte par capitale")
    add_photo(page, plain_image(400, 300, "red"))
    page.get_by_role("button", name="✨ Générer les cartes").click()
    page.locator(".flash").first.wait_for()
    page.wait_for_timeout(800)  # (kept a moment after the change)
    page.get_by_role("link", name="Réglages").click()
    page.wait_for_url("**/admin.html")
    page.goto("/")
    sync_api.expect(page.locator(".flash").first).to_be_in_viewport()  # its cards, not the photos above

    other = browser.new_context(locale="fr-FR", base_url=server).new_page()
    try:
        other.goto("/")
        started(other)
        sync_api.expect(other.locator(".flash")).to_have_count(0)
        sync_api.expect(other.locator(".thumb img")).to_have_count(0)
        other.locator("textarea[x-ref=promptText]").fill("Une autre leçon")
        add_photo(other, plain_image(400, 300, "blue"))
        other.wait_for_timeout(800)
    finally:
        other.context.close()
    again = browser.new_context(locale="fr-FR", base_url=server).new_page()
    try:
        again.goto("/")
        sync_api.expect(again.locator(".thumb img")).to_have_count(1)  # not made yet: found again
        sync_api.expect(again.locator("textarea[x-ref=promptText]")).to_have_value("Une autre leçon")
    finally:
        again.context.close()


def test_what_the_user_began_kept_over_the_lesson_left(page):
    """A photo added while the lesson left in progress is still being read: theirs kept,
    never replaced by the one found again."""
    page.goto("/")
    page.get_by_role("radio", name="✏️ Libre").click()
    page.locator("textarea[x-ref=promptText]").fill("La leçon d'avant")
    page.evaluate("Alpine.$data(document.querySelector('[x-data]')).saveDraft()")
    page.wait_for_function("Alpine.$data(document.querySelector('[x-data]')).draftSent.includes('avant')")
    held = []
    page.route("**/api/draft", lambda route: held.append(route) if route.request.method == "GET" else route.continue_())
    page.reload()
    add_photo(page, plain_image(400, 300, "blue"))  # begun while it is read
    while not held:
        page.wait_for_timeout(50)
    held[0].continue_()
    started(page)
    sync_api.expect(page.locator(".thumb img")).to_have_count(1)
    assert page.locator("textarea[x-ref=promptText]").input_value() != "La leçon d'avant"


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


def test_every_sheet_slides_in_as_a_dialog(page):
    """The sheets share their slide from the bottom (Alpine.bind "sheet", app.js): the
    children's, which had none, slides in too; each is a dialog for screen readers (four
    had no role), the confirmation keeping its own (alertdialog)."""
    page.goto("/")
    page.get_by_role("button", name="Enfants").click()
    sheet = page.get_by_role("dialog", name="Enfants")
    sync_api.expect(sheet).to_be_visible()
    assert page.evaluate("document.querySelector('aside.sheet[x-bind=sheet]')._x_transition !== undefined")
    roles = page.evaluate("[...document.querySelectorAll('aside.sheet')].map(a => a.getAttribute('role'))")
    assert roles and all(r in ("dialog", "alertdialog") for r in roles) and "alertdialog" in roles


def test_lessons_shared_ticked_from_my_lessons_no_test_needed(page, tmp_path):
    """📚 Mes leçons → "Partager des leçons": lessons ticked one by one or a whole subject,
    then a sheet says what goes with the cards before the file is made; no test needed."""
    page.goto("/")
    for deck in ("Histoire::Révolution", "Histoire::Napoléon", "Anglais::Leçon 1"):
        made = page.request.post("/api/extract", multipart={"prompt": FRONT_PROMPT}).json()
        page.request.put(f"/api/lessons/{made['id']}", data={"deck": deck, "cards": made["cards"]})
    assert page.request.get("/api/exams").json() == []
    page.reload()
    page.get_by_role("button", name="Leçons").click()
    page.get_by_role("button", name="📤 Partager des leçons").click()
    page.get_by_role("checkbox", name="Toute la matière : Histoire").check()
    done = page.get_by_role("button", name="📤 Partager (2 leçons)")
    sync_api.expect(done).to_be_enabled()
    done.click()

    sheet = page.get_by_role("dialog", name="Partager les cartes")
    sync_api.expect(sheet).to_contain_text("Les photos et schémas des leçons partent avec les cartes")
    sync_api.expect(sheet).to_contain_text("importer dans Anki ou AnkiDroid")
    sync_api.expect(sheet.get_by_label("Nom du paquet")).to_have_value("Histoire")
    with page.expect_download() as download:
        sheet.get_by_role("button", name="📤 Créer le fichier").click()
    assert download.value.suggested_filename == "Histoire.apkg"
    sync_api.expect(sheet).to_be_hidden()
