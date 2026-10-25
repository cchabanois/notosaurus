"""What kind of card a card is, from its content; its texts as plain text."""

import re

from .models import Card

# A gap in a text: {{c1::1789}}, {{c2::la Bastille::lieu}} (Anki's cloze syntax)
CLOZE = re.compile(r"\{\{c\d+::")

# Markup the AI writes now and then despite its rules (a letter underlined, a word in bold):
# the fields are plain text (escaped, as any text, before Anki shows them), so a tag would
# show as it is. Emphasis becomes square brackets, the lesson's own way of singling out a
# part ("the group in brackets"); the rest of the tags goes; a line break stays one.
EMPHASIS = re.compile(r"<(u|b|i|em|strong|mark)(?:\s[^<>]*)?>(.*?)</\1>", re.IGNORECASE | re.DOTALL)
BOLD_MARKDOWN = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")  # not "__": underscores belong to words (__init__)
LINE_BREAK = re.compile(r"<br\s*/?>|</p>\s*<p>", re.IGNORECASE)
TAG = re.compile(r"</?[a-zA-Z][^<>]*>")
TEXT_FIELDS = ("front", "back", "info", "fun_fact", "explanation", "mnemonic")


def plain(text: str) -> str:
    """The text without markup: emphasis in square brackets, tags gone, breaks kept."""
    if "<" not in text and "**" not in text:
        return text
    for _ in range(3):  # nested emphasis, inside out
        text = EMPHASIS.sub(lambda m: f"[{m.group(2)}]", text)
    text = BOLD_MARKDOWN.sub(lambda m: f"[{m.group(1)}]", text)
    text = LINE_BREAK.sub("\n", text)
    return TAG.sub("", text)


def plain_cards(cards: list[Card]) -> None:
    """Every text of the cards as plain text, in place (the AI's answer, before anything
    else reads it)."""
    for card in cards:
        for name in TEXT_FIELDS:
            setattr(card, name, plain(getattr(card, name)))
        card.choices = [plain(c) for c in card.choices]
        if card.doubt:
            for name in ("reason", "front", "back"):
                setattr(card.doubt, name, plain(getattr(card.doubt, name)))


def is_cloze(text: str) -> bool:
    """A text with gaps: a cloze card, one Anki card per gap number."""
    return bool(CLOZE.search(text))


def is_choice(card: Card) -> bool:
    """A multiple-choice or true/false card: a right answer (its back) and wrong ones.
    A text with gaps or a diagram label stays what it is."""
    return bool(
        card.front.strip()
        and card.back.strip()
        and any(c.strip() for c in card.choices)
        and not card.mask
        and not is_cloze(card.front)
    )
