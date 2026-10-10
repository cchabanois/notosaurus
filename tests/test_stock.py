"""Free pictures found for a card (stock): the licences kept, what pupils mustn't see
left out, the sources taking turns, nothing fetched from an address the client gives."""

import asyncio
import io
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from PIL import Image as PILImage

from notosaurus_core import files, llm, pictures, stock
from notosaurus_core.config import AIConfig
from notosaurus_core.errors import AppError
from notosaurus_core.models import PictureSource
from notosaurus_core.providers import gemini


def jpeg(side=300) -> bytes:
    out = io.BytesIO()
    PILImage.new("RGB", (side, side), "teal").save(out, "JPEG")
    return out.getvalue()


def commons_page(index, title, licence="pd", categories="Paintings", host="upload.wikimedia.org", mime="image/jpeg"):
    meta = {"License": {"value": licence}, "Categories": {"value": categories}}
    return {
        "index": index,
        "title": title,
        "imageinfo": [
            {
                "mime": mime,
                "thumburl": f"https://{host}/thumb/{index}.jpg",
                "descriptionurl": f"https://commons.wikimedia.org/wiki/{title}",
                "extmetadata": meta,
            }
        ],
    }


COMMONS = {
    "query": {
        "pages": {
            "1": commons_page(2, "File:Prise de la Bastille.jpg"),
            "2": commons_page(1, "File:Storming.jpg", licence="cc0"),
            "3": commons_page(3, "File:Someone's.jpg", licence="cc-by-sa-4.0"),  # asks for credit: left out
            "4": commons_page(4, "File:Nude study.jpg"),  # not for pupils
            "5": commons_page(5, "File:Bastille.svg", mime="image/svg+xml"),
            "6": commons_page(6, "File:Elsewhere.jpg", host="evil.example"),  # its preview is never fetched
        }
    }
}
OPENVERSE = {
    "results": [
        {
            "id": "d32a3ea6-bbb6-4987-affb-e6a1198d07ac",
            "title": "Bastille",
            "license": "pdm",
            "mature": False,
            "thumbnail": "https://api.openverse.org/v1/images/d32a3ea6-bbb6-4987-affb-e6a1198d07ac/thumb/",
            "foreign_landing_url": "https://www.flickr.com/photos/x/1",
        },
        {
            "id": "93cbbfc8-a7d7-4a4d-b7af-ada48bb57f66",
            "title": "Mature",
            "license": "cc0",
            "mature": True,
            "thumbnail": "https://api.openverse.org/v1/images/93cbbfc8-a7d7-4a4d-b7af-ada48bb57f66/thumb/",
        },
    ]
}
PIXABAY = {
    "hits": [
        {
            "id": 42,
            "tags": "fortress, paris, fortress",
            "previewURL": "https://cdn.pixabay.com/p/42.jpg",
            "webformatURL": "https://pixabay.com/get/42.jpg",
            "pageURL": "https://pixabay.com/photos/fortress-42/",
        }
    ]
}


class Services:
    def __init__(self, failing=()):
        self.failing, self.asked = set(failing), []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.asked.append(request)
        host = request.url.host
        if host in self.failing:
            return httpx.Response(503)
        if host == "commons.wikimedia.org":
            return httpx.Response(200, json=COMMONS)
        if host == "api.openverse.org" and request.url.path == "/v1/images/":
            return httpx.Response(200, json=OPENVERSE)
        if host == "api.openverse.org" and request.url.path.count("/") == 4:  # /v1/images/<id>/: its details
            found = next(r for r in OPENVERSE["results"] if r["id"] in request.url.path)
            return httpx.Response(200, json=found)
        if host == "pixabay.com" and request.url.path == "/api/":
            return httpx.Response(200, json=PIXABAY)
        return httpx.Response(200, content=jpeg())  # a picture


def run(coroutine):
    with ThreadPoolExecutor(1) as pool:  # after the page tests, Playwright's loop runs in this thread
        return pool.submit(asyncio.run, coroutine).result()


@pytest.fixture
def services(monkeypatch):
    fake = Services()
    monkeypatch.setattr(stock, "_transport", httpx.MockTransport(fake))
    stock._cache.clear()
    return fake


def test_only_free_pictures_pupils_may_see(services):
    found = run(stock.search("storming of the Bastille"))
    assert [(f.source, f.id, f.licence) for f in found] == [
        ("openverse", "d32a3ea6-bbb6-4987-affb-e6a1198d07ac", "Public domain"),  # the sources take turns
        ("commons", "File:Storming.jpg", "CC0"),
        ("commons", "File:Prise de la Bastille.jpg", "Public domain"),
    ]
    assert found[1].title == "Storming" and all(f.preview.startswith("data:image/jpeg;base64,") for f in found)
    assert not any(r.url.host == "evil.example" for r in services.asked)
    assert not any(r.url.host == "pixabay.com" for r in services.asked)  # no key: no Pixabay (the computer)


