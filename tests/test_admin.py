"""The settings: the admin password, the API keys (masked, never sent back), the
validation, the AI providers' model lists and connection test, the settings saved
by older versions, and who may open the settings at all."""

import json
import sys

import httpx
import pytest
from conftest import ADMIN
from fastapi.testclient import TestClient

from app import settings
from app.main import DEVICE_COOKIE, app


def test_admin_password_protected(admin):
    assert admin.get("/api/admin").json()["password_set"] is True
    assert admin.get("/api/admin/settings").status_code == 401
    assert admin.get("/api/admin/settings", headers={"X-Admin-Password": "faux"}).status_code == 401
    assert admin.get("/api/admin/settings", headers=ADMIN).status_code == 200
    # Once set, changing it requires the current password
    assert admin.post("/api/admin/password", json={"new": "pirate"}).status_code == 401
    assert admin.post("/api/admin/password", json={"current": "secret", "new": "nouveau"}).status_code == 204
    assert admin.get("/api/admin/settings", headers={"X-Admin-Password": "nouveau"}).status_code == 200


def test_admin_keys_never_sent_back(admin, monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaFROMENV0001")
    res = admin.put(
        "/api/admin/settings",
        headers=ADMIN,
        json={"llm": "anthropic", "model": "claude-sonnet-5", "anthropic_api_key": " sk-ant-SECRET9876 "},
    )
    assert res.status_code == 200
    view = res.json()
    assert view["anthropic_api_key"] == "•••• 9876"
    assert view["gemini_api_key"] == "•••• 0001"  # default from the environment
    assert "SECRET" not in res.text and "FROMENV" not in res.text

    s = settings.current()
    assert (s.llm, s.model, s.anthropic_api_key) == ("anthropic", "claude-sonnet-5", "sk-ant-SECRET9876")
    if sys.platform != "win32":  # Windows: no Unix permissions (the user profile protects the file)
        assert (tmp_path / "data" / "settings.json").stat().st_mode & 0o777 == 0o600

    # Omitted key: unchanged; empty string: cleared
    admin.put("/api/admin/settings", headers=ADMIN, json={"model": ""})
    assert settings.current().anthropic_api_key == "sk-ant-SECRET9876"
    admin.put("/api/admin/settings", headers=ADMIN, json={"anthropic_api_key": ""})
    assert settings.current().anthropic_api_key == ""


def test_admin_invalid_values(admin):
    assert admin.put("/api/admin/settings", headers=ADMIN, json={"llm": "skynet"}).status_code == 422
    assert admin.put("/api/admin/settings", headers=ADMIN, json={"tts_rate": "vite"}).status_code == 422
    assert admin.post("/api/admin/password", json={"current": "secret", "new": "abc"}).status_code == 422


def test_admin_connection_test(admin):
    res = admin.post("/api/admin/test", headers=ADMIN)
    assert res.status_code == 200
    assert (res.json()["vision"], res.json()["json"]) == (True, True)


def test_extraction_follows_settings(admin, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    admin.put("/api/admin/settings", headers=ADMIN, json={"llm": "gemini"})
    files = [("images", ("p.jpg", b"x", "image/jpeg"))]
    res = admin.post("/api/extract", files=files, data={"prompt": "x"})
    assert res.status_code == 502
    assert res.json()["detail"] == {"code": "llm.missing_key", "params": {"provider": "Gemini"}}


def test_addon_settings_only_on_the_computer(client, monkeypatch):
    """Add-on: settings only from the computer itself, without a password; never from a phone."""
    monkeypatch.setenv("NOTOSAURUS_EMBEDDED", "1")
    # From a phone on the Wi-Fi (TestClient's default address is not local)
    assert client.get("/api/admin").json() == {"password_set": False, "password_needed": False, "allowed": False}
    assert client.get("/api/admin/settings").status_code == 403
    assert client.get("/api/admin/settings").json()["detail"]["code"] == "admin.local_only"
    assert client.post("/api/admin/password", json={"new": "pirate"}).status_code == 403

    with TestClient(app, client=("127.0.0.1", 50000)) as local:
        assert local.get("/api/admin").json()["allowed"] is True
        assert local.get("/api/admin/settings").status_code == 200  # no password needed
        assert local.put("/api/admin/settings", json={"tts_rate": "+0%"}).status_code == 200
        # Relayed by a proxy (e.g. tailscale serve): comes from 127.0.0.1 but isn't local,
        # even from a paired phone
        local.cookies.set(DEVICE_COOKIE, settings.device_token())
        relayed = local.get("/api/admin/settings", headers={"X-Forwarded-For": "100.64.0.7"})
        assert relayed.status_code == 403
    assert settings.current().tts_rate == "+0%"


def test_standalone_password_from_the_phone(admin):
    """Standalone: settings from any device of the network, with the password."""
    assert admin.get("/api/admin").json() == {"password_set": True, "password_needed": True, "allowed": True}
    assert admin.get("/api/admin/settings", headers=ADMIN).status_code == 200


@pytest.mark.parametrize(
    ("saved", "expected"),
    [
        # One provider with a key per address (the settings before the split)
        (
            {
                "llm": "openai",
                "model": "gpt-6-luna",
                "openai_base_url": "https://api.openai.com/v1",
                "openai_keys": {"https://api.openai.com/v1": "sk-o", "https://openrouter.ai/api/v1/": "sk-r"},
            },
            {"llm": "openai", "openai_api_key": "sk-o", "openrouter_api_key": "sk-r", "model": "gpt-6-luna"},
        ),
        (
            {"llm": "openai", "openai_base_url": "https://openrouter.ai/api/v1", "openai_keys": {}},
            {"llm": "openrouter"},
        ),
        (
            {
                "llm": "openai",
                "openai_base_url": "http://localhost:11434/v1",
                "openai_keys": {"http://localhost:11434/v1": "ollama"},
            },
            {"llm": "compatible", "compatible_base_url": "http://localhost:11434/v1", "compatible_api_key": "ollama"},
        ),
        # Older still: one key, for the address saved with it
        (
            {"llm": "gemini", "openai_base_url": "https://openrouter.ai/api/v1", "openai_api_key": "sk-old"},
            {"llm": "gemini", "openrouter_api_key": "sk-old", "openai_api_key": ""},
        ),
    ],
)
def test_settings_saved_before_the_split(client, tmp_path, saved, expected):
    path = tmp_path / "data" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(saved))
    current = settings.current().model_dump()
    assert {k: current[k] for k in expected} == expected
    settings.save({"tts_rate": "+0%"})  # written in the new form
    written = json.loads(path.read_text(encoding="utf-8"))
    assert "openai_base_url" not in written and "openai_keys" not in written
    assert {k: settings.current().model_dump()[k] for k in expected} == expected


def test_env_before_the_split(client, monkeypatch):
    monkeypatch.setenv("NOTOSAURUS_LLM", "openai")
    monkeypatch.setenv("NOTOSAURUS_OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("NOTOSAURUS_OPENAI_API_KEY", "sk-env")
    s = settings.current()
    assert (s.llm, s.openrouter_api_key, s.base_url()) == ("openrouter", "sk-env", "https://openrouter.ai/api/v1")


# --- The AI services and their models ----------------------------------------


def listed(res) -> dict:
    """The model list's main fields (the short list is tested on its own)."""
    return {k: res.json()[k] for k in ("models", "vision_only")}


class FakeModel:
    def __init__(self, id, modalities=None, parameters=None, name=None):
        self.id = id
        self.model_extra = {"architecture": {"input_modalities": modalities}} if modalities else {}
        if name:
            self.model_extra["name"] = name
        if parameters is not None:
            self.model_extra["supported_parameters"] = parameters


def fake_openai(models, seen):
    class Models:
        def list(self):
            async def gen():
                for m in models:
                    yield m

            return gen()

    class Client:
        def __init__(self, base_url, api_key):
            seen.update(base_url=base_url, api_key=api_key)
            self.models = Models()

    return Client


class FakeMistralModel:
    def __init__(self, id, vision):
        self.id = id
        self.model_extra = {"capabilities": {"completion_chat": True, "vision": vision}}


def local_server(monkeypatch, routes):
    """httpx client answering like a local LM Studio / Ollama (routes: (method, path) → JSON)."""
    real = httpx.AsyncClient

    def handler(request):
        key = (request.method, request.url.path)
        if key not in routes:
            return httpx.Response(404)
        answer = routes[key]
        return httpx.Response(200, json=answer(json.loads(request.content)) if callable(answer) else answer)

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))


