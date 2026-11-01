"""Pictures on cards ("front: the picture of the word"), drawn by an image model."""

import base64
import io

import apkg
import pytest
from helpers import bomb_png, plain_image, run
from PIL import Image

from app.settings import Settings
from notosaurus_core import diagrams, llm, pictures, tts
from notosaurus_core.config import AIConfig
from notosaurus_core.errors import AppError
from notosaurus_core.models import Card, PicturePlan
from notosaurus_core.relay_api import MAX_IMAGE_BYTES


def png(color="red") -> bytes:
    return plain_image(1024, 1024, color, "PNG")


@pytest.fixture
def drawn(monkeypatch):
    """A fake image model: records each call like a real one (0.03 $ each)."""
    subjects = []

    async def draw(s, subject):
        subjects.append(subject)
        if "umbrella" in subject:
            raise pictures.PictureError("picture.failed", detail="refused")
        await llm.record(s, "openrouter.ai", "google/gemini-3.1-flash-lite-image", 20, 1300, cost=0.03)
        return png()

    monkeypatch.setattr(pictures, "draw", draw)
    return subjects


def lesson_with_pictures(client):
    return client.post("/api/extract", data={"prompt": "10 mots courants, recto : image du mot"}).json()


def test_cards_ask_for_pictures_and_get_ids(client):
    lesson = lesson_with_pictures(client)
    assert [c["picture_prompt"] for c in lesson["cards"]] == ["an apple", "a dog", "an umbrella", ""]
    assert all(c["id"] and not c["picture"] for c in lesson["cards"])
    assert len({c["id"] for c in lesson["cards"]}) == 4


def test_pictures_drawn_and_kept(client, drawn):
    lesson = lesson_with_pictures(client)
    res = client.post(f"/api/lessons/{lesson['id']}/pictures", json={"draw": True}).json()
    cards = res["lesson"]["cards"]
    assert res["failures"] == 1  # the umbrella: its card stays without a picture
    assert res["error"] == {"code": "picture.failed", "params": {"detail": "refused"}}  # why, for the page
    assert sorted(drawn) == ["a dog", "an apple", "an umbrella"]  # nothing for "tomorrow"
    assert [bool(c["picture"]) for c in cards] == [True, True, False, False]
    assert [c["id"] for c in cards] == [c["id"] for c in lesson["cards"]]  # ids kept
    picture = client.get(f"/api/lessons/{lesson['id']}/pictures/{cards[0]['picture']}")
    assert picture.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(picture.content)).size == (pictures.SIDE, pictures.SIDE)
    calls = client.get(f"/api/lessons/{lesson['id']}").json()["ai_calls"]
    assert [c["kind"] for c in calls] == ["extract", "picture", "picture"]

    # Drawn again: only what is missing (the umbrella, failing again)
    drawn.clear()
    client.post(f"/api/lessons/{lesson['id']}/pictures", json={"draw": True})
    assert drawn == ["an umbrella"]


def test_picture_names_checked(client, drawn):
    lesson = lesson_with_pictures(client)
    for name in ("../lesson.json", "page-1.jpg", "picture-x-12345678.jpg"):
        assert client.get(f"/api/lessons/{lesson['id']}/pictures/{name}").status_code == 404


def test_picture_cards_in_anki(client, drawn, tmp_path):
    lesson = lesson_with_pictures(client)
    cards = client.post(f"/api/lessons/{lesson['id']}/pictures", json={"draw": True}).json()["lesson"]["cards"]

    def package(cards):
        return apkg.export(client, {"deck": "D", "cards": cards, "lesson_id": lesson["id"]}, tmp_path)

    first = package(cards)
    names = first.models
    # A picture is any card's: the same note type as the umbrella without its, and "tomorrow"
    assert {names[mid]["name"] for _, mid, _ in first.notes} == {"Notosaurus recto/verso (audio)"}
    pictured = [first.fields_by_name(note) for note in first.notes if first.fields_by_name(note)["Picture"]]
    assert len(pictured) == 2 and pictured[0]["Front"] == "Comment dit-on en anglais ?"
    assert (pictured[0]["Picture"], pictured[0]["Id"]) == (f'<img src="{cards[0]["picture"]}">', cards[0]["id"])
    assert first.media == sorted([cards[0]["picture"], cards[1]["picture"]])

    # Same front on every picture card, then a new picture: the same notes (GUID from the id)
    cards[0]["picture"], cards[1]["front"] = cards[1]["picture"], ""
    assert package(cards).guids == first.guids


