"""The calls to Gemini: how much the model thinks on a light task."""

import asyncio
import types as py_types

from google.genai import errors, types

from app import llm, settings
from app.figures import Drawing

SVG = '{"svg": "<svg/>"}'


class FakeGemini:
    """A Gemini whose models may refuse the "minimal" thinking level, as gemini-3.8-flash does."""

    def __init__(self, no_minimal=()):
        self.no_minimal, self.levels = set(no_minimal), []
        self.aio = py_types.SimpleNamespace(models=py_types.SimpleNamespace(generate_content=self.generate))

    async def generate(self, model, contents, config):
        level = config.thinking_config.thinking_level if config.thinking_config else None
        self.levels.append((model, level))
        if model in self.no_minimal and level == types.ThinkingLevel.MINIMAL:
            message = "Thinking level MINIMAL is not supported for this model. Please retry with other thinking level."
            raise errors.ClientError(400, {"error": {"code": 400, "message": message, "status": "INVALID_ARGUMENT"}})
        candidate = py_types.SimpleNamespace(finish_reason=types.FinishReason.STOP)
        return py_types.SimpleNamespace(usage_metadata=None, candidates=[candidate], text=SVG)


def test_light_tasks_think_as_little_as_each_model_allows(client, monkeypatch):
    monkeypatch.setenv("NOTOSAURUS_LLM", "gemini")
    monkeypatch.setenv("NOTOSAURUS_MODEL", "gemini-3.8-flash")
    fake = FakeGemini(no_minimal={"gemini-3.8-flash"})
    monkeypatch.setattr(llm, "_gemini_client", lambda s: fake)
    monkeypatch.setattr(llm, "_NO_MINIMAL_THINKING", set())
    s = settings.current()

    def draw():
        return asyncio.run(llm._generate(s, [], "a triangle", Drawing, "rules", light=True))

    assert draw().svg == "<svg/>"  # refused "minimal": "low", at once
    assert fake.levels == [
        ("gemini-3.8-flash", types.ThinkingLevel.MINIMAL),
        ("gemini-3.8-flash", types.ThinkingLevel.LOW),
    ]
    fake.levels.clear()
    draw()  # learnt: "low" straight away
    assert fake.levels == [("gemini-3.8-flash", types.ThinkingLevel.LOW)]

    # A model that allows it keeps "minimal"; a task that isn't light sets nothing
    monkeypatch.setenv("NOTOSAURUS_MODEL", "gemini-3.5-flash-lite")
    s = settings.current()
    fake.levels.clear()
    draw()
    asyncio.run(llm._generate(s, [], "cards", Drawing, "rules"))
    assert fake.levels == [("gemini-3.5-flash-lite", types.ThinkingLevel.MINIMAL), ("gemini-3.5-flash-lite", None)]


def test_other_refusals_are_still_errors(client, monkeypatch):
    monkeypatch.setenv("NOTOSAURUS_LLM", "gemini")
    monkeypatch.setenv("NOTOSAURUS_MODEL", "gemini-3.8-flash")

    class Refusing(FakeGemini):
        async def generate(self, model, contents, config):
            self.levels.append(model)
            raise errors.ClientError(
                400, {"error": {"code": 400, "message": "Bad image", "status": "INVALID_ARGUMENT"}}
            )

    fake = Refusing()
    monkeypatch.setattr(llm, "_gemini_client", lambda s: fake)
    try:
        asyncio.run(llm._generate(settings.current(), [], "x", Drawing, "rules", light=True))
    except llm.ExtractionError as e:
        assert e.code == "llm.api_error" and fake.levels == ["gemini-3.8-flash"]  # no second try
    else:
        raise AssertionError("an error was expected")
