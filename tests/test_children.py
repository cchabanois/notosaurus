"""The children's cards (app/children.py): their class and instructions told to the AI,
never their name; their decks the lessons go in; the instructions per Anki profile, before,
made cards."""

from app import children, settings
from app.children import Child


def test_cards_listed_saved_and_refused_twice(client):
    assert client.get("/api/children").json() == []
    jules = {
        "id": "jules",
        "name": "Jules",
        "grade": "5e",
        "decks": "Jules::{classe}",
        "instructions": "Peu de cartes.",
    }
    saved = client.put("/api/children", json=[jules, {"id": "mathilde", "name": "Mathilde", "grade": "3e"}]).json()
    assert [c["name"] for c in saved] == ["Jules", "Mathilde"]
    assert client.get("/api/children").json()[0] == {**jules, "anki_profile": ""}
    twice = client.put("/api/children", json=[jules, jules])
    assert (twice.status_code, twice.json()["detail"]["code"]) == (400, "children.same_id")
    assert client.put("/api/children", json=[{**jules, "id": "../x"}]).status_code == 422


def test_the_ai_told_the_class_and_instructions_never_the_name():
    jules = Child(id="jules", name="Jules", grade="5e", instructions="Il confond b et d.")
    told = children.for_ai(jules)
    assert "5e" in told and "Il confond b et d." in told and "Jules" not in told
    assert children.for_ai(None) == ""
    text = settings.standing_instructions(settings.Settings(instructions="Pour tous."), told)
    assert "Pour tous." in text and "5e" in text and "Jules" not in text  # the profile's name neither


def test_the_childs_decks_with_its_class_not_twice():
    jules = Child(id="jules", name="Jules", grade="5e", decks="Jules::{classe}")
    assert children.deck_for(jules, "Anglais::School subjects") == "Jules::5e::Anglais::School subjects"
    # The AI's deck holding the class already ("5ème"), or the child's name: not twice
    assert children.deck_for(jules, "Anglais::5ème::School subjects") == "Jules::5e::Anglais::School subjects"
    assert children.deck_for(jules, "jules::Maths") == "Jules::5e::Maths"
    assert children.deck_for(Child(id="m", name="M", decks="Mathilde"), "SVT") == "Mathilde::SVT"
    assert children.deck_for(Child(id="m", name="M", decks="Mathilde::{class}"), "SVT") == "Mathilde::SVT"  # no class
    assert children.deck_for(Child(id="m", name="M"), "SVT") == "SVT"  # no decks of its own
    assert children.deck_for(None, "SVT") == "SVT"


def test_the_instructions_per_profile_become_cards(client, monkeypatch):
    s = settings.current()
    monkeypatch.setattr(
        settings, "current", lambda: s.model_copy(update={"profile_instructions": {"Léa": "5e", "Tom": " "}})
    )
    assert [(c.id, c.name, c.instructions, c.anki_profile) for c in children.list_all()] == [
        ("lea", "Léa", "5e", "Léa")
    ]


def test_a_lesson_for_a_child(client, monkeypatch):
    from app.routes import generation
    from notosaurus_core import llm

    seen = {}

    async def extract_cards(s, images, prompt, deck="", decks=(), **options):
        seen["instructions"] = options["instructions"]
        return await llm.extract_cards(s, images, prompt, deck, decks)

    monkeypatch.setattr(generation, "extract_cards", extract_cards)
    jules = {
        "id": "jules",
        "name": "Jules",
        "grade": "5e",
        "decks": "Jules::{classe}",
        "instructions": "Peu de cartes.",
    }
    client.put("/api/children", json=[jules])
    lesson = client.post("/api/extract", data={"prompt": "FR → ES", "child": "jules"}).json()
    assert lesson["child"] == "jules" and lesson["deck"].startswith("Jules::5e::")
    assert "5e" in seen["instructions"] and "Peu de cartes." in seen["instructions"]
    assert "Jules" not in seen["instructions"]
    assert client.get("/api/lessons").json()[0]["child"] == "jules"  # the list tells, the page filters
    # Made again: still for Jules
    again = client.post(f"/api/lessons/{lesson['id']}/regenerate", data={"prompt": "FR → ES"}).json()
    assert again["child"] == "jules"
    # For no child: as before
    other = client.post("/api/extract", data={"prompt": "FR → ES"}).json()
    assert other["child"] == "" and not other["deck"].startswith("Jules")


