"""The calls to Gemini: how much the model thinks on a light task."""

import asyncio
import types as py_types
from contextlib import suppress

from google.genai import errors, types
from helpers import run

from app import settings
from notosaurus_core import llm
from notosaurus_core.config import AIConfig
from notosaurus_core.figures import Drawing
from notosaurus_core.providers import gemini

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
    monkeypatch.setattr(gemini, "_gemini_client", lambda s: fake)
    monkeypatch.setattr(gemini, "_NO_MINIMAL_THINKING", set())
    s = settings.current()

    def draw():
        return asyncio.run(llm._ask_provider(s, [], "a triangle", Drawing, "rules", light=True))

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
    asyncio.run(llm._ask_provider(s, [], "cards", Drawing, "rules"))
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
    monkeypatch.setattr(gemini, "_gemini_client", lambda s: fake)
    try:
        asyncio.run(llm._ask_provider(settings.current(), [], "x", Drawing, "rules", light=True))
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
    monkeypatch.setattr(gemini, "_gemini_client", lambda s: fake)
    assert asyncio.run(llm._ask_provider(s, [], "cards", Drawing, "rules")).svg == "<svg/>"
    assert [m for m, _ in fake.levels] == ["gemini-3.8-flash", "gemini-3.5-flash"]

    # The key check says which model answered, and which one the key can't use
    found = asyncio.run(llm.check(s))
    assert (found["model"], found["quota"]) == ("gemini-3.5-flash", "gemini-3.8-flash")

    # No quota anywhere: said, with what to do (not "try again in a moment")
    fake.without_quota.add("gemini-3.5-flash")
    for call in (lambda: llm._ask_provider(s, [], "cards", Drawing, "rules"), lambda: llm.check(s)):
        try:
            asyncio.run(call())
        except llm.ExtractionError as e:
            assert e.code == "llm.gemini_quota"
        else:
            raise AssertionError("an error was expected")


def test_gemini_through_vertex_ai(monkeypatch):
    """A Vertex AI project instead of a key (the relay on Google Cloud): Gemini is ready,
    its clients made for Vertex AI, the pictures drawn by it too."""
    from google import genai

    from notosaurus_core import config, pictures
    from notosaurus_core.config import AIConfig

    vertex = AIConfig(llm="gemini", gemini_vertex_project="p")
    assert config.configured(vertex) and not config.configured(AIConfig(llm="gemini"))
    assert vertex.gemini_options() == {"vertexai": True, "project": "p", "location": "global"}
    assert AIConfig(gemini_api_key="k").gemini_options() == {"api_key": "k"}
    assert pictures.service(vertex) == "gemini"

    made = []
    monkeypatch.setattr(genai, "Client", lambda **options: made.append(options))
    gemini._gemini_client(vertex.model_copy(update={"gemini_vertex_location": "europe-west1"}))
    assert made[0]["vertexai"] and made[0]["location"] == "europe-west1" and "api_key" not in made[0]


def test_quick_lessons_think_little(monkeypatch):
    """A lesson made quick (the page's "Quick"): Gemini 3 thinks "low"; carefully, as it likes."""
    fake = FakeGemini()
    monkeypatch.setattr(gemini, "_gemini_client", lambda s: fake)
    s = AIConfig(gemini_api_key="k", model="gemini-3.8-flash")
    asyncio.run(llm._ask_provider(s, [], "cards", Drawing, "rules", quick=True))
    asyncio.run(llm._ask_provider(s, [], "cards", Drawing, "rules"))
    assert fake.levels == [("gemini-3.8-flash", types.ThinkingLevel.LOW), ("gemini-3.8-flash", None)]


class Recording(FakeGemini):
    """A Gemini that answers `answer` and keeps each request: its model, contents and config."""

    def __init__(self, answer: str, finish=types.FinishReason.STOP):
        super().__init__()
        self.answer, self.finish, self.calls = answer, finish, []

    async def generate(self, model, contents, config):
        self.calls.append((model, contents, config))
        candidate = py_types.SimpleNamespace(finish_reason=self.finish)
        usage = py_types.SimpleNamespace(prompt_token_count=100, candidates_token_count=20, thoughts_token_count=5)
        return py_types.SimpleNamespace(usage_metadata=usage, candidates=[candidate], text=self.answer)


LIGHT = AIConfig(gemini_api_key="k", model="gemini-3.8-flash")


def _light_call(monkeypatch, answer: str, call, finish=types.FinishReason.STOP):
    """`call` (a coroutine of the light-call function, given the config) answered by a
    recording Gemini: the result, and the one request made."""
    fake = Recording(answer, finish)
    monkeypatch.setattr(gemini, "_gemini_client", lambda s: fake)
    monkeypatch.setattr(gemini, "_NO_MINIMAL_THINKING", set())
    found = asyncio.run(call(LIGHT))
    assert len(fake.calls) == 1  # one call, to the configured model
    return found, fake.calls[0]