def test_service_models(admin, monkeypatch):
    import openai

    seen = {}
    admin.put(
        "/api/admin/settings",
        headers=ADMIN,
        json={"llm": "openrouter", "openrouter_api_key": "sk-or-1"},
    )

    # OpenRouter: models describe their inputs → only those accepting images
    monkeypatch.setattr(
        openai,
        "AsyncOpenAI",
        fake_openai(
            [
                FakeModel("openai/gpt-6-luna", ["text", "image"], ["tools", "structured_outputs"]),
                FakeModel("openai/gpt-6-luna:batch", ["text", "image"], ["structured_outputs"]),  # answers late
                FakeModel("some/text-only", ["text"], ["structured_outputs"]),
                FakeModel("anthropic/claude-sonnet-5", ["image", "text"], ["structured_outputs"]),
                FakeModel("vision/no-json", ["image", "text"], ["tools", "response_format"]),
            ],
            seen,
        ),
    )
    res = admin.post("/api/admin/models", headers=ADMIN)
    assert listed(res) == {"models": ["anthropic/claude-sonnet-5", "openai/gpt-6-luna"], "vision_only": True}
    assert seen == {"base_url": "https://openrouter.ai/api/v1", "api_key": "sk-or-1"}

    # OpenAI: no description → every model
    admin.put("/api/admin/settings", headers=ADMIN, json={"llm": "openai", "openai_api_key": "sk-openai-1"})
    monkeypatch.setattr(openai, "AsyncOpenAI", fake_openai([FakeModel("b"), FakeModel("a")], seen))
    assert listed(admin.post("/api/admin/models", headers=ADMIN)) == {"models": ["a", "b"], "vision_only": False}
    assert seen == {"base_url": "https://api.openai.com/v1", "api_key": "sk-openai-1"}
    assert admin.post("/api/admin/models").status_code == 401