def test_no_childs_name_in_the_decks_the_ai_sees(client, monkeypatch):
    from app.routes import generation, lessons
    from notosaurus_core import llm

    every = [Child(id="jules", name="Jules", grade="5e", decks="Jules::{classe}")]
    assert children.split_deck("Jules::5e::Anglais::Food", every) == ("Jules::5e", "Anglais::Food")
    assert children.for_ai_deck("Anglais::Food", every) == "Anglais::Food"

    client.put("/api/children", json=[every[0].model_dump()])
    seen = {}

    async def extract_cards(s, images, prompt, deck="", decks=(), **options):
        seen["decks"] = decks
        return await llm.extract_cards(s, images, prompt, deck, decks)

    monkeypatch.setattr(generation, "extract_cards", extract_cards)
    first = client.post("/api/extract", data={"prompt": "FR → ES", "child": "jules"}).json()
    client.post("/api/extract", data={"prompt": "FR → ES", "child": "jules"})
    assert seen["decks"] and not any("Jules" in d or d.startswith("5e") for d in seen["decks"])

    async def revise_cards(s, photos, prompt, deck, instruction, *rest, **options):
        seen["revised"] = deck.deck
        return await llm.revise_cards(s, photos, prompt, deck, instruction, *rest, **options)

    monkeypatch.setattr(lessons, "revise_cards", revise_cards)
    body = {**first, "instruction": "ajoute une carte"}
    revised = client.post(f"/api/lessons/{first['id']}/revise", json=body).json()["lesson"]
    assert not seen["revised"].startswith("Jules") and revised["deck"] == first["deck"]  # put back


def test_only_the_childs_decks_and_no_ones_to_the_ai():
    jules = Child(id="jules", name="Jules", grade="5e", decks="Jules::{classe}")
    mathilde = Child(id="mathilde", name="Mathilde", grade="3e", decks="Mathilde")
    every = [jules, mathilde]
    decks = ["Jules::5e::Anglais::Food", "Mathilde::SVT::La cellule", "Maths::Fractions", "Jules"]
    assert children.decks_for_ai(decks, every, jules) == ["Anglais::Food", "Maths::Fractions"]
    assert children.decks_for_ai(decks, every, mathilde) == ["Maths::Fractions", "SVT::La cellule"]
    assert children.decks_for_ai(decks, every, None) == ["Maths::Fractions"]  # a lesson for no one


def test_the_child_of_the_anki_profile():
    """The child of a lesson made in an Anki profile, none chosen: its only one."""
    jules = Child(id="jules", name="Jules", anki_profile="Jules (Anki)")
    every = [jules, Child(id="m", name="M", anki_profile="Famille"), Child(id="t", name="T", anki_profile="Famille")]
    assert children.chosen(every, "", "Jules (Anki)") is jules
    assert children.chosen(every, "m", "Jules (Anki)").id == "m"  # the page's choice first
    assert children.chosen(every, "", "Famille") is None  # a shared profile: chosen in the page
    assert children.chosen(every, "", "Autre") is None and children.chosen(every, "", None) is None


def test_cards_saved_before_linked_to_their_profile(client, monkeypatch):
    """Format 1 (no links): the cards made from the instructions per profile linked to it."""
    from app import storage

    s = settings.current()
    monkeypatch.setattr(settings, "current", lambda: s.model_copy(update={"profile_instructions": {"Léa": "5e"}}))
    cards = [{"id": "lea", "name": "Léa", "instructions": "5e"}, {"id": "tom", "name": "Tom"}]
    storage.write_json(children._path(), {"format": 1, "children": cards})
    assert [c.anki_profile for c in children.list_all()] == ["Léa", ""]


def test_a_lesson_copied_for_another_child(client):
    """Its decks, its child, new cards (other notes in Anki), the pictures with them; free."""
    from app import lessons, storage

    jules = {"id": "jules", "name": "Jules", "grade": "5e", "decks": "Jules::5e"}
    mathilde = {"id": "mathilde", "name": "Mathilde", "grade": "3e", "decks": "Mathilde::3e"}
    client.put("/api/children", json=[jules, mathilde])
    lesson = client.post("/api/extract", data={"prompt": "FR → ES", "child": "jules"}).json()
    first = lesson["cards"][0]
    folder = lessons.folder(lesson["id"])
    (folder / "images").mkdir(exist_ok=True)
    picture = f"picture-{first['id']}-abcdef12.jpg"
    (folder / "images" / picture).write_bytes(b"jpeg")
    saved = storage.read_json(folder / "lesson.json")  # a picture (the server sets them)
    saved["cards"][0]["picture"] = picture
    storage.write_json(folder / "lesson.json", saved)

    copy = client.post(f"/api/lessons/{lesson['id']}/copy", json={"child": "mathilde"}).json()
    assert copy["id"] != lesson["id"] and copy["child"] == "mathilde"
    assert copy["deck"] == lesson["deck"].replace("Jules::5e", "Mathilde::3e")
    assert [c["front"] for c in copy["cards"]] == [c["front"] for c in lesson["cards"]]
    assert not {c["id"] for c in copy["cards"]} & {c["id"] for c in lesson["cards"]}
    copied = copy["cards"][0]["picture"]
    assert copied == f"picture-{copy['cards'][0]['id']}-abcdef12.jpg"
    assert (lessons.folder(copy["id"]) / "images" / copied).read_bytes() == b"jpeg"
    assert copy["ai_calls"] == [] and copy["exported_at"] is None and copy["anki_notes"] == {}
    assert client.get(f"/api/lessons/{lesson['id']}").json()["cards"][0]["picture"] == picture  # unchanged
    gone = client.post(f"/api/lessons/{lesson['id']}/copy", json={"child": "nobody"})
    assert (gone.status_code, gone.json()["detail"]["code"]) == (404, "children.not_found")
