"""Who owns a lesson, who may change it: one lesson list per Anki profile, the
shared ones, the private ones hidden, and the settings' page managing every lesson."""

from conftest import ADMIN, SEND, extract_lesson


def test_lesson_owned_by_anki_profile(anki, client):
    lesson = extract_lesson(client)
    assert (lesson["owner"], lesson["shared"]) == ("Léa", False)
    assert client.get("/api/lessons").json()[0]["owner"] == "Léa"


def test_lesson_without_anki_has_no_owner(client):
    assert extract_lesson(client)["owner"] == ""


def test_only_the_owner_changes_a_lesson(anki, client):
    lesson = extract_lesson(client)  # created in Léa's profile: hers, private
    assert (lesson["owner"], lesson["shared"]) == ("Léa", False)
    url = f"/api/lessons/{lesson['id']}"
    cards = lesson["cards"]
    read_only = {"code": "lesson.read_only", "params": {"owner": "Léa"}}

    # Léa shares it; the owner never changes, even if a page sends one
    shared = client.put(url, json={"deck": lesson["deck"], "cards": cards, "shared": True, "owner": "Paul"}).json()
    assert (shared["owner"], shared["shared"]) == ("Léa", True)

    # From Paul's profile: read-only
    anki.profile = "Paul"
    for method, path, body in [
        ("PUT", url, {"deck": "Changed", "cards": []}),
        ("PUT", url, {"deck": lesson["deck"], "cards": cards, "shared": False}),
        ("POST", f"{url}/revise", {"deck": "D", "cards": cards, "instruction": "remove the last card"}),
        ("DELETE", url, None),
    ]:
        r = client.request(method, path, json=body)
        assert (r.status_code, r.json()["detail"]) == (403, read_only), (method, path)
    r = client.post(f"{url}/regenerate", data={"prompt": "Texte à trous"})
    assert (r.status_code, r.json()["detail"]) == (403, read_only)

    # ...but Paul can still read it, send it to his own Anki and export it, without changing it
    assert client.get(url).status_code == 200
    changed = {"deck": "Paul's copy", "cards": cards[:1], "lesson_id": lesson["id"]}
    assert client.post("/api/anki/send", json={**SEND, **changed}).status_code == 200
    assert client.post("/api/export", json=changed).status_code == 200
    kept = client.get(url).json()
    assert (kept["deck"], len(kept["cards"]), kept["shared"], kept["exported_at"]) == (
        lesson["deck"],
        len(cards),
        True,
        None,
    )

    # Back in Léa's profile: hers to change; updates that don't mention sharing leave it alone
    anki.profile = "Léa"
    assert client.put(url, json={"deck": "D", "cards": []}).json()["shared"] is True
    assert client.delete(url).status_code == 200


def test_lesson_without_owner_is_everyones(client):
    lesson = extract_lesson(client)  # Anki closed: no owner
    assert lesson["owner"] == ""
    url = f"/api/lessons/{lesson['id']}"
    assert client.put(url, json={"deck": "D", "cards": []}).status_code == 200
    assert client.delete(url).status_code == 200


def test_other_profiles_private_lessons_hidden(anki, client):
    lea = extract_lesson(client)  # private to Léa
    anki.profile = "Paul"
    paul = extract_lesson(client)
    shared = extract_lesson(client)
    client.put(f"/api/lessons/{shared['id']}", json={"deck": "S", "cards": [], "shared": True})

    # Paul doesn't get Léa's private lesson, in any route
    ids = {lesson["id"] for lesson in client.get("/api/lessons").json()}
    assert ids == {paul["id"], shared["id"]}
    for method, url in [
        ("GET", f"/api/lessons/{lea['id']}"),
        ("GET", f"/api/lessons/{lea['id']}/photos/1"),
        ("DELETE", f"/api/lessons/{lea['id']}"),
    ]:
        assert client.request(method, url).status_code == 404
    assert client.put(f"/api/lessons/{lea['id']}", json={"deck": "x", "cards": []}).status_code == 404
    assert client.post("/api/anki/send", json={**SEND, "lesson_id": lea["id"]}).status_code == 404

    anki.profile = "Léa"  # back in Léa's profile: it's hers again
    assert client.get(f"/api/lessons/{lea['id']}").status_code == 200
    assert {lesson["id"] for lesson in client.get("/api/lessons").json()} == {lea["id"], shared["id"]}

    # Anki closed: no profile known, every lesson listed (read-only for those with an owner)
    anki.profile = None
    assert len(client.get("/api/lessons").json()) == 3


def test_admin_manages_every_lesson(anki, admin):
    lea = extract_lesson(admin)  # Léa's, private
    url = f"/api/admin/lessons/{lea['id']}"
    assert admin.get("/api/admin/lessons").status_code == 401  # settings password needed
    assert admin.put(url, json={"owner": "Paul"}).status_code == 401

    listing = admin.get("/api/admin/lessons", headers=ADMIN).json()
    assert listing["profiles"] == ["Léa", "Paul"]
    assert [(x["id"], x["owner"], x["shared"]) for x in listing["lessons"]] == [(lea["id"], "Léa", False)]

    # Given to Paul, shared, then to nobody; the content is untouched
    anki.profile = "Paul"
    assert admin.put(url, headers=ADMIN, json={"owner": "Paul"}).json()["owner"] == "Paul"
    assert admin.put(f"/api/lessons/{lea['id']}", json={"deck": "Paul's now", "cards": []}).status_code == 200
    assert admin.put(url, headers=ADMIN, json={"shared": True}).json()["shared"] is True
    nobody = admin.put(url, headers=ADMIN, json={"owner": ""}).json()
    assert (nobody["owner"], nobody["deck"]) == ("", "Paul's now")

    # A lesson whose owner left Anki can be deleted from the settings
    admin.put(url, headers=ADMIN, json={"owner": "Ghost"})
    assert admin.delete(url, headers=ADMIN).status_code == 200
    assert admin.get(f"/api/lessons/{lea['id']}").status_code == 404
    assert admin.delete(url, headers=ADMIN).status_code == 404
    assert admin.put(url, headers=ADMIN, json={"owner": "Paul"}).status_code == 404


def test_admin_lessons_without_anki(admin):
    extract_lesson(admin)
    listing = admin.get("/api/admin/lessons", headers=ADMIN).json()
    assert listing["profiles"] is None  # Anki closed: the page says so
    assert len(listing["lessons"]) == 1


def test_anki_notes_only_in_the_owners_profile(anki, admin):
    lesson = extract_lesson(admin)  # Léa's
    admin.post("/api/anki/send", json={"deck": lesson["deck"], "cards": lesson["cards"], "lesson_id": lesson["id"]})
    admin.put(f"/api/lessons/{lesson['id']}", json={"deck": lesson["deck"], "cards": lesson["cards"], "shared": True})
    anki.profile = "Paul"  # another profile can't delete it, nor see notes it can't have
    assert admin.get(f"/api/lessons/{lesson['id']}/anki-notes").status_code == 403
    assert admin.get(f"/api/admin/lessons/{lesson['id']}/anki-notes", headers=ADMIN).json() == {
        "available": False,
        "count": 0,
    }
    r = admin.delete(f"/api/admin/lessons/{lesson['id']}?anki=true", headers=ADMIN)
    assert (r.status_code, r.json()["detail"]["code"]) == (502, "anki.unreachable")
    anki.profile = "Léa"
    assert admin.get(f"/api/admin/lessons/{lesson['id']}/anki-notes", headers=ADMIN).json()["count"] == 6
