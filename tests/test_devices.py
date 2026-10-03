"""The phones: pairing by the QR code's token, the cookie it becomes, unpairing,
the link the QR code carries, and the QR codes themselves."""

from conftest import ADMIN
from fastapi.testclient import TestClient

from app import settings
from app.main import DEVICE_COOKIE, app


def test_only_paired_devices_use_notosaurus(client):
    token = settings.device_token()
    client.cookies.clear()  # a phone that never scanned the QR code
    r = client.get("/api/lessons")
    assert (r.status_code, r.json()["detail"]["code"]) == (401, "device.not_paired")
    assert client.post("/api/extract", data={"prompt": "x"}).status_code == 401
    assert client.get("/api/lang").status_code == 200  # the page saying how to pair is translated
    # The settings have their own protection (password here): they give the QR code (Docker)
    assert client.get("/api/admin").status_code == 200
    assert client.get("/api/admin/phone").json()["detail"]["code"] == "admin.password_required"
    assert client.get("/").status_code == 200  # the page itself
    assert client.get("/?k=wrong").cookies.get(DEVICE_COOKIE) is None

    # The QR code's link: the phone keeps the token in a cookie, never sent by other sites
    r = client.get(f"/?k={token}")
    cookie = r.headers["set-cookie"].lower()
    assert "samesite=strict" in cookie and "httponly" in cookie and "max-age=34560000" in cookie
    assert client.get("/api/lessons").status_code == 200
    # Its home screen icon opens the page with the token (an iPhone icon has its own cookies)
    assert client.get("/manifest.json").json()["start_url"] == f"/?k={token}"

    # The computer itself needs no token; a request relayed by a proxy isn't the computer
    with TestClient(app, client=("127.0.0.1", 50000)) as local:
        assert local.get("/api/lessons").status_code == 200
        assert local.get("/manifest.json").json()["start_url"] == "/"
        assert local.get("/api/lessons", headers={"X-Forwarded-For": "100.64.0.7"}).status_code == 401


def test_unpair_every_phone(admin):
    with TestClient(app, client=("127.0.0.1", 50000)) as local:
        link = local.get("/api/admin/phone", headers=ADMIN).json()["url"]
        assert link.startswith("http://")
        old = settings.device_token()
        assert f"/?k={old}" in link
        new = local.post("/api/admin/phone/unpair", headers=ADMIN).json()["url"]
        assert old not in new and f"/?k={settings.device_token()}" in new
    assert admin.get("/api/lessons").status_code == 401  # the phone paired with the old token


def test_phone_link_address(client, monkeypatch):
    from app import main

    monkeypatch.setattr(main, "lan_address", lambda: "192.168.1.10")
    monkeypatch.setenv("NOTOSAURUS_EMBEDDED", "1")  # the add-on asks for it on the computer itself
    with TestClient(app, client=("127.0.0.1", 50000), base_url="http://127.0.0.1:8000") as local:
        token = settings.device_token()
        assert local.get("/api/admin/phone").json()["url"] == f"http://192.168.1.10:8000/?k={token}"
        monkeypatch.setenv("NOTOSAURUS_PUBLIC_URL", "https://pc.example.ts.net/")  # Docker, tailscale serve
        assert local.get("/api/admin/phone").json()["url"] == f"https://pc.example.ts.net/?k={token}"


def test_qr_code(client):
    res = client.get("/api/qr", params={"text": "http://192.168.1.20:8000/"})
    assert res.status_code == 200 and res.headers["content-type"] == "image/png"
    assert res.content.startswith(b"\x89PNG")
