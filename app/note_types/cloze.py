"""Cloze cards: a text with gaps, one card per gap number."""

from .common import BACK_INFO, CSS, HELP_FIELDS, NoteType, field_html, fix_link, helps, info

CLOZE_CSS = """\
.cloze { font-weight: 700; color: #0b5cad; }
.extra { margin-top: 12px; }
"""


def cloze_note_type() -> NoteType:
    """A text with gaps ("{{c1::1789}}"): Anki makes one card per gap number, the
    others shown. "Extra" (the card's back, often empty) shows with the answer. Not
    read aloud. "Id" (the card's own id) tells which note an update is for: the text
    is what gets corrected."""
    info = BACK_INFO + fix_link("Id")
    templates = (
        {
            "name": "Texte à trous",
            "qfmt": "{{cloze:Text}}",
            "afmt": '{{cloze:Text}}{{#Extra}}<div class="extra">{{Extra}}</div>{{/Extra}}' + info,
        },
    )
    fields = ("Text", "Extra", "Info", "Id", *HELP_FIELDS)
    return NoteType("Notosaurus texte à trous", "cloze", fields, templates, css=CSS + CLOZE_CSS, key="Id", cloze=True)


def cloze_fields(card, card_id: str) -> dict[str, str]:
    """The gaps are the answers: the back is optional."""
    return {
        "Text": field_html(card.front.strip()),
        "Extra": field_html(card.back.strip()),
        "Info": info(card),
        "Id": card_id,
        **helps(card),
    }
