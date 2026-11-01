"""The notes a lesson gives, and the .apkg package built from them with genanki. The
note types, one module per family, are in app/note_types/ (re-exported here)."""

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import genanki

from notosaurus_core import tts
from notosaurus_core.cards import is_choice, is_cloze

from .errors import AppError
from .models import ExportRequest
from .note_types import (
    BACK_INFO,
    CSS,
    HELP_FIELDS,
    SOURCE_FIELD,
    NoteType,
    choice_fields,
    choice_note_type,
    choice_order,
    cloze_fields,
    cloze_note_type,
    diagram_fields,
    diagram_note_type,
    family,
    model_id,
    note_type,
    picture_fields,
    picture_note_type,
)
from .note_types.common import field_html, helps, info
from .note_types.common import stable_id as _stable_id

# What the callers (ankiconnect, lesson_notes, the routes, tools/, the tests) use
__all__ = [
    "BACK_INFO",
    "CSS",
    "HELP_FIELDS",
    "SOURCE_FIELD",
    "TAG_PREFIX",
    "Note",
    "NoteType",
    "build_apkg",
    "choice_note_type",
    "choice_order",
    "cloze_note_type",
    "diagram_note_type",
    "family",
    "guids",
    "is_choice",
    "is_cloze",
    "lesson_notes",
    "lesson_tag",
    "model_id",
    "note_type",
    "notes",
    "picture_note_type",
]


@dataclass
class Note:
    nt: NoteType
    deck: str
    fields: dict[str, str]  # field name → HTML value
    tags: list[str]
    media: list[Path]  # files the note uses: mp3, images
    card_id: str = ""  # the card it is (Card.id): finds its note again even if its front changed

    @property
    def key(self) -> str:
        return self.fields[self.nt.key]


@dataclass
class _Export:
    """What every note of an export shares: the request, its media, its note types."""

    req: ExportRequest
    audio: dict[str, Path]
    images: dict[int, tuple[Path, list[float] | None]]
    pictures: dict[int, Path]
    extra_tags: dict[str, list[str]] | None = None  # card id → tags of the tests it is in (exams.py)

    def __post_init__(self):
        req = self.req
        self.own_tags = [lesson_tag(req.lesson_id)] if req.lesson_id else []  # to find the lesson's notes again
        self.typing = req.typing or req.dictation or req.dictation_only
        self.text_nt = note_type(req.voice, req.reverse, req.typing, req.dictation, req.dictation_only)
        self.diagram_nt = diagram_note_type(req.voice, req.typing)
        self.picture_nt = picture_note_type(req.voice, req.typing)
        self.answer_picture_nt = picture_note_type(req.voice, req.typing, on_back=True)
        # A formula isn't typed (its code would be) nor heard
        self.math_nt = note_type(req.voice, req.reverse)
        # An answer too long to type (typed): heard and asked as the others, not typed
        self.untyped_nt = note_type(req.voice, req.reverse, False, req.dictation, req.dictation_only)
        self.cloze_nt, self.choice_nt = cloze_note_type(), choice_note_type()

    def note(self, card, nt: NoteType, fields: dict[str, str], media: list[Path]) -> Note:
        return Note(
            nt=nt,
            deck=_deck_name(self.req.deck, card.subdeck),
            fields=fields,
            tags=[_tag(t) for t in card.tags if t.strip()] + self.own_tags + (self.extra_tags or {}).get(card.id, []),
            media=media,
        )

    def card_id(self, i: int, card) -> str:
        return card.id or f"{self.req.lesson_id or ''}:{i}"


def notes(
    req: ExportRequest,
    audio: dict[str, Path] | None = None,
    images: dict[int, tuple[Path, list[float] | None]] | None = None,
    pictures: dict[int, Path] | None = None,
    extra_tags: dict[str, list[str]] | None = None,
) -> list[Note]:
    """The notes to send, in both output formats. `audio` maps a card back to its mp3;
    `images` maps the index of a diagram card to its diagram's image and crop;
    `pictures`, the index of a picture card to its picture; `extra_tags`, a card's id to
    the tags of the tests it is in (exams.card_tags)."""
    export = _Export(req, audio or {}, images or {}, pictures or {}, extra_tags)
    result = []
    for i, card in enumerate(req.cards):
        if is_cloze(card.front.strip()):
            note = export.note(card, export.cloze_nt, cloze_fields(card, export.card_id(i, card)), [])
        elif is_choice(card):
            picture = export.pictures.get(i)
            fields = choice_fields(card, export.card_id(i, card), picture)
            note = export.note(card, export.choice_nt, fields, [picture] if picture else [])
        else:
            note = _two_sided_note(export, i, card)
        if note:
            note.card_id = export.card_id(i, card)
            result.append(note)
    if not result:
        raise AppError("export.no_cards")
    return result


