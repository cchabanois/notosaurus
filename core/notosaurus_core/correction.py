"""The cards corrected by the AI: the lesson's ("remove…", "you forgot…") or one card's
("the answer is 1789"). A card corrected stays the card it was (cards.matching): its id,
so its note in Anki, its picture and its place on a diagram."""

from collections.abc import Sequence

from . import ai, diagrams
from .calls import ExtractionError, Image
from .cards import matching, plain_cards
from .cards import plain as plain_text
from .config import AIConfig
from .models import Card, CardFix, Deck, FixedCard, Revision
from .prompts import _fix_text, _revision_text
from .providers import demo as demo_ai


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
    fmt = ai._box_format(s)
    images, sizes = ai._prepare(images)
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
    answer = await ai._ask_provider(
        s,
        images,
        text,
        ai.ai_schema(Revision, fun_facts=True, helps=True, claude=ai.for_claude(s)),
        demo=lambda: demo_ai.revision(deck, instruction, texts),
    )
    revision = Revision.model_validate(ai._accepted(answer).model_dump())
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
    images, _ = ai._prepare(images)
    text = instructions + _fix_text(prompt, deck, card, others, instruction, language, len(images))
    texts = {**demo_ai.DEMO, **(demo or {})}
    answer = await ai._ask_provider(
        s,
        images,
        text,
        ai.ai_schema(CardFix, fun_facts=True, helps=True, claude=ai.for_claude(s)),
        demo=lambda: demo_ai.fixed_card(card, instruction, texts),
    )
    fix = CardFix.model_validate(ai._accepted(answer).model_dump())
    if not fix.cards:
        raise ExtractionError("llm.invalid_answer")
    fixed = fix.cards[0]
    plain_cards([fixed])
    fixed.mask = card.mask
    _same_card(fixed, card)
    return FixedCard(card=fixed, summary=plain_text(fix.summary))


def _keep_ids(revised: list[Card], before: list[Card]) -> None:
    """A revised card keeps the id and the picture of the card it was (cards.matching, in any
    part of the deck: a correction may move it): Anki updates its note, the picture stays,
    unless what to draw changed (the picture's subject, the figure's description)."""
    for card, match in zip(revised, matching(revised, before, any_part=True), strict=True):
        if match:
            _same_card(card, match)
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
    """Give each revised card the mask of the card it was (cards.matching, as its id: a
    changed answer keeps its place on the diagram). Other cards keep the mask the model gave
    (a label added by the correction), placed like at extraction, with a number not used yet
    on its photo."""
    added = []
    for card, match in zip(revised, matching(revised, before, any_part=True), strict=True):
        if match and match.mask:
            card.mask = match.mask
        elif card.mask:
            added.append(card)
    _keep_ids(revised, before)
    diagrams.normalize(added, sizes, fmt)
    used = {(c.mask.page, c.mask.n) for c in revised if c.mask and c not in added}
    for card in (c for c in added if c.mask):
        if (card.mask.page, card.mask.n) in used:
            card.mask.n = max((n for page, n in used if page == card.mask.page), default=0) + 1
        used.add((card.mask.page, card.mask.n))
