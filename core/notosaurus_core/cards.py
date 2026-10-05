"""What kind of card a card is, from its content."""

import re

from .models import Card

# A gap in a text: {{c1::1789}}, {{c2::la Bastille::lieu}} (Anki's cloze syntax)
CLOZE = re.compile(r"\{\{c\d+::")


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