def _assert_light_request(request, schema, rules):
    model, contents, config = request
    assert model == "gemini-3.8-flash"
    assert config.system_instruction == rules
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == schema.model_json_schema()
    assert config.thinking_config.thinking_level == types.ThinkingLevel.MINIMAL  # light: thinks as little as it can
    assert config.automatic_function_calling.disable and config.safety_settings  # the stricter filters too
    assert len(contents) == 1 and isinstance(contents[0], str)  # text only, no photo
    return contents[0]


def _error(monkeypatch, answer: str, call, finish=types.FinishReason.STOP) -> str:
    try:
        _light_call(monkeypatch, answer, call, finish)
    except llm.ExtractionError as e:
        return e.code
    raise AssertionError("an error was expected")


def test_draw_figure_with_gemini(monkeypatch):
    from notosaurus_core import figures
    from notosaurus_core.calls import recording

    with recording("picture") as calls:
        svg, request = _light_call(
            monkeypatch,
            '{"svg": "<svg viewBox=\\"0 0 400 300\\"/>"}',
            lambda s: llm.draw_figure(s, "  a right triangle ABC "),
        )
    assert svg == '<svg viewBox="0 0 400 300"/>'
    text = _assert_light_request(request, Drawing, figures.RULES)
    assert text == "Figure to draw: a right triangle ABC"
    assert [(c.model, c.input_tokens, c.output_tokens) for c in calls] == [("gemini-3.8-flash", 100, 25)]

    draw = lambda s: llm.draw_figure(s, "a square")  # noqa: E731
    assert _error(monkeypatch, "", draw) == "llm.empty_answer"
    assert _error(monkeypatch, "<svg/>", draw) == "llm.invalid_answer"  # not the JSON asked for
    assert _error(monkeypatch, '{"drawing": "<svg/>"}', draw) == "llm.invalid_answer"
    assert _error(monkeypatch, '{"svg": "<svg', draw, types.FinishReason.MAX_TOKENS) == "llm.truncated"
    assert _error(monkeypatch, '{"svg": ""}', draw, types.FinishReason.SAFETY) == "llm.refused"


def test_plan_picture_with_gemini(monkeypatch):
    from notosaurus_core.models import PicturePlan
    from notosaurus_core.prompts import PLAN_RULES

    answer = '{"kind": "picture", "description": " a red fox in snow ", "search": " red fox "}'
    plan, request = _light_call(
        monkeypatch, answer, lambda s: llm.plan_picture(s, " le renard ", " fox ", " un renard roux ", "French")
    )
    assert (plan.kind, plan.description, plan.search) == ("picture", "a red fox in snow", "red fox")  # trimmed
    text = _assert_light_request(request, PicturePlan, PLAN_RULES)
    assert "in French" in text and "le renard → fox" in text and "un renard roux" in text

    # Nothing written: the card alone decides; a figure has no search
    answer = '{"kind": "figure", "description": "Un triangle ABC rectangle en A"}'
    plan, request = _light_call(monkeypatch, answer, lambda s: llm.plan_picture(s, "Pythagore", "BC² = AB² + AC²"))
    assert (plan.kind, plan.description, plan.search) == ("figure", "Un triangle ABC rectangle en A", "")
    assert "nothing: decide from the card" in request[1][0]

    plan_ = lambda s: llm.plan_picture(s, "a", "b")  # noqa: E731
    assert _error(monkeypatch, "", plan_) == "llm.empty_answer"
    assert _error(monkeypatch, '{"kind": "photo", "description": "x"}', plan_) == "llm.invalid_answer"
    assert _error(monkeypatch, '{"kind": "picture"}', plan_) == "llm.invalid_answer"  # no description
    assert _error(monkeypatch, "not json", plan_) == "llm.invalid_answer"


def test_search_words_with_gemini(monkeypatch):
    from notosaurus_core.models import SearchWords
    from notosaurus_core.prompts import SEARCH_WORDS_RULES

    words, request = _light_call(
        monkeypatch, '{"words": " Eiffel tower "}', lambda s: llm.search_words(s, " la tour Eiffel ", "Paris → France")
    )
    assert words == "Eiffel tower"
    text = _assert_light_request(request, SearchWords, SEARCH_WORDS_RULES)
    assert "la tour Eiffel" in text and "The card it is for: Paris → France" in text

    # No context: no card line; empty words: what the user wrote, searched as it is
    words, request = _light_call(monkeypatch, '{"words": "  "}', lambda s: llm.search_words(s, " un chat "))
    assert words == "un chat" and "The card" not in request[1][0]

    search = lambda s: llm.search_words(s, "x")  # noqa: E731
    assert _error(monkeypatch, "", search) == "llm.empty_answer"
    assert _error(monkeypatch, '{"word": "cat"}', search) == "llm.invalid_answer"
    assert _error(monkeypatch, "[]", search) == "llm.invalid_answer"


# --- One model, the fallback over the models, the answer read ---------------------


