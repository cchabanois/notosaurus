"""Gemini, through the official google-genai SDK (a key, or Vertex AI): stricter safety
filters, the fallback models when one is overloaded, has no quota or stops answering, "light" and
"quick" thinking, the answer streamed card by card when asked."""

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from ..calls import CardStream, ExtractionError, Image, OnCard, record, tell
from ..config import AIConfig
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

    client = _gemini_client(s)
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
    response = await _fallback(_Request(client, s, contents, config, light, quick, on_card), models)
    return _read_answer(response, schema)


async def _fallback(request: _Request, models: list[str]):
    """The answer of the first model that gives one, in order (the configured model, then
    the fallback ones): overloaded, without quota or stalled, the next one is tried; any
    other error stops, as does the last model's."""
    for model in models:
        try:
            return await _call_one_model(request, model)
        except ExtractionError as e:
            if e.code not in _NEXT_MODEL or model == models[-1]:
                raise
            quota = e.code == "llm.gemini_quota"
            log.warning("Quota exceeded: falling back to the next model" if quota else "Falling back to the next model")
            tell({"step": "fallback"})
    raise ExtractionError("llm.empty_answer", provider="Gemini")  # no model at all


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
        call = request.client.aio.models.generate_content(model=model, contents=request.contents, config=request.config)
        return await _within(WHOLE_ANSWER_S, call)
    return await _streamed(request, model, request.on_card)


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
    stream = await _within(FIRST_PART_S, call)
    parts, wait = aiter(stream), FIRST_PART_S
    try:
        while True:
            try:
                chunk = await _within(wait, anext(parts))
            except StopAsyncIteration:
                break
            wait = NEXT_PART_S
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
