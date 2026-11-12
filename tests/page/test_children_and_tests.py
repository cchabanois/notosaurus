"""The children and the tests to prepare (Contrôles)."""

import re

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from page.support import (  # noqa: E402
    FRONT_PROMPT,
)


def test_children_of_the_same_name_told_apart_and_removed_once_confirmed(page):
    ce1 = {"id": "lea-ce1", "name": "Léa", "grade": "CE1"}
    cm2 = {"id": "lea-cm2", "name": "Léa", "grade": "CM2"}
    page.request.put("/api/children", data=[ce1, cm2])
    page.goto("/")
    header = page.get_by_role("button", name="Enfants")
    page.evaluate("document.querySelector('[x-data]')._x_dataStack[0].chooseChild('lea-cm2')")
    sync_api.expect(header).to_have_text(re.compile("Léa · CM2"))
    header.click()
    page.get_by_role("button", name="Modifier Léa").first.click()
    page.get_by_role("button", name="Retirer", exact=True).click()
    asked = page.get_by_role("alertdialog", name="Retirer Léa ? Ses leçons sont gardées.")
    asked.get_by_role("button", name="Annuler").click()
    sync_api.expect(asked).to_be_hidden()
    assert len(page.request.get("/api/children").json()) == 2  # cancelled: kept
    page.get_by_role("button", name="Retirer", exact=True).click()
    asked.get_by_role("button", name="Retirer").click()
    sync_api.expect(asked).to_be_hidden()
    sync_api.expect(header).to_have_text(re.compile(r"Léa\s*$"))  # the only Léa now
    assert [c["id"] for c in page.request.get("/api/children").json()] == ["lea-cm2"]


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


def test_many_lessons_to_add_their_button_in_view_a_long_title_beside_its_box(page):
    """Adding lessons to a test with many of them: the button stays in view, and a lesson's
    title on two lines wraps beside its box, not under it."""
    page.goto("/")
    for n in range(12):
        prompt = "Jules › 5e › Anglais › Twinkle Twinkle Little Star, une très longue leçon" if n == 0 else FRONT_PROMPT
        page.request.post("/api/extract", multipart={"prompt": prompt})
    page.request.put("/api/exams/interro", data={"name": "Interro", "date": "", "lessons": []})
    page.reload()
    page.wait_for_function("document.documentElement.classList.contains('i18n-ready')")
    page.evaluate(
        "(async () => { const app = document.querySelector('[x-data]')._x_dataStack[0];"
        " await app.loadExams(); app.openExams(app.exams[0]); })()"
    )
    page.get_by_role("button", name="＋ Ajouter des leçons").click()
    rows = page.locator(".exam-add .child-row")
    sync_api.expect(rows).to_have_count(12)
    rows.first.locator("input").check()
    sync_api.expect(page.get_by_role("button", name="Ajouter 1 leçon")).to_be_in_viewport()
    for row in rows.all():  # the box and the title on the same line, however long the title
        box, title = row.locator("input").bounding_box(), row.locator("strong").bounding_box()
        assert box["y"] >= title["y"] - 2 and box["y"] + box["height"] <= title["y"] + title["height"] + 2


def test_a_tests_cards_shared_from_its_sheet(page):
    """A test's sheet: "Share the test's cards" opens the sheet with the test's name as the
    package's, the file made from the test's own cards."""
    page.goto("/")
    made = page.request.post("/api/extract", multipart={"prompt": FRONT_PROMPT}).json()
    exam = {"name": "Interro lundi", "date": "", "lessons": [{"lesson": made["id"]}]}
    page.request.put("/api/exams/interro", data=exam)
    page.reload()
    page.get_by_role("button", name="Leçons").click()
    page.get_by_role("button", name=re.compile("Interro lundi")).click()
    page.get_by_role("button", name="📤 Partager les cartes du contrôle").click()
    sheet = page.get_by_role("dialog", name="Partager les cartes")
    sync_api.expect(sheet.get_by_label("Nom du paquet")).to_have_value("Interro lundi")
    with page.expect_download() as download:
        sheet.get_by_role("button", name="📤 Créer le fichier").click()
    assert download.value.suggested_filename == "Interro lundi.apkg"
