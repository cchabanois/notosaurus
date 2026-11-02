"""What every note type shares: the base CSS, the answer's helps, the ids, the
NoteType itself, and the field values all cards fill the same way."""

import hashlib
import html
from collections.abc import Mapping
from dataclasses import dataclass

CSS = """\
.card { font-family: system-ui, sans-serif; font-size: 26px; text-align: center; }
.info { font-size: 18px; color: #777; margin-top: 12px; }
.card img { max-width: 100%; height: auto; }
.dictation { font-size: 40px; }
.notosaurus-help {
  max-width: 32em; margin: 10px auto 0; padding: 4px 10px; border-left: 3px solid #8bb8c4;
  font-size: 18px; color: #555; text-align: left;
}
.nightMode .notosaurus-help { color: #bbb; }
.notosaurus-fix { margin-top: 16px; font-size: 14px; }
.notosaurus-fix a { color: #8bb8c4; text-decoration: none; }
.notosaurus-context { font-size: 14px; color: #888; margin-bottom: 12px; }
"""

# On the back, under the info: the helps asked for at generation (why the answer is the
# answer, a way to remember it), each only when the AI wrote one
BACK_INFO = (
    '{{#Info}}<div class="info">{{Info}}</div>{{/Info}}'
    '{{#Explanation}}<div class="notosaurus-help">💬 {{Explanation}}</div>{{/Explanation}}'
    '{{#Mnemonic}}<div class="notosaurus-help">🧠 {{Mnemonic}}</div>{{/Mnemonic}}'
)
HELP_FIELDS = ("Explanation", "Mnemonic")

# Under the back: "✎ Notosaurus", the card opened in Notosaurus to correct it. Built on
# the card from what the note holds already (AnkiDroid can't add a field to a note type
# it has): the lesson from its tag, the card from the note's key field. On Android, a
# short page of the documentation (FIX_PAGE) that opens the app: AnkiDroid lets a card
# open http(s) links, and blocks every other scheme unless a setting allows it. On the
# computer, the page served by the add-on. Nowhere else (AnkiWeb, AnkiMobile): hidden.
FIX_PAGE = "https://cchabanois.github.io/notosaurus/fix/"  # docs/public/fix/index.html
FIX_SCRIPT = f"""<script>(function(){{var A=document.querySelectorAll("a.nfix:not([data-done])");\
for(var i=0;i<A.length;i++){{var a=A[i];a.dataset.done="1";\
var m=/(?:^|\\s)notosaurus::(\\S+)/.exec(a.dataset.tags||"");\
var c=document.documentElement.className+" "+document.body.className,\
android=/\\bandroid\\b/.test(c)||/Android/.test(navigator.userAgent),\
desktop=typeof pycmd==="function"||/\\b(win|mac|linux)\\b/.test(c);\
if(!m||!(android||desktop)){{a.parentNode.style.display="none";continue;}}\
var q="lesson="+encodeURIComponent(m[1])+"&key="+encodeURIComponent(a.dataset.key||"");\
a.href=(android?"{FIX_PAGE}?":"http://localhost:8000/?")+q;}}}})();</script>"""


def fix_link(key: str, fallback: str = "") -> str:
    """The back's "✎ Notosaurus" link (FIX_SCRIPT): `key`, the note's field telling the card
    ("Front": its text; "Id": its id); `fallback`, the field when that one is empty (a note
    sent before it had an "Id")."""
    told = f"{{{{text:{key}}}}}"
    if fallback:
        told = f"{{{{#{key}}}}}{told}{{{{/{key}}}}}{{{{^{key}}}}}{{{{text:{fallback}}}}}{{{{/{key}}}}}"
    link = f'<a class="nfix" href="#" data-key="{told}" data-tags="{{{{Tags}}}}">✎ Notosaurus</a>'
    return f'<div class="notosaurus-fix">{link}</div>{FIX_SCRIPT}'


