"""What the AI is told: the rules of each task (cards, explanations), the pupils' safety
rules, and the requests built from the user's prompt, the lesson's text, the cards."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from . import diagrams
from .models import Card, Deck

# The fixed rules, in rules/<name>.md: a paragraph or a bullet per line, read as they are
# (what each call adds to them, the lesson, the cards, a language: the _…_text functions)
RULES = Path(__file__).parent / "rules"


def _rule(name: str) -> str:
    return (RULES / f"{name}.md").read_text(encoding="utf-8")


# Who the cards are for, in every system prompt: what to make, what to refuse, and
# the user's text and the photos as content, never rules. `{refuse}`: how each task
# refuses (the cards: "refused"; an explanation: one sentence).
SAFETY = _rule("safety")

REFUSE_CARDS = 'set "refused" to true and give no cards'

REFUSE_TEXT = "answer only, in one short sentence, that you can't help with this"

SYSTEM_PROMPT = _rule("system") + SAFETY.format(refuse=REFUSE_CARDS)

# Asked for with a switch, never by default: only then is the AI told about them.
FUN_FACTS = _rule("fun_facts")

# Pictures where they truly help, whatever the prompt (a setting, on at first): only then
# is the AI told it may add them unasked.
PICTURES = _rule("pictures")

# Helps on the back, asked for with a switch (its default set in the settings): only
# where they truly help, as the follow-ups of an explanation (see EXPLAIN_RULES).
HELPS = _rule("helps")


@dataclass(frozen=True)
class ExtractOptions:
    """How a lesson is made, besides its prompt and photos (llm.extract_cards): an option
    added here once, not in every signature. `deck`: the deck name template; `decks`: the
    decks that already exist, to reuse their names; `fun_facts`, `helps`, `pictures`: the
    AI may add them (FUN_FACTS, HELPS, PICTURES); `page_texts`: one per photo, the text of
    a PDF page ("" for a photo); `instructions`: the user's standing instructions, put
    before the request (never replacing the rules); `quick`: made fast, the model thinking
    little; `existing`: the lesson's cards made from its earlier pages ("front [part]"),
    when these photos are its next pages: not made again."""

    deck: str = ""
    decks: Sequence[str] = ()
    fun_facts: bool = False
    helps: bool = False
    pictures: bool = False
    page_texts: Sequence[str] = ()
    instructions: str = ""
    quick: bool = False
    existing: Sequence[str] = ()


def _user_text(
    prompt: str,
    options: ExtractOptions,
    photos: int,
    sizes: Sequence[tuple[int, int] | None] = (),
    fmt: str = "",
) -> str:
    text = f"Instructions: {prompt.strip()}"
    if options.fun_facts:
        text += "\n" + FUN_FACTS
    if options.helps:
        text += "\n" + HELPS
    if options.pictures:
        text += "\n" + PICTURES
    if options.deck.strip():
        text += f"\nDeck name template: {options.deck.strip()}"
    if options.decks:
        text += "\nExisting decks: " + "; ".join(options.decks)
    if options.existing:
        made = "; ".join(options.existing)[:EXISTING_MAX]
        text += (
            f"\nThese photos are the next pages of a lesson that already has these cards: {made}. "
            "Make cards only for what these pages add, never one of these again; use the same "
            "parts (subdeck) and the same kinds of cards when they fit."
        )
    if not photos:
        text += "\nThere is no photo: create the cards from these instructions alone."
    elif fmt:
        text += f"\nDiagram label boxes, if any: {diagrams.FORMATS[fmt]}."
        if fmt == "pixels":
            known = [f"photo {i}: {size[0]}x{size[1]}" for i, size in enumerate(sizes, 1) if size]
            text += "\nPhoto sizes: " + ", ".join(known) + "."
    return text + _pdf_texts(options.page_texts)


EXISTING_MAX = 6000  # characters of the cards already made sent (a long lesson: its first ones)
PAGE_TEXT_MAX = 8000  # characters per page: a dense page holds 3 to 5,000


def _pdf_texts(texts: Sequence[str]) -> str:
    """The text of the photos that are PDF pages, as the PDF holds it: the exact words
    (no misreading), the photo keeping the layout and the diagrams. A scanned PDF has
    no text (or a few stray characters): nothing then."""
    pages = [
        f"Text of photo {n}, from its PDF:\n<<<\n{t.strip()[:PAGE_TEXT_MAX]}\n>>>"
        for n, t in enumerate(texts, 1)
        if len("".join(t.split())) >= 20
    ]
    if not pages:
        return ""
    return (
        "\nSome photos are pages of a PDF; their text follows, as the PDF holds it. Trust it for the "
        "exact words, spelling and numbers; trust the photo for the layout, the order, what goes "
        "together, the diagrams and anything the text misses.\n" + "\n".join(pages)
    )


EXPLAIN_RULES = _rule("explain") + SAFETY.format(refuse=REFUSE_TEXT)

EXPLAIN_ASKS = {
    "explain": "Explain this card: what it means, the context that helps understand it, and why its answer "
    "is the answer. No example, no memory trick and, for a multiple choice, nothing about the other "
    "options here: those are follow-ups.",
    "example": "Give one or two examples that make this card clearer (a sentence using the word, "
    "a worked calculation with the formula…).",
    "mnemonic": "Give one genuine way to remember the answer: the word's real origin or family, a "
    "simple image, a mnemonic schools really use. Never a rhyme, sentence or pun of your own.",
    "why": "Explain why the answer is right. For a multiple choice or a true/false card, also say "
    "why each other option is wrong, one short line each.",
}


def _explain_text(card: Card, kind: str, prompt: str, deck: str, language: str, page_texts: Sequence[str]) -> str:
    shown: dict[str, str | list[str]] = {"front": card.front, "back": card.back, "info": card.info}
    if card.choices:
        shown["wrong_options"] = card.choices
    text = (
        f"Lesson instructions: {prompt.strip()}\nDeck: {deck}\n"
        f"The card (JSON): {json.dumps(shown, ensure_ascii=False)}\n"
        f"Request: {EXPLAIN_ASKS[kind]}\nAnswer in {language}."
    )
    lesson_text = "\n".join(t.strip() for t in page_texts if t.strip())[:4000]
    if lesson_text:
        text += f"\nThe lesson's text (from its PDF):\n<<<\n{lesson_text}\n>>>"
    return text


def _revision_text(
    prompt: str,
    deck: Deck,
    instruction: str,
    language: str,
    photos: int,
    sizes: Sequence[tuple[int, int] | None] = (),
    fmt: str = "",
    labels: dict[int, list[int]] | None = None,
) -> str:
    """`labels`: numbers of the diagram labels already hidden, per photo."""
    current = json.dumps(deck.model_dump(), ensure_ascii=False, indent=1)
    source = "these photos with these instructions" if photos else "these instructions (no photo)"
    add = "To add cards, use the photos." if photos else "To add cards, follow the instructions."
    if photos and fmt:
        add += (
            ' Cards about labels already hidden on a diagram have "mask": null here: keep it null.'
            ' To add a card about another label of a diagram (a title, a part…), fill its "mask": page,'
            " the next free number n on that photo, and the box of the label's text,"
            f" {diagrams.FORMATS[fmt]}."
        )
        if labels:
            add += " Numbers already used: " + "; ".join(f"photo {p}: {sorted(ns)}" for p, ns in labels.items()) + "."
        if fmt == "pixels":
            known = [f"photo {i}: {size[0]}x{size[1]}" for i, size in enumerate(sizes, 1) if size]
            add += " Photo sizes: " + ", ".join(known) + "."
    return f"""\
