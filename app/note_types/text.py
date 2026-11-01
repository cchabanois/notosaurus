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
    SOURCE_FIELD,
    NoteType,
    fix_link,
    typed,
    variant,
    with_context,
)


def note_type(
    voice: str, reverse: bool, typing: bool = False, dictation: bool = False, dictation_only: bool = False
) -> NoteType:
    # Two ways to read the back aloud:
    # - Anki locale ("es_ES"): {{tts}} tag, spoken by the device's speech engine;
    # - edge-tts voice: embedded mp3, in an "Audio" field ([sound:…]).
    # Each combination gets its own note type (stable id, distinct name), so we
    # never overwrite a note type the user already has.
    # A picture or figure, if the card has one, whatever else it is: on the question
    # (PICTURE) or with the answer (BACK_PICTURE), the sound where the card says it.
    anki_tts = tts.is_anki_locale(voice)
    sound = f"{{{{tts {voice}:Back}}}}" if anki_tts else "{{Audio}}"
    info = BACK_INFO + fix_link("Id", fallback="Front")
    templates = [
        {
            "name": "Recto → Verso",
            "qfmt": f"{PICTURE}{{{{Front}}}}",
            "afmt": f'{{{{FrontSide}}}}<hr id="answer">{{{{Back}}}}{sound}{BACK_PICTURE}{info}',
        }
    ]
    if reverse:
        templates.append(
            {
                "name": "Verso → Recto",
                "qfmt": f"{{{{Back}}}}{sound}",
                "afmt": f'{{{{FrontSide}}}}<hr id="answer">{PICTURE}{{{{Front}}}}{BACK_PICTURE}{info}',
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
            "name": "Dictée",
            "qfmt": heard,
            "afmt": f'{heard}<hr id="answer">{{{{Front}}}}{BACK_PICTURE}{info}',
        }
        if dictation_only:  # alone, its front shown too: the sentence with its blank (or "Sentence 3")
            heard = f'<div class="dictation">🎧</div>{sound}{PICTURE}{{{{Front}}}}{{{{type:Back}}}}'
            dictated = {"name": "Dictée", "qfmt": heard, "afmt": f'{heard}<hr id="answer">{BACK_PICTURE}{info}'}
        templates = [dictated] if dictation_only else [*templates, dictated]
    fields = ["Front", "Back", "Info"]
    if anki_tts:
        kind = f"TTS Anki {voice}"
    else:
        fields.append("Audio")
        kind = "audio"
    # The picture's fields after the others: where a note type made before them gets them
    # (ankiconnect._bring_up_to_date adds a field at the end), the same order everywhere
    fields += [*HELP_FIELDS, "Picture", "BackPicture", "Id", SOURCE_FIELD]
    if dictation and dictation_only:  # its own note type: the dictation card alone, whatever else is on
        name, option, reverse = "Notosaurus dictée", "dictation-only", False
    else:
        name, option = variant("Notosaurus recto/verso" + (" + inverse" if reverse else ""), typing, dictation)
    templates = with_context(templates)
    return NoteType(
        f"{name} ({kind})",
        kind,
        tuple(fields),
        templates,
        css=CSS + PICTURE_CSS,
        variant=option,
        reverse=reverse,
        picture_key="Id",
    )