class Scripted(FakeGemini):
    """A Gemini whose models each do as told (`by_model`): "stall" (never answers), an
    HTTP status (an error still there after the SDK's retries), or answer (by default)."""

    def __init__(self, **by_model):
        super().__init__()
        self.by_model, self.models = by_model, []

    async def generate(self, model, contents, config):
        self.models.append(model)
        what = self.by_model.get(model)
        if what == "stall":
            await asyncio.sleep(3600)
        if isinstance(what, int):
            error = errors.ClientError if what < 500 else errors.ServerError
            message = "API key not valid" if model == "bad-key" else "no"
            raise error(what, {"error": {"code": what, "message": message, "status": "X"}})
        candidate = py_types.SimpleNamespace(finish_reason=types.FinishReason.STOP)
        usage = py_types.SimpleNamespace(prompt_token_count=100, candidates_token_count=20, thoughts_token_count=5)
        return py_types.SimpleNamespace(usage_metadata=usage, candidates=[candidate], text=SVG)


def _request(fake) -> gemini._Request:
    return gemini._Request(fake, LIGHT, ["cards"], types.GenerateContentConfig())


def _failure(call) -> tuple[str, dict]:
    try:
        run(call)
    except llm.ExtractionError as e:
        return e.code, e.params
    raise AssertionError("an error was expected")


def test_overloaded_without_quota_or_stalled_the_next_model_answers(monkeypatch):
    monkeypatch.setattr(gemini, "WHOLE_ANSWER_S", 0.05)
    for failure in ("stall", 503, 429):
        fake = Scripted(a=failure)
        response = run(gemini._fallback(_request(fake), ["a", "b"]))
        assert response.text == SVG and fake.models == ["a", "b"]


def test_the_last_models_failure_is_said(monkeypatch):
    monkeypatch.setattr(gemini, "WHOLE_ANSWER_S", 0.05)
    said = {
        "stall": ("llm.timeout", {"provider": "Gemini"}),
        503: ("llm.overloaded", {"provider": "Gemini", "status": 503}),
        429: ("llm.gemini_quota", {}),
    }
    for failure, error in said.items():
        fake = Scripted(a=failure, b=failure)
        assert _failure(gemini._fallback(_request(fake), ["a", "b"])) == error
        assert fake.models == ["a", "b"]


def test_other_errors_stop_at_the_first_model():
    """A wrong key or a request refused: the next model would fail the same way."""
    stops = {
        401: ("llm.invalid_key", {"provider": "Gemini"}),
        403: ("llm.invalid_key", {"provider": "Gemini"}),
        400: ("llm.api_error", {"provider": "Gemini", "status": 400, "detail": "no"}),
    }
    for status, error in stops.items():
        fake = Scripted(a=status)
        assert _failure(gemini._fallback(_request(fake), ["a", "b"])) == error
        assert fake.models == ["a"]
    fake = Scripted(**{"bad-key": 400})  # a key refused with a 400: said as a wrong key
    assert _failure(gemini._fallback(_request(fake), ["bad-key", "b"]))[0] == "llm.invalid_key"
    assert fake.models == ["bad-key"]
    assert _failure(gemini._fallback(_request(fake), [])) == ("llm.empty_answer", {"provider": "Gemini"})


def test_one_models_answer_is_recorded():
    from notosaurus_core.calls import recording

    async def recorded(fake, model):
        with recording("extract") as calls, suppress(llm.ExtractionError):
            await gemini._call_one_model(_request(fake), model)
        return [(c.provider, c.model, c.input_tokens, c.output_tokens) for c in calls]

    assert run(recorded(Scripted(), "gemini-3.8-flash")) == [
        ("gemini", "gemini-3.8-flash", 100, 25)  # the thinking billed too
    ]
    assert run(recorded(Scripted(a=503), "a")) == []  # no answer, nothing paid


def _response(text=SVG, finish=types.FinishReason.STOP, block_reason=None, candidates=True):
    candidate = py_types.SimpleNamespace(finish_reason=finish)
    feedback = py_types.SimpleNamespace(block_reason=block_reason)
    return py_types.SimpleNamespace(text=text, candidates=[candidate] if candidates else None, prompt_feedback=feedback)


def test_the_answer_read():
    assert gemini._read_answer(_response(), Drawing).svg == "<svg/>"
    unread = {
        "llm.refused": [_response(finish=types.FinishReason.SAFETY), _response(block_reason="PROHIBITED_CONTENT")],
        "llm.empty_answer": [_response(text=""), _response(candidates=False)],
        "llm.truncated": [_response(text='{"svg": "<sv', finish=types.FinishReason.MAX_TOKENS)],
        "llm.invalid_answer": [_response(text="<svg/>"), _response(text='{"drawing": "<svg/>"}')],
    }
    for code, responses in unread.items():
        for response in responses:
            try:
                gemini._read_answer(response, Drawing)
            except llm.ExtractionError as e:
                assert e.code == code
            else:
                raise AssertionError(f"{code} expected")
