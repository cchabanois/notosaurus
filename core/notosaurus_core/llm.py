"""Card extraction with a vision model.

A single interface, `extract_cards`, and a provider chosen in the AI configuration
(config.AIConfig, passed to every call):

- "gemini" (default): Gemini, through the official google-genai SDK (providers/gemini.py).
- "anthropic": Claude, through the official SDK (providers/anthropic.py).
- "openai":     OpenAI itself (GPT).
- "openrouter": OpenRouter, every provider's models with one key.
- "compatible": any other OpenAI-compatible service at its address (Ollama, LM Studio,
  Mistral…); these three in providers/openai_like.py.
- "fake":      canned cards, to work on the UI without a key or any cost (demo.py).

What the AI is told is in prompts.py; what every call shares (photos, errors, the
calls recorded, the cards streamed) in calls.py.
"""

from functools import cache

from pydantic import BaseModel, Field, create_model

from . import config, diagrams
from .calls import CardStream, ExtractionError, Image, OnCard, record, recording  # noqa: F401 (llm's API)
from .config import AIConfig
from .demo import (
    DEMO,
    _fake,
    _fake_dictation,
    _fake_explanation,
    _fake_figure,
    _fake_rephrased,
    _fake_revision,
    _lets_choose,
)
from .models import Card, Deck, Dictation, Explanation, Extraction, Frame, Picked, Rephrased, Revision
from .prompts import (
    DICTATION_RULES,
    EXPLAIN_RULES,
    PICK_RULES,
    REPHRASE_RULES,
    SYSTEM_PROMPT,
    _dictation_text,
    _explain_text,
    _pick_text,
    _rephrase_text,
    _revision_text,
    _user_text,
)
from .providers import anthropic, gemini, openai_like
from .providers.openai_like import list_models  # noqa: F401 (llm's API)

# What the AI sees of a card: what it fills, and only that. Anthropic refuses a response
# schema with too many optional fields ("Schema is too complex"): the fields Notosaurus
# sets itself are left out, and the ones only some requests ask for (fun facts, helps)
# are there only then.
SET_BY_NOTOSAURUS = {"picture", "picture_source", "id"}


@cache
def ai_schema[T: BaseModel](base: type[T], fun_facts: bool = False, helps: bool = False) -> type[T]:
    """`base` (Extraction, Revision) as the AI fills it; turned back into it with
    `base.model_validate(answer.model_dump())`."""
    left_out = set(SET_BY_NOTOSAURUS)
    left_out |= set() if fun_facts else {"fun_fact"}
    left_out |= set() if helps else {"explanation", "mnemonic"}
    card_fields = {k: (f.annotation, f) for k, f in Card.model_fields.items() if k not in left_out}
    card = create_model("Card", __doc__=Card.__doc__, **card_fields)
    fields = {k: (f.annotation, f) for k, f in base.model_fields.items() if k != "cards"}
    refused = (bool, Field(default=False, description="True when the request must be refused (see the rules)."))
    return create_model(base.__name__, __doc__=base.__doc__, cards=(list[card], Field()), **fields, refused=refused)


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