def test_pixabay_with_the_relays_key(services):
    found = run(stock.search("Bastille", pixabay_key="k"))
    assert found[0].source == "pixabay" and found[0].licence == "Pixabay"
    assert found[0].title == "fortress, paris"  # each tag once
    search = next(r for r in services.asked if r.url.host == "pixabay.com")
    assert search.url.params["safesearch"] == "true"


def test_a_source_down_leaves_the_others(services):
    services.failing = {"commons.wikimedia.org"}
    assert [f.source for f in run(stock.search("Bastille"))] == ["openverse"]
    services.failing = {"commons.wikimedia.org", "api.openverse.org"}
    stock._cache.clear()
    with pytest.raises(AppError) as e:
        run(stock.search("Bastille"))
    assert e.value.code == "picture.search_failed"


def test_answers_kept_a_day(services):
    run(stock.search("Bastille"))
    asked = len(services.asked)
    run(stock.search("  Bastille "))
    searches = [r for r in services.asked[asked:] if r.url.path in ("/w/api.php", "/v1/images/")]
    assert searches == []  # the same subject: from the cache


def test_the_one_chosen_fetched_again_by_its_id(services):
    picture, origin = run(stock.fetch("commons", "File:Storming.jpg"))
    assert PILImage.open(io.BytesIO(picture)).size == (300, 300)  # card size (≤ 512)
    assert origin == PictureSource(
        source="commons", licence="CC0", page="https://commons.wikimedia.org/wiki/File:Storming.jpg", title="Storming"
    )
    lookup = services.asked[0]
    assert lookup.url.params["titles"] == "File:Storming.jpg" and lookup.url.params["iiurlwidth"] == "1024"
    assert services.asked[-1].url.host == "upload.wikimedia.org"

    _, origin = run(stock.fetch("openverse", "d32a3ea6-bbb6-4987-affb-e6a1198d07ac"))
    assert str(services.asked[-1].url).startswith("https://api.openverse.org/v1/images/d32a3ea6")
    assert (origin.licence, origin.page) == ("Public domain", "https://www.flickr.com/photos/x/1")
    _, origin = run(stock.fetch("pixabay", "42", pixabay_key="k"))
    assert services.asked[-1].url.host == "pixabay.com"
    assert (origin.licence, origin.title) == ("Pixabay", "fortress, paris")
    assert origin.page == "https://pixabay.com/photos/fortress-42/"
    with pytest.raises(AppError):  # mature on Openverse: never fetched
        run(stock.fetch("openverse", "93cbbfc8-a7d7-4a4d-b7af-ada48bb57f66"))


@pytest.mark.parametrize(
    ("source", "id_", "key"),
    [
        ("commons", "File:Someone's.jpg", ""),  # asks for credit
        ("commons", "File:Elsewhere.jpg", ""),  # a picture on another host
        ("openverse", "../../admin", ""),
        ("pixabay", "42", ""),  # no key: no Pixabay
        ("pixabay", "42/../x", "k"),
        ("flickr", "1", ""),
    ],
)
def test_nothing_else_fetched(services, source, id_, key):
    with pytest.raises(AppError) as e:
        run(stock.fetch(source, id_, pixabay_key=key))
    assert e.value.code == "picture.not_found"
    assert not any(r.url.host == "evil.example" for r in services.asked)


def test_found_on_the_computer(client, monkeypatch):
    async def search(subject, pixabay_key=""):
        assert pixabay_key == ""  # never on the computer
        return [stock.Found(source="commons", id="File:A.jpg", title="A", preview="data:,", licence="CC0")]

    async def fetch(source, id_, pixabay_key=""):
        assert (source, id_) == ("commons", "File:A.jpg")
        return jpeg(), PictureSource(
            source="commons", licence="CC0", page="https://commons.wikimedia.org/wiki/File:A.jpg"
        )

    monkeypatch.setattr(stock, "search", search)
    monkeypatch.setattr(stock, "fetch", fetch)
    res = client.post("/api/pictures/search", json={"subject": "a castle"})
    assert res.json()["results"][0]["id"] == "File:A.jpg"

    from conftest import extract_lesson

    lesson = extract_lesson(client)
    card = lesson["cards"][0]
    res = client.post(
        f"/api/lessons/{lesson['id']}/cards/{card['id']}/picture/found", json={"source": "commons", "id": "File:A.jpg"}
    )
    assert res.status_code == 201
    picture = res.json()["card"]["picture"]
    assert picture and client.get(f"/api/lessons/{lesson['id']}/pictures/{picture}").status_code == 200
    assert res.json()["card"]["picture_source"]["page"] == "https://commons.wikimedia.org/wiki/File:A.jpg"
    photo = client.post(
        f"/api/lessons/{lesson['id']}/cards/{card['id']}/picture", files={"photo": ("p.jpg", jpeg(), "image/jpeg")}
    )
    assert photo.json()["card"]["picture_source"] == {
        "source": "photo",
        "licence": "",
        "page": "",
        "title": "",
        "model": "",
    }
    gone = client.delete(f"/api/lessons/{lesson['id']}/cards/{card['id']}/picture")
    assert gone.json()["card"]["picture_source"] is None
    bad = client.post(f"/api/lessons/{lesson['id']}/cards/{card['id']}/picture/found", json={"source": "x", "id": "1"})
    assert bad.status_code == 422


