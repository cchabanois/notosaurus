"""The calls to Gemini: how much the model thinks on a light task."""

import asyncio
import types as py_types

from google.genai import errors, types

from app import settings
from notosaurus_core import llm
from notosaurus_core.figures import Drawing

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


class NoQuota(FakeGemini):
    """A free key: no quota for the given models (gemini-3.8-flash has none on the free tier)."""

    def __init__(self, without_quota):
        super().__init__()
        self.without_quota = set(without_quota)

    async def generate(self, model, contents, config):
        if model in self.without_quota:
            self.levels.append((model, "429"))
            message = "You exceeded your current quota, please check your plan and billing details."
            raise errors.ClientError(429, {"error": {"code": 429, "message": message, "status": "RESOURCE_EXHAUSTED"}})
        return await super().generate(model, contents, config)


def test_no_quota_left_the_fallback_answers(client, monkeypatch):
    monkeypatch.setenv("NOTOSAURUS_LLM", "gemini")
    monkeypatch.setenv("NOTOSAURUS_MODEL", "gemini-3.8-flash")
    monkeypatch.delenv("NOTOSAURUS_FALLBACK_MODEL", raising=False)
    s = settings.current()
    assert s.fallback_models == "gemini-3.5-flash"  # by default: not flash-lite, which reads lessons badly
    fake = NoQuota({"gemini-3.8-flash"})
    monkeypatch.setattr(llm, "_gemini_client", lambda s: fake)
    assert asyncio.run(llm._generate(s, [], "cards", Drawing, "rules")).svg == "<svg/>"
    assert [m for m, _ in fake.levels] == ["gemini-3.8-flash", "gemini-3.5-flash"]

    # The key check says which model answered, and which one the key can't use
    found = asyncio.run(llm.check(s))
    assert (found["model"], found["quota"]) == ("gemini-3.5-flash", "gemini-3.8-flash")

    # No quota anywhere: said, with what to do (not "try again in a moment")
    fake.without_quota.add("gemini-3.5-flash")
    for call in (lambda: llm._generate(s, [], "cards", Drawing, "rules"), lambda: llm.check(s)):
        try:
            asyncio.run(call())
        except llm.ExtractionError as e:
            assert e.code == "llm.gemini_quota"
        else:
            raise AssertionError("an error was expected")
