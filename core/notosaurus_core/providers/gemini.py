"""Gemini, through the official google-genai SDK (a key, or Vertex AI): stricter safety
filters, the fallback models when one is overloaded, has no quota or stops answering, "light" and
"quick" thinking, the answer streamed card by card when asked; other routes (another Vertex AI
location, the Gemini API) tried first when one stalls, a route stalling again and again left
to rest (config.GeminiRouting)."""

import asyncio
import logging
import time
from contextlib import suppress
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from ..calls import CardStream, ExtractionError, Image, OnCard, record, tell
from ..config import AIConfig, GeminiRouting
from ..prompts import SYSTEM_PROMPT

if TYPE_CHECKING:
    from google import genai
    from google.genai import errors, types

log = logging.getLogger("notosaurus")


def gemini_safety() -> list:
    """Gemini's own filters, stricter than its defaults (off for the latest models):
    what is made is for pupils. "Medium" and above: lessons on hard topics (history,
    biology) still pass."""
    from google.genai import types

    categories = (
        types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        types.HarmCategory.HARM_CATEGORY_HARASSMENT,
    )
    threshold = types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
    return [types.SafetySetting(category=c, threshold=threshold) for c in categories]


# Gemini's answer stopped by its filters
GEMINI_BLOCKED = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "IMAGE_SAFETY"}


def _gemini_client(s: AIConfig):
    from google import genai
    from google.genai import types

    if not s.gemini_ready():
        raise ExtractionError("llm.missing_key", provider="Gemini")
    # 5xx errors (mostly 503 "model overloaded") are frequent and short-lived, and so is a
    # 429 on Vertex AI's shared quota (its pool busy for a moment, not ours spent): the SDK
    # tries again with exponential backoff and jitter (2 s, then 4 s, give or take) before
    # the fallback model, often as busy then (Google's advice for 429s).
    return genai.Client(
        **s.gemini_options(),
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(
                attempts=3, initial_delay=2, jitter=1, http_status_codes=[429, 500, 502, 503, 504]
            )
        ),
    )


# Light tasks think as little as the model allows: "minimal", or "low" for the models
# that refuse it (gemini-3.8-flash: "Thinking level MINIMAL is not supported"), learnt
# at their first refusal.
_NO_MINIMAL_THINKING: set[str] = set()

# An answer that stops coming (seen: a stream left with nothing for minutes) is given up
# on and the next model tried, rather than waited for forever. Its first part comes once
# the model has thought (a rich lesson, carefully: up to a minute), then a card about
# every second; an answer asked whole comes at once.
FIRST_PART_S = 90
NEXT_PART_S = 45
WHOLE_ANSWER_S = 180

# A light call (a few seconds: a figure drawn, checked) at times hangs for a minute or more,
# the model's own wait, not the work (seen on Vertex AI): not answered after this, it is
# asked again beside it, the first answer taken, the other one cancelled
ASK_AGAIN_S = 12
# …and given up on (the next model tried) when neither came after this: both left waiting,
# seen for 180 s, the fallback model answering in under 2
LIGHT_ANSWER_S = 30

# What makes the next model tried, unless it was the last: overloaded (a 5xx still there
# after the SDK's retries), no quota (a free key has none for the latest models, and a
# quota of its own for each model: the next one may still answer), stopped answering.
# Anything else (a wrong key, a request refused) stops at once.
_NEXT_MODEL = {"llm.overloaded", "llm.gemini_quota", "llm.timeout"}


class _Stalled(Exception):
    """The model stopped answering."""


@dataclass
class _Request:
    """What every model tried is sent: the photos then the text, and the config (its
    thinking set for each model). `told`: the cards told so far to `on_card`, dropped
    when another model starts again."""

    client: "genai.Client"
    s: AIConfig
    contents: list[Any]
    config: "types.GenerateContentConfig"
    light: bool = False
    quick: bool = False
    on_card: OnCard | None = None
    told: int = 0
    routing: GeminiRouting = field(default_factory=GeminiRouting)
    spare: Any = None  # another route's client: a light call left waiting is asked again there