# --- Found first, at generation (stock.find, pictures.picture) --------------------


def test_the_ai_picks_among_the_pictures_found(services, monkeypatch):
    seen = []

    async def pick(s, candidates, search, context):
        seen.append((len(candidates), search, context))
        return 1

    monkeypatch.setattr(llm, "pick_picture", pick)
    card = "14 juillet 1789 → prise de la Bastille"
    picture, origin = run(stock.find(AIConfig(llm="gemini"), "storming of the Bastille", card))
    assert origin.source == "commons" and origin.licence == "CC0"
    assert PILImage.open(io.BytesIO(picture)).size == (300, 300)
    assert seen == [(3, "storming of the Bastille", card)]
    assert services.asked[-1].url.host == "upload.wikimedia.org"  # the second one found: Commons' CC0 one

    async def none_fits(s, candidates, search, context):
        return None

    monkeypatch.setattr(llm, "pick_picture", none_fits)
    assert run(stock.find(AIConfig(llm="gemini"), "Bastille", "")) is None
    services.failing = {"commons.wikimedia.org", "api.openverse.org"}
    stock._cache.clear()
    assert run(stock.find(AIConfig(llm="gemini"), "Bastille", "")) is None  # nothing to be had: drawn instead


def test_found_first_drawn_otherwise(monkeypatch, tmp_path):
    monkeypatch.setattr(files, "_cache_root", lambda: tmp_path)  # restored after
    finds, draws = [], []

    async def find(s, query, context, pixabay_key=""):
        finds.append((query, context, pixabay_key))
        return None if query == "nothing" else (jpeg(100), PictureSource(source="commons", licence="CC0"))

    async def draw(s, subject):
        draws.append(subject)
        return jpeg(200)

    monkeypatch.setattr(stock, "find", find)
    monkeypatch.setattr(pictures, "draw", draw)
    s = AIConfig(llm="gemini")
    found = run(pictures.picture(s, "a dog sitting", search="dog", context="le chien → el perro", pixabay_key="k"))
    assert PILImage.open(io.BytesIO(found)).size == (100, 100) and draws == []
    assert finds == [("dog", "le chien → el perro", "k")]
    _, origin = run(pictures.sourced_picture(s, "a dog sitting", search="dog"))
    assert len(finds) == 1 and origin.source == "commons"  # kept, with where it came from: found once for every lesson
    _, origin = run(pictures.sourced_picture(s, "a cow"))
    assert origin.source == "drawn"  # by the image model (none set here)

    run(pictures.picture(s, "a cat", search="nothing"))  # none fits: drawn
    run(pictures.picture(s, "a dog sitting", fresh=True, search="dog"))  # "Draw" asked: drawn
    run(pictures.picture(s.model_copy(update={"picture_find": False}), "a bird", search="bird"))  # always drawn
    run(pictures.picture(s, "a happy face"))  # nothing to search for
    assert draws == ["a cow", "a cat", "a dog sitting", "a bird", "a happy face"]


def test_the_cards_say_what_to_search_for(client, monkeypatch):
    """The computer's pictures, after a generation: the card's picture_search and the card itself."""
    asked = []

    async def find(s, query, context, pixabay_key=""):
        asked.append((query, context, pixabay_key))
        return jpeg(), PictureSource(source="pixabay", licence="Pixabay", page="https://pixabay.com/photos/dog-1/")

    monkeypatch.setattr(stock, "find", find)
    lesson = client.post("/api/extract", data={"prompt": "Mots en images"}).json()
    cards = [{**c, "picture_prompt": "a dog", "picture_search": "dog"} for c in lesson["cards"][:1]]
    client.put(f"/api/lessons/{lesson['id']}", json={**lesson, "cards": cards})
    res = client.post(f"/api/lessons/{lesson['id']}/pictures").json()
    assert res["failures"] == 0 and res["lesson"]["cards"][0]["picture"]
    assert res["lesson"]["cards"][0]["picture_source"]["page"] == "https://pixabay.com/photos/dog-1/"
    card = cards[0]
    assert asked == [("dog", f"{card['front']} → {card['back']}", "")]  # no Pixabay on the computer


def test_the_ai_says_which_fits(monkeypatch):
    from test_dictation import HearingGemini

    for answer, expected in (('{"choice": 2}', 2), ('{"choice": -1}', None), ('{"choice": 9}', None)):
        fake = HearingGemini(answer)
        monkeypatch.setattr(gemini, "_gemini_client", lambda s, fake=fake: fake)
        previews = [llm.Image(jpeg(20), "image/jpeg")] * 3
        s = AIConfig(llm="gemini", model="gemini-3.5-flash", gemini_api_key="k")
        assert run(llm.pick_picture(s, previews, "dog", "le chien → el perro")) == expected
    contents, config = fake.calls[0]
    assert (
        len(contents) == 4
        and "The card: le chien → el perro" in contents[-1]
        and "that very thing" in config.system_instruction
    )