def test_only_the_owner_draws(client, drawn, monkeypatch):
    from app import ankiconnect

    profile = {"name": "Léa"}

    async def active_profile():
        return profile["name"]

    monkeypatch.setattr(ankiconnect, "active_profile", active_profile)
    lesson = lesson_with_pictures(client)  # Léa's
    client.put(f"/api/lessons/{lesson['id']}", json={"deck": "D", "cards": lesson["cards"], "shared": True})
    profile["name"] = "Paul"
    assert client.post(f"/api/lessons/{lesson['id']}/pictures").status_code == 403


def test_correction_keeps_ids_and_pictures():
    before = [
        Card(front="Q", back="an apple", picture_prompt="an apple", picture="picture-a-12345678.jpg", id="a"),
        Card(front="Q", back="a dog", picture_prompt="a dog", picture="picture-b-12345678.jpg", id="b"),
    ]
    revised = [
        Card(front="Q", back="a dog", picture_prompt="a dog"),
        Card(front="Q", back="the apple", picture_prompt="an apple"),  # answer fixed: same card
        Card(front="Q", back="a cat", picture_prompt="a cat"),  # added
    ]
    llm._keep_ids(revised, before)
    assert [(c.id, c.picture) for c in revised] == [
        ("b", "picture-b-12345678.jpg"),
        ("a", "picture-a-12345678.jpg"),
        ("", ""),
    ]


def test_pictures_drawn_by_the_cards_service():
    def drawing(**kw):
        s = Settings(**kw)
        return pictures.service(s), pictures.model(s)

    assert drawing() == ("", "")  # no key
    # The cards' own service, when it draws
    assert drawing(llm="gemini", gemini_api_key="k") == ("gemini", "gemini-3.1-flash-lite-image")
    assert drawing(llm="openai", openai_api_key="k", openrouter_api_key="r") == ("openai", "gpt-image-2")
    assert drawing(llm="openrouter", openrouter_api_key="k", gemini_api_key="free") == (
        "openrouter",
        "google/gemini-3.1-flash-lite-image",
    )
    # Claude or a local model can't draw: the first service with a key
    assert drawing(llm="anthropic", gemini_api_key="k") == ("gemini", "gemini-3.1-flash-lite-image")
    assert drawing(llm="compatible", gemini_api_key="g", openrouter_api_key="r")[0] == "openrouter"
    # Chosen on purpose: that service, with its model or the one set
    chosen = {"llm": "openai", "openai_api_key": "k", "openrouter_api_key": "r", "picture_service": "openrouter"}
    assert drawing(**chosen) == ("openrouter", "google/gemini-3.1-flash-lite-image")
    assert drawing(**chosen, picture_model="openai/gpt-5-image-mini") == ("openrouter", "openai/gpt-5-image-mini")
    assert drawing(llm="gemini", gemini_api_key="k", picture_service="openai") == ("", "")  # its key is missing
    assert drawing(llm="gemini", gemini_api_key="k", picture_service="none") == ("", "")  # no pictures


def test_picture_model_saved_before_the_service(client, tmp_path):
    """A model saved alone went through the service its name told: still the same."""
    import json

    from app import settings

    path = tmp_path / "data" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"llm": "openai", "picture_model": "google/gemini-3.1-flash-image"}))
    assert settings.current().picture_service == "openrouter"
    path.write_text(json.dumps({"llm": "anthropic", "picture_model": "gemini-3.1-flash-image"}))
    assert settings.current().picture_service == "gemini"


def test_cache_reused_by_the_next_lessons(client, drawn):
    first = lesson_with_pictures(client)
    client.post(f"/api/lessons/{first['id']}/pictures", json={"draw": True})
    assert sorted(drawn) == ["a dog", "an apple", "an umbrella"]
    drawn.clear()
    second = lesson_with_pictures(client)  # the same subjects
    cards = client.post(f"/api/lessons/{second['id']}/pictures", json={"draw": True}).json()["lesson"]["cards"]
    assert drawn == ["an umbrella"]  # only the one that failed: the others come from the cache, free
    assert [bool(c["picture"]) for c in cards] == [True, True, False, False]
    calls = client.get(f"/api/lessons/{second['id']}").json()["ai_calls"]
    assert [c["kind"] for c in calls] == ["extract"]  # nothing paid for the pictures


