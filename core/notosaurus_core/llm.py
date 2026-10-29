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

import asyncio
import logging
from collections.abc import Callable, Sequence
from functools import cache
from typing import Any, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, create_model

from . import config, diagrams
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
from .cards import plain as plain_text
from .cards import plain_cards
from .config import AIConfig
from .errors import loggable
from .models import (
    Card,
    CardFix,
    Deck,
    Dictation,
    Drawings,
    Explanation,
    Extraction,
    Figures,
    FixedCard,
    Frame,
    Picked,
    PicturePlan,
    Rephrased,
    Revision,
    SearchWords,
    Sorted,
)
from .prompts import (
    DICTATION_RULES,
    DRAWINGS_RULES,
    EXPLAIN_RULES,
    FIGURES_RULES,
    PICK_RULES,
    PLAN_RULES,
    REPHRASE_RULES,
    SEARCH_WORDS_RULES,
    SORT_RULES,
    SYSTEM_PROMPT,
    ExtractOptions,
    _dictation_text,
    _drawings_text,
    _explain_text,
    _figures_text,
    _fix_text,
    _pick_text,
    _plan_text,
    _rephrase_text,
    _revision_text,
    _search_words_text,
    _user_text,
)
from .providers import anthropic, gemini, openai_like
from .providers import demo as demo_ai
from .providers.openai_like import list_models  # noqa: F401 (llm's API)

log = logging.getLogger("notosaurus")
SLOW_S = 20  # an answer not started by then: the user told it's slow (calls.tell)
SLOW_THINKING_S = 45  # the same when the model thinks (a careful lesson): longer at first

# What the AI sees of a card: what it fills, and only that. Anthropic refuses a response
# schema with too many optional fields ("Schema is too complex"): the fields Notosaurus
# sets itself are left out, and the ones only some requests ask for (fun facts, helps)
# are there only then.
SET_BY_NOTOSAURUS = {"picture", "picture_source", "id", "voice"}


@cache
def ai_schema(base: type[BaseModel], fun_facts: bool = False, helps: bool = False) -> type[BaseModel]:
    """`base` (Extraction, Revision) as the AI fills it: another model, turned back into
    `base` with `base.model_validate(answer.model_dump())`."""
    left_out = set(SET_BY_NOTOSAURUS)
    left_out |= set() if fun_facts else {"fun_fact"}
    left_out |= set() if helps else {"explanation", "mnemonic"}
    # Field name → (annotation, FieldInfo), as create_model takes them
    card_fields: dict[str, Any] = {k: (f.annotation, f) for k, f in Card.model_fields.items() if k not in left_out}

    # figure_kind required in the schema the AI is given ("" without a figure): an optional
    # field more would pass Claude's limit; an answer without it still read (its default)
    def required(schema: dict[str, Any]) -> None:
        schema.setdefault("required", []).append("figure_kind")

    config = ConfigDict(json_schema_extra=required)  # pyright: ignore[reportArgumentType]
    card = create_model("Card", __doc__=Card.__doc__, __config__=config, **card_fields)
    fields: dict[str, Any] = {k: (f.annotation, f) for k, f in base.model_fields.items() if k != "cards"}
    refused = (bool, Field(default=False, description="True when the request must be refused (see the rules)."))
    cards: Any = (list[card], Field())  # Any: a model built at run time, not a type pyright can check
    return create_model(base.__name__, __doc__=base.__doc__, cards=cards, **fields, refused=refused)


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


