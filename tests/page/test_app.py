"""The page as a whole and in the Android app: languages, touch targets, the welcome, the
subscription, help links."""

import json
import re
from datetime import UTC, datetime, timedelta

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from page.support import (  # noqa: E402
    CUT,
    FRONT_PROMPT,
    android_settings,
    generate_free,
    new_password,
    off_contrast,
)


def test_the_free_trial_started_said_after_the_first_lesson(page):
    """The Android app: the first lesson starts the free trial; the page asks after it and
    says so in a toast (seen wherever the page is scrolled), once."""
    told = {"trial": None}

    def switches(route):
        trial, told["trial"] = told["trial"], None  # told once
        body = {"notice": None, "disabled": [], "update": False, "store": "https://play.google.com/x", "trial": trial}
        route.fulfill(json=body)

    page.route("**/api/switches", switches)
    page.goto("/")
    told["trial"] = {
        "plan": "free_trial",
        "credits_left": 300,
        "daily_left": 150,
        "ends_at": "2026-11-07T10:00:00+00:00",
    }
    page.get_by_role("radio", name="✏️ Libre").click()
    page.locator("textarea[x-ref=promptText]").fill(FRONT_PROMPT)
    page.get_by_role("button", name="✨ Générer à partir de la consigne seule").click()
    sync_api.expect(page.locator(".toast.ok")).to_contain_text("Essai gratuit : 300 crédits jusqu'au 7 novembre")


def test_touch_targets_and_an_off_button_readable(page):
    """Every small control a finger hits is 44 px at least (its invisible layer), its look
    unchanged; a main button off reads plainly (not a paler teal, 2.2:1 before)."""
    generate_free(page, FRONT_PROMPT)
    sizes = page.evaluate(
        """[...document.querySelectorAll('.flash-actions .icon-btn, .appbar .chip-btn.icon-only')]
           .filter((b) => b.offsetParent)
           .map((b) => {
             const s = getComputedStyle(b, '::after');
             return [b.getBoundingClientRect().width, parseFloat(s.width), parseFloat(s.height)];
           })"""
    )
    assert sizes and all(w < 44 for w, _, _ in sizes)  # small to look at…
    assert all(aw >= 44 and ah >= 44 for _, aw, ah in sizes), sizes  # …44 px to touch
    for scheme in ("light", "dark"):
        page.emulate_media(color_scheme=scheme)
        assert off_contrast(page) >= 4.5, scheme


@pytest.mark.parametrize("lang", ["en", "fr", "es", "de", "it", "pt"])
def test_every_language_fits_a_narrow_phone(page, browser, server, lang):
    context = browser.new_context(locale="fr-FR", viewport={"width": 360, "height": 780}, base_url=server)
    context.add_init_script(f"localStorage.setItem('notosaurus.lang', '{lang}')")
    try:
        other = context.new_page()
        other.goto("/")
        other.wait_for_function("document.documentElement.classList.contains('i18n-ready')")
        other.locator(".chip").first.click()  # the free prompt
        other.locator("textarea[x-ref=promptText]").fill("QCM sur la Révolution")
        other.locator(".bottom-bar button.btn.primary.wide").first.click()  # from the prompt alone (nextAction)
        other.locator(".flash").first.wait_for()
        assert other.evaluate(CUT) == []
        other.goto("/admin.html")
        new_password(other)
        other.locator("button.btn.primary.wide").first.click()  # create the password
        other.locator("section.panel h2 .step").first.wait_for()  # the settings, unlocked (About is always there)
        assert other.evaluate(CUT) == []
        other.wait_for_function("Alpine.$data(document.querySelector('[x-data]')).saveState !== 'pending'")
        # The setup assistant, with its longest step: Gemini's key, explained
        other.request.put("/api/admin/settings", headers={"X-Admin-Password": "secret-pw"}, data={"llm": "gemini"})
        other.goto("/setup.html")
        other.locator(".setup-guide").wait_for()
        assert other.evaluate(CUT) == []
    finally:
        context.close()