The cards below were made from {source}:
{prompt.strip()}

Current cards (JSON):
{current}

Requested correction: {instruction.strip()}

Apply this request and return the complete deck (every card, not only the ones that \
change). Only change what the request is about; keep the other cards exactly as they \
are, in the same order. {add} In "summary", describe in one short sentence, in \
{language}, what you changed."""


def _fix_text(
    prompt: str, deck: str, card: Card, others: Sequence[str], instruction: str, language: str, photos: int
) -> str:
    """One card corrected, or written when it is still empty (a card just added): the
    others' fronts shown, not to repeat one of them."""
    source = "these photos with these instructions" if photos else "these instructions (no photo)"
    listed = "\n".join(f"- {front.strip()}" for front in others if front.strip()) or "(none)"
    if not (card.front.strip() or card.back.strip()):
        asked = f"""\
A card to write for this lesson (still empty): {instruction.strip()}

Write this card, as the one card in "cards", from the request and the lesson (the photos, \
the instructions): what the request asks for, not one of the other cards above."""
        done = "what the card asks"
    else:
        current = json.dumps(card.model_dump(exclude={"id", "picture", "mask", "voice"}), ensure_ascii=False, indent=1)
        asked = f"""\
The card to correct (JSON):
{current}

Requested correction for this card: {instruction.strip()}

Apply this request to this card only and return it, as the one card in "cards". Only change \
what the request is about; keep the rest of the card as it is."""
        done = "what you changed"
    return f"""\
The lesson "{deck}" was made from {source}:
{prompt.strip()}

Its other cards (their fronts):
{listed}

{asked} What the card says comes from the lesson, unless the request itself gives it. In \
"summary", describe in one short sentence, in {language}, {done}."""


