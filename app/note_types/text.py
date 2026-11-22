"""Text cards (recto/verso): with their options, the reverse card, the typed answer and
the dictation (with the other cards, or alone); a picture or figure on any of them."""

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
    fix_link,
    sound_kind,
    sounds,
    typed,
    variant,
    versioned,
    with_context,
)


def note_type(
    voice: str, reverse: bool, typing: bool = False, dictation: bool = False, dictation_only: bool = False
) -> NoteType:
    # A sound a side, the question's ("FrontAudio") and the answer's ("Audio"), either empty when
    # that side isn't read (Card.sound), in two ways (common.sounds):
    # - Anki locale ("es_ES"): the field's text, {{tts}}, spoken by the device's speech engine;
    # - edge-tts voice: embedded mp3, in the field ([sound:…]).
    # Each combination gets its own note type (stable id, distinct name), so we
    # never overwrite a note type the user already has.
    # A picture or figure, if the card has one, whatever else it is: on the question
    # (PICTURE) or with the answer (BACK_PICTURE), the sound where the card says it.
    anki_tts = tts.is_anki_locale(voice)
    front_sound, sound = sounds(anki_tts, voice)
    info = BACK_INFO + fix_link("Id", fallback="Front")
    templates = [
        {
            "name": "Front → Back",
            "qfmt": f"{PICTURE}{{{{Front}}}}{front_sound}",
            "afmt": f'{{{{FrontSide}}}}<hr id="answer">{{{{Back}}}}{sound}{BACK_PICTURE}{info}',
        }
    ]
    if reverse:
        templates.append(
            {
                "name": "Back → Front",
                "qfmt": f"{{{{Back}}}}{sound}",
                "afmt": f'{{{{FrontSide}}}}<hr id="answer">{PICTURE}{{{{Front}}}}{front_sound}{BACK_PICTURE}{info}',
            }
        )
    if typing:
        templates = [typed(templates[0], "Back"), *[typed(t, "Front") for t in templates[1:]]]
    dictation = (dictation or dictation_only) and bool(voice)  # nothing to hear without a voice
    if dictation:
        # Hear the back, write it; the answer shows the comparison and what it means. Its
        # picture on the question: what the word is, never how it is written
        heard = f'<div class="dictation">🎧</div>{sound}{PICTURE}{{{{type:Back}}}}'
        dictated = {
            "name": "Dictation",
            "qfmt": heard,
            "afmt": f'{heard}<hr id="answer">{{{{Front}}}}{BACK_PICTURE}{info}',
        }
        if dictation_only:  # alone, its front shown too: the sentence with its blank (or "Sentence 3")
            # its front a block of its own: the answer's comparison never glued to it (TYP-10)
            heard = f'<div class="dictation">🎧</div>{sound}{PICTURE}<div>{{{{Front}}}}</div>{{{{type:Back}}}}'
            dictated = {"name": "Dictation", "qfmt": heard, "afmt": f'{heard}<hr id="answer">{BACK_PICTURE}{info}'}
        templates = [dictated] if dictation_only else [*templates, dictated]
    fields = ["Front", "Back", "Info", *SOUND_FIELDS]  # a sound a side, either voice (common.sounds)
    kind = sound_kind(anki_tts, voice)
    # The picture's fields after the others: where a note type made before them gets them
    # (ankiconnect._bring_up_to_date adds a field at the end), the same order everywhere
    fields += [*HELP_FIELDS, "Picture", "BackPicture", "Id", SOURCE_FIELD]
    if dictation and dictation_only:  # its own note type: the dictation card alone, whatever else is on
        name, option, reverse = "Notosaurus dictation", "dictation-only", False
    else:
        name, option = variant("Notosaurus front/back" + (" + reverse" if reverse else ""), typing, dictation)
    templates = with_context(templates)
    return NoteType(
        versioned(f"{name} ({kind})"),
        kind,
        tuple(fields),
        templates,
        css=CSS + PICTURE_CSS,
        variant=option,
        reverse=reverse,
    )
