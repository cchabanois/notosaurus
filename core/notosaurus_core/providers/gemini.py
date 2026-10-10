"""Gemini, through the official google-genai SDK (a key, or Vertex AI): stricter safety
filters, the fallback models when one is overloaded, has no quota or stops answering, "light" and
"quick" thinking, the answer streamed card by card when asked."""

import asyncio
import logging
from contextlib import suppress
from types import SimpleNamespace

from pydantic import BaseModel

from ..calls import CardStream, ExtractionError, Image, OnCard, record
from ..config import AIConfig
from ..prompts import SYSTEM_PROMPT

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
    # 5xx errors (mostly 503 "model overloaded") are frequent and short-lived:
    # the SDK retries with exponential backoff before giving up.
    return genai.Client(
        **s.gemini_options(),
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(attempts=3, initial_delay=2, http_status_codes=[500, 502, 503, 504])
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


class _Stalled(Exception):
    """The model stopped answering."""


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
    from google.genai import errors, types

    client = _gemini_client(s)
    told = 0  # cards told to on_card

    async def within(seconds: float, awaitable):
        try:
            return await asyncio.wait_for(awaitable, seconds)
        except TimeoutError:
            raise _Stalled from None

    async def generate(model: str):
        """The model's answer; written as it comes when the cards are wanted at once."""
        nonlocal told
        if on_card is None:
            return await within(
                WHOLE_ANSWER_S, client.aio.models.generate_content(model=model, contents=contents, config=config)
            )
        if told:  # another model starts again
            await on_card(None)
            told = 0
        chunks, cards = [], CardStream()
        stream = await within(
            FIRST_PART_S, client.aio.models.generate_content_stream(model=model, contents=contents, config=config)
        )
        parts, wait = aiter(stream), FIRST_PART_S
        try:
            while True:
                try:
                    chunk = await within(wait, anext(parts))
                except StopAsyncIteration:
                    break
                wait = NEXT_PART_S
                chunks.append(chunk)
                for card in cards.feed(chunk.text or ""):
                    await on_card(card)
                    told += 1
        finally:
            with suppress(Exception):  # given up on: the connection goes too
                await stream.aclose()
        return _joined(chunks)

    contents = [types.Part.from_bytes(data=img.data, mime_type=img.media_type) for img in images]
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

    def thinking(model: str):
        if not ((light or quick) and model.startswith("gemini-3")):  # older models set thinking otherwise
            return None
        if quick:
            return types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)
        level = types.ThinkingLevel.LOW if model in _NO_MINIMAL_THINKING else types.ThinkingLevel.MINIMAL
        return types.ThinkingConfig(thinking_level=level)

    for model in models:
        try:
            config.thinking_config = thinking(model)
            try:
                response = await generate(model)
            except errors.ClientError as e:
                if not (config.thinking_config and e.code == 400 and "Thinking level" in str(e.message)):
                    raise
                _NO_MINIMAL_THINKING.add(model)  # this model thinks a little at least: "low" from now on
                config.thinking_config = thinking(model)
                response = await generate(model)
            break
        except errors.ClientError as e:
            log.warning("Gemini %s : %s %s", model, e.code, e.message)
            if e.code in (401, 403) or "API key" in str(e):
                raise ExtractionError("llm.invalid_key", provider="Gemini") from e
            if e.code == 429:
                # A free key has no quota for the latest models, and a quota of its own
                # for each model: the next one may still answer
                if model != models[-1]:
                    log.warning("Quota exceeded: falling back to the next model")
                    continue
                raise ExtractionError("llm.gemini_quota") from e
            raise ExtractionError("llm.api_error", provider="Gemini", status=e.code, detail=e.message) from e
        except errors.APIError as e:
            log.warning("Gemini %s : %s %s", model, e.code, e.message)
            if model == models[-1]:
                raise ExtractionError("llm.overloaded", provider="Gemini", status=e.code) from e
            log.warning("Falling back to the next model")
        except _Stalled:
            log.warning("Gemini %s stopped answering", model)
            if model == models[-1]:
                raise ExtractionError("llm.timeout", provider="Gemini") from None
            log.warning("Falling back to the next model")

    usage = response.usage_metadata
    if usage:
        output = (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)  # thinking is billed too
        await record(s, "gemini", model, usage.prompt_token_count, output)
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


def _joined(chunks: list):
    """A streamed answer as one: its whole text, the last usage and candidate (where the
    finish reason is), the first prompt feedback (where a block is said)."""
    return SimpleNamespace(
        text="".join(c.text or "" for c in chunks),
        usage_metadata=next((c.usage_metadata for c in reversed(chunks) if c.usage_metadata), None),
        candidates=next((c.candidates for c in reversed(chunks) if c.candidates), None),
        prompt_feedback=next((c.prompt_feedback for c in chunks if c.prompt_feedback), None),
    )
