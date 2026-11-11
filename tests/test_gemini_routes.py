"""Gemini's other routes (config.GeminiRouting): the same model asked elsewhere when a route
stalls, a route stalling again and again left to rest, then tried again by one call."""

import asyncio
import json
import logging
import types as py_types

from google.genai import types
from helpers import run
from test_gemini import SVG, Scripted

from notosaurus_core import calls, llm
from notosaurus_core.config import AIConfig, GeminiRouting
from notosaurus_core.prompts import ExtractOptions
from notosaurus_core.providers import gemini

ROUTED = AIConfig(
    gemini_vertex_project="p",
    gemini_vertex_location="eu",
    gemini_api_key="k",
    gemini_routing=GeminiRouting(routes="key", stalls=2, window_s=60, rest_s=60),
)


def _routed(monkeypatch, **by_route) -> dict[str, Scripted]:
    """Each route a Gemini of its own (`by_route`: its Scripted, by route name)."""
    clients = {name: by_route.get(name) or Scripted() for name in ("eu", "global", "key")}
    monkeypatch.setattr(gemini, "_gemini_client", lambda s: clients[s.gemini_route()])
    monkeypatch.setattr(gemini, "_HEALTH", {})
    monkeypatch.setattr(gemini, "WHOLE_ANSWER_S", 0.05)
    return clients


def _ask(s: AIConfig = ROUTED, models=("a", "b"), light=False):
    """The answer through `s`'s routes, and the steps told to the user."""
    request = gemini._Request(
        gemini._gemini_client(s), s, ["cards"], types.GenerateContentConfig(), light=light, routing=s.gemini_routing
    )
    told: list[dict] = []

    async def asked():
        with calls.telling(told.append):
            return await gemini._fallback(request, list(models), gemini._routes(s))

    return run(asked()), told


def _asked(clients) -> list[tuple[str, str]]:
    return [(name, model) for name, client in clients.items() for model in client.models]


def test_a_stalled_route_the_same_model_asked_on_the_next(monkeypatch):
    """eu stalls: model "a" asked through the Gemini API, not the fallback model on eu (as
    busy then); the user told, as for a fallback model."""
    clients = _routed(monkeypatch, eu=Scripted(a="stall"))
    response, told = _ask()
    assert response.text == SVG
    assert _asked(clients) == [("eu", "a"), ("key", "a")]
    assert told == [{"step": "fallback"}]


def test_a_route_stalling_again_and_again_rests_then_is_tried_again(monkeypatch):
    clients = _routed(monkeypatch, eu=Scripted(a="stall"))
    _ask()
    _ask()  # its second stall within the window: eu rests
    clients["eu"].models.clear()
    clients["key"].models.clear()
    response, told = _ask()
    assert response.text == SVG and told == []  # straight to the Gemini API: no wait, nothing said
    assert _asked(clients) == [("key", "a")]

    gemini._HEALTH["eu"].rest_until = 0.001  # its rest over: one call tries it again
    clients["eu"].by_model = {}  # eu answers again
    _ask()
    assert clients["eu"].models == ["a"] and not gemini._HEALTH["eu"].rest_until  # back on eu
    _ask()
    assert clients["eu"].models == ["a", "a"]


def test_a_route_still_failing_when_tried_again_rests_more(monkeypatch):
    clients = _routed(monkeypatch, eu=Scripted(a="stall"))
    gemini._HEALTH["eu"] = gemini._Health(rest_until=0.001)
    response, _ = _ask()
    assert response.text == SVG and _asked(clients) == [("eu", "a"), ("key", "a")]
    assert gemini._HEALTH["eu"].rest_until > 1 and not gemini._HEALTH["eu"].trying


def test_one_call_alone_tries_a_rested_route_again(monkeypatch):
    _routed(monkeypatch)
    routes = gemini._routes(ROUTED)
    gemini._HEALTH["eu"] = gemini._Health(rest_until=0.001)
    first, second = [], []
    assert [r.name for r in gemini._order(routes, first)] == ["eu", "key"]
    assert [r.name for r in gemini._order(routes, second)] == ["key"]  # the first one is trying it
    assert [r.name for r in first] == ["eu"] and second == []


def test_another_routes_own_failure_goes_on(monkeypatch):
    """The Gemini API refusing (its key, its prepaid credits): the fallback model on eu, not
    an error; the config's own route refusing still stops at once."""
    clients = _routed(monkeypatch, eu=Scripted(a="stall"), key=Scripted(a=401))
    response, _ = _ask()
    assert response.text == SVG and _asked(clients) == [("eu", "a"), ("eu", "b"), ("key", "a")]

    clients = _routed(monkeypatch, eu=Scripted(a=400))
    try:
        _ask()
    except llm.ExtractionError as e:
        assert e.code == "llm.api_error"
    else:
        raise AssertionError("an error was expected")
    assert _asked(clients) == [("eu", "a")]