class Extracted(BaseModel):
    deck: Deck
    turns: list[int]  # clockwise turn that puts each photo upright
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
    fmt = _box_format(s)
    images, sizes = _prepare(images)
    text = options.instructions + _user_text(prompt, options, len(images), sizes, fmt)
    fun_facts, helps = options.fun_facts, options.helps
    schema = ai_schema(Extraction, fun_facts, helps)
    answer = await _ask_provider(
        s,
        images,
        text,
        schema,
        quick=options.quick,
        on_card=on_card,
        demo=lambda: demo_ai.extraction(images, prompt, fun_facts, helps),
    )
    result = Extraction.model_validate(_accepted(answer).model_dump())
    plain_cards(result.cards)  # a tag the AI wrote all the same would show as it is
    diagrams.normalize(result.cards, sizes, fmt)
    await _complete_figures(s, images, result.cards)
    return Extracted(
        deck=Deck(deck=plain_text(result.deck), cards=result.cards),
        turns=diagrams.turns(result.text_lines, sizes, fmt),
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
        found = await _ask_provider(s, images, text, Figures, FIGURES_RULES, light=True, demo=Figures)
    except ExtractionError as e:
        log.warning("Figures left undescribed (%d cards): %s", len(todo), loggable(e))
        return
    for item in found.figures:
        if 0 <= item.card < len(todo) and item.figure.strip():
            todo[item.card].figure = item.figure.strip()
            todo[item.card].figure_kind = item.figure_kind


# A light drawing that can't be used: drawn again with the model's thinking
_UNUSABLE = {"llm.invalid_answer", "llm.truncated", "llm.empty_answer", "figure.invalid"}


class MadeFigure(NamedTuple):
    """A figure drawn (made_figure): its SVG, cleaned, and how: "typst" (its family's
    packages) or "svg"; its family; with the model's thinking or not."""

    svg: str
    engine: Literal["typst", "svg"]
    family: str
    careful: bool


async def draw_figure(
    s: AIConfig,
    description: str,
    step: Callable[[dict], Any] | None = None,
    kind: str = "",
    problem: str = "",
    careful: bool = False,
) -> str:
    """The SVG of a figure (made_figure's)."""
    return (await made_figure(s, description, step, kind, problem, careful)).svg


async def made_figure(
    s: AIConfig,
    description: str,
    step: Callable[[dict], Any] | None = None,
    kind: str = "",
    problem: str = "",
    careful: bool = False,
) -> MadeFigure:
    """A figure, its SVG cleaned (figures.clean) and how it was made, drawn by the cards' AI: in Typst
    (figures_typst.py: a curve computed from its function, marks from their points, angles
    by angle-mark), else as SVG (figures.py). Drawn quickly (light calls), not checked: the
    user checks it when in doubt (check_figure). A light drawing that can't be used: drawn
    again with the model's thinking. `problem`: what the check found in the last one, told
    to the AI: drawn quickly again (told the problem, it mostly gets it right: 9 times in 12,
    10 with thinking, four times slower), with the model's thinking when `careful` (the user
    asks it again after a quick one still wrong). `step`: told each step as it
    begins (relay_api.PictureStep). `kind`: its family, when the AI that described it said it
    (Card.figure_kind): not asked again."""
    from . import figures

    tell = step or (lambda _: None)
    text = f"Figure to draw: {description.strip()}"
    family = await _figure_family(s, description, kind)
    if problem.strip():
        text += f"\n\nA first drawing had this problem: {problem.strip()} Draw it right."
        if careful:
            tell({"step": "redrawing", "problem": problem.strip()})
            return await _drawn(s, text, description, family, light=False)
    tell({"step": "drawing"})
    try:
        return await _drawn(s, text, description, family, light=True)
    except (ExtractionError, figures.FigureError) as e:
        if e.code not in _UNUSABLE:
            raise
        log.warning("Figure drawn again with thinking: %s", loggable(e))
    tell({"step": "redrawing", "problem": ""})
    return await _drawn(s, text, description, family, light=False)


async def check_figure(s: AIConfig, description: str, svg: str) -> str:
    """What is wrong in a figure, seen as a picture against its description (the user asked
    it: the "🔍 Check" button); "" when it looks right. figure.invalid: it can't be seen."""
    from . import figures

    png = figures.to_png(figures.clean(svg))
    if png is None:
        raise figures.FigureError("figure.invalid")
    checked = await _ask_provider(
        s,
        [Image(png, "image/png")],
        f"Description: {description.strip()}",
        figures.Checked,
        figures.CHECK_RULES,
        light=True,
        demo=lambda: figures.Checked(ok=True, problem=""),
    )
    return "" if checked.ok else (checked.problem.strip() or "It doesn't match its description.")


async def _figure_family(s: AIConfig, description: str, kind: str = "") -> str:
    """Which family of figures_typst draws it: `kind` when given (the AI that described it
    said it), else a light call; "other" (drawn as SVG): none of them, Typst not installed,
    the demo, or not told."""
    from . import figures_typst

    if s.llm == "fake" or not figures_typst.available():
        return "other"
    if kind in figures_typst.FAMILIES or kind == "other":
        return kind
    try:
        picked = await _ask_provider(
            s, [], f"Figure: {description.strip()}", figures_typst.Kind, figures_typst.FAMILY_RULES, light=True
        )
    except ExtractionError as e:
        if e.code not in _UNUSABLE:
            raise
        return "other"
    return picked.family


async def _drawn(s: AIConfig, text: str, description: str, family: str, light: bool) -> MadeFigure:
    """A figure drawn once, cleaned: in Typst with its family's package and rule (asked again
    once, told what Typst said, when it doesn't compile), else as SVG (family "other", Typst
    refusing it twice; the demo)."""
    from . import figures, figures_typst

    if family in figures_typst.FAMILIES:
        rules = figures_typst.FAMILIES[family].rules + figures_typst.COMMON
        asked = text
        for _ in range(2):
            try:
                body = (await _ask_provider(s, [], asked, figures_typst.Figure, rules, light=light)).typst
            except ExtractionError as e:
                if e.code not in _UNUSABLE:
                    raise
                break
            try:
                svg = figures.clean(await asyncio.to_thread(figures_typst.compile_svg, family, body))
                return MadeFigure(svg, "typst", family, not light)
            except (figures_typst.Unusable, figures.FigureError) as e:
                said = str(e) if isinstance(e, figures_typst.Unusable) else "its SVG was unusable"
                asked = (
                    f"{text}\n\nYour previous answer didn't compile:\n{body}\n\n"
                    f"Typst said: {said}\n\nAnswer it again, corrected."
                )
        log.warning("Figure drawn as SVG: Typst refused it")
    demo = lambda: demo_ai.figure(description)  # noqa: E731
    drawing = await _ask_provider(s, [], text, figures.Drawing, figures.RULES, light=light, demo=demo)
    return MadeFigure(figures.clean(drawing.svg), "svg", family, not light)


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
    found = await _ask_provider(
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
    found = await _ask_provider(
        s, [audio], text, Dictation, DICTATION_RULES, light=True, demo=lambda: demo_ai.dictation(kind)
    )
    return found.text.strip()


async def rephrase(s: AIConfig, text: str, language: str = "English") -> str:
    """A lesson's instructions tidied up ("✨ Tidy up"): clear and short, in their own
    language, every intention kept and none added. A light call, text only.

    `language`: the app's, its English name ("French")."""
    asked = _rephrase_text(text, language)
    found = await _ask_provider(
        s, [], asked, Rephrased, REPHRASE_RULES, light=True, demo=lambda: demo_ai.rephrased(text)
    )
    return found.text.strip()


async def pick_picture(s: AIConfig, candidates: list[Image], search: str, context: str) -> int | None:
    """Which of the pictures found (their previews, in order) fits a card: its index, or
    None when none does. `context`: the card, as "front → back"."""
    text = _pick_text(search, context, len(candidates))
    found = await _ask_provider(s, candidates, text, Picked, PICK_RULES, light=True, demo=demo_ai.picked)
    return found.choice if 0 <= found.choice < len(candidates) else None


async def find_drawings(s: AIConfig, images: list[Image], cards: list[str]) -> dict[int, tuple[int, list[float]]]:
    """The drawings of their own the lesson's pages show for these cards ("front → back"),
    in one light call: {card's index: (its page, from 0; its box, [x0, y0, x1, y1] fractions
    of the page)}; none found: {}."""
    if not images or not cards:
        return {}
    prepared, sizes = _prepare(images)
    fmt = _box_format(s)
    found = await _ask_provider(
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
    found = await _ask_provider(
        s, candidates, text, Sorted, SORT_RULES, light=True, demo=lambda: demo_ai.sorted_pictures(len(candidates))
    )
    return list(dict.fromkeys(i for i in found.fitting if 0 <= i < len(candidates)))


async def plan_picture(s: AIConfig, front: str, back: str, asked: str = "", language: str = "English") -> PicturePlan:
    """What a card's picture should be ("🎨 Draw" in its panel): an exact figure or an image
    model's picture, described from the card and what the user wrote (any language; empty:
    the card alone). `language`: the cards', its English name."""
    text = _plan_text(front, back, asked, language)
    plan = await _ask_provider(
        s, [], text, PicturePlan, PLAN_RULES, light=True, demo=lambda: demo_ai.picture_plan(back, asked)
    )
    plan.description, plan.search = plan.description.strip(), plan.search.strip()
    return plan


async def search_words(s: AIConfig, asked: str, context: str = "") -> str:
    """A few English words to search free pictures of what the user wrote (any language,
    maybe LaTeX); `context`: the card, "front → back"."""
    text = _search_words_text(asked, context)
    found = await _ask_provider(
        s, [], text, SearchWords, SEARCH_WORDS_RULES, light=True, demo=lambda: demo_ai.search_words(asked)
    )
    return found.words.strip() or asked.strip()


async def revise_cards(
    s: AIConfig,
    images: list[Image],
    prompt: str,
    deck: Deck,
    instruction: str,
    language: str = "English",
    instructions: str = "",
    demo: dict[str, str] | None = None,
) -> Revision:
    """Apply a natural-language correction ("remove…", "you forgot…") to the cards.

    `language`: English name of the page's language ("French"), for the one-line
    summary; `instructions`: see prompts.ExtractOptions; `demo`: the demo provider's texts in
    that language ("removed", "added", "addedFront"; English by default)."""
    # The existing masks stay out of the conversation (their boxes are in our own
    # format): the revised cards get back the mask of the card they were. New cards
    # about a diagram label come with a mask in the model's format.
    fmt = _box_format(s)
    images, sizes = _prepare(images)
    labels: dict[int, list[int]] = {}
    for card in deck.cards:
        if card.mask:
            labels.setdefault(card.mask.page, []).append(card.mask.n)
    plain = Deck(
        deck=deck.deck,
        cards=[c.model_copy(update={"mask": None, "picture": "", "id": "", "voice": ""}) for c in deck.cards],
    )
    text = instructions + _revision_text(prompt, plain, instruction, language, len(images), sizes, fmt, labels)
    # The fun facts and helps already there are kept: the AI sees them
    texts = {**demo_ai.DEMO, **(demo or {})}
    answer = await _ask_provider(
        s,
        images,
        text,
        ai_schema(Revision, fun_facts=True, helps=True),
        demo=lambda: demo_ai.revision(deck, instruction, texts),
    )
    revision = Revision.model_validate(_accepted(answer).model_dump())
    plain_cards(revision.cards)
    revision.summary = plain_text(revision.summary)
    _keep_masks(revision.cards, deck.cards, sizes, fmt)
    return revision


async def fix_card(
    s: AIConfig,
    images: list[Image],
    prompt: str,
    deck: str,
    card: Card,
    instruction: str,
    others: Sequence[str] = (),
    language: str = "English",
    instructions: str = "",
    demo: dict[str, str] | None = None,
) -> FixedCard:
    """One card corrected by a natural-language request ("the answer is 1789"), seeing the
    lesson's photos: the only card the AI writes, so no other changes. `others`: the other
    cards' fronts (not to repeat one); `language`, `instructions`, `demo`: as revise_cards.
    It stays the same card: its id (Anki updates its note) and its diagram label; its
    picture too, unless what to draw changed."""
    images, _ = _prepare(images)
    text = instructions + _fix_text(prompt, deck, card, others, instruction, language, len(images))
    texts = {**demo_ai.DEMO, **(demo or {})}
    answer = await _ask_provider(
        s,
        images,
        text,
        ai_schema(CardFix, fun_facts=True, helps=True),
        demo=lambda: demo_ai.fixed_card(card, instruction, texts),
    )
    fix = CardFix.model_validate(_accepted(answer).model_dump())
    if not fix.cards:
        raise ExtractionError("llm.invalid_answer")
    fixed = fix.cards[0]
    plain_cards([fixed])
    fixed.mask = card.mask
    _same_card(fixed, card)
    return FixedCard(card=fixed, summary=plain_text(fix.summary))


def _keep_ids(revised: list[Card], before: list[Card]) -> None:
    """A revised card keeps the id and the picture of the card it was (same front and
    back, else same back, else same front): Anki updates its note, the picture stays —
    unless what to draw changed (the picture's subject, the figure's description)."""
    left = list(before)
    for card in revised:
        match = next((c for c in left if (c.front, c.back) == (card.front, card.back)), None)
        match = match or next((c for c in left if c.back == card.back), None)
        match = match or next((c for c in left if c.front == card.front and c.front), None)
        if match:
            _same_card(card, match)
            left.remove(match)
        else:
            card.id, card.picture = "", ""  # a new card: its id comes when saved


def _same_card(card: Card, before: Card) -> None:
    """`card` is `before` changed: its id and voice, and its picture unless what to draw changed."""
    card.id, card.voice = before.id, before.voice
    unchanged = (card.picture_prompt, card.figure) == (before.picture_prompt, before.figure)
    if unchanged or not (card.picture_prompt or card.figure):
        card.picture, card.picture_prompt, card.figure = before.picture, before.picture_prompt, before.figure
        card.picture_on_back = card.picture_on_back if unchanged else before.picture_on_back


def _keep_masks(
    revised: list[Card], before: list[Card], sizes: Sequence[tuple[int, int] | None] = (), fmt: str = "pixels"
) -> None:
    """Give each revised card the mask of the same card before (same front and back,
    else same front; a changed answer keeps its place on the diagram). Other cards keep
    the mask the model gave (a label added by the correction), placed like at
    extraction, with a number not used yet on its photo."""
    masked = [c for c in before if c.mask]
    added = []
    for card in revised:
        match = next((c for c in masked if (c.front, c.back) == (card.front, card.back)), None)
        match = match or next((c for c in masked if c.front == card.front), None)
        if match:
            card.mask = match.mask
            masked.remove(match)
        elif card.mask:
            added.append(card)
    _keep_ids(revised, before)
    diagrams.normalize(added, sizes, fmt)
    used = {(c.mask.page, c.mask.n) for c in revised if c.mask and c not in added}
    for card in (c for c in added if c.mask):
        if (card.mask.page, card.mask.n) in used:
            card.mask.n = max((n for page, n in used if page == card.mask.page), default=0) + 1
        used.add((card.mask.page, card.mask.n))


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