# On the question, small: the card's deck ("Anglais › Character traits"), which the card
# alone doesn't say: the subject (for a language, the one to answer in) and the lesson.
# Anki's own {{Deck}} (a filtered deck's card: its home deck), so nothing to add to the
# notes (AnkiDroid can't add a field to a note type it has): the templates only, brought
# up to date by their signature. "::" shown as " › " where the card runs scripts.
CONTEXT = (
    '<div class="notosaurus-context">{{Deck}}</div>'
    '<script>(function(){var D=document.querySelectorAll(".notosaurus-context:not([data-done])");'
    'for(var i=0;i<D.length;i++){D[i].dataset.done="1";'
    'D[i].textContent=D[i].textContent.split("::").join(" › ");}})();</script>'
)


def with_context(templates) -> tuple[dict, ...]:
    """The templates with the card's deck on the question (CONTEXT), and on an answer that
    doesn't repeat the question ({{FrontSide}})."""
    return tuple(
        {
            **t,
            "qfmt": CONTEXT + t["qfmt"],
            "afmt": t["afmt"] if "{{FrontSide}}" in t["afmt"] else CONTEXT + t["afmt"],
        }
        for t in templates
    )


# Where a card's picture comes from (models.PictureSource): kept with the note, never shown
# (no card template uses it). Written by the computer; the Android app keeps it as it is
SOURCE_FIELD = "Source"

# A card's picture or figure, if any: on the question ("Picture") or with the answer
# ("BackPicture"), whatever the card's kind (text, typed, reverse, dictation, multiple choice)
PICTURE = '{{#Picture}}<div class="notosaurus-picture">{{Picture}}</div>{{/Picture}}'
BACK_PICTURE = '{{#BackPicture}}<div class="notosaurus-picture">{{BackPicture}}</div>{{/BackPicture}}'
PICTURE_CSS = """\
.notosaurus-picture img { max-width: min(100%, 320px); max-height: 50vh; border-radius: 12px; }
"""


def stable_id(*parts: str) -> int:
    """Deterministic id that fits in the 31 bits Anki expects."""
    digest = hashlib.sha256("|".join(parts).encode()).digest()
    return int.from_bytes(digest[:4], "big") >> 1


@dataclass(frozen=True)
class NoteType:
    name: str
    kind: str
    fields: tuple[str, ...]
    templates: tuple[dict, ...]  # {"name", "qfmt", "afmt"}
    css: str = CSS
    key: str = "Id"  # field telling which note an update is for: the card's id (Export.card_id)
    cloze: bool = False  # Anki makes one card per gap number
    variant: str = ""  # typed answer, dictation: part of the note type's id
    reverse: bool = False  # with the reverse card: part of the note type's id

    @property
    def family(self) -> str:
        return family(self.name)

    @property
    def signature(self) -> str:
        """What the note type is made of (fields, card templates, CSS), in 12 characters."""
        templates = [f"{t['name']}\x1e{t['qfmt']}\x1e{t['afmt']}" for t in self.templates]
        parts = [self.name, str(self.cloze), *self.fields, *templates, self.css]
        return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:12]

    @property
    def full_css(self) -> str:
        """Its CSS, signed: a note type in Anki without today's signature was made by an
        older Notosaurus (or before signatures) and is brought up to date at the next
        send. Changed by hand in Anki, it is replaced then too: copy it to change it."""
        return f"{self.css}\n/* Notosaurus note type, version {self.signature}: updated by Notosaurus */\n"

    def __hash__(self) -> int:
        return hash(self.name)


# Note types of a family hold the same kind of card; their options (voice, reverse,
# typed answer, dictation) differ. A note can change type within its family.
# Their names in English, the same on every device whatever its language (two names, two
# note types: a lesson sent from both would make its notes twice). In French before 1.1.0:
# those still known, their notes moved to today's (FORMER_TEMPLATES their cards).
FAMILIES = {
    "Notosaurus front/back": "text",
    "Notosaurus dictation": "text",  # the dictation card alone: the same notes
    "Notosaurus labels": "diagram",
    "Notosaurus cloze": "cloze",
    "Notosaurus multiple choice": "choice",
    "Notosaurus recto/verso": "text",
    "Notosaurus dictée": "text",
    "Notosaurus légendes": "diagram",
    "Notosaurus image": "picture",
    "Notosaurus texte à trous": "cloze",
    "Notosaurus QCM": "choice",
}