def test_openai_compatible_without_model(admin):
    admin.put("/api/admin/settings", headers=ADMIN, json={"llm": "compatible", "model": ""})
    files = [("images", ("p.jpg", b"x", "image/jpeg"))]
    res = admin.post("/api/extract", files=files, data={"prompt": "x"})
    assert res.status_code == 502
    assert res.json()["detail"]["code"] == "llm.missing_model"


def test_openai_compatible_service_error(admin, monkeypatch):
    """The provider's own error code goes in the message, not in the HTTP status (regression)."""
    import openai

    request = httpx.Request("GET", "https://api.example.test/v1/models")

    class Failing:
        def __init__(self, base_url, api_key):
            self.models = self

        def list(self):
            async def gen():
                raise openai.InternalServerError("boom", response=httpx.Response(500, request=request), body=None)
                yield

            return gen()

    admin.put(
        "/api/admin/settings",
        headers=ADMIN,
        json={"llm": "compatible", "compatible_base_url": "https://api.example.test/v1"},
    )
    monkeypatch.setattr(openai, "AsyncOpenAI", Failing)
    res = admin.post("/api/admin/models", headers=ADMIN)
    assert res.status_code == 502
    assert res.json()["detail"] == {
        "code": "llm.api_error",
        "params": {"provider": "api.example.test", "status": 500, "detail": "boom"},
    }

    admin.put("/api/admin/settings", headers=ADMIN, json={"compatible_base_url": ""})
    assert admin.post("/api/admin/models", headers=ADMIN).json()["detail"]["code"] == "llm.missing_url"


