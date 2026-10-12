from fastapi import APIRouter, BackgroundTasks

from .. import access, ankiconnect, decks, lessons, media
from ..anki import notes
from ..models import ExportRequest

router = APIRouter()


# --- Direct send to Anki (AnkiConnect) ----------------------------------------


@router.get("/api/decks")
async def deck_names() -> list[str]:
    """The decks that already exist (Anki's and the lessons'), offered for the deck name."""
    return await decks.known(await ankiconnect.active_profile())


@router.get("/api/anki/status")
async def anki_status() -> dict:
    try:
        return {
            "available": True,
            "version": await ankiconnect.version(),
            "profile": await ankiconnect.active_profile(),
            "sync": await ankiconnect.sync_configured(),  # logged in to AnkiWeb (None: unknown)
        }
    except ankiconnect.AnkiConnectError as e:
        return {"available": False, "error": e.detail()}


@router.post("/api/anki/send")
async def anki_send(req: ExportRequest, background: BackgroundTasks) -> dict:
    lesson = await access.lesson(req.lesson_id)  # another profile's private lesson doesn't exist for this one
    saved = lesson if lesson and await access.is_owner(lesson) else None  # someone else's: sent, not changed
    audio, failures = await media.card_audio(req, background)
    profile = await ankiconnect.active_profile() or ""
    known = lesson.anki_notes.get(profile, {}) if lesson else {}
    sent = notes(req, audio, media.diagram_images(req, lesson), media.card_pictures(req, lesson))
    result = await ankiconnect.send(sent, known)
    answer = {**result.__dict__, "audio_failures": failures}
    answer.pop("note_ids")  # the lesson keeps them, the page needn't
    if saved:
        lessons.update(saved.id, req, exported=True)
        lessons.set_anki_notes(saved.id, profile, result.note_ids)
        # Its notes no card updated (cards deleted, or remade): the page offers to delete them
        answer["leftovers"] = await ankiconnect.leftovers(saved.id, set(result.note_ids.values()))
    return answer
