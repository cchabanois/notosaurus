"""Cloze cards: a text with gaps, one card per gap number; a picture and a sound on either side."""

from pathlib import Path

from notosaurus_core import tts

from .common import (
    BACK_INFO,
    BACK_PICTURE,
    CSS,
    HELP_FIELDS,
    PICTURE,
    PICTURE_CSS,
    SOUND_FIELDS,
    SOURCE_FIELD,
    NoteType,
    field_html,
    fix_link,
    helps,
    info,
    sound_kind,
    sounds,
    versioned,
    with_context,
)

CLOZE_CSS = (Path(__file__).parent / "css" / "cloze.css").read_text(encoding="utf-8")


def cloze_note_type(voice: str = "") -> NoteType:
    """A text with gaps ("{{c1::1789}}"): Anki makes one card per gap number, the
    others shown. "Extra" (the card's back, often empty) shows with the answer. Its
    picture or figure, if any, on the question ("Picture") or with the answer
    ("BackPicture"); its sounds in `voice` (common.sounds): the text with its gaps blank on
    the question ("FrontAudio"), whole with the answer ("Audio"), each when the card says
    (Card.sound). "Id" (the card's own id) tells which note an update is for: the text is
    what gets corrected."""
    anki_tts = tts.is_anki_locale(voice)
    front_sound, sound = sounds(anki_tts, voice)
    info = BACK_INFO + fix_link("Id")
    templates = (
        {
            "name": "Cloze",
            "qfmt": f"{PICTURE}{{{{cloze:Text}}}}{front_sound}",
            "afmt": f"{PICTURE}{{{{cloze:Text}}}}{sound}"
            + '{{#Extra}}<div class="extra">{{Extra}}</div>{{/Extra}}'
            + BACK_PICTURE
            + info,
        },
    )
    fields = ("Text", "Extra", "Info", *SOUND_FIELDS, "Id", *HELP_FIELDS, "Picture", "BackPicture", SOURCE_FIELD)
    return NoteType(
        versioned(f"Notosaurus cloze ({sound_kind(anki_tts, voice)})"),
        f"cloze {sound_kind(anki_tts, voice)}",  # its id's: a voice's note type never another's
        fields,
        with_context(templates),
        css=CSS + PICTURE_CSS + CLOZE_CSS,
        key="Id",
        cloze=True,
    )


def cloze_fields(card, card_id: str) -> dict[str, str]:
    """The gaps are the answers: the back is optional. Its picture's and sounds' fields
    empty: the export's to fill (anki.notes)."""
    return {
        "Text": field_html(card.front.strip()),
        "Extra": field_html(card.back.strip()),
        "Info": info(card),
        "Id": card_id,
        "Picture": "",
        "BackPicture": "",
        SOURCE_FIELD: "",
        **dict.fromkeys(SOUND_FIELDS, ""),
        **helps(card),
    }
