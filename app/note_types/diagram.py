"""Diagram labels (image occlusion): the diagram with its labels hidden, one asked."""

from pathlib import Path

from notosaurus_core import diagrams, tts

from .common import BACK_INFO, CSS, HELP_FIELDS, NoteType, fix_link, typed, variant, with_context

# The masks are HTML over the image, placed in % of its size.
DIAGRAM_CSS = """\
.notosaurus-diagram { position: relative; display: inline-block; max-width: 100%; line-height: 0; }
.notosaurus-diagram img { display: block; }
.notosaurus-mask {
  position: absolute; box-sizing: border-box; display: flex; align-items: center; justify-content: center;
  overflow: hidden; line-height: 1; font-size: 13px; font-weight: 700;
  background: #ffe08a; border: 2px solid #c77700; border-radius: 3px; color: #3d2b00;
}
.notosaurus-mask.target { background: #ff7a59; border-color: #b3261e; color: #fff; }
.notosaurus-mask.revealed { background: transparent; border: 3px solid #1b873f; }
"""


def diagram_note_type(voice: str, typing: bool = False) -> NoteType:
    """A diagram label: the diagram with every label hidden and the question, then the
    answer with that label shown again. One image per diagram, shared by its cards;
    the masks are HTML ("Masks", "AnswerMasks"). "Id" (lesson, photo, label number)
    tells which note an update is for, as the question alone ("What is (1)?") repeats."""
    anki_tts = tts.is_anki_locale(voice)
    sound = f"{{{{tts {voice}:Back}}}}" if anki_tts else "{{Audio}}"
    info = BACK_INFO + fix_link("Id")
    templates = (
        {
            "name": "Schéma",
            "qfmt": '<div class="notosaurus-diagram">{{Image}}{{Masks}}</div><div>{{Front}}</div>',
            "afmt": '<div class="notosaurus-diagram">{{Image}}{{AnswerMasks}}</div><div>{{Front}}</div>'
            f'<hr id="answer">{{{{Back}}}}{sound}{info}',
        },
    )
    if typing:
        templates = (typed(templates[0], "Back"),)
    fields = ["Front", "Back", "Info"] + ([] if anki_tts else ["Audio"]) + ["Image", "Masks", "AnswerMasks", "Id"]
    fields += HELP_FIELDS
    kind = f"labels TTS Anki {voice}" if anki_tts else "labels audio"
    name, option = variant("Notosaurus légendes", typing, False)
    name = f"{name} ({kind.removeprefix('labels ')})"
    return NoteType(name, kind, tuple(fields), with_context(templates), css=CSS + DIAGRAM_CSS, key="Id", variant=option)


def diagram_fields(cards: list, card, image: Path, box: list[float] | None, lesson_id: str | None) -> dict[str, str]:
    """A label's own fields: its diagram (the image and crop shared by the labels of its
    photo, among `cards`) with every label of the photo masked, this one asked."""
    page = [c.mask for c in cards if c.mask and c.mask.page == card.mask.page]
    return {
        "Image": f'<img src="{image.name}">',
        "Masks": diagrams.masks_html(page, card.mask.n, reveal=False, box=box),
        "AnswerMasks": diagrams.masks_html(page, card.mask.n, reveal=True, box=box),
        "Id": f"{lesson_id or ''}:{card.mask.page}:{card.mask.n}",
    }