DICTATION_RULES = _rule("dictation")

DICTATED = {
    "prompt": "instructions for making flashcards from a lesson",
    "correction": "a correction of a lesson's flashcards",
}


def _dictation_text(kind: str, language: str) -> str:
    return (
        f"The recording: {DICTATED[kind]}. The app is in {language}: the speaker usually speaks it, "
        "maybe with words of the language being learned."
    )


REPHRASE_RULES = _rule("rephrase")


def _rephrase_text(text: str, language: str) -> str:
    return f"The app is in {language}. The user's instructions, to tidy up:\n<<<\n{text}\n>>>"


PICK_RULES = _rule("pick")


SORT_RULES = _rule("sort")


def _pick_text(search: str, context: str, count: int) -> str:
    card = f"The card: {context}\n" if context.strip() else ""
    return f"{card}The picture searched for: {search}\nCandidates 0 to {count - 1}, in that order."


DRAWINGS_RULES = _rule("drawings")


def _drawings_text(cards: list[str], fmt: str, sizes: list[tuple[int, int] | None]) -> str:
    """The cards to look for ("front → back", numbered), and how to give the boxes (in pixels:
    the photos' sizes)."""
    listed = "\n".join(f"{i}. {card}" for i, card in enumerate(cards))
    sized = [f"photo {i + 1}: {size[0]}x{size[1]}" for i, size in enumerate(sizes) if size and fmt == "pixels"]
    return f"Cards:\n{listed}\n\nBoxes: {diagrams.FORMATS[fmt]}" + (f" ({'; '.join(sized)})" if sized else "") + "."


FIGURES_RULES = _rule("figures")


def _figures_text(cards: list[str]) -> str:
    listed = "\n".join(f"{n}. {card}" for n, card in enumerate(cards))
    return f"The cards (front → back), by number:\n{listed}"


PLAN_RULES = _rule("plan")

SEARCH_WORDS_RULES = _rule("search_words")


def _plan_text(front: str, back: str, asked: str, language: str) -> str:
    wrote = asked.strip() or "(nothing: decide from the card)"
    return f"The card, in {language}: {front.strip()} → {back.strip()}\nWhat the user wrote for its picture: {wrote}"


def _search_words_text(asked: str, context: str) -> str:
    card = f"\nThe card it is for: {context.strip()}" if context.strip() else ""
    return f"What to find a picture of: {asked.strip()}{card}"
