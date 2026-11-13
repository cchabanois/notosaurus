"""The cards in Anki: sent once their figures are, reviewed, up to date, left over, AnkiDroid
installed, decks and profiles."""

import re

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from page.support import (  # noqa: E402
    FRONT_PROMPT,
    SAVED,
    generate_free,
    lesson,
    lessons,
    reopen,
)


def test_the_decks_offered_are_the_chosen_childs_and_no_ones(page):
    jules = {"id": "jules", "name": "Jules", "grade": "5e", "decks": "Jules::5e"}
    mathilde = {"id": "mathilde", "name": "Mathilde", "grade": "3e", "decks": "Mathilde"}
    page.request.put("/api/children", data=[jules, mathilde])
    decks = ["Jules::5ème::Anglais", "Mathilde::SVT", "Maths::Fractions", "Jules"]
    page.route("**/api/decks", lambda route: route.fulfill(json=decks))
    generate_free(page, FRONT_PROMPT)
    page.locator("input[list=decks]").focus()

    def offered():
        return page.locator("#decks option").evaluate_all("options => options.map((o) => o.value)")

    sync_api.expect(page.locator("#decks option")).not_to_have_count(0)
    assert offered() == ["Jules::5ème::Anglais", "Maths::Fractions", "Jules"]  # Jules is chosen first
    page.evaluate("document.querySelector('[x-data]')._x_dataStack[0].chooseChild('mathilde')")
    sync_api.expect(page.locator("#decks option")).to_have_count(2)
    assert offered() == ["Mathilde::SVT", "Maths::Fractions"]


def test_no_apkg_where_the_cards_go_straight_to_ankidroid(page, anki):
    """The Android app's own page says apkg: false: "Add to Anki" alone. Elsewhere the open
    lesson's cards shared: what goes with them said first, then its file, as it always was."""
    generate_free(page, FRONT_PROMPT)
    page.get_by_role("button", name="Partager les cartes").click()
    sheet = page.get_by_role("dialog", name="Partager les cartes")
    sync_api.expect(sheet).to_contain_text("Les photos et schémas des leçons partent avec les cartes")
    with page.expect_download() as download:
        sheet.get_by_role("button", name="📤 Créer le fichier").click()
    assert download.value.suggested_filename.endswith(".apkg")

    def app(route):
        route.fulfill(json={**route.fetch().json(), "apkg": False})

    page.route("**/api/config", app)
    generate_free(page, FRONT_PROMPT)
    sync_api.expect(page.get_by_role("button", name="Partager les cartes")).to_be_hidden()
    sync_api.expect(page.get_by_role("button", name=re.compile("Anki"))).not_to_have_count(0)


def test_send_waits_for_the_figures_and_says_so(page, anki):
    """ "Add to Anki" while the figures are drawn: the button says it waits for them, how many
    are ready; sent once they're there, with them."""
    held = []
    page.route("**/api/lessons/*/pictures", lambda route: held.append(route))
    generate_free(page, "Le triangle rectangle (géométrie)")  # demo mode: three figures to draw
    page.get_by_role("button", name="📥 Ajouter à Anki").click()
    sync_api.expect(page.locator(".bar-row button.primary.wide", has_text="Images")).to_contain_text(
        "Images et figures : 0 / 3 prêtes"
    )
    for route in held:
        route.continue_()
    sync_api.expect(page.get_by_role("button", name="✓ À jour dans Anki")).to_be_visible()
    (summary,) = lessons(page)
    assert all(c["picture"].endswith(".svg") for c in lesson(page, summary["id"])["cards"])