def test_past_the_budget_the_fallback_model_not_another_route(monkeypatch):
    clients = _routed(monkeypatch, eu=Scripted(a="stall"))
    late = ROUTED.model_copy(update={"gemini_routing": ROUTED.gemini_routing.model_copy(update={"budget_s": 0})})
    response, _ = _ask(late)
    assert response.text == SVG and _asked(clients) == [("eu", "a"), ("eu", "b")]


def test_a_light_call_left_waiting_is_asked_again_on_the_next_route(monkeypatch):
    monkeypatch.setattr(gemini, "ASK_AGAIN_S", 0.05)
    clients = _routed(monkeypatch, eu=Scripted(a="stall"))
    response, _ = _ask(light=True)
    assert response.text == SVG and _asked(clients) == [("eu", "a"), ("key", "a")]


def test_one_route_as_before(monkeypatch):
    """No other route: the fallback models on the config's own, no route left to rest."""
    clients = _routed(monkeypatch, eu=Scripted(a="stall"))
    alone = ROUTED.model_copy(update={"gemini_routing": GeminiRouting()})
    for _ in range(3):
        _ask(alone)
    assert _asked(clients) == [("eu", "a"), ("eu", "b")] * 3 and gemini._HEALTH == {}


def test_route_changes_logged_with_their_values(monkeypatch, caplog):
    """Nothing of a lesson in them: marked so, the relay keeps their values (its NoContent)."""
    _routed(monkeypatch, eu=Scripted(a="stall"))
    with caplog.at_level(logging.WARNING, logger="notosaurus"):
        _ask()
        _ask()
    said = [r for r in caplog.records if getattr(r, "no_content", False)]
    assert [r.getMessage() for r in said] == [
        "Gemini route eu: llm.timeout, key tried",
        "Gemini route eu failed 2 times in 60 s: rests 60 s",
        "Gemini route eu: llm.timeout, key tried",
    ]


def test_routes_from_the_config():
    assert [r.name for r in gemini._routes(ROUTED)] == ["eu", "key"]
    both = ROUTED.model_copy(update={"gemini_routing": GeminiRouting(routes="global, key, eu")})
    assert [r.name for r in gemini._routes(both)] == ["eu", "global", "key"]  # its own not twice
    no_key = ROUTED.model_copy(update={"gemini_api_key": ""})
    assert [r.name for r in gemini._routes(no_key)] == ["eu"]  # "key" without one: left out
    by_key = AIConfig(gemini_api_key="k", gemini_routing=GeminiRouting(routes="global"))
    assert [r.name for r in gemini._routes(by_key)] == ["key"]  # a location without a project
    assert ROUTED.on_gemini_route("key").gemini_options() == {"api_key": "k"}
    assert ROUTED.on_gemini_route("global").gemini_options()["location"] == "global"


class SlowStart:
    """A Gemini whose stream's first part comes after `delay` seconds (the model thinking)."""

    def __init__(self, delay: float):
        self.delay, self.models = delay, []
        self.aio = py_types.SimpleNamespace(models=py_types.SimpleNamespace(generate_content_stream=self.stream))

    async def stream(self, model, contents, config):
        self.models.append(model)
        delay = self.delay if len(self.models) == 1 else 0

        async def chunks():
            await asyncio.sleep(delay)
            text = json.dumps({"cards": [{"front": "la mère", "back": "la madre"}], "deck": "D"})
            candidate = py_types.SimpleNamespace(finish_reason=types.FinishReason.STOP)
            yield py_types.SimpleNamespace(text=text, candidates=[candidate], usage_metadata=None, prompt_feedback=None)

        return chunks()


def test_the_first_part_waited_for_as_long_as_the_lesson_thinks(monkeypatch):
    """A quick lesson's first card comes in about 5 s, a careful one's in about 12 s, whatever
    its pages: each its own wait before the next try."""
    routing = GeminiRouting(first_part_quick_s=0.1, first_part_s=1)
    s = AIConfig(gemini_api_key="k", model="x", fallback_models="y", gemini_routing=routing)

    async def on_card(card):
        pass

    for quick, models in ((True, ["x", "y"]), (False, ["x"])):
        fake = SlowStart(0.3)
        monkeypatch.setattr(gemini, "_gemini_client", lambda s, fake=fake: fake)
        run(llm.extract_cards(s, [], "FR → ES", ExtractOptions(quick=quick), on_card=on_card))
        assert fake.models == models