async def extract_cards(
    s: AIConfig,
    images: list[Image],
    prompt: str,
    deck: str = "",
    decks: list[str] = (),
    fun_facts: bool = False,
    page_texts: list[str] = (),
    helps: bool = False,
    instructions: str = "",
    quick: bool = False,
    on_card: OnCard | None = None,
) -> Extracted:
    """`decks`: the decks that already exist, to reuse their names; `instructions`: the
    user's standing instructions, put before the request (never replacing the rules);
    `quick`: made fast, the model thinking little; `on_card`: each card as soon as it is
    written (see _generate)."""
    if s.llm == "fake":
        await record(s, "fake", "fake", 0, 0, cost=0.0)
        choice = "Vocabulaire d'espagnol : français → espagnol" if _lets_choose(prompt) else ""
        found = _fake(images, prompt, deck)
        if fun_facts:  # the demo's "did you know" on its first card
            found.cards[0].fun_fact = "Le savais-tu ? Ce mot vient du latin."
        if helps:  # the demo's helps: an explanation on the first card, a mnemonic on the second
            found.cards[0].explanation = "(démo) Pourquoi c'est la réponse."
            found.cards[-1].mnemonic = "(démo) Une astuce pour retenir."
        for card in found.cards if on_card else ():  # one by one, as a real AI writes them
            await on_card(card.model_dump(exclude_defaults=True))
        return Extracted(deck=found, turns=[0] * len(images), frames=[], back_language="es-ES", choice=choice)
    fmt = diagrams.box_format(s.model_for_provider())
    images, sizes = _prepare(images)
    text = instructions + _user_text(prompt, deck, len(images), sizes, fmt, decks, fun_facts, page_texts, helps)
    schema = ai_schema(Extraction, fun_facts, helps)
    answer = await _generate(s, images, text, schema, quick=quick, on_card=on_card)
    result = Extraction.model_validate(_accepted(answer).model_dump())
    diagrams.normalize(result.cards, sizes, fmt)
    return Extracted(
        deck=Deck(deck=result.deck, cards=result.cards),
        turns=diagrams.turns(result.text_lines, sizes, fmt),
        frames=diagrams.frames(result.frames, sizes, fmt),
        back_language=result.back_language.strip(),
        choice=result.choice.strip(),
    )


async def draw_figure(s: AIConfig, description: str) -> str:
    """The SVG of a figure, drawn by the cards' AI with the drawing rules (figures.py)."""
    from . import figures

    if s.llm == "fake":
        await record(s, "fake", "fake", 0, 0, cost=0.0)
        return _fake_figure(description)
    drawing = await _generate(
        s, [], f"Figure to draw: {description.strip()}", figures.Drawing, figures.RULES, light=True
    )
    return drawing.svg


async def explain_card(
    s: AIConfig,
    card: Card,
    kind: str,
    prompt: str,
    deck: str,
    language: str = "English",
    instructions: str = "",
    page_texts: list[str] = (),
) -> Explanation:
    """A short explanation of a card for the pupil (or an example, a way to remember it,
    why the answer is right), and the follow-ups worth offering. A light call: no photo.

    `language`: its English name ("French"); `instructions`: see extract_cards."""
    if s.llm == "fake":
        await record(s, "fake", "fake", 0, 0, cost=0.0)
        return _fake_explanation(card, kind)
    text = instructions + _explain_text(card, kind, prompt, deck, language, page_texts)
    found = await _generate(s, [], text, Explanation, EXPLAIN_RULES, light=True)
    found.more = list(dict.fromkeys(k for k in found.more if k != kind))
    return found


async def transcribe(s: AIConfig, audio: Image, kind: str, language: str = "English") -> str:
    """A dictation as the text its speaker meant to type (models.Dictated `kind`: a
    lesson's instructions or a correction): their words, hesitations out, their own
    corrections applied, a lesson's foreign words spelled right. Gemini only: it hears
    the recording itself (the others take no audio).

    `audio`: the recording (audio/aac, ogg, mpeg, wav, flac); `language`: the app's,
    its English name ("French")."""
    if s.llm == "fake":
        await record(s, "fake", "fake", 0, 0, cost=0.0)
        return _fake_dictation(kind)
    if s.llm != "gemini":
        raise ExtractionError("llm.no_audio", provider=s.llm)
    found = await _generate(s, [audio], _dictation_text(kind, language), Dictation, DICTATION_RULES, light=True)
    return found.text.strip()


async def rephrase(s: AIConfig, text: str, language: str = "English") -> str:
    """A lesson's instructions tidied up ("✨ Tidy up"): clear and short, in their own
    language, every intention kept and none added. A light call, text only.

    `language`: the app's, its English name ("French")."""
    if s.llm == "fake":
        await record(s, "fake", "fake", 0, 0, cost=0.0)
        return _fake_rephrased(text)
    found = await _generate(s, [], _rephrase_text(text, language), Rephrased, REPHRASE_RULES, light=True)
    return found.text.strip()