def test_review_in_ankidroid_once_sent(page, anki):
    """The Android app's page (review_in_anki): "📚 Review" once the lesson is sent."""
    asked = []

    def app(route):
        route.fulfill(json={**route.fetch().json(), "review_in_anki": True})

    page.route("**/api/config", app)
    page.route(
        "**/api/anki/review",
        lambda route: (asked.append(route.request.post_data_json), route.fulfill(json={"opened": True})),
    )
    generate_free(page, FRONT_PROMPT)
    review = page.locator(".bar-row").get_by_role("button", name="📚 Réviser")
    sync_api.expect(review).to_be_hidden()  # not sent yet
    page.get_by_role("button", name="📥 Ajouter à Anki").click()
    sync_api.expect(page.locator(".toast.ok").get_by_role("button", name="📚 Réviser")).to_be_visible()
    # Sent: up to date in Anki (sending again stays possible)
    sync_api.expect(page.get_by_role("button", name="✓ À jour dans Anki")).to_be_visible()
    review.click()
    sync_api.expect(page.locator(".toast.ok")).to_be_hidden()
    assert [a["deck"] for a in asked] == [page.locator(".field.deck input").input_value()]


def test_cards_left_over_in_anki_deleted_when_asked(page, anki):
    """A card deleted after a send: the next send says its note is left in Anki, with its
    text, and deletes it only on "Delete from Anki"."""
    generate_free(page, FRONT_PROMPT)
    page.get_by_role("button", name="📥 Ajouter à Anki").click()
    sync_api.expect(page.get_by_role("button", name="✓ À jour dans Anki")).to_be_visible()
    update = page.get_by_role("button", name="🔄 Mettre à jour dans Anki")
    notes = len(anki.notes)
    first = page.locator(".flash").first
    gone = first.locator("textarea").first.input_value()
    first.get_by_role("button", name="Plus d'actions").click()
    first.get_by_role("button", name="Supprimer la carte").click()
    update.click()
    sheet = page.locator("aside.sheet", has_text="Cartes en trop dans Anki")
    sync_api.expect(sheet).to_be_visible()
    sync_api.expect(sheet.locator(".leftovers li").first).to_have_text(gone)
    sheet.get_by_role("button", name="Supprimer d'Anki").click()
    sync_api.expect(sheet).to_be_hidden()
    assert len(anki.notes) == notes - 1


def test_up_to_date_in_anki_until_it_changes(page, anki):
    """Sent: "Up to date in Anki" (sending again stays possible), until a card changes:
    "Update in Anki", sent again up to date; reopened unchanged, still up to date."""
    generate_free(page, FRONT_PROMPT)
    page.get_by_role("button", name="📥 Ajouter à Anki").click()
    up_to_date = page.get_by_role("button", name="✓ À jour dans Anki")
    sync_api.expect(up_to_date).to_be_visible()
    sync_api.expect(up_to_date).to_have_class(re.compile(r"\bsoft\b"))
    notes = len(anki.notes)
    up_to_date.click()  # sent again all the same: no card added
    sync_api.expect(up_to_date).to_be_visible()
    assert len(anki.notes) == notes

    page.locator(".flash textarea").first.fill("la abuela")
    update = page.get_by_role("button", name="🔄 Mettre à jour dans Anki")
    sync_api.expect(update).to_be_visible()
    sync_api.expect(update).to_have_class(re.compile(r"\bprimary\b"))
    page.locator(".flash textarea").first.press("Tab")
    sync_api.expect(page.locator(".save-pill")).to_have_class(SAVED)  # saved: changed since it was sent
    reopen(page)
    sync_api.expect(update).to_be_visible()  # reopened: still to send
    update.click()
    sync_api.expect(up_to_date).to_be_visible()
    reopen(page)
    sync_api.expect(up_to_date).to_be_visible()  # reopened unchanged since