@dataclass
class _Route:
    """Where Gemini is asked: `name` a Vertex AI location or "key" ("": the request's own
    client, no other route); its client made when first used."""

    name: str
    s: AIConfig | None = None
    client: Any = None

    def made(self, request: _Request):
        if self.client is None:
            self.client = _gemini_client(self.s) if self.s is not None else request.client
        return self.client


@dataclass
class _Health:
    """A route's recent stalls (monotonic times), and whether it rests: until `rest_until`,
    then `trying` while one call tries it again."""

    stalled: list[float] = field(default_factory=list)
    rest_until: float = 0.0
    trying: bool = False


# Each route's health in this process (a relay's instance): shared by its calls
_HEALTH: dict[str, _Health] = {}
_NO_CONTENT = {"no_content": True}  # a log line with nothing of a lesson: its values kept (the relay's filter)


def _routes(s: AIConfig) -> list[_Route]:
    """The config's own route, then the GeminiRouting's others that can be used."""
    routes, names = [_Route(s.gemini_route(), s)], {s.gemini_route()}
    for name in s.gemini_routing.route_names():
        other = s.on_gemini_route(name)
        if other is not None and name not in names:
            routes.append(_Route(name, other))
            names.add(name)
    return routes


def _order(routes: list[_Route], claimed: list[_Route]) -> list[_Route]:
    """The routes to try, in order, the resting ones left out; one whose rest is over is
    tried again by this call alone (`claimed`, until it answers or fails). All resting: the
    first, as with one route."""
    if len(routes) == 1:
        return routes
    now, order = time.monotonic(), []
    for route in routes:
        health = _HEALTH.setdefault(route.name, _Health())
        if not health.rest_until:
            order.append(route)
        elif now >= health.rest_until and not health.trying:
            health.trying = True
            claimed.append(route)
            order.append(route)
    return order or routes[:1]


def _answered(route: _Route, claimed: list[_Route]) -> None:
    health = _HEALTH.get(route.name)
    if health is None:
        return
    if health.rest_until:
        log.warning("Gemini route %s answers again", route.name, extra=_NO_CONTENT)
    health.stalled, health.rest_until, health.trying = [], 0.0, False
    if route in claimed:
        claimed.remove(route)


def _failed(route: _Route, routing: GeminiRouting, claimed: list[_Route]) -> None:
    """A route stalled or failed: counted; `stalls` within `window_s` (or its one call
    trying it again failing) and it rests `rest_s`."""
    health, now = _HEALTH.setdefault(route.name, _Health()), time.monotonic()
    if route in claimed:
        claimed.remove(route)
        health.trying, health.rest_until = False, now + routing.rest_s
        log.warning("Gemini route %s still failing: rests %d s more", route.name, routing.rest_s, extra=_NO_CONTENT)
        return
    health.stalled = [t for t in health.stalled if t > now - routing.window_s] + [now]
    if len(health.stalled) >= routing.stalls and not health.rest_until:
        health.stalled, health.rest_until = [], now + routing.rest_s
        log.warning(
            "Gemini route %s failed %d times in %d s: rests %d s",
            route.name,
            routing.stalls,
            routing.window_s,
            routing.rest_s,
            extra=_NO_CONTENT,
        )


async def _gemini[T: BaseModel](
    s: AIConfig,
    images: list[Image],
    text: str,
    schema: type[T],
    system: str = SYSTEM_PROMPT,
    light: bool = False,
    quick: bool = False,
    on_card: OnCard | None = None,
) -> T:
    from google.genai import types

    routes = _routes(s)
    client = routes[0].client = _gemini_client(s)  # its own: made at once (a missing key said now)
    # The photos then the text (the SDK's PartUnion is a variable, not usable as a type)
    contents: list[Any] = [types.Part.from_bytes(data=img.data, mime_type=img.media_type) for img in images]
    contents.append(text)
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_json_schema=schema.model_json_schema(),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        safety_settings=gemini_safety(),
    )
    models = [s.model_for_provider()]
    models += [m.strip() for m in s.fallback_models.split(",") if m.strip()]
    request = _Request(client, s, contents, config, light, quick, on_card, routing=s.gemini_routing)
    response = await _fallback(request, models, routes)
    return _read_answer(response, schema)