async def pick_picture(s: AIConfig, candidates: list[Image], search: str, context: str) -> int | None:
    """Which of the pictures found (their previews, in order) fits a card: its index, or
    None when none does. `context`: the card, as "front → back"."""
    if s.llm == "fake":
        await record(s, "fake", "fake", 0, 0, cost=0.0)
        return 0 if candidates else None
    found = await _generate(s, candidates, _pick_text(search, context, len(candidates)), Picked, PICK_RULES, light=True)
    return found.choice if 0 <= found.choice < len(candidates) else None


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
    summary; `instructions`: see extract_cards; `demo`: the demo provider's texts in
    that language ("removed", "added", "addedFront"; English by default)."""
    if s.llm == "fake":
        await record(s, "fake", "fake", 0, 0, cost=0.0)
        return _fake_revision(deck, instruction, {**DEMO, **(demo or {})})
    # The existing masks stay out of the conversation (their boxes are in our own
    # format): the revised cards get back the mask of the card they were. New cards
    # about a diagram label come with a mask in the model's format.
    fmt = diagrams.box_format(s.model_for_provider())
    images, sizes = _prepare(images)
    labels: dict[int, list[int]] = {}
    for card in deck.cards:
        if card.mask:
            labels.setdefault(card.mask.page, []).append(card.mask.n)
    plain = Deck(
        deck=deck.deck, cards=[c.model_copy(update={"mask": None, "picture": "", "id": ""}) for c in deck.cards]
    )
    text = instructions + _revision_text(prompt, plain, instruction, language, len(images), sizes, fmt, labels)
    # The fun facts and helps already there are kept: the AI sees them
    answer = await _generate(s, images, text, ai_schema(Revision, fun_facts=True, helps=True))
    revision = Revision.model_validate(_accepted(answer).model_dump())
    _keep_masks(revision.cards, deck.cards, sizes, fmt)
    return revision


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
            card.id = match.id
            unchanged = (card.picture_prompt, card.figure) == (match.picture_prompt, match.figure)
            if unchanged or not (card.picture_prompt or card.figure):
                card.picture, card.picture_prompt, card.figure = match.picture, match.picture_prompt, match.figure
                card.picture_on_back = card.picture_on_back if unchanged else match.picture_on_back
            left.remove(match)
        else:
            card.id, card.picture = "", ""  # a new card: its id comes when saved


def _keep_masks(
    revised: list[Card], before: list[Card], sizes: list[tuple[int, int] | None] = (), fmt: str = "pixels"
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


async def _generate[T: BaseModel](
    s: AIConfig,
    images: list[Image],
    text: str,
    schema: type[T],
    system: str = SYSTEM_PROMPT,
    light: bool = False,
    quick: bool = False,
    on_card: OnCard | None = None,
) -> T:
    """Send photos + text to the configured provider and parse the answer as `schema`.
    `system`: the fixed rules (the cards' by default). `light`: a task that needs little
    thinking (drawing a figure described precisely): the model thinks as little as it
    can, where the service lets us say so — cheaper and faster. `quick`: a lesson made
    fast (the page's "Quick"): the model thinks little ("low"), 2 to 4 times faster,
    a little less careful on rich lessons (a figure, maths). `on_card`: each card as soon
    as it is written (Gemini; the other services answer all at once)."""
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
    if s.llm == "fake":
        return {"vision": True, "json": True, "answer": "red"}
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
        answer = await _generate(only_main_model, [Image(_test_image(), "image/png")], prompt, _CheckAnswer)
    except ExtractionError as e:
        if e.code in ("llm.invalid_answer", "llm.truncated"):
            return {"vision": False, "json": False, "answer": ""}  # answered, but not in the JSON format
        detail = str(e.params.get("detail", "")).lower()
        if e.params.get("status") == 400 and any(w in detail for w in ("image", "multimodal", "vision")):
            # e.g. Ollama: "model does not support multimodal requests"
            return {"vision": False, "json": None, "answer": "", "refused": e.params["detail"]}
        raise
    return {"vision": "red" in answer.color.lower(), "json": True, "answer": answer.color.strip()[:40]}
