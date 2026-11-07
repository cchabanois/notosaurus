"""The AI's small tasks around a lesson, each a light call: a card explained, a dictation
transcribed, instructions tidied up, a picture picked or planned, the lesson's own drawings
found."""

from collections.abc import Sequence

from . import ai, config, diagrams
from .calls import ExtractionError, Image
from .config import AIConfig
from .models import Card, Dictation, Drawings, Explanation, Picked, PicturePlan, Rephrased, SearchWords, Sorted
from .prompts import (
    DICTATION_RULES,
    DRAWINGS_RULES,
    EXPLAIN_RULES,
    PICK_RULES,
    PLAN_RULES,
    REPHRASE_RULES,
    SEARCH_WORDS_RULES,
    SORT_RULES,
    _dictation_text,
    _drawings_text,
    _explain_text,
    _pick_text,
    _plan_text,
    _rephrase_text,
    _search_words_text,
)
from .providers import demo as demo_ai


async def explain_card(
    s: AIConfig,
    card: Card,
    kind: str,
    prompt: str,
    deck: str,
    language: str = "English",
    instructions: str = "",
    page_texts: Sequence[str] = (),
) -> Explanation:
    """A short explanation of a card for the pupil (or an example, a way to remember it,
    why the answer is right), and the follow-ups worth offering. A light call: no photo.

    `language`: its English name ("French"); `instructions`: see prompts.ExtractOptions."""
    text = instructions + _explain_text(card, kind, prompt, deck, language, page_texts)
    found = await ai._ask_provider(
        s, [], text, Explanation, EXPLAIN_RULES, light=True, demo=lambda: demo_ai.explanation(card, kind)
    )
    found.more = list(dict.fromkeys(k for k in found.more if k != kind))
    return found


async def transcribe(s: AIConfig, audio: Image, kind: str, language: str = "English") -> str:
    """A dictation as the text its speaker meant to type (models.Dictated `kind`: a
    lesson's instructions or a correction): their words, hesitations out, their own
    corrections applied, a lesson's foreign words spelled right. Gemini only: it hears
    the recording itself (the others take no audio).

    `audio`: the recording (audio/aac, ogg, mpeg, wav, flac); `language`: the app's,
    its English name ("French")."""
    if s.llm not in config.HEARS_AUDIO:
        raise ExtractionError("llm.no_audio", provider=s.llm)
    text = _dictation_text(kind, language)
    found = await ai._ask_provider(
        s, [audio], text, Dictation, DICTATION_RULES, light=True, demo=lambda: demo_ai.dictation(kind)
    )
    return found.text.strip()


async def rephrase(s: AIConfig, text: str, language: str = "English") -> str:
    """A lesson's instructions tidied up ("✨ Tidy up"): clear and short, in their own
    language, every intention kept and none added. A light call, text only.

    `language`: the app's, its English name ("French")."""
    asked = _rephrase_text(text, language)
    found = await ai._ask_provider(
        s, [], asked, Rephrased, REPHRASE_RULES, light=True, demo=lambda: demo_ai.rephrased(text)
    )
    return found.text.strip()


async def pick_picture(s: AIConfig, candidates: list[Image], search: str, context: str) -> int | None:
    """Which of the pictures found (their previews, in order) fits a card: its index, or
    None when none does. `context`: the card, as "front → back"."""
    text = _pick_text(search, context, len(candidates))
    found = await ai._ask_provider(s, candidates, text, Picked, PICK_RULES, light=True, demo=demo_ai.picked)
    return found.choice if 0 <= found.choice < len(candidates) else None


async def find_drawings(s: AIConfig, images: list[Image], cards: list[str]) -> dict[int, tuple[int, list[float]]]:
    """The drawings of their own the lesson's pages show for these cards ("front → back"),
    in one light call: {card's index: (its page, from 0; its box, [x0, y0, x1, y1] fractions
    of the page)}; none found: {}."""
    if not images or not cards:
        return {}
    prepared, sizes = ai._prepare(images)
    fmt = ai._box_format(s)
    found = await ai._ask_provider(
        s, prepared, _drawings_text(cards, fmt, sizes), Drawings, DRAWINGS_RULES, light=True, demo=Drawings
    )
    drawings: dict[int, tuple[int, list[float]]] = {}
    for item in found.drawings:
        page = item.page - 1
        size = sizes[page] if 0 <= page < len(sizes) else None
        box = diagrams.fractions(item.box, size, fmt) if size and 0 <= item.card < len(cards) else None
        if box:
            drawings.setdefault(item.card, (page, box))
    return drawings


async def sort_pictures(s: AIConfig, candidates: list[Image], search: str, context: str = "") -> list[int]:
    """Which of the pictures found (their previews, in order) show what was searched for,
    the best first: their indexes, none when none does. `context`: the card, as
    "front → back" ("": none)."""
    text = _pick_text(search, context, len(candidates))
    found = await ai._ask_provider(
        s, candidates, text, Sorted, SORT_RULES, light=True, demo=lambda: demo_ai.sorted_pictures(len(candidates))
    )
    return list(dict.fromkeys(i for i in found.fitting if 0 <= i < len(candidates)))


async def plan_picture(s: AIConfig, front: str, back: str, asked: str = "", language: str = "English") -> PicturePlan:
    """What a card's picture should be ("🎨 Draw" in its panel): an exact figure or an image
    model's picture, described from the card and what the user wrote (any language; empty:
    the card alone). `language`: the cards', its English name."""
    text = _plan_text(front, back, asked, language)
    plan = await ai._ask_provider(
        s, [], text, PicturePlan, PLAN_RULES, light=True, demo=lambda: demo_ai.picture_plan(back, asked)
    )
    plan.description, plan.search = plan.description.strip(), plan.search.strip()
    return plan


async def search_words(s: AIConfig, asked: str, context: str = "") -> str:
    """A few English words to search free pictures of what the user wrote (any language,
    maybe LaTeX); `context`: the card, "front → back"."""
    text = _search_words_text(asked, context)
    found = await ai._ask_provider(
        s, [], text, SearchWords, SEARCH_WORDS_RULES, light=True, demo=lambda: demo_ai.search_words(asked)
    )
    return found.words.strip() or asked.strip()