def test_image_made_then_drawn_when_asked(client, drawn):
    """ "✨ Image": decided first (make: a figure drawn, a picture's description and search
    words for the page to look for free ones); drawn by the image model only when asked."""
    lesson = lesson_with_pictures(client)
    cards = client.post(f"/api/lessons/{lesson['id']}/pictures", json={"draw": True}).json()["lesson"]["cards"]
    apple = cards[0]
    make = f"/api/lessons/{lesson['id']}/cards/{apple['id']}/picture/make"
    draw = f"/api/lessons/{lesson['id']}/cards/{apple['id']}/picture/draw"

    drawn.clear()
    res = client.post(make, json={}).json()  # the same subject: nothing to decide, nothing drawn
    assert drawn == [] and res["search"] and res["card"]["picture"] == apple["picture"]
    res = client.post(draw).json()  # the user said yes: drawn anew, not from the cache
    assert drawn == ["an apple"] and res["card"]["picture"] and res["card"]["id"] == apple["id"]
    res = client.post(make, json={"subject": "a green apple"}).json()
    assert res["card"]["picture_prompt"] == "a green apple" and res["search"] and drawn == ["an apple"]
    res = client.post(draw).json()
    assert drawn[-1] == "a green apple"
    saved = client.get(f"/api/lessons/{lesson['id']}").json()
    assert saved["cards"][0]["picture"] == res["card"]["picture"]
    # 2 at first + 1 drawn again + the new subject planned and drawn
    assert [c["kind"] for c in saved["ai_calls"]].count("picture") == 5

    # A card without a picture ("tomorrow"): nothing written, the AI plans it from the card
    tomorrow = cards[3]
    make = f"/api/lessons/{lesson['id']}/cards/{tomorrow['id']}/picture/make"
    res = client.post(make, json={"subject": " "}).json()
    assert res["card"]["picture_prompt"] == tomorrow["back"] and not res["card"]["picture"]  # the demo AI: the back
    assert client.post(make, json={"subject": "un calendrier"}).json()["card"]["picture_prompt"] == "un calendrier"
    assert client.post(f"/api/lessons/{lesson['id']}/cards/nope/picture/make", json={}).status_code == 404


def test_no_picture_drawn_without_a_yes(client, drawn):
    """After a generation, the pictures no free one fits are listed, not drawn: the image
    model costs, the user is asked first."""
    lesson = lesson_with_pictures(client)
    res = client.post(f"/api/lessons/{lesson['id']}/pictures").json()
    assert drawn == []
    assert sorted(res["to_draw"]) == sorted(c["id"] for c in lesson["cards"][:3])  # the three with a picture
    assert not any(c["picture"] for c in res["lesson"]["cards"])
    res = client.post(f"/api/lessons/{lesson['id']}/pictures", json={"draw": True}).json()
    assert sorted(drawn) == ["a dog", "an apple", "an umbrella"] and res["to_draw"] == []


def test_own_photo_then_no_picture(client, drawn, tmp_path):
    lesson = lesson_with_pictures(client)
    cards = client.post(f"/api/lessons/{lesson['id']}/pictures", json={"draw": True}).json()["lesson"]["cards"]
    dog = cards[1]
    url = f"/api/lessons/{lesson['id']}/cards/{dog['id']}/picture"
    res = client.post(url, files={"photo": ("p.jpg", plain_image(1600, 1200, "blue"), "image/jpeg")}).json()
    assert res["card"]["picture"] != dog["picture"]
    folder = tmp_path / "data" / "lessons" / lesson["id"] / "images"
    assert not (folder / dog["picture"]).exists()  # the replaced picture is removed
    assert Image.open(folder / res["card"]["picture"]).size == (pictures.SIDE, 384)
    assert client.post(url, files={"photo": ("p.txt", b"x", "text/plain")}).status_code == 400

    res = client.delete(url).json()
    assert (res["card"]["picture"], res["card"]["picture_prompt"]) == ("", "")  # a text card now
    assert not any(folder.glob(f"picture-{dog['id']}-*"))


