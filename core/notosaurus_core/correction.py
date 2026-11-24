"""The cards corrected by the AI: the lesson's ("remove…", "you forgot…") or one card's
("the answer is 1789"). A card corrected stays the card it was (cards.matching): its id,
so its note in Anki, its picture and its place on a diagram."""

import asyncio
from collections.abc import Sequence

from . import ai, diagrams, figures
from .calls import MAX_IMAGES, ExtractionError, Image
from .cards import as_pages, matching, page_numbers, pages_within, plain_cards
from .cards import plain as plain_text
from .config import AIConfig
from .models import Card, CardFix, Deck, FixedCard, PhotosSent, Revision
from .prompts import _fix_text, _revision_text
from .providers import demo as demo_ai


def fix_photos(page: int, photos: int | Sequence[int]) -> tuple[list[int], PhotosSent]:
    """The lesson's photos sent to correct one card (their numbers, from 1), and what they
    are: the card's own when its page is one of the lesson's `photos` ("card"); else every
    one, when a call takes them all ("all"); else none ("none": a card made before cards knew
    their page, in a lesson longer than a call takes). `photos`: the numbers of the lesson's
    pages there (cards.page_numbers: a count, 1 to n): a page missing is never replaced by
    another, its card's page then unknown. The same rule on the phone (Generation.fixPhotos:
    core/shared-cases.json)."""
    present = page_numbers(photos)
    if page in present:
        return [page], "card"
    if len(present) <= MAX_IMAGES:
        return present, "all"
    return [], "none"


def revise_photos(photos: int | Sequence[int]) -> tuple[list[int], PhotosSent]:
    """The lesson's photos sent to correct the whole lesson (their numbers, from 1), and what
    they are: every one, when a call takes them all ("all"); else none ("none": the lesson
    corrected from its cards, the AI told its pages aren't shown). More than a call takes
    would be heavy for the AI, slow and costly, and the relay refuses them; one card's page
    is sent when that card alone is corrected (fix_photos). `photos`: as fix_photos'. The
    same rule on the phone (Generation.revisePhotos: core/shared-cases.json)."""
    present = page_numbers(photos)
    if len(present) <= MAX_IMAGES:
        return present, "all"
    return [], "none"


async def revise_cards(
    s: AIConfig,
    images: list[Image],
    prompt: str,
    deck: Deck,
    instruction: str,
    language: str = "English",
    instructions: str = "",
    demo: dict[str, str] | None = None,
    quick: bool = False,
    photos_sent: PhotosSent = "all",
    pages: Sequence[int] = (),
) -> Revision:
    """Apply a natural-language correction ("remove…", "you forgot…") to the cards.

    `language`: English name of the page's language ("French"), for the one-line
    summary; `instructions`: see prompts.ExtractOptions; `demo`: the demo provider's texts in
    that language ("removed", "added", "addedFront"; English by default). `quick`: the model
    thinking little, as a lesson made quick (2026-11-19, 27 corrections with photos: as right,
    about 30 % faster). `photos_sent`: what `images` are of the lesson's photos
    (revise_photos): all of them, or "none" of a lesson that has some (corrected from its
    cards: the AI says what it couldn't do without the pages). Without a photo the AI writes
    no card's page (a new card's is 0) and no new mask; the cards keep theirs. `pages`: the
    lesson's page numbers of `images`, in their order (revise_photos; none given: 1 to n). The AI
    numbers the photos it is given from 1: the cards' pages and masks are shown it so, and what
    it answers is turned back into the lesson's page numbers (a page missing from the lesson
    leaves a gap: photo 3 may be its page 4)."""
    # The existing masks stay out of the conversation (their boxes are in our own
    # format): the revised cards get back the mask of the card they were. New cards
    # about a diagram label come with a mask in the model's format.
    fmt = ai._box_format(s)
    images, sizes = ai._prepare(images)
    numbers = list(pages) if len(pages) == len(images) else list(range(1, len(images) + 1))
    photo = {page: n for n, page in enumerate(numbers, 1)}  # a page's number → its photo's, as the AI counts
    labels: dict[int, list[int]] = {}
    for card in deck.cards:
        if card.mask and card.mask.page in photo:
            labels.setdefault(photo[card.mask.page], []).append(card.mask.n)
    plain = Deck(
        deck=deck.deck,
        cards=[
            c.model_copy(update={"mask": None, "picture": "", "id": "", "voice": "", "page": photo.get(c.page, 0)})
            for c in deck.cards
        ],
    )
    text = instructions + _revision_text(
        prompt, plain, instruction, language, len(images), sizes, fmt, labels, photos_sent, numbers
    )
    # The fun facts and helps already there are kept: the AI sees them
    texts = {**demo_ai.DEMO, **(demo or {})}
    answer = await ai._ask_provider(
        s,
        images,
        text,
        # No photo seen: no page to write (numbered among the photos it is given)
        ai.ai_schema(Revision, fun_facts=True, helps=True, claude=ai.for_claude(s), page=bool(images)),
        quick=quick,
        demo=lambda: demo_ai.revision(plain, instruction, texts),  # as the AI would: from what it is shown
    )
    revision = Revision.model_validate(ai._accepted(answer).model_dump())
    plain_cards(revision.cards)
    pages_within(revision.cards, len(images))  # numbered among the photos given…
    as_pages(revision.cards, numbers)  # …turned into the lesson's page numbers
    revision.summary = plain_text(revision.summary)
    _keep_masks(revision.cards, deck.cards, sizes, fmt, added=bool(images), pages=numbers)
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
    figure_svg: str = "",
    quick: bool = False,
    photos_sent: PhotosSent = "all",
) -> FixedCard:
    """One card corrected by a natural-language request ("the answer is 1789"), seeing the
    lesson's photos: the only card the AI writes, so no other changes. `others`: the other
    cards' fronts (not to repeat one); `language`, `instructions`, `demo`: as revise_cards.
    It stays the same card: its id (Anki updates its note) and its diagram label; its
    picture too, unless what to draw changed. `figure_svg`: its figure as drawn, shown after
    the photos: a request about the drawing ("E is on the wrong side") is seen, and said in
    figure_problem for it to be drawn again (its picture kept until then); left out when it
    can't be drawn (_drawn). `quick`: as revise_cards'. `photos_sent`: what `images` are of the
    lesson's photos (fix_photos): all, the card's own page, or none of a lesson that has some.
    Its page stays its own: the AI isn't asked for it."""
    images, _ = ai._prepare(images)
    photos = len(images)
    drawn = await asyncio.to_thread(_drawn, figure_svg) if figure_svg.strip() and card.figure.strip() else None
    if drawn is not None:
        images.append(Image(drawn, "image/png"))
    text = instructions + _fix_text(
        prompt, deck, card, others, instruction, language, photos, drawn is not None, photos_sent
    )
    texts = {**demo_ai.DEMO, **(demo or {})}
    answer = await ai._ask_provider(
        s,
        images,
        text,
        ai.ai_schema(CardFix, fun_facts=True, helps=True, claude=ai.for_claude(s), page=False),
        quick=quick,
        demo=lambda: demo_ai.fixed_card(card, instruction, texts),
    )
    fix = CardFix.model_validate(ai._accepted(answer).model_dump())
    if not fix.cards:
        raise ExtractionError("llm.invalid_answer")
    fixed = fix.cards[0]
    plain_cards([fixed])
    fixed.mask, fixed.page = card.mask, card.page
    _same_card(fixed, card)
    problem = plain_text(fix.figure_problem).strip() if drawn is not None and fixed.figure.strip() else ""
    if problem:
        # Drawn again, told the problem: shown until then
        fixed.picture, fixed.picture_source = card.picture, card.picture_source
    return FixedCard(card=fixed, summary=plain_text(fix.summary), figure_problem=problem)


