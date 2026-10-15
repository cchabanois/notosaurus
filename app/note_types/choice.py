"""Multiple-choice and true/false cards: the options in plain HTML, no script."""

import random
from pathlib import Path

from .common import BACK_INFO, CSS, HELP_FIELDS, SOURCE_FIELD, NoteType, field_html, fix_link, helps, info, stable_id
from .picture import PICTURE_CSS, source

# The options in a list (A, B, C…), the right one marked on the answer
CHOICE_CSS = """\
.notosaurus-choices {
  display: inline-block; margin: 12px auto 0; padding-left: 1.8em; text-align: left; list-style: upper-alpha;
}
.notosaurus-choices li { margin: 6px 0; }
.notosaurus-choices li.right { color: #1b873f; font-weight: 700; }
.notosaurus-choices li.right::after { content: " ✔"; }
.notosaurus-choices li.wrong { opacity: .5; }
"""


def choice_order(card) -> list[str]:
    """The options as Anki shows them: always the same order for a card (on its question
    and its answer, from one review to the next), the right one anywhere. Two options
    (true/false): alphabetical, the same for every card."""
    options = list(dict.fromkeys(o.strip() for o in [card.back, *card.choices] if o.strip()))
    if len(options) == 2:
        return sorted(options, key=str.casefold)
    random.Random(stable_id("choices", card.front.strip())).shuffle(options)
    return options


def _choices_html(card, reveal: bool) -> str:
    right = card.back.strip()
    items = []
    for option in choice_order(card):
        mark = (' class="right"' if option == right else ' class="wrong"') if reveal else ""
        items.append(f"<li{mark}>{field_html(option)}</li>")
    return f'<ol class="notosaurus-choices">{"".join(items)}</ol>'


def choice_note_type() -> NoteType:
    """A multiple-choice or true/false card: the question and its options, then the
    options again with the right one marked. In plain HTML, no script: the same on every
    Anki. The options' order is fixed per card ("Choices", "AnswerChoices"). Its picture
    or figure, if any, goes on the question ("Picture") or with the answer
    ("BackPicture"). "Id" (the card's own id) tells which note an update is for."""
    info = BACK_INFO + fix_link("Id")
    picture = '{{#Picture}}<div class="notosaurus-picture">{{Picture}}</div>{{/Picture}}'
    back_picture = '{{#BackPicture}}<div class="notosaurus-picture">{{BackPicture}}</div>{{/BackPicture}}'
    question = f"{picture}<div>{{{{Question}}}}</div>"
    templates = (
        {
            "name": "QCM",
            "qfmt": f"{question}{{{{Choices}}}}",
            "afmt": f'{question}<hr id="answer">{{{{AnswerChoices}}}}{back_picture}{info}',
        },
    )
    fields = (
        "Question",
        "Answer",
        "Choices",
        "AnswerChoices",
        "Picture",
        "BackPicture",
        "Info",
        "Id",
        *HELP_FIELDS,
        SOURCE_FIELD,
    )
    css = CSS + PICTURE_CSS + CHOICE_CSS
    return NoteType("Notosaurus QCM", "choice", fields, templates, css=css, key="Id")


def choice_fields(card, card_id: str, picture_file: Path | None) -> dict[str, str]:
    """Not typed nor heard: the options are read. Its picture (`picture_file`), if any,
    on the question or with the answer."""
    picture = f'<img src="{picture_file.name}">' if picture_file else ""
    return {
        "Question": field_html(card.front.strip()),
        "Answer": field_html(card.back.strip()),
        "Choices": _choices_html(card, reveal=False),
        "AnswerChoices": _choices_html(card, reveal=True),
        "Picture": "" if card.picture_on_back else picture,
        SOURCE_FIELD: source(card) if picture_file else "",
        "BackPicture": picture if card.picture_on_back else "",
        "Info": info(card),
        "Id": card_id,
        **helps(card),
    }