def test_uploads_too_heavy_refused(client, drawn):
    """The page sends prepared photos (a few hundred KB): a far heavier one is refused
    before being read whole into memory, as the relay refuses it."""
    heavy = b"\xff\xd8" + b"x" * MAX_IMAGE_BYTES
    too_large = {"code": "extract.too_large", "params": {"max": 4}}
    res = client.post("/api/extract", files=[("images", ("p.jpg", heavy, "image/jpeg"))], data={"prompt": "x"})
    assert (res.status_code, res.json()["detail"]) == (413, too_large)

    lesson = lesson_with_pictures(client)
    url = f"/api/lessons/{lesson['id']}/cards/{lesson['cards'][0]['id']}/picture"
    res = client.post(url, files={"photo": ("p.jpg", heavy, "image/jpeg")})
    assert (res.status_code, res.json()["detail"]) == (413, too_large)
    res = client.post(f"/api/lessons/{lesson['id']}/complete", files=[("images", ("p.jpg", heavy, "image/jpeg"))],
                      data={"prompt": "x"})  # fmt: skip
    assert res.status_code == 413


BOMBS = [
    pytest.param(20_000, id="refused-by-pillow"),  # DecompressionBombError: neither OSError nor ValueError
    pytest.param(10_000, id="over-the-limit"),  # Pillow only warns below twice its limit: refused all the same
]
CANT_READ = {"code": "relay.bad_image", "params": {}}


@pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning")
@pytest.mark.parametrize("side", BOMBS)
def test_a_decompression_bomb_is_a_photo_that_cant_be_read(client, drawn, side):
    """A PNG of a few bytes claiming side² pixels: a clean error, never a 500, nothing saved."""
    bomb = [("images", ("p.png", bomb_png(side), "image/png"))]
    res = client.post("/api/extract", files=bomb, data={"prompt": "FR → ES"})
    assert (res.status_code, res.json()["detail"]) == (415, CANT_READ)
    assert client.get("/api/lessons").json() == []

    lesson = lesson_with_pictures(client)
    res = client.post(f"/api/lessons/{lesson['id']}/complete", files=bomb, data={"prompt": "x"})
    assert (res.status_code, res.json()["detail"]) == (415, CANT_READ)

    url = f"/api/lessons/{lesson['id']}/cards/{lesson['cards'][0]['id']}/picture"
    res = client.post(url, files={"photo": ("p.png", bomb_png(side), "image/png")})  # the user's own photo
    assert (res.status_code, res.json()["detail"]) == (415, CANT_READ)
    assert not client.get(f"/api/lessons/{lesson['id']}").json()["cards"][0]["picture"]


@pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning")
@pytest.mark.parametrize("side", BOMBS)
def test_a_decompression_bomb_never_decoded(side):
    """In the core, wherever a picture or a photo is opened (the relay's too)."""
    for opening in (
        lambda: pictures.card_size(bomb_png(side)),  # a drawn, found or own picture
        lambda: diagrams.prepare(bomb_png(side), "image/png"),  # a photo sent to the AI
        lambda: diagrams.turn(bomb_png(side), [], 90),  # turned upright
    ):
        with pytest.raises(AppError) as e:
            opening()
        assert (e.value.code, e.value.status) == ("relay.bad_image", 415)
    assert diagrams.prepare(b"\xff\xd8not a photo", "image/jpeg")[2] is None  # unreadable: sent as is, as before


def test_the_settings_picture_test(admin, drawn, monkeypatch):
    """The settings draw one picture with the chosen service and model, shown with its cost."""
    from conftest import ADMIN

    assert admin.post("/api/admin/pictures/test").status_code == 401  # the settings' password
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    found = admin.post("/api/admin/pictures/test", headers=ADMIN).json()
    assert drawn == ["a giraffe"]
    assert (found["service"], found["model"], found["cost"]) == (
        "openrouter",
        "google/gemini-3.1-flash-lite-image",
        0.03,
    )
    assert found["image"].startswith("data:image/jpeg;base64,")
    image = Image.open(io.BytesIO(base64.b64decode(found["image"].split(",", 1)[1])))
    assert image.size == (pictures.SIDE, pictures.SIDE)  # as on a card