async def _fallback(request: _Request, models: list[str], routes: list[_Route] | None = None):
    """The answer of the first try that gives one: the configured model on each route
    (resting ones left out), then the fallback models on the first. Overloaded, without
    quota or stalled, the next try; any other error stops, as does the last try's, except
    on another route than the config's own (its key, its credits: the next try may work).
    Another route is tried only within the routing's budget."""
    if not models:
        raise ExtractionError("llm.empty_answer", provider="Gemini")  # no model at all
    routes = routes or [_Route("")]
    claimed: list[_Route] = []
    order = _order(routes, claimed)
    tries = [(route, models[0]) for route in order] + [(order[0], model) for model in models[1:]]
    started = time.monotonic()
    try:
        for n, (route, model) in enumerate(tries):
            last = n == len(tries) - 1
            late = time.monotonic() - started >= request.routing.budget_s
            if model == models[0] and route is not order[0] and late and not last:
                continue  # past the budget: the fallback models, not another route's wait
            request.client = route.made(request)
            others = [r for r in order if r is not route]
            request.spare = others[0].made(request) if others else None
            try:
                response = await _call_one_model(request, model)
            except ExtractionError as e:
                elsewhere = route is not routes[0]  # another route's own failure (its key, its credits)
                if len(routes) > 1 and (e.code in _NEXT_MODEL or elsewhere):
                    _failed(route, request.routing, claimed)
                if last or not (e.code in _NEXT_MODEL or elsewhere):
                    raise
                if len(routes) > 1 and tries[n + 1][0] is not route:
                    log.warning(
                        "Gemini route %s: %s, %s tried", route.name, e.code, tries[n + 1][0].name, extra=_NO_CONTENT
                    )
                elif e.code == "llm.gemini_quota":
                    log.warning("Quota exceeded: falling back to the next model")
                else:
                    log.warning("Falling back to the next model")
                tell({"step": "fallback"})
                continue
            if len(routes) > 1:
                _answered(route, claimed)
            return response
    finally:
        for route in claimed:  # claimed but never tried: another call tries it again
            _HEALTH[route.name].trying = False
    raise ExtractionError("llm.empty_answer", provider="Gemini")


async def _call_one_model(request: _Request, model: str):
    """One model's answer, its usage recorded; its failures as ExtractionError. A model
    refusing the "minimal" thinking of a light task is asked again at once, "low"."""
    from google.genai import errors

    config = request.config
    try:
        config.thinking_config = _thinking(model, request.light, request.quick)
        try:
            response = await _generate(request, model)
        except errors.ClientError as e:
            if not (config.thinking_config and e.code == 400 and "Thinking level" in str(e.message)):
                raise
            _NO_MINIMAL_THINKING.add(model)  # this model thinks a little at least: "low" from now on
            config.thinking_config = _thinking(model, request.light, request.quick)
            response = await _generate(request, model)
    except errors.APIError as e:
        raise _api_error(model, e) from e
    except _Stalled:
        log.warning("Gemini %s stopped answering", model)
        raise ExtractionError("llm.timeout", provider="Gemini") from None
    usage = response.usage_metadata
    if usage:
        output = (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)  # thinking is billed too
        await record(request.s, "gemini", model, usage.prompt_token_count, output)
    return response


def _thinking(model: str, light: bool, quick: bool) -> "types.ThinkingConfig | None":
    """How much the model thinks: "low" when quick, as little as it can when light."""
    from google.genai import types

    if not ((light or quick) and model.startswith("gemini-3")):  # older models set thinking otherwise
        return None
    if quick:
        return types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)
    level = types.ThinkingLevel.LOW if model in _NO_MINIMAL_THINKING else types.ThinkingLevel.MINIMAL
    return types.ThinkingConfig(thinking_level=level)


def _api_error(model: str, e: "errors.APIError") -> ExtractionError:
    """An error from Gemini, as the page says it (still there after the SDK's retries)."""
    from google.genai import errors

    # The status, not the message: a 400's may quote the prompt (no lesson in logs)
    log.warning("Gemini %s: %s %s", model, e.code, e.status)
    if not isinstance(e, errors.ClientError):
        return ExtractionError("llm.overloaded", provider="Gemini", status=e.code)
    if e.code in (401, 403) or "API key" in str(e):
        return ExtractionError("llm.invalid_key", provider="Gemini")
    if e.code == 429:
        return ExtractionError("llm.gemini_quota")
    return ExtractionError("llm.api_error", provider="Gemini", status=e.code, detail=e.message)


