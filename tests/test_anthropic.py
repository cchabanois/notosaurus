"""The calls to Claude: the request sent, the answer read, its cost kept, and the
service's errors told to the page as codes."""

import base64
import types

import anthropic as anthropic_sdk
import httpx
import pytest
from helpers import plain_image, run

from notosaurus_core import llm
from notosaurus_core.calls import ExtractionError, Image, recording
from notosaurus_core.config import AIConfig
from notosaurus_core.figures import Drawing
from notosaurus_core.prompts import SYSTEM_PROMPT
from notosaurus_core.providers import anthropic

MODEL = "claude-sonnet-4-6"
CONFIG = AIConfig(llm="anthropic", model=MODEL, anthropic_api_key="sk-test")
REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


class FakeClaude:
    """A Claude answering `answer` (validated against the schema asked for), or raising
    `error`; it keeps the arguments of each call."""

    def __init__(self, answer=None, error=None, stop_reason="end_turn", usage=(1000, 100), model=MODEL):
        self.answer, self.error, self.stop_reason, self.usage, self.model = answer, error, stop_reason, usage, model
        self.calls = []
        self.messages = types.SimpleNamespace(parse=self.parse)

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        parsed = kwargs["output_format"].model_validate(self.answer) if self.answer is not None else None
        usage = types.SimpleNamespace(input_tokens=self.usage[0], output_tokens=self.usage[1]) if self.usage else None
        return types.SimpleNamespace(model=self.model, usage=usage, stop_reason=self.stop_reason, parsed_output=parsed)


def ask(monkeypatch, fake, images=(), text="a triangle", schema=Drawing, system="rules"):
    """The provider called directly with `fake` as the client."""
    monkeypatch.setattr(anthropic, "_anthropic_client", lambda s: fake)
    return run(anthropic._anthropic(CONFIG, list(images), text, schema, system))


def ask_recorded(monkeypatch, fake):
    """The provider called while the calls are recorded: (its answer or error, the calls
    kept). Recorded inside the coroutine: `run` gives it a thread of its own. Used with
    the `client` fixture: the model prices come from its fake list, not the network."""
    monkeypatch.setattr(anthropic, "_anthropic_client", lambda s: fake)

    async def call():
        with recording("extract") as calls:
            try:
                return await anthropic._anthropic(CONFIG, [], "a triangle", Drawing, "rules"), calls
            except ExtractionError as e:
                return e, calls

    return run(call())


def status_error(cls, status, message="boom"):
    response = httpx.Response(status, request=REQUEST, json={"error": {"message": message}})
    return cls(message, response=response, body=None)


def test_the_request_sent(monkeypatch):
    """The model chosen, the rules as the system prompt, each photo as a base64 image
    block with its own media type, then the user's text last; room for a long answer,
    and the server-side fallback when the model refuses."""
    fake = FakeClaude(answer={"svg": "<svg/>"})
    jpeg, png = plain_image(4, 4), plain_image(4, 4, fmt="PNG")
    images = [Image(jpeg, "image/jpeg"), Image(png, "image/png")]
    assert ask(monkeypatch, fake, images, text="draw it").svg == "<svg/>"
    (sent,) = fake.calls
    assert sent["model"] == MODEL
    assert sent["system"] == "rules"
    assert sent["max_tokens"] == 16000
    assert sent["output_format"] is Drawing
    (message,) = sent["messages"]
    assert message["role"] == "user"
    first, second, text = message["content"]
    assert first == {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.standard_b64encode(jpeg).decode()},
    }
    assert second["source"]["media_type"] == "image/png"
    assert base64.standard_b64decode(second["source"]["data"]) == png
    assert text == {"type": "text", "text": "draw it"}
    assert sent["extra_headers"] == {"anthropic-beta": "server-side-fallback-2026-07-01"}
    assert sent["extra_body"] == {"fallbacks": "default"}


def test_the_default_model_and_rules(monkeypatch):
    """No model chosen: the provider's recommended one; no rules given: the cards' rules."""
    fake = FakeClaude(answer={"svg": "<svg/>"})
    monkeypatch.setattr(anthropic, "_anthropic_client", lambda s: fake)
    run(anthropic._anthropic(AIConfig(llm="anthropic", anthropic_api_key="k"), [], "x", Drawing))
    assert fake.calls[0]["model"] == AIConfig(llm="anthropic").model_for_provider() != ""
    assert fake.calls[0]["system"] == SYSTEM_PROMPT


def test_without_a_key():
    """No key: told at once, before any call."""
    with pytest.raises(ExtractionError) as e:
        anthropic._anthropic_client(AIConfig(llm="anthropic"))
    assert (e.value.code, e.value.params) == ("llm.missing_key", {"provider": "Anthropic"})
    assert isinstance(anthropic._anthropic_client(CONFIG), anthropic_sdk.AsyncAnthropic)  # no network: just built