def test_openai_openrouter_and_compatible_are_separate(admin):
    def put(body):
        return admin.put("/api/admin/settings", headers=ADMIN, json=body).json()

    view = put({"openai_api_key": "sk-openai-1111", "openrouter_api_key": "sk-or-2222", "compatible_api_key": "loc"})
    # Each its own key, masked for the page
    assert (view["openai_api_key"], view["openrouter_api_key"]) == ("•••• 1111", "•••• 2222")
    assert "sk-" not in json.dumps(view)
    for provider, url, key in [
        ("openai", "https://api.openai.com/v1", "sk-openai-1111"),
        ("openrouter", "https://openrouter.ai/api/v1", "sk-or-2222"),
    ]:
        put({"llm": provider})
        assert (settings.current().base_url(), settings.current().api_key()) == (url, key)
    put({"llm": "compatible", "compatible_base_url": "http://localhost:11434/v1"})
    assert (settings.current().base_url(), settings.current().api_key()) == ("http://localhost:11434/v1", "loc")
    assert admin.put("/api/admin/settings", headers=ADMIN, json={"compatible_base_url": "localhost"}).status_code == 422
    # Their default models
    assert view["default_models"]["openrouter"] == "google/gemini-3.8-flash"  # pinned, not "~…-latest"
    put({"llm": "openai", "openai_api_key": ""})  # cleared
    assert settings.current().api_key() == ""


def test_mistral_models(admin, monkeypatch):
    import openai

    admin.put(
        "/api/admin/settings",
        headers=ADMIN,
        json={"llm": "compatible", "compatible_base_url": "https://api.mistral.ai/v1"},
    )
    monkeypatch.setattr(
        openai,
        "AsyncOpenAI",
        fake_openai([FakeMistralModel("mistral-medium-3-5", True), FakeMistralModel("codestral", False)], {}),
    )
    assert listed(admin.post("/api/admin/models", headers=ADMIN)) == {
        "models": ["mistral-medium-3-5"],
        "vision_only": True,
    }


def test_lm_studio_models(admin, monkeypatch):
    import openai

    admin.put(
        "/api/admin/settings",
        headers=ADMIN,
        json={"llm": "compatible", "compatible_base_url": "http://localhost:1234/v1"},
    )
    monkeypatch.setattr(openai, "AsyncOpenAI", fake_openai([FakeModel("google/gemma-4"), FakeModel("qwen/qwen3")], {}))
    local_server(
        monkeypatch,
        {
            ("GET", "/api/v1/models"): {
                "models": [
                    {"type": "llm", "key": "google/gemma-4", "capabilities": {"vision": True}},
                    {"type": "llm", "key": "qwen/qwen3", "capabilities": {"vision": False}},
                    {"type": "embedding", "key": "nomic-embed"},
                ]
            }
        },
    )
    assert listed(admin.post("/api/admin/models", headers=ADMIN)) == {"models": ["google/gemma-4"], "vision_only": True}


def test_ollama_models(admin, monkeypatch):
    import openai

    admin.put(
        "/api/admin/settings",
        headers=ADMIN,
        json={"llm": "compatible", "compatible_base_url": "http://localhost:11434/v1"},
    )
    monkeypatch.setattr(openai, "AsyncOpenAI", fake_openai([FakeModel("qwen2.5vl:7b"), FakeModel("llama3:8b")], {}))
    capabilities = {"qwen2.5vl:7b": ["completion", "vision"], "llama3:8b": ["completion"]}
    local_server(
        monkeypatch,
        {
            ("GET", "/api/tags"): {"models": [{"name": "qwen2.5vl:7b"}, {"name": "llama3:8b"}]},
            ("POST", "/api/show"): lambda body: {"capabilities": capabilities[body["model"]]},
        },
    )
    assert listed(admin.post("/api/admin/models", headers=ADMIN)) == {"models": ["qwen2.5vl:7b"], "vision_only": True}