def test_every_image_model_of_the_service(admin, monkeypatch):
    """The settings suggest every model the drawing service lists that draws as asked."""
    from conftest import ADMIN

    listed = {
        "gemini": [
            {"id": "gemini-3.1-flash-lite-image", "actions": ["generateContent", "countTokens"]},
            {"id": "gemini-3.8-flash", "actions": ["generateContent"]},  # writes, doesn't draw
            {"id": "imagen-5.0-generate", "actions": ["predict"]},  # another API
        ],
        "openai": [{"id": "gpt-image-2.5-flare"}, {"id": "gpt-image-1-mini"}, {"id": "dall-e-3"}, {"id": "gpt-6-luna"}],
        "openrouter": [
            {"id": "openai/gpt-5.4-image-2", "outputs": ["image", "text"]},
            {"id": "google/gemini-3.1-flash-image:batch", "outputs": ["image", "text"]},  # answered hours later
            {"id": "openrouter/auto", "outputs": ["text", "image"]},  # a router, not a model
            {"id": "google/gemini-3.8-flash", "outputs": ["text"]},
        ],
    }

    async def fetch(s, drawing):
        return listed[drawing]

    monkeypatch.setattr(pictures, "_fetch_models", fetch)
    for service, key, expected in (
        ("gemini", "GEMINI_API_KEY", ["gemini-3.1-flash-lite-image"]),
        ("openai", "OPENAI_API_KEY", ["gpt-image-1-mini", "gpt-image-2.5-flare"]),
        ("openrouter", "OPENROUTER_API_KEY", ["openai/gpt-5.4-image-2"]),
    ):
        monkeypatch.setenv(key, "k")
        admin.put("/api/admin/settings", headers=ADMIN, json={"picture_service": service})
        assert admin.post("/api/admin/pictures/models", headers=ADMIN).json() == {
            "service": service,
            "models": expected,
        }

    admin.put("/api/admin/settings", headers=ADMIN, json={"picture_service": "none"})
    assert admin.post("/api/admin/pictures/models", headers=ADMIN).json()["detail"]["code"] == "picture.no_model"


def test_failing_pictures_and_sounds_log_nothing_of_the_lesson(monkeypatch, caplog, tmp_path):
    """The relay's logs hold nothing of a lesson: neither a picture's subject nor a text read,
    nor an error quoting them."""

    async def figure_or_picture(s, folder, card, **_):
        if "volcano" in card.picture_prompt:
            raise pictures.PictureError("picture.failed", detail=f"refused: {card.picture_prompt}")
        raise ValueError(f"not an image: {card.figure}")

    monkeypatch.setattr(pictures, "figure_or_picture", figure_or_picture)
    cards = [
        Card(front="Le volcan", back="El volcán", picture_prompt="an erupting volcano"),
        Card(front="Le cycle de l'eau", back="…", figure="the water cycle, with clouds"),
    ]

    async def synthesize(text, voice, path, rate):
        raise RuntimeError(f"cannot read {text}")

    monkeypatch.setattr(tts, "_synthesize", synthesize)
    with caplog.at_level("WARNING", logger="notosaurus"):
        assert run(pictures.draw_all(AIConfig(llm="gemini"), tmp_path, cards, draw=True))[0] == 2
        assert run(tts.tts_many(["el volcán ruge"], "es-ES-ElviraNeural", tmp_path)) == ({}, 1)
    assert len(caplog.records) == 3 and "picture.failed" in caplog.text and "RuntimeError" in caplog.text
    for content in ("volcano", "water cycle", "volcán"):
        assert not any(content in r.getMessage() for r in caplog.records)


def test_a_picture_showing_the_answer_goes_on_the_back(monkeypatch):
    """ "✨ Image" on a card: a picture naming its answer (the countries of an alliance on a
    map) goes with the answer, never giving it away on the front; one that only shows what the
    question is about stays on the front."""
    for on_back in (True, False):

        async def plan(s, front, back, asked="", language="English", on_back=on_back):
            return PicturePlan(kind="figure", description="Carte de l'Europe", on_back=on_back)

        monkeypatch.setattr(llm, "plan_picture", plan)
        card = Card(front="Quels pays forment la Triple-Alliance ?", back="Allemagne, Autriche-Hongrie, Italie")
        decided = run(pictures.decided(AIConfig(llm="gemini"), card))
        assert decided.picture_on_back is on_back and decided.figure == "Carte de l'Europe"
