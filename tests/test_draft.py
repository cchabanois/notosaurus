"""The lesson in progress, kept by the computer (app/draft.py, /api/draft)."""

import json

from app.routes.common import MAX_IMAGES


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
    many = [("photos", (f"p{n}.jpg", b"x", "image/jpeg")) for n in range(MAX_IMAGES + 1)]
    refused = client.put("/api/draft", data={"draft": "{}", "photos_sent": "true"}, files=many)
    assert (refused.status_code, refused.json()["detail"]["code"]) == (413, "draft.too_large")
    assert client.get("/api/draft").json() == {}
