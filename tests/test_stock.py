"""Free pictures found for a card (stock): the licences kept, what pupils mustn't see
left out, the sources taking turns, nothing fetched from an address the client gives."""

import io

import httpx
import pytest
from helpers import HearingGemini, bomb_png, plain_image, run
from PIL import Image as PILImage

from notosaurus_core import files, llm, pictures, stock
from notosaurus_core.config import AIConfig
from notosaurus_core.errors import AppError
from notosaurus_core.models import PictureSource
from notosaurus_core.providers import gemini


def jpeg(side=300) -> bytes:
    return plain_image(side, side, "teal")


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


class Redirecting(Services):
    """Commons' picture host answering every picture with a redirect to `to`."""

    def __init__(self, to):
        super().__init__()
        self.to = to

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "upload.wikimedia.org" and request.url.path.startswith("/thumb/"):
            self.asked.append(request)
            return httpx.Response(302, headers={"Location": self.to})
        return super().__call__(request)  # anywhere else, the redirect's target too: a picture


REDIRECTS = [
    "https://evil.example/x.jpg",  # another host
    "https://upload.wikimedia.org/elsewhere.jpg",  # an allowed host: never followed either
    "http://upload.wikimedia.org/thumb/1.jpg",  # plain http
    "http://127.0.0.1:8000/api/admin/settings",  # the computer itself (SSRF)
]


@pytest.mark.parametrize("to", REDIRECTS)
def test_a_redirect_from_an_allowed_host_never_followed(monkeypatch, to):
    redirecting = Redirecting(to)
    monkeypatch.setattr(stock, "_transport", httpx.MockTransport(redirecting))
    stock._cache.clear()

    async def download():
        async with stock._client() as client:
            return await stock._download(client, "commons", "https://upload.wikimedia.org/thumb/1.jpg")

    with pytest.raises(AppError) as e:
        run(download())
    assert e.value.code == "picture.search_failed"
    with pytest.raises(AppError):  # the one chosen
        run(stock.fetch("commons", "File:Storming.jpg"))
    found = run(stock.search("Bastille"))  # the previews: Commons' are left out, Openverse's kept
    assert [f.source for f in found] == ["openverse"]
    assert redirecting.asked and not any(str(r.url) == to for r in redirecting.asked)
    assert not any(r.url.host in ("evil.example", "127.0.0.1") for r in redirecting.asked)


@pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning")
def test_a_decompression_bomb_found_is_left_out(monkeypatch):
    def bombs(request: httpx.Request) -> httpx.Response:
        if request.url.host == "upload.wikimedia.org":
            return httpx.Response(200, content=bomb_png())
        return Services()(request)

    monkeypatch.setattr(stock, "_transport", httpx.MockTransport(bombs))
    stock._cache.clear()
    assert [f.source for f in run(stock.search("Bastille"))] == ["openverse"]  # no preview: not offered
    with pytest.raises(AppError) as e:
        run(stock.fetch("commons", "File:Storming.jpg"))
    assert e.value.code == "relay.bad_image"


def test_found_on_the_computer(client, monkeypatch):
    async def search(subject, pixabay_key="", *_):
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


# --- Searched for by the user, sorted by the AI (stock.sorted_search) ---------------


def test_the_ai_keeps_only_the_pictures_that_fit(services, monkeypatch):
    seen = []

    async def sort(s, candidates, search, context=""):
        seen.append((len(candidates), search, context))
        return [2, 0]  # the third first; the second left out

    monkeypatch.setattr(llm, "sort_pictures", sort)
    found = run(stock.sorted_search(AIConfig(llm="gemini"), "Bastille", "14 juillet 1789 → prise de la Bastille"))
    assert [f.id for f in found] == ["File:Prise de la Bastille.jpg", "d32a3ea6-bbb6-4987-affb-e6a1198d07ac"]
    assert seen == [(3, "Bastille", "14 juillet 1789 → prise de la Bastille")]  # every one found, seen


def test_more_looked_for_when_sorted(monkeypatch):
    asked = []

    async def search(subject, pixabay_key="", per_source=stock.PER_SOURCE, most=stock.MAX_RESULTS):
        asked.append((per_source, most))
        return [
            stock.Found(source="commons", id=str(i), title="", preview="data:,", licence="CC0") for i in range(most)
        ]

    async def sort(s, candidates, search, context=""):
        return list(range(len(candidates)))

    monkeypatch.setattr(stock, "search", search)
    monkeypatch.setattr(llm, "sort_pictures", sort)
    found = run(stock.sorted_search(AIConfig(llm="gemini"), "dog"))
    assert asked == [(stock.SORT_PER_SOURCE, stock.SORT_PER_SOURCE * 3)] and len(found) == stock.MAX_RESULTS


def test_unsorted_when_the_ai_cant(services, monkeypatch, caplog):
    async def sort(s, candidates, search, context=""):
        raise AppError("llm.no_key", detail=f"nothing for {search}")

    monkeypatch.setattr(llm, "sort_pictures", sort)
    with caplog.at_level("WARNING", logger="notosaurus"):
        found = run(stock.sorted_search(AIConfig(llm="gemini"), "Bastille"))
    assert [f.source for f in found] == ["openverse", "commons", "commons"]  # as they came
    assert not any("Bastille" in r.getMessage() for r in caplog.records)


def test_none_that_fits_none_offered(services, monkeypatch):
    async def sort(s, candidates, search, context=""):
        return []

    monkeypatch.setattr(llm, "sort_pictures", sort)
    assert run(stock.sorted_search(AIConfig(llm="gemini"), "Bastille")) == []


def test_sorting_keeps_the_indexes_that_exist_once(monkeypatch):
    from notosaurus_core.models import Sorted

    async def ask(s, images, text, schema, rules, **_):
        assert schema is Sorted and "The card:" not in text  # no card: not said
        return Sorted(fitting=[1, 5, -1, 1, 0])

    monkeypatch.setattr(llm, "_ask_provider", ask)
    assert run(llm.sort_pictures(AIConfig(llm="gemini"), [llm.Image(jpeg(), "image/jpeg")] * 3, "dog")) == [1, 0]


def test_the_cards_search_words_used_as_they_are(client, monkeypatch):
    async def words(*_):
        raise AssertionError("not asked again")

    async def sorted_search(s, subject, context="", pixabay_key=""):
        assert subject == "Bastille fortress"
        return []

    monkeypatch.setattr(llm, "search_words", words)
    monkeypatch.setattr(stock, "sorted_search", sorted_search)
    res = client.post("/api/pictures/search", json={"subject": "La Bastille prise", "words": "Bastille fortress"})
    assert res.json() == {"results": [], "words": "Bastille fortress"}


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


def test_a_failing_search_logs_nothing_of_the_lesson(monkeypatch, caplog):
    """The relay's logs hold nothing of a lesson: neither the query nor an error quoting it."""
    subject = "storming of the Bastille"

    async def search(query, pixabay_key=""):
        raise AppError("picture.api_error", status=503, detail=f"nothing for {query}")

    monkeypatch.setattr(stock, "search", search)
    with caplog.at_level("WARNING", logger="notosaurus"):
        assert run(stock.find(AIConfig(llm="gemini"), subject, "14 juillet 1789 → prise de la Bastille")) is None
    assert caplog.records and "picture.api_error (503)" in caplog.text
    assert not any("Bastille" in r.getMessage() for r in caplog.records)
