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
# A LaTeX command the AI wrote with one backslash where JSON wants two ("\text" for
# "\\text"): JSON read its first letter as an escape, so "\text{m}" came as a tab and
# "ext{m}", "\frac" as a form feed and "rac". A tab, form feed, backspace or carriage return
# right before a letter is never meant in a card: it is put back as the command. A line
# break is meant, outside a formula: within one (\( … \), \[ … \]) it is put back too.
LOST_ESCAPE = re.compile(r"[\t\f\b\r](?=[a-zA-Z])")
FORMULA = re.compile(r"\\\(.*?\\\)|\\\[.*?\\\]", re.DOTALL)
LOST_NEWLINE = re.compile(r"\n(?=[a-zA-Z])")
ESCAPES = {"\t": "\\t", "\f": "\\f", "\b": "\\b", "\r": "\\r", "\n": "\\n"}
# The formula's own delimiters lost the same way ("\(" isn't a JSON escape: the AI drops
# its backslash): a group in plain parentheses opening on a command, in a text without
# any formula, is the formula it meant, "(\text{m})" for "\(\text{m}\)".
BARE_FORMULA = re.compile(r"\((\\[a-zA-Z][^()]*)\)")
TEXT_FIELDS = ("front", "back", "info", "fun_fact", "explanation", "mnemonic")


def plain(text: str) -> str:
    """The text without markup: emphasis in square brackets, tags gone, breaks kept;
    LaTeX commands whose backslash JSON read as an escape put back."""
    text = formulas(text)
    if "<" not in text and "**" not in text:
        return text
    for _ in range(3):  # nested emphasis, inside out
        text = EMPHASIS.sub(lambda m: f"[{m.group(2)}]", text)
    text = BOLD_MARKDOWN.sub(lambda m: f"[{m.group(1)}]", text)
    text = LINE_BREAK.sub("\n", text)
    return TAG.sub("", text)


def formulas(text: str) -> str:
    """The text with the LaTeX the AI meant: commands whose backslash JSON read as an
    escape put back, a formula whose delimiters lost theirs delimited again."""
    text = LOST_ESCAPE.sub(lambda m: ESCAPES[m.group()], text)
    if "\\" not in text:
        return text
    if not FORMULA.search(text):
        return BARE_FORMULA.sub(r"\\(\1\\)", text)
    return FORMULA.sub(lambda m: LOST_NEWLINE.sub("\\\\n", m.group()), text)


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
