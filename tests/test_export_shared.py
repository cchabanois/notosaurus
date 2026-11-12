"""A test's cards, or lessons ticked, in one package for another family (POST
/api/export/shared): a deck of its own, a subdeck per lesson, the chosen cards only, nothing
of this home (the child's name and levels, its tags, its review history)."""

import sqlite3

import apkg
from conftest import extract_lesson
from helpers import plain_image

from app import anki

JULES = {"id": "jules", "name": "Jules", "grade": "5e", "decks": "Jules::{classe}"}


def _lesson(client, deck: str) -> dict:
    """A lesson made, then put in the child's deck as the page saves it."""
    made = extract_lesson(client)
    assert client.put(f"/api/lessons/{made['id']}", json={"deck": deck, "cards": made["cards"]}).status_code == 200
    return client.get(f"/api/lessons/{made['id']}").json()


def package_decks(package: apkg.Apkg) -> set[str]:
    return {d["name"] for d in package.decks.values() if d["name"] != "Default"}


def _lessons_decks(package: apkg.Apkg) -> set[str]:
    """The lessons' decks: the cards' parts (the demo's "Vocabulaire", "Phrases") left out."""
    return {"::".join(d.split("::")[:2]) for d in package_decks(package)}


def _shared(client, body: dict, dest) -> apkg.Apkg:
    res = client.post("/api/export/shared", json=body)
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/apkg"
    return apkg.Apkg(res.content, dest)


def test_a_tests_chosen_cards_in_one_package_without_the_child(client, tmp_path):
    client.put("/api/children", json=[JULES])
    revolution = _lesson(client, "Jules::5e::Histoire::Révolution")
    napoleon = _lesson(client, "Jules::5e::Histoire::Napoléon")
    some = [c["id"] for c in napoleon["cards"][:1]]
    exam = {
        "name": "Interro d'histoire",
        "lessons": [{"lesson": revolution["id"]}, {"lesson": napoleon["id"], "cards": some}],
    }
    assert client.put("/api/exams/interro", json=exam).status_code == 200

    (tmp_path / "shared").mkdir()
    (tmp_path / "whole").mkdir()
    package = _shared(client, {"exam": "interro"}, tmp_path / "shared")
    decks = _lessons_decks(package)
    assert decks == {"Interro d'histoire::Révolution", "Interro d'histoire::Napoléon"}
    assert not any("Jules" in d or "5e" in d for d in package_decks(package))
    # Every card of the first lesson, the one chosen of the second
    sent = apkg.export(client, {"deck": "X", "cards": revolution["cards"]}, tmp_path / "whole")
    assert len(package.notes) == len(sent.notes) + 1
    # Its note types the usual ones: an importer who has them gets no second copy
    assert set(package.models) <= set(sent.models) | {
        anki.model_id(nt) for nt in [anki.cloze_note_type(), anki.choice_note_type()]
    }

    conn = sqlite3.connect(tmp_path / "shared" / "collection.anki2")
    assert conn.execute("SELECT count(*) FROM revlog").fetchone()[0] == 0  # no review history
    assert {row for row in conn.execute("SELECT DISTINCT type, queue FROM cards")} == {(0, 0)}  # new cards
    tags = " ".join(t for (t,) in conn.execute("SELECT tags FROM notes"))
    assert "notosaurus::" not in tags and "Exam::" not in tags
    everything = "\n".join(str(row) for table in ("notes", "col") for row in conn.execute(f"SELECT * FROM {table}"))
    assert "Jules" not in everything and "jules" not in everything  # the lessons' ids name the child too
    conn.close()


def test_lessons_ticked_under_the_deck_they_share_or_a_name(client, tmp_path):
    client.put("/api/children", json=[JULES])
    a = _lesson(client, "Jules::5e::Histoire::Révolution")
    b = _lesson(client, "Jules::5e::Histoire::Napoléon")
    (tmp_path / "shared").mkdir()
    (tmp_path / "named").mkdir()

    package = _shared(client, {"lessons": [a["id"], b["id"]]}, tmp_path / "shared")
    assert _lessons_decks(package) == {"Histoire::Révolution", "Histoire::Napoléon"}

    named = _shared(client, {"lessons": [a["id"]], "name": "Pour Léa :: Histoire"}, tmp_path / "named")
    # One deck of its own, not a hierarchy it didn't ask for; one lesson: the package's deck itself
    assert {d.split("::")[0] for d in package_decks(named)} == {"Pour Léa - Histoire"}
    assert not any("Révolution" in d for d in package_decks(named))


def test_nothing_to_share(client):
    assert client.post("/api/export/shared", json={"lessons": []}).json()["detail"]["code"] == "export.no_cards"
    assert (
        client.post("/api/export/shared", json={"lessons": ["nowhere"]}).json()["detail"]["code"] == "export.no_cards"
    )
    assert client.post("/api/export/shared", json={"exam": "none"}).status_code == 404


def test_a_diagrams_labels_shared_with_their_image_not_the_lessons_id(client, tmp_path):
    """A lesson's id is made from its deck, which may name the child ("…-jules-5e-svt-…"): a
    diagram's labels carried it in their key; shared, a key of their own."""
    client.put("/api/children", json=[JULES])
    made = client.post(
        "/api/extract",
        files=[("images", ("p.jpg", plain_image(1000, 500), "image/jpeg"))],
        data={"prompt": "Le schéma sans les noms", "child": "jules"},  # its deck in the child's
    ).json()
    assert "jules" in made["id"]

    package = _shared(client, {"lessons": [made["id"]]}, tmp_path)
    fields = package.fields_by_name(package.notes[0])
    assert fields["Masks"].count("notosaurus-mask") == 3 and len(package.media) == 1  # its image goes with it
    assert "jules" not in fields["Id"]
    assert not any("Jules" in d for d in package_decks(package))
