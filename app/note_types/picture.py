"""Picture cards: a picture on the question, or with the answer; where it comes from."""

import html
from pathlib import Path

from notosaurus_core import tts

from .common import BACK_INFO, CSS, HELP_FIELDS, SOURCE_FIELD, NoteType, field_html, typed, variant

PICTURE_CSS = """\
.notosaurus-picture img { max-width: min(100%, 320px); max-height: 50vh; border-radius: 12px; }
"""
SOURCE_NAMES = {"commons": "Wikimedia Commons", "openverse": "Openverse", "pixabay": "Pixabay"}


def picture_note_type(voice: str, typing: bool = False, on_back: bool = False) -> NoteType:
    """A picture card: the picture and the front text (e.g. "How do you say it in
    English?"), then the answer. "Id" (the card's own id) tells which note an update
    is for: the fronts are often all the same. `on_back`: the picture belongs to the
    answer ("What is a tangent?"): shown with it only. Same fields and card name: a note
    moves from one to the other keeping its history."""
    anki_tts = tts.is_anki_locale(voice)
    sound = f"{{{{tts {voice}:Back}}}}" if anki_tts else "{{Audio}}"
    info = BACK_INFO
    picture = '<div class="notosaurus-picture">{{Picture}}</div>'
    if on_back:
        question, answer = "{{Front}}", f'{{{{FrontSide}}}}<hr id="answer">{{{{Back}}}}{sound}{picture}{info}'
    else:
        question = picture + "{{#Front}}<div>{{Front}}</div>{{/Front}}"
        answer = f'{{{{FrontSide}}}}<hr id="answer">{{{{Back}}}}{sound}{info}'
    templates = ({"name": "Image", "qfmt": question, "afmt": answer},)
    if typing:
        templates = (typed(templates[0], "Back"),)
    fields = ["Front", "Back", "Info"] + ([] if anki_tts else ["Audio"]) + ["Picture", "Id", *HELP_FIELDS, SOURCE_FIELD]
    kind = f"picture TTS Anki {voice}" if anki_tts else "picture audio"
    name, option = variant("Notosaurus image au verso" if on_back else "Notosaurus image", typing, False)
    option = "+".join(filter(None, ["back" if on_back else "", option]))
    name = f"{name} ({kind.removeprefix('picture ')})"
    return NoteType(name, kind, tuple(fields), templates, css=CSS + PICTURE_CSS, key="Id", variant=option)


def picture_fields(card, picture: Path, card_id: str) -> dict[str, str]:
    """A picture card's own fields: its picture, where it comes from, its id."""
    return {"Picture": f'<img src="{picture.name}">', SOURCE_FIELD: source(card), "Id": card_id}


def source(card) -> str:
    """Where the card's picture comes from, as its note's hidden Source field: "Wikimedia
    Commons · Public domain · Prise de la Bastille · <its page>", "Drawn by <model>", "Own photo"."""
    origin = card.picture_source
    if origin is None:
        return ""
    if origin.source == "drawn":
        return field_html(f"Drawn by {origin.model}" if origin.model else "Drawn")
    if origin.source == "photo":
        return "Own photo"
    parts = [field_html(p) for p in (SOURCE_NAMES.get(origin.source, origin.source), origin.licence, origin.title) if p]
    if origin.page:
        page = html.escape(origin.page, quote=True)
        parts.append(f'<a href="{page}">{page}</a>')
    return " · ".join(parts)
