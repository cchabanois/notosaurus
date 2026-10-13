"""Drawing a picture with each image service (OpenRouter, Gemini, OpenAI): the request
sent, the image read from the answer, its cost recorded, the service's errors as the
app's codes. The services are faked (an httpx MockTransport under the OpenAI SDK, a
fake google-genai client): never the network."""

import base64
import json
import types as py_types

import httpx
import openai
import pytest
from google import genai
from google.genai import errors, types
from helpers import plain_image, run

from notosaurus_core import files, llm, pictures
from notosaurus_core.config import AIConfig
from notosaurus_core.models import Card, PicturePlan

PNG = plain_image(64, 64, "red", "PNG")


@pytest.fixture
def recorded(monkeypatch):
    """The calls noted for the costs: (provider, model, input, output, cost)."""
    calls = []

    async def record(s, provider, model, input_tokens, output_tokens, cost=None):
        calls.append((provider, model, input_tokens, output_tokens, cost))

    monkeypatch.setattr(llm, "record", record)
    return calls


@pytest.fixture
def openai_api(monkeypatch):
    """OpenAI's SDK (OpenAI and OpenRouter) answering through `answer(request)`; it keeps
    the clients' options and the requests sent."""
    fake = py_types.SimpleNamespace(clients=[], requests=[], answer=None)
    real = openai.AsyncOpenAI

    def handle(request):
        fake.requests.append(request)
        return fake.answer(request)

    def client(**options):
        fake.clients.append(options)
        transport = httpx.MockTransport(handle)
        return real(**options, http_client=httpx.AsyncClient(transport=transport), max_retries=0)

    monkeypatch.setattr(openai, "AsyncOpenAI", client)
    return fake


class FakeGemini:
    """google-genai's client: answers `response` (or raises it), lists `models`; keeps
    its options and what it was sent."""

    def __init__(self, response=None, models=()):
        self.response, self.models, self.options, self.calls = response, models, None, []
        self.aio = py_types.SimpleNamespace(
            models=py_types.SimpleNamespace(generate_content=self.generate, list=self.list)
        )

    def __call__(self, **options):  # genai.Client(...)
        self.options = options
        return self

    async def generate(self, model, contents, config):
        self.calls.append((model, contents, config))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    async def list(self):
        async def pager():
            for m in self.models:
                yield m

        return pager()


def gemini_answer(*parts, finish_reason="STOP", usage=True):
    usage_metadata = types.GenerateContentResponseUsageMetadata(prompt_token_count=20, candidates_token_count=1290)
    content = types.Content(role="model", parts=list(parts)) if parts else None
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=content, finish_reason=finish_reason)],
        usage_metadata=usage_metadata if usage else None,
    )


def picture_error(coroutine) -> pictures.PictureError:
    with pytest.raises(pictures.PictureError) as raised:
        run(coroutine)
    return raised.value


def test_draw_through_the_service_set(openai_api, recorded, monkeypatch):
    """`draw` sends the drawing style with the subject to the drawing service; none ready: no model."""
    fake = FakeGemini(gemini_answer(types.Part.from_bytes(data=PNG, mime_type="image/png")))
    monkeypatch.setattr(genai, "Client", fake)
    openai_api.answer = lambda request: httpx.Response(
        200, json={"data": [{"b64_json": base64.b64encode(PNG).decode()}]}
    )

    assert run(pictures.draw(AIConfig(llm="gemini", gemini_api_key="g"), "  a dog ")) == PNG
    assert fake.calls[0][1] == pictures.STYLE.format(subject="a dog")
    assert run(pictures.draw(AIConfig(llm="anthropic", openai_api_key="o"), "a cat")) == PNG  # Claude can't draw
    assert openai_api.requests[0].url.path == "/v1/images/generations"

    assert picture_error(pictures.draw(AIConfig(llm="anthropic"), "a dog")).code == "picture.no_model"
    chosen = AIConfig(llm="gemini", gemini_api_key="g", picture_service="openrouter")  # without its key
    assert picture_error(pictures.draw(chosen, "a dog")).code == "picture.no_model"
    assert len(fake.calls) == 1 and len(openai_api.requests) == 1  # nothing sent


