from fastapi import APIRouter, BackgroundTasks

from .. import ankiconnect, decks, lessons
from ..anki import notes
from ..models import ExportRequest
from .common import _card_audio, _diagram_images, _is_owner, _lesson, _pictures

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
    lesson = await _lesson(req.lesson_id)  # another profile's private lesson doesn't exist for this one
    save = lesson and await _is_owner(lesson)  # someone else's lesson: sent, not changed
    audio, failures = await _card_audio(req, background)
    result = await ankiconnect.send(notes(req, audio, _diagram_images(req, lesson), _pictures(req, lesson)))
    if save:
        lessons.update(lesson.id, req, exported=True)
    return {**result.__dict__, "audio_failures": failures}