def test_android_credits_said_as_the_plan_is(page):
    """The plan in the page's language; the trial's credits not "this month"; today's only
    when fewer than what is left."""
    # a trial still running: one whose end is past is over (relay.trial_ended), whatever today is
    ends_at = (datetime.now(UTC) + timedelta(days=10)).isoformat()
    android_settings(page, {"plan": "free_trial", "credits_left": 94, "daily_left": 119, "ends_at": ends_at})
    sync_api.expect(page.get_by_text("Formule : Essai gratuit", exact=True)).to_be_visible()
    sync_api.expect(page.get_by_text("94 crédits restants pour l'essai", exact=True)).to_be_visible()
    sync_api.expect(page.locator("textarea[x-model='form.instructions']")).to_be_visible()  # once the settings came
    sync_api.expect(page.get_by_text("utilisables aujourd'hui")).to_be_hidden()
    android_settings(
        page, {"plan": "monthly", "credits_left": 2000, "daily_left": 50, "renews_at": "2026-11-30T10:00:00Z"}
    )
    sync_api.expect(page.get_by_text("Formule : Mensuel", exact=True)).to_be_visible()
    sync_api.expect(page.get_by_text("2000 crédits restants ce mois-ci", exact=True)).to_be_visible()
    sync_api.expect(page.get_by_text("Dont 50 utilisables aujourd'hui", exact=True)).to_be_visible()
    android_settings(page, {"plan": "beta", "credits_left": 10, "daily_left": 10})
    sync_api.expect(page.get_by_text("Formule : beta", exact=True)).to_be_visible()  # one given by hand: as it is


def test_android_check_says_it_checked(page):
    """ "Vérifier" in the subscription: nothing typed, the key kept is checked again (it did
    nothing, not a word); a key typed, saved then checked; both said. No key: nothing to check."""
    android_settings(page, {"plan": "monthly", "credits_left": 2000, "daily_left": 2000})
    asked = []
    page.on("request", lambda r: asked.append(r.url) if r.url.endswith("/api/admin/account") else None)
    sync_api.expect(page.get_by_text("Formule : Mensuel", exact=True)).to_be_visible()
    asked.clear()
    check = page.get_by_role("button", name="Vérifier")
    check.click()  # nothing typed
    sync_api.expect(page.get_by_text("✓ Clé vérifiée : à jour.")).to_be_visible()
    assert len(asked) == 1

    page.locator(".toast.ok button").click()
    page.get_by_label("Clé de licence").fill("nts_new")
    check.click()
    sync_api.expect(page.get_by_text("✓ Clé vérifiée : à jour.")).to_be_visible()
    sync_api.expect(page.get_by_label("Clé de licence")).to_have_value("")  # saved

    page.evaluate("Alpine.$data(document.querySelector('[x-data]')).form.has_key = false")
    sync_api.expect(check).to_be_disabled()


def test_what_the_page_keeps_kept_by_the_android_app(page):
    """The Android app serves saved.js (its preferences): read from it, not localStorage,
    each change told to it (PUT /api/saved)."""
    page.request.put("/api/children", data=[{"id": "jules", "name": "Jules"}, {"id": "lea", "name": "Léa"}])
    saved = {"notosaurus.child": "lea", "notosaurus.careful": "1"}
    told = []
    page.route(
        "**/saved.js",
        lambda route: route.fulfill(body=f"window.SAVED = {json.dumps(saved)};", content_type="text/javascript"),
    )
    page.route("**/api/saved", lambda route: (told.append(route.request.post_data_json), route.fulfill(json={})))
    page.goto("/")
    sync_api.expect(page.get_by_role("button", name="Enfants")).to_have_text(re.compile("Léa"))
    sync_api.expect(page.get_by_role("radio", name="Soigné")).to_be_checked()
    page.evaluate("document.querySelector('[x-data]')._x_dataStack[0].chooseChild('jules')")
    sync_api.expect(page.get_by_role("button", name="Enfants")).to_have_text(re.compile("Jules"))
    page.wait_for_timeout(200)  # the PUT sent meanwhile
    assert {"notosaurus.child": "jules"} in told
    assert page.evaluate("localStorage.length") == 0  # the app keeps them