def test_openrouter_draws_in_a_chat_answer(openai_api, recorded):
    """OpenRouter: a chat completion asking for an image, read from the message's data URL;
    the cost OpenRouter states is the one kept."""
    url = "data:image/png;base64," + base64.b64encode(PNG).decode()
    message = {"role": "assistant", "content": "", "images": [{"type": "image_url", "image_url": {"url": url}}]}
    openai_api.answer = lambda request: httpx.Response(
        200,
        json={
            "id": "gen-1",
            "object": "chat.completion",
            "created": 0,
            "model": "google/gemini-3.1-flash-lite-image",
            "choices": [{"index": 0, "finish_reason": "stop", "message": message}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 1300, "total_tokens": 1320, "cost": 0.03},
        },
    )
    s = AIConfig(llm="openrouter", openrouter_api_key="sk-or", picture_model="google/gemini-3.1-flash-lite-image")
    assert run(pictures.draw(s, "an apple")) == PNG

    assert openai_api.clients == [{"base_url": pictures.OPENROUTER, "api_key": "sk-or"}]
    request = openai_api.requests[0]
    assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
    body = json.loads(request.content)
    assert body["model"] == "google/gemini-3.1-flash-lite-image"
    assert body["messages"] == [{"role": "user", "content": pictures.STYLE.format(subject="an apple")}]
    assert body["modalities"] == ["image", "text"] and body["usage"] == {"include": True}
    assert recorded == [("openrouter.ai", "google/gemini-3.1-flash-lite-image", 20, 1300, 0.03)]


def test_openrouter_errors(openai_api, recorded):
    """No image in the answer: empty (still paid for: recorded); out of credit: quota; else failed."""
    s = AIConfig(llm="openrouter", openrouter_api_key="sk-or")
    text_only = {"role": "assistant", "content": "I can't draw that."}
    openai_api.answer = lambda request: httpx.Response(
        200,
        json={
            "id": "gen-1",
            "object": "chat.completion",
            "created": 0,
            "model": "m",
            "choices": [{"index": 0, "finish_reason": "stop", "message": text_only}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28, "cost": 0.0001},
        },
    )
    assert picture_error(pictures.draw(s, "a dog")).code == "picture.empty"
    assert len(recorded) == 1

    openai_api.answer = lambda request: httpx.Response(429, json={"error": {"message": "Rate limited"}})
    error = picture_error(pictures.draw(s, "a dog"))
    assert (error.code, error.params) == ("picture.quota", {"service": "OpenRouter"})

    openai_api.answer = lambda request: httpx.Response(400, json={"error": {"message": "No such model"}})
    error = picture_error(pictures.draw(s, "a dog"))
    assert error.code == "picture.failed" and "No such model" in error.params["detail"]
    assert len(error.params["detail"]) <= 200
    assert len(recorded) == 1  # the refused calls: nothing to pay

    assert picture_error(pictures._openrouter(AIConfig(), "m", "p")).params == {"service": "OpenRouter"}


def test_openrouter_answers_without_an_image(openai_api, recorded):
    """No choice, an image that isn't a data URL, or not base64: that card has no picture
    (picture.empty), never a crash that would stop the lesson's other pictures."""
    s = AIConfig(llm="openrouter", openrouter_api_key="sk-or")

    def answer(choices):
        return lambda request: httpx.Response(
            200,
            json={"id": "gen-1", "object": "chat.completion", "created": 0, "model": "m", "choices": choices},
        )

    def with_image(url):
        message = {"role": "assistant", "content": "", "images": [{"type": "image_url", "image_url": {"url": url}}]}
        return [{"index": 0, "finish_reason": "stop", "message": message}]

    for choices in ([], with_image("https://example.com/dog.png"), with_image("data:image/png;base64,%%%")):
        openai_api.answer = answer(choices)
        assert picture_error(pictures.draw(s, "a dog")).code == "picture.empty"


