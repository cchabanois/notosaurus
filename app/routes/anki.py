import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Header

from .. import access, ankiconnect, decks, exams, lessons, media
from ..anki import notes
from ..models import ExportRequest
from .common import Step, stepped
from .generation import NDJSON

log = logging.getLogger("notosaurus")

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
async def anki_send(req: ExportRequest, background: BackgroundTasks, accept: str | None = Header(None)):
    """The lesson's cards sent to Anki. Asked for as application/x-ndjson: its steps as
    they go, then the answer (see _steps)."""
    if NDJSON in (accept or ""):
        return stepped(lambda step: _send(req, background, step), "Sending")
    return await _send(req, background)


async def _send(req: ExportRequest, background: BackgroundTasks, step: Step | None = None) -> dict:
    lesson = await access.lesson(req.lesson_id)  # another profile's private lesson doesn't exist for this one
    saved = lesson if lesson and await access.is_owner(lesson) else None  # someone else's: sent, not changed

    def sound(done: int, total: int) -> None:
        if step:
            step({"step": "sounds", "done": done, "total": total})

    audio, failures = await media.card_audio(req, background, sound)
    if step:
        step({"step": "cards"})
    profile = await ankiconnect.active_profile() or ""
    known = lesson.anki_notes.get(profile, {}) if lesson else {}
    tags = await asyncio.to_thread(exams.card_tags, lesson.id, [c.id for c in req.cards]) if lesson else {}
    sent = notes(req, audio, media.diagram_images(req, lesson), media.card_pictures(req, lesson), tags)
    result = await ankiconnect.send(sent, known)
    answer = {**result.__dict__, "audio_failures": failures}
    answer.pop("note_ids")  # the lesson keeps them, the page needn't
    if saved:
        await asyncio.to_thread(lessons.update, saved.id, req, exported=True)
        await asyncio.to_thread(lessons.set_anki_notes, saved.id, profile, result.note_ids)
        # Its notes no card updated (cards deleted, or remade): the page offers to delete them
        answer["leftovers"] = await ankiconnect.leftovers(saved.id, set(result.note_ids.values()))
    return answer