def test_no_support_link_where_notosaurus_is_paid_for(page):
    """The Android app's own page (its subscription) says donations: false."""
    page.goto("/")
    sync_api.expect(page.locator(".support-link")).to_be_visible()

    def paid(route):
        config = route.fetch().json()
        route.fulfill(json={**config, "donations": False})

    page.route("**/api/config", paid)
    page.reload()
    page.wait_for_function("document.documentElement.classList.contains('i18n-ready')")
    sync_api.expect(page.locator(".support-link")).to_be_hidden()


def test_the_apps_welcome_accepted_once(page):
    """The app's first launch: a parent's tool, Gemini, the privacy policy. Accept stays off
    until ticked; accepted, it goes (the app keeps it). Not on the computer (no "welcome")."""
    accepted = []

    def config(route):
        route.fulfill(json={**route.fetch().json(), "welcome": 1, "welcome_accepted": bool(accepted)})

    page.route("**/api/config", config)
    page.route("**/api/welcome", lambda route: (accepted.append(1), route.fulfill(json={"accepted": 1})))
    page.goto("/")
    welcome = page.get_by_role("dialog", name="Avant de commencer")
    sync_api.expect(welcome).to_be_visible()
    sync_api.expect(welcome).to_contain_text("Gemini de Google")
    sync_api.expect(welcome.get_by_role("link", name="Politique de confidentialité")).to_have_attribute(
        "href", re.compile(r"/fr/app-privacy/")
    )
    accept = welcome.get_by_role("button", name="Accepter")
    sync_api.expect(accept).to_be_disabled()
    welcome.get_by_label("Je suis un parent (un adulte) et j'accepte la politique de confidentialité.").check()
    accept.click()
    sync_api.expect(welcome).to_be_hidden()
    assert accepted == [1]
    page.reload()
    sync_api.expect(page.locator(".flash, .tagline").first).to_be_visible()
    sync_api.expect(welcome).to_be_hidden()  # once


def test_no_welcome_on_the_computer(page):
    page.goto("/")
    page.locator(".tagline").wait_for()
    sync_api.expect(page.get_by_role("dialog", name="Avant de commencer")).to_be_hidden()


def test_help_links_in_the_page_language(page):
    docs = "https://cchabanois.github.io/notosaurus/"
    page.goto("/")
    sync_api.expect(page.locator(".docs-link")).to_have_attribute("href", docs + "fr/")  # the footer
    sync_api.expect(page.get_by_role("link", name="☕ Soutenir Notosaurus")).to_have_attribute(
        "href", "https://ko-fi.com/notosaurus"
    )
    generate_free(page, FRONT_PROMPT)
    page.locator(".chip-btn").first.click()  # the lessons sheet: its own page
    sync_api.expect(page.get_by_role("link", name="Aide : Mes leçons")).to_have_attribute("href", docs + "fr/lessons/")
    page.locator(".lang-select select").select_option("pt")
    sync_api.expect(page.locator(".docs-link")).to_have_attribute("href", docs + "pt-br/")


def test_subscribe_offered_whatever_call_said_the_licence_lapsed(page):
    """The Android app, its subscription ended: "Subscribe" on the message, whether a lesson
    or a dictation (or a picture, a correction…) said it."""
    switches = {"notice": None, "disabled": [], "update": False, "store": "https://play.google.com/x", "trial": None}
    page.route("**/api/switches", lambda route: route.fulfill(json=switches))
    page.route("**/api/config", lambda route: route.fulfill(json={**route.fetch().json(), "dictation": True}))
    page.route("**/api/dictation/start", lambda route: route.fulfill(json={"listening": True}))
    ended = {"detail": {"code": "relay.subscription_ended", "params": {}}}
    page.route("**/api/dictation/stop", lambda route: route.fulfill(status=402, json=ended))
    page.goto("/")
    page.get_by_role("button", name="Dicter").first.click()
    page.get_by_role("button", name="Arrêter et écrire le texte").click()
    toast = page.get_by_role("alert")
    sync_api.expect(toast).to_contain_text("Votre abonnement est terminé")
    sync_api.expect(toast.get_by_role("link", name="S'abonner")).to_be_visible()
    page.evaluate("document.querySelector('[x-data]')._x_dataStack[0].error = 'Autre erreur.'")
    sync_api.expect(toast.get_by_role("link", name="S'abonner")).to_be_hidden()  # another error: none
