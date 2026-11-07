"""What every call to the AI shares: the request's schema (what the AI fills of a card),
the photos as the model sees them, the provider chosen (config.AIConfig) and asked, the
user told when it is slow, and the check of a model (the setup's "Test").

Called as `ai._ask_provider(...)`, never imported by name, by llm.py, figure_making.py,
tasks.py and correction.py: a test replaces it here once, for all of them."""

import asyncio
import logging
from collections.abc import Callable
from functools import cache
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, create_model

from . import config, diagrams
from .calls import ExtractionError, Image, OnCard, tell
from .config import AIConfig
from .models import Card
from .prompts import SYSTEM_PROMPT
from .providers import anthropic, gemini, openai_like
from .providers import demo as demo_ai

log = logging.getLogger("notosaurus")
SLOW_S = 20  # an answer not started by then: the user told it's slow (calls.tell)
SLOW_THINKING_S = 45  # the same when the model thinks (a careful lesson): longer at first

# What the AI sees of a card: what it fills, and only that. Anthropic refuses a response
# schema with too many optional fields ("Schema is too complex"): the fields Notosaurus
# sets itself are left out, and the ones only some requests ask for (fun facts, helps)
# are there only then.
SET_BY_NOTOSAURUS = {"picture", "picture_source", "id", "voice"}


# Claude's structured outputs refuse a schema past 20 optional fields ("Schema is too
# complex"): for Claude, these card fields are required, written empty ("", false) when
# they don't apply, as they read when left out. Not the helps and the fun fact: required,
# a model would write one on every card.
CLAUDE_REQUIRED = ("subdeck", "info", "figure", "picture_search", "picture_on_back")


def for_claude(s: AIConfig) -> bool:
    """A Claude model answers: Anthropic's API, or Claude through OpenRouter."""
    return s.llm == "anthropic" or (
        s.llm in config.OPENAI_LIKE and s.model_for_provider().lstrip("~").startswith("anthropic/")
    )


@cache
def ai_schema(
    base: type[BaseModel], fun_facts: bool = False, helps: bool = False, claude: bool = False
) -> type[BaseModel]:
    """`base` (Extraction, Revision) as the AI fills it: another model, turned back into
    `base` with `base.model_validate(answer.model_dump())`. `claude`: within Claude's limit
    (CLAUDE_REQUIRED)."""
    left_out = set(SET_BY_NOTOSAURUS)
    left_out |= set() if fun_facts else {"fun_fact"}
    left_out |= set() if helps else {"explanation", "mnemonic"}
    # Field name → (annotation, FieldInfo), as create_model takes them
    card_fields: dict[str, Any] = {k: (f.annotation, f) for k, f in Card.model_fields.items() if k not in left_out}

    # figure_kind required in the schema the AI is given ("" without a figure): an optional
    # field more would pass Claude's limit; an answer without it still read (its default)
    def required(schema: dict[str, Any]) -> None:
        schema.setdefault("required", []).append("figure_kind")
        if claude:
            schema["required"] += [k for k in CLAUDE_REQUIRED if k in card_fields]

    config = ConfigDict(json_schema_extra=required)  # pyright: ignore[reportArgumentType]
    card = create_model("Card", __doc__=Card.__doc__, __config__=config, **card_fields)
    fields: dict[str, Any] = {k: (f.annotation, f) for k, f in base.model_fields.items() if k != "cards"}
    # Decided first, before any card: last, a model that wrote cards of an ordinary lesson
    # (a history course's war) could still turn back on them and refuse
    refused = (
        bool,
        Field(
            default=False,
            description="Decide this first, from the rules: true when the request must be refused (then no "
            "cards); false for any genuine lesson, whatever its topic.",
        ),
    )
    cards: Any = (list[card], Field())  # Any: a model built at run time, not a type pyright can check
    return create_model(base.__name__, __doc__=base.__doc__, refused=refused, cards=cards, **fields)


def _box_format(s: AIConfig) -> str:
    """How the provider's model gives diagram boxes (diagrams.FORMATS)."""
    return demo_ai.BOX_FORMAT if s.llm == "fake" else diagrams.box_format(s.model_for_provider())


def _accepted[T: BaseModel](answer: T) -> T:
    """The AI's answer, unless it refused the request (SAFETY): llm.refused."""
    if getattr(answer, "refused", False):
        raise ExtractionError("llm.refused")
    return answer


def _prepare(images: list[Image]) -> tuple[list[Image], list[tuple[int, int] | None]]:
    """Photos as the model will see them, and their sizes (for boxes in pixels)."""
    prepared, sizes = [], []
    for img in images:
        data, media_type, size = diagrams.prepare(img.data, img.media_type)
        prepared.append(Image(data, media_type))
        sizes.append(size)
    return prepared, sizes