def test_gemini_draws_inline(recorded, monkeypatch):
    """Gemini: an image and text asked for, with the app's safety filters; the image is the
    first inline part (after any text); the tokens recorded, the cost estimated later."""
    fake = FakeGemini(
        gemini_answer(types.Part(text="Here it is"), types.Part.from_bytes(data=PNG, mime_type="image/png"))
    )
    monkeypatch.setattr(genai, "Client", fake)
    s = AIConfig(llm="gemini", gemini_api_key="g")
    assert run(pictures.draw(s, "an apple")) == PNG

    assert fake.options == {"api_key": "g"}
    model, contents, config = fake.calls[0]
    assert model == "gemini-3.1-flash-lite-image" and contents == pictures.STYLE.format(subject="an apple")
    assert config.response_modalities == ["IMAGE", "TEXT"] and config.safety_settings
    assert recorded == [("gemini", "gemini-3.1-flash-lite-image", 20, 1290, None)]

    # Through Vertex AI (a project, no key): the same
    vertex = AIConfig(llm="gemini", gemini_vertex_project="p", gemini_vertex_location="europe-west1")
    assert run(pictures.draw(vertex, "an apple")) == PNG
    assert fake.options == {"vertexai": True, "project": "p", "location": "europe-west1"}


def test_gemini_errors(recorded, monkeypatch):
    """Gemini: a refusal (its safety filters, or only text) is "no picture", not a crash;
    429 is the quota; another error fails with its code and message."""
    fake = FakeGemini()
    monkeypatch.setattr(genai, "Client", fake)
    s = AIConfig(llm="gemini", gemini_api_key="g")

    fake.response = gemini_answer(finish_reason="IMAGE_SAFETY")  # no content at all
    assert picture_error(pictures.draw(s, "a dog")).code == "picture.empty"
    fake.response = gemini_answer(types.Part(text="I can't draw that."))
    assert picture_error(pictures.draw(s, "a dog")).code == "picture.empty"
    fake.response = types.GenerateContentResponse(candidates=[], usage_metadata=None)  # the prompt refused
    assert picture_error(pictures.draw(s, "a dog")).code == "picture.empty"
    assert len(recorded) == 2  # the answered ones with their tokens

    fake.response = errors.APIError(429, {"error": {"message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}})
    error = picture_error(pictures.draw(s, "a dog"))
    assert (error.code, error.params) == ("picture.quota", {"service": "Gemini"})
    fake.response = errors.APIError(400, {"error": {"message": "Bad model", "status": "INVALID_ARGUMENT"}})
    error = picture_error(pictures.draw(s, "a dog"))
    assert (error.code, error.params) == ("picture.failed", {"detail": "400 Bad model"})

    assert picture_error(pictures._gemini(AIConfig(), "m", "p")).params == {"service": "Gemini"}


def test_openai_draws_with_its_images_api(openai_api, recorded):
    """OpenAI: its images API, a square at low quality (cheap, enough for a card), read
    from base64; the tokens recorded."""
    openai_api.answer = lambda request: httpx.Response(
        200,
        json={
            "created": 0,
            "data": [{"b64_json": base64.b64encode(PNG).decode()}],
            "usage": {"input_tokens": 30, "output_tokens": 272, "total_tokens": 302},
        },
    )
    s = AIConfig(llm="openai", openai_api_key="sk")
    assert run(pictures.draw(s, "an apple")) == PNG

    assert openai_api.clients == [{"api_key": "sk"}]
    request = openai_api.requests[0]
    assert str(request.url) == "https://api.openai.com/v1/images/generations"
    assert json.loads(request.content) == {
        "model": "gpt-image-2",
        "prompt": pictures.STYLE.format(subject="an apple"),
        "size": "1024x1024",
        "quality": "low",
    }
    assert recorded == [("openai", "gpt-image-2", 30, 272, None)]

    openai_api.answer = lambda request: httpx.Response(400, json={"error": {"message": "Your request was rejected"}})
    error = picture_error(pictures.draw(s, "a dog"))
    assert error.code == "picture.failed" and "rejected" in error.params["detail"]
    assert picture_error(pictures._openai(AIConfig(), "m", "p")).params == {"service": "OpenAI"}

    # No image, or a link instead of it: picture.empty, not a crash
    for data in ([], [{"url": "https://example.com/dog.png"}]):
        openai_api.answer = lambda request, data=data: httpx.Response(200, json={"created": 0, "data": data})
        assert picture_error(pictures.draw(s, "a dog")).code == "picture.empty"


def test_image_models_listed_by_each_service(openai_api, monkeypatch):
    """The models each service lists, read from its own answer and kept when they draw."""
    models = {
        "/api/v1/models": [
            {"id": "openai/gpt-5.4-image-2", "architecture": {"output_modalities": ["image", "text"]}},
            {"id": "google/gemini-3.8-flash", "architecture": {"output_modalities": ["text"]}},
            {"id": "some/model-without-architecture"},
        ],
        "/v1/models": [{"id": "gpt-image-2"}, {"id": "dall-e-3"}],
    }
    openai_api.answer = lambda request: httpx.Response(
        200, json={"object": "list", "data": [{"object": "model", **m} for m in models[request.url.path]]}
    )
    assert run(pictures.image_models(AIConfig(llm="openrouter", openrouter_api_key="r"))) == ["openai/gpt-5.4-image-2"]
    assert run(pictures.image_models(AIConfig(llm="openai", openai_api_key="o"))) == ["gpt-image-2"]
    assert openai_api.clients == [{"api_key": "r", "base_url": pictures.OPENROUTER}, {"api_key": "o"}]

    listed = [
        py_types.SimpleNamespace(name="models/gemini-3.1-flash-lite-image", supported_actions=["generateContent"]),
        py_types.SimpleNamespace(name="models/imagen-5.0-generate", supported_actions=["predict"]),
        # Vertex AI: a longer name and no actions said
        py_types.SimpleNamespace(name="publishers/google/models/gemini-3.1-flash-image", supported_actions=None),
    ]
    monkeypatch.setattr(genai, "Client", FakeGemini(models=listed))
    assert run(pictures.image_models(AIConfig(llm="gemini", gemini_api_key="g"))) == ["gemini-3.1-flash-lite-image"]
    vertex = AIConfig(llm="gemini", gemini_vertex_project="p")
    assert run(pictures.image_models(vertex)) == ["gemini-3.1-flash-image", "gemini-3.1-flash-lite-image"]


def test_image_models_errors(openai_api, monkeypatch):
    """No drawing service: no model; the service's own error: failed, with its message; a
    PictureError raised while listing goes through as it is."""
    assert picture_error(pictures.image_models(AIConfig(llm="anthropic"))).code == "picture.no_model"

    openai_api.answer = lambda request: httpx.Response(401, json={"error": {"message": "Incorrect API key"}})
    error = picture_error(pictures.image_models(AIConfig(llm="openai", openai_api_key="bad")))
    assert error.code == "picture.failed" and "Incorrect API key" in error.params["detail"]

    async def fetch(s, drawing):
        raise pictures.PictureError("picture.quota", service="OpenAI")

    monkeypatch.setattr(pictures, "_fetch_models", fetch)
    assert picture_error(pictures.image_models(AIConfig(llm="openai", openai_api_key="o"))).code == "picture.quota"


def test_nothing_to_draw_planned(monkeypatch):
    """The cards' AI finds nothing to draw on a card: said (a 400), nothing drawn."""

    async def plan(s, front, back, asked, language):
        return PicturePlan(kind="picture", description="", search="")

    monkeypatch.setattr(llm, "plan_picture", plan)
    with pytest.raises(pictures.AppError) as raised:
        run(pictures.card_picture(AIConfig(), Card(front="?", back="!")))
    assert raised.value.code == "picture.no_subject" and raised.value.status == 400


def test_a_drawing_that_is_no_image(monkeypatch, tmp_path):
    """The image model answers bytes that aren't an image: that card fails as "no picture",
    the others are drawn."""
    monkeypatch.setattr(files, "_cache_root", lambda: tmp_path / "cache")

    async def draw(s, subject):
        return b"<html>not an image</html>" if subject == "a dog" else PNG

    monkeypatch.setattr(pictures, "draw", draw)
    cards = [
        Card(front="Q", back="a dog", picture_prompt="a dog", id="d"),
        Card(front="Q", back="a cat", picture_prompt="a cat", id="c"),
    ]
    failed, first, _ = run(pictures.draw_all(AIConfig(picture_find=False), tmp_path / "images", cards, draw=True))
    assert (failed, first) == (1, {"code": "picture.empty", "params": {}})
    assert [bool(c.picture) for c in cards] == [False, True]
