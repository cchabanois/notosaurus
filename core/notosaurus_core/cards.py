"""What kind of card a card is, from its content; its texts as plain text."""

import html
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
# A bracket the AI "escaped" (a French interval, "]-\infty ; +\infty[" written
# "\]-\infty ; +\infty\["): "\[" and "\]" open and close a formula on its own, so one
# out of that order is a bracket. Put back as one, the part it bounds a formula when it
# holds a command and no formula already: "\(]-\infty ; +\infty[\)".
DISPLAY = re.compile(r"\\[\[\]]")
INLINE = re.compile(r"\\\(.*?\\\)", re.DOTALL)
TEXT_FIELDS = ("front", "back", "info", "fun_fact", "explanation", "mnemonic")


def plain(text: str) -> str:
    """The text without markup: HTML entities decoded (the AI writes "&eacute;" now and then:
    a card never means one), emphasis in square brackets, tags gone, breaks kept; LaTeX
    commands whose backslash JSON read as an escape put back."""
    if "&" in text:
        text = html.unescape(text)
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
    text = brackets(text)
    if not FORMULA.search(text):
        return BARE_FORMULA.sub(r"\\(\1\\)", text)
    return FORMULA.sub(lambda m: LOST_NEWLINE.sub("\\\\n", m.group()), text)


def brackets(text: str) -> str:
    """The text with its brackets the AI wrote as display delimiters put back (DISPLAY): a
    "\\[" closed by the next "\\]" is a formula; any other is a bracket."""
    marks = list(DISPLAY.finditer(text))
    stray, i = [], 0
    while i < len(marks):
        if marks[i].group() == "\\[" and i + 1 < len(marks) and marks[i + 1].group() == "\\]":
            i += 2  # a formula on its own
            continue
        stray.append(marks[i])
        i += 1
    if not stray:
        return text
    inline = [m.span() for m in INLINE.finditer(text)]
    parts, at = [], 0
    for first, last in zip(stray[0::2], stray[1::2], strict=False):
        start, end = first.start(), last.end()
        bounded = text[first.end() : last.start()]
        inside = any(a <= start and end <= b for a, b in inline)
        piece = first.group()[1] + bounded + last.group()[1]
        parts += [text[at:start], piece if inside or "\\" not in bounded else f"\\({piece}\\)"]
        at = end
    if len(stray) % 2:  # one alone: a bracket, as it is
        last = stray[-1]
        parts += [text[at : last.start()], last.group()[1]]
        at = last.end()
    return "".join(parts) + text[at:]


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


# A dictation's blank, where the word to write goes ("…", "...", "___"): its sound reads the
# sentence with the word put back (tts.spoken)
BLANK = re.compile(r"…|\.{3}|_{3,}")
# The front of a dictation's card that has none: its blank alone, the word heard to write
DICTATION_FRONT = "…"


def blank_dictations(cards: list[Card]) -> None:
    """A dictation's cards never show their answer, whatever the AI wrote (its rule said a
    blank, it wrote "Write the word: maison"): in place, a front without a blank that holds
    its back exactly once, as a whole word (emphasised: "[maison]" too), gets "…" there. A
    front with its blank already ("la maison de … poupée" → "la": the other "la" isn't it),
    or holding its back more than once (which one?), stays as it is. An empty front (ANK-08:
    the AI wrote none) gets the blank alone, "…": the word heard, to write; without it, no
    note in Anki (its first field)."""
    for card in cards:
        back = card.back.strip()
        if back and not card.front.strip():
            card.front = DICTATION_FRONT
            continue
        if not back or "\n" in back or BLANK.search(card.front):
            continue
        word = re.escape(back)
        found = list(re.finditer(rf"\[{word}\]|(?<!\w){word}(?!\w)", card.front, re.IGNORECASE))
        if len(found) == 1:
            card.front = card.front[: found[0].start()] + "…" + card.front[found[0].end() :]


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