def _two_sided_note(export: _Export, i: int, card) -> Note | None:
    """A front and a back: text, a diagram's label, or a picture (on the front or the
    back). None for a card with nothing to ask or to answer."""
    req, images, pictures = export.req, export.images, export.pictures
    front, back = card.front.strip(), card.back.strip()
    on_back = i in pictures and card.picture_on_back
    if not back or not (front or (i in pictures and not on_back)):  # a picture card may have no front text
        return None
    if i in images:
        nt = export.diagram_nt
    elif i in pictures:
        nt = export.answer_picture_nt if on_back else export.picture_nt
    else:
        if export.typing and tts.has_math(back):
            nt = export.math_nt
        elif req.typing and not typed(back):
            nt = export.untyped_nt
        else:
            nt = export.text_nt
    values = {"Front": field_html(front), "Back": field_html(back), "Info": info(card), **helps(card)}
    media = []
    if "Audio" in nt.fields:
        mp3 = export.audio.get(tts.spoken(card, req.dictation or req.dictation_only))
        values["Audio"] = f"[sound:{mp3.name}]" if mp3 else ""
        media += [mp3] if mp3 else []
    if i in images:
        image, box = images[i]
        values |= diagram_fields(req.cards, card, image, box, req.lesson_id)
        media.append(image)
    elif i in pictures:
        values |= picture_fields(card, pictures[i], export.card_id(i, card))
        media.append(pictures[i])
    return export.note(card, nt, values, media)


# Typed answers ("typing"): at most this many words. A longer one (a sentence, a definition)
# is said in one's own words, not typed again letter by letter (Anki.kt: TYPED_WORDS)
TYPED_WORDS = 4


def typed(back: str) -> bool:
    """An answer asked typed when the lesson's are: short (a form, a word or two)."""
    return len(back.split()) <= TYPED_WORDS


TAG_PREFIX = "notosaurus::"


def lesson_tag(lesson_id: str) -> str:
    """The tag of every note sent for a lesson: its notes can be found again (to delete
    them with the lesson), whatever was changed in them."""
    return f"{TAG_PREFIX}{lesson_id}"


def lesson_notes(req: ExportRequest) -> list[Note]:
    """The notes a lesson gives, as sent (note type, deck, key), without their media:
    to find in Anki the notes sent before they had the lesson's tag."""
    diagrams_: dict[int, tuple[Path, list[float] | None]] = {
        i: (Path("diagram.jpg"), None) for i, c in enumerate(req.cards) if c.mask
    }
    pictures_ = {i: Path("picture.jpg") for i, c in enumerate(req.cards) if c.picture and not c.mask}
    try:
        return notes(req, images=diagrams_, pictures=pictures_)
    except AppError:  # no card
        return []


def guids(notes: list[Note]) -> list[str]:
    """Each note's GUID, the same in every package and in a direct send (through the
    add-on): Anki tells notes apart by GUID, so re-importing a corrected lesson, or a
    package after a direct send, updates the notes instead of duplicating them (as long
    as the front, or a label's place, and the deck stay the same). The same key twice in
    a deck ("le vol": vuelo, robo): numbered."""
    seen: dict[tuple[str, str], int] = {}
    result = []
    for note in notes:
        n = seen[(note.deck, note.key)] = seen.get((note.deck, note.key), -1) + 1
        result.append(genanki.guid_for(note.deck, note.key, *([n] if n else [])))
    return result


def _model(nt: NoteType) -> genanki.Model:
    return genanki.Model(
        model_id(nt),
        nt.name,
        fields=[{"name": f} for f in nt.fields],
        templates=list(nt.templates),
        css=nt.full_css,
        model_type=genanki.Model.CLOZE if nt.cloze else genanki.Model.FRONT_BACK,
    )


def _deck_name(base: str, subdeck: str) -> str:
    """The card's deck: the lesson's, then its part. A part named as the deck's last level
    ("Anglais::School subjects" and "School subjects": the lesson's own title, often as the
    deck was chosen) isn't added again; Anki doesn't tell decks apart by case."""
    base, subdeck = base.strip(), subdeck.strip()
    if not subdeck or base.rsplit("::", 1)[-1].strip().casefold() == subdeck.casefold():
        return base
    return f"{base}::{subdeck}"


def _tag(t: str) -> str:
    return re.sub(r"\s+", "_", t.strip())  # Anki tags cannot contain spaces


def build_apkg(
    req: ExportRequest,
    audio: dict[str, Path] | None = None,
    images: dict[int, tuple[Path, list[float] | None]] | None = None,
    pictures: dict[int, Path] | None = None,
    extra_tags: dict[str, list[str]] | None = None,
) -> str:
    """Write the package to a temporary file and return its path.

    `audio` maps a card back to its mp3 (edge-tts voice); backs missing from it get no
    sound. `images`: see `notes`.
    """
    decks: dict[str, genanki.Deck] = {}
    models: dict[NoteType, genanki.Model] = {}
    all_notes = notes(req, audio, images, pictures, extra_tags)
    for note, guid in zip(all_notes, guids(all_notes), strict=True):
        deck = decks.setdefault(note.deck, genanki.Deck(_stable_id("deck", note.deck), note.deck))
        deck.add_note(
            genanki.Note(
                model=models.setdefault(note.nt, _model(note.nt)),
                fields=[note.fields[f] for f in note.nt.fields],
                tags=note.tags,
                guid=guid,
            )
        )
    media = sorted({str(path) for n in all_notes for path in n.media})
    fd, path = tempfile.mkstemp(suffix=".apkg")
    os.close(fd)
    genanki.Package(list(decks.values()), media_files=media).write_to_file(path)
    return path
