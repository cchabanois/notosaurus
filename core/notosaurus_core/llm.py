"""Card extraction with a vision model.

A single interface, `extract_cards`, and a provider chosen in the AI configuration
(config.AIConfig, passed to every call):

- "gemini" (default): Gemini, through the official google-genai SDK (providers/gemini.py).
- "anthropic": Claude, through the official SDK (providers/anthropic.py).
- "openai":     OpenAI itself (GPT).
- "openrouter": OpenRouter, every provider's models with one key.
- "compatible": any other OpenAI-compatible service at its address (Ollama, LM Studio,
  Mistral…); these three in providers/openai_like.py.
- "fake":      the demo AI: canned cards, to work on the UI without a key or any cost
  (providers/demo.py).

What the AI is told is in prompts.py; what every call shares (photos, errors, the
calls recorded, the cards streamed) in calls.py.
"""

import logging

from pydantic import BaseModel

from . import ai, diagrams
from .ai import (  # noqa: F401 (llm's API)
    CLAUDE_REQUIRED,
    SET_BY_NOTOSAURUS,
    _CheckAnswer,
    ai_schema,
    check,
    for_claude,
)
from .calls import (  # noqa: F401 (llm's API)
    CardStream,
    ExtractionError,
    Image,
    OnCard,
    record,
    recording,
    tell,
    telling,
)
from .cards import blank_dictations, plain_cards, without_repeats
from .cards import plain as plain_text
from .config import AIConfig
from .correction import _keep_ids, _keep_masks, _same_card, fix_card, revise_cards  # noqa: F401 (llm's API)
from .errors import loggable
from .figure_making import MadeFigure, _figure_family, check_figure, draw_figure, made_figure  # noqa: F401 (llm's API)
from .models import (  # noqa: F401 (llm's API)
    Card,
    Deck,
    Explanation,
    Extraction,
    Figures,
    FixedCard,
    Frame,
    Revision,
)
from .prompts import FIGURES_RULES, ExtractOptions, _figures_text, _user_text
from .providers import demo as demo_ai
from .providers.openai_like import list_models  # noqa: F401 (llm's API)
from .tasks import (  # noqa: F401 (llm's API)
    explain_card,
    find_drawings,
    pick_picture,
    plan_picture,
    rephrase,
    search_words,
    sort_pictures,
    transcribe,
)

log = logging.getLogger("notosaurus")


class Extracted(BaseModel):
    deck: Deck
    # Always 0 now: no turn guessed (the AI named a line's direction wrongly, a photo turned
    # upside down; ↻ turns one). Kept for the apps reading /v1/extract's (1.1.0)
    turns: list[int]
    frames: list[Frame]  # diagram frames, as fractions of the photos (not turned yet)
    back_language: str = ""  # "es-ES": for a prompt whose voice is "auto"
    choice: str = ""  # what the AI chose to make (prompt "Automatic")
    dictation: bool = False  # dictation cards alone: asked, or chosen (prompt "Automatic")
    dictation_card: bool = False  # the instructions ask for a dictation of each card too
    typing: bool = False  # the instructions ask for the answers to be typed
    reverse: bool = False  # the instructions ask for the reverse card too
    read_aloud: bool = False  # the instructions ask for the backs to be heard, even in the pupil's own language
    speed: str = ""  # how fast the instructions ask for the backs to be read: "slow", "normal", "" not said


async def extract_cards(
    s: AIConfig,
    images: list[Image],
    prompt: str,
    options: ExtractOptions | None = None,
    on_card: OnCard | None = None,
) -> Extracted:
    """The lesson's cards from its photos (or from the prompt alone), made as `options`
    says (prompts.ExtractOptions; None: the defaults); `on_card`: each card as soon as it
    is written (see _ask_provider)."""
    options = options or ExtractOptions()
    fmt = ai._box_format(s)
    images, sizes = ai._prepare(images)
    text = options.instructions + _user_text(prompt, options, len(images), sizes, fmt)
    fun_facts, helps = options.fun_facts, options.helps
    schema = ai.ai_schema(Extraction, fun_facts, helps, ai.for_claude(s))
    answer = await ai._ask_provider(
        s,
        images,
        text,
        schema,
        quick=options.quick,
        on_card=on_card,
        demo=lambda: demo_ai.extraction(images, prompt, fun_facts, helps),
    )
    result = Extraction.model_validate(ai._accepted(answer).model_dump())
    plain_cards(result.cards)  # a tag the AI wrote all the same would show as it is
    result.cards = without_repeats(result.cards)  # an AI caught in a loop
    if result.dictation:  # a dictation alone: no front giving its answer away
        blank_dictations(result.cards)
    diagrams.normalize(result.cards, sizes, fmt)
    await _complete_figures(s, images, result.cards)
    return Extracted(
        deck=Deck(deck=plain_text(result.deck), cards=result.cards),
        turns=[0] * len(images),
        frames=diagrams.frames(result.frames, sizes, fmt),
        back_language=result.back_language.strip(),
        choice=plain_text(result.choice).strip(),
        dictation=result.dictation,
        dictation_card=result.dictation_card,
        typing=result.typing,
        reverse=result.reverse,
        read_aloud=result.read_aloud,
        speed=result.speed,
    )


async def _complete_figures(s: AIConfig, images: list[Image], cards: list[Card]) -> None:
    """Cards whose picture goes on the back but that have neither picture nor figure: the
    model decided on a figure but left it undescribed (it happens now and then, more when
    it thinks little). One light call, seeing the lesson's pages, describes them; a card
    still without one stands as it is."""
    todo = [c for c in cards if c.picture_on_back and not (c.figure.strip() or c.picture_prompt.strip() or c.mask)]
    if not todo:
        return
    text = _figures_text([f"{c.front.strip()} → {c.back.strip()}" for c in todo])
    tell({"step": "figures"})
    try:
        found = await ai._ask_provider(s, images, text, Figures, FIGURES_RULES, light=True, demo=Figures)
    except ExtractionError as e:
        log.warning("Figures left undescribed (%d cards): %s", len(todo), loggable(e))
        return
    for item in found.figures:
        if 0 <= item.card < len(todo) and item.figure.strip():
            todo[item.card].figure = item.figure.strip()
            todo[item.card].figure_kind = item.figure_kind