def test_ankidroid_installed_from_the_message(page, anki):
    """The app without AnkiDroid: "Add to Anki" says so, with a button to install it
    (Google Play only opens when asked)."""
    installs = []
    page.route(
        "**/api/anki/send",
        lambda route: route.fulfill(status=400, json={"detail": {"code": "anki.android_missing", "params": {}}}),
    )
    page.route("**/api/anki/install", lambda route: (installs.append(1), route.fulfill(json={"opened": True})))
    generate_free(page, FRONT_PROMPT)
    page.get_by_role("button", name="📥 Ajouter à Anki").click()
    toast = page.locator(".toast[role=alert]")
    sync_api.expect(toast).to_contain_text("AnkiDroid")
    assert installs == []
    toast.get_by_role("button", name="Installer AnkiDroid").click()
    sync_api.expect(toast).to_be_hidden()
    assert installs == [1]

    # Another error: no such button
    page.route(
        "**/api/anki/send",
        lambda route: route.fulfill(
            status=502, json={"detail": {"code": "anki.android_failed", "params": {"detail": "x"}}}
        ),
    )
    page.get_by_role("button", name="📥 Ajouter à Anki").click()
    sync_api.expect(toast).to_be_visible()
    sync_api.expect(toast.get_by_role("button", name="Installer AnkiDroid")).to_be_hidden()


def test_the_children_of_the_open_anki_profile(page):
    """On the computer, a card belongs to the Anki profile it was made in: only the open
    profile's are offered; a profile's only child chosen by itself. The profile stays said
    under the name (where the cards go), nowhere else."""
    kids = [
        {"id": "jules", "name": "Jules", "anki_profile": "Famille"},
        {"id": "mathilde", "name": "Mathilde", "anki_profile": "Famille"},
        {"id": "tom", "name": "Tom"},  # made before: the profile it is next seen in
    ]
    page.request.put("/api/children", data=kids)
    open_profile = {"name": "Famille"}
    page.route(
        "**/api/anki/status",
        lambda route: route.fulfill(json={"available": True, "profile": open_profile["name"]}),
    )
    page.goto("/")
    chip = page.get_by_role("button", name="Enfants")
    sync_api.expect(page.locator(".brand-profile")).to_contain_text("Famille")  # a shared profile: said
    chip.click()
    sheet = page.get_by_role("dialog", name="Enfants")
    sync_api.expect(sheet).not_to_contain_text("profil Anki")  # the children, not the profile
    sync_api.expect(sheet.locator(".child-rows li:visible")).to_have_count(3)  # Tom: this profile's now
    sheet.locator(".child-row", has_text="Mathilde").click()
    sync_api.expect(chip).to_contain_text("Mathilde")
    owners = {c["id"]: c["anki_profile"] for c in page.request.get("/api/children").json()}
    assert owners == {"jules": "Famille", "mathilde": "Famille", "tom": "Famille"}

    open_profile["name"] = "Léa"  # her own profile: none of the family's; a card made here is hers
    sync_api.expect(page.locator(".brand-profile")).to_contain_text("Léa", timeout=8000)
    sync_api.expect(chip).to_contain_text("Pour qui ?")
    chip.click()
    sheet.locator("input.child-name").fill("Léa")
    sheet.get_by_role("button", name="Enregistrer").click()
    sync_api.expect(sheet.locator(".child-rows li:visible")).to_have_count(1)
    sheet.get_by_role("button", name="Fermer").click()
    sync_api.expect(chip).to_contain_text("Léa")  # its only child, chosen
    sync_api.expect(page.locator(".brand-profile")).to_contain_text("Léa")  # always said
    assert page.request.get("/api/children").json()[-1]["anki_profile"] == "Léa"

    open_profile["name"] = "Famille"  # back: Léa's card not offered
    sync_api.expect(chip).not_to_contain_text("Léa", timeout=8000)


def test_no_profile_badge_where_there_are_no_profiles(page):
    """The Android app (AnkiDroid doesn't say its profile) says profiles: false."""
    page.route("**/api/anki/status", lambda route: route.fulfill(json={"available": True, "profile": None}))
    page.goto("/")
    sync_api.expect(page.locator(".brand-profile")).to_be_visible()  # "none": no profile open in Anki

    def phone(route):
        route.fulfill(json={**route.fetch().json(), "profiles": False})

    page.route("**/api/config", phone)
    page.reload()
    page.wait_for_function("document.documentElement.classList.contains('i18n-ready')")
    sync_api.expect(page.locator(".brand-profile")).to_be_hidden()
