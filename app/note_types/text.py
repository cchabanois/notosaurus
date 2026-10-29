"""Text cards (recto/verso): with their options, the reverse card, the typed answer and
the dictation (with the other cards, or alone)."""

from notosaurus_core import tts

from .common import BACK_INFO, HELP_FIELDS, NoteType, fix_link, typed, variant, with_context


def note_type(
    voice: str, reverse: bool, typing: bool = False, dictation: bool = False, dictation_only: bool = False
) -> NoteType:
    # Two ways to read the back aloud:
    # - Anki locale ("es_ES"): {{tts}} tag, spoken by the device's speech engine;
    # - edge-tts voice: embedded mp3, in an "Audio" field ([sound:…]).
    # Each combination gets its own note type (stable id, distinct name), so we
    # never overwrite a note type the user already has.
    anki_tts = tts.is_anki_locale(voice)
    sound = f"{{{{tts {voice}:Back}}}}" if anki_tts else "{{Audio}}"
    info = BACK_INFO + fix_link("Front")
    templates = [
        {
            "name": "Recto → Verso",
            "qfmt": "{{Front}}",
            "afmt": f'{{{{FrontSide}}}}<hr id="answer">{{{{Back}}}}{sound}{info}',
        }
    ]
    if reverse:
        templates.append(
            {
                "name": "Verso → Recto",
                "qfmt": f"{{{{Back}}}}{sound}",
                "afmt": f'{{{{FrontSide}}}}<hr id="answer">{{{{Front}}}}{info}',
            }
        )
    if typing:
        templates = [typed(templates[0], "Back"), *[typed(t, "Front") for t in templates[1:]]]
    dictation = (dictation or dictation_only) and bool(voice)  # nothing to hear without a voice
    if dictation:
        # Hear the back, write it; the answer shows the comparison and what it means
        heard = f'<div class="dictation">🎧</div>{sound}{{{{type:Back}}}}'
        dictated = {"name": "Dictée", "qfmt": heard, "afmt": f'{heard}<hr id="answer">{{{{Front}}}}{info}'}
        if dictation_only:  # alone, its front shown too: the sentence with its blank (or "Sentence 3")
            heard = f'<div class="dictation">🎧</div>{sound}{{{{Front}}}}{{{{type:Back}}}}'
            dictated = {"name": "Dictée", "qfmt": heard, "afmt": f'{heard}<hr id="answer">{info}'}
        templates = [dictated] if dictation_only else [*templates, dictated]
    fields = ["Front", "Back", "Info"]
    if anki_tts:
        kind = f"TTS Anki {voice}"
    else:
        fields.append("Audio")
        kind = "audio"
    fields += HELP_FIELDS
    if dictation and dictation_only:  # its own note type: the dictation card alone, whatever else is on
        name, option, reverse = "Notosaurus dictée", "dictation-only", False
    else:
        name, option = variant("Notosaurus recto/verso" + (" + inverse" if reverse else ""), typing, dictation)
    return NoteType(f"{name} ({kind})", kind, tuple(fields), with_context(templates), variant=option, reverse=reverse)