async def _within(seconds: float, awaitable):
    try:
        return await asyncio.wait_for(awaitable, seconds)
    except TimeoutError:
        raise _Stalled from None


async def _generate(request: _Request, model: str):
    """The model's answer; written as it comes when the cards are wanted at once."""
    if request.on_card is None:

        def call():
            return request.client.aio.models.generate_content(
                model=model, contents=request.contents, config=request.config
            )

        def call_elsewhere():
            return (request.spare or request.client).aio.models.generate_content(
                model=model, contents=request.contents, config=request.config
            )

        if request.light:
            return await _within(LIGHT_ANSWER_S, _asked_again(call, call_elsewhere))
        return await _within(WHOLE_ANSWER_S, call())
    return await _streamed(request, model, request.on_card)


async def _asked_again(call, again=None):
    """`call`'s answer; not there after ASK_AGAIN_S, the same asked again beside it (by
    `again`: on another route when there is one): the first answer that comes, the other
    cancelled. Both failing: the last one's error."""
    first = asyncio.ensure_future(call())
    done, _ = await asyncio.wait({first}, timeout=ASK_AGAIN_S)
    if done:
        return first.result()
    log.info("Gemini slow to answer: asked again")
    running = {first, asyncio.ensure_future((again or call)())}
    try:
        while True:
            done, running = await asyncio.wait(running, return_when=asyncio.FIRST_COMPLETED)
            answered = [t for t in done if not t.exception()]
            if answered:
                return answered[0].result()
            if not running:
                return done.pop().result()  # raises: the last one's error
    finally:
        for task in running:
            task.cancel()


async def _streamed(request: _Request, model: str, on_card: OnCard):
    """The answer as it comes, each card told as soon as written (those of a model tried
    before dropped first); given up on when its next part is too long in coming."""
    if request.told:  # another model starts again
        await on_card(None)
        request.told = 0
    chunks, cards = [], CardStream()
    call = request.client.aio.models.generate_content_stream(
        model=model, contents=request.contents, config=request.config
    )
    routing = request.routing
    first = (routing.first_part_quick_s if request.quick else routing.first_part_s) or FIRST_PART_S
    stream = await _within(first, call)
    parts, wait = aiter(stream), first
    try:
        while True:
            try:
                chunk = await _within(wait, anext(parts))
            except StopAsyncIteration:
                break
            wait = routing.next_part_s or NEXT_PART_S
            chunks.append(chunk)
            for card in cards.feed(chunk.text or ""):
                await on_card(card)
                request.told += 1
    finally:
        with suppress(Exception):  # given up on: the connection goes too
            await stream.aclose()
    return _joined(chunks)


def _joined(chunks: list):
    """A streamed answer as one: its whole text, the last usage and candidate (where the
    finish reason is), the first prompt feedback (where a block is said)."""
    return SimpleNamespace(
        text="".join(c.text or "" for c in chunks),
        usage_metadata=next((c.usage_metadata for c in reversed(chunks) if c.usage_metadata), None),
        candidates=next((c.candidates for c in reversed(chunks) if c.candidates), None),
        prompt_feedback=next((c.prompt_feedback for c in chunks if c.prompt_feedback), None),
    )


def _read_answer[T: BaseModel](response, schema: type[T]) -> T:
    """The answer as `schema`, unless Gemini's filters stopped it, it is empty, cut short
    or not the JSON asked for."""
    from google.genai import types

    candidate = response.candidates[0] if response.candidates else None
    feedback = getattr(response, "prompt_feedback", None)
    stopped = getattr(getattr(candidate, "finish_reason", None), "value", None)
    if (feedback and feedback.block_reason) or stopped in GEMINI_BLOCKED:
        raise ExtractionError("llm.refused")
    if candidate is None or not response.text:
        raise ExtractionError("llm.empty_answer", provider="Gemini")
    if candidate.finish_reason == types.FinishReason.MAX_TOKENS:
        raise ExtractionError("llm.truncated")
    try:
        return schema.model_validate_json(response.text)
    except ValueError as e:
        raise ExtractionError("llm.invalid_answer") from e