async def _ask_provider[T: BaseModel](
    s: AIConfig,
    images: list[Image],
    text: str,
    schema: type[T],
    system: str = SYSTEM_PROMPT,
    light: bool = False,
    quick: bool = False,
    on_card: OnCard | None = None,
    demo: Callable[[], T] | None = None,
) -> T:
    """Send photos + text to the configured provider and parse the answer as `schema`.
    `system`: the fixed rules (the cards' by default). `light`: a task that needs little
    thinking (drawing a figure described precisely): the model thinks as little as it
    can, where the service lets us say so — cheaper and faster. `quick`: a lesson made
    fast (the page's "Quick"): the model thinks little ("low"), 2 to 4 times faster,
    a little less careful on rich lessons (a figure, maths). `on_card`: each card as soon
    as it is written (Gemini and the demo; the other services answer all at once).
    `demo`: the demo AI's answer to this request, built from what it was made of (the
    prompt, the card…): see providers/demo.py."""
    if s.llm == "fake":
        return await demo_ai._demo(s, demo, on_card)
    # Not a word after a while (a model busy, stalled): said, the user knows it's not stuck
    after = SLOW_S if light or quick else SLOW_THINKING_S
    slow = asyncio.get_running_loop().call_later(after, tell, {"step": "slow"})
    try:
        return await _provider(s, images, text, schema, system, light, quick, on_card)
    finally:
        slow.cancel()


async def _provider[T: BaseModel](
    s: AIConfig,
    images: list[Image],
    text: str,
    schema: type[T],
    system: str,
    light: bool,
    quick: bool,
    on_card: OnCard | None,
) -> T:
    if s.llm == "gemini":
        return await gemini._gemini(s, images, text, schema, system, light, quick, on_card)
    if s.llm == "anthropic":
        return await anthropic._anthropic(s, images, text, schema, system)  # Claude only thinks when asked to
    if s.llm in config.OPENAI_LIKE:
        return await openai_like._openai(s, images, text, schema, system, light, quick)
    raise ExtractionError("llm.unknown_provider", provider=s.llm)


def _test_image() -> bytes:
    """A 32×32 plain red PNG, built without an image library."""
    import struct
    import zlib

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    size = 32
    rows = b"".join(b"\x00" + b"\xdc\x14\x14" * size for _ in range(size))  # filter byte + RGB pixels
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit RGB
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


class _CheckAnswer(BaseModel):
    color: str


async def check(s: AIConfig) -> dict:
    """Check what Notosaurus needs from the model: reading an image and answering
    in the requested JSON format. Sends a tiny red image (a fraction of a cent).

    Returns {"vision": bool, "json": bool, "answer": str}, with "model" and "quota" (the
    chosen model) when a Gemini fallback answered instead; raises ExtractionError
    when the service itself fails (key, address, model name…)."""
    try:
        return await _check_model(s.model_copy(update={"fallback_models": ""}))  # the chosen model, not a fallback
    except ExtractionError as e:
        if e.code != "llm.gemini_quota":
            raise
        # Gemini without quota for the chosen model (a free key and the latest model): the
        # cards will come from a fallback, if one answers. Said with the model that did.
        for fallback in [m.strip() for m in s.fallback_models.split(",") if m.strip()]:
            try:
                found = await _check_model(s.model_copy(update={"model": fallback, "fallback_models": ""}))
            except ExtractionError as again:
                if again.code != "llm.gemini_quota":
                    raise
                continue
            return {**found, "model": fallback, "quota": s.model_for_provider()}
        raise


async def _check_model(only_main_model: AIConfig) -> dict:
    prompt = "What is the main colour of this image? Answer with one lowercase English word."
    try:
        image = Image(_test_image(), "image/png")
        answer = await _ask_provider(
            only_main_model, [image], prompt, _CheckAnswer, demo=lambda: _CheckAnswer(color="red")
        )
    except ExtractionError as e:
        if e.code in ("llm.invalid_answer", "llm.truncated"):
            return {"vision": False, "json": False, "answer": ""}  # answered, but not in the JSON format
        detail = str(e.params.get("detail", "")).lower()
        if e.params.get("status") == 400 and any(w in detail for w in ("image", "multimodal", "vision")):
            # e.g. Ollama: "model does not support multimodal requests"
            return {"vision": False, "json": None, "answer": "", "refused": e.params["detail"]}
        raise
    return {"vision": "red" in answer.color.lower(), "json": True, "answer": answer.color.strip()[:40]}
