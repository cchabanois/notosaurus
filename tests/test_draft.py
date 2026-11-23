"""The lesson in progress, kept by the computer (app/draft.py, /api/draft)."""

import json

from starlette.datastructures import UploadFile

from app.draft import MAX_PHOTO_BYTES
from app.routes.common import MAX_PAGES


def test_kept_found_again_cleared(client):
    assert client.get("/api/draft").json() == {}
    draft = {"lesson": None, "prompt": {"selected": None, "chosen": True, "form": {"text": "Une carte par capitale"}}}
    photos = [("photos", ("p1.jpg", b"one", "image/jpeg")), ("photos", ("p2.jpg", b"two", "image/jpeg"))]
    sent = client.put("/api/draft", data={"draft": json.dumps(draft), "photos_sent": "true"}, files=photos)
    assert sent.status_code == 200
    assert client.get("/api/draft").json() == {**draft, "photos": 2}
    assert client.get("/api/draft/photos/2").content == b"two"
    # The prompt changed alone: the photos kept
    draft["prompt"]["form"]["text"] = "Une carte par fleuve"
    client.put("/api/draft", data={"draft": json.dumps(draft)})
    assert client.get("/api/draft").json()["photos"] == 2
    # Made: the lesson open, no photo kept
    client.put("/api/draft", data={"draft": json.dumps({"lesson": "abc"}), "photos_sent": "true"})
    assert client.get("/api/draft").json() == {"lesson": "abc", "photos": 0}
    assert client.get("/api/draft/photos/1").status_code == 404
    assert client.delete("/api/draft").status_code == 200
    assert client.get("/api/draft").json() == {}


def test_what_isnt_a_draft_refused(client):
    assert client.put("/api/draft", data={"draft": "not json"}).json()["detail"]["code"] == "draft.invalid"
    assert client.put("/api/draft", data={"draft": "[1]"}).json()["detail"]["code"] == "draft.invalid"
    many = [("photos", (f"p{n}.jpg", b"x", "image/jpeg")) for n in range(MAX_PAGES + 1)]
    refused = client.put("/api/draft", data={"draft": "{}", "photos_sent": "true"}, files=many)
    assert (refused.status_code, refused.json()["detail"]["code"]) == (413, "draft.too_large")
    assert client.get("/api/draft").json() == {}


def _reads(monkeypatch) -> list[int]:
    """The bytes each read of an uploaded photo returned (Starlette makes them, FastAPI's type its subclass)."""
    read = UploadFile.read
    returned: list[int] = []

    async def counted(self, size: int = -1) -> bytes:
        data = await read(self, size)
        returned.append(len(data))
        return data

    monkeypatch.setattr(UploadFile, "read", counted)
    return returned


def test_too_many_photos_refused_before_any_is_read(client, monkeypatch):
    reads = _reads(monkeypatch)
    many = [("photos", (f"p{n}.jpg", b"x", "image/jpeg")) for n in range(MAX_PAGES + 1)]
    refused = client.put("/api/draft", data={"draft": "{}", "photos_sent": "true"}, files=many)
    assert (refused.status_code, refused.json()["detail"]["code"]) == (413, "draft.too_large")
    assert reads == []
    assert client.get("/api/draft").json() == {}


def test_a_photo_too_heavy_read_no_further_than_its_cap(client, monkeypatch):
    reads = _reads(monkeypatch)
    heavy = [("photos", ("p1.jpg", b"x" * (MAX_PHOTO_BYTES + 1024 * 1024), "image/jpeg"))]
    refused = client.put("/api/draft", data={"draft": "{}", "photos_sent": "true"}, files=heavy)
    assert (refused.status_code, refused.json()["detail"]["code"]) == (413, "draft.too_large")
    assert sum(reads) <= MAX_PHOTO_BYTES + 64 * 1024
    assert client.get("/api/draft").json() == {}


def test_as_many_photos_as_a_lesson_has_kept(client):
    photos = [("photos", (f"p{n}.jpg", f"photo {n}".encode(), "image/jpeg")) for n in range(1, MAX_PAGES + 1)]
    sent = client.put("/api/draft", data={"draft": "{}", "photos_sent": "true"}, files=photos)
    assert sent.status_code == 200
    assert client.get("/api/draft").json() == {"photos": MAX_PAGES}
    assert client.get(f"/api/draft/photos/{MAX_PAGES}").content == f"photo {MAX_PAGES}".encode()