# The cards of the note types before 1.1.0, by their name then: a note moved to today's keeps
# each card (its review history) when its name is the same; renamed first (ankiconnect)
FORMER_TEMPLATES = {
    "Recto → Verso": "Front → Back",
    "Verso → Recto": "Back → Front",
    "Dictée": "Dictation",
    "Schéma": "Diagram",
    "Texte à trous": "Cloze",
    "QCM": "Multiple choice",
}


# A note type's fields never change under its name: AnkiDroid can't add one to a note type it
# has (a phone alone would keep it lacking them for good, its cards without their pictures).
# Its family's fields changed, its version goes up and its name with it ("… v2"), a new note
# type on every device; the computer moves its notes there (its family's: _change_type), their
# history kept. Without a suffix: version 1, 1.0.0's. tests/test_note_types.py keeps each
# version's fields: changing them without a new version fails it.
VERSIONS = {"text": 2, "choice": 2, "diagram": 2, "cloze": 2}  # 2: named in English, and text's, choice's fields


def versioned(name: str) -> str:
    """The note type's name with its family's version: "Notosaurus multiple choice v2" ("" for 1)."""
    version = VERSIONS[family(name)]
    return name if version == 1 else f"{name} v{version}"


def family(note_type_name: str) -> str:
    """ "text", "diagram", "picture", "cloze", "choice", or "" for a note type not Notosaurus's."""
    return next((f for prefix, f in FAMILIES.items() if note_type_name.startswith(prefix)), "")


def key_of(nt: NoteType, values: Mapping[str, str]) -> str:
    """The note's key, as its fields' `values` give it: its note type's key field, the card's
    id (never its front: a corrected front, two cards of the same front, dictations whose
    fronts are all the blank, "…", stay their own notes). Notes sent with 1.0.0 were keyed
    by their front: sent again, they come anew (1.1.0's notes)."""
    return values.get(nt.key, "")


def model_id(nt: NoteType) -> int:
    """The note type's id, the same in every package and in a direct send (through the
    add-on): Anki tells note types apart by id, so they never come twice. Reverse card
    or not, then the options: unique per note type. (Before the dictation card, "two
    templates" meant the reverse card: same ids as then.)"""
    return stable_id("model", nt.kind, str(nt.reverse), *([nt.variant] if nt.variant else []))


def typed(template: dict, field: str) -> dict:
    """The template asking to type `field`: a box on the question, Anki's letter by
    letter comparison in its place on the answer. The answer repeats the question
    (not {{FrontSide}}, which would show the box twice)."""
    question = template["qfmt"]
    answer = template["afmt"].replace("{{FrontSide}}", question).replace(f"{{{{{field}}}}}", f"{{{{type:{field}}}}}", 1)
    return {**template, "qfmt": f"{question}{{{{type:{field}}}}}", "afmt": answer}


def variant(name: str, typing: bool, dictation: bool) -> tuple[str, str]:
    """The note type's name and variant ("" for the plain one: its id is unchanged)."""
    parts = [p for p, on in (("typing", typing), ("dictation", dictation)) if on]
    name += (" typed" if typing else "") + (" + dictation" if dictation else "")
    return name, "+".join(parts)


def field_html(text: str) -> str:
    """A card's text as an Anki field: escaped, its line breaks kept."""
    return html.escape(text).replace("\n", "<br>")


def info(card) -> str:
    """The Info field: the card's info, then its "did you know" (💡, in italics). Styled
    inline: the note types already in Anki keep their own CSS."""
    info, fact = field_html(card.info.strip()), card.fun_fact.strip()
    if not fact:
        return info
    style = "margin-top:8px;font-style:italic"
    return f'{info}<div style="{style}">💡 {field_html(fact)}</div>'


def helps(card) -> dict[str, str]:
    return {"Explanation": field_html(card.explanation.strip()), "Mnemonic": field_html(card.mnemonic.strip())}