def test_a_lesson_made_by_claude(client, monkeypatch):
    """Through the app: Claude's cards make the lesson, and the call is kept with its
    model, tokens and estimated cost (Claude gives no price)."""
    monkeypatch.setenv("NOTOSAURUS_LLM", "anthropic")
    monkeypatch.setenv("NOTOSAURUS_MODEL", MODEL)
    fake = FakeClaude(
        answer={"deck": "Espagnol", "cards": [{"front": "le chat", "back": "el gato"}]}, usage=(2000, 300)
    )
    monkeypatch.setattr(anthropic, "_anthropic_client", lambda s: fake)
    files = [("images", ("p1.png", plain_image(8, 8, fmt="PNG"), "image/png"))]
    res = client.post("/api/extract", files=files, data={"prompt": "words: le chat"})
    assert res.status_code == 201
    lesson = res.json()
    assert [(c["front"], c["back"]) for c in lesson["cards"]] == [("le chat", "el gato")]
    (call,) = lesson["ai_calls"]
    assert call | {"at": None} == {
        "at": None,
        "kind": "extract",
        "provider": "anthropic",
        "model": MODEL,
        "input_tokens": 2000,
        "output_tokens": 300,
        "cost": pytest.approx(2000 * 0.000003 + 300 * 0.000015),  # anthropic/claude-sonnet-4.6's price
        "exact": False,
    }
    content = fake.calls[0]["messages"][0]["content"]
    assert [block["type"] for block in content] == ["image", "text"]
    assert "le chat" in content[-1]["text"]


def test_the_model_that_answered_is_the_one_recorded(client, monkeypatch):
    """A refusal rerun on the fallback model: the call is kept under the model that
    answered (the one paid for), not the one asked."""
    fake = FakeClaude(answer={"svg": "<svg/>"}, model="claude-opus-4-6")
    _, calls = ask_recorded(monkeypatch, fake)
    assert [(c.provider, c.model, c.input_tokens, c.output_tokens) for c in calls] == [
        ("anthropic", "claude-opus-4-6", 1000, 100)
    ]


@pytest.mark.parametrize(
    ("stop_reason", "answer", "code"),
    [
        ("refusal", None, "llm.refused"),
        ("max_tokens", None, "llm.truncated"),
        ("end_turn", None, "llm.invalid_answer"),  # no answer read in the schema
    ],
)
def test_answers_that_make_no_cards(client, monkeypatch, stop_reason, answer, code):
    """The model answered but gave nothing usable: an error the page translates, and
    the call still kept (it is paid for)."""
    fake = FakeClaude(answer=answer, stop_reason=stop_reason)
    error, calls = ask_recorded(monkeypatch, fake)
    assert isinstance(error, ExtractionError) and error.code == code
    assert len(calls) == 1


def test_no_usage_nothing_recorded(client, monkeypatch):
    fake = FakeClaude(answer={"svg": "<svg/>"}, usage=None)
    drawing, calls = ask_recorded(monkeypatch, fake)
    assert drawing.svg == "<svg/>"
    assert calls == []


@pytest.mark.parametrize(
    ("error", "code", "params"),
    [
        (status_error(anthropic_sdk.AuthenticationError, 401), "llm.invalid_key", {"provider": "Anthropic"}),
        (status_error(anthropic_sdk.RateLimitError, 429), "llm.quota", {"provider": "Anthropic"}),
        (
            status_error(anthropic_sdk.InternalServerError, 529, "Overloaded"),
            "llm.api_error",
            {"provider": "Anthropic", "status": 529, "detail": "Overloaded"},
        ),
        (
            status_error(anthropic_sdk.BadRequestError, 400, "Image too large"),
            "llm.api_error",
            {"provider": "Anthropic", "status": 400, "detail": "Image too large"},
        ),
        (anthropic_sdk.APIConnectionError(request=REQUEST), "llm.unreachable", {"provider": "Anthropic"}),
        (anthropic_sdk.APITimeoutError(request=REQUEST), "llm.unreachable", {"provider": "Anthropic"}),
    ],
)
def test_service_errors_become_codes(client, monkeypatch, error, code, params):
    """Each failure of the service becomes a code the page translates; nothing is
    recorded (nothing was answered)."""
    raised, calls = ask_recorded(monkeypatch, FakeClaude(error=error))
    assert isinstance(raised, ExtractionError)
    assert (raised.code, raised.params, raised.status) == (code, params, 502)
    assert calls == []


def test_chosen_by_the_settings(monkeypatch):
    """llm._generate sends to Claude when the settings say "anthropic"."""
    fake = FakeClaude(answer={"svg": "<svg/>"})
    monkeypatch.setattr(anthropic, "_anthropic_client", lambda s: fake)
    assert run(llm._generate(CONFIG, [], "x", Drawing, "rules", light=True)).svg == "<svg/>"
    assert len(fake.calls) == 1