def test_test_image_and_json(admin, monkeypatch):
    """The admin test tells whether the model reads the image and answers in JSON."""
    from app import llm

    admin.put("/api/admin/settings", headers=ADMIN, json={"llm": "gemini", "gemini_api_key": "k"})

    def test():
        return admin.post("/api/admin/test", headers=ADMIN)

    async def answer(color):
        return llm._CheckAnswer(color=color)

    monkeypatch.setattr(llm, "_generate", lambda s, images, text, schema: answer("Red"))
    assert (test().json()["vision"], test().json()["json"]) == (True, True)

    monkeypatch.setattr(llm, "_generate", lambda s, images, text, schema: answer("I see no image"))
    assert (test().json()["vision"], test().json()["json"]) == (False, True)

    async def not_json(*_):
        raise llm.ExtractionError("llm.invalid_answer")

    monkeypatch.setattr(llm, "_generate", not_json)
    assert test().json()["json"] is False

    async def bad_key(*_):
        raise llm.ExtractionError("llm.invalid_key", provider="Gemini")

    monkeypatch.setattr(llm, "_generate", bad_key)
    assert test().status_code == 502 and test().json()["detail"]["code"] == "llm.invalid_key"


def test_model_without_vision_refuses_image(admin, monkeypatch):
    """Ollama refuses an image for a text-only model with a 400: the test says so plainly."""
    from app import llm

    admin.put("/api/admin/settings", headers=ADMIN, json={"llm": "gemini", "gemini_api_key": "k"})

    async def refuse(*_):
        raise llm.ExtractionError(
            "llm.api_error",
            provider="localhost:11434",
            status=400,
            detail="Multimodal data provided, but model does not support multimodal requests.",
        )

    monkeypatch.setattr(llm, "_generate", refuse)
    r = admin.post("/api/admin/test", headers=ADMIN).json()
    assert (r["vision"], r["json"]) == (False, None)
    assert "multimodal" in r["refused"]

    nested = {"message": '{"error":{"code":400,"message":"no vision here","type":"x"}}'}
    assert llm._error_message(nested) == "no vision here"


def test_recommended_models_first_is_the_default(admin):
    """The recommended models (app/recommended.py), in order, for every service that
    has some: the first one is its default, for the cards and for the pictures."""
    from app import pictures, recommended

    view = admin.get("/api/admin/settings", headers=ADMIN).json()
    for provider in ("gemini", "anthropic", "openai", "openrouter"):
        listed = [m["id"] for m in view["recommended"]["cards"][provider]]
        assert listed[0] == view["default_models"][provider] == settings.DEFAULT_MODELS[provider]
        assert not any(m.startswith("~") for m in listed)  # pinned versions: what was tested runs
    for service in ("gemini", "openai", "openrouter"):
        assert view["recommended"]["pictures"][service][0]["id"] == pictures.DEFAULT_MODELS[service]
    assert view["recommended"]["cards"]["gemini"][1] == {
        "id": "gemini-3.5-flash",
        "name": "Gemini 3.5 Flash",
        "cents": 3.8,
        "note": "freeKey",
    }
    assert "compatible" not in view["recommended"]["cards"]  # a local service: its own models
    assert recommended.default(recommended.CARDS, "compatible") == ""


def test_configured_once_the_service_has_its_key(admin, monkeypatch):
    """Until the cards' AI has its key (or address), the setup assistant is offered."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert admin.get("/api/config").json()["configured"] is True  # the demo AI needs nothing
    admin.put("/api/admin/settings", headers=ADMIN, json={"llm": "gemini"})
    assert admin.get("/api/config").json()["configured"] is False
    admin.put("/api/admin/settings", headers=ADMIN, json={"gemini_api_key": "AIza-test"})
    assert admin.get("/api/config").json()["configured"] is True
    admin.put("/api/admin/settings", headers=ADMIN, json={"llm": "compatible"})
    assert admin.get("/api/config").json()["configured"] is False  # its address first
    admin.put("/api/admin/settings", headers=ADMIN, json={"compatible_base_url": "http://localhost:11434/v1"})
    assert admin.get("/api/config").json()["configured"] is True
