import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, BackgroundTasks, Header
from fastapi.responses import StreamingResponse

from notosaurus_core.errors import loggable

from .. import access, ankiconnect, decks, exams, lessons, media
from ..anki import notes
from ..errors import AppError
from ..models import ExportRequest
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
        return _steps(lambda step: _send(req, background, step))
    return await _send(req, background)


Step = Callable[[dict], None]
_sending: set[asyncio.Task] = set()  # sends under way, kept until done


def _steps(work: Callable[[Step], Awaitable[dict]]) -> StreamingResponse:
    """A send told as it goes, one JSON per line: {"step": "sounds", "done", "total"}
    as the backs' sounds are made, {"step": "cards"} as the notes go to Anki, then
    {"result": …} (the answer without the stream) or {"error": {"code", "params"}}.
    The send goes on if the page goes away meanwhile."""
    queue: asyncio.Queue = asyncio.Queue()

    async def run() -> None:
        try:
            queue.put_nowait({"result": await work(queue.put_nowait)})
        except AppError as e:
            queue.put_nowait({"error": e.detail()})
        except Exception as e:
            log.error("Sending failed: %s", loggable(e))
            queue.put_nowait({"error": {"code": "internal", "params": {}}})
        finally:
            queue.put_nowait(None)

    task = asyncio.create_task(run())
    _sending.add(task)
    task.add_done_callback(_sending.discard)

    async def lines():
        while (item := await queue.get()) is not None:
            yield json.dumps(item, ensure_ascii=False) + "\n"

    return StreamingResponse(lines(), media_type=NDJSON)


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