def _drawn(figure_svg: str) -> bytes | None:
    """The figure as drawn, as a picture for the AI to see; None when it can't be drawn (not an
    SVG the cleaning keeps): the card corrected without it, as without resvg."""
    try:
        return figures.to_png(figures.clean(figure_svg))
    except figures.FigureError:
        return None


def _keep_ids(revised: list[Card], before: list[Card]) -> None:
    """A revised card keeps the id and the picture of the card it was (cards.matching, in any
    part of the deck: a correction may move it): Anki updates its note, the picture stays,
    unless what to draw changed (the picture's subject, the figure's description); its page
    too, unless the AI gave one."""
    for card, match in zip(revised, matching(revised, before, any_part=True), strict=True):
        if match:
            _same_card(card, match)
            card.page = card.page or match.page
        else:
            card.id, card.picture, card.picture_source = "", "", None  # a new card: its id comes when saved


def _same_card(card: Card, before: Card) -> None:
    """`card` is `before` changed: its id and voice, and its picture (with where it comes
    from) unless what to draw changed."""
    card.id, card.voice = before.id, before.voice
    unchanged = (card.picture_prompt, card.figure) == (before.picture_prompt, before.figure)
    if unchanged or not (card.picture_prompt or card.figure):
        card.picture, card.picture_prompt, card.figure = before.picture, before.picture_prompt, before.figure
        card.picture_source = before.picture_source
        card.picture_on_back = card.picture_on_back if unchanged else before.picture_on_back
    else:
        card.picture, card.picture_source = "", None  # drawn again


def _keep_masks(
    revised: list[Card],
    before: list[Card],
    sizes: Sequence[tuple[int, int] | None] = (),
    fmt: str = "pixels",
    added: bool = True,
    pages: Sequence[int] = (),
) -> None:
    """Give each revised card the mask of the card it was (cards.matching, as its id: a
    changed answer keeps its place on the diagram). Other cards keep the mask the model gave
    (a label added by the correction), placed like at extraction, with a number not used yet
    on its photo; none when `added` is False (the AI saw no photo: a box it gives is on none).
    `pages`: the lesson's page numbers of the photos the AI numbered from 1 (none: 1 to n)."""
    new = []
    for card, match in zip(revised, matching(revised, before, any_part=True), strict=True):
        if match and match.mask:
            card.mask = match.mask
        elif card.mask and added:
            new.append(card)
        else:
            card.mask = None
    _keep_ids(revised, before)
    diagrams.normalize(new, sizes, fmt)
    for card in new:  # placed on its photo: on the lesson's page that photo is
        if card.mask and 1 <= card.mask.page <= len(pages):
            card.mask.page = pages[card.mask.page - 1]
    used = {(c.mask.page, c.mask.n) for c in revised if c.mask and c not in new}
    for card in (c for c in new if c.mask):
        if (card.mask.page, card.mask.n) in used:
            card.mask.n = max((n for page, n in used if page == card.mask.page), default=0) + 1
        used.add((card.mask.page, card.mask.n))
